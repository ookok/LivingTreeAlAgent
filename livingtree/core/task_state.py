"""Task State Manager — structured state persistence for long-running agent tasks.

Claude 4 Multi-Context Window pattern:
  - tests.json: structured test/verification state
  - progress.txt: unstructured progress notes
  - git log: checkpoint for resume across sessions

LivingTree implementation:
  - task_state.json: structured task progress (completed/total/current)
  - progress.md: human-readable progress log
  - Auto-checkpoint: save state before context window exhaustion
  - Resume: discover state from filesystem on restart
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


@dataclass
class TaskProgress:
    """Structured task progress — like Claude 4's tests.json."""
    task_id: str
    task_name: str
    total_items: int = 0
    completed_items: int = 0
    failed_items: int = 0
    current_item: str = ""
    current_index: int = 0
    percent: float = 0.0
    items: list[dict] = field(default_factory=list)  # [{id, status, result}]
    started_at: str = ""
    last_checkpoint: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass
class ProgressNote:
    """Unstructured progress note — like Claude 4's progress.txt."""
    session: str = ""
    timestamp: str = ""
    summary: str = ""
    next_steps: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    notes: str = ""


class TaskStateManager:
    """Structured state persistence for resume-able agent tasks.

    Usage:
        tsm = TaskStateManager("~/.livingtree/tasks")
        
        # Start a patrol task
        tsm.start_task("patrol_20260506", "环境公告巡逻", total_sites=100)
        
        # Update progress
        tsm.update_progress(completed=47, current="site_48")
        
        # Before context window exhaustion → checkpoint
        tsm.checkpoint("Context window nearly full — saving state")
        
        # On restart → auto-discover and resume
        task = tsm.discover_and_resume("patrol")
        print(f"Resuming: {task.completed_items}/{task.total_items} done")
    """

    def __init__(self, data_dir: str = ""):
        self._data_dir = data_dir or os.path.expanduser("~/.livingtree/tasks")
        os.makedirs(self._data_dir, exist_ok=True)
        self._active_task: Optional[TaskProgress] = None

    def start_task(self, task_id: str, task_name: str,
                   total_items: int = 0,
                   items: list[dict] = None) -> TaskProgress:
        """Start a new task with structured progress tracking."""
        task = TaskProgress(
            task_id=task_id,
            task_name=task_name,
            total_items=total_items,
            started_at=time.strftime("%Y-%m-%d %H:%M"),
            last_checkpoint=time.strftime("%Y-%m-%d %H:%M"),
            items=items or [],
        )
        self._active_task = task
        self._save(task)
        self._write_progress_note(task_id, ProgressNote(
            session="start",
            timestamp=task.started_at,
            summary=f"Task started: {task_name} ({total_items} items)",
        ))
        logger.info("TaskState: started '%s' — %d items", task_id, total_items)
        return task

    def update_progress(self, task_id: str = "",
                        completed: int = -1, failed: int = -1,
                        current: str = "", item_status: dict = None) -> Optional[TaskProgress]:
        """Update progress of the active task."""
        task = self._active_task or self._load(task_id)
        if not task:
            return None

        if completed >= 0:
            task.completed_items = completed
        if failed >= 0:
            task.failed_items = failed
        if current:
            task.current_item = current

        if item_status:
            task.items.append(item_status)

        task.percent = (task.completed_items / max(task.total_items, 1)) * 100
        task.last_checkpoint = time.strftime("%Y-%m-%d %H:%M")
        self._save(task)

        if task.completed_items % 10 == 0 or task.percent >= 100:
            self._write_progress_note(task.task_id, ProgressNote(
                session="progress",
                timestamp=task.last_checkpoint,
                summary=f"Progress: {task.completed_items}/{task.total_items} ({task.percent:.0f}%)",
                next_steps=[f"Continue from item #{task.completed_items + 1}"],
            ))

        return task

    def checkpoint(self, task_id: str = "", reason: str = "") -> Optional[TaskProgress]:
        """Save a checkpoint (call before context window exhaustion)."""
        task = self._active_task or self._load(task_id)
        if not task:
            return None

        task.last_checkpoint = time.strftime("%Y-%m-%d %H:%M")
        self._save(task)

        self._write_progress_note(task.task_id, ProgressNote(
            session="checkpoint",
            timestamp=task.last_checkpoint,
            summary=f"CHECKPOINT: {reason} — {task.completed_items}/{task.total_items} done",
            next_steps=[f"Resume from item #{task.completed_items + 1}: {task.current_item}"],
            notes=reason,
        ))

        logger.info("TaskState: checkpoint '%s' — %.0f%% done", task_id, task.percent)
        return task

    def discover_and_resume(self, task_prefix: str = "") -> Optional[TaskProgress]:
        """Auto-discover and resume an incomplete task from filesystem.

        Like Claude 4.5's pattern: "look at progress.txt, tests.json, git log"
        """
        # Find most recent task state file
        task_files = []
        try:
            for f in os.listdir(self._data_dir):
                if f.startswith("task_") and f.endswith(".json"):
                    path = os.path.join(self._data_dir, f)
                    task_files.append((path, os.path.getmtime(path)))
        except Exception:
            pass

        if not task_files:
            return None

        task_files.sort(key=lambda x: -x[1])  # Most recent first

        for path, _ in task_files:
            task = self._load_from_path(path)
            if task and task_prefix in task.task_id:
                if task.percent < 100:
                    self._active_task = task
                    logger.info(
                        "TaskState: RESUMED '%s' — %.0f%% done (%d/%d), current: %s",
                        task.task_id, task.percent, task.completed_items,
                        task.total_items, task.current_item,
                    )
                    return task

        return None

    def is_complete(self, task_id: str = "") -> bool:
        task = self._active_task or self._load(task_id)
        return task is not None and task.percent >= 100

    def get_summary(self, task_id: str = "") -> str:
        task = self._active_task or self._load(task_id)
        if not task:
            return "No active task"

        bar_len = 20
        done = int(task.percent / 100 * bar_len)
        bar = "█" * done + "░" * (bar_len - done)

        return (
            f"📋 {task.task_name}\n"
            f"  [{bar}] {task.percent:.0f}%\n"
            f"  {task.completed_items}/{task.total_items} completed"
            f"{', ' + str(task.failed_items) + ' failed' if task.failed_items else ''}\n"
            f"  Current: {task.current_item[:80] if task.current_item else 'N/A'}\n"
            f"  Started: {task.started_at} | Last save: {task.last_checkpoint}"
        )

    def list_tasks(self) -> list[dict]:
        tasks = []
        try:
            for f in os.listdir(self._data_dir):
                if f.startswith("task_") and f.endswith(".json"):
                    task = self._load_from_path(os.path.join(self._data_dir, f))
                    if task:
                        tasks.append({
                            "id": task.task_id,
                            "name": task.task_name,
                            "percent": task.percent,
                            "completed": task.completed_items,
                            "total": task.total_items,
                            "active": task.percent < 100,
                        })
        except Exception:
            pass
        return sorted(tasks, key=lambda t: -t["percent"])

    # ═══ Persistence ═══

    def _save(self, task: TaskProgress) -> None:
        path = os.path.join(self._data_dir, f"task_{task.task_id}.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({
                    "task_id": task.task_id,
                    "task_name": task.task_name,
                    "total_items": task.total_items,
                    "completed_items": task.completed_items,
                    "failed_items": task.failed_items,
                    "current_item": task.current_item,
                    "current_index": task.current_index,
                    "percent": task.percent,
                    "items": task.items[-200:],
                    "started_at": task.started_at,
                    "last_checkpoint": task.last_checkpoint,
                    "warnings": task.warnings[-20:],
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning("TaskState save: %s", e)

    def _load(self, task_id: str) -> Optional[TaskProgress]:
        path = os.path.join(self._data_dir, f"task_{task_id}.json")
        return self._load_from_path(path)

    def _load_from_path(self, path: str) -> Optional[TaskProgress]:
        try:
            if not os.path.exists(path):
                return None
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return TaskProgress(
                task_id=data["task_id"],
                task_name=data["task_name"],
                total_items=data.get("total_items", 0),
                completed_items=data.get("completed_items", 0),
                failed_items=data.get("failed_items", 0),
                current_item=data.get("current_item", ""),
                current_index=data.get("current_index", 0),
                percent=data.get("percent", 0),
                items=data.get("items", []),
                started_at=data.get("started_at", ""),
                last_checkpoint=data.get("last_checkpoint", ""),
                warnings=data.get("warnings", []),
            )
        except Exception:
            return None

    def _write_progress_note(self, task_id: str, note: ProgressNote) -> None:
        path = os.path.join(self._data_dir, f"progress_{task_id}.md")
        entry = (
            f"## {note.session.upper()} — {note.timestamp}\n"
            f"{note.summary}\n"
        )
        if note.next_steps:
            entry += "\nNext steps:\n" + "\n".join(f"- {s}" for s in note.next_steps)
        if note.blockers:
            entry += "\nBlockers:\n" + "\n".join(f"- {s}" for s in note.blockers)
        entry += "\n---\n\n"

        try:
            mode = "a" if os.path.exists(path) else "w"
            with open(path, mode, encoding="utf-8") as f:
                f.write(entry)
        except Exception:
            pass


# ═══ Gateway Prompt Injection ═══

# Claude 4 anti-hallucination pattern
INVESTIGATE_BEFORE_ANSWERING = """
<investigate_before_answering>
永远不要推测你没有读取的内容。如果引用了特定文件或数据，你必须先读取再回答。
在提出解决方案之前，始终先检查相关文件和数据。在回答知识相关问题时，
引用你实际检索到的来源，而不是凭空生成。确保答案是务实、准确、无幻觉的。
</investigate_before_answering>
"""

# Claude 4 progressive task pattern
PROGRESSIVE_WORK_PATTERN = """
<progressive_work>
这是一个长任务。逐步推进，一次专注于少数事项。跟踪你的进度。
在有大量未提交工作时不耗尽context。系统地持续工作直到任务完成。
在context window接近限制前，将当前进度和状态保存到内存/文件。
</progressive_work>
"""

# Claude 4 parallel execution pattern
PARALLEL_EXECUTION = """
<use_parallel_tool_calls>
如果你打算调用多个工具且工具调用之间没有依赖关系，请并行进行所有独立的工具调用。
优先同时调用工具，只要操作可以并行而不是顺序完成。
例如同时读取多个文件、同时进行多个搜索查询。最大化使用并行以提高速度和效率。
</use_parallel_tool_calls>
"""

# Claude 4 anti-overengineering pattern
ANTI_OVERENGINEERING = """
<avoid_overengineering>
只进行直接请求或明确必要的更改。保持解决方案简单和专注。
不要添加功能、重构代码或进行超出要求的"改进"。不要为假设的未来需求进行设计。
正确的复杂度是当前任务所需的最小值。
</avoid_overengineering>
"""

# Claude 4 source verification pattern
SOURCE_VERIFICATION = """
<source_verification>
在收集数据时，跨多个来源验证信息。发展竞争性假设。跟踪置信水平。
定期自我批评方法和计划。将发现持久化到文件以提供透明度。
</source_verification>
"""

# Composite gateway system prompt
GATEWAY_SYSTEM_PROMPT = (
    f"{INVESTIGATE_BEFORE_ANSWERING}\n"
    f"{PROGRESSIVE_WORK_PATTERN}\n"
    f"{SOURCE_VERIFICATION}\n"
    f"{ANTI_OVERENGINEERING}"
)


class PromptInjector:
    """Inject Claude 4 best-practice prompts into LLM gateway calls.

    Usage:
        injector = PromptInjector()
        messages = injector.inject(messages, mode="gateway")
        # → messages now has system prompt with anti-hallucination + progressive + parallel
    """

    MODES = {
        "gateway": GATEWAY_SYSTEM_PROMPT,
        "research": f"{INVESTIGATE_BEFORE_ANSWERING}\n{SOURCE_VERIFICATION}",
        "coding": f"{PROGRESSIVE_WORK_PATTERN}\n{PARALLEL_EXECUTION}\n{ANTI_OVERENGINEERING}",
        "light": INVESTIGATE_BEFORE_ANSWERING,
    }

    def inject(self, messages: list[dict], mode: str = "gateway") -> list[dict]:
        """Inject best-practice prompts into message list."""
        prompt = self.MODES.get(mode, self.MODES["gateway"])

        # Check if already has a system message
        if messages and messages[0].get("role") == "system":
            messages[0]["content"] = prompt + "\n\n" + messages[0]["content"]
        else:
            messages.insert(0, {"role": "system", "content": prompt})

        return messages

    def inject_for_task(self, messages: list[dict], task_type: str) -> list[dict]:
        """Auto-select best mode based on task type."""
        task_modes = {
            "search": "research",
            "analyze": "research",
            "generate": "coding",
            "train": "coding",
            "chat": "light",
        }
        mode = task_modes.get(task_type, "gateway")
        return self.inject(messages, mode)


# ═══ Singleton ═══

_state_manager: Optional[TaskStateManager] = None
_injector: Optional[PromptInjector] = None


def get_state_manager() -> TaskStateManager:
    global _state_manager
    if _state_manager is None:
        _state_manager = TaskStateManager()
    return _state_manager

def get_prompt_injector() -> PromptInjector:
    global _injector
    if _injector is None:
        _injector = PromptInjector()
    return _injector
