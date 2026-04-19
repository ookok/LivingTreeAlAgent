#!/usr/bin/env python3
"""
测试分布式功能
- 消息队列
- P2P模块
- 分布式IM
- 文件传输
"""

import asyncio
import time
import tempfile
import os
from core.p2p_knowledge.p2p_node import P2PNode, create_node
from core.unified_chat.chat_hub import get_chat_hub
from core.unified_chat.models import UnifiedMessage, MessageType, MessageStatus
from core.p2p_connector.multi_channel_manager import MultiChannelManager

async def test_p2p_module():
    """测试P2P模块"""
    print("=== 测试P2P模块 ===")
    
    try:
        # 创建两个P2P节点
        node1 = await create_node(node_id="node1", user_id="user1")
        node2 = await create_node(node_id="node2", user_id="user2")
        
        print(f"Node1: {node1.get_stats()}")
        print(f"Node2: {node2.get_stats()}")
        
        # 测试节点连接
        local_ip = node1._get_local_ip()
        print(f"Local IP: {local_ip}")
        
        # 连接测试
        from core.p2p_knowledge.models import NetworkAddress
        addr = NetworkAddress(ip=local_ip, port=node2.udp_port)
        success = await node1.connect_to_peer(addr)
        print(f"Node1 connect to Node2: {success}")
        
        # 测试消息发送
        from core.p2p_knowledge.models import Message
        msg = Message(
            msg_type="test",
            source_id=node1.node_id,
            payload={"test": "Hello P2P!"}
        )
        
        # 模拟消息处理
        def test_handler(message, addr):
            print(f"Received message: {message.msg_type} from {addr}")
            print(f"Payload: {message.payload}")
        
        node2.protocol.register_handler("test", test_handler)
        
        # 发送测试消息
        success = await node1.protocol.send_message(
            (local_ip, node2.udp_port),
            msg
        )
        print(f"Send test message: {success}")
        
        # 等待消息处理
        await asyncio.sleep(2)
        
        # 停止节点
        await node1.stop()
        await node2.stop()
        
        print("P2P模块测试完成")
        return True
    except Exception as e:
        print(f"P2P模块测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_chat_hub():
    """测试分布式IM功能"""
    print("\n=== 测试分布式IM功能 ===")
    
    try:
        # 获取ChatHub实例
        chat_hub = get_chat_hub()
        chat_hub.ensure_initialized()
        
        # 设置身份
        chat_hub.set_my_identity(
            node_id="test_node_123",
            short_id="tn123",
            name="Test User"
        )
        
        # 创建会话
        session = chat_hub.get_or_create_session(
            peer_id="peer_node_456",
            peer_name="Peer User"
        )
        print(f"Created session: {session.session_id}")
        
        # 测试发送文本消息
        text_msg = await chat_hub.send_text_message(
            session_id=session.session_id,
            text="Hello from test!"
        )
        print(f"Sent text message: {text_msg.msg_id}")
        
        # 测试发送文件消息
        # 创建测试文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Test file content for file transfer test")
            test_file = f.name
        
        try:
            file_msg = await chat_hub.send_file_message(
                session_id=session.session_id,
                file_path=test_file,
                file_name="test_file.txt",
                file_size=os.path.getsize(test_file)
            )
            print(f"Sent file message: {file_msg.msg_id}")
            
            # 等待文件传输模拟
            await asyncio.sleep(3)
        finally:
            if os.path.exists(test_file):
                os.unlink(test_file)
        
        # 获取所有会话
        sessions = chat_hub.get_all_sessions()
        print(f"Total sessions: {len(sessions)}")
        
        # 测试搜索功能
        search_results = chat_hub.search_messages("Hello")
        print(f"Search results: {len(search_results)}")
        
        print("分布式IM功能测试完成")
        return True
    except Exception as e:
        print(f"分布式IM功能测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_file_transfer():
    """测试文件传输功能"""
    print("\n=== 测试文件传输功能 ===")
    
    try:
        chat_hub = get_chat_hub()
        
        # 创建测试文件
        test_content = """\nThis is a test file for file transfer testing.\nIt contains multiple lines of text to simulate a real file.\nFile transfer should work seamlessly in the distributed system.\n"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(test_content)
            test_file = f.name
        
        try:
            # 创建会话
            session = chat_hub.get_or_create_session(
                peer_id="file_transfer_test",
                peer_name="File Transfer Test"
            )
            
            # 发送文件
            print(f"Sending file: {test_file}")
            print(f"File size: {os.path.getsize(test_file)} bytes")
            
            file_msg = await chat_hub.send_file_message(
                session_id=session.session_id,
                file_path=test_file,
                file_name="test_transfer.txt",
                file_size=os.path.getsize(test_file)
            )
            
            print(f"File message created: {file_msg.msg_id}")
            print(f"Message type: {file_msg.type}")
            
            # 等待传输完成
            print("Waiting for file transfer to complete...")
            await asyncio.sleep(5)
            
            # 检查传输状态
            status_info = chat_hub.get_status_info()
            print(f"Status info: {status_info}")
            
        finally:
            if os.path.exists(test_file):
                os.unlink(test_file)
        
        print("文件传输功能测试完成")
        return True
    except Exception as e:
        print(f"文件传输功能测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_message_queue():
    """测试消息队列功能"""
    print("\n=== 测试消息队列功能 ===")
    
    try:
        # 检查是否有消息队列实现
        if os.path.exists("core/message_queue"):
            print("消息队列模块存在")
            # 这里可以添加具体的消息队列测试
        else:
            print("消息队列模块尚未实现，使用内置消息处理")
        
        # 测试ChatHub的消息处理
        chat_hub = get_chat_hub()
        
        # 创建测试消息
        test_messages = [
            "Hello, how are you?",
            "What's the weather today?",
            "Can you help me with a task?",
            "Let's test message queue performance"
        ]
        
        session = chat_hub.get_or_create_session(
            peer_id="mq_test",
            peer_name="Message Queue Test"
        )
        
        print(f"Sending {len(test_messages)} test messages...")
        for i, msg_text in enumerate(test_messages, 1):
            msg = await chat_hub.send_text_message(
                session_id=session.session_id,
                text=msg_text
            )
            print(f"Sent message {i}: {msg.msg_id}")
            await asyncio.sleep(0.5)
        
        # 测试消息搜索
        search_results = chat_hub.search_messages("test")
        print(f"Found {len(search_results)} messages containing 'test'")
        
        print("消息队列功能测试完成")
        return True
    except Exception as e:
        print(f"消息队列功能测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """主测试函数"""
    print("开始测试分布式功能...")
    
    results = []
    
    # 测试消息队列
    results.append(await test_message_queue())
    
    # 测试P2P模块
    results.append(await test_p2p_module())
    
    # 测试分布式IM
    results.append(await test_chat_hub())
    
    # 测试文件传输
    results.append(await test_file_transfer())
    
    # 总结
    print("\n=== 测试总结 ===")
    tests = ["消息队列", "P2P模块", "分布式IM", "文件传输"]
    for test, result in zip(tests, results):
        status = "✓ 成功" if result else "✗ 失败"
        print(f"{test}: {status}")
    
    if all(results):
        print("\n🎉 所有测试通过！")
    else:
        print("\n⚠️ 部分测试失败，需要进一步完善")

if __name__ == "__main__":
    asyncio.run(main())
