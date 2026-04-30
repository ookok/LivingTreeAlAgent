"""
Smart Help System Demo - 智能求助系统演示

演示完整的求助流程：
1. 问题脱敏
2. 平台选择
3. 提问生成
4. 帖子发布
5. 答案监控
6. 答案整合
"""

import sys
import time
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, 'd:/mhzyapp/hermes-desktop')

from business.smart_help_system import (
    SmartHelpController,
    QuestionSanitizer,
    PlatformSelector,
    QuestionGenerator,
    AnswerMonitor,
    AnswerAggregator,
    Platform,
    QuestionType,
    HelpStatus,
)


def print_separator(title: str = ""):
    """打印分隔符"""
    print("\n" + "=" * 60)
    if title:
        print(f"  {title}")
        print("=" * 60)


def demo_question_sanitizer():
    """演示问题脱敏"""
    print_separator("Demo 1: Question Sanitizer")

    sanitizer = QuestionSanitizer()

    # 测试用例
    test_questions = [
        "My Python code has a timeout error when connecting to MongoDB. Contact: 15951865326",
        "Project Alpha-2024 server IP 192.168.1.100 connection failed, help!",
        "API call failed with api_key='sk-abcd1234efgh5678' - what to do?",
        "Docker container on server 10.0.0.1 cannot start, permission denied error",
    ]

    for i, question in enumerate(test_questions, 1):
        print(f"\n--- Test Case {i} ---")
        print(f"Original: {question}")

        result = sanitizer.sanitize(question)

        print(f"Privacy Level: {result.privacy_level.upper()}")
        print(f"Sanitized: {result.sanitized}")
        print(f"Detected: {list(result.substitutions.values())}")

        if result.generalization_suggestions:
            print("Suggestions:")
            for suggestion in result.generalization_suggestions:
                print(f"  - {suggestion}")


def demo_platform_selector():
    """演示平台选择"""
    print_separator("Demo 2: Platform Selector")

    selector = PlatformSelector()

    test_cases = [
        ("Python MongoDB connection timeout how to fix?", None, None),
        ("React vs Vue for enterprise admin system?", "en", None),
        ("How to quickly set up a machine learning project?", None, None),
        ("Docker container memory overflow error?", None, None),
    ]

    for question, lang, platforms in test_cases:
        print(f"\nQuestion: {question}")

        result = selector.select(
            question=question,
            preferred_language=lang,
            preferred_platforms=platforms
        )

        platform_info = selector.get_platform_info(result.primary_platform)

        print(f"  Type: {result.question_type.value}")
        print(f"  Platform: {platform_info.name if platform_info else result.primary_platform.value}")
        print(f"  Confidence: {result.confidence:.0%}")
        print(f"  Tags: {', '.join(result.suggested_tags)}")


def demo_question_generator():
    """演示提问生成"""
    print_separator("Demo 3: Question Generator")

    sanitizer = QuestionSanitizer()
    generator = QuestionGenerator()
    selector = PlatformSelector()

    question = "Python MongoDB timeout error, code: MongoClient('mongodb://localhost')"

    print(f"Question: {question}\n")

    # Sanitize
    sanitized = sanitizer.sanitize(question)

    # Select platform
    selection = selector.select(question)

    # Generate post
    context = {
        'error_message': 'timeout error',
        'code': "MongoClient('mongodb://localhost:27017')",
        'os': 'Windows 11',
        'language': 'Python 3.11',
        'framework': 'PyMongo',
    }

    post = generator.generate(
        sanitized_question=sanitized,
        platform=selection.primary_platform,
        question_type=selection.question_type,
        context=context
    )

    print(f"Platform: {post.platform.value}")
    print(f"\nTitle: {post.title}")
    print(f"\nBody Preview:\n{post.body[:400]}...")
    print(f"\nTags: {', '.join(post.tags)}")


def demo_answer_monitor():
    """演示答案监控"""
    print_separator("Demo 4: Answer Monitor")

    monitor = AnswerMonitor()

    # Publish a simulated post
    post = monitor.publish_post(
        platform=Platform.STACKOVERFLOW,
        title="Python MongoDB connection timeout",
        body="Having timeout issues...",
        tags=["python", "mongodb", "timeout"]
    )

    print(f"Published Post ID: {post.post_id}")
    print(f"URL: {post.post_url}")
    print(f"Status: {post.status.value}")

    # Check status
    print("\nMonitoring for new answers...")
    time.sleep(1)

    status = monitor.get_post_status(post.post_id)
    if status:
        print(f"Current answers: {len(status.answers)}")


def demo_answer_aggregator():
    """演示答案整合"""
    print_separator("Demo 5: Answer Aggregator")

    aggregator = AnswerAggregator()

    # Simulate posts with answers
    from business.smart_help_system.answer_monitor import MonitoredPost, Answer, MonitorStatus

    # Create simulated posts
    post1 = MonitoredPost(
        post_id="so_123",
        platform=Platform.STACKOVERFLOW,
        post_url="https://stackoverflow.com/questions/123",
        title="Python MongoDB timeout",
        status=MonitorStatus.ANSWERED,
        posted_at=datetime.now(),
        last_checked_at=datetime.now(),
        answers=[
            Answer(
                answer_id="a1",
                author="user123",
                author_reputation=1500,
                content="Try increasing timeout: MongoClient(connectTimeoutMS=30000)",
                upvotes=45,
                is_accepted=True,
                posted_at=datetime.now()
            ),
            Answer(
                answer_id="a2",
                author="expert456",
                author_reputation=5000,
                content="Could be network/firewall issue",
                upvotes=20,
                is_accepted=False,
                posted_at=datetime.now()
            ),
        ]
    )

    post2 = MonitoredPost(
        post_id="csdn_456",
        platform=Platform.CSDN,
        post_url="https://blog.csdn.net/question/456",
        title="MongoDB Connection Timeout",
        status=MonitorStatus.ANSWERED,
        posted_at=datetime.now(),
        last_checked_at=datetime.now(),
        answers=[
            Answer(
                answer_id="a3",
                author="zhang_g",
                author_reputation=800,
                content="Try using connection pool instead",
                upvotes=15,
                is_accepted=False,
                posted_at=datetime.now()
            ),
        ]
    )

    # Aggregate
    aggregated = aggregator.aggregate(
        posts=[post1, post2],
        original_question="Python MongoDB timeout"
    )

    print(f"Aggregated {len(aggregated.sources)} sources")
    print(f"Confidence: {aggregated.confidence:.0%}")
    print(f"\nSummary: {aggregated.summary}")

    if aggregated.key_points:
        print(f"\nKey Points:")
        for point in aggregated.key_points[:3]:
            print(f"  - {point}")

    # Generate user-friendly report
    report = aggregator.generate_user_friendly_report(
        aggregated, "Python MongoDB timeout"
    )
    print(f"\n--- User Report Preview ---\n{report[:500]}...")


def demo_full_workflow():
    """演示完整工作流"""
    print_separator("Demo 6: Full Workflow")

    controller = SmartHelpController()

    question = """
    My project has an issue when calling OpenAI API.
    Error: RateLimitError for api_key='sk-xxxxx'

    Code:
    ```python
    import openai
    openai.api_key = 'sk-xxxxx'
    response = openai.ChatCompletion.create(model='gpt-4', messages=[...])
    ```

    Environment: macOS + Python 3.11. How to solve this?
    """

    context = {
        'error_message': 'RateLimitError: Rate limit reached',
        'code': "openai.ChatCompletion.create(...)",
        'os': 'macOS',
        'language': 'Python 3.11',
        'framework': 'OpenAI SDK',
    }

    print("Original Question (sanitized):")
    print(question[:200] + "...\n")

    # Create request
    request = controller.create_help_request(question, context)

    # Execute
    request = controller.execute_help_request(request, auto_publish=True)

    print(f"Request ID: {request.request_id}")
    print(f"Status: {controller.get_status_description(request.status)}")

    if request.platform_selection:
        platform_info = controller.platform_selector.get_platform_info(
            request.platform_selection.primary_platform
        )
        print(f"Platform: {platform_info.name if platform_info else 'Unknown'}")

    if request.generated_post:
        print(f"Title: {request.generated_post.title}")

    print(f"\nPublished posts: {len(request.monitored_posts)}")
    for post in request.monitored_posts:
        print(f"  - {post.platform.value}: {post.post_url}")


def main():
    """主函数"""
    print("""
+============================================================+
|                                                              |
|        Smart Help System - Demo                             |
|                                                              |
|        Concept: Auto-post to communities when AI fails      |
|                                                              |
+============================================================+
    """)

    try:
        demo_question_sanitizer()
        print("\n" + "-" * 40)
        print("Demo 1 Complete!")
        input("\nPress Enter to continue...")

        demo_platform_selector()
        print("\n" + "-" * 40)
        print("Demo 2 Complete!")
        input("\nPress Enter to continue...")

        demo_question_generator()
        print("\n" + "-" * 40)
        print("Demo 3 Complete!")
        input("\nPress Enter to continue...")

        demo_answer_monitor()
        print("\n" + "-" * 40)
        print("Demo 4 Complete!")
        input("\nPress Enter to continue...")

        demo_answer_aggregator()
        print("\n" + "-" * 40)
        print("Demo 5 Complete!")
        input("\nPress Enter to continue...")

        demo_full_workflow()

        print_separator()
        print("All Demos Complete!")
        print("\nNext Steps:")
        print("  1. Use UI panel: ui/help_request_panel.py")
        print("  2. Integrate with main_window.py")
        print("  3. Configure platform API credentials")

    except KeyboardInterrupt:
        print("\n\nDemo interrupted")
    except Exception as e:
        print(f"\n\nDemo error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
