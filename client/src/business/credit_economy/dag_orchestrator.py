"""
多插件DAG编排器 (DAG Orchestrator)
====================================

复杂任务的多插件编排，如：
- [视频抽帧] → [OCR识别] → [翻译]
- [文档解析] → [知识提取] → [问答生成]

调度器的挑战：
- 每个环节都有多种插件选择
- 插件之间有兼容性问题（输出格式必须能被下一个读取）
- 前一个插件的输出质量影响下一个插件的处理难度

解决方案：
- 用有向无环图（DAG）描述任务流程
- 用动态规划计算全局最优路径
- 为每个插件定义"输入/输出规范"确保兼容性
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Set, Tuple, Union
from enum import Enum
from threading import RLock
from collections import deque
import json

from .credit_registry import CreditRegistry, PluginCreditProfile, TaskType
from .task_estimator import TaskEstimator, TaskSpec
from .scheduler import Scheduler, SchedulingDecision


class DataFormat(Enum):
    """数据格式"""
    TEXT = "text"                         # 纯文本
    HTML = "html"                         # HTML
    MARKDOWN = "markdown"                 # Markdown
    JSON = "json"                         # JSON
    IMAGE = "image"                       # 图片
    AUDIO = "audio"                       # 音频
    VIDEO = "video"                       # 视频
    PDF = "pdf"                           # PDF
    BINARY = "binary"                     # 二进制


@dataclass
class IOCompatibility:
    """输入输出兼容性"""
    input_formats: List[DataFormat] = field(default_factory=list)
    output_formats: List[DataFormat] = field(default_factory=list)

    # 格式转换能力
    can_convert_from: Dict[DataFormat, List[DataFormat]] = field(default_factory=dict)

    def can_accept(self, format: DataFormat) -> bool:
        """检查是否接受某种输入格式"""
        if format in self.input_formats:
            return True
        # 检查是否能转换
        return format in self.can_convert_from

    def can_produce(self, format: DataFormat) -> bool:
        """检查是否能产生某种输出格式"""
        return format in self.output_formats


@dataclass
class TaskNode:
    """
    任务节点

    DAG图中的一个节点，表示一个子任务。
    """
    node_id: str                          # 节点ID
    name: str                             # 节点名称
    task_type: TaskType                   # 任务类型

    # 节点配置
    input_format: DataFormat = DataFormat.TEXT  # 输入格式
    output_format: DataFormat = DataFormat.TEXT # 输出格式

    # 节点配置
    min_quality: int = 60                 # 最低质量要求
    is_optional: bool = False             # 是否可选
    parallel_group: Optional[str] = None   # 并行组（同一组的节点可并行执行）

    # 约束
    allowed_plugins: List[str] = field(default_factory=list)
    blocked_plugins: List[str] = field(default_factory=list)

    def __hash__(self):
        return hash(self.node_id)


@dataclass
class TaskEdge:
    """
    任务边

    表示节点之间的依赖关系。
    """
    from_node: str                        # 源节点ID
    to_node: str                          # 目标节点ID
    data_flow: str = "default"            # 数据流标识
    transformation: Optional[str] = None  # 转换类型

    # 约束
    format_match_required: bool = True   # 是否需要格式匹配

    def __hash__(self):
        return hash((self.from_node, self.to_node))


@dataclass
class NodeExecutionPlan:
    """节点执行计划"""
    node_id: str
    plugin_id: str
    plugin_name: str
    estimated_time_sec: float
    estimated_credits: float
    quality_score: int
    input_data_key: str                   # 输入数据的key
    output_data_key: str                 # 输出数据的key


@dataclass
class ExecutionPlan:
    """
    执行计划

    完整的DAG执行方案。
    """
    workflow_id: str
    workflow_name: str

    # 节点执行计划
    node_plans: List[NodeExecutionPlan] = field(default_factory=list)

    # 执行顺序
    execution_order: List[str] = field(default_factory=list)  # 节点ID列表
    parallel_groups: List[List[str]] = field(default_factory=list)  # 可并行的节点组

    # 总成本
    total_estimated_time_sec: float = 0.0
    total_estimated_credits: float = 0.0
    min_quality: int = 0

    # 备选方案
    alternatives: List['ExecutionPlan'] = field(default_factory=list)

    # 可行性
    is_feasible: bool = True
    feasibility_issues: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "node_plans": [
                {
                    "node_id": n.node_id,
                    "plugin_id": n.plugin_id,
                    "plugin_name": n.plugin_name,
                    "estimated_time_sec": n.estimated_time_sec,
                    "estimated_credits": n.estimated_credits,
                    "quality_score": n.quality_score,
                }
                for n in self.node_plans
            ],
            "execution_order": self.execution_order,
            "parallel_groups": self.parallel_groups,
            "total_estimated_time_sec": self.total_estimated_time_sec,
            "total_estimated_credits": self.total_estimated_credits,
            "min_quality": self.min_quality,
            "is_feasible": self.is_feasible,
            "feasibility_issues": self.feasibility_issues,
        }


@dataclass
class WorkflowSpec:
    """
    工作流规格

    定义一个完整的工作流。
    """
    workflow_id: str
    name: str
    description: str = ""

    # DAG定义
    nodes: List[TaskNode] = field(default_factory=list)
    edges: List[TaskEdge] = field(default_factory=list)

    # 全局约束
    global_min_quality: int = 60
    global_max_time: float = 300.0
    global_max_credits: float = 5000.0

    # 输入输出
    input_format: DataFormat = DataFormat.TEXT
    output_format: DataFormat = DataFormat.TEXT

    def get_node(self, node_id: str) -> Optional[TaskNode]:
        """获取节点"""
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        return None

    def get_outgoing_edges(self, node_id: str) -> List[TaskEdge]:
        """获取节点的出边"""
        return [e for e in self.edges if e.from_node == node_id]

    def get_incoming_edges(self, node_id: str) -> List[TaskEdge]:
        """获取节点的入边"""
        return [e for e in self.edges if e.to_node == node_id]

    def topological_sort(self) -> List[str]:
        """拓扑排序"""
        # 构建邻接表和入度表
        in_degree = {node.node_id: 0 for node in self.nodes}
        adj_list = {node.node_id: [] for node in self.nodes}

        for edge in self.edges:
            adj_list[edge.from_node].append(edge.to_node)
            in_degree[edge.to_node] += 1

        # Kahn算法
        queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
        result = []

        while queue:
            node_id = queue.popleft()
            result.append(node_id)
            for neighbor in adj_list[node_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return result


class DAGOrchestrator:
    """
    DAG编排器

    核心职责：
    1. 验证工作流DAG的合法性
    2. 为每个节点选择最优插件
    3. 计算全局最优执行路径
    4. 处理插件间的格式兼容性问题
    """

    _instance = None
    _lock = RLock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self.registry = CreditRegistry.get_instance()
        self.estimator = TaskEstimator(self.registry)
        self.scheduler = Scheduler.get_instance()

        # 预定义的工作流模板
        self._workflow_templates: Dict[str, WorkflowSpec] = {}

        # 格式转换器注册表
        self._format_converters: Dict[Tuple[DataFormat, DataFormat], str] = {}
        self._init_format_converters()

    @classmethod
    def get_instance(cls) -> 'DAGOrchestrator':
        return cls()

    def _init_format_converters(self):
        """初始化格式转换器映射"""
        # 定义常见的格式转换路径
        conversions = [
            # 图片相关
            (DataFormat.IMAGE, DataFormat.TEXT, "ocr"),        # OCR
            (DataFormat.PDF, DataFormat.TEXT, "pdf_parser"),    # PDF解析
            (DataFormat.PDF, DataFormat.IMAGE, "pdf_renderer"), # PDF渲染

            # 音频相关
            (DataFormat.AUDIO, DataFormat.TEXT, "asr"),         # 语音识别

            # 视频相关
            (DataFormat.VIDEO, DataFormat.IMAGE, "video_frame"), # 视频抽帧
            (DataFormat.VIDEO, DataFormat.AUDIO, "video_audio"),# 视频提取音频

            # 文本相关
            (DataFormat.TEXT, DataFormat.HTML, "text_to_html"),
            (DataFormat.TEXT, DataFormat.MARKDOWN, "text_to_md"),
            (DataFormat.HTML, DataFormat.TEXT, "html_parser"),
            (DataFormat.MARKDOWN, DataFormat.TEXT, "md_parser"),
            (DataFormat.JSON, DataFormat.TEXT, "json_formatter"),
        ]
        for (src, dst, converter) in conversions:
            self._format_converters[(src, dst)] = converter

    # ==================== 预定义工作流 ====================

    def register_template(self, workflow: WorkflowSpec) -> None:
        """注册工作流模板"""
        self._workflow_templates[workflow.workflow_id] = workflow

    def get_template(self, workflow_id: str) -> Optional[WorkflowSpec]:
        """获取工作流模板"""
        return self._workflow_templates.get(workflow_id)

    def create_video_translation_workflow(
        self,
        input_length: int = 0,
        target_languages: List[str] = None
    ) -> WorkflowSpec:
        """
        创建视频翻译工作流

        [视频抽帧] → [OCR识别] → [翻译]

        Returns:
            工作流规格
        """
        if target_languages is None:
            target_languages = ["en"]

        workflow = WorkflowSpec(
            workflow_id="video_translation",
            name="视频翻译工作流",
            description="从视频中提取文字并翻译",
            nodes=[
                TaskNode(
                    node_id="video_frame",
                    name="视频抽帧",
                    task_type=TaskType.MEDIA_PROCESSING if hasattr(TaskType, 'MEDIA_PROCESSING') else TaskType.CUSTOM,
                    input_format=DataFormat.VIDEO,
                    output_format=DataFormat.IMAGE,
                    min_quality=60,
                ),
                TaskNode(
                    node_id="ocr",
                    name="OCR识别",
                    task_type=TaskType.TEXT_ANALYSIS,
                    input_format=DataFormat.IMAGE,
                    output_format=DataFormat.TEXT,
                    min_quality=60,
                ),
                TaskNode(
                    node_id="translation",
                    name="翻译",
                    task_type=TaskType.TRANSLATION,
                    input_format=DataFormat.TEXT,
                    output_format=DataFormat.TEXT,
                    min_quality=70,
                ),
            ],
            edges=[
                TaskEdge(from_node="video_frame", to_node="ocr"),
                TaskEdge(from_node="ocr", to_node="translation"),
            ],
            input_format=DataFormat.VIDEO,
            output_format=DataFormat.TEXT,
        )
        return workflow

    def create_document_analysis_workflow(
        self,
        analysis_depth: str = "normal"
    ) -> WorkflowSpec:
        """
        创建文档分析工作流

        [文档解析] → [知识提取] → [问答生成]
        """
        workflow = WorkflowSpec(
            workflow_id="doc_analysis",
            name="文档分析工作流",
            description="深度分析文档内容",
            nodes=[
                TaskNode(
                    node_id="parse",
                    name="文档解析",
                    task_type=TaskType.FILE_CONVERSION if hasattr(TaskType, 'FILE_CONVERSION') else TaskType.CUSTOM,
                    input_format=DataFormat.PDF,
                    output_format=DataFormat.TEXT,
                    min_quality=60,
                ),
                TaskNode(
                    node_id="extract",
                    name="知识提取",
                    task_type=TaskType.TEXT_ANALYSIS,
                    input_format=DataFormat.TEXT,
                    output_format=DataFormat.JSON,
                    min_quality=70,
                ),
                TaskNode(
                    node_id="qa",
                    name="问答生成",
                    task_type=TaskType.CUSTOM,
                    input_format=DataFormat.JSON,
                    output_format=DataFormat.TEXT,
                    min_quality=60,
                    is_optional=True,
                ),
            ],
            edges=[
                TaskEdge(from_node="parse", to_node="extract"),
                TaskEdge(from_node="extract", to_node="qa"),
            ],
            input_format=DataFormat.PDF,
            output_format=DataFormat.TEXT,
        )
        return workflow

    # ==================== 核心编排 ====================

    def plan(
        self,
        workflow: WorkflowSpec,
        input_data: Dict[str, Any],
        user_id: str = "default"
    ) -> ExecutionPlan:
        """
        为工作流生成执行计划

        Args:
            workflow: 工作流规格
            input_data: 输入数据
            user_id: 用户ID

        Returns:
            执行计划
        """
        user = self.registry.get_user(user_id)

        # 验证DAG
        if not self._validate_dag(workflow):
            return ExecutionPlan(
                workflow_id=workflow.workflow_id,
                workflow_name=workflow.name,
                is_feasible=False,
                feasibility_issues=["DAG验证失败：存在循环依赖或孤立节点"],
            )

        # 拓扑排序确定执行顺序
        execution_order = workflow.topological_sort()

        # 找出可并行的节点组
        parallel_groups = self._find_parallel_groups(workflow)

        # 为每个节点选择插件
        node_plans = []
        total_time = 0.0
        total_credits = 0.0
        min_quality = 100
        issues = []

        for node_id in execution_order:
            node = workflow.get_node(node_id)
            if not node:
                continue

            # 构建任务规格
            task_spec = TaskSpec(
                task_id=f"{workflow.workflow_id}_{node_id}",
                task_type=node.task_type,
                input_length=input_data.get(f"{node_id}_length", 1000),
                min_quality=node.min_quality,
                max_wait_time=workflow.global_max_time,
                budget=workflow.global_max_credits,
            )

            # 选择插件
            candidates = self.registry.list_plugins(
                task_type=node.task_type,
                enabled_only=True,
                min_quality=node.min_quality,
            )

            if not candidates:
                issues.append(f"节点【{node.name}】没有可用的插件")
                continue

            # 选择最佳插件
            best = None
            best_est = None
            for plugin in candidates:
                est = self.estimator.estimate(task_spec, plugin, user)
                if est.is_feasible:
                    if best_est is None or est.total_credits < best_est.total_credits:
                        best = plugin
                        best_est = est

            if best is None:
                issues.append(f"节点【{node.name}】没有满足约束的插件")
                continue

            # 创建节点计划
            node_plan = NodeExecutionPlan(
                node_id=node_id,
                plugin_id=best.plugin_id,
                plugin_name=best.name,
                estimated_time_sec=best_est.estimated_time_sec,
                estimated_credits=best_est.total_credits,
                quality_score=best_est.quality_score,
                input_data_key=f"input_{node_id}",
                output_data_key=f"output_{node_id}",
            )
            node_plans.append(node_plan)

            total_time += best_est.estimated_time_sec
            total_credits += best_est.total_credits
            min_quality = min(min_quality, best_est.quality_score)

        # 构建执行计划
        plan = ExecutionPlan(
            workflow_id=workflow.workflow_id,
            workflow_name=workflow.name,
            node_plans=node_plans,
            execution_order=execution_order,
            parallel_groups=parallel_groups,
            total_estimated_time_sec=total_time,
            total_estimated_credits=total_credits,
            min_quality=min_quality,
            is_feasible=len(issues) == 0,
            feasibility_issues=issues,
        )

        return plan

    def _validate_dag(self, workflow: WorkflowSpec) -> bool:
        """验证DAG合法性"""
        # 检查节点存在
        node_ids = {n.node_id for n in workflow.nodes}

        for edge in workflow.edges:
            if edge.from_node not in node_ids or edge.to_node not in node_ids:
                return False

        # 检查循环（通过拓扑排序）
        sorted_nodes = workflow.topological_sort()
        return len(sorted_nodes) == len(workflow.nodes)

    def _find_parallel_groups(self, workflow: WorkflowSpec) -> List[List[str]]:
        """找出可并行的节点组"""
        # 简化实现：按层级分组
        # 同一层级的节点如果没有依赖关系可以并行

        groups = []
        remaining = {n.node_id for n in workflow.nodes}
        processed = set()

        while remaining:
            current_group = []

            for node_id in list(remaining):
                # 检查所有入边是否都已处理
                incoming = workflow.get_incoming_edges(node_id)
                if all(e.from_node in processed for e in incoming):
                    current_group.append(node_id)

            if not current_group:
                break

            groups.append(current_group)
            for node_id in current_group:
                remaining.remove(node_id)
                processed.add(node_id)

        return groups

    # ==================== 格式转换 ====================

    def find_format_conversion_path(
        self,
        from_format: DataFormat,
        to_format: DataFormat
    ) -> Optional[List[Tuple[DataFormat, str]]]:
        """
        找到格式转换路径

        Returns:
            转换路径，如 [(VIDEO, "video_frame"), (IMAGE, "ocr"), ...]
            或 None 如果无法转换
        """
        if from_format == to_format:
            return []

        # BFS找最短路径
        queue = deque([(from_format, [])])
        visited = {from_format}

        while queue:
            current, path = queue.popleft()

            for (src, dst), converter in self._format_converters.items():
                if src == current and dst not in visited:
                    new_path = path + [(dst, converter)]
                    if dst == to_format:
                        return new_path
                    visited.add(dst)
                    queue.append((dst, new_path))

        return None

    # ==================== 执行模拟 ====================

    def simulate_execution(
        self,
        plan: ExecutionPlan,
        input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        模拟执行工作流

        返回执行结果（不实际执行）。
        """
        results = {}
        current_data = input_data.copy()

        for node_plan in plan.node_plans:
            # 模拟节点执行
            results[node_plan.node_id] = {
                "status": "pending",
                "plugin_used": node_plan.plugin_name,
                "estimated_time": node_plan.estimated_time_sec,
                "estimated_credits": node_plan.estimated_credits,
            }

        return {
            "plan": plan.to_dict(),
            "simulated_results": results,
            "total_credits": plan.total_estimated_credits,
            "total_time": plan.total_estimated_time_sec,
        }


def get_dag_orchestrator() -> DAGOrchestrator:
    """获取DAG编排器单例"""
    return DAGOrchestrator.get_instance()
