# agent-learning · Agent 开发学习工程

> 目标：30 天内从"会用 AI 写代码"进阶到"能独立设计并交付 Agent 应用"。
> 终极项目：**企业知识库 + 智能客服 Agent（私有化 / 国产模型）**
> 原则：**Core First —— 核心模块先手写，再用框架对照。**

---

## 为什么这样组织
每一节（dayXX）都是一次"手写实践"，而不是看教程。学完即写、写完即测。
最终的 Agent 能力会像搭积木一样，一层层叠加到最后的客服项目里。

## 目录规划（随进度生长）
```
agent-learning/
├── README.md                 # 本文件
├── day01_raw_llm/            # ✅ 原生 LLM 调用 + 结构化输出（第 1 天）
├── day02_function_call/      # ⏳ 手写 Function Calling（第 2–3 天）
├── day03_react_loop/         # ⏳ 手写 ReAct 循环（第 4–5 天）
├── day04_memory/             # ⏳ 记忆机制（第 6 天）
├── week2_framework_rag/      # ⏳ 框架 + RAG（第 2 周）
└── cs-agent/                 # 🎯 终极项目：智能客服 Agent（第 3 周）
```
> ⏳ = 待创建，🎯 = 主项目

## 学习闭环（每天必做）
1. 读当天 `README.md` 的任务与目标；
2. 手写并跑通代码（不许 AI 代劳，卡住先自己想 15 分钟）；
3. 回答当天"自测题"，能脱稿讲清才算过关；
4. 用自己的话写 3–5 行笔记。

## 环境准备（一次即可）
```bash
cd day01_raw_llm
pip install -r requirements.txt
cp .env.example .env      # 然后把你的 API Key 填进 .env
python 01_hello_llm.py
```

## 模型选择说明
本项目统一走 **OpenAI 兼容接口**，因此可无缝切换国产模型：
GLM（智谱）、通义千问（DashScope 兼容模式）、DeepSeek、Moonshot 等。
这也是"贴合大陆业务"的第一步——后续主项目将基于国产模型 + 私有化部署。

---
_学习工程 · 由 JARVIS 协同构建_
