"""
内部邮件系统示例

展示 P2P 内部邮件的完整使用流程
"""

import asyncio
from business.living_tree_ai.internal_mail import (
    # 身份
    NodeIdentity,
    create_node_identity,
    # 邮件
    MailMessage,
    MailManager,
    create_mail_manager,
    # 附件
    Attachment,
    AttachmentStatus,
    DHTAttachmentStore,
    # AI 增强
    MailAIEnhancer,
    # 传输
    MailTransport,
    # 路由
    MessageRouter,
    # 加密
    E2EEncryption,
    # 会话
    MailSession,
)


async def example_basic_mail():
    """
    示例1: 基础邮件发送
    """
    print("=" * 60)
    print("示例1: 基础邮件发送")
    print("=" * 60)

    # 1. 创建节点身份
    alice = create_node_identity("alice", "laptop-001", "Alice")
    print(f"✓ Alice 身份创建: {alice.node_id}")

    # 2. 创建邮件管理器
    alice_mail = create_mail_manager(alice)
    print(f"✓ Alice 邮件管理器创建")

    # 3. 发送邮件
    mail = await alice_mail.send_mail(
        to_nodes=["bob@desktop-001"],
        subject="项目进度更新",
        body="""
        Hi Bob,

        今天的同步任务完成了，以下是进度：

        1. ✅ 用户认证模块 - 已完成
        2. ✅ 数据库迁移 - 已完成
        3. 🔄 API 对接 - 进行中

        预计明天完成剩余部分。

        Best,
        Alice
        """,
        priority=7,
        tags=["工作", "项目进度"]
    )

    print(f"\n✓ 邮件发送成功!")
    print(f"  - 邮件ID: {mail.mail_id}")
    print(f"  - 收件人: {mail.to_nodes}")
    print(f"  - 主题: {mail.subject}")
    print(f"  - AI摘要: {mail.ai_summary}")

    return mail


async def example_reply_mail():
    """
    示例2: 回复邮件
    """
    print("\n" + "=" * 60)
    print("示例2: 回复邮件")
    print("=" * 60)

    # 创建 Bob 的身份和邮件管理器
    bob = create_node_identity("bob", "desktop-001", "Bob")
    bob_mail = create_mail_manager(bob)

    # Bob 收到 Alice 的邮件 (模拟)
    alice_mail = MailMessage(
        mail_id="orig-123",
        from_node="alice@laptop-001",
        to_nodes=["bob@desktop-001"],
        subject="项目进度更新",
        body="今天的同步任务完成了..."
    )

    # Bob 回复
    reply = await bob_mail.reply_to(
        alice_mail,
        """
        Hi Alice,

        收到！进度很顺利。

        关于 API 对接，我这边已经准备好了测试环境，
        等你完成后直接对接就行。

        有问题随时 @ 我。

        Best,
        Bob
        """
    )

    print(f"✓ 回复发送成功!")
    print(f"  - 原邮件: {alice_mail.subject}")
    print(f"  - 回复主题: {reply.subject}")
    print(f"  - 引用: {reply.references}")

    return reply


async def example_attachment():
    """
    示例3: 附件处理 (DHT)
    """
    print("\n" + "=" * 60)
    print("示例3: 附件处理 (DHT)")
    print("=" * 60)

    # 创建 DHT 存储
    dht_store = DHTAttachmentStore()

    # 模拟文件数据
    file_data = b"""
    # 项目文档

    ## 概述
    这是一个示例项目文档。

    ## 功能
    1. 用户认证
    2. 数据管理
    3. API 接口
    """

    # 上传附件
    attachment = await dht_store.store_attachment(
        file_data,
        "项目文档.md"
    )

    print(f"✓ 附件上传成功!")
    print(f"  - 文件ID: {attachment.file_id}")
    print(f"  - 文件名: {attachment.file_name}")
    print(f"  - SHA256: {attachment.hash_sha256[:16]}...")
    print(f"  - 大小: {attachment.file_size} bytes")
    print(f"  - 类型: {attachment.mime_type}")

    # 检索附件
    retrieved = await dht_store.retrieve_attachment(attachment.hash_sha256)
    print(f"\n✓ 附件检索成功: {len(retrieved)} bytes")

    return attachment


async def example_ai_enhancement():
    """
    示例4: AI 增强功能
    """
    print("\n" + "=" * 60)
    print("示例4: AI 增强功能")
    print("=" * 60)

    # 创建 AI 增强器
    ai = MailAIEnhancer()

    # 模拟邮件
    bug_mail = MailMessage(
        mail_id="bug-001",
        from_node="dev@server",
        to_nodes=["alice@laptop-001"],
        subject="Bug 报告: 用户登录失败",
        body="""
        发现一个 Bug:

        用户 "test_user" 尝试登录时返回 500 错误。

        堆栈信息:
        ```
        Traceback (most recent call last):
          File "auth.py", line 42, in login
            token = jwt.encode(...)
        AttributeError: 'NoneType' object has no attribute 'encode'
        ```

        请尽快修复！

        @alice 请确认这个问题。
        """
    )

    # 分析上下文
    context = await ai.analyze_context(bug_mail, {})
    print(f"\n✓ AI 上下文分析:")
    print(f"  - 意图识别: {context['intent']}")
    print(f"  - 建议操作: {context['suggested_actions']}")
    print(f"  - @提及: {context['mentioned_users']}")

    # 自动生成标签
    tags = await ai.auto_tag(bug_mail)
    print(f"\n✓ AI 自动标签: {tags}")

    # 生成回复建议
    suggestion = await ai.generate_reply_suggestion(bug_mail)
    print(f"\n✓ 回复建议: {suggestion}")

    # 生成摘要
    summary = await ai.summarize(bug_mail)
    print(f"\n✓ AI 摘要: {summary[:50]}...")

    return context


async def example_encrypted_mail():
    """
    示例5: 端到端加密
    """
    print("\n" + "=" * 60)
    print("示例5: 端到端加密")
    print("=" * 60)

    # 创建加密器
    e2e = E2EEncryption()

    # 生成密钥对
    alice_pubkey = e2e.generate_keypair()
    print(f"✓ Alice 密钥对生成")

    # 加密消息
    secret_message = "这是机密信息，仅限指定收件人查看。"
    encrypted = e2e.encrypt(secret_message, alice_pubkey)
    print(f"✓ 消息加密: {encrypted[:30]}...")

    # 解密消息
    decrypted = e2e.decrypt(encrypted, alice_pubkey)
    print(f"✓ 消息解密: {decrypted}")

    return True


async def example_message_router():
    """
    示例6: 消息路由 (中心节点)
    """
    print("\n" + "=" * 60)
    print("示例6: 消息路由")
    print("=" * 60)

    # 创建路由器
    router = MessageRouter()

    # 注册节点
    alice = create_node_identity("alice", "laptop-001", "Alice")
    alice.metadata = {"host": "192.168.1.100", "port": 8080}

    bob = create_node_identity("bob", "desktop-001", "Bob")
    bob.metadata = {"host": "192.168.1.101", "port": 8080}

    router.register_node(alice)
    router.register_node(bob)

    print(f"✓ 节点注册完成")
    print(f"  - 在线节点: {router.broadcast_presence()}")

    # 解析节点
    alice_info = router.resolve_node("alice@laptop-001")
    print(f"\n✓ 节点解析: {alice_info.display_name}")
    print(f"  - 在线状态: {alice_info.is_online}")

    # 查找路由
    route = router.find_node_route("alice@laptop-001")
    print(f"  - 路由地址: {route}")

    return router


async def example_forward_mail():
    """
    示例7: 转发邮件
    """
    print("\n" + "=" * 60)
    print("示例7: 转发邮件")
    print("=" * 60)

    # 创建 Charlie 的邮件管理器
    charlie = create_node_identity("charlie", "phone-001", "Charlie")
    charlie_mail = create_mail_manager(charlie)

    # 模拟收到 Alice 的邮件
    alice_mail = MailMessage(
        mail_id="orig-alice-001",
        from_node="alice@laptop-001",
        to_nodes=["bob@desktop-001"],
        subject="项目进度更新",
        body="今天的同步任务完成了..."
    )

    # Bob 转发给 Charlie
    forward = await charlie_mail.forward(alice_mail, ["charlie@phone-001"])

    print(f"✓ 邮件转发成功!")
    print(f"  - 原邮件: {alice_mail.subject}")
    print(f"  - 转发主题: {forward.subject}")
    print(f"  - 标签: {forward.tags}")

    return forward


async def example_mail_session():
    """
    示例8: 邮件会话
    """
    print("\n" + "=" * 60)
    print("示例8: 邮件会话管理")
    print("=" * 60)

    # 创建会话
    session = MailSession(
        session_id="session-001",
        root_mail_id="root-mail-001"
    )

    # 添加参与者
    session.add_participant("alice@laptop-001")
    session.add_participant("bob@desktop-001")
    session.add_participant("charlie@phone-001")

    # 添加回复
    session.add_reply("reply-001")
    session.add_reply("reply-002")
    session.add_reply("reply-003")

    print(f"✓ 会话创建成功!")
    print(f"  - 会话ID: {session.session_id}")
    print(f"  - 参与者: {session.participants}")
    print(f"  - 邮件数: {len(session.mail_ids)}")
    print(f"  - 创建时间: {session.created_at}")

    return session


async def example_concurrent_mail():
    """
    示例9: 并发邮件发送
    """
    print("\n" + "=" * 60)
    print("示例9: 并发邮件发送")
    print("=" * 60)

    # 创建邮件管理器
    alice = create_node_identity("alice", "laptop-001", "Alice")
    alice_mail = create_mail_manager(alice)

    # 准备多封邮件
    recipients = [
        ("bob@desktop-001", "项目更新 #1", "这是第一周的进度报告..."),
        ("charlie@phone-001", "项目更新 #2", "这是第二周的进度报告..."),
        ("david@server-001", "项目更新 #3", "这是第三周的进度报告..."),
    ]

    # 并发发送
    tasks = []
    for recipient, subject, body in recipients:
        task = alice_mail.send_mail(
            to_nodes=[recipient],
            subject=subject,
            body=body
        )
        tasks.append(task)

    results = await asyncio.gather(*tasks)

    print(f"✓ 并发发送完成: {len(results)} 封邮件")
    for i, mail in enumerate(results):
        print(f"  - [{i+1}] {mail.subject} -> {mail.to_nodes}")

    return results


async def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("📧 内部邮件系统 - 完整示例")
    print("=" * 60 + "\n")

    # 运行所有示例
    await example_basic_mail()
    await example_reply_mail()
    await example_attachment()
    await example_ai_enhancement()
    await example_encrypted_mail()
    await example_message_router()
    await example_forward_mail()
    await example_mail_session()
    await example_concurrent_mail()

    print("\n" + "=" * 60)
    print("✅ 所有示例执行完成!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
