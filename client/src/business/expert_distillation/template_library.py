"""
专家模板库 - ExpertTemplateLibrary

存储和管理各领域的专家思维模板，
用于在推理时注入专家级别的思考模式。
"""

import json
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime
import hashlib


@dataclass
class ReasoningStep:
    order: int
    description: str
    prompt_hint: str


@dataclass
class ChainTemplate:
    id: str
    name: str
    domain: str
    query_type: str
    query_patterns: List[str]
    reasoning_steps: List[ReasoningStep]
    pattern_summary: str
    usage_count: int = 0
    success_rate: float = 0.0
    total_ratings: int = 0
    rating_sum: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "id": self.id, "name": self.name, "domain": self.domain,
            "query_type": self.query_type, "query_patterns": self.query_patterns,
            "reasoning_steps": [{"order": s.order, "description": s.description, "prompt_hint": s.prompt_hint} for s in self.reasoning_steps],
            "pattern_summary": self.pattern_summary, "usage_count": self.usage_count, "success_rate": self.success_rate
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ChainTemplate":
        steps = [ReasoningStep(**s) for s in data.get("reasoning_steps", [])]
        return cls(id=data["id"], name=data["name"], domain=data["domain"], query_type=data["query_type"],
                   query_patterns=data.get("query_patterns", []), reasoning_steps=steps,
                   pattern_summary=data["pattern_summary"], usage_count=data.get("usage_count", 0),
                   success_rate=data.get("success_rate", 0.0))

    def add_rating(self, rating: float):
        self.total_ratings += 1
        self.rating_sum += rating
        self.success_rate = self.rating_sum / self.total_ratings


class ExpertProfile:
    def __init__(self, domain: str, role: str, description: str, system_prompt: str, traits: List[str]):
        self.domain = domain
        self.role = role
        self.description = description
        self.system_prompt = system_prompt
        self.traits = traits

    def get_system_prompt(self) -> str:
        return self.system_prompt


class ExpertTemplateLibrary:
    """专家模板库"""

    DEFAULT_EXPERTS = {
        "金融": {
            "分析师": ExpertProfile("金融", "分析师", "资深金融分析师",
                """你是一位资深金融分析师，拥有20年投资经验。

专业能力：
- 精通股票、债券、基金、外汇等金融产品分析
- 擅长基本面分析、技术面分析
- 熟悉宏观经济和行业周期
- 能够识别风险并提供资产配置建议

分析风格：数据驱动、风险优先、逻辑严谨""",
                ["价值投资", "风险控制", "量化分析", "宏观研判", "估值建模"]),
            "风控师": ExpertProfile("金融", "风控师", "风险管理专家",
                """你是一位风险管理专家，精通各类风险识别与控制。

专业能力：
- 市场风险、信用风险、操作风险评估
- 风险量化模型（VaR、CVaR）
- 风险对冲策略设计""",
                ["风险识别", "量化建模", "对冲策略", "合规审查"])
        },
        "技术": {
            "架构师": ExpertProfile("技术", "架构师", "系统架构师",
                """你是一位资深系统架构师，专注于复杂系统设计与优化。

专业能力：
- 微服务架构、分布式系统
- 高并发、高可用架构
- 性能优化与容量规划
- 云原生架构""",
                ["分布式设计", "性能优化", "高可用", "云原生"]),
            "安全专家": ExpertProfile("技术", "安全专家", "网络安全专家",
                """你是一位网络安全专家，精通攻击与防御。

专业能力：
- 渗透测试与漏洞评估
- 安全架构设计
- 加密算法与协议""",
                ["渗透测试", "漏洞扫描", "加密安全", "应急响应"])
        },
        "法律": {
            "律师": ExpertProfile("法律", "律师", "商业法律师",
                """你是一位资深律师，专注于商业法律服务。

专业能力：
- 合同审查与起草
- 公司法、证券法、知识产权法
- 投融资法律尽调""",
                ["合同起草", "尽职调查", "权益保护", "合规建议"])
        },
        "医疗": {
            "医生": ExpertProfile("医疗", "医生", "临床医师",
                """你是一位主任医师，专注于临床诊断与治疗。

专业能力：
- 症状分析与鉴别诊断
- 检查检验结果解读
- 用药方案制定""",
                ["临床诊断", "检查解读", "用药安全", "病例分析"])
        }
    }

    DEFAULT_TEMPLATES = [
        ChainTemplate("fin_analysis", "金融分析", "金融", "reasoning",
            ["分析", "评估", "走势", "估值", "投资", "股票", "债券"],
            [ReasoningStep(1, "识别目标", "明确分析的公司/产品"),
             ReasoningStep(2, "收集数据", "获取财务、市场、行业数据"),
             ReasoningStep(3, "对比分析", "与行业和竞争对手对比"),
             ReasoningStep(4, "识别因素", "找出关键驱动因素和风险"),
             ReasoningStep(5, "形成结论", "给出投资建议")],
            "数据→对比→因素→结论"),
        ChainTemplate("tech_diagnosis", "技术诊断", "技术", "deduction",
            ["问题", "错误", "bug", "故障", "性能", "优化"],
            [ReasoningStep(1, "复现问题", "确认问题表现和复现条件"),
             ReasoningStep(2, "定位层", "确定问题在哪一层"),
             ReasoningStep(3, "收集证据", "查看日志、监控、堆栈"),
             ReasoningStep(4, "推理根因", "基于证据推理根本原因"),
             ReasoningStep(5, "制定方案", "提出解决方案")],
            "复现→定位→取证→推理→解决"),
        ChainTemplate("legal_analysis", "法律分析", "法律", "analogy",
            ["合同", "协议", "条款", "权利", "义务", "风险"],
            [ReasoningStep(1, "明确性质", "确定合同类型和主体"),
             ReasoningStep(2, "梳理权义", "列出各方权利义务"),
             ReasoningStep(3, "识别风险", "找出不利条款"),
             ReasoningStep(4, "参考判例", "类比类似案例"),
             ReasoningStep(5, "完善建议", "给出优化建议")],
            "定性→梳理→识别→参考→建议"),
        ChainTemplate("medical_diagnosis", "临床诊断", "医疗", "deduction",
            ["症状", "诊断", "治疗", "检查", "用药"],
            [ReasoningStep(1, "收集病史", "了解症状和既往史"),
             ReasoningStep(2, "体检发现", "整理生命体征"),
             ReasoningStep(3, "辅助检查", "解读检验结果"),
             ReasoningStep(4, "鉴别诊断", "列出可能诊断并排除"),
             ReasoningStep(5, "制定方案", "确定诊断并制定治疗计划")],
            "病史→体检→检查→鉴别→治疗")
    ]

    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = Path(storage_path) if storage_path else Path("data/templates")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.experts = {k: v.copy() for k, v in self.DEFAULT_EXPERTS.items()}
        self.chain_templates = self.DEFAULT_TEMPLATES.copy()
        self._template_index: Dict[str, List[int]] = {}
        self._rebuild_index()
        self._load_from_disk()

    def _rebuild_index(self):
        self._template_index = {}
        for i, template in enumerate(self.chain_templates):
            if template.domain not in self._template_index:
                self._template_index[template.domain] = []
            self._template_index[template.domain].append(i)

    def _load_from_disk(self):
        templates_file = self.storage_path / "templates.json"
        if templates_file.exists():
            try:
                with open(templates_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for t_data in data:
                        self.chain_templates.append(ChainTemplate.from_dict(t_data))
                self._rebuild_index()
            except Exception:
                pass

    def save_to_disk(self):
        templates_data = [t.to_dict() for t in self.chain_templates if t.id.startswith("custom_")]
        with open(self.storage_path / "templates.json", "w", encoding="utf-8") as f:
            json.dump(templates_data, f, ensure_ascii=False, indent=2)

    def get_expert_profile(self, domain: str, role: str) -> Optional[ExpertProfile]:
        return self.experts.get(domain, {}).get(role)

    def get_domain_experts(self, domain: str) -> List[ExpertProfile]:
        return list(self.experts.get(domain, {}).values())

    def get_template(self, query: str, domain: Optional[str] = None) -> Optional[ChainTemplate]:
        query_lower = query.lower()
        candidates = []
        template_list = self._template_index.get(domain, list(range(len(self.chain_templates)))) if domain else list(range(len(self.chain_templates)))

        for idx in template_list:
            template = self.chain_templates[idx]
            score = 0
            for pattern in template.query_patterns:
                if pattern.lower() in query_lower:
                    score += 1
            if domain and template.domain == domain:
                score += 2
            if score > 0:
                candidates.append((score, -template.usage_count, template))

        if candidates:
            candidates.sort()
            template = candidates[0][2]
            template.usage_count += 1
            return template
        return None

    def get_prompt_hint(self, query: str, domain: Optional[str] = None) -> str:
        template = self.get_template(query, domain)
        if not template:
            return ""
        hints = [f"【{template.name}】请按以下步骤分析："]
        for step in template.reasoning_steps:
            hints.append(f"{step.order}. {step.prompt_hint}")
        return "\n".join(hints)

    def inject_expert_context(self, query: str, domain: str, role: Optional[str] = None) -> str:
        experts = self.get_domain_experts(domain)
        expert = experts[0] if experts else None
        template = self.get_template(query, domain)
        parts = []
        if expert:
            parts.append(expert.get_system_prompt())
        if template:
            parts.append(self.get_prompt_hint(query, domain))
        parts.append(f"\n【用户问题】\n{query}")
        return "\n\n".join(parts)

    def add_template(self, template: ChainTemplate):
        if not template.id:
            template.id = f"custom_{hashlib.md5(template.name.encode()).hexdigest()[:8]}"
        self.chain_templates.append(template)
        self._rebuild_index()
        self.save_to_disk()

    def get_stats(self) -> Dict:
        return {"total_templates": len(self.chain_templates), "by_domain": {d: len(ids) for d, ids in self._template_index.items()}}


def get_expert_prompt(domain: str, query: str) -> str:
    library = ExpertTemplateLibrary()
    return library.inject_expert_context(query, domain)
