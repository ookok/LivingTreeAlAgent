"""
Broadcast Network Example - 订阅制广播系统示例
==========================================

Author: LivingTreeAI Community
"""

import asyncio
import time


async def example_content_publishing():
    """内容发布示例"""
    from broadcast_network import (
        BroadcastManager,
        Content,
        ContentType,
        ContentScope,
        create_post,
        create_email,
    )

    print("=== 内容发布示例 ===\n")

    # 创建广播管理器
    manager = BroadcastManager("node_a")

    # 发布帖子
    print("发布帖子...")
    success, msg = await manager.publish_post(
        board="tech",
        title="P2P优化技巧分享",
        body="我发现了几个可以优化节点同步效率的方法...",
        tags=["P2P", "优化"],
    )
    print(f"  结果: {success}, {msg}")

    # 发送邮件
    print("\n发送邮件...")
    success, msg = await manager.publish_email(
        recipients=["node_b", "node_c"],
        subject="项目进展通报",
        body="本周完成了搜索功能的开发...",
        priority="normal",
    )
    print(f"  结果: {success}, {msg}")

    return manager


async def example_subscription():
    """订阅管理示例"""
    from broadcast_network import BroadcastManager

    print("\n=== 订阅管理示例 ===\n")

    manager = BroadcastManager("node_a")

    # 订阅板块
    manager.subscribe_board("tech")
    manager.subscribe_board("general")

    # 关注作者
    manager.subscribe_author("node_expert_1")

    # 订阅关键词
    manager.subscribe_keyword("P2P")
    manager.subscribe_keyword("优化")

    # 获取订阅列表
    subs = manager.get_subscriptions()
    print(f"订阅的板块: {subs['boards']}")
    print(f"关注的作者: {subs['authors']}")
    print(f"订阅的关键词: {subs['keywords']}")


async def example_search():
    """搜索示例"""
    from broadcast_network import BroadcastManager, SearchQuery

    print("\n=== 搜索示例 ===\n")

    manager = BroadcastManager("node_a")

    # 发布一些内容
    await manager.publish_post(
        board="tech",
        title="深度学习优化方法",
        body="关于P2P网络中的深度学习优化...",
    )
    await manager.publish_post(
        board="tech",
        title="分布式系统设计",
        body="如何设计高效的分布式缓存...",
    )

    # 搜索
    print("搜索 'P2P 优化'...")
    results = await manager.search("P2P 优化", limit=10)
    print(f"  找到 {len(results)} 条结果")
    for r in results[:3]:
        print(f"    - {r.content_id[:16]}... (score: {r.score:.2f})")


async def example_anti_spam():
    """反垃圾示例"""
    from broadcast_network import AntiSpamSystem, Content, ContentType

    print("\n=== 反垃圾示例 ===\n")

    antispam = AntiSpamSystem("node_a")

    # 测试正常内容
    normal_content = Content(
        type=ContentType.POST,
        author="trusted_user",
        title="正经技术文章",
        body="这是一篇关于分布式系统的正经技术文章...",
        board="tech",
    )

    score = antispam.evaluate_content(normal_content)
    allowed, spam_score = antispam.filter_content(normal_content)
    print(f"正常内容: score={score:.2f}, allowed={allowed}, spam={spam_score.value}")

    # 测试垃圾内容
    spam_content = Content(
        type=ContentType.POST,
        author="spam_user",
        title="免费赚钱",
        body="点击此处立即购买！限时特价优惠...",
        board="tech",
    )

    score = antispam.evaluate_content(spam_content)
    allowed, spam_score = antispam.filter_content(spam_content)
    print(f"垃圾内容: score={score:.2f}, allowed={allowed}, spam={spam_score.value}")

    # 速率限制
    print("\n速率限制测试...")
    for i in range(5):
        allowed = antispam.check_rate_limit("user_1", "publish_post")
        print(f"  发布 #{i+1}: {'允许' if allowed else '拒绝'}")
        if allowed:
            antispam.record_action("user_1", "publish_post")


async def example_reputation():
    """信誉系统示例"""
    from broadcast_network import AntiSpamSystem

    print("\n=== 信誉系统示例 ===\n")

    antispam = AntiSpamSystem("node_a")

    # 记录贡献
    for i in range(15):
        antispam.record_positive_interaction("good_user", f"content_{i}")

    # 举报垃圾
    antispam.record_negative_interaction("bad_user", "spam_content_1")
    antispam.record_negative_interaction("bad_user", "spam_content_2")

    # 获取统计
    print("好用户统计:")
    good_stats = antispam.get_author_stats("good_user")
    print(f"  {good_stats}")

    print("\n坏用户统计:")
    bad_stats = antispam.get_author_stats("bad_user")
    print(f"  {bad_stats}")


async def example_email_system():
    """邮件系统示例"""
    from broadcast_network import EmailSystem

    print("\n=== 邮件系统示例 ===\n")

    email_system = EmailSystem("user_a")

    # 发送邮件
    print("发送邮件...")
    email = await email_system.send_email(
        recipients=["user_b", "user_c"],
        subject="测试邮件",
        body="这是一封测试邮件的正文内容...",
        priority="normal",
    )
    print(f"  邮件ID: {email.content_id[:16]}...")

    # 接收邮件
    print("\n接收邮件...")
    received = await email_system.receive_email(email.to_dict())
    print(f"  来自: {received.author}")
    print(f"  主题: {received.title}")


async def example_full_workflow():
    """完整工作流示例"""
    from broadcast_network import (
        BroadcastManager,
        Content,
        ContentType,
    )

    print("\n" + "=" * 50)
    print("广播系统 - 完整工作流示例")
    print("=" * 50)

    # 创建两个节点
    node_a = BroadcastManager("node_a")
    node_b = BroadcastManager("node_b")

    # 节点B订阅节点A的板块
    node_b.subscribe_board("tech")
    print("\n节点B订阅了 tech 板块")

    # 节点A发布内容
    print("\n节点A发布帖子...")
    success, msg = await node_a.publish_post(
        board="tech",
        title="P2P网络优化技巧",
        body="本文介绍几种优化P2P同步效率的方法...",
        author="node_a",
        tags=["P2P", "优化"],
    )
    print(f"  发布结果: {success}")

    # 节点A执行搜索
    print("\n节点A搜索 'P2P'...")
    results = await node_a.search("P2P", boards=["tech"])
    print(f"  找到 {len(results)} 条结果")

    # 获取统计
    print("\n节点A统计:")
    stats = node_a.get_stats()
    print(f"  发布内容: {stats['published']}")
    print(f"  接收内容: {stats['received']}")
    print(f"  搜索次数: {stats['searched']}")
    print(f"  垃圾过滤: {stats['spam_filtered']}")


async def main():
    """运行所有示例"""
    print("=" * 60)
    print("广播网络系统示例")
    print("=" * 60)

    await example_content_publishing()
    await asyncio.sleep(0.2)

    await example_subscription()
    await asyncio.sleep(0.2)

    await example_search()
    await asyncio.sleep(0.2)

    await example_anti_spam()
    await asyncio.sleep(0.2)

    await example_reputation()
    await asyncio.sleep(0.2)

    await example_email_system()
    await asyncio.sleep(0.2)

    await example_full_workflow()

    print("\n" + "=" * 60)
    print("示例完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())