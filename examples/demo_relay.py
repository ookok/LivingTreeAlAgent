#!/usr/bin/env python
"""
WebSocket 中继系统演示
WebSocket Relay System Demo

演示内容：
1. 启动中继服务器
2. 连接多个客户端
3. 创建/加入会话
4. 消息收发
5. 心跳与重连

使用方法：
1. 终端1：python -m examples.demo_relay --mode server
2. 终端2：python -m examples.demo_relay --mode desktop
3. 终端3：python -m examples.demo_relay --mode mobile
"""

import os
import sys
import time
import asyncio
import argparse
import logging

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.relay_server import RelayServer, RelayProtocol, MessageType
from core.relay_client import AsyncRelayClient, SyncRelayClient, ClientType, ConnectionState

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class RelayDemo:
    """中继系统演示"""
    
    def __init__(self, mode: str = "server"):
        self.mode = mode
        self.server = None
        self.clients = []
    
    async def run_server(self):
        """运行服务器"""
        logger.info("=" * 50)
        logger.info("启动 WebSocket 中继服务器")
        logger.info("=" * 50)
        
        self.server = RelayServer(
            host="0.0.0.0",
            port=8765,
            max_connections=1000
        )
        
        # 设置回调
        self.server.on_client_connected = self._on_server_client_connected
        self.server.on_client_disconnected = self._on_server_client_disconnected
        self.server.on_message_received = self._on_server_message
        self.server.on_session_created = self._on_server_session_created
        
        # 启动服务器
        await self.server.start()
        
        logger.info(f"服务器已启动: ws://0.0.0.0:8765")
        logger.info("按 Ctrl+C 停止服务器")
        
        # 保持运行
        try:
            while True:
                await asyncio.sleep(1)
                # 显示统计信息
                stats = self.server.get_stats()
                if stats["total_messages"] > 0:
                    print(f"\r在线客户端: {stats['online_clients']} | 会话数: {stats['active_sessions']} | 消息数: {stats['total_messages']}", end="", flush=True)
        except KeyboardInterrupt:
            logger.info("\n正在停止服务器...")
        finally:
            await self.server.stop()
            logger.info("服务器已停止")
    
    async def _on_server_client_connected(self, client):
        """客户端连接回调"""
        logger.info(f"[服务器] 客户端连接: {client.name} ({client.id})")
    
    async def _on_server_client_disconnected(self, client):
        """客户端断开回调"""
        logger.info(f"[服务器] 客户端断开: {client.name} ({client.id})")
    
    async def _on_server_message(self, client, message):
        """消息接收回调"""
        logger.info(f"[服务器] 收到 {client.name} 的消息: {message.get('type')}")
    
    async def _on_server_session_created(self, session):
        """会话创建回调"""
        logger.info(f"[服务器] 会话创建: {session.id} by {session.host_id}")
    
    async def run_desktop_client(self, user_name: str = "Desktop User"):
        """运行桌面客户端"""
        logger.info("=" * 50)
        logger.info(f"启动桌面客户端: {user_name}")
        logger.info("=" * 50)
        
        client = AsyncRelayClient(
            server_url="ws://localhost:8765",
            client_name=user_name,
            client_type=ClientType.DESKTOP
        )
        
        # 设置回调
        client.on_connected = self._on_client_connected
        client.on_disconnected = self._on_client_disconnected
        client.on_message = self._on_client_message
        client.on_session_created = self._on_client_session_created
        client.on_session_joined = self._on_client_session_joined
        client.on_error = self._on_client_error
        
        self.clients.append(client)
        
        try:
            # 连接
            await client.connect()
            
            # 等待认证
            while client.state != ConnectionState.AUTHENTICATED:
                await asyncio.sleep(0.1)
            
            logger.info(f"连接成功! 客户端ID: {client.client_id}")
            
            # 创建会话
            logger.info("创建会话...")
            await client.create_session(name="测试会话", max_clients=10)
            
            # 等待会话创建
            await asyncio.sleep(1)
            
            # 发送消息
            for i in range(3):
                message = f"桌面端消息 #{i + 1}"
                logger.info(f"发送: {message}")
                await client.broadcast({"text": message, "from": user_name})
                await asyncio.sleep(2)
            
            # 保持连接
            logger.info("会话中...")
            for _ in range(10):
                await asyncio.sleep(1)
            
        except KeyboardInterrupt:
            logger.info("\n正在断开连接...")
        finally:
            await client.disconnect()
            logger.info("客户端已断开")
    
    async def run_mobile_client(self, user_name: str = "Mobile User"):
        """运行移动端客户端"""
        logger.info("=" * 50)
        logger.info(f"启动移动端客户端: {user_name}")
        logger.info("=" * 50)
        
        client = AsyncRelayClient(
            server_url="ws://localhost:8765",
            client_name=user_name,
            client_type=ClientType.MOBILE
        )
        
        # 设置回调
        client.on_connected = self._on_client_connected
        client.on_disconnected = self._on_client_disconnected
        client.on_message = self._on_client_message
        client.on_session_created = self._on_client_session_created
        client.on_session_joined = self._on_client_session_joined
        client.on_error = self._on_client_error
        
        self.clients.append(client)
        
        try:
            # 连接
            await client.connect()
            
            # 等待认证
            while client.state != ConnectionState.AUTHENTICATED:
                await asyncio.sleep(0.1)
            
            logger.info(f"连接成功! 客户端ID: {client.client_id}")
            
            # 等待会话ID输入
            logger.info("等待加入会话（5秒后自动加入）...")
            await asyncio.sleep(5)
            
            # 加入会话（如果有的话）
            if self.clients and len(self.clients) > 1:
                # 找到桌面客户端创建的会话
                for _ in range(3):
                    if client.current_session:
                        break
                    await asyncio.sleep(1)
            
            # 发送消息
            for i in range(2):
                message = f"移动端消息 #{i + 1}"
                logger.info(f"发送: {message}")
                await client.broadcast({"text": message, "from": user_name})
                await asyncio.sleep(3)
            
        except KeyboardInterrupt:
            logger.info("\n正在断开连接...")
        finally:
            await client.disconnect()
            logger.info("客户端已断开")
    
    async def _on_client_connected(self, data: dict):
        """连接成功回调"""
        logger.info(f"[客户端] 连接成功: {data}")
    
    async def _on_client_disconnected(self):
        """断开连接回调"""
        logger.info("[客户端] 连接已断开")
    
    async def _on_client_message(self, data: dict):
        """消息接收回调"""
        sender = data.get("from_name", data.get("from", "Unknown"))
        text = data.get("text", "")
        logger.info(f"[客户端] 收到 {sender} 的消息: {text}")
    
    async def _on_client_session_created(self, data: dict):
        """会话创建回调"""
        session_id = data.get("session_id")
        logger.info(f"[客户端] 会话已创建: {session_id}")
    
    async def _on_client_session_joined(self, data: dict):
        """加入会话回调"""
        session_id = data.get("session_id")
        logger.info(f"[客户端] 已加入会话: {session_id}")
    
    async def _on_client_error(self, data: dict):
        """错误回调"""
        logger.error(f"[客户端] 错误: {data}")


async def run_multi_client_demo():
    """多客户端演示"""
    logger.info("=" * 50)
    logger.info("多客户端演示")
    logger.info("=" * 50)
    
    # 启动服务器
    server = RelayServer(host="0.0.0.0", port=8765)
    await server.start()
    logger.info("服务器已启动")
    
    # 创建客户端任务
    desktop = AsyncRelayClient(
        server_url="ws://localhost:8765",
        client_name="桌面端",
        client_type=ClientType.DESKTOP
    )
    
    mobile1 = AsyncRelayClient(
        server_url="ws://localhost:8765",
        client_name="移动端1",
        client_type=ClientType.MOBILE
    )
    
    mobile2 = AsyncRelayClient(
        server_url="ws://localhost:8765",
        client_name="移动端2",
        client_type=ClientType.MOBILE
    )
    
    # 连接所有客户端
    await desktop.connect()
    logger.info("桌面端已连接")
    
    await mobile1.connect()
    logger.info("移动端1已连接")
    
    await mobile2.connect()
    logger.info("移动端2已连接")
    
    # 桌面端创建会话
    await desktop.create_session(name="多客户端测试", max_clients=10)
    await asyncio.sleep(1)
    
    # 移动端加入会话
    session_id = desktop.current_session
    if session_id:
        logger.info(f"会话ID: {session_id}")
        
        await mobile1.join_session(session_id)
        await mobile2.join_session(session_id)
        await asyncio.sleep(1)
        
        # 广播消息测试
        logger.info("\n--- 广播测试 ---")
        await desktop.broadcast({"text": "大家好！我是桌面端", "from": "桌面端"})
        await asyncio.sleep(1)
        
        await mobile1.broadcast({"text": "我是移动端1", "from": "移动端1"})
        await asyncio.sleep(1)
        
        await mobile2.broadcast({"text": "我是移动端2", "from": "移动端2"})
        
        # 等待消息传播
        await asyncio.sleep(3)
        
        # 显示统计
        stats = server.get_stats()
        logger.info(f"\n--- 服务器统计 ---")
        logger.info(f"在线客户端: {stats['online_clients']}")
        logger.info(f"活动会话: {stats['active_sessions']}")
        logger.info(f"总消息数: {stats['total_messages']}")
    
    # 清理
    logger.info("\n--- 清理 ---")
    await desktop.disconnect()
    await mobile1.disconnect()
    await mobile2.disconnect()
    await server.stop()
    logger.info("演示完成！")


def main():
    """主入口"""
    parser = argparse.ArgumentParser(description="WebSocket 中继系统演示")
    parser.add_argument(
        "--mode", "-m",
        choices=["server", "desktop", "mobile", "multi"],
        default="server",
        help="运行模式"
    )
    parser.add_argument(
        "--name", "-n",
        default="",
        help="客户端名称"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8765,
        help="服务器端口"
    )
    
    args = parser.parse_args()
    
    demo = RelayDemo(mode=args.mode)
    
    if args.mode == "server":
        asyncio.run(demo.run_server())
    
    elif args.mode == "desktop":
        name = args.name or "桌面用户"
        asyncio.run(demo.run_desktop_client(name))
    
    elif args.mode == "mobile":
        name = args.name or "移动用户"
        asyncio.run(demo.run_mobile_client(name))
    
    elif args.mode == "multi":
        asyncio.run(run_multi_client_demo())


if __name__ == "__main__":
    main()
