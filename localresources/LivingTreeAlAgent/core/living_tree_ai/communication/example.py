"""
Communication Stack 使用示例
============================

演示四层通信协议栈的使用方法

Author: LivingTreeAI Community
"""

import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_discovery():
    """
    示例：节点发现
    """
    from core.living_tree_ai.communication import (
        NodeDiscovery,
        DiscoveryType,
    )

    # 创建发现器
    discovery = NodeDiscovery(
        node_id="client_001",
        central_server="http://localhost:8000",  # 可选
        multicast_port=19888,
    )

    # 执行发现
    logger.info("开始节点发现...")
    result = await discovery.discover(timeout=5.0)

    logger.info(f"发现 {len(result.nodes)} 个节点:")
    for node in result.nodes:
        logger.info(f"  - {node.node_id} @ {node.ip}:{node.port} "
                   f"({node.discovery_type.value}, {node.latency_ms:.0f}ms)")

    # 获取最优节点
    best_nodes = result.get_best_nodes(k=3)
    logger.info(f"最优3个节点: {[n.node_id for n in best_nodes]}")

    # 手动添加节点
    discovery.add_node("manual_node", "192.168.1.100", 8765)


async def example_transport():
    """
    示例：传输层连接
    """
    from core.living_tree_ai.communication import (
        NodeConnection,
        NodeEndpoint,
        ConnectionStrategy,
        TransportType,
    )

    # 创建连接管理器
    transport = NodeConnection(
        node_id="client_001",
        strategy=ConnectionStrategy.WEBRTC_FIRST,
    )

    # 创建端点
    endpoint = NodeEndpoint(
        node_id="server_001",
        ip="192.168.1.100",
        port=8765,
        websocket_port=8765,
        tcp_port=8766,
    )

    # 连接到节点
    logger.info(f"连接到 {endpoint.node_id}...")
    try:
        conn_info = await transport.connect_to(endpoint)
        logger.info(f"连接成功: {conn_info.transport_type.value}")
        logger.info(f"  连接ID: {conn_info.connection_id}")
        logger.info(f"  远程: {conn_info.remote_ip}:{conn_info.remote_port}")

        # 发送数据
        data = b"Hello, World!"
        sent = await transport.send(endpoint.node_id, data)
        logger.info(f"发送 {sent} 字节")

        # 接收数据
        response = await transport.receive(endpoint.node_id, timeout=5.0)
        if response:
            logger.info(f"收到响应: {response}")

    except ConnectionError as e:
        logger.error(f"连接失败: {e}")

    finally:
        # 断开连接
        await transport.disconnect(endpoint.node_id)


async def example_rpc():
    """
    示例：RPC调用
    """
    from core.living_tree_ai.communication import (
        NodeRPCServer,
        NodeRPCClient,
    )

    # 创建RPC服务器
    server = NodeRPCServer(node_id="server_001")

    # 注册方法
    async def add(a: int, b: int) -> int:
        return a + b

    async def get_info() -> dict:
        return {
            "node_id": server.node_id,
            "methods": ["add", "get_info"],
        }

    server.register_method("add", add)
    server.register_method("get_info", get_info)

    # 创建RPC客户端
    async def mock_send(node_id: str, data: bytes) -> int:
        # 模拟发送
        return len(data)

    client = NodeRPCClient(node_id="client_001", send_func=mock_send)

    # 模拟调用
    request = asyncio.create_task(client.call(
        target_node="server_001",
        method="add",
        10,
        20,
        timeout=5.0,
    ))

    # 服务端处理
    response = await server.handle_message(
        request.result().to_bytes() if request.done() else b"",
        sender_id="client_001",
    )

    logger.info(f"RPC调用完成")


async def example_security():
    """
    示例：端到端加密
    """
    from core.living_tree_ai.communication import (
        NoiseProtocol,
    )

    # 创建安全协议实例
    security = NoiseProtocol()

    # 获取公钥
    public_key = security.get_public_key_bytes()
    logger.info(f"我的公钥: {public_key.hex()[:32]}...")

    # 模拟与对方握手
    remote_public_key = b"\x00" * 32  # 模拟远程公钥
    session_key = security.handshake(remote_public_key)
    logger.info(f"会话密钥: {session_key.hex()[:32]}...")

    # 创建安全会话
    ctx = security.create_session("peer_001", session_key)
    logger.info(f"安全会话已创建: {ctx.peer_id}")

    # 加密消息
    plaintext = b"Hello, encrypted world!"
    ciphertext = security.encrypt_for_peer("peer_001", plaintext)
    logger.info(f"加密后: {ciphertext.hex()[:32]}...")

    # 解密消息
    decrypted = security.decrypt_from_peer("peer_001", ciphertext)
    logger.info(f"解密后: {decrypted}")


async def example_server():
    """
    示例：启动服务器
    """
    from core.living_tree_ai.communication import (
        LifeTreeServer,
        ServerConfig,
    )

    # 创建配置
    config = ServerConfig(
        node_id="lifetree_server_001",
        host="0.0.0.0",
        websocket_port=8765,
        tcp_port=8766,
        enable_webrtc=True,
        enable_websocket=True,
        enable_tcp=True,
    )

    # 创建服务器
    server = LifeTreeServer(config)

    # 启动服务器
    logger.info("启动服务器...")
    # await server.start()  # 会阻塞


async def example_client():
    """
    示例：客户端连接
    """
    from core.living_tree_ai.communication import LifeTreeClient

    # 创建客户端
    client = LifeTreeClient(
        node_id="client_001",
        server_address="localhost:8765",
    )

    # 连接到服务器
    logger.info("连接到服务器...")
    # await client.connect()

    # 发起RPC调用
    # result = await client.call("echo", "Hello, server!")
    # logger.info(f"响应: {result}")

    # 断开连接
    # await client.disconnect()


async def example_full_stack():
    """
    完整示例：整合所有层
    """
    from core.living_tree_ai.communication import (
        NodeDiscovery,
        NodeConnection,
        NodeEndpoint,
        NodeRPCServer,
        NodeRPCClient,
        NoiseProtocol,
        ConnectionStrategy,
    )

    # 1. 发现阶段
    logger.info("=== 阶段1: 节点发现 ===")
    discovery = NodeDiscovery(node_id="node_001")
    result = await discovery.discover(timeout=3.0)
    logger.info(f"发现 {len(result.nodes)} 个节点")

    # 2. 连接阶段
    logger.info("\n=== 阶段2: 建立连接 ===")
    transport = NodeConnection(
        node_id="node_001",
        strategy=ConnectionStrategy.WEBRTC_FIRST,
    )

    if result.nodes:
        target = result.nodes[0]
        endpoint = NodeEndpoint(
            node_id=target.node_id,
            ip=target.ip,
            port=target.port,
            websocket_port=target.port,
            tcp_port=target.port + 1,
        )

        try:
            conn_info = await transport.connect_to(endpoint)
            logger.info(f"连接成功: {conn_info.transport_type.value}")

            # 3. 安全握手
            logger.info("\n=== 阶段3: 安全握手 ===")
            security = NoiseProtocol()
            session_key = security.handshake(target.node_id.encode())
            security.create_session(target.node_id, session_key)
            logger.info("安全会话已建立")

            # 4. RPC调用
            logger.info("\n=== 阶段4: RPC调用 ===")
            async def send_func(node_id: str, data: bytes) -> int:
                return await transport.send(node_id, data)

            rpc_client = NodeRPCClient(node_id="node_001", send_func=send_func)
            # result = await rpc_client.call(target.node_id, "ping", timeout=5.0)
            logger.info("RPC调用完成")

            # 5. 断开连接
            await transport.disconnect(target.node_id)
            logger.info("\n=== 连接已关闭 ===")

        except Exception as e:
            logger.error(f"连接失败: {e}")


if __name__ == "__main__":
    # 运行示例
    print("1. 节点发现示例")
    asyncio.run(example_discovery())

    print("\n2. 完整协议栈示例")
    asyncio.run(example_full_stack())