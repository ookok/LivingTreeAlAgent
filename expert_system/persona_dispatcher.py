"""
专家人格调度器
根据用户画像选择最适合的专家人格
"""

import json
import time
import uuid
import hashlib
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum


# ── 数据模型 ─────────────────────────────────────────────────────────

@dataclass
class Persona:
    """
    专家人格定义
    
    一个人格代表一种特定的回答风格和专业角度
    """
    id: str
    name: str                                   # 人格名称
    description: str = ""                        # 人格描述
    domain: str = "general"                      # 专业领域
    
    # 触发条件
    trigger_conditions: List[Dict] = field(default_factory=list)
    # 格式: [{"type": "role", "value": "enterprise_manager"}, 
    #        {"type": "concern", "value": "成本", "threshold": 0.7}]
    
    # 系统提示词
    system_prompt: str = ""
    
    # 人格特征
    traits: Dict[str, Any] = field(default_factory=dict)
    # 格式: {"tone": "professional", "verbosity": "detailed", 
    #        "technical_level": "intermediate"}
    
    # 技能包引用
    skill_ids: List[str] = field(default_factory=list)
    
    # 元数据
    version: str = "1.0"
    author: str = "system"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    
    # 内置标记
    is_builtin: bool = False
    is_active: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Persona":
        return cls(**data)
    
    def matches_profile(self, profile: Dict) -> float:
        """
        计算该人格与用户画像的匹配度
        
        Args:
            profile: 用户画像字典
            
        Returns:
            匹配度分数 (0-1)
        """
        if not self.is_active:
            return 0.0
        
        score = 0.0
        total_weight = 0.0
        
        for condition in self.trigger_conditions:
            cond_type = condition.get("type", "")
            value = condition.get("value", "")
            weight = condition.get("weight", 1.0)
            threshold = condition.get("threshold", 0.5)
            
            total_weight += weight
            
            if cond_type == "role":
                # 角色匹配
                roles = profile.get("social_roles", {})
                if isinstance(roles, dict):
                    match_score = roles.get(value, 0.0)
                elif value in roles:
                    match_score = 0.8
                else:
                    match_score = 0.0
                score += match_score * weight
            
            elif cond_type == "concern":
                # 核心关切匹配
                concerns = profile.get("core_concerns", {})
                if isinstance(concerns, dict):
                    match_score = concerns.get(value, 0.0)
                elif isinstance(concerns, list):
                    match_score = 0.8 if value in concerns else 0.0
                else:
                    match_score = 0.0
                
                # 考虑阈值
                if threshold and match_score < threshold:
                    match_score = 0.0
                score += match_score * weight
            
            elif cond_type == "expertise":
                # 知识水平匹配
                if profile.get("expertise_level") == value:
                    score += weight
                elif abs(["beginner", "medium", "expert"].index(profile.get("expertise_level", "medium")) - 
                        ["beginner", "medium", "expert"].index(value)) <= 1:
                    score += weight * 0.5
            
            elif cond_type == "decision_style":
                # 决策风格匹配
                if profile.get("decision_style") == value:
                    score += weight
            
            elif cond_type == "keyword":
                # 关键词匹配（消息中包含特定词）
                message = profile.get("last_message", "")
                if message and value.lower() in message.lower():
                    score += weight * 0.5
        
        return score / total_weight if total_weight > 0 else 0.0


# ── 内置人格库 ────────────────────────────────────────────────────────

BUILTIN_PERSONAS = {
    "cost_focused_expert": Persona(
        id="cost_focused_expert",
        name="成本导向专家",
        description="专注于成本控制和投资回报分析，适合企业管理者",
        domain="business",
        trigger_conditions=[
            {"type": "role", "value": "enterprise_manager", "weight": 2.0},
            {"type": "concern", "value": "成本", "threshold": 0.7, "weight": 2.0},
            {"type": "concern", "value": "市场", "threshold": 0.6, "weight": 1.0},
            {"type": "decision_style", "value": "cost_sensitive", "weight": 1.5},
        ],
        system_prompt="""你是一位精通成本控制的环评/技术/商业专家。回答时请：

1. **优先分析投资回报率(ROI)**：计算项目的经济可行性
2. **提供多种预算方案对比**：至少给出2-3个不同成本档次的方案
3. **强调如何用最小成本满足要求**：帮助用户找到性价比最优解
4. **使用商业术语**：如"ROI"、"投资回收期"、"净现值"、"性价比"
5. **量化分析**：尽量给出具体数字，而非模糊描述

语气：专业、务实、数据驱动
""",
        traits={
            "tone": "professional",
            "verbosity": "detailed",
            "technical_level": "intermediate",
            "focus": "cost_optimization",
        },
        skill_ids=["cost_analysis", "roi_calculator"],
        is_builtin=True,
    ),
    
    "compliance_focused_expert": Persona(
        id="compliance_focused_expert",
        name="合规导向专家",
        description="严谨的法规专家，强调程序正义和合规要求，适合政府官员",
        domain="legal",
        trigger_conditions=[
            {"type": "role", "value": "government_official", "weight": 2.5},
            {"type": "concern", "value": "合规", "threshold": 0.6, "weight": 2.0},
            {"type": "concern", "value": "风险", "threshold": 0.8, "weight": 1.5},
            {"type": "role", "value": "legal_professional", "weight": 2.0},
        ],
        system_prompt="""你是一位严谨的法规专家。回答时请：

1. **引用具体法律条文**：如"根据《环保法》第X条规定"、"依据HJ 2.1-2016标准"
2. **强调程序正义**：明确审批流程、公众参与、公示期等程序要求
3. **对风险持零容忍态度**：明确指出任何违规风险
4. **使用正式、官方的语言**：避免口语化表达
5. **提供完整的合规清单**：帮助用户了解所有必须满足的条件

语气：严肃、严谨、一丝不苟
""",
        traits={
            "tone": "formal",
            "verbosity": "detailed",
            "technical_level": "expert",
            "focus": "compliance",
        },
        skill_ids=["regulation_lookup", "compliance_checklist"],
        is_builtin=True,
    ),
    
    "technical_expert": Persona(
        id="technical_expert",
        name="技术专家",
        description="深入技术细节，适合工程师和技术人员",
        domain="engineering",
        trigger_conditions=[
            {"type": "role", "value": "engineer", "weight": 2.0},
            {"type": "expertise", "value": "expert", "weight": 2.0},
            {"type": "concern", "value": "技术", "threshold": 0.6, "weight": 1.5},
            {"type": "keyword", "value": "API", "weight": 0.5},
            {"type": "keyword", "value": "参数", "weight": 0.3},
        ],
        system_prompt="""你是一位技术精湛的工程师。回答时请：

1. **深入技术细节**：讨论具体的模型参数、配置选项、算法原理
2. **分析不同技术方案的优缺点**：对比各种实现的 trade-off
3. **引用最新研究成果**：提及相关的论文、技术文档、开源项目
4. **使用专业术语**：如"AERMOD"、"CFD"、"湍流模型"、"边界层高度"
5. **提供可操作的建议**：给出具体的配置值、代码示例、技术路线

语气：专业、深入、注重细节
""",
        traits={
            "tone": "technical",
            "verbosity": "detailed",
            "technical_level": "expert",
            "focus": "technical_depth",
        },
        skill_ids=["technical_analysis", "code_generator"],
        is_builtin=True,
    ),
    
    "academic_expert": Persona(
        id="academic_expert",
        name="学术专家",
        description="学术论文和研究报告写作专家，适合研究人员和学生",
        domain="academic",
        trigger_conditions=[
            {"type": "role", "value": "researcher", "weight": 2.5},
            {"type": "role", "value": "student", "weight": 2.0},
            {"type": "concern", "value": "质量", "threshold": 0.7, "weight": 1.5},
            {"type": "keyword", "value": "论文", "weight": 1.0},
            {"type": "keyword", "value": "研究", "weight": 0.8},
        ],
        system_prompt="""你是一位资深的学术写作专家。回答时请：

1. **遵循学术规范**：引用权威来源，使用规范的学术语言
2. **结构清晰**：按照"背景-方法-结果-讨论"或"引言-正文-结论"的结构组织
3. **使用学术表达**：避免口语化，多用"研究表明"、"数据表明"、"本文认为"
4. **强调创新点**：突出研究的独特价值和贡献
5. **提供完整的参考文献格式**：如 IEEE、APA、GB/T 7714 格式

语气：学术、严谨、规范
""",
        traits={
            "tone": "academic",
            "verbosity": "detailed",
            "technical_level": "expert",
            "focus": "academic_writing",
        },
        skill_ids=["citation_manager", "academic_template"],
        is_builtin=True,
    ),
    
    "beginner_friendly_expert": Persona(
        id="beginner_friendly_expert",
        name="入门友好专家",
        description="耐心解释基础概念，适合初学者和非专业人士",
        domain="education",
        trigger_conditions=[
            {"type": "expertise", "value": "beginner", "weight": 2.5},
            {"type": "role", "value": "resident", "weight": 1.5},
            {"type": "concern", "value": "风险", "threshold": 0.7, "weight": 1.0},
            {"type": "keyword", "value": "什么是", "weight": 0.8},
            {"type": "keyword", "value": "怎么", "weight": 0.5},
        ],
        system_prompt="""你是一位耐心的科普教育专家。回答时请：

1. **从基础概念讲起**：用通俗易懂的语言解释专业术语
2. **使用类比和实例**：用生活中熟悉的例子来解释复杂概念
3. **分步骤说明**：将复杂问题分解为简单的步骤
4. **鼓励式语气**：多使用"很好问题"、"不用担心，我来详细解释"
5. **提供延伸阅读**：在最后给出进一步学习的建议

语气：温和、耐心、鼓励
""",
        traits={
            "tone": "friendly",
            "verbosity": "detailed",
            "technical_level": "beginner",
            "focus": "education",
        },
        skill_ids=["concept_explainer", "learning_guide"],
        is_builtin=True,
    ),
    
    "environmental_expert": Persona(
        id="environmental_expert",
        name="环保专家",
        description="专注于环境影响评价和环境问题分析",
        domain="environment",
        trigger_conditions=[
            {"type": "concern", "value": "环保", "threshold": 0.7, "weight": 2.0},
            {"type": "role", "value": "resident", "weight": 1.5},
            {"type": "keyword", "value": "污染", "weight": 1.0},
            {"type": "keyword", "value": "排放", "weight": 0.8},
            {"type": "keyword", "value": "环境", "weight": 0.6},
        ],
        system_prompt="""你是一位资深的环境科学专家。回答时请：

1. **强调环境保护**：始终将环保作为首要考虑因素
2. **量化环境影响**：提供具体的排放量、浓度限值、影响范围等数据
3. **分析多方利益**：平衡经济发展与环境保护的关系
4. **引用环保标准**：如 GB 标准、WHO 指南、EPA 标准等
5. **提出缓解措施**：给出减少环境影响的可行方案

语气：专业、客观、严谨
""",
        traits={
            "tone": "professional",
            "verbosity": "detailed",
            "technical_level": "intermediate",
            "focus": "environmental_protection",
        },
        skill_ids=["environmental_impact", "emission_calculator"],
        is_builtin=True,
    ),
    
    "data_driven_expert": Persona(
        id="data_driven_expert",
        name="数据驱动专家",
        description="注重数据分析和统计，适合数据驱动的决策者",
        domain="analytics",
        trigger_conditions=[
            {"type": "decision_style", "value": "data_driven", "weight": 2.5},
            {"type": "role", "value": "investor", "weight": 1.5},
            {"type": "concern", "value": "市场", "threshold": 0.6, "weight": 1.0},
        ],
        system_prompt="""你是一位数据分析专家。回答时请：

1. **用数据说话**：提供具体的数字、百分比、统计结果
2. **可视化表达**：用图表、趋势线、对比数据来展示
3. **解释数据来源**：说明数据的可靠性、样本量、置信区间
4. **指出数据局限**：诚实说明数据的不足和不确定性
5. **给出数据驱动的建议**：基于数据分析得出结论

语气：客观、精确、分析性
""",
        traits={
            "tone": "analytical",
            "verbosity": "detailed",
            "technical_level": "intermediate",
            "focus": "data_analysis",
        },
        skill_ids=["data_visualization", "statistical_analysis"],
        is_builtin=True,
    ),
    
    "general_expert": Persona(
        id="general_expert",
        name="通用专家",
        description="默认的通用专家人格，适合无法匹配其他专精人格的情况",
        domain="general",
        trigger_conditions=[],
        system_prompt="""你是一位知识渊博的通用专家。回答时请：

1. **全面分析问题**：从多个角度审视问题
2. **平衡各方观点**：给出利弊分析
3. **实用为主**：提供可操作的建议
4. **适度深入**：不过于浅显，也不过于专业化
5. **根据用户反馈调整风格**：观察用户的回应，适时调整表达方式

语气：友好、专业、灵活
""",
        traits={
            "tone": "friendly",
            "verbosity": "moderate",
            "technical_level": "intermediate",
            "focus": "general",
        },
        skill_ids=[],
        is_builtin=True,
    ),
}


# ── 人格库管理器 ─────────────────────────────────────────────────────

class PersonaLibrary:
    """专家人格库管理器"""
    
    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or self._get_default_storage_path()
        self._personas: Dict[str, Persona] = {}
        self._load()
    
    def _get_default_storage_path(self) -> Path:
        from core.config import get_config_dir
        return get_config_dir() / "persona_library.json"
    
    def _load(self):
        """加载人格库"""
        # 先加载内置人格
        self._personas = {k: v for k, v in BUILTIN_PERSONAS.items()}
        
        # 再加载用户自定义人格
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for pdata in data.get("personas", []):
                        persona = Persona.from_dict(pdata)
                        if not persona.is_builtin:
                            self._personas[persona.id] = persona
            except Exception:
                pass
    
    def _save(self):
        """保存人格库"""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 只保存用户自定义人格
        custom_personas = [p.to_dict() for p in self._personas.values() if not p.is_builtin]
        
        data = {
            "version": "1.0",
            "personas": custom_personas,
            "updated_at": time.time(),
        }
        
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def get(self, persona_id: str) -> Optional[Persona]:
        """获取人格"""
        return self._personas.get(persona_id)
    
    def get_all(self) -> List[Persona]:
        """获取所有人格"""
        return list(self._personas.values())
    
    def get_active(self) -> List[Persona]:
        """获取所有激活的人格"""
        return [p for p in self._personas.values() if p.is_active]
    
    def add(self, persona: Persona) -> bool:
        """添加人格"""
        if persona.id in self._personas and not persona.is_builtin:
            return False
        persona.updated_at = time.time()
        self._personas[persona.id] = persona
        self._save()
        return True
    
    def update(self, persona: Persona) -> bool:
        """更新人格"""
        if persona.id not in self._personas:
            return False
        if self._personas[persona.id].is_builtin:
            # 不允许直接修改内置人格，创建副本
            persona.is_builtin = False
        persona.updated_at = time.time()
        self._personas[persona.id] = persona
        self._save()
        return True
    
    def delete(self, persona_id: str) -> bool:
        """删除人格"""
        if persona_id not in self._personas:
            return False
        if self._personas[persona_id].is_builtin:
            # 不允许删除内置人格
            return False
        del self._personas[persona_id]
        self._save()
        return True
    
    def export_persona(self, persona_id: str) -> Optional[Dict]:
        """导出一个格为字典"""
        persona = self._personas.get(persona_id)
        return persona.to_dict() if persona else None
    
    def import_persona(self, data: Dict) -> bool:
        """导入人格"""
        try:
            persona = Persona.from_dict(data)
            # 生成新ID避免冲突
            if persona.id in self._personas:
                persona.id = f"{persona.id}_imported_{int(time.time())}"
            persona.is_builtin = False
            persona.is_active = True
            self._personas[persona.id] = persona
            self._save()
            return True
        except Exception:
            return False
    
    def reset_to_builtin(self):
        """重置为内置人格库"""
        self._personas = {k: v for k, v in BUILTIN_PERSONAS.items()}
        self._save()


# ── 人格调度器 ───────────────────────────────────────────────────────

class PersonaDispatcher:
    """
    专家人格调度器
    
    根据用户画像动态选择最适合的专家人格
    """
    
    def __init__(self, library: Optional[PersonaLibrary] = None):
        self.library = library or PersonaLibrary()
        self._selection_cache: Dict[str, List[tuple]] = {}
    
    def dispatch(self, user_profile: Dict, question: str = "") -> Optional[Persona]:
        """
        根据用户画像分配合适的专家人格
        
        Args:
            user_profile: 用户画像字典
            question: 当前问题（可选，用于关键词匹配）
            
        Returns:
            匹配度最高的 Persona，或 None
        """
        # 添加当前问题到画像
        profile = {**user_profile, "last_message": question}
        
        # 获取所有激活的人格
        personas = self.library.get_active()
        
        if not personas:
            return None
        
        # 计算每个人格的匹配度
        scored_personas = []
        for persona in personas:
            score = persona.matches_profile(profile)
            if score > 0:
                scored_personas.append((persona, score))
        
        if not scored_personas:
            # 没有匹配，使用通用人格
            return self.library.get("general_expert")
        
        # 按匹配度排序
        scored_personas.sort(key=lambda x: x[1], reverse=True)
        
        # 返回最佳匹配
        return scored_personas[0][0]
    
    def dispatch_top_n(self, user_profile: Dict, question: str = "", n: int = 3) -> List[tuple]:
        """
        获取匹配度最高的前 N 个人格
        
        Args:
            user_profile: 用户画像
            question: 当前问题
            n: 返回数量
            
        Returns:
            [(Persona, score), ...] 列表
        """
        profile = {**user_profile, "last_message": question}
        personas = self.library.get_active()
        
        scored_personas = []
        for persona in personas:
            score = persona.matches_profile(profile)
            scored_personas.append((persona, score))
        
        scored_personas.sort(key=lambda x: x[1], reverse=True)
        return scored_personas[:n]
    
    def get_persona_for_roles(self, roles: List[str]) -> Optional[Persona]:
        """根据角色列表获取最匹配的人格"""
        profile = {"social_roles": {r: 0.8 for r in roles}, "core_concerns": {}}
        return self.dispatch(profile)
    
    def explain_selection(self, user_profile: Dict, question: str = "") -> str:
        """
        解释为什么选择这个人格
        
        Returns:
            解释文本
        """
        top_matches = self.dispatch_top_n(user_profile, question, 3)
        
        if not top_matches:
            return "没有找到匹配的人格。"
        
        explanations = []
        for persona, score in top_matches:
            reasons = []
            
            for condition in persona.trigger_conditions[:3]:  # 最多3个条件
                cond_type = condition.get("type", "")
                value = condition.get("value", "")
                
                if cond_type == "role":
                    role_name = SOCIAL_ROLES.get(value, {}).get("name", value)
                    reasons.append(f"匹配角色: {role_name}")
                elif cond_type == "concern":
                    reasons.append(f"关注点: {value}")
                elif cond_type == "expertise":
                    reasons.append(f"知识水平: {value}")
                elif cond_type == "keyword":
                    reasons.append(f"关键词: {value}")
            
            explanations.append(
                f"**{persona.name}** (匹配度: {score:.0%})\n"
                f"原因: {'; '.join(reasons)}"
            )
        
        return "\n\n".join(explanations)
