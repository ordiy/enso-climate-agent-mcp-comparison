# ENSO 气候分析 Agent — LangGraph 实现

用 **LangGraph** 实现与 n8n 工作流等价的多源 ENSO 气候分析 AI Agent。

---

## 项目结构

```
langchain-agent-app/
├── tools.py        # 5 个 ENSO 数据源工具（@tool 函数）
├── agent.py        # LangGraph ReAct Agent 核心逻辑
├── main.py         # CLI 对话入口（交互/单次/流式 三种模式）
├── requirements.txt
└── .venv/
```

---

## 快速开始

```bash
cd langchain-agent-app
cp .env.example .env
# 编辑 .env，填入 GEMINI_API_KEY
source .venv/bin/activate

# 流式模式（推荐，可看到每步推理过程）
python main.py --stream "分析东亚地区当前的ENSO情况"

# 单次问答
python main.py --once "当前是厄尔尼诺还是拉尼娜？"

# 多轮交互对话
python main.py
```

> 不要将真实 API Key 写入代码或提交到 Git 仓库。

---

## 与 n8n 工作流的对应关系

| n8n 节点 | 代码实现 | 文件 |
|---------|---------|------|
| When chat message received | `run_interactive()` / `run_once()` | `main.py` |
| AI Agent | `agent_node()` + `should_continue()` | `agent.py` |
| Google Vertex Chat Model | `ChatGoogleGenerativeAI(model="gemini-2.0-flash")` | `agent.py` |
| Simple Memory | `AgentState.messages` + `add_messages` | `agent.py` |
| NOAA-CPC-ONI-index | `fetch_noaa_oni()` | `tools.py` |
| HKO-ENSO-report | `fetch_hko_report()` | `tools.py` |
| JPO-ENSO-outlook | `fetch_jma_outlook()` | `tools.py` |
| iri.columbia.edu-ENSO-report | `fetch_iri_forecast()` | `tools.py` |
| BOM-ENSO-outlook | `fetch_bom_outlook()` | `tools.py` |

---

## 核心逻辑：ReAct 循环

```
用户输入
    │
    ▼
[agent_node]  ← LLM 推理：需要哪些数据？
    │ 有 tool_calls
    ▼
[tool_node]   ← 执行 HTTP 工具（串行/并发）
    │ 工具结果加入 messages
    ▼
[agent_node]  ← LLM 综合数据，生成报告 or 继续调工具
    │ 无 tool_calls
    ▼
  [END]        ← 输出最终分析报告
```

典型执行轨迹（`--stream` 模式实际运行记录，2026-03-17）：

```
问题: 分析东亚地区当前的ENSO情况，并预测未来趋势

============================================================

🤔 [Agent 推理] 决定调用工具: fetch_noaa_oni, fetch_hko_report, fetch_jma_outlook, fetch_iri_forecast
  🌐 [fetch_noaa_oni]    返回 5000 字: Climate Prediction Center - ONI ...
  🌐 [fetch_hko_report]  返回 1349 字: Latest status (February 2026) In the past month...
  🌐 [fetch_jma_outlook] 返回 3221 字: El Nino Monitoring and Outlook / TCC...
  🌐 [fetch_iri_forecast] 返回 5000 字: IRI February 2026 Quick Look...

📊 [Agent 最终回答]

## 1. 当前 ENSO 状态

根据香港天文台和日本气象厅的报告，赤道中东太平洋海面温度目前整体接近正常，
日本气象厅明确指出 2026 年 2 月 ENSO 处于中性状态，且类似拉尼娜的海洋和大气
条件正在消散。哥伦比亚大学 IRI 的分析也表明，赤道太平洋正在经历"减弱中的拉
尼娜"条件，NINO3.4 指数从弱拉尼娜范围（2026 年 1 月为 -0.54°C）向中性状态
（2026 年 2 月中旬为 -0.2°C）转变。

综合来看，当前 ENSO 状态正从弱拉尼娜向 ENSO 中性条件过渡。

## 2. 关键监测指数与趋势

- **NINO3.4 海温距平（升温趋势）：**
  - 2026 年 11 月–1 月：-0.61°C（弱拉尼娜）
  - 2026 年 1 月：-0.54°C
  - 2026 年 2 月 11 日当周：-0.2°C（接近中性）
  - JMA 报告 2 月 NINO.3 区域：+0.1°C（已回正）
- **SOI（南方涛动指数）：** 1 月 SOI = +9.9，赤道 SOI = +0.5，强度减弱中
- **次表层海温：** 西赤道太平洋暖水自 2025 年 12 月起向东传播（厄尔尼诺先兆）
- **大气环流：** 拉尼娜特征消散，信风强度趋于正常

## 3. 对东亚地区的气候影响

香港天文台预计赤道中东太平洋海温在 2026 年春季将升至正常或偏高。随着 ENSO
向中性过渡，东亚气候模式逐渐摆脱拉尼娜影响，气温有所回升。IRI 报告印度尼西
亚部分地区对流增强和降水增加，与拉尼娜消退阶段对东南亚的影响一致。

## 4. 未来 1–3 个月预测

| 时间段 | 中性概率 | 厄尔尼诺概率 | 来源 |
|--------|---------|------------|------|
| 2–4 月 | 96% | 4% | IRI |
| 3–5 月 | 90% | 10% | IRI |
| 4–6 月 | 65% | 35% | IRI |
| 5–7 月 | ~39% | 58–61% | IRI |
| 夏季   | 40% | 60% | JMA |

**总结：** 春季 ENSO 中性主导，夏季厄尔尼诺发展概率超 60%。

## 5. 数据来源说明

- 美国 NOAA 气候预测中心（ONI 指数）
- 香港天文台（HKO）ENSO 月度报告
- 日本气象厅（JMA）ENSO 预测展望
- 哥伦比亚大学 IRI ENSO 概率预测

============================================================
```

**执行统计：**
- 总耗时：~26 秒
- ReAct 循环轮次：2 轮（1 次工具调用 + 1 次综合输出）
- 实际调用工具数：4 个（BOM 未调用，其他 4 个数据已足够）
- 返回数据总量：约 14,570 字符

---

## 选型说明

### 为什么选 LangGraph 而不是 LangChain AgentExecutor？

```python
# ❌ AgentExecutor（旧方式）
from langchain.agents import AgentExecutor
executor = AgentExecutor(agent=agent, tools=tools)
result = executor.invoke({"input": "..."})
# 内部循环完全不可见，调试极难

# ✅ LangGraph（推荐）
graph = build_graph()
for step in graph.stream({"messages": [...]}):
    print(step)  # 每个节点执行结果实时可见
```

| 能力 | AgentExecutor | LangGraph |
|------|:---:|:---:|
| 每步状态可观测 | ❌ | ✅ |
| 中途人工干预 | ❌ | ✅ `interrupt_before` |
| 持久化到数据库 | 复杂 | ✅ `checkpointer` |
| 并行工具调用 | ❌ | ✅ |
| 与 n8n 思维模型一致 | 部分 | ✅ 节点+边+状态 |

### 为什么选 langchain-google-genai 而不是 langchain-google-vertexai？

| | google-genai | google-vertexai |
|--|--|--|
| 认证方式 | API Key | GCP 服务账号 |
| 配置复杂度 | 低 | 高（需 GCP 项目） |
| 适用场景 | 开发/原型 | 生产/企业 |
| 模型等价性 | 相同（Gemini） | 相同（Gemini） |

### 为什么 temperature=0？

气候数据分析需要**确定性**输出——相同数据应产生相同结论。
高 temperature 会导致工具选择随机性增加，分析结论每次不同。

---

## ⚠️ 最容易出错的地方

### 1. Tool docstring 写得不精确（最高风险）

```python
# ❌ 太模糊 → LLM 不知道该调哪个工具
@tool
def fetch_noaa_oni() -> str:
    """获取 ENSO 数据"""
    ...

# ✅ 精确描述：机构名、数据类型、适用场景
@tool
def fetch_noaa_oni() -> str:
    """
    获取美国 NOAA ONI 指数，国际公认的 ENSO 判断标准。
    当 ONI >= +0.5°C 持续5个月为厄尔尼诺。
    适用于：查询当前 ONI 数值、ENSO 状态官方判定。
    """
    ...
```

### 2. 工具串行执行导致响应慢（最大性能瓶颈）

```
当前（串行）：5 个工具 × 平均 8s = 约 40s
优化（并发）：max(各工具耗时) ≈ 约 10s
```

优化方案：将 `tools.py` 改为异步工具：

```python
import httpx

@tool
async def fetch_noaa_oni() -> str:
    """..."""
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(URL, headers=_HEADERS)
        ...
```

然后用 `chat_async()` 调用：

```python
reply, history = await chat_async("分析ENSO情况")
```

### 3. 对话历史无限增长（内存泄漏）

```python
# ⚠️ 长时间对话后，messages 列表包含大量 ToolMessage（每条 5000 字）
# 超过 LLM 上下文窗口后报错

# 临时方案：定期清空历史
history = []  # 用户输入 reset 时

# 生产方案：使用 checkpointer + 历史压缩
from langgraph.checkpoint.memory import MemorySaver
graph = builder.compile(checkpointer=MemorySaver())
```

### 4. JMA 网站响应超时（最常见运行时错误）

```python
# JMA 日本气象厅响应偏慢，20s 默认超时经常失败
# tools.py 中已设置 timeout=30，但仍有失败可能

# 在 _fetch_text 中加了防御性处理：
except httpx.TimeoutException:
    return f"[抓取超时] URL: {url}，请稍后重试"
```

### 5. 无限循环风险

```python
# LLM 持续返回 tool_calls 且工具返回错误信息
# → Agent 陷入无限循环

# 通过 recursion_limit 限制：
graph.invoke(..., config={"recursion_limit": 10})
# 超过 10 次抛出 GraphRecursionError，而非无限运行
```
