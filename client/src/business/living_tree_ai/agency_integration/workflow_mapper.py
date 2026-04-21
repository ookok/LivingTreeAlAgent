"""工作流程映射器 - 将 agency-agents 工作流程映射为任务链"""

import json
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

import sys
import os

# 添加父目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from node import Task


@dataclass
class WorkflowStep:
    """工作流程步骤"""
    name: str
    description: str
    task_type: str
    required_skills: List[str]
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]


@dataclass
class Workflow:
    """工作流程"""
    name: str
    description: str
    steps: List[WorkflowStep]
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]


class WorkflowMapper:
    """工作流程映射器"""
    
    def __init__(self, data_dir: str = "~/.living_tree_ai/agency"):
        """初始化工作流程映射器"""
        self.data_dir = os.path.expanduser(data_dir)
        self.workflows: Dict[str, Workflow] = {}
        
        # 确保数据目录存在
        os.makedirs(self.data_dir, exist_ok=True)
        
        # 加载内置工作流程
        self.load_builtin_workflows()
        
    def load_builtin_workflows(self):
        """加载内置工作流程"""
        # 内置工作流程定义
        builtin_workflows = [
            {
                "name": "full_stack_dev",
                "description": "全栈开发工作流程",
                "steps": [
                    {
                        "name": "需求分析",
                        "description": "分析用户需求",
                        "task_type": "inference",
                        "required_skills": ["需求分析", "系统设计"],
                        "input_schema": {"requirements": "string"},
                        "output_schema": {"analysis": "string", "technical_plan": "string"}
                    },
                    {
                        "name": "后端开发",
                        "description": "开发后端服务",
                        "task_type": "inference",
                        "required_skills": ["Python", "Django", "API设计"],
                        "input_schema": {"technical_plan": "string"},
                        "output_schema": {"backend_code": "string", "api_docs": "string"}
                    },
                    {
                        "name": "前端开发",
                        "description": "开发前端界面",
                        "task_type": "inference",
                        "required_skills": ["JavaScript", "React", "UI设计"],
                        "input_schema": {"technical_plan": "string"},
                        "output_schema": {"frontend_code": "string", "ui_components": "string"}
                    },
                    {
                        "name": "测试验证",
                        "description": "测试系统功能",
                        "task_type": "inference",
                        "required_skills": ["测试", "调试"],
                        "input_schema": {"backend_code": "string", "frontend_code": "string"},
                        "output_schema": {"test_results": "string", "bugs": "array"}
                    },
                    {
                        "name": "部署发布",
                        "description": "部署系统",
                        "task_type": "coordination",
                        "required_skills": ["DevOps", "部署"],
                        "input_schema": {"backend_code": "string", "frontend_code": "string"},
                        "output_schema": {"deployment_status": "string", "url": "string"}
                    }
                ],
                "input_schema": {"requirements": "string"},
                "output_schema": {"complete_system": "string", "url": "string"}
            },
            {
                "name": "ui_design",
                "description": "UI设计工作流程",
                "steps": [
                    {
                        "name": "需求分析",
                        "description": "分析设计需求",
                        "task_type": "inference",
                        "required_skills": ["需求分析", "用户研究"],
                        "input_schema": {"requirements": "string"},
                        "output_schema": {"user_stories": "array", "design_goals": "array"}
                    },
                    {
                        "name": "原型设计",
                        "description": "创建界面原型",
                        "task_type": "inference",
                        "required_skills": ["原型设计", "Figma"],
                        "input_schema": {"user_stories": "array"},
                        "output_schema": {"wireframes": "string", "user_flow": "string"}
                    },
                    {
                        "name": "视觉设计",
                        "description": "设计视觉风格",
                        "task_type": "inference",
                        "required_skills": ["视觉设计", "色彩理论"],
                        "input_schema": {"wireframes": "string"},
                        "output_schema": {"design_system": "string", "mockups": "string"}
                    },
                    {
                        "name": "设计交付",
                        "description": "交付设计资产",
                        "task_type": "storage",
                        "required_skills": ["设计交付", "文件管理"],
                        "input_schema": {"design_system": "string", "mockups": "string"},
                        "output_schema": {"design_assets": "string", "style_guide": "string"}
                    }
                ],
                "input_schema": {"requirements": "string"},
                "output_schema": {"design_assets": "string", "style_guide": "string"}
            }
        ]
        
        for workflow_data in builtin_workflows:
            steps = [WorkflowStep(**step_data) for step_data in workflow_data["steps"]]
            workflow = Workflow(
                name=workflow_data["name"],
                description=workflow_data["description"],
                steps=steps,
                input_schema=workflow_data["input_schema"],
                output_schema=workflow_data["output_schema"]
            )
            self.workflows[workflow.name] = workflow
        
        print(f"[WorkflowMapper] 加载了 {len(builtin_workflows)} 个内置工作流程")
    
    def load_workflows(self, workflows_dir: Optional[str] = None):
        """从目录加载工作流程"""
        if workflows_dir is None:
            workflows_dir = os.path.join(self.data_dir, "workflows")
        
        if not os.path.exists(workflows_dir):
            print(f"[WorkflowMapper] 工作流程目录不存在: {workflows_dir}")
            return
        
        for filename in os.listdir(workflows_dir):
            if filename.endswith('.json'):
                file_path = os.path.join(workflows_dir, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        workflow_data = json.load(f)
                    
                    steps = [WorkflowStep(**step_data) for step_data in workflow_data["steps"]]
                    workflow = Workflow(
                        name=workflow_data["name"],
                        description=workflow_data["description"],
                        steps=steps,
                        input_schema=workflow_data["input_schema"],
                        output_schema=workflow_data["output_schema"]
                    )
                    
                    self.workflows[workflow.name] = workflow
                    print(f"[WorkflowMapper] 加载工作流程: {workflow.name}")
                except Exception as e:
                    print(f"[WorkflowMapper] 加载工作流程失败 {filename}: {e}")
    
    def map_to_task_chain(self, workflow_name: str, input_data: Dict[str, Any]) -> List[Task]:
        """将工作流程映射为任务链"""
        if workflow_name not in self.workflows:
            print(f"[WorkflowMapper] 工作流程不存在: {workflow_name}")
            return []
        
        workflow = self.workflows[workflow_name]
        task_chain = []
        
        # 生成任务链
        for i, step in enumerate(workflow.steps):
            # 构建任务输入数据
            task_input = {
                "step_name": step.name,
                "step_description": step.description,
                "input_data": input_data,
                "step_index": i,
                "total_steps": len(workflow.steps)
            }
            
            # 创建任务
            task = Task(
                task_id=f"task_{workflow_name}_{i}",
                task_type=step.task_type,
                priority=1,
                input_data=task_input,
                required_capability=step.required_skills[0] if step.required_skills else None,
                max_time_seconds=300
            )
            
            task_chain.append(task)
        
        print(f"[WorkflowMapper] 为工作流程 {workflow_name} 生成了 {len(task_chain)} 个任务")
        return task_chain
    
    def get_workflow(self, workflow_name: str) -> Optional[Workflow]:
        """获取工作流程"""
        return self.workflows.get(workflow_name)
    
    def get_all_workflows(self) -> List[str]:
        """获取所有工作流程"""
        return list(self.workflows.keys())
    
    def save_workflow(self, workflow: Workflow):
        """保存工作流程"""
        workflows_dir = os.path.join(self.data_dir, "workflows")
        os.makedirs(workflows_dir, exist_ok=True)
        
        filename = f"{workflow.name}.json"
        file_path = os.path.join(workflows_dir, filename)
        
        workflow_data = {
            "name": workflow.name,
            "description": workflow.description,
            "steps": [
                {
                    "name": step.name,
                    "description": step.description,
                    "task_type": step.task_type,
                    "required_skills": step.required_skills,
                    "input_schema": step.input_schema,
                    "output_schema": step.output_schema
                }
                for step in workflow.steps
            ],
            "input_schema": workflow.input_schema,
            "output_schema": workflow.output_schema
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(workflow_data, f, indent=2, ensure_ascii=False)
        
        # 更新内存中的工作流程
        self.workflows[workflow.name] = workflow
        
        print(f"[WorkflowMapper] 保存工作流程: {workflow.name}")
    
    def delete_workflow(self, workflow_name: str):
        """删除工作流程"""
        if workflow_name not in self.workflows:
            print(f"[WorkflowMapper] 工作流程不存在: {workflow_name}")
            return
        
        # 从内存中删除
        del self.workflows[workflow_name]
        
        # 从文件中删除
        workflows_dir = os.path.join(self.data_dir, "workflows")
        filename = f"{workflow_name}.json"
        file_path = os.path.join(workflows_dir, filename)
        
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"[WorkflowMapper] 删除工作流程文件: {file_path}")
        
        print(f"[WorkflowMapper] 删除工作流程: {workflow_name}")
