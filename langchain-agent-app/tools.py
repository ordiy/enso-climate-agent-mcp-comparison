"""
tools.py — ENSO 多源数据抓取工具集
====================================
对应 n8n 工作流中的 5 个 HTTP Request Tool 节点：
    NOAA-CPC-ONI-index
    HKO-ENSO-report
    JPO-ENSO-outlook
    iri.columbia.edu-ENSO-report
    BOM-ENSO-outlook

设计原则：
- 每个 @tool 函数的 docstring 是 LLM 决定"何时调用此工具"的唯一依据，
  必须精确描述数据内容、适用场景，不能省略。
- 所有工具共享同一个 _fetch_text() 底层实现，避免重复代码。
- 网络 IO 用同步 httpx（工具在 ToolNode 里由 LangGraph 管理并发）。

⚠️ 性能瓶颈：5 个工具都是同步阻塞 HTTP 请求，串行执行约 25-50s。
   见 agent.py 中 async 并发抓取的优化说明。
"""

import httpx
from bs4 import BeautifulSoup
from langchain_core.tools import tool

# ── 底层抓取函数 ──────────────────────────────────────────────────────────────

# 选 httpx 不选 requests 的原因：
#   1. 同步/异步 API 一致，未来升级到 async 版本无需改业务代码
#   2. 内置 HTTP/2 支持，连接复用性更好
#   3. 类型标注完整，IDE 提示友好
#
# 选 BeautifulSoup+lxml 不选正则的原因：
#   正则对 HTML 极脆弱（属性顺序、换行、编码差异都会导致匹配失败）
#   BS4 能正确处理嵌套、乱码、自闭合标签等边缘情况
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9,zh;q=0.8",
}

# 每个工具的文本截断上限
# 5 个工具 × 5000 字 = 25000 字 ≈ 约 6000 tokens，在 Gemini 的上下文窗口内
_MAX_CHARS = 5000


def _fetch_text(url: str, timeout: int = 20) -> str:
    """
    通用 HTTP 抓取 + HTML 净化，返回纯文本。

    ⚠️ 最容易出错的地方：
    1. timeout 设置过短：某些政府网站（尤其 JMA）响应可能超过 10s
    2. raise_for_status()：若网站返回 403/429，需要调整 User-Agent 或加重试
    3. lxml 解析器：若目标站点 HTML 极度不规范，改用 "html.parser" 兜底
    """
    try:
        resp = httpx.get(url, headers=_HEADERS, timeout=timeout, follow_redirects=True)
        resp.raise_for_status()
    except httpx.TimeoutException:
        return f"[抓取超时] URL: {url}，请稍后重试"
    except httpx.HTTPStatusError as e:
        return f"[HTTP 错误] {e.response.status_code} — {url}"
    except httpx.RequestError as e:
        return f"[网络错误] {e} — {url}"

    soup = BeautifulSoup(resp.text, "lxml")

    # 删除所有不含信息的标签（JS、样式、导航等）
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "iframe"]):
        tag.decompose()

    lines = [l for l in soup.get_text("\n", strip=True).splitlines() if l.strip()]
    return "\n".join(lines)[:_MAX_CHARS]


# ── 5 个 ENSO 数据源工具 ──────────────────────────────────────────────────────
#
# @tool 装饰器做了三件事：
#   1. 将普通函数包装为 LangChain BaseTool 实例
#   2. 把函数名作为 tool name（LLM 调用时使用）
#   3. 把 docstring 作为 tool description（LLM 决策依据）
#
# ⚠️ 最容易出错的地方：
#   docstring 写得太模糊 → LLM 不知道该调哪个工具，或重复调用所有工具
#   docstring 必须包含：数据机构名、数据类型、适用场景

@tool
def fetch_noaa_oni() -> str:
    """
    获取美国 NOAA（国家海洋大气局）气候预测中心的最新 ONI（海洋尼诺指数）数据。
    ONI 是国际公认的 ENSO 状态官方判断标准：连续3个月滚动平均 SST 距平。
    当 ONI >= +0.5°C 持续5个月为厄尔尼诺；<= -0.5°C 为拉尼娜。
    适用于：查询当前 ONI 数值、历史 ENSO 事件列表、ENSO 状态官方判定。
    """
    return _fetch_text(
        "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/ensostuff/ONI_v5.php"
    )


@tool
def fetch_hko_report() -> str:
    """
    获取香港天文台（HKO）最新 ENSO 状态月度报告。
    内容包含：赤道太平洋海面温度距平、当前 ENSO 状态判断、
    对东亚和香港地区气候的具体影响（温度/降水/台风）、未来季度预测。
    适用于：分析 ENSO 对东亚/华南/香港地区的气候影响，获取最新月度状态。
    """
    return _fetch_text(
        "https://www.hko.gov.hk/en/lrf/enso/enso-latest.htm"
    )


@tool
def fetch_jma_outlook() -> str:
    """
    获取日本气象厅（JMA）最新 ENSO 预测展望报告。
    内容包含：厄尔尼诺监测指数、季节预报、未来6个月海温距平预测。
    JMA 是亚太地区权威气象机构，预报对西太平洋和东亚地区有特别参考价值。
    适用于：获取亚洲视角的 ENSO 季节预测、西太平洋区域气候展望。
    """
    return _fetch_text(
        "https://www.data.jma.go.jp/tcc/tcc/products/elnino/outlook.html",
        timeout=30,  # JMA 响应偏慢，延长超时
    )


@tool
def fetch_iri_forecast() -> str:
    """
    获取哥伦比亚大学国际气候与社会研究所（IRI）ENSO 概率预测。
    特点：提供未来各季度厄尔尼诺/中性/拉尼娜发生的概率分布，
    综合了全球30+气候模式的集合预报，是预测不确定性分析的最佳来源。
    适用于：查询 ENSO 未来演变概率、多模式集合预报共识、预测置信区间。
    """
    return _fetch_text(
        "https://iri.columbia.edu/our-expertise/climate/forecasts/enso/current/"
    )


@tool
def fetch_bom_outlook() -> str:
    """
    获取澳大利亚气象局（BOM）ENSO 展望及 Nino3.4 海温指数报告。
    内容包含：Nino3.4 区域海温距平实时数据、南方涛动指数（SOI）、
    ENSO 状态判断及对澳大利亚和太平洋地区降水的影响预测。
    适用于：获取南半球/太平洋视角的 ENSO 评估、SOI 指数、降水异常分析。
    """
    return _fetch_text(
        "https://www.bom.gov.au/climate/ocean/outlooks/?index=nino34"
    )


# 导出给 agent.py 使用
ENSO_TOOLS = [
    fetch_noaa_oni,
    fetch_hko_report,
    fetch_jma_outlook,
    fetch_iri_forecast,
    fetch_bom_outlook,
]
