# ENSO 气候分析 Agent/MCP — 三种实现方案对比

> **目标：** 用同一个业务场景（东亚 ENSO 气候分析），对比三种实现方式的差异：
> - **方案 A**：Python Coding MCP（手写 MCP Server）
> - **方案 B**：n8n MCP（可视化工作流）
> - **方案 C**：LangGraph Agent（ReAct 多源推理 Agent）

---

## 目录结构

```
test_mcp_dev_01/
├── python-enso-clam-agent-app/   ← 方案 A：Python Coding MCP
│   ├── enso_server.py            # MCP Server 主文件（含完整注释）
│   ├── requirements.txt
│   ├── README.md
│   └── .venv/
│
├── n8n-enso-mcp-demo/            ← 方案 B：n8n MCP
│   ├── workflow.json             # n8n 工作流导出文件（可直接导入）
│   └── README.md
│
├── langchain-agent-app/          ← 方案 C：LangGraph ReAct Agent
│   ├── tools.py                  # 5 个 ENSO 数据源工具（@tool 函数）
│   ├── agent.py                  # LangGraph StateGraph + ReAct 循环
│   ├── main.py                   # CLI 入口（交互/单次/流式三种模式）
│   ├── requirements.txt
│   ├── README.md
│   └── .venv/
│
└── README.md                     ← 本文档：三方案对比
```

---

## 实现效果（三方案一致）

在 Cursor Chat 输入：`分析东亚地区当前的ENSO情况`

AI Agent 自动调用工具，返回包含当前状态、监测指数、气候影响、未来预测的分析报告：

![效果截图](https://raw.githubusercontent.com/ordiy/study_notes/master/res/image/2026/20260317213525805.png)

---

## 架构对比

### 方案 A：Python Coding MCP

```
Cursor
  │  stdin JSON-RPC
  ▼
enso_server.py (本地进程)
  ├─ asyncio.gather() ──┬── httpx GET EN ──► HKO
  │                     └── httpx GET ZH ──► HKO
  ├─ BeautifulSoup → 纯文本
  └─ asyncio.to_thread(genai) ──► Gemini API
  │  stdout JSON-RPC
  ▼
Cursor 展示报告
```

### 方案 B：n8n MCP

```
Cursor
  │  SSE / HTTP JSON-RPC
  ▼
n8n Cloud (远程服务)
  ├─ [HTTP Request] ──► HKO EN
  ├─ [HTTP Request] ──► HKO ZH   ← 并行执行
  ├─ [Code 节点] → 纯文本
  └─ [Google Gemini 节点] ──► Gemini API
  │  SSE 响应
  ▼
Cursor 展示报告
```

### 方案 C：LangGraph ReAct Agent

```
用户输入（CLI / 程序调用）
  │
  ▼
[agent_node] ← LLM 推理：需要哪些数据源？
  │ tool_calls 不为空
  ▼
[tool_node]  ← 并行执行 HTTP 工具（最多 5 个数据源）
  │  NOAA / HKO / JMA / IRI / BOM
  ▼
[agent_node] ← LLM 综合数据 → 继续调工具 or 输出报告
  │ tool_calls 为空
  ▼
[END] 输出结构化分析报告
```

> 方案 C 是独立的 Agent 程序，不通过 MCP 协议暴露给 Cursor，
> 而是直接作为 Python 应用运行，适合作为后端服务或独立脚本使用。

---

## 详细对比表

### 开发体验

| 维度 | 方案 A Python MCP | 方案 B n8n MCP | 方案 C LangGraph |
|------|:-----------------:|:--------------:|:----------------:|
| 开发方式 | 手写代码 | 拖拽节点 | 手写代码 |
| 学习门槛 | Python + asyncio + MCP SDK | n8n 基本操作 | Python + LangGraph + ReAct |
| 开发时间 | ~2 小时 | ~20 分钟 | ~3 小时 |
| 代码行数 | 307 行 | 0 行（配置） | ~450 行（3个文件） |
| 调试难度 | 日志 / 断点 | 可视化节点输出 | `--stream` 逐步可见 |
| 版本控制 | `.py` 文件 | `workflow.json` | `.py` 文件 |

### 运行环境

| 维度 | 方案 A Python MCP | 方案 B n8n MCP | 方案 C LangGraph |
|------|:-----------------:|:--------------:|:----------------:|
| 运行位置 | 本地进程 | 云端 n8n 实例 | 本地进程 |
| 传输协议 | stdio | SSE / HTTP | 无（直接调用） |
| 接入 Cursor | ✅ mcp.json | ✅ mcp.json (url) | ❌ 独立运行 |
| 数据源数量 | 1（HKO） | 1（HKO） | 5（多机构） |
| Python 版本 | >= 3.11 | 无要求 | >= 3.11 |

### 功能与性能

| 维度 | 方案 A Python MCP | 方案 B n8n MCP | 方案 C LangGraph |
|------|:-----------------:|:--------------:|:----------------:|
| 数据来源 | HKO（单源） | HKO（单源） | NOAA+HKO+JMA+IRI+BOM（多源）|
| 并发抓取 | `asyncio.gather()` | Fan-out 并行 | ToolNode 并行 |
| AI 分析 | gemini-3-flash-preview | gemini-2.5-flash | gemini-2.5-flash |
| 推理模式 | 单轮（固定流程） | 单轮（固定流程） | ReAct 多轮循环 |
| 自适应工具调用 | ❌ | ❌ | ✅ LLM 动态决策 |
| 错误处理 | 3 层降级逻辑 | 节点级别 | 工具返回错误提示 |
| 响应时间 | ~15-20s | ~15-25s | ~25-30s |
| 对话记忆 | ❌ | ❌ | ✅ messages 历史 |

### 运维与扩展

| 维度 | 方案 A Python MCP | 方案 B n8n MCP | 方案 C LangGraph |
|------|:-----------------:|:--------------:|:----------------:|
| 监控 | 自定义日志 | n8n 执行历史 | LangSmith 追踪 |
| 定时触发 | 需额外开发 | Schedule Trigger | 需额外开发 |
| 添加新数据源 | 注册新 Tool | 新增 HTTP 节点 | 新增 @tool 函数 |
| 多轮对话 | ❌ | ❌ | ✅ history 传递 |
| 团队协作 | 代码 Review | 可视化流程 | 代码 Review |

---

## LangGraph 方案实际运行记录

```
$ python main.py --stream "分析东亚地区当前的ENSO情况，并预测未来趋势"

问题: 分析东亚地区当前的ENSO情况，并预测未来趋势

============================================================

🤔 [Agent 推理] 决定调用工具: fetch_noaa_oni, fetch_hko_report,
                              fetch_jma_outlook, fetch_iri_forecast
  🌐 [fetch_noaa_oni]     返回 5000 字（NOAA ONI 指数页面）
  🌐 [fetch_hko_report]   返回 1349 字（HKO 2026年2月月报）
  🌐 [fetch_jma_outlook]  返回 3221 字（JMA 季节预测）
  🌐 [fetch_iri_forecast]  返回 5000 字（IRI 概率预报）

📊 [Agent 最终回答]

## 1. 当前 ENSO 状态
当前正从弱拉尼娜向 ENSO 中性状态过渡。JMA 明确指出 2026 年 2 月
ENSO 处于中性，拉尼娜特征正在消散。IRI 数据显示 NINO3.4 指数从
-0.54°C（1 月）升至 -0.2°C（2 月中旬），回升趋势明显。

## 2. 关键监测指数与趋势
- NINO3.4 距平：-0.61°C → -0.54°C → -0.2°C（持续升温）
- JMA NINO.3 区域：+0.1°C（已回正）
- SOI：1 月 +9.9，减弱中
- 次表层暖水自 2025 年 12 月起向东传播（厄尔尼诺先兆）

## 3. 对东亚地区的气候影响
HKO 预计春季海温升至正常至偏高。东亚逐渐摆脱拉尼娜影响，
气温有所回升。印度尼西亚对流增强，降水增加。

## 4. 未来 1–3 个月预测
| 时间段 | 中性概率 | 厄尔尼诺概率 |
|--------|---------|------------|
| 2–4 月 | 96%     | 4%         |
| 3–5 月 | 90%     | 10%        |
| 4–6 月 | 65%     | 35%        |
| 5–7 月 | ~39%    | 58–61%     |
| 夏季   | 40%     | 60%        |

春季 ENSO 中性主导，夏季厄尔尼诺发展概率超 60%。

============================================================
```

**执行统计：**

| 指标 | 数值 |
|------|------|
| 总耗时 | ~26 秒 |
| ReAct 循环轮次 | 2 轮 |
| 实际调用工具数 | 4 个（BOM 未触发，数据已足够） |
| 返回数据总量 | ~14,570 字符 |
| 模型 | gemini-2.5-flash（temperature=0） |

---

## 三方案技术对应关系

```
功能                Python MCP        n8n MCP              LangGraph
───────────────────────────────────────────────────────────────────────
工具入口        @server.call_tool() MCP Server Trigger   @tool 函数
LLM 调用        genai.Client        Google Gemini 节点   ChatGoogleGenerativeAI
并发请求        asyncio.gather()    Fan-out 连接         ToolNode 并行
HTML 解析       BeautifulSoup       Code 节点 JS         BeautifulSoup
传输层          stdio               SSE / HTTP           无（直接调用）
对话记忆        无                  无                   add_messages
动态工具决策    无（固定流程）      无（固定流程）       LLM ReAct 循环
```

---

## 如何选择？

```
接入 Cursor / Claude 作为 MCP Tool？
    → 方案 A（Python）或 方案 B（n8n）

需要快速原型 / 非技术团队？
    → 方案 B（n8n）✅

需要多机构数据综合 / 自适应推理 / 多轮对话？
    → 方案 C（LangGraph）✅

需要精确控制 / 轻量无依赖？
    → 方案 A（Python MCP）✅
```

### 决策树

```
需要接入 Cursor MCP？
    是 ↓                           否 → 方案 C（LangGraph）
    ├─ 有 n8n 实例？
    │       是 → 方案 B（n8n）
    │       否 ↓
    └─ 需要多数据源或复杂逻辑？
            是 → 方案 A（Python）+ 可选接入方案 C 作为后端
            否 → 方案 A（Python，最简）
```

---

## 快速开始

### 方案 A：Python Coding MCP

```bash
cd python-enso-clam-agent-app
cp .env.example .env
# 编辑 .env，填入 GEMINI_API_KEY
source .venv/bin/activate
python3 enso_server.py
```

`~/.cursor/mcp.json` 配置：

```json
{
  "mcpServers": {
    "enso-python": {
      "command": "/path/to/python-enso-clam-agent-app/.venv/bin/python3",
      "args": ["/path/to/python-enso-clam-agent-app/enso_server.py"]
    }
  }
}
```

### 方案 B：n8n MCP

```bash
# 1. 导入 n8n-enso-mcp-demo/workflow.json 到 n8n
# 2. 配置 Google Gemini API Key
# 3. 激活工作流，复制 SSE Endpoint URL
```

`~/.cursor/mcp.json` 配置：

```json
{
  "mcpServers": {
    "enso-n8n": {
      "url": "https://your-n8n-instance/mcp/YOUR_WORKFLOW_ID/sse"
    }
  }
}
```

### 方案 C：LangGraph Agent

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

> 开源前请确认：仓库中不包含 `.env`、真实 API Key、账号密码等敏感信息。

---

## 参考资料

- [MCP 官方文档](https://modelcontextprotocol.io/)
- [n8n MCP Server Trigger 文档](https://docs.n8n.io/)
- [LangGraph 文档](https://langchain-ai.github.io/langgraph/)
- [Google Gemini API](https://ai.google.dev/gemini-api/docs)
- [香港天文台 ENSO 页面](https://www.hko.gov.hk/tc/lrf/enso/enso-latest.htm)
- [NOAA ONI 指数](https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/ensostuff/ONI_v5.php)
- [IRI ENSO 预测](https://iri.columbia.edu/our-expertise/climate/forecasts/enso/current/)
