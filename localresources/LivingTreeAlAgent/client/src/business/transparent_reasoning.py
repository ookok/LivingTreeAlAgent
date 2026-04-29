"""
透明推理可视化模块
展示AI的思维过程和决策逻辑
"""

import os
import json
import asyncio
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class ReasoningStepType(Enum):
    """推理步骤类型"""
    THOUGHT = "thought"
    ACTION = "action"
    OBSERVATION = "observation"
    DECISION = "decision"
    QUESTION = "question"
    ANSWER = "answer"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ConfidenceLevel(Enum):
    """置信度级别"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


@dataclass
class ReasoningStep:
    """推理步骤"""
    id: str
    step_type: ReasoningStepType
    content: str
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    children: List[str] = field(default_factory=list)


class ReasoningTree:
    """推理树"""
    
    def __init__(self, root_id: str):
        self.root_id = root_id
        self.steps: Dict[str, ReasoningStep] = {}
        self.created_at: datetime = datetime.now()
        self.modified_at: datetime = datetime.now()
    
    def add_step(self, step: ReasoningStep):
        """添加推理步骤"""
        self.steps[step.id] = step
        self.modified_at = datetime.now()
    
    def add_child(self, parent_id: str, child_id: str):
        """添加子步骤"""
        if parent_id in self.steps:
            self.steps[parent_id].children.append(child_id)
            self.modified_at = datetime.now()
    
    def get_step(self, step_id: str) -> Optional[ReasoningStep]:
        """获取推理步骤"""
        return self.steps.get(step_id)
    
    def get_steps(self) -> List[ReasoningStep]:
        """获取所有推理步骤"""
        return list(self.steps.values())
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'root_id': self.root_id,
            'steps': {k: {
                'id': v.id,
                'step_type': v.step_type.value,
                'content': v.content,
                'confidence': v.confidence.value,
                'timestamp': v.timestamp.isoformat(),
                'metadata': v.metadata,
                'children': v.children
            } for k, v in self.steps.items()},
            'created_at': self.created_at.isoformat(),
            'modified_at': self.modified_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ReasoningTree':
        """从字典创建"""
        tree = cls(data['root_id'])
        tree.created_at = datetime.fromisoformat(data['created_at'])
        tree.modified_at = datetime.fromisoformat(data['modified_at'])
        
        for step_id, step_data in data['steps'].items():
            step = ReasoningStep(
                id=step_data['id'],
                step_type=ReasoningStepType(step_data['step_type']),
                content=step_data['content'],
                confidence=ConfidenceLevel(step_data['confidence']),
                timestamp=datetime.fromisoformat(step_data['timestamp']),
                metadata=step_data['metadata'],
                children=step_data['children']
            )
            tree.steps[step_id] = step
        
        return tree


class ReasoningVisualizer:
    """推理可视化器"""
    
    def __init__(self):
        self.reasoning_trees: Dict[str, ReasoningTree] = {}
        self._step_counter = 0
    
    def _generate_step_id(self) -> str:
        """生成步骤ID"""
        self._step_counter += 1
        return f"step_{self._step_counter}_{int(datetime.now().timestamp())}"
    
    def create_reasoning_tree(self) -> str:
        """创建推理树"""
        root_id = self._generate_step_id()
        tree = ReasoningTree(root_id)
        tree.add_step(ReasoningStep(
            id=root_id,
            step_type=ReasoningStepType.THOUGHT,
            content="开始推理",
            confidence=ConfidenceLevel.HIGH
        ))
        tree_id = f"tree_{int(datetime.now().timestamp())}"
        self.reasoning_trees[tree_id] = tree
        return tree_id
    
    def add_reasoning_step(self, tree_id: str, parent_id: str, step_type: ReasoningStepType, content: str, confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM, **metadata) -> str:
        """添加推理步骤"""
        tree = self.reasoning_trees.get(tree_id)
        if not tree:
            return None
        
        step_id = self._generate_step_id()
        step = ReasoningStep(
            id=step_id,
            step_type=step_type,
            content=content,
            confidence=confidence,
            metadata=metadata
        )
        tree.add_step(step)
        tree.add_child(parent_id, step_id)
        return step_id
    
    def get_reasoning_tree(self, tree_id: str) -> Optional[ReasoningTree]:
        """获取推理树"""
        return self.reasoning_trees.get(tree_id)
    
    def list_reasoning_trees(self) -> List[ReasoningTree]:
        """列出所有推理树"""
        return list(self.reasoning_trees.values())
    
    def visualize_reasoning(self, tree_id: str) -> Optional[str]:
        """可视化推理过程"""
        tree = self.reasoning_trees.get(tree_id)
        if not tree:
            return None
        
        # 生成可视化HTML
        html = self._generate_html(tree)
        return html
    
    def _generate_html(self, tree: ReasoningTree) -> str:
        """生成HTML可视化"""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>推理过程可视化</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        .header {{
            background-color: #333;
            color: white;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .step {{
            background-color: white;
            border: 1px solid #ddd;
            border-radius: 5px;
            padding: 15px;
            margin-bottom: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .step.thought {{
            border-left: 4px solid #3498db;
        }}
        .step.action {{
            border-left: 4px solid #2ecc71;
        }}
        .step.observation {{
            border-left: 4px solid #f39c12;
        }}
        .step.decision {{
            border-left: 4px solid #9b59b6;
        }}
        .step.question {{
            border-left: 4px solid #e74c3c;
        }}
        .step.answer {{
            border-left: 4px solid #1abc9c;
        }}
        .step.error {{
            border-left: 4px solid #e74c3c;
            background-color: #ffebee;
        }}
        .step.warning {{
            border-left: 4px solid #f39c12;
            background-color: #fff3e0;
        }}
        .step.info {{
            border-left: 4px solid #3498db;
            background-color: #e3f2fd;
        }}
        .step-header {{
            font-weight: bold;
            margin-bottom: 5px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .step-content {{
            margin: 10px 0;
            line-height: 1.5;
        }}
        .step-metadata {{
            font-size: 12px;
            color: #666;
            margin-top: 10px;
        }}
        .confidence-low {{
            color: #e74c3c;
        }}
        .confidence-medium {{
            color: #f39c12;
        }}
        .confidence-high {{
            color: #2ecc71;
        }}
        .confidence-very-high {{
            color: #27ae60;
        }}
        .children {{
            margin-left: 20px;
            margin-top: 10px;
        }}
        .timestamp {{
            font-size: 12px;
            color: #999;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>AI 推理过程可视化</h1>
            <p>生成时间: {created_at}</p>
        </div>
        {steps_html}
    </div>
</body>
</html>
        """
        
        steps_html = self._generate_steps_html(tree, tree.root_id, 0)
        return html.format(
            created_at=tree.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            steps_html=steps_html
        )
    
    def _generate_steps_html(self, tree: ReasoningTree, step_id: str, level: int) -> str:
        """生成步骤HTML"""
        step = tree.get_step(step_id)
        if not step:
            return ""
        
        indent = "margin-left: " + str(level * 20) + "px;"
        confidence_class = f"confidence-{step.confidence.value}"
        
        html = f"""
        <div class="step {step.step_type.value}" style="{indent}">
            <div class="step-header">
                <span>{step.step_type.value.capitalize()}</span>
                <span class="{confidence_class}">置信度: {step.confidence.value}</span>
                <span class="timestamp">{step.timestamp.strftime('%H:%M:%S')}</span>
            </div>
            <div class="step-content">{step.content}</div>
            {metadata_html}
            {children_html}
        </div>
        """
        
        # 生成元数据HTML
        metadata_html = ""
        if step.metadata:
            metadata_html = '<div class="step-metadata">'
            for key, value in step.metadata.items():
                metadata_html += f"<strong>{key}:</strong> {value}<br>"
            metadata_html += '</div>'
        
        # 生成子步骤HTML
        children_html = ""
        if step.children:
            children_html = '<div class="children">'
            for child_id in step.children:
                children_html += self._generate_steps_html(tree, child_id, level + 1)
            children_html += '</div>'
        
        return html.format(
            metadata_html=metadata_html,
            children_html=children_html
        )
    
    def export_reasoning(self, tree_id: str, file_path: str) -> bool:
        """导出推理过程"""
        tree = self.reasoning_trees.get(tree_id)
        if not tree:
            return False
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(tree.to_dict(), f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"导出推理过程失败: {e}")
            return False
    
    def import_reasoning(self, file_path: str) -> Optional[str]:
        """导入推理过程"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            tree = ReasoningTree.from_dict(data)
            tree_id = f"tree_{int(datetime.now().timestamp())}"
            self.reasoning_trees[tree_id] = tree
            return tree_id
        except Exception as e:
            print(f"导入推理过程失败: {e}")
            return None
    
    def get_reasoning_stats(self) -> Dict[str, Any]:
        """获取推理统计"""
        stats = {
            'total_trees': len(self.reasoning_trees),
            'total_steps': 0,
            'steps_by_type': {}
        }
        
        for tree in self.reasoning_trees.values():
            steps = tree.get_steps()
            stats['total_steps'] += len(steps)
            
            for step in steps:
                step_type = step.step_type.value
                stats['steps_by_type'][step_type] = stats['steps_by_type'].get(step_type, 0) + 1
        
        return stats


class ReasoningManager:
    """推理管理器"""
    
    def __init__(self):
        self.visualizer = ReasoningVisualizer()
        self.active_tree_id: Optional[str] = None
    
    def start_reasoning(self) -> str:
        """开始推理"""
        tree_id = self.visualizer.create_reasoning_tree()
        self.active_tree_id = tree_id
        return tree_id
    
    def add_step(self, step_type: ReasoningStepType, content: str, parent_id: str = None, confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM, **metadata) -> str:
        """添加推理步骤"""
        if not self.active_tree_id:
            self.start_reasoning()
        
        tree = self.visualizer.get_reasoning_tree(self.active_tree_id)
        if not tree:
            return None
        
        parent_id = parent_id or tree.root_id
        return self.visualizer.add_reasoning_step(
            self.active_tree_id,
            parent_id,
            step_type,
            content,
            confidence,
            **metadata
        )
    
    def add_thought(self, content: str, parent_id: str = None, confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM, **metadata) -> str:
        """添加思考步骤"""
        return self.add_step(ReasoningStepType.THOUGHT, content, parent_id, confidence, **metadata)
    
    def add_action(self, content: str, parent_id: str = None, confidence: ConfidenceLevel = ConfidenceLevel.HIGH, **metadata) -> str:
        """添加行动步骤"""
        return self.add_step(ReasoningStepType.ACTION, content, parent_id, confidence, **metadata)
    
    def add_observation(self, content: str, parent_id: str = None, confidence: ConfidenceLevel = ConfidenceLevel.HIGH, **metadata) -> str:
        """添加观察步骤"""
        return self.add_step(ReasoningStepType.OBSERVATION, content, parent_id, confidence, **metadata)
    
    def add_decision(self, content: str, parent_id: str = None, confidence: ConfidenceLevel = ConfidenceLevel.HIGH, **metadata) -> str:
        """添加决策步骤"""
        return self.add_step(ReasoningStepType.DECISION, content, parent_id, confidence, **metadata)
    
    def add_question(self, content: str, parent_id: str = None, confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM, **metadata) -> str:
        """添加问题步骤"""
        return self.add_step(ReasoningStepType.QUESTION, content, parent_id, confidence, **metadata)
    
    def add_answer(self, content: str, parent_id: str = None, confidence: ConfidenceLevel = ConfidenceLevel.HIGH, **metadata) -> str:
        """添加回答步骤"""
        return self.add_step(ReasoningStepType.ANSWER, content, parent_id, confidence, **metadata)
    
    def add_error(self, content: str, parent_id: str = None, **metadata) -> str:
        """添加错误步骤"""
        return self.add_step(ReasoningStepType.ERROR, content, parent_id, ConfidenceLevel.LOW, **metadata)
    
    def add_warning(self, content: str, parent_id: str = None, **metadata) -> str:
        """添加警告步骤"""
        return self.add_step(ReasoningStepType.WARNING, content, parent_id, ConfidenceLevel.MEDIUM, **metadata)
    
    def add_info(self, content: str, parent_id: str = None, **metadata) -> str:
        """添加信息步骤"""
        return self.add_step(ReasoningStepType.INFO, content, parent_id, ConfidenceLevel.MEDIUM, **metadata)
    
    def visualize(self, tree_id: str = None) -> Optional[str]:
        """可视化推理过程"""
        tree_id = tree_id or self.active_tree_id
        if not tree_id:
            return None
        return self.visualizer.visualize_reasoning(tree_id)
    
    def export(self, file_path: str, tree_id: str = None) -> bool:
        """导出推理过程"""
        tree_id = tree_id or self.active_tree_id
        if not tree_id:
            return False
        return self.visualizer.export_reasoning(tree_id, file_path)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取推理统计"""
        return self.visualizer.get_reasoning_stats()


def create_reasoning_manager() -> ReasoningManager:
    """
    创建推理管理器
    
    Returns:
        ReasoningManager: 推理管理器实例
    """
    return ReasoningManager()