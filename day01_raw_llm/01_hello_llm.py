"""
Day 1 · 练习一：手写原生 LLM 调用（不使用任何 SDK）

=== 目标 ===
1. 理解 Chat Completions 接口的 HTTP 请求结构；
2. 理解 messages 中的角色：system / user / assistant 各自的作用；
3. 亲手控制请求与响应——这是后面手写 Agent 的地基。

=== 为什么不用 openai SDK？===
SDK 帮你屏蔽了细节。若只调 SDK，你会"会用但讲不清原理"。
面试官问一句"模型请求长什么样"就会露底。手写一遍，细节才真正属于你。

=== 完成后自问 ===
- 请求体里 model / messages / temperature 分别控制什么？
- system 和 user 角色有什么本质区别？
- 如果去掉 system，结果会有什么变化？动手试试。
"""

import os
import json

import requests
from dotenv import load_dotenv

# 从 .env 读取配置（需先复制 .env.example 为 .env 并填入 Key）
load_dotenv()

BASE_URL = os.getenv("LLM_BASE_URL", "").rstrip("/")
API_KEY = os.getenv("LLM_API_KEY", "")
MODEL = os.getenv("LLM_MODEL", "")


def chat(messages: list[dict], temperature: float = 0.7) -> str:
    """最小可用的对话调用：输入消息列表，返回模型回复文本。

    这十几行代码，就是所有 Agent 与 LLM 交互的最底层。
    后面无论用多花哨的框架，本质上都是在这里做文章。
    """
    # 配置自检：把"看不懂的报错"变成"看得懂的人话"
    # （MissingSchema 这类错误的根因几乎都是 .env 没配好）
    if not BASE_URL or not API_KEY or not MODEL:
        missing = [
            name for name, val in
            [("LLM_BASE_URL", BASE_URL), ("LLM_API_KEY", API_KEY), ("LLM_MODEL", MODEL)]
            if not val or val == "your_api_key_here"
        ]
        raise SystemExit(
            f"\n[配置错误] 以下配置缺失或未修改：{', '.join(missing)}\n"
            f"当前读取到的 BASE_URL = {BASE_URL!r}\n\n"
            f"请检查：\n"
            f"  1) 本目录下是否存在 .env 文件（不是 .env.example）？\n"
            f"     —— 若没有：cp .env.example .env\n"
            f"  2) 是否已把 .env 里的 your_api_key_here 换成真实 Key？\n"
            f"  3) .env 必须与本脚本在同一目录。\n"
        )

    url = f"{BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,   # 0 → 稳定保守；1+ → 发散有创意
    }

    # 超时是必须的：生产环境网络一定会出问题，别让请求永远挂着
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    # 常见错误的人话翻译（生产里应记日志 + 分级告警，这里先让新手能自查）
    if resp.status_code == 401:
        raise SystemExit(
            "\n[鉴权失败 401] 请求已发出，但 API Key 无效。请检查：\n"
            "  · .env 里的 LLM_API_KEY 是否已换成真实 Key（不是 your_api_key_here）？\n"
            "  · Key 是否复制完整（前后无空格、无换行）？\n"
            "  · Key 是否与 LLM_BASE_URL 属于同一平台？\n"
        )
    if resp.status_code == 404:
        raise SystemExit(
            f"\n[模型不存在 404] LLM_MODEL={MODEL!r} 可能不被该平台支持。\n"
            "  请核对 .env 中模型名与该平台文档一致（如 glm-4-flash / deepseek-chat / qwen-plus）。\n"
        )
    if resp.status_code == 429:
        raise SystemExit("\n[限流 429] 请求过于频繁或额度用尽，稍后重试或检查账户余额。\n")
    resp.raise_for_status()           # 其余 4xx/5xx 直接抛错，便于定位问题
    data = resp.json()
    return data["choices"][0]["message"]["content"]

if __name__ == "__main__":
    # 场景预热：我们最终要做智能客服，这里先让模型扮演客服助手
    messages = [
        {"role": "system", "content": "你是一名专业的中文客服助手，回答简洁、准确、礼貌。"},
        {"role": "user", "content": "你能帮我写代码吗？"},
    ]

    print(">>> 即将发送的请求体 messages：")
    print(json.dumps(messages, ensure_ascii=False, indent=2))
    print("\n>>> 模型回复：")
    print(chat(messages))

    messages.append({"role": "assistant", "content": "当然可以！请告诉我：你希望实现什么功能？（例如：爬取网页、处理Excel、写个计算器、Web接口等）  - 使用什么编程语言？（如 Python、JavaScript、Java 等，默认可按 Python）  - 是否有特定要求？（如使用某库、运行环境、输入输出格式、是否需要注释或错误处理等）我会为你提供简洁、可运行的代码，并附上简要说明。😊"})
    messages.append({"role": "user", "content": "帮我实现一个计算两数之差的绝对值的Python函数"})
    print(">>> 即将发送的请求体 messages：")
    print(json.dumps(messages, ensure_ascii=False, indent=2))
    print("\n>>> 模型回复：")
    print(chat(messages))

    # --- 动手练习区（务必亲手改一改、跑一跑）---
    # 1. 把 system 删掉，观察回复风格的变化；
    # 2. 加一条历史消息，构造多轮对话：
    #      messages.append({"role": "assistant", "content": "..."})
    #      messages.append({"role": "user", "content": "第二个问题"})
    #    再次调用 chat(messages)，体会"上下文"是如何被带上的。
