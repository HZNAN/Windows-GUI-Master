"""
新 Agent 测试脚本
使用 PlannerAgent( GLM-4.6-flash 视觉) + GLM-OCR 精确定位 + ExecutionEngine 执行
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
import os
os.environ["ZHIPU_API_KEY"] = "e539790a8240487c90e89c889f814b4f.1H5t3p9QsiOJuWn5"

from core.agent_loop import AgentLoop

if __name__ == "__main__":
    goal = "给 Agent Hands 发送消息：测试新架构"

    print("=" * 60)
    print("New Agent Architecture Test")
    print("=" * 60)
    print(f"Goal: {goal}")
    print()

    agent = AgentLoop(goal=goal)
    result = agent.run()

    print()
    print("=" * 60)
    print("Result:")
    print(f"  Success: {result.success}")
    print(f"  Total steps: {result.total_steps}")
    print(f"  Output dir: {agent.output_dir}")
    if result.error_reason:
        print(f"  Error: {result.error_reason[:100]}")
    print()
    print("Step decisions:")
    for i, d in enumerate(result.decisions):
        print(f"  [{i+1}] {d.action} ({d.x},{d.y}) | {d.status} | {d.think[:50]}")
