"""
状态管理模块

管理 GSD 项目状态：
- ProjectState: 项目状态
- PhaseState: 阶段状态
- StateManager: 状态管理器
"""

import json
import time
from pathlib import Path
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import threading


class StateVersion(Enum):
    """状态版本"""
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


@dataclass
class Decision:
    """决策"""
    decision_id: str
    description: str
    rationale: str
    created_at: float = field(default_factory=time.time)
    created_by: str = "system"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Blocker:
    """阻塞项"""
    blocker_id: str
    description: str
    severity: str = "medium"
    created_at: float = field(default_factory=time.time)
    resolved_at: Optional[float] = None
    resolution: Optional[str] = None


@dataclass
class Assumption:
    """假设"""
    assumption_id: str
    description: str
    validated: bool = False
    validated_at: Optional[float] = None
    created_at: float = field(default_factory=time.time)


@dataclass
class PhaseState:
    """阶段状态"""
    phase_id: int
    name: str
    status: str
    decisions: List[Decision] = field(default_factory=list)
    blockers: List[Blocker] = field(default_factory=list)
    assumptions: List[Assumption] = field(default_factory=list)
    current_plan_index: int = 0
    completed_tasks: List[str] = field(default_factory=list)
    pending_tasks: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class ProjectState:
    """项目状态"""
    project_id: str
    name: str
    version: StateVersion = StateVersion.DRAFT
    current_phase: int = 1
    completed_phases: List[int] = field(default_factory=list)
    global_decisions: List[Decision] = field(default_factory=list)
    global_blockers: List[Blocker] = field(default_factory=list)
    phase_states: List[PhaseState] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class StateManager:
    """
    状态管理器

    功能：
    1. 持久化项目状态
    2. 版本控制
    3. 状态验证
    4. 状态同步
    """

    def __init__(self, state_file: Optional[str | Path] = None):
        self.state_file = Path(state_file) if state_file else Path(".planning/state.json")
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._state: Optional[ProjectState] = None
        self._version_history: List[Dict[str, Any]] = []
        self._observers: List[Callable] = []
        self._load_state()

    def _load_state(self):
        """加载状态"""
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text(encoding='utf-8'))
                self._state = self._dict_to_state(data)
            except Exception as e:
                print(f"[StateManager] Failed to load state: {e}")
                self._state = None

    def _save_state(self):
        """保存状态"""
        if self._state:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            data = self._state_to_dict(self._state)
            self.state_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')

    def _state_to_dict(self, state: ProjectState) -> Dict[str, Any]:
        """状态转字典"""
        return {
            "project_id": state.project_id,
            "name": state.name,
            "version": state.version.value,
            "current_phase": state.current_phase,
            "completed_phases": state.completed_phases,
            "global_decisions": [
                {
                    "decision_id": d.decision_id,
                    "description": d.description,
                    "rationale": d.rationale,
                    "created_at": d.created_at,
                    "created_by": d.created_by,
                    "metadata": d.metadata
                }
                for d in state.global_decisions
            ],
            "global_blockers": [
                {
                    "blocker_id": b.blocker_id,
                    "description": b.description,
                    "severity": b.severity,
                    "created_at": b.created_at,
                    "resolved_at": b.resolved_at,
                    "resolution": b.resolution
                }
                for b in state.global_blockers
            ],
            "phase_states": [
                {
                    "phase_id": p.phase_id,
                    "name": p.name,
                    "status": p.status,
                    "decisions": [
                        {
                            "decision_id": d.decision_id,
                            "description": d.description,
                            "rationale": d.rationale,
                            "created_at": d.created_at
                        }
                        for d in p.decisions
                    ],
                    "blockers": [
                        {
                            "blocker_id": b.blocker_id,
                            "description": b.description,
                            "severity": b.severity,
                            "created_at": b.created_at,
                            "resolved_at": b.resolved_at,
                            "resolution": b.resolution
                        }
                        for b in p.blockers
                    ],
                    "assumptions": [
                        {
                            "assumption_id": a.assumption_id,
                            "description": a.description,
                            "validated": a.validated,
                            "validated_at": a.validated_at,
                            "created_at": a.created_at
                        }
                        for a in p.assumptions
                    ],
                    "current_plan_index": p.current_plan_index,
                    "completed_tasks": p.completed_tasks,
                    "pending_tasks": p.pending_tasks,
                    "created_at": p.created_at,
                    "updated_at": p.updated_at
                }
                for p in state.phase_states
            ],
            "metadata": state.metadata,
            "created_at": state.created_at,
            "updated_at": state.updated_at
        }

    def _dict_to_state(self, data: Dict[str, Any]) -> ProjectState:
        """字典转状态"""
        state = ProjectState(
            project_id=data["project_id"],
            name=data["name"],
            version=StateVersion(data.get("version", "draft")),
            current_phase=data.get("current_phase", 1),
            completed_phases=data.get("completed_phases", []),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time())
        )

        for d_data in data.get("global_decisions", []):
            state.global_decisions.append(Decision(
                decision_id=d_data["decision_id"],
                description=d_data["description"],
                rationale=d_data["rationale"],
                created_at=d_data.get("created_at", time.time()),
                created_by=d_data.get("created_by", "system")
            ))

        for b_data in data.get("global_blockers", []):
            state.global_blockers.append(Blocker(
                blocker_id=b_data["blocker_id"],
                description=b_data["description"],
                severity=b_data.get("severity", "medium"),
                created_at=b_data.get("created_at", time.time()),
                resolved_at=b_data.get("resolved_at"),
                resolution=b_data.get("resolution")
            ))

        for p_data in data.get("phase_states", []):
            phase = PhaseState(
                phase_id=p_data["phase_id"],
                name=p_data["name"],
                status=p_data.get("status", "pending"),
                current_plan_index=p_data.get("current_plan_index", 0),
                completed_tasks=p_data.get("completed_tasks", []),
                pending_tasks=p_data.get("pending_tasks", []),
                created_at=p_data.get("created_at", time.time()),
                updated_at=p_data.get("updated_at", time.time())
            )

            for d_data in p_data.get("decisions", []):
                phase.decisions.append(Decision(
                    decision_id=d_data["decision_id"],
                    description=d_data["description"],
                    rationale=d_data["rationale"],
                    created_at=d_data.get("created_at", time.time())
                ))

            for b_data in p_data.get("blockers", []):
                phase.blockers.append(Blocker(
                    blocker_id=b_data["blocker_id"],
                    description=b_data["description"],
                    severity=b_data.get("severity", "medium"),
                    created_at=b_data.get("created_at", time.time()),
                    resolved_at=b_data.get("resolved_at"),
                    resolution=b_data.get("resolution")
                ))

            for a_data in p_data.get("assumptions", []):
                phase.assumptions.append(Assumption(
                    assumption_id=a_data["assumption_id"],
                    description=a_data["description"],
                    validated=a_data.get("validated", False),
                    validated_at=a_data.get("validated_at"),
                    created_at=a_data.get("created_at", time.time())
                ))

            state.phase_states.append(phase)

        return state

    def init_project(self, project_id: str, name: str) -> ProjectState:
        """
        初始化项目

        Args:
            project_id: 项目 ID
            name: 项目名称

        Returns:
            ProjectState: 初始状态
        """
        with self._lock:
            self._state = ProjectState(
                project_id=project_id,
                name=name
            )
            self._save_state()
            self._notify_observers("project_init", self._state)
            return self._state

    def get_state(self) -> Optional[ProjectState]:
        """获取当前状态"""
        return self._state

    def add_phase(self, phase_id: int, name: str) -> PhaseState:
        """
        添加阶段

        Args:
            phase_id: 阶段 ID
            name: 阶段名称

        Returns:
            PhaseState: 阶段状态
        """
        with self._lock:
            if not self._state:
                raise RuntimeError("Project not initialized")

            phase = PhaseState(
                phase_id=phase_id,
                name=name,
                status="pending"
            )
            self._state.phase_states.append(phase)
            self._state.updated_at = time.time()
            self._save_state()
            self._notify_observers("phase_added", phase)
            return phase

    def update_phase_status(self, phase_id: int, status: str):
        """
        更新阶段状态

        Args:
            phase_id: 阶段 ID
            status: 新状态
        """
        with self._lock:
            if not self._state:
                return

            for phase in self._state.phase_states:
                if phase.phase_id == phase_id:
                    phase.status = status
                    phase.updated_at = time.time()
                    break

            self._state.updated_at = time.time()
            self._save_state()
            self._notify_observers("phase_status_updated", phase_id, status)

    def add_decision(
        self,
        description: str,
        rationale: str,
        phase_id: Optional[int] = None,
        created_by: str = "system"
    ) -> Decision:
        """
        添加决策

        Args:
            description: 决策描述
            rationale: 决策理由
            phase_id: 阶段 ID（可选）
            created_by: 创建者

        Returns:
            Decision: 创建的决策
        """
        import uuid
        decision = Decision(
            decision_id=str(uuid.uuid4())[:8],
            description=description,
            rationale=rationale,
            created_by=created_by
        )

        with self._lock:
            if phase_id is None:
                self._state.global_decisions.append(decision)
            else:
                for phase in self._state.phase_states:
                    if phase.phase_id == phase_id:
                        phase.decisions.append(decision)
                        break

            self._state.updated_at = time.time()
            self._save_state()
            self._notify_observers("decision_added", decision)

        return decision

    def add_blocker(
        self,
        description: str,
        severity: str = "medium",
        phase_id: Optional[int] = None
    ) -> Blocker:
        """
        添加阻塞项

        Args:
            description: 描述
            severity: 严重程度
            phase_id: 阶段 ID（可选）

        Returns:
            Blocker: 创建的阻塞项
        """
        import uuid
        blocker = Blocker(
            blocker_id=str(uuid.uuid4())[:8],
            description=description,
            severity=severity
        )

        with self._lock:
            if phase_id is None:
                self._state.global_blockers.append(blocker)
            else:
                for phase in self._state.phase_states:
                    if phase.phase_id == phase_id:
                        phase.blockers.append(blocker)
                        break

            self._state.updated_at = time.time()
            self._save_state()
            self._notify_observers("blocker_added", blocker)

        return blocker

    def resolve_blocker(self, blocker_id: str, resolution: str):
        """
        解决阻塞项

        Args:
            blocker_id: 阻塞项 ID
            resolution: 解决方案
        """
        with self._lock:
            if not self._state:
                return

            for blocker in self._state.global_blockers:
                if blocker.blocker_id == blocker_id:
                    blocker.resolved_at = time.time()
                    blocker.resolution = resolution
                    break

            for phase in self._state.phase_states:
                for blocker in phase.blockers:
                    if blocker.blocker_id == blocker_id:
                        blocker.resolved_at = time.time()
                        blocker.resolution = resolution
                        break

            self._state.updated_at = time.time()
            self._save_state()
            self._notify_observers("blocker_resolved", blocker_id)

    def add_assumption(
        self,
        description: str,
        phase_id: int
    ) -> Assumption:
        """
        添加假设

        Args:
            description: 假设描述
            phase_id: 阶段 ID

        Returns:
            Assumption: 创建的假设
        """
        import uuid
        assumption = Assumption(
            assumption_id=str(uuid.uuid4())[:8],
            description=description
        )

        with self._lock:
            for phase in self._state.phase_states:
                if phase.phase_id == phase_id:
                    phase.assumptions.append(assumption)
                    break

            self._state.updated_at = time.time()
            self._save_state()
            self._notify_observers("assumption_added", assumption)

        return assumption

    def validate_assumption(self, assumption_id: str, phase_id: int, valid: bool):
        """
        验证假设

        Args:
            assumption_id: 假设 ID
            phase_id: 阶段 ID
            valid: 是否有效
        """
        with self._lock:
            for phase in self._state.phase_states:
                if phase.phase_id == phase_id:
                    for assumption in phase.assumptions:
                        if assumption.assumption_id == assumption_id:
                            assumption.validated = valid
                            assumption.validated_at = time.time()
                            break
                    break

            self._state.updated_at = time.time()
            self._save_state()
            self._notify_observers("assumption_validated", assumption_id, valid)

    def complete_phase(self, phase_id: int):
        """
        完成阶段

        Args:
            phase_id: 阶段 ID
        """
        with self._lock:
            if not self._state:
                return

            self.update_phase_status(phase_id, "completed")

            if phase_id not in self._state.completed_phases:
                self._state.completed_phases.append(phase_id)

            if phase_id >= self._state.current_phase:
                self._state.current_phase = phase_id + 1

            self._state.updated_at = time.time()
            self._save_state()
            self._notify_observers("phase_completed", phase_id)

    def validate_state(self) -> Dict[str, Any]:
        """
        验证状态

        Returns:
            Dict: 验证结果
        """
        issues = []

        if not self._state:
            issues.append("Project not initialized")
            return {"valid": False, "issues": issues}

        unresolved_blockers = [
            b.blocker_id for b in self._state.global_blockers
            if b.resolved_at is None
        ]
        if unresolved_blockers:
            issues.append(f"Unresolved global blockers: {unresolved_blockers}")

        for phase in self._state.phase_states:
            unresolved_phase_blockers = [
                b.blocker_id for b in phase.blockers
                if b.resolved_at is None
            ]
            if unresolved_phase_blockers:
                issues.append(
                    f"Phase {phase.phase_id} has unresolved blockers: {unresolved_phase_blockers}"
                )

            unvalidated_assumptions = [
                a.assumption_id for a in phase.assumptions
                if not a.validated
            ]
            if unvalidated_assumptions:
                issues.append(
                    f"Phase {phase.phase_id} has unvalidated assumptions: {unvalidated_assumptions}"
                )

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "current_phase": self._state.current_phase,
            "completed_phases": self._state.completed_phases
        }

    def get_summary(self) -> Dict[str, Any]:
        """获取状态摘要"""
        if not self._state:
            return {"initialized": False}

        return {
            "initialized": True,
            "project_id": self._state.project_id,
            "name": self._state.name,
            "version": self._state.version.value,
            "current_phase": self._state.current_phase,
            "completed_phases": self._state.completed_phases,
            "total_phases": len(self._state.phase_states),
            "global_blockers": len([b for b in self._state.global_blockers if b.resolved_at is None]),
            "global_decisions": len(self._state.global_decisions),
            "last_updated": self._state.updated_at
        }

    def sync_from_filesystem(self, root_path: Path):
        """
        从文件系统同步状态

        Args:
            root_path: 根目录
        """
        planning_dir = root_path / ".planning"

        existing_files = []
        if planning_dir.exists():
            existing_files = list(planning_dir.glob("**/*"))

        modified = False

        if self._state:
            for phase in self._state.phase_states:
                phase_dir = planning_dir / f"phase-{phase.phase_id}"
                if not phase_dir.exists():
                    phase_dir.mkdir(parents=True, exist_ok=True)
                    modified = True

        if modified:
            self._save_state()
            self._notify_observers("state_synced", root_path)

    def observe(self, callback: Callable):
        """注册观察者"""
        self._observers.append(callback)

    def _notify_observers(self, event: str, *args):
        """通知观察者"""
        for observer in self._observers:
            try:
                observer(event, *args)
            except Exception as e:
                print(f"[StateManager] Observer error: {e}")


_global_state_manager: Optional[StateManager] = None


def get_state_manager(state_file: Optional[str] = None) -> StateManager:
    """获取状态管理器"""
    global _global_state_manager
    if _global_state_manager is None:
        _global_state_manager = StateManager(state_file)
    return _global_state_manager