"""
AiToEarn 集成功能测试

测试多平台分发和社交互动功能
"""

import time
import asyncio


def test_platform_tools():
    """测试多平台工具"""
    print("=== 测试多平台工具 ===")
    
    from client.src.business.aitotearn import (
        PlatformType,
        ContentType,
        Content,
        MultiPlatformManager,
        PlatformFactory,
    )
    
    # 创建管理器
    manager = MultiPlatformManager()
    
    # 注册平台
    manager.register_platform(PlatformType.DOUYIN)
    manager.register_platform(PlatformType.XIAOHONGSHU)
    manager.register_platform(PlatformType.BILIBILI)
    manager.register_platform(PlatformType.TIKTOK)
    manager.register_platform(PlatformType.YOUTUBE)
    
    print(f"已注册平台: {[p.value for p in manager.list_platforms()]}")
    
    # 测试创建平台 API
    douyin_api = PlatformFactory.create(PlatformType.DOUYIN)
    print(f"创建抖音 API: {type(douyin_api).__name__}")
    
    # 测试内容发布
    content = Content(
        title="测试标题",
        body="这是测试内容",
        content_type=ContentType.ARTICLE,
        tags=["测试", "AI"]
    )
    
    print("\n测试发布内容到抖音...")
    
    async def test_publish():
        result = await douyin_api.publish(content)
        return result
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        publish_result = loop.run_until_complete(test_publish())
    finally:
        loop.close()
    
    print(f"发布结果:")
    print(f"  成功: {publish_result.success}")
    print(f"  帖子ID: {publish_result.post_id}")
    print(f"  URL: {publish_result.post_url}")
    print(f"  时间戳: {publish_result.timestamp}")
    
    # 测试批量发布
    print("\n测试批量发布...")
    
    async def test_batch_publish():
        results = await manager.publish([
            PlatformType.DOUYIN,
            PlatformType.XIAOHONGSHU,
        ], content)
        return results
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        batch_results = loop.run_until_complete(test_batch_publish())
    finally:
        loop.close()
    
    print("批量发布结果:")
    for platform, result in batch_results.items():
        print(f"  {platform}: {'成功' if result.success else '失败'}")
    
    # 测试获取统计
    print("\n测试获取统计...")
    
    async def test_stats():
        stats = await manager.get_all_stats()
        return stats
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        all_stats = loop.run_until_complete(test_stats())
    finally:
        loop.close()
    
    print("平台统计:")
    for platform, stats in all_stats.items():
        print(f"  {platform}: 粉丝 {stats.followers}, 帖子 {stats.posts}")
    
    print("\n多平台工具测试完成!")


def test_social_engage():
    """测试社交互动"""
    print("\n=== 测试社交互动 ===")
    
    from client.src.business.aitotearn import (
        PlatformType,
        EngageAction,
        MultiPlatformManager,
        SocialEngageSubAgent,
        CommentGenerator,
    )
    
    # 创建管理器
    manager = MultiPlatformManager()
    manager.register_platform(PlatformType.DOUYIN)
    
    # 创建社交互动子智能体
    subagent = SocialEngageSubAgent(
        platform_manager=manager,
        comment_generator=CommentGenerator()
    )
    
    # 测试点赞
    print("测试点赞...")
    
    async def test_like():
        result = await subagent.like_post(PlatformType.DOUYIN, "post_123")
        return result
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        like_result = loop.run_until_complete(test_like())
    finally:
        loop.close()
    
    print(f"点赞结果: {'成功' if like_result.success else '失败'}")
    
    # 测试评论
    print("\n测试评论...")
    
    async def test_comment():
        result = await subagent.comment_post(
            PlatformType.DOUYIN,
            "post_456",
            content="很棒的内容！"
        )
        return result
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        comment_result = loop.run_until_complete(test_comment())
    finally:
        loop.close()
    
    print(f"评论结果: {'成功' if comment_result.success else '失败'}")
    
    # 测试批量点赞
    print("\n测试批量点赞...")
    
    async def test_batch_like():
        results = await subagent.batch_like(
            PlatformType.DOUYIN,
            ["post_1", "post_2", "post_3"]
        )
        return results
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        batch_results = loop.run_until_complete(test_batch_like())
    finally:
        loop.close()
    
    success_count = sum(1 for r in batch_results if r.success)
    print(f"批量点赞: {success_count}/{len(batch_results)} 成功")
    
    # 获取统计
    stats = subagent.get_stats()
    print(f"\n社交互动统计:")
    print(f"  总点赞: {stats['total_likes']}")
    print(f"  总评论: {stats['total_comments']}")
    print(f"  总关注: {stats['total_follows']}")
    
    print("\n社交互动测试完成!")


def test_content_workflow():
    """测试内容工作流"""
    print("\n=== 测试内容工作流 ===")
    
    from client.src.business.aitotearn import (
        PlatformType,
        ContentPlanner,
        MaterialCollector,
        ContentGenerator,
        ContentWorkflow,
        MultiPlatformManager,
    )
    
    # 创建组件
    planner = ContentPlanner()
    collector = MaterialCollector()
    generator = ContentGenerator()
    
    # 创建管理器
    manager = MultiPlatformManager()
    manager.register_platform(PlatformType.DOUYIN)
    manager.register_platform(PlatformType.XIAOHONGSHU)
    
    # 创建工作流
    workflow = ContentWorkflow(
        platform_manager=manager,
        content_planner=planner,
        material_collector=collector,
        content_generator=generator,
    )
    
    # 添加主题
    topics = ["AI 技术趋势", "智能体发展", "未来展望"]
    for topic in topics:
        planner.add_topic(topic, priority=1)
    
    print(f"已添加 {len(topics)} 个主题")
    
    # 生成计划
    platforms = [PlatformType.DOUYIN.value, PlatformType.XIAOHONGSHU.value]
    schedule = planner.generate_schedule(platforms, posts_per_week=4)
    print(f"生成了 {len(schedule)} 个发布计划")
    
    # 执行工作流（简化版，不实际调用 API）
    print("\n工作流任务预览:")
    for plan in schedule[:2]:
        print(f"  [{plan['priority']}] {plan['topic']} -> {plan['platform']}")
    
    # 测试内容生成
    print("\n测试内容生成...")
    
    async def test_generate():
        content = await generator.generate(
            topic="AI 技术趋势",
            content_type="article",
            materials=[{"type": "text", "content": "AI 技术发展迅速"}],
            style="friendly",
            language="zh"
        )
        return content
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        generated = loop.run_until_complete(test_generate())
    finally:
        loop.close()
    
    print(f"生成内容:")
    print(f"  标题: {generated.get('title', 'N/A')}")
    print(f"  类型: {generated.get('type')}")
    print(f"  正文预览: {generated.get('body', '')[:50]}...")
    
    print("\n内容工作流测试完成!")


def test_integration():
    """测试集成功能"""
    print("\n=== 测试集成功能 ===")
    
    from client.src.business.aitotearn import (
        PlatformType,
        Content,
        ContentType,
        MultiPlatformManager,
        SocialEngageSubAgent,
        ContentWorkflow,
        CommentGenerator,
    )
    
    # 创建组件
    manager = MultiPlatformManager()
    manager.register_platform(PlatformType.DOUYIN)
    manager.register_platform(PlatformType.XIAOHONGSHU)
    
    # 创建子智能体
    subagent = SocialEngageSubAgent(
        platform_manager=manager,
        comment_generator=CommentGenerator()
    )
    
    # 模拟完整流程
    print("1. 创建内容...")
    content = Content(
        title="AI Agent 发展趋势",
        body="本文分析 AI Agent 的发展趋势...",
        content_type=ContentType.ARTICLE,
        tags=["AI", "Agent", "趋势"]
    )
    print(f"   内容创建完成: {content.title}")
    
    print("\n2. 发布到多平台...")
    
    async def publish():
        return await manager.publish_all(content)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        results = loop.run_until_complete(publish())
    finally:
        loop.close()
    
    success_count = sum(1 for r in results.values() if r.success)
    print(f"   发布成功: {success_count}/{len(results)}")
    
    print("\n3. 社交互动...")
    
    async def engage():
        # 点赞
        like_result = await subagent.like_post(PlatformType.DOUYIN, "viral_post_1")
        # 评论
        comment_result = await subagent.comment_post(
            PlatformType.DOUYIN,
            "viral_post_1",
            content="分析得很到位！"
        )
        return like_result, comment_result
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        like_r, comment_r = loop.run_until_complete(engage())
    finally:
        loop.close()
    
    print(f"   点赞: {'成功' if like_r.success else '失败'}")
    print(f"   评论: {'成功' if comment_r.success else '失败'}")
    
    print("\n4. 获取最终统计...")
    stats = {}
    engage_stats = subagent.get_stats()
    
    print("   平台统计:")
    for platform, s in stats.items():
        print(f"     {platform}: 粉丝 {s.followers}, 帖子 {s.posts}")
    
    print("   互动统计:")
    print(f"     总点赞: {engage_stats['total_likes']}")
    print(f"     总评论: {engage_stats['total_comments']}")
    
    print("\n集成测试完成!")


if __name__ == "__main__":
    print("=" * 50)
    print("AiToEarn 集成功能测试")
    print("=" * 50)
    
    try:
        test_platform_tools()
        test_social_engage()
        test_content_workflow()
        test_integration()
        print("\n" + "=" * 50)
        print("✅ 所有测试通过!")
        print("=" * 50)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n测试完成")
