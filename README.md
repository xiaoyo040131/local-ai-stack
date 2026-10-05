# local-ai-stack

> 把**本地运行的开源大模型**接入日常 AI 工具的一套轻量方案：在 **Claude Code** 里用本地模型写代码，在**命令行**里跟本地模型联网聊天。全程本地推理，不依赖云端 API，数据不出本机。

---

## 这个东西具体是做什么的？

现在人人都能用 ChatGPT / Claude 等云端大模型，但这些都要联网、要付费、数据也要发给别人。`local-ai-stack` 提供另一条路：**用跑在你自己电脑上的开源大模型（如 OpenAI 开源的 gpt-oss:20b）**，通过 Ollama 本地运行，然后让你常用的工具（Claude Code、终端）能直接调用这个本地模型。

它包含三件事：

1. **让 Claude Code 用上本地模型** —— Claude Code 本是 Anthropic 官方模型的客户端，通过本项目的一个轻量代理，把它"骗"成本地模型的入口，于是你能在 Claude Code 里用本地模型写代码、改文件、跑命令。
2. **让本地模型在终端里联网聊天** —— 命令行里跟模型对话，模型可以自动调用搜索（必应/百度）获取最新信息，再总结成中文回答。相当于一个"离线可联网"的 AI 助手。
3. **一套一键启动脚本** —— 不用记一堆命令，双击 `.bat` 就能把后端（Ollama + 代理）拉起来。

### 架构图

```
┌───────────────────────────────────────────────────────────┐
│  Claude Code (Anthropic 客户端)                            │
│        │  HTTPS → localhost:11435  (Anthropic /v1/messages) │
│        ▼                                                  │
│  gptoss_proxy.py   ← 本项目的核心代理                      │
│   - 把 Anthropic 请求转成 Ollama 原生 /api/chat            │
│   - 支持 web_search 工具往返（联网搜索）                    │
│        │  HTTP → localhost:11434                            │
│        ▼                                                  │
│  Ollama  ──>  本地模型 (gpt-oss:20b)                       │
└───────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────┐
│  终端聊天  webchat.py  (命令行)                            │
│        │  HTTP → localhost:11434  (Ollama /api/chat)        │
│        ▼                                                  │
│  Ollama  ──>  本地模型  ──>  自动联网搜索 (必应/百度)        │
└───────────────────────────────────────────────────────────┘
```

### 特性

- ✅ **完全本地推理**：模型跑在本机，数据不出电脑，无需注册云端服务。
- ✅ **Claude Code 兼容**：通过代理让 Claude Code 走本地模型（Anthropic + OpenAI 双协议）。
- ✅ **联网搜索**：终端聊天时模型可自动搜索最新信息（必应主、百度备）。
- ✅ **工具调用**：支持把搜索工具暴露给模型，模型决定调用、结果回传总结。
- ✅ **一键启动**：`.bat` 脚本，改几个路径就能用。
- ✅ **纯标准库**：Python 脚本零第三方依赖，只需 Python 3 标准库。

---

## 目录结构

```
local-ai-stack/
├── README.md                 # 本文件：项目介绍
├── LICENSE                   # MIT 开源协议
├── .gitignore                # 忽略模型文件、缓存等
├── docs/
│   └── USAGE.md              # 详细使用说明（安装/配置/常见问题）
└── scripts/
    ├── gptoss_proxy.py       # 核心：Anthropic/OpenAI 兼容代理（本地模型入口）
    ├── webchat.py            # 终端联网聊天工具
    ├── start-local-ai.bat    # 一键启动后端（Ollama + 代理）
    ├── start-claude-code.bat # 一键启动后端 + 打开 Claude Code
    └── webchat.bat           # 一键启动终端联网聊天
```

---

## 快速开始

**前置依赖**：Ollama、Python 3、Claude Code（仅用 Claude Code 时需要）。详见 [docs/USAGE.md](docs/USAGE.md)。

```bash
# 1. 拉取一个本地模型（示例用 OpenAI 的 gpt-oss:20b）
ollama pull gpt-oss:20b

# 2. 启动后端（Ollama + 代理）
#    Windows：双击 scripts/start-local-ai.bat
#    或手动：
python scripts/gptoss_proxy.py &

# 3a. 用 Claude Code（需先按 USAGE.md 配置好 .claude/settings.json）
claude

# 3b. 或直接在终端联网聊天
python scripts/webchat.py
```

> ⚠️ 脚本里的路径（`OLLAMA` / `PYTHON` / `CLAUDE`）是占位符，使用前请按 `docs/USAGE.md` 改成你自己的机器路径。

---

## 为什么需要这个代理？（原理）

用 Claude Code 直连 Ollama 会遇到两个坑，本项目就是为解决它们而写的：

1. **推理模型在兼容接口下 `content` 为空**：`gpt-oss` 这类推理模型，通过 Ollama 的 OpenAI/Anthropic 兼容端点时，答案会被吞进 `thinking`，正文为空；只有 Ollama 原生 `/api/chat` 能正确返回正文。所以代理必须走 `/api/chat`。
2. **协议转换**：Claude Code 说 Anthropic 协议，Ollama 原生是自有协议，代理负责在两者之间翻译，并处理好流式事件、工具往返。

---

## 环境变量（都可选）

| 变量 | 默认 | 说明 |
|---|---|---|
| `OLLAMA_API` | `http://localhost:11434/api/chat` | Ollama 聊天端点 |
| `OLLAMA_MODEL` | `gpt-oss:20b` | 要用的本地模型名 |
| `PROXY_PORT` | `11435` | 代理监听端口 |

---

## 许可证

[MIT](LICENSE)

本项目是工具脚本与文档，**不包含**任何模型权重或第三方服务代码。所用模型（如 gpt-oss）与工具（Ollama、Claude Code、Open WebUI）均为各自开源/官方发布，请遵守各自许可。
