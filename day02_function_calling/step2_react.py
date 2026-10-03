"""
Day 2 · step2 · ReAct 循环
==========================
概念阶梯 ②/③ —— 停止权交给【模型】

★ 与 step1 的差异，全文件只有两处：
  ① 外面套了 for 循环——模型可以多轮"决策 → 执行 → 观察 → 再决策"；
  ② 没有"收尾调用收走菜单"这回事——停止条件改为"模型不再请求工具"。
一句话：**停止权从代码手里交给了模型。这就是 ReAct。**

ReAct 三段式在现代 Function Calling 协议里的对应物（面试必答）：
    Thought（思考）    → 模型内部推理（推理模型可见 reasoning_content 字段）
    Action（行动）     → message.tool_calls（结构化数据，不再是文本）
    Observation（观察）→ role="tool" 的消息（用 tool_call_id 与请求配对）

2022 年 ReAct 论文问世时没有 FC 接口：模型被迫输出
"Thought: ... / Action: search[query]" 这样的**文本**，harness 用正则解析执行，
再把 "Observation: ..." 拼回 prompt。现代协议只是把这三段结构化了——同构换马甲。

【本文件是今天最值得手敲的文件】敲不出来的地方，就是知识洞。
"""

import json

from llm_client import chat_once
from _tools import TOOL_IMPL, TOOLS_SCHEMA

SYSTEM_PROMPT = (
    "你是一名电商客服助手，可以调用工具查询订单信息、计算金额。"
    "每一步先想清楚自己还缺什么信息，再决定是否调用工具；"   # ← 策略：显式鼓励迭代
    "如果信息已足够，就直接给出最终中文回答，不要再调用工具。"  # ← 策略：显式终止条件
)


def react_agent(user_query: str, max_steps: int = 5, verbose: bool = True) -> dict:
    """ReAct 循环：停止权在模型（模型不再要工具即停）。代码只兜底 max_steps。"""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_query},
    ]

    total_tool_exec = 0

    # ★ 差异 ①：循环。step1 是"决策→执行→收尾"三段写死；这里是"直到模型喊停"
    for step in range(1, max_steps + 1):
        msg = chat_once(messages, TOOLS_SCHEMA)
        tool_calls = msg.get("tool_calls")

        # ★ 差异 ②：停止条件。step1 靠"收尾调用不给菜单"；
        #    这里模型有菜单，但它自己决定不再点——停止权在模型
        if not tool_calls:
            if verbose:
                print(f"[Step {step}] 模型判断信息已足够 → 最终回答")
            return {"answer": msg.get("content", ""), "steps": step, "tool_exec": total_tool_exec}

        # Action 记录：assistant 的 tool_calls 消息必须回存（协议要求）
        messages.append(msg)

        for call in tool_calls:
            fn_name = call["function"]["name"]
            raw_args = call["function"]["arguments"]
            total_tool_exec += 1

            try:
                args = json.loads(raw_args) if raw_args else {}
            except json.JSONDecodeError:
                args = {}

            result = TOOL_IMPL[fn_name](**args) if fn_name in TOOL_IMPL \
                else {"error": f"未知工具：{fn_name}"}

            if verbose:
                print(f"[Step {step}] Action → {fn_name}({raw_args})")
                print(f"[Step {step}] Observation ← {json.dumps(result, ensure_ascii=False)}")

            # Observation 记录：role=tool + tool_call_id 配对
            messages.append({
                "role": "tool",
                "tool_call_id": call["id"],
                "content": json.dumps(result, ensure_ascii=False),
            })

    return {"answer": "（达到 max_steps，未收敛——这就是没有护栏的风险，见 step3）",
            "steps": max_steps, "tool_exec": total_tool_exec}


if __name__ == "__main__":
    # 与 step1 完全相同的 S1/S2/S3——对比答案与统计，差异自现
    scenarios = [
        ("S1 · 单工具问题", "帮我查一下订单 A1002 现在到哪了？"),
        ("S2 · 依赖链问题（ReAct 的主场）",
         "帮我算一下订单 A1003 能退多少钱？\n"
         "规则：未签收全额退；已签收只退实付的 80%。\n"
         "金额和状态你自己查工具，不要来问我。"),
        ("S3 · 无需工具（常识问答）", "你们支持七天无理由退货吗？"),
    ]

    for label, q in scenarios:
        print("=" * 64)
        print(f"{label}\n用户：{q}\n")
        stats = react_agent(q)
        print(f"\n回答：{stats['answer']}")
        print(f"[统计] 思考步数={stats['steps']}，工具执行={stats['tool_exec']}\n")

    # ── 跑完对照 step1 回答三个问题（写进 NOTES.md）──
    # 1. S2 的退款金额：step1（心算）与 step2（calculator）各是多少？谁对？
    # 2. S1/S3 两者行为几乎一样——那 ReAct 多花的 token 什么时候才值得？
    # 3. 注意 S2 里模型的调用顺序：它是不是先查状态/价格，看到结果后才调 calculator？
    #    "B 步的参数依赖 A 步的观察"——这就是 ReAct 买到的能力。
