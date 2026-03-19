"""
main.py — 对话入口（CLI 模式）
================================
对应 n8n 工作流中的：When chat message received 触发节点

运行方式：
    python main.py                  # 交互式对话
    python main.py --once "问题"    # 单次问答
    python main.py --stream "问题"  # 流式输出（逐步显示推理过程）
"""

import argparse
import asyncio
import sys

from agent import chat, chat_async, get_graph
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


def _print_step(step: dict):
    """
    打印 LangGraph 每一步的状态变化（stream 模式专用）。

    stream() 返回的是每个节点执行后的状态增量，格式为：
        {"agent": {"messages": [AIMessage(...)]}}
        {"tools": {"messages": [ToolMessage(...), ToolMessage(...)]}}

    通过观察每一步，可以清楚看到 ReAct 的推理过程：
        Step 1 [agent]  → LLM 决定调用哪些工具
        Step 2 [tools]  → 工具执行结果
        Step 3 [agent]  → LLM 综合结果，输出最终答案
    """
    for node_name, node_output in step.items():
        messages = node_output.get("messages", [])
        for msg in messages:
            if isinstance(msg, AIMessage):
                if msg.tool_calls:
                    tools_called = [tc["name"] for tc in msg.tool_calls]
                    print(f"\n🤔 [Agent 推理] 决定调用工具: {', '.join(tools_called)}")
                else:
                    # Gemini 2.5 返回 list[dict]，统一提取纯文本
                    content = msg.content
                    if isinstance(content, list):
                        content = "\n".join(
                            p.get("text", "") if isinstance(p, dict) else str(p)
                            for p in content
                        )
                    print(f"\n📊 [Agent 最终回答]\n{content}")
            elif isinstance(msg, ToolMessage):
                preview = msg.content[:200].replace("\n", " ")
                print(f"  🌐 [{msg.name}] 返回 {len(msg.content)} 字: {preview}...")


def run_interactive():
    """
    交互式多轮对话模式。

    演示 Simple Memory 的效果：
        第1轮：问当前 ENSO 状态
        第2轮：问与去年同期对比（LLM 能记住上轮结果）
        第3轮：问对中国农业的影响（LLM 继续在同一上下文中推理）
    """
    print("="*60)
    print("ENSO 气候分析 Agent（LangGraph）")
    print("输入问题，按 Enter 发送；输入 'quit' 退出；输入 'reset' 清空记忆")
    print("="*60)

    history = []

    while True:
        try:
            user_input = input("\n你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not user_input:
            continue
        if user_input.lower() == "quit":
            print("再见！")
            break
        if user_input.lower() == "reset":
            history = []
            print("[记忆已清空]")
            continue

        print("\n⏳ Agent 正在分析（约 20-40 秒）...\n")

        try:
            reply, history = chat(user_input, history)
            print(f"\nAgent: {reply}")
            print(f"\n[对话轮次: {sum(1 for m in history if isinstance(m, HumanMessage))}]")
        except Exception as e:
            print(f"\n[错误] {e}")
            print("提示：检查网络连接和 GEMINI_API_KEY 是否有效")


def run_once(question: str):
    """单次问答模式，适合脚本调用。"""
    print(f"问题: {question}\n")
    print("⏳ 分析中...\n")

    reply, history = chat(question)
    print(reply)

    # 统计工具调用情况
    tool_calls = [m for m in history if isinstance(m, ToolMessage)]
    print(f"\n[共调用 {len(tool_calls)} 个工具: {', '.join(m.name for m in tool_calls)}]")


def run_stream(question: str):
    """
    流式输出模式：实时显示 Agent 的每一步推理过程。

    选择流式输出的原因：
        总耗时 25-40s，用户体验很差
        stream() 让用户能实时看到"Agent 正在调用 NOAA 工具..."
        感知等待时间大幅降低

    ⚠️ stream() 与 invoke() 的区别：
        invoke()：等待全部完成后一次性返回最终结果
        stream()：每个节点执行完毕后立即推送状态增量
    """
    from langchain_core.messages import HumanMessage

    print(f"问题: {question}\n")
    print("="*60)

    graph = get_graph()

    for step in graph.stream(
        {"messages": [HumanMessage(content=question)]},
        config={"recursion_limit": 10},
        stream_mode="updates",
    ):
        _print_step(step)

    print("\n" + "="*60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ENSO 气候分析 Agent")
    parser.add_argument("--once", type=str, help="单次问答模式")
    parser.add_argument("--stream", type=str, help="流式输出模式（显示推理过程）")
    args = parser.parse_args()

    if args.once:
        run_once(args.once)
    elif args.stream:
        run_stream(args.stream)
    else:
        run_interactive()
