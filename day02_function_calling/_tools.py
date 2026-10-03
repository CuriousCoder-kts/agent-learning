"""
Day 2 · 共享工具集（被 step1 / step2 / step3 / self_check 共用）

=== 设计原则：单一事实来源 ===
工具实现与 Schema 只在这里写一遍，所有脚本 import。
（v1 的教训：01 文件内联一份、_tools 又一份，两处不同步是真实 bug 源。）

=== 工具即 Agent 的"行动菜单" ===
模型看不到函数实现，只能看到 Schema 里的 name / description / parameters。
description 写什么，模型就"以为"这个工具能干什么——
它既是说明书，也是策略载体（看 refund_apply 的描述：里面写着"没给订单号先追问"）。

=== 数据语义（业务设计题，面试可讲） ===
A1002：标价 128 × 3 = 384，但 paid_total = 307.2（下单时打了八折，实付 307.2）。
退款必须按 paid_total（实付）退，而不是单价 × 数量——
"工具返回哪些字段、字段什么语义"是工具设计者的责任，模型只负责正确地用。
把这道语义题想清楚，比多写十个工具有价值。
"""


def get_order_status(order_id: str) -> dict:
    """查询订单物流状态（模拟数据库）"""
    fake_db = {
        "A1001": {"status": "已发货", "carrier": "顺丰", "eta": "明天下午"},
        "A1002": {"status": "待发货", "carrier": None, "eta": "预计 48 小时内"},
        "A1003": {"status": "已签收", "carrier": "京东物流", "eta": "已完成"},
    }
    return fake_db.get(order_id, {"error": f"未找到订单 {order_id}"})


def get_order_price(order_id: str) -> dict:
    """查询订单金额明细（模拟数据库）。

    注意 paid_total 是**实付**（已扣折扣）——退款、开票一律以它为准。
    """
    fake_db = {
        "A1001": {"unit_price": 199, "quantity": 2, "paid_total": 398},
        "A1002": {"unit_price": 128, "quantity": 3, "paid_total": 307.2},
        "A1003": {"unit_price": 259, "quantity": 1, "paid_total": 259},
    }
    return fake_db.get(order_id, {"error": f"未找到订单 {order_id} 的价格信息"})


def calculator(expression: str) -> dict:
    """四则运算计算器（演示参数白名单校验与安全边界）"""
    allowed = set("0123456789+-*/(). ")
    if not set(expression) <= allowed:
        return {"error": "表达式包含非法字符，已拒绝执行"}
    try:
        # 教学用 eval + 字符白名单；生产请用 ast.literal_eval 或 sympy
        return {"result": eval(expression, {"__builtins__": {}}, {})}
    except Exception as e:
        return {"error": f"计算失败：{e}"}


def refund_apply(order_id: str, reason: str) -> dict:
    """提交退款申请（模拟）。这是一个"写操作"，与上面三个"读操作"性质不同。"""
    fake_db = {
        "A1001": "已发货",
        "A1002": "待发货",
        "A1003": "已签收",
    }
    if order_id not in fake_db:
        return {"success": False, "error": f"未找到订单 {order_id}，无法申请退款"}
    status = fake_db[order_id]
    return {
        "success": True,
        "refund_id": f"RF{order_id}",
        "message": (
            f"订单 {order_id}（{status}）退款申请已提交，原因：{reason}。"
            "预计 1-3 个工作日按实付金额原路退回。"
        ),
    }


# 函数名 → 真实函数 的注册表
TOOL_IMPL = {
    "get_order_status": get_order_status,
    "get_order_price": get_order_price,
    "calculator": calculator,
    "refund_apply": refund_apply,
}

# 工具的 JSON Schema——模型唯一能看到的"菜单"
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "get_order_status",
            "description": "根据订单号查询物流状态、承运商和预计到达时间。用户问订单进度、发货情况、是否签收时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "订单编号，例如 A1001"}
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_order_price",
            "description": "查询订单的实付金额明细：单价、数量、实付总价（paid_total 为实付，已扣折扣）。用户问多少钱、实付多少、退款能退多少时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "订单编号，例如 A1001"}
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "四则运算。需要计算金额、折扣、数量等数学表达式时使用。金额计算优先用它，不要心算。",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "合法的四则运算表达式，例如 259*0.8"}
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            # 描述里的策略（"没给订单号先追问"）源自 Sir 10.03 的作业，保留——
            # 工具描述里可以写行为策略，这是 Agent 设计的重要手段
            "name": "refund_apply",
            "description": "为用户提交退款申请（按实付金额退）。当用户明确表达要退款/退货/退钱时调用。如果用户没提供订单号，请先追问，不要瞎猜；如果没说原因，可用默认原因「其他」。",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "要退款的订单编号，例如 A1001"},
                    "reason": {"type": "string", "description": "退款原因，例如：拍错了、不想要了、质量问题"},
                },
                "required": ["order_id", "reason"],
            },
        },
    },
]
