"""
L2 轻量模型层
亚秒级响应（<500ms），处理简单查询
"""

import time
import asyncio
from typing import Optional, Any, Dict, Callable
from dataclasses import dataclass
from enum import Enum


class QueryComplexity(Enum):
    """查询复杂度枚举"""
    TRIVIAL = 0      # 极简单
    SIMPLE = 1       # 简单
    MODERATE = 2     # 中等
    COMPLEX = 3      # 复杂


@dataclass
class LightweightResult:
    """轻量模型处理结果"""
    tier: str = "L2"
    response: Any = None
    latency_ms: float = 0
    confidence: float = 0.0
    complexity: QueryComplexity = QueryComplexity.SIMPLE
    needs_upgrade: bool = False


class Tier2Lightweight:
    """
    L2 轻量模型层
    - 处理目标：亚秒级响应（<500ms）
    - 模型选择：微型模型（<3B参数）或蒸馏模型
    - 置信度阈值：> 0.8
    """
    
    def __init__(self, model_loader: Callable = None):
        self.model_loader = model_loader
        self.model = None
        self.model_name = "phi-2"  # 默认轻量模型
        self.confidence_threshold = 0.8
        self.max_latency_ms = 500
        
        # 简单查询关键词
        self.simple_keywords = {
            "定义", "是什么", "什么意思", "who is", "what is", "定义是",
            "翻译", "格式", "换算", "计算", "今天", "明天", "日期",
            "问候", "你好", "谢谢", "天气", "时间"
        }
        
        # 复杂查询关键词
        self.complex_keywords = {
            "分析", "比较", "评估", "建议", "如何", "为什么", "推理",
            "分析", "设计", "实现", "创建", "生成", "分析", "证明",
            "analyze", "compare", "evaluate", "design", "implement"
        }
        
        self._total_requests = 0
        self._successful_requests = 0
    
    def _classify_complexity(self, query: str) -> QueryComplexity:
        """分类查询复杂度"""
        query_lower = query.lower()
        
        # 统计关键词
        simple_count = sum(1 for kw in self.simple_keywords if kw in query_lower)
        complex_count = sum(1 for kw in self.complex_keywords if kw in query_lower)
        
        # 查询长度
        length = len(query)
        
        if simple_count >= 2 and length < 50:
            return QueryComplexity.TRIVIAL
        elif simple_count >= 1 and complex_count == 0 and length < 100:
            return QueryComplexity.SIMPLE
        elif complex_count >= 2 or length > 200:
            return QueryComplexity.COMPLEX
        else:
            return QueryComplexity.MODERATE
    
    def _load_model(self):
        """加载轻量模型"""
        if self.model is None and self.model_loader:
            self.model = self.model_loader(self.model_name)
    
    async def process(self, query: str, context: str = None) -> LightweightResult:
        """
        处理查询
        - 复杂度检测
        - 模型推理
        - 置信度评估
        """
        start = time.perf_counter()
        self._total_requests += 1
        
        # 复杂度检测
        complexity = self._classify_complexity(query)
        query_length = len(query)
        
        # 简单查询直接处理
        if complexity in (QueryComplexity.TRIVIAL, QueryComplexity.SIMPLE):
            result = await self._generate_response(query, context)
            latency = (time.perf_counter() - start) * 1000
            
            self._successful_requests += 1
            
            return LightweightResult(
                tier="L2",
                response=result["response"],
                latency_ms=latency,
                confidence=result.get("confidence", 0.9),
                complexity=complexity,
                needs_upgrade=latency > self.max_latency_ms
            )
        
        # 中等复杂度需要模型判断
        elif complexity == QueryComplexity.MODERATE:
            # 检查是否在处理能力范围内
            if query_length < 150:
                result = await self._generate_response(query, context)
                latency = (time.perf_counter() - start) * 1000
                
                # 检查置信度
                if result.get("confidence", 0) >= self.confidence_threshold:
                    self._successful_requests += 1
                    return LightweightResult(
                        tier="L2",
                        response=result["response"],
                        latency_ms=latency,
                        confidence=result["confidence"],
                        complexity=complexity,
                        needs_upgrade=False
                    )
            
            # 置信度不足或太复杂，需要升级
            return LightweightResult(
                tier="L2",
                response=None,
                latency_ms=(time.perf_counter() - start) * 1000,
                confidence=0.0,
                complexity=complexity,
                needs_upgrade=True
            )
        
        # 复杂查询直接升级
        return LightweightResult(
            tier="L2",
            response=None,
            latency_ms=(time.perf_counter() - start) * 1000,
            confidence=0.0,
            complexity=QueryComplexity.COMPLEX,
            needs_upgrade=True
        )
    
    async def _generate_response(self, query: str, context: str = None) -> Dict[str, Any]:
        """生成响应"""
        # 模板化回复
        templates = {
            "定义": self._template_definition,
            "翻译": self._template_translate,
            "问候": self._template_greeting,
            "计算": self._template_calculate,
            "日期": self._template_date,
        }
        
        for keyword, func in templates.items():
            if keyword in query:
                response = func(query)
                return {"response": response, "confidence": 0.95}
        
        # 如果有模型，使用模型生成
        if self.model:
            try:
                response = self.model.generate(query, max_tokens=100)
                return {"response": response, "confidence": 0.85}
            except Exception:
                pass
        
        # 默认回复
        return {
            "response": f"这是一个简单的查询回复：{query[:50]}...",
            "confidence": 0.7
        }
    
    def _template_definition(self, query: str) -> str:
        """定义类查询模板"""
        # 提取关键词
        import re
        match = re.search(r'[是为]([^?。！？]+)', query)
        if match:
            term = match.group(1).strip()
            return f"{term}是指..."
        return "这是一个定义类查询。"
    
    def _template_translate(self, query: str) -> str:
        """翻译类查询模板"""
        return "翻译内容..."
    
    def _template_greeting(self, query: str) -> str:
        """问候类查询模板"""
        greetings = ["你好", "hello", "hi", "您好"]
        for g in greetings:
            if g in query.lower():
                return "你好！有什么可以帮助你的吗？"
        return "你好！"
    
    def _template_calculate(self, query: str) -> str:
        """计算类查询模板"""
        import re
        # 简单数学表达式提取
        match = re.search(r'(\d+)\s*([+\-*/])\s*(\d+)', query)
        if match:
            a, op, b = int(match.group(1)), match.group(2), int(match.group(3))
            ops = {"+": a + b, "-": a - b, "*": a * b, "/": a / b if b != 0 else 0}
            result = ops.get(op, 0)
            return f"计算结果：{result}"
        return "我来进行计算..."
    
    def _template_date(self, query: str) -> str:
        """日期类查询模板"""
        from datetime import datetime
        now = datetime.now()
        return f"当前时间：{now.strftime('%Y年%m月%d日 %H:%M:%S')}"
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        success_rate = self._successful_requests / self._total_requests if self._total_requests > 0 else 0
        
        return {
            "tier": "L2",
            "model": self.model_name,
            "total_requests": self._total_requests,
            "successful_requests": self._successful_requests,
            "success_rate": success_rate,
            "confidence_threshold": self.confidence_threshold,
            "max_latency_ms": self.max_latency_ms
        }
