"""
Minimalist Skills Loader - 极简创业技能加载器
基于《The Minimalist Entrepreneur》方法论
"""

import os
import re
import hashlib
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum


class SkillCategory(Enum):
    """技能分类"""
    VALIDATION = "validation"      # 验证
    COMMUNITY = "community"          # 社区
    PRICING = "pricing"             # 定价
    MARKETING = "marketing"         # 营销
    PRODUCT = "product"            # 产品
    OPERATIONS = "operations"      # 运营


@dataclass
class MinimalistSkill:
    """极简创业技能"""
    name: str
    description: str
    category: SkillCategory
    steps: list[str]
    checklist: list[str]
    tips: list[str]
    body: str  # 原始正文


class MinimalistSkillLoader:
    """极简创业技能加载器"""

    # 内置技能定义（精简版）
    BUILTIN_SKILLS = {
        "find-community": {
            "name": "Find Community",
            "description": "找到你的目标社区",
            "category": SkillCategory.COMMUNITY,
            "steps": [
                "确定你解决的是什么问题，以及为谁解决",
                "找到遇到这个问题的群体（在线/线下）",
                "观察他们在哪里聚集，讨论什么",
                "成为活跃成员，提供价值而非推销",
                "找到社区中的群主/意见领袖",
                "建立信任后再自然引入你的产品"
            ],
            "checklist": [
                "我明确知道为谁解决什么问题",
                "找到了至少3个目标社区",
                "已在其中2个以上活跃参与",
                "发现了社区的沟通文化和规则",
                "建立了至少5个真实关系"
            ],
            "tips": [
                "社区优先于客户：先成为成员，再成为卖家",
                "不要一开始就推销，先提供价值",
                "找到社区的'疼痛点'和现有解决方案",
                "耐心：建立信任需要时间"
            ]
        },
        "validate-idea": {
            "name": "Validate Idea",
            "description": "验证你的创业想法",
            "category": SkillCategory.VALIDATION,
            "steps": [
                "明确你要解决的问题和目标用户",
                "验证问题确实存在且值得解决",
                "了解现有解决方案及其缺陷",
                "尝试手动方式先交付（不看技术）",
                "寻找愿意付费的早期用户",
                "基于反馈迭代产品概念"
            ],
            "checklist": [
                "我能清楚描述问题和目标用户",
                "目标用户确认这是真实问题",
                "至少3个用户表示愿意付费",
                "手动方式已被验证可行",
                "收到了具体的用户反馈"
            ],
            "tips": [
                "验证而非计划：尽快接触真实用户",
                "'糟糕的演示好过完美的计划'",
                "如果没人愿意付费，问题可能不够痛",
                "最小可行产品要真正可用，而非半成品"
            ]
        },
        "mvp": {
            "name": "Build MVP",
            "description": "构建最小可行产品",
            "category": SkillCategory.PRODUCT,
            "steps": [
                "基于验证结果确定核心功能",
                "只做目标用户必需的1-3个功能",
                "优先解决最痛的点",
                "用最快方式交付（表格/手动/现有工具）",
                "让真实用户使用并收集反馈",
                "快速迭代而非追求完美"
            ],
            "checklist": [
                "核心功能不超过3个",
                "能在1周内交付",
                "真实用户在用",
                "每周都有反馈",
                "产品正在被迭代"
            ],
            "tips": [
                "MVP不是半成品，是精简版好东西",
                "先自动化手动流程中重复的部分",
                "技术选型要快，不要过度工程化",
                "'Done is better than perfect'"
            ]
        },
        "pricing": {
            "name": "Pricing Strategy",
            "description": "制定定价策略",
            "category": SkillCategory.PRICING,
            "steps": [
                "了解你的成本结构（时间/金钱/工具）",
                "研究竞争对手的定价",
                "确定你的独特价值",
                "选择定价模型（订阅/一次性/混合）",
                "设计早期用户优惠",
                "测试不同价格点的转化率"
            ],
            "checklist": [
                "清楚知道成本结构",
                "竞品定价在某个范围",
                "有明确的差异化价值主张",
                "设计了早期折扣或试用",
                "有定价测试计划"
            ],
            "tips": [
                "定价要覆盖成本并留有利润空间",
                "不要因为害怕定价高而牺牲利润",
                "早期优惠可以换取口碑和案例",
                "订阅制提供稳定的现金流"
            ]
        },
        "marketing-plan": {
            "name": "Marketing Plan",
            "description": "制定营销计划",
            "category": SkillCategory.MARKETING,
            "steps": [
                "确定目标用户画像",
                "找到他们的信息获取渠道",
                "创造能解决问题的内容",
                "在目标社区中分发内容",
                "建立邮件列表或关注渠道",
                "衡量并优化营销效果"
            ],
            "checklist": [
                "有清晰的用户画像",
                "确定了主要营销渠道",
                "内容计划覆盖至少1个月",
                "有邮件列表或粉丝积累计划",
                "有衡量指标"
            ],
            "tips": [
                "内容营销是最高效的获客方式",
                "一个爆款内容胜过100篇平庸文章",
                "社区营销成本最低效果最好",
                "口碑传播是最好的营销"
            ]
        },
        "growth": {
            "name": "Growth Strategy",
            "description": "增长策略",
            "category": SkillCategory.MARKETING,
            "steps": [
                "分析当前增长数据和来源",
                "找到增长最快的渠道",
                "加大投入产出比最高的渠道",
                "测试新的增长渠道",
                "建立增长漏斗指标",
                "自动化可重复的增长动作"
            ],
            "checklist": [
                "有清晰的增长指标",
                "知道主要增长来源",
                "有正在测试的新渠道",
                "增长流程有部分自动化",
                "有A/B测试机制"
            ],
            "tips": [
                "专注于1-2个最有效的渠道",
                "口碑推荐是最强的增长引擎",
                "自动化重复的营销任务",
                "数据驱动决策而非直觉"
            ]
        },
        "sales": {
            "name": "Sales Process",
            "description": "销售流程",
            "category": SkillCategory.OPERATIONS,
            "steps": [
                "明确销售流程的步骤",
                "准备销售话术和材料",
                "找到潜在客户的来源",
                "主动联系并预约沟通",
                "进行销售演示/对话",
                "处理异议并达成成交",
                "跟进并建立长期关系"
            ],
            "checklist": [
                "有清晰的销售漏斗",
                "销售话术经过打磨",
                "有明确的转化目标",
                "客户反馈有收集机制",
                "有复购或增购计划"
            ],
            "tips": [
                "销售是倾听而非讲述",
                "了解客户真正的购买动机",
                "处理异议要真诚而非对抗",
                "成交只是关系的开始"
            ]
        },
        "operations": {
            "name": "Business Operations",
            "description": "业务运营",
            "category": SkillCategory.OPERATIONS,
            "steps": [
                "文档化核心业务流程",
                "识别重复性任务",
                "优先自动化高价值任务",
                "选择合适的工具和系统",
                "建立运营指标仪表板",
                "定期回顾和优化流程"
            ],
            "checklist": [
                "核心流程已文档化",
                "有正在使用的工具栈",
                "有运营仪表板",
                "每周有运营回顾",
                "有流程优化计划"
            ],
            "tips": [
                "不要在工具上过度投入",
                "简单工具用好胜过复杂工具闲置",
                "自动化要聚焦高价值任务",
                "定期回顾是优化的前提"
            ]
        }
    }

    def __init__(self, skills_dir: Optional[str] = None):
        """
        初始化加载器

        Args:
            skills_dir: 外部技能目录，若不存在则使用内置技能
        """
        if skills_dir:
            self.skills_dir = Path(skills_dir)
        else:
            # 默认使用内置技能
            self.skills_dir = None
        self.skills: dict[str, MinimalistSkill] = {}

    def load_all(self) -> int:
        """
        加载所有技能

        Returns:
            加载的技能数量
        """
        self.skills.clear()

        # 1. 尝试从外部目录加载
        external_count = 0
        if self.skills_dir and self.skills_dir.exists():
            external_count = self._load_from_directory()

        # 2. 合并内置技能
        self._load_builtin_skills()

        # 3. 外部技能覆盖内置（如果有同名）
        if external_count > 0:
            self._merge_external_skills()

        return len(self.skills)

    def _load_from_directory(self) -> int:
        """从外部目录加载 SKILL.md 文件"""
        count = 0
        if not self.skills_dir:
            return 0

        for skill_dir in self.skills_dir.glob("*"):
            if not skill_dir.is_dir():
                continue

            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue

            try:
                text = skill_file.read_text(encoding="utf-8")
                skill = self._parse_skill_file(skill_dir.name, text)
                if skill:
                    self.skills[skill_dir.name] = skill
                    count += 1
            except Exception as e:
                print(f"Warning: Failed to load skill from {skill_file}: {e}")

        return count

    def _load_builtin_skills(self):
        """加载内置技能"""
        for skill_id, skill_data in self.BUILTIN_SKILLS.items():
            # 确定分类
            category = skill_data.get("category", SkillCategory.VALIDATION)

            # 构建 body
            body = self._build_skill_body(skill_data)

            skill = MinimalistSkill(
                name=skill_data["name"],
                description=skill_data["description"],
                category=category,
                steps=skill_data.get("steps", []),
                checklist=skill_data.get("checklist", []),
                tips=skill_data.get("tips", []),
                body=body
            )
            self.skills[skill_id] = skill

    def _merge_external_skills(self):
        """合并外部技能（同名覆盖）"""
        if not self.skills_dir:
            return

        for skill_dir in self.skills_dir.glob("*"):
            if not skill_dir.is_dir():
                continue

            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue

            try:
                text = skill_file.read_text(encoding="utf-8")
                skill = self._parse_skill_file(skill_dir.name, text)
                if skill:
                    # 外部技能覆盖内置
                    self.skills[skill_dir.name] = skill
            except Exception:
                pass

    def _parse_skill_file(self, skill_id: str, text: str) -> Optional[MinimalistSkill]:
        """解析 SKILL.md 文件"""
        # 解析 YAML Front Matter
        meta_match = re.match(r"^---\s*\n([\s\S]+?)\n---\s*\n", text)
        if not meta_match:
            return None

        meta_str = meta_match.group(1)
        body = text[meta_match.end():].strip()

        # 解析 YAML
        meta = {}
        for line in meta_str.split("\n"):
            line = line.strip()
            if ":" in line:
                key, value = line.split(":", 1)
                meta[key.strip()] = value.strip()

        # 解析内容
        steps = []
        checklist = []
        tips = []

        # 提取步骤 (## Steps / ## 执行步骤)
        steps_match = re.search(r"(?:## Steps|## 执行步骤)\s*\n([\s\S]+?)(?=\n##|\n#|$)", body, re.IGNORECASE)
        if steps_match:
            steps = [line.strip() for line in steps_match.group(1).split("\n") if line.strip().startswith("- ") or line.strip().startswith("* ") or line[0].isdigit()]

        # 提取检查清单
        checklist_match = re.search(r"(?:## Checklist|## 检查清单)\s*\n([\s\S]+?)(?=\n##|\n#|$)", body, re.IGNORECASE)
        if checklist_match:
            checklist = [line.strip().lstrip("- *").strip() for line in checklist_match.group(1).split("\n") if line.strip()]

        # 提取提示
        tips_match = re.search(r"(?:## Tips|## 提示)\s*\n([\s\S]+?)(?=\n##|\n#|$)", body, re.IGNORECASE)
        if tips_match:
            tips = [line.strip().lstrip("- *").strip() for line in tips_match.group(1).split("\n") if line.strip()]

        # 确定分类
        category_str = meta.get("category", "").lower()
        category_map = {
            "validation": SkillCategory.VALIDATION,
            "community": SkillCategory.COMMUNITY,
            "pricing": SkillCategory.PRICING,
            "marketing": SkillCategory.MARKETING,
            "product": SkillCategory.PRODUCT,
            "operations": SkillCategory.OPERATIONS
        }
        category = category_map.get(category_str, SkillCategory.VALIDATION)

        return MinimalistSkill(
            name=meta.get("name", skill_id),
            description=meta.get("description", ""),
            category=category,
            steps=steps,
            checklist=checklist,
            tips=tips,
            body=body
        )

    def _build_skill_body(self, data: dict) -> str:
        """构建技能正文"""
        lines = []

        lines.append(f"# {data['name']}")
        lines.append("")
        lines.append(data.get("description", ""))
        lines.append("")

        if data.get("steps"):
            lines.append("## Steps")
            for step in data["steps"]:
                lines.append(f"- {step}")
            lines.append("")

        if data.get("checklist"):
            lines.append("## Checklist")
            for item in data["checklist"]:
                lines.append(f"- [ ] {item}")
            lines.append("")

        if data.get("tips"):
            lines.append("## Tips")
            for tip in data["tips"]:
                lines.append(f"- {tip}")

        return "\n".join(lines)

    def get_skill(self, name: str) -> Optional[MinimalistSkill]:
        """获取技能"""
        return self.skills.get(name)

    def get_skill_body(self, name: str) -> str:
        """获取技能正文"""
        skill = self.get_skill(name)
        return skill.body if skill else ""

    def get_skill_as_prompt(self, name: str, user_context: str = "") -> str:
        """
        获取技能的系统提示格式

        Args:
            name: 技能名称
            user_context: 用户上下文

        Returns:
            格式化的系统提示
        """
        skill = self.get_skill(name)
        if not skill:
            return ""

        prompt_parts = []

        # 角色定义
        prompt_parts.append("你是一名极简创业教练，遵循《The Minimalist Entrepreneur》的方法论。")
        prompt_parts.append("")
        prompt_parts.append(f"## 当前技能: {skill.name}")
        prompt_parts.append(f"{skill.description}")
        prompt_parts.append("")

        # 步骤
        if skill.steps:
            prompt_parts.append("### 执行步骤:")
            for i, step in enumerate(skill.steps, 1):
                prompt_parts.append(f"{i}. {step}")
            prompt_parts.append("")

        # 检查清单
        if skill.checklist:
            prompt_parts.append("### 检查清单:")
            for item in skill.checklist:
                prompt_parts.append(f"- [ ] {item}")
            prompt_parts.append("")

        # 提示
        if skill.tips:
            prompt_parts.append("### 关键提示:")
            for tip in skill.tips:
                prompt_parts.append(f"- {tip}")
            prompt_parts.append("")

        # 用户上下文
        if user_context:
            prompt_parts.append("---")
            prompt_parts.append(f"### 用户情况:")
            prompt_parts.append(user_context)
            prompt_parts.append("")
            prompt_parts.append("请基于以上技能指南，帮助用户完成当前任务。")

        return "\n".join(prompt_parts)

    def list_skills(self, category: Optional[SkillCategory] = None) -> list[str]:
        """列出技能"""
        if category:
            return [k for k, v in self.skills.items() if v.category == category]
        return list(self.skills.keys())

    def get_all_categories(self) -> list[SkillCategory]:
        """获取所有技能分类"""
        categories = set(skill.category for skill in self.skills.values())
        return list(categories)

    def get_skill_info(self, name: str) -> dict:
        """获取技能简要信息"""
        skill = self.get_skill(name)
        if not skill:
            return {}
        return {
            "id": name,
            "name": skill.name,
            "description": skill.description,
            "category": skill.category.value,
            "steps_count": len(skill.steps),
            "checklist_count": len(skill.checklist)
        }


# 全局单例
_global_loader: Optional[MinimalistSkillLoader] = None


def get_skill_loader(skills_dir: Optional[str] = None) -> MinimalistSkillLoader:
    """获取全局技能加载器"""
    global _global_loader
    if _global_loader is None:
        _global_loader = MinimalistSkillLoader(skills_dir)
        _global_loader.load_all()
    return _global_loader


def clone_skills_repo(repo_url: str, target_dir: str) -> bool:
    """
    克隆技能仓库（需要 git）

    Args:
        repo_url: 仓库 URL
        target_dir: 目标目录

    Returns:
        是否成功
    """
    try:
        import subprocess
        target_path = Path(target_dir)
        if target_path.exists():
            # 已有则更新
            subprocess.run(["git", "pull"], cwd=target_path, check=True, capture_output=True)
        else:
            subprocess.run(["git", "clone", repo_url, target_dir], check=True, capture_output=True)
        return True
    except Exception as e:
        print(f"Warning: Failed to clone repo: {e}")
        return False
