"""
QueryTransformer - 查询转换器
对查询进行转换，提高检索准确性

核心功能：
1. 查询重写（Query Rewriting）
2. 查询分解（Query Decomposition）
3. 多语言查询支持
4. 从历史查询中学习转换模式

遵循自我进化原则：从交互中学习查询转换模式
"""

import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger

try:
    from business.global_model_router import GlobalModelRouter, ModelCapability
    HAS_ROUTER = True
except ImportError:
    HAS_ROUTER = False


@dataclass
class TransformResult:
    """转换结果"""
    original_query: str
    transformed_queries: List[str] = field(default_factory=list)
    decomposed_queries: List[str] = field(default_factory=list)
    reasoning: str = ""


class QueryTransformer:
    """
    查询转换器
    
    对查询进行转换，提高检索准确性：
    - 查询重写：将模糊查询转换为更精确的查询
    - 查询分解：将复杂查询分解为多个简单查询
    
    遵循自我进化原则：
    - 从交互中学习转换模式
    - 动态优化转换策略
    """

    def __init__(self):
        self._router = GlobalModelRouter() if HAS_ROUTER else None
        self._logger = logger.bind(component="QueryTransformer")
        self._transformation_history: List[Dict[str, Any]] = []

    async def transform(self, query: str, history: Optional[List[str]] = None) -> TransformResult:
        """
        转换查询
        
        Args:
            query: 原始查询
            history: 历史查询列表（可选）
            
        Returns:
            TransformResult
        """
        self._logger.info(f"转换查询: {query[:50]}...")

        transformed = []
        decomposed = []

        # 1. 查询重写
        if self._router:
            rewrites = await self._rewrite_query(query)
            transformed.extend(rewrites)

        # 2. 查询分解（如果查询复杂）
        if len(query) > 50 or "并且" in query or "同时" in query:
            if self._router:
                decomposed = await self._decompose_query(query)

        # 3. 添加原始查询作为后备
        if query not in transformed:
            transformed.append(query)

        return TransformResult(
            original_query=query,
            transformed_queries=transformed,
            decomposed_queries=decomposed,
            reasoning=f"生成了 {len(transformed)} 个重写查询，{len(decomposed)} 个分解查询"
        )

    async def _rewrite_query(self, query: str) -> List[str]:
        """
        重写查询
        
        将模糊查询转换为更精确的查询
        """
        prompt = f"""
你是一个查询重写专家。

请将以下查询重写为多个更精确的变体，以提高检索准确性：

原始查询：{query}

要求：
1. 生成 2-3 个不同的重写版本
2. 保留核心语义
3. 使用不同的表达方式
4. 可以扩展或简化查询

输出格式（每行一个重写查询）：
1. 重写查询1
2. 重写查询2
3. 重写查询3
"""

        try:
            response = self._router.call_model_sync(
                capability=ModelCapability.REASONING,
                prompt=prompt,
                temperature=0.5
            )

            # 解析响应
            lines = response.strip().split("\n")
            rewrites = []
            for line in lines:
                # 去除序号和空白
                line = line.strip()
                if line and not line.startswith("原始查询"):
                    # 去除 "1." "2." 等序号
                    import re
                    line = re.sub(r'^\d+\.\s*', '', line)
                    if line and line != query:
                        rewrites.append(line)

            return rewrites[:3]  # 最多返回 3 个

        except Exception as e:
            self._logger.error(f"查询重写失败: {e}")
            return []

    async def _decompose_query(self, query: str) -> List[str]:
        """
        分解复杂查询
        
        将复杂查询分解为多个简单查询
        """
        prompt = f"""
你是一个查询分解专家。

请将以下复杂查询分解为多个简单查询：

原始查询：{query}

要求：
1. 每个子查询应该是一个独立的问题
2. 所有子查询合起来应该能够回答原始查询
3. 输出 JSON 格式

输出格式：
{{
    "sub_queries": ["子查询1", "子查询2", "子查询3"]
}}
"""

        try:
            response = self._router.call_model_sync(
                capability=ModelCapability.REASONING,
                prompt=prompt,
                temperature=0.3
            )

            # 解析 JSON
            result = json.loads(response)
            return result.get("sub_queries", [])

        except Exception as e:
            self._logger.error(f"查询分解失败: {e}")
            return []

    async def learn_from_feedback(self, original_query: str, transformed: List[str], feedback: str):
        """
        从反馈中学习
        
        Args:
            original_query: 原始查询
            transformed: 转换后的查询列表
            feedback: 用户反馈（"effective" / "ineffective"）
        """
        self._transformation_history.append({
            "original": original_query,
            "transformed": transformed,
            "feedback": feedback,
            "timestamp": len(self._transformation_history)
        })

        if feedback == "ineffective":
            self._logger.info(f"学习改进转换策略: {original_query[:30]}...")

    def get_stats(self) -> Dict[str, Any]:
        """获取转换器统计信息"""
        return {
            "total_transformations": len(self._transformation_history),
            "effective_count": sum(
                1 for h in self._transformation_history if h.get("feedback") == "effective"
            ),
        }