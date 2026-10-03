"""
Day 1 · 练习二：强制结构化输出（JSON）

=== 目标 ===
让模型稳定返回 **JSON**，而不是"看心情"的自由文本。

=== 为什么这是 Agent 的地基？===
Agent 的本质是"模型决定下一步做什么"。模型要能被程序解析——
它必须回答"我要调用哪个工具、参数是什么"，而这些必须是结构化的。
不会结构化输出，就做不出 Function Calling，更做不出 Agent。

=== 两种做法 ===
1) Prompt 约束：在提示词里明确要求输出 JSON（通用，所有模型都支持）；
2) response_format={"type": "json_object"}：若模型支持，稳定性更高。

=== 生产铁律 ===
无论用哪种，都要加 **解析失败兜底**。
模型一定会有不听话的时候（这也是后面"错误处理 + 重试"的雏形）。

=== 完成后自问 ===
- 为什么"prompt 里写了要 JSON"，模型有时还是会输出别的？
- 如果模型返回的 JSON 解析失败，你的程序应该怎么办？
"""

import os
import json

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("LLM_BASE_URL", "").rstrip("/")
API_KEY = os.getenv("LLM_API_KEY", "")
MODEL = os.getenv("LLM_MODEL", "")


def _require_config():
    """配置自检：把 MissingSchema 这类‘看不懂的报错’变成人话。

    根因几乎总是 .env 缺失或 Key 未填写。这是一种工程习惯：
    在昂贵/易错的调用之前，先做廉价的前置校验。
    """
    if not BASE_URL or not API_KEY or not MODEL or API_KEY == "your_api_key_here":
        missing = [
            name for name, val in
            [("LLM_BASE_URL", BASE_URL), ("LLM_API_KEY", API_KEY), ("LLM_MODEL", MODEL)]
            if not val or val == "your_api_key_here"
        ]
        raise SystemExit(
            f"\n[配置错误] 缺失或未修改：{', '.join(missing)}\n"
            f"当前 BASE_URL = {BASE_URL!r}\n\n"
            f"排查：1) 本目录是否有 .env（非 .env.example）？没有就 cp .env.example .env；"
            f"2) 把 your_api_key_here 换成真实 Key；3) .env 需与本脚本同目录。\n"
        )


def chat(messages: list[dict], temperature: float = 0.0, json_mode: bool = False) -> str:
    """对话调用。json_mode=True 时尝试启用模型的 JSON 输出模式。

    注意 temperature 默认设为 0：结构化任务要稳定，不要创造性。
    """
    _require_config()
    url = f"{BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
    }
    if json_mode:
        # 并非所有模型/接口都支持，用 try 兜底或按需去掉
        payload["response_format"] = {"type": "json_object"}

    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def parse_json_safely(text: str) -> dict | None:
    """安全解析 JSON：处理模型偶尔包裹 ```json 代码块的情况。

    生产环境请务必保留这层兜底，而不是直接 json.loads()。
    """
    text = text.strip()
    if text.startswith("```"):                      # 去掉 ```json ... ```
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


# —— 场景：客服 Agent 的第一步是"理解用户意图" ——
# 我们要模型输出结构化的意图判断，程序才能据此决定后续动作。
SYSTEM_PROMPT = """你是一名客服意图识别引擎。请分析用户的话，只输出 JSON，不要任何多余文字。
JSON 格式如下：
{
  "intent": "咨询价格 | 查询订单 | 申请退款 | 投诉建议 | 其他",
  "emotion": "平静 | 不满 | 愤怒",
  "need_human": true 或 false,
  "confidence": 0 到 1 之间的小数
}
其中 need_human 表示是否需要转接人工客服（例如用户强烈不满或问题超出范围）。"""


if __name__ == "__main__":
    user_input = "你们这个东西怎么这么垃圾啊？？"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_input},
    ]

    print(f">>> 用户输入：{user_input}\n")

    raw = chat(messages, temperature=0.0, json_mode=False)
    print(">>> 模型原始输出：")
    print(raw)

    result = parse_json_safely(raw)
    print("\n>>> 解析结果：")
    if result is None:
        # 兜底：解析失败时的降级策略（这里简化为转人工）
        print("解析失败！降级策略：转人工处理。")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result.get("need_human"):
            print("\n[决策] 该用户需要转人工客服。")

    # --- 动手练习区 ---
    # 1. 多试几句不同的话（如"多少钱？"、"我要退款"、"挺好的谢谢"），
    #    观察 intent / emotion / need_human 是否合理；
    # 2. 把 json_mode 关掉，看模型是否仍能输出合法 JSON，对比稳定性；
    # 3. 故意在 SYSTEM_PROMPT 里把格式删掉，制造"解析失败"，走一遍兜底逻辑。
