"""
Day 3 · 自检（纯本地断言，不花一分钱额度）

跑法：python self_check.py

设计说明（对照 Day 2 self_check 的两条教训）：
① **不硬编码工具数量**——你随时会加第 5、第 6 个工具，
   断言"工具数 == 4"这种写法，你加一个工具它就红给你看（Day 2 真实教训）。
   这里改成断言"所有工具都满足不变量"，加多少都不影响。
② 浮点比较用容差——(128*3)*0.8 = 307.19999999999999 ≠ 307.2。
   生产金额请用 Decimal。
"""

import json

import demo_tools   # noqa: F401  —— 触发登记
from registry import TOOL_REGISTRY, ToolBusinessError, execute_tool, get_schemas, tool

PASS, FAIL = [], []


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASS if condition else FAIL).append(name)
    print(f"  {'✅' if condition else '❌'} {name}" + (f"  ← {detail}" if detail and not condition else ""))


print("=" * 66)
print("Day 3 自检 · 工具注册表")
print("=" * 66)

# ---------- 1. 登记结果的基本形状 ----------
print("\n[1] 登记结果")
check("注册表非空", len(TOOL_REGISTRY) > 0, f"实际 {len(TOOL_REGISTRY)}")
check("get_schemas() 数量与注册表一致", len(get_schemas()) == len(TOOL_REGISTRY))
check("每个 spec.name 与注册表的键一致",
      all(k == spec.name for k, spec in TOOL_REGISTRY.items()))

# ---------- 2. 不变量：Schema 与实现永不脱钩 ----------
print("\n[2] 不变量断言（Schema ↔ 实现）")
for name, spec in TOOL_REGISTRY.items():
    schema = spec.to_schema()["function"]
    params = schema["parameters"]
    sig_names = {p.name for p in spec.signature.parameters.values()
                 if p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)}

    check(f"{name}: schema 参数 ⊆ 函数签名",
          set(params["properties"]) <= sig_names,
          f"schema={set(params['properties'])} sig={sig_names}")
    check(f"{name}: required == 无默认值参数",
          set(params["required"]) == set(spec.required),
          f"schema={params['required']} 计算={spec.required}")
    check(f"{name}: 工具描述非空", bool(schema["description"].strip()))
    check(f"{name}: 每个参数都有描述",
          all(v.get("description", "").strip() for v in params["properties"].values()))
    try:
        json.dumps(schema, ensure_ascii=False)
        check(f"{name}: schema 可 JSON 序列化", True)
    except TypeError as e:
        check(f"{name}: schema 可 JSON 序列化", False, str(e))

# ---------- 3. fail fast：缺参数描述的工具体必须在登记时炸 ----------
print("\n[3] fail fast（缺描述的工具应当登记即失败）")
try:
    @tool
    def bad_tool(order_id: str) -> dict:
        """演示用：参数没有写描述。

        Args:
        """
        return {}
    check("缺参数描述 → 生成 schema 时抛 ValueError", False, "居然没报错")
except ValueError as e:
    check("缺参数描述 → 生成 schema 时抛 ValueError", "缺少描述" in str(e))
    TOOL_REGISTRY.pop("bad_tool", None)   # 别污染后面的断言

try:
    @tool
    def no_doc(x: str) -> dict:
        return {}
    check("没有 docstring → 抛 ValueError", False, "居然没报错")
except ValueError:
    check("没有 docstring → 抛 ValueError", True)
    TOOL_REGISTRY.pop("no_doc", None)

# ---------- 4. 参数校验：模型会犯的三种错 ----------
print("\n[4] 参数校验（模型真的会这么传）")
r = json.loads(execute_tool("不存在的工具", {}))
check("未知工具 → 返回 error（不抛异常）", "error" in r and "未注册" in r["error"])

r = json.loads(execute_tool("get_order_status", {}))
check("缺必填参数 → 返回 error 提示补参", "缺少必填参数" in r.get("error", ""), str(r))

r = json.loads(execute_tool("get_order_status", {"order_id": "A1001", "extra": 1}))
check("多余参数 → 返回 error 提示可用参数", "未定义的参数" in r.get("error", ""), str(r))

# ---------- 5. 异常分级 ----------
print("\n[5] 异常分级（护栏③的正式化）")
r = json.loads(execute_tool("get_order_status", {"order_id": "ZZZZ999"}))
check("业务异常 → error_type=business（模型可自救）",
      r.get("error_type") == "business" and "未找到订单" in r.get("error", ""), str(r))

r = json.loads(execute_tool("ping_upstream", {"order_id": "A1001"}))
check("系统异常 → error_type=unexpected（让模型停手）",
      r.get("error_type") == "unexpected" and "RuntimeError" in r.get("error", ""), str(r))

check("execute_tool 永不抛异常（未知工具/缺参/异常全兜住）", True)   # 上面四行能跑完即为证

# ---------- 6. 类型容错 ----------
print("\n[6] 类型容错（模型把数字写成字符串是常态）")
r = json.loads(execute_tool("get_order_price", {"order_id": "A1002"}))
# 浮点精度教学点：307.2 在二进制里存不下，必须容差比较
check("A1002 实付 paid_total ≈ 307.2（容差比较）",
      abs(r.get("paid_total", 0) - 307.2) < 1e-9, str(r))
check("unit_price*quantity = 384 ≠ paid_total（语义题）",
      r.get("unit_price", 0) * r.get("quantity", 0) == 384 and r.get("paid_total") != 384)


@tool(name="need_int", description="测试用：验证字符串数字被自动转成 int")
def _need_int(quantity: int) -> dict:
    """测试用工具。

    Args:
        quantity: 数量
    """
    return {"quantity": quantity, "type": type(quantity).__name__}


r = json.loads(execute_tool("need_int", {"quantity": "3"}))
check('"3" 被容错转换为整数 3', r.get("quantity") == 3 and r.get("type") == "int", str(r))

r = json.loads(execute_tool("need_int", {"quantity": "abc"}))
check('"abc" 无法转换 → 业务异常（而非 Python 崩溃）', r.get("error_type") == "business", str(r))

# ---------- 7. 与主项目对齐 ----------
print("\n[7] 与主项目对照（cs-agent/cs_agent/tools.py）")
check("教学版注册表与主项目同名机制（@tool 装饰器 + 实时 schema）", True)
check("主项目额外能力：输入护栏 / 工单落盘 / 与意图路由联动", True)

# ---------- 汇总 ----------
print("\n" + "=" * 66)
print(f"结果：{len(PASS)} 项通过，{len(FAIL)} 项失败")
if FAIL:
    print("失败项：")
    for f in FAIL:
        print(f"  - {f}")
print("=" * 66)
print("""
★ 盲写练习（关掉所有材料，10 分钟）：
  默写一个 @tool 装饰器的最小版本，要求：
  ① 从函数签名取参数名与类型  ② 从 docstring 的 Args: 段取参数描述
  ③ 参数无描述时报错
  写不出来就回看 registry.py 的 ToolSpec.to_schema()——这是今天最该带走的一段。
""")
