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
    resp.raise_for_status()           # 4xx/5xx 直接抛错，便于定位问题
    data = resp.json()
    return data["choices"][0]["message"]["content"]


if __name__ == "__main__":
    # 场景预热：我们最终要做智能客服，这里先让模型扮演客服助手
    messages = [
        {"role": "system", "content": "你是一名专业的中文客服助手，回答简洁、准确、礼貌。"},
        {"role": "user", "content": "你好，请用一句话介绍你自己。"},
    ]

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
