# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Windows desktop automation agent using a ReAct loop with vision model. The agent analyzes screenshots and controls mouse/keyboard to complete tasks. Exposes an ACP (Agent Communication Protocol) server for integration with the `acpx` CLI.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # then edit .env with your ARK_API_KEY
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
python test_message_injector.py   # full test: click/scroll/drag/type/hotkey
python debug_drag.py              # drag diagnosis
python debug_coords.py            # coordinate mapping diagnosis

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

**ACP Layer** (`core/acp/`): JSON-RPC 2.0 protocol over stdio or WebSocket. `server.py` handles connections/sessions; `protocol.py` builds/parses messages; `auth.py` provides Bearer token auth. Two transport modes:
- **Stdio**: `test_acp_stdio.py` — used by `acpx` CLI (configured in `.acpxrc.json`)
- **WebSocket**: `test_react_agent_acp.py` — for remote clients connecting to `ws://localhost:8765`

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

Screenshots are resized to 1000×1000 for API calls. Tools receive `grid_x`/`grid_y` in this coordinate space. `tools/_shared.py::grid_to_screen()` converts back to actual screen coordinates.

## Key Patterns

- **State tools**: Every turn must end with `finish()`, `continue_steps()`, or `retry()` — the last tool call in a multi-tool response must be a state tool
- **History window**: Sliding window of 3 turns; `(check)` items need verification from next screenshot, `(success)`/`(fail)` track outcomes
- **Chinese text input**: Edit controls use clipboard + `WM_PASTE`; all other windows use `WM_CHAR` with Unicode codepoints (no clipboard needed)
- **Cursor hiding**: Long operations replace the system arrow cursor with a transparent 32×32 monochrome cursor via `SetSystemCursor`, restored on completion with `try/finally`
- **Keyboard injection**: `keybd_event` requires the target window to have keyboard focus (`AttachThreadInput` + `SetFocus`); `WM_CHAR` via PostMessage does not

## Configuration

All config in `config/settings.py`, loaded from `.env` via `python-dotenv`. Key settings:

| Variable | Default | Purpose |
|---|---|---|
| `ARK_API_KEY` | (hardcoded default) | 火山引擎 ARK API key |
| `ARK_VISION_MODEL` | `doubao-seed-2-0-lite-260215` | Vision model ID |
| `AGENT_MAX_STEPS` | 15 | Max ReAct loop iterations |
| `AGENT_HISTORY_WINDOW` | 3 | Turns kept in context |
| `AGENT_TURN_DELAY` | 0.3 | Pause (seconds) after tools finish before next turn screenshot |
| `INPUT_MODE` | `message` | Input mode: `message` \| `virtual` \| `normal` |
| `VIRTUAL_CURSOR_DURATION` | 0.5 | Cursor move animation duration (seconds) |
| `ACP_HOST`/`ACP_PORT` | localhost:8765 | WebSocket server bind |

The `.acpxrc.json` at project root configures the `acpx` CLI integration — registers agent `feishu-test` pointing to `test_acp_stdio.py` with `acp` protocol over stdio.
