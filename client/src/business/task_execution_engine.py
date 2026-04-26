"""
智能任务执行引擎 - Smart Task Execution Engine

核心特性：
1. 智能触发判断（LLM + 规则）
2. 上下文管理（跨任务共享状态）
3. 执行层数控制（防止过度分解）
4. 失败恢复机制（重试 + 回滚）
5. 任务树可视化
"""

from __future__ import annotations

import json
import time
import uuid
import traceback
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Iterator, List, Optional, Dict
from threading import Event, Lock
import random

from client.src.business.logger import get_logger

logger = get_logger('task_execution_engine')

# 导入统一配置
try:
    from client.src.business.config import get_max_retries, get_retry_delay, get_config as _get_unified_config
    _uconfig = _get_unified_config()
except ImportError:
    _uconfig = None
    # 兼容旧环境
    def get_max_retries(category="default"):
        return 3
    def get_retry_delay(category="default"):
        return 1.0

# 配置快捷变量
_POLL_SHORT = _uconfig.get("delays.polling_short", 0.1) if _uconfig else 0.1


# ── 枚举定义 ────────────────────────────────────────────────────────────────


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"          # 待执行
    RUNNING = "running"          # 执行中
    COMPLETED = "completed"      # 已完成
    FAILED = "failed"           # 失败
    RETRYING = "retrying"       # 重试中
    SKIPPED = "skipped"         # 跳过
    WAITING = "waiting"         # 等待依赖


class ExecutionStrategy(Enum):
    """执行策略"""
    SEQUENTIAL = "sequential"    # 串行
    PARALLEL = "parallel"        # 并行
    DAG = "dag"                  # 依赖图


class FailureAction(Enum):
    """失败处理动作"""
    RETRY = "retry"             # 重试
    SKIP = "skip"               # 跳过
    ROLLBACK = "rollback"       # 回滚
    ABORT = "abort"             # 中止


class TriggerType(Enum):
    """触发类型"""
    MANUAL = "manual"            # 手动触发
    AUTO = "auto"               # 自动触发（LLM 判断）
    RULE = "rule"               # 规则触发（关键词）
    CONTEXT = "context"         # 上下文触发


# ── 上下文管理 ──────────────────────────────────────────────────────────────


@dataclass
class TaskContext:
    """
    任务执行上下文

    用于在子任务间共享状态和数据
    """
    # 共享变量（所有任务可见）
    variables: Dict[str, Any] = field(default_factory=dict)

    # 文件路径（跨任务传递）
    file_paths: Dict[str, str] = field(default_factory=dict)

    # 执行结果缓存
    results: Dict[str, Any] = field(default_factory=dict)

    # 错误记录
    errors: List[Dict[str, Any]] = field(default_factory=list)

    # 原始输入
    original_task: str = ""

    # 根任务 ID
    root_task_id: str = ""

    def set_var(self, key: str, value: Any):
        """设置共享变量"""
        self.variables[key] = value

    def get_var(self, key: str, default: Any = None) -> Any:
        """获取共享变量"""
        return self.variables.get(key, default)

    def add_result(self, task_id: str, result: Any):
        """添加任务结果"""
        self.results[task_id] = result

    def add_error(self, task_id: str, error: str, tb: str = ""):
        """记录错误"""
        self.errors.append({
            "task_id": task_id,
            "error": error,
            "traceback": tb,
            "timestamp": time.time(),
        })

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "variables": self.variables,
            "file_paths": self.file_paths,
            "results_count": len(self.results),
            "errors_count": len(self.errors),
            "original_task": self.original_task[:50] + "..." if len(self.original_task) > 50 else self.original_task,
        }


# ── 任务节点 ───────────────────────────────────────────────────────────────


@dataclass
class TaskNode:
    """
    任务节点（支持树形结构）

    Attributes:
        node_id: 唯一标识
        title: 任务标题
        description: 详细描述
        status: 执行状态
        depth: 层级深度（0 = 根）
        parent_id: 父节点 ID
        children: 子节点列表
        retry_count: 当前重试次数
        max_retries: 最大重试次数
        execution_time: 执行耗时
        result: 执行结果
        error: 错误信息
        created_at: 创建时间
        started_at: 开始时间
        completed_at: 完成时间
    """
    node_id: str
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    depth: int = 0
    parent_id: Optional[str] = None
    children: List[TaskNode] = field(default_factory=list)
    retry_count: int = 0
    max_retries: int = field(default_factory=lambda: get_max_retries("default"))
    execution_time: float = 0.0
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    # 依赖管理
    depends_on: List[str] = field(default_factory=list)
    depends_results: Dict[str, Any] = field(default_factory=dict)

    # 资源需求
    required_capabilities: List[str] = field(default_factory=list)

    @property
    def duration(self) -> float:
        """计算执行耗时"""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        elif self.started_at:
            return time.time() - self.started_at
        return 0.0

    @property
    def progress(self) -> float:
        """计算节点进度"""
        if self.status == TaskStatus.COMPLETED:
            return 100.0
        elif self.status == TaskStatus.RUNNING:
            return 50.0  # 正在执行
        elif self.status == TaskStatus.FAILED:
            return 0.0
        return 0.0

    def can_retry(self) -> bool:
        """是否可以重试"""
        return self.retry_count < self.max_retries

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "node_id": self.node_id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "depth": self.depth,
            "parent_id": self.parent_id,
            "children_count": len(self.children),
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "duration": self.duration,
            "has_error": self.error is not None,
            "progress": self.progress,
        }


# ── 分解决策 ───────────────────────────────────────────────────────────────


@dataclass
class DecompositionDecision:
    """
    分解决策

    记录为什么任务需要/不需要分解
    """
    should_decompose: bool
    trigger_type: TriggerType
    confidence: float  # 0-1 置信度
    reasons: List[str]
    estimated_subtasks: int
    estimated_depth: int
    strategy: ExecutionStrategy
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "should_decompose": self.should_decompose,
            "trigger_type": self.trigger_type.value,
            "confidence": self.confidence,
            "reasons": self.reasons,
            "estimated_subtasks": self.estimated_subtasks,
            "estimated_depth": self.estimated_depth,
            "strategy": self.strategy.value,
            "warnings": self.warnings,
        }


# ── 智能分解器 ─────────────────────────────────────────────────────────────


class SmartDecomposer:
    """
    智能任务分解器

    使用 LLM + 规则混合判断是否需要分解
    """

    # 触发关键词
    HIGH_PRIORITY_TRIGGERS = frozenset([
        "实现", "开发", "构建", "设计", "架构", "搭建", "创建",
        "重构", "迁移", "集成", "部署", "发布",
    ])

    MEDIUM_PRIORITY_TRIGGERS = frozenset([
        "分析", "调研", "研究", "比较", "评估", "优化",
        "修复", "调试", "排查", "解决",
        "配置", "安装", "设置", "部署",
    ])

    # 并行模式关键词
    PARALLEL_INDICATORS = frozenset([
        "和", "与", "及", "、", "或者", "或",
        "同时", "一并", "一起",
    ])

    # 复杂度评估规则
    COMPLEXITY_PATTERNS = [
        (r"包括.*、.*包括", 2),      # 多项目并列
        (r"(注册|登录|认证|权限)", 2),  # 认证相关
        (r"(数据库|API|前端|后端)", 2),  # 技术栈
        (r"多个?.*或.*多个?", 2),   # 多个选择
        (r"完整.*系统", 3),          # 完整系统
        (r"微服务", 3),             # 微服务架构
        (r"集群|分布式", 3),         # 高级架构
    ]

    def __init__(
        self,
        llm_client: Any = None,
        max_depth: int = 3,
        max_subtasks_per_node: int = 8,
    ):
        self.llm_client = llm_client
        self.max_depth = max_depth
        self.max_subtasks_per_node = max_subtasks_per_node

    def should_decompose(self, task: str, context: TaskContext = None) -> DecompositionDecision:
        """
        智能判断任务是否需要分解

        Args:
            task: 任务描述
            context: 当前上下文（可选）

        Returns:
            DecompositionDecision: 分解决策
        """
        reasons = []
        warnings = []
        confidence = 0.5

        # ── 1. 规则快速判断 ────────────────────────────────────────
        rule_decision = self._rule_based_decision(task)
        if rule_decision:
            return rule_decision

        # ── 2. 复杂度评估 ─────────────────────────────────────────
        complexity, complexity_reasons = self._assess_complexity(task)
        reasons.extend(complexity_reasons)

        # ── 3. 上下文感知 ──────────────────────────────────────────
        if context:
            context_influence = self._assess_context_influence(context, task)
            if context_influence:
                reasons.append(context_influence)

        # ── 4. LLM 辅助判断（如果有） ───────────────────────────────
        if self.llm_client and complexity >= 2:
            llm_decision = self._llm_assisted_decision(task, complexity)
            if llm_decision:
                confidence = max(confidence, llm_decision.confidence)
                reasons.extend(llm_decision.reasons)

        # ── 5. 最终决策 ────────────────────────────────────────────
        should = complexity >= 2 or len(reasons) >= 2

        strategy = ExecutionStrategy.SEQUENTIAL
        if any(ind in task for ind in self.PARALLEL_INDICATORS):
            strategy = ExecutionStrategy.PARALLEL

        estimated_depth = min(complexity, self.max_depth)
        estimated_subtasks = min(complexity * 2, self.max_subtasks_per_node)

        # 警告
        if complexity >= 4:
            warnings.append("任务复杂度较高，可能需要多次分解")
        if estimated_depth >= 3:
            warnings.append("分解深度较大，建议分批执行")

        return DecompositionDecision(
            should_decompose=should,
            trigger_type=TriggerType.AUTO if should else TriggerType.MANUAL,
            confidence=confidence,
            reasons=reasons,
            estimated_subtasks=estimated_subtasks,
            estimated_depth=estimated_depth,
            strategy=strategy,
            warnings=warnings,
        )

    def _rule_based_decision(self, task: str) -> Optional[DecompositionDecision]:
        """基于规则的快速判断"""
        # 检查高优先级触发词
        high_matches = [t for t in self.HIGH_PRIORITY_TRIGGERS if t in task]
        if len(high_matches) >= 2:
            return DecompositionDecision(
                should_decompose=True,
                trigger_type=TriggerType.RULE,
                confidence=0.9,
                reasons=[f"检测到高优先级关键词: {', '.join(high_matches)}"],
                estimated_subtasks=4,
                estimated_depth=2,
                strategy=ExecutionStrategy.SEQUENTIAL,
            )

        # 检查任务长度
        if len(task) > 100:
            return DecompositionDecision(
                should_decompose=True,
                trigger_type=TriggerType.RULE,
                confidence=0.8,
                reasons=["任务描述较长，可能包含多个子目标"],
                estimated_subtasks=3,
                estimated_depth=2,
                strategy=ExecutionStrategy.SEQUENTIAL,
            )

        return None

    def _assess_complexity(self, task: str) -> tuple[int, List[str]]:
        """评估任务复杂度 (1-5)"""
        import re
        complexity = 1
        reasons = []

        for pattern, weight in self.COMPLEXITY_PATTERNS:
            if re.search(pattern, task):
                complexity += weight
                reasons.append(f"匹配模式: {pattern}")

        # 标点符号分隔
        separators = ["，", "。", "；", "；"]
        separator_count = sum(task.count(s) for s in separators)
        if separator_count >= 2:
            complexity += separator_count
            reasons.append(f"检测到 {separator_count} 个分隔符")

        # 限制复杂度范围
        complexity = min(5, max(1, complexity))
        return complexity, reasons

    def _assess_context_influence(self, context: TaskContext, task: str) -> Optional[str]:
        """评估上下文对分解的影响"""
        if not context.variables:
            return None

        # 检查是否有相关上下文
        relevant_vars = [
            k for k in context.variables.keys()
            if k.lower() in task.lower()
        ]

        if relevant_vars:
            return f"上下文包含相关变量: {', '.join(relevant_vars)}"

        return None

    def _llm_assisted_decision(self, task: str, base_complexity: int) -> Optional[DecompositionDecision]:
        """LLM 辅助判断"""
        try:
            prompt = f"""分析以下任务，判断是否需要分解为多个子任务：

任务: {task}

请以 JSON 格式回答：
{{
    "should_decompose": true/false,
    "confidence": 0.0-1.0,
    "reason": "判断理由",
    "suggested_subtasks": ["子任务1", "子任务2", ...],
    "strategy": "sequential/parallel/dag"
}}"""

            # 使用全局模型路由器（同步调用）
            from client.src.business.global_model_router import call_model_sync, ModelCapability
            response = call_model_sync(
                capability=ModelCapability.REASONING,
                prompt=prompt,
                system_prompt="你是一个任务分解决策助手。"
            )

            # 解析响应
            text = response if isinstance(response, str) else response.get("content", "")
            import re
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                data = json.loads(match.group(0))
                return DecompositionDecision(
                    should_decompose=data.get("should_decompose", False),
                    trigger_type=TriggerType.AUTO,
                    confidence=data.get("confidence", 0.5),
                    reasons=[data.get("reason", "")],
                    estimated_subtasks=len(data.get("suggested_subtasks", [])),
                    estimated_depth=min(len(data.get("suggested_subtasks", [])), self.max_depth),
                    strategy=ExecutionStrategy(data.get("strategy", "sequential")),
                )
        except Exception:
            pass

        return None

    def decompose(
        self,
        task: str,
        context: TaskContext,
        decision: DecompositionDecision,
    ) -> List[TaskNode]:
        """
        执行任务分解

        Args:
            task: 原始任务
            context: 执行上下文
            decision: 分解决策

        Returns:
            List[TaskNode]: 子任务节点列表
        """
        # 创建根节点
        root = TaskNode(
            node_id=f"root_{uuid.uuid4().hex[:8]}",
            title=task[:50] + "..." if len(task) > 50 else task,
            description=task,
            depth=0,
        )
        context.root_task_id = root.node_id

        # 根据决策生成子任务
        subtasks = self._generate_subtasks(task, decision)

        # 构建任务树
        for i, subtask_data in enumerate(subtasks):
            node = TaskNode(
                node_id=f"subtask_{uuid.uuid4().hex[:8]}",
                title=subtask_data["title"],
                description=subtask_data.get("description", ""),
                depth=1,
                parent_id=root.node_id,
                depends_on=subtask_data.get("depends_on", []),
            )
            root.children.append(node)

        return root.children


    def _generate_subtasks(
        self,
        task: str,
        decision: DecompositionDecision,
    ) -> List[Dict[str, Any]]:
        """生成子任务列表"""
        # 默认分解模板
        templates = [
            {"title": "理解需求", "description": "分析任务需求，确定目标和约束"},
            {"title": "制定计划", "description": "规划实现步骤和方法"},
            {"title": "环境准备", "description": "准备所需的开发环境和依赖"},
            {"title": "核心实现", "description": "实现主要功能"},
            {"title": "测试验证", "description": "编写测试并验证功能"},
            {"title": "集成检查", "description": "检查模块间的集成"},
            {"title": "文档整理", "description": "整理文档和使用说明"},
        ]

        # 根据复杂度选择模板
        num_tasks = min(decision.estimated_subtasks, len(templates))
        selected = templates[:num_tasks]

        # 如果有 LLM，使用 LLM 生成
        if self.llm_client:
            try:
                llm_tasks = self._generate_with_llm(task, decision)
                if llm_tasks:
                    return llm_tasks
            except Exception:
                pass

        return selected

    def _generate_with_llm(
        self,
        task: str,
        decision: DecompositionDecision,
    ) -> Optional[List[Dict[str, Any]]]:
        """使用 LLM 生成子任务"""
        prompt = f"""将以下任务分解为 {decision.estimated_subtasks} 个子任务：

任务: {task}

请按 JSON 数组格式输出：
[
    {{"title": "子任务标题", "description": "详细描述", "depends_on": ["依赖的任务标题"]}},
    ...
]

要求：
1. 每个子任务独立可执行
2. 包含必要的依赖关系
3. 标题简洁明了"""

        response = self.llm_client.chat([{"role": "user", "content": prompt}])
        text = response if isinstance(response, str) else response.get("content", "")

        import re
        match = re.search(r"\[[\s\S]*\]", text)
        if match:
            return json.loads(match.group(0))

        return None


# ── 智能执行引擎 ───────────────────────────────────────────────────────────


class SmartTaskExecutor:
    """
    智能任务执行引擎

    特性：
    - 支持任务树执行
    - 自动重试和回滚
    - 执行层数控制
    - 进度追踪
    """

    def __init__(
        self,
        task_handler: Callable[[TaskNode, TaskContext], Any] = None,
        max_depth: int = 3,
        default_retries: int = None,
        retry_delay: float = None,
    ):
        self.task_handler = task_handler or self._default_handler
        self.max_depth = max_depth
        self.default_retries = default_retries if default_retries is not None else get_max_retries("default")
        self.retry_delay = retry_delay if retry_delay is not None else get_retry_delay("default")

        self._interrupt_event = Event()
        self._context: Optional[TaskContext] = None
        self._current_node: Optional[TaskNode] = None
        self._lock = Lock()

        # 回调
        self.on_node_start: Optional[Callable[[TaskNode], None]] = None
        self.on_node_progress: Optional[Callable[[TaskNode, float], None]] = None
        self.on_node_complete: Optional[Callable[[TaskNode], None]] = None
        self.on_node_error: Optional[Callable[[TaskNode, str], None]] = None
        self.on_node_retry: Optional[Callable[[TaskNode, int], None]] = None
        self.on_all_complete: Optional[Callable[[TaskContext], None]] = None

    def execute(
        self,
        nodes: List[TaskNode],
        context: TaskContext,
        strategy: ExecutionStrategy = ExecutionStrategy.SEQUENTIAL,
    ) -> TaskContext:
        """
        执行任务节点

        Args:
            nodes: 任务节点列表
            context: 执行上下文
            strategy: 执行策略

        Returns:
            TaskContext: 更新后的上下文
        """
        self._context = context

        if strategy == ExecutionStrategy.PARALLEL:
            self._execute_parallel(nodes)
        elif strategy == ExecutionStrategy.DAG:
            self._execute_dag(nodes)
        else:
            self._execute_sequential(nodes)

        if self.on_all_complete:
            self.on_all_complete(context)

        return context

    def execute_stream(
        self,
        nodes: List[TaskNode],
        context: TaskContext,
        strategy: ExecutionStrategy = ExecutionStrategy.SEQUENTIAL,
    ) -> Iterator[TaskContext]:
        """流式执行"""
        self._context = context

        if strategy == ExecutionStrategy.PARALLEL:
            iterator = self._execute_parallel_stream(nodes)
        elif strategy == ExecutionStrategy.DAG:
            iterator = self._execute_dag_stream(nodes)
        else:
            iterator = self._execute_sequential_stream(nodes)

        for state in iterator:
            yield state

        if self.on_all_complete:
            self.on_all_complete(context)

    def interrupt(self):
        """中断执行"""
        self._interrupt_event.set()

    def retry_failed(self, nodes: List[TaskNode]) -> int:
        """重试失败的任务"""
        retry_count = 0
        for node in nodes:
            if node.status == TaskStatus.FAILED and node.can_retry():
                node.status = TaskStatus.PENDING
                node.retry_count += 1
                node.error = None
                retry_count += 1

                if self.on_node_retry:
                    self.on_node_retry(node, node.retry_count)

        return retry_count

    def skip_failed(self, nodes: List[TaskNode]) -> int:
        """跳过失败的任务"""
        skip_count = 0
        for node in nodes:
            if node.status == TaskStatus.FAILED:
                node.status = TaskStatus.SKIPPED
                skip_count += 1
        return skip_count

    def get_execution_summary(self, nodes: List[TaskNode]) -> dict:
        """获取执行摘要"""
        total = len(nodes)
        completed = sum(1 for n in nodes if n.status == TaskStatus.COMPLETED)
        failed = sum(1 for n in nodes if n.status == TaskStatus.FAILED)
        running = sum(1 for n in nodes if n.status == TaskStatus.RUNNING)
        pending = sum(1 for n in nodes if n.status == TaskStatus.PENDING)

        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "running": running,
            "pending": pending,
            "success_rate": completed / total if total > 0 else 0,
            "total_duration": sum(n.duration for n in nodes),
        }

    def _execute_sequential(self, nodes: List[TaskNode]):
        """串行执行"""
        for node in nodes:
            if self._interrupt_event.is_set():
                node.status = TaskStatus.SKIPPED
                continue
            self._execute_single(node)

    def _execute_sequential_stream(self, nodes: List[TaskNode]) -> Iterator[TaskContext]:
        """串行执行（流式）"""
        for node in nodes:
            if self._interrupt_event.is_set():
                node.status = TaskStatus.SKIPPED
                yield self._context
                continue

            self._execute_single(node)
            yield self._context

    def _execute_parallel(self, nodes: List[TaskNode]):
        """并行执行"""
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(self._execute_single, node): node
                for node in nodes
            }

            for future in concurrent.futures.as_completed(futures):
                if self._interrupt_event.is_set():
                    break

    def _execute_parallel_stream(self, nodes: List[TaskNode]) -> Iterator[TaskContext]:
        """并行执行（流式）"""
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(self._execute_single, node): node
                for node in nodes
            }

            while futures:
                done = [f for f in futures if f.done()]
                for f in done:
                    del futures[f]

                yield self._context

                if not futures:
                    break

                time.sleep(_POLL_SHORT)

    def _execute_dag(self, nodes: List[TaskNode]):
        """依赖图执行"""
        node_map = {n.node_id: n for n in nodes}
        completed = set()

        while len(completed) < len(nodes):
            if self._interrupt_event.is_set():
                break

            made_progress = False

            for node in nodes:
                if node.node_id in completed:
                    continue

                if self._check_dependencies(node, node_map, completed):
                    self._execute_single(node)
                    completed.add(node.node_id)
                    made_progress = True

            if not made_progress:
                # 死锁检测
                remaining = [n.node_id for n in nodes if n.node_id not in completed]
                logger.info(f"[SmartTaskExecutor] 警告: 可能的死锁，剩余: {remaining}")
                break

    def _execute_dag_stream(self, nodes: List[TaskNode]) -> Iterator[TaskContext]:
        """依赖图执行（流式）"""
        node_map = {n.node_id: n for n in nodes}
        completed = set()

        while len(completed) < len(nodes):
            if self._interrupt_event.is_set():
                yield self._context
                break

            made_progress = False

            for node in nodes:
                if node.node_id in completed:
                    continue

                if self._check_dependencies(node, node_map, completed):
                    self._execute_single(node)
                    completed.add(node.node_id)
                    made_progress = True
                    yield self._context

            if not made_progress:
                break

    def _check_dependencies(
        self,
        node: TaskNode,
        node_map: Dict[str, TaskNode],
        completed: set,
    ) -> bool:
        """检查依赖是否满足"""
        for dep_id in node.depends_on:
            if dep_id not in completed:
                return False
            # 收集依赖结果
            dep_node = node_map.get(dep_id)
            if dep_node:
                node.depends_results[dep_id] = dep_node.result
        return True

    def _execute_single(self, node: TaskNode):
        """执行单个任务"""
        logger.info(f"[SmartTaskExecutor] 执行: {node.title}")

        node.status = TaskStatus.RUNNING
        node.started_at = time.time()

        if self.on_node_start:
            self.on_node_start(node)

        # 带重试的执行
        last_error = None
        for attempt in range(node.max_retries):
            try:
                result = self.task_handler(node, self._context)

                node.result = result
                node.status = TaskStatus.COMPLETED
                node.completed_at = time.time()
                node.execution_time = node.duration

                # 更新上下文
                if self._context:
                    self._context.add_result(node.node_id, result)

                if self.on_node_complete:
                    self.on_node_complete(node)

                logger.info(f"[SmartTaskExecutor] 完成: {node.title} ({node.duration:.2f}s)")
                return

            except Exception as e:
                last_error = e
                node.retry_count = attempt + 1

                if self.on_node_retry:
                    self.on_node_retry(node, attempt + 1)

                if attempt < node.max_retries - 1:
                    logger.info(f"[SmartTaskExecutor] 重试 {attempt + 1}/{node.max_retries}: {node.title}")
                    time.sleep(self.retry_delay * (2 ** attempt))  # 指数退避
                else:
                    logger.info(f"[SmartTaskExecutor] 失败: {node.title} - {e}")

        # 所有重试都失败
        node.status = TaskStatus.FAILED
        node.error = str(last_error)
        node.completed_at = time.time()

        if self._context:
            self._context.add_error(node.node_id, str(last_error), traceback.format_exc())

        if self.on_node_error:
            self.on_node_error(node, str(last_error))

    def _default_handler(self, node: TaskNode, context: TaskContext) -> Any:
        """默认处理器"""
        # 模拟执行
        for i in range(1, 11):
            if self._interrupt_event.is_set():
                raise Exception("任务被中断")

            if self.on_node_progress:
                self.on_node_progress(node, i * 10)

            time.sleep(_POLL_SHORT)

        return {"status": "success", "node": node.title}


# ── 树形结构工具 ─────────────────────────────────────────────────────────────


def build_task_tree(nodes: List[TaskNode]) -> Dict[str, Any]:
    """构建任务树结构"""
    node_map = {n.node_id: n for n in nodes}

    def build_tree(node: TaskNode) -> Dict[str, Any]:
        return {
            "node_id": node.node_id,
            "title": node.title,
            "status": node.status.value,
            "depth": node.depth,
            "progress": node.progress,
            "duration": node.duration,
            "has_error": node.error is not None,
            "error": node.error,
            "children": [build_tree(node_map[cid]) for cid in
                        [c.node_id for c in nodes if c.parent_id == node.node_id]],
        }

    # 找根节点
    roots = [n for n in nodes if n.parent_id is None]
    if roots:
        return build_tree(roots[0])

    return {}


# ── 测试 ─────────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("智能任务执行引擎测试")
    logger.info("=" * 60)

    # 测试智能分解判断
    decomposer = SmartDecomposer(max_depth=3)

    test_tasks = [
        ("写一个函数", None),
        ("实现用户认证系统，包括注册、登录、权限管理", 0.9),
        ("帮我搭建微服务架构", 0.85),
        ("优化这个查询性能", 0.6),
    ]

    logger.info("\n[1] 智能分解判断测试")
    for task, expected in test_tasks:
        decision = decomposer.should_decompose(task)
        logger.info(f"\n  Task: {task}")
        logger.info(f"  Decision: {decision.should_decompose} ({decision.trigger_type.value})")
        logger.info(f"  Confidence: {decision.confidence:.2f}")
        logger.info(f"  Reasons: {decision.reasons}")
        logger.info(f"  Strategy: {decision.strategy.value}")

    # 测试执行引擎
    logger.info("\n[2] 执行引擎测试")
    context = TaskContext(original_task="测试任务")
    executor = SmartTaskExecutor(default_retries=2)

    nodes = [
        TaskNode(node_id="1", title="步骤1"),
        TaskNode(node_id="2", title="步骤2", depends_on=["1"]),
        TaskNode(node_id="3", title="步骤3"),
    ]

    logger.info("\n执行节点:")
    for state in executor.execute_stream(nodes, context):
        summary = executor.get_execution_summary(nodes)
        logger.info(f"  Progress: {summary['completed']}/{summary['total']}")

    logger.info(f"\n摘要: {summary}")
    logger.info(f"上下文: {context.to_dict()}")
