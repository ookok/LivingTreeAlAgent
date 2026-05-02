"""
统一优化器服务

整合 EntralyOptimizer 和 TokenOptimizer 的功能：
1. 代码上下文优化 - PRISM过滤 + 背包选择
2. Token压缩 - 语义压缩 + 冗余去除
3. 实时监控 - 成本仪表盘

优先级策略：
- 代码片段优化 → 使用 EntralyOptimizer（PRISM + 背包）
- 文本/prompt优化 → 使用 TokenOptimizer（语义压缩）
- 实时监控 → 使用 EntralyOptimizer 的仪表盘
"""

import time
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum

# 导入 EntralyOptimizer 组件
from .entroly_optimizer import (
    EntralyOptimizer,
    OptimizationConfig as EntralyConfig,
    OptimizationResult as EntralyResult,
    get_entroly_optimizer,
)

# 导入 TokenOptimizer 组件
from ..token_optimizer import (
    TokenOptimizer,
    OptimizationLevel,
    OptimizationStrategy,
    OptimizationResult as TokenResult,
    get_token_optimizer,
)


class OptimizerType(Enum):
    """优化器类型"""
    AUTO = "auto"                     # 自动选择
    ENTRALY = "entroly"               # Entraly优化器（上下文优化）
    TOKEN = "token"                   # Token优化器（文本压缩）
    HYBRID = "hybrid"                 # 混合模式（两者结合）


class TaskType(Enum):
    """任务类型"""
    GENERAL = "general"               # 通用任务
    CODE_ANALYSIS = "code_analysis"   # 代码分析
    CODE_COMPLETION = "code_completion" # 代码补全
    DOC_SUMMARIZATION = "doc_summarization" # 文档摘要
    CHAT = "chat"                     # 聊天对话
    SEARCH = "search"                 # 搜索查询


@dataclass
class UnifiedOptimizationResult:
    """统一优化结果"""
    optimized_text: Optional[str] = None
    original_fragments: Optional[List[Any]] = None
    selected_fragments: Optional[List[Any]] = None
    original_tokens: int = 0
    optimized_tokens: int = 0
    compression_ratio: float = 0.0
    token_reduction_percent: float = 0.0
    importance_scores: Dict[str, float] = field(default_factory=dict)
    processing_time_ms: float = 0.0
    cost_savings: float = 0.0
    optimizer_used: str = ""
    strategy: str = ""


@dataclass
class UnifiedConfig:
    """统一配置"""
    max_tokens: int = 4000
    optimization_level: OptimizationLevel = OptimizationLevel.BALANCED
    optimizer_type: OptimizerType = OptimizerType.AUTO
    task_type: TaskType = TaskType.GENERAL
    enable_prism: bool = True
    enable_knapsack: bool = True
    enable_dashboard: bool = True
    noise_filter_ratio: float = 0.8


class UnifiedOptimizer:
    """
    统一优化器 - 整合 EntralyOptimizer 和 TokenOptimizer
    
    核心能力：
    1. 智能路由 - 根据任务类型自动选择最优优化器
    2. 代码上下文优化 - PRISM过滤 + 背包选择
    3. Token压缩 - 语义压缩 + 冗余去除
    4. 实时监控 - 成本仪表盘
    5. 混合模式 - 结合两者优势
    """

    def __init__(self, config: Optional[UnifiedConfig] = None):
        """初始化统一优化器"""
        self.config = config or UnifiedConfig()
        
        # 初始化两个优化器
        self.entroly_optimizer = get_entroly_optimizer(
            EntralyConfig(
                max_tokens=self.config.max_tokens,
                noise_filter_ratio=self.config.noise_filter_ratio,
                enable_prism=self.config.enable_prism,
                enable_knapsack=self.config.enable_knapsack,
                enable_dashboard=self.config.enable_dashboard,
                task_type=self.config.task_type.value
            )
        )
        self.token_optimizer = get_token_optimizer()
        
        # 会话管理
        self.session_id = None
        self._stats = {
            "total_optimizations": 0,
            "total_tokens_saved": 0,
            "total_cost_saved": 0.0,
            "avg_processing_time_ms": 0.0,
        }

    def start_session(self) -> str:
        """开始优化会话"""
        self.session_id = self.entroly_optimizer.start_session()
        return self.session_id

    def end_session(self):
        """结束优化会话"""
        self.entroly_optimizer.end_session()

    def _select_optimizer(self, task_type: TaskType) -> OptimizerType:
        """根据任务类型选择优化器"""
        if self.config.optimizer_type != OptimizerType.AUTO:
            return self.config.optimizer_type
        
        # 根据任务类型自动选择
        code_tasks = {TaskType.CODE_ANALYSIS, TaskType.CODE_COMPLETION}
        text_tasks = {TaskType.DOC_SUMMARIZATION, TaskType.CHAT}
        
        if task_type in code_tasks:
            return OptimizerType.ENTRALY
        elif task_type in text_tasks:
            return OptimizerType.TOKEN
        else:
            return OptimizerType.HYBRID

    def optimize(self, 
                 content: Union[str, List[Tuple[str, str, int]]],
                 query: Optional[str] = None,
                 task_type: Optional[TaskType] = None,
                 max_tokens: Optional[int] = None) -> UnifiedOptimizationResult:
        """
        统一优化入口
        
        Args:
            content: 待优化内容（字符串或代码片段列表）
            query: 用户查询（用于上下文相关性分析）
            task_type: 任务类型
            max_tokens: 最大token数
        
        Returns:
            UnifiedOptimizationResult: 优化结果
        """
        start_time = time.time()
        
        task = task_type or self.config.task_type
        optimizer_type = self._select_optimizer(task)
        max_tok = max_tokens or self.config.max_tokens
        
        result = UnifiedOptimizationResult()
        result.optimizer_used = optimizer_type.value
        
        # 根据内容类型和优化器类型选择策略
        if isinstance(content, list) and optimizer_type in [OptimizerType.ENTRALY, OptimizerType.HYBRID]:
            # 代码片段列表 → 使用 EntralyOptimizer
            result = self._optimize_with_entroly(content, query, max_tok)
        elif isinstance(content, str) and optimizer_type in [OptimizerType.TOKEN, OptimizerType.HYBRID]:
            # 文本字符串 → 使用 TokenOptimizer
            result = self._optimize_with_token(content, max_tok)
        elif isinstance(content, str):
            # 文本但需要代码优化 → 转换为片段
            fragments = [(content, "text.txt", len(content))]
            result = self._optimize_with_entroly(fragments, query, max_tok)
        else:
            # 默认使用 TokenOptimizer
            text_content = str(content) if not isinstance(content, str) else content
            result = self._optimize_with_token(text_content, max_tok)
        
        # 混合模式：先上下文优化，再Token压缩
        if optimizer_type == OptimizerType.HYBRID and result.optimized_text:
            token_result = self.token_optimizer.optimize(
                result.optimized_text,
                max_tokens=max_tok,
                level=self.config.optimization_level
            )
            result.optimized_text = token_result.optimized_text
            result.optimized_tokens = token_result.optimized_tokens
            result.compression_ratio = token_result.compression_ratio
            result.strategy = "hybrid"
        
        result.processing_time_ms = (time.time() - start_time) * 1000
        
        # 更新统计
        self._update_stats(result)
        
        return result

    def _optimize_with_entroly(self, 
                              fragments: List[Tuple[str, str, int]],
                              query: Optional[str],
                              max_tokens: int) -> UnifiedOptimizationResult:
        """使用 EntralyOptimizer 优化"""
        try:
            entraly_result = self.entroly_optimizer.optimize_context(
                query=query or "",
                fragments=fragments,
                model="gpt-4o"
            )
            
            # 构建优化后的文本
            optimized_text = "\n\n".join(
                f"// {fragment.file_path}\n{fragment.content}"
                for fragment in entraly_result.selected_fragments
            )
            
            return UnifiedOptimizationResult(
                optimized_text=optimized_text,
                original_fragments=entraly_result.original_fragments,
                selected_fragments=entraly_result.selected_fragments,
                original_tokens=entraly_result.total_original_tokens,
                optimized_tokens=entraly_result.total_selected_tokens,
                token_reduction_percent=entraly_result.token_reduction_percent,
                importance_scores=entraly_result.importance_scores,
                cost_savings=entraly_result.cost_savings,
                optimizer_used="entroly",
                strategy="prism+knapsack"
            )
        except Exception:
            # 降级到简单处理
            text = "\n\n".join(f[0] for f in fragments)
            return UnifiedOptimizationResult(
                optimized_text=text,
                original_tokens=len(text),
                optimized_tokens=len(text),
                optimizer_used="entroly_fallback",
                strategy="passthrough"
            )

    def _optimize_with_token(self, text: str, max_tokens: int) -> UnifiedOptimizationResult:
        """使用 TokenOptimizer 优化"""
        try:
            token_result = self.token_optimizer.optimize(
                text,
                max_tokens=max_tokens,
                level=self.config.optimization_level
            )
            
            return UnifiedOptimizationResult(
                optimized_text=token_result.optimized_text,
                original_tokens=token_result.original_tokens,
                optimized_tokens=token_result.optimized_tokens,
                compression_ratio=token_result.compression_ratio,
                optimizer_used="token",
                strategy=token_result.strategy.value
            )
        except Exception:
            return UnifiedOptimizationResult(
                optimized_text=text,
                original_tokens=len(text),
                optimized_tokens=len(text),
                optimizer_used="token_fallback",
                strategy="passthrough"
            )

    def optimize_code_context(self, 
                             query: str,
                             code_fragments: List[Tuple[str, str, int]],
                             max_tokens: int = 4000) -> UnifiedOptimizationResult:
        """
        优化代码上下文（专为代码分析场景设计）
        
        Args:
            query: 用户查询
            code_fragments: 代码片段列表 [(content, file_path, token_count), ...]
            max_tokens: 最大token数
        
        Returns:
            UnifiedOptimizationResult: 优化结果
        """
        return self.optimize(
            content=code_fragments,
            query=query,
            task_type=TaskType.CODE_ANALYSIS,
            max_tokens=max_tokens
        )

    def optimize_prompt(self, 
                        prompt: str,
                        max_tokens: int = 4000,
                        level: Optional[OptimizationLevel] = None) -> UnifiedOptimizationResult:
        """
        优化 Prompt 文本
        
        Args:
            prompt: 待优化的prompt文本
            max_tokens: 最大token数
            level: 优化级别
        
        Returns:
            UnifiedOptimizationResult: 优化结果
        """
        original_level = self.config.optimization_level
        if level:
            self.config.optimization_level = level
        
        try:
            return self.optimize(
                content=prompt,
                task_type=TaskType.CHAT,
                max_tokens=max_tokens
            )
        finally:
            self.config.optimization_level = original_level

    def optimize_document(self, 
                         document: str,
                         max_tokens: int = 4000) -> UnifiedOptimizationResult:
        """
        优化文档摘要
        
        Args:
            document: 文档内容
            max_tokens: 最大token数
        
        Returns:
            UnifiedOptimizationResult: 优化结果
        """
        return self.optimize(
            content=document,
            task_type=TaskType.DOC_SUMMARIZATION,
            max_tokens=max_tokens
        )

    def _update_stats(self, result: UnifiedOptimizationResult):
        """更新统计信息"""
        self._stats["total_optimizations"] += 1
        tokens_saved = result.original_tokens - result.optimized_tokens
        self._stats["total_tokens_saved"] += max(0, tokens_saved)
        self._stats["total_cost_saved"] += result.cost_savings
        
        # 更新平均处理时间
        avg_time = self._stats["avg_processing_time_ms"]
        count = self._stats["total_optimizations"]
        self._stats["avg_processing_time_ms"] = (avg_time * (count - 1) + result.processing_time_ms) / count

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self._stats.copy()

    def reset_stats(self):
        """重置统计信息"""
        self._stats = {
            "total_optimizations": 0,
            "total_tokens_saved": 0,
            "total_cost_saved": 0.0,
            "avg_processing_time_ms": 0.0,
        }

    def visualize_result(self, result: UnifiedOptimizationResult) -> str:
        """可视化优化结果"""
        lines = [
            "=" * 60,
            "优化结果报告",
            "=" * 60,
            f"使用优化器: {result.optimizer_used}",
            f"优化策略: {result.strategy}",
            f"原始Token: {result.original_tokens}",
            f"优化后Token: {result.optimized_tokens}",
            f"Token减少: {result.token_reduction_percent:.1f}%" if result.token_reduction_percent else f"压缩率: {result.compression_ratio:.2f}",
            f"处理时间: {result.processing_time_ms:.2f}ms",
            f"成本节省: ${result.cost_savings:.4f}",
            "=" * 60,
        ]
        return "\n".join(lines)


# 全局实例
_global_unified_optimizer: Optional[UnifiedOptimizer] = None


def get_unified_optimizer(config: Optional[UnifiedConfig] = None) -> UnifiedOptimizer:
    """获取统一优化器实例"""
    global _global_unified_optimizer
    if _global_unified_optimizer is None:
        _global_unified_optimizer = UnifiedOptimizer(config)
    return _global_unified_optimizer