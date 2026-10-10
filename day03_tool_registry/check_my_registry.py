"""
关卡一验证器：把你的手敲实现与参考实现逐字段比对。

用法（在 day03_tool_registry 目录下）：
    python check_my_registry.py my_registry.py     # 指定你的文件
    python check_my_registry.py                    # 默认找同目录 my_registry.py

它在做什么：
  同一个测试工具函数，分别交给**你的 @tool** 和**参考 registry.py 的 @tool**，
  然后把两份 JSON Schema 逐字段对比。
  这不是"看着像对的"，这是"结果必须一模一样"——
  最后一项还会检验 fail fast（参数缺描述必须报错）。

设计说明：验证器的输出要能**直接指向你哪里写错了**，
所以每条失败都带"常见原因"，而不是只丢一句 False。
"""

import importlib.util
import inspect
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

PASS, FAIL = [], []


def check(name: str, ok: bool, hint: str = "") -> None:
    (PASS if ok else FAIL).append((name, hint))
    print(f"  {'✅' if ok else '❌'} {name}")
    if not ok and hint:
        print(f"      ↳ 常见原因：{hint}")


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------- 测试用工具
def make_simple_tool():
    """一个参数有默认值、一个没有——用来验证 required 的计算。"""
    def sample(order_id: str, reason: str = "其他") -> dict:
        """查询订单信息（测试用）。

        Args:
            order_id: 订单编号，例如 A1001
            reason: 原因说明，默认「其他」
        """
        return {"ok": True}
    return sample


def make_typed_tool():
    """用来验证三种非字符串类型的映射。"""
    def typed(count: int, ratio: float, urgent: bool) -> dict:
        """类型映射测试（测试用）。

        Args:
            count: 数量，整数
            ratio: 比例，小数
            urgent: 是否加急
        """
        return {}
    return typed


def make_no_desc_tool():
    """参数缺描述——应当在登记或生成 schema 时报错。"""
    def bad(order_id: str) -> dict:
        """缺描述的测试工具。

        Args:
        """
        return {}
    return bad


def make_no_doc_tool():
    def nodoc(x: str) -> dict:
        return {}
    return nodoc


# ---------------------------------------------------------------- 取你的 spec
def get_schema(mod, name):
    """从你的实现里取出工具 schema——容忍三种写法。"""
    reg = getattr(mod, "TOOL_REGISTRY", None)
    if isinstance(reg, dict) and name in reg:
        spec = reg[name]
        if hasattr(spec, "to_schema"):
            return spec.to_schema()
    if hasattr(mod, "get_schemas"):
        for s in mod.get_schemas():
            if s.get("function", {}).get("name") == name:
                return s
    return None


def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else "my_registry.py"
    path = Path(arg)
    if not path.is_absolute():
        path = HERE / path
    if not path.exists():
        print(f"找不到文件：{path}")
        print("用法：python check_my_registry.py my_registry.py")
        sys.exit(2)

    import registry as ref   # 参考实现

    print("=" * 68)
    print(f"关卡一验证 · 你的实现：{path.name}")
    print("=" * 68)

    # ---------- 0. 能否导入 ----------
    print("\n[0] 模块导入")
    try:
        his = load_module(path)
        check("模块可正常导入", True)
    except Exception as e:
        check("模块可正常导入", False, f"{type(e).__name__}: {e}")
        print("\n导入都不过，先修语法/依赖，再回来。")
        sys.exit(1)

    check("存在 @tool 装饰器", hasattr(his, "tool"),
          "函数名应为 tool，且支持无参用法 @tool 和有参用法 @tool(name=...)")

    # ---------- 1. 装饰器语义 ----------
    print("\n[1] 装饰器语义（最常见的第一个坑）")
    original = make_simple_tool()
    original_sig = str(inspect.signature(original))
    try:
        returned = his.tool(original)
        check("tool() 返回的是原函数（不是包装器）",
              returned is original,
              "装饰器里应 return fn 本身；若返回了一个 wrapper，"
              "签名会变、单测和自调用都会出问题")
        check("返回值仍可调用且签名未变",
              str(inspect.signature(returned)) == original_sig,
              f"期望签名 {original_sig}，实际 {inspect.signature(returned)}")
    except Exception as e:
        check("tool() 返回的是原函数（不是包装器）", False, f"{type(e).__name__}: {e}")

    # 用同一个函数分别喂给两边，保证对比公平
    his.tool(make_simple_tool())
    ref.tool(make_simple_tool())
    his.tool(make_typed_tool())
    ref.tool(make_typed_tool())

    # ---------- 2. Schema 逐字段比对 ----------
    print("\n[2] Schema 逐字段比对（你的 vs 参考）")
    his_schema = get_schema(his, "sample")
    ref_schema = get_schema(ref, "sample")
    if his_schema is None:
        check("能取到 sample 的 schema", False,
              "没找到工具：请确认工具被登记进了 TOOL_REGISTRY（装饰器里要写入注册表）")
    else:
        check("能取到 sample 的 schema", True)
        check("外层 type == 'function'",
              his_schema.get("type") == "function")
        hf, rf = his_schema["function"], ref_schema["function"]
        check("name 正确", hf.get("name") == "sample", f"实际 {hf.get('name')!r}")
        check("description 只取 docstring 首段（不含 Args: 内容）",
              hf.get("description") == rf["description"],
              f"期望 {rf['description']!r}，实际 {hf.get('description')!r}；"
              "提示：用 doc.split('\\n\\n')[0] 取首段，别把 Args: 一起塞进去")
        hprops = hf.get("parameters", {}).get("properties", {})
        rprops = rf["parameters"]["properties"]
        check("参数名集合一致",
              set(hprops) == set(rprops),
              f"期望 {sorted(rprops)}，实际 {sorted(hprops)}；"
              "提示：参数要从函数签名（inspect.signature）取，不是手写")
        for pname, rp in rprops.items():
            hp = hprops.get(pname, {})
            check(f"参数 {pname} 的类型映射正确（{rp['type']}）",
                  hp.get("type") == rp["type"],
                  f"期望 {rp['type']}，实际 {hp.get('type')}；"
                  "提示：_TYPE_MAP 里 str→string / int→integer / float→number / bool→boolean")
            check(f"参数 {pname} 的描述从 docstring Args: 段解析到",
                  (hp.get("description") or "").strip() == rp["description"],
                  f"期望 {rp['description']!r}，实际 {hp.get('description')!r}；"
                  "提示：Args: 段里按 '参数名: 说明' 逐行解析")
        check("required == 无默认值的参数（reason 有默认值，不应进 required）",
              hf["parameters"].get("required") == rf["parameters"]["required"],
              f"期望 {rf['parameters']['required']}，实际 {hf['parameters'].get('required')}；"
              "提示：default is inspect.Parameter.empty 的才进 required")

    # ---------- 3. 三种类型映射（单独验一次） ----------
    print("\n[3] 类型映射（int / float / bool）")
    ht = get_schema(his, "typed")
    if ht is None:
        check("能取到 typed 的 schema", False, "同上：工具是否登记成功？")
    else:
        got = {k: v.get("type") for k, v in ht["function"]["parameters"]["properties"].items()}
        expect = {"count": "integer", "ratio": "number", "urgent": "boolean"}
        check("int→integer / float→number / bool→boolean",
              got == expect, f"期望 {expect}，实际 {got}")

    # ---------- 4. fail fast ----------
    print("\n[4] fail fast：错误必须在“登记/生成 schema”时炸，而不是运行时")
    try:
        his.tool(make_no_desc_tool())
        get_schema(his, "bad")
        check("参数缺描述 → 报错", False,
              "没有报错：请在生成 schema 时校验每个参数都有描述，缺了就 raise ValueError")
    except ValueError as e:
        check("参数缺描述 → 抛 ValueError", "缺少描述" in str(e) or "描述" in str(e),
              f"抛出了，但信息不够明确：{e}")
    except Exception as e:
        check("参数缺描述 → 抛 ValueError", False,
              f"抛的是 {type(e).__name__}，建议统一成 ValueError 并写清怎么修")
    else:
        getattr(his, "TOOL_REGISTRY", {}).pop("bad", None)

    try:
        his.tool(make_no_doc_tool())
        get_schema(his, "nodoc")
        check("没有 docstring → 报错", False, "没有 docstring 时 description 为空，应该 raise")
    except ValueError:
        check("没有 docstring → 抛 ValueError", True)
    except Exception as e:
        check("没有 docstring → 抛 ValueError", False, f"抛的是 {type(e).__name__}")
    else:
        getattr(his, "TOOL_REGISTRY", {}).pop("nodoc", None)

    # ---------- 5. 顺带看一眼你的 schema 长什么样 ----------
    print("\n[5] 你的 schema 实际长相（目测用）")
    if his_schema:
        print(json.dumps(his_schema, ensure_ascii=False, indent=2))

    # ---------- 6. execute_tool：如果手敲了，就一起验（不改用法也能验） ----------
    print("\n[6] execute_tool 行为（若你实现了它）")
    if not hasattr(his, "execute_tool"):
        print("  ⏭  未实现 execute_tool —— 关卡一只要求 to_schema + tool 装饰器，这一节跳过。")
    else:
        def biz_tool(order_id: str) -> dict:
            """业务异常演示。

            Args:
                order_id: 订单号
            """
            raise his.ToolBusinessError("订单不存在（业务异常）")

        def boom_tool(order_id: str) -> dict:
            """系统异常演示。

            Args:
                order_id: 订单号
            """
            raise RuntimeError("上游超时（系统异常）")

        def int_tool(quantity: int) -> dict:
            """类型容错演示。

            Args:
                quantity: 数量
            """
            return {"quantity": quantity}

        for maker in (biz_tool, boom_tool, int_tool):
            his.tool(maker)

        def run(name, args):
            try:
                return json.loads(his.execute_tool(name, args))
            except Exception as e:   # noqa: BLE001
                return {"__raised__": f"{type(e).__name__}: {e}"}

        r = run("不存在的工具", {})
        check("未知工具 → 返回 error 而不抛异常",
              "error" in r, f"实际：{r}")

        r = run("biz_tool", {})
        check("缺必填参数 → 返回 error", "error" in r, f"实际：{r}")

        r = run("biz_tool", {"order_id": "A1", "extra": 1})
        check("多余参数 → 返回 error", "error" in r, f"实际：{r}")

        r = run("biz_tool", {"order_id": "A1"})
        check("业务异常 → error_type=business",
              r.get("error_type") == "business",
              f"实际：{r}；提示：ToolBusinessError 要单独 except，别混进通用异常")

        r = run("boom_tool", {"order_id": "A1"})
        check("系统异常 → error_type=unexpected",
              r.get("error_type") == "unexpected",
              f"实际：{r}；提示：先 except 业务异常，再 except Exception 兜底")

        r = run("int_tool", {"quantity": "3"})
        check('类型容错："3" → 整数 3',
              r.get("quantity") == 3,
              f"实际：{r}；"
              "若报 NameError/AttributeError，多半是 execute_tool 里调用了没定义的辅助函数"
              "（比如 _coerce 只写了调用、没写实现）或类型转换逻辑不完整")

    # ---------- 汇总 ----------
    print("\n" + "=" * 68)
    print(f"结果：{len(PASS)} 项通过，{len(FAIL)} 项失败")
    if FAIL:
        print("需要修的：")
        for name, hint in FAIL:
            print(f"  ❌ {name}")
    else:
        print("🎉 第 1 关通过。把这段输出发我，然后进第 2 关。")
    print("=" * 68)
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
