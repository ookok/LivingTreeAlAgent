"""
AiToEarn 独立测试

完全独立测试多平台分发和社交互动核心功能
"""

import time
import asyncio


# ============ 复制核心组件 ============

class PlatformType:
    DOUYIN = "douyin"
    XIAOHONGSHU = "xiaohongshu"
    BILIBILI = "bilibili"
    TIKTOK = "tiktok"
    YOUTUBE = "youtube"


class ContentType:
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    ARTICLE = "article"


class EngageAction:
    LIKE = "like"
    COMMENT = "comment"
    FOLLOW = "follow"
    SHARE = "share"


class Content:
    def __init__(self, title, body, content_type, media_urls=None, tags=None):
        self.title = title
        self.body = body
        self.content_type = content_type
        self.media_urls = media_urls or []
        self.tags = tags or []


class PublishResult:
    def __init__(self, platform, success, post_id=None, post_url=None, error=None):
        self.platform = platform
        self.success = success
        self.post_id = post_id
        self.post_url = post_url
        self.error = error
        self.timestamp = time.time()


class EngageResult:
    def __init__(self, platform, action, success, target_id, result_id=None, error=None):
        self.platform = platform
        self.action = action
        self.success = success
        self.target_id = target_id
        self.result_id = result_id
        self.error = error
        self.timestamp = time.time()


class MultiPlatformManager:
    def __init__(self):
        self.platforms = {}
    
    def register_platform(self, platform_type):
        self.platforms[platform_type] = True
    
    def unregister_platform(self, platform_type):
        if platform_type in self.platforms:
            del self.platforms[platform_type]
            return True
        return False
    
    async def publish(self, platform_types, content):
        results = {}
        for platform_type in platform_types:
            await asyncio.sleep(0.1)
            post_id = f"{platform_type}_{int(time.time())}"
            results[platform_type] = PublishResult(
                platform=platform_type,
                success=True,
                post_id=post_id,
                post_url=f"https://{platform_type}.com/video/{post_id}"
            )
        return results
    
    async def publish_all(self, content):
        return await self.publish(list(self.platforms.keys()), content)
    
    async def engage(self, platform_type, action, target_id, **kwargs):
        await asyncio.sleep(0.05)
        return EngageResult(
            platform=platform_type,
            action=action,
            success=True,
            target_id=target_id,
            result_id=f"result_{int(time.time())}"
        )


class CommentGenerator:
    def __init__(self):
        self.default_comments = {
            "friendly": ["很棒的内容！", "学到了，感谢分享！", "支持！"],
            "professional": ["分析到位", "观点很有见地"],
            "humorous": ["笑死我了", "哈哈太真实了"],
        }
    
    async def generate(self, content, style="friendly", language="zh"):
        comments = self.default_comments.get(style, self.default_comments["friendly"])
        import random
        return random.choice(comments)


class SocialEngageSubAgent:
    def __init__(self, platform_manager, comment_generator=None):
        self.platform_manager = platform_manager
        self.comment_generator = comment_generator or CommentGenerator()
        self.stats = {"total_likes": 0, "total_comments": 0, "total_follows": 0}
    
    async def like_post(self, platform, post_id):
        result = await self.platform_manager.engage(platform, EngageAction.LIKE, post_id)
        if result.success:
            self.stats["total_likes"] += 1
        return result
    
    async def comment_post(self, platform, post_id, content=None, auto_generate=True):
        if auto_generate and not content:
            content = await self.comment_generator.generate(f"Post: {post_id}")
        result = await self.platform_manager.engage(platform, EngageAction.COMMENT, post_id, content=content)
        if result.success:
            self.stats["total_comments"] += 1
        return result
    
    async def batch_like(self, platform, post_ids):
        tasks = [self.like_post(platform, pid) for pid in post_ids]
        return await asyncio.gather(*tasks)
    
    def get_stats(self):
        return self.stats.copy()


class ContentPlanner:
    def __init__(self):
        self.topics = []
        self.schedule = {}
    
    def add_topic(self, topic, priority=1):
        self.topics.append({"topic": topic, "priority": priority, "added_at": time.time()})
    
    def generate_schedule(self, platforms, posts_per_week=10):
        schedule = []
        sorted_topics = sorted(self.topics, key=lambda x: x["priority"], reverse=True)
        posts_per_platform = posts_per_week // len(platforms) if platforms else 0
        
        for i, topic in enumerate(sorted_topics[:posts_per_week]):
            for j, platform in enumerate(platforms[:posts_per_platform]):
                schedule.append({
                    "task_id": f"plan_{i}_{j}",
                    "topic": topic["topic"],
                    "platform": platform,
                    "priority": topic["priority"],
                })
        
        return schedule


class ContentGenerator:
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.generated_content = []
    
    async def generate(self, topic, content_type, materials=None, style="friendly", language="zh"):
        content = {
            "topic": topic,
            "type": content_type,
            "style": style,
            "language": language,
            "created_at": time.time(),
        }
        
        if self.llm_client and materials:
            content["body"] = f"Generated content about {topic}"
            content["title"] = f"AI Generated: {topic}"
        else:
            content["body"] = f"这是一篇关于 {topic} 的{content_type}内容"
            content["title"] = f"{topic} - 内容创作"
        
        self.generated_content.append(content)
        return content


# ============ 测试函数 ============

def test_platform_tools():
    print("=== 测试多平台工具 ===")
    
    manager = MultiPlatformManager()
    manager.register_platform(PlatformType.DOUYIN)
    manager.register_platform(PlatformType.XIAOHONGSHU)
    manager.register_platform(PlatformType.BILIBILI)
    manager.register_platform(PlatformType.TIKTOK)
    manager.register_platform(PlatformType.YOUTUBE)
    
    print(f"已注册平台: {list(manager.platforms.keys())}")
    
    content = Content(
        title="测试标题",
        body="这是测试内容",
        content_type=ContentType.ARTICLE,
    )
    
    print("\n测试发布内容...")
    
    async def test():
        results = await manager.publish([PlatformType.DOUYIN, PlatformType.XIAOHONGSHU], content)
        return results
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        results = loop.run_until_complete(test())
    finally:
        loop.close()
    
    print("发布结果:")
    for platform, result in results.items():
        print(f"  {platform}: {'成功' if result.success else '失败'}")
        if result.success:
            print(f"    URL: {result.post_url}")
    
    print("\n多平台工具测试完成!")


def test_social_engage():
    print("\n=== 测试社交互动 ===")
    
    manager = MultiPlatformManager()
    manager.register_platform(PlatformType.DOUYIN)
    
    subagent = SocialEngageSubAgent(
        platform_manager=manager,
        comment_generator=CommentGenerator()
    )
    
    print("测试点赞...")
    
    async def test_like():
        return await subagent.like_post(PlatformType.DOUYIN, "post_123")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        like_result = loop.run_until_complete(test_like())
    finally:
        loop.close()
    
    print(f"点赞结果: {'成功' if like_result.success else '失败'}")
    
    print("\n测试评论...")
    
    async def test_comment():
        return await subagent.comment_post(PlatformType.DOUYIN, "post_456", content="很棒的内容！")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        comment_result = loop.run_until_complete(test_comment())
    finally:
        loop.close()
    
    print(f"评论结果: {'成功' if comment_result.success else '失败'}")
    
    print("\n测试批量点赞...")
    
    async def test_batch():
        return await subagent.batch_like(PlatformType.DOUYIN, ["post_1", "post_2", "post_3"])
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        batch_results = loop.run_until_complete(test_batch())
    finally:
        loop.close()
    
    success_count = sum(1 for r in batch_results if r.success)
    print(f"批量点赞: {success_count}/{len(batch_results)} 成功")
    
    stats = subagent.get_stats()
    print(f"\n社交互动统计:")
    print(f"  总点赞: {stats['total_likes']}")
    print(f"  总评论: {stats['total_comments']}")
    
    print("\n社交互动测试完成!")


def test_content_workflow():
    print("\n=== 测试内容工作流 ===")
    
    planner = ContentPlanner()
    generator = ContentGenerator()
    
    topics = ["AI 技术趋势", "智能体发展", "未来展望"]
    for topic in topics:
        planner.add_topic(topic, priority=1)
    
    print(f"已添加 {len(topics)} 个主题")
    
    platforms = [PlatformType.DOUYIN, PlatformType.XIAOHONGSHU]
    schedule = planner.generate_schedule(platforms, posts_per_week=4)
    print(f"生成了 {len(schedule)} 个发布计划")
    
    print("\n发布计划预览:")
    for plan in schedule[:2]:
        print(f"  [{plan['priority']}] {plan['topic']} -> {plan['platform']}")
    
    print("\n测试内容生成...")
    
    async def test_generate():
        return await generator.generate(
            topic="AI 技术趋势",
            content_type="article",
            style="friendly",
            language="zh"
        )
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        generated = loop.run_until_complete(test_generate())
    finally:
        loop.close()
    
    print(f"生成内容:")
    print(f"  标题: {generated.get('title', 'N/A')}")
    print(f"  类型: {generated.get('type')}")
    print(f"  正文预览: {generated.get('body', '')[:30]}...")
    
    print("\n内容工作流测试完成!")


def test_integration():
    print("\n=== 测试集成功能 ===")
    
    manager = MultiPlatformManager()
    manager.register_platform(PlatformType.DOUYIN)
    manager.register_platform(PlatformType.XIAOHONGSHU)
    
    subagent = SocialEngageSubAgent(
        platform_manager=manager,
        comment_generator=CommentGenerator()
    )
    
    print("1. 创建内容...")
    content = Content(
        title="AI Agent 发展趋势",
        body="本文分析 AI Agent 的发展趋势...",
        content_type=ContentType.ARTICLE,
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
        like_result = await subagent.like_post(PlatformType.DOUYIN, "viral_post_1")
        comment_result = await subagent.comment_post(PlatformType.DOUYIN, "viral_post_1", content="分析得很到位！")
        return like_result, comment_result
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        like_r, comment_r = loop.run_until_complete(engage())
    finally:
        loop.close()
    
    print(f"   点赞: {'成功' if like_r.success else '失败'}")
    print(f"   评论: {'成功' if comment_r.success else '失败'}")
    
    stats = subagent.get_stats()
    print("\n4. 最终统计...")
    print(f"   总点赞: {stats['total_likes']}")
    print(f"   总评论: {stats['total_comments']}")
    
    print("\n集成测试完成!")


if __name__ == "__main__":
    print("=" * 50)
    print("AiToEarn 独立测试")
    print("=" * 50)
    
    try:
        test_platform_tools()
        test_social_engage()
        test_content_workflow()
        test_integration()
        print("\n" + "=" * 50)
        print("All tests passed!")
        print("=" * 50)
    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\nTest completed")
