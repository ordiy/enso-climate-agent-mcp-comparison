"""
ENSO MCP Server
===============
功能：从香港天文台抓取最新 ENSO 监测数据，使用 Gemini 3 Flash 模型分析，
      通过 MCP 协议将分析报告返回给 Cursor / Claude 等 AI Agent。

架构概览：
    Cursor (AI Agent)
        │  JSON-RPC: tools/call { name: "analyze_enso_situation" }
        ▼  stdin (stdio 传输)
    enso_server.py
        │
        ├─ asyncio.gather() ──┬── httpx GET 中文页 ──► HKO 服务器
        │   (并发，约 5s)     └── httpx GET 英文页 ──► HKO 服务器
        │
        ├─ BeautifulSoup 清洗 HTML → 纯文本
        │
        ├─ asyncio.to_thread() ── genai.generate_content() ──► Gemini API
        │   (线程池，约 10s)
        │
        └─ TextContent(分析报告)
        │  stdout
        ▼
    Cursor 展示分析报告
"""

import asyncio
import os
from pathlib import Path

# httpx：原生支持 async/await 的 HTTP 客户端，适合异步架构
# 不使用 requests，因为 requests 是同步库，会阻塞事件循环
import httpx

# BeautifulSoup：专为 HTML 解析设计，健壮处理乱码/嵌套结构
# lxml 作为解析器，速度比 html.parser 快约 3 倍
from bs4 import BeautifulSoup

# google.genai：Gemini 新版 SDK（旧版 google.generativeai 已废弃）
from google import genai
from dotenv import load_dotenv

# MCP Server 核心：管理工具注册、请求路由、协议握手
from mcp.server import Server

# stdio_server：通过 stdin/stdout 与 Cursor 通信，是本地 MCP 的标准传输方式
from mcp.server.stdio import stdio_server

# Tool：描述工具元数据（名称、描述、参数 Schema），供 AI Agent 决策时使用
# TextContent：MCP 协议规定的标准文本返回类型
from mcp.types import Tool, TextContent


# ── 常量配置 ──────────────────────────────────────────────────────────────────
#
# 数据源选择说明：
#   经过分析，HKO 网站有两个关键页面：
#   - enso-front.htm：门户首页，静态内容只有 429 字，数据是动态加载的
#   - enso-latest.htm：最新状况页，包含完整文字报告（中文 513 字 + 英文 1349 字）
#   因此使用 enso-latest.htm 作为数据源
#
# 同时抓取中英文两个版本的原因：
#   - 中文版（繁体）：权威发布语言，专业术语准确
#   - 英文版：措辞更详细，数值描述更精确
#   双语互补，给 Gemini 提供更充分的信息，提升分析质量
HKO_URL_ZH = "https://www.hko.gov.hk/tc/lrf/enso/enso-latest.htm"
HKO_URL_EN = "https://www.hko.gov.hk/en/lrf/enso/enso-latest.htm"

# 从项目同目录 .env 加载环境变量（若存在）
load_dotenv(dotenv_path=Path(__file__).with_name(".env"))

# 使用 gemini-3-flash-preview：文档需求指定的模型
# 备选：gemini-2.5-flash（更稳定），gemini-2.5-pro（更精准但较慢）
GEMINI_MODEL = "gemini-3-flash-preview"

# Prompt 设计要点：
#   1. 角色设定："专业气候分析专家" → 引导 Gemini 进入专业模式
#   2. 双语输入：同时提供繁体中文和英文原文，互为补充
#   3. 结构化输出：预定义 4 个章节标题，保证每次返回格式一致
#   4. Markdown 格式：Cursor Chat 界面原生渲染，用户体验更好
#   5. [:4000] 截断（在调用处）：防御性设计，防止页面结构突变导致超出 Token 限制
PROMPT_TEMPLATE = """\
你是一位专业气候分析专家。以下是香港天文台 ENSO 最新监测数据（繁体中文+英文原文）：

【繁体中文版】
{text_zh}

【英文版】
{text_en}

请根据上述信息，用简体中文撰写分析报告，包含以下四个部分：

## 1. 当前 ENSO 状态
（厄尔尼诺 / 拉尼娜 / 中性，并说明判断依据）

## 2. 关键监测数据与趋势
（列出海表温度异常、主要指数数值及最新变化趋势）

## 3. 对东亚地区的气候影响
（温度、降水、台风等方面的影响）

## 4. 未来 1-3 个月预测
（基于当前数据的短期展望）

请以 Markdown 格式输出，语言简洁专业。\
"""


# ── 初始化 MCP Server ────────────────────────────────────────────────────────
# "enso-analyzer" 是服务器标识名，会在 MCP 握手时上报给客户端
server = Server("enso-analyzer")


# ── 工具函数 ─────────────────────────────────────────────────────────────────

async def _fetch_page(url: str) -> str:
    """
    抓取单个 HKO 页面并返回清洗后的纯文本。

    设计决策：
    - User-Agent 伪装：政府网站会屏蔽非浏览器 UA，使用真实浏览器 UA 避免被拒
    - timeout=20：政府网站响应可能慢，20s 是合理上限，防止无限等待
    - follow_redirects=True：HKO 部分 URL 存在 302 跳转
    - raise_for_status()：非 2xx 状态直接抛异常，由上层 call_tool 统一处理

    HTML 净化逻辑：
    - 删除 script/style/nav/footer 等噪音标签
    - 只保留正文内容，避免 JS 代码和导航文字污染 Gemini 的分析
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        # Accept-Language 影响服务器返回的内容语言
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    }
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")

    # 删除所有非内容标签，减少噪音并节省 Gemini Token
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "iframe"]):
        tag.decompose()

    # 按行分割并过滤空行，得到干净的纯文本
    lines = [l for l in soup.get_text(separator="\n", strip=True).splitlines() if l.strip()]
    return "\n".join(lines)


async def fetch_enso_data() -> tuple[str, str]:
    """
    并发抓取中英文两个版本，返回 (zh_text, en_text)。

    并发 vs 串行的性能对比：
    - 串行方式：中文 ~5s + 英文 ~5s = ~10s
    - 并发方式：max(~5s, ~5s) = ~5s，响应速度提升 50%

    asyncio.create_task() 立即启动两个协程任务（非阻塞）
    asyncio.gather() 等待全部完成并按顺序返回结果
    """
    zh_task = asyncio.create_task(_fetch_page(HKO_URL_ZH))
    en_task = asyncio.create_task(_fetch_page(HKO_URL_EN))
    zh_text, en_text = await asyncio.gather(zh_task, en_task)
    return zh_text, en_text


async def analyze_with_gemini(text_zh: str, text_en: str) -> str:
    """
    将双语原文传给 Gemini 3 Flash，返回结构化气候分析报告。

    关键设计：asyncio.to_thread()
    - genai.Client.generate_content() 是同步阻塞函数
    - 直接在 async 函数里调用会卡死整个事件循环，MCP Server 无法处理其他请求
    - asyncio.to_thread() 将其放到线程池执行，主事件循环不受阻塞
    - 示意图：
        主事件循环 ──── 继续处理其他 MCP 请求 ────►
                └── [线程池] Gemini API 阻塞等待 ──► 结果回调

    [:4000] 截断：
    - 防御性设计：当前页面约 500-1300 字，远低于限制
    - 但若 HKO 页面结构突变导致内容暴增，不会因超出 Token 限制而崩溃
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("缺少 GEMINI_API_KEY，请在 .env 或系统环境变量中配置后重试。")

    client = genai.Client(api_key=api_key)
    prompt = PROMPT_TEMPLATE.format(
        text_zh=text_zh[:4000],
        text_en=text_en[:4000],
    )
    # to_thread 将同步的 Gemini SDK 调用包装为异步非阻塞
    response = await asyncio.to_thread(
        client.models.generate_content,
        model=GEMINI_MODEL,
        contents=prompt,
    )
    return response.text


# ── MCP Tool 注册 ─────────────────────────────────────────────────────────────

@server.list_tools()
async def list_tools() -> list[Tool]:
    """
    响应 MCP 协议的 tools/list 请求。

    当 Cursor/Claude 连接时会先发此请求，用于：
    1. 发现服务器提供了哪些工具
    2. 读取工具描述，决定何时调用该工具

    description 字段非常重要：AI Agent 根据此描述判断"何时调用"，
    需要清晰说明：触发场景 + 数据来源 + 返回内容。

    inputSchema 为空对象：
    - 该工具不需要用户输入参数（数据源固定为 HKO）
    - 符合 JSON Schema 规范：properties={}, required=[]
    """
    return [
        Tool(
            name="analyze_enso_situation",
            description=(
                "抓取香港天文台最新 ENSO（厄尔尼诺-南方涛动）监测数据，"
                "使用 Gemini AI 分析东亚地区当前气候状况、趋势及预测。"
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """
    响应 MCP 协议的 tools/call 请求，执行完整的抓取-分析流程。

    错误处理策略（优雅降级）：
    ┌─────────────────────┬──────────────────────────────────────────┐
    │ 错误场景            │ 处理方式                                  │
    ├─────────────────────┼──────────────────────────────────────────┤
    │ 网页抓取失败        │ 返回友好提示，不崩溃，用户可重试          │
    │ 页面内容为空        │ 提示数据异常，不传空文本给 Gemini         │
    │ Gemini 分析失败     │ 降级：直接返回原始页面文本（数据不丢失）  │
    └─────────────────────┴──────────────────────────────────────────┘

    返回类型 list[TextContent]：
    - MCP 协议规定工具返回值为内容列表，理论上支持多块内容（文字+图片等）
    - 此处仅返回一块文字，但保持列表格式符合协议规范
    """
    if name != "analyze_enso_situation":
        raise ValueError(f"未知工具: {name}")

    # Step 1：并发抓取中英文页面
    try:
        text_zh, text_en = await fetch_enso_data()
    except httpx.HTTPError as e:
        return [TextContent(type="text", text=f"网页抓取失败：{e}\n\n请检查网络连接或稍后重试。")]

    # Step 2：内容有效性检查
    if not text_zh.strip() and not text_en.strip():
        return [TextContent(type="text", text="网页内容为空，无法进行分析。")]

    # Step 3：Gemini 分析，失败时降级返回原始数据
    try:
        report = await analyze_with_gemini(text_zh, text_en)
    except Exception as e:
        return [TextContent(
            type="text",
            text=(
                f"Gemini 分析失败：{e}\n\n"
                f"原始数据（中文）：\n{text_zh}\n\n"
                f"原始数据（英文）：\n{text_en}"
            ),
        )]

    return [TextContent(type="text", text=report)]


# ── 服务入口 ──────────────────────────────────────────────────────────────────

async def main():
    """
    启动 MCP Server，使用 stdio 传输与 Cursor 通信。

    stdio_server() 上下文管理器：
    - 将 stdin/stdout 包装成异步流
    - 退出时优雅关闭流，防止资源泄漏或数据截断
    - 通信格式：JSON-RPC 2.0（MCP 协议规定）

    通信方向：
        Cursor ──(stdin)──► enso_server.py ──(stdout)──► Cursor
               JSON-RPC 请求                 JSON-RPC 响应
    """
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    # __name__ 守卫：防止被其他模块 import 时意外启动服务
    # 例如测试脚本可以安全地 `from enso_server import fetch_enso_data`
    asyncio.run(main())
