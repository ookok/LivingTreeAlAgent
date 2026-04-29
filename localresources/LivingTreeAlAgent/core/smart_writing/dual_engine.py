"""
智能写作双引擎核心架构
Smart Writing Dual-Engine Core Architecture

核心设计理念：
- 咨询模式 (Consulting Mode): 效率、准确、结构化
- 创作模式 (Creative Mode): 创意、流畅、表达力

三级AI协同：
- L1 即时辅助: 语法检查、错别字、基础补全 (<100ms)
- L2 深度协作: 段落重写、风格调整、逻辑优化 (1-3s)
- L3 创意伙伴: 情节发展、人物塑造、主题深化 (3-10s)
"""

import json
import time
import hashlib
from pathlib import Path
from typing import Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
import asyncio


class WritingMode(Enum):
    """写作模式枚举"""
    CONSULTING = "consulting"  # 咨询模式
    CREATIVE = "creative"       # 创作模式


class AILevel(Enum):
    """AI处理层级"""
    L1_INSTANT = "l1_instant"   # L1 即时辅助
    L2_DEEP = "l2_deep"         # L2 深度协作
    L3_CREATIVE = "l3_creative" # L3 创意伙伴


@dataclass
class WritingProfile:
    """用户写作画像"""
    user_id: str = ""
    
    # 语言风格偏好
    style_formality: float = 0.5  # 0=随意, 1=正式
    style_conciseness: float = 0.5  # 0=华丽, 1=简洁
    
    # 内容偏好
    preferred_genres: list = field(default_factory=list)  # 题材偏好
    common_topics: list = field(default_factory=list)    # 常用话题
    vocabulary_level: str = "medium"  # low/medium/high
    
    # 交互偏好
    ai_proactivity: float = 0.5  # 0=少打扰, 1=主动建议
    suggestion_frequency: float = 0.5  # 建议频率
    
    # 审美偏好
    structure_preference: str = "balanced"  # linear/balanced/creative
    rhythm_preference: str = "moderate"  # fast/moderate/flowing
    
    # 学习数据
    feedback_history: list = field(default_factory=list)
    adjustment_weights: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "user_id": self.user_id,
            "style_formality": self.style_formality,
            "style_conciseness": self.style_conciseness,
            "preferred_genres": self.preferred_genres,
            "common_topics": self.common_topics,
            "vocabulary_level": self.vocabulary_level,
            "ai_proactivity": self.ai_proactivity,
            "suggestion_frequency": self.suggestion_frequency,
            "structure_preference": self.structure_preference,
            "rhythm_preference": self.rhythm_preference,
            "feedback_history": self.feedback_history,
            "adjustment_weights": self.adjustment_weights,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "WritingProfile":
        """从字典创建"""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class WritingContext:
    """写作上下文状态"""
    # 项目上下文
    mode: WritingMode = WritingMode.CREATIVE
    project_type: str = ""  # 咨询报告/小说/诗歌/技术文档
    project_name: str = ""
    
    # 进度上下文
    position: str = "start"  # start/middle/end
    progress_percent: float = 0.0
    word_count: int = 0
    target_word_count: int = 0
    
    # 情感上下文
    emotional_tone: str = "neutral"  # tense/calm/excited/solemn
    intensity: float = 0.5  # 0-1
    
    # 时间上下文
    session_duration_minutes: int = 0
    session_start_time: Optional[float] = None
    
    # 环境上下文
    device_type: str = "desktop"
    network_status: str = "good"
    
    # 内容上下文
    current_section: str = ""
    previous_sections: list = field(default_factory=list)
    upcoming_sections: list = field(default_factory=list)
    
    def update_progress(self, word_count: int):
        """更新进度"""
        self.word_count = word_count
        if self.target_word_count > 0:
            self.progress_percent = min(word_count / self.target_word_count, 1.0)
        
        # 更新位置
        if self.progress_percent < 0.2:
            self.position = "start"
        elif self.progress_percent > 0.8:
            self.position = "end"
        else:
            self.position = "middle"
    
    def update_time(self):
        """更新时间"""
        if self.session_start_time is None:
            self.session_start_time = time.time()
        self.session_duration_minutes = int((time.time() - self.session_start_time) / 60)


@dataclass
class WritingTask:
    """写作任务"""
    task_id: str
    task_type: str  # "grammar", "polish", "rewrite", "expand", "creative"
    content: str
    context: WritingContext
    ai_level: AILevel = AILevel.L1_INSTANT
    priority: int = 0  # 0-10, 越高越优先
    timeout_ms: int = 5000
    created_at: float = field(default_factory=time.time)
    
    def __hash__(self):
        return hash(self.task_id)


@dataclass
class WritingResponse:
    """写作响应"""
    task_id: str
    success: bool
    content: str = ""
    suggestions: list = field(default_factory=list)
    confidence: float = 0.0
    processing_time_ms: float = 0.0
    ai_level_used: AILevel = AILevel.L1_INSTANT
    error: str = ""


class DualEngineCore:
    """
    双引擎核心架构
    
    负责：
    1. 双模式管理（咨询/创作）
    2. AI层级调度
    3. 用户画像管理
    4. 上下文跟踪
    """
    
    def __init__(self, agent=None):
        self.agent = agent
        
        # 模式状态
        self.current_mode: WritingMode = WritingMode.CREATIVE
        self.mode_config: dict = {}
        
        # 用户画像
        self.profile: WritingProfile = WritingProfile()
        
        # 上下文
        self.context: WritingContext = WritingContext()
        
        # AI层级配置
        self.ai_configs: dict = {
            AILevel.L1_INSTANT: {
                "model": "phi-2",  # 微型模型
                "max_tokens": 500,
                "temperature": 0.3,
                "timeout_ms": 100,
            },
            AILevel.L2_DEEP: {
                "model": "qwen2.5:7b",  # 标准模型
                "max_tokens": 2000,
                "temperature": 0.5,
                "timeout_ms": 3000,
            },
            AILevel.L3_CREATIVE: {
                "model": "qwen2.5:14b",  # 大模型
                "max_tokens": 4000,
                "temperature": 0.8,
                "timeout_ms": 10000,
            },
        }
        
        # 模式配置
        self._init_mode_configs()
        
        # 回调函数
        self.on_mode_changed: Optional[Callable] = None
        self.on_context_updated: Optional[Callable] = None
        self.on_suggestion_ready: Optional[Callable] = None
        
        # 锁
        self._lock = Lock()
        
        # 任务队列
        self._task_queue: list[WritingTask] = []
        self._processing = False
    
    def _init_mode_configs(self):
        """初始化模式配置"""
        # 咨询模式配置
        self.mode_config[WritingMode.CONSULTING] = {
            "name": "咨询模式",
            "description": "高效、结构化、专业",
            "icon": "📊",
            "primary_ai": AILevel.L2_DEEP,
            "features": [
                "结构化模板",
                "数据可视化",
                "框架生成",
                "逻辑验证",
                "术语库",
            ],
            "layout": "three_column",  # 大纲-编辑-参考
            "auto_save_interval": 30,  # 秒
            "suggestion_frequency": 0.3,  # 较低频率
        }
        
        # 创作模式配置
        self.mode_config[WritingMode.CREATIVE] = {
            "name": "创作模式",
            "description": "沉浸、创意、表达",
            "icon": "✨",
            "primary_ai": AILevel.L3_CREATIVE,
            "features": [
                "灵感引擎",
                "沉浸写作",
                "非线性支持",
                "风格模仿",
                "感官描写",
            ],
            "layout": "single_column",  # 单栏沉浸
            "auto_save_interval": 60,
            "suggestion_frequency": 0.5,
        }
    
    # ==================== 模式管理 ====================
    
    def set_mode(self, mode: WritingMode) -> bool:
        """
        切换写作模式
        
        Args:
            mode: 目标模式
            
        Returns:
            是否切换成功
        """
        if mode == self.current_mode:
            return True
        
        with self._lock:
            old_mode = self.current_mode
            self.current_mode = mode
            self.context.mode = mode
            
            # 触发回调
            if self.on_mode_changed:
                self.on_mode_changed(old_mode, mode)
            
            return True
    
    def get_mode_info(self) -> dict:
        """获取当前模式信息"""
        return {
            "current": self.current_mode,
            "config": self.mode_config.get(self.current_mode, {}),
            "available_modes": [
                {"mode": m.value, **self.mode_config[m]}
                for m in WritingMode
            ],
        }
    
    # ==================== 用户画像 ====================
    
    def update_profile(self, **kwargs):
        """更新用户画像"""
        for key, value in kwargs.items():
            if hasattr(self.profile, key):
                setattr(self.profile, key, value)
    
    def add_feedback(self, feedback_type: str, content: str, accepted: bool):
        """
        添加用户反馈
        
        Args:
            feedback_type: 反馈类型 (suggestion/revision/structure)
            content: 反馈内容
            accepted: 是否采纳
        """
        self.profile.feedback_history.append({
            "type": feedback_type,
            "content": content,
            "accepted": accepted,
            "timestamp": time.time(),
        })
        
        # 调整权重
        if not accepted:
            key = f"dismissed_{feedback_type}"
            self.profile.adjustment_weights[key] = \
                self.profile.adjustment_weights.get(key, 0.5) * 0.9
        else:
            key = f"accepted_{feedback_type}"
            self.profile.adjustment_weights[key] = \
                self.profile.adjustment_weights.get(key, 0.5) * 1.1
    
    def get_adjusted_suggestion_level(self) -> AILevel:
        """根据用户画像调整建议层级"""
        proactivity = self.profile.ai_proactivity
        
        if proactivity < 0.3:
            return AILevel.L1_INSTANT
        elif proactivity < 0.7:
            return AILevel.L2_DEEP
        else:
            return AILevel.L3_CREATIVE
    
    # ==================== 上下文管理 ====================
    
    def update_context(self, **kwargs):
        """更新上下文"""
        for key, value in kwargs.items():
            if hasattr(self.context, key):
                setattr(self.context, key, value)
        
        if self.on_context_updated:
            self.on_context_updated(self.context)
    
    def update_progress(self, word_count: int):
        """更新写作进度"""
        self.context.update_progress(word_count)
        
        # 进度感知的AI策略
        if self.context.position == "start":
            # 开头多建议
            self.profile.ai_proactivity = min(1.0, self.profile.ai_proactivity + 0.1)
        elif self.context.position == "end":
            # 结尾少打扰
            self.profile.ai_proactivity = max(0.0, self.profile.ai_proactivity - 0.2)
    
    def get_context_summary(self) -> dict:
        """获取上下文摘要"""
        return {
            "mode": self.current_mode.value,
            "position": self.context.position,
            "progress": f"{self.context.progress_percent:.1%}",
            "word_count": self.context.word_count,
            "emotional_tone": self.context.emotional_tone,
            "duration": f"{self.context.session_duration_minutes}min",
        }
    
    # ==================== AI调度 ====================
    
    def select_ai_level(self, task_type: str) -> AILevel:
        """
        根据任务类型选择AI层级
        
        Args:
            task_type: 任务类型
            
        Returns:
            推荐的AI层级
        """
        # 任务类型到AI层级的映射
        task_to_ai = {
            # L1 即时辅助
            "grammar": AILevel.L1_INSTANT,
            "spell_check": AILevel.L1_INSTANT,
            "auto_complete": AILevel.L1_INSTANT,
            "format": AILevel.L1_INSTANT,
            
            # L2 深度协作
            "polish": AILevel.L2_DEEP,
            "rewrite": AILevel.L2_DEEP,
            "expand": AILevel.L2_DEEP,
            "structure": AILevel.L2_DEEP,
            "analyze": AILevel.L2_DEEP,
            
            # L3 创意伙伴
            "creative": AILevel.L3_CREATIVE,
            "story": AILevel.L3_CREATIVE,
            "character": AILevel.L3_CREATIVE,
            "theme": AILevel.L3_CREATIVE,
            "brainstorm": AILevel.L3_CREATIVE,
        }
        
        # 根据任务类型选择
        base_level = task_to_ai.get(task_type, AILevel.L2_DEEP)
        
        # 根据模式调整
        if self.current_mode == WritingMode.CONSULTING:
            # 咨询模式倾向于使用较低层级以提高效率
            if base_level == AILevel.L3_CREATIVE:
                return AILevel.L2_DEEP
        else:
            # 创作模式可以充分发挥
            pass
        
        # 根据上下文调整
        if self.context.network_status == "poor":
            # 网络差时使用本地
            if base_level == AILevel.L3_CREATIVE:
                return AILevel.L2_DEEP
        
        return base_level
    
    def get_ai_config(self, level: AILevel) -> dict:
        """获取AI配置"""
        return self.ai_configs.get(level, self.ai_configs[AILevel.L2_DEEP])
    
    async def process_task(self, task: WritingTask) -> WritingResponse:
        """
        处理写作任务
        
        Args:
            task: 写作任务
            
        Returns:
            写作响应
        """
        start_time = time.time()
        
        # 确定AI层级
        if task.ai_level == AILevel.L1_INSTANT:
            # 如果是L1，可能使用缓存
            response = await self._process_l1(task)
        elif task.ai_level == AILevel.L2_DEEP:
            response = await self._process_l2(task)
        else:
            response = await self._process_l3(task)
        
        response.processing_time_ms = (time.time() - start_time) * 1000
        return response
    
    async def _process_l1(self, task: WritingTask) -> WritingResponse:
        """L1即时处理"""
        config = self.get_ai_config(AILevel.L1_INSTANT)
        
        # 本地处理或使用缓存
        if task.task_type == "grammar":
            result = await self._grammar_check(task.content)
        elif task.task_type == "spell_check":
            result = await self._spell_check(task.content)
        elif task.task_type == "auto_complete":
            result = await self._auto_complete(task.content)
        else:
            result = task.content  # 直接返回
        
        return WritingResponse(
            task_id=task.task_id,
            success=True,
            content=result,
            ai_level_used=AILevel.L1_INSTANT,
            confidence=0.95,
        )
    
    async def _process_l2(self, task: WritingTask) -> WritingResponse:
        """L2深度处理"""
        config = self.get_ai_config(AILevel.L2_DEEP)
        
        # 调用标准模型
        prompt = self._build_l2_prompt(task)
        result = await self._call_ai(prompt, config)
        
        return WritingResponse(
            task_id=task.task_id,
            success=True,
            content=result,
            ai_level_used=AILevel.L2_DEEP,
            confidence=0.85,
        )
    
    async def _process_l3(self, task: WritingTask) -> WritingResponse:
        """L3创意处理"""
        config = self.get_ai_config(AILevel.L3_CREATIVE)
        
        # 调用大模型
        prompt = self._build_l3_prompt(task)
        result = await self._call_ai(prompt, config)
        
        return WritingResponse(
            task_id=task.task_id,
            success=True,
            content=result,
            ai_level_used=AILevel.L3_CREATIVE,
            confidence=0.75,
        )
    
    def _build_l2_prompt(self, task: WritingTask) -> str:
        """构建L2提示"""
        mode_instruction = ""
        if self.current_mode == WritingMode.CONSULTING:
            mode_instruction = "使用专业、正式的语言风格。"
        else:
            mode_instruction = "使用流畅、富有表现力的语言风格。"
        
        return f"""{mode_instruction}

任务类型: {task.task_type}

内容:
{task.content}

请完成{self._get_task_description(task.task_type)}任务。"""
    
    def _build_l3_prompt(self, task: WritingTask) -> str:
        """构建L3提示"""
        # 包含上下文信息
        context_info = f"""
当前写作位置: {self.context.position}
项目类型: {self.context.project_type}
情感基调: {self.context.emotional_tone}
"""
        
        return f"""你是一个创意写作助手，帮助用户进行创意写作。

{context_info}

任务类型: {task.task_type}

当前内容:
{task.content}

请发挥创意，完成这个写作任务。"""
    
    def _get_task_description(self, task_type: str) -> str:
        """获取任务描述"""
        descriptions = {
            "polish": "润色",
            "rewrite": "重写",
            "expand": "扩展",
            "structure": "结构优化",
            "analyze": "分析",
        }
        return descriptions.get(task_type, task_type)
    
    async def _call_ai(self, prompt: str, config: dict) -> str:
        """调用AI"""
        if self.agent:
            try:
                # 使用agent调用AI
                response = await asyncio.wait_for(
                    self.agent.generate(prompt, **config),
                    timeout=config.get("timeout_ms", 3000) / 1000
                )
                return response
            except Exception as e:
                return f"[AI调用失败: {e}]"
        return "[AI未连接]"
    
    # ==================== 本地处理 ====================
    
    async def _grammar_check(self, text: str) -> str:
        """语法检查"""
        # 简单的本地语法检查
        # 实际应该使用语言模型
        corrections = []
        
        # 示例：检测常见错误
        if "的的" in text:
            text = text.replace("的的", "的")
            corrections.append("修正：的的 -> 的")
        
        return text
    
    async def _spell_check(self, text: str) -> str:
        """拼写检查"""
        # 简单的拼写检查
        return text
    
    async def _auto_complete(self, text: str) -> str:
        """自动补全"""
        return text
    
    # ==================== 建议系统 ====================
    
    def should_offer_suggestion(self) -> bool:
        """判断是否应该提供建议"""
        frequency = self.mode_config.get(
            self.current_mode, {}
        ).get("suggestion_frequency", 0.5)
        
        return self.profile.ai_proactivity >= frequency
    
    def get_suggestion_timing(self) -> str:
        """获取建议时机"""
        if self.context.position == "start":
            return "aggressive"  # 开头积极建议
        elif self.context.position == "end":
            return "minimal"  # 结尾最小打扰
        else:
            return "moderate"  # 中间适度建议
    
    # ==================== 状态保存/加载 ====================
    
    def save_state(self, path: str):
        """保存状态"""
        state = {
            "current_mode": self.current_mode.value,
            "profile": self.profile.to_dict(),
            "ai_configs": {
                k.value: v for k, v in self.ai_configs.items()
            },
        }
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    
    def load_state(self, path: str):
        """加载状态"""
        if not Path(path).exists():
            return
        
        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)
        
        if "current_mode" in state:
            self.current_mode = WritingMode(state["current_mode"])
        
        if "profile" in state:
            self.profile = WritingProfile.from_dict(state["profile"])


# 单例
_dual_engine: Optional[DualEngineCore] = None


def get_dual_engine(agent=None) -> DualEngineCore:
    """获取双引擎核心单例"""
    global _dual_engine
    if _dual_engine is None:
        _dual_engine = DualEngineCore(agent)
    return _dual_engine
