"""
测试 ReAct 代理
"""
from agents.react_agent import ReactAgentLoop

if __name__ == "__main__":
    agent = ReactAgentLoop(
        goal="打开飞书日历，创建一个明天下午3点的日程，标题为'AI代理测试会议'"
    )
    result = agent.run()

    print(f"\n=== Result ===")
    print(f"Success: {result.success}")
    print(f"Steps: {result.total_steps}")
    print(f"Output: {result.final_message[:500]}")
    if result.error_reason:
        print(f"Error: {result.error_reason}")
