"""
browser-use 工作流测试

测试 browser-use 节点在工作流中的使用
"""

import asyncio
import logging
import sys
import os

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_browser_use_workflow():
    """测试 browser-use 工作流"""
    logger.info("=== 测试 browser-use 工作流 ===")
    
    try:
        # 导入工作流模块
        from core.workflow import (
            WorkflowDesigner, WorkflowEngine, get_workflow_engine,
            create_browser_use_node
        )
        
        # 创建工作流设计器
        designer = WorkflowDesigner()
        
        # 创建新工作流
        workflow = designer.create_workflow(
            name="浏览器自动化测试工作流",
            description="测试 browser-use 浏览器自动化功能"
        )
        
        # 添加 browser-use 节点
        browser_node = create_browser_use_node(
            name="导航到示例网站",
            task_type="navigate",
            task_params={
                "url": "https://example.com"
            },
            result_variable="navigate_result"
        )
        workflow.nodes.append(browser_node)
        
        # 添加内容提取节点
        extract_node = create_browser_use_node(
            name="提取页面内容",
            task_type="extract_content",
            task_params={
                "url": "https://example.com"
            },
            result_variable="content_result"
        )
        workflow.nodes.append(extract_node)
        
        # 添加搜索节点
        search_node = create_browser_use_node(
            name="搜索浏览器自动化",
            task_type="search",
            task_params={
                "query": "browser automation",
                "engine": "google"
            },
            result_variable="search_result"
        )
        workflow.nodes.append(search_node)
        
        # 连接节点
        designer.connect(workflow.nodes[0].id, browser_node.id)  # 开始 -> 导航
        designer.connect(browser_node.id, extract_node.id)       # 导航 -> 提取
        designer.connect(extract_node.id, search_node.id)        # 提取 -> 搜索
        designer.connect(search_node.id, workflow.nodes[-1].id)  # 搜索 -> 结束
        
        # 验证工作流
        validation = designer.validate()
        logger.info(f"工作流验证结果: {validation}")
        
        if not validation["valid"]:
            logger.error("工作流验证失败")
            return
        
        # 获取工作流引擎
        engine = get_workflow_engine()
        
        # 启动工作流
        logger.info("启动工作流...")
        execution = await engine.start_workflow(
            workflow=workflow,
            initiator_id="test_user",
            initiator_name="测试用户"
        )
        
        logger.info(f"工作流启动成功，执行 ID: {execution.id}")
        logger.info(f"工作流状态: {execution.status}")
        
        # 模拟完成任务
        for task in execution.pending_tasks:
            logger.info(f"完成任务: {task['name']}")
            execution = await engine.complete_task(
                execution=execution,
                task_id=task['id'],
                action="complete",
                user_id="test_user",
                user_name="测试用户"
            )
        
        logger.info(f"工作流执行完成，状态: {execution.status}")
        
        # 检查结果
        if "navigate_result" in execution.context:
            logger.info(f"导航结果: {execution.context['navigate_result']}")
        if "content_result" in execution.context:
            logger.info(f"内容提取结果: {execution.context['content_result']}")
        if "search_result" in execution.context:
            logger.info(f"搜索结果: {execution.context['search_result']}")
        
        logger.info("\nbrowser-use 工作流测试完成！")
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """主测试函数"""
    logger.info("开始测试 browser-use 工作流...")
    
    try:
        # 测试 browser-use 工作流
        await test_browser_use_workflow()
        
        logger.info("\n所有 browser-use 工作流测试完成！")
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
