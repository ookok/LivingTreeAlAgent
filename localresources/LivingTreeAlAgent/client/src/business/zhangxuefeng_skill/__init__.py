"""
张雪峰 Skill 系统 - 人格化/领域技能封装

基于《张雪峰：选择比努力更重要》方法论的 AI Skill 封装
包含：心智模型 + 决策启发式 + 表达DNA

核心概念：
- SkillPackage: 可复用的技能包
- MentalModel: 心智模型（决策逻辑）
- ExpressionDNA: 表达DNA（语气/风格）
- DynamicValidator: 动态数据校验
- ZhangAgent: 技能编排 Agent
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
import json
import os


class SkillType(Enum):
    """技能类型"""
    SALES = "sales"              # 销售
    CONSULTATION = "consultation"  # 咨询
    CODING = "coding"            # 编程
    REVIEW = "review"             # 评审
    ACADEMIC = "academic"         # 学术
    LIFE = "life"                # 生活


@dataclass
class MentalModel:
    """心智模型"""
    model_id: str
    model_type: str  # decision_tree, rule_based, score_card, comparison
    name: str
    description: str
    rules: List[Dict] = field(default_factory=list)
    score_weights: Dict[str, float] = field(default_factory=dict)
    enabled: bool = True


@dataclass
class ExpressionDNA:
    """表达DNA - 固定语气和风格"""
    tone: str = "friendly"  # friendly, professional, casual, enthusiastic
    phrases: List[str] = field(default_factory=list)  # 常用短语
    forbidden: List[str] = field(default_factory=list)  # 禁用词
    punctuation_style: str = "~"  # 语气符号风格 "~" or "!"
    emoji_hint: List[str] = field(default_factory=list)  # 推荐emoji


@dataclass
class DecisionPattern:
    """决策模式"""
    pattern_id: str
    name: str
    triggers: List[str]  # 触发关键词
    decision_tree: Dict[str, str]  # 决策步骤
    output_template: str = ""

    def matches(self, query: str) -> bool:
        """检查是否匹配此模式"""
        query_lower = query.lower()
        return any(trigger.lower() in query_lower for trigger in self.triggers)


@dataclass
class SkillMetadata:
    """技能元数据"""
    author: str = ""
    version: str = "1.0.0"
    tags: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)


class SkillPackage:
    """
    技能包 - 包含心智模型、表达DNA、决策模式的完整技能封装

    结构：
    - mental_models: 心智模型列表
    - expression_dna: 表达DNA
    - decision_patterns: 决策模式
    - references: 调研数据引用
    - examples: 实战演示
    """

    def __init__(self, skill_id: str, name: str, description: str,
                 version: str = "1.0.0", skill_type: SkillType = SkillType.SALES):
        self.skill_id = skill_id
        self.name = name
        self.description = description
        self.version = version
        self.skill_type = skill_type

        self.mental_models: List[MentalModel] = []
        self.expression_dna: Optional[ExpressionDNA] = None
        self.decision_patterns: List[DecisionPattern] = []
        self.metadata = SkillMetadata(version=version)
        self.references: List[Dict] = []
        self.examples: List[Dict] = []

        self._system_prompt_template = ""

    def add_mental_model(self, model_type: str, name: str,
                        description: str, rules: List[Dict] = None) -> MentalModel:
        """添加心智模型"""
        import uuid
        model = MentalModel(
            model_id=f"model_{uuid.uuid4().hex[:8]}",
            model_type=model_type,
            name=name,
            description=description,
            rules=rules or []
        )
        self.mental_models.append(model)
        return model

    def set_expression_dna(self, tone: str = "friendly",
                           phrases: List[str] = None,
                           forbidden: List[str] = None) -> ExpressionDNA:
        """设置表达DNA"""
        self.expression_dna = ExpressionDNA(
            tone=tone,
            phrases=phrases or [],
            forbidden=forbidden or []
        )
        return self.expression_dna

    def add_decision_pattern(self, pattern: DecisionPattern):
        """添加决策模式"""
        self.decision_patterns.append(pattern)

    def detect_pattern(self, query: str) -> Optional[DecisionPattern]:
        """检测匹配的决策模式"""
        for pattern in self.decision_patterns:
            if pattern.matches(query):
                return pattern
        return None

    def build_system_prompt(self, extra_context: str = "") -> str:
        """构建系统提示词"""
        prompt_parts = [
            f"# {self.name}",
            f"## 角色定义",
            f"{self.description}",
            ""
        ]

        # 添加心智模型
        if self.mental_models:
            prompt_parts.append("## 心智模型")
            for model in self.mental_models:
                if model.enabled:
                    prompt_parts.append(f"- **{model.name}**: {model.description}")
            prompt_parts.append("")

        # 添加表达DNA
        if self.expression_dna:
            prompt_parts.append("## 表达风格")
            prompt_parts.append(f"语气: {self.expression_dna.tone}")
            if self.expression_dna.phrases:
                prompt_parts.append(f"常用语: {', '.join(self.expression_dna.phrases[:3])}")
            if self.expression_dna.forbidden:
                prompt_parts.append(f"禁用语: {', '.join(self.expression_dna.forbidden)}")
            prompt_parts.append("")

        # 添加决策模式
        if self.decision_patterns:
            prompt_parts.append("## 决策模式")
            for pattern in self.decision_patterns:
                prompt_parts.append(f"- {pattern.name}: {pattern.triggers}")
            prompt_parts.append("")

        # 额外上下文
        if extra_context:
            prompt_parts.append(f"## 当前上下文")
            prompt_parts.append(extra_context)
            prompt_parts.append("")

        return "\n".join(prompt_parts)

    def apply_expression_filter(self, text: str) -> str:
        """应用表达DNA过滤器"""
        if not self.expression_dna:
            return text

        # 替换禁用词
        for word in self.expression_dna.forbidden:
            text = text.replace(word, "[过滤]")

        # 添加常用语风格（如果原文本较短）
        if len(text) < 50 and self.expression_dna.phrases:
            prefix = self.expression_dna.phrases[0]
            if not any(text.startswith(p) for p in ["亲", "您好", "老板"]):
                text = f"{prefix}，{text}"

        return text

    def add_reference(self, title: str, content: str, source: str = ""):
        """添加参考资料"""
        self.references.append({
            "title": title,
            "content": content,
            "source": source,
            "added_at": datetime.now().isoformat()
        })

    def add_example(self, scenario: str, query: str, response: str):
        """添加实战示例"""
        self.examples.append({
            "scenario": scenario,
            "query": query,
            "response": response
        })

    def to_dict(self) -> dict:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "skill_type": self.skill_type.value,
            "mental_models": [
                {
                    "model_id": m.model_id,
                    "model_type": m.model_type,
                    "name": m.name,
                    "description": m.description,
                    "rules": m.rules
                }
                for m in self.mental_models
            ],
            "expression_dna": vars(self.expression_dna) if self.expression_dna else None,
            "decision_patterns": [
                {
                    "pattern_id": p.pattern_id,
                    "name": p.name,
                    "triggers": p.triggers
                }
                for p in self.decision_patterns
            ],
            "metadata": vars(self.metadata)
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SkillPackage":
        skill = cls(
            skill_id=data["skill_id"],
            name=data["name"],
            description=data["description"],
            version=data.get("version", "1.0.0"),
            skill_type=SkillType(data.get("skill_type", "sales"))
        )

        # 恢复心智模型
        for m_data in data.get("mental_models", []):
            model = MentalModel(**m_data)
            skill.mental_models.append(model)

        # 恢复表达DNA
        if data.get("expression_dna"):
            skill.expression_dna = ExpressionDNA(**data["expression_dna"])

        # 恢复决策模式
        for p_data in data.get("decision_patterns", []):
            pattern = DecisionPattern(**p_data)
            skill.decision_patterns.append(pattern)

        return skill


class DynamicValidator:
    """
    动态数据校验器

    功能：
    - 调用外部 API 验证信息时效性
    - 搜索最新数据补充答案
    - 标记不可靠信息
    """

    def __init__(self):
        self.validators: List[Dict[str, Any]] = []
        self.search_enabled = True

    def add_validator(self, name: str, validator_func: Callable,
                     trigger_keywords: List[str] = None):
        """添加校验器"""
        self.validators.append({
            "name": name,
            "func": validator_func,
            "triggers": trigger_keywords or []
        })

    async def validate(self, query: str, claims: List[str]) -> Dict:
        """
        验证声明

        返回：
        {
            "valid": [...],      # 验证通过的
            "invalid": [...],    # 验证失败的
            "uncertain": [...]   # 无法验证的
        }
        """
        result = {"valid": [], "invalid": [], "uncertain": []}

        for claim in claims:
            # 检查是否需要验证
            needs_validation = any(
                keyword in claim.lower()
                for validator in self.validators
                for keyword in validator["triggers"]
            )

            if not needs_validation:
                result["valid"].append({"claim": claim, "status": "assumed"})
                continue

            # 执行校验
            try:
                # 简化实现：标记为需要搜索
                result["uncertain"].append({
                    "claim": claim,
                    "status": "needs_search",
                    "suggestion": "建议联网搜索验证"
                })
            except Exception as e:
                result["invalid"].append({
                    "claim": claim,
                    "status": "error",
                    "error": str(e)
                })

        return result


class ZhangAgent:
    """
    张雪峰风格 Agent

    功能：
    - 技能包管理
    - 心智模型选择
    - 表达DNA应用
    - 动态数据校验
    """

    def __init__(self):
        self.skills: Dict[str, SkillPackage] = {}
        self.active_skill_id: Optional[str] = None
        self.validator = DynamicValidator()

        # 内置技能
        self._register_builtin_skills()

    def _register_builtin_skills(self):
        """注册内置技能"""
        # 电商销售技能
        sales_skill = build_persona_skill("sales_advisor", "friendly",
                                         ["砍价", "对比", "性价比"])
        self.register_skill(sales_skill)

        # 咨询顾问技能
        consult_skill = build_persona_skill("consultant", "professional",
                                           ["选择", "规划", "建议"])
        self.register_skill(consult_skill)

        # 代码评审技能
        code_skill = self._build_coding_skill()
        self.register_skill(code_skill)

    def _build_coding_skill(self) -> SkillPackage:
        """构建编程技能"""
        skill = SkillPackage(
            skill_id="code_reviewer",
            name="代码评审专家",
            description="你是一名资深代码评审专家，注重代码质量、可维护性和性能优化。",
            skill_type=SkillType.CODING
        )

        # 心智模型
        skill.add_mental_model(
            model_type="checklist",
            name="代码评审清单",
            description="系统性检查代码质量",
            rules=[
                {"item": "命名规范", "check": "变量/函数命名是否清晰"},
                {"item": "逻辑错误", "check": "条件判断是否完整"},
                {"item": "性能", "check": "是否有O(n²)或更差的复杂度"},
                {"item": "安全", "check": "是否有注入/越界风险"}
            ]
        )

        # 表达DNA
        skill.set_expression_dna(
            tone="professional",
            phrases=["建议优化", "可以考虑", "这里有个问题"],
            forbidden=["垃圾", "烂代码", "完全错误"]
        )

        return skill

    def register_skill(self, skill: SkillPackage):
        """注册技能"""
        self.skills[skill.skill_id] = skill

    def activate_skill(self, skill_id: str) -> bool:
        """激活技能"""
        if skill_id in self.skills:
            self.active_skill_id = skill_id
            return True
        return False

    def get_active_skill(self) -> Optional[SkillPackage]:
        """获取当前技能"""
        if self.active_skill_id:
            return self.skills.get(self.active_skill_id)
        return None

    def get_active_skill_id(self) -> str:
        return self.active_skill_id or "none"

    def select_skill_for_query(self, query: str) -> Optional[str]:
        """根据查询选择合适技能"""
        query_lower = query.lower()

        # 关键词匹配
        skill_keywords = {
            "sales_advisor": ["价格", "便宜", "性价比", "砍价", "买", "卖"],
            "consultant": ["选择", "规划", "建议", "怎么办", "要不要"],
            "code_reviewer": ["代码", "函数", "class", "review", "优化"]
        }

        for skill_id, keywords in skill_keywords.items():
            if any(kw in query_lower for kw in keywords):
                return skill_id

        return self.active_skill_id  # 保持当前技能

    async def process(self, query: str, context: Dict = None) -> Dict:
        """处理查询"""
        # 1. 选择技能
        skill_id = self.select_skill_for_query(query)
        if skill_id:
            self.activate_skill(skill_id)

        skill = self.get_active_skill()
        if not skill:
            return {"error": "No skill activated"}

        # 2. 检测决策模式
        pattern = skill.detect_pattern(query)

        # 3. 构建提示词
        extra = context.get("extra_context", "") if context else ""
        system_prompt = skill.build_system_prompt(extra)

        # 4. 验证数据（如果有外部验证器）
        validation_result = None
        if hasattr(self.validator, 'validate'):
            # 简化：不需要实时验证
            pass

        return {
            "skill_id": skill.skill_id,
            "skill_name": skill.name,
            "system_prompt": system_prompt,
            "pattern_matched": pattern.name if pattern else None,
            "query": query
        }


# 全局单例
_zhang_agent: Optional[ZhangAgent] = None


def get_zhang_agent() -> ZhangAgent:
    """获取 ZhangAgent 单例"""
    global _zhang_agent
    if _zhang_agent is None:
        _zhang_agent = ZhangAgent()
    return _zhang_agent


def build_persona_skill(persona_type: str, tone: str = "friendly",
                        expertise: List[str] = None) -> SkillPackage:
    """
    构建人格化技能包的工厂函数

    参数：
    - persona_type: 人物类型 (sales_advisor, consultant, life_coach 等)
    - tone: 语气风格 (friendly, professional, enthusiastic)
    - expertise: 专业领域列表
    """

    persona_configs = {
        "sales_advisor": {
            "name": "电商销售顾问",
            "description": "你是一名专业的电商销售顾问，擅长帮买家找到性价比最高的产品，"
                         "同时帮助卖家提升转化率。注重实用性和性价比表达。"
        },
        "consultant": {
            "name": "专业咨询顾问",
            "description": "你是一名资深咨询顾问，善于分析问题、提供选择方案。"
                         "你的建议基于数据和逻辑，同时考虑用户实际情况。"
        },
        "life_coach": {
            "name": "人生规划导师",
            "description": "你是一名人生规划导师，帮助用户理清思路、做出重要决定。"
                         "你的风格温暖但务实，强调选择比努力更重要。"
        }
    }

    config = persona_configs.get(persona_type, persona_configs["consultant"])
    skill = SkillPackage(
        skill_id=f"persona_{persona_type}",
        name=config["name"],
        description=config["description"],
        skill_type=SkillType.SALES if "销售" in config["name"] else SkillType.CONSULTATION
    )

    # 设置表达DNA
    tone_phrases = {
        "friendly": ["亲", "这款真的很不错", "性价比很高哦"],
        "professional": ["根据分析", "建议考虑", "方案如下"],
        "enthusiastic": ["太棒了", "强烈推荐", "绝对不容错过"]
    }

    tone_forbidden = {
        "friendly": ["质量差", "不要买", "骗人的"],
        "professional": ["垃圾", "烂", "完全没用"],
        "enthusiastic": ["还行吧", "无所谓"]
    }

    phrases = tone_phrases.get(tone, tone_phrases["friendly"])
    forbidden = tone_forbidden.get(tone, tone_forbidden["professional"])

    skill.set_expression_dna(tone=tone, phrases=phrases, forbidden=forbidden)

    # 添加默认决策模式
    common_triggers = expertise or ["选择", "建议", "比较"]
    skill.add_decision_pattern(DecisionPattern(
        pattern_id=f"{persona_type}_decision",
        name=f"{config['name']}决策模式",
        triggers=common_triggers,
        decision_tree={
            "step1": "理解用户需求",
            "step2": "分析可行方案",
            "step3": "对比优劣势",
            "step4": "给出建议"
        }
    ))

    # 添加元数据
    skill.metadata.tags = [persona_type, tone]
    if expertise:
        skill.metadata.config["expertise"] = expertise

    return skill
