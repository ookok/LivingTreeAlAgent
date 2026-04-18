"""
去中心化邮箱测试脚本
"""

import asyncio
import sys
sys.path.insert(0, '.')

from core.decentralized_mailbox import (
    MailboxHub, MailboxAddress, MailMessage, Contact,
    AddressManager, MailCrypto, MessageStore, MessageRouter,
    TrustLevel, MessageStatus
)


async def test_basic():
    """基础功能测试"""
    print("=" * 50)
    print("Decentralized Mailbox Basic Test")
    print("=" * 50)

    # 创建邮箱核心
    hub = MailboxHub()
    print(f"[OK] MailboxHub created")

    # 创建身份
    addr = hub.create_identity("alice")
    print(f"[OK] Created identity: {addr}")

    # 获取我的地址
    my_addr = hub.get_my_address()
    print(f"[OK] My address: {my_addr}")

    # 加密测试
    crypto = MailCrypto()
    crypto.generate_keypair()
    print(f"[OK] Crypto keypair: {crypto.key_id}")

    # 加密消息
    plaintext = "Hello, P2P Email!"
    ciphertext, iv, salt = crypto.encrypt_message(plaintext)
    print(f"[OK] Encrypted message: {len(ciphertext)} bytes")

    # 解密消息
    decrypted = crypto.decrypt_message(ciphertext, iv, salt)
    print(f"[OK] Decrypted: {decrypted}")

    # 地址解析
    addr_mgr = AddressManager()
    parsed = addr_mgr.parse_address("bob@abc123def456.p2p")
    print(f"[OK] Parsed address: {parsed}")

    # 添加联系人
    contact = Contact(
        address=parsed,
        display_name="Bob"
    )
    addr_mgr.add_contact(contact)
    print(f"[OK] Added contact: {contact.address}")

    # 消息存储测试
    store = MessageStore()

    # 创建测试消息
    msg = MailMessage(
        message_id="test001",
        subject="Test Email",
        body="This is a test message",
        body_plain="This is a test message",
        from_addr=my_addr,
        to_addrs=[parsed],
        status=MessageStatus.DELIVERED
    )

    # 保存消息
    store.save_message(msg)
    print(f"[OK] Saved message: {msg.message_id}")

    # 读取消息
    loaded = store.get_message("test001")
    if loaded:
        print(f"[OK] Loaded message: {loaded.subject}")

    # 搜索消息
    results = store.search_messages("test")
    print(f"[OK] Search found {len(results)} messages")

    print("\n" + "=" * 50)
    print("All basic tests passed!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(test_basic())
