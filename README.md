# 🤖 microbot

**microbot: Ultra-Lightweight Personal AI Assistant**

> 核心 agent 功能，仅 ~2000 行 Python 代码 — 比 nanobot 的 4000 行还要精简 50%

[![Python](https://img.shields.io/badge/python-≥3.11-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Lines of Code](https://img.shields.io/badge/LoC-~2000-orange)]()

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🧠 **Multi-LLM Support** | OpenAI (GPT-4o, o1, o3) + Anthropic (Claude) with streaming |
| 🔧 **Tool Calling** | 10 built-in tools with auto JSON Schema generation |
| 💾 **Conversation Memory** | SQLite-based session persistence, search & export |
| 🖥️ **Rich CLI** | ANSI-colored terminal UI with streaming output |
| ⚡ **Zero Heavy Deps** | Only requires `httpx` — no langchain, no frameworks |
| 📦 **~2000 Lines** | Complete agent in pure Python, easy to read and extend |

### Built-in Tools

| Tool | Description |
|------|-------------|
| `read_file` | Read file contents |
| `write_file` | Write/create files |
| `append_file` | Append to files |
| `list_directory` | List directory contents |
| `search_files` | Glob-based file search |
| `search_content` | Grep-like content search |
| `shell_exec` | Execute shell commands |
| `python_exec` | Execute Python code |
| `calculator` | Safe math evaluation |
| `web_fetch` | HTTP GET with HTML stripping |
| `get_system_info` | Current date, time, OS info |

---

## 🚀 Quick Start

### 1. Install

```bash
pip install -r requirements.txt
pip install -e .
```

### 2. Configure API Key

```bash
# OpenAI
export OPENAI_API_KEY=sk-...

# Or Anthropic
export ANTHROPIC_API_KEY=sk-ant-...
```

### 3. Run

```bash
# Interactive mode
microbot

# Or via python module
python -m microbot

# Single prompt
microbot -e "What is the capital of France?"

# Custom model
microbot -m gpt-4o

# Anthropic
microbot -m claude-sonnet-4-20250514 -p anthropic
```

---

## 💬 Usage

### Interactive Commands

```
/help       Show help
/clear      Clear conversation
/save       Save session
/load <id>  Load a session
/history    List saved sessions
/search <q> Search sessions
/model      Show/change model
/config     Show configuration
/tokens     Token usage estimate
/tools      List available tools
/export <f> Export to file
/exit       Exit (also Ctrl+D)
```

### Multiline Input

End a line with `\` to continue on the next line:

```
You > Write a function that \
... > calculates fibonacci numbers
```

### Examples

```
You > Read the file main.py and explain what it does
Bot > [reads file using tool, then explains]

You > What's 2^100?
Bot > [uses calculator] 2^100 = 1267650600228229401496703205376

You > Search for all Python files containing "TODO"
Bot > [uses search_content tool to find TODOs]
```

---

## ⚙️ Configuration

### Config File

Create `~/.microbot/config.json`:

```json
{
  "llm": {
    "provider": "openai",
    "model": "gpt-4o-mini",
    "temperature": 0.7,
    "max_tokens": 4096
  },
  "tools_enabled": true,
  "stream": true,
  "max_history": 50
}
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `MICROBOT_MODEL` | Override model name |
| `MICROBOT_PROVIDER` | Override provider (openai/anthropic) |
| `MICROBOT_BASE_URL` | Custom API base URL |
| `MICROBOT_TEMPERATURE` | Override temperature |

### CLI Arguments

```
microbot --model gpt-4o          # Set model
microbot --provider anthropic    # Set provider
microbot --no-tools              # Disable tools
microbot --no-stream             # Disable streaming
microbot --exec "prompt"         # Single-shot mode
microbot --init                  # Create default config
```

---

## 🏗️ Architecture

```
microbot/                      ~2000 lines total
├── __init__.py          (5)   Package metadata
├── __main__.py          (6)   Entry point
├── config.py          (110)   Config management (JSON + env vars)
├── llm.py             (300)   Multi-provider LLM (OpenAI + Anthropic)
├── tools.py           (340)   Tool registry + 11 built-in tools
├── agent.py           (200)   Core ReAct agent loop
├── memory.py          (200)   SQLite conversation persistence
├── cli.py             (400)   Rich terminal UI
├── prompts.py          (60)   System prompts
└── utils.py           (120)   Utility functions
```

### How It Works

```
User Input
    │
    ▼
┌─────────┐     ┌─────────┐     ┌──────────┐
│   CLI   │────▶│  Agent  │────▶│   LLM    │
│ (cli.py)│     │(agent.py│     │ (llm.py) │
└─────────┘     └────┬────┘     └──────────┘
                     │                │
                     │  tool calls    │ streaming
                     ▼                │ response
               ┌──────────┐          │
               │  Tools   │          │
               │(tools.py)│          │
               └──────────┘          │
                     │                │
                     │  results       │
                     └────────────────┘
                            │
                            ▼
                     ┌──────────┐
                     │  Memory  │
                     │(memory.py│
                     └──────────┘
```

### Design Principles

1. **Minimal Dependencies** — Only `httpx` for HTTP. No langchain, no heavy frameworks.
2. **Pure Python** — No compiled extensions, runs anywhere Python 3.11+ works.
3. **Readable** — Every file is self-contained and well-documented.
4. **Extensible** — Add new tools with a simple `@tool` decorator.
5. **Streaming First** — Real-time token-by-token output for responsive UX.

---

## 🔧 Extending

### Add a Custom Tool

```python
from microbot.tools import tool

@tool(description="Get weather for a city")
def get_weather(city: str, units: str = "celsius") -> str:
    """Fetch current weather.
    city: City name
    units: Temperature units (celsius/fahrenheit)
    """
    # Your implementation here
    return f"Weather in {city}: 22°C, sunny"
```

The `@tool` decorator automatically:
- Generates JSON Schema from type hints
- Extracts parameter descriptions from the docstring
- Registers the tool in the global store

---

## 📊 Comparison

| Feature | microbot | nanobot | LangChain |
|---------|----------|---------|-----------|
| Lines of Code | ~2,000 | ~4,000 | ~430,000 |
| Dependencies | 1 (httpx) | ? | 100+ |
| Multi-LLM | ✅ | ✅ | ✅ |
| Tool Calling | ✅ | ✅ | ✅ |
| Streaming | ✅ | ✅ | ✅ |
| Memory | ✅ SQLite | ✅ | ✅ |
| Install Time | <5s | <5s | >60s |
| Learning Curve | 30 min | 1 hour | Days |

---

## 📄 License

MIT License — Use it however you want.
