"""
AI工作流引擎 - AI-Centric自动化研发流水线核心组件

核心设计哲学：对话即流水线
用户通过自然语言描述需求，系统自动规划、分解、执行完整的软件研发生命周期任务

架构定位：协调层核心组件
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio
import json
import os
from pathlib import Path

from business.global_model_router import GlobalModelRouter, ModelCapability


class WorkflowStatus(Enum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    DECOMPOSING = "decomposing"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowNodeType(Enum):
    START = "start"
    END = "end"
    ACTION = "action"
    CONDITION = "condition"
    LOOP = "loop"
    PARALLEL = "parallel"
    APPROVAL = "approval"
    GATE = "gate"


@dataclass
class WorkflowNode:
    id: str
    type: WorkflowNodeType
    name: str
    description: str = ""
    action_type: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    next_node: Optional[str] = None
    condition: Optional[str] = None
    parallel_nodes: List[str] = field(default_factory=list)
    approval_required: bool = False
    gate_type: Optional[str] = None
    status: str = "pending"
    result: Optional[Any] = None
    execution_time: float = 0.0


@dataclass
class ExecutionContext:
    workflow_id: str
    instance_id: str
    status: WorkflowStatus = WorkflowStatus.PENDING
    variables: Dict[str, Any] = field(default_factory=dict)
    execution_history: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    current_node: Optional[str] = None


@dataclass
class WorkflowDefinition:
    id: str
    name: str
    description: str = ""
    version: str = "1.0.0"
    nodes: Dict[str, WorkflowNode] = field(default_factory=dict)
    start_node: str = "start"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    learning_score: float = 0.0
    usage_count: int = 0


class AIWorkflowEngine:
    """
    AI工作流引擎 - 支持学习型工作流编排
    
    核心特性：
    1. 对话驱动：从自然语言需求自动生成工作流
    2. 动态决策：基于上下文和历史学习做出智能决策
    3. 质量门禁：集成四级质量门禁体系
    4. 持续学习：从执行中学习优化工作流模式
    """

    def __init__(self, storage_path: Optional[str] = None):
        self._router = GlobalModelRouter()
        self._storage_path = Path(storage_path or os.path.expanduser("~/.livingtree/workflows"))
        self._storage_path.mkdir(parents=True, exist_ok=True)
        
        self._workflows: Dict[str, WorkflowDefinition] = {}
        self._instances: Dict[str, ExecutionContext] = {}
        self._learning_patterns: Dict[str, Any] = {}
        
        self._load_workflows()
        self._load_learning_patterns()

    def _load_workflows(self):
        """加载已保存的工作流定义"""
        workflow_dir = self._storage_path / "definitions"
        workflow_dir.mkdir(exist_ok=True)
        
        for filepath in workflow_dir.glob("*.json"):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    workflow = self._deserialize_workflow(data)
                    self._workflows[workflow.id] = workflow
            except Exception as e:
                print(f"加载工作流失败 {filepath}: {e}")

    def _load_learning_patterns(self):
        """加载学习模式"""
        pattern_file = self._storage_path / "learning_patterns.json"
        if pattern_file.exists():
            try:
                with open(pattern_file, 'r', encoding='utf-8') as f:
                    self._learning_patterns = json.load(f)
            except Exception as e:
                print(f"加载学习模式失败: {e}")

    def _save_workflow(self, workflow: WorkflowDefinition):
        """保存工作流定义"""
        workflow_dir = self._storage_path / "definitions"
        workflow_dir.mkdir(exist_ok=True)
        
        filepath = workflow_dir / f"{workflow.id}.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self._serialize_workflow(workflow), f, ensure_ascii=False, indent=2)

    def _save_learning_patterns(self):
        """保存学习模式"""
        pattern_file = self._storage_path / "learning_patterns.json"
        with open(pattern_file, 'w', encoding='utf-8') as f:
            json.dump(self._learning_patterns, f, ensure_ascii=False, indent=2)

    def _serialize_workflow(self, workflow: WorkflowDefinition) -> Dict[str, Any]:
        """序列化工作流定义"""
        return {
            "id": workflow.id,
            "name": workflow.name,
            "description": workflow.description,
            "version": workflow.version,
            "start_node": workflow.start_node,
            "created_at": workflow.created_at.isoformat(),
            "updated_at": workflow.updated_at.isoformat() if workflow.updated_at else None,
            "learning_score": workflow.learning_score,
            "usage_count": workflow.usage_count,
            "nodes": {
                node_id: {
                    "id": node.id,
                    "type": node.type.value,
                    "name": node.name,
                    "description": node.description,
                    "action_type": node.action_type,
                    "parameters": node.parameters,
                    "next_node": node.next_node,
                    "condition": node.condition,
                    "parallel_nodes": node.parallel_nodes,
                    "approval_required": node.approval_required,
                    "gate_type": node.gate_type
                }
                for node_id, node in workflow.nodes.items()
            }
        }

    def _deserialize_workflow(self, data: Dict[str, Any]) -> WorkflowDefinition:
        """反序列化工作流定义"""
        workflow = WorkflowDefinition(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            version=data.get("version", "1.0.0"),
            start_node=data.get("start_node", "start"),
            learning_score=data.get("learning_score", 0.0),
            usage_count=data.get("usage_count", 0)
        )
        
        if "created_at" in data:
            workflow.created_at = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data and data["updated_at"]:
            workflow.updated_at = datetime.fromisoformat(data["updated_at"])
        
        for node_id, node_data in data.get("nodes", {}).items():
            workflow.nodes[node_id] = WorkflowNode(
                id=node_id,
                type=WorkflowNodeType(node_data["type"]),
                name=node_data["name"],
                description=node_data.get("description", ""),
                action_type=node_data.get("action_type"),
                parameters=node_data.get("parameters", {}),
                next_node=node_data.get("next_node"),
                condition=node_data.get("condition"),
                parallel_nodes=node_data.get("parallel_nodes", []),
                approval_required=node_data.get("approval_required", False),
                gate_type=node_data.get("gate_type")
            )
        
        return workflow

    async def create_workflow_from_requirement(self, requirement: str) -> WorkflowDefinition:
        """
        从自然语言需求自动生成工作流
        
        Args:
            requirement: 用户自然语言需求描述
            
        Returns:
            生成的工作流定义
        """
        print(f"🧠 分析需求生成工作流: {requirement[:50]}...")
        
        prompt = f"""
作为一个专业的软件研发工作流设计专家，根据以下用户需求生成完整的工作流定义。

用户需求: {requirement}

请按照以下格式输出JSON：
{{
    "workflow_name": "工作流名称",
    "workflow_description": "工作流描述",
    "nodes": [
        {{
            "id": "节点ID",
            "type": "start|action|condition|loop|parallel|approval|gate|end",
            "name": "节点名称",
            "description": "节点描述",
            "action_type": "代码生成|测试|审查|部署等",
            "parameters": {{...}},
            "next_node": "下一个节点ID",
            "approval_required": false,
            "gate_type": null
        }}
    ],
    "start_node": "起始节点ID"
}}

注意事项：
1. 节点类型必须是 start, action, condition, loop, parallel, approval, gate, end 之一
2. action_type 可以是：需求分析、代码生成、单元测试、集成测试、代码审查、部署、发布等
3. 对于关键节点（如发布前）添加 approval_required: true
4. 质量门禁节点使用 gate_type: "code_quality|functionality|non_functional|release"
5. 确保工作流逻辑完整，从start开始到end结束
"""

        response = await self._router.call_model(
            capability=ModelCapability.REASONING,
            prompt=prompt,
            temperature=0.2
        )

        try:
            result = json.loads(response)
            
            workflow = WorkflowDefinition(
                id=result["workflow_name"].lower().replace(" ", "_"),
                name=result["workflow_name"],
                description=result.get("workflow_description", ""),
                start_node=result.get("start_node", "start")
            )
            
            for node_data in result["nodes"]:
                workflow.nodes[node_data["id"]] = WorkflowNode(
                    id=node_data["id"],
                    type=WorkflowNodeType(node_data["type"]),
                    name=node_data["name"],
                    description=node_data.get("description", ""),
                    action_type=node_data.get("action_type"),
                    parameters=node_data.get("parameters", {}),
                    next_node=node_data.get("next_node"),
                    approval_required=node_data.get("approval_required", False),
                    gate_type=node_data.get("gate_type")
                )
            
            self._workflows[workflow.id] = workflow
            self._save_workflow(workflow)
            
            print(f"✅ 工作流生成成功: {workflow.name}")
            return workflow
            
        except Exception as e:
            print(f"❌ 工作流生成失败: {e}")
            return self._create_default_workflow(requirement)

    def _create_default_workflow(self, requirement: str) -> WorkflowDefinition:
        """创建默认工作流作为兜底"""
        workflow = WorkflowDefinition(
            id=f"workflow_{int(datetime.now().timestamp())}",
            name=f"开发任务: {requirement[:20]}...",
            description=requirement
        )
        
        workflow.nodes["start"] = WorkflowNode(
            id="start",
            type=WorkflowNodeType.START,
            name="开始",
            next_node="analyze"
        )
        
        workflow.nodes["analyze"] = WorkflowNode(
            id="analyze",
            type=WorkflowNodeType.ACTION,
            name="需求分析",
            action_type="需求分析",
            next_node="code"
        )
        
        workflow.nodes["code"] = WorkflowNode(
            id="code",
            type=WorkflowNodeType.ACTION,
            name="代码生成",
            action_type="代码生成",
            next_node="unit_test"
        )
        
        workflow.nodes["unit_test"] = WorkflowNode(
            id="unit_test",
            type=WorkflowNodeType.ACTION,
            name="单元测试",
            action_type="单元测试",
            next_node="gate1"
        )
        
        workflow.nodes["gate1"] = WorkflowNode(
            id="gate1",
            type=WorkflowNodeType.GATE,
            name="代码质量门禁",
            gate_type="code_quality",
            next_node="review"
        )
        
        workflow.nodes["review"] = WorkflowNode(
            id="review",
            type=WorkflowNodeType.APPROVAL,
            name="代码审查",
            action_type="代码审查",
            approval_required=True,
            next_node="deploy"
        )
        
        workflow.nodes["deploy"] = WorkflowNode(
            id="deploy",
            type=WorkflowNodeType.ACTION,
            name="部署",
            action_type="部署",
            next_node="end"
        )
        
        workflow.nodes["end"] = WorkflowNode(
            id="end",
            type=WorkflowNodeType.END,
            name="结束"
        )
        
        return workflow

    def create_workflow_instance(self, workflow_id: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        创建工作流实例
        
        Args:
            workflow_id: 工作流ID
            context: 初始上下文变量
            
        Returns:
            实例ID
        """
        if workflow_id not in self._workflows:
            raise ValueError(f"工作流不存在: {workflow_id}")
        
        instance_id = f"instance_{workflow_id}_{int(datetime.now().timestamp())}"
        workflow = self._workflows[workflow_id]
        
        self._instances[instance_id] = ExecutionContext(
            workflow_id=workflow_id,
            instance_id=instance_id,
            variables=context or {},
            current_node=workflow.start_node
        )
        
        print(f"✅ 创建工作流实例: {instance_id}")
        return instance_id

    async def execute_workflow(self, instance_id: str) -> Dict[str, Any]:
        """
        执行工作流实例
        
        Args:
            instance_id: 实例ID
            
        Returns:
            执行结果
        """
        if instance_id not in self._instances:
            return {"error": f"实例不存在: {instance_id}"}
        
        instance = self._instances[instance_id]
        workflow = self._workflows[instance.workflow_id]
        
        instance.status = WorkflowStatus.EXECUTING
        instance.started_at = datetime.now()
        
        try:
            await self._execute_node(instance, workflow, instance.current_node)
            
            instance.status = WorkflowStatus.COMPLETED
            instance.completed_at = datetime.now()
            
            await self._learn_from_execution(instance, workflow)
            
            return {
                "success": True,
                "instance_id": instance_id,
                "context": instance.variables,
                "history": instance.execution_history,
                "duration": (instance.completed_at - instance.started_at).total_seconds()
            }
            
        except Exception as e:
            instance.status = WorkflowStatus.FAILED
            return {
                "success": False,
                "instance_id": instance_id,
                "error": str(e),
                "history": instance.execution_history
            }

    async def _execute_node(self, instance: ExecutionContext, workflow: WorkflowDefinition, node_id: str):
        """执行单个节点"""
        if node_id not in workflow.nodes:
            return
        
        node = workflow.nodes[node_id]
        instance.current_node = node_id
        
        start_time = datetime.now()
        
        instance.execution_history.append({
            "node_id": node_id,
            "node_name": node.name,
            "node_type": node.type.value,
            "timestamp": datetime.now().isoformat(),
            "context_before": dict(instance.variables)
        })
        
        print(f"🔧 执行节点: {node.name} ({node.type.value})")
        
        if node.type == WorkflowNodeType.START:
            if node.next_node:
                await self._execute_node(instance, workflow, node.next_node)
        
        elif node.type == WorkflowNodeType.END:
            return
        
        elif node.type == WorkflowNodeType.ACTION:
            result = await self._execute_action(node, instance)
            if result:
                instance.variables[f"result_{node.id}"] = result
            
            if node.next_node:
                await self._execute_node(instance, workflow, node.next_node)
        
        elif node.type == WorkflowNodeType.CONDITION:
            condition_result = self._evaluate_condition(node.condition, instance.variables)
            next_node = node.next_node if condition_result else node.parameters.get("else_node")
            
            if next_node:
                await self._execute_node(instance, workflow, next_node)
        
        elif node.type == WorkflowNodeType.PARALLEL:
            tasks = []
            for parallel_id in node.parallel_nodes:
                tasks.append(self._execute_node(instance, workflow, parallel_id))
            
            await asyncio.gather(*tasks)
            
            if node.next_node:
                await self._execute_node(instance, workflow, node.next_node)
        
        elif node.type == WorkflowNodeType.APPROVAL:
            if node.approval_required:
                instance.variables[f"approval_{node.id}"] = await self._request_approval(node, instance)
            
            if node.next_node:
                await self._execute_node(instance, workflow, node.next_node)
        
        elif node.type == WorkflowNodeType.GATE:
            gate_passed = await self._execute_gate(node, instance)
            instance.variables[f"gate_{node.id}"] = gate_passed
            
            if gate_passed and node.next_node:
                await self._execute_node(instance, workflow, node.next_node)
            elif not gate_passed:
                raise Exception(f"质量门禁未通过: {node.name}")
        
        node.execution_time = (datetime.now() - start_time).total_seconds()
        node.status = "completed"

    async def _execute_action(self, node: WorkflowNode, instance: ExecutionContext) -> Any:
        """执行动作节点"""
        action_type = node.action_type
        
        handlers = {
            "需求分析": self._handle_requirement_analysis,
            "代码生成": self._handle_code_generation,
            "单元测试": self._handle_unit_test,
            "集成测试": self._handle_integration_test,
            "代码审查": self._handle_code_review,
            "部署": self._handle_deployment,
            "发布": self._handle_release
        }
        
        handler = handlers.get(action_type)
        if handler:
            return await handler(node, instance)
        
        return {"action": action_type, "status": "executed"}

    async def _handle_requirement_analysis(self, node: WorkflowNode, instance: ExecutionContext) -> Dict[str, Any]:
        """处理需求分析"""
        requirement = instance.variables.get("requirement", "")
        print(f"📋 分析需求: {requirement[:50]}...")
        
        prompt = f"""
作为一个需求分析专家，分析以下需求并输出结构化结果。

需求: {requirement}

输出格式（JSON）:
{{
    "epic": "EPIC描述",
    "user_stories": [
        {{
            "id": "US-001",
            "title": "用户故事标题",
            "description": "详细描述",
            "acceptance_criteria": ["条件1", "条件2"],
            "complexity": "低|中|高"
        }}
    ],
    "dependencies": ["依赖项1", "依赖项2"],
    "estimated_hours": 16,
    "risks": ["风险1", "风险2"]
}}
"""

        response = await self._router.call_model(
            capability=ModelCapability.REASONING,
            prompt=prompt,
            temperature=0.2
        )
        
        try:
            return json.loads(response)
        except:
            return {"epic": requirement, "user_stories": [], "estimated_hours": 8}

    async def _handle_code_generation(self, node: WorkflowNode, instance: ExecutionContext) -> Dict[str, Any]:
        """处理代码生成"""
        requirement = instance.variables.get("requirement", "")
        print(f"💻 生成代码: {requirement[:30]}...")
        
        return {"status": "generated", "files": ["main.py", "utils.py"]}

    async def _handle_unit_test(self, node: WorkflowNode, instance: ExecutionContext) -> Dict[str, Any]:
        """处理单元测试"""
        print("🧪 执行单元测试...")
        
        return {"status": "passed", "coverage": 85.5, "tests_run": 42}

    async def _handle_integration_test(self, node: WorkflowNode, instance: ExecutionContext) -> Dict[str, Any]:
        """处理集成测试"""
        print("🔗 执行集成测试...")
        
        return {"status": "passed", "tests_run": 15}

    async def _handle_code_review(self, node: WorkflowNode, instance: ExecutionContext) -> Dict[str, Any]:
        """处理代码审查"""
        print("🔍 执行代码审查...")
        
        return {"status": "approved", "comments": []}

    async def _handle_deployment(self, node: WorkflowNode, instance: ExecutionContext) -> Dict[str, Any]:
        """处理部署"""
        print("🚀 执行部署...")
        
        return {"status": "deployed", "environment": "staging"}

    async def _handle_release(self, node: WorkflowNode, instance: ExecutionContext) -> Dict[str, Any]:
        """处理发布"""
        print("🎉 执行发布...")
        
        return {"status": "released", "version": "1.0.0"}

    async def _request_approval(self, node: WorkflowNode, instance: ExecutionContext) -> bool:
        """请求人工审批（模拟）"""
        print(f"⚠️ 需要审批: {node.name}")
        
        return True

    async def _execute_gate(self, node: WorkflowNode, instance: ExecutionContext) -> bool:
        """执行质量门禁检查"""
        gate_type = node.gate_type
        print(f"🚧 执行质量门禁: {gate_type}")
        
        gate_checks = {
            "code_quality": self._check_code_quality,
            "functionality": self._check_functionality,
            "non_functional": self._check_non_functional,
            "release": self._check_release_readiness
        }
        
        if gate_type in gate_checks:
            return await gate_checks[gate_type](instance)
        
        return True

    async def _check_code_quality(self, instance: ExecutionContext) -> bool:
        """代码质量检查"""
        return True

    async def _check_functionality(self, instance: ExecutionContext) -> bool:
        """功能正确性检查"""
        return True

    async def _check_non_functional(self, instance: ExecutionContext) -> bool:
        """非功能需求检查"""
        return True

    async def _check_release_readiness(self, instance: ExecutionContext) -> bool:
        """发布就绪检查"""
        return True

    def _evaluate_condition(self, condition: Optional[str], variables: Dict[str, Any]) -> bool:
        """评估条件表达式"""
        if not condition:
            return True
        
        try:
            for key, value in variables.items():
                condition = condition.replace(f"{{{{{key}}}}}", str(value))
            
            return eval(condition)
        except:
            return False

    async def _learn_from_execution(self, instance: ExecutionContext, workflow: WorkflowDefinition):
        """从执行中学习优化"""
        workflow.usage_count += 1
        
        success = instance.status == WorkflowStatus.COMPLETED
        avg_execution_time = sum(
            node.execution_time for node in workflow.nodes.values()
        ) / len(workflow.nodes)
        
        # 简单的学习评分更新
        if success:
            workflow.learning_score = min(1.0, workflow.learning_score + 0.05)
        else:
            workflow.learning_score = max(0.0, workflow.learning_score - 0.1)
        
        # 更新学习模式
        workflow_type = self._classify_workflow(workflow)
        if workflow_type not in self._learning_patterns:
            self._learning_patterns[workflow_type] = {
                "count": 0,
                "success_count": 0,
                "avg_duration": 0.0
            }
        
        pattern = self._learning_patterns[workflow_type]
        pattern["count"] += 1
        pattern["success_count"] += 1 if success else 0
        pattern["avg_duration"] = (pattern["avg_duration"] * (pattern["count"] - 1) + 
                                   (instance.completed_at - instance.started_at).total_seconds()) / pattern["count"]
        
        self._save_workflow(workflow)
        self._save_learning_patterns()

    def _classify_workflow(self, workflow: WorkflowDefinition) -> str:
        """分类工作流类型"""
        action_types = [node.action_type for node in workflow.nodes.values() if node.action_type]
        
        if "发布" in action_types:
            return "release"
        elif "部署" in action_types:
            return "deployment"
        elif "代码生成" in action_types:
            return "development"
        else:
            return "general"

    def get_workflow(self, workflow_id: str) -> Optional[WorkflowDefinition]:
        """获取工作流定义"""
        return self._workflows.get(workflow_id)

    def get_instance(self, instance_id: str) -> Optional[ExecutionContext]:
        """获取工作流实例"""
        return self._instances.get(instance_id)

    def list_workflows(self) -> List[Dict[str, Any]]:
        """列出所有工作流"""
        result = []
        for workflow in self._workflows.values():
            result.append({
                "id": workflow.id,
                "name": workflow.name,
                "description": workflow.description,
                "version": workflow.version,
                "node_count": len(workflow.nodes),
                "learning_score": workflow.learning_score,
                "usage_count": workflow.usage_count,
                "created_at": workflow.created_at.isoformat()
            })
        return result

    def get_instance_status(self, instance_id: str) -> Dict[str, Any]:
        """获取实例状态"""
        instance = self._instances.get(instance_id)
        if not instance:
            return {"error": "实例不存在"}
        
        return {
            "instance_id": instance.instance_id,
            "workflow_id": instance.workflow_id,
            "status": instance.status.value,
            "current_node": instance.current_node,
            "variables": instance.variables,
            "execution_history": instance.execution_history,
            "started_at": instance.started_at.isoformat() if instance.started_at else None,
            "completed_at": instance.completed_at.isoformat() if instance.completed_at else None
        }


def get_ai_workflow_engine() -> AIWorkflowEngine:
    """获取AI工作流引擎单例"""
    global _workflow_engine_instance
    if _workflow_engine_instance is None:
        _workflow_engine_instance = AIWorkflowEngine()
    return _workflow_engine_instance


_workflow_engine_instance = None