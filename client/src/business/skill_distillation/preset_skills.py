"""
预置蒸馏技能到 Hermes Skill Factory

将所有蒸馏技能转换为可调用的工具并注册到系统。
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from loguru import logger
logger.remove()
logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)

from client.src.business.hermes_skill_factory import SkillFactory
from client.src.business.skill_distillation import (
    DEFAULT_SKILL_SOURCES,
    register_all_tools,
    get_stats,
    get_distilled_tools
)


def preset_distilled_skills():
    """预置蒸馏技能到系统"""
    print("=" * 60)
    print("预置蒸馏技能到 Hermes Skill Factory")
    print("=" * 60)
    
    # 创建技能工厂
    factory = SkillFactory()
    
    print("\n[1] 正在创建蒸馏技能工具...")
    
    created_count = 0
    for source in DEFAULT_SKILL_SOURCES:
        print(f"  创建: {source.name}")
        
        # 创建工具配置
        factory.create_and_register(
            name=source.name,
            description=source.description,
            category=source.category,
            node_type="deterministic",
            parameters=[
                {
                    "name": "query",
                    "type": "string",
                    "description": "查询内容",
                    "required": False
                },
                {
                    "name": "mode",
                    "type": "string",
                    "description": "执行模式",
                    "required": False,
                    "default": "default"
                }
            ],
            examples=[
                {
                    "input": {"query": "分析问题", "mode": "analyze"},
                    "description": f"使用 {source.name} 分析问题"
                }
            ]
        )
        created_count += 1
    
    print(f"\n✓ 成功创建 {created_count} 个蒸馏技能工具")
    
    # 通过 DistilledSkillTool 注册到技能注册中心
    print("\n[2] 正在注册到技能注册中心...")
    registered_count = register_all_tools()
    print(f"✓ 成功注册 {registered_count} 个蒸馏技能")
    
    # 显示统计信息
    print("\n[3] 蒸馏技能统计:")
    stats = get_stats()
    print(f"  总技能数: {stats['total_skills']}")
    print(f"  类别分布:")
    for category, count in stats['categories'].items():
        print(f"    - {category}: {count} 个")
    
    # 列出所有技能
    print("\n[4] 已预置的蒸馏技能:")
    tools = get_distilled_tools()
    for tool in tools:
        print(f"  ✓ [{tool.category}] {tool.name}: {tool.description}")
    
    print("\n" + "=" * 60)
    print("蒸馏技能预置完成!")
    print("=" * 60)
    
    return {
        "success": True,
        "created_count": created_count,
        "registered_count": registered_count,
        "total_skills": stats['total_skills'],
        "categories": stats['categories']
    }


def create_skill_config_file():
    """创建技能配置文件"""
    from client.src.business.skill_distillation import DistillationConfig
    
    config = DistillationConfig(sources=DEFAULT_SKILL_SOURCES)
    
    config_dir = os.path.join(
        os.path.dirname(__file__),
        "configs"
    )
    os.makedirs(config_dir, exist_ok=True)
    
    config_path = os.path.join(config_dir, "distilled_skills.yaml")
    config.save_to_yaml(config_path)
    
    logger.info(f"技能配置文件已保存: {config_path}")
    return config_path


if __name__ == "__main__":
    # 创建配置文件
    create_skill_config_file()
    
    # 预置技能
    result = preset_distilled_skills()
    
    if result["success"]:
        sys.exit(0)
    else:
        sys.exit(1)