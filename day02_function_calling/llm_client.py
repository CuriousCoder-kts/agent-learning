"""
Day 2 · 共享 LLM 客户端（单一事实来源）

所有 step 脚本都 `from llm_client import chat_once`——
HTTP 细节、配置自检、错误翻译只写这一遍。
（v1 的教训：这三样在三个文件里各抄一份，改一处忘两处。）

三个设计要点（都是生产习惯，值得内化）：
1. 显式指定 .env 路径（本文件同目录），不依赖"当前工作目录"——
   从任何位置运行脚本都能读到配置；
2. 配置自检在调用前拦截——把看不懂的 MissingSchema 堆栈翻译成人话；
3. 401 / 404 / 429 高频错误就地翻译，其余原样抛出。
"""

import os

import requests
from dotenv import load_dotenv

# 显式加载本目录的 .env（不依赖 CWD；从任何位置运行均可）
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

BASE_URL = os.getenv("LLM_BASE_URL", "").rstrip("/")
API_KEY = os.getenv("LLM_API_KEY", "")
MODEL = os.getenv("LLM_MODEL", "")


def _require_config():
    """配置自检：在昂贵调用之前，先做廉价的前置校验。"""
    if not BASE_URL or not API_KEY or not MODEL or API_KEY == "your_api_key_here":
        missing = [
            name for name, val in
            [("LLM_BASE_URL", BASE_URL), ("LLM_API_KEY", API_KEY), ("LLM_MODEL", MODEL)]
            if not val or val == "your_api_key_here"
        ]
        raise SystemExit(
            f"\n[配置错误] 缺失或未修改：{', '.join(missing)}\n"
            f"当前 BASE_URL = {BASE_URL!r}\n\n"
            f"排查：1) day02_function_calling/.env 是否存在且已填真实 Key（不是 your_api_key_here）？\n"
            f"      2) 若选 DeepSeek/通义，需同时启用对应的 BASE_URL 与 MODEL 两行。\n"
            f"详见仓库根目录 TROUBLESHOOTING.md。\n"
        )


def chat_once(messages: list[dict], tools: list[dict] | None = None) -> dict:
    """单次模型调用，返回**完整 message 对象**（不是 content 字符串！）。

    为什么返回整个 message？因为 Function Calling 的关键信息在
    message.tool_calls 里，只取 content 会把它丢掉。

    tools=None 时不给模型工具菜单——step1 的收尾调用正是靠它"剥夺停止权"。
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
        "temperature": 0.0,   # 工具决策要稳定，不要创造性
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"   # 由模型自行决定是否调用工具

    # 超时必须设：生产环境网络一定会出问题，别让请求永远挂着
    resp = requests.post(url, headers=headers, json=payload, timeout=60)

    # 高频错误的人话翻译（生产里对应的是日志 + 分级告警）
    if resp.status_code == 401:
        raise SystemExit(
            "\n[鉴权失败 401] 请求已发出，但 Key 无效。检查：\n"
            "  · .env 里是否已把 your_api_key_here 换成真实 Key？\n"
            "  · Key 是否复制完整（前后无空格换行）？\n"
            "  · Key 与 BASE_URL 是否属于同一平台？\n"
        )
    if resp.status_code == 404:
        raise SystemExit(
            f"\n[404] 模型名 {MODEL!r} 可能不被该平台支持，核对 .env 的 LLM_MODEL。\n"
        )
    if resp.status_code == 429:
        raise SystemExit("\n[限流 429] 请求过频或额度用尽，稍后重试或查账户余额。\n")
    resp.raise_for_status()   # 其余错误原样抛出，便于定位

    return resp.json()["choices"][0]["message"]
