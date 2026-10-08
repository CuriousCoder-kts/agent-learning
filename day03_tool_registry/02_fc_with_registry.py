"""
Day 3 · 实验二：注册表 + FC 循环（真实 API，这是今天唯一花钱的脚本）

与 Day 2 的 step3_guardrails.py 是什么关系？
  · 循环骨架、护栏思想完全一样（Day 2 的成果直接复用）
  · 唯一升级：工具菜单不再硬编码，而是 `get_schemas()` 从注册表实时取
    → 加工具 = 写一个函数 + 一个装饰器，主循环一个字都不用改

三个场景（s2 最值得盯）：
  s1  查订单        → 一次工具调用，正常收尾
  s2  退款能退多少  → 必须先调 get_order_price 拿实付 307.2，不能心算 384
  s3  查不存在的单  → 工具抛业务异常 → 回传 Observation → 模型自己换思路
  s3b 格式就错的单  → 模型可能**自己识破**、根本不调工具（实测如此）
  s4  上游故障工具  → 系统异常被兜住 → 模型被告知"别重试"，如实告知用户

★ 诚实提示：LLM 是非确定性的。同一个 s3，模型也可能像 s3b 那样先自己判格式。
  两种行为都对——**观察点不是"必须调工具"，而是"它有没有拿到真实数据再回答"**。
  这也是为什么主项目要建评测集：靠单次运行下结论是不严谨的。

跑法：python 02_fc_with_registry.py
"""

import json

import demo_tools   # noqa: F401  —— import 即完成工具登记（副作用即注册）
from llm_client import chat_once
from registry import TOOL_REGISTRY, execute_tool, get_schemas

SYSTEM_PROMPT = """你是一名电商客服助手。你可以调用工具查询真实数据。

规则：
1. 需要订单数据时必须调工具，禁止凭空编造订单信息。
2. 涉及金额（退款、赔付）必须先调用工具拿到实付金额，禁止用单价心算。
3. 工具返回 error 时：business 类错误请换个参数或如实告知用户；
   unexpected 类错误不要重试同一调用，直接告知用户并建议转人工。
4. 信息不足时（如没给订单号）先礼貌追问。
5. 回答简洁口语化，不要提及"工具""函数"这类词。"""


def run_agent(user_query: str, max_steps: int = 6) -> dict:
    """注册表版 FC 循环：与 Day 2 骨架同源，护栏照旧，菜单改由注册表提供。"""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_query},
    ]
    schema = get_schemas()          # ← 唯一与 Day 2 不同的地方
    seen_calls: set[str] = set()    # 护栏②：同参数去重（每轮独立，跨轮不累积）
    tools_used: list[str] = []
    trace: list[str] = []

    for step in range(1, max_steps + 1):   # 护栏①：max_steps
        msg = chat_once(messages, tools=schema)
        messages.append(msg)
        calls = msg.get("tool_calls") or []

        if not calls:
            return {"answer": msg.get("content", ""), "steps": step,
                    "tools_used": tools_used, "trace": trace}

        for call in calls:
            name = call["function"]["name"]
            raw = call["function"]["arguments"] or "{}"
            signature = f"{name}:{raw}"

            if signature in seen_calls:
                observation = json.dumps(
                    {"warning": f"已用相同参数调用过 {name}，请勿重复，换个思路或直接作答"},
                    ensure_ascii=False)
                trace.append(f"step{step} ↻ {name}（重复，已拦截）")
            else:
                seen_calls.add(signature)
                observation = execute_tool(name, json.loads(raw))   # 护栏③在 registry 内部
                tools_used.append(name)
                trace.append(f"step{step} → {name}({raw})")
                print(f"    [step{step}] {name}({raw})")
                print(f"            ← {observation[:150]}")

            messages.append({"role": "tool", "tool_call_id": call["id"], "content": observation})

    return {"answer": "（达到最大步数上限，已转人工）", "steps": max_steps,
            "tools_used": tools_used, "trace": trace}


SCENARIOS = [
    ("s1 常规查询", "订单 A1001 到哪了？"),
    ("s2 金额依赖链", "订单 A1002 显示签收了但我没收到，我要退款，能退多少？"),
    ("s3 业务异常自救", "帮我查一下订单 A9999 的状态"),   # 格式对但不存在 → 必然触发业务异常
    ("s3b 格式自检", "订单 ZZZZ999 到哪了？"),            # 模型很可能自己识破格式，不调工具
    ("s4 系统异常兜底", "用健康检查工具 ping 一下订单系统，订单号 A1001"),
]

if __name__ == "__main__":
    print("=" * 70)
    print(f"Day 3 · 注册表版 FC 循环｜已登记工具：{', '.join(TOOL_REGISTRY)}")
    print("=" * 70)
    for label, query in SCENARIOS:
        print(f"\n【{label}】{query}")
        result = run_agent(query)
        print(f"  → 回复：{result['answer']}")
        print(f"  → 步数={result['steps']}  调用工具={result['tools_used']}")

    print("""
--------------------------------------------------------------------
看完 s2 请回答自己：模型拿到的是 307.2 还是 384？
  如果是 384，说明工具契约缺了语义（回看 demo_tools.get_order_price 的 docstring）。
看完 s3/s4 请回答自己：两条 error 的 error_type 分别是什么？
  为什么 business 可以让模型继续尝试，unexpected 必须让它停手？
--------------------------------------------------------------------
""")
