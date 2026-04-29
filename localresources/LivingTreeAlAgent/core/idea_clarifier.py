"""
需求头脑风暴系统
IdeaClarifier - 将模糊需求转化为清晰的设计规格

核心设计理念（借鉴 obra/superpowers brainstorming）：
1. HARD-GATE：禁止在用户批准设计前执行任何实现
2. 一次一问：减少认知负担
3. 多选优先：提供选项而非开放问题
4. 逐段展示：每段获取用户批准
5. 方案权衡：提供 2-3 种方案并推荐
"""

import uuid
import json
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ClarifyPhase(Enum):
    """澄清阶段"""
    CONTEXT = "context"           # 探索上下文
    PURPOSE = "purpose"           # 明确目的
    CONSTRAINTS = "constraints"   # 识别约束
    SUCCESS_CRITERIA = "success"  # 成功标准
    ALTERNATIVES = "alternatives"  # 方案探索
    DESIGN = "design"             # 方案设计
    REVIEW = "review"            # 规格审核
    APPROVED = "approved"         # 已批准
    CANCELLED = "cancelled"      # 已取消


class QuestionType(Enum):
    """问题类型"""
    OPEN = "open"                # 开放式
    MULTIPLE_CHOICE = "choice"   # 多选
    YES_NO = "yesno"             # 是/否
    SCALE = "scale"              # 量表


@dataclass
class ClarifyQuestion:
    """澄清问题"""
    question_id: str
    phase: ClarifyPhase
    question_type: QuestionType
    text: str
    options: List[str] = field(default_factory=list)
    hint: str = ""
    required: bool = True
    answered: bool = False
    answer: Optional[Any] = None


@dataclass
class DesignOption:
    """设计方案"""
    option_id: str
    name: str
    description: str
    pros: List[str] = field(default_factory=list)
    cons: List[str] = field(default_factory=list)
    complexity: str = "medium"  # low/medium/high
    recommended: bool = False


@dataclass
class DesignSection:
    """设计段落"""
    section_id: str
    title: str
    content: str = ""
    approved: bool = False


@dataclass
class ClarifySession:
    """头脑风暴会话"""
    session_id: str
    topic: str
    created_at: datetime
    phase: ClarifyPhase = ClarifyPhase.CONTEXT
    
    questions: List[ClarifyQuestion] = field(default_factory=list)
    answers: Dict[str, Any] = field(default_factory=dict)
    
    design_options: List[DesignOption] = field(default_factory=list)
    selected_option: Optional[str] = None
    
    design_sections: List[DesignSection] = field(default_factory=list)
    
    notes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "topic": self.topic,
            "created_at": self.created_at.isoformat(),
            "phase": self.phase.value,
            "answers": self.answers,
            "selected_option": self.selected_option,
            "design_options": [
                {
                    "option_id": o.option_id,
                    "name": o.name,
                    "description": o.description,
                    "pros": o.pros,
                    "cons": o.cons,
                    "complexity": o.complexity,
                    "recommended": o.recommended
                } for o in self.design_options
            ],
            "design_sections": [
                {
                    "section_id": s.section_id,
                    "title": s.title,
                    "content": s.content,
                    "approved": s.approved
                } for s in self.design_sections
            ],
            "notes": self.notes
        }


class IdeaClarifier:
    """
    需求澄清器 - 引导用户将模糊想法转化为清晰设计
    
    工作流程：
    1. Context: 探索项目上下文
    2. Purpose: 明确核心目的
    3. Constraints: 识别约束条件
    4. Success: 定义成功标准
    5. Alternatives: 探索替代方案
    6. Design: 逐段展示设计
    7. Review: 审核规格
    8. Approved: 获得批准
    """
    
    def __init__(self):
        self._sessions: Dict[str, ClarifySession] = {}
        self._current_session: Optional[ClarifySession] = None
        self._question_templates = self._init_question_templates()
    
    def _init_question_templates(self) -> Dict[ClarifyPhase, List[Dict]]:
        """初始化问题模板"""
        return {
            ClarifyPhase.CONTEXT: [
                {
                    "phase": ClarifyPhase.CONTEXT,
                    "question_type": QuestionType.OPEN,
                    "text": "请用一句话描述你想要实现的功能或解决什么问题？",
                    "hint": "例如：我想做一个待办事项提醒功能",
                    "required": True
                }
            ],
            ClarifyPhase.PURPOSE: [
                {
                    "phase": ClarifyPhase.PURPOSE,
                    "question_type": QuestionType.MULTIPLE_CHOICE,
                    "text": "这个功能的核心目的是什么？",
                    "options": [
                        "提高效率 - 自动化重复性工作",
                        "解决问题 - 解决现有流程中的痛点",
                        "探索创新 - 尝试新的可能性",
                        "改进体验 - 优化现有的用户体验"
                    ],
                    "required": True
                },
                {
                    "phase": ClarifyPhase.PURPOSE,
                    "question_type": QuestionType.OPEN,
                    "text": "这个功能为谁服务？他们有什么特点？",
                    "hint": "考虑目标用户的技能水平、使用场景等",
                    "required": True
                }
            ],
            ClarifyPhase.CONSTRAINTS: [
                {
                    "phase": ClarifyPhase.CONSTRAINTS,
                    "question_type": QuestionType.MULTIPLE_CHOICE,
                    "text": "有什么技术限制需要考虑？",
                    "options": [
                        "性能要求 - 需要快速响应",
                        "兼容性 - 需要支持特定平台/浏览器",
                        "安全性 - 需要处理敏感数据",
                        "无特殊限制"
                    ],
                    "required": False
                },
                {
                    "phase": ClarifyPhase.CONSTRAINTS,
                    "question_type": QuestionType.MULTIPLE_CHOICE,
                    "text": "项目的时间要求？",
                    "options": [
                        "紧急 - 希望尽快完成",
                        "正常 - 有合理的开发周期",
                        "宽松 - 质量优先，不着急"
                    ],
                    "required": True
                }
            ],
            ClarifyPhase.SUCCESS_CRITERIA: [
                {
                    "phase": ClarifyPhase.SUCCESS_CRITERIA,
                    "question_type": QuestionType.MULTIPLE_CHOICE,
                    "text": "如何判断这个功能成功了？",
                    "options": [
                        "功能完整性 - 所有计划的功能都能正常工作",
                        "性能指标 - 达到特定的性能目标",
                        "用户反馈 - 用户满意度达到某个水平",
                        "业务指标 - 带来可衡量的业务价值"
                    ],
                    "required": True
                },
                {
                    "phase": ClarifyPhase.SUCCESS_CRITERIA,
                    "question_type": QuestionType.SCALE,
                    "text": "功能完成后，你希望它达到什么质量水平？",
                    "options": ["MVP - 能用就行", "Production - 生产可用", "Polish - 精致打磨"],
                    "required": True
                }
            ]
        }
    
    def start_session(self, topic: str) -> ClarifySession:
        """开始新的头脑风暴会话"""
        session_id = str(uuid.uuid4())
        session = ClarifySession(
            session_id=session_id,
            topic=topic,
            created_at=datetime.now(),
            phase=ClarifyPhase.CONTEXT
        )
        
        self._sessions[session_id] = session
        self._current_session = session
        
        # 初始化第一阶段问题
        self._init_questions_for_phase(session, ClarifyPhase.CONTEXT)
        
        logger.info(f"Started brainstorm session: {session_id}, topic: {topic}")
        return session
    
    def _init_questions_for_phase(self, session: ClarifySession, phase: ClarifyPhase):
        """为指定阶段初始化问题"""
        templates = self._question_templates.get(phase, [])
        
        for i, template in enumerate(templates):
            question = ClarifyQuestion(
                question_id=f"{session.session_id}_{phase.value}_{i}",
                phase=phase,
                question_type=QuestionType(template["question_type"].value),
                text=template["text"],
                options=template.get("options", []),
                hint=template.get("hint", ""),
                required=template.get("required", True)
            )
            session.questions.append(question)
    
    def get_current_question(self, session_id: str) -> Optional[ClarifyQuestion]:
        """获取当前需要回答的问题"""
        session = self._sessions.get(session_id)
        if not session:
            return None
        
        # 找到下一个未回答的必要问题
        for question in session.questions:
            if question.required and not question.answered:
                return question
        
        return None
    
    def answer_question(self, session_id: str, question_id: str, answer: Any) -> Dict[str, Any]:
        """回答问题"""
        session = self._sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}
        
        # 找到问题并记录答案
        for question in session.questions:
            if question.question_id == question_id:
                question.answered = True
                question.answer = answer
                session.answers[question_id] = answer
                break
        
        # 检查是否需要进入下一阶段
        return self._check_phase_transition(session)
    
    def _check_phase_transition(self, session: ClarifySession) -> Dict[str, Any]:
        """检查是否需要进入下一阶段"""
        phase_order = [
            ClarifyPhase.CONTEXT,
            ClarifyPhase.PURPOSE,
            ClarifyPhase.CONSTRAINTS,
            ClarifyPhase.SUCCESS_CRITERIA,
            ClarifyPhase.ALTERNATIVES,
            ClarifyPhase.DESIGN,
            ClarifyPhase.REVIEW
        ]
        
        current_idx = phase_order.index(session.phase)
        
        # 检查当前阶段是否完成
        current_phase_questions = [q for q in session.questions if q.phase == session.phase]
        required_questions = [q for q in current_phase_questions if q.required]
        all_required_answered = all(q.answered for q in required_questions)
        
        if all_required_answered:
            # 进入下一阶段
            if current_idx < len(phase_order) - 1:
                next_phase = phase_order[current_idx + 1]
                return self._transition_to_phase(session, next_phase)
            else:
                # 已完成所有阶段
                session.phase = ClarifyPhase.APPROVED
                return {
                    "transition": True,
                    "next_phase": "completed",
                    "message": "所有阶段已完成"
                }
        
        return {
            "transition": False,
            "next_question": self.get_current_question(session.session_id)
        }
    
    def _transition_to_phase(self, session: ClarifySession, phase: ClarifyPhase) -> Dict[str, Any]:
        """切换到指定阶段"""
        old_phase = session.phase
        session.phase = phase
        
        logger.info(f"Session {session.session_id} transitioned: {old_phase.value} -> {phase.value}")
        
        if phase == ClarifyPhase.ALTERNATIVES:
            # 生成方案选项
            self._generate_design_options(session)
            return {
                "transition": True,
                "next_phase": phase.value,
                "design_options": session.design_options,
                "message": "基于你的需求，我准备了几个方案供你选择"
            }
        
        elif phase == ClarifyPhase.DESIGN:
            # 生成设计方案
            self._generate_design_sections(session)
            return {
                "transition": True,
                "next_phase": phase.value,
                "design_sections": session.design_sections,
                "message": "设计文档已生成，请逐段审核"
            }
        
        elif phase == ClarifyPhase.REVIEW:
            return {
                "transition": True,
                "next_phase": phase.value,
                "message": "请审核完整的设计规格文档"
            }
        
        elif phase == ClarifyPhase.APPROVED:
            return {
                "transition": True,
                "next_phase": phase.value,
                "message": "设计已批准，可以开始实现了"
            }
        
        # 为新阶段初始化问题
        if phase in self._question_templates:
            self._init_questions_for_phase(session, phase)
        
        next_question = self.get_current_question(session.session_id)
        return {
            "transition": True,
            "next_phase": phase.value,
            "next_question": next_question,
            "message": f"已从 {old_phase.value} 阶段进入 {phase.value} 阶段"
        }
    
    def _generate_design_options(self, session: ClarifySession) -> List[DesignOption]:
        """基于用户需求生成方案选项"""
        topic = session.topic
        answers = session.answers
        
        # 根据目的类型生成不同方案
        purpose_type = None
        for q in session.questions:
            if q.phase == ClarifyPhase.PURPOSE and q.answer:
                purpose_type = q.answer
                break
        
        # 生成3种方案
        session.design_options = [
            DesignOption(
                option_id="simple",
                name="简洁方案",
                description=f"快速实现 {topic} 的核心功能，采用最小化设计",
                pros=["开发周期短", "易于维护", "风险低"],
                cons=["功能有限", "可能需要后续扩展"],
                complexity="low",
                recommended=True
            ),
            DesignOption(
                option_id="balanced",
                name="平衡方案",
                description=f"在功能和复杂性之间取得平衡的 {topic} 实现",
                pros=["功能完整", "可扩展性", "代码质量高"],
                cons=["开发周期中等", "需要更多设计"],
                complexity="medium",
                recommended=False
            ),
            DesignOption(
                option_id="full",
                name="完整方案",
                description=f"为 {topic} 提供完整功能的实现，包括所有边缘情况",
                pros=["功能最全面", "用户体验最佳", "可扩展性强"],
                cons=["开发周期长", "复杂性高", "维护成本高"],
                complexity="high",
                recommended=False
            )
        ]
        
        return session.design_options
    
    def select_option(self, session_id: str, option_id: str) -> Dict[str, Any]:
        """选择方案"""
        session = self._sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}
        
        session.selected_option = option_id
        
        # 进入设计阶段
        return self._transition_to_phase(session, ClarifyPhase.DESIGN)
    
    def _generate_design_sections(self, session: ClarifySession) -> List[DesignSection]:
        """生成设计段落"""
        topic = session.topic
        option = session.selected_option or "balanced"
        
        # 根据方案类型调整设计复杂度
        complexity_map = {
            "simple": ["概述", "核心功能", "数据模型", "接口设计"],
            "balanced": ["概述", "核心功能", "数据模型", "接口设计", "错误处理", "扩展点"],
            "full": ["概述", "核心功能", "数据模型", "接口设计", "错误处理", "扩展点", "性能优化", "安全考虑"]
        }
        
        section_titles = complexity_map.get(option, complexity_map["balanced"])
        
        # 生成设计段落
        for i, title in enumerate(section_titles):
            section = DesignSection(
                section_id=f"sec_{i}",
                title=title,
                content=f"[自动生成 {title} 的设计内容]"
            )
            session.design_sections.append(section)
        
        return session.design_sections
    
    def update_section(self, session_id: str, section_id: str, content: str) -> Dict[str, Any]:
        """更新设计段落内容"""
        session = self._sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}
        
        for section in session.design_sections:
            if section.section_id == section_id:
                section.content = content
                break
        
        return {"success": True, "section_id": section_id}
    
    def approve_section(self, session_id: str, section_id: str) -> Dict[str, Any]:
        """批准设计段落"""
        session = self._sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}
        
        for section in session.design_sections:
            if section.section_id == section_id:
                section.approved = True
                break
        
        # 检查是否所有段落都已批准
        all_approved = all(s.approved for s in session.design_sections)
        if all_approved:
            return self._transition_to_phase(session, ClarifyPhase.REVIEW)
        
        return {
            "success": True,
            "approved_section": section_id,
            "remaining": [s.section_id for s in session.design_sections if not s.approved]
        }
    
    def approve_design(self, session_id: str) -> Dict[str, Any]:
        """最终批准设计"""
        session = self._sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}
        
        # 批准所有未批准段落
        for section in session.design_sections:
            section.approved = True
        
        return self._transition_to_phase(session, ClarifyPhase.APPROVED)
    
    def cancel_session(self, session_id: str) -> bool:
        """取消会话"""
        session = self._sessions.get(session_id)
        if session:
            session.phase = ClarifyPhase.CANCELLED
            if self._current_session and self._current_session.session_id == session_id:
                self._current_session = None
            return True
        return False
    
    def get_session(self, session_id: str) -> Optional[ClarifySession]:
        """获取会话"""
        return self._sessions.get(session_id)
    
    def get_all_sessions(self) -> List[ClarifySession]:
        """获取所有会话"""
        return list(self._sessions.values())
    
    def generate_spec_document(self, session_id: str) -> Optional[str]:
        """生成设计规格文档"""
        session = self._sessions.get(session_id)
        if not session:
            return None
        
        if session.phase != ClarifyPhase.APPROVED:
            return None
        
        # 生成 Markdown 格式的设计规格
        # 注意：使用多行字符串避免转义问题
        doc_lines = [
            f"# {session.topic} 设计规格",
            "",
            f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"> 会话ID: {session.session_id}",
            "",
            "---",
            "",
            "## 1. 概述",
            "",
            session.answers.get('context', '基于头脑风暴的需求分析结果'),
            "",
            "### 目标用户",
            self._get_answer_text(session, ClarifyPhase.PURPOSE, '目标用户'),
            "",
            "### 选择方案",
            next((o.name for o in session.design_options if o.option_id == session.selected_option), '未选择'),
            "",
            "---",
            "",
            "## 2. 功能需求",
            "",
        ]
        
        # 添加设计段落
        for section in session.design_sections:
            doc_lines.extend([
                f"### {section.title}",
                "",
                section.content,
                ""
            ])
        
        # 添加成功标准
        doc_lines.extend([
            "---",
            "",
            "## 3. 成功标准",
            "",
        ])
        for q in session.questions:
            if q.phase == ClarifyPhase.SUCCESS_CRITERIA and q.answered:
                doc_lines.append(f"- **{q.text}**: {q.answer}")
        
        # 添加方案权衡
        if session.design_options:
            doc_lines.extend([
                "",
                "---",
                "",
                "## 4. 方案权衡",
                "",
            ])
            for option in session.design_options:
                rec = " ⭐ 推荐" if option.recommended else ""
                doc_lines.extend([
                    f"### {option.name}{rec}",
                    "",
                    option.description,
                    "",
                    f"**优势**: {', '.join(option.pros)}",
                    f"**劣势**: {', '.join(option.cons)}",
                    ""
                ])
        
        # 添加约束
        doc_lines.extend([
            "",
            "---",
            "",
            "## 5. 约束条件",
            "",
        ])
        for q in session.questions:
            if q.phase == ClarifyPhase.CONSTRAINTS and q.answered:
                doc_lines.append(f"- {q.text}: {q.answer}")
        
        # 后续步骤 - 使用普通列表避免字符串问题
        doc_lines.extend([
            "",
            "---",
            "",
            "## 6. 后续步骤",
            "",
            "- [ ] 根据本规格创建实现计划",
            "- [ ] 分解为可执行的任务",
            "- [ ] 开始编码实现",
            "",
            "---",
            "",
            "*本文档由 IdeaClarifier 自动生成，未经用户审核批准不得开始实现*"
        ])
        
        return "\n".join(doc_lines)
    
    def _get_answer_text(self, session: ClarifySession, phase: ClarifyPhase, hint: str = "") -> str:
        """获取特定阶段的答案文本"""
        for q in session.questions:
            if q.phase == phase and q.answered:
                if not hint or hint in q.text:
                    return str(q.answer)
        return "[未填写]"


# 全局实例
_clarifier: Optional[IdeaClarifier] = None


def get_idea_clarifier() -> IdeaClarifier:
    """获取 IdeaClarifier 单例"""
    global _clarifier
    if _clarifier is None:
        _clarifier = IdeaClarifier()
    return _clarifier
