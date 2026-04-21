"""
0/1 背包上下文选择器

实现 Entroly 的 0/1 背包动态规划算法
把关键代码信息压缩到最小 token 容量
"""

import math
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class ContextItem:
    """上下文项（相当于背包问题中的物品）"""
    item_id: str
    content: str
    token_count: int
    importance: float          # 重要性 (0-1)
    semantic_value: float     # 语义价值 (0-1)
    dependency_ids: List[str] = field(default_factory=list)  # 依赖项


@dataclass
class SelectionResult:
    """选择结果"""
    selected_items: List[ContextItem]
    total_tokens: int
    total_importance: float
    total_semantic_value: float
    excluded_items: List[ContextItem]
    efficiency: float  # 效率 = 价值 / token


class KnapsackContextSelector:
    """
    0/1 背包上下文选择器

    使用动态规划算法，将关键代码信息压缩到最小 token 容量
    保证 AI 获取足够的核心信息，同时减少 token 消耗
    """

    def __init__(self, max_tokens: int = 4000):
        """
        初始化选择器

        Args:
            max_tokens: 最大 token 容量
        """
        self.max_tokens = max_tokens
        self.items: Dict[str, ContextItem] = {}
        self._dp_cache: Dict[Tuple[int, int], float] = {}

    def add_item(
        self,
        item_id: str,
        content: str,
        token_count: int,
        importance: float = 0.5,
        semantic_value: float = 0.5,
        dependency_ids: Optional[List[str]] = None
    ) -> bool:
        """
        添加上下文项

        Args:
            item_id: 项 ID
            content: 内容
            token_count: token 数量
            importance: 重要性 (0-1)
            semantic_value: 语义价值 (0-1)
            dependency_ids: 依赖项 ID 列表

        Returns:
            bool: 是否成功
        """
        if item_id in self.items:
            return False

        # 验证数值范围
        importance = max(0.0, min(1.0, importance))
        semantic_value = max(0.0, min(1.0, semantic_value))

        item = ContextItem(
            item_id=item_id,
            content=content,
            token_count=token_count,
            importance=importance,
            semantic_value=semantic_value,
            dependency_ids=dependency_ids or []
        )

        self.items[item_id] = item
        self._dp_cache.clear()  # 清空缓存
        return True

    def remove_item(self, item_id: str) -> bool:
        """移除上下文项"""
        if item_id not in self.items:
            return False

        del self.items[item_id]
        self._dp_cache.clear()
        return True

    def _calculate_value(self, item: ContextItem) -> float:
        """
        计算项的价值

        价值 = 重要性 * 0.6 + 语义价值 * 0.4
        """
        return item.importance * 0.6 + item.semantic_value * 0.4

    def _resolve_dependencies(self, selected_ids: set) -> set:
        """
        解析依赖，确保被选中的项的依赖项也被选中

        Args:
            selected_ids: 已选中的 ID 集合

        Returns:
            set: 包含依赖的完整 ID 集合
        """
        resolved = set(selected_ids)
        changed = True

        # 迭代解析，直到没有新添加
        while changed:
            changed = False
            for item_id in list(resolved):
                item = self.items.get(item_id)
                if not item:
                    continue

                for dep_id in item.dependency_ids:
                    if dep_id not in resolved and dep_id in self.items:
                        resolved.add(dep_id)
                        changed = True

        return resolved

    def _dp_select(
        self,
        item_ids: List[str],
        current_index: int,
        remaining_tokens: int
    ) -> float:
        """
        动态规划选择

        使用记忆化递归实现 0/1 背包

        Args:
            item_ids: 物品 ID 列表
            current_index: 当前索引
            remaining_tokens: 剩余 token 容量

        Returns:
            float: 最大价值
        """
        # 缓存命中
        cache_key = (current_index, remaining_tokens)
        if cache_key in self._dp_cache:
            return self._dp_cache[cache_key]

        # 基准情况：没有物品或没有容量
        if current_index >= len(item_ids) or remaining_tokens <= 0:
            return 0.0

        item = self.items.get(item_ids[current_index])
        if not item:
            return self._dp_select(item_ids, current_index + 1, remaining_tokens)

        # 不选择当前物品
        value_without = self._dp_select(item_ids, current_index + 1, remaining_tokens)

        # 选择当前物品（如果容量足够）
        value_with = 0.0
        if item.token_count <= remaining_tokens:
            value = self._calculate_value(item)
            value_with = value + self._dp_select(
                item_ids,
                current_index + 1,
                remaining_tokens - item.token_count
            )

        # 取较大值
        result = max(value_without, value_with)
        self._dp_cache[cache_key] = result

        return result

    def select(self, resolve_dependencies: bool = True) -> SelectionResult:
        """
        执行选择算法

        Args:
            resolve_dependencies: 是否解析依赖

        Returns:
            SelectionResult: 选择结果
        """
        if not self.items:
            return SelectionResult(
                selected_items=[],
                total_tokens=0,
                total_importance=0.0,
                total_semantic_value=0.0,
                excluded_items=[],
                efficiency=0.0
            )

        # 获取所有物品 ID
        item_ids = list(self.items.keys())

        # 使用动态规划找出最优选择
        self._dp_cache.clear()
        max_value = self._dp_select(item_ids, 0, self.max_tokens)

        # 回溯找出具体选择了哪些物品
        selected_ids = self._backtrack_select(item_ids, 0, self.max_tokens)

        # 解析依赖
        if resolve_dependencies:
            selected_ids = self._resolve_dependencies(selected_ids)

        # 计算结果
        selected_items = []
        excluded_items = []
        total_tokens = 0
        total_importance = 0.0
        total_semantic_value = 0.0

        for item_id, item in self.items.items():
            if item_id in selected_ids:
                selected_items.append(item)
                total_tokens += item.token_count
                total_importance += item.importance
                total_semantic_value += item.semantic_value
            else:
                excluded_items.append(item)

        # 计算效率
        efficiency = max_value / self.max_tokens if self.max_tokens > 0 else 0.0

        return SelectionResult(
            selected_items=selected_items,
            total_tokens=total_tokens,
            total_importance=total_importance,
            total_semantic_value=total_semantic_value,
            excluded_items=excluded_items,
            efficiency=efficiency
        )

    def _backtrack_select(
        self,
        item_ids: List[str],
        current_index: int,
        remaining_tokens: int
    ) -> set:
        """
        回溯选择具体的物品

        Args:
            item_ids: 物品 ID 列表
            current_index: 当前索引
            remaining_tokens: 剩余容量

        Returns:
            set: 选中的物品 ID 集合
        """
        selected = set()

        i = current_index
        tokens = remaining_tokens

        while i < len(item_ids):
            item = self.items.get(item_ids[i])
            if not item:
                i += 1
                continue

            # 检查选择这个物品是否能获得最优值
            value_with = 0.0
            if item.token_count <= tokens:
                value_with = self._calculate_value(item)
                remaining = tokens - item.token_count

                # 递归计算后续最优值
                remaining_value = 0.0
                for j in range(i + 1, len(item_ids)):
                    sub_item = self.items.get(item_ids[j])
                    if sub_item and sub_item.token_count <= remaining:
                        remaining_value += self._calculate_value(sub_item)
                        remaining -= sub_item.token_count
                        if remaining <= 0:
                            break

                value_with += remaining_value

            # 不选择这个物品的后续最优值
            value_without = 0.0
            remaining_without = tokens
            for j in range(i + 1, len(item_ids)):
                sub_item = self.items.get(item_ids[j])
                if sub_item and sub_item.token_count <= remaining_without:
                    remaining_without -= sub_item.token_count
                    value_without += self._calculate_value(sub_item)

            # 选择价值更大的方案
            if value_with >= value_without and item.token_count <= tokens:
                selected.add(item.item_id)
                tokens -= item.token_count

            i += 1

        return selected

    def get_optimal_subset(self, target_value: float) -> List[str]:
        """
        获取达到目标价值的最小物品子集

        Args:
            target_value: 目标价值

        Returns:
            List[str]: 物品 ID 列表
        """
        result = self.select()
        selected_ids = set()

        # 迭代添加物品直到达到目标价值
        current_value = 0.0
        sorted_items = sorted(
            self.items.values(),
            key=lambda x: self._calculate_value(x) / x.token_count if x.token_count > 0 else 0,
            reverse=True
        )

        for item in sorted_items:
            if current_value >= target_value:
                break

            if item.token_count <= self.max_tokens:
                selected_ids.add(item.item_id)
                current_value += self._calculate_value(item)

        return list(selected_ids)

    def visualize_selection(self, result: SelectionResult) -> str:
        """
        可视化选择结果

        Args:
            result: 选择结果

        Returns:
            str: 可视化字符串
        """
        lines = ["=" * 60]
        lines.append("0/1 背包上下文选择结果")
        lines.append("=" * 60)
        lines.append(f"最大容量: {self.max_tokens} tokens")
        lines.append(f"总物品数: {len(self.items)}")
        lines.append("")
        lines.append(f"选中物品数: {len(result.selected_items)}")
        lines.append(f"总 token 数: {result.total_tokens}")
        lines.append(f"总重要性: {result.total_importance:.2f}")
        lines.append(f"总语义价值: {result.total_semantic_value:.2f}")
        lines.append(f"效率: {result.efficiency:.4f}")
        lines.append("")

        if result.selected_items:
            lines.append("选中的物品:")
            for item in result.selected_items:
                value = self._calculate_value(item)
                lines.append(f"  - {item.item_id}: {item.token_count} tokens, 价值={value:.2f}")

        if result.excluded_items:
            lines.append("")
            lines.append("排除的物品:")
            for item in result.excluded_items[:5]:  # 最多显示5个
                lines.append(f"  - {item.item_id}: {item.token_count} tokens")

        lines.append("=" * 60)
        return "\n".join(lines)


class AdaptiveContextSelector:
    """
    自适应上下文选择器

    根据任务类型动态调整选择策略
    """

    def __init__(self, base_max_tokens: int = 4000):
        """初始化自适应选择器"""
        self.base_max_tokens = base_max_tokens
        self.knapsack_selector = KnapsackContextSelector(base_max_tokens)

        # 任务类型对应的 token 预算比例
        self.task_token_ratios = {
            "code_generation": 0.8,      # 代码生成需要更多上下文
            "code_review": 0.6,           # 代码审查中等
            "debugging": 0.7,             # 调试需要较多上下文
            "refactoring": 0.6,          # 重构中等
            "general": 0.4                # 通用任务较少
        }

    def select_for_task(
        self,
        task_type: str,
        context_items: List[ContextItem]
    ) -> SelectionResult:
        """
        根据任务类型选择上下文

        Args:
            task_type: 任务类型
            context_items: 上下文项列表

        Returns:
            SelectionResult: 选择结果
        """
        # 获取任务对应的 token 预算
        ratio = self.task_token_ratios.get(task_type, 0.5)
        max_tokens = int(self.base_max_tokens * ratio)

        # 创建临时选择器
        selector = KnapsackContextSelector(max_tokens)
        for item in context_items:
            selector.add_item(
                item_id=item.item_id,
                content=item.content,
                token_count=item.token_count,
                importance=item.importance,
                semantic_value=item.semantic_value,
                dependency_ids=item.dependency_ids
            )

        return selector.select()

    def optimize_for_cost(
        self,
        context_items: List[ContextItem],
        budget_tokens: int
    ) -> SelectionResult:
        """
        根据成本预算优化选择

        Args:
            context_items: 上下文项列表
            budget_tokens: token 预算

        Returns:
            SelectionResult: 选择结果
        """
        selector = KnapsackContextSelector(budget_tokens)
        for item in context_items:
            selector.add_item(
                item_id=item.item_id,
                content=item.content,
                token_count=item.token_count,
                importance=item.importance,
                semantic_value=item.semantic_value,
                dependency_ids=item.dependency_ids
            )

        return selector.select()


# 全局实例
_global_selector: Optional[KnapsackContextSelector] = None


def get_knapsack_selector(max_tokens: int = 4000) -> KnapsackContextSelector:
    """获取背包选择器"""
    global _global_selector
    if _global_selector is None:
        _global_selector = KnapsackContextSelector(max_tokens)
    return _global_selector


def get_adaptive_selector(base_max_tokens: int = 4000) -> AdaptiveContextSelector:
    """获取自适应选择器"""
    return AdaptiveContextSelector(base_max_tokens)
