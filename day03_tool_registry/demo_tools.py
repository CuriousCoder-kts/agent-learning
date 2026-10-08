"""
Day 3 · 用注册表登记工具（对照 Day 2 的 _tools.py）

对照着看，你会发现省掉了什么：
  Day 2：写函数（25 行）+ 手写 Schema（60 行）= 两份需要同步的清单
  Day 3：写函数 + 一个 @tool 装饰器  = 一份真相

跑法：这个文件本身不执行任何东西，它就是"工具库"。
      02_fc_with_registry.py 会 import 它，从而完成登记（import 即注册）。
"""

from registry import ToolBusinessError, tool

# 假数据库（教学用；主项目里换成了真实业务系统）
_ORDERS = {
    "A1001": {"status": "已发货", "carrier": "顺丰", "eta": "明天下午",
              "unit_price": 199, "quantity": 2, "paid_total": 398},
    "A1002": {"status": "待发货", "carrier": None, "eta": "预计 48 小时内",
              "unit_price": 128, "quantity": 3, "paid_total": 307.2},
    "A1003": {"status": "已签收", "carrier": "京东物流", "eta": "已完成",
              "unit_price": 259, "quantity": 1, "paid_total": 259},
}


@tool
def get_order_status(order_id: str) -> dict:
    """查询订单的物流状态、承运商和预计到达时间。用户问订单进度、发货情况、是否签收时使用。

    Args:
        order_id: 订单编号，形如 A1001（字母 A + 四位数字）
    """
    order = _ORDERS.get(order_id)
    if order is None:
        # 业务异常师范：订单不存在是"可预期"的错误，抛 ToolBusinessError 回传给模型
        raise ToolBusinessError(f"未找到订单 {order_id}，请确认订单号是否正确")
    return {"order_id": order_id, "status": order["status"],
            "carrier": order["carrier"], "eta": order["eta"]}


@tool
def get_order_price(order_id: str) -> dict:
    """查询订单金额明细：单价、数量、实付总价。用户问多少钱、退款能退多少、开票金额时使用。

    注意 paid_total 是**实付**（已扣折扣），退款与开票一律以它为准。

    Args:
        order_id: 订单编号，形如 A1002
    """
    order = _ORDERS.get(order_id)
    if order is None:
        raise ToolBusinessError(f"未找到订单 {order_id} 的价格信息")
    return {"order_id": order_id, "unit_price": order["unit_price"],
            "quantity": order["quantity"], "paid_total": order["paid_total"]}


@tool
def calculator(expression: str) -> dict:
    """四则运算计算器。需要算金额、折扣、数量等数学表达式时使用，金额计算优先用它，不要心算。

    Args:
        expression: 合法的四则运算表达式，例如 259*0.8 或 (128*3)*0.8
    """
    allowed = set("0123456789+-*/(). ")
    if not set(expression) <= allowed:
        raise ToolBusinessError("表达式包含非法字符，只允许数字和 + - * / ( ) . 和空格")
    try:
        return {"expression": expression, "result": eval(expression, {"__builtins__": {}}, {})}
    except ZeroDivisionError:
        raise ToolBusinessError("除数不能为零")
    except Exception as e:   # 语法错误等
        raise ToolBusinessError(f"表达式无法计算：{e}")


@tool
def refund_apply(order_id: str, reason: str) -> dict:
    """为用户提交退款申请（按实付金额退回）。用户明确表达要退款/退货/退钱时调用。

    如果用户没提供订单号，请先追问，不要瞎猜订单号；没说原因时可用「其他」。

    Args:
        order_id: 要退款的订单编号，例如 A1001
        reason: 退款原因，例如：拍错了、不想要了、质量问题
    """
    if order_id not in _ORDERS:
        raise ToolBusinessError(f"订单 {order_id} 不存在，无法申请退款")
    return {"success": True, "refund_id": f"RF{order_id}",
            "message": f"订单 {order_id} 的退款申请已提交（按实付金额退回），原因：{reason}，预计 1-3 个工作日到账。"}


@tool(name="ping_upstream", description="内部健康检查：探测订单系统上游是否可用（演示系统异常被兜住）")
def _ping(order_id: str) -> dict:
    """演示用工具：故意抛出一个**系统异常**（不是业务异常），看护栏如何兜住它。

    Args:
        order_id: 任意订单号，仅用于演示
    """
    raise RuntimeError("上游订单服务连接超时（模拟的系统故障）")
