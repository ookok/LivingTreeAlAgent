"""
ServerMain - 四层通信协议栈整合入口
===================================

整合发现层、传输层、会话层、安全层

Author: LivingTreeAI Community
from __future__ import annotations
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
import asyncio
import logging
import signal
import sys

logger = logging.getLogger(__name__)


@dataclass
class ServerConfig:
    """服务器配置"""
    node_id: str
    host: str = "0.0.0.0"

    # 端口配置
    websocket_port: int = 8765
    tcp_port: int = 8766
    multicast_port: int = 19888

    # 中心服务器
    central_server: str = None

    # 信令服务器
    signaling_port: int = 8080

    # 功能开关
    enable_webrtc: bool = True
    enable_websocket: bool = True
    enable_tcp: bool = True
    enable_multicast: bool = True


class LifeTreeServer:
    """
    生命之树服务器主入口

    整合四层通信协议栈：
    1. 发现层 - 节点发现与寻址
    2. 传输层 - 跨平台连接建立
    3. 会话层 - MessagePack RPC
    4. 安全层 - 端到端加密
    """

    def __init__(self, config: ServerConfig = None):
        self.config = config or ServerConfig(node_id="server_node")

        # 组件
        from .discovery import NodeDiscovery, get_discovery
        from .transport import NodeConnection, NodeEndpoint, get_transport
        from .session import NodeRPCServer, get_rpc_server
        from .security import NoiseProtocol, get_security

        self.discovery = get_discovery(
            node_id=self.config.node_id,
            central_server=self.config.central_server,
        )

        self.transport = get_transport(
            node_id=self.config.node_id,
        )

        self.rpc_server = get_rpc_server(
            node_id=self.config.node_id,
        )

        self.security = get_security()

        # 任务
        self._tasks: List[asyncio.Task] = []
        self._running = False

        # 注册业务方法
        self._register_business_methods()

        logger.info(f"LifeTreeServer 初始化: node_id={self.config.node_id}")

    def _register_business_methods(self):
        """注册业务RPC方法"""

        async def search(query: str, limit: int = 10) -> Dict:
            """搜索方法"""
            return {
                "query": query,
                "results": [],
                "total": 0,
            }

        async def relay_stream(node_id: str, data: bytes) -> Dict:
            """流数据转发"""
            return {"status": "ok", "bytes": len(data)}

        async def get_peers() -> List[Dict]:
            """获取所有对等节点"""
            nodes = self.discovery.get_nodes()
            return [n.to_dict() for n in nodes]

        async def echo(message: str) -> Dict:
            """回显测试"""
            return {
                "echo": message,
                "timestamp": datetime.now().isoformat(),
                "node_id": self.config.node_id,
            }

        self.rpc_server.register_method("search", search)
        self.rpc_server.register_method("relay_stream", relay_stream)
        self.rpc_server.register_method("get_peers", get_peers)
        self.rpc_server.register_method("echo", echo)

    async def start(self):
        """启动服务器"""
        self._running = True

        logger.info("启动 LifeTreeServer...")

        # 启动发现广播
        if self.config.enable_multicast:
            self._tasks.append(
                asyncio.create_task(self.discovery.start_advertising())
            )

        # 启动传输层服务器
        if self.config.enable_websocket:
            self._tasks.append(
                asyncio.create_task(self._start_websocket_server())
            )

        if self.config.enable_tcp:
            self._tasks.append(
                asyncio.create_task(self._start_tcp_server())
            )

        # 启动信令服务器（WebRTC需要）
        if self.config.enable_webrtc:
            self._tasks.append(
                asyncio.create_task(self._start_signaling_server())
            )

        # 执行初始发现
        asyncio.create_task(self._periodic_discovery())

        logger.info(f"服务器已启动: WebSocket={self.config.websocket_port}, "
                   f"TCP={self.config.tcp_port}, Signal={self.config.signaling_port}")

        # 等待所有任务
        try:
            await asyncio.gather(*self._tasks)
        except asyncio.CancelledError:
            logger.info("服务器任务被取消")

    async def stop(self):
        """停止服务器"""
        logger.info("停止 LifeTreeServer...")
        self._running = False

        # 取消所有任务
        for task in self._tasks:
            task.cancel()

        # 停止广播
        self.discovery.stop_advertising()

        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        logger.info("服务器已停止")

    # ==================== 服务器启动 ====================

    async def _start_websocket_server(self):
        """启动WebSocket服务器"""
        try:
            import websockets
        except ImportError:
            logger.error("websockets 未安装，WebSocket服务器无法启动")
            return

        async def handler(websocket, path):
            peer_id = None

            try:
                # 获取对端信息
                remote_ip = websocket.remote_address[0]
                logger.info(f"WebSocket连接: {remote_ip}")

                async for message in websocket:
                    # 处理消息
                    response = await self.rpc_server.handle_message(message, sender_id=peer_id)

                    if response:
                        await websocket.send(response)

            except Exception as e:
                logger.error(f"WebSocket处理错误: {e}")

        server = await websockets.serve(
            handler,
            self.config.host,
            self.config.websocket_port,
        )

        logger.info(f"WebSocket服务器已启动: ws://{self.config.host}:{self.config.websocket_port}")

        # 保持服务器运行
        await asyncio.Future()

    async def _start_tcp_server(self):
        """启动TCP服务器（兜底）"""
        async def handle_connection(reader, writer):
            remote_address = writer.get_extra_info('peername')
            logger.info(f"TCP连接: {remote_address}")

            try:
                while True:
                    data = await reader.read(4096)
                    if not data:
                        break

                    # 处理消息
                    response = await self.rpc_server.handle_message(data, sender_id=remote_address[0])

                    if response:
                        writer.write(response)
                        await writer.drain()

            except Exception as e:
                logger.error(f"TCP处理错误: {e}")

            finally:
                writer.close()
                await writer.wait_closed()

        server = await asyncio.start_server(
            handle_connection,
            self.config.host,
            self.config.tcp_port,
        )

        logger.info(f"TCP服务器已启动: tcp://{self.config.host}:{self.config.tcp_port}")

        async with server:
            await server.serve_forever()

    async def _start_signaling_server(self):
        """启动WebRTC信令服务器"""
        try:
            from aiohttp import web
        except ImportError:
            logger.error("aiohttp 未安装，信令服务器无法启动")
            return

        self._signaling_data: Dict[str, Any] = {}

        async def handle_signal(request):
            """处理WebRTC信令"""
            data = await request.json()

            from_node = data.get("from_node")
            to_node = data.get("to_node")
            sdp = data.get("sdp")
            sdp_type = data.get("type")

            # 存储信令数据
            key = f"{from_node}->{to_node}"
            self._signaling_data[key] = {
                "sdp": sdp,
                "type": sdp_type,
                "timestamp": datetime.now().isoformat(),
            }

            # 检查是否有待处理的信令
            reverse_key = f"{to_node}->{from_node}"
            if reverse_key in self._signaling_data:
                answer = self._signaling_data.pop(reverse_key)
                return web.json_response(answer)

            # 返回等待状态
            return web.json_response({"status": "waiting"})

        app = web.Application()
        app.router.add_post("/signal", handle_signal)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self.config.host, self.config.signaling_port)
        await site.start()

        logger.info(f"信令服务器已启动: http://{self.config.host}:{self.config.signaling_port}")

        # 保持运行
        await asyncio.Future()

    # ==================== 定期任务 ====================

    async def _periodic_discovery(self):
        """定期执行节点发现"""
        while self._running:
            try:
                result = await self.discovery.discover(timeout=5.0)
                logger.debug(f"发现 {len(result.nodes)} 个节点")
            except Exception as e:
                logger.error(f"节点发现错误: {e}")

            await asyncio.sleep(30)  # 每30秒发现一次


class LifeTreeClient:
    """
    生命之树客户端

    简化客户端用法，自动处理连接和RPC调用
    """

    def __init__(self, node_id: str, server_address: str):
        self.node_id = node_id
        self.server_address = server_address

        from .transport import NodeConnection, NodeEndpoint, get_transport
        from .session import NodeRPCClient
        from .security import get_security

        self.transport = get_transport(node_id=node_id)
        self.security = get_security()

        # 解析服务器地址
        host, port = self._parse_address(server_address)
        self._server_endpoint = NodeEndpoint(
            node_id="server",
            ip=host,
            port=port,
            websocket_port=port,
            tcp_port=port + 1,
        )

        self._rpc_client: Optional[NodeRPCClient] = None
        self._connected = False

    def _parse_address(self, address: str) -> Tuple[str, int]:
        """解析地址"""
        if ":" in address:
            host, port_str = address.split(":", 1)
            return host, int(port_str)
        return address, 8765

    async def connect(self):
        """连接到服务器"""
        try:
            conn_info = await self.transport.connect_to(self._server_endpoint)
            self._connected = True

            # 创建RPC客户端
            async def send_func(node_id: str, data: bytes) -> int:
                return await self.transport.send(node_id, data)

            self._rpc_client = NodeRPCClient(
                node_id=self.node_id,
                send_func=send_func,
            )

            logger.info(f"已连接到服务器: {self.server_address}")

        except Exception as e:
            logger.error(f"连接失败: {e}")
            raise

    async def call(self, method: str, *params, timeout: float = 30.0) -> Any:
        """发起RPC调用"""
        if not self._connected or self._rpc_client is None:
            raise ConnectionError("未连接到服务器")

        return await self._rpc_client.call(
            target_node="server",
            method=method,
            *params,
            timeout=timeout,
        )

    async def disconnect(self):
        """断开连接"""
        await self.transport.disconnect("server")
        self._connected = False
        logger.info("已断开服务器连接")


# ==================== 便捷函数 ====================

async def start_server(node_id: str = None, config: ServerConfig = None):
    """启动服务器（便捷函数）"""
    if config is None:
        config = ServerConfig(node_id=node_id or "lifetree_server")

    server = LifeTreeServer(config)

    # 设置信号处理
    loop = asyncio.get_event_loop()

    def signal_handler():
        asyncio.create_task(server.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            # Windows不支持add_signal_handler
            pass

    await server.start()


if __name__ == "__main__":
    # 示例：启动服务器
    async def main():
        config = ServerConfig(
            node_id="lifetree_server_001",
            host="0.0.0.0",
            websocket_port=8765,
            tcp_port=8766,
        )
        await start_server(config=config)

    asyncio.run(main())