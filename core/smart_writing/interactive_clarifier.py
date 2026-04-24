# -*- coding: utf-8 -*-
"""
智能写作交互式澄清模块 - Interactive Clarifier Enhanced
=======================================================

增强功能：
1. 基于知识库动态生成问题
2. 根据历史案例智能补全
3. 与自进化引擎集成
4. 支持多轮渐进式澄清

复用模块：
- SmartWritingEvolutionEngine (自进化)
- KnowledgeBaseVectorStore (知识库)

Author: Hermes Desktop Team
"""

import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ClarifyStage(Enum):
    """澄清阶段"""
    INITIAL = "initial"           # 初始识别
    BASIC_INFO = "basic_info"     # 基本信息
    TECHNICAL = "technical"       # 技术细节
    DATA_REQUIREMENTS = "data"    # 数据需求
    STANDARDS = "standards"      # 标准规范
    COMPLETED = "completed"        # 完成


@dataclass
class ClarifyQuestion:
    """澄清问题"""
    field: str
    question: str
    hint: str = ""
    options: Optional[List[str]] = None
    required: bool = True
    auto_fill: bool = False  # 是否可自动填充
    depends_on: Optional[str] = None  # 依赖字段
    stage: ClarifyStage = ClarifyStage.BASIC_INFO


@dataclass
class ClarifyProgress:
    """澄清进度"""
    stage: ClarifyStage = ClarifyStage.INITIAL
    answered: Dict[str, Any] = field(default_factory=dict)
    pending: List[str] = field(default_factory=list)
    completed_fields: List[str] = field(default_factory=list)
    auto_filled: Dict[str, Any] = field(default_factory=dict)


class InteractiveClarifier:
    """
    交互式需求澄清器（增强版）
    
    使用示例：
    ```python
    clarifier = InteractiveClarifier()
    
    # 开始澄清流程
    session = clarifier.start_session(
        requirement="写一份武汉化工项目的可行性研究报告",
        doc_type="feasibility_report"
    )
    
    # 获取下一步问题
    questions = clarifier.get_next_questions(session)
    
    # 回答问题
    session = clarifier.answer(session, "investment", "5000万元")
    
    # 获取补充建议
    suggestions = clarifier.get_auto_suggestions(session)
    ```
    """
    
    def __init__(self):
        self._evolution_engine = None
        self._session_cache: Dict[str, ClarifyProgress] = {}
        
    @property
    def evolution_engine(self):
        """延迟加载自进化引擎"""
        if self._evolution_engine is None:
            try:
                from core.smart_writing.self_evolution import get_evolution_engine
                self._evolution_engine = get_evolution_engine()
            except ImportError:
                logger.warning("自进化引擎未安装")
        return self._evolution_engine
    
    def start_session(
        self,
        requirement: str,
        doc_type: str,
        existing_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        开始澄清会话
        
        Args:
            requirement: 原始需求
            doc_type: 文档类型
            existing_data: 已有的数据
        
        Returns:
            会话状态
        """
        import uuid
        
        session_id = uuid.uuid4().hex[:8]
        
        # 初始化进度
        progress = ClarifyProgress()
        progress.stage = ClarifyStage.INITIAL
        
        # 从已有数据初始化
        if existing_data:
            progress.answered = existing_data.copy()
            progress.completed_fields = list(existing_data.keys())
            
        # 存储会话
        self._session_cache[session_id] = progress
        
        # 生成基础问题
        questions = self._generate_base_questions(doc_type, requirement)
        progress.pending = [q.field for q in questions if q.required and not q.auto_fill]
        
        # 尝试自动填充
        auto_filled = self._try_auto_fill(doc_type, requirement)
        for field, value in auto_filled.items():
            if field not in progress.answered:
                progress.auto_filled[field] = value
                
        progress.stage = ClarifyStage.BASIC_INFO
        
        return {
            "session_id": session_id,
            "doc_type": doc_type,
            "requirement": requirement,
            "stage": progress.stage.value,
            "questions": [
                {
                    "field": q.field,
                    "question": q.question,
                    "hint": q.hint,
                    "options": q.options,
                    "required": q.required,
                    "auto_filled": field in progress.auto_filled,
                }
                for q in questions
            ],
            "auto_filled": progress.auto_filled,
            "progress": self._calculate_progress(progress),
        }
    
    def _generate_base_questions(self, doc_type: str, requirement: str) -> List[ClarifyQuestion]:
        """生成基础问题列表"""
        questions = []
        
        # 通用基础问题
        questions.extend([
            ClarifyQuestion(
                field="project_name",
                question="项目名称是什么？",
                hint="请输入完整的项目名称",
                stage=ClarifyStage.BASIC_INFO,
            ),
            ClarifyQuestion(
                field="location",
                question="项目地点在哪里？",
                hint="如：湖北省武汉市",
                stage=ClarifyStage.BASIC_INFO,
            ),
        ])
        
        # 根据文档类型添加特定问题
        if "可行性" in doc_type or "feasibility" in doc_type.lower():
            questions.extend([
                ClarifyQuestion(
                    field="investment",
                    question="预计投资金额是多少？",
                    hint="单位：万元",
                    stage=ClarifyStage.BASIC_INFO,
                ),
                ClarifyQuestion(
                    field="construction_period",
                    question="预计建设周期是多久？",
                    hint="如：18个月",
                    stage=ClarifyStage.TECHNICAL,
                ),
                ClarifyQuestion(
                    field="capacity",
                    question="预计产能规模是多少？",
                    hint="如：年产10万吨",
                    stage=ClarifyStage.TECHNICAL,
                ),
            ])
            
        elif "环境" in doc_type or "eia" in doc_type.lower():
            questions.extend([
                ClarifyQuestion(
                    field="industry_type",
                    question="所属行业类型是什么？",
                    options=["化工", "制药", "电子", "造纸", "其他"],
                    stage=ClarifyStage.TECHNICAL,
                ),
                ClarifyQuestion(
                    field="pollutants",
                    question="主要污染物种类？",
                    options=["废气", "废水", "固废", "噪声"],
                    stage=ClarifyStage.TECHNICAL,
                ),
                ClarifyQuestion(
                    field="sensitive_targets",
                    question="周边有哪些敏感目标？",
                    hint="如：居民区、学校、医院",
                    stage=ClarifyStage.TECHNICAL,
                ),
            ])
            
        elif "安全" in doc_type or "safety" in doc_type.lower():
            questions.extend([
                ClarifyQuestion(
                    field="major_hazards",
                    question="涉及哪些重大危险源？",
                    options=["易燃易爆", "有毒有害", "高温高压", "其他"],
                    stage=ClarifyStage.TECHNICAL,
                ),
                ClarifyQuestion(
                    field="accident_history",
                    question="近5年有无安全事故记录？",
                    options=["无", "有，但已整改", "有，正在整改"],
                    stage=ClarifyStage.TECHNICAL,
                ),
            ])
        
        # 数据需求问题
        questions.extend([
            ClarifyQuestion(
                field="need_calculation",
                question="是否需要进行财务/环境计算？",
                options=["是", "否"],
                required=False,
                stage=ClarifyStage.DATA_REQUIREMENTS,
            ),
            ClarifyQuestion(
                field="reference_standards",
                question="需要引用的标准规范？",
                hint="如：GB 3095-2012",
                required=False,
                auto_fill=True,
                stage=ClarifyStage.STANDARDS,
            ),
        ])
        
        return questions
    
    def _try_auto_fill(self, doc_type: str, requirement: str) -> Dict[str, Any]:
        """尝试自动填充字段"""
        auto_filled = {}
        
        # 1. 从知识库检索相似案例
        if self.evolution_engine:
            try:
                refs = self.evolution_engine.get_reference_documents(
                    requirement, doc_type, limit=3
                )
                for ref in refs:
                    meta = ref.get("metadata", {})
                    if "investment" in meta and "investment" not in auto_filled:
                        auto_filled["investment"] = meta["investment"]
                    if "location" in meta and "location" not in auto_filled:
                        auto_filled["location"] = meta["location"]
            except Exception as e:
                logger.debug(f"自动填充失败: {e}")
                
        # 2. 从需求中提取
        import re
        
        # 提取地点
        locations = re.findall(r'[省市县区]([^省市县区]+(?:市|县|区))', requirement)
        if locations:
            auto_filled["location"] = locations[0]
            
        # 提取金额
        amounts = re.findall(r'(\\d+(?:,\\d{3})*(?:\\.\\d+)?)\\s*(?:万|亿)?\\s*元', requirement)
        if amounts:
            auto_filled["investment"] = amounts[0]
            
        # 提取时间
        periods = re.findall(r'(\\d+)\\s*(?:个)?月', requirement)
        if periods:
            auto_filled["construction_period"] = f"{periods[0]}个月"
            
        return auto_filled
    
    def get_next_questions(
        self,
        session: Dict[str, Any],
        answered_field: Optional[str] = None
    ) -> List[Dict]:
        """
        获取下一步需要回答的问题
        
        Args:
            session: 会话状态
            answered_field: 已回答的字段（触发后续问题）
        
        Returns:
            问题列表
        """
        session_id = session.get("session_id")
        if not session_id or session_id not in self._session_cache:
            return []
            
        progress = self._session_cache[session_id]
        current_stage = ClarifyStage(progress.stage)
        
        # 根据当前阶段返回问题
        all_questions = self._generate_base_questions(
            session.get("doc_type", ""),
            session.get("requirement", "")
        )
        
        # 过滤已回答的问题
        pending_questions = [
            q for q in all_questions
            if q.field not in progress.answered
            and (not q.depends_on or q.depends_on in progress.answered)
        ]
        
        # 按阶段排序
        stage_order = [
            ClarifyStage.BASIC_INFO,
            ClarifyStage.TECHNICAL,
            ClarifyStage.DATA_REQUIREMENTS,
            ClarifyStage.STANDARDS,
        ]
        
        def stage_priority(q: ClarifyQuestion) -> int:
            try:
                return stage_order.index(q.stage)
            except ValueError:
                return len(stage_order)
                
        pending_questions.sort(key=stage_priority)
        
        return [
            {
                "field": q.field,
                "question": q.question,
                "hint": q.hint,
                "options": q.options,
                "required": q.required,
                "auto_filled": q.field in progress.auto_filled,
                "auto_value": progress.auto_filled.get(q.field),
            }
            for q in pending_questions[:5]  # 每次最多5个问题
        ]
    
    def answer(
        self,
        session: Dict[str, Any],
        field: str,
        value: Any
    ) -> Dict[str, Any]:
        """
        回答问题
        
        Args:
            session: 会话状态
            field: 字段名
            value: 回答值
        
        Returns:
            更新后的会话状态
        """
        session_id = session.get("session_id")
        if not session_id or session_id not in self._session_cache:
            return session
            
        progress = self._session_cache[session_id]
        
        # 记录回答
        progress.answered[field] = value
        if field not in progress.completed_fields:
            progress.completed_fields.append(field)
            
        # 移除待处理
        if field in progress.pending:
            progress.pending.remove(field)
            
        # 更新阶段
        questions = self._generate_base_questions(
            session.get("doc_type", ""),
            session.get("requirement", "")
        )
        
        completed_stages = set()
        for q in questions:
            if q.field in progress.answered:
                completed_stages.add(q.stage)
                
        if ClarifyStage.STANDARDS in completed_stages:
            progress.stage = ClarifyStage.COMPLETED
        elif ClarifyStage.DATA_REQUIREMENTS in completed_stages:
            progress.stage = ClarifyStage.STANDARDS
        elif ClarifyStage.TECHNICAL in completed_stages:
            progress.stage = ClarifyStage.DATA_REQUIREMENTS
        elif ClarifyStage.BASIC_INFO in completed_stages:
            progress.stage = ClarifyStage.TECHNICAL
            
        # 更新会话
        session["answered"] = progress.answered
        session["stage"] = progress.stage.value
        session["progress"] = self._calculate_progress(progress)
        
        return session
    
    def get_auto_suggestions(self, session: Dict[str, Any]) -> List[Dict]:
        """
        获取自动补全建议
        
        Returns:
            建议列表
        """
        suggestions = []
        session_id = session.get("session_id")
        
        if not session_id or session_id not in self._session_cache:
            return suggestions
            
        progress = self._session_cache[session_id]
        answered = progress.answered
        
        # 1. 从进化引擎获取参考
        if self.evolution_engine:
            try:
                refs = self.evolution_engine.get_reference_documents(
                    session.get("requirement", ""),
                    session.get("doc_type", ""),
                    limit=3
                )
                for ref in refs:
                    suggestions.append({
                        "type": "reference",
                        "title": f"参考案例 (相似度: {ref.get('score', 0):.2f})",
                        "content": ref.get("content", "")[:200],
                    })
            except Exception:
                pass
                
        # 2. 从已有数据推断建议
        if "industry_type" in answered and "location" in answered:
            # 可以添加行业特定建议
            suggestions.append({
                "type": "inference",
                "title": "基于行业和地点的建议",
                "content": f"根据{answered['industry_type']}行业特点，建议关注当地环保要求。",
            })
            
        # 3. 写作指导
        if self.evolution_engine:
            try:
                guidance = self.evolution_engine.get_writing_guidance(
                    session.get("doc_type", ""),
                    session.get("requirement", "")
                )
                if guidance.get("sections"):
                    suggestions.append({
                        "type": "structure",
                        "title": "建议文档结构",
                        "content": " > ".join(guidance["sections"][:5]),
                    })
            except Exception:
                pass
                
        return suggestions
    
    def complete_session(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """
        完成澄清会话，输出完整需求
        
        Args:
            session: 会话状态
        
        Returns:
            完整的需求信息
        """
        session_id = session.get("session_id")
        if not session_id or session_id not in self._session_cache:
            return session
            
        progress = self._session_cache[session_id]
        
        # 合并自动填充和用户输入
        final_data = {}
        final_data.update(progress.auto_filled)
        final_data.update(progress.answered)
        
        # 添加缺失字段的默认值
        questions = self._generate_base_questions(
            session.get("doc_type", ""),
            session.get("requirement", "")
        )
        
        for q in questions:
            if q.field not in final_data and q.auto_fill:
                # 使用默认值
                if q.options:
                    final_data[q.field] = q.options[0]
                else:
                    final_data[q.field] = "未指定"
                    
        # 记录到进化引擎
        if self.evolution_engine:
            try:
                self.evolution_engine.learn_from_generation(
                    requirement=session.get("requirement", ""),
                    doc_type=session.get("doc_type", ""),
                    content=json.dumps(final_data, ensure_ascii=False),
                    quality_score=0.7,
                    metadata=final_data
                )
            except Exception as e:
                logger.debug(f"学习失败: {e}")
                
        # 清理会话
        del self._session_cache[session_id]
        
        return {
            "session_id": session_id,
            "requirement": session.get("requirement"),
            "doc_type": session.get("doc_type"),
            "data": final_data,
            "completeness": self._calculate_completeness(final_data, questions),
        }
    
    def _calculate_progress(self, progress: ClarifyProgress) -> Dict:
        """计算澄清进度"""
        total = len(progress.completed_fields) + len(progress.pending)
        completed = len(progress.completed_fields)
        
        return {
            "completed": completed,
            "pending": len(progress.pending),
            "total": total,
            "percentage": int(completed / total * 100) if total > 0 else 0,
            "auto_filled": len(progress.auto_filled),
        }
    
    def _calculate_completeness(
        self,
        data: Dict,
        questions: List[ClarifyQuestion]
    ) -> Dict:
        """计算数据完整度"""
        required_fields = [q.field for q in questions if q.required]
        filled_required = [f for f in required_fields if f in data and data[f]]
        optional_fields = [q.field for q in questions if not q.required]
        filled_optional = [f for f in optional_fields if f in data and data[f]]
        
        required_score = len(filled_required) / len(required_fields) if required_fields else 1.0
        optional_score = len(filled_optional) / len(optional_fields) if optional_fields else 1.0
        
        return {
            "required_complete": len(filled_required),
            "required_total": len(required_fields),
            "optional_complete": len(filled_optional),
            "optional_total": len(optional_fields),
            "overall_score": round(required_score * 0.7 + optional_score * 0.3, 2),
            "missing_required": [f for f in required_fields if f not in data or not data[f]],
        }


import json


# 全局实例
_clarifier: Optional[InteractiveClarifier] = None


def get_clarifier() -> InteractiveClarifier:
    """获取全局澄清器实例"""
    global _clarifier
    if _clarifier is None:
        _clarifier = InteractiveClarifier()
    return _clarifier


def quick_clarify(requirement: str, doc_type: str) -> Dict[str, Any]:
    """快速澄清接口"""
    clarifier = get_clarifier()
    session = clarifier.start_session(requirement, doc_type)
    return clarifier.complete_session(session)
