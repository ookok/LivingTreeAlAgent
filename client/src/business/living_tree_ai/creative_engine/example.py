"""
分布式创作引擎使用示例
========================

本文件展示如何组合使用分布式创作引擎的各个模块。
"""

import asyncio


async def example_distributed_generation():
    """
    示例 1: 分布式内容生成

    同时调用多个 AI 节点生成不同风格的版本。
    """
    from .distributed_generator import (
        DistributedGenerator,
        GenerationType,
        ToneStyle,
        NodeCapability
    )

    # 创建生成器
    generator = DistributedGenerator(data_dir="./data/creative")

    # 注册多个创作节点
    generator.register_node(NodeCapability(
        node_id="claude-academic",
        node_name="Claude 学术节点",
        model_type="claude",
        supported_types=[GenerationType.TEXT, GenerationType.CODE],
        supported_tones=[ToneStyle.ACADEMIC, ToneStyle.TECHNICAL],
        latency_ms=200,
        cost_per_1k_tokens=0.008,
        reputation=0.95
    ))

    generator.register_node(NodeCapability(
        node_id="gpt-creative",
        node_name="GPT 创意节点",
        model_type="gpt",
        supported_types=[GenerationType.TEXT, GenerationType.CODE],
        supported_tones=[ToneStyle.CASUAL, ToneStyle.HUMOROUS, ToneStyle.CREATIVE],
        latency_ms=150,
        cost_per_1k_tokens=0.01,
        reputation=0.92
    ))

    generator.register_node(NodeCapability(
        node_id="local-fast",
        node_name="本地快速节点",
        model_type="local",
        supported_types=[GenerationType.TEXT],
        supported_tones=[ToneStyle.CASUAL],
        latency_ms=50,
        cost_per_1k_tokens=0,
        reputation=0.88
    ))

    # 设置风格锚点
    generator.set_style_anchor(ToneStyle.ACADEMIC, [
        "本研究旨在探讨分布式系统的一致性问题。",
        "实验结果表明，通过优化共识算法可以显著提升系统吞吐量。",
    ])

    # 并行生成多个版本
    result = await generator.generate_parallel(
        prompt="写一段关于量子计算的科普",
        generation_types=[GenerationType.TEXT],
        tones=[ToneStyle.ACADEMIC, ToneStyle.CASUAL, ToneStyle.HUMOROUS]
    )

    print(f"生成了 {len(result.versions)} 个版本")
    for version in result.versions:
        print(f"\n[{version.node_name}] ({version.tone.value}):")
        print(version.content[:200] + "...")

    # 混合编辑：合并不同版本的段落
    merged = result.merge_versions({
        ToneStyle.ACADEMIC: (0, 1),  # 学术版本的第一段
        ToneStyle.CASUAL: (1, 3)     # 通俗版本的第2-3段
    })
    print(f"\n混合编辑结果:\n{merged[:200]}...")

    return result


async def example_browser_integration():
    """
    示例 2: 浏览器内即圈即生

    处理用户在浏览器中选中的代码/文本，生成 AI 增强内容。
    """
    from .browser_integration import (
        BrowserIntegration,
        GenerationIntent
    )

    # 创建浏览器集成
    integration = BrowserIntegration(data_dir="./data/creative")

    # 模拟用户选中代码
    selected_code = """
def quicksort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quicksort(left) + middle + quicksort(right)
"""

    # 处理选中内容
    response = await integration.process_selection(
        selected_text=selected_code,
        html_element="<pre>...</pre>",
        page_url="https://example.com/sorting",
        page_title="排序算法示例",
        user_instruction="优化这段代码的性能"
    )

    print(f"生成请求 ID: {response.request_id}")
    print(f"内容类型: {response.content_type}")
    print(f"生成内容:\n{response.content}")
    print(f"执行命令: {response.execution_command}")
    print(f"建议: {response.suggestions}")

    # 生成注入脚本
    injection_script = await integration.setup_browser_injection(None)
    print(f"\n浏览器注入脚本长度: {len(injection_script)} 字符")


async def example_execution_validator():
    """
    示例 3: 执行即验证

    AI 生成的代码自动在沙箱中执行验证。
    """
    from .execution_validator import (
        ExecutionValidator,
        ExecutionLanguage,
        ExecutionMode
    )

    # 创建验证器
    validator = ExecutionValidator(data_dir="./data/creative")

    # 注册边缘节点
    validator.register_node("tokyo-edge-001", {
        "name": "东京边缘节点",
        "capabilities": ["python", "javascript"],
        "online": True,
        "load": 0.3
    })

    validator.register_node("singapore-edge-001", {
        "name": "新加坡边缘节点",
        "capabilities": ["python", "node"],
        "online": True,
        "load": 0.5
    })

    # AI 生成的代码
    code = """
import requests

def fetch_user_data(user_id):
    response = requests.get(f"https://api.example.com/users/{user_id}")
    return response.json()

print(fetch_user_data(123))
"""

    # 检测依赖
    language = validator.detect_language(code)
    dependencies = validator.detect_dependencies(code, language)
    print(f"检测到的语言: {language.value}")
    print(f"检测到的依赖:")
    for dep in dependencies:
        print(f"  - {dep['name']} ({dep['type']})")
        print(f"    安装命令: {dep['install_cmd']}")
        print(f"    建议: {dep['node_suggestion']}")

    # 验证代码（本地沙箱执行）
    result = await validator.validate_code(
        code=code,
        language=language,
        mode=ExecutionMode.SANDBOX,
        timeout_seconds=10
    )

    print(f"\n执行结果:")
    print(f"  状态: {result.status.value}")
    print(f"  执行时间: {result.execution_time_ms:.2f}ms")
    if result.stderr:
        print(f"  错误: {result.stderr[:200]}")
    print(f"  建议: {result.suggestions}")

    # 如果成功，自动 Git 提交
    if result.is_success():
        commit_sha = await validator.git_commit(
            code=code,
            message="AI: 添加用户数据获取函数",
            file_path="src/api.py"
        )
        print(f"  Git Commit: {commit_sha}")


async def example_style_migrator():
    """
    示例 4: P2P 知识库与风格迁移

    学习用户的写作风格，并使用该风格生成内容。
    """
    from .style_migrator import StyleMigrator

    # 创建风格迁移器
    migrator = StyleMigrator(data_dir="./data/creative")

    # 学习风格（需要有文档文件）
    # profile = await migrator.learn_style(
    #     documents=["path/to/blog_post1.md", "path/to/blog_post2.md"],
    #     profile_name="我的技术博客风格"
    # )

    # 获取已有画像
    profiles = migrator.get_profiles()
    print(f"现有风格画像: {len(profiles)} 个")
    for profile in profiles:
        print(f"  - {profile.name} (置信度: {profile.confidence:.2%})")

    # 存储知识条目
    entry = await migrator.store_knowledge(
        content="通过消息队列实现系统解耦是微服务架构中的常见模式。",
        content_type="document",
        tags=["架构", "消息队列", "微服务"],
        source="内部技术分享",
        source_url="internal://tech-share/001"
    )
    print(f"\n已存储知识条目: {entry.entry_id}")

    # 检索相关知识
    results = await migrator.retrieve_knowledge(
        query="如何设计微服务架构",
        top_k=3,
        tags=["架构"]
    )
    print(f"\n检索到 {len(results)} 条相关知识:")
    for r in results:
        print(f"  - [{r.tags}] {r.content[:50]}... (访问: {r.access_count})")

    # 获取知识库统计
    stats = migrator.get_knowledge_stats()
    print(f"\n知识库统计:")
    print(f"  总条目: {stats['total_entries']}")
    print(f"  按类型: {stats['by_content_type']}")
    print(f"  总标签: {stats['total_tags']}")


async def example_gamification():
    """
    示例 5: 游戏化与三维创作空间

    创建思维导图空间，用语音命令创作。
    """
    from .gamification import (
        CreativeGamification,
        SpaceType,
        NodeType
    )

    # 创建游戏化系统
    gamification = CreativeGamification(data_dir="./data/creative")

    # 创建思维导图空间
    space = await gamification.create_space(
        name="分布式系统设计",
        space_type=SpaceType.MIND_MAP,
        owner_id="alice"
    )
    print(f"创建空间: {space.name} ({space.space_id})")

    # 添加根节点
    root = await gamification.add_node(
        space_id=space.space_id,
        node_type=NodeType.IDEA,
        title="分布式系统概述",
        content="包含一致性、可用性、分区容错性",
        author_id="alice"
    )
    print(f"添加根节点: {root.title} ({root.node_id})")

    # 添加子节点
    child1 = await gamification.add_node(
        space_id=space.space_id,
        node_type=NodeType.TASK,
        title="一致性方案",
        content="Paxos、Raft、ZAB 等共识算法",
        parent_id=root.node_id,
        author_id="alice"
    )

    child2 = await gamification.add_node(
        space_id=space.space_id,
        node_type=NodeType.TASK,
        title="CAP 定理",
        content="一致性、可用性、分区容错性无法同时满足",
        parent_id=root.node_id,
        author_id="alice"
    )

    child3 = await gamification.add_node(
        space_id=space.space_id,
        node_type=NodeType.MILESTONE,
        title="设计评审",
        content="完成架构设计文档",
        parent_id=root.node_id,
        author_id="alice"
    )

    # 添加 AI 建议节点
    ai_suggestion = await gamification.add_node(
        space_id=space.space_id,
        node_type=NodeType.AI_SUGGESTION,
        title="建议添加监控",
        content="建议引入 Prometheus + Grafana 进行监控",
        parent_id=child1.node_id,
        author_id="ai"
    )

    print(f"添加子节点完成，共 {len(space.nodes)} 个节点")

    # AI 自动整理
    report = await gamification.auto_organize(space.space_id)
    print(f"\nAI 整理报告:")
    print(f"  新增连接: {report['added_connections']}")
    print(f"  重新定位: {report['repositioned_nodes']}")
    print(f"  建议: {report['suggestions']}")

    # 语音命令
    voice_result = await gamification.voice_command(
        space_id=space.space_id,
        command="添加节点 性能优化策略",
        user_id="alice"
    )
    print(f"\n语音命令结果: {voice_result['message']}")

    # 获取空间摘要
    summary = gamification.get_space_summary(space.space_id)
    print(f"\n空间摘要:")
    print(f"  总节点: {summary['total_nodes']}")
    print(f"  按类型: {summary['by_type']}")
    print(f"  按状态: {summary['by_status']}")

    # 导出 3D 可视化数据
    viz_data = gamification.export_3d_visualization(space.space_id)
    print(f"\n3D 可视化数据:")
    print(f"  节点数: {viz_data['metadata']['total_nodes']}")
    print(f"  连接数: {len(viz_data['connections'])} + {len(viz_data['node_connections'])}")

    # 获取成就状态
    print(f"\n成就系统:")
    print(f"  已解锁成就:")
    for achievement in gamification._achievements.values():
        if achievement.unlocked_at:
            print(f"    - {achievement.icon} {achievement.name}")
    print(f"  进行中成就:")
    for achievement in gamification._achievements.values():
        if not achievement.unlocked_at and achievement.progress > 0:
            print(f"    - {achievement.name}: {achievement.progress:.0%}")


async def main():
    """运行所有示例"""
    print("=" * 60)
    print("分布式创作引擎示例")
    print("=" * 60)

    # 示例 1: 分布式内容生成
    print("\n\n>>> 示例 1: 分布式内容生成")
    print("-" * 40)
    await example_distributed_generation()

    # 示例 2: 浏览器内即圈即生
    print("\n\n>>> 示例 2: 浏览器内即圈即生")
    print("-" * 40)
    await example_browser_integration()

    # 示例 3: 执行即验证
    print("\n\n>>> 示例 3: 执行即验证")
    print("-" * 40)
    await example_execution_validator()

    # 示例 4: 风格迁移
    print("\n\n>>> 示例 4: P2P 知识库与风格迁移")
    print("-" * 40)
    await example_style_migrator()

    # 示例 5: 游戏化
    print("\n\n>>> 示例 5: 游戏化与三维创作空间")
    print("-" * 40)
    await example_gamification()

    print("\n\n" + "=" * 60)
    print("所有示例运行完成!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())