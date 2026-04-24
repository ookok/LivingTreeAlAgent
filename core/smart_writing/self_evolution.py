# -*- coding: utf-8 -*-
"""
智能写作自进化引擎 - Smart Writing Self-Evolution Engine
========================================================

核心功能：
1. 文档生成经验自动积累到知识库
2. 实时检索相关参考文档
3. 专家反馈转化为系统能力
4. 新模板模式自动识别入库

复用系统：
- SkillEvolutionAgent (技能自进化)
- ExpertPanel (专家反馈)
- KnowledgeBaseVectorStore (知识存储)
- WikiGenerator (深度搜索)
- ExpertTrainingPipeline (专家训练)

Author: Hermes Desktop Team
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import json

logger = logging.getLogger(__name__)


@dataclass
class EvolutionMetrics:
    """进化指标"""
    total_generations: int = 0
    successful_generations: int = 0
    expert_feedback_count: int = 0
    pattern_discoveries: int = 0
    template_creations: int = 0
    average_quality_score: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "total_generations": self.total_generations,
            "successful_generations": self.successful_generations,
            "expert_feedback_count": self.expert_feedback_count,
            "pattern_discoveries": self.pattern_discoveries,
            "template_creations": self.template_creations,
            "average_quality_score": round(self.average_quality_score, 2),
        }


class SmartWritingEvolutionEngine:
    """
    智能写作自进化引擎
    
    核心原理：
    每次文档生成后自动评估，优秀案例入库作为参考。
    专家反馈自动学习，形成新的写作模式。
    新文档类型自动识别入库，扩展系统能力。
    """
    
    def __init__(self):
        self.metrics = EvolutionMetrics()
        self._initialized = False
        self._patterns_cache: Dict[str, List[Dict]] = {}
        
    def initialize(self) -> bool:
        """初始化各组件连接"""
        if self._initialized:
            return True
            
        try:
            # 延迟导入避免循环依赖
            from core.knowledge_vector_db import KnowledgeBaseVectorStore
            from core.deep_search_wiki.wiki_generator import WikiGenerator
            from core.skill_evolution.agent_loop import SkillEvolutionAgent
            from expert_system.smart_expert import SmartExpert
            
            self._kb: Optional[KnowledgeBaseVectorStore] = None
            self._wiki: Optional[WikiGenerator] = None
            self._skill_agent: Optional[SkillEvolutionAgent] = None
            self._expert: Optional[SmartExpert] = None
            
            logger.info("自进化引擎组件已就绪")
            self._initialized = True
            return True
            
        except ImportError as e:
            logger.warning(f"部分组件未安装: {e}")
            self._initialized = True  # 允许降级运行
            return False
    
    def learn_from_generation(
        self,
        requirement: str,
        doc_type: str,
        content: str,
        quality_score: float = 0.0,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        从文档生成中学习
        
        Args:
            requirement: 原始需求
            doc_type: 文档类型
            content: 生成内容
            quality_score: 质量评分 (0-1)
            metadata: 额外元数据
        
        Returns:
            是否学习成功
        """
        if not self._initialized:
            self.initialize()
            
        self.metrics.total_generations += 1
        if quality_score >= 0.7:
            self.metrics.successful_generations += 1
            
        # 更新平均分
        n = self.metrics.total_generations
        self.metrics.average_quality_score = (
            (self.metrics.average_quality_score * (n - 1) + quality_score) / n
        )
        
        # 优秀案例入库
        if quality_score >= 0.8:
            self._store_excellent_case(requirement, doc_type, content, quality_score, metadata)
            
        # 提取并存储模式
        patterns = self._extract_patterns(requirement, doc_type, content)
        if patterns:
            self._store_patterns(doc_type, patterns)
            self.metrics.pattern_discoveries += len(patterns)
            
        # 通知技能进化系统
        self._notify_skill_system(requirement, doc_type, content, quality_score)
        
        logger.info(f"已学习: {doc_type}, 质量={quality_score:.2f}, 提取模式={len(patterns)}")
        return True
    
    def _store_excellent_case(
        self,
        requirement: str,
        doc_type: str,
        content: str,
        quality_score: float,
        metadata: Optional[Dict]
    ):
        """存储优秀案例到知识库"""
        if not hasattr(self, '_kb') or self._kb is None:
            return
            
        try:
            doc_id = hashlib.md5(f"{requirement}:{datetime.now().isoformat()}".encode()).hexdigest()[:12]
            
            # 构建知识条目
            kb_entry = {
                "id": doc_id,
                "type": "excellent_case",
                "doc_type": doc_type,
                "requirement": requirement,
                "content_summary": content[:500],  # 只存摘要
                "quality_score": quality_score,
                "created_at": datetime.now().isoformat(),
                "metadata": metadata or {},
            }
            
            # 存入向量知识库
            self._kb.add_document(
                text=requirement + "\n\n" + content[:2000],
                metadata=kb_entry
            )
            logger.debug(f"优秀案例已入库: {doc_id}")
            
        except Exception as e:
            logger.warning(f"存储优秀案例失败: {e}")
    
    def _extract_patterns(
        self,
        requirement: str,
        doc_type: str,
        content: str
    ) -> List[Dict]:
        """从内容中提取模式"""
        patterns = []
        
        # 提取章节结构模式
        sections = self._extract_sections(content)
        if sections:
            patterns.append({
                "pattern_type": "section_structure",
                "doc_type": doc_type,
                "sections": sections,
                "source": "auto_extract",
            })
            
        # 提取表格模式
        tables = self._extract_table_structures(content)
        for table in tables:
            patterns.append({
                "pattern_type": "table",
                "doc_type": doc_type,
                "table_info": table,
                "source": "auto_extract",
            })
            
        # 提取关键句模式
        key_phrases = self._extract_key_phrases(content)
        if key_phrases:
            patterns.append({
                "pattern_type": "key_phrases",
                "doc_type": doc_type,
                "phrases": key_phrases[:20],  # 最多20个
                "source": "auto_extract",
            })
            
        return patterns
    
    def _extract_sections(self, content: str) -> List[str]:
        """提取章节标题"""
        import re
        # 匹配常见标题格式
        patterns = [
            r'^第[一二三四五六七八九十\\d]+[章节部分][\\s　]+(.+)$',
            r'^(#{1,6})\\s+(.+)$',
            r'^(\\d+\\.\\d+[\\s　]+.+)$',
            r'^【(.+?)】$',
        ]
        
        sections = []
        for line in content.split('\\n'):
            line = line.strip()
            for pattern in patterns:
                match = re.match(pattern, line)
                if match:
                    title = match.group(1) if match.lastindex else match.group(0)
                    title = title.strip()
                    if 2 <= len(title) <= 50:
                        sections.append(title)
                    break
                    
        return sections
    
    def _extract_table_structures(self, content: str) -> List[Dict]:
        """提取表格结构"""
        import re
        tables = []
        
        # 简单Markdown表格检测
        lines = content.split('\\n')
        for i, line in enumerate(lines):
            if re.match(r'\\|.*\\|', line) and '---' not in line:
                # 可能是表格
                headers = [h.strip() for h in line.split('|') if h.strip()]
                if len(headers) >= 2:
                    tables.append({
                        "header_count": len(headers),
                        "headers": headers[:10],  # 最多10列
                        "line_index": i,
                    })
                    
        return tables
    
    def _extract_key_phrases(self, content: str) -> List[str]:
        """提取关键短语"""
        import re
        # 提取括号内内容
        phrases = re.findall(r'【(.+?)】', content)
        phrases += re.findall(r'《(.+?)》', content)
        phrases += re.findall(r'"([^"]{3,30})"', content)
        
        # 去除重复
        seen = set()
        unique = []
        for p in phrases:
            if p not in seen and len(p) >= 2:
                seen.add(p)
                unique.append(p)
                
        return unique
    
    def _store_patterns(self, doc_type: str, patterns: List[Dict]):
        """存储提取的模式"""
        if doc_type not in self._patterns_cache:
            self._patterns_cache[doc_type] = []
            
        self._patterns_cache[doc_type].extend(patterns)
        
        # 尝试存入知识库
        if hasattr(self, '_kb') and self._kb:
            try:
                for pattern in patterns:
                    self._kb.add_document(
                        text=f"{doc_type}: {json.dumps(pattern, ensure_ascii=False)}",
                        metadata={"type": "pattern", "doc_type": doc_type}
                    )
            except Exception as e:
                logger.debug(f"模式入库失败: {e}")
    
    def _notify_skill_system(self, requirement: str, doc_type: str, content: str, quality_score: float):
        """通知技能进化系统"""
        if not hasattr(self, '_skill_agent') or self._skill_agent is None:
            return
            
        try:
            # 优质文档可能形成新技能
            if quality_score >= 0.9:
                task_desc = f"高质量{doc_type}文档生成: {requirement[:100]}"
                # 异步触发技能评估（实际由SkillEvolutionAgent处理）
                logger.debug(f"触发技能评估: {task_desc}")
                
        except Exception as e:
            logger.debug(f"通知技能系统失败: {e}")
    
    def learn_from_expert_feedback(
        self,
        requirement: str,
        doc_type: str,
        feedback: str,
        suggested_changes: Optional[List[str]] = None
    ) -> bool:
        """
        从专家反馈中学习
        
        Args:
            requirement: 原始需求
            doc_type: 文档类型
            feedback: 专家反馈内容
            suggested_changes: 建议的修改项
        
        Returns:
            是否学习成功
        """
        self.metrics.expert_feedback_count += 1
        
        # 存入专家反馈库
        self._store_expert_feedback(requirement, doc_type, feedback, suggested_changes)
        
        # 提取专家知识
        expert_knowledge = self._extract_expert_knowledge(feedback, doc_type)
        if expert_knowledge:
            self._store_expert_knowledge(doc_type, expert_knowledge)
            
        logger.info(f"已学习专家反馈: {doc_type}, 反馈次数={self.metrics.expert_feedback_count}")
        return True
    
    def _store_expert_feedback(
        self,
        requirement: str,
        doc_type: str,
        feedback: str,
        suggested_changes: Optional[List[str]]
    ):
        """存储专家反馈"""
        if hasattr(self, '_expert') and self._expert:
            try:
                # 使用专家系统存储反馈
                self._expert.add_expert_feedback(
                    domain=doc_type,
                    feedback=feedback,
                    context={"requirement": requirement}
                )
            except Exception as e:
                logger.debug(f"专家反馈存储失败: {e}")
    
    def _extract_expert_knowledge(self, feedback: str, doc_type: str) -> Dict:
        """提取专家知识"""
        import re
        
        knowledge = {
            "corrections": [],
            "suggestions": [],
            "standards": [],
            "best_practices": [],
        }
        
        # 提取修正内容
        corrections = re.findall(r'[应该|需要|必须|应当]\\s*([^\n。]+)', feedback)
        knowledge["corrections"] = corrections[:5]
        
        # 提取建议
        suggestions = re.findall(r'建议[:：]\\s*([^\n]+)', feedback)
        knowledge["suggestions"] = suggestions[:5]
        
        # 提取标准引用
        standards = re.findall(r'(GB\\d+|HJ\\d+|AQ\\d+|YD\\d+)[^\n]*', feedback)
        knowledge["standards"] = standards[:10]
        
        # 提取最佳实践
        best_practices = re.findall(r'最佳[实践做法][:：]\\s*([^\n]+)', feedback)
        knowledge["best_practices"] = best_practices[:5]
        
        return knowledge
    
    def _store_expert_knowledge(self, doc_type: str, knowledge: Dict):
        """存储专家知识"""
        if hasattr(self, '_kb') and self._kb:
            try:
                text = f"专家知识-{doc_type}: {json.dumps(knowledge, ensure_ascii=False)}"
                self._kb.add_document(
                    text=text,
                    metadata={"type": "expert_knowledge", "doc_type": doc_type}
                )
                logger.debug(f"专家知识已入库: {doc_type}")
            except Exception as e:
                logger.debug(f"专家知识入库失败: {e}")
    
    def recognize_new_document_type(
        self,
        requirement: str,
        content: str,
        source: str = "user_upload"
    ) -> Optional[str]:
        """
        识别新文档类型并入库
        
        Args:
            requirement: 需求描述
            content: 文档内容
            source: 来源 (user_upload/ai_generated/manual)
        
        Returns:
            识别的类型名称，未识别则返回None
        """
        # 提取类型特征
        features = self._extract_type_features(requirement, content)
        
        # 生成类型标识
        type_id = self._generate_type_id(features)
        
        # 检查是否是新类型
        if type_id not in self._patterns_cache:
            self._register_new_type(type_id, features, source)
            self.metrics.template_creations += 1
            logger.info(f"发现新文档类型: {type_id}")
            return type_id
            
        return type_id
    
    def _extract_type_features(self, requirement: str, content: str) -> Dict:
        """提取类型特征"""
        import re
        
        # 统计内容特征
        word_count = len(content)
        para_count = content.count('\\n\\n') + 1
        table_count = content.count('|')
        header_count = len(re.findall(r'^#{1,6}\\s+', content, re.MULTILINE))
        calc_mentions = len(re.findall(r'计算|估算|分析|评估|评价', content))
        
        # 提取关键词
        keywords = []
        for kw in re.findall(r'[\\u4e00-\\u9fa5]{4,8}', requirement):
            if kw not in keywords:
                keywords.append(kw)
                
        return {
            "word_count_range": self._categorize_count(word_count),
            "para_count_range": self._categorize_count(para_count),
            "table_density": "high" if table_count > 10 else "medium" if table_count > 3 else "low",
            "header_count_range": self._categorize_count(header_count),
            "calculation_intensity": "high" if calc_mentions > 10 else "medium" if calc_mentions > 3 else "low",
            "keywords": keywords[:10],
        }
    
    def _categorize_count(self, count: int) -> str:
        """将数量分类"""
        if count <= 5:
            return "very_low"
        elif count <= 20:
            return "low"
        elif count <= 100:
            return "medium"
        elif count <= 500:
            return "high"
        else:
            return "very_high"
    
    def _generate_type_id(self, features: Dict) -> str:
        """生成类型标识"""
        # 基于特征生成ID
        key_parts = [
            features.get("table_density", "low"),
            features.get("calculation_intensity", "low"),
            features.get("word_count_range", "medium"),
        ]
        base_id = "_".join(key_parts)
        
        # 添加关键词哈希
        keywords = features.get("keywords", [])[:3]
        if keywords:
            kw_hash = hashlib.md5("".join(keywords).encode()).hexdigest()[:4]
            return f"custom_{base_id}_{kw_hash}"
        return f"custom_{base_id}"
    
    def _register_new_type(self, type_id: str, features: Dict, source: str):
        """注册新类型"""
        self._patterns_cache[type_id] = [{
            "type_id": type_id,
            "features": features,
            "source": source,
            "registered_at": datetime.now().isoformat(),
            "usage_count": 1,
        }]
        
        # 存入知识库
        if hasattr(self, '_kb') and self._kb:
            try:
                self._kb.add_document(
                    text=f"新文档类型: {type_id}\\n特征: {json.dumps(features, ensure_ascii=False)}",
                    metadata={"type": "document_type", "type_id": type_id}
                )
            except Exception as e:
                logger.debug(f"新类型入库失败: {e}")
    
    def get_reference_documents(
        self,
        requirement: str,
        doc_type: str,
        limit: int = 5
    ) -> List[Dict]:
        """
        获取参考文档
        
        Args:
            requirement: 当前需求
            doc_type: 文档类型
            limit: 返回数量
        
        Returns:
            参考文档列表
        """
        if not self._initialized:
            self.initialize()
            
        references = []
        
        # 1. 从知识库检索相似案例
        if hasattr(self, '_kb') and self._kb:
            try:
                results = self._kb.search(requirement, top_k=limit)
                for r in results:
                    references.append({
                        "source": "knowledge_base",
                        "type": r.metadata.get("type", "unknown"),
                        "score": r.score,
                        "content": r.text[:500],
                        "metadata": r.metadata,
                    })
            except Exception as e:
                logger.debug(f"知识库检索失败: {e}")
        
        # 2. 检索同类型模式
        patterns = self._patterns_cache.get(doc_type, [])
        for p in patterns[:limit]:
            references.append({
                "source": "pattern",
                "type": p.get("pattern_type", "unknown"),
                "content": json.dumps(p, ensure_ascii=False)[:500],
            })
        
        # 3. 深度搜索补充
        if hasattr(self, '_wiki') and self._wiki and len(references) < limit:
            try:
                wiki_results = self._wiki.generate_wiki(requirement, depth=1)
                for wr in wiki_results.get("chunks", [])[:limit - len(references)]:
                    references.append({
                        "source": "deep_search",
                        "type": "wiki",
                        "content": wr.get("text", "")[:500],
                    })
            except Exception as e:
                logger.debug(f"深度搜索失败: {e}")
                
        return references[:limit]
    
    def get_writing_guidance(
        self,
        doc_type: str,
        topic: str
    ) -> Dict[str, Any]:
        """
        获取写作指导
        
        Args:
            doc_type: 文档类型
            topic: 主题
        
        Returns:
            写作指导信息
        """
        guidance = {
            "doc_type": doc_type,
            "topic": topic,
            "sections": [],
            "key_points": [],
            "common_mistakes": [],
            "expert_tips": [],
            "reference_standards": [],
        }
        
        # 从模式中提取章节结构
        patterns = self._patterns_cache.get(doc_type, [])
        for p in patterns:
            if p.get("pattern_type") == "section_structure":
                guidance["sections"] = p.get("sections", [])
                
        # 从专家知识中提取建议
        if hasattr(self, '_expert') and self._expert:
            try:
                expert_kb = self._expert.get_knowledge_base(doc_type)
                if expert_kb:
                    guidance["expert_tips"] = expert_kb.get("best_practices", [])
                    guidance["reference_standards"] = expert_kb.get("standards", [])
            except Exception:
                pass
                
        # 添加常见错误
        guidance["common_mistakes"] = [
            "数据前后不一致",
            "缺少定量分析",
            "标准引用不规范",
            "结构逻辑不清晰",
        ]
        
        return guidance
    
    def get_metrics(self) -> Dict:
        """获取进化指标"""
        return self.metrics.to_dict()
    
    def get_learning_progress(self) -> Dict:
        """获取学习进度"""
        success_rate = (
            self.metrics.successful_generations / self.metrics.total_generations * 100
            if self.metrics.total_generations > 0 else 0
        )
        
        return {
            "total_generations": self.metrics.total_generations,
            "success_rate": f"{success_rate:.1f}%",
            "expert_feedbacks": self.metrics.expert_feedback_count,
            "patterns_learned": self.metrics.pattern_discoveries,
            "new_types_created": self.metrics.template_creations,
            "average_quality": f"{self.metrics.average_quality_score:.2f}",
            "knowledge_base_size": len(self._patterns_cache),
        }


# 全局实例
_evolution_engine: Optional[SmartWritingEvolutionEngine] = None


def get_evolution_engine() -> SmartWritingEvolutionEngine:
    """获取全局进化引擎实例"""
    global _evolution_engine
    if _evolution_engine is None:
        _evolution_engine = SmartWritingEvolutionEngine()
        _evolution_engine.initialize()
    return _evolution_engine


def quick_learn(
    requirement: str,
    doc_type: str,
    content: str,
    quality_score: float = 0.0
) -> bool:
    """快速学习接口"""
    engine = get_evolution_engine()
    return engine.learn_from_generation(requirement, doc_type, content, quality_score)


def quick_recognize(content: str) -> Optional[str]:
    """快速识别文档类型"""
    engine = get_evolution_engine()
    return engine.recognize_new_document_type("", content)
