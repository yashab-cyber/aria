# Architecture Overview

A.R.I.A. is built with a highly modular and extensible architecture, allowing for specialized execution depending on the user's intent.

## Core Backend (`/core`)
- **LLM Engine (`llm_engine.py`)**: The central routing system that interfaces with external language models.
- **Planner & Intent Classifier (`planner.py`, `intent_classifier.py`)**: Responsible for analyzing user requests, breaking them down into autonomous steps, and deciding which tools to use.
- **Tool Registry (`tool_registry.py`)**: Centralized decorator-based registry (`@aria_tool`) that exposes class methods as actionable tools for the LLM.

## Capabilities & Modules (`/modules`)
A.R.I.A.'s toolset is categorized into independent modules:
- **System (`system/`)**: File management (`read_file`, `write_file`, `replace_in_file`, `search_code`), OS-level shell execution, and hardware metric gathering.
- **Coding (`coding/`)**: Provides the `CodeSandbox` for safely spinning up and executing Python or JavaScript/Node.js files.
- **Browser (`browser/`)**: Enables the agent to control web browsers to autonomously research or automate internet tasks.
- **Email & Research (`email/`, `research/`)**: Outbound/inbound communication and specialized internet querying.

## RAG Memory System (`/memory`)
A persistent memory layer powered by ChromaDB.
- Automatically vectorizes and stores user conversations, security findings, or past execution logs.
- Recalls cross-session context so A.R.I.A. learns from past interactions and avoids repeating mistakes.

## Frontend UI (`/ui`)
A modern interface utilizing:
- **TypeScript & Vite**: For lightning-fast rendering.
- **WebSockets**: To maintain a persistent, bidirectional event stream with the FastAPI backend, enabling real-time terminal output and streaming LLM responses.
