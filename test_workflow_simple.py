"""
简化的工作流增强功能测试

直接测试工作流模块，避免导入不必要的依赖
"""

import asyncio
import logging
import sys
import os

# 添加核心目录到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "core"))

# 直接导入工作流模块的组件
from living_tree_ai.workflow.registry.ai_templates import register_ai_templates
from living_tree_ai.workflow.engine.generator import get_workflow_generator
from living_tree_ai.workflow.registry.node_discovery import get_node_discoverer
from living_tree_ai.workflow.registry.node_registry import get_registry

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_ai_templates():
    """测试 AI 工作流模板"""
    logger.info("=== 测试 AI 工作流模板 ===")
    
    # 注册 AI 模板
    templates = register_ai_templates()
    logger.info(f"注册了 {len(templates)} 个 AI 工作流模板")
    
    # 打印模板信息
    for template_id, workflow in templates.items():
        logger.info(f"模板: {template_id} - {workflow.name}")
        logger.info(f"  描述: {workflow.description}")
        logger.info(f"  节点数: {len(workflow.nodes)}")
        logger.info(f"  连接数: {len(workflow.connections)}")
    
    logger.info("AI 工作流模板测试完成！")


async def test_workflow_generator():
    """测试工作流自动生成"""
    logger.info("\n=== 测试工作流自动生成 ===")
    
    # 获取工作流生成器
    generator = get_workflow_generator()
    
    # 测试模板列表
    templates = generator.list_templates()
    logger.info(f"可用模板: {len(templates)}")
    for template in templates:
        logger.info(f"  - {template['name']}: {template['description']}")
    
    # 测试基于任务描述生成工作流
    test_tasks = [
        "对文本进行情感分析",
        "生成一个 Python 函数",
        "回答用户问题",
        "总结一篇文章",
        "翻译一段文本"
    ]
    
    for task in test_tasks:
        logger.info(f"\n测试任务: {task}")
        workflow = generator.generate_from_task(task)
        if workflow:
            logger.info(f"  生成工作流: {workflow.name}")
            logger.info(f"  节点数: {len(workflow.nodes)}")
            logger.info(f"  连接数: {len(workflow.connections)}")
        else:
            logger.warning(f"  无法生成工作流")
    
    # 测试从模板生成工作流
    template_name = "text_classification"
    workflow = generator.generate_from_template(template_name)
    if workflow:
        logger.info(f"\n从模板生成工作流: {workflow.name}")
        logger.info(f"  节点数: {len(workflow.nodes)}")
        logger.info(f"  连接数: {len(workflow.connections)}")
    
    logger.info("工作流自动生成测试完成！")


async def test_node_discovery():
    """测试节点自动发现"""
    logger.info("\n=== 测试节点自动发现 ===")
    
    # 获取节点发现器
    discoverer = get_node_discoverer()
    
    # 发现节点
    nodes = discoverer.discover_nodes()
    logger.info(f"发现了 {len(nodes)} 个节点")
    
    # 按类别分组
    categories = {}
    for node in nodes:
        if node.category not in categories:
            categories[node.category] = []
        categories[node.category].append(node)
    
    # 打印节点信息
    for category, nodes_in_category in categories.items():
        logger.info(f"\n类别: {category} ({len(nodes_in_category)} 个节点)")
        for node in nodes_in_category:
            logger.info(f"  - {node.name} ({node.node_type})")
            logger.info(f"    描述: {node.description}")
            logger.info(f"    输入端口: {len(node.inputs)}")
            logger.info(f"    输出端口: {len(node.outputs)}")
    
    # 注册到注册表
    registry = get_registry()
    discoverer.register_discovered_nodes(registry)
    
    # 验证注册成功
    all_nodes = registry.get_all()
    logger.info(f"\n注册表中总节点数: {len(all_nodes)}")
    
    logger.info("节点自动发现测试完成！")


async def main():
    """主测试函数"""
    logger.info("开始测试工作流增强功能...")
    
    try:
        # 测试 AI 模板
        await test_ai_templates()
        
        # 测试工作流生成
        await test_workflow_generator()
        
        # 测试节点发现
        await test_node_discovery()
        
        logger.info("\n所有工作流增强功能测试完成！")
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
