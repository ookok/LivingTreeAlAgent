"""工作流模板管理器"""

import json
import os
from typing import Dict, List, Optional
from dataclasses import dataclass

from .models.workflow import Workflow


@dataclass
class WorkflowTemplate:
    """工作流模板"""
    template_id: str
    name: str
    description: str
    workflow: Workflow
    tags: List[str] = None
    author: str = ""
    version: str = "1.0.0"
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "template_id": self.template_id,
            "name": self.name,
            "description": self.description,
            "workflow": self.workflow.to_dict(),
            "tags": self.tags or [],
            "author": self.author,
            "version": self.version
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'WorkflowTemplate':
        """从字典创建模板"""
        workflow = Workflow.from_dict(data["workflow"])
        return cls(
            template_id=data["template_id"],
            name=data["name"],
            description=data["description"],
            workflow=workflow,
            tags=data.get("tags", []),
            author=data.get("author", ""),
            version=data.get("version", "1.0.0")
        )


class TemplateManager:
    """模板管理器"""
    
    def __init__(self, templates_dir: str = None):
        """
        初始化模板管理器
        
        Args:
            templates_dir: 模板存储目录
        """
        self.templates_dir = templates_dir or os.path.expanduser("~/.living_tree_ai/templates")
        os.makedirs(self.templates_dir, exist_ok=True)
    
    def save_template(self, template: WorkflowTemplate) -> str:
        """
        保存模板
        
        Args:
            template: 模板对象
            
        Returns:
            模板文件路径
        """
        template_path = os.path.join(self.templates_dir, f"{template.template_id}.json")
        with open(template_path, 'w', encoding='utf-8') as f:
            json.dump(template.to_dict(), f, indent=2, ensure_ascii=False)
        return template_path
    
    def load_template(self, template_id: str) -> Optional[WorkflowTemplate]:
        """
        加载模板
        
        Args:
            template_id: 模板ID
            
        Returns:
            模板对象，如果不存在返回None
        """
        template_path = os.path.join(self.templates_dir, f"{template_id}.json")
        if not os.path.exists(template_path):
            return None
        
        with open(template_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return WorkflowTemplate.from_dict(data)
    
    def list_templates(self) -> List[WorkflowTemplate]:
        """
        列出所有模板
        
        Returns:
            模板列表
        """
        templates = []
        for filename in os.listdir(self.templates_dir):
            if filename.endswith('.json'):
                template_id = filename[:-5]  # 移除 .json 后缀
                template = self.load_template(template_id)
                if template:
                    templates.append(template)
        return templates
    
    def delete_template(self, template_id: str) -> bool:
        """
        删除模板
        
        Args:
            template_id: 模板ID
            
        Returns:
            是否删除成功
        """
        template_path = os.path.join(self.templates_dir, f"{template_id}.json")
        if os.path.exists(template_path):
            os.remove(template_path)
            return True
        return False
    
    def export_template(self, template_id: str, output_path: str) -> bool:
        """
        导出模板
        
        Args:
            template_id: 模板ID
            output_path: 输出路径
            
        Returns:
            是否导出成功
        """
        template = self.load_template(template_id)
        if not template:
            return False
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(template.to_dict(), f, indent=2, ensure_ascii=False)
        return True
    
    def import_template(self, input_path: str) -> Optional[WorkflowTemplate]:
        """
        导入模板
        
        Args:
            input_path: 输入路径
            
        Returns:
            导入的模板对象，如果失败返回None
        """
        if not os.path.exists(input_path):
            return None
        
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        template = WorkflowTemplate.from_dict(data)
        self.save_template(template)
        return template


# 导出模块
__all__ = ['WorkflowTemplate', 'TemplateManager']
