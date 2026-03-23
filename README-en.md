# ENSO Climate Analysis Agent/MCP — Comparison of Three Implementations

> **Goal:** Use the same business scenario (East Asia ENSO climate analysis) to compare three implementation approaches:
> - **Approach A**: Python Coding MCP (handwritten MCP Server)
> - **Approach B**: n8n MCP/Agent (visual workflow)
> - **Approach C**: LangGraph Agent (ReAct multi-source reasoning agent)

---

## Project Structure

```text
test_mcp_dev_01/
├── python-enso-clam-agent-app/   ← Approach A: Python Coding MCP
│   ├── enso_server.py            # MCP server main file (fully commented)
│   ├── requirements.txt
│   ├── README.md
│   └── .venv/
│
├── n8n-enso-mcp-demo/            ← Approach B: n8n MCP
│   ├── workflow.json             # n8n workflow export (ready to import)
│   └── README.md
│
├── langchain-agent-app/          ← Approach C: LangGraph ReAct Agent
│   ├── tools.py                  # 5 ENSO data source tools (@tool functions)
│   ├── agent.py                  # LangGraph StateGraph + ReAct loop
│   ├── main.py                   # CLI entrypoint (interactive / one-shot / stream)
│   ├── requirements.txt
│   ├── README.md
│   └── .venv/
│
└── README.md                     ← This document: 3-approach comparison
```

---

## Result (Consistent Across All Three Approaches)

In Cursor Chat, input: `Analyze the current ENSO condition in East Asia`

The AI Agent automatically calls tools and returns an analysis report including current status, monitoring indices, regional impacts, and near-term outlook.

![Result Screenshot](https://raw.githubusercontent.com/ordiy/study_notes/master/res/image/2026/20260317213525805.png)

---

## Architecture Comparison

### Approach A: Python Coding MCP

```text
Cursor
  │  stdin JSON-RPC
  ▼
enso_server.py (local process)
  ├─ asyncio.gather() ──┬── httpx GET EN ──► HKO
  │                     └── httpx GET ZH ──► HKO
  ├─ BeautifulSoup → plain text
  └─ asyncio.to_thread(genai) ──► Gemini API
  │  stdout JSON-RPC
  ▼
Cursor renders report
```

### Approach B: n8n MCP/Agent

```text
Cursor
  │  SSE / HTTP JSON-RPC
  ▼
n8n Cloud (remote service)
  ├─ [HTTP Request] ──► HKO EN
  ├─ [HTTP Request] ──► JMO EN
  ├─ Memory (session cache)
  ├─ [Code node] → plain text
  └─ [Google Gemini node] ──► Gemini API
  │  SSE response
  ▼
Cursor renders report
```

![](https://raw.githubusercontent.com/ordiy/study_notes/master/res/image/2026/20260323151230910.png)

### Approach C: LangGraph ReAct Agent

```text
User input (CLI / programmatic call)
  │
  ▼
[agent_node] ← LLM reasoning: which sources are needed?
  │ tool_calls is not empty
  ▼
[tool_node]  ← Execute HTTP tools in parallel (up to 5 data sources)
  │  NOAA / HKO / JMA / IRI / BOM
  ▼
[agent_node] ← LLM synthesizes data → call more tools or return report
  │ tool_calls is empty
  ▼
[END] Structured analysis report
```

> Approach C is an independent agent application.  
> It is not exposed to Cursor through MCP, and runs directly as a Python app.
> It is suitable for backend service use or standalone scripts.

## Detailed Comparison Table

### Developer Experience

| Dimension | Approach A Python MCP | Approach B n8n MCP | Approach C LangGraph |
|------|:-----------------:|:--------------:|:----------------:|
| Development style | Handwritten code | Drag-and-drop nodes | Handwritten code |
| Learning curve | Python + asyncio + MCP SDK | Basic n8n operations | Python + LangGraph + ReAct |
| Build time | ~2 hours | ~20 minutes | ~3 hours |
| Lines of code | 307 | 0 (configuration) | ~450 (3 files) |
| Debugging | Logs / breakpoints | Visual node outputs | `--stream` step-by-step |
| Version control | `.py` files | `workflow.json` | `.py` files |

### Runtime Environment

| Dimension | Approach A Python MCP | Approach B n8n MCP | Approach C LangGraph |
|------|:-----------------:|:--------------:|:----------------:|
| Runtime location | Local process | Cloud n8n instance | Local process |
| Transport protocol | stdio | SSE / HTTP | None (direct call) |
| Cursor integration | `mcp.json` | `mcp.json` (url) | Independent run |
| Number of data sources | 1 (HKO) | 1 (HKO) | 5 (multi-agency) |
| Python version | >= 3.11 | Not required | >= 3.11 |

### Features and Performance

| Dimension | Approach A Python MCP | Approach B n8n MCP | Approach C LangGraph |
|------|:-----------------:|:--------------:|:----------------:|
| Data source | HKO (single-source) | HKO (single-source) | NOAA+HKO+JMA+IRI+BOM (multi-source) |
| Concurrent fetching | `asyncio.gather()` | Fan-out parallel | ToolNode parallel |
| AI analysis model | gemini-3-flash-preview | gemini-2.5-flash | gemini-2.5-flash |
| Inference mode | Single-turn (fixed flow) | Single-turn (fixed flow) | ReAct multi-turn loop |
| Adaptive tool calling | No | No | Yes, dynamic LLM decision |
| Error handling | 3-layer fallback logic | Node-level | Tool-returned error text |
| Response time | ~15-20s | ~15-25s | ~25-30s |
| Conversation memory | No | No | Yes, message history |

### Operations and Extensibility

| Dimension | Approach A Python MCP | Approach B n8n MCP | Approach C LangGraph |
|------|:-----------------:|:--------------:|:----------------:|
| Monitoring | Custom logs | n8n execution history | LangSmith tracing |
| Scheduled execution | Extra development needed | Schedule Trigger | Extra development needed |
| Add new data source | Register a new Tool | Add HTTP node | Add `@tool` function |
| Multi-turn conversation | No | No | Yes, history passing |
| Team collaboration | Code review | Visual workflow | Code review |

---

## LangGraph Real Run Log

```bash
$ python main.py --stream "Analyze the current ENSO condition in East Asia and predict near-term trends"

Question: Analyze the current ENSO condition in East Asia and predict near-term trends

============================================================

[Agent reasoning] decided to call tools: fetch_noaa_oni, fetch_hko_report,
                                    fetch_jma_outlook, fetch_iri_forecast
  [fetch_noaa_oni]      returned 5000 chars (NOAA ONI index page)
  [fetch_hko_report]    returned 1349 chars (HKO monthly report, Feb 2026)
  [fetch_jma_outlook]   returned 3221 chars (JMA seasonal outlook)
  [fetch_iri_forecast]  returned 5000 chars (IRI probabilistic forecast)

[Agent final answer]

## 1. Current ENSO State
The system is transitioning from weak La Nina to ENSO-neutral conditions.
JMA confirms ENSO-neutral in Feb 2026, with La Nina signals fading.
IRI indicates the NINO3.4 index rose from -0.54°C (Jan) to -0.2°C (mid-Feb).

## 2. Key Monitoring Indices and Trends
- NINO3.4 anomaly: -0.61°C → -0.54°C → -0.2°C (steady warming)
- JMA NINO.3 region: +0.1°C (back to positive)
- SOI: +9.9 in January, weakening
- Subsurface warm water has propagated eastward since Dec 2025 (El Nino precursor)

## 3. Climate Impacts on East Asia
HKO expects spring SST to return to normal-to-above-normal levels.
East Asia is gradually moving away from La Nina influence, with warmer conditions.
Convection over Indonesia is strengthening, with increased rainfall.

## 4. Forecast for Next 1-3 Months
| Period | Neutral Probability | El Nino Probability |
|--------|---------------------|---------------------|
| Feb-Apr | 96%               | 4%                  |
| Mar-May | 90%               | 10%                 |
| Apr-Jun | 65%               | 35%                 |
| May-Jul | ~39%              | 58-61%              |
| Summer  | 40%               | 60%                 |

ENSO-neutral dominates spring; El Nino development probability exceeds 60% in summer.

============================================================
```

**Execution stats:**

| Metric | Value |
|------|------|
| Total latency | ~26 seconds |
| ReAct loop rounds | 2 |
| Tools actually used | 4 (BOM not triggered; existing data sufficient) |
| Total returned data | ~14,570 characters |
| Model | gemini-2.5-flash (`temperature=0`) |

---

## Technical Mapping Across Three Approaches

```text
Capability            Python MCP        n8n MCP               LangGraph
──────────────────────────────────────────────────────────────────────────
Tool entry            @server.call_tool() MCP Server Trigger  @tool function
LLM call              genai.Client      Google Gemini node    ChatGoogleGenerativeAI
Concurrent requests   asyncio.gather()  Fan-out links         ToolNode parallel
HTML parsing          BeautifulSoup     Code node JS          BeautifulSoup
Transport             stdio             SSE / HTTP            None (direct call)
Conversation memory   None              None                  add_messages
Dynamic tool decision None (fixed flow) None (fixed flow)    LLM ReAct loop
```

---

## How to Choose

```text
Need to integrate with Cursor/Claude via MCP tools?
    -> Approach A (Python) or Approach B (n8n)

Need fast prototyping / non-engineering team?
    -> Approach B (n8n)

Need multi-agency data synthesis / adaptive reasoning / multi-turn chat?
    -> Approach C (LangGraph)

Need fine-grained control / lightweight dependency?
    -> Approach A (Python MCP)
```

### Decision Tree

```text
Need Cursor MCP integration?
    Yes ↓                           No -> Approach C (LangGraph)
    ├─ Have n8n instance?
    │       Yes -> Approach B (n8n)
    │       No ↓
    └─ Need multi-source data or complex logic?
            Yes -> Approach A (Python) + optionally connect C as backend
            No  -> Approach A (Python, simplest path)
```

---

## Quick Start

### Approach A: Python Coding MCP

```bash
cd python-enso-clam-agent-app
cp .env.example .env
# Edit .env and fill GEMINI_API_KEY
source .venv/bin/activate
python3 enso_server.py
```

`~/.cursor/mcp.json` config:

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

### Approach B: n8n MCP

```bash
# 1. Import n8n-enso-mcp-demo/workflow.json into n8n
# 2. Configure Google Gemini API Key
# 3. Activate the workflow and copy the SSE endpoint URL
```

`~/.cursor/mcp.json` config:

```json
{
  "mcpServers": {
    "enso-n8n": {
      "url": "https://your-n8n-instance/mcp/YOUR_WORKFLOW_ID/sse"
    }
  }
}
```

### Approach C: LangGraph Agent

```bash
cd langchain-agent-app
cp .env.example .env
# Edit .env and fill GEMINI_API_KEY
source .venv/bin/activate

# Stream mode (recommended, shows each reasoning step)
python main.py --stream "Analyze the current ENSO condition in East Asia"

# One-shot QA
python main.py --once "Is it El Nino or La Nina now?"

# Multi-turn interactive chat
python main.py
```

> Before open-sourcing, verify that the repository does not include `.env`, real API keys, account credentials, or other secrets.

---

## References

- [MCP Official Docs](https://modelcontextprotocol.io/)
- [n8n MCP Server Trigger Docs](https://docs.n8n.io/)
- [LangGraph Docs](https://langchain-ai.github.io/langgraph/)
- [Google Gemini API](https://ai.google.dev/gemini-api/docs)
- [HKO ENSO Page](https://www.hko.gov.hk/tc/lrf/enso/enso-latest.htm)
- [NOAA ONI Index](https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/ensostuff/ONI_v5.php)
- [IRI ENSO Forecast](https://iri.columbia.edu/our-expertise/climate/forecasts/enso/current/)

## Data Sources

https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/lanina/enso_evolution-status-fcsts-web.pdf

- NOAA
https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/ensostuff/ONI_v5.php

- Columbia IRI ENSO
https://iri.columbia.edu/our-expertise/climate/forecasts/enso/current/

- BOM
https://www.bom.gov.au/climate/ocean/outlooks/?index=nino34

- JMA
https://www.data.jma.go.jp/tcc/tcc/products/elnino/outlook.html

- HKO
https://www.hko.gov.hk/tc/lrf/enso/enso-front.htm
