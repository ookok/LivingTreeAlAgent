"""
测试技能蒸馏集成模块
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from loguru import logger
logger.remove()
logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)

from client.src.business.skill_distillation import (
    DistillationIntegrator,
    SkillFinder,
    SkillConverter
)


async def test_distillation_integration():
    """测试蒸馏技能集成"""
    print("=" * 60)
    print("测试技能蒸馏集成模块")
    print("=" * 60)

    finder = SkillFinder()
    converter = SkillConverter()
    integrator = DistillationIntegrator()

    # 测试 1: 列出所有技能源
    print("\n[1] 测试列出所有技能源")
    sources = finder.get_all_sources()
    print(f"✓ 找到 {len(sources)} 个技能源")
    print(f"  类别: {finder.get_categories()}")

    # 测试 2: 搜索技能
    print("\n[2] 测试搜索技能")
    results = finder.search_sources("business")
    print(f"✓ 搜索 'business' 找到 {len(results)} 个技能")
    for r in results[:3]:
        print(f"  - {r.name}: {r.description}")

    # 测试 3: 获取技能详情
    print("\n[3] 测试获取技能详情")
    info = finder.get_source_info("munger-skill")
    print(f"✓ 获取技能详情: {info['name']}")
    print(f"  URL: {info['url']}")
    print(f"  类别: {info['category']}")
    print(f"  是否已安装: {info['installed']}")

    # 测试 4: 按类别获取技能
    print("\n[4] 测试按类别获取技能")
    thinking_skills = finder.get_sources_by_category("thinking")
    print(f"✓ 思维模型类技能: {len(thinking_skills)} 个")
    for skill in thinking_skills:
        print(f"  - {skill.name}")

    # 测试 5: 技能转换
    print("\n[5] 测试技能转换")
    test_json = '''{
        "name": "test_skill",
        "description": "测试技能",
        "category": "utility",
        "parameters": [
            {"name": "input", "type": "string", "description": "输入参数", "required": true}
        ],
        "examples": [{"input": "test", "output": "result"}]
    }'''
    converted = converter.convert_from_json(test_json)
    print(f"✓ JSON 转换成功")
    print(f"  名称: {converted['name']}")
    print(f"  参数数量: {len(converted['parameters'])}")

    # 测试 6: 获取统计信息
    print("\n[6] 测试获取统计信息")
    stats = integrator.get_stats()
    print(f"✓ 总技能源: {stats['total_sources']}")
    print(f"✓ 已安装: {stats['installed_count']}")
    print(f"✓ 类别分布: {stats['categories']}")

    # 测试 7: 获取技能状态
    print("\n[7] 测试获取技能状态")
    status = integrator.get_skill_status("steve-jobs-skill")
    print(f"✓ 技能状态: {status['name']} - {status['status']}")

    # 测试 8: 安装技能（需要 Git 环境）
    print("\n[8] 测试安装技能（演示模式）")
    print("  注意：实际安装需要 Git 环境和网络连接")
    print("  当前已安装技能:")
    installed = integrator.get_installed_skills()
    if installed:
        for skill in installed:
            print(f"    ✓ {skill['name']}")
    else:
        print("    暂无已安装技能")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_distillation_integration())