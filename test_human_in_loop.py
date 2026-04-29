#!/usr/bin/env python3
"""
人机协同 + session/update 通知模拟测试 — 无 LLM 依赖

模拟真实 Agent 行为:
  - 每轮输出 agent_message_chunk / tool_call / tool_result 通知
  - 需要确认时返回 needs_human
  - 收到人类回答后继续执行并完成

用于验证 acpx 对 session/update 通知和 needs_human 交互的兼容性。
"""
import asyncio
import json
import sys
import io
import uuid
import time

sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from core.acp.types import ACPMethod, ACPErrorCode
from core.acp.protocol import ACPProtocol


class MockAgent:
    """模拟 Agent — 含 session/update 通知输出"""

    def __init__(self):
        self.session_id: str | None = None
        self.task_prompt: str | None = None
        self.awaiting_human = False

    # ===== 消息路由 =====

    def handle(self, raw: str) -> list[str]:
        msg = ACPProtocol.parse(raw)
        method = msg.method

        if method in (ACPMethod.INITIALIZE.value, "initialize"):
            return self._rsp(msg.id, {
                "protocolVersion": "1.0",
                "capabilities": {"execute": True, "confirm": True, "push": True},
                "serverInfo": {"name": "mock-agent-notify", "version": "2.0.0"},
            })

        elif method in (ACPMethod.NEW_SESSION.value, "session/new"):
            params = msg.params or {}
            self.session_id = params.get("sessionId") or str(uuid.uuid4())[:8]
            self.awaiting_human = False
            self._log(f"Session created: {self.session_id}")
            return self._rsp(msg.id, {"sessionId": self.session_id})

        elif method in (ACPMethod.LOAD_SESSION.value, "session/load"):
            self.session_id = (msg.params or {}).get("sessionId", "") or self.session_id
            self._log(f"Session loaded: {self.session_id}")
            return self._rsp(msg.id, {"sessionId": self.session_id})

        elif method in (ACPMethod.PROMPT.value, "session/prompt"):
            return self._handle_prompt(msg)

        elif method == ACPMethod.PING.value:
            return self._rsp(msg.id, {"pong": True})

        else:
            return [self._err(msg.id, ACPErrorCode.INVALID_PARAMS, f"Unknown: {method}")]

    # ===== prompt 双模式 =====

    def _handle_prompt(self, msg) -> list[str]:
        prompt_text = self._extract_text((msg.params or {}).get("prompt", ""))
        sid = self.session_id or "default"

        if self.awaiting_human:
            return self._human_answer(msg.id, sid, prompt_text)
        else:
            return self._new_task(msg.id, sid, prompt_text)

    def _new_task(self, msg_id: str, sid: str, prompt_text: str) -> list[str]:
        self.task_prompt = prompt_text
        self._log(f"NEW TASK | prompt='{prompt_text[:60]}'")

        outputs: list[str] = []

        # 模拟工具序列 + 通知 (acpx 兼容格式)
        outputs += self._notify(sid, "agent_message_chunk",
                                f"收到任务: {prompt_text}")
        outputs += self._notify(sid, "tool_call", "{}",
                                toolCallId="tc-sshot", title="screenshot",
                                status="in_progress", rawInput={"text": "{}"})
        time.sleep(0.05)
        outputs += self._notify(sid, "tool_call_update", "截图完成 (1000x1000)",
                                toolCallId="tc-sshot", title="screenshot",
                                status="completed", rawInput={"text": "{}"},
                                rawOutput={"text": "截图完成 (1000x1000)"})

        outputs += self._notify(sid, "agent_message_chunk",
                                "已分析截图，需要人类确认后继续执行。")

        # 请求人类确认
        self.awaiting_human = True
        question = f"我已收到任务: '{prompt_text[:40]}...'。请确认是否继续？"
        outputs += self._rsp(msg_id, {
            "sessionId": sid,
            "stopReason": "needs_human",
            "message": question,
        })
        return outputs

    def _human_answer(self, msg_id: str, sid: str, answer: str) -> list[str]:
        self.awaiting_human = False
        self._log(f"HUMAN ANSWER | answer='{answer[:60]}'")

        outputs: list[str] = []

        outputs += self._notify(sid, "agent_message_chunk",
                                f"收到人类确认: {answer}")
        outputs += self._notify(sid, "tool_call", '{"grid_x":500,"grid_y":300}',
                                toolCallId="tc-click", title="click",
                                status="in_progress",
                                rawInput={"text": '{"grid_x":500,"grid_y":300}'})
        time.sleep(0.02)
        outputs += self._notify(sid, "tool_call_update", "点击成功 (960, 540)",
                                toolCallId="tc-click", title="click",
                                status="completed",
                                rawInput={"text": '{"grid_x":500,"grid_y":300}'},
                                rawOutput={"text": "点击成功 (960, 540)"})

        outputs += self._notify(sid, "tool_call", f"执行: {self.task_prompt[:20]}...",
                                toolCallId="tc-type", title="type_text",
                                status="in_progress",
                                rawInput={"text": f"执行: {self.task_prompt[:20]}..."})
        time.sleep(0.02)
        outputs += self._notify(sid, "tool_call_update", "输入完成",
                                toolCallId="tc-type", title="type_text",
                                status="completed",
                                rawInput={"text": f"执行: {self.task_prompt[:20]}..."},
                                rawOutput={"text": "输入完成"})

        outputs += self._notify(sid, "agent_message_chunk",
                                f"任务执行完毕。")

        outputs += self._rsp(msg_id, {
            "sessionId": sid,
            "stopReason": "completed",
            "message": f"根据人类回复 '{answer[:30]}...' 已完成: {self.task_prompt[:30]}...",
        })
        return outputs

    # ===== 辅助方法 =====

    def _notify(self, sid: str, utype: str, content: str, **extra) -> list[str]:
        """构建 session/update 通知"""
        return [ACPProtocol.encode(
            ACPProtocol.build_session_update(sid, utype, content, extra if extra else None)
        )]

    def _rsp(self, msg_id: str, result: dict) -> list[str]:
        return [ACPProtocol.encode(ACPProtocol.build_response(msg_id, result=result))]

    def _err(self, msg_id: str, code, message: str) -> str:
        return ACPProtocol.encode(ACPProtocol.build_error(msg_id, code, message))

    @staticmethod
    def _extract_text(prompt_content) -> str:
        if isinstance(prompt_content, list):
            parts = []
            for item in prompt_content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(item.get("text", ""))
            return "".join(parts)
        return str(prompt_content)

    def _log(self, msg: str):
        print(f"[MOCK] {msg}", file=sys.stderr, flush=True)


# ===== 主循环 =====

def main():
    agent = MockAgent()
    print("[MOCK] Mock Agent (with notifications) started", file=sys.stderr, flush=True)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        print(f"[MOCK] RAW: {line[:120]}", file=sys.stderr, flush=True)
        try:
            outputs = agent.handle(line)
        except Exception as e:
            import traceback
            traceback.print_exc(file=sys.stderr)
            outputs = [ACPProtocol.encode(
                ACPProtocol.build_error(None, ACPErrorCode.EXECUTION_FAILED, str(e))
            )]
        for out in outputs:
            print(out, flush=True)
            sys.stdout.flush()


if __name__ == "__main__":
    main()
