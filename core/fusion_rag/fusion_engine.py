"""
多源融合引擎 (Multi-Source Fusion Engine)
汇聚四层检索结果，生成最优答案

功能:
- 多源结果去重与合并
- 基于置信度加权融合
- RRF/MRR 等融合算法
- 答案生成与优化
"""

import time
import hashlib
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from collections import defaultdict

if TYPE_CHECKING:
    from .l4_executor import L4RelayExecutor
    from .write_back_cache import WriteBackCache


class FusionEngine:
    """多源融合引擎（支持 L4 穿透）"""
    
    def __init__(
        self,
        top_k: int = 10,
        l4_executor: Optional[Any] = None,
        write_back_cache: Optional[Any] = None
    ):
        """
        初始化融合引擎
        
        Args:
            top_k: 返回的最终结果数量
            l4_executor: L4 执行器 (L4RelayExecutor)
            write_back_cache: L4 回填缓存
        """
        self.top_k = top_k
        self.l4_executor = l4_executor
        self.write_back_cache = write_back_cache
        
        # 融合算法配置
        self.algorithms = {
            "weighted_sum": self._weighted_sum_fusion,
            "rrf": self._rrf_fusion,
            "mrr": self._mrr_fusion,
            "hybrid": self._hybrid_fusion
        }
        
        # 默认算法
        self.default_algorithm = "hybrid"
        
        # 统计
        self.fusion_count = 0
        self.avg_results_count = 0
        self.l4_execution_count = 0
        self.write_back_count = 0
        
        print(f"[FusionEngine] 初始化完成，默认算法: {self.default_algorithm}")
    
    def _normalize_scores(self, results: List[Dict], score_key: str = "score") -> List[Dict]:
        """归一化分数"""
        if not results:
            return results
        
        scores = [r.get(score_key, 0) for r in results]
        max_score = max(scores) if scores else 1
        min_score = min(scores) if scores else 0
        score_range = max_score - min_score if max_score != min_score else 1
        
        for r in results:
            original = r.get(score_key, 0)
            r[f"{score_key}_normalized"] = (original - min_score) / score_range
        
        return results
    
    def _weighted_sum_fusion(
        self,
        layer_results: Dict[str, List[Dict]],
        weights: Dict[str, float]
    ) -> List[Dict]:
        """加权求和融合"""
        # 合并所有结果
        all_results = []
        result_sources = {}  # id -> source
        
        for layer, results in layer_results.items():
            weight = weights.get(layer, 0.25)
            
            for r in results:
                # 生成唯一ID
                content = r.get("content", "")
                content_hash = hashlib.md5(content.encode()).hexdigest()[:12]
                result_id = f"{content_hash}"
                
                # 归一化分数
                r["score"] = r.get("score", 0.5) * weight
                r["source"] = layer
                r["result_id"] = result_id
                
                all_results.append(r)
                result_sources[result_id] = layer
        
        # 去重 (保留最高分)
        unique_results = {}
        for r in all_results:
            result_id = r["result_id"]
            if result_id not in unique_results or r["score"] > unique_results[result_id]["score"]:
                unique_results[result_id] = r
        
        # 排序
        sorted_results = sorted(
            unique_results.values(),
            key=lambda x: x["score"],
            reverse=True
        )[:self.top_k]
        
        return sorted_results
    
    def _rrf_fusion(
        self,
        layer_results: Dict[str, List[Dict]],
        weights: Dict[str, float],
        k: int = 60
    ) -> List[Dict]:
        """
        Reciprocal Rank Fusion (RRF)
        基于排名的融合算法，对不同来源的结果按排名加权
        """
        # 收集所有内容
        all_content = {}  # content_hash -> content info
        
        for layer, results in layer_results.items():
            for rank, r in enumerate(results, 1):
                content = r.get("content", "")
                content_hash = hashlib.md5(content.encode()).hexdigest()[:12]
                
                if content_hash not in all_content:
                    all_content[content_hash] = {
                        "content": content,
                        "ranks": {},
                        "scores": {},
                        "data": r
                    }
                
                # RRF 分数 = 1 / (k + rank)
                rrf_score = 1.0 / (k + rank)
                
                # 加权
                weight = weights.get(layer, 0.25)
                all_content[content_hash]["ranks"][layer] = rank
                all_content[content_hash]["scores"][layer] = r.get("score", 0) * weight
                
                # 累积 RRF
                if "rrf_total" not in all_content[content_hash]:
                    all_content[content_hash]["rrf_total"] = 0
                all_content[content_hash]["rrf_total"] += rrf_score * weight
        
        # 计算最终分数
        for content_hash, info in all_content.items():
            # 综合分数 = RRF分数 * 0.6 + 原始分数 * 0.4
            avg_score = sum(info["scores"].values()) / max(len(info["scores"]), 1)
            info["fused_score"] = info["rrf_total"] * 0.6 + avg_score * 0.4
            info["source"] = list(info["scores"].keys())[0] if info["scores"] else "unknown"
        
        # 排序
        sorted_results = sorted(
            all_content.values(),
            key=lambda x: x["fused_score"],
            reverse=True
        )[:self.top_k]
        
        # 格式化输出
        formatted = []
        for info in sorted_results:
            r = info["data"].copy()
            r["fused_score"] = info["fused_score"]
            r["source"] = info["source"]
            r["rrf_score"] = info["rrf_total"]
            formatted.append(r)
        
        return formatted
    
    def _mrr_fusion(
        self,
        layer_results: Dict[str, List[Dict]],
        weights: Dict[str, float]
    ) -> List[Dict]:
        """Mean Reciprocal Rank (MRR) 融合"""
        # 类似 RRF，但使用倒数排名
        return self._rrf_fusion(layer_results, weights, k=1)
    
    def _hybrid_fusion(
        self,
        layer_results: Dict[str, List[Dict]],
        weights: Dict[str, float]
    ) -> List[Dict]:
        """混合融合算法"""
        # 结合加权求和和 RRF
        
        # 先做加权求和
        weighted_results = self._weighted_sum_fusion(layer_results, weights)
        
        # 计算 RRF 分数
        rrf_scores = {}
        
        for layer, results in layer_results.items():
            for rank, r in enumerate(results, 1):
                content = r.get("content", "")
                content_hash = hashlib.md5(content.encode()).hexdigest()[:12]
                
                if content_hash not in rrf_scores:
                    rrf_scores[content_hash] = 0
                
                weight = weights.get(layer, 0.25)
                rrf_scores[content_hash] += (1.0 / (60 + rank)) * weight
        
        # 合并分数
        for r in weighted_results:
            content = r.get("content", "")
            content_hash = hashlib.md5(content.encode()).hexdigest()[:12]
            
            rrf = rrf_scores.get(content_hash, 0)
            r["rrf_score"] = rrf
            
            # 融合: 加权分数 * 0.5 + RRF * 0.5
            r["fused_score"] = r["score"] * 0.5 + rrf * 0.5
        
        # 重新排序
        weighted_results.sort(key=lambda x: x["fused_score"], reverse=True)
        
        return weighted_results
    
    def fuse(
        self,
        layer_results: Dict[str, List[Dict]],
        weights: Optional[Dict[str, float]] = None,
        algorithm: Optional[str] = None
    ) -> List[Dict]:
        """
        融合多源结果
        
        Args:
            layer_results: {
                "exact_cache": [...],
                "session_cache": [...],
                "knowledge_base": [...],
                "database": [...]
            }
            weights: 各层权重
            algorithm: 融合算法
            
        Returns:
            融合后的结果列表
        """
        self.fusion_count += 1
        
        if not layer_results:
            return []
        
        # 归一化权重
        if weights is None:
            weights = {layer: 0.25 for layer in layer_results}
        else:
            total = sum(weights.values())
            if total > 0:
                weights = {k: v / total for k, v in weights.items()}
        
        # 选择算法
        algo_name = algorithm or self.default_algorithm
        fusion_func = self.algorithms.get(algo_name, self._hybrid_fusion)
        
        # 执行融合
        results = fusion_func(layer_results, weights)
        
        # 更新统计
        self.avg_results_count = (
            (self.avg_results_count * (self.fusion_count - 1) + len(results)) / self.fusion_count
        )
        
        return results
    
    def generate_answer(
        self,
        query: str,
        fused_results: List[Dict],
        use_llm: bool = False
    ) -> Dict[str, Any]:
        """
        基于融合结果生成答案
        
        Args:
            query: 查询
            fused_results: 融合后的结果
            use_llm: 是否使用 LLM 生成
            
        Returns:
            {
                "answer": "...",
                "sources": [...],
                "confidence": 0.85
            }
        """
        if not fused_results:
            return {
                "answer": "抱歉，我无法找到相关信息。",
                "sources": [],
                "confidence": 0.0
            }
        
        # 直接使用最优结果
        best_result = fused_results[0]
        
        # 收集来源
        sources = []
        for r in fused_results[:3]:
            sources.append({
                "content": r.get("content", "")[:100],
                "source": r.get("source", "unknown"),
                "score": r.get("fused_score", 0)
            })
        
        return {
            "answer": best_result.get("content", ""),
            "sources": sources,
            "confidence": best_result.get("fused_score", 0),
            "has_llm_enhancement": use_llm
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "fusion_count": self.fusion_count,
            "avg_results_count": self.avg_results_count,
            "available_algorithms": list(self.algorithms.keys()),
            "default_algorithm": self.default_algorithm,
            "l4_enabled": self.l4_executor is not None,
            "l4_execution_count": self.l4_execution_count,
            "write_back_count": self.write_back_count
        }

    # ==================== L4 穿透支持 ====================

    async def execute_l4(
        self,
        messages: List[Dict[str, Any]],
        model: str = "auto",
        intent: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        穿透到 L4 执行

        Args:
            messages: 对话消息
            model: 模型
            intent: 意图

        Returns:
            L4 执行结果
        """
        if self.l4_executor is None:
            raise FusionEngineError("L4 执行器未配置")

        self.l4_execution_count += 1
        result = await self.l4_executor.execute(
            messages=messages,
            model=model,
            intent=intent
        )

        # 异步回填缓存
        if self.write_back_cache:
            try:
                await self.write_back_cache.write_back(messages, result)
                self.write_back_count += 1
            except Exception as e:
                print(f"[FusionEngine] 回填缓存失败: {e}")

        return result

    async def query_with_l4_fallback(
        self,
        messages: List[Dict[str, Any]],
        layer_results: Dict[str, List[Dict]],
        weights: Optional[Dict[str, float]] = None,
        strategy: str = "balanced",
        intent: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        带 L4 兜底的查询

        流程:
        1. 融合缓存层结果
        2. 判断是否需要穿透 L4
        3. 如需穿透，执行 L4 并回填缓存

        Args:
            messages: 对话消息
            layer_results: 各层检索结果
            weights: 融合权重
            strategy: 路由策略
            intent: 意图

        Returns:
            {
                "source": "l4" | "cache",
                "answer": "...",
                "confidence": 0.9,
                "result": {...}
            }
        """
        # 1. 融合缓存结果
        fused_results = self.fuse(layer_results, weights)

        # 2. 判断是否需要 L4
        needs_l4 = self._should_execute_l4(fused_results, strategy, intent)

        if not needs_l4 and fused_results:
            # 缓存命中
            answer = self.generate_answer(
                messages[-1].get("content", ""),
                fused_results,
                use_llm=False
            )
            return {
                "source": "cache",
                "answer": answer["answer"],
                "confidence": answer["confidence"],
                "fused_results": fused_results,
                "result": fused_results[0] if fused_results else None
            }

        # 3. 穿透 L4
        if self.l4_executor:
            try:
                l4_result = await self.execute_l4(
                    messages=messages,
                    intent=intent.get("primary") if intent else None
                )

                # 提取 L4 回答
                l4_answer = self._extract_l4_answer(l4_result)

                return {
                    "source": "l4",
                    "answer": l4_answer,
                    "confidence": 0.95,
                    "fused_results": fused_results,
                    "result": l4_result,
                    "l4_provider": l4_result.get("_provider", "unknown")
                }
            except Exception as e:
                print(f"[FusionEngine] L4 执行失败: {e}")
                # L4 失败，返回缓存结果
                if fused_results:
                    answer = self.generate_answer(
                        messages[-1].get("content", ""),
                        fused_results,
                        use_llm=False
                    )
                    return {
                        "source": "cache_fallback",
                        "answer": answer["answer"],
                        "confidence": answer["confidence"] * 0.5,  # 降权
                        "fused_results": fused_results,
                        "error": str(e)
                    }

        # 4. 完全无结果
        return {
            "source": "none",
            "answer": "抱歉，我无法找到相关信息。",
            "confidence": 0.0,
            "fused_results": [],
            "result": None
        }

    def _should_execute_l4(
        self,
        fused_results: List[Dict],
        strategy: str,
        intent: Optional[Dict[str, Any]]
    ) -> bool:
        """判断是否需要穿透 L4"""
        # 无结果
        if not fused_results:
            return True

        # 最高置信度低于阈值
        max_score = max((r.get("fused_score", 0) for r in fused_results), default=0)

        thresholds = {
            "speed_first": 0.7,
            "accuracy_first": 0.9,
            "balanced": 0.8,
            "cache_only": 1.0,  # 从不穿透
            "llm_first": 0.0    # 始终穿透
        }

        threshold = thresholds.get(strategy, 0.8)

        # 意图调整
        if intent and intent.get("primary") == "creative":
            threshold -= 0.1

        return max_score < threshold

    def _extract_l4_answer(self, l4_result: Dict[str, Any]) -> str:
        """从 L4 结果中提取回答"""
        if not l4_result:
            return ""

        # 标准 OpenAI 格式
        if "choices" in l4_result and len(l4_result["choices"]) > 0:
            choice = l4_result["choices"][0]
            if "message" in choice:
                return choice["message"].get("content", "")
            if "delta" in choice:
                return choice["delta"].get("content", "")

        return str(l4_result.get("content", l4_result))


class FusionEngineError(Exception):
    """FusionEngine 异常"""
    pass
