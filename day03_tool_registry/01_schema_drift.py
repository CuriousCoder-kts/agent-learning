"""
Day 3 · 实验一：手写 Schema 的三种死法（纯本地，不花额度）

目的：让你**亲眼看到** Day 2 那种"函数 + 手写 Schema"的双份清单，
是怎么在三次普通改动里悄悄烂掉的。

跑法：python 01_schema_drift.py
"""

import json

from registry import TOOL_REGISTRY, get_schemas

print("=" * 68)
print("实验一：手写 Schema 的三种死法")
print("=" * 68)

# ---------------------------------------------------------------- 事故现场
# 假设 Day 2 时代你手写了这份 schema（节选），然后代码改了……

HANDWRITTEN_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "get_order_status",
            "description": "查询订单物流状态",
            "parameters": {
                "type": "object",
                "properties": {"order_id": {"type": "string", "description": "订单号"}},
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "计算器",
            # ← 手写时忘了写 parameters
        },
    },
]

print("\n【事故 ①】改了参数名，忘了改 schema")
print("  实现改成：def get_order_status(order_sn: str)")
print("  schema 仍写：{order_id}")
print("  后果：模型永远传 order_id → 实现报 TypeError: missing 'order_sn'")
print("        而模型看到的报错是「系统异常」，它会以为系统坏了，而不是自己传错了")
print("        一个改名动作，毁掉一个工具。\n")

print("【事故 ②】schema 缺了 parameters")
print("  calculator 那条没有 parameters 字段")
print("  后果：模型可能传 {}、也可能不传 → 工具时好时坏")
print("        最难查的 bug 不是必现的，是偶发的。\n")

print("【事故 ③】描述与实现不一致")
print("  描述写「计算器」，实现只能做四则运算、拒绝任何字母")
print("  后果：模型拿它算 sqrt、算复利 → 每次都被拒 → 步数浪费在重试上")
print("        描述是模型的说明书，写错说明书 = 教模型犯错。\n")

# ---------------------------------------------------------------- 注册表怎么治
# import demo_tools 的瞬间，四个工具就登记完了
import demo_tools   # noqa: E402  （放在这里就是为了让你看到"import 即注册"）

print("=" * 68)
print("注册表方案：schema 由函数实时生成，不存在第二份清单")
print("=" * 68)
for schema in get_schemas():
    fn = schema["function"]
    params = fn["parameters"]
    props = ", ".join(f"{k}:{v['type']}" for k, v in params["properties"].items())
    print(f"\n  {fn['name']}({props})")
    print(f"    描述：{fn['description'][:48]}…")
    print(f"    必填：{params['required']}")

print("\n" + "=" * 68)
print("现在请亲手做这两件事（做完你就真的懂了）：")
print("=" * 68)
print("""
  ① 打开 demo_tools.py，把 get_order_status 的参数 order_id 改名为 order_sn
     （函数体内三处也一起改），保存后重新运行本脚本——
     观察 schema 是否**自动**跟着变了。然后在 fc 脚本里跑一次，
     模型照样能正确调用（因为菜单和实现一起变了）。
     ★ 记住：这就是"改一处、全同步"的手感。

  ② 把某个参数的 Args: 描述那一行删掉，重新运行本脚本——
     报错会在 **import 时** 直接炸出来，而不是等模型瞎猜。
     ★ 这就是 fail fast：把错误拦在最早、最便宜的地方。

  做完把参数名改回来。（改完跑一次 self_check.py 确认全绿）
""")
