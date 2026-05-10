"""Overnight task — long-running autonomous task orchestrator v2.0.

Proper execution engine with:
- LLM-powered step decomposition and execution
- Step-by-step progress tracking
- Pause/resume/cancel with state persistence
- Result/report retrieval
- REST API + Living Canvas UI ready
"""

from __future__ import annotations

import asyncio
import json as _json
import time as _time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from loguru import logger


class OvernightStatus(Enum):
    IDLE = "idle"
    PLANNING = "planning"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskStep:
    step_num: int
    name: str
    status: str = "pending"
    result: str = ""
    started_at: float = 0.0
    completed_at: float = 0.0


@dataclass
class OvernightTask:
    hub: object

    _goal: str = ""
    _status: OvernightStatus = OvernightStatus.IDLE
    _progress: float = 0.0
    _result: Optional[str] = None
    _report_path: str = ""
    _started_at: float = 0.0
    _error: str = ""
    _task_id: str = ""
    _steps: list[TaskStep] = field(default_factory=list)
    _current_step: int = 0
    _paused_at_step: int = 0
    _cancel_event: Optional[asyncio.Event] = None
    _output_dir: Path = field(default_factory=lambda: Path("./data/output/tasks"))

    @property
    def status(self):
        return self._status

    @property
    def goal(self) -> str:
        return self._goal

    @property
    def progress(self) -> float:
        return self._progress

    @property
    def result(self) -> Optional[str]:
        return self._result

    def to_dict(self) -> dict:
        return {
            "task_id": self._task_id,
            "goal": self._goal,
            "state": self._status.value,
            "percent": round(self._progress * 100, 1),
            "current_step": self._steps[self._current_step].name if self._steps and self._current_step < len(self._steps) else "",
            "completed_steps": sum(1 for s in self._steps if s.status == "done"),
            "total_steps": len(self._steps),
            "steps": [{"num": s.step_num, "name": s.name, "status": s.status, "result": s.result[:200]} for s in self._steps],
            "report_path": self._report_path,
            "elapsed_seconds": _time.time() - self._started_at if self._started_at else 0,
            "error": self._error,
        }

    async def start(self, goal: str, auto_execute: bool = True) -> dict:
        self._goal = goal
        self._status = OvernightStatus.PLANNING
        self._progress = 0.0
        self._result = None
        self._report_path = ""
        self._error = ""
        self._started_at = _time.time()
        self._task_id = f"task_{int(self._started_at)}"
        self._steps = []
        self._current_step = 0
        self._cancel_event = asyncio.Event()
        self._output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"OvernightTask [{self._task_id}] planning: {goal[:60]}")

        try:
            consc = self._get_consciousness()
            if consc:
                resp = await consc.chain_of_thought(
                    f"将以下任务分解为3-8个具体执行步骤。输出JSON: "
                    f'{{"steps":["步骤1描述","步骤2描述",...]}}\n\n任务: {goal}',
                    steps=1,
                )
                text = resp if isinstance(resp, str) else ""
                try:
                    data = _json.loads(text[text.find("{"):text.rfind("}") + 1])
                    step_names = data.get("steps", [])
                except Exception:
                    step_names = [s.strip() for s in text.split("\n") if s.strip() and len(s) > 5][:8]

                if not step_names:
                    step_names = ["分析任务", "规划方案", "执行任务", "验证结果", "生成报告"]

                self._steps = [
                    TaskStep(step_num=i + 1, name=name)
                    for i, name in enumerate(step_names[:8])
                ]
            else:
                self._steps = [
                    TaskStep(step_num=1, name="分析任务"),
                    TaskStep(step_num=2, name="执行任务"),
                    TaskStep(step_num=3, name="生成报告"),
                ]
        except Exception as e:
            logger.debug(f"Task planning fallback: {e}")
            self._steps = [
                TaskStep(step_num=1, name="分析任务"),
                TaskStep(step_num=2, name="执行任务"),
                TaskStep(step_num=3, name="生成报告"),
            ]

        self._progress = 0.05
        self._status = OvernightStatus.RUNNING

        if auto_execute:
            asyncio.create_task(self._execute())

        return self.to_dict()

    async def _execute(self) -> None:
        total = len(self._steps)
        if total == 0:
            self._status = OvernightStatus.COMPLETED
            self._progress = 1.0
            return

        results = []
        for i, step in enumerate(self._steps):
            if self._cancel_event and self._cancel_event.is_set():
                self._status = OvernightStatus.CANCELLED
                self._save_state()
                return

            while self._status == OvernightStatus.PAUSED:
                await asyncio.sleep(1)
                if self._cancel_event and self._cancel_event.is_set():
                    self._status = OvernightStatus.CANCELLED
                    self._save_state()
                    return

            self._current_step = i
            step.status = "running"
            step.started_at = _time.time()

            try:
                result = await self._execute_step(step)
                step.result = result
                step.status = "done"
                step.completed_at = _time.time()
                results.append(f"## {step.name}\n\n{result}")
            except Exception as e:
                step.status = "failed"
                step.result = str(e)[:500]
                self._error = str(e)
                logger.warning(f"Task [{self._task_id}] step {step.step_num} failed: {e}")

            self._progress = (i + 1) / total
            self._save_state()

        self._result = "\n\n".join(results)
        self._status = OvernightStatus.COMPLETED
        self._progress = 1.0

        report_path = self._output_dir / f"{self._task_id}_report.md"
        try:
            report_path.write_text(
                f"# 任务报告\n\n目标: {self._goal}\n\n耗时: {_time.time() - self._started_at:.0f}秒\n\n{self._result}",
                encoding="utf-8",
            )
            self._report_path = str(report_path)
        except Exception as e:
            logger.debug(f"Report save failed: {e}")

        self._save_state()
        logger.info(f"OvernightTask [{self._task_id}] completed: {self._goal[:40]}")

    async def _execute_step(self, step: TaskStep) -> str:
        consc = self._get_consciousness()
        if consc:
            prompt = (
                f"正在执行挂机任务。总目标: {self._goal}\n\n"
                f"当前步骤({step.step_num}/{len(self._steps)}): {step.name}\n\n"
                f"请完成此步骤并输出结果。使用Markdown格式，包含具体内容。"
            )
            resp = await consc.chain_of_thought(prompt, steps=2)
            return resp if isinstance(resp, str) else str(resp)

        return f"步骤 '{step.name}' 已完成。（离线模式）"

    def _get_consciousness(self):
        try:
            world = getattr(self.hub, "world", None)
            if world:
                return getattr(world, "consciousness", None)
        except Exception:
            pass
        return None

    def pause(self):
        if self._status == OvernightStatus.RUNNING:
            self._status = OvernightStatus.PAUSED
            self._paused_at_step = self._current_step
            self._save_state()

    async def resume(self) -> Optional[dict]:
        if self._status == OvernightStatus.PAUSED:
            self._status = OvernightStatus.RUNNING
            return self.to_dict()
        return None

    def stop(self):
        if self._cancel_event:
            self._cancel_event.set()
        self._status = OvernightStatus.CANCELLED
        self._save_state()

    def cancel(self):
        self.stop()

    def _save_state(self):
        try:
            state_path = self._output_dir / f"{self._task_id}_state.json"
            state_path.write_text(_json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    @classmethod
    def load_state(cls, hub, task_id: str) -> Optional[OvernightTask]:
        try:
            output_dir = Path("./data/output/tasks")
            state_path = output_dir / f"{task_id}_state.json"
            if not state_path.exists():
                return None
            data = _json.loads(state_path.read_text(encoding="utf-8"))
            task = cls(hub)
            task._task_id = data.get("task_id", "")
            task._goal = data.get("goal", "")
            task._status = OvernightStatus(data.get("state", "idle"))
            task._progress = data.get("percent", 0) / 100
            task._result = data.get("result")
            task._report_path = data.get("report_path", "")
            task._started_at = _time.time() - data.get("elapsed_seconds", 0)
            task._error = data.get("error", "")
            steps_data = data.get("steps", [])
            task._steps = [
                TaskStep(
                    step_num=s.get("num", i + 1),
                    name=s.get("name", ""),
                    status=s.get("status", "pending"),
                    result=s.get("result", ""),
                )
                for i, s in enumerate(steps_data)
            ]
            task._current_step = sum(1 for s in task._steps if s.status == "done")
            task._cancel_event = asyncio.Event()
            logger.info(f"OvernightTask loaded: {task._task_id}")
            return task
        except Exception as e:
            logger.debug(f"Task load failed: {e}")
            return None


def get_overnight_task(hub: object = None) -> OvernightTask:
    return OvernightTask(hub)
