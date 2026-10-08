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
├── NOTES.md                  # 📝 学习笔记（每天填，面试前一夜只看它）
├── TROUBLESHOOTING.md        # 🔧 报错速查表（先查这里，再找我）
├── day01_raw_llm/            # ✅ 原生 LLM 调用 + 结构化输出（第 1 天）
├── day02_function_calling/   # ✅ 概念阶梯：one-shot → ReAct → 护栏（第 2 天，v2）
├── day03_tool_registry/      # ✅ 工具注册表 + 异常分级兜底（第 3 天）
├── day04_memory/             # ⏳ 记忆机制（第 4 天）
├── week2_framework_rag/      # ⏳ 框架 + RAG（第 2 周）
└── cs-agent/                 # 🎯 终极项目：智能客服 Agent（第 3 周）
```
> ⏳ = 待创建，✅ = 已完成，🎯 = 主项目

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

## Day 2 快速开始（Function Calling 与 ReAct）
```bash
cd day02_function_calling
python self_check.py          # 0. 纯本地自检（10 项断言，不花额度）
python step1_oneshot.py       # ① one-shot：停止权在代码（收尾 tools=None）
python step2_react.py         # ② ReAct 循环：停止权交给模型（★只差两处）
python step3_guardrails.py    # ③ 生产护栏：max_steps / 去重 / 异常回传
```
> 核心命题：**停止权在谁手里**。三个 step 跑相同场景（S1/S2/S3），对比答案与统计，差异自现。
> 三个 step 共享 `_tools.py`（工具单一事实来源）与 `llm_client.py`（配置自检 + 错误人话翻译）。
> 跑完去 `experiments.md` 做破坏性实验（至少 3 个）——课程地图见 day02 的 `README.md`。
> 依赖与 Day 1 相同（requests + python-dotenv），Day 1 装过则无需重装；
> 从任何目录直接运行均可（脚本会自动找到同目录的共享模块）。
> **笔记请写入仓库根目录 `NOTES.md`**——面试前一夜只看它。

## Day 3 快速开始（工具注册表与异常分级）
```bash
cd day03_tool_registry
python 01_schema_drift.py        # ① 先看"病"：手写 schema 的三种死法（纯本地）
python self_check.py             # ② 42 项不变量断言（不花额度）
python 02_fc_with_registry.py    # ③ 注册表版 FC 循环，5 个场景实跑（花额度）
```
> 核心命题：**工具的"说明书"与"实现"必须是同一份真相**。
> `@tool` 装饰器一次登记 → schema 由函数签名 + docstring 实时生成，
> 加一个工具只写一个函数（Day 2 要改两处，这就是升级的全部意义）。
> 异常做了**分级**：业务异常回传给模型让它自救，系统异常回传但要求它停手。
> 对照阅读：这一天的机制就是主项目 `cs-agent/cs_agent/tools.py` 的骨架。

## 模型选择说明
本项目统一走 **OpenAI 兼容接口**，因此可无缝切换国产模型：
GLM（智谱）、通义千问（DashScope 兼容模式）、DeepSeek、Moonshot 等。
这也是"贴合大陆业务"的第一步——后续主项目将基于国产模型 + 私有化部署。

---
_学习工程 · 由 JARVIS 协同构建_
