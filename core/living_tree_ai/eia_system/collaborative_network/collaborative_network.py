"""
P2P协同编制网络
将报告编制从"单机作业"变为"分布式协同"

核心能力：
1. 任务智能分派
2. 实时协同编辑
3. 贡献度量化与激励
"""

import asyncio
import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


# ============================================================================
# 数据模型
# ============================================================================

class NodeType(Enum):
    COORDINATOR = "coordinator"
    WORKER = "worker"
    EXPERT = "expert"
    VALIDATOR = "validator"


class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    REVIEWING = "reviewing"
    COMPLETED = "completed"
    REJECTED = "rejected"


class OperationType(Enum):
    INSERT = "insert"
    DELETE = "delete"
    UPDATE = "update"
    FORMAT = "format"


@dataclass
class NetworkNode:
    node_id: str
    node_type: NodeType
    name: str
    capabilities: list
    workload: float = 0
    reputation: float = 0
    tokens: float = 0
    is_online: bool = True
    last_seen: datetime = field(default_factory=datetime.now)


@dataclass
class ReportModule:
    module_id: str
    name: str
    content: str = ""
    version: int = 1
    status: TaskStatus = TaskStatus.PENDING
    assigned_to: Optional[str] = None
    dependencies: list = field(default_factory=list)


@dataclass
class CollaborativeTask:
    task_id: str
    module: ReportModule
    status: TaskStatus
    assigned_nodes: list = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    deadline: Optional[datetime] = None
    progress: float = 0


@dataclass
class EditOperation:
    operation_id: str
    node_id: str
    module_id: str
    operation_type: OperationType
    position: int
    content: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    base_version: int = 0


@dataclass
class Contribution:
    contribution_id: str
    node_id: str
    module_id: str
    task_id: str
    contribution_type: str
    amount: float
    tokens_earned: float
    timestamp: datetime = field(default_factory=datetime.now)
    hash: str = ""


@dataclass
class ConsensusRecord:
    record_id: str
    report_id: str
    content_hash: str
    nodes_agreed: list
    timestamp: datetime = field(default_factory=datetime.now)
    previous_hash: str = ""


# ============================================================================
# 任务智能分派器
# ============================================================================

class TaskDispatcher:
    def __init__(self, config: dict = None):
        self.config = config or {}
        self._nodes: dict = {}

    def register_node(self, node: NetworkNode):
        self._nodes[node.node_id] = node

    def unregister_node(self, node_id: str):
        if node_id in self._nodes:
            self._nodes[node_id].is_online = False

    async def dispatch_task(self, module: ReportModule, preferred_capabilities: list = None) -> list[NetworkNode]:
        candidates = []
        for node in self._nodes.values():
            if not node.is_online or node.workload >= 0.9:
                continue
            if preferred_capabilities:
                if any(cap in node.capabilities for cap in preferred_capabilities):
                    candidates.append(node)
            else:
                candidates.append(node)

        candidates.sort(key=lambda n: (n.reputation / 100) - n.workload, reverse=True)
        return candidates[:min(3, len(candidates))]

    async def dispatch_all_tasks(self, modules: list[ReportModule]) -> dict:
        results = {}
        sorted_modules = self._topological_sort(modules)

        for module in sorted_modules:
            capabilities = self._infer_capabilities(module.name)
            assigned = await self.dispatch_task(module, capabilities)
            results[module.module_id] = assigned

            for node in assigned:
                node.workload += 1.0 / len(assigned) if assigned else 0

        return results

    def _infer_capabilities(self, module_name: str) -> list:
        capability_map = {
            "大气": ["atmosphere_modeling", "air_quality"],
            "水": ["water_modeling", "hydrology"],
            "生态": ["ecology", "biology"],
            "风险": ["risk_assessment", "safety"],
            "噪声": ["noise_modeling", "acoustic"],
            "工程分析": ["engineering", "process"]
        }
        for key, caps in capability_map.items():
            if key in module_name:
                return caps
        return ["general"]

    def _topological_sort(self, modules: list[ReportModule]) -> list[ReportModule]:
        sorted_modules = []
        remaining = modules.copy()
        completed = set()

        while remaining:
            for module in remaining:
                deps_satisfied = all(dep in completed for dep in module.dependencies)
                if deps_satisfied:
                    sorted_modules.append(module)
                    completed.add(module.module_id)
                    remaining.remove(module)
                    break
            else:
                sorted_modules.extend(remaining)
                break

        return sorted_modules


# ============================================================================
# 协同编辑引擎（OT算法）
# ============================================================================

class CollaborativeEditor:
    def __init__(self, config: dict = None):
        self.config = config or {}
        self._documents: dict = {}
        self._operations: dict = {}
        self._pending_ops: dict = {}

    def init_document(self, module_id: str, initial_content: str = ""):
        self._documents[module_id] = {"content": initial_content, "version": 1, "operations": []}
        self._operations[module_id] = []

    async def apply_operation(self, operation: EditOperation) -> bool:
        module_id = operation.module_id
        if module_id not in self._documents:
            return False

        doc = self._documents[module_id]
        transformed_op = self._transform_operation(operation, doc)

        if transformed_op.operation_type == OperationType.INSERT:
            doc["content"] = (doc["content"][:transformed_op.position] + transformed_op.content + doc["content"][transformed_op.position:])
        elif transformed_op.operation_type == OperationType.DELETE:
            if transformed_op.position < len(doc["content"]):
                doc["content"] = doc["content"][:transformed_op.position] + doc["content"][transformed_op.position + len(transformed_op.content):]
        elif transformed_op.operation_type == OperationType.UPDATE:
            doc["content"] = transformed_op.content

        doc["version"] += 1
        transformed_op.base_version = doc["version"]
        self._operations[module_id].append(transformed_op)
        self._pending_ops[operation.node_id] = []

        return True

    def _transform_operation(self, operation: EditOperation, document: dict) -> EditOperation:
        ops_since_base = [op for op in self._operations.get(operation.module_id, []) if op.base_version > operation.base_version]
        offset = 0
        for op in ops_since_base:
            if op.operation_type == OperationType.INSERT and op.position <= operation.position:
                offset += len(op.content)
            elif op.operation_type == OperationType.DELETE and op.position < operation.position:
                offset -= len(op.content)
        operation.position += offset
        return operation

    def get_document(self, module_id: str) -> Optional[dict]:
        return self._documents.get(module_id)

    def get_operations(self, module_id: str, since_version: int = 0) -> list:
        return [op for op in self._operations.get(module_id, []) if op.base_version > since_version]


# ============================================================================
# 贡献度量化引擎
# ============================================================================

class ContributionTracker:
    def __init__(self, config: dict = None):
        self.config = config or {}
        self._contributions: dict = {}

    async def record_contribution(self, node_id: str, module_id: str, task_id: str, contribution_type: str, amount: float, content_hash: str = "") -> Contribution:
        token_reward = self._calculate_reward(contribution_type, amount)
        contribution = Contribution(
            contribution_id=f"contrib_{uuid.uuid4().hex[:12]}",
            node_id=node_id,
            module_id=module_id,
            task_id=task_id,
            contribution_type=contribution_type,
            amount=amount,
            tokens_earned=token_reward,
            hash=content_hash or hashlib.sha256(f"{node_id}{amount}".encode()).hexdigest()[:16]
        )
        if node_id not in self._contributions:
            self._contributions[node_id] = []
        self._contributions[node_id].append(contribution)
        return contribution

    def _calculate_reward(self, contribution_type: str, amount: float) -> float:
        rates = {"content": 1.0, "review": 0.7, "validation": 0.5}
        return round(amount * rates.get(contribution_type, 0.5), 2)

    def get_node_stats(self, node_id: str) -> dict:
        contributions = self._contributions.get(node_id, [])
        if not contributions:
            return {"total_contributions": 0, "total_tokens": 0, "total_content": 0, "total_reviews": 0}
        return {
            "total_contributions": len(contributions),
            "total_tokens": sum(c.tokens_earned for c in contributions),
            "total_content": sum(c.amount for c in contributions if c.contribution_type == "content"),
            "total_reviews": sum(c.amount for c in contributions if c.contribution_type == "review")
        }


# ============================================================================
# 区块链式追溯系统
# ============================================================================

class ContributionLedger:
    def __init__(self, config: dict = None):
        self.config = config or {}
        self._records: list[ConsensusRecord] = []

    def add_record(self, report_id: str, content_hash: str, agreed_nodes: list[str]) -> ConsensusRecord:
        previous_hash = self._records[-1].content_hash if self._records else "0" * 16
        record = ConsensusRecord(
            record_id=f"rec_{uuid.uuid4().hex[:12]}",
            report_id=report_id,
            content_hash=content_hash,
            nodes_agreed=agreed_nodes,
            previous_hash=previous_hash
        )
        self._records.append(record)
        return record

    def verify_chain(self) -> bool:
        for i, record in enumerate(self._records):
            if i == 0:
                continue
            if record.previous_hash != self._records[i-1].content_hash:
                return False
        return True


# ============================================================================
# P2P协同网络管理器（主入口）
# ============================================================================

class CollaborativeNetwork:
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.dispatcher = TaskDispatcher(config)
        self.editor = CollaborativeEditor(config)
        self.contribution_tracker = ContributionTracker(config)
        self.ledger = ContributionLedger(config)
        self._tasks: dict = {}
        self._local_node_id = f"node_{uuid.uuid4().hex[:12]}"

    async def create_project(self, project_name: str, modules: list[dict]) -> dict:
        project_id = f"proj_{uuid.uuid4().hex[:12]}"
        report_modules = []
        for i, mod_data in enumerate(modules):
            module = ReportModule(
                module_id=f"{project_id}_mod_{i+1}",
                name=mod_data.get("name", f"模块{i+1}"),
                content=mod_data.get("content", ""),
                dependencies=mod_data.get("dependencies", [])
            )
            report_modules.append(module)
            self.editor.init_document(module.module_id, module.content)

        assignments = await self.dispatcher.dispatch_all_tasks(report_modules)
        return {"project_id": project_id, "project_name": project_name, "modules": report_modules, "assignments": assignments}

    async def submit_edit(self, node_id: str, module_id: str, operation_type: OperationType, position: int, content: str = "") -> bool:
        operation = EditOperation(
            operation_id=f"op_{uuid.uuid4().hex[:12]}",
            node_id=node_id,
            module_id=module_id,
            operation_type=operation_type,
            position=position,
            content=content,
            base_version=0
        )
        return await self.editor.apply_operation(operation)

    async def approve_module(self, module_id: str, approver_node_id: str) -> bool:
        task = self._tasks.get(module_id)
        if not task:
            return False
        task.status = TaskStatus.COMPLETED
        task.module.status = TaskStatus.COMPLETED
        content_hash = hashlib.sha256(task.module.content.encode()).hexdigest()[:16]
        self.ledger.add_record(report_id=task.task_id, content_hash=content_hash, agreed_nodes=[approver_node_id])
        return True

    def get_module_status(self, module_id: str) -> Optional[dict]:
        doc = self.editor.get_document(module_id)
        if not doc:
            return None
        return {"module_id": module_id, "content": doc["content"], "version": doc["version"], "operations_count": len(self.editor.get_operations(module_id))}

    def get_node_contributions(self, node_id: str) -> dict:
        return self.contribution_tracker.get_node_stats(node_id)


_network: Optional[CollaborativeNetwork] = None


def get_collaborative_network() -> CollaborativeNetwork:
    global _network
    if _network is None:
        _network = CollaborativeNetwork()
    return _network


async def create_collaborative_project_async(project_name: str, modules: list[dict]) -> dict:
    network = get_collaborative_network()
    return await network.create_project(project_name, modules)
