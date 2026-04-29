"""工作流生成器

基于用户输入的任务描述，自动生成相应的工作流
"""

import re
from typing import Optional, List, Dict, Any

from ..models.workflow import Workflow
from ..registry.ai_templates import register_ai_templates


class WorkflowGenerator:
    """工作流生成器
    
    基于用户输入的任务描述，自动生成相应的工作流
    """
    
    def __init__(self):
        """初始化工作流生成器"""
        # 注册 AI 工作流模板
        self.templates = register_ai_templates()
        
        # 任务类型匹配规则
        self.task_patterns = {
            # 文本分类
            r"分类.*文本|文本.*分类|classify.*text|text.*classify": "text_classification",
            
            # 情感分析
            r"情感.*分析|分析.*情感|sentiment.*analysis|analysis.*sentiment": "sentiment_analysis",
            
            # 问答系统
            r"问答|question.*answer|answer.*question|QA|qa": "question_answering",
            
            # 文本摘要
            r"摘要|summarize|summary|summarization": "text_summarization",
            
            # 翻译
            r"翻译|translate|translation": "translation",
            
            # 数据处理
            r"数据.*处理|处理.*数据|data.*process|process.*data": "data_processing",
            
            # 图像描述
            r"图像.*描述|描述.*图像|image.*caption|caption.*image": "image_captioning",
            
            # 代码生成
            r"代码.*生成|生成.*代码|code.*generate|generate.*code": "code_generation"
        }
    
    def generate_from_task(self, task_description: str) -> Optional[Workflow]:
        """根据任务描述生成工作流
        
        Args:
            task_description: 任务描述
            
        Returns:
            生成的工作流，或 None 如果无法匹配
        """
        # 转换为小写进行匹配
        task_lower = task_description.lower()
        
        # 匹配任务类型
        matched_template = None
        for pattern, template_name in self.task_patterns.items():
            if re.search(pattern, task_lower):
                matched_template = template_name
                break
        
        if matched_template and matched_template in self.templates:
            # 返回匹配的模板
            return self.templates[matched_template]
        
        # 如果没有匹配到模板，尝试生成自定义工作流
        return self._generate_custom_workflow(task_description)
    
    def _generate_custom_workflow(self, task_description: str) -> Optional[Workflow]:
        """生成自定义工作流
        
        Args:
            task_description: 任务描述
            
        Returns:
            生成的工作流
        """
        # 基本工作流结构
        workflow = Workflow(
            id=f"custom_{hash(task_description) % 10000}",
            name="自定义工作流",
            description=task_description,
            nodes=[],
            connections=[]
        )
        
        # 添加输入节点
        input_node = {
            "id": "input",
            "type": "input",
            "name": "输入",
            "position": {"x": 100, "y": 100},
            "config": {
                "variable_name": "input",
                "variable_type": "string"
            }
        }
        workflow.nodes.append(input_node)
        
        # 添加 LLM 节点
        llm_node = {
            "id": "llm",
            "type": "llm",
            "name": "AI 处理",
            "position": {"x": 300, "y": 100},
            "config": {
                "model": "gpt-4",
                "temperature": 0.7,
                "max_tokens": 1000
            }
        }
        workflow.nodes.append(llm_node)
        
        # 添加输出节点
        output_node = {
            "id": "output",
            "type": "output",
            "name": "输出",
            "position": {"x": 500, "y": 100},
            "config": {
                "variable_name": "output"
            }
        }
        workflow.nodes.append(output_node)
        
        # 添加连接
        connections = [
            {"source": "input", "target": "llm", "source_port": "output", "target_port": "prompt"},
            {"source": "llm", "target": "output", "source_port": "response", "target_port": "input"}
        ]
        workflow.connections.extend(connections)
        
        return workflow
    
    def generate_from_template(self, template_name: str) -> Optional[Workflow]:
        """从模板生成工作流
        
        Args:
            template_name: 模板名称
            
        Returns:
            生成的工作流，或 None 如果模板不存在
        """
        if template_name in self.templates:
            return self.templates[template_name]
        return None
    
    def list_templates(self) -> List[Dict[str, Any]]:
        """列出所有可用的模板
        
        Returns:
            模板列表，每个模板包含 id, name, description
        """
        templates = []
        for template_id, workflow in self.templates.items():
            templates.append({
                "id": template_id,
                "name": workflow.name,
                "description": workflow.description
            })
        return templates


# 导出工作流生成器
def get_workflow_generator() -> WorkflowGenerator:
    """获取工作流生成器实例
    
    Returns:
        工作流生成器实例
    """
    return WorkflowGenerator()


# 导出函数
__all__ = ['WorkflowGenerator', 'get_workflow_generator']
