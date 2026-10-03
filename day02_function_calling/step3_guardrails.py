"""
Day 2 · step3 · 生产护栏
========================
概念阶梯 ③/③ —— 模型有了自由，就需要护栏

★ 在 step2 基础上新增三道护栏（其余代码不变，可 diff 对照）：

  护栏① max_steps 5 → 8 + 明确的未收敛返回
       防：模型无限循环烧 token（自由是有账单的）
  护栏② seen_calls 去重——同一工具+同一参数只真执行一次，
       第二次返回 warning 提醒模型换思路
       防：模型原地打转（真实场景：模型"不放心"反复查同一订单）
  护栏③ 异常全量回传——工具抛任何异常都包装成 Observation 喂回去，
       让模型自己决定重试、换参数还是放弃
       防：一个工具崩溃杀死整个循环（step2 里工具抛 KeyError 会直接崩）

【为什么护栏是"生产"与"玩具"的分界线】
ReAct 给了模型自由，但自由 = 不可预测。
面试金句：**循环骨架 20 行写完，难的从来不是循环，
是策略（提示词）、记忆（历史维护）与护栏（防失控）。**
"""

import json

from llm_client import chat_once
from _tools import TOOL_IMPL, TOOLS_SCHEMA

SYSTEM_PROMPT = (
    "你是一名电商客服助手，可以调用工具查询订单信息、计算金额。"
    "每一步先想清楚自己还缺什么信息，再决定是否调用工具；"
    "如果信息已足够，就直接给出最终中文回答，不要再调用工具。"
)


def guardrailed_agent(user_query: str, max_steps: int = 8, verbose: bool = True) -> dict:
    """带三道护栏的 ReAct 循环——主项目 cs-agent 的引擎就直接长在这个函数上。"""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_query},
    ]

    # ★ 护栏② 的状态：记录已执行过的 (工具名:参数) 签名
    seen_calls = set()
    total_tool_exec = 0

    for step in range(1, max_steps + 1):        # ★ 护栏①：max_steps=8
        msg = chat_once(messages, TOOLS_SCHEMA)
        tool_calls = msg.get("tool_calls")

        if not tool_calls:
            if verbose:
                print(f"[Step {step}] 模型判断信息已足够 → 最终回答")
            return {"answer": msg.get("content", ""), "steps": step,
                    "tool_exec": total_tool_exec, "blocked_repeats": 0}

        messages.append(msg)

        for call in tool_calls:
            fn_name = call["function"]["name"]
            raw_args = call["function"]["arguments"]
            total_tool_exec += 1

            # ★ 护栏②：重复调用检测——同签名第二次不执行，改为提醒
            signature = f"{fn_name}:{raw_args}"
            if signature in seen_calls:
                result = {"warning": "该工具与参数的结果此前已给出。请基于已有信息作答，"
                                     "或改用其他工具/参数。"}
                if verbose:
                    print(f"[Step {step}] ⚠ 护栏②拦截重复调用 → {fn_name}({raw_args})")
            else:
                seen_calls.add(signature)
                try:
                    args = json.loads(raw_args) if raw_args else {}
                except json.JSONDecodeError:
                    args = {}
                try:
                    # ★ 护栏③：任何异常都包装成 Observation，而不是让循环崩溃
                    result = TOOL_IMPL[fn_name](**args) if fn_name in TOOL_IMPL \
                        else {"error": f"未知工具：{fn_name}"}
                except Exception as e:
                    result = {"error": f"工具执行异常：{e}"}

            if verbose:
                print(f"[Step {step}] Action → {fn_name}({raw_args})")
                print(f"[Step {step}] Observation ← {json.dumps(result, ensure_ascii=False)}")

            messages.append({
                "role": "tool",
                "tool_call_id": call["id"],
                "content": json.dumps(result, ensure_ascii=False),
            })

    return {"answer": "（达到 max_steps=8，仍未收敛——真实系统此时应转人工）",
            "steps": max_steps, "tool_exec": total_tool_exec,
            "blocked_repeats": len(seen_calls)}


if __name__ == "__main__":
    # S4/S5 是专为触发护栏设计的场景；S2 复跑用于看带护栏版的统计
    scenarios = [
        ("S2 · 依赖链问题（复跑对照 step2）",
         "帮我算一下订单 A1003 能退多少钱？\n"
         "规则：未签收全额退；已签收只退实付的 80%。\n"
         "金额和状态你自己查工具，不要来问我。"),
        ("S4 · 重复调用触发器（护栏②的舞台）",
         "帮我查 A1002 的状态。\n"
         "嗯……我有点不放心，再查一遍 A1002 确认一下吧。\n"
         "算了，还是再查一遍 A1002 吧，万一状态变了呢？"),
        ("S5 · 错误观察（护栏③的舞台：模型如何消化 error）",
         "帮我查一下订单 ZZZZ999 的状态；如果没有这个订单，"
         "就改查 A1003 的实付金额并告诉我。"),
    ]

    for label, q in scenarios:
        print("=" * 64)
        print(f"{label}\n用户：{q}\n")
        stats = guardrailed_agent(q)
        print(f"\n回答：{stats['answer']}")
        print(f"[统计] 思考步数={stats['steps']}，工具执行={stats['tool_exec']}\n")

    # ── 跑完思考（写进 NOTES.md）──
    # 1. S4：第 2、3 次"查 A1002"被拦截了吗？模型收到 warning 后做了什么？
    # 2. S5：模型看到 ZZZZ999 的 error 后，是直接放弃还是改查 A1003？
    #    "错误也是信息"——这就是护栏③把异常回传而不是崩溃的意义。
    # 3. 对比 S2 在 step2 与 step3 的步数——护栏有没有拖慢正常任务？
    #    （好护栏的标准：正常路径零感知，异常路径强干预。）
