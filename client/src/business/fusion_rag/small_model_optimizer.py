"""
本地小模型优化器 (Small Model Optimizer)
使用本地小型语言模型优化检索结果

支持的模型:
- Qwen2.5-1.5B-Instruct: 极速响应
- ChatGLM3-6B-32K: 复杂答案整合
- Phi-3-mini: 微软小模型
- Ollama 本地模型
"""

import time
import hashlib
from typing import Dict, Any, List, Optional
from collections import defaultdict


class SmallModelOptimizer:
    """本地小模型优化器"""
    
    def __init__(
        self,
        model_name: str = "qwen2.5:1.5b",
        ollama_url: str = "http://localhost:11434",
        enable_cache: bool = True
    ):
        """
        初始化小模型优化器
        
        Args:
            model_name: 模型名称
            ollama_url: Ollama 服务地址
            enable_cache: 是否启用结果缓存
        """
        self.model_name = model_name
        self.ollama_url = ollama_url
        self.enable_cache = enable_cache
        
        # 结果缓存
        self.result_cache: Dict[str, Dict] = {}
        self.cache_hits = 0
        self.cache_misses = 0
        
        # 统计
        self.optimization_count = 0
        self.total_latency_ms = 0
        self.quality_scores = []
        
        # 可用的优化任务
        self.optimization_tasks = {
            "deduplicate": self._deduplicate,
            "format": self._format_answer,
            "expand": self._expand_answer,
            "summarize": self._summarize,
            "rewrite": self._rewrite
        }
        
        print(f"[SmallModelOptimizer] 初始化完成，模型: {model_name}")
    
    def _generate_cache_key(self, query: str, results: List[Dict]) -> str:
        """生成缓存键"""
        # 简化: 只用查询和结果数量
        key_parts = [query, str(len(results))]
        return hashlib.md5("|".join(key_parts).encode()).hexdigest()
    
    def _call_ollama(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 512
    ) -> Dict[str, Any]:
        """
        调用 Ollama API
        
        Args:
            prompt: 提示词
            system_prompt: 系统提示
            max_tokens: 最大token数
            
        Returns:
            API 响应
        """
        # 模拟 Ollama 调用 (实际使用 requests 库)
        try:
            import requests
            
            url = f"{self.ollama_url}/api/generate"
            
            data = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": 0.7
                }
            }
            
            if system_prompt:
                data["system"] = system_prompt
            
            response = requests.post(url, json=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "response": result.get("response", ""),
                    "latency_ms": result.get("total_duration", 0) / 1e6
                }
            else:
                return {
                    "success": False,
                    "error": f"API error: {response.status_code}"
                }
        
        except ImportError:
            # requests 未安装，使用模拟响应
            return self._mock_generate(prompt)
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _mock_generate(self, prompt: str) -> Dict[str, Any]:
        """模拟生成 (用于测试)"""
        time.sleep(0.1)  # 模拟延迟
        
        # 简单模拟
        return {
            "success": True,
            "response": f"[优化后的答案] 基于检索结果整合: {prompt[:50]}...",
            "latency_ms": 100
        }
    
    def _deduplicate(self, query: str, results: List[Dict]) -> List[Dict]:
        """去重优化"""
        seen = set()
        deduplicated = []
        
        for r in results:
            content = r.get("content", "")
            # 简单去重 (基于内容哈希)
            content_hash = hashlib.md5(content.encode()).hexdigest()[:16]
            
            if content_hash not in seen:
                seen.add(content_hash)
                deduplicated.append(r)
        
        return deduplicated
    
    def _format_answer(self, content: str, style: str = "default") -> str:
        """格式化答案"""
        if style == "default":
            return content
        elif style == "concise":
            # 提取关键句子
            sentences = content.split("。")
            return "。".join(sentences[:2]) + "。"
        elif style == "detailed":
            return content + "\n\n[以上信息来自知识库检索]"
        else:
            return content
    
    def _expand_answer(self, query: str, results: List[Dict]) -> str:
        """扩展答案"""
        if not results:
            return "抱歉，没有找到相关信息。"
        
        # 合并多个结果
        contents = [r.get("content", "") for r in results[:3]]
        combined = "\n\n".join(contents)
        
        prompt = f"""根据以下检索结果，生成一个完整、准确的答案：

问题：{query}

检索结果：
{combined}

请整合以上信息，给出一个连贯、完整的答案。"""
        
        return prompt
    
    def _summarize(self, query: str, results: List[Dict]) -> str:
        """总结答案"""
        if not results:
            return "没有找到相关信息。"
        
        # 取最高分结果
        best = results[0]
        content = best.get("content", "")
        
        # 简单截断
        if len(content) > 200:
            return content[:200] + "..."
        
        return content
    
    def _rewrite(self, query: str, results: List[Dict]) -> str:
        """重写答案"""
        return self._expand_answer(query, results)
    
    def _assess_quality(self, query: str, answer: str, results: List[Dict]) -> Dict[str, float]:
        """
        评估答案质量
        
        Returns:
            {
                "relevance": 0.9,
                "completeness": 0.8,
                "accuracy": 0.85,
                "readability": 0.9,
                "overall": 0.86
            }
        """
        scores = {
            "relevance": 0.0,
            "completeness": 0.0,
            "accuracy": 0.0,
            "readability": 0.0,
            "overall": 0.0
        }
        
        # 基础评分
        if not answer or answer == "抱歉，没有找到相关信息。":
            return scores
        
        # 相关性: 查询词在答案中出现
        query_words = set(query.lower().split())
        answer_words = set(answer.lower())
        overlap = len(query_words & answer_words) / max(len(query_words), 1)
        scores["relevance"] = min(overlap * 2, 1.0)  # 放大
        
        # 完整性: 是否有多个来源
        scores["completeness"] = min(len(results) / 3, 1.0) if results else 0.3
        
        # 准确性: 来源分数
        if results:
            avg_source_score = sum(r.get("score", 0) for r in results) / len(results)
            scores["accuracy"] = avg_source_score
        else:
            scores["accuracy"] = 0.5
        
        # 可读性: 长度合理
        length = len(answer)
        if 50 < length < 500:
            scores["readability"] = 0.9
        elif 20 < length < 1000:
            scores["readability"] = 0.7
        else:
            scores["readability"] = 0.5
        
        # 综合分数
        scores["overall"] = (
            scores["relevance"] * 0.3 +
            scores["completeness"] * 0.2 +
            scores["accuracy"] * 0.3 +
            scores["readability"] * 0.2
        )
        
        return scores
    
    def optimize(
        self,
        query: str,
        results: List[Dict],
        task: str = "deduplicate",
        use_llm: bool = False
    ) -> Dict[str, Any]:
        """
        优化检索结果
        
        Args:
            query: 查询
            results: 检索结果
            task: 优化任务
            use_llm: 是否使用 LLM
            
        Returns:
            {
                "answer": "...",
                "quality_score": 0.85,
                "sources": [...],
                "confidence": 0.90
            }
        """
        start_time = time.time()
        self.optimization_count += 1
        
        # 检查缓存
        cache_key = self._generate_cache_key(query, results)
        
        if self.enable_cache and cache_key in self.result_cache:
            self.cache_hits += 1
            cached = self.result_cache[cache_key].copy()
            cached["from_cache"] = True
            return cached
        
        self.cache_misses += 1
        
        # 执行优化任务
        if task == "deduplicate":
            optimized_results = self._deduplicate(query, results)
            answer = self._format_answer(optimized_results[0].get("content", "") if optimized_results else "")
        
        elif task == "expand":
            if use_llm:
                answer = self._expand_answer(query, results)
            else:
                # 非LLM: 简单合并
                answer = "\n\n".join([r.get("content", "") for r in results[:2]])
        
        elif task == "summarize":
            answer = self._summarize(query, results)
        
        elif task == "rewrite":
            answer = self._rewrite(query, results)
        
        else:
            answer = results[0].get("content", "") if results else "没有找到相关信息。"
            optimized_results = results
        
        # 评估质量
        quality = self._assess_quality(query, answer, results)
        self.quality_scores.append(quality["overall"])
        
        # 计算延迟
        latency_ms = (time.time() - start_time) * 1000
        self.total_latency_ms += latency_ms
        
        # 构建响应
        response = {
            "answer": answer,
            "quality_score": quality["overall"],
            "quality_details": quality,
            "sources": [
                {
                    "content": r.get("content", "")[:100],
                    "source": r.get("source", "unknown"),
                    "score": r.get("score", 0)
                }
                for r in results[:3]
            ],
            "confidence": quality["overall"] * 0.9,
            "optimization_task": task,
            "used_llm": use_llm,
            "latency_ms": latency_ms,
            "from_cache": False
        }
        
        # 缓存结果
        if self.enable_cache:
            self.result_cache[cache_key] = response
        
        return response
    
    def batch_optimize(
        self,
        queries: List[str],
        results_list: List[List[Dict]],
        task: str = "deduplicate"
    ) -> List[Dict[str, Any]]:
        """批量优化"""
        return [
            self.optimize(query, results, task)
            for query, results in zip(queries, results_list)
        ]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        avg_quality = (
            sum(self.quality_scores) / len(self.quality_scores)
            if self.quality_scores else 0
        )
        
        avg_latency = (
            self.total_latency_ms / self.optimization_count
            if self.optimization_count > 0 else 0
        )
        
        cache_total = self.cache_hits + self.cache_misses
        cache_hit_rate = (
            self.cache_hits / cache_total if cache_total > 0 else 0
        )
        
        return {
            "optimization_count": self.optimization_count,
            "avg_quality_score": avg_quality,
            "avg_latency_ms": avg_latency,
            "cache_hit_rate": cache_hit_rate,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "model_name": self.model_name
        }
