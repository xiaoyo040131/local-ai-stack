# 详细使用说明 (USAGE)

本页教你在自己的机器上把这套方案跑起来。目标：**用本地大模型**接入 Claude Code + 命令行联网聊天。

---

## 0. 你需要什么

| 依赖 | 用途 | 安装 |
|---|---|---|
| [Ollama](https://ollama.com/) | 本地运行大模型的引擎 | 官网下载安装 |
| Python 3（≥3.8） | 运行代理和聊天脚本 | [python.org](https://www.python.org/) |
| [Claude Code](https://www.anthropic.com/claude-code)（可选） | 在 Claude Code 里用本地模型 | `npm install -g @anthropic-ai/claude-code` |

> 本项目 Python 脚本只用标准库，**不需要** pip 装任何东西。

---

## 1. 安装与拉取模型

### 1.1 安装 Ollama

官网下载安装。装好后打开一个终端验证：

```bash
ollama --version
```

### 1.2 拉取一个本地模型

示例用 OpenAI 开源的 **gpt-oss:20b**（推理模型，约 13GB）：

```bash
ollama pull gpt-oss:20b
```

也可以换成任何 Ollama 支持的模型（qwen、llama 等）。模型名会作为 `OLLAMA_MODEL`。

### 1.3 确认模型能跑

```bash
ollama run gpt-oss:20b "你好"
```

能看到回复说明本地推理 OK。**先完成这一步，再继续**。

---

## 2. 配置脚本路径

`scripts/` 下的三个 `.bat` 顶部都有**占位符路径**，使用前必须改成你自己的机器路径：

| 变量 | 例子（Windows） | 说明 |
|---|---|---|
| `OLLAMA` | `C:\Users\you\AppData\Local\Programs\Ollama\ollama.exe` | ollama.exe 完整路径 |
| `PYTHON` | `C:\Users\you\AppData\Local\Programs\Python\Python312\python.exe` | python.exe 完整路径 |
| `CLAUDE` | `C:\path\to\claude.exe` | 仅 `start-claude-code.bat` 需要 |

改好后，脚本会通过环境变量 `OLLAMA_MODEL` 把模型名传给 Python（默认 `gpt-oss:20b`）。

> 提示：直接运行 Python 脚本（不经过 .bat）时，用环境变量控制：
> ```bash
> set OLLAMA_MODEL=qwen2.5:7b
> python gptoss_proxy.py
> ```

---

## 3. 用法一：终端联网聊天（webchat）

**命令行里跟本地模型聊天，模型会自动联网搜索再回答。**

```bash
# Windows 双击脚本
scripts\webchat.bat

# 或命令行直接跑
python scripts/webchat.py
```

- 输入问题回车即可；模型会先自动搜索（必应/百度）再总结。
- 输入 `exit` / `quit` 退出。
- 必须先启动 Ollama（可先运行 `start-local-ai.bat`）。

---

## 4. 用法二：在 Claude Code 里用本地模型

### 4.1 启动后端

```bash
scripts\start-local-ai.bat
```

它会启动：
- **Ollama**（本地模型引擎，端口 11434）
- **gptoss_proxy.py**（代理，端口 11435）

### 4.2 配置 Claude Code 指向本地模型

编辑 Claude Code 的配置文件，把 `ANTHROPIC_BASE_URL` 指向代理、`ANTHROPIC_MODEL` 指向你的模型：

**文件**：`~/.claude/settings.json`

```json
{
  "auth": { "skipLoginCheck": true },
  "env": {
    "ANTHROPIC_AUTH_TOKEN": "ollama",
    "ANTHROPIC_BASE_URL": "http://localhost:11435",
    "ANTHROPIC_MODEL": "gpt-oss:20b",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "gpt-oss:20b",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "gpt-oss:20b",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "gpt-oss:20b",
    "CLAUDE_CODE_DISABLE_UNKNOWN_MODEL_WINDOW_ENFORCEMENT": "1"
  }
}
```

> 备份你原来的 `settings.json` 再改。Claude Code 每个会话的配置在它的安装目录里，找不到就用 `claude --version` 相关命令定位。

### 4.3 启动 Claude Code

```bash
claude
```

就能用本地模型对话、写代码了。代理在 11435 端口处理 Claude Code 发来的请求并转发给 Ollama。

> ⚠️ **已知限制**：本地 20B 级模型在 Claude Code 的"自动 Agent 循环"里，**实时联网搜索**可能不稳定（反复搜索、不收敛总结）。普通对话/写代码完全稳定。想要稳定的联网对话，请用 `webchat`（用法一）。

---

## 5. 一键启动脚本一览

| 脚本 | 作用 |
|---|---|
| `start-local-ai.bat` | 只启动后端（Ollama + 代理），不打开任何界面 |
| `start-claude-code.bat` | 启动后端 + 直接打开 Claude Code |
| `webchat.bat` | 启动后端检查 + 进入终端联网聊天 |

---

## 6. 常见问题 (FAQ)

**Q: 代理起来了，但连不上？**
确认 Ollama 在跑（`ollama --version`），且端口监听正常：
```bash
netstat -ano | findstr :11435    # 代理
netstat -ano | findstr :11434    # Ollama
```

**Q: Claude Code 报 unrecognized_model？**
无害警告——本地模型不在 Claude 官方目录里。`CLAUDE_CODE_DISABLE_UNKNOWN_MODEL_WINDOW_ENFORCEMENT=1` 已帮你抑制大部分。不影响使用。

**Q: 聊天时模型说"无法联网"？**
在 `webchat` 里不会——它强制模型调搜索。在 Claude Code 里，20B 模型可能不会稳定触发联网，这是模型能力限制，见上文。

**Q: 换了模型怎么改？**
改环境变量 `OLLAMA_MODEL`，或在 `.bat` 顶部改 `OLLAMA_MODEL`。

**Q: 报错 "cannot find closing '}'"？**
工具参数的 `arguments` 必须是 JSON 对象而不是字符串——本项目代理已正确处理。若你自己改代码，注意这点。

---

## 7. 术语

- **Ollama**：本地大模型运行器。
- **Anthropic /v1/messages**：Claude Code 使用的 API 协议。
- **OpenAI /v1/chat/completions**：另一种通用协议，本代理也支持。
- **gpt-oss**：OpenAI 开源模型，本项目示例用的推理模型。
