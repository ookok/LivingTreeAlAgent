# LivingTreeAI Agent 重构技术方案

> 文档版本: v1.0
> 生成时间: 2026-04-24
> 目标: 基于已有模块，提出具体可执行的重构技术方案

---

## 1. 技术方案概览

### 1.1 核心目标

将现有的 **18+ 核心模块** 整合为统一的 Agent 工作流，消除重复代码，实现：

```
用户请求 → 意图分类 → 智能路由 → 多源检索 → 结果融合 → LLM生成 → 技能固化
```

### 1.2 五大重构方向

| # | 重构方向 | 目标模块 | 涉及核心模块 |
|---|---------|---------|-------------|
| **R1** | 统一入口整合 | `HermesAgent` | FusionRAG + UnifiedCache |
| **R2** | 任务执行与技能解耦 | `SmartTaskExecutor` | SkillEvolutionAgent |
| **R3** | 上下文统一管理 | `UnifiedContext` | MemoryPalace + ConversationalClarifier |
| **R4** | 智能写作工作流 | `SmartWritingPipeline` | AIEnhancedGeneration + WikiGenerator |
| **R5** | 面板与引擎分离 | UI Panels | 业务逻辑解耦 |

---

## 2. R1: 统一入口整合

### 2.1 问题分析

**现状**：
- 各模块分散调用：`agent_chat.py` 直接导入多个模块
- 缺乏统一的请求处理流水线
- 缓存未充分利用

**目标**：在 `HermesAgent` 中建立标准化的处理流水线

### 2.2 实施代码

```python
# core/unified_pipeline.py
"""
统一处理流水线 - Unified Processing Pipeline
============================================

职责：
1. 接收用户 Query
2. 执行 L0 意图分类
3. 执行 L1-L2 检索路由
4. 执行 L3-L4 深度生成
5. 结果缓存与技能固化

复用模块：
- QueryIntentClassifier (意图分类)
- IntelligentRouter (智能路由)
- UnifiedCache (统一缓存)
- KnowledgeBaseLayer (知识库)
- DeepSearchWikiSystem (深度搜索)
- SkillEvolutionAgent (技能固化)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Iterator

logger = logging.getLogger(__name__)


class IntentType(Enum):
    """意图类型枚举"""
    FACTUAL = "factual"           # 事实查询
    CONVERSATIONAL = "conversational"  # 对话类
    PROCEDURAL = "procedural"     # 流程/代码类
    CREATIVE = "creative"         # 创意类
    TASK = "task"                 # 任务执行
    UNKNOWN = "unknown"           # 未知


@dataclass
class PipelineContext:
    """流水线上下文"""
    # 输入
    user_id: str
    query: str
    session_id: str = ""
    
    # 中间结果
    intent: IntentType = IntentType.UNKNOWN
    route_decision: Dict[str, Any] = field(default_factory=dict)
    retrieved_context: List[Any] = field(default_factory=list)
    
    # 输出
    response: str = ""
    sources: List[Any] = field(default_factory=list)
    confidence: float = 0.0
    needs_clarification: bool = False
    clarification_prompt: str = ""
    
    # 执行追踪
    execution_trace: List[Dict[str, Any]] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    
    def add_trace(self, stage: str, detail: str, duration: float = 0):
        """添加执行追踪"""
        self.execution_trace.append({
            "stage": stage,
            "detail": detail,
            "duration": duration,
            "timestamp": time.time() - self.start_time
        })


class UnifiedPipeline:
    """
    统一处理流水线
    
    使用示例：
    ```python
    pipeline = UnifiedPipeline()
    
    # 同步调用
    result = pipeline.process(
        user_id="user_001",
        query="帮我分析一下 Python 的异步编程"
    )
    
    # 流式调用
    for chunk in pipeline.process_stream(query):
        print(chunk, end="", flush=True)
    ```
    """
    
    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        embed_model: str = "nomic-embed-text",
        cache_dir: str = ".cache/unified"
    ):
        self._init_components()
        
        # 配置
        self.ollama_url = ollama_url
        self.embed_model = embed_model
        self.cache_dir = cache_dir
        
        logger.info("UnifiedPipeline 初始化完成")
    
    def _init_components(self):
        """延迟初始化所有组件"""
        # L0: 意图分类
        self._intent_classifier = None
        # L1-L2: 路由与检索
        self._router = None
        self._knowledge_base = None
        self._unified_cache = None
        # L3-L4: 深度生成
        self._llm_executor = None
        self._wiki_generator = None
        # 技能系统
        self._skill_agent = None
        # 上下文管理
        self._clarifier = None
        self._memory_palace = None
    
    # ── 属性懒加载 ──────────────────────────────────────────────────────────
    
    @property
    def intent_classifier(self):
        if self._intent_classifier is None:
            from core.fusion_rag.intent_classifier import QueryIntentClassifier
            self._intent_classifier = QueryIntentClassifier()
        return self._intent_classifier
    
    @property
    def router(self):
        if self._router is None:
            from core.fusion_rag.intelligent_router import IntelligentRouter
            self._router = IntelligentRouter()
        return self._router
    
    @property
    def knowledge_base(self):
        if self._knowledge_base is None:
            from core.fusion_rag.knowledge_base import KnowledgeBaseLayer
            self._knowledge_base = KnowledgeBaseLayer()
        return self._knowledge_base
    
    @property
    def unified_cache(self):
        if self._unified_cache is None:
            from unified_cache import UnifiedCache
            self._unified_cache = UnifiedCache()
        return self._unified_cache
    
    @property
    def wiki_generator(self):
        if self._wiki_generator is None:
            from core.deep_search_wiki.wiki_generator import WikiGenerator
            self._wiki_generator = WikiGenerator()
        return self._wiki_generator
    
    @property
    def skill_agent(self):
        if self._skill_agent is None:
            from core.skill_evolution.agent_loop import SkillEvolutionAgent
            self._skill_agent = SkillEvolutionAgent()
        return self._skill_agent
    
    @property
    def clarifier(self):
        if self._clarifier is None:
            from core.conversational_clarifier import ConversationalClarifier
            self._clarifier = ConversationalClarifier()
        return self._clarifier
    
    @property
    def memory_palace(self):
        if self._memory_palace is None:
            from core.memory_palace.models import MemoryPalace
            self._memory_palace = MemoryPalace()
        return self._memory_palace
    
    # ── 核心处理流程 ────────────────────────────────────────────────────────
    
    def process(
        self,
        user_id: str,
        query: str,
        session_id: str = "",
        use_cache: bool = True,
        enable_skill: bool = True,
        **kwargs
    ) -> PipelineContext:
        """
        处理用户请求（同步版本）
        
        Args:
            user_id: 用户 ID
            query: 用户查询
            session_id: 会话 ID
            use_cache: 是否使用缓存
            enable_skill: 是否启用技能系统
            
        Returns:
            PipelineContext: 处理上下文（含结果）
        """
        ctx = PipelineContext(
            user_id=user_id,
            query=query,
            session_id=session_id
        )
        
        try:
            # Step 1: 需求澄清检查
            self._step_clarification(ctx)
            if ctx.needs_clarification:
                return ctx
            
            # Step 2: L0 意图分类
            self._step_intent_classify(ctx)
            
            # Step 3: 缓存检查
            if use_cache:
                cached = self._step_cache_lookup(ctx)
                if cached:
                    ctx.response = cached
                    ctx.add_trace("cache", "命中缓存")
                    return ctx
            
            # Step 4: L1-L2 路由与检索
            self._step_route_and_retrieve(ctx)
            
            # Step 5: L3-L4 深度生成
            self._step_deep_generate(ctx)
            
            # Step 6: 结果缓存
            if use_cache:
                self._step_cache_write(ctx)
            
            # Step 7: 技能固化（异步）
            if enable_skill:
                self._step_skill_consolidate(ctx)
            
        except Exception as e:
            logger.error(f"Pipeline 处理失败: {e}")
            ctx.response = f"处理出错: {str(e)}"
            ctx.add_trace("error", str(e))
        
        return ctx
    
    def process_stream(
        self,
        user_id: str,
        query: str,
        session_id: str = "",
        **kwargs
    ) -> Iterator[str]:
        """
        处理用户请求（流式版本）
        
        Yields:
            str: 生成的文本块
        """
        ctx = PipelineContext(
            user_id=user_id,
            query=query,
            session_id=session_id
        )
        
        # 前置处理
        self._step_clarification(ctx)
        if ctx.needs_clarification:
            yield ctx.clarification_prompt
            return
        
        self._step_intent_classify(ctx)
        self._step_route_and_retrieve(ctx)
        
        # 流式生成
        for chunk in self._step_deep_generate_stream(ctx):
            yield chunk
    
    # ── 流水线步骤实现 ─────────────────────────────────────────────────────
    
    def _step_clarification(self, ctx: PipelineContext):
        """Step 1: 需求澄清检查"""
        start = time.time()
        
        # 使用 ConversationalClarifier 检测模糊需求
        is_ambiguous = self.clarifier.should_prompt(ctx.query)
        
        if is_ambiguous:
            ctx.needs_clarification = True
            ctx.clarification_prompt = self.clarifier.generate_prompt(ctx.query)
            logger.info(f"检测到模糊需求: {ctx.query[:50]}...")
        
        ctx.add_trace("clarification", f"needs_clarification={is_ambiguous}", time.time() - start)
    
    def _step_intent_classify(self, ctx: PipelineContext):
        """Step 2: L0 意图分类"""
        start = time.time()
        
        # 使用 QueryIntentClassifier
        raw_intent = self.intent_classifier.classify(ctx.query)
        
        # 映射到 IntentType
        ctx.intent = self._map_intent(raw_intent)
        
        ctx.add_trace("intent_classify", f"intent={ctx.intent.value}", time.time() - start)
        logger.debug(f"意图分类结果: {ctx.intent.value}")
    
    def _map_intent(self, raw_intent: str) -> IntentType:
        """映射原始意图到 IntentType"""
        mapping = {
            "factual": IntentType.FACTUAL,
            "fact": IntentType.FACTUAL,
            "query": IntentType.FACTUAL,
            "conversational": IntentType.CONVERSATIONAL,
            "chat": IntentType.CONVERSATIONAL,
            "procedural": IntentType.PROCEDURAL,
            "code": IntentType.PROCEDURAL,
            "task": IntentType.TASK,
            "creative": IntentType.CREATIVE,
            "generate": IntentType.CREATIVE,
        }
        return mapping.get(raw_intent.lower(), IntentType.UNKNOWN)
    
    def _step_cache_lookup(self, ctx: PipelineContext) -> Optional[str]:
        """Step 3: 缓存查询"""
        start = time.time()
        
        # 使用 UnifiedCache
        cached = self.unified_cache.get(
            query=ctx.query,
            user_id=ctx.user_id
        )
        
        ctx.add_trace("cache_lookup", f"hit={cached is not None}", time.time() - start)
        return cached
    
    def _step_route_and_retrieve(self, ctx: PipelineContext):
        """Step 4: L1-L2 路由与检索"""
        start = time.time()
        
        # 使用 IntelligentRouter
        ctx.route_decision = self.router.route(
            query=ctx.query,
            intent=ctx.intent.value
        )
        
        # 根据路由决策执行检索
        if ctx.route_decision.get("use_knowledge_base"):
            ctx.retrieved_context = self.knowledge_base.search(
                query=ctx.query,
                top_k=ctx.route_decision.get("top_k", 5)
            )
        
        ctx.add_trace(
            "route_retrieve",
            f"sources={len(ctx.retrieved_context)}",
            time.time() - start
        )
    
    def _step_deep_generate(self, ctx: PipelineContext):
        """Step 5: L3-L4 深度生成（同步）"""
        start = time.time()
        
        if ctx.intent == IntentType.FACTUAL and len(ctx.retrieved_context) > 0:
            # 有检索结果 → 基于上下文生成
            ctx.response = self._generate_with_context(ctx)
        elif ctx.intent in [IntentType.CREATIVE, IntentType.TASK]:
            # 需要深度生成 → 使用 WikiGenerator
            wiki_page = self.wiki_generator.generate(
                topic=ctx.query,
                search_results=ctx.retrieved_context
            )
            ctx.response = self._format_wiki_response(wiki_page)
            ctx.sources = wiki_page.sources
            ctx.confidence = wiki_page.confidence
        else:
            # 默认 → 直接 LLM 生成
            ctx.response = self._generate_direct(ctx)
        
        ctx.add_trace("deep_generate", f"length={len(ctx.response)}", time.time() - start)
    
    def _step_deep_generate_stream(self, ctx: PipelineContext) -> Iterator[str]:
        """Step 5: L3-L4 深度生成（流式）"""
        # TODO: 实现流式生成
        # 复用 OllamaClient 的流式接口
        raise NotImplementedError("流式生成待实现")
    
    def _step_cache_write(self, ctx: PipelineContext):
        """Step 6: 结果缓存"""
        start = time.time()
        
        self.unified_cache.set(
            query=ctx.query,
            response=ctx.response,
            user_id=ctx.user_id
        )
        
        ctx.add_trace("cache_write", "写入缓存", time.time() - start)
    
    def _step_skill_consolidate(self, ctx: PipelineContext):
        """Step 7: 技能固化（异步）"""
        # 异步执行，不阻塞主流程
        # 使用 SkillEvolutionAgent 的 execute_task
        if ctx.intent == IntentType.TASK:
            self.skill_agent.execute_task(
                task_description=ctx.query,
                context=ctx.retrieved_context
            )
    
    # ── 辅助方法 ──────────────────────────────────────────────────────────
    
    def _generate_with_context(self, ctx: PipelineContext) -> str:
        """基于检索上下文生成回答"""
        # 构建上下文提示
        context_text = "\n".join([
            f"[{i+1}] {item.get('content', str(item))}"
            for i, item in enumerate(ctx.retrieved_context)
        ])
        
        prompt = f"""基于以下参考资料回答问题：

参考资料：
{context_text}

问题：{ctx.query}

要求：
1. 基于资料准确回答
2. 如资料不足，说明不知道
3. 引用来源

回答："""
        
        # 调用 OllamaClient
        return self._call_llm(prompt)
    
    def _generate_direct(self, ctx: PipelineContext) -> str:
        """直接生成回答"""
        prompt = f"问题：{ctx.query}\n\n回答："
        return self._call_llm(prompt)
    
    def _format_wiki_response(self, wiki_page) -> str:
        """格式化 Wiki 页面响应"""
        # 复用 WikiGenerator 的格式化逻辑
        return wiki_page.to_markdown()
    
    def _call_llm(self, prompt: str, model: str = "qwen2.5:1.5b") -> str:
        """调用 LLM"""
        from core.ollama_client import OllamaClient
        
        client = OllamaClient()
        response = client.generate(
            prompt=prompt,
            model=model
        )
        return response.get("response", "")
```

### 2.3 集成到 HermesAgent

```python
# core/agent.py 改造方案

class HermesAgent:
    """HermesAgent - 集成统一流水线"""
    
    def __init__(self, config: dict = None):
        # ... 原有初始化 ...
        
        # 新增：统一流水线
        self.pipeline = UnifiedPipeline()
    
    def chat(self, message: str, **kwargs) -> str:
        """统一聊天入口"""
        
        # 获取用户上下文
        user_context = self._get_user_context(kwargs.get("user_id"))
        
        # 使用统一流水线处理
        ctx = self.pipeline.process(
            user_id=kwargs.get("user_id", "default"),
            query=message,
            session_id=self.session_id,
            use_cache=True,
            enable_skill=True
        )
        
        # 检查是否需要澄清
        if ctx.needs_clarification:
            return ctx.clarification_prompt
        
        # 存储到记忆宫殿
        self._store_to_memory(user_context, message, ctx.response)
        
        return ctx.response
    
    def _get_user_context(self, user_id: str) -> dict:
        """获取用户上下文"""
        return self.pipeline.memory_palace.recall_user_context(user_id)
    
    def _store_to_memory(self, context: dict, query: str, response: str):
        """存储到记忆宫殿"""
        self.pipeline.memory_palace.store_fact(
            user_id=context.get("user_id"),
            fact=query,
            category="conversation"
        )
```

---

## 3. R2: 任务执行与技能解耦

### 3.1 问题分析

**现状**：
- `SkillEvolutionAgent` 内部包含完整的执行循环
- 任务执行逻辑与技能固化逻辑耦合
- 难以独立使用任务执行功能

**目标**：
- 提取通用执行引擎
- 技能系统专注固化逻辑
- 支持独立任务执行

### 3.2 实施代码

```python
# core/task_execution/unified_executor.py
"""
统一任务执行器 - Unified Task Executor
========================================

职责：
1. 通用任务执行引擎（SmartTaskExecutor 重构）
2. 与 SkillEvolutionAgent 解耦
3. 支持串行/并行/DAG 执行
4. 支持重试/回滚/检查点

复用：core/task_execution_engine.py 的核心逻辑
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from core.task_execution_engine import (
    TaskNode, TaskStatus, ExecutionStrategy, 
    FailureAction, TaskContext, SmartDecomposer
)

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    result: Any = None
    error: str = ""
    duration: float = 0
    retry_count: int = 0
    checkpoint_id: str = ""


class UnifiedTaskExecutor:
    """
    统一任务执行器
    
    使用示例：
    ```python
    executor = UnifiedTaskExecutor()
    
    # 串行执行
    result = executor.execute_sequential([
        {"id": "t1", "action": "read_file", "params": {"path": "a.txt"}},
        {"id": "t2", "action": "write_file", "params": {"path": "b.txt", "content": "..."}},
    ])
    
    # 并行执行
    result = executor.execute_parallel([
        {"id": "p1", "action": "search", "params": {"query": "python"}},
        {"id": "p2", "action": "search", "params": {"query": "java"}},
    ])
    
    # DAG 执行（带依赖）
    result = executor.execute_dag([
        {"id": "d1", "action": "fetch_data"},
        {"id": "d2", "action": "process", "depends_on": ["d1"]},
        {"id": "d3", "action": "save", "depends_on": ["d2"]},
    ])
    ```
    """
    
    def __init__(
        self,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        enable_checkpoint: bool = True
    ):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.enable_checkpoint = enable_checkpoint
        
        # 任务分解器
        self.decomposer = SmartDecomposer()
        
        # 工具注册表
        self._tool_registry: Dict[str, Callable] = {}
        
        # 检查点存储
        self._checkpoints: Dict[str, Dict] = {}
        
        # 注册内置工具
        self._register_builtin_tools()
        
        logger.info("UnifiedTaskExecutor 初始化完成")
    
    def _register_builtin_tools(self):
        """注册内置工具"""
        from core.tools_registry import ToolRegistry
        
        # 复用 ToolRegistry 的工具
        self._tool_registry = {
            "read_file": self._tool_read_file,
            "write_file": self._tool_write_file,
            "execute_command": self._tool_execute_command,
            "search": self._tool_search,
            "llm_generate": self._tool_llm_generate,
        }
    
    def register_tool(self, name: str, handler: Callable):
        """注册自定义工具"""
        self._tool_registry[name] = handler
    
    # ── 执行入口 ────────────────────────────────────────────────────────────
    
    def execute(
        self,
        tasks: List[Dict],
        strategy: ExecutionStrategy = ExecutionStrategy.SEQUENTIAL,
        context: Optional[TaskContext] = None
    ) -> ExecutionResult:
        """
        执行任务
        
        Args:
            tasks: 任务列表
            strategy: 执行策略
            context: 共享上下文
            
        Returns:
            ExecutionResult: 执行结果
        """
        if context is None:
            context = TaskContext(original_task=str(tasks))
        
        start_time = time.time()
        
        try:
            # 判断是否需要分解
            if self.decomposer.should_decompose(tasks):
                tasks = self.decomposer.decompose(tasks, context)
            
            # 根据策略执行
            if strategy == ExecutionStrategy.SEQUENTIAL:
                result = self._execute_sequential(tasks, context)
            elif strategy == ExecutionStrategy.PARALLEL:
                result = self._execute_parallel(tasks, context)
            elif strategy == ExecutionStrategy.DAG:
                result = self._execute_dag(tasks, context)
            else:
                raise ValueError(f"Unknown strategy: {strategy}")
            
            return ExecutionResult(
                success=True,
                result=result,
                duration=time.time() - start_time
            )
            
        except Exception as e:
            logger.error(f"任务执行失败: {e}")
            return ExecutionResult(
                success=False,
                error=str(e),
                duration=time.time() - start_time
            )
    
    def execute_sequential(self, tasks: List[Dict], context: TaskContext = None) -> List[Any]:
        """串行执行"""
        return self.execute(tasks, ExecutionStrategy.SEQUENTIAL, context)
    
    def execute_parallel(self, tasks: List[Dict], context: TaskContext = None) -> List[Any]:
        """并行执行"""
        return self.execute(tasks, ExecutionStrategy.PARALLEL, context)
    
    def execute_dag(self, tasks: List[Dict], context: TaskContext = None) -> List[Any]:
        """DAG 执行"""
        return self.execute(tasks, ExecutionStrategy.DAG, context)
    
    # ── 执行策略实现 ───────────────────────────────────────────────────────
    
    def _execute_sequential(self, tasks: List[Dict], context: TaskContext) -> List[Any]:
        """串行执行"""
        results = []
        
        for task in tasks:
            result = self._execute_single(task, context)
            results.append(result)
            
            if isinstance(result, dict) and not result.get("success", True):
                # 任务失败，根据策略处理
                failure_action = task.get("failure_action", FailureAction.ABORT)
                if failure_action == FailureAction.ABORT:
                    break
                elif failure_action == FailureAction.SKIP:
                    results.append(None)
                    continue
        
        return results
    
    def _execute_parallel(self, tasks: List[Dict], context: TaskContext) -> List[Any]:
        """并行执行"""
        import concurrent.futures
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(tasks)) as executor:
            futures = {
                executor.submit(self._execute_single, task, context): task
                for task in tasks
            }
            
            results = []
            for future in concurrent.futures.as_completed(futures):
                task = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"任务 {task.get('id')} 执行异常: {e}")
                    results.append({"success": False, "error": str(e)})
        
        return results
    
    def _execute_dag(self, tasks: List[Dict], context: TaskContext) -> List[Any]:
        """DAG 执行（拓扑排序）"""
        # 构建依赖图
        task_map = {t["id"]: t for t in tasks}
        in_degree = {t["id"]: 0 for t in tasks}
        dependents = {t["id"]: [] for t in tasks}
        
        for task in tasks:
            for dep in task.get("depends_on", []):
                in_degree[task["id"]] += 1
                dependents[dep].append(task["id"])
        
        # 拓扑排序
        queue = [tid for tid, degree in in_degree.items() if degree == 0]
        results = {}
        
        while queue:
            current_id = queue.pop(0)
            task = task_map[current_id]
            
            # 执行当前任务
            result = self._execute_single(task, context)
            results[current_id] = result
            
            # 更新依赖计数
            for next_id in dependents[current_id]:
                in_degree[next_id] -= 1
                if in_degree[next_id] == 0:
                    queue.append(next_id)
        
        return [results[t["id"]] for t in tasks]
    
    def _execute_single(self, task: Dict, context: TaskContext) -> Dict:
        """执行单个任务（带重试）"""
        task_id = task.get("id", str(uuid.uuid4()))
        action = task.get("action")
        params = task.get("params", {})
        
        # 保存检查点
        if self.enable_checkpoint:
            checkpoint_id = self._save_checkpoint(task_id, task, context)
        
        # 重试逻辑
        for retry in range(self.max_retries):
            try:
                # 获取工具
                tool = self._tool_registry.get(action)
                if not tool:
                    return {"success": False, "error": f"Unknown action: {action}"}
                
                # 执行
                result = tool(**params)
                
                # 保存结果到上下文
                context.add_result(task_id, result)
                
                return {"success": True, "result": result}
                
            except Exception as e:
                logger.warning(f"任务 {task_id} 第 {retry+1} 次执行失败: {e}")
                if retry < self.max_retries - 1:
                    time.sleep(self.retry_delay * (retry + 1))
                else:
                    context.add_error(task_id, str(e))
                    return {"success": False, "error": str(e), "retry_count": retry + 1}
        
        return {"success": False, "error": "Max retries exceeded"}
    
    # ── 检查点管理 ─────────────────────────────────────────────────────────
    
    def _save_checkpoint(self, task_id: str, task: Dict, context: TaskContext) -> str:
        """保存检查点"""
        checkpoint_id = f"ckpt_{task_id}_{int(time.time())}"
        self._checkpoints[checkpoint_id] = {
            "task": task,
            "context": context.to_dict(),
            "timestamp": time.time()
        }
        return checkpoint_id
    
    def restore_checkpoint(self, checkpoint_id: str) -> bool:
        """恢复检查点"""
        checkpoint = self._checkpoints.get(checkpoint_id)
        if not checkpoint:
            return False
        
        # TODO: 实现恢复逻辑
        return True
    
    # ── 内置工具 ───────────────────────────────────────────────────────────
    
    def _tool_read_file(self, path: str, **kwargs) -> str:
        """读取文件"""
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    
    def _tool_write_file(self, path: str, content: str, **kwargs):
        """写入文件"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"path": path}
    
    def _tool_execute_command(self, command: str, **kwargs) -> str:
        """执行命令"""
        import subprocess
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True
        )
        return result.stdout
    
    def _tool_search(self, query: str, **kwargs) -> List[Dict]:
        """搜索"""
        # 复用 KnowledgeBaseLayer
        from core.fusion_rag.knowledge_base import KnowledgeBaseLayer
        kb = KnowledgeBaseLayer()
        return kb.search(query, top_k=5)
    
    def _tool_llm_generate(self, prompt: str, model: str = "qwen2.5:1.5b", **kwargs) -> str:
        """LLM 生成"""
        from core.ollama_client import OllamaClient
        client = OllamaClient()
        response = client.generate(prompt=prompt, model=model)
        return response.get("response", "")


# ── 技能系统专用封装 ────────────────────────────────────────────────────────


class SkillExecutionAdapter:
    """
    技能执行适配器
    
    将 UnifiedTaskExecutor 适配到 SkillEvolutionAgent
    复用 SkillEvolutionAgent 的技能搜索和固化逻辑
    """
    
    def __init__(self):
        self.executor = UnifiedTaskExecutor()
        self._skill_search = None
        self._skill_store = None
    
    @property
    def skill_search(self):
        """技能搜索（复用 SkillEvolutionAgent）"""
        if self._skill_search is None:
            from core.skill_evolution.agent_loop import SkillEvolutionAgent
            agent = SkillEvolutionAgent()
            self._skill_search = agent._search_similar_skills
        return self._skill_search
    
    def execute_task_with_skill(
        self,
        task_description: str,
        context: List[Any] = None
    ) -> ExecutionResult:
        """
        带技能的任务执行
        
        流程：
        1. 搜索相似技能
        2. 如有 → 复用技能执行
        3. 如无 → 使用 UnifiedTaskExecutor 执行
        4. 执行完成后 → 触发技能固化
        """
        # 搜索相似技能
        similar_skills = self.skill_search(task_description)
        
        if similar_skills:
            # 复用技能
            skill = similar_skills[0]
            logger.info(f"复用技能: {skill.name}")
            return self._execute_with_skill(skill, context)
        else:
            # 执行新任务
            result = self._execute_new_task(task_description, context)
            
            # 触发固化判断
            if result.success:
                self._try_consolidate(task_description, result)
            
            return result
    
    def _execute_with_skill(self, skill, context) -> ExecutionResult:
        """使用技能执行"""
        # TODO: 实现技能执行
        raise NotImplementedError()
    
    def _execute_new_task(self, task_description: str, context) -> ExecutionResult:
        """执行新任务"""
        # 构建任务
        tasks = [{"id": "main", "action": "llm_generate", "params": {"prompt": task_description}}]
        return self.executor.execute(tasks)
    
    def _try_consolidate(self, task_description: str, result: ExecutionResult):
        """尝试固化技能"""
        # TODO: 调用 SkillEvolutionAgent 的 _try_consolidate
        pass
```

---

## 4. R3: 上下文统一管理

### 4.1 问题分析

**现状**：
- `MemoryPalace` 管理长期记忆
- `SessionDB` 管理会话历史
- `ConversationalClarifier` 管理需求澄清
- 三者分离，调用复杂

**目标**：统一上下文管理器，一次调用获取完整上下文

### 4.2 实施代码

```python
# core/context/unified_context.py
"""
统一上下文管理器 - Unified Context Manager
============================================

职责：
1. 整合 MemoryPalace + SessionDB + ConversationalClarifier
2. 提供统一的上下文获取接口
3. 支持上下文压缩和优先级排序

复用模块：
- MemoryPalace (长期记忆)
- SessionDB (会话历史)
- ConversationalClarifier (需求澄清)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ContextEntry:
    """上下文条目"""
    source: str                    # 来源: palace / session / clarifier
    type: str                      # 类型: fact / preference / commitment / ...
    content: str                   # 内容
    relevance: float = 1.0          # 相关度 (0-1)
    timestamp: float = field(default_factory=time.time)
    access_count: int = 0          # 访问次数
    
    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "type": self.type,
            "content": self.content,
            "relevance": self.relevance,
            "timestamp": self.timestamp,
            "access_count": self.access_count
        }


@dataclass
class UnifiedContext:
    """
    统一上下文
    
    使用示例：
    ```python
    ctx_manager = UnifiedContext(user_id="user_001")
    
    # 获取完整上下文
    context = ctx_manager.get_context(
        query="分析 Python 异步编程",
        max_entries=20
    )
    
    # 构建 LLM prompt
    prompt = ctx_manager.build_prompt(context, query)
    ```
    """
    
    def __init__(
        self,
        user_id: str,
        session_id: str = "",
        max_history: int = 50,
        max_facts: int = 100
    ):
        self.user_id = user_id
        self.session_id = session_id
        self.max_history = max_history
        self.max_facts = max_facts
        
        # 组件初始化（延迟加载）
        self._palace = None
        self._session_db = None
        self._clarifier = None
    
    # ── 属性懒加载 ─────────────────────────────────────────────────────────
    
    @property
    def palace(self):
        if self._palace is None:
            from core.memory_palace.models import MemoryPalace
            self._palace = MemoryPalace()
        return self._palace
    
    @property
    def session_db(self):
        if self._session_db is None:
            from core.session_db import SessionDB
            self._session_db = SessionDB()
        return self._session_db
    
    @property
    def clarifier(self):
        if self._clarifier is None:
            from core.conversational_clarifier import ConversationalClarifier
            self._clarifier = ConversationalClarifier()
        return self._clarifier
    
    # ── 核心接口 ──────────────────────────────────────────────────────────
    
    def get_context(
        self,
        query: str = "",
        max_entries: int = 20,
        include_history: bool = True,
        include_facts: bool = True,
        include_pending: bool = True
    ) -> Dict[str, Any]:
        """
        获取统一上下文
        
        Args:
            query: 当前查询（用于相关度排序）
            max_entries: 最大条目数
            include_history: 包含会话历史
            include_facts: 包含长期记忆
            include_pending: 包含待澄清项
            
        Returns:
            dict: 统一上下文
        """
        entries: List[ContextEntry] = []
        
        # 1. 获取会话历史
        if include_history:
            history_entries = self._get_session_history()
            entries.extend(history_entries)
        
        # 2. 获取长期记忆
        if include_facts:
            fact_entries = self._get_long_term_facts(query)
            entries.extend(fact_entries)
        
        # 3. 获取待澄清项
        if include_pending:
            pending_entries = self._get_pending_clarifications()
            entries.extend(pending_entries)
        
        # 4. 根据相关度排序
        entries = self._sort_by_relevance(entries, query)
        
        # 5. 截断
        entries = entries[:max_entries]
        
        # 6. 构造成结构化上下文
        return self._build_context_struct(entries)
    
    def build_prompt(
        self,
        context: Dict[str, Any],
        query: str,
        system_prompt: str = ""
    ) -> str:
        """
        构建 LLM Prompt
        
        Args:
            context: get_context() 返回的上下文
            query: 用户查询
            system_prompt: 系统提示（可选）
            
        Returns:
            str: 完整的 prompt
        """
        parts = []
        
        # 系统提示
        if system_prompt:
            parts.append(f"【系统】{system_prompt}")
        
        # 上下文
        if context.get("facts"):
            facts_text = "\n".join([
                f"- {f['content']}" for f in context["facts"][:5]
            ])
            parts.append(f"【用户背景】\n{facts_text}")
        
        if context.get("recent_history"):
            history_text = "\n".join([
                f"【{h['role']}】{h['content'][:100]}"
                for h in context["recent_history"][-3:]
            ])
            parts.append(f"【最近对话】\n{history_text}")
        
        if context.get("pending_clarifications"):
            clarifications = ", ".join(context["pending_clarifications"])
            parts.append(f"【待澄清】{clarifications}")
        
        # 用户查询
        parts.append(f"【当前问题】{query}")
        
        return "\n\n".join(parts)
    
    def should_clarify(self, query: str) -> Tuple[bool, str]:
        """
        判断是否需要澄清
        
        Returns:
            (需要澄清, 澄清提示)
        """
        return self.clarifier.should_prompt(query), ""
    
    def record_interaction(
        self,
        role: str,
        content: str,
        metadata: Dict = None
    ):
        """记录交互到会话历史"""
        self.session_db.add_message(
            session_id=self.session_id,
            role=role,
            content=content,
            metadata=metadata or {}
        )
        
        # 同时存入记忆宫殿
        if role == "user":
            self.palace.store_fact(
                user_id=self.user_id,
                fact=content,
                category="conversation",
                tags=["interaction"]
            )
    
    def store_fact(
        self,
        fact: str,
        category: str = "general",
        tags: List[str] = None,
        commitment: bool = False
    ):
        """存储事实到长期记忆"""
        self.palace.store_fact(
            user_id=self.user_id,
            fact=fact,
            category=category,
            tags=tags,
            commitment=commitment
        )
    
    # ── 私有方法 ───────────────────────────────────────────────────────────
    
    def _get_session_history(self) -> List[ContextEntry]:
        """获取会话历史"""
        entries = []
        
        try:
            messages = self.session_db.get_recent(
                session_id=self.session_id,
                limit=self.max_history
            )
            
            for msg in messages:
                entries.append(ContextEntry(
                    source="session",
                    type="message",
                    content=msg.get("content", ""),
                    timestamp=msg.get("timestamp", time.time())
                ))
        except Exception as e:
            logger.warning(f"获取会话历史失败: {e}")
        
        return entries
    
    def _get_long_term_facts(self, query: str) -> List[ContextEntry]:
        """获取长期记忆"""
        entries = []
        
        try:
            facts = self.palace.recall_user_context(
                user_id=self.user_id,
                query=query,
                max_results=self.max_facts
            )
            
            for fact in facts:
                entries.append(ContextEntry(
                    source="palace",
                    type=fact.get("category", "general"),
                    content=fact.get("content", ""),
                    relevance=fact.get("relevance", 1.0),
                    timestamp=fact.get("timestamp", time.time()),
                    access_count=fact.get("access_count", 0)
                ))
        except Exception as e:
            logger.warning(f"获取长期记忆失败: {e}")
        
        return entries
    
    def _get_pending_clarifications(self) -> List[ContextEntry]:
        """获取待澄清项"""
        entries = []
        
        try:
            pending = self.clarifier.get_pending_clarifications()
            
            for item in pending:
                entries.append(ContextEntry(
                    source="clarifier",
                    type="pending_clarification",
                    content=item.get("question", ""),
                    relevance=0.8  # 待澄清项默认较高优先级
                ))
        except Exception as e:
            logger.warning(f"获取待澄清项失败: {e}")
        
        return entries
    
    def _sort_by_relevance(
        self,
        entries: List[ContextEntry],
        query: str
    ) -> List[ContextEntry]:
        """根据相关度排序"""
        # 简单实现：按 source 优先级 + relevance 排序
        source_priority = {"clarifier": 3, "palace": 2, "session": 1}
        
        def sort_key(entry: ContextEntry) -> Tuple[int, float]:
            priority = source_priority.get(entry.source, 0)
            return (priority, entry.relevance)
        
        return sorted(entries, key=sort_key, reverse=True)
    
    def _build_context_struct(
        self,
        entries: List[ContextEntry]
    ) -> Dict[str, Any]:
        """构造成结构化上下文"""
        # 按来源分组
        by_source = {"session": [], "palace": [], "clarifier": []}
        
        for entry in entries:
            if entry.source in by_source:
                by_source[entry.source].append(entry.to_dict())
        
        # 提取关键类型
        facts = [e for e in entries if e.type in ("fact", "preference", "commitment")]
        recent_history = [e for e in entries if e.source == "session"][-10:]
        pending_clarifications = [e for e in entries if e.source == "clarifier"]
        
        return {
            "user_id": self.user_id,
            "session_id": self.session_id,
            "timestamp": time.time(),
            
            # 分组
            "by_source": by_source,
            
            # 分类
            "facts": [f.to_dict() for f in facts],
            "recent_history": [h.to_dict() for h in recent_history],
            "pending_clarifications": [p.to_dict() for p in pending_clarifications],
            
            # 统计
            "total_entries": len(entries),
            "source_counts": {
                source: len(items)
                for source, items in by_source.items()
            }
        }
```

---

## 5. R4: 智能写作工作流

### 5.1 问题分析

**现状**：
- `AIEnhancedGeneration` 和 `ProjectGeneration` 相互独立
- 未复用 `DeepSearchWikiSystem` 的搜索能力
- 未复用 `ConversationalClarifier` 的需求引导

**目标**：建立统一的智能写作工作流，整合所有相关模块

### 5.2 实施代码

```python
# core/smart_writing/unified_workflow.py
"""
智能写作统一工作流 - Smart Writing Unified Workflow
=====================================================

职责：
1. 统一 AI 写作和项目生成流程
2. 整合需求澄清 → 深度搜索 → Wiki 生成 → 审核辩论
3. 支持多轮迭代优化

复用模块：
- ConversationalClarifier (需求澄清)
- DeepSearchWikiSystem (深度搜索)
- AIEnhancedGeneration (内容生成)
- ProjectGeneration (项目生成)
- ReviewMaster (审核)
- AdversarialReview (对抗评审)
- DigitalAvatar (数字分身)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Iterator

logger = logging.getLogger(__name__)


class WritingStage(Enum):
    """写作阶段"""
    REQUIREMENT_CLARIFICATION = "requirement_clarification"
    KNOWLEDGE_RETRIEVAL = "knowledge_retrieval"
    DEEP_SEARCH = "deep_search"
    CONTENT_GENERATION = "content_generation"
    REVIEW_DEBATE = "review_debate"
    VIRTUAL_MEETING = "virtual_meeting"
    FINAL_REVISION = "final_revision"
    COMPLETED = "completed"


@dataclass
class WritingContext:
    """写作上下文"""
    # 输入
    user_requirement: str
    document_type: str = "general"  # general / report / proposal / code
    
    # 阶段状态
    current_stage: WritingStage = WritingStage.REQUIREMENT_CLARIFICATION
    stage_history: List[Dict] = field(default_factory=list)
    
    # 中间产物
    clarified_requirements: str = ""
    retrieved_knowledge: List[Dict] = field(default_factory=list)
    search_results: List[Dict] = field(default_factory=list)
    draft_content: str = ""
    review_issues: List[Dict] = field(default_factory=list)
    debate_transcript: str = ""
    
    # 最终产物
    final_content: str = ""
    confidence: float = 0.0
    
    # 元数据
    iterations: int = 0
    start_time: float = field(default_factory=time.time)


class SmartWritingWorkflow:
    """
    智能写作统一工作流
    
    使用示例：
    ```python
    workflow = SmartWritingWorkflow()
    
    # 同步执行
    result = workflow.execute(
        requirement="写一份关于 AI Agent 的技术报告",
        document_type="report"
    )
    
    # 流式执行
    for stage_result in workflow.execute_stream(requirement):
        print(f"Stage: {stage_result['stage']}")
        print(f"Content: {stage_result['content']}")
    ```
    """
    
    def __init__(
        self,
        max_iterations: int = 3,
        enable_review: bool = True,
        enable_debate: bool = True
    ):
        self.max_iterations = max_iterations
        self.enable_review = enable_review
        self.enable_debate = enable_debate
        
        # 组件初始化
        self._clarifier = None
        self._knowledge_base = None
        self._wiki_generator = None
        self._content_generator = None
        self._review_master = None
        
        logger.info("SmartWritingWorkflow 初始化完成")
    
    # ── 属性懒加载 ─────────────────────────────────────────────────────────
    
    @property
    def clarifier(self):
        if self._clarifier is None:
            from core.conversational_clarifier import ConversationalClarifier
            self._clarifier = ConversationalClarifier()
        return self._clarifier
    
    @property
    def knowledge_base(self):
        if self._knowledge_base is None:
            from core.fusion_rag.knowledge_base import KnowledgeBaseLayer
            self._knowledge_base = KnowledgeBaseLayer()
        return self._knowledge_base
    
    @property
    def wiki_generator(self):
        if self._wiki_generator is None:
            from core.deep_search_wiki.wiki_generator import WikiGenerator
            self._wiki_generator = WikiGenerator()
        return self._wiki_generator
    
    @property
    def content_generator(self):
        if self._content_generator is None:
            from core.smart_writing.ai_enhanced_generation import AIEnhancedGeneration
            self._content_generator = AIEnhancedGeneration()
        return self._content_generator
    
    # ── 执行入口 ───────────────────────────────────────────────────────────
    
    def execute(
        self,
        requirement: str,
        document_type: str = "general",
        config: Dict = None
    ) -> WritingContext:
        """
        执行智能写作工作流（同步版本）
        """
        ctx = WritingContext(
            user_requirement=requirement,
            document_type=document_type
        )
        
        config = config or {}
        
        try:
            # Stage 1: 需求澄清
            ctx = self._stage_clarification(ctx)
            if ctx.current_stage == WritingStage.REQUIREMENT_CLARIFICATION:
                # 等待用户确认
                return ctx
            
            # Stage 2: 知识检索
            ctx = self._stage_knowledge_retrieval(ctx)
            
            # Stage 3: 深度搜索
            ctx = self._stage_deep_search(ctx)
            
            # Stage 4: 内容生成
            ctx = self._stage_content_generation(ctx)
            
            # Stage 5: 审核辩论（可选）
            if self.enable_review:
                ctx = self._stage_review_debate(ctx)
            
            # Stage 6: 最终修订
            ctx = self._stage_final_revision(ctx)
            
            ctx.current_stage = WritingStage.COMPLETED
            
        except Exception as e:
            logger.error(f"写作工作流失败: {e}")
            ctx.final_content = f"生成失败: {str(e)}"
        
        return ctx
    
    def execute_stream(
        self,
        requirement: str,
        document_type: str = "general"
    ) -> Iterator[Dict]:
        """
        执行智能写作工作流（流式版本）
        """
        ctx = WritingContext(
            user_requirement=requirement,
            document_type=document_type
        )
        
        # Stage 1: 需求澄清
        yield {"stage": "clarification", "content": "正在分析需求..."}
        ctx = self._stage_clarification(ctx)
        yield {"stage": "clarification", "content": ctx.clarified_requirements}
        
        if ctx.current_stage == WritingStage.REQUIREMENT_CLARIFICATION:
            yield {"stage": "wait_confirm", "content": "需要确认需求"}
            return
        
        # Stage 2-4: 检索和生成
        yield {"stage": "retrieval", "content": "正在检索知识..."}
        ctx = self._stage_knowledge_retrieval(ctx)
        
        yield {"stage": "search", "content": "正在进行深度搜索..."}
        ctx = self._stage_deep_search(ctx)
        
        yield {"stage": "generation", "content": "正在生成内容..."}
        ctx = self._stage_content_generation(ctx)
        yield {"stage": "draft", "content": ctx.draft_content}
        
        # Stage 5: 审核
        if self.enable_review:
            yield {"stage": "review", "content": "正在进行审核..."}
            ctx = self._stage_review_debate(ctx)
        
        # Stage 6: 最终结果
        yield {"stage": "completed", "content": ctx.final_content}
    
    # ── 阶段实现 ───────────────────────────────────────────────────────────
    
    def _stage_clarification(self, ctx: WritingContext) -> WritingContext:
        """Stage 1: 需求澄清"""
        ctx.current_stage = WritingStage.REQUIREMENT_CLARIFICATION
        
        # 使用 ConversationalClarifier 检测模糊需求
        needs_clarify, prompt = self.clarifier.should_prompt(ctx.user_requirement)
        
        if needs_clarify:
            # 生成澄清问题
            ctx.clarified_requirements = self._generate_clarification_questions(
                ctx.user_requirement
            )
            # 保持等待确认状态
        else:
            # 需求已明确，直接进入下一阶段
            ctx.clarified_requirements = ctx.user_requirement
            ctx.current_stage = WritingStage.KNOWLEDGE_RETRIEVAL
        
        ctx.stage_history.append({
            "stage": "clarification",
            "timestamp": time.time(),
            "needs_clarify": needs_clarify
        })
        
        return ctx
    
    def _generate_clarification_questions(self, requirement: str) -> str:
        """生成澄清问题"""
        prompt = f"""分析以下需求，生成澄清问题：

需求：{requirement}

请指出：
1. 模糊或不明确的地方
2. 缺失的关键信息
3. 需要确认的假设

格式：
- 问题1：...
- 问题2：...
- 问题3：..."""
        
        from core.ollama_client import OllamaClient
        client = OllamaClient()
        response = client.generate(prompt=prompt, model="qwen2.5:1.5b")
        return response.get("response", "")
    
    def _stage_knowledge_retrieval(self, ctx: WritingContext) -> WritingContext:
        """Stage 2: 知识检索"""
        ctx.current_stage = WritingStage.KNOWLEDGE_RETRIEVAL
        
        # 使用 KnowledgeBaseLayer 检索
        ctx.retrieved_knowledge = self.knowledge_base.search(
            query=ctx.clarified_requirements,
            top_k=10
        )
        
        ctx.stage_history.append({
            "stage": "retrieval",
            "timestamp": time.time(),
            "results_count": len(ctx.retrieved_knowledge)
        })
        
        return ctx
    
    def _stage_deep_search(self, ctx: WritingContext) -> WritingContext:
        """Stage 3: 深度搜索"""
        ctx.current_stage = WritingStage.DEEP_SEARCH
        
        # 使用 DeepSearchWikiSystem
        wiki_page = self.wiki_generator.generate(
            topic=ctx.clarified_requirements,
            search_results=ctx.retrieved_knowledge,
            use_search=True
        )
        
        # 转换为搜索结果格式
        ctx.search_results = [
            {
                "title": section.title,
                "content": section.content,
                "source": section.source
            }
            for section in wiki_page.sections
        ]
        
        ctx.stage_history.append({
            "stage": "deep_search",
            "timestamp": time.time(),
            "sections_count": len(wiki_page.sections)
        })
        
        return ctx
    
    def _stage_content_generation(self, ctx: WritingContext) -> WritingContext:
        """Stage 4: 内容生成"""
        ctx.current_stage = WritingStage.CONTENT_GENERATION
        
        # 根据文档类型选择生成器
        if ctx.document_type == "project":
            from core.smart_writing.project_generation import ProjectGeneration
            generator = ProjectGeneration()
            result = generator.generate(
                requirement=ctx.clarified_requirements,
                knowledge=ctx.retrieved_knowledge,
                search_results=ctx.search_results
            )
            ctx.draft_content = result.get("content", "")
        else:
            # 使用 AIEnhancedGeneration
            result = self.content_generator.generate(
                requirement=ctx.clarified_requirements,
                context=ctx.search_results
            )
            ctx.draft_content = result.get("content", "")
        
        ctx.stage_history.append({
            "stage": "generation",
            "timestamp": time.time(),
            "content_length": len(ctx.draft_content)
        })
        
        return ctx
    
    def _stage_review_debate(self, ctx: WritingContext) -> WritingContext:
        """Stage 5: 审核辩论"""
        ctx.current_stage = WritingStage.REVIEW_DEBATE
        
        if not self.enable_review:
            return ctx
        
        # 使用 ReviewMaster 进行审核
        # （复用 core/review_master/ 的逻辑）
        
        ctx.stage_history.append({
            "stage": "review_debate",
            "timestamp": time.time(),
            "issues_count": len(ctx.review_issues)
        })
        
        return ctx
    
    def _stage_final_revision(self, ctx: WritingContext) -> WritingContext:
        """Stage 6: 最终修订"""
        ctx.current_stage = WritingStage.FINAL_REVISION
        
        # 根据审核意见修订
        if ctx.review_issues:
            ctx.final_content = self._apply_revisions(
                ctx.draft_content,
                ctx.review_issues
            )
        else:
            ctx.final_content = ctx.draft_content
        
        # 计算置信度
        ctx.confidence = self._calculate_confidence(ctx)
        
        ctx.stage_history.append({
            "stage": "final_revision",
            "timestamp": time.time(),
            "confidence": ctx.confidence
        })
        
        return ctx
    
    # ── 辅助方法 ───────────────────────────────────────────────────────────
    
    def _apply_revisions(self, content: str, issues: List[Dict]) -> str:
        """应用修订"""
        # TODO: 实现修订逻辑
        return content
    
    def _calculate_confidence(self, ctx: WritingContext) -> float:
        """计算置信度"""
        factors = []
        
        # 知识检索覆盖率
        if ctx.retrieved_knowledge:
            factors.append(0.3)
        
        # 深度搜索覆盖率
        if ctx.search_results:
            factors.append(0.3)
        
        # 审核问题数量
        if len(ctx.review_issues) == 0:
            factors.append(0.4)
        elif len(ctx.review_issues) < 3:
            factors.append(0.2)
        else:
            factors.append(0.0)
        
        return min(1.0, sum(factors))
```

---

## 6. R5: 面板与引擎分离

### 6.1 问题分析

**现状**：
- `ui/ai_enhanced_generation_panel.py` 混合了 UI 和业务逻辑
- 难以独立测试业务逻辑
- 难以复用后端引擎

**目标**：将 UI 与业务逻辑完全分离

### 6.2 实施代码

```python
# ui/panels/smart_writing_panel.py
"""
智能写作面板 - Smart Writing Panel (重构版)
=============================================

职责：
1. UI 展示（PyQt6）
2. 事件转发到业务引擎
3. 结果展示

复用：
- SmartWritingWorkflow (业务逻辑)
- UnifiedContext (上下文)
"""

from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton,
    QTextEdit, QLabel, QProgressBar, QWidget
)

from core.smart_writing.unified_workflow import SmartWritingWorkflow, WritingStage

logger = logging.getLogger(__name__)


class WritingWorker(QThread):
    """写作工作线程"""
    
    progress = pyqtSignal(str, str)  # stage, message
    content_ready = pyqtSignal(str)  # content
    error = pyqtSignal(str)
    
    def __init__(self, workflow: SmartWritingWorkflow, requirement: str, doc_type: str):
        super().__init__()
        self.workflow = workflow
        self.requirement = requirement
        self.doc_type = doc_type
    
    def run(self):
        try:
            # 流式执行
            for stage_result in self.workflow.execute_stream(
                requirement=self.requirement,
                document_type=self.doc_type
            ):
                self.progress.emit(
                    stage_result["stage"],
                    stage_result["content"]
                )
                
                if stage_result["stage"] == "completed":
                    self.content_ready.emit(stage_result["content"])
                    
        except Exception as e:
            logger.error(f"写作失败: {e}")
            self.error.emit(str(e))


class SmartWritingPanel(QWidget):
    """
    智能写作面板（UI 层）
    
    仅负责：
    1. UI 渲染
    2. 用户输入
    3. 结果展示
    
    不包含：
    - 业务逻辑（委托给 SmartWritingWorkflow）
    - 数据处理（委托给 UnifiedContext）
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 业务引擎（复用）
        self.workflow = SmartWritingWorkflow()
        
        # 工作线程
        self.worker: Optional[WritingWorker] = None
        
        # UI 组件
        self._init_ui()
    
    def _init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        
        # 需求输入
        self.requirement_input = QTextEdit()
        self.requirement_input.setPlaceholderText("输入您的写作需求...")
        layout.addWidget(QLabel("需求描述"))
        layout.addWidget(self.requirement_input)
        
        # 文档类型选择
        self.doc_type_layout = QHBoxLayout()
        self.doc_type_layout.addWidget(QLabel("文档类型"))
        # ... 添加类型选择按钮 ...
        layout.addLayout(self.doc_type_layout)
        
        # 生成按钮
        self.generate_btn = QPushButton("开始生成")
        self.generate_btn.clicked.connect(self._on_generate)
        layout.addWidget(self.generate_btn)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # 状态标签
        self.status_label = QLabel()
        layout.addWidget(self.status_label)
        
        # 结果展示
        self.result_output = QTextEdit()
        self.result_output.setReadOnly(True)
        layout.addWidget(QLabel("生成结果"))
        layout.addWidget(self.result_output)
    
    def _on_generate(self):
        """触发生成"""
        requirement = self.requirement_input.toPlainText().strip()
        if not requirement:
            self.status_label.setText("请输入需求")
            return
        
        # 禁用按钮
        self.generate_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        
        # 启动工作线程
        self.worker = WritingWorker(
            workflow=self.workflow,
            requirement=requirement,
            doc_type="general"
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.content_ready.connect(self._on_content_ready)
        self.worker.error.connect(self._on_error)
        self.worker.start()
    
    def _on_progress(self, stage: str, message: str):
        """进度更新"""
        self.status_label.setText(f"阶段: {stage}")
        self.result_output.append(f"[{stage}] {message[:100]}...")
    
    def _on_content_ready(self, content: str):
        """内容就绪"""
        self.result_output.setPlainText(content)
        self.generate_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText("生成完成")
    
    def _on_error(self, error: str):
        """错误处理"""
        self.status_label.setText(f"错误: {error}")
        self.generate_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
```

---

## 7. 实施计划

### 7.1 优先级排序

| 优先级 | 重构项 | 工作量 | 收益 | 风险 |
|-------|-------|-------|-----|-----|
| **P0** | R1: 统一入口整合 | 高 | 高 | 中 |
| **P1** | R3: 上下文统一管理 | 中 | 高 | 低 |
| **P2** | R2: 任务执行解耦 | 高 | 中 | 中 |
| **P3** | R4: 智能写作工作流 | 中 | 高 | 低 |
| **P4** | R5: 面板引擎分离 | 低 | 中 | 低 |

### 7.2 实施步骤

```
Week 1-2: R1 + R3
├── 实现 UnifiedPipeline
├── 实现 UnifiedContext
├── 集成到 HermesAgent
└── 单元测试

Week 3-4: R2
├── 提取 UnifiedTaskExecutor
├── 适配 SkillExecutionAdapter
└── 迁移现有调用

Week 5-6: R4
├── 实现 SmartWritingWorkflow
├── 复用 WikiGenerator + KnowledgeBase
└── 对接 UI Panel

Week 7-8: R5
├── 重构 AIEnhancedGenerationPanel
├── 解耦业务逻辑
└── 集成测试
```

### 7.3 回归测试清单

| 测试项 | 验证内容 | 优先级 |
|-------|---------|-------|
| 意图分类 | QueryIntentClassifier 准确性 | P0 |
| 缓存命中 | UnifiedCache L0/L1/L2/L3 | P0 |
| 知识检索 | KnowledgeBaseLayer 召回率 | P0 |
| 深度搜索 | WikiGenerator 输出质量 | P1 |
| 任务执行 | SmartTaskExecutor DAG | P1 |
| 上下文 | MemoryPalace + SessionDB | P2 |
| 技能固化 | SkillEvolutionAgent | P2 |

---

## 8. 总结

本技术方案提供了 **5 个核心重构方向** 的详细实施方案：

1. **R1 统一入口整合**：建立标准化流水线，复用 8+ 核心模块
2. **R2 任务执行解耦**：提取通用执行引擎，技能系统专注固化
3. **R3 上下文统一管理**：一次调用获取完整上下文
4. **R4 智能写作工作流**：整合需求澄清→搜索→生成→审核全流程
5. **R5 面板引擎分离**：UI 与业务逻辑完全解耦

所有方案均基于 **已有模块**，最大程度复用现有代码，避免重复造轮子。

---

> 📌 **下一步建议**：选择一个优先级最高（P0）的重构项开始实施，例如 **R1: 统一入口整合**，具体执行时先从 `UnifiedPipeline` 核心类开始，逐步集成到 `HermesAgent`。
