# ENSO-Klimaanalyse Agent/MCP — Vergleich von drei Implementierungsansätzen

> **Ziel:** Dasselbe Business-Szenario (ENSO-Klimaanalyse für Ostasien) mit drei Implementierungsansätzen vergleichen:
> - **Ansatz A:** Python Coding MCP (handgeschriebener MCP-Server)
> - **Ansatz B:** n8n MCP/Agent (visueller Workflow)
> - **Ansatz C:** LangGraph Agent (ReAct-Agent mit Multi-Source-Reasoning)

---

## Projektstruktur

```text
test_mcp_dev_01/
├── python-enso-clam-agent-app/   ← Ansatz A: Python Coding MCP
│   ├── enso_server.py            # MCP-Server-Hauptdatei (voll kommentiert)
│   ├── requirements.txt
│   ├── README.md
│   └── .venv/
│
├── n8n-enso-mcp-demo/            ← Ansatz B: n8n MCP
│   ├── workflow.json             # n8n-Workflow-Export (direkt importierbar)
│   └── README.md
│
├── langchain-agent-app/          ← Ansatz C: LangGraph ReAct Agent
│   ├── tools.py                  # 5 ENSO-Datenquellen-Tools (@tool-Funktionen)
│   ├── agent.py                  # LangGraph StateGraph + ReAct-Schleife
│   ├── main.py                   # CLI-Einstieg (interaktiv / einmalig / stream)
│   ├── requirements.txt
│   ├── README.md
│   └── .venv/
│
└── README.md                     ← Dieses Dokument: Vergleich der 3 Ansätze
```

---

## Ergebnis (bei allen drei Ansätzen konsistent)

In Cursor Chat eingeben: `Analyze the current ENSO condition in East Asia`

Der AI-Agent ruft automatisch Tools auf und liefert einen Bericht mit aktuellem Zustand, Monitoring-Indizes, regionalen Auswirkungen und kurzfristiger Prognose.

![Ergebnis-Screenshot](https://raw.githubusercontent.com/ordiy/study_notes/master/res/image/2026/20260317213525805.png)

---

## Architekturvergleich

### Ansatz A: Python Coding MCP

```text
Cursor
  │  stdin JSON-RPC
  ▼
enso_server.py (lokaler Prozess)
  ├─ asyncio.gather() ──┬── httpx GET EN ──► HKO
  │                     └── httpx GET ZH ──► HKO
  ├─ BeautifulSoup → Klartext
  └─ asyncio.to_thread(genai) ──► Gemini API
  │  stdout JSON-RPC
  ▼
Cursor zeigt Bericht an
```

### Ansatz B: n8n MCP/Agent

```text
Cursor
  │  SSE / HTTP JSON-RPC
  ▼
n8n Cloud (Remote-Service)
  ├─ [HTTP Request] ──► HKO EN
  ├─ [HTTP Request] ──► JMO EN
  ├─ Memory (Session-Cache)
  ├─ [Code-Node] → Klartext
  └─ [Google Gemini-Node] ──► Gemini API
  │  SSE-Antwort
  ▼
Cursor zeigt Bericht an
```

![](https://raw.githubusercontent.com/ordiy/study_notes/master/res/image/2026/20260323151230910.png)

### Ansatz C: LangGraph ReAct Agent

```text
Benutzereingabe (CLI / Programmaufruf)
  │
  ▼
[agent_node] ← LLM-Reasoning: Welche Quellen werden benötigt?
  │ tool_calls ist nicht leer
  ▼
[tool_node]  ← HTTP-Tools parallel ausführen (bis zu 5 Datenquellen)
  │  NOAA / HKO / JMA / IRI / BOM
  ▼
[agent_node] ← LLM synthetisiert Daten → weitere Tools oder Bericht
  │ tool_calls ist leer
  ▼
[END] Strukturierter Analysebericht
```

> Ansatz C ist eine eigenständige Agent-Anwendung.  
> Er wird nicht über MCP in Cursor exponiert, sondern direkt als Python-App ausgeführt.
> Geeignet für Backend-Services oder Standalone-Skripte.

## Detaillierte Vergleichstabelle

### Developer Experience

| Dimension | Ansatz A Python MCP | Ansatz B n8n MCP | Ansatz C LangGraph |
|------|:-----------------:|:--------------:|:----------------:|
| Entwicklungsstil | Handgeschriebener Code | Drag-and-drop Nodes | Handgeschriebener Code |
| Lernaufwand | Python + asyncio + MCP SDK | n8n-Grundlagen | Python + LangGraph + ReAct |
| Entwicklungszeit | ~2 Stunden | ~20 Minuten | ~3 Stunden |
| Codezeilen | 307 | 0 (Konfiguration) | ~450 (3 Dateien) |
| Debugging | Logs / Breakpoints | Visuelle Node-Ausgaben | `--stream` schrittweise |
| Versionskontrolle | `.py` Dateien | `workflow.json` | `.py` Dateien |

### Laufzeitumgebung

| Dimension | Ansatz A Python MCP | Ansatz B n8n MCP | Ansatz C LangGraph |
|------|:-----------------:|:--------------:|:----------------:|
| Ausführungsort | Lokaler Prozess | n8n-Cloud-Instanz | Lokaler Prozess |
| Transportprotokoll | stdio | SSE / HTTP | Kein Protokoll (Direktaufruf) |
| Cursor-Integration | `mcp.json` | `mcp.json` (url) | Unabhängige Ausführung |
| Anzahl Datenquellen | 1 (HKO) | 1 (HKO) | 5 (mehrere Institute) |
| Python-Version | >= 3.11 | Nicht erforderlich | >= 3.11 |

### Funktionen und Performance

| Dimension | Ansatz A Python MCP | Ansatz B n8n MCP | Ansatz C LangGraph |
|------|:-----------------:|:--------------:|:----------------:|
| Datenquelle | HKO (Single Source) | HKO (Single Source) | NOAA+HKO+JMA+IRI+BOM (Multi Source) |
| Paralleles Laden | `asyncio.gather()` | Fan-out parallel | ToolNode parallel |
| AI-Analysemodell | gemini-3-flash-preview | gemini-2.5-flash | gemini-2.5-flash |
| Inferenzmodus | Single-Turn (fixer Flow) | Single-Turn (fixer Flow) | ReAct Multi-Turn Schleife |
| Adaptiver Tool-Aufruf | Nein | Nein | Ja, dynamische LLM-Entscheidung |
| Fehlerbehandlung | 3-stufige Fallback-Logik | Node-Ebene | Tool liefert Fehlertext |
| Antwortzeit | ~15-20s | ~15-25s | ~25-30s |
| Konversationsspeicher | Nein | Nein | Ja, Nachrichtenhistorie |

### Betrieb und Erweiterbarkeit

| Dimension | Ansatz A Python MCP | Ansatz B n8n MCP | Ansatz C LangGraph |
|------|:-----------------:|:--------------:|:----------------:|
| Monitoring | Eigene Logs | n8n-Ausführungsverlauf | LangSmith Tracing |
| Geplante Ausführung | Zusätzliche Entwicklung nötig | Schedule Trigger | Zusätzliche Entwicklung nötig |
| Neue Datenquelle hinzufügen | Neues Tool registrieren | HTTP-Node hinzufügen | `@tool`-Funktion hinzufügen |
| Multi-Turn-Dialog | Nein | Nein | Ja, History-Passing |
| Teamzusammenarbeit | Code Review | Visueller Workflow | Code Review |

---

## Reales Laufprotokoll (LangGraph)

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

**Ausführungsstatistik:**

| Kennzahl | Wert |
|------|------|
| Gesamtlatenz | ~26 Sekunden |
| ReAct-Schleifenrunden | 2 |
| Tatsächlich genutzte Tools | 4 (BOM nicht getriggert; vorhandene Daten reichten aus) |
| Gesamtmenge Rückgabedaten | ~14.570 Zeichen |
| Modell | gemini-2.5-flash (`temperature=0`) |

---

## Technische Entsprechung der drei Ansätze

```text
Funktion              Python MCP        n8n MCP               LangGraph
──────────────────────────────────────────────────────────────────────────
Tool-Einstieg         @server.call_tool() MCP Server Trigger  @tool function
LLM-Aufruf            genai.Client      Google Gemini node    ChatGoogleGenerativeAI
Parallele Requests    asyncio.gather()  Fan-out links         ToolNode parallel
HTML-Parsing          BeautifulSoup     Code node JS          BeautifulSoup
Transport             stdio             SSE / HTTP            None (direct call)
Dialogspeicher        None              None                  add_messages
Dynamische Toolwahl   None (fixed flow) None (fixed flow)    LLM ReAct loop
```

---

## Entscheidungshilfe

```text
MCP-Integration mit Cursor/Claude benötigt?
    -> Ansatz A (Python) oder Ansatz B (n8n)

Schneller Prototyp / nicht-technisches Team?
    -> Ansatz B (n8n)

Mehrere Datenquellen / adaptive Inferenz / Multi-Turn-Dialog?
    -> Ansatz C (LangGraph)

Feingranulare Kontrolle / leichtgewichtige Abhängigkeiten?
    -> Ansatz A (Python MCP)
```

### Entscheidungsbaum

```text
Cursor MCP integration needed?
    Yes ↓                           No -> Approach C (LangGraph)
    ├─ Have n8n instance?
    │       Yes -> Approach B (n8n)
    │       No ↓
    └─ Need multi-source data or complex logic?
            Yes -> Approach A (Python) + optionally connect C as backend
            No  -> Approach A (Python, simplest path)
```

---

## Schnellstart

### Ansatz A: Python Coding MCP

```bash
cd python-enso-clam-agent-app
cp .env.example .env
# .env bearbeiten und GEMINI_API_KEY setzen
source .venv/bin/activate
python3 enso_server.py
```

`~/.cursor/mcp.json` Konfiguration:

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

### Ansatz B: n8n MCP

```bash
# 1. n8n-enso-mcp-demo/workflow.json in n8n importieren
# 2. Google Gemini API Key konfigurieren
# 3. Workflow aktivieren und SSE-Endpoint-URL kopieren
```

`~/.cursor/mcp.json` Konfiguration:

```json
{
  "mcpServers": {
    "enso-n8n": {
      "url": "https://your-n8n-instance/mcp/YOUR_WORKFLOW_ID/sse"
    }
  }
}
```

### Ansatz C: LangGraph Agent

```bash
cd langchain-agent-app
cp .env.example .env
# .env bearbeiten und GEMINI_API_KEY setzen
source .venv/bin/activate

# Stream-Modus (empfohlen; zeigt jeden Reasoning-Schritt)
python main.py --stream "Analyze the current ENSO condition in East Asia"

# Einmalige Frage
python main.py --once "Is it El Nino or La Nina now?"

# Multi-Turn interaktiver Dialog
python main.py
```

> Vor dem Open-Source-Release sicherstellen, dass keine `.env`, echten API-Keys, Zugangsdaten oder andere Secrets im Repository enthalten sind.

---

## Referenzen

- [MCP Official Docs](https://modelcontextprotocol.io/)
- [n8n MCP Server Trigger Docs](https://docs.n8n.io/)
- [LangGraph Docs](https://langchain-ai.github.io/langgraph/)
- [Google Gemini API](https://ai.google.dev/gemini-api/docs)
- [HKO ENSO Page](https://www.hko.gov.hk/tc/lrf/enso/enso-latest.htm)
- [NOAA ONI Index](https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/ensostuff/ONI_v5.php)
- [IRI ENSO Forecast](https://iri.columbia.edu/our-expertise/climate/forecasts/enso/current/)

## Datenquellen

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
