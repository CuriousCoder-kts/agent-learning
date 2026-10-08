"""
Day 3 · 共享 LLM 客户端

与 day02/llm_client.py 内容基本一致（显式 .env 路径 + 配置自检 + 错误人话翻译），
这里刻意**复制一份而不是跨目录 import**：
教学仓库里每个 day 目录保持自足（能独立拷贝走、独立运行），
跨目录 import 会让"从任何位置运行"变得脆弱。

工程上什么时候该抽公共层？出现**第三个**消费者时。
主项目里它已经升级成了 `cs_agent/llm.py`——那就是真实项目的公共层做法。
"""

import os

import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

BASE_URL = os.getenv("LLM_BASE_URL", "").rstrip("/")
API_KEY = os.getenv("LLM_API_KEY", "")
MODEL = os.getenv("LLM_MODEL", "")


def _require_config():
    """配置自检：昂贵调用之前先做廉价校验。"""
    bad = [
        name for name, val in
        [("LLM_BASE_URL", BASE_URL), ("LLM_API_KEY", API_KEY), ("LLM_MODEL", MODEL)]
        if not val or val == "your_api_key_here"
    ]
    if bad:
        raise SystemExit(
            f"\n[配置错误] 缺失或未修改：{', '.join(bad)}\n"
            f"当前 BASE_URL = {BASE_URL!r}\n\n"
            f"修复：把 day03_tool_registry/.env 里的 your_api_key_here 换成真实 Key\n"
            f"（可直接从 day02_function_calling/.env 复制过来）。\n"
            f"详见仓库根目录 TROUBLESHOOTING.md。\n"
        )


def chat_once(messages: list[dict], tools: list[dict] | None = None) -> dict:
    """单次模型调用，返回**完整 message**（tool_calls 在里面，不能只取 content）。"""
    _require_config()
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.0,   # 决策类任务要稳定
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    resp = requests.post(
        f"{BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    if resp.status_code == 401:
        raise SystemExit("\n[鉴权失败 401] Key 无效或与 BASE_URL 不匹配。\n")
    if resp.status_code == 404:
        raise SystemExit(f"\n[404] 模型名 {MODEL!r} 可能不被该平台支持，核对 LLM_MODEL。\n")
    if resp.status_code == 429:
        raise SystemExit("\n[限流 429] 请求过频或额度用尽，稍后重试。\n")
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]
