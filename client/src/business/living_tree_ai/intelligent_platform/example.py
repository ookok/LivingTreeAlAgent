"""
智能工作空间使用示例
====================

演示如何创建智能内容、发布网页、协作、以及安全存储
"""

import asyncio
from pathlib import Path

# 导入智能工作空间
from intelligent_platform import (
    IntelligentWorkspace, create_workspace,
    ContentType, PublishStatus,
    ContentCreator, WritingTone, ContentTemplate,
    WebPublisher, PageType,
    CollaborationEngine, ReplyTone,
    SecurityGuard, ThreatLevel,
    StorageEngine, StorageType
)


async def example_content_creation():
    """示例：创建智能内容"""
    print("\n" + "="*60)
    print("📝 示例1: 创建智能内容")
    print("="*60)

    # 创建工作空间
    workspace = create_workspace(
        workspace_id="my_workspace",
        local_storage_path=Path.home() / ".hermes-desktop" / "workspace_demo"
    )

    # 创建技术文章
    content = await workspace.create_content(
        title="分布式 AI 计算网络的架构设计",
        content="""
# 分布式 AI 计算网络架构

## 背景
随着 AI 应用的普及，需要一种能够整合多种 AI 能力的分布式架构。

## 设计原则
1. 分层架构：感知层、推理层、控制层
2. 节点自治：各节点独立运作，通过中心节点协调
3. 数据不动，计算动：原始数据保留在本地

## 核心组件
- **感知层**：采集用户意图
- **推理层**：执行 AI 模型计算
- **控制层**：任务分解、路由、上下文管理
        """,
        content_type=ContentType.ARTICLE,
        author_node_id="alice@laptop-001"
    )

    print(f"✅ 内容创建成功！")
    print(f"   ID: {content.metadata.content_id}")
    print(f"   摘要: {content.summary}")
    print(f"   标签: {content.metadata.tags}")
    print(f"   合规: {'通过' if content.compliance.passed else '未通过'}")

    return content


async def example_smart_reply():
    """示例：智能回复建议"""
    print("\n" + "="*60)
    print("💬 示例2: 智能回复建议")
    print("="*60)

    workspace = create_workspace("my_workspace")

    # 获取协作引擎
    collab = workspace.collaboration

    # 模拟对话
    original_message = "这个接口的响应时间太慢了，能否优化一下？"

    # 生成多种语气的回复建议
    suggestions = await collab.suggest_replies(
        original_message=original_message,
        context="用户反馈系统性能问题",
        tones=[ReplyTone.TECHNICAL, ReplyTone.FRIENDLY, ReplyTone.CONCISE]
    )

    print(f"📨 原始消息: {original_message}\n")
    print("💡 回复建议:")

    for i, s in enumerate(suggestions, 1):
        print(f"\n   [{i}] {s.tone.value} (置信度: {s.confidence:.0%})")
        print(f"       {s.content}")
        if s.relevant_context:
            print(f"       📎 相关: {s.relevant_context}")


async def example_security_scan():
    """示例：安全扫描"""
    print("\n" + "="*60)
    print("🔒 示例3: 安全扫描")
    print("="*60)

    workspace = create_workspace("my_workspace")
    security = workspace.security

    # 扫描内容
    test_content = """
    请查收附件中的财务报表，这是公司内部的机密资料。
    来源：https://example.com/article
    """

    result = await security.scan_content(test_content)

    print(f"✅ 合规扫描结果:")
    print(f"   通过: {'是' if result.passed else '否'}")
    print(f"   评分: {result.score:.0%}")

    if result.warnings:
        print(f"\n   ⚠️ 警告:")
        for w in result.warnings:
            print(f"      - {w}")

    # 附件扫描
    print("\n📎 附件扫描:")
    attachment_result = await security.scan_attachment(
        file_hash="abc123",
        file_name="invoice.exe",
        file_size=1024 * 1024,
        file_type="exe"
    )
    print(f"   威胁等级: {attachment_result.threat_level.value}")
    print(f"   问题: {', '.join(attachment_result.issues) or '无'}")

    # 防误发检测
    print("\n📧 防误发检测:")
    misend_result = await security.check_misend_risk(
        recipients=["bob@gmail.com", "alice@company.local"],
        content="这是内部的项目计划，请保密",
        attachments=["核心架构图.docx"]
    )
    print(f"   风险等级: {misend_result['risk_level']}")
    print(f"   需要确认: {'是' if misend_result['confirm_required'] else '否'}")
    for w in misend_result['warnings']:
        print(f"      - {w}")


async def example_web_publishing():
    """示例：智能网页发布"""
    print("\n" + "="*60)
    print("🌐 示例4: 智能网页发布")
    print("="*60)

    workspace = create_workspace("my_workspace")
    publisher = workspace.web_publisher

    # 创建网页
    page = await publisher.create_page(
        url_path="/articles/distributed-ai",
        title="分布式 AI 计算网络的架构设计",
        content="""
        <article>
            <h1>分布式 AI 计算网络</h1>
            <p>本文介绍了一种创新的分布式 AI 架构...</p>
        </article>
        """,
        page_type=PageType.ARTICLE,
        author_node_id="alice@laptop-001"
    )

    print(f"✅ 页面创建成功!")
    print(f"   ID: {page.page_id}")
    print(f"   URL: {page.url_path}")

    if page.seo:
        print(f"\n   📊 SEO 优化:")
        print(f"      标题: {page.seo.title}")
        print(f"      描述: {page.seo.meta_description}")
        print(f"      关键词: {', '.join(page.seo.meta_keywords)}")
        print(f"      可读性: {page.seo.readability_score:.0f}")

    # 模拟搜索引擎预览
    preview = await publisher.preview_for_search_engine(page)
    print(f"\n   🔍 搜索预览:")
    print(f"      {preview['title']}")
    print(f"      {preview['url']}")
    print(f"      {preview['description'][:80]}...")


async def example_collaboration():
    """示例：协作功能"""
    print("\n" + "="*60)
    print("🤝 示例5: 协作功能")
    print("="*60)

    workspace = create_workspace("my_workspace")
    collab = workspace.collaboration

    # 自动标签
    print("\n🏷️ 自动标签:")
    test_contents = [
        "系统出现了崩溃，如何解决？",
        "建议增加一个导出 PDF 的功能",
        "Python 异步编程入门教程"
    ]
    for content in test_contents:
        tags = await collab.auto_tag_content(content)
        print(f"   「{content[:20]}...」")
        print(f"      标签: {', '.join(tags)}")

    # 邮件转工单
    print("\n📋 邮件转工单:")
    ticket = await collab.convert_to_ticket(
        title="Bug报告：登录失败",
        content="用户反映在 Chrome 浏览器下无法登录，系统报错 'Invalid Token'",
        source_type="mail"
    )
    print(f"   工单ID: {ticket.ticket_id}")
    print(f"   类型: {ticket.ticket_type}")
    print(f"   优先级: {ticket.priority}")


async def example_storage():
    """示例：存储引擎"""
    print("\n" + "="*60)
    print("💾 示例6: 存储引擎")
    print("="*60)

    workspace = create_workspace("my_workspace")
    storage = workspace.storage

    # 存储内容
    content_id = "test_content_001"
    await storage.store_content(
        content_id=content_id,
        content="这是一段测试内容，用于演示存储引擎",
        metadata={"type": "test", "author": "alice"}
    )
    print(f"✅ 内容存储成功: {content_id}")

    # 附件去重
    print("\n📦 附件去重:")
    result = await storage.deduplicate_attachment(
        file_hash="hash_abc123",
        file_path="/path/to/duplicate_file.pdf",
        file_size=1024 * 1024
    )
    print(f"   文件Hash: {result.file_hash}")
    print(f"   规范路径: {result.canonical_path}")
    print(f"   引用次数: {result.reference_count}")

    # 预测性预取
    print("\n⚡ 预测性预取:")
    prefetch_ids = await storage.predict_and_prefetch(
        user_node_id="alice@laptop-001",
        context={"hour": 9, "location": "home", "device": "desktop"}
    )
    print(f"   预测内容: {prefetch_ids}")

    # 存储统计
    stats = storage.get_storage_stats()
    print(f"\n📊 存储统计:")
    print(f"   索引总数: {stats['total_indices']}")
    print(f"   预览缓存: {stats['total_previews']}")
    print(f"   本地内容: {stats['local_content_size'] / 1024:.1f} KB")


async def example_full_workflow():
    """示例：完整工作流"""
    print("\n" + "="*60)
    print("🚀 示例7: 完整工作流 - 智能邮件的旅程")
    print("="*60)

    workspace = create_workspace("my_workspace")

    print("""
    📧 场景：一封智能邮件的旅程

    1️⃣ 撰写（客户端）
    """)
    # 创建邮件内容
    content = await workspace.create_content(
        title="项目进度更新",
        content="""
        大家好，

        项目已完成了第一阶段的开发，主要成果：
        1. 用户认证模块 ✅
        2. 数据同步服务 ✅
        3. AI 助手集成 🔄

        下周计划：
        - 完成移动端适配
        - 开始性能优化

        请查收附件中的详细文档。
        """,
        content_type=ContentType.MAIL,
        author_node_id="alice@laptop-001"
    )
    print(f"       内容创建完成: {content.metadata.content_id}")

    print("""
    2️⃣ 增强（边缘节点）
    """)
    # AI 增强
    enhanced = await workspace.content_creator.enhance_writing(
        content.original_content,
        target_tone=WritingTone.PROFESSIONAL
    )
    print(f"       语气优化完成")
    print(f"       摘要: {content.summary}")

    print("""
    3️⃣ 扫描（中心节点）
    """)
    # 安全扫描
    scan_result = await workspace.security.scan_content(content.original_content)
    print(f"       合规检查: {'通过' if scan_result.passed else '需要修改'}")
    if scan_result.warnings:
        for w in scan_result.warnings:
            print(f"       ⚠️ {w}")

    print("""
    4️⃣ 存储（本地）
    """)
    # 本地存储
    storage_path = await workspace.storage.store_content(
        content.metadata.content_id,
        content.original_content,
        metadata={"type": "mail", "to": ["bob@desktop-001"]}
    )
    print(f"       保存至: {storage_path}")

    print("""
    5️⃣ 索引（分布式）
    """)
    # 生成预览并索引
    previews = await workspace.storage.generate_preview(content)
    print(f"       生成预览: {len(previews)} 个")

    # 去重附件
    dedup = await workspace.storage.deduplicate_attachment(
        file_hash="doc_hash_001",
        file_path="/attachments/project_plan.pdf",
        file_size=2 * 1024 * 1024
    )
    print(f"       附件去重: 节省 {dedup.reference_count - 1} 份副本")

    print("""
    ✅ 邮件旅程完成！
    """)


async def main():
    """运行所有示例"""
    print("\n" + "="*60)
    print("🧠 智能工作空间演示")
    print("="*60)

    # 运行各示例
    await example_content_creation()
    await example_smart_reply()
    await example_security_scan()
    await example_web_publishing()
    await example_collaboration()
    await example_storage()
    await example_full_workflow()

    print("\n" + "="*60)
    print("✨ 所有演示完成！")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())