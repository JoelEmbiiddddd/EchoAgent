
# EchoAgent

> 🧠 **Context-first Agent Runtime** for building inspectable, iterative, and skill-driven AI workflows.

EchoAgent is an engineering-oriented Agent framework that treats **context as a first-class runtime artifact**.  
Instead of opaque prompt chains, EchoAgent structures agent execution into **explicit phases**, backed by a unified context store, a protocolized Skill system, and built-in observability.

EchoAgent is designed for developers who want to **understand, debug, evolve, and trust** their agents.

---

## ✨ Key Features

- 🧠 **Context-Centered Design**  
  Unified context system as the single source of truth across iterations.

- 🏗 **Explicit Agent Runtime**  
  Clear separation between instruction building, execution, parsing, and tracking.

- 🧩 **Protocolized Skills**  
  Skills are declarative documents, not ad-hoc functions.

- 📊 **Observability First**  
  Structured events, grouped logs, artifacts, and error surfacing.

- 🔌 **Extensible Integration**  
  Tool system, MCP runtime scaffolding, and provider abstraction.

- 🧪 **Engineering-First**  
  Designed for refactoring, replay, testing, and long-term evolution.

---

## 🏗 Architecture Overview

EchoAgent follows a **layered, runtime-oriented architecture**:

```

User / Workflow
↓
Context (Blackboard)
↓
Instruction Builder
↓
Executor (LLM / Tool / Skill)
↓
Output Handler
↓
Tracker → Logs / Events / Artifacts

```

**Design principle**

> *Context is explicit. Execution is observable. Behavior is reproducible.*

---

## 📦 Repository Layout

```

EchoAgent/
├── echoagent/                 # Core library
│   ├── agent/                 # Agent runtime & orchestration
│   ├── context/               # Context system (state + blocks)
│   ├── tools/                 # Tool registry & executor
│   ├── skills/                # Skill specs, registry, router
│   ├── llm/                   # Model provider abstraction
│   └── mcp/                   # MCP runtime integration
│
├── workflows/                 # Opinionated workflows
├── examples/                  # Runnable examples
├── frontend/                  # Lightweight workflow UI
├── openspec/                  # Architecture & refactor specs
├── outputs/                   # Run artifacts
└── tests/

````

> 📌 Start with `openspec/` if you want to understand the architectural intent.

---

## 🚀 Getting Started

### 1️⃣ Clone

```bash
git clone https://github.com/JoelEmbiiddddd/EchoAgent.git
cd EchoAgent
````

### 2️⃣ Environment

```bash
cp .env.example .env
```

Required:

* `OPENAI_API`
* `OPENAI_URL`
* `OPENAI_MODEL`

Optional:

* `SERPER_API_KEY`
* `SEARCH_PROVIDER=serper | searchxng`

---

## 🧠 Core Concepts

### 🧠 Context

Context is the **shared memory and state store** for the entire agent run:

* conversation history
* intermediate reasoning outputs
* tool / skill results
* errors and metadata

All agent steps **read from and write to Context**, making state transitions explicit and inspectable.

---

### 🧩 Agent Runtime

An EchoAgent run is a **phased pipeline**:

1. Instruction building (context blocks + policy)
2. Execution (model / tool / skill)
3. Output handling (tolerant parsing & validation)
4. Tracking (events, logs, artifacts)
5. Iteration control (stop conditions, limits)

Agents are **runtime systems**, not just prompts.

---

### 🔌 Tools vs Skills

| Concept | Purpose              | Characteristics                     |
| ------- | -------------------- | ----------------------------------- |
| Tool    | Low-level capability | Stateless, direct execution         |
| Skill   | Agent-level ability  | Declarative, contextual, observable |

Skills may:

* restrict tool access
* override models
* disable LLM calls
* encapsulate reusable behaviors

---

## 🔍 Architecture Deep Dive

### 🧩 Agent Layer (`echoagent/agent/`)

* **executor.py** – provider calls & runtime config
* **output_handler.py** – tolerant parsing & schema validation
* **tracker.py** – events, groups, logs, artifacts
* **prompting/** – instruction assembly & context rendering

---

### 🔌 Skill System (`echoagent/skills/`)

Skills are **Markdown documents with YAML frontmatter**.

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

This enables:

* skill discovery
* routing & activation
* capability boundaries
* future compatibility with external catalogs

---

### 📊 Observability

EchoAgent records:

* structured runtime events
* grouped logs (iteration / phase)
* explicit error blocks
* persistent run artifacts

This enables:

* replay
* debugging
* UI visualization
* regression testing

---

## 🧪 Examples & Workflows

Run a workflow:

```bash
python examples/web_researcher.py
```

Available workflows:

* Web research
* Data science
* Vanilla chat
* Skill-driven agent

Workflows act as **integration surfaces** for the runtime.

---

## ⚙️ Configuration System

Workflows accept:

* YAML / JSON paths
* dictionaries
* patch-based overrides

This allows:

* reproducible runs
* environment-specific configs
* clean separation of logic and policy

---

## 🧭 Roadmap (High-Level)

### 🟢 Near-term

* Skill routing & discovery improvements
* Iteration-aware frontend UI
* Run replay & artifact inspection

### 🟡 Mid-term

* Capability sandboxing
* Multi-agent orchestration patterns
* Structured telemetry export

### 🔵 Long-term

* Standardized Skill protocol compatibility
* Pluggable memory systems
* Production hardening

---

## 🤝 Contributing

Contributions are welcome.

Suggested workflow:

1. Read `openspec/` to understand design intent
2. Modify one runtime boundary at a time
3. Add or update a workflow as validation
4. Submit focused PRs with context

Architecture discussions are encouraged.

---

## 📄 License

This project is provided under the repository’s license terms.
