"""
测试 SkillFactory 模块
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from loguru import logger
logger.remove()
logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)

from business.hermes_skill_factory import (
    SkillFactory,
    SkillConfig,
    ToolConfig,
    ParameterConfig
)


async def test_skill_factory():
    """测试技能工厂"""
    print("=" * 60)
    print("测试 Hermes Skill Factory")
    print("=" * 60)
    
    factory = SkillFactory()
    
    # 测试 1: 创建工具配置
    print("\n[1] 测试创建工具配置")
    tool_config = factory.create_tool_config(
        name="weather_query",
        description="查询天气信息",
        category="general",
        node_type="deterministic",
        parameters=[
            {
                "name": "city",
                "type": "string",
                "description": "城市名称",
                "required": True
            },
            {
                "name": "date",
                "type": "string",
                "description": "查询日期（格式：YYYY-MM-DD）",
                "required": False,
                "default": "today"
            }
        ],
        examples=[
            {
                "input": {"city": "北京", "date": "2024-01-15"},
                "description": "查询北京指定日期的天气"
            }
        ]
    )
    print(f"✓ 创建工具配置: {tool_config.name}")
    print(f"  参数数量: {len(tool_config.parameters)}")
    
    # 测试 2: 验证配置
    print("\n[2] 测试验证配置")
    is_valid = factory.validate_tool_config(tool_config)
    print(f"✓ 配置验证: {'通过' if is_valid else '失败'}")
    
    # 测试 3: 生成工具代码
    print("\n[3] 测试生成工具代码")
    filepath = factory.generate_tool(tool_config)
    print(f"✓ 生成工具文件: {filepath}")
    
    # 测试 4: 注册工具
    print("\n[4] 测试注册工具")
    registered = factory.register_from_file(filepath)
    print(f"✓ 注册工具: {registered}")
    
    # 测试 5: 创建技能配置并保存
    print("\n[5] 测试创建技能配置")
    skill_config = factory.create_skill_config([tool_config])
    factory.save_config(skill_config, "weather_skills")
    print(f"✓ 创建并保存技能配置")
    
    # 测试 6: 创建并注册多个工具
    print("\n[6] 测试创建并注册工具")
    success = factory.create_and_register(
        name="news_search",
        description="搜索新闻资讯",
        category="search",
        node_type="deterministic",
        parameters=[
            {
                "name": "keyword",
                "type": "string",
                "description": "搜索关键词",
                "required": True
            },
            {
                "name": "count",
                "type": "integer",
                "description": "返回数量",
                "required": False,
                "default": 10
            }
        ]
    )
    print(f"✓ 创建并注册工具: {'成功' if success else '失败'}")
    
    # 测试 7: 获取统计信息
    print("\n[7] 测试获取统计信息")
    stats = factory.get_stats()
    print(f"✓ 已生成技能: {len(stats['generated_skills'])}")
    print(f"✓ 可用模板: {stats['available_templates']}")
    
    # 测试 8: 批量创建
    print("\n[8] 测试批量创建")
    # 创建测试配置文件
    test_config = SkillConfig([
        ToolConfig(
            name="stock_query",
            description="查询股票信息",
            category="general",
            parameters=[
                ParameterConfig(name="symbol", type="string", description="股票代码", required=True)
            ]
        ),
        ToolConfig(
            name="calculator",
            description="计算器工具",
            category="utility",
            parameters=[
                ParameterConfig(name="expression", type="string", description="数学表达式", required=True)
            ]
        )
    ])
    factory.save_config(test_config, "batch_test")
    
    result = factory.batch_create_from_config(
        os.path.join(factory._config_dir, "batch_test.yaml"),
        register=True
    )
    print(f"✓ 批量创建结果: {'成功' if result['success'] else '失败'}")
    print(f"  生成文件数: {result['generated_count']}")
    print(f"  注册文件数: {result['registered_count']}")
    
    # 测试 9: 列出模板
    print("\n[9] 测试列出模板")
    templates = factory.list_templates()
    print(f"✓ 可用模板: {templates}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_skill_factory())