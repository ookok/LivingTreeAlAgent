"""
DistillationConfig - 蒸馏技能配置

定义技能源和集成配置的标准化格式。
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
import json
import yaml


class SkillSourceType(Enum):
    """技能源类型"""
    GITHUB = "github"
    LOCAL = "local"
    PYPI = "pypi"
    API = "api"


class SkillCategory(Enum):
    """技能类别"""
    THINKING = "thinking"         # 思维模型
    BUSINESS = "business"         # 商业决策
    SCIENCE = "science"           # 科学方法
    PHILOSOPHY = "philosophy"     # 哲学思考
    TRADITIONAL = "traditional"   # 传统文化
    CREATIVE = "creative"         # 创意生成
    UTILITY = "utility"           # 工具技能
    MENTOR = "mentor"             # 导师指导
    OTHER = "other"               # 其他


@dataclass
class SkillSource:
    """技能源配置"""
    name: str
    url: str
    type: str = "github"
    category: str = "other"
    description: str = ""
    author: str = ""
    version: str = "latest"
    enabled: bool = True
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "url": self.url,
            "type": self.type,
            "category": self.category,
            "description": self.description,
            "author": self.author,
            "version": self.version,
            "enabled": self.enabled,
            "tags": self.tags
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SkillSource':
        return cls(
            name=data["name"],
            url=data["url"],
            type=data.get("type", "github"),
            category=data.get("category", "other"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            version=data.get("version", "latest"),
            enabled=data.get("enabled", True),
            tags=data.get("tags", [])
        )


@dataclass
class DistillationConfig:
    """蒸馏技能配置"""
    sources: List[SkillSource] = field(default_factory=list)
    default_install_dir: str = "~/LivingTreeAI/distilled_skills"
    auto_update: bool = False
    update_interval_hours: int = 24

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sources": [s.to_dict() for s in self.sources],
            "default_install_dir": self.default_install_dir,
            "auto_update": self.auto_update,
            "update_interval_hours": self.update_interval_hours
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DistillationConfig':
        return cls(
            sources=[SkillSource.from_dict(s) for s in data.get("sources", [])],
            default_install_dir=data.get("default_install_dir", "~/LivingTreeAI/distilled_skills"),
            auto_update=data.get("auto_update", False),
            update_interval_hours=data.get("update_interval_hours", 24)
        )

    @classmethod
    def from_yaml(cls, yaml_content: str) -> 'DistillationConfig':
        data = yaml.safe_load(yaml_content)
        return cls.from_dict(data)

    @classmethod
    def from_yaml_file(cls, filepath: str) -> 'DistillationConfig':
        with open(filepath, 'r', encoding='utf-8') as f:
            return cls.from_yaml(f.read())

    def to_yaml(self) -> str:
        return yaml.dump(self.to_dict(), default_flow_style=False, allow_unicode=True)

    def save_to_yaml(self, filepath: str):
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(self.to_yaml())

    def add_source(self, source: SkillSource):
        """添加技能源"""
        self.sources.append(source)

    def remove_source(self, name: str):
        """移除技能源"""
        self.sources = [s for s in self.sources if s.name != name]

    def get_source(self, name: str) -> Optional[SkillSource]:
        """获取技能源"""
        return next((s for s in self.sources if s.name == name), None)

    def get_sources_by_category(self, category: str) -> List[SkillSource]:
        """按类别获取技能源"""
        return [s for s in self.sources if s.category == category]


# 内置的蒸馏技能源配置
DEFAULT_SKILL_SOURCES = [
    SkillSource(
        name="nuwa-skill",
        url="https://github.com/alchaincyf/nuwa-skill",
        type="github",
        category="creative",
        description="女娲技能 - 创意生成与设计辅助",
        author="alchaincyf",
        tags=["creative", "design", "generation"]
    ),
    SkillSource(
        name="yourself-skill",
        url="https://github.com/notdog1998/yourself-skill",
        type="github",
        category="thinking",
        description="自我认知与个人成长技能",
        author="notdog1998",
        tags=["self", "growth", "psychology"]
    ),
    SkillSource(
        name="anti-distill",
        url="https://github.com/leilei926524-tech/anti-distill",
        type="github",
        category="utility",
        description="反蒸馏防御技术",
        author="leilei926524-tech",
        tags=["security", "defense", "privacy"]
    ),
    SkillSource(
        name="ex-skill",
        url="https://github.com/perkfly/ex-skill",
        type="github",
        category="thinking",
        description="专家技能框架",
        author="perkfly",
        tags=["expert", "knowledge", "framework"]
    ),
    SkillSource(
        name="bazi-skill",
        url="https://github.com/jinchenma94/bazi-skill",
        type="github",
        category="traditional",
        description="八字命理技能",
        author="jinchenma94",
        tags=["traditional", "fengshui", "astrology"]
    ),
    SkillSource(
        name="steve-jobs-skill",
        url="https://github.com/alchaincyf/steve-jobs-skill",
        type="github",
        category="business",
        description="乔布斯思维模型",
        author="alchaincyf",
        tags=["business", "innovation", "design"]
    ),
    SkillSource(
        name="x-mentor-skill",
        url="https://github.com/alchaincyf/x-mentor-skill",
        type="github",
        category="mentor",
        description="导师指导技能",
        author="alchaincyf",
        tags=["mentor", "coaching", "guidance"]
    ),
    SkillSource(
        name="master-skill",
        url="https://github.com/alchaincyf/master-skill",
        type="github",
        category="utility",
        description="技能管理大师",
        author="alchaincyf",
        tags=["management", "skill", "master"]
    ),
    SkillSource(
        name="boss-skills",
        url="https://github.com/vogtsw/boss-skills",
        type="github",
        category="business",
        description="老板技能集",
        author="vogtsw",
        tags=["business", "leadership", "management"]
    ),
    SkillSource(
        name="elon-musk-skill",
        url="https://github.com/alchaincyf/elon-musk-skill",
        type="github",
        category="business",
        description="马斯克思维模型",
        author="alchaincyf",
        tags=["business", "innovation", "space"]
    ),
    SkillSource(
        name="munger-skill",
        url="https://github.com/alchaincyf/munger-skill",
        type="github",
        category="thinking",
        description="芒格思维模型",
        author="alchaincyf",
        tags=["thinking", "investing", "mental-models"]
    ),
    SkillSource(
        name="naval-skill",
        url="https://github.com/alchaincyf/naval-skill",
        type="github",
        category="philosophy",
        description="纳瓦尔智慧",
        author="alchaincyf",
        tags=["philosophy", "wisdom", "life"]
    ),
    SkillSource(
        name="feynman-skill",
        url="https://github.com/alchaincyf/feynman-skill",
        type="github",
        category="science",
        description="费曼学习法",
        author="alchaincyf",
        tags=["science", "learning", "method"]
    ),
    SkillSource(
        name="taleb-skill",
        url="https://github.com/alchaincyf/taleb-skill",
        type="github",
        category="philosophy",
        description="塔勒布反脆弱思维",
        author="alchaincyf",
        tags=["philosophy", "risk", "antifragile"]
    ),
    SkillSource(
        name="zhang-yiming-skill",
        url="https://github.com/alchaincyf/zhang-yiming-skill",
        type="github",
        category="business",
        description="张一鸣管理哲学",
        author="alchaincyf",
        tags=["business", "management", "tech"]
    ),
    SkillSource(
        name="reasoning-skill",
        url="https://github.com/stallone0000/Reasoning-Skill",
        type="github",
        category="thinking",
        description="推理技能框架",
        author="stallone0000",
        tags=["reasoning", "logic", "thinking"]
    ),
    SkillSource(
        name="khazix-skills",
        url="https://github.com/KKKKhazix/khazix-skills",
        type="github",
        category="utility",
        description="Khazix 技能集",
        author="KKKKhazix",
        tags=["skills", "utility", "toolkit"]
    )
]


def get_default_config() -> DistillationConfig:
    """获取默认配置"""
    return DistillationConfig(sources=DEFAULT_SKILL_SOURCES)