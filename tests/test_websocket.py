"""
测试 WebSocket 实时通信功能
"""

import pytest
import asyncio
from datetime import datetime

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False


@pytest.mark.skipif(not WEBSOCKETS_AVAILABLE, reason="websockets 库未安装")
class TestWebSocketServer:
    """WebSocket 服务器测试"""
    
    @pytest.mark.asyncio
    async def test_server_start_stop(self):
        """测试服务器启动和停止"""
        from client.src.infrastructure.websocket_server import WebSocketServer
        
        server = WebSocketServer(host="127.0.0.1", port=8766)
        
        # 启动服务器在后台运行
        server_task = asyncio.create_task(server.start())
        
        # 等待服务器启动
        await asyncio.sleep(1)
        
        stats = server.get_stats()
        assert stats["total_connections"] == 0
        
        # 停止服务器
        await server.stop()
        await server_task
    
    @pytest.mark.asyncio
    async def test_client_connect(self):
        """测试客户端连接"""
        from client.src.infrastructure.websocket_server import WebSocketServer
        from client.src.infrastructure.websocket_client import WebSocketClient
        
        server = WebSocketServer(host="127.0.0.1", port=8767)
        server_task = asyncio.create_task(server.start())
        
        await asyncio.sleep(1)
        
        client = WebSocketClient(server_url="ws://127.0.0.1:8767")
        connected = await client.connect(user_id="test_user")
        
        assert connected is True
        assert client.is_connected() is True
        
        await asyncio.sleep(0.5)
        
        stats = server.get_stats()
        assert stats["total_connections"] >= 1
        assert stats["authenticated_users"] >= 1
        
        await client.disconnect()
        await server.stop()
        await server_task
    
    @pytest.mark.asyncio
    async def test_sync_message(self):
        """测试同步消息（跨设备同步）- 简化版本"""
        from client.src.infrastructure.websocket_server import WebSocketServer, SyncType
        
        server = WebSocketServer(host="127.0.0.1", port=8768)
        server_task = asyncio.create_task(server.start())
        
        await asyncio.sleep(1)
        
        # 测试服务器内部同步逻辑
        # 模拟用户会话注册
        server._user_sessions["test_user"] = ["session1", "session2"]
        
        # 创建模拟会话
        class MockSession:
            def __init__(self):
                self.user_id = "test_user"
                self.authenticated = True
                self.joined_channels = []
                self.last_active = datetime.now()
        
        server._sessions["session1"] = MockSession()
        server._sessions["session2"] = MockSession()
        
        # 测试同步到其他设备
        received_data = []
        
        # 替换 _send_message 来捕获发送的数据
        original_send = server._send_message
        async def capture_send(session_id, message_type, content):
            if session_id != "session1":  # 排除发送者
                received_data.append(content)
        
        server._send_message = capture_send
        
        # 调用同步方法
        test_data = {"workspace_id": "test_workspace", "name": "Test"}
        await server._sync_to_other_devices("test_user", "session1", SyncType.WORKSPACE, test_data)
        
        # 验证同步数据已发送
        assert len(received_data) == 1
        assert received_data[0]["sync_type"] == "workspace"
        assert received_data[0]["data"] == test_data
        
        await server.stop()
        await server_task


@pytest.mark.skipif(not WEBSOCKETS_AVAILABLE, reason="websockets 库未安装")
class TestWebSocketClient:
    """WebSocket 客户端测试"""
    
    @pytest.mark.asyncio
    async def test_client_reconnect(self):
        """测试客户端自动重连"""
        from client.src.infrastructure.websocket_server import WebSocketServer
        from client.src.infrastructure.websocket_client import WebSocketClient
        
        server = WebSocketServer(host="127.0.0.1", port=8769)
        server_task = asyncio.create_task(server.start())
        
        await asyncio.sleep(1)
        
        client = WebSocketClient(server_url="ws://127.0.0.1:8769")
        await client.connect(user_id="test_user_reconnect")
        
        assert client.is_connected() is True
        
        # 停止服务器模拟断开
        await server.stop()
        await server_task
        
        await asyncio.sleep(1)
        assert client.is_connected() is False
        
        # 重启服务器
        server = WebSocketServer(host="127.0.0.1", port=8769)
        server_task = asyncio.create_task(server.start())
        
        await asyncio.sleep(6)
        
        assert client.is_connected() is True
        
        await client.disconnect()
        await server.stop()
        await server_task
    
    @pytest.mark.asyncio
    async def test_channel_message(self):
        """测试频道消息"""
        from client.src.infrastructure.websocket_server import WebSocketServer
        from client.src.infrastructure.websocket_client import WebSocketClient
        
        server = WebSocketServer(host="127.0.0.1", port=8770)
        server_task = asyncio.create_task(server.start())
        
        await asyncio.sleep(1)
        
        client1 = WebSocketClient(server_url="ws://127.0.0.1:8770")
        client2 = WebSocketClient(server_url="ws://127.0.0.1:8770")
        
        await client1.connect(user_id="user1")
        await client2.connect(user_id="user2")
        
        message_received = asyncio.Event()
        received_content = None
        
        from client.src.infrastructure.websocket_client import MessageType

        def message_handler(data):
            nonlocal received_content
            if data.get("content", {}).get("action") == "message":
                received_content = data.get("content", {}).get("content")       
                message_received.set()

        client2.on_message(MessageType.CHANNEL, message_handler)
        
        await client1.join_channel("test_channel")
        await client2.join_channel("test_channel")
        
        await asyncio.sleep(0.5)
        
        await client1.send_to_channel("test_channel", {"text": "Hello, World!"})
        
        await asyncio.wait_for(message_received.wait(), timeout=5)
        
        assert received_content == {"text": "Hello, World!"}
        
        await client1.disconnect()
        await client2.disconnect()
        await server.stop()
        await server_task


if __name__ == "__main__":
    pytest.main([__file__, "-v"])