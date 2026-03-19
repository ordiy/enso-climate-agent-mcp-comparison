# ENSO 气候分析 — n8n MCP Server Demo

用 **n8n 可视化工作流** 实现与 Python 版本完全等价的 ENSO 气候分析 MCP 服务。
无需编写代码，通过拖拽节点配置完成。

---

## 工作流结构

```
[MCP Server Trigger]
    │  工具名：analyze_enso_situation
    │
    ├──────────────────────┐
    ▼                      ▼
[HTTP Request]        [HTTP Request]       ← 并行抓取（n8n 自动并发）
 英文版 HKO 页面       中文版 HKO 页面
    │                      │
    └──────────┬───────────┘
               ▼
         [Code 节点]                       ← 提取 HTML 纯文本
          JS 去除标签
               │
               ▼
        [Google Gemini]                    ← AI 分析生成报告
         gemini-2.5-flash
               │
               ▼
          返回报告给 Cursor
```

---

## 快速部署

### Step 1：导入工作流

1. 打开 n8n 实例（本地或云端）
2. 进入 **Workflows** → **Import from file**
3. 选择本目录的 `workflow.json`

### Step 2：配置 Gemini 凭证

1. 进入 **Credentials** → **New Credential**
2. 搜索 `Google Gemini`
3. 填入你自己的 Gemini API Key（不要提交到仓库）
4. 保存并在 Gemini Analysis 节点中选择该凭证

### Step 3：激活工作流

1. 点击右上角 **Active** 开关，启用工作流
2. 复制 MCP Server Trigger 节点显示的 **SSE Endpoint URL**

### Step 4：配置 Cursor

编辑 `~/.cursor/mcp.json`：

```json
{
  "mcpServers": {
    "enso-n8n": {
      "url": "https://your-n8n-instance/mcp/YOUR_WORKFLOW_ID/sse"
    }
  }
}
```

### Step 5：验证

在 Cursor Chat 输入：
```
分析东亚地区当前的ENSO情况
```

---

## 节点说明

### MCP Server Trigger

| 参数 | 值 |
|------|-----|
| Tool Name | `analyze_enso_situation` |
| Description | 抓取香港天文台最新ENSO数据，使用Gemini AI分析东亚气候 |
| Input Schema | 无参数（数据源固定） |

MCP Server Trigger 会自动生成两个端点：
- **SSE Endpoint**：`/mcp/{id}/sse` — 供 Cursor 建立长连接
- **Message Endpoint**：`/mcp/{id}/message` — 接收 JSON-RPC 消息

### HTTP Request × 2（并行抓取）

n8n 通过 **分叉连接**（Fan-out）实现并发：MCP Trigger 同时连接两个 HTTP Request 节点，n8n 引擎自动并行执行。

| 节点 | URL |
|------|-----|
| Fetch HKO EN | `https://www.hko.gov.hk/en/lrf/enso/enso-latest.htm` |
| Fetch HKO ZH | `https://www.hko.gov.hk/tc/lrf/enso/enso-latest.htm` |

Headers 设置：
```
User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)...
Accept-Language: zh-TW,zh;q=0.9,en;q=0.8
```

### Code 节点（文本提取）

用 JavaScript 去除 HTML 标签，提取纯文本：

```javascript
function extractText(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/<style[\s\S]*?<\/style>/gi, '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .substring(0, 4000);  // 防御性截断
}
```

### Google Gemini 节点

| 参数 | 值 |
|------|-----|
| Model | `gemini-2.5-flash` |
| Prompt | 结构化4段式分析 Prompt（见 workflow.json） |

---

## curl 测试

```bash
# 初始化连接
curl -X POST \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  https://your-n8n-instance/mcp/YOUR_ID \
  -d '{
    "jsonrpc": "2.0", "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {"name": "curl-test", "version": "1.0"}
    }
  }'

# 列出工具
curl -X POST \
  -H "Content-Type: application/json" \
  https://your-n8n-instance/mcp/YOUR_ID \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'

# 调用工具
curl -X POST \
  -H "Content-Type: application/json" \
  https://your-n8n-instance/mcp/YOUR_ID \
  -d '{
    "jsonrpc":"2.0","id":3,
    "method":"tools/call",
    "params":{"name":"analyze_enso_situation","arguments":{}}
  }'
```

---

## 与 Python 版本的等价关系

| Python 代码 | n8n 节点 |
|------------|---------|
| `asyncio.gather(fetch_zh, fetch_en)` | MCP Trigger → 并行连接两个 HTTP Request |
| `BeautifulSoup(...).get_text()` | Code 节点（JS 去除 HTML 标签） |
| `asyncio.to_thread(genai.generate_content)` | Google Gemini 节点（内部异步处理） |
| `@server.list_tools()` | MCP Server Trigger 的工具元数据配置 |
| `@server.call_tool()` | 整条工作流的执行逻辑 |
| `stdio_server()` | n8n 自动管理 SSE/HTTP 传输层 |
