"""
令牌优化器
Token Optimizer

用于优化记忆检索的令牌使用效率
"""

import re
from typing import List, Dict, Any


class TokenCounter:
    """令牌计数器"""

    @staticmethod
    def count_tokens(text: str) -> int:
        """
        估算文本的令牌数
        基于规则的简单估算
        """
        if not text:
            return 0

        # 英文单词和数字
        words = re.findall(r'[A-Za-z0-9]+', text)
        word_tokens = len(words)

        # 中文汉字
        chinese_chars = re.findall(r'[\u4e00-\u9fa5]', text)
        chinese_tokens = len(chinese_chars)

        # 标点符号和其他字符
        other_chars = len(re.findall(r'[^A-Za-z0-9\u4e00-\u9fa5\s]', text))

        # 空格和换行
        whitespace = len(re.findall(r'\s+', text))

        # 总令牌数估算
        total_tokens = word_tokens + chinese_tokens + other_chars + whitespace // 2

        return max(1, total_tokens)

    @staticmethod
    def count_batch_tokens(texts: List[str]) -> List[int]:
        """
        批量估算令牌数
        """
        return [TokenCounter.count_tokens(text) for text in texts]


class TokenBudgetManager:
    """令牌预算管理器"""

    def __init__(self, max_tokens: int):
        self.max_tokens = max_tokens
        self.used_tokens = 0
        self.remaining_tokens = max_tokens

    def allocate(self, tokens: int) -> bool:
        """
        分配令牌
        返回是否成功
        """
        if tokens <= self.remaining_tokens:
            self.used_tokens += tokens
            self.remaining_tokens -= tokens
            return True
        return False

    def reset(self):
        """
        重置预算
        """
        self.used_tokens = 0
        self.remaining_tokens = self.max_tokens

    def get_status(self) -> Dict[str, int]:
        """
        获取预算状态
        """
        return {
            "max_tokens": self.max_tokens,
            "used_tokens": self.used_tokens,
            "remaining_tokens": self.remaining_tokens
        }


class ProgressiveRetrievalOptimizer:
    """渐进式检索优化器"""

    def __init__(self, max_tokens: int = 2000):
        self.max_tokens = max_tokens
        self.token_counter = TokenCounter()

    def optimize_retrieval(
        self,
        memory_items: List[Any],
        query: str
    ) -> Dict[str, Any]:
        """
        优化检索策略
        """
        # 1. 按价值和相关性排序
        memory_items.sort(key=lambda x: (x.value_level, x.usage_count), reverse=True)

        # 2. 渐进式构建上下文
        budget_manager = TokenBudgetManager(self.max_tokens)
        context = {
            "summaries": [],
            "detailed_items": [],
            "tokens_used": 0,
            "optimization_stats": {
                "initial_items": len(memory_items),
                "selected_items": 0,
                "summary_ratio": 0
            }
        }

        selected_count = 0
        summary_tokens = 0
        total_tokens = 0

        for item in memory_items:
            # 计算摘要的令牌数
            summary_token_count = self.token_counter.count_tokens(item.summary)
            
            # 尝试分配令牌
            if budget_manager.allocate(summary_token_count):
                context["summaries"].append({
                    "id": item.id,
                    "summary": item.summary,
                    "keywords": item.keywords,
                    "value_level": item.value_level,
                    "created_at": item.created_at,
                    "tokens": summary_token_count
                })
                selected_count += 1
                summary_tokens += summary_token_count
                total_tokens += summary_token_count

                # 检查是否还有足够的令牌获取详细内容
                content = item.compressed_content or item.content
                content_token_count = self.token_counter.count_tokens(content)
                
                if budget_manager.allocate(content_token_count):
                    context["detailed_items"].append({
                        "id": item.id,
                        "content": content,
                        "summary": item.summary,
                        "keywords": item.keywords,
                        "tokens": content_token_count
                    })
                    total_tokens += content_token_count
            else:
                # 令牌不足，停止
                break

        # 更新统计信息
        context["tokens_used"] = total_tokens
        context["optimization_stats"]["selected_items"] = selected_count
        context["optimization_stats"]["summary_ratio"] = summary_tokens / total_tokens if total_tokens > 0 else 0
        context["optimization_stats"]["budget_utilization"] = total_tokens / self.max_tokens

        return context

    def calculate_optimal_batch_size(self, average_token_per_item: int) -> int:
        """
        计算最优批处理大小
        """
        if average_token_per_item <= 0:
            return 1
        return max(1, self.max_tokens // (average_token_per_item * 2))


class ContextPrioritizer:
    """上下文优先级排序器"""

    @staticmethod
    def prioritize_items(memory_items: List[Any], query: str) -> List[Any]:
        """
        优先级排序记忆项
        """
        # 1. 计算每个记忆项的相关性分数
        scored_items = []
        for item in memory_items:
            score = ContextPrioritizer._calculate_relevance_score(item, query)
            scored_items.append((score, item))

        # 2. 按分数排序
        scored_items.sort(key=lambda x: x[0], reverse=True)

        # 3. 返回排序后的记忆项
        return [item for _, item in scored_items]

    @staticmethod
    def _calculate_relevance_score(item: Any, query: str) -> float:
        """
        计算记忆项与查询的相关性分数
        """
        score = 0.0

        # 基于价值等级
        score += item.value_level * 0.3

        # 基于使用频率
        score += min(item.usage_count / 10, 1.0) * 0.2

        # 基于关键词匹配
        query_keywords = set(query.lower().split())
        item_keywords = set(keyword.lower() for keyword in item.keywords)
        common_keywords = query_keywords.intersection(item_keywords)
        if item_keywords:
            score += len(common_keywords) / len(item_keywords) * 0.3

        # 基于内容匹配
        if query.lower() in item.content.lower():
            score += 0.2

        return min(score, 1.0)
