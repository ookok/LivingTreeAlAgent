"""
AI协作系统
AI Collaborator System

三级AI协同架构：
- L1 即时辅助: 语法检查、错别字、基础补全 (<100ms)
- L2 深度协作: 段落重写、风格调整、逻辑优化 (1-3s)
- L3 创意伙伴: 情节发展、人物塑造、主题深化 (3-10s)
"""

import asyncio
import time
from typing import Optional, Callable, Any, Generator
from dataclasses import dataclass, field
from enum import Enum
import hashlib


class AILevel(Enum):
    """AI处理层级"""
    L1_INSTANT = "l1_instant"    # L1 即时辅助
    L2_DEEP = "l2_deep"          # L2 深度协作
    L3_CREATIVE = "l3_creative"  # L3 创意伙伴


class TaskPriority(Enum):
    """任务优先级"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3


@dataclass
class AITask:
    """AI任务"""
    task_id: str
    task_type: str  # grammar, polish, expand, creative, etc.
    content: str
    context: dict = field(default_factory=dict)
    
    ai_level: AILevel = AILevel.L1_INSTANT
    priority: TaskPriority = TaskPriority.NORMAL
    
    timeout_ms: int = 5000
    retry_count: int = 0
    max_retries: int = 2
    
    created_at: float = field(default_factory=time.time)
    
    def __hash__(self):
        return hash(self.task_id)


@dataclass
class AIResponse:
    """AI响应"""
    task_id: str
    success: bool
    content: str = ""
    
    confidence: float = 0.0
    suggestions: list = field(default_factory=list)
    processing_time_ms: float = 0.0
    
    ai_level_used: AILevel = AILevel.L1_INSTANT
    model_used: str = ""
    
    error: str = ""
    fallback_used: bool = False


@dataclass
class ModelConfig:
    """模型配置"""
    model_name: str
    max_tokens: int = 1000
    temperature: float = 0.5
    top_p: float = 0.9
    
    timeout_ms: int = 5000
    supports_streaming: bool = True
    
    is_local: bool = True
    requires_internet: bool = False


class AICollaborator:
    """
    AI协作系统
    
    提供三级AI协同能力
    """
    
    # 模型配置
    MODEL_CONFIGS = {
        # L1 即时模型（本地，轻量）
        AILevel.L1_INSTANT: ModelConfig(
            model_name="phi-2",
            max_tokens=500,
            temperature=0.3,
            timeout_ms=100,
            is_local=True,
        ),
        # L2 标准模型（本地/云端）
        AILevel.L2_DEEP: ModelConfig(
            model_name="qwen2.5:7b",
            max_tokens=2000,
            temperature=0.5,
            timeout_ms=3000,
            is_local=True,
        ),
        # L3 创意模型（云端/大模型）
        AILevel.L3_CREATIVE: ModelConfig(
            model_name="qwen2.5:14b",
            max_tokens=4000,
            temperature=0.8,
            timeout_ms=10000,
            is_local=True,
        ),
    }
    
    # 任务类型到AI层级的映射
    TASK_TO_LEVEL = {
        "grammar": AILevel.L1_INSTANT,
        "spell_check": AILevel.L1_INSTANT,
        "auto_complete": AILevel.L1_INSTANT,
        "format": AILevel.L1_INSTANT,
        "quick_fix": AILevel.L1_INSTANT,
        
        "polish": AILevel.L2_DEEP,
        "rewrite": AILevel.L2_DEEP,
        "expand": AILevel.L2_DEEP,
        "structure": AILevel.L2_DEEP,
        "analyze": AILevel.L2_DEEP,
        "summarize": AILevel.L2_DEEP,
        
        "creative": AILevel.L3_CREATIVE,
        "story": AILevel.L3_CREATIVE,
        "character": AILevel.L3_CREATIVE,
        "theme": AILevel.L3_CREATIVE,
        "brainstorm": AILevel.L3_CREATIVE,
        "world_building": AILevel.L3_CREATIVE,
    }
    
    def __init__(self, agent=None):
        self.agent = agent
        
        # 任务队列
        self._task_queue: list[AITask] = []
        self._processing = False
        self._lock = asyncio.Lock()
        
        # 回调
        self.on_task_complete: Optional[Callable] = None
        self.on_progress: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
    
    # ==================== 任务提交 ====================
    
    def submit_task(
        self,
        task_type: str,
        content: str,
        context: dict = None,
        ai_level: AILevel = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        **kwargs,
    ) -> str:
        """
        提交AI任务
        
        Args:
            task_type: 任务类型
            content: 任务内容
            context: 上下文信息
            ai_level: 指定AI层级（自动检测如果为None）
            priority: 任务优先级
            
        Returns:
            任务ID
        """
        task_id = self._generate_task_id(task_type, content)
        
        # 自动检测AI层级
        if ai_level is None:
            ai_level = self.TASK_TO_LEVEL.get(task_type, AILevel.L2_DEEP)
        
        # 获取超时配置
        config = self.MODEL_CONFIGS.get(ai_level)
        timeout_ms = kwargs.get("timeout_ms", config.timeout_ms if config else 5000)
        
        task = AITask(
            task_id=task_id,
            task_type=task_type,
            content=content,
            context=context or {},
            ai_level=ai_level,
            priority=priority,
            timeout_ms=timeout_ms,
        )
        
        # 添加到队列（按优先级排序）
        self._add_to_queue(task)
        
        return task_id
    
    def _generate_task_id(self, task_type: str, content: str) -> str:
        """生成任务ID"""
        hash_input = f"{task_type}:{content[:50]}:{time.time()}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:12]
    
    def _add_to_queue(self, task: AITask):
        """添加任务到队列"""
        # 按优先级插入
        inserted = False
        for i, t in enumerate(self._task_queue):
            if task.priority.value > t.priority.value:
                self._task_queue.insert(i, task)
                inserted = True
                break
        
        if not inserted:
            self._task_queue.append(task)
    
    # ==================== 任务执行 ====================
    
    async def process_task(self, task: AITask) -> AIResponse:
        """
        处理单个任务
        
        Args:
            task: AI任务
            
        Returns:
            AI响应
        """
        start_time = time.time()
        
        try:
            # 根据任务类型分发处理
            if task.ai_level == AILevel.L1_INSTANT:
                result = await self._process_l1(task)
            elif task.ai_level == AILevel.L2_DEEP:
                result = await self._process_l2(task)
            else:
                result = await self._process_l3(task)
            
            result.processing_time_ms = (time.time() - start_time) * 1000
            result.success = True
            
        except asyncio.TimeoutError:
            result = AIResponse(
                task_id=task.task_id,
                success=False,
                error="任务超时",
                ai_level_used=task.ai_level,
                processing_time_ms=(time.time() - start_time) * 1000,
            )
            
            # 尝试降级重试
            if task.retry_count < task.max_retries:
                result = await self._retry_with_fallback(task)
        
        except Exception as e:
            result = AIResponse(
                task_id=task.task_id,
                success=False,
                error=str(e),
                ai_level_used=task.ai_level,
                processing_time_ms=(time.time() - start_time) * 1000,
            )
        
        return result
    
    async def _process_l1(self, task: AITask) -> AIResponse:
        """L1即时处理（本地）"""
        content = task.content
        
        # 根据任务类型执行
        if task.task_type == "grammar":
            content = await self._grammar_check(content)
        elif task.task_type == "spell_check":
            content = await self._spell_check(content)
        elif task.task_type == "auto_complete":
            content = await self._auto_complete(content, task.context)
        elif task.task_type == "format":
            content = self._apply_format(content, task.context)
        
        return AIResponse(
            task_id=task.task_id,
            success=True,
            content=content,
            confidence=0.95,
            ai_level_used=AILevel.L1_INSTANT,
            model_used=self.MODEL_CONFIGS[AILevel.L1_INSTANT].model_name,
        )
    
    async def _process_l2(self, task: AITask) -> AIResponse:
        """L2深度处理"""
        prompt = self._build_l2_prompt(task)
        
        # 调用AI
        content = await self._call_ai(
            prompt,
            self.MODEL_CONFIGS[AILevel.L2_DEEP],
        )
        
        return AIResponse(
            task_id=task.task_id,
            success=True,
            content=content,
            confidence=0.85,
            ai_level_used=AILevel.L2_DEEP,
            model_used=self.MODEL_CONFIGS[AILevel.L2_DEEP].model_name,
        )
    
    async def _process_l3(self, task: AITask) -> AIResponse:
        """L3创意处理"""
        prompt = self._build_l3_prompt(task)
        
        # 调用AI
        content = await self._call_ai(
            prompt,
            self.MODEL_CONFIGS[AILevel.L3_CREATIVE],
        )
        
        return AIResponse(
            task_id=task.task_id,
            success=True,
            content=content,
            confidence=0.75,
            ai_level_used=AILevel.L3_CREATIVE,
            model_used=self.MODEL_CONFIGS[AILevel.L3_CREATIVE].model_name,
        )
    
    async def _retry_with_fallback(self, task: AITask) -> AIResponse:
        """降级重试"""
        task.retry_count += 1
        
        # 降级到L1
        original_level = task.ai_level
        task.ai_level = AILevel.L1_INSTANT
        
        result = await self.process_task(task)
        result.fallback_used = True
        
        # 恢复原始级别
        task.ai_level = original_level
        
        return result
    
    # ==================== L1处理实现 ====================
    
    async def _grammar_check(self, text: str) -> str:
        """语法检查"""
        corrections = []
        result = text
        
        # 简单语法检查规则
        rules = [
            # 的/地/得
            (r"的地得", self._fix_de_d,
             "注意区分\"的\"、\"地\"、\"得\"的使用"),
            
            # 重复字词
            (r"(.)\1{2,}", lambda m: m.group(1) * 2,
             "检测到重复字符"),
            
            # 常见错别字
            {
                "那里": "那里",
                "在哪": "在哪",
                # 可以添加更多
            },
        ]
        
        for rule in rules:
            if isinstance(rule[0], str) and callable(rule[1]):
                pattern, fix_func, _ = rule
                if pattern in result:
                    result = fix_func(result)
                    corrections.append(rule[2])
        
        return result
    
    def _fix_de_d(self, text: str) -> str:
        """修复的/地/得"""
        # 简化版本，实际需要更复杂的NLP
        return text
    
    async def _spell_check(self, text: str) -> str:
        """拼写检查"""
        # 简单实现
        return text
    
    async def _auto_complete(self, text: str, context: dict) -> str:
        """自动补全"""
        if not text:
            return ""
        
        # 简单实现：基于上下文的补全
        last_chars = text[-20:] if len(text) > 20 else text
        
        # 检测未完成句子
        if any(text.rstrip().endswith(p) for p in ["，", "、", "（", "“"]):
            # 未完成句子，尝试补全
            return f"{text}[待续...]"
        
        return text
    
    def _apply_format(self, text: str, context: dict) -> str:
        """应用格式"""
        fmt = context.get("format", "markdown")
        
        if fmt == "markdown":
            return text
        elif fmt == "latex":
            return self._to_latex(text)
        else:
            return text
    
    def _to_latex(self, text: str) -> str:
        """转换为LaTeX"""
        return text
    
    # ==================== 提示构建 ====================
    
    def _build_l2_prompt(self, task: AITask) -> str:
        """构建L2提示"""
        mode = task.context.get("mode", "creative")
        
        if task.task_type == "polish":
            instruction = "请润色以下文本，使其更加流畅、专业："
        elif task.task_type == "rewrite":
            instruction = "请重写以下内容，保持核心意思但改变表达方式："
        elif task.task_type == "expand":
            instruction = "请扩展以下内容，增加细节和深度："
        elif task.task_type == "structure":
            instruction = "请优化以下内容的结构："
        else:
            instruction = f"请处理以下{topic.task_type}任务："
        
        return f"""{instruction}

要求：
- 保持原文的核心意思
- 适当调整表达方式
- 注意语言流畅性

内容：
{task.content}
"""
    
    def _build_l3_prompt(self, task: AITask) -> str:
        """构建L3提示"""
        genre = task.context.get("genre", "通用")
        tone = task.context.get("tone", "中性")
        
        if task.task_type == "creative":
            instruction = "发挥创意，续写以下内容："
        elif task.task_type == "story":
            instruction = "基于以下设定，创作故事情节："
        elif task.task_type == "character":
            instruction = "为以下角色增添更多细节："
        else:
            instruction = "发挥创意完成以下创作任务："
        
        return f"""你是一个创意写作助手。

写作类型：{genre}
情感基调：{tone}

{instruction}

{task.content}
"""
    
    # ==================== AI调用 ====================
    
    async def _call_ai(self, prompt: str, config: ModelConfig) -> str:
        """调用AI"""
        if self.agent:
            try:
                response = await asyncio.wait_for(
                    self.agent.generate(prompt),
                    timeout=config.timeout_ms / 1000,
                )
                return response
            except Exception as e:
                return f"[AI调用失败: {e}]"
        
        return "[AI未连接]"
    
    # ==================== 流式处理 ====================
    
    async def process_streaming(
        self,
        task: AITask,
        on_token: Callable[[str], None],
    ) -> AIResponse:
        """
        流式处理任务
        
        Args:
            task: AI任务
            on_token: 每个token的回调
            
        Returns:
            最终响应
        """
        start_time = time.time()
        
        try:
            if task.ai_level == AILevel.L1_INSTANT:
                result = await self._process_l1(task)
                on_token(result.content)
            else:
                # L2/L3支持流式
                config = self.MODEL_CONFIGS.get(
                    task.ai_level,
                    self.MODEL_CONFIGS[AILevel.L2_DEEP],
                )
                
                if config.supports_streaming:
                    result_content = await self._call_ai_streaming(
                        self._build_l2_prompt(task) if task.ai_level == AILevel.L2_DEEP else self._build_l3_prompt(task),
                        config,
                        on_token,
                    )
                else:
                    result = await self.process_task(task)
                    on_token(result.content)
                    return result
                
                return AIResponse(
                    task_id=task.task_id,
                    success=True,
                    content=result_content,
                    ai_level_used=task.ai_level,
                    processing_time_ms=(time.time() - start_time) * 1000,
                )
        
        except Exception as e:
            return AIResponse(
                task_id=task.task_id,
                success=False,
                error=str(e),
            )
    
    async def _call_ai_streaming(
        self,
        prompt: str,
        config: ModelConfig,
        on_token: Callable[[str], None],
    ) -> str:
        """流式调用AI"""
        # 如果agent支持流式
        if hasattr(self.agent, "generate_streaming"):
            return await self.agent.generate_streaming(prompt, on_token)
        
        # 否则使用普通调用
        result = await self._call_ai(prompt, config)
        on_token(result)
        return result
    
    # ==================== 批处理 ====================
    
    async def process_batch(
        self,
        tasks: list[AITask],
    ) -> list[AIResponse]:
        """
        批量处理任务
        
        Args:
            tasks: 任务列表
            
        Returns:
            响应列表
        """
        results = []
        
        # 按AI层级分组
        l1_tasks = [t for t in tasks if t.ai_level == AILevel.L1_INSTANT]
        l2_tasks = [t for t in tasks if t.ai_level == AILevel.L2_DEEP]
        l3_tasks = [t for t in tasks if t.ai_level == AILevel.L3_CREATIVE]
        
        # L1任务可以并行
        if l1_tasks:
            l1_results = await asyncio.gather(
                *[self.process_task(t) for t in l1_tasks]
            )
            results.extend(l1_results)
        
        # L2任务顺序处理（避免资源竞争）
        for t in l2_tasks:
            results.append(await self.process_task(t))
        
        # L3任务异步处理（耗时长）
        if l3_tasks:
            l3_results = await asyncio.gather(
                *[self.process_task(t) for t in l3_tasks],
                return_exceptions=True,
            )
            results.extend(l3_results)
        
        return results
    
    # ==================== 状态查询 ====================
    
    def get_queue_status(self) -> dict:
        """获取队列状态"""
        return {
            "total_pending": len(self._task_queue),
            "processing": self._processing,
            "by_level": {
                "l1": sum(1 for t in self._task_queue if t.ai_level == AILevel.L1_INSTANT),
                "l2": sum(1 for t in self._task_queue if t.ai_level == AILevel.L2_DEEP),
                "l3": sum(1 for t in self._task_queue if t.ai_level == AILevel.L3_CREATIVE),
            },
        }
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        for i, task in enumerate(self._task_queue):
            if task.task_id == task_id:
                self._task_queue.pop(i)
                return True
        return False
