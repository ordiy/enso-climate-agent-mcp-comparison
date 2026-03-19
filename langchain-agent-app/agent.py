"""
agent.py — LangGraph ReAct Agent 核心实现
==========================================
对应 n8n 工作流中的：
    AI Agent 节点（决策+推理）
    Google Vertex Chat Model（LLM）
    Simple Memory（对话历史）
    Tool 节点的路由逻辑（有工具调用 → 执行工具；无 → 输出结果）

选型说明：
  LangGraph vs LangChain AgentExecutor
  ┌─────────────────────┬──────────────────────────────────┐
  │ LangChain Executor  │ 内部循环不可见，调试困难          │
  │ LangGraph           │ 每个节点状态可观测，可随时中断    │
  └─────────────────────┴──────────────────────────────────┘
  → 选 LangGraph，原因：生产可维护性 > 代码量

  langchain-google-genai vs langchain-google-vertexai
  ┌─────────────────────────┬──────────────────────────────┐
  │ langchain-google-genai  │ 直接用 API Key，无需 GCP 项目 │
  │ langchain-google-vertex │ 需要 GCP 项目和服务账号       │
  └─────────────────────────┴──────────────────────────────┘
  → 选 langchain-google-genai，原因：开发简单，与 n8n 截图模型等价

ReAct 模式说明（Reasoning + Acting）：
  LLM 在每一步先 Reason（分析需要哪个工具），再 Act（调用工具），
  收到工具结果后再 Reason，循环直到得出最终答案。
  这与 n8n AI Agent 节点的内部机制完全一致。
"""

import os
from typing import Annotated

from dotenv import load_dotenv
from langchain_core.messages import SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

from tools import ENSO_TOOLS

load_dotenv()

# ── System Prompt ─────────────────────────────────────────────────────────────
#
# System Prompt 的设计决策：
#   1. 明确角色：气候专家，专注 ENSO 分析
#   2. 列出可用工具和各自的数据特点（帮助 LLM 选择正确工具）
#   3. 规定输出格式：结构化报告（与 n8n 版本保持一致）
#
# ⚠️ 最容易出错的地方：
#   System Prompt 描述不够清晰时，LLM 会：
#   - 同时调用所有5个工具（浪费时间和 token）
#   - 只调用1个工具就输出结论（数据不完整）
#   - 每次调用同一工具多次（LangGraph 无次数限制，可能死循环）
SYSTEM_PROMPT = """你是一位专业气候分析专家，专注于 ENSO（厄尔尼诺-南方涛动）分析。

## 可用数据源工具
- fetch_noaa_oni：NOAA ONI 指数，ENSO 状态官方判断标准（首选）
- fetch_hko_report：香港天文台，东亚/华南气候影响分析
- fetch_jma_outlook：日本气象厅，亚太季节预测
- fetch_iri_forecast：哥伦比亚大学 IRI，多模式集合概率预测
- fetch_bom_outlook：澳大利亚气象局，南太平洋/SOI 指数

## 分析原则
1. 综合多个数据源（至少3个），避免单源偏差
2. 先调用 fetch_noaa_oni 获取 ONI 基准值，再调用其他补充数据源
3. 每个工具只调用一次，不重复

## 输出格式（Markdown）
## 1. 当前 ENSO 状态
## 2. 关键监测指数与趋势
## 3. 对东亚地区的气候影响
## 4. 未来 1-3 个月预测
## 5. 数据来源说明"""


# ── State 定义 ────────────────────────────────────────────────────────────────
#
# 为什么用 TypedDict + Annotated[list, add_messages]：
#   - TypedDict：提供静态类型检查，IDE 自动补全
#   - add_messages：LangGraph 内置的 reducer，自动将新消息追加到历史列表
#     而非覆盖，这就是 n8n Simple Memory 的等价实现
#
# Simple Memory 的实现原理：
#   每次 graph.invoke() 传入完整的 messages 历史
#   → LLM 在上下文中看到所有历史对话
#   → 实现多轮对话记忆（无持久化，进程退出即消失）
#
# ⚠️ 性能瓶颈：
#   随着对话轮次增加，messages 列表不断增长
#   当历史消息 + 工具结果超过 LLM 上下文窗口时会报错
#   生产环境应使用 langgraph.checkpoint.SqliteSaver 或 PostgresSaver
#   并配合 ConversationSummaryMemory 压缩长历史
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


# ── LLM 初始化 ────────────────────────────────────────────────────────────────
#
# 选 ChatGoogleGenerativeAI 的原因：
#   - 直接用 GEMINI_API_KEY，无需 GCP 项目配置
#   - 与 n8n 截图中的 Google Vertex Chat Model 使用相同底层模型
#   - gemini-2.0-flash：速度/质量最佳平衡点，支持 function calling
#
# temperature=0 的原因：
#   气候数据分析需要确定性输出，不需要创意发散
#   高 temperature 会导致工具选择随机性增加
def _build_llm():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("缺少 GEMINI_API_KEY，请在 .env 或系统环境变量中配置后重试。")

    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=api_key,
        temperature=0,
    )


# ── Graph 节点定义 ────────────────────────────────────────────────────────────

def build_agent_node(llm_with_tools):
    """
    构建 agent_node 函数（对应 n8n AI Agent 节点）。

    agent_node 的职责：
      接收当前 State → 调用 LLM（附带工具列表）→ 返回 LLM 的响应
      LLM 的响应有两种可能：
        a) AIMessage with tool_calls → 需要执行工具
        b) AIMessage without tool_calls → 最终答案，流程结束

    为什么用闭包而不是全局变量：
      llm_with_tools 在 build_graph() 中创建，避免模块加载时就初始化 LLM
      （防止在 import 时触发网络请求或 Key 校验）
    """
    def agent_node(state: AgentState) -> dict:
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}
    return agent_node


def should_continue(state: AgentState) -> str:
    """
    路由函数（对应 n8n 中 AI Agent 节点的条件输出端口）。

    LangGraph 的条件边机制：
      此函数返回字符串 → LangGraph 根据返回值选择下一个节点
      "call_tools" → 跳转到 tool_node 执行工具
      END          → 流程结束，输出最终答案

    ⚠️ 潜在死循环风险：
      如果 LLM 持续返回 tool_calls 且工具返回错误信息，
      Agent 可能陷入无限循环。
      生产环境应在 build_graph() 中设置 recursion_limit 限制最大循环次数。
    """
    last_msg = state["messages"][-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "call_tools"
    return END


# ── Graph 构建 ────────────────────────────────────────────────────────────────

def build_graph():
    """
    构建并编译 LangGraph 状态图。

    图结构（等价于 n8n 画布的连线）：
                        ┌──────────────────────────────┐
                        │                              │
        START ──► [agent_node] ──有 tool_calls──► [tool_node]
                        │                              │
                        │无 tool_calls                 │
                        ▼                              │
                       END ◄──────────────────────────┘

    关键设计：tool_node → agent_node 的回边
      工具执行完毕后，结果作为 ToolMessage 加入 messages
      再次进入 agent_node，让 LLM 综合工具结果进行下一步推理
      这就是 ReAct 的"反复推理"机制

    recursion_limit=10 的含义：
      最多允许 10 次 agent↔tools 循环
      5 个工具各调用一次 = 5 次循环，10 次上限有足够余量
      防止 LLM 陷入死循环导致费用暴增
    """
    llm = _build_llm()
    llm_with_tools = llm.bind_tools(ENSO_TOOLS)

    tool_node = ToolNode(ENSO_TOOLS)

    builder = StateGraph(AgentState)
    builder.add_node("agent", build_agent_node(llm_with_tools))
    builder.add_node("tools", tool_node)

    builder.set_entry_point("agent")

    builder.add_conditional_edges(
        "agent",
        should_continue,
        {"call_tools": "tools", END: END},
    )
    builder.add_edge("tools", "agent")

    return builder.compile()


# ── 公开 API ──────────────────────────────────────────────────────────────────

# 单例：模块加载时构建一次，避免重复编译
_graph = None

def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def chat(user_input: str, history: list | None = None) -> tuple[str, list]:
    """
    对话入口函数（对应 n8n 的 When chat message received 触发节点）。

    参数：
        user_input: 用户当前输入
        history:    历史消息列表（实现多轮对话，等价于 n8n Simple Memory）

    返回：
        (assistant_reply, updated_history)
        updated_history 应传入下一次 chat() 调用，实现连续对话

    ⚠️ 性能瓶颈：
        graph.invoke() 是同步阻塞调用，完成时间 = 所有工具串行执行时间之和
        5 个工具 × 平均 5s = 约 25-40s（工具默认串行）
        优化方案见 chat_async()
    """
    from langchain_core.messages import HumanMessage

    if history is None:
        history = []

    graph = get_graph()
    result = graph.invoke(
        {"messages": history + [HumanMessage(content=user_input)]},
        config={"recursion_limit": 10},
    )

    updated_history = result["messages"]
    raw = updated_history[-1].content
    # Gemini 2.5 可能返回 list[dict]，统一提取纯文本
    if isinstance(raw, list):
        reply = "\n".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in raw)
    else:
        reply = raw
    return reply, updated_history


async def chat_async(user_input: str, history: list | None = None) -> tuple[str, list]:
    """
    异步对话入口（优化版）。

    为什么需要 async 版本：
        同步版本下，ToolNode 串行执行 5 个 HTTP 工具，约 25-40s
        异步版本下，ToolNode 并发执行，约 5-10s（瓶颈变为最慢的单个工具）

    ⚠️ 注意：需要将 tools.py 中的工具改为 async def + await httpx.AsyncClient
            否则 async 版本依然是同步执行，无性能提升
    """
    from langchain_core.messages import HumanMessage

    if history is None:
        history = []

    graph = get_graph()
    result = await graph.ainvoke(
        {"messages": history + [HumanMessage(content=user_input)]},
        config={"recursion_limit": 10},
    )

    updated_history = result["messages"]
    raw = updated_history[-1].content
    if isinstance(raw, list):
        reply = "\n".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in raw)
    else:
        reply = raw
    return reply, updated_history
