from __future__ import annotations

import inspect
import json
from typing import Any, Callable, get_type_hints

TOOL_REGISTRY: dict[str, "ToolSpec"] = {}

_TYPE_MAP: dict[Any, str] = {str: "string", int: "integer", float: "number", bool: "boolean"}

_ARGS_HEADERS = ("Args:", "Arguments:", "Parameters:", "参数:")

class ToolBusinessError(Exception):
    """业务异常：可预期，应该回传给大模型让它自己纠正。"""

class ToolSpec:
    """一个已登记工具的完整规格：函数 + 描述 + 签名 + 参数说明。 """

    def __init__(self, fn: Callable, description: str, name: str | None = None) -> None:
        self.fn = fn
        self.name = name or fn.__name__
        self.description = description.strip()
        self.signature = inspect.signature(fn)
        self.hints = get_type_hints(fn)
        self.param_docs = _parse_param_docs(fn)
    
    @property
    def required(self) -> list[str]:
        """没有默认值的参数 -> required。"""
        return [
            p.name
            for p in self.signature.parameters.values()
            if p.default is inspect.Parameter.empty
            and p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)
        ]

    def to_schema(self) -> dict:
        """生成模型可见的JSON Schema"""
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
                }
            }
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

def execute_tool(name:str, args: dict) -> str:
    """执行工具：永远返回字符串"""
    spec = TOOL_REGISTRY.get(name)
    if spec is None:
        return json.dumps(
            {"error": f"未注册的工具 {name}", "hint": f"可用工具：{', '.join(TOOL_REGISTRY)}"},
            ensure_ascii=False,
        )
    missing = [p for p in spec.required if p not in args]
    if missing:
        return json.dumps(
            {"error": f"缺少必填参数：{','.join(missing)}","hint": "请补齐后重试"},
            ensure_ascii=False,
        )
    valid_names = {p.name for p in spec.signature.parameters.values()}
    extra = [k for k in args if k not in valid_names]
    if extra:
        return json.dumps(
            {"error": f"收到了未定义的参数：{','.join(extra)}",
            "hint": f"{name} 只接受：{','.join(valid_names)}"},
            ensure_ascii=False,
        )
    try:
        clean: dict[str,Any] = {}
        for pname,p in spec.signature.parameters.items():
            if pname in args:
                clean[pname] = _coerce(args[pname], spec.hints.get(pname,str),name,pname)
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