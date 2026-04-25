"""
ACP 协议测试客户端
用于测试 ACP Server 是否正常工作
"""
import asyncio
import json
import sys

import websockets

# 添加项目根目录到路径
sys.path.insert(0, ".")

from core.acp.types import ACPMessage, ACPMethod, ACPErrorCode
from core.acp.protocol import ACPProtocol


async def test_server_info(uri: str, token: str = ""):
    """测试获取服务器信息"""
    print("\n" + "=" * 60)
    print("测试 1: 获取服务器信息 (agent.execute)")
    print("=" * 60)

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with websockets.connect(uri, additional_headers=headers) as ws:
        # 发送 execute 请求
        msg = ACPProtocol.build_execute(
            action="server.info",
            params={},
            msg_id="test_001",
        )
        await ws.send(ACPProtocol.encode(msg))
        print(f"发送: {ACPProtocol.encode(msg)}")

        # 接收响应
        response = await ws.recv()
        print(f"接收: {response}")

        data = json.loads(response)
        if data.get("result"):
            print("✅ 测试通过")
            return True
        else:
            print("❌ 测试失败")
            return False


async def test_confirm_request(uri: str, token: str = ""):
    """测试确认请求 (Server -> Client)"""
    print("\n" + "=" * 60)
    print("测试 2: 模拟 Server 发送确认请求")
    print("=" * 60)

    # 这个测试需要 Server 支持模拟确认请求
    # 先发送一个特殊的测试请求
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with websockets.connect(uri, additional_headers=headers) as ws:
        msg = ACPProtocol.build_request(
            method="test.confirm_flow",
            params={"test": True},
            msg_id="test_002",
        )
        await ws.send(ACPProtocol.encode(msg))
        print(f"发送: {ACPProtocol.encode(msg)}")

        try:
            response = await asyncio.wait_for(ws.recv(), timeout=5)
            print(f"接收: {response}")
            print("✅ 测试通过")
            return True
        except asyncio.TimeoutError:
            print("⏰ 等待超时（可能 Server 不支持此测试）")
            return False


async def test_invalid_method(uri: str, token: str = ""):
    """测试无效方法"""
    print("\n" + "=" * 60)
    print("测试 3: 发送无效方法")
    print("=" * 60)

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with websockets.connect(uri, additional_headers=headers) as ws:
        msg = ACPProtocol.build_request(
            method="invalid.method",
            params={},
            msg_id="test_003",
        )
        await ws.send(ACPProtocol.encode(msg))
        print(f"发送: {ACPProtocol.encode(msg)}")

        response = await ws.recv()
        print(f"接收: {response}")

        data = json.loads(response)
        if data.get("error") and data["error"].get("code") == -32003:
            print("✅ 测试通过 (正确返回 INVALID_PARAMS 错误)")
            return True
        else:
            print("❌ 测试失败")
            return False


async def test_ping(uri: str, token: str = ""):
    """测试 ping"""
    print("\n" + "=" * 60)
    print("测试 4: Ping 测试")
    print("=" * 60)

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with websockets.connect(uri, additional_headers=headers) as ws:
        msg = ACPProtocol.build_request(
            method=ACPMethod.PING.value,
            params={},
            msg_id="test_004",
        )
        await ws.send(ACPProtocol.encode(msg))
        print(f"发送: {ACPProtocol.encode(msg)}")

        response = await ws.recv()
        print(f"接收: {response}")

        data = json.loads(response)
        if data.get("result", {}).get("pong"):
            print("✅ 测试通过")
            return True
        else:
            print("❌ 测试失败")
            return False


async def test_auth_without_token(uri: str):
    """测试无 Token 认证"""
    print("\n" + "=" * 60)
    print("测试 5: 无 Token 认证 (预期失败)")
    print("=" * 60)

    try:
        async with websockets.connect(uri) as ws:
            msg = ACPProtocol.build_request(
                method=ACPMethod.PING.value,
                params={},
                msg_id="test_005",
            )
            await ws.send(ACPProtocol.encode(msg))
            response = await asyncio.wait_for(ws.recv(), timeout=5)
            print(f"接收: {response}")
            print("⚠️  未启用认证或认证未生效")
            return False
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"✅ 测试通过 (Server 拒绝了无效请求: status={e.status_code})")
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


async def run_all_tests():
    """运行所有测试"""
    # 从环境变量或使用默认值
    import os
    from dotenv import load_dotenv
    load_dotenv()

    host = os.getenv("ACP_HOST", "localhost")
    port = os.getenv("ACP_PORT", "8765")
    token = os.getenv("ACP_TOKEN", "")

    uri = f"ws://{host}:{port}"

    print("=" * 60)
    print("ACP 协议测试客户端")
    print("=" * 60)
    print(f"目标地址: {uri}")
    print(f"Token: {'已配置' if token else '未配置'}")

    results = []

    # 运行测试
    results.append(("Server Info", await test_server_info(uri, token)))
    results.append(("Confirm Flow", await test_confirm_request(uri, token)))
    results.append(("Invalid Method", await test_invalid_method(uri, token)))
    results.append(("Ping", await test_ping(uri, token)))
    results.append(("Auth Without Token", await test_auth_without_token(uri)))

    # 汇总
    print("\n" + "=" * 60)
    print("测试汇总")
    print("=" * 60)
    passed = sum(1 for _, r in results if r)
    total = len(results)
    for name, result in results:
        status = "✅" if result else "❌"
        print(f"  {status} {name}")
    print(f"\n通过: {passed}/{total}")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
