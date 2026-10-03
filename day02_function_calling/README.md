# Day 2 · Function Calling 与 ReAct 循环（v2）

> **今天的核心命题只有一个：停止权在谁手里？**
> 模型只会"点菜"（返回 tool_calls），你的代码负责"上菜"（执行并回传）。
> Agent 的全部演进，都是围绕"谁来决定信息够了、该停了"展开的。

---

## 为什么有 v2（坦白书）

v1 把 `01` 标注为"单轮四步闭环"、`02` 标注为"多轮 ReAct 进阶"——
但你（Sir）看得比标签准：**01 的骨架本来就是循环，两个文件同构**。
标签撒谎了，所以推倒重来。v2 的设计原则：**差异必须真实存在于代码里，
每个概念钉子都用 ★ 标在钉的位置。**

---

## 概念阶梯（本目录的全部逻辑）

```
step1  one-shot          step2  ReAct               step3  护栏
停止权在【代码】    →    停止权交给【模型】    →    自由 + 护栏
最多 2 次调用            循环，模型喊停才停        max_steps / 去重 / 异常回传
收尾 tools=None          ★ 与 step1 只差两处       ★ 在 step2 上加三道
"菜单收走了，硬答"        "模型自己决定不点了"      "自由是有账单的"
```

三个文件跑**相同的场景**（S1/S2/S3），答案与统计的差异会自己说话。

## 文件地图

| 文件 | 角色 | 一句话 |
|---|---|---|
| `_tools.py` | 共享工具集 | 4 个工具 + Schema，**单一事实来源**，全目录只此一份 |
| `llm_client.py` | 共享客户端 | .env 显式路径加载 + 配置自检 + 401/404/429 人话翻译 |
| `step1_oneshot.py` | 阶梯 ① | 停止权在代码：收尾调用 `tools=None` 收走菜单 |
| `step2_react.py` | 阶梯 ② | 停止权给模型：循环 + "模型不再要工具即停"（★两处差异） |
| `step3_guardrails.py` | 阶梯 ③ | 三道护栏：max_steps=8 / seen_calls 去重 / 异常全量回传 |
| `self_check.py` | 自检 | 纯本地断言，**不花一分钱**，跑任何脚本前先跑它 |
| `experiments.md` | 破坏性实验 | E1–E6：改代码看它怎么坏——理解的试金石 |

## 运行顺序（总计约 90 分钟）

```bash
# 前置：本目录 .env 已填真实 Key（Day 1 装过依赖则无需重装）
python self_check.py          # 0. 本地自检，10 项断言全绿再继续
python step1_oneshot.py       # 1. 记下 S2 的退款金额（模型被迫心算的）
python step2_react.py         # 2. 对比 S2 金额（这次能调 calculator）与步数
python step3_guardrails.py    # 3. 看 S4 重复调用被拦、S5 错误观察自救
```

然后：`experiments.md` 挑 3 个做 → 盲写 `react_agent` → 费曼复述自测题。

---

## 核心概念一：One-Shot vs ReAct = 停止权在谁手里

| | step1 one-shot | step2 ReAct |
|---|---|---|
| 结构 | 无循环，最多 2 次模型调用 | `for step in range(max_steps)` |
| 停止权 | **代码**（收尾 `tools=None`，菜单收走） | **模型**（不再请求工具即停） |
| 依赖链问题（S2） | 被迫心算 259×0.8，**可能算错** | 查完状态/价格后**再调** calculator |
| 适用 | 查快递/查天气类单工具问答（便宜、快、可控） | "B 步的参数依赖 A 步的观察"的任务 |
| 生产地位 | 大量存在，不是落后 | Agent 的骨架 |

**判别式一句话：任务需要"根据观察决定下一步"吗？不需要 → one-shot；需要 → ReAct。**

## 核心概念二：ReAct 的决策模型不在 Python 里（四个载体）

代码是决策的**搬运工与记录员，不是决策者**。决策分布在四个地方：

| 载体 | 位置 | 代码里的体现 | 改动会怎样 |
|---|---|---|---|
| ① 模型权重 | 云端（不可见） | `chat_once` 那一次 HTTP 请求 | 换模型 = 换一个决策大脑 |
| ② 策略提示词 | system prompt | step2 的 `SYSTEM_PROMPT`（"每步先想缺什么"） | 步数、行为模式明显变化（实验 E2） |
| ③ 工具描述 | TOOLS_SCHEMA 的 description | refund_apply 里写着"没给订单号先追问" | 模型选错工具/用错方式（实验 E6） |
| ④ 对话历史 | messages 列表 | 每次 `messages.append(...)` | 丢一条 Observation，模型立刻"失忆" |

## 核心概念三：ReAct 三段式 ↔ 现代 FC 协议映射（面试必答）

| 论文时代（2022，纯文本+正则） | 现代 Function Calling |
|---|---|
| `Thought: ...` | 模型内部推理（推理模型可见 `reasoning_content`） |
| `Action: search[query]` | `message.tool_calls`（结构化 JSON，不用正则解析了） |
| `Observation: ...` 拼回 prompt | `role="tool"` 消息，`tool_call_id` 与请求配对 |

**同构换马甲**：协议只是把三段文本结构化了，思想没变。

## 核心概念四：三道护栏（玩具与生产的分界线）

| 护栏 | 防什么 | 代码位置 |
|---|---|---|
| ① `max_steps=8` + 未收敛显式返回 | 模型无限循环烧 token | `for step in range(1, max_steps+1)` |
| ② `seen_calls` 去重（同工具+同参数） | 原地打转反复查同一订单 | `signature in seen_calls` 分支 |
| ③ 异常全量包装成 Observation | 一个工具崩溃杀死整个循环 | `except Exception as e` → `{"error": ...}` |

**面试金句：循环骨架 20 行写完，难的从来不是循环，是策略（提示词）、记忆（历史维护）与护栏（防失控）。**
好护栏的标准：正常路径零感知，异常路径强干预。

---

## 今天的学法（四步学习法）

1. **手敲 step2**（30–40 分钟）：`step2_react.py` 是今天最值得手敲的文件——敲不出来的地方就是知识洞。不看屏幕上这份，另存 `my_react.py` 默写骨架。
2. **破坏性实验**：`experiments.md` 至少做 3 个（推荐 E1、E3、E6）。改代码看它怎么坏，比读十遍注释有用。
3. **盲写核心**：关掉所有材料，白板/纸上默写 ReAct 循环骨架（循环、停止条件、tool_calls 解析、role=tool 回传、max_steps 兜底）。写不出来的就是没学会。
4. **费曼复述**：对着下面的自测题，讲给 JARVIS 听，接受追问。

## 自测题（10 道，讲不清的回去重跑对应 step）

1. Function Calling 四步闭环是哪四步？模型执行工具吗？（它不执行，只"点菜"）
2. `messages.append(msg)`（assistant 带 tool_calls 的消息）如果不回存，会发生什么？
3. `role="tool"` 消息里的 `tool_call_id` 是干嘛的？去掉会怎样？
4. One-Shot 和 ReAct 的本质区别一句话？停止权在谁手里？
5. step1 收尾调用为什么必须 `tools=None`？传了会怎样（"半吊子 one-shot"bug）？
6. ReAct 的决策模型在 Python 代码里吗？说出四个载体。
7. Thought / Action / Observation 在现代 FC 协议里分别对应什么？
8. 三道护栏各防什么？去掉 seen_calls，S4 场景会发生什么？
9. 工具抛异常，step2 会怎样、step3 会怎样？"错误也是信息"怎么理解？
10. A1002 退款该退多少（paid_total=307.2 vs 单价×数量=384）？为什么工具的 paid_total 字段语义是设计者的责任？

## 面试预警（出现率很高的三问）

- **"手写过 Agent 吗？"** → 讲 step2→step3：先循环骨架，再谈三护栏，落在金句上。
- **"Function Calling 的原理？"** → 四步闭环 + "模型不执行、代码执行" + tool_call_id 配对。
- **"ReAct 是什么？"** → 论文背景（文本+正则）→ 协议化映射 → 本质是"观察驱动的迭代决策"。

## 衔接

- **笔记**：所有观察写进仓库根目录 `NOTES.md` 的 Day 2 节（面试前一夜只看它）。
- **下一步**：主项目 `cs-agent` v0.1 的引擎，**就直接长在 step3 的 `guardrailed_agent` 上**——今天把这个函数吃透，主项目开工省一半力气。

---
_v2 · 2026-10-04 重构 · 概念阶梯设计 · 由 JARVIS 交付_
