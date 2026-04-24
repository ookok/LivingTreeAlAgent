# -*- coding: utf-8 -*-
"""
统一任务执行器 - Unified Task Executor
==========================================

职责：
1. 统一的任务执行入口
2. 支持多种执行策略（串行/并行/DAG）
3. 与 UnifiedPipeline 协同工作
4. Skill 生命周期管理

复用模块：
- SmartTaskExecutor (core/task_execution_engine.py)
- SkillEvolutionAgent (core/skill_evolution/agent_loop.py)
- ToolRegistry (core/tools_registry.py)

Author: Hermes Desktop Team
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


# ── 枚举定义 ────────────────────────────────────────────────────────────────


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExecutionStrategy(Enum):
    """执行策略"""
    SEQUENTIAL = "sequential"    # 串行
    PARALLEL = "parallel"      # 并行
    DAG = "dag"                 # 依赖图


# ── 数据结构 ────────────────────────────────────────────────────────────────


@dataclass
class TaskContext:
    """任务执行上下文"""
    task_id: str = ""
    user_id: str = ""
    session_id: str = ""
    variables: Dict[str, Any] = field(default_factory=dict)
    results: Dict[str, Any] = field(default_factory=dict)
    errors: List[Dict[str, Any]] = field(default_factory=list)

    def set_var(self, key: str, value: Any):
        self.variables[key] = value

    def get_var(self, key: str, default: Any = None) -> Any:
        return self.variables.get(key, default)


@dataclass
class ExecutionResult:
    """执行结果"""
    task_id: str
    status: TaskStatus
    output: Any = None
    error: Optional[str] = None
    duration: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


# ── 统一任务执行器 ──────────────────────────────────────────────────────────


class UnifiedTaskExecutor:
    """
    统一任务执行器

    特点：
    1. 属性懒加载 - 避免循环依赖
    2. 三种执行策略 - 串行/并行/DAG
    3. Skill 适配器 - 统一技能调用接口
    4. 流式支持 - execute_stream() 支持流式输出
    """

    def __init__(
        self,
        ollama_url: Optional[str] = None,
        max_workers: int = 4,
        default_strategy: ExecutionStrategy = ExecutionStrategy.SEQUENTIAL,
        default_model: Optional[str] = None,
        **kwargs
    ):
        # 从配置模块获取默认值
        from core.config_provider import get_ollama_url, get_l1_model

        self._ollama_url = ollama_url or get_ollama_url()
        self._max_workers = max_workers
        self._default_strategy = default_strategy
        self._default_model = default_model or get_l1_model()
        self._ollama_client = None
        self._smart_executor = None
        self._skill_registry = {}
        self._executor = None

        logger.info(f"UnifiedTaskExecutor 初始化 (url={self._ollama_url}, strategy={default_strategy})")

    # ── 属性懒加载 ────────────────────────────────────────────────────────────

    @property
    def ollama_client(self):
        """Ollama 客户端（使用 requests 直接调用）"""
        if self._ollama_client is None:
            self._ollama_client = self._create_simple_client()
        return self._ollama_client

    def _create_simple_client(self):
        """创建简化的 Ollama 客户端"""
        import requests

        class SimpleOllamaClient:
            def __init__(self, base_url):
                self.base_url = base_url

            def chat_sync(self, messages, model=None, **kwargs):
                from core.config_provider import get_l1_model
                model = model or get_l1_model()
                content = messages[0]["content"] if isinstance(messages[0], dict) else messages[0].content
                resp = requests.post(
                    f"{self.base_url}/chat/completions",
                    json={"model": model, "messages": [{"role": "user", "content": content}]},
                    timeout=kwargs.get("timeout", 60)
                )
                return resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")

        return SimpleOllamaClient(self._ollama_url)

        return SimpleOllamaClient(self._ollama_url)

    @property
    def smart_executor(self):
        """智能任务执行器（延迟加载）"""
        if self._smart_executor is None:
            try:
                from core.task_execution_engine import SmartTaskExecutor
                self._smart_executor = SmartTaskExecutor(
                    llm_client=self.ollama_client,
                    max_depth=3,
                    max_subtasks_per_node=8
                )
            except ImportError:
                logger.warning("SmartTaskExecutor 不可用，使用简化执行器")
                self._smart_executor = None
        return self._smart_executor

    @property
    def tool_registry(self):
        """工具注册表（延迟加载）"""
        try:
            from core.tools_registry import ToolRegistry
            return ToolRegistry
        except ImportError:
            return None

    # ── 核心执行接口 ──────────────────────────────────────────────────────────

    def execute(
        self,
        task: str,
        context: Optional[TaskContext] = None,
        strategy: Optional[ExecutionStrategy] = None,
        **kwargs
    ) -> ExecutionResult:
        """
        执行任务

        Args:
            task: 任务描述
            context: 执行上下文
            strategy: 执行策略（默认使用初始化时的策略）

        Returns:
            ExecutionResult: 执行结果
        """
        task_id = str(uuid.uuid4())[:8]
        context = context or TaskContext(task_id=task_id)
        strategy = strategy or self._default_strategy

        start_time = time.time()
        logger.info(f"[{task_id}] 执行任务 (strategy={strategy.value}): {task[:50]}...")

        try:
            # 1. 判断是否需要分解
            if self.smart_executor:
                decision = self.smart_executor.should_decompose(task, context)
                if decision.should_decompose:
                    # 需要分解，执行多步骤
                    result = self._execute_decomposed(task, context, decision, strategy)
                else:
                    # 直接执行
                    result = self._execute_single(task, context, **kwargs)
            else:
                # 简化执行
                result = self._execute_single(task, context, **kwargs)

            result.duration = time.time() - start_time
            logger.info(f"[{task_id}] 任务完成 (duration={result.duration:.2f}s)")

            return result

        except Exception as e:
            logger.error(f"[{task_id}] 执行失败: {e}")
            return ExecutionResult(
                task_id=task_id,
                status=TaskStatus.FAILED,
                error=str(e),
                duration=time.time() - start_time
            )

    def execute_stream(
        self,
        task: str,
        context: Optional[TaskContext] = None,
        **kwargs
    ) -> Iterator[str]:
        """
        流式执行任务

        Args:
            task: 任务描述
            context: 执行上下文

        Yields:
            str: 流式输出片段
        """
        task_id = str(uuid.uuid4())[:8]
        logger.info(f"[{task_id}] 开始流式执行: {task[:50]}...")

        # 简化的流式实现
        result = self.execute(task, context, **kwargs)

        if result.status == TaskStatus.COMPLETED:
            output = str(result.output or "")
            # 模拟流式输出
            for i in range(0, len(output), 50):
                yield output[i:i+50]
        else:
            yield f"[Error] {result.error}"

    # ── 内部执行方法 ──────────────────────────────────────────────────────────

    def _execute_single(
        self,
        task: str,
        context: TaskContext,
        **kwargs
    ) -> ExecutionResult:
        """执行单个任务"""
        # 调用 LLM 生成结果
        prompt = self._build_prompt(task, context)
        model = kwargs.get("model", self._default_model)

        output = self.ollama_client.chat_sync([{"role": "user", "content": prompt}], model=model, **kwargs)

        return ExecutionResult(
            task_id=context.task_id,
            status=TaskStatus.COMPLETED,
            output=output
        )

    def _execute_decomposed(
        self,
        task: str,
        context: TaskContext,
        decision,
        strategy: ExecutionStrategy
    ) -> ExecutionResult:
        """执行分解后的任务"""
        if strategy == ExecutionStrategy.PARALLEL:
            return self._execute_parallel(task, context, decision)
        else:
            return self._execute_sequential(task, context, decision)

    def _execute_sequential(
        self,
        task: str,
        context: TaskContext,
        decision
    ) -> ExecutionResult:
        """串行执行子任务"""
        outputs = []

        # 生成子任务列表（简化版）
        subtasks = self._generate_subtasks(task, decision.estimated_subtasks)

        for i, subtask in enumerate(subtasks):
            logger.info(f"执行子任务 {i+1}/{len(subtasks)}: {subtask[:30]}...")
            result = self._execute_single(subtask, context)
            outputs.append(result.output)

            if result.status == TaskStatus.FAILED:
                return result

        # 合并结果
        combined = self._combine_outputs(outputs, task)
        return ExecutionResult(
            task_id=context.task_id,
            status=TaskStatus.COMPLETED,
            output=combined,
            metadata={"subtasks_count": len(subtasks)}
        )

    def _execute_parallel(
        self,
        task: str,
        context: TaskContext,
        decision
    ) -> ExecutionResult:
        """并行执行子任务"""
        subtasks = self._generate_subtasks(task, decision.estimated_subtasks)

        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=self._max_workers)

        futures = {}
        for subtask in subtasks:
            future = self._executor.submit(self._execute_single, subtask, context)
            futures[future] = subtask

        outputs = []
        for future in as_completed(futures):
            result = future.result()
            outputs.append(result.output)

        combined = self._combine_outputs(outputs, task)
        return ExecutionResult(
            task_id=context.task_id,
            status=TaskStatus.COMPLETED,
            output=combined,
            metadata={"subtasks_count": len(subtasks), "parallel": True}
        )

    # ── 辅助方法 ──────────────────────────────────────────────────────────────

    def _build_prompt(self, task: str, context: TaskContext) -> str:
        """构建提示词"""
        prompt_parts = []

        # 上下文变量
        if context.variables:
            prompt_parts.append(f"上下文信息: {context.variables}")

        # 任务
        prompt_parts.append(f"任务: {task}")

        return "\n".join(prompt_parts)

    def _generate_subtasks(self, task: str, count: int) -> List[str]:
        """生成子任务（使用 LLM）"""
        prompt = f"""将以下任务分解为 {count} 个子任务，只返回子任务列表，每行一个：

任务：{task}

格式：
1. 子任务1
2. 子任务2
...
"""

        try:
            response = self.ollama_client.chat_sync(
                [{"role": "user", "content": prompt}],
                model=self._default_model,
                max_tokens=500
            )
            # 解析子任务
            subtasks = []
            for line in response.strip().split("\n"):
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith("-")):
                    # 去除序号
                    subtask = line.lstrip("0123456789.-) ")
                    if subtask:
                        subtasks.append(subtask)
            return subtasks[:count] if subtasks else [task]
        except Exception as e:
            logger.warning(f"子任务生成失败: {e}")
            return [task]

    def _combine_outputs(self, outputs: List[Any], original_task: str) -> str:
        """合并子任务输出"""
        if not outputs:
            return ""

        prompt = f"""合并以下输出为一个连贯的答案：

原始任务：{original_task}

子任务输出：
{chr(10).join(str(o) for o in outputs)}

请生成最终答案：
"""

        try:
            return self.ollama_client.chat_sync(
                [{"role": "user", "content": prompt}],
                model=self._default_model,
                max_tokens=2000
            )
        except Exception as e:
            logger.warning(f"结果合并失败: {e}")
            return "\n\n".join(str(o) for o in outputs)


# ── 技能适配器 ──────────────────────────────────────────────────────────────


class SkillExecutionAdapter:
    """
    技能执行适配器

    将各种类型的 Skill 统一适配到 UnifiedTaskExecutor
    """

    def __init__(self, executor: UnifiedTaskExecutor):
        self.executor = executor
        self._skill_handlers: Dict[str, Callable] = {}

    def register_handler(self, skill_name: str, handler: Callable):
        """注册技能处理器"""
        self._skill_handlers[skill_name] = handler

    def execute_skill(
        self,
        skill_name: str,
        params: Dict[str, Any],
        context: Optional[TaskContext] = None
    ) -> ExecutionResult:
        """执行技能"""
        if skill_name in self._skill_handlers:
            handler = self._skill_handlers[skill_name]
            try:
                result = handler(params, context)
                return ExecutionResult(
                    task_id=context.task_id if context else "unknown",
                    status=TaskStatus.COMPLETED,
                    output=result
                )
            except Exception as e:
                return ExecutionResult(
                    task_id=context.task_id if context else "unknown",
                    status=TaskStatus.FAILED,
                    error=str(e)
                )
        else:
            # 回退到通用执行
            task = f"{skill_name}: {params}"
            return self.executor.execute(task, context)


# ── 入口点 ──────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    # 测试
    logging.basicConfig(level=logging.INFO)

    # 从配置获取 Ollama URL
    from core.config_provider import get_ollama_url
from core.logger import get_logger
logger = get_logger('unified_task_executor')


    executor = UnifiedTaskExecutor(
        ollama_url=get_ollama_url(),  # 使用配置
        default_strategy=ExecutionStrategy.SEQUENTIAL
    )

    # 测试单个任务
    result = executor.execute("你好，请用一句话介绍自己")
    logger.info(f"Status: {result.status.value}")
    logger.info(f"Output: {result.output}")
    logger.info(f"Duration: {result.duration:.2f}s")
