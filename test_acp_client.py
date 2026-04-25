"""
ACP 协议测试客户端
测试 Standard ACP 兼容性和扩展方法
"""
import asyncio
import json
import sys

import websockets

sys.path.insert(0, ".")

from core.acp.protocol import ACPProtocol
from core.acp.types import ACPMethod


def create_ws_headers(token: str) -> dict:
    """创建 WebSocket headers（兼容不同版本 websockets）"""
    if not token:
        return {}
    # websockets 12.0+ uses additional_headers, 10.x uses extra_headers
    try:
        import websockets
        version = getattr(websockets, 'version', '0.0.0')
        major = int(version.split('.')[0]) if version else 0
        if major >= 12:
            return {"additional_headers": {"Authorization": f"Bearer {token}"}}
        else:
            return {"extra_headers": {"Authorization": f"Bearer {token}"}}
    except:
        return {"extra_headers": {"Authorization": f"Bearer {token}"}}


async def ws_connect(uri: str, token: str = ""):
    """创建 WebSocket 连接（兼容不同版本）"""
    headers = create_ws_headers(token)
    return await websockets.connect(uri, **headers)


async def test_initialize(uri: str, token: str = ""):
    """测试 initialize (Standard ACP)"""
    print("\n" + "=" * 60)
    print("测试 1: initialize (Standard ACP)")
    print("=" * 60)

    ws = await ws_connect(uri, token)
    async with ws:
        msg = ACPProtocol.build_initialize(
            protocol_version="1.0",
            capabilities={
                "fs": {"readTextFile": True, "writeTextFile": True},
                "terminal": True,
            },
            client_info={"name": "test-client", "version": "1.0.0"},
            msg_id="init_001",
        )
        await ws.send(ACPProtocol.encode(msg))
        print(f"发送: {ACPProtocol.encode(msg)}")

        response = await ws.recv()
        print(f"接收: {response}")

        data = json.loads(response)
        if data.get("result", {}).get("protocolVersion"):
            print("✅ initialize 成功")
            return True
        else:
            print("❌ initialize 失败")
            return False


async def test_new_session(uri: str, token: str = ""):
    """测试 newSession (Standard ACP)"""
    print("\n" + "=" * 60)
    print("测试 2: newSession (Standard ACP)")
    print("=" * 60)

    ws = await ws_connect(uri, token)
    async with ws:
        msg = ACPProtocol.build_new_session(
            session_id=None,
            cwd="/test/workspace",
            msg_id="sess_001",
        )
        await ws.send(ACPProtocol.encode(msg))
        print(f"发送: {ACPProtocol.encode(msg)}")

        response = await ws.recv()
        print(f"接收: {response}")

        data = json.loads(response)
        if data.get("result", {}).get("sessionId"):
            print(f"✅ newSession 成功, sessionId: {data['result']['sessionId']}")
            return data["result"]["sessionId"]
        else:
            print("❌ newSession 失败")
            return None


async def test_prompt(uri: str, token: str = ""):
    """测试 prompt (Standard ACP)"""
    print("\n" + "=" * 60)
    print("测试 3: prompt (Standard ACP)")
    print("=" * 60)

    ws = await ws_connect(uri, token)
    async with ws:
        msg = ACPProtocol.build_prompt(
            prompt="Hello, this is a test prompt",
            system_prompt="You are a test agent",
            msg_id="prompt_001",
        )
        await ws.send(ACPProtocol.encode(msg))
        print(f"发送: {ACPProtocol.encode(msg)}")

        response = await ws.recv()
        print(f"接收: {response}")

        data = json.loads(response)
        if data.get("result", {}).get("message"):
            print("✅ prompt 成功")
            return True
        else:
            print("❌ prompt 失败")
            return False


async def test_ping(uri: str, token: str = ""):
    """测试 ping (扩展方法)"""
    print("\n" + "=" * 60)
    print("测试 4: ping (扩展方法)")
    print("=" * 60)

    ws = await ws_connect(uri, token)
    async with ws:
        msg = ACPProtocol.build_request(
            method=ACPMethod.PING.value,
            params={},
            msg_id="ping_001",
        )
        await ws.send(ACPProtocol.encode(msg))
        print(f"发送: {ACPProtocol.encode(msg)}")

        response = await ws.recv()
        print(f"接收: {response}")

        data = json.loads(response)
        if data.get("result", {}).get("pong"):
            print("✅ ping 成功")
            return True
        else:
            print("❌ ping 失败")
            return False


async def test_execute(uri: str, token: str = ""):
    """测试 agent.execute (扩展方法)"""
    print("\n" + "=" * 60)
    print("测试 5: agent.execute (扩展方法)")
    print("=" * 60)

    ws = await ws_connect(uri, token)
    async with ws:
        msg = ACPProtocol.build_execute(
            action="server.info",
            params={},
            msg_id="exec_001",
        )
        await ws.send(ACPProtocol.encode(msg))
        print(f"发送: {ACPProtocol.encode(msg)}")

        response = await ws.recv()
        print(f"接收: {response}")

        data = json.loads(response)
        if data.get("result", {}).get("name"):
            print("✅ agent.execute 成功")
            return True
        else:
            print("❌ agent.execute 失败")
            return False


async def test_invalid_method(uri: str, token: str = ""):
    """测试无效方法"""
    print("\n" + "=" * 60)
    print("测试 6: 无效方法")
    print("=" * 60)

    ws = await ws_connect(uri, token)
    async with ws:
        msg = ACPProtocol.build_request(
            method="invalid.method",
            params={},
            msg_id="invalid_001",
        )
        await ws.send(ACPProtocol.encode(msg))
        print(f"发送: {ACPProtocol.encode(msg)}")

        response = await ws.recv()
        print(f"接收: {response}")

        data = json.loads(response)
        if data.get("error", {}).get("code") == -32003:
            print("✅ 正确返回 INVALID_PARAMS 错误")
            return True
        else:
            print("❌ 错误处理失败")
            return False


async def run_all_tests():
    """运行所有测试"""
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
    print(f"websockets 版本: {websockets.version}")

    results = []

    # Standard ACP 测试
    results.append(("initialize", await test_initialize(uri, token)))
    results.append(("newSession", await test_new_session(uri, token)))
    results.append(("prompt", await test_prompt(uri, token)))
    results.append(("ping", await test_ping(uri, token)))
    results.append(("agent.execute", await test_execute(uri, token)))
    results.append(("invalid method", await test_invalid_method(uri, token)))

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
