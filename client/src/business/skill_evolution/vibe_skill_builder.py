"""
Vibe驱动技能构建器 (Vibe Skill Builder)
遵循自我进化原则：从自然语言描述中学习生成技能，而非预置模板

架构指南参考: docs/LIVINGTREE_ARCHITECTURE_GUIDE.md (章节 5.3.2)

核心借鉴: refly (匹配度55%, 借鉴性80%)
- 自然语言 → 自动生成技能
- 从示例中学习技能模式
- 动态优化技能结构
"""
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from pathlib import Path
import json
import logging
import re

from business.global_model_router import GlobalModelRouter, ModelCapability


logger = logging.getLogger(__name__)


@dataclass
class Skill:
    """
    技能数据结构

    遵循自我进化原则：
    - 不预置固定的技能模板
    - 从描述/示例中学习技能结构
    """
    name: str
    description: str
    version: str = "1.0.0"
    author: str = "LivingTreeAI"
    created_at: str = ""

    # 核心能力
    capabilities: List[str] = field(default_factory=list)

    # 工作流程（从学习中生成）
    workflow: List[Dict[str, Any]] = field(default_factory=list)

    # 常见问题（从交互中学习）
    common_questions: List[str] = field(default_factory=list)

    # 输出模板（从示例中学习）
    output_templates: Dict[str, str] = field(default_factory=dict)

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    # 学习统计
    usage_count: int = 0
    success_rate: float = 0.0

    def to_skill_md(self) -> str:
        """生成 SKILL.md 格式"""
        lines = []
        lines.append(f"# {self.name}")
        lines.append("")
        lines.append(f"**版本**: {self.version}")
        lines.append(f"**作者**: {self.author}")
        lines.append(f"**创建日期**: {self.created_at}")
        lines.append("")

        # YAML frontmatter
        lines.append("---")
        lines.append("yaml")
        lines.append(f"name: {self.name}")
        lines.append(f"version: {self.version}")
        lines.append(f"author: {self.author}")
        lines.append("capabilities:")
        for cap in self.capabilities:
            lines.append(f"  - {cap}")
        lines.append("---")
        lines.append("")

        # 描述
        lines.append("## 核心能力")
        lines.append("")
        lines.append(self.description)
        lines.append("")

        # 工作流程
        if self.workflow:
            lines.append("## 工作流程")
            lines.append("")
            for i, step in enumerate(self.workflow, 1):
                lines.append(f"{i}. **{step.get('name', f'步骤{i}')}**: {step.get('description', '')}")
            lines.append("")

        # 常见问题
        if self.common_questions:
            lines.append("## 常见问题")
            lines.append("")
            for q in self.common_questions:
                lines.append(f"- Q: {q}")
            lines.append("")

        # 输出模板
        if self.output_templates:
            lines.append("## 输出模板")
            lines.append("")
            for name, template in self.output_templates.items():
                lines.append(f"### {name}")
                lines.append("")
                lines.append(template)
                lines.append("")

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "created_at": self.created_at,
            "capabilities": self.capabilities,
            "workflow": self.workflow,
            "common_questions": self.common_questions,
            "output_templates": self.output_templates,
            "metadata": self.metadata,
            "usage_count": self.usage_count,
            "success_rate": self.success_rate
        }


class VibeSkillBuilder:
    """
    Vibe驱动技能构建器

    核心原则：
    ❌ 不预置固定的技能模板
    ✅ 从自然语言描述中理解技能需求
    ✅ 从示例中学习技能结构
    ✅ 动态生成和优化技能
    ✅ 验证并注册到 ToolRegistry
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self.router = GlobalModelRouter()
        self.storage_path = storage_path or Path.home() / ".livingtree" / "learned_skills.json"
        self.learned_skills: Dict[str, Skill] = {}
        self.skill_patterns: Dict[str, Dict[str, Any]] = {}  # 学习的技能模式
        self._load_skills()

    def _load_skills(self):
        """加载已学习的技能"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for skill_data in data.get("skills", []):
                        skill = Skill(**skill_data)
                        self.learned_skills[skill.name] = skill
                    self.skill_patterns = data.get("patterns", {})
                logger.info(f"✅ 已加载 {len(self.learned_skills)} 个已学习技能")
            except Exception as e:
                logger.warning(f"⚠️ 加载技能失败: {e}")

    def _save_skills(self):
        """保存学习的技能"""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "skills": [s.to_dict() for s in self.learned_skills.values()],
                "patterns": self.skill_patterns
            }
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"❌ 保存技能失败: {e}")

    async def build_from_description(self, user_description: str) -> Skill:
        """
        从描述中构建技能

        流程：
        1. 理解技能需求（分析描述）
        2. 生成技能结构
        3. 如果有示例，从示例中学习
        4. 验证并注册
        """
        logger.info(f"🎓 开始构建技能: {user_description[:50]}...")

        # 1. 分析技能需求
        analysis = await self._analyze_description(user_description)

        # 2. 生成技能结构
        skill = await self._generate_skill_structure(analysis)

        # 3. 如果有示例，学习
        if analysis.get("examples"):
            skill = await self._learn_from_examples(skill, analysis["examples"])

        # 4. 验证技能
        is_valid, errors = await self._validate_skill(skill)
        if not is_valid:
            logger.warning(f"⚠️ 技能验证失败: {errors}")
            # 尝试修复
            skill = await self._fix_skill(skill, errors)

        # 5. 保存技能
        self.learned_skills[skill.name] = skill
        self._save_skills()

        logger.info(f"✅ 技能构建完成: {skill.name}")
        return skill

    async def _analyze_description(self, description: str) -> Dict[str, Any]:
        """使用 LLM 分析技能描述"""
        prompt = f"""
作为一个技能设计专家，分析以下技能描述，提取关键信息。

技能描述: {description}

要求：
1. 推断技能名称（简洁、描述性）
2. 识别核心能力
3. 判断是否提供了示例
4. 返回 JSON 格式

返回格式:
{{
    "skill_name": "技能名称",
    "description": "技能详细描述",
    "capabilities": ["能力1", "能力2", ...],
    "examples": ["示例1", "示例2", ...],  // 如果描述中包含示例
    "category": "技能类别（如：数据分析、文档处理、代码生成等）"
}}

只返回 JSON，不要有其他内容。
"""

        try:
            response = self.router.call_model_sync(
                capability=ModelCapability.REASONING,
                prompt=prompt,
                temperature=0.3
            )
            result = json.loads(response)
            result["raw_description"] = description
            return result
        except Exception as e:
            logger.error(f"❌ 分析描述失败: {e}")
            # 兜底：简单提取
            return {
                "skill_name": description[:20],
                "description": description,
                "capabilities": ["通用能力"],
                "examples": [],
                "category": "通用"
            }

    async def _generate_skill_structure(self, analysis: Dict[str, Any]) -> Skill:
        """生成技能结构"""
        prompt = f"""
作为一个技能设计专家，根据以下分析结果，生成完整的技能结构。

分析结果: {json.dumps(analysis, ensure_ascii=False)}

要求：
1. 设计合理的工作流程（3-7步）
2. 预测常见问题（3-5个）
3. 设计输出模板（如果有明确输出格式）
4. 返回 JSON 格式

返回格式:
{{
    "workflow": [
        {{"name": "步骤1", "description": "描述", "inputs": [], "outputs": []}},
        ...
    ],
    "common_questions": ["问题1", "问题2", ...],
    "output_templates": {{
        "default": "模板内容",
        ...
    }}
}}

只返回 JSON，不要有其他内容。
"""

        try:
            response = self.router.call_model_sync(
                capability=ModelCapability.REASONING,
                prompt=prompt,
                temperature=0.3
            )
            result = json.loads(response)

            # 创建 Skill 对象
            skill = Skill(
                name=analysis.get("skill_name", "未命名技能"),
                description=analysis.get("description", ""),
                capabilities=analysis.get("capabilities", []),
                workflow=result.get("workflow", []),
                common_questions=result.get("common_questions", []),
                output_templates=result.get("output_templates", {}),
                metadata={
                    "category": analysis.get("category", "通用"),
                    "source": "vibe_generated"
                }
            )
            return skill

        except Exception as e:
            logger.error(f"❌ 生成技能结构失败: {e}")
            # 返回基础技能
            return Skill(
                name=analysis.get("skill_name", "未命名技能"),
                description=analysis.get("description", ""),
                capabilities=analysis.get("capabilities", [])
            )

    async def _learn_from_examples(self, skill: Skill, examples: List[str]) -> Skill:
        """从示例中学习技能模式"""
        logger.info(f"📝 从 {len(examples)} 个示例中学习...")

        prompt = f"""
作为一个技能学习专家，从以下示例中学习技能模式。

技能: {skill.name}
描述: {skill.description}
示例:
{chr(10).join(f"{i+1}. {ex}" for i, ex in enumerate(examples))}

要求：
1. 分析示例中的共同模式
2. 优化工作流程
3. 提取输出模板
4. 返回 JSON 格式

返回格式:
{{
    "optimized_workflow": [...],  # 优化后的工作流程
    "learned_templates": {{"name": "template"}},  # 学习的模板
    "patterns": ["模式1", "模式2", ...]  # 发现的模式
}}

只返回 JSON，不要有其他内容。
"""

        try:
            response = self.router.call_model_sync(
                capability=ModelCapability.REASONING,
                prompt=prompt,
                temperature=0.2
            )
            result = json.loads(response)

            # 更新技能
            if result.get("optimized_workflow"):
                skill.workflow = result["optimized_workflow"]
            if result.get("learned_templates"):
                skill.output_templates.update(result["learned_templates"])

            # 记录学习的模式
            pattern_key = f"{skill.name}_{len(self.skill_patterns)}"
            self.skill_patterns[pattern_key] = {
                "skill_name": skill.name,
                "patterns": result.get("patterns", []),
                "examples_count": len(examples)
            }

            logger.info(f"✅ 已从示例中学习: {skill.name}")
            return skill

        except Exception as e:
            logger.error(f"❌ 从示例学习失败: {e}")
            return skill

    async def _validate_skill(self, skill: Skill) -> tuple:
        """验证技能是否有效"""
        errors = []

        # 基础检查
        if not skill.name or len(skill.name) < 2:
            errors.append("技能名称太短")
        if not skill.description or len(skill.description) < 10:
            errors.append("技能描述太短")
        if not skill.capabilities:
            errors.append("缺少核心能力")

        # 工作流程检查
        if skill.workflow:
            for i, step in enumerate(skill.workflow):
                if not step.get("name"):
                    errors.append(f"工作流程步骤 {i+1} 缺少名称")

        return len(errors) == 0, errors

    async def _fix_skill(self, skill: Skill, errors: List[str]) -> Skill:
        """尝试修复技能"""
        logger.info(f"🔧 尝试修复技能: {', '.join(errors)}")

        prompt = f"""
作为一个技能修复专家，修复以下技能问题。

技能: {skill.name}
错误: {chr(10).join(errors)}
当前技能结构: {json.dumps(skill.to_dict(), ensure_ascii=False)}

要求：
1. 修复所有错误
2. 返回修复后的完整技能 JSON
3. 保持原有合理部分

只返回 JSON，不要有其他内容。
"""

        try:
            response = self.router.call_model_sync(
                capability=ModelCapability.REASONING,
                prompt=prompt,
                temperature=0.2
            )
            result = json.loads(response)

            # 更新技能
            skill.description = result.get("description", skill.description)
            skill.capabilities = result.get("capabilities", skill.capabilities)
            skill.workflow = result.get("workflow", skill.workflow)
            skill.common_questions = result.get("common_questions", skill.common_questions)

            logger.info(f"✅ 技能修复完成: {skill.name}")
            return skill

        except Exception as e:
            logger.error(f"❌ 修复技能失败: {e}")
            return skill

    async def register_skill(self, skill: Skill, output_path: Optional[Path] = None) -> bool:
        """
        注册技能到系统

        1. 生成 SKILL.md
        2. 保存到 .livingtree/skills/ 目录
        3. 注册到 ToolRegistry（如果需要）
        """
        try:
            # 1. 确定保存路径
            if output_path is None:
                output_path = Path.home() / ".livingtree" / "skills" / skill.name
            output_path.mkdir(parents=True, exist_ok=True)

            # 2. 生成 SKILL.md
            skill_md = skill.to_skill_md()
            skill_file = output_path / "SKILL.md"
            with open(skill_file, 'w', encoding='utf-8') as f:
                f.write(skill_md)

            logger.info(f"✅ 技能已保存到: {skill_file}")

            # 3. 注册到 ToolRegistry（如果需要）
            # TODO: 实现 ToolRegistry 注册逻辑

            return True

        except Exception as e:
            logger.error(f"❌ 注册技能失败: {e}")
            return False

    async def learn_from_interaction(self, interaction: Dict[str, Any]):
        """
        从交互中学习，优化技能

        交互格式:
        {
            "skill_name": "技能名称",
            "user_input": "用户输入",
            "skill_output": "技能输出",
            "rating": 0.8,  # 用户评分 0-1
            "feedback": "用户反馈"
        }
        """
        skill_name = interaction.get("skill_name")
        if skill_name not in self.learned_skills:
            return

        skill = self.learned_skills[skill_name]
        rating = interaction.get("rating", 0.5)

        # 更新使用统计
        skill.usage_count += 1
        skill.success_rate = (skill.success_rate * (skill.usage_count - 1) + rating) / skill.usage_count

        # 如果评分低，学习改进
        if rating < 0.6:
            logger.info(f"🔄 低评分技能，学习中: {skill_name} (评分: {rating})")
            await self._improve_skill_from_feedback(skill, interaction)

        self._save_skills()

    async def _improve_skill_from_feedback(self, skill: Skill, interaction: Dict[str, Any]):
        """从反馈中改进技能"""
        prompt = f"""
作为一个技能优化专家，根据以下反馈改进技能。

技能: {skill.name}
当前描述: {skill.description}
用户反馈: {interaction.get("feedback", "")}
用户评分: {interaction.get("rating", 0)}

要求：
1. 分析反馈中的问题
2. 提出改进方案
3. 返回 JSON 格式

返回格式:
{{
    "improved_description": "改进后的描述",
    "new_workflow": [...],  # 可选
    "new_questions": [...]  # 可选
}}

只返回 JSON，不要有其他内容。
"""

        try:
            response = self.router.call_model_sync(
                capability=ModelCapability.REASONING,
                prompt=prompt,
                temperature=0.3
            )
            result = json.loads(response)

            # 应用改进
            if result.get("improved_description"):
                skill.description = result["improved_description"]
            if result.get("new_workflow"):
                skill.workflow = result["new_workflow"]
            if result.get("new_questions"):
                skill.common_questions.extend(result["new_questions"])

            logger.info(f"✅ 技能已改进: {skill.name}")

        except Exception as e:
            logger.error(f"❌ 改进技能失败: {e}")

    def get_skill_stats(self) -> Dict[str, Any]:
        """获取技能统计信息"""
        if not self.learned_skills:
            return {"total_skills": 0}

        avg_success_rate = sum(s.success_rate for s in self.learned_skills.values()) / len(self.learned_skills)
        total_usage = sum(s.usage_count for s in self.learned_skills.values())

        return {
            "total_skills": len(self.learned_skills),
            "total_patterns": len(self.skill_patterns),
            "average_success_rate": round(avg_success_rate, 2),
            "total_usage": total_usage,
            "top_skills": [
                {
                    "name": s.name,
                    "usage_count": s.usage_count,
                    "success_rate": round(s.success_rate, 2)
                }
                for s in sorted(self.learned_skills.values(), key=lambda x: x.usage_count, reverse=True)[:5]
            ]
        }
