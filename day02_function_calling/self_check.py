"""
Day 2 · 自检脚本（跑任何 step 之前，先跑我）
=============================================
纯本地断言：不调模型、不花一分钱、不需要 .env 里有真实 Key。

【设计哲学：断言"不变量"，不硬编码"数量"】
v1 的教训：断言"工具数量必须等于 2"，结果你自主加了 get_order_price，
断言立刻失败——是断言错了，不是你错了。
工具数量天然会增长，但下面这些不变量永远不该被破坏：
    · Schema 与实现一一对应（改了名字忘了另一边 = 上线即崩）
    · required 字段 ⊆ 函数签名（Schema 承诺的参数，函数必须接得住）
    · description 非空（模型唯一能看到的说明书，空 = 模型瞎选工具）
    · 返回值可 JSON 序列化（Observation 要拼进 messages 发回模型）
    · 异常输入不崩溃（工具崩 = 循环崩，step3 护栏③之前的最后防线）

全部通过再跑 step1/2/3。任何一项 FAIL：先修 _tools.py，再继续。
"""

import inspect
import json
import os
import sys

from _tools import TOOL_IMPL, TOOLS_SCHEMA

HERE = os.path.dirname(os.path.abspath(__file__))


def check_schema_impl_consistent():
    """不变量 1：每个 Schema 有实现，每个实现有 Schema（双向）"""
    schema_names = {t["function"]["name"] for t in TOOLS_SCHEMA}
    impl_names = set(TOOL_IMPL)
    only_schema = schema_names - impl_names
    only_impl = impl_names - schema_names
    assert not only_schema, f"Schema 声明了但没有实现：{only_schema}"
    assert not only_impl, f"实现了但没写 Schema（模型看不见=白写）：{only_impl}"
    return f"Schema ↔ Impl 一一对应，共 {len(schema_names)} 个工具"


def check_required_subset_of_signature():
    """不变量 2：Schema 里 required 的参数，函数签名必须接得住。
    反例：Schema 承诺 refund_apply 需要 order_id，但函数没有该参数——
    模型一旦按 Schema 调用，本地直接 TypeError。"""
    for t in TOOLS_SCHEMA:
        fn = TOOL_IMPL[t["function"]["name"]]
        sig_params = set(inspect.signature(fn).parameters)
        required = set(t["function"]["parameters"].get("required", []))
        missing = required - sig_params
        assert not missing, (
            f"{t['function']['name']}：required={missing} 不在函数签名 {sig_params} 里"
        )
    return "所有 required 参数均 ⊆ 函数签名"


def check_descriptions_nonempty():
    """不变量 3：工具级与参数级 description 都非空。
    模型看不到函数体——description 就是它对该工具的全部认知。"""
    for t in TOOLS_SCHEMA:
        name = t["function"]["name"]
        assert t["function"].get("description", "").strip(), f"{name}：工具级 description 为空"
        for pname, pdef in t["function"]["parameters"].get("properties", {}).items():
            assert pdef.get("description", "").strip(), f"{name}.{pname}：参数 description 为空"
    return "所有 description 均非空（模型看得懂菜单）"


def check_schema_json_serializable():
    """不变量 4：TOOLS_SCHEMA 必须可 JSON 序列化——它要整个塞进 HTTP payload。"""
    json.dumps(TOOLS_SCHEMA, ensure_ascii=False)
    return "TOOLS_SCHEMA 可 JSON 序列化"


def check_results_json_serializable():
    """不变量 5：每个工具的返回值都能 json.dumps——Observation 的 content 是字符串。"""
    samples = [
        TOOL_IMPL["get_order_status"]("A1001"),
        TOOL_IMPL["get_order_price"]("A1002"),
        TOOL_IMPL["calculator"]("259*0.8"),
        TOOL_IMPL["refund_apply"]("A1001", "不想要了"),
    ]
    for s in samples:
        json.dumps(s, ensure_ascii=False)
    return "全部工具返回值可 JSON 序列化"


def check_known_data_correct():
    """不变量 6：已知订单的数据正确——含浮点精度教学。

    (128*3)*0.8 == 307.2 在二进制浮点下是 False（307.19999999999999）！
    所以金额断言必须用容差比较；生产系统金额计算用 Decimal。
    这个坑 v1 就踩过，值得终身记住。"""
    price = TOOL_IMPL["get_order_price"]("A1002")
    # 错误示范（会 False）：assert price["paid_total"] == (128 * 3) * 0.8
    assert abs(price["paid_total"] - 307.2) < 1e-9, f"paid_total 语义错误：{price}"
    assert abs(TOOL_IMPL["calculator"]("259*0.8")["result"] - 207.2) < 1e-9
    return "A1002 paid_total=307.2、259*0.8=207.2（浮点容差断言）"


def check_unknown_input_no_crash():
    """不变量 7：未知/异常输入返回 error 字典，绝不抛异常。
    对照 step3 的 S5 场景：'查 ZZZZ999' 应得到 error 观察，而不是堆栈。"""
    r1 = TOOL_IMPL["get_order_status"]("ZZZZ999")
    assert "error" in r1 and "ZZZZ999" in r1["error"]
    r2 = TOOL_IMPL["get_order_price"]("ZZZZ999")
    assert "error" in r2
    r3 = TOOL_IMPL["refund_apply"]("ZZZZ999", "测试")
    assert r3.get("success") is False
    return "未知订单返回 error/success=False，不崩溃"


def check_calculator_whitelist():
    """不变量 8：calculator 的字符白名单能拦住注入尝试。"""
    r = TOOL_IMPL["calculator"]('__import__("os").system("echo hacked")')
    assert "error" in r, f"白名单失效，危险表达式被执行了：{r}"
    r2 = TOOL_IMPL["calculator"]("1/0")
    assert "error" in r2, "除零应当返回 error 而非抛异常"
    return "白名单拦截注入、除零不崩溃"


def check_scenario_data_ready():
    """不变量 9：三个 step 脚本的场景引用的数据都在（A1002/A1003/ZZZZ999 语义完整）。"""
    status = TOOL_IMPL["get_order_status"]("A1003")
    assert status["status"] == "已签收", "S2/S5 场景依赖 A1003=已签收（80% 退款规则的分支前提）"
    return "场景数据就绪（A1003=已签收，依赖链前提成立）"


def check_files_complete():
    """不变量 10：目录骨架完整——缺文件说明 v2 结构被破坏。"""
    must_exist = [
        "_tools.py", "llm_client.py",
        "step1_oneshot.py", "step2_react.py", "step3_guardrails.py",
        "README.md", "experiments.md", "requirements.txt", ".env.example",
    ]
    missing = [f for f in must_exist if not os.path.exists(os.path.join(HERE, f))]
    assert not missing, f"缺文件：{missing}"
    return "v2 目录骨架完整（9 个必备文件齐全）"


ALL_CHECKS = [
    check_schema_impl_consistent,
    check_required_subset_of_signature,
    check_descriptions_nonempty,
    check_schema_json_serializable,
    check_results_json_serializable,
    check_known_data_correct,
    check_unknown_input_no_crash,
    check_calculator_whitelist,
    check_scenario_data_ready,
    check_files_complete,
]


if __name__ == "__main__":
    print("=" * 60)
    print("Day 2 self_check · 纯本地断言（不调模型、不花额度）")
    print("=" * 60)
    passed = 0
    for i, check in enumerate(ALL_CHECKS, 1):
        try:
            msg = check()
            print(f"[PASS] {i:>2}. {msg}")
            passed += 1
        except AssertionError as e:
            print(f"[FAIL] {i:>2}. {check.__name__}：{e}")
    print("-" * 60)
    print(f"结果：{passed}/{len(ALL_CHECKS)} 通过")
    if passed != len(ALL_CHECKS):
        print("先修 _tools.py / 补齐文件，再跑 step1/2/3。")
        sys.exit(1)
    print("全绿。下一步：python step1_oneshot.py（记得先确认 .env 已填真实 Key）")
