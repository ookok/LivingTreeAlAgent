"""
通用知识发现引擎基类

所有领域知识发现引擎都应继承此类
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
import hashlib
import logging

logger = logging.getLogger(__name__)

# 导入 GlobalModelRouter（遵守系统架构设定）
try:
    from client.src.business.global_model_router import (
        RoutingStrategy
    )
    GLOBAL_ROUTER_AVAILABLE = True
except ImportError:
    GLOBAL_ROUTER_AVAILABLE = False
    RoutingStrategy = None


@dataclass
class KnowledgeDiscovery:
    """知识发现数据结构（通用）"""
    discovery_id: str
    discovery_type: str  # correlation, causation, optimization, trend, anomaly
    title: str
    description: str
    evidence: List[str]
    confidence: float  # 0-1
    novelty: float  # 0-1
    implications: List[str]
    domain: str = "general"  # 所属领域
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class KnowledgeDiscoveryEngine(ABC):
    """
    通用知识发现引擎基类
    
    所有领域特定的知识发现引擎都应继承此类
    """
    
    def __init__(self, domain_name: str, domain_keywords: List[str] = None):
        """
        初始化知识发现引擎
        
        Args:
            domain_name: 领域名称（如：environmental, medical, finance）
            domain_keywords: 领域关键词列表（用于判断是否适用于某领域）
        """
        self.domain_name = domain_name
        self.domain_keywords = domain_keywords or []
        logger.info(f"初始化领域知识发现引擎：{domain_name}")
    
    @abstractmethod
    def discover_knowledge(self, project_data: Dict) -> List[KnowledgeDiscovery]:
        """
        发现知识（由子类实现）
        
        Args:
            project_data: 项目数据（包含训练内容、领域信息等）
            
        Returns:
            知识发现列表
        """
        pass
    
    @abstractmethod
    def _extract_domain_features(self, training_content: str) -> Dict:
        """
        提取领域特征（由子类实现）
        
        Args:
            training_content: 训练内容
            
        Returns:
            领域特征字典
        """
        pass
    
    def can_handle(self, domain: str, training_content: str) -> float:
        """
        判断是否能处理该领域的知识发现
        
        Args:
            domain: 领域名称
            training_content: 训练内容（用于关键词匹配）
            
        Returns:
            匹配度分数（0-1）
        """
        # 1. 检查领域名称是否匹配
        if domain == self.domain_name:
            return 1.0
        
        # 2. 检查关键词匹配度
        if self.domain_keywords:
            content_lower = training_content.lower()
            matched_keywords = [kw for kw in self.domain_keywords if kw in content_lower]
            if matched_keywords:
                return len(matched_keywords) / len(self.domain_keywords)
        
        return 0.0
    
    def _generate_discovery_id(self, title: str, description: str) -> str:
        """生成知识发现ID"""
        content = f"{title}{description}{datetime.now().isoformat()}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    def _create_discovery(
        self,
        discovery_type: str,
        title: str,
        description: str,
        evidence: List[str],
        confidence: float,
        novelty: float,
        implications: List[str]
    ) -> KnowledgeDiscovery:
        """创建知识发现对象"""
        return KnowledgeDiscovery(
            discovery_id=self._generate_discovery_id(title, description),
            discovery_type=discovery_type,
            title=title,
            description=description,
            evidence=evidence,
            confidence=confidence,
            novelty=novelty,
            implications=implications,
            domain=self.domain_name
        )
    
    def _call_llm(self, prompt: str, system_prompt: str = "", 
                 capability_name: str = "knowledge_query") -> str:
        """
        使用 GlobalModelRouter 调用 LLM（同步）
        
        遵守系统架构设定：所有 LLM 调用都通过 GlobalModelRouter
        
        Args:
            prompt: 用户提示
            system_prompt: 系统提示
            capability_name: 能力名称（对应 ModelCapability 枚举）
            
        Returns:
            LLM 输出的文本
        """
        try:
            from client.src.business.global_model_router import (
                get_global_router,
                ModelCapability,
                call_model_sync,
                RoutingStrategy
            )
            
            # 将字符串转换为 ModelCapability 枚举
            try:
                capability = ModelCapability(capability_name)
            except ValueError:
                capability = ModelCapability.KNOWLEDGE_QUERY  # 默认能力
            
            # 使用同步方式调用 LLM
            response = call_model_sync(
                capability=capability,
                prompt=prompt,
                system_prompt=system_prompt,
                strategy=RoutingStrategy.QUALITY if GLOBAL_ROUTER_AVAILABLE else None,
                use_cache=True
            )
            
            return response or ""
            
        except ImportError:
            logger.warning("GlobalModelRouter 不可用，使用规则方法")
            return ""
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            return ""
    
    def discover_knowledge_with_llm(self, project_data: Dict) -> List[KnowledgeDiscovery]:
        """
        使用 LLM 增强的知识发现（同步版本）
        
        结合规则方法和 LLM 分析，产生更高质量的知识发现
        """
        # 1. 先使用规则方法（基础发现）
        rule_based_discoveries = self.discover_knowledge(project_data)
        
        # 2. 使用 LLM 增强分析
        training_content = project_data.get("training_content", "")
        if not training_content:
            return rule_based_discoveries
            
        # 构建 LLM 提示
        llm_prompt = f"""请分析以下训练内容，发现其中的知识模式、关联、趋势或异常。

训练内容：
---
{training_content[:2000]}  # 限制长度
---

请以 JSON 格式返回发现（最多 3 个）：
```json
[
  {{
    "discovery_type": "correlation|trend|anomaly",
    "title": "发现标题",
    "description": "详细描述",
    "confidence": 0.8,  // 0-1
    "novelty": 0.6,      // 0-1
    "implications": ["启示1", "启示2"]
  }}
]
```

只返回 JSON，不要其他解释。"""

        try:
            llm_response = self._call_llm(
                prompt=llm_prompt,
                system_prompt="你是一个知识发现助手。只输出 JSON，不要解释。",
                capability_name="knowledge_query"
            )
            
            if not llm_response:
                return rule_based_discoveries
                
            # 解析 LLM 响应
            import json
            import re
            
            # 提取 JSON
            json_match = re.search(r'\[.*\]', llm_response, re.DOTALL)
            if not json_match:
                return rule_based_discoveries
                
            llm_discoveries = json.loads(json_match.group(0))
            
            # 转换为 KnowledgeDiscovery 对象
            enhanced_discoveries = list(rule_based_discoveries)  # 复制规则发现
            
            for disc_dict in llm_discoveries:
                enhanced_discoveries.append(self._create_discovery(
                    discovery_type=disc_dict.get("discovery_type", "llm_enhanced"),
                    title=disc_dict.get("title", "LLM 发现"),
                    description=disc_dict.get("description", ""),
                    evidence=[f"LLM 分析训练内容"],
                    confidence=disc_dict.get("confidence", 0.5),
                    novelty=disc_dict.get("novelty", 0.5),
                    implications=disc_dict.get("implications", [])
                ))
                
            return enhanced_discoveries
            
        except Exception as e:
            logger.error(f"LLM 增强知识发现失败: {e}")
            return rule_based_discoveries


class GeneralKnowledgeDiscoveryEngine(KnowledgeDiscoveryEngine):
    """
    通用领域知识发现引擎
    
    使用 LLM 进行通用知识发现，不局限于特定领域。
    适用于：未找到专门领域引擎的场景。
    """
    
    def __init__(self):
        super().__init__(
            domain_name="general",
            domain_keywords=["分析", "研究", "发现", "规律", "趋势", "关联"]
        )
        logger.info("初始化通用知识发现引擎")
    
    def discover_knowledge(self, project_data: Dict) -> List[KnowledgeDiscovery]:
        """
        通用知识发现逻辑
        
        使用 LLM 分析项目数据，发现通用知识
        """
        discoveries = []
        
        # 从项目数据中提取关键信息
        training_content = project_data.get("training_content", "")
        domain = project_data.get("domain", "general")
        expert_name = project_data.get("expert_name", "")
        
        # 简单的规则发现（实际应使用 LLM）
        if training_content:
            # 发现1：关键词共现分析
            keywords = self._extract_keywords(training_content)
            if len(keywords) >= 2:
                discoveries.append(self._create_discovery(
                    discovery_type="co_occurrence",
                    title=f"发现关键词共现：{', '.join(keywords[:3])}",
                    description=f"在分析内容中发现多个关键词共同出现，可能存在关联",
                    evidence=[f"关键词：{', '.join(keywords)}", "文本内容分析"],
                    confidence=0.6,
                    novelty=0.5,
                    implications=["建议深入分析这些关键词的关联关系", "可能发现新的知识模式"]
                ))
            
            # 发现2：领域特征识别
            if domain != "general":
                discoveries.append(self._create_discovery(
                    discovery_type="domain_feature",
                    title=f"识别到{domain}领域特征",
                    description=f"根据分析，内容主要涉及{domain}领域",
                    evidence=[f"领域标签：{domain}", f"专家名称：{expert_name}"],
                    confidence=0.8,
                    novelty=0.3,
                    implications=[f"可以针对性地应用{domain}领域知识", "建议补充领域特定数据"]
                ))
        
        return discoveries
    
    def _extract_domain_features(self, training_content: str) -> Dict:
        """
        提取通用领域特征
        
        返回包含关键词、主题、实体等信息的字典
        """
        features = {
            "keywords": self._extract_keywords(training_content),
            "length": len(training_content),
            "language": "zh" if any('\u4e00' <= c <= '\u9fff' for c in training_content) else "en",
            "structure": self._analyze_structure(training_content)
        }
        return features
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词（简化实现）"""
        # 实际应使用 LLM 或 TF-IDF
        common_terms = ["分析", "研究", "方法", "技术", "系统", "设计", "实现", "优化", "管理", "控制"]
        found = []
        for term in common_terms:
            if term in text and len(found) < 5:
                found.append(term)
        return found
    
    def _analyze_structure(self, text: str) -> Dict:
        """分析文本结构"""
        return {
            "has_numbers": any(c.isdigit() for c in text),
            "has_english": any(c.isalpha() and ord(c) < 128 for c in text),
            "paragraph_count": text.count('\n\n') + 1
        }

