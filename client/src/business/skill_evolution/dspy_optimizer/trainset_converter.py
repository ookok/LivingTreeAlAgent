"""
DSPy 训练集转换器

将本项目的执行记录 (ExecutionRecord, SessionArchive, TaskSkill)
转换为 DSPy 训练集/验证集格式
"""

import json
import time
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from ..models import (
    ExecutionRecord,
    ExecutionPhase,
    TaskContext,
    TaskSkill,
    SessionArchive,
)
from ..atom_tools import get_default_tools
from .config import _import_dspy, get_dspy_config


# ============ DSPy 数据格式定义 ============

class DSpyByExample:
    """
    DSPy Example 的包装类
    
    DSPy 训练集由 Example 对象组成，每个 Example 包含 input 和 output 字段
    """
    
    def __init__(self, inputs: Dict[str, Any], outputs: Dict[str, Any]):
        self.inputs = inputs
        self.outputs = outputs
        self._example = None
    
    def to_dspy_example(self):
        """转换为 DSPy Example 对象"""
        dspy = _import_dspy()
        # DSPy 的 Example 将 input/output keys 作为属性
        all_data = {**self.inputs, **self.outputs}
        # inputs 标记为 label=False（即输入）, outputs 为 label=True（即标签）
        label_values = list(self.outputs.keys()) if self.outputs else None
        return dspy.Example(**all_data, label_values=label_values)


# ============ 转换核心逻辑 ============

class TrainsetConverter:
    """
    训练集转换器
    
    将执行记录转换为 DSPy 训练集格式：
    - 输入: task_description, tool_context
    - 输出: tool_sequence, args_sequence, success_pattern
    """
    
    def __init__(self):
        self.config = get_dspy_config()
    
    def convert_successful_tasks(
        self,
        task_contexts: List[TaskContext],
        min_success_rate: float = 0.6
    ) -> Tuple[List[DSpyByExample], List[DSpyByExample]]:
        """
        将成功的任务转换为训练集/验证集
        
        Args:
            task_contexts: 任务上下文列表
            min_success_rate: 最低成功率阈值
            
        Returns:
            (trainset, devset): DSPy training/dev 数据集
        """
        trainset = []
        devset = []
        opt_config = self.config.optimizer
        
        for ctx in task_contexts:
            # 过滤成功的任务
            if ctx.calculate_success_rate() < min_success_rate:
                continue
            
            example = self._task_context_to_example(ctx)
            if example:
                # 按比例拆分 train/dev
                if len(trainset) < opt_config.max_train_examples:
                    trainset.append(example)
                elif len(devset) < opt_config.max_dev_examples:
                    devset.append(example)
        
        # 确保有最少样本
        if len(devset) < opt_config.min_dev_examples and len(trainset) > opt_config.min_train_examples + opt_config.min_dev_examples:
            # 从训练集中划分一部分到验证集
            split_point = len(trainset) - opt_config.min_dev_examples
            devset = trainset[split_point:]
            trainset = trainset[:split_point]
        
        return trainset, devset
    
    def convert_skill_execution_records(
        self,
        skill: TaskSkill
    ) -> Tuple[List[DSpyByExample], List[DSpyByExample]]:
        """
        将技能的历史执行记录转换为训练集
        
        用于针对单个技能进行优化
        """
        examples = []
        opt_config = self.config.optimizer
        
        # 从技能的执行流程中提取训练模式
        if skill.execution_flow:
            example = self._skill_to_example(skill)
            if example:
                examples.append(example)
        
        # 拆分
        split = max(1, len(examples) - opt_config.min_dev_examples)
        trainset = examples[:split]
        devset = examples[split:]
        
        return trainset, devset
    
    def convert_session_archives(
        self,
        archives: List[SessionArchive],
        only_successful: bool = True
    ) -> Tuple[List[DSpyByExample], List[DSpyByExample]]:
        """
        将会话归档转换为训练集
        
        使用 L4 归档中的经验数据
        """
        trainset = []
        devset = []
        opt_config = self.config.optimizer
        
        for archive in archives:
            if only_successful and not archive.success:
                continue
            
            example = self._archive_to_example(archive)
            if example:
                if len(trainset) < opt_config.max_train_examples:
                    trainset.append(example)
                elif len(devset) < opt_config.max_dev_examples:
                    devset.append(example)
        
        return trainset, devset
    
    def build_training_data_from_records(
        self,
        execution_records: List[ExecutionRecord],
        task_description: str
    ) -> Optional[DSpyByExample]:
        """
        将单次执行的记录转换为训练 example
        
        这是最细粒度的训练数据：
        - 输入: 任务描述 + 上下文
        - 输出: 成功工具调用序列的最佳模式
        """
        if not execution_records:
            return None
        
        # 只选取成功的记录
        successful = [r for r in execution_records if r.success]
        if not successful:
            return None
        
        # 构建输入
        inputs = {
            "task": task_description,
            "context": self._build_context_text(successful),
        }
        
        # 构建输出（成功的工具序列模式）
        outputs = {
            "tool_sequence": self._extract_tool_pattern(successful),
            "reasoning": self._extract_reasoning_pattern(successful),
        }
        
        return DspByExample(inputs, outputs)
    
    def to_dspy_examples(self, examples: List[DSpyByExample]) -> List:
        """将包装的 examples 批量转换为真实 DSPy Example 对象"""
        dspy = _import_dspy()
        result = []
        for ex in examples:
            result.append(ex.to_dspy_example())
        return result
    
    def save_trainset(
        self,
        trainset: List,
        devset: List,
        skill_name: str,
        timestamp: Optional[float] = None
    ) -> str:
        """
        保存训练集到文件系统
        
        Returns:
            path: 保存的文件路径
        """
        timestamp = timestamp or time.time()
        ts_str = time.strftime("%Y%m%d_%H%M%S", time.localtime(timestamp))
        
        trainset_path = Path(self.config.trainset_dir).expanduser()
        trainset_path.mkdir(parents=True, exist_ok=True)
        
        filename = f"{skill_name}_{ts_str}.json"
        filepath = trainset_path / filename
        
        # 保存为 JSON
        data = {
            "skill_name": skill_name,
            "timestamp": timestamp,
            "train_size": len(trainset),
            "dev_size": len(devset),
            "trainset": self._serialize_examples(trainset),
            "devset": self._serialize_examples(devset),
        }
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return str(filepath)
    
    def load_trainset(self, filepath: str) -> Tuple[List, List]:
        """加载已保存的训练集"""
        dspy = _import_dspy()
        
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        trainset = [
            dspy.Example(**ex, label_values=ex.get("_labels", None))
            for ex in data["trainset"]
        ]
        devset = [
            dspy.Example(**ex, label_values=ex.get("_labels", None))
            for ex in data["devset"]
        ]
        
        return trainset, devset
    
    # ============ 辅助方法 ============
    
    def _task_context_to_example(self, ctx: TaskContext) -> Optional[DSpyByExample]:
        """将任务上下文转换为训练 example"""
        if not ctx.execution_records:
            return None
        
        successful_records = [r for r in ctx.execution_records if r.success]
        if not successful_records:
            return None
        
        inputs = {
            "task": ctx.description,
            "task_type": ctx.task_type or "general",
            "available_tools": json.dumps([t["name"] for t in get_default_tools()]),
        }
        
        outputs = {
            "best_tool_sequence": json.dumps([
                r.tool_name for r in successful_records
            ]),
            "expected_output": ctx.final_result or "任务完成",
        }
        
        return DspByExample(inputs, outputs)
    
    def _skill_to_example(self, skill: TaskSkill) -> Optional[DSpyByExample]:
        """将技能转换为训练 example"""
        inputs = {
            "task": skill.description,
            "task_type": skill.metadata.get("task_type", "general"),
            "trigger_patterns": json.dumps(skill.trigger_patterns),
            "success_rate": skill.success_rate,
        }
        
        outputs = {
            "tool_sequence": json.dumps(skill.tool_sequence),
            "execution_flow": json.dumps(skill.execution_flow[:10]),
            "reasoning": self._generate_skill_reasoning(skill),
        }
        
        return DspByExample(inputs, outputs)
    
    def _archive_to_example(self, archive: SessionArchive) -> Optional[DSpyByExample]:
        """将会话归档转换为训练 example"""
        inputs = {
            "task": archive.task_description,
            "task_type": archive.task_type or "general",
            "lessons_learned": json.dumps(archive.lessons_learned),
        }
        
        outputs = {
            "tools_used": json.dumps(archive.tools_used),
            "execution_summary": archive.execution_summary,
            "outcome": archive.final_outcome,
            "mistakes_to_avoid": json.dumps(archive.mistakes_made),
        }
        
        return DspByExample(inputs, outputs)
    
    def _build_context_text(self, records: List[ExecutionRecord]) -> str:
        """构建上下文文本"""
        parts = []
        for i, r in enumerate(records[:20]):  # 限制长度
            status = "success" if r.success else "failed"
            parts.append(f"Step {i+1} ({status}): {r.tool_name} with args={r.tool_args}")
        return "\n".join(parts)
    
    def _extract_tool_pattern(self, records: List[ExecutionRecord]) -> str:
        """提取工具模式"""
        tools = [r.tool_name for r in records]
        return " -> ".join(tools)
    
    def _extract_reasoning_pattern(self, records: List[ExecutionRecord]) -> str:
        """提取推理模式"""
        patterns = []
        prev_tool = None
        for r in records:
            if prev_tool and prev_tool != r.tool_name:
                patterns.append(f"After {prev_tool}, switch to {r.tool_name}")
            elif not prev_tool:
                patterns.append(f"Start with {r.tool_name}")
            prev_tool = r.tool_name
        return "; ".join(patterns)
    
    def _generate_skill_reasoning(self, skill: TaskSkill) -> str:
        """为技能生成推理文本"""
        parts = []
        if skill.tool_sequence:
            parts.append(f"使用工具链: {' -> '.join(skill.tool_sequence)}")
        if skill.success_rate > 0.8:
            parts.append(f"高成功率 ({skill.success_rate:.0%}) 证明此方法可靠")
        elif skill.success_rate > 0.6:
            parts.append(f"中等成功率 ({skill.success_rate:.0%}) 需要优化")
        if skill.use_count > 5:
            parts.append(f"经过 {skill.use_count} 次验证")
        return " ".join(parts) if parts else skill.description
    
    def _serialize_examples(self, examples: List) -> List[Dict]:
        """序列化 DSPy Example 对象"""
        results = []
        for ex in examples:
            if hasattr(ex, 'toDict'):
                d = ex.toDict()
                d['_labels'] = list(getattr(ex, 'labels', []))
                results.append(d)
            elif isinstance(ex, dict):
                results.append(ex)
        return results


# ============ 全局转换器实例 ============

_converter_instance: Optional[TrainsetConverter] = None


def get_trainset_converter() -> TrainsetConverter:
    """获取训练集转换器单例"""
    global _converter_instance
    if _converter_instance is None:
        _converter_instance = TrainsetConverter()
    return _converter_instance
