# 常见报错速查表（TROUBLESHOOTING）

> 遇到报错先来这里查。**看不懂的错误，多半是配置问题，不是代码问题。**
> 若排查超过 20 分钟仍无解，直接找 JARVIS，别死磕。

---

## 一、配置类（占新手报错的 80%）

### ❌ `requests.exceptions.MissingSchema: Invalid URL '/chat/completions'`

**现象**：报错里的 URL 只有半截，前面没有域名。

**根因**：`.env` 不存在，或不在脚本同目录 → `LLM_BASE_URL` 读出空字符串。

**排查（按顺序）**：
```bash
cd agent-learning/day01_raw_llm     # 注意是脚本所在目录，不是仓库根目录
ls -a                               # 用 ls -a 才能看到隐藏文件 .env
# 若没有 .env：
cp .env.example .env
```
然后在 PyCharm 里打开 `.env`，把 `your_api_key_here` 换成真实 Key。

> ⚠️ 用 PyCharm 左侧文件树看不到 `.env`？因为它是隐藏文件，需在设置里勾选
> "Show hidden files"，或直接用终端 `ls -a` 确认。

### ❌ `401 Client Error: Unauthorized`

**含义**：请求已正确发出，但身份不对。**这是进步**——说明配置和网络都通了。

**排查**：Key 是否为真实 Key / 是否复制完整（无多余空格换行）/ 是否与 BASE_URL 同平台。

### ❌ `404 Client Error: Not Found`（或模型不存在）

**含义**：`LLM_MODEL` 拼错，或该平台没有这个模型。

**排查**：核对 `.env` 里的模型名，如智谱用 `glm-4-flash`、DeepSeek 用 `deepseek-chat`、
通义用 `qwen-plus`。

### ❌ `429 Too Many Requests`

额度用尽或请求过频。检查账户余额，或降低调试频率。

### ❌ `ModuleNotFoundError: No module named 'requests'`

**根因**：运行脚本的 Python 解释器不是项目 `.venv`，或依赖没装。

**排查**：
```bash
cd agent-learning
.venv/Scripts/python.exe -m pip install -r day01_raw_llm/requirements.txt   # Windows
```
PyCharm 中确认右下角解释器已选中项目 `.venv`。

### ❌ `ModuleNotFoundError: No module named 'dotenv'`

装的是 `dotenv` 而非 `python-dotenv`（同名但不同包）。执行：
```bash
.venv/Scripts/python.exe -m pip uninstall dotenv -y
.venv/Scripts/python.exe -m pip install python-dotenv
```

---

## 二、运行位置类

### ❌ `ModuleNotFoundError: No module named '_tools'`（Day 2）

**根因**：从仓库根目录运行，脚本找不到同目录的 `_tools.py`。

**说明**：Day 2 的 `self_check.py` / `01` / `02` 已实测**支持跨目录运行**。
若仍报此错，说明您以 `python -m` 或特殊方式运行——改为直接指定脚本路径：
```bash
python agent-learning/day02_function_calling/01_handwritten_fc.py
```

---

## 三、网络类

### ❌ 请求超时 / `ConnectionError` / `SSLError`

**排查顺序**：
1. 换手机热点试试——公司/校园网常拦第三方 API；
2. 检查代理软件：某些全局代理会拦 `api.xxx.com`，把域名加白名单或关闭代理；
3. 确认能访问：浏览器打开您的 `LLM_BASE_URL` 域名应有响应。

> 铁律：**超时是必然的，不是意外**。生产代码必须设 `timeout`（本项目已统一设 60s）。

---

## 四、万能排查三步法（值得内化成习惯）

1. **看报错最后一行**——Python 把最关键的结论放在最下面。
2. **看路径**——文件名和行号告诉你崩在哪；URL 少了域名就是配置问题。
3. **最小化复现**——把可疑代码剥到最简（比如只 `print(BASE_URL)`），
   确认读到什么值。**打印变量值 > 猜。**

> 现在所有脚本已内置配置自检，会把上述大部分错误直接翻译成人话，先看它说什么。
