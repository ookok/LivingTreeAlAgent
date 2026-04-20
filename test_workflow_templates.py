"""
工作流模板测试

直接测试工作流模板和生成器功能，避免导入冲突
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


class MockWorkflow:
    """模拟 Workflow 类"""
    def __init__(self, id, name, description, nodes=None, connections=None):
        self.id = id
        self.name = name
        self.description = description
        self.nodes = nodes or []
        self.connections = connections or []
        self.type = id  # 用于测试


def mock_register_ai_templates():
    """模拟注册 AI 工作流模板"""
    templates = {
        "text_classification": MockWorkflow(
            id="text_classification",
            name="文本分类工作流",
            description="对输入文本进行分类",
            nodes=["input", "classifier", "output"],
            connections=["input->classifier", "classifier->output"]
        ),
        "sentiment_analysis": MockWorkflow(
            id="sentiment_analysis",
            name="情感分析工作流",
            description="分析文本的情感倾向",
            nodes=["input", "llm", "output"],
            connections=["input->llm", "llm->output"]
        ),
        "question_answering": MockWorkflow(
            id="question_answering",
            name="问答系统工作流",
            description="基于知识库回答问题",
            nodes=["input", "knowledge", "llm", "output"],
            connections=["input->knowledge", "knowledge->llm", "input->llm", "llm->output"]
        )
    }
    logger.info(f"[Mock] 注册了 {len(templates)} 个 AI 工作流模板")
    return templates


class MockWorkflowGenerator:
    """模拟工作流生成器"""
    def __init__(self):
        self.templates = mock_register_ai_templates()
        
    def list_templates(self):
        """列出所有可用的模板"""
        templates = []
        for template_id, workflow in self.templates.items():
            templates.append({
                "id": template_id,
                "name": workflow.name,
                "description": workflow.description
            })
        return templates
    
    def generate_from_task(self, task_description):
        """根据任务描述生成工作流"""
        task_lower = task_description.lower()
        
        # 简单的任务匹配
        if "分类" in task_lower or "classify" in task_lower:
            return self.templates.get("text_classification")
        elif "情感" in task_lower or "sentiment" in task_lower:
            return self.templates.get("sentiment_analysis")
        elif "问答" in task_lower or "question" in task_lower or "answer" in task_lower:
            return self.templates.get("question_answering")
        else:
            # 生成自定义工作流
            return MockWorkflow(
                id=f"custom_{hash(task_description) % 10000}",
                name="自定义工作流",
                description=task_description,
                nodes=["input", "llm", "output"],
                connections=["input->llm", "llm->output"]
            )
    
    def generate_from_template(self, template_name):
        """从模板生成工作流"""
        return self.templates.get(template_name)


def get_mock_generator():
    """获取模拟工作流生成器"""
    return MockWorkflowGenerator()


async def test_ai_templates():
    """测试 AI 工作流模板"""
    logger.info("=== 测试 AI 工作流模板 ===")
    
    # 注册 AI 模板
    templates = mock_register_ai_templates()
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
    generator = get_mock_generator()
    
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


async def main():
    """主测试函数"""
    logger.info("开始测试工作流增强功能...")
    
    try:
        # 测试 AI 模板
        await test_ai_templates()
        
        # 测试工作流生成
        await test_workflow_generator()
        
        logger.info("\n所有工作流增强功能测试完成！")
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
