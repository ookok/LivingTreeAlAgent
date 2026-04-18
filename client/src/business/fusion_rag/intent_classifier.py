"""
查询意图分类器 (Query Intent Classifier)
基于轻量级规则和特征工程的意图识别

支持意图类型:
- factual: 事实查询
- conversational: 对话类
- procedural: 流程类
- creative: 创意类
- hybrid: 混合类
"""

import re
from typing import Dict, Any, List
from collections import defaultdict


class QueryIntentClassifier:
    """查询意图分类器"""
    
    def __init__(self):
        """初始化分类器"""
        
        # 意图关键词
        self.intent_keywords = {
            "factual": {
                "question_words": ["什么", "是谁", "在哪", "多少", "怎么", "如何", "为什么", "是不是", "能不能"],
                "knowledge_words": ["定义", "概念", "原理", "历史", "区别", "方法", "步骤", "流程"],
                "examples": ["Python是什么", "机器学习的原理是什么", "如何使用Ollama"]
            },
            "conversational": {
                "context_words": ["之前", "刚才", "上面", "那个", "这个", "继续", "还有", "另外"],
                "follow_up": ["然后呢", "接下来", "还有吗", "补充一下", "详细说说"],
                "examples": ["我之前说的那个", "刚才的问题继续", "还有其他的吗"]
            },
            "procedural": {
                "action_words": ["怎么做", "如何实现", "怎么解决", "步骤", "流程", "教程", "指南"],
                "code_words": ["代码", "编程", "写", "开发", "部署", "配置", "安装", "运行"],
                "examples": ["如何安装Python", "怎么部署到服务器", "Redis缓存怎么配置"]
            },
            "creative": {
                "creative_words": ["写", "创作", "生成", "设计", "发明", "想象", "假如", "假设"],
                "content_words": ["故事", "诗", "文章", "小说", "剧本", "歌词", "文案", "策划"],
                "examples": ["帮我写一首诗", "创作一个故事", "设计一个Logo"]
            }
        }
        
        # 意图模式
        self.intent_patterns = {
            "factual": [
                r"^什么是",
                r"^.*是什么",
                r"^.*的原理",
                r"^.*的区别",
                r"^.*在哪里",
                r"^.*怎么做",
                r"^.*如何使用",
            ],
            "conversational": [
                r"^(上面|之前|刚才)说的",
                r"^还有",
                r"^继续",
                r"^然后",
                r"^另外",
            ],
            "procedural": [
                r"^(如何|怎么).*(安装|配置|部署|使用)",
                r"^(教程|指南|步骤)",
                r"^代码.*",
            ],
            "creative": [
                r"^(帮我)?写.*",
                r"^创作.*",
                r"^生成.*",
                r"^设计.*",
            ]
        }
        
        # 统计分析器
        self.stats = defaultdict(int)
    
    def _extract_features(self, query: str) -> Dict[str, Any]:
        """提取查询特征"""
        query_lower = query.lower()
        words = re.findall(r'[\w]+', query_lower)
        
        features = {
            # 基础特征
            "query_length": len(query),
            "word_count": len(words),
            "has_question_mark": "？" in query or "?" in query,
            
            # 意图关键词
            "has_question_word": False,
            "has_knowledge_word": False,
            "has_context_word": False,
            "has_action_word": False,
            "has_creative_word": False,
            "has_code_word": False,
            
            # 技术术语
            "has_technical_terms": False,
            
            # 复杂度
            "complexity_score": 0.0,
        }
        
        # 检测意图关键词
        for kw_type, keywords in self.intent_keywords.items():
            if kw_type == "factual":
                if any(kw in query for kw in keywords["question_words"]):
                    features["has_question_word"] = True
                if any(kw in query for kw in keywords["knowledge_words"]):
                    features["has_knowledge_word"] = True
            
            elif kw_type == "conversational":
                if any(kw in query for kw in keywords["context_words"] + keywords["follow_up"]):
                    features["has_context_word"] = True
            
            elif kw_type == "procedural":
                if any(kw in query for kw in keywords["action_words"]):
                    features["has_action_word"] = True
                if any(kw in query for kw in keywords["code_words"]):
                    features["has_code_word"] = True
            
            elif kw_type == "creative":
                if any(kw in query for kw in keywords["creative_words"] + keywords["content_words"]):
                    features["has_creative_word"] = True
        
        # 检测技术术语
        technical_terms = [
            "python", "java", "javascript", "api", "http", "sql", "json", "xml",
            "linux", "docker", "kubernetes", "git", "github", "redis", "mongodb",
            "mysql", "postgresql", "elasticsearch", "kafka", "rabbitmq",
            "vue", "react", "angular", "nodejs", "django", "flask",
            "tensorflow", "pytorch", "keras", "scikit",
            "llm", "gpt", "bert", "transformer",
            "oauth", "jwt", "https", "ssl", "tls",
            "mqtt", "websocket", "grpc", "rest",
        ]
        
        if any(term in query_lower for term in technical_terms):
            features["has_technical_terms"] = True
        
        # 计算复杂度
        complexity = 0.0
        if features["has_question_word"]:
            complexity += 0.2
        if features["has_knowledge_word"]:
            complexity += 0.3
        if features["has_technical_terms"]:
            complexity += 0.2
        if features["query_length"] > 20:
            complexity += 0.1
        if features["has_action_word"]:
            complexity += 0.2
        
        features["complexity_score"] = min(complexity, 1.0)
        
        return features
    
    def _match_patterns(self, query: str) -> Dict[str, float]:
        """模式匹配"""
        scores = defaultdict(float)
        
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query):
                    scores[intent] += 0.5
        
        return dict(scores)
    
    def _rule_based_classify(self, query: str, features: Dict) -> tuple:
        """基于规则分类"""
        query_lower = query.lower()
        
        # 规则优先级 (从高到低)
        
        # 1. 创意类
        if features["has_creative_word"]:
            return "creative", 0.85
        
        # 2. 流程/代码类
        if features["has_action_word"] or features["has_code_word"]:
            if features["has_question_word"]:
                return "procedural", 0.80
            return "factual", 0.70
        
        # 3. 对话类
        if features["has_context_word"]:
            return "conversational", 0.90
        
        # 4. 事实类
        if features["has_question_word"] or features["has_knowledge_word"]:
            if features["has_technical_terms"]:
                return "factual", 0.75
            return "factual", 0.80
        
        return "factual", 0.50
    
    def classify(self, query: str) -> Dict[str, Any]:
        """
        分类查询意图
        
        Args:
            query: 查询文本
            
        Returns:
            {
                "primary": "factual",
                "confidence": 0.85,
                "features": {...},
                "all_intents": {...}
            }
        """
        # 提取特征
        features = self._extract_features(query)
        
        # 模式匹配
        pattern_scores = self._match_patterns(query)
        
        # 规则分类
        rule_intent, rule_confidence = self._rule_based_classify(query, features)
        
        # 综合评分
        final_scores = defaultdict(float)
        
        # 规则分数
        if rule_intent:
            final_scores[rule_intent] += rule_confidence * 0.6
        
        # 模式分数
        for intent, score in pattern_scores.items():
            final_scores[intent] += score * 0.4
        
        # 归一化
        if final_scores:
            max_score = max(final_scores.values())
            for intent in final_scores:
                final_scores[intent] = final_scores[intent] / max_score if max_score > 0 else 0
        
        # 确定主意图
        if final_scores:
            primary = max(final_scores, key=final_scores.get)
            confidence = final_scores[primary]
        else:
            primary = "factual"
            confidence = 0.5
        
        # 更新统计
        self.stats[primary] += 1
        
        return {
            "primary": primary,
            "confidence": confidence,
            "features": features,
            "all_intents": dict(final_scores),
            "pattern_matches": pattern_scores
        }
    
    def get_recommended_layers(self, intent: Dict) -> List[str]:
        """
        根据意图推荐检索层级
        
        Args:
            intent: 分类结果
            
        Returns:
            推荐的层级列表
        """
        primary = intent["primary"]
        confidence = intent["confidence"]
        
        # 默认层级
        default_layers = ["exact_cache", "session_cache", "knowledge_base", "database"]
        
        if primary == "factual":
            return ["exact_cache", "knowledge_base", "database"]
        
        elif primary == "conversational":
            return ["exact_cache", "session_cache", "knowledge_base"]
        
        elif primary == "procedural":
            return ["exact_cache", "knowledge_base"]
        
        elif primary == "creative":
            return ["exact_cache", "session_cache"]  # 主要依赖生成
        
        return default_layers
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = sum(self.stats.values())
        
        return {
            "total_classifications": total,
            "intent_distribution": dict(self.stats),
            "intent_percentages": {
                k: v / total * 100 if total > 0 else 0
                for k, v in self.stats.items()
            }
        }
