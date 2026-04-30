"""
QueryClassifier - 查询分类器
判断查询是否需要进行检索

核心功能：
1. 二元分类：sufficient（已有知识足够回答）/ insufficient（需要检索）
2. 基于 LLM 的语义理解
3. 支持多种分类策略
4. 可训练分类器

遵循自我进化原则：从交互数据中学习分类模式
"""

import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from loguru import logger

try:
    from business.global_model_router import GlobalModelRouter, ModelCapability
    HAS_ROUTER = True
except ImportError:
    HAS_ROUTER = False


@dataclass
class ClassificationResult:
    """分类结果"""
    decision: str  # "sufficient" / "insufficient" / "unknown"
    confidence: float = 0.0
    reasoning: str = ""
    features: Dict[str, Any] = field(default_factory=dict)


class QueryClassifier:
    """
    查询分类器
    
    判断查询是否需要进行检索：
    - sufficient: 已有知识足够回答，直接生成即可
    - insufficient: 需要检索外部知识
    
    遵循自我进化原则：
    - 不预置固定规则
    - 从交互中学习分类模式
    """

    def __init__(self):
        self._router = GlobalModelRouter() if HAS_ROUTER else None
        self._logger = logger.bind(component="QueryClassifier")
        self._learning_history: List[Dict[str, Any]] = []

    async def classify(self, query: str, context: Optional[str] = None) -> ClassificationResult:
        """
        分类查询
        
        Args:
            query: 用户查询
            context: 上下文信息（可选）
            
        Returns:
            ClassificationResult
        """
        self._logger.info(f"分类查询: {query[:50]}...")

        # 1. 快速规则检查（简单模式）
        fast_result = self._fast_check(query)
        if fast_result:
            return fast_result

        # 2. 使用 LLM 进行深度分析
        if self._router:
            return await self._llm_based_classify(query, context)

        # 3. 兜底：默认需要检索
        return ClassificationResult(
            decision="insufficient",
            confidence=0.5,
            reasoning="默认需要检索"
        )

    def _fast_check(self, query: str) -> Optional[ClassificationResult]:
        """
        快速规则检查
        
        基于简单模式匹配的快速分类
        """
        query_lower = query.lower()

        # 明显不需要检索的模式
        no_retrieval_patterns = [
            r'^[0-9]+(\.[0-9]+)?\s*[+\-*/%]\s*[0-9]+(\.[0-9]+)?',  # 简单计算
            r'^你好|^您好|^hi|^hello',  # 问候
            r'^我想.*|^我要.*|^我需要.*',  # 意图表达（可能需要进一步分析）
        ]

        # 明显需要检索的模式
        retrieval_patterns = [
            r'什么是.*',  # 定义类问题
            r'如何.*|怎么.*|怎样.*',  # 方法类问题
            r'最新.*|最近.*|现在.*',  # 时效性问题
            r'多少.*|多少个.*|多少钱.*',  # 数量类问题
            r'哪个.*|哪一个.*',  # 选择类问题
            r'为什么.*|为何.*',  # 原因类问题
            r'对比.*|比较.*',  # 对比类问题
            r'分析.*|评估.*',  # 分析类问题
            r'根据.*|依据.*',  # 需要参考资料的问题
        ]

        import re
        for pattern in no_retrieval_patterns:
            if re.match(pattern, query_lower):
                return ClassificationResult(
                    decision="sufficient",
                    confidence=0.8,
                    reasoning=f"匹配模式: {pattern}"
                )

        for pattern in retrieval_patterns:
            if re.search(pattern, query_lower):
                return ClassificationResult(
                    decision="insufficient",
                    confidence=0.7,
                    reasoning=f"匹配模式: {pattern}"
                )

        return None

    async def _llm_based_classify(self, query: str, context: Optional[str] = None) -> ClassificationResult:
        """
        使用 LLM 进行深度分类
        """
        prompt = f"""
你是一个查询分类专家。

请分析以下查询，判断是否需要进行外部知识检索：

查询：{query}
上下文：{context or "无"}

分类标准：
1. sufficient（已有知识足够）：
   - 事实性问题，答案固定且广泛已知
   - 简单计算或逻辑推理
   - 问候、闲聊等不需要外部知识的问题

2. insufficient（需要检索）：
   - 需要最新信息的问题（如新闻、天气、股票）
   - 需要特定领域知识的问题（如法规、技术文档）
   - 需要参考特定文档的问题
   - 复杂分析或需要对比的问题

请以 JSON 格式输出：
{{
    "decision": "sufficient" 或 "insufficient",
    "confidence": 0.0-1.0,
    "reasoning": "推理过程"
}}

只输出 JSON，不要有其他内容。
"""

        try:
            response = self._router.call_model_sync(
                capability=ModelCapability.REASONING,
                prompt=prompt,
                temperature=0.1
            )

            # 解析响应
            try:
                result = json.loads(response)
                return ClassificationResult(
                    decision=result.get("decision", "unknown"),
                    confidence=result.get("confidence", 0.5),
                    reasoning=result.get("reasoning", "")
                )
            except json.JSONDecodeError:
                # 尝试提取 JSON
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                    return ClassificationResult(
                        decision=result.get("decision", "unknown"),
                        confidence=result.get("confidence", 0.5),
                        reasoning=result.get("reasoning", "")
                    )

        except Exception as e:
            self._logger.error(f"LLM 分类失败: {e}")

        # 兜底
        return ClassificationResult(
            decision="insufficient",
            confidence=0.5,
            reasoning="分类失败，默认需要检索"
        )

    async def learn_from_feedback(self, query: str, classification: str, feedback: str):
        """
        从反馈中学习
        
        Args:
            query: 原始查询
            classification: 之前的分类结果
            feedback: 用户反馈（"correct" / "incorrect"）
        """
        self._learning_history.append({
            "query": query,
            "classification": classification,
            "feedback": feedback,
            "timestamp": len(self._learning_history)
        })

        # 如果反馈表明分类错误，记录以便后续学习
        if feedback == "incorrect":
            self._logger.info(f"学习纠正: {query[:30]}...")

    def get_stats(self) -> Dict[str, Any]:
        """获取分类器统计信息"""
        return {
            "total_classifications": len(self._learning_history),
            "correct_classifications": sum(
                1 for h in self._learning_history if h.get("feedback") == "correct"
            ),
            "learning_patterns": len(self._learning_history)
        }