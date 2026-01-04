

# EchoAgent

> 🧠 **Context-First Agent Runtime for Building Inspectable AI Systems**

EchoAgent is an **engineering-oriented agent framework** that treats **context as a first-class runtime artifact**.
Instead of hiding reasoning inside opaque prompt chains, EchoAgent exposes execution as a **structured, observable, and reproducible process**.

It is designed for developers who want to **understand, debug, and evolve** intelligent agents — not just run them.

---

## ✨ Why EchoAgent?

Most agent frameworks focus on *getting something to work*.

EchoAgent focuses on **making it understandable, controllable, and evolvable**.

| Traditional Agents | EchoAgent             |
| ------------------ | --------------------- |
| Prompt-centric     | Context-centric       |
| Implicit state     | Explicit state        |
| Hard to debug      | Fully observable      |
| Ad-hoc tools       | Protocolized skills   |
| One-off flows      | Reproducible runtimes |

---

## ⚡ Using uv (Recommended)

This project uses **uv** for fast, reliable Python package management and reproducible environments.

### Install uv
macOS/Linux:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
````

### Setup Environment

```bash
# Clone the repository
git clone https://github.com/JoelEmbiiddddd/EchoAgent.git
cd EchoAgent

# Create .env
cp .env.example .env

# Sync dependencies (creates .venv and uses uv.lock if present)
uv sync
```

> Tip: Commit `uv.lock` to keep environments reproducible across machines.

---

## 🔐 Configure API Keys

EchoAgent requires API keys for LLM providers and tools.
Set your environment in `.env`:

```env
OPENAI_API_KEY=your_key
OPENAI_MODEL=gpt-4.1
```

See `.env.example` for full configuration options.

---

## 🚀 Quick Start

### Run a workflow (recommended)

```bash
uv run python workflows/web_researcher.py
```

After a run completes, you will get a **single run directory**:

```
outputs/runs/{run_id}/
  reports/
    final_report.md
    final_report.html
  runlog/
    runlog.jsonl
    run_index.json
  snapshots/
    iter_1.json
    iter_2.json
    ...
  debug/   # empty by default (disabled)
```

* **final_report.md/html**: the final result (what you usually care about)
* **runlog/runlog.jsonl**: structured event timeline (steps/tools/errors)
* **runlog/run_index.json**: fast index for UI/replay
* **snapshots/**: per-iteration snapshots for resume/replay
* **debug/**: only generated when debug mode is enabled

---

## ✅ Testing

```bash
uv run pytest -q
```

Optional self-check:

```bash
uv run python -m compileall echoagent
```

---

## 🧠 Core Idea

EchoAgent treats an agent run as a **runtime system**, not a prompt.

At its core:

> **Context is the source of truth.**
> All execution reads from it and writes back to it.

This makes behavior:

* inspectable
* debuggable
* reproducible
* extensible

---

## 🏗 Architecture Overview

```mermaid
flowchart TD
  U[User / Workflow] --> W[Workflow Runner<br/>workflows/*]

  subgraph R["Runtime Core (echoagent/)"]
    direction TB
    C[(Context Store<br/>echoagent/context)]
    IB[Instruction Builder<br/>echoagent/agent/prompting]
    EX[Executor<br/>echoagent/agent/executor.py]
    OH[Output Handler<br/>echoagent/agent/output_handler.py]
    TR[Tracker / Observability<br/>echoagent/agent/tracker.py]
    C --> IB --> EX --> OH --> TR
    TR -->|writes| C
  end

  W --> C

  subgraph E["Execution Surface"]
    direction LR
    LLM[LLM Provider<br/>echoagent/llm/*]
    TOOLS[Tool Runtime<br/>echoagent/tools]
    SKILLS[Skill System<br/>echoagent/skills]
  end

  EX -->|model call| LLM
  EX -->|tool call| TOOLS
  EX -->|skill activation| SKILLS

  subgraph O["Outputs"]
    direction TB
    OUT[outputs/runs/{run_id}/]
    REPORTS[reports/<br/>final_report.*]
    RUNLOG[runlog/<br/>runlog.jsonl + run_index.json]
    SNAP[snapshots/<br/>iter_*.json]
    DEBUG[debug/<br/>(off by default)]
  end

  TR --> OUT
  OUT --> REPORTS
  OUT --> RUNLOG
  OUT --> SNAP
  OUT --> DEBUG
```

---

## 🧩 Core Concepts

### Context

Context is the shared, mutable state of a run:

* conversation history
* intermediate reasoning
* tool / skill results
* errors & metadata

All runtime stages **read from and write to Context**.

---

### Agent Runtime

An EchoAgent run is a **phased pipeline**:

1. Instruction building
2. Execution (LLM / Tool / Skill)
3. Output parsing & validation
4. Tracking & artifact generation
5. Iteration control

Each phase is explicit and observable.

---

### Tools vs Skills

| Concept | Purpose              | Properties                        |
| ------- | -------------------- | --------------------------------- |
| Tool    | Low-level capability | Stateless, direct execution       |
| Skill   | Agent behavior       | Declarative, contextual, governed |

Skills can:

* restrict tool usage
* override models
* disable LLM calls
* encapsulate reusable logic

---

## 🧩 Skill Definition (Example)

```markdown
---
name: web-research-summarize
description: Research a topic and summarize findings.
tags: [web, research]
allowed_tools: [web.search, web.crawl]
model_override: gpt-4.1
---

# Instructions
You are a research assistant...
```

---

## 🔍 Observability & Debugging

EchoAgent records:

* structured runtime events (runlog.jsonl)
* iteration snapshots (snapshots/)
* final result report (final_report.*)

This enables:

* replay & inspection
* regression testing
* UI visualization
* behavior comparison

---

## 📦 Repository Structure

```
EchoAgent/
├── echoagent/
│   ├── agent/        # runtime orchestration
│   ├── context/      # shared state & blocks
│   ├── tools/        # tool registry & execution
│   ├── skills/       # skill definitions
│   ├── llm/          # model providers
│   └── mcp/          # MCP integration
│
├── workflows/        # opinionated pipelines
├── examples/         # runnable demos
├── outputs/          # runtime outputs (gitignored)
└── tests/
```

---

## 🤝 Contributing

Contributions are welcome.

Guidelines:

1. Change one runtime boundary at a time
2. Add or update a workflow as validation
3. Keep behavior observable

---

## 📄 License

Provided under the repository license.

