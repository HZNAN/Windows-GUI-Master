# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Windows desktop automation agent using a ReAct loop with vision model. The agent analyzes screenshots and controls mouse/keyboard to complete tasks. Exposes an ACP (Agent Communication Protocol) server for integration with the `acpx` CLI.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env                     # then edit .env with your LLM_API_KEY
cp .acpxrc.json.example .acpxrc.json     # for acpx CLI integration
```

## Commands

```bash
# Standalone agent run
python test_react_agent.py
python test_bilibili.py

# ACP stdio server (for acpx CLI integration — primary deployment mode)
python test_acp_stdio.py
# Then from another terminal: acpx feishu-test "your task"

# ACP WebSocket server (for remote clients)
python test_react_agent_acp.py

# Run individual tests
pytest test_virtual_cursor_effects.py -v
python test_virtual_cursor_effects_visual.py   # visual/manual observation
python test_wm_paint_timing.py                 # paint performance benchmark
python test_full_animation_timing.py           # animation pipeline benchmark

# Message injection tests (interactive, needs manual window setup)
python test_message_injector.py            # full test: click/scroll/drag/type/hotkey
python test_message_injector_chinese.py    # Chinese text injection
python test_message_injector_scroll.py     # scroll wheel injection
python debug_drag.py                       # drag diagnosis
python debug_coords.py                     # coordinate mapping diagnosis

# Virtual cursor tests
python test_virtual_cursor_120fps.py       # cursor animation at 120fps

# ACP integration tests (start server first, then client)
python test_acp_server.py      # terminal 1
python test_acp_client.py       # terminal 2
python test_acp_scenarios.py    # terminal 2 (advanced scenarios)
```

## Architecture

```
acpx CLI ──► [ACP Protocol] ──► [ReAct Agent] ──► [Tools] ──► [Execution Engine] ──► [Drivers]
               core/acp/         agents/           tools/     core/                  drivers/
```

**ACP Layer** (`core/acp/`): JSON-RPC 2.0 protocol over stdio or WebSocket. `server.py` handles connections/sessions; `protocol.py` builds/parses messages; `auth.py` provides Bearer token auth.

**Shared Service** (`core/agent_service.py`): `ReactAgentService` — transport-agnostic business logic shared by both ACP transports. Session CRUD, prompt text extraction, ReactAgent lifecycle, and resource cleanup. The transport entry points (`test_acp_stdio.py`, `test_react_agent_acp.py`) are thin adapters that delegate to this service.

Two transport modes:
- **Stdio**: `test_acp_stdio.py` → `StdioHandler` — used by `acpx` CLI (configured in `.acpxrc.json`)
- **WebSocket**: `test_react_agent_acp.py` → `ReactAgentHandler(ACPHandler)` — for remote clients connecting to `ws://localhost:8765`

**ReAct Agent** (`agents/react_agent.py`): LangChain-based loop with `ChatOpenAI` bound to tools. Multi-tool-call per turn, sliding history window of 3 turns, screenshot verification after each action.

**Tools** (`tools/`): LangChain `@tool`-decorated functions exposed to the LLM. `screen.py` captures screenshot with 1000×1000 coordinate grid overlay. `mouse.py`/`keyboard.py` accept grid coordinates. `agent.py` provides state tools (`finish`/`continue_steps`/`retry`) — every turn must end with one.

**Execution Engine** (`core/execution_engine.py`): Translates tool calls into driver commands. Routes to `InputControl` based on `INPUT_MODE` config.

**Input Modes** (configured via `INPUT_MODE` in `.env`):

| Mode | Control | Mechanism | Cursor Impact |
|------|---------|-----------|---------------|
| `message` (default) | `MessageInjector` | Hybrid: PostMessage for transient, mouse_event for long ops | Hidden during long ops, zero for transient |
| `virtual` | `InputControl(virtual_mode=True)` | SetCursorPos + mouse_event (save/restore) | Brief flicker |
| `normal` | `InputControl()` | pyautogui | Full real cursor |

**MessageInjector** (`drivers/message_injector.py`): Hybrid injection driver. Pure `PostMessage`/`SendMessage` for transient operations (click, type ASCII, double_click). For operations that fundamentally require system input state (drag, mouse_down/up, scroll on non-Edit windows), uses hidden real cursor + `mouse_event` with `SetSystemCursor` transparent cursor replacement.

**Message injection dispatch table:**

| Operation | Edit/RichEdit | Chrome/Browser | Explorer/Feishu/Other |
|-----------|--------------|----------------|----------------------|
| click | PostMessage WM_LBUTTONDOWN/UP | same | same |
| double_click | PostMessage WM_LBUTTONDBLCLK | same | same |
| scroll | PostMessage WM_MOUSEWHEEL | PostMessage WM_MOUSEWHEEL | mouse_event WHEEL (hidden cursor) |
| drag | mouse_event (hidden cursor) | same | same |
| mouse_down/up | mouse_event (hidden cursor) | same | same |
| type_text (ASCII) | PostMessage WM_CHAR | same | same |
| type_text (Chinese) | Clipboard + WM_PASTE | PostMessage WM_CHAR (Unicode) | same |
| hotkey Ctrl+V | PostMessage WM_PASTE | focus + keybd_event | same |
| hotkey Ctrl+A/C/X | EM_SETSEL/WM_COPY/WM_CUT | same | same |

**Virtual Cursor** (`core/virtual_cursor.py` + `drivers/win32_overlay.py`): Animated cursor overlay using cubic Bezier curves. Rotates to face movement direction, with wind-up/wind-down rotation and idle wobble (12° sinusoidal at 0.83Hz). Rendered via Win32 layered window with `DrawIconEx`.

## Coordinate System

Screenshots are resized to `GRID_SIZE` × `GRID_SIZE` (default 1000×1000) for API calls. Tools receive `grid_x`/`grid_y` in this coordinate space. `tools/_shared.py::grid_to_screen()` converts back to actual screen coordinates.

## Key Patterns

- **State tools**: Every turn must end with `finish()`, `continue_steps()`, or `retry()` — the last tool call in a multi-tool response must be a state tool
- **History window**: Sliding window of 3 turns; `(check)` items need verification from next screenshot, `(success)`/`(fail)` track outcomes
- **Chinese text input**: Edit controls use clipboard + `WM_PASTE`; all other windows use `WM_CHAR` with Unicode codepoints (no clipboard needed)
- **Cursor hiding**: Long operations replace the system arrow cursor with a transparent 32×32 monochrome cursor via `SetSystemCursor`, restored on completion with `try/finally`
- **Keyboard injection**: `keybd_event` requires the target window to have keyboard focus (`AttachThreadInput` + `SetFocus`); `WM_CHAR` via PostMessage does not
- **Human-in-the-loop**: Agent can call `ask_human(question)` tool to pause and wait for human input. The tool blocks the agent thread via `threading.Event`; the main thread polls `AgentSession.is_waiting()` and returns `stopReason: "needs_human"` to the client. The next prompt to the same session is treated as the human's answer and injected via `inject_answer()`, waking the agent thread. The human response flows into history via the normal `current_turn_operations` → `_update_history` pipeline. Session state bridging is in `core/agent_service.py::AgentSession`
- **session/update notifications**: During prompt processing, the agent pushes real-time events (tool_call, tool_result, agent_message_chunk) into `AgentSession.notification_queue`. The main thread drains this queue during polling and sends `session/update` JSON-RPC notifications (no `id` — fire-and-forget) to the client via stdout (stdio) or WebSocket. Notification types go in `params.sessionUpdate`, matching OpenClaw ACP spec

## Configuration

All config in `config/settings.py`, loaded from `.env` via `python-dotenv`. Key settings:

| Variable | Default | Purpose |
|---|---|---|
| `LLM_API_KEY` | (required) | OpenAI 兼容 API Key（火山/小米/智谱/OpenAI 等） |
| `LLM_BASE_URL` | `https://ark.cn-beijing.volces.com/api/v3` | API 地址（OpenAI 兼容格式） |
| `LLM_MODEL` | `doubao-seed-2-0-lite-260215` | 模型名称（vision-capable） |
| `GRID_SIZE` | 1000 | Screenshot resize target (GRID_SIZE × GRID_SIZE) |
| `AGENT_MAX_STEPS` | 15 | Max ReAct loop iterations |
| `AGENT_HISTORY_WINDOW` | 3 | Turns kept in context |
| `AGENT_TURN_DELAY` | 0.3 | Pause (seconds) after tools finish before next turn screenshot |
| `INPUT_MODE` | `message` | Input mode: `message` \| `virtual` \| `normal` |
| `VIRTUAL_CURSOR_DURATION` | 0.5 | Cursor move animation duration (seconds) |
| `ACP_HOST`/`ACP_PORT` | localhost:8765 | WebSocket server bind |
| `ACP_TOKEN` | (empty) | Bearer token for ACP auth; empty = no auth |
| `VIRTUAL_CURSOR_FPS` | 60 | Cursor animation frame rate |
| `VIRTUAL_CURSOR_AMPLITUDE` | 15 | Bezier curve perturbation (pixels) |
| `LLM_TEMPERATURE` | 0.1 | Model sampling temperature |

The `.acpxrc.json` at project root configures the `acpx` CLI integration — registers agent `feishu-test` pointing to `test_acp_stdio.py` with `acp` protocol over stdio. This file is gitignored; copy from `.acpxrc.json.example`.

Virtual cursor assets live in `cursor/` — each subdirectory holds an `arrow.png` and `hand.png`. Configure via `VIRTUAL_CURSOR_PATH` in `.env`.
