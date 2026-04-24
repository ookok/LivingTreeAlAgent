"""
TaskRouter - 多层递归任务分解器
让智能体能够"层层深入思考"，处理嵌套型复杂任务

核心能力：
- 任务栈管理（collections.deque）
- TaskNode 封装（prompt, context, tools, parent_id, depth）
- 自动递归判断（摘要 > 500 tokens + 复杂度 > 0.7）
- 链式推理：提取 → 分析 → 绘图 三级联动
"""

import json
import uuid
import threading
from dataclasses import dataclass, field, asdict
from typing import Callable, Iterator, Optional
from collections import deque
from enum import Enum
import time


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING_APPROVAL = "waiting_approval"


class TaskPriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class TaskNode:
    """
    任务节点封装

    Attributes:
        task_id: 唯一标识
        prompt: 当前子任务指令
        context_snapshot: 独立上下文快照（JSON）
        tools_allowed: 动态权限列表
        parent_id: 父任务ID，用于回溯
        depth: 当前层级（≤3）
        status: 任务状态
        priority: 任务优先级
        complexity_score: 复杂度评分（0-1）
        summary: 子任务执行后的摘要
        result: 执行结果
        children: 子任务列表
        created_at: 创建时间
        started_at: 开始时间
        completed_at: 完成时间
    """
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    prompt: str = ""
    context_snapshot: dict = field(default_factory=dict)
    tools_allowed: list[str] = field(default_factory=list)
    parent_id: Optional[str] = None
    depth: int = 0
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    complexity_score: float = 0.0
    summary: str = ""
    result: dict = field(default_factory=dict)
    children: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    def to_dict(self) -> dict:
        """转换为字典（JSON 序列化）"""
        d = asdict(self)
        d["status"] = self.status.value
        d["priority"] = self.priority.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "TaskNode":
        """从字典恢复"""
        d["status"] = TaskStatus(d.get("status", "pending"))
        d["priority"] = TaskPriority(d.get("priority", 1))
        return cls(**d)

    def get_age_seconds(self) -> float:
        """获取任务存在时间（秒）"""
        return time.time() - self.created_at

    def mark_started(self):
        self.status = TaskStatus.RUNNING
        self.started_at = time.time()

    def mark_completed(self, summary: str = "", result: dict = None):
        self.status = TaskStatus.COMPLETED
        self.completed_at = time.time()
        self.summary = summary
        if result:
            self.result = result

    def mark_failed(self, error: str):
        self.status = TaskStatus.FAILED
        self.completed_at = time.time()
        self.result = {"error": error}


class TaskRouter:
    """
    多层递归任务分解器

    使用 deque 构建任务队列，支持深度递归处理。

    递归触发条件：
    1. 子任务摘要 > 500 tokens
    2. 任务复杂度评分 > 0.7
    3. 当前深度 < max_depth (默认3)

    使用示例：
        router = TaskRouter(max_depth=3, complexity_threshold=0.7)

        # 添加主任务
        root_id = router.add_task(
            prompt="分析《红楼梦》人物关系",
            context={"book": "红楼梦"},
            tools=["read_file", "search_files"],
        )

        # 执行任务（自动递归）
        for progress in router.execute():
            logger.info(progress)
    """

    MAX_DEPTH = 3  # 最大递归深度
    SUMMARY_TOKEN_THRESHOLD = 500  # 摘要 token 数阈值
    COMPLEXITY_THRESHOLD = 0.7  # 复杂度阈值

    def __init__(
        self,
        max_depth: int = 3,
        complexity_threshold: float = 0.7,
        token_threshold: int = 500,
        llm_callback: Optional[Callable] = None,
    ):
        self.max_depth = max_depth
        self.complexity_threshold = complexity_threshold
        self.token_threshold = token_threshold
        self.llm_callback = llm_callback  # LLM 调用接口

        # 任务存储
        self._tasks: dict[str, TaskNode] = {}
        self._task_queue: deque[str] = deque()  # 任务队列
        self._lock = threading.RLock()

        # 统计
        self._stats = {
            "total": 0,
            "completed": 0,
            "failed": 0,
            "recursion_depth": 0,
        }

    def add_task(
        self,
        prompt: str,
        context: Optional[dict] = None,
        tools: Optional[list[str]] = None,
        parent_id: Optional[str] = None,
        depth: int = 0,
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> str:
        """
        添加新任务到队列

        Args:
            prompt: 任务指令
            context: 上下文快照
            tools: 允许使用的工具列表
            parent_id: 父任务ID
            depth: 当前深度
            priority: 优先级

        Returns:
            任务ID
        """
        with self._lock:
            # 计算复杂度
            complexity = self._estimate_complexity(prompt)

            task = TaskNode(
                prompt=prompt,
                context_snapshot=context or {},
                tools_allowed=tools or [],
                parent_id=parent_id,
                depth=depth,
                complexity_score=complexity,
                priority=priority,
            )

            self._tasks[task.task_id] = task
            self._task_queue.append(task.task_id)
            self._stats["total"] += 1

            if depth > self._stats["recursion_depth"]:
                self._stats["recursion_depth"] = depth

            return task.task_id

    def _estimate_complexity(self, prompt: str) -> float:
        """
        估算任务复杂度（0-1）

        基于关键词和结构分析：
        - 多步骤指示词（首先、然后、最后）
        - 数量词（多个、各自、分别）
        - 分析类词汇（关系、对比、原因、影响）
        - 递归暗示词（每、循环、迭代）
        """
        prompt_lower = prompt.lower()
        score = 0.0

        # 多步骤指示
        step_words = ["首先", "然后", "最后", "第一", "第二", "第三", "接着", "接下来"]
        for w in step_words:
            if w in prompt_lower:
                score += 0.15

        # 数量指示
        quantity_words = ["多个", "分别", "各自", "每个", "逐一", "批量", "全部"]
        for w in quantity_words:
            if w in prompt_lower:
                score += 0.1

        # 分析类词汇
        analysis_words = [
            "分析", "关系", "对比", "对比分析", "原因", "影响", "因素",
            "图谱", "网络", "层级", "结构", "模式", "规律", "趋势"
        ]
        for w in analysis_words:
            if w in prompt_lower:
                score += 0.1

        # 递归暗示
        recursion_words = ["每", "循环", "迭代", "递归", "逐层", "层层"]
        for w in recursion_words:
            if w in prompt_lower:
                score += 0.2

        # 长度加成（过长通常更复杂）
        if len(prompt) > 200:
            score += 0.1

        return min(score, 1.0)

    def _should_recurse(self, summary: str, complexity: float, depth: int) -> bool:
        """
        判断是否需要递归分解

        条件：
        1. 摘要 token 数 > 阈值
        2. 复杂度 > 阈值
        3. 深度 < 最大深度
        """
        # 简单估算 token 数（中文约 0.5 token/字）
        estimated_tokens = len(summary) * 0.5

        return (
            estimated_tokens > self.token_threshold
            and complexity > self.complexity_threshold
            and depth < self.max_depth
        )

    def _generate_subtasks(self, task: TaskNode, summary: str) -> list[dict]:
        """
        生成子任务（通过 LLM 分析摘要）

        返回子任务列表，每项包含：
        - prompt: 子任务指令
        - context: 上下文
        - tools: 工具权限
        """
        if not self.llm_callback:
            # 无 LLM 时使用启发式分解
            return self._heuristic_subtasks(task, summary)

        # 使用 LLM 进行智能分解
        prompt = f"""分析以下任务摘要，生成 2-4 个子任务：

摘要：{summary}

原始任务：{task.prompt}

要求：
1. 每个子任务应聚焦一个具体目标
2. 子任务之间有逻辑顺序
3. 返回 JSON 数组格式

示例输出：
[
  {{"prompt": "子任务1", "tools": ["read_file"]}},
  {{"prompt": "子任务2", "tools": ["search_files"]}}
]
"""
        try:
            response = self.llm_callback(prompt)
            # 尝试解析 JSON
            import re
from core.logger import get_logger
logger = get_logger('task_router')

            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception:
            pass

        # 回退到启发式
        return self._heuristic_subtasks(task, summary)

    def _heuristic_subtasks(self, task: TaskNode, summary: str) -> list[dict]:
        """
        启发式子任务分解

        基于摘要内容自动推断子任务类型
        """
        subtasks = []
        summary_lower = summary.lower()

        # 提取阶段
        if any(k in summary_lower for k in ["提取", "获取", "收集", "扫描"]):
            subtasks.append({
                "prompt": f"提取相关信息：{task.prompt}",
                "tools": task.tools_allowed.copy(),
            })

        # 分析阶段
        if any(k in summary_lower for k in ["分析", "计算", "统计", "归纳"]):
            subtasks.append({
                "prompt": f"执行分析任务：{task.prompt}",
                "tools": task.tools_allowed.copy(),
            })

        # 生成阶段
        if any(k in summary_lower for k in ["生成", "创建", "绘制", "输出", "报告"]):
            subtasks.append({
                "prompt": f"生成最终结果：{task.prompt}",
                "tools": task.tools_allowed.copy(),
            })

        # 如果没有匹配，至少返回原任务
        if not subtasks:
            subtasks.append({
                "prompt": task.prompt,
                "tools": task.tools_allowed.copy(),
            })

        return subtasks

    def execute(self) -> Iterator[dict]:
        """
        执行任务队列（生成器）

        Yields:
            进度字典，包含任务状态和结果
        """
        while self._task_queue:
            with self._lock:
                task_id = self._task_queue.popleft()

            task = self._tasks.get(task_id)
            if not task:
                continue

            # 标记开始
            task.mark_started()
            yield {
                "event": "task_started",
                "task_id": task_id,
                "depth": task.depth,
                "prompt": task.prompt,
            }

            try:
                # 执行任务（实际由外部 Agent 执行）
                result = self._execute_task(task)

                # 生成摘要
                summary = self._summarize_result(result, task)

                # 标记完成
                task.mark_completed(summary, result)

                yield {
                    "event": "task_completed",
                    "task_id": task_id,
                    "depth": task.depth,
                    "summary": summary,
                    "complexity": task.complexity_score,
                }

                self._stats["completed"] += 1

                # 检查是否需要递归
                if self._should_recurse(summary, task.complexity_score, task.depth):
                    subtasks = self._generate_subtasks(task, summary)
                    for st in subtasks:
                        child_id = self.add_task(
                            prompt=st["prompt"],
                            context=task.context_snapshot.copy(),
                            tools=st.get("tools", task.tools_allowed),
                            parent_id=task_id,
                            depth=task.depth + 1,
                        )
                        self._tasks[task_id].children.append(child_id)

                    yield {
                        "event": "recursion_triggered",
                        "task_id": task_id,
                        "subtasks": len(subtasks),
                        "max_depth": self.max_depth,
                    }

                # 收集父任务结果
                if task.parent_id:
                    parent = self._tasks.get(task.parent_id)
                    if parent:
                        parent.result.setdefault("subtask_results", {})[task_id] = {
                            "summary": summary,
                            "depth": task.depth,
                        }

            except Exception as e:
                task.mark_failed(str(e))
                self._stats["failed"] += 1
                yield {
                    "event": "task_failed",
                    "task_id": task_id,
                    "error": str(e),
                }

    def _execute_task(self, task: TaskNode) -> dict:
        """
        执行单个任务（模板方法，实际由 AgentWorker 调用）
        """
        # 这里返回模拟结果，实际由外部 Agent 执行
        return {
            "output": f"[Task {task.task_id}] {task.prompt}",
            "depth": task.depth,
            "tools_used": task.tools_allowed,
        }

    def _summarize_result(self, result: dict, task: TaskNode) -> str:
        """
        摘要执行结果
        """
        output = result.get("output", "")

        # 如果有 LLM，使用它生成摘要
        if self.llm_callback:
            try:
                prompt = f"用一句话总结以下内容，控制在100字以内：\n{output[:1000]}"
                return self.llm_callback(prompt)[:200]
            except Exception:
                pass

        # 回退到截取
        return output[:200] if output else ""

    def get_task_tree(self, root_id: Optional[str] = None) -> dict:
        """
        获取任务树结构（用于 UI 展示）
        """
        def build_tree(tid: str) -> dict:
            task = self._tasks.get(tid)
            if not task:
                return {}

            node = {
                "id": tid,
                "prompt": task.prompt[:50] + "..." if len(task.prompt) > 50 else task.prompt,
                "status": task.status.value,
                "depth": task.depth,
                "complexity": task.complexity_score,
                "children": [build_tree(cid) for cid in task.children],
            }
            return node

        if root_id:
            return build_tree(root_id)

        # 返回所有根任务
        roots = [tid for tid, t in self._tasks.items() if t.parent_id is None]
        return {
            "roots": [build_tree(rid) for rid in roots],
            "stats": self._stats,
        }

    def get_pending_count(self) -> int:
        """获取待执行任务数"""
        with self._lock:
            return len(self._task_queue)

    def cancel_task(self, task_id: str) -> bool:
        """取消任务（仅限 pending 状态）"""
        with self._lock:
            task = self._tasks.get(task_id)
            if task and task.status == TaskStatus.PENDING:
                task.mark_failed("Cancelled by user")
                return True
        return False

    def get_stats(self) -> dict:
        """获取统计信息"""
        return self._stats.copy()


# ── 便捷函数 ────────────────────────────────────────────────────────

def create_task_router(
    max_depth: int = 3,
    complexity_threshold: float = 0.7,
    llm_callback: Optional[Callable] = None,
) -> TaskRouter:
    """创建 TaskRouter 实例"""
    return TaskRouter(
        max_depth=max_depth,
        complexity_threshold=complexity_threshold,
        llm_callback=llm_callback,
    )
