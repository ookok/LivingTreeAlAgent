"""
Skill 自进化系统 - 数据模型
借鉴 GenericAgent 的分层记忆设计 (L0-L4)

架构设计：
┌─────────────────────────────────────────────────────────────┐
│                    分层记忆系统 (L0-L4)                       │
├─────────────────────────────────────────────────────────────┤
│  L0: Meta Rules（元规则）    - Agent 基础行为约束              │
│  L1: Insight Index（索引）  - 记忆索引，快速路由与召回          │
│  L2: Global Facts（事实）   - 长期积累的稳定知识                │
│  L3: Task Skills/SOPs      - 可复用工作流程（技能核心）         │
│  L4: Session Archive       - 已完成任务的提炼归档              │
└─────────────────────────────────────────────────────────────┘

技能进化流程：
[遇到新任务] → [自主摸索] → [将执行路径固化为 Skill] → [写入 L3] → [下次直接调用]
"""

import json
import sqlite3
import hashlib
import time
import os
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Optional, Dict, Any, Callable
from pathlib import Path
from datetime import datetime
import threading


# ============ 枚举定义 ============

class MemoryLayer(Enum):
    """记忆层级"""
    L0_META_RULES = "l0_meta_rules"      # 元规则
    L1_INSIGHT_INDEX = "l1_insight_index"  # 索引
    L2_GLOBAL_FACTS = "l2_global_facts"   # 事实
    L3_TASK_SKILLS = "l3_task_skills"     # 技能
    L4_SESSION_ARCHIVE = "l4_session_archive"  # 归档


class SkillEvolutionStatus(Enum):
    """技能进化状态"""
    SEED = "seed"           # 种子态：刚学会
    GROWING = "growing"     # 成长态：多次验证
    MATURED = "matured"    # 成熟态：稳定可靠
    ATROPHIED = "atrophied"  # 萎缩态：久未使用
    MERGED = "merged"      # 合并态：已与其他技能融合


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"     # 待处理
    RUNNING = "running"     # 执行中
    COMPLETED = "completed" # 已完成
    FAILED = "failed"       # 失败
    ABORTED = "aborted"     # 中止


class ExecutionPhase(Enum):
    """执行阶段"""
    PERCEIVE = "perceive"    # 感知
    REASON = "reason"        # 推理
    EXECUTE = "execute"      # 执行
    REFLECT = "reflect"      # 反思
    CONSOLIDATE = "consolidate"  # 固化


# ============ 核心数据结构 ============

@dataclass
class MetaRule:
    """
    L0 元规则 - Agent 基础行为约束

    定义 Agent 的基础运行规则，如：
    - 安全边界
    - 权限限制
    - 系统约束
    """
    id: str
    name: str
    description: str
    rule_type: str  # safety / permission / system
    content: str
    priority: int = 0  # 优先级，数字越大越优先
    enabled: bool = True
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MetaRule":
        return cls(**data)


@dataclass
class InsightIndex:
    """
    L1 记忆索引 - 快速路由与召回

    通过关键词/语义索引快速定位记忆
    """
    id: str
    keywords: List[str]  # 关键词列表
    layer: MemoryLayer   # 指向的层级
    target_id: str       # 指向的记忆ID
    summary: str         # 摘要描述
    embedding_hint: str = ""  # 向量提示（用于快速匹配）
    access_count: int = 0    # 访问次数
    last_accessed: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['layer'] = self.layer.value if isinstance(self.layer, MemoryLayer) else self.layer
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InsightIndex":
        if isinstance(data.get('layer'), str):
            data['layer'] = MemoryLayer(data['layer'])
        return cls(**data)


@dataclass
class GlobalFact:
    """
    L2 全局事实 - 长期积累的稳定知识

    如：
    - "用户偏好中文沟通"
    - "用户工作目录是 D:/mhzyapp"
    - "用户使用 PyCharm 作为 IDE"
    """
    id: str
    category: str  # preference / context / knowledge / habit
    content: str   # 事实内容
    confidence: float = 1.0  # 置信度
    source: str = ""  # 来源
    verified: bool = False
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GlobalFact":
        return cls(**data)


@dataclass
class TaskSkill:
    """
    L3 任务技能 - 可复用的工作流程

    这是技能自主进化的核心产物：
    - 当 Agent 成功完成一个任务后
    - 将执行路径固化为 Skill
    - 下次遇到类似任务时直接调用

    Attributes:
        skill_id: 唯一标识
        name: 技能名称（如 "提取财务数据_v1"）
        description: 功能描述
        trigger_patterns: 触发模式列表（如 ["查财报", "提取财务数据"...]）
        execution_flow: 执行流程（步骤列表）
        tool_sequence: 工具调用序列
        success_rate: 成功率
        use_count: 使用次数
        avg_duration: 平均执行时长（秒）
        evolution_status: 进化状态
        version: 版本号
        parent_skill_id: 父技能ID（用于技能分叉/合并追踪）
        prerequisites: 前置条件
        output_schema: 输出参数 schema
        metadata: 附加元数据
    """
    skill_id: str
    name: str
    description: str
    trigger_patterns: List[str] = field(default_factory=list)
    execution_flow: List[Dict[str, Any]] = field(default_factory=list)  # 步骤详情
    tool_sequence: List[str] = field(default_factory=list)  # 工具名序列
    success_rate: float = 1.0
    use_count: int = 0
    failed_count: int = 0
    avg_duration: float = 0.0  # 秒
    total_duration: float = 0.0
    evolution_status: SkillEvolutionStatus = SkillEvolutionStatus.SEED
    version: str = "1.0.0"
    parent_skill_id: Optional[str] = None
    prerequisites: List[str] = field(default_factory=list)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def get_text_for_matching(self) -> str:
        """获取用于匹配的文本"""
        parts = [
            self.name,
            self.description,
            " ".join(self.trigger_patterns),
        ]
        return " ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['evolution_status'] = self.evolution_status.value if isinstance(self.evolution_status, SkillEvolutionStatus) else self.evolution_status
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskSkill":
        if isinstance(data.get('evolution_status'), str):
            data['evolution_status'] = SkillEvolutionStatus(data['evolution_status'])
        return cls(**data)

    def record_usage(self, success: bool, duration: float):
        """记录一次使用"""
        self.use_count += 1
        self.total_duration += duration
        self.avg_duration = self.total_duration / self.use_count
        self.last_used = time.time()

        if success:
            # 成功则提升成功率
            self.success_rate = (self.success_rate * (self.use_count - 1) + 1.0) / self.use_count
            # 更新进化状态
            if self.use_count >= 10 and self.success_rate >= 0.9:
                self.evolution_status = SkillEvolutionStatus.MATURED
            elif self.use_count >= 3 and self.success_rate >= 0.7:
                self.evolution_status = SkillEvolutionStatus.GROWING
        else:
            self.failed_count += 1
            self.success_rate = (self.success_rate * (self.use_count - 1)) / self.use_count


@dataclass
class SessionArchive:
    """
    L4 会话归档 - 已完成任务的提炼记录

    用于长程召回，从已完成任务中提炼经验
    """
    id: str
    task_description: str
    task_type: str  # classification type
    execution_summary: str  # 执行摘要
    key_insights: List[str] = field(default_factory=list)
    mistakes_made: List[str] = field(default_factory=list)  # 犯过的错误
    lessons_learned: List[str] = field(default_factory=list)
    final_outcome: str = ""  # 最终结果
    success: bool = False
    duration: float = 0.0  # 秒
    turns_count: int = 0    # 轮数
    tools_used: List[str] = field(default_factory=list)
    session_id: str = ""  # 关联的会话ID
    archived_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionArchive":
        return cls(**data)


@dataclass
class ExecutionRecord:
    """
    执行记录 - 追踪单次任务执行过程

    用于分析和优化执行流程
    """
    id: str
    task_id: str
    phase: ExecutionPhase
    tool_name: str
    tool_args: Dict[str, Any] = field(default_factory=dict)
    tool_result: Any = None
    success: bool = True
    error_msg: str = ""
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0
    duration: float = 0.0  # 秒

    def finish(self, success: bool = True, error_msg: str = "", result: Any = None):
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        self.success = success
        self.error_msg = error_msg
        self.tool_result = result

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['phase'] = self.phase.value if isinstance(self.phase, ExecutionPhase) else self.phase
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionRecord":
        if isinstance(data.get('phase'), str):
            data['phase'] = ExecutionPhase(data['phase'])
        return cls(**data)


@dataclass
class TaskContext:
    """
    任务上下文 - 完整记录一个任务的执行过程

    用于技能固化和经验传承
    """
    task_id: str
    description: str
    task_type: str = ""  # 任务分类
    status: TaskStatus = TaskStatus.PENDING
    skill_id: Optional[str] = None  # 关联的技能（如果有）
    execution_records: List[ExecutionRecord] = field(default_factory=list)
    final_result: Any = None
    error_message: str = ""
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0
    duration: float = 0.0

    def finish(self, status: TaskStatus, result: Any = None, error: str = ""):
        self.status = status
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        self.final_result = result
        self.error_message = error

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['status'] = self.status.value if isinstance(self.status, TaskStatus) else self.status
        data['execution_records'] = [r.to_dict() for r in self.execution_records]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskContext":
        if isinstance(data.get('status'), str):
            data['status'] = TaskStatus(data['status'])
        data['execution_records'] = [ExecutionRecord.from_dict(r) for r in data.get('execution_records', [])]
        return cls(**data)

    def extract_tool_sequence(self) -> List[str]:
        """提取工具序列"""
        return [r.tool_name for r in self.execution_records if r.tool_name != "no_tool"]

    def calculate_success_rate(self) -> float:
        """计算成功率"""
        if not self.execution_records:
            return 0.0
        successful = sum(1 for r in self.execution_records if r.success)
        return successful / len(self.execution_records)

    def get_execution_flow(self) -> List[Dict[str, Any]]:
        """获取执行流程详情"""
        flow = []
        for record in self.execution_records:
            step = {
                "phase": record.phase.value if isinstance(record.phase, ExecutionPhase) else record.phase,
                "tool": record.tool_name,
                "args": record.tool_args,
                "success": record.success,
                "duration": record.duration,
            }
            if record.error_msg:
                step["error"] = record.error_msg
            flow.append(step)
        return flow


# ============ 工具函数 ============

def generate_id(prefix: str = "") -> str:
    """生成唯一ID"""
    raw = f"{prefix}_{os.urandom(8).hex()}_{time.time()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def generate_skill_id(name: str) -> str:
    """生成技能ID"""
    raw = f"skill_{name}_{time.time()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def calculate_similarity(text1: str, text2: str) -> float:
    """
    简单相似度计算（基于关键词重叠）

    注意：实际生产中应使用 sentence-transformers 等语义嵌入
    """
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    if not words1 or not words2:
        return 0.0
    intersection = words1 & words2
    union = words1 | words2
    return len(intersection) / len(union) if union else 0.0
