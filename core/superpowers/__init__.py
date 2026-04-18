"""
Superpowers 工作流技能系统
基于 obra/superpowers 思想：AI 可复用的业务流程技能模块

核心思想：
- 一次教，终身用
- 从"野生程序员"到"职业选手"的范式转变
- 减少 LLM 幻觉，确保操作指令符合业务规范
"""

import json
import time
import asyncio
from pathlib import Path
from typing import Optional, Callable, Dict, List, Any
from dataclasses import dataclass, field
from enum import Enum
import hashlib


class WorkflowStatus(Enum):
    IDLE = "idle"
    RECORDING = "recording"
    PLAYING = "playing"
    COMPLETED = "completed"
    FAILED = "failed"


class StepType(Enum):
    ACTION = "action"           # 执行动作
    CONDITION = "condition"     # 条件判断
    INPUT = "input"             # 用户输入
    OUTPUT = "output"           # 输出结果
    LOOP = "loop"               # 循环
    CALL = "call"               # 调用子流程


@dataclass
class WorkflowStep:
    """工作流步骤"""
    id: str
    type: StepType
    name: str
    description: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    result: Any = None
    error: str = ""
    duration: float = 0.0
    timestamp: float = 0.0


@dataclass
class Workflow:
    """可复用工作流"""
    id: str
    name: str
    description: str = ""
    category: str = "general"
    version: str = "1.0.0"
    steps: List[WorkflowStep] = field(default_factory=list)
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    author: str = "user"
    tags: List[str] = field(default_factory=list)
    times_used: int = 0
    success_rate: float = 1.0


@dataclass
class Superpower:
    """超级能力包（Superpower）"""
    id: str
    name: str
    description: str
    workflow: Workflow
    triggers: List[str] = field(default_factory=list)
    conditions: Dict[str, Any] = field(default_factory=dict)
    variables: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class WorkflowRecorder:
    """工作流录制器 - 记录用户操作步骤"""

    def __init__(self, workflow_id: str, name: str):
        self.workflow_id = workflow_id
        self.name = name
        self.status = WorkflowStatus.IDLE
        self.steps: List[WorkflowStep] = []
        self.start_time = 0.0
        self._step_counter = 0

    def start_recording(self):
        """开始录制"""
        self.status = WorkflowStatus.RECORDING
        self.start_time = time.time()
        self.steps = []
        print(f"[Superpowers] Started recording: {self.name}")

    def record_step(
        self,
        step_type: StepType,
        name: str,
        params: Dict[str, Any] = None,
        description: str = ""
    ) -> str:
        """记录一个步骤"""
        if self.status != WorkflowStatus.RECORDING:
            return ""

        self._step_counter += 1
        step_id = f"step_{self._step_counter}_{int(time.time())}"

        step = WorkflowStep(
            id=step_id,
            type=step_type,
            name=name,
            params=params or {},
            description=description,
            timestamp=time.time()
        )

        self.steps.append(step)
        print(f"[Superpowers] Recorded: [{step_type.value}] {name}")
        return step_id

    def complete_step(self, step_id: str, result: Any = None, error: str = ""):
        """完成步骤录制"""
        for step in self.steps:
            if step.id == step_id:
                step.result = result
                step.error = error
                step.duration = time.time() - step.timestamp
                break

    def stop_recording(self) -> Workflow:
        """停止录制并返回工作流"""
        self.status = WorkflowStatus.COMPLETED

        workflow = Workflow(
            id=self.workflow_id,
            name=self.name,
            steps=self.steps
        )

        print(f"[Superpowers] Stopped recording: {self.name} ({len(self.steps)} steps)")
        return workflow


class WorkflowPlayer:
    """工作流播放器 - 回放已录制的工作流"""

    def __init__(self, workflow: Workflow):
        self.workflow = workflow
        self.status = WorkflowStatus.IDLE
        self.current_step = 0
        self.context: Dict[str, Any] = {}

    async def execute(
        self,
        input_params: Dict[str, Any] = None,
        callbacks: Dict[str, Callable] = None
    ) -> Dict[str, Any]:
        """执行工作流"""
        self.status = WorkflowStatus.PLAYING
        self.context = input_params or {}

        callbacks = callbacks or {}

        print(f"[Superpowers] Playing workflow: {self.workflow.name}")

        for step in self.workflow.steps:
            self.current_step += 1
            print(f"[Superpowers] Step {self.current_step}: [{step.type.value}] {step.name}")

            try:
                if step.type == StepType.ACTION:
                    # 执行动作
                    result = await self._execute_action(step, callbacks)
                    step.result = result

                elif step.type == StepType.CONDITION:
                    # 条件判断
                    result = await self._evaluate_condition(step, callbacks)
                    if not result:
                        print(f"[Superpowers] Condition false, skipping remaining steps")
                        break

                elif step.type == StepType.INPUT:
                    # 获取输入
                    step.result = self.context.get(step.name, "")

                elif step.type == StepType.CALL:
                    # 调用子流程（递归）
                    pass

            except Exception as e:
                step.error = str(e)
                self.status = WorkflowStatus.FAILED
                print(f"[Superpowers] Step failed: {e}")
                break

        self.status = WorkflowStatus.COMPLETED
        return self.context

    async def _execute_action(self, step: WorkflowStep, callbacks: Dict) -> Any:
        """执行动作步骤"""
        action_name = step.params.get("action", "")
        params = step.params.get("params", {})

        # 合并上下文变量
        for k, v in self.context.items():
            if k not in params:
                params[k] = v

        # 调用回调
        if action_name in callbacks:
            return await callbacks[action_name](**params)

        return {"status": "ok"}

    async def _evaluate_condition(self, step: WorkflowStep, callbacks: Dict) -> bool:
        """评估条件"""
        condition = step.params.get("condition", "")
        # 简单条件评估
        if "==" in condition:
            k, v = condition.split("==")
            return str(self.context.get(k.strip(), "")).strip() == v.strip()
        return True


class SuperpowerRegistry:
    """超级能力注册表"""

    def __init__(self, storage_dir: str = None):
        self.storage_dir = Path(storage_dir or "./data/superpowers")
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.superpowers: Dict[str, Superpower] = {}
        self._load_from_disk()

    def _load_from_disk(self):
        """从磁盘加载"""
        index_file = self.storage_dir / "index.json"
        if index_file.exists():
            data = json.loads(index_file.read_text())
            for sp_data in data.get("superpowers", []):
                workflow = self._load_workflow(sp_data["workflow_id"])
                if workflow:
                    self.superpowers[sp_data["id"]] = Superpower(
                        id=sp_data["id"],
                        name=sp_data["name"],
                        description=sp_data["description"],
                        workflow=workflow,
                        triggers=sp_data.get("triggers", [])
                    )

    def _load_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """加载工作流"""
        wf_file = self.storage_dir / f"{workflow_id}.json"
        if wf_file.exists():
            data = json.loads(wf_file.read_text())
            steps = [WorkflowStep(**s) for s in data.get("steps", [])]
            return Workflow(
                id=data["id"],
                name=data["name"],
                description=data.get("description", ""),
                category=data.get("category", "general"),
                steps=steps,
                inputs=data.get("inputs", {}),
                outputs=data.get("outputs", {})
            )
        return None

    def register(self, superpower: Superpower):
        """注册超级能力"""
        self.superpowers[superpower.id] = superpower

        # 保存到磁盘
        self._save_workflow(superpower.workflow)
        self._save_index()

        print(f"[Superpowers] Registered: {superpower.name}")

    def _save_workflow(self, workflow: Workflow):
        """保存工作流"""
        wf_file = self.storage_dir / f"{workflow.id}.json"
        data = {
            "id": workflow.id,
            "name": workflow.name,
            "description": workflow.description,
            "category": workflow.category,
            "steps": [
                {
                    "id": s.id,
                    "type": s.type.value,
                    "name": s.name,
                    "params": s.params,
                    "description": s.description
                }
                for s in workflow.steps
            ],
            "inputs": workflow.inputs,
            "outputs": workflow.outputs
        }
        wf_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def _save_index(self):
        """保存索引"""
        index_file = self.storage_dir / "index.json"
        data = {
            "superpowers": [
                {
                    "id": sp.id,
                    "name": sp.name,
                    "description": sp.description,
                    "workflow_id": sp.workflow.id,
                    "triggers": sp.triggers
                }
                for sp in self.superpowers.values()
            ]
        }
        index_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def get(self, superpower_id: str) -> Optional[Superpower]:
        """获取超级能力"""
        return self.superpowers.get(superpower_id)

    def find_by_trigger(self, trigger: str) -> List[Superpower]:
        """根据触发词查找"""
        return [
            sp for sp in self.superpowers.values()
            if trigger in sp.triggers
        ]

    def list_all(self) -> List[Superpower]:
        """列出所有超级能力"""
        return list(self.superpowers.values())


# ==================== 内置电商超级能力 ====================

def create_listing_superpower() -> Superpower:
    """创建商品上架超级能力"""
    steps = [
        WorkflowStep(
            id="step_1",
            type=StepType.INPUT,
            name="product_name",
            description="商品名称"
        ),
        WorkflowStep(
            id="step_2",
            type=StepType.INPUT,
            name="price",
            description="商品价格"
        ),
        WorkflowStep(
            id="step_3",
            type=StepType.INPUT,
            name="description",
            description="商品描述"
        ),
        WorkflowStep(
            id="step_4",
            type=StepType.ACTION,
            name="validate_input",
            params={"action": "validate", "fields": ["product_name", "price"]}
        ),
        WorkflowStep(
            id="step_5",
            type=StepType.ACTION,
            name="create_listing",
            params={"action": "create_listing"}
        ),
        WorkflowStep(
            id="step_6",
            type=StepType.OUTPUT,
            name="listing_id",
            description="上架成功的商品ID"
        )
    ]

    workflow = Workflow(
        id="wf_listing_v1",
        name="商品上架流程",
        description="标准商品上架工作流",
        category="ecommerce",
        steps=steps
    )

    return Superpower(
        id="sp_ecommerce_listing",
        name="商品上架",
        description="标准商品上架流程，包含信息录入、验证、发布",
        workflow=workflow,
        triggers=["上架商品", "发布商品", "new listing"]
    )


def create_refund_superpower() -> Superpower:
    """创建售后退款超级能力"""
    steps = [
        WorkflowStep(
            id="step_1",
            type=StepType.INPUT,
            name="order_id",
            description="订单号"
        ),
        WorkflowStep(
            id="step_2",
            type=StepType.INPUT,
            name="reason",
            description="退款原因"
        ),
        WorkflowStep(
            id="step_3",
            type=StepType.ACTION,
            name="verify_order",
            params={"action": "verify_order_status"}
        ),
        WorkflowStep(
            id="step_4",
            type=StepType.CONDITION,
            name="order_valid",
            params={"condition": "order_status==paid"}
        ),
        WorkflowStep(
            id="step_5",
            type=StepType.ACTION,
            name="process_refund",
            params={"action": "refund"}
        )
    ]

    workflow = Workflow(
        id="wf_refund_v1",
        name="售后退款流程",
        description="标准退款处理工作流",
        category="ecommerce",
        steps=steps
    )

    return Superpower(
        id="sp_ecommerce_refund",
        name="售后退款",
        description="订单验证+退款处理标准化流程",
        workflow=workflow,
        triggers=["退款", "售后", "refund"]
    )


# ==================== 单例 ====================

_registry: Optional[SuperpowerRegistry] = None


def get_superpower_registry() -> SuperpowerRegistry:
    """获取超级能力注册表单例"""
    global _registry
    if _registry is None:
        _registry = SuperpowerRegistry()
        # 注册内置超级能力
        _registry.register(create_listing_superpower())
        _registry.register(create_refund_superpower())
    return _registry
