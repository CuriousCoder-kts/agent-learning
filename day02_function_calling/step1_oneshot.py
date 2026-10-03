"""
Day 2 · step1 · 一次性工具调用（One-Shot）
==========================================
概念阶梯 ①/③ —— 停止权在【代码】手里

Agent 与工具增强问答的最小形态：
    第 1 次调模型 → 模型给出 Action（调什么工具）
    你的代码执行工具 → 把 Observation 喂回去
    第 2 次调模型 → 收尾作答（关键：tools=None，菜单已收走）

【本文件的核心设计】收尾调用 chat_once(messages, tools=None)——
模型即使还想再查，也没有菜单可点，只能基于已有观察硬答。
"停止权在代码"，就体现在这一个参数上。

【One-Shot 不是落后】查天气、查快递、查余额这类单工具问答，
生产中大量使用 one-shot：便宜（≤2 次请求）、快（少一轮往返）、可控（行为可枚举）。
选型一句话：任务需要"根据观察决定下一步"吗？不需要 → one-shot；需要 → step2。

【运行后观察】S2 退款问题里，模型被迫"心算" 259×0.8——
记下它的答案，等下与 step2 对比（那边模型可以再调 calculator）。
"""

import json

from llm_client import chat_once
from _tools import TOOL_IMPL, TOOLS_SCHEMA

SYSTEM_PROMPT = (
    "你是一名电商客服助手，可以调用工具查询订单信息、计算金额，"
    "然后用简洁的中文回答用户。"
)


def oneshot_agent(user_query: str, verbose: bool = True) -> dict:
    """一次性工具调用：最多 2 次模型请求。停止权在代码。"""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_query},
    ]

    # ── 第 1 次调用：模型决策（要不要工具、要哪个）──
    msg = chat_once(messages, TOOLS_SCHEMA)
    tool_calls = msg.get("tool_calls")

    if not tool_calls:
        # 连工具都不需要：1 次调用直接收工（one-shot 的最快路径）
        if verbose:
            print("[调用 1] 模型未请求工具，直接回答。")
        return {"answer": msg.get("content", ""), "model_calls": 1, "tool_exec": 0}

    # 协议要求：assistant 的 tool_calls 消息必须回存历史（Action 记录）
    messages.append(msg)

    # ── 执行这一轮工具（Observation 记录）──
    executed = 0
    for call in tool_calls:
        fn_name = call["function"]["name"]
        raw_args = call["function"]["arguments"]
        try:
            args = json.loads(raw_args) if raw_args else {}
        except json.JSONDecodeError:
            args = {}

        result = TOOL_IMPL[fn_name](**args) if fn_name in TOOL_IMPL \
            else {"error": f"未知工具：{fn_name}"}
        executed += 1

        if verbose:
            print(f"[调用 1] Action → {fn_name}({raw_args})")
            print(f"[调用 1] Observation ← {json.dumps(result, ensure_ascii=False)}")

        # Observation 以 role=tool 回传，tool_call_id 与请求一一对应
        messages.append({
            "role": "tool",
            "tool_call_id": call["id"],
            "content": json.dumps(result, ensure_ascii=False),
        })

    # ── 第 2 次调用：收尾。★ 关键：tools=None，菜单收走 ──
    # 若这里仍传 TOOLS_SCHEMA，模型很可能再要工具，而 one-shot 没有循环去执行，
    # 请求只能被丢弃，对话陷入未完成状态——这是真实项目最常见的"半吊子 one-shot"bug。
    final = chat_once(messages, tools=None)
    if verbose:
        print("[调用 2] 收尾作答（工具菜单已收走，模型只能基于已有观察）")
    return {"answer": final.get("content", ""), "model_calls": 2, "tool_exec": executed}


if __name__ == "__main__":
    # S1/S2/S3 与 step2 完全相同——跑完两边对比，差异自现
    scenarios = [
        ("S1 · 单工具问题（one-shot 的主场）", "帮我查一下订单 A1002 现在到哪了？"),
        ("S2 · 依赖链问题（one-shot 的软肋）",
         "帮我算一下订单 A1003 能退多少钱？\n"
         "规则：未签收全额退；已签收只退实付的 80%。\n"
         "金额和状态你自己查工具，不要来问我。"),
        ("S3 · 无需工具（常识问答）", "你们支持七天无理由退货吗？"),
    ]

    for label, q in scenarios:
        print("=" * 64)
        print(f"{label}\n用户：{q}\n")
        stats = oneshot_agent(q)
        print(f"\n回答：{stats['answer']}")
        print(f"[统计] 模型调用={stats['model_calls']}，工具执行={stats['tool_exec']}\n")

    # ── 跑完立即做 ──
    # 记下 S2 的退款金额答案（模型心算的 259×0.8），然后运行 step2_react.py 对比。
