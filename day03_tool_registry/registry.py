"""
Day 3 核心 · 工具注册表（Tool Registry）

=== 为什么需要它（v0.4 的真实教训）===
Day 2 里，加一个工具要改**两处**：写函数 + 手写一段 Schema。
两处不同步就是 bug：
  · 改了参数名忘改 schema  → 模型传的参对不上，工具永远报参数错
  · 加了参数忘改 schema    → 模型永远不知道该传这个参数
  · 描述写得和实现不一致   → 模型"以为"工具能干的事和它真能干的不是一回事
主项目 cs-agent 用的是**装饰器注册表**：一次登记，实现 + Schema + 描述同源。
本文件就是那套机制的最小教学版——把 cs_agent/tools.py 剥掉业务后的骨架。

=== 三个设计决策（每条都有理由，面试可讲）===
① 装饰器登记：`@tool` 让"写一个函数"这件事自动完成 schema 生成——
   调用方式不变（仍是普通函数），但注册表里多了一条记录。**不改用法，只加能力**。
② Schema 的唯一来源是函数本身：参数名/类型/默认值取自签名，
   参数说明取自 docstring 的 Args: 段。**没有第二个地方需要维护。**
③ 参数没写描述 = 直接报错（fail fast）：
   模型只能看到 description，没描述的参数等于没说明书。
   这类错误必须在**导入时**炸，而不是等线上模型瞎猜时才发现。

=== 异常分级（Day 2 护栏③的正式化）===
- ToolBusinessError：**业务异常**，可预期（订单不存在、参数越界）。
  回传给模型 → 模型自己纠正（换个订单号 / 换种说法）。
- 其他 Exception：**系统异常**，不可预期（代码 bug、依赖挂了）。
  也回传，但标记 error_type=unexpected 并提示"不要重复调用"，
  生产里同时要打日志告警——**能自愈的让它自愈，不能自愈的让人介入**。
"""

from __future__ import annotations

import inspect
import json
from typing import Any, Callable, get_type_hints

# 函数名 → 工具规格。全局唯一事实来源。
TOOL_REGISTRY: dict[str, "ToolSpec"] = {}

# Python 类型 → JSON Schema 类型（只支持四种，够用且不引入复杂性）
_TYPE_MAP: dict[Any, str] = {str: "string", int: "integer", float: "number", bool: "boolean"}

# docstring 里参数说明段的常见写法
_ARGS_HEADERS = ("Args:", "Arguments:", "Parameters:", "参数:")


class ToolBusinessError(Exception):
    """业务异常：可预期，应该回传给模型让它自己纠正。"""


class ToolSpec:
    """一个已登记工具的完整规格：函数 + 描述 + 签名 + 参数说明。"""

    def __init__(self, fn: Callable, description: str, name: str | None = None) -> None:
        self.fn = fn
        self.name = name or fn.__name__
        self.description = description.strip()
        self.signature = inspect.signature(fn)
        self.hints = get_type_hints(fn)
        self.param_docs = _parse_param_docs(fn)

    @property
    def required(self) -> list[str]:
        """没有默认值的参数 → required。"""
        return [
            p.name
            for p in self.signature.parameters.values()
            if p.default is inspect.Parameter.empty
            and p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)
        ]

    def to_schema(self) -> dict:
        """生成模型可见的 JSON Schema——这是模型的全部世界观。"""
        props: dict[str, dict] = {}
        for pname, p in self.signature.parameters.items():
            if p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
                continue
            ptype = self.hints.get(pname, str)
            json_type = _TYPE_MAP.get(ptype)
            if json_type is None:
                raise TypeError(
                    f"工具 {self.name} 的参数 {pname} 类型 {ptype!r} 无法映射到 JSON Schema；"
                    f"day03 只支持 str / int / float / bool。"
                )
            desc = self.param_docs.get(pname, "")
            if not desc:
                # fail fast：宁可导入时就炸，也不要让模型去猜
                raise ValueError(
                    f"工具 {self.name} 的参数 {pname} 缺少描述。\n"
                    f"  请在 {self.fn.__name__} 的 docstring 里补一段：\n\n"
                    f"      Args:\n          {pname}: 这个参数是什么、什么格式\n"
                )
            props[pname] = {"type": json_type, "description": desc}
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": props,
                    "required": self.required,
                },
            },
        }


def _parse_param_docs(fn: Callable) -> dict[str, str]:
    """从 docstring 的 Args: 段解析 `参数名: 说明`（缩进行）。"""
    docs: dict[str, str] = {}
    inside = False
    for raw in (fn.__doc__ or "").splitlines():
        if raw.strip() in _ARGS_HEADERS:
            inside = True
            continue
        if not inside:
            continue
        if not raw.strip():
            continue
        if not raw.startswith((" ", "\t")):   # 回到顶格 → 这一段结束
            break
        if ":" in raw:
            key, _, desc = raw.strip().partition(":")
            key = key.strip().split("(")[0].strip()   # 容忍 "order_id (str): ..." 写法
            docs[key] = desc.strip()
    return docs


def tool(_fn: Callable | None = None, *, name: str | None = None,
         description: str | None = None):
    """装饰器：把普通函数登记为模型可调用的工具。

    用法一（推荐，描述取自 docstring 首段）：
        @tool
        def get_order_status(order_id: str) -> dict:
            \"\"\"查询订单物流状态。\"\"\"
            Args:
                order_id: 订单编号，例如 A1001

    用法二（需要覆盖名字或描述时显式指定）：
        @tool(name="calc", description="四则运算")
    """
    def wrap(fn: Callable) -> Callable:
        doc = (fn.__doc__ or "").strip()
        summary = description or doc.split("\n\n")[0].replace("\n", " ").strip()
        if not summary:
            raise ValueError(f"工具 {fn.__name__} 没有描述——docstring 首行就是模型的说明书。")
        spec = ToolSpec(fn, summary, name)
        # fail fast：登记时就把 schema 生成一遍，参数缺描述/类型不支持当场报错。
        # （错误拦在 import 那一刻，而不是等线上模型瞎猜时才发现）
        spec.to_schema()
        TOOL_REGISTRY[spec.name] = spec
        return fn   # 原样返回：装饰后仍是普通函数，可直接调用、可直接单测

    return wrap(_fn) if _fn is not None else wrap


def get_schemas() -> list[dict]:
    """模型要的那份"行动菜单"——由注册表实时生成，不可能与实现脱钩。"""
    return [spec.to_schema() for spec in TOOL_REGISTRY.values()]


def _coerce(value: Any, expected: Any, tool_name: str, pname: str) -> Any:
    """参数类型容错：模型常把数字写成字符串（"3" 而不是 3）。

    能安全转换就转，转不了就抛业务异常（回传给模型纠正），
    **绝不让 TypeError 变成系统异常**——这是工具层的职责。
    """
    if expected is bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.lower() in ("true", "false"):
            return value.lower() == "true"
    if expected in (int, float) and isinstance(value, str):
        try:
            return expected(value)
        except ValueError:
            raise ToolBusinessError(
                f"参数 {pname} 需要{'整数' if expected is int else '数字'}，收到的是 {value!r}"
            )
    if expected is int and isinstance(value, float) and value.is_integer():
        return int(value)
    if not isinstance(value, expected) and not (expected is float and isinstance(value, int)):
        raise ToolBusinessError(
            f"参数 {pname} 类型应为 {expected.__name__}，收到 {type(value).__name__}（{value!r}）"
        )
    return value


def execute_tool(name: str, args: dict) -> str:
    """执行工具，**永远返回字符串**（Observation）。

    这是与 Day 2 一脉相承的铁律：任何异常都不许穿透出去杀死循环。
    异常在这里被翻译成"模型能读懂的反馈"。
    """
    spec = TOOL_REGISTRY.get(name)
    if spec is None:
        return json.dumps(
            {"error": f"未注册的工具 {name}", "hint": f"可用工具：{', '.join(TOOL_REGISTRY)}"},
            ensure_ascii=False,
        )

    # ① 参数校验：缺参数 / 多参数（模型真会这么干）
    missing = [p for p in spec.required if p not in args]
    if missing:
        return json.dumps(
            {"error": f"缺少必填参数：{', '.join(missing)}", "hint": "请补齐后重试"},
            ensure_ascii=False,
        )
    valid_names = {p.name for p in spec.signature.parameters.values()}
    extra = [k for k in args if k not in valid_names]
    if extra:
        return json.dumps(
            {"error": f"收到了未定义的参数：{', '.join(extra)}",
             "hint": f"{name} 只接受：{', '.join(sorted(valid_names))}"},
            ensure_ascii=False,
        )

    # ② 类型容错
    try:
        clean: dict[str, Any] = {}
        for pname, p in spec.signature.parameters.items():
            if pname in args:
                clean[pname] = _coerce(args[pname], spec.hints.get(pname, str), name, pname)
    except ToolBusinessError as e:
        return json.dumps({"error": str(e), "error_type": "business"}, ensure_ascii=False)

    # ③ 执行 + 异常分级兜底
    try:
        result = spec.fn(**clean)
    except ToolBusinessError as e:
        return json.dumps(
            {"error": str(e), "error_type": "business",
             "hint": "这是可预期的业务错误，请据此调整参数或如实告知用户，不要重复相同调用"},
            ensure_ascii=False,
        )
    except Exception as e:   # noqa: BLE001 —— 这里就是要兜住一切
        # 系统异常：也回传，但明确告诉模型"别重试"，同时生产里应打日志告警
        return json.dumps(
            {"error": f"{type(e).__name__}: {e}", "error_type": "unexpected",
             "hint": "系统内部错误，请如实告知用户并建议转人工，不要重复调用同一工具"},
            ensure_ascii=False,
        )

    return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
