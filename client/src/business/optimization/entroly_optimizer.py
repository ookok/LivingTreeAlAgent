"""
Entroly 风格优化管理器

集成 PRISM 优化器、0/1 背包选择器和实时监控仪表盘
提供端到端的代码上下文优化解决方案
"""

import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

from .prism_optimizer import (
    PRISMOptimizer,
    PRISMConfig,
    FragmentManager,
    CodeFragment,
    FragmentMetrics,
    get_prism_optimizer,
)
from .knapsack_selector import (
    KnapsackContextSelector,
    AdaptiveContextSelector,
    ContextItem,
    SelectionResult,
    get_knapsack_selector,
    get_adaptive_selector,
)
from .realtime_dashboard import (
    RealtimeDashboard,
    MetricType,
    get_dashboard,
)


@dataclass
class OptimizationConfig:
    """优化配置"""
    max_tokens: int = 4000           # 最大 token 数
    noise_filter_ratio: float = 0.8  # 噪音过滤比例
    enable_prism: bool = True         # 启用 PRISM
    enable_knapsack: bool = True      # 启用背包选择
    enable_dashboard: bool = True      # 启用仪表盘
    task_type: str = "general"       # 任务类型


@dataclass
class OptimizationResult:
    """优化结果"""
    original_fragments: List[CodeFragment]
    selected_fragments: List[CodeFragment]
    total_original_tokens: int
    total_selected_tokens: int
    token_reduction_percent: float
    importance_scores: Dict[str, float]
    processing_time_ms: float
    cost_savings: float


class EntralyOptimizer:
    """
    Entraly 风格优化器

    整合三大核心技术：
    1. PRISM 优化器 - 过滤噪音
    2. 0/1 背包选择 - 压缩上下文
    3. 实时仪表盘 - 监控成本
    """

    def __init__(self, config: Optional[OptimizationConfig] = None):
        """初始化优化器"""
        self.config = config or OptimizationConfig()

        # 初始化组件
        self.prism = get_prism_optimizer()
        self.knapsack = get_knapsack_selector(self.config.max_tokens)
        self.adaptive_selector = get_adaptive_selector(self.config.max_tokens)
        self.dashboard = get_dashboard() if self.config.enable_dashboard else None

        # 片段管理器
        self.fragment_manager = FragmentManager(self.prism)

        # 会话
        self.session_id = None

    def start_session(self) -> str:
        """开始会话"""
        if self.dashboard:
            self.session_id = self.dashboard.start_session()
        return self.session_id or "local_session"

    def end_session(self):
        """结束会话"""
        if self.dashboard:
            self.dashboard.end_session(self.session_id)

    def optimize_context(
        self,
        query: str,
        fragments: List[Tuple[str, str, int]],
        model: str = "gpt-4o"
    ) -> OptimizationResult:
        """
        优化上下文

        Args:
            query: 查询字符串
            fragments: 代码片段列表 [(content, file_path, token_count), ...]
            model: 模型名称

        Returns:
            OptimizationResult: 优化结果
        """
        start_time = time.time()

        # 1. PRISM 过滤
        if self.config.enable_prism:
            filtered = self._prism_filter(query, fragments)
        else:
            filtered = [(f[0], f[1], 1.0) for f in fragments]  # 不过滤

        # 2. 背包选择
        if self.config.enable_knapsack:
            selected = self._knapsack_select(filtered)
        else:
            selected = filtered  # 全选

        # 3. 计算结果
        result = self._build_result(
            fragments,
            selected,
            start_time,
            model
        )

        # 4. 记录仪表盘
        if self.dashboard and result.token_reduction_percent > 0:
            self.dashboard.record_optimization(
                original_tokens=result.total_original_tokens,
                optimized_tokens=result.total_selected_tokens,
                model=model,
                session_id=self.session_id
            )

        return result

    def _prism_filter(
        self,
        query: str,
        fragments: List[Tuple[str, str, int]]
    ) -> List[Tuple[str, str, float]]:
        """
        PRISM 过滤

        Args:
            query: 查询
            fragments: [(content, file_path, token_count), ...]

        Returns:
            List[Tuple[content, file_path, importance_score]]: 过滤后的片段
        """
        # 添加片段到 PRISM
        for i, (content, file_path, _) in enumerate(fragments):
            fragment_id = f"frag_{i}"
            self.fragment_manager.add_fragment(
                content=content,
                file_path=file_path,
                language="python",  # 简化处理
                start_line=0,
                end_line=0
            )

        # 过滤噪音
        filtered_ids = self.prism.filter_noise(query)

        # 构建结果
        filtered = []
        for i, (content, file_path, token_count) in enumerate(fragments):
            fragment_id = f"frag_{i}"
            score = 0.0
            for fid, s in filtered_ids:
                if fid == fragment_id:
                    score = s
                    break
            if score > 0:
                filtered.append((content, file_path, score))

        return filtered

    def _knapsack_select(
        self,
        fragments: List[Tuple[str, str, float]]
    ) -> List[Tuple[str, str, float]]:
        """
        0/1 背包选择

        Args:
            fragments: [(content, file_path, importance_score), ...]

        Returns:
            List[Tuple[content, file_path, importance_score]]: 选中的片段
        """
        # 清空选择器
        self.knapsack = KnapsackContextSelector(self.config.max_tokens)

        # 添加项
        for i, (content, file_path, importance) in enumerate(fragments):
            token_count = len(content.split())  # 简化估算
            item_id = f"item_{i}"

            self.knapsack.add_item(
                item_id=item_id,
                content=content,
                token_count=token_count,
                importance=importance,
                semantic_value=importance
            )

        # 执行选择
        result = self.knapsack.select()

        # 构建选中列表
        selected = []
        for item in result.selected_items:
            idx = int(item.item_id.split("_")[1])
            if idx < len(fragments):
                selected.append(fragments[idx])

        return selected

    def _build_result(
        self,
        original: List[Tuple[str, str, int]],
        selected: List[Tuple[str, str, float]],
        start_time: float,
        model: str
    ) -> OptimizationResult:
        """构建优化结果"""
        # 原始 token 数
        total_original = sum(f[2] for f in original)

        # 选中片段的 token 数
        total_selected = sum(len(f[0].split()) for f in selected)

        # 计算压缩比
        if total_original > 0:
            reduction = (total_original - total_selected) / total_original * 100
        else:
            reduction = 0.0

        # 构建片段对象
        original_fragments = []
        for content, file_path, token_count in original:
            frag = CodeFragment(
                fragment_id=f"frag_{len(original_fragments)}",
                content=content,
                file_path=file_path,
                language="python",
                start_line=0,
                end_line=0,
                hash="",
                created_at=time.time(),
                updated_at=time.time()
            )
            original_fragments.append(frag)

        selected_fragments = []
        for content, file_path, score in selected:
            frag = CodeFragment(
                fragment_id=f"frag_{len(selected_fragments)}",
                content=content,
                file_path=file_path,
                language="python",
                start_line=0,
                end_line=0,
                hash="",
                created_at=time.time(),
                updated_at=time.time()
            )
            selected_fragments.append(frag)

        # 重要性分数
        scores = {f"frag_{i}": s for i, (_, _, s) in enumerate(selected)}

        # 计算节省
        from .realtime_dashboard import CostCalculator
        cost_savings = CostCalculator.calculate_savings(
            total_original, total_selected, model
        )

        return OptimizationResult(
            original_fragments=original_fragments,
            selected_fragments=selected_fragments,
            total_original_tokens=total_original,
            total_selected_tokens=total_selected,
            token_reduction_percent=reduction,
            importance_scores=scores,
            processing_time_ms=(time.time() - start_time) * 1000,
            cost_savings=cost_savings
        )

    def get_dashboard_data(self) -> Dict[str, Any]:
        """获取仪表盘数据"""
        if self.dashboard:
            return self.dashboard.get_dashboard_data()
        return {}

    def visualize_result(self, result: OptimizationResult) -> str:
        """可视化优化结果"""
        lines = ["=" * 60]
        lines.append("Entroly 风格优化结果")
        lines.append("=" * 60)
        lines.append(f"原始片段数: {len(result.original_fragments)}")
        lines.append(f"选中片段数: {len(result.selected_fragments)}")
        lines.append(f"原始 Token: {result.total_original_tokens}")
        lines.append(f"选中 Token: {result.total_selected_tokens}")
        lines.append(f"Token 减少: {result.token_reduction_percent:.1f}%")
        lines.append(f"处理时间: {result.processing_time_ms:.2f} ms")
        lines.append(f"成本节省: ${result.cost_savings:.6f}")
        lines.append("=" * 60)
        return "\n".join(lines)


# 全局实例
_global_optimizer: Optional[EntralyOptimizer] = None


def get_entroly_optimizer(config: Optional[OptimizationConfig] = None) -> EntralyOptimizer:
    """获取 Entraly 优化器"""
    global _global_optimizer
    if _global_optimizer is None:
        _global_optimizer = EntralyOptimizer(config)
    return _global_optimizer
