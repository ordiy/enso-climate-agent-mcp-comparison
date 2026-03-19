# ENSO 气候分析 MCP Server

基于 MCP（Model Context Protocol）协议的 ENSO 气候分析服务。当 AI Agent（Cursor / Claude）调用时，自动从香港天文台抓取最新 ENSO 监测数据，使用 **Gemini 3 Flash** 模型生成结构化气候分析报告。

实现效果：

![效果截图](https://raw.githubusercontent.com/ordiy/study_notes/master/res/image/2026/20260317213525805.png)

---

## 目录

- [功能说明](#功能说明)
- [系统架构](#系统架构)
- [数据来源](#数据来源)
- [快速开始](#快速开始)
- [代码结构](#代码结构)
- [核心设计思路](#核心设计思路)
- [接入 Cursor](#接入-cursor)
- [本地测试](#本地测试)
- [错误处理](#错误处理)
- [常见问题](#常见问题)

---

## 功能说明

在 Cursor Chat 中输入：

```
分析东亚地区当前的 ENSO 情况
```

AI Agent 自动调用 `analyze_enso_situation` 工具，返回包含以下内容的分析报告：

1. **当前 ENSO 状态** — 厄尔尼诺 / 拉尼娜 / 中性，附判断依据
2. **关键监测数据与趋势** — 海表温度异常、主要指数、变化趋势
3. **对东亚地区的气候影响** — 温度、降水、台风
4. **未来 1-3 个月预测** — 基于多模式预报的短期展望

---

## 系统架构

```
Cursor (AI Agent)
    │  JSON-RPC: tools/call
    │  { name: "analyze_enso_situation" }
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
```

### MCP 协议握手流程

```
Cursor                          enso_server.py
  │── initialize ──────────────►│
  │◄── capabilities ────────────│
  │── notifications/initialized ►│
  │── tools/list ───────────────►│
  │◄── [analyze_enso_situation] ─│
  │── tools/call ───────────────►│  ← 用户触发
  │◄── TextContent(报告) ────────│
```

---

## 数据来源

| 来源 | URL | 说明 |
|------|-----|------|
| 香港天文台（中文） | https://www.hko.gov.hk/tc/lrf/enso/enso-latest.htm | 权威中文发布，繁体 |
| 香港天文台（英文） | https://www.hko.gov.hk/en/lrf/enso/enso-latest.htm | 英文版，数值描述更详细 |

> **为什么选 HKO？**  
> 香港天文台每月更新一次 ENSO 状态报告，内容权威、格式稳定，且针对东亚地区气候影响有专门分析。

**其他参考数据源（扩展用）：**

| 机构 | URL |
|------|-----|
| NOAA（美国） | https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/ensostuff/ONI_v5.php |
| IRI（哥伦比亚大学） | https://iri.columbia.edu/our-expertise/climate/forecasts/enso/current/ |
| BOM（澳大利亚） | https://www.bom.gov.au/climate/ocean/outlooks/?index=nino34 |
| JMA（日本） | https://www.data.jma.go.jp/tcc/tcc/products/elnino/outlook.html |

---

## 快速开始

### 环境要求

- Python >= 3.11（需要 `asyncio.TaskGroup` 等新特性）
- 建议使用 Python 3.13（项目已测试）

### 安装

```bash
# 1. 克隆项目
cd /your/project/dir

# 2. 创建虚拟环境（必须使用 Python 3.11+）
/opt/homebrew/bin/python3.13 -m venv .venv
source .venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt
```

### 依赖清单（requirements.txt）

```
mcp>=1.0.0            # MCP Server 核心框架
httpx>=0.27.0         # 异步 HTTP 客户端
beautifulsoup4>=4.12.0 # HTML 解析
google-genai>=1.0.0   # Gemini 新版 SDK
lxml>=5.0.0           # BS4 解析器（速度快）
```

### 配置 API Key（必填）

```bash
# 方式 1：使用 .env（推荐）
cp .env.example .env
# 然后编辑 .env，填入真实值：
# GEMINI_API_KEY=your_gemini_api_key

# 方式 2：临时环境变量
export GEMINI_API_KEY="your_gemini_api_key"
```

> 不要将真实 API Key 写入代码、README 或提交到 Git 仓库。

---

## 代码结构

```
test_mcp_dev_01/
├── enso_server.py          # MCP Server 主文件（完整注释版）
├── requirements.txt        # Python 依赖
├── README.md               # 本文档
├── doc_feat01.md           # 原始需求文档
├── test-curl.md            # curl 测试命令记录
├── READEME-cn.md           # 扩展数据源参考
└── .venv/                  # Python 虚拟环境（不提交 Git）
```

### enso_server.py 模块结构

```python
enso_server.py
├── [常量配置]
│     ├── HKO_URL_ZH / HKO_URL_EN   # 数据源 URL
│     ├── GEMINI_API_KEY             # API 密钥
│     ├── GEMINI_MODEL               # 模型名称
│     └── PROMPT_TEMPLATE            # Prompt 模板
│
├── [工具函数]
│     ├── _fetch_page(url)           # 抓取单个页面 → 纯文本
│     ├── fetch_enso_data()          # 并发抓取中英文版本
│     └── analyze_with_gemini()      # 调用 Gemini 生成报告
│
├── [MCP Tool 注册]
│     ├── @list_tools()              # 声明工具列表
│     └── @call_tool()               # 处理工具调用
│
└── [服务入口]
      └── main() / asyncio.run()     # 启动 stdio MCP Server
```

---

## 核心设计思路

### 1. 并发抓取（性能优化）

```python
# 串行：~10s
zh_text = await _fetch_page(HKO_URL_ZH)  # 5s
en_text = await _fetch_page(HKO_URL_EN)  # 5s

# 并发：~5s（快 50%）
zh_task = asyncio.create_task(_fetch_page(HKO_URL_ZH))
en_task = asyncio.create_task(_fetch_page(HKO_URL_EN))
zh_text, en_text = await asyncio.gather(zh_task, en_task)
```

### 2. 线程池调用同步 SDK（防止阻塞）

```python
# ❌ 错误：直接调用同步函数，卡死事件循环
response = client.models.generate_content(...)

# ✅ 正确：放入线程池，主循环不受阻塞
response = await asyncio.to_thread(
    client.models.generate_content,
    model=GEMINI_MODEL,
    contents=prompt,
)
```

### 3. 优雅降级（错误处理）

```
网页抓取失败（HTTPError）
    → 返回友好提示，不崩溃

内容为空
    → 提示数据异常，不传空文本给 Gemini

Gemini 分析失败
    → 降级策略：返回原始页面文本，用户至少能看到数据
```

### 4. Prompt 工程

- **角色设定**：`你是一位专业气候分析专家` — 专业模式，避免泛泛而谈
- **双语输入**：中英文互补，提升分析准确性
- **结构化输出**：预定义 4 个章节，每次返回格式一致
- **截断保护**：`text[:4000]` 防止 Token 超限

---

## 接入 Cursor

编辑 `~/.cursor/mcp.json`，添加以下配置：

```json
{
  "mcpServers": {
    "enso-analyzer": {
      "command": "/your/project/path/.venv/bin/python3",
      "args": ["/your/project/path/enso_server.py"]
    }
  }
}
```

替换实际路径后重启 Cursor，在 MCP 工具面板确认 `enso-analyzer` 状态为绿色。

**验证方式：** 在 Chat 中输入 `分析东亚地区当前的ENSO情况`，AI 会自动调用工具。

---

## 本地测试

### 方式一：直接测试核心函数

```bash
source .venv/bin/activate

# 测试网页抓取
python3 -c "
import asyncio
from enso_server import fetch_enso_data
async def test():
    zh, en = await fetch_enso_data()
    print(f'中文 {len(zh)} 字，英文 {len(en)} 字')
    print(zh[:300])
asyncio.run(test())
"

# 测试完整链路（抓取 + Gemini 分析，约 20s）
python3 -c "
import asyncio
from enso_server import fetch_enso_data, analyze_with_gemini
async def test():
    zh, en = await fetch_enso_data()
    report = await analyze_with_gemini(zh, en)
    print(report)
asyncio.run(test())
"
```

### 方式二：MCP 协议直接测试（JSON-RPC）

```bash
# 测试工具列表
printf '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{\"protocolVersion\":\"2024-11-05\",\"capabilities\":{},\"clientInfo\":{\"name\":\"test\",\"version\":\"1\"}}}\n{\"jsonrpc\":\"2.0\",\"method\":\"notifications/initialized\",\"params\":{}}\n{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"tools/list\",\"params\":{}}\n' \
  | .venv/bin/python3 enso_server.py 2>/dev/null

# 测试工具调用（保持 stdin 开放，约 20s）
(printf '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1"}}}\n{"jsonrpc":"2.0","method":"notifications/initialized","params":{}}\n{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"analyze_enso_situation","arguments":{}}}\n'; sleep 60) \
  | .venv/bin/python3 enso_server.py 2>/dev/null
```

### 方式三：MCP Inspector（图形界面）

```bash
npx @modelcontextprotocol/inspector .venv/bin/python3 enso_server.py
```

打开浏览器 `http://localhost:6274`，在界面中点击调用工具。

### 方式四：测试 n8n 云端 MCP Server（curl）

```bash
# 初始化
curl -X POST \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  https://your-n8n-instance/mcp-endpoint \
  -d '{
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "curl-test", "version": "1.0"}}
  }'

# 列出工具
curl -X POST \
  -H "Content-Type: application/json" \
  https://your-n8n-instance/mcp-endpoint \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
```

---

## 错误处理

| 错误场景 | 返回内容 | 用户操作 |
|---------|---------|---------|
| HKO 网站无法访问 | `网页抓取失败：...` | 检查网络，稍后重试 |
| 页面内容为空 | `网页内容为空，无法分析` | 等待 HKO 更新 |
| Gemini API 失败 | `Gemini 分析失败：...` + 原始文本 | 检查 API Key 或配额 |
| 未知工具名 | `ValueError: 未知工具` | 检查工具名是否拼写正确 |

---

## 常见问题

**Q: Python 版本不对怎么办？**

```bash
# 确认使用 Python 3.11+
which python3.13  # macOS Homebrew
/opt/homebrew/bin/python3.13 -m venv .venv
```

**Q: `mcp` 包找不到？**

旧版 pip 或 Python 3.9 以下不支持 `mcp` 包：
```bash
pip install --upgrade pip
pip install mcp>=1.0.0
```

**Q: Gemini 返回 404 NOT_FOUND？**

模型名称可能已变更，查看可用模型：
```python
from google import genai
client = genai.Client(api_key="YOUR_KEY")
for m in client.models.list():
    if 'flash' in m.name: print(m.name)
```

**Q: 分析结果为什么是 2 月数据？**

HKO 每月下旬更新一次，当前数据为最新月份。下次更新时间会在页面底部注明。

---

## 技术栈

| 组件 | 版本 | 用途 |
|------|------|------|
| Python | 3.13 | 运行时 |
| mcp | 1.26.0 | MCP Server 框架 |
| httpx | 0.28.1 | 异步 HTTP 客户端 |
| beautifulsoup4 | 4.14.3 | HTML 解析 |
| google-genai | 1.67.0 | Gemini API SDK |
| lxml | 6.0.2 | HTML 解析器 |
