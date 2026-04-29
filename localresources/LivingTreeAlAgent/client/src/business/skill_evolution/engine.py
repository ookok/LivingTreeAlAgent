"""
Skill 自进化系统 - 进化引擎

管理技能的生命周期：
- 技能固化
- 技能合并
- 技能分裂
- 技能遗忘
"""

import time
import threading
from typing import List, Optional, Dict, Any, Callable
from dataclasses import dataclass

from .models import (
    TaskSkill,
    SkillEvolutionStatus,
    MemoryLayer,
    InsightIndex,
    generate_id,
)
from .database import EvolutionDatabase


@dataclass
class ConsolidationResult:
    """固化结果"""
    success: bool
    skill_id: str = ""
    skill_name: str = ""
    message: str = ""


@dataclass
class MergeSuggestion:
    """合并建议"""
    skill_a: TaskSkill
    skill_b: TaskSkill
    similarity: float
    suggested_name: str
    reason: str


class EvolutionEngine:
    """
    进化引擎 - 管理技能的生命周期

    主要功能：
    1. 技能固化 - 将成功的执行转化为可复用技能
    2. 技能合并 - 合并相似的技能
    3. 技能分裂 - 将过于复杂的技能拆分为多个
    4. 技能遗忘 - 清理长期不用的技能
    5. 技能优化 - 基于使用反馈优化技能
    """

    def __init__(self, database: EvolutionDatabase):
        self.db = database
        self._lock = threading.Lock()

        # 配置
        self.config = {
            "consolidation_min_steps": 2,
            "consolidation_min_success_rate": 0.6,
            "merge_similarity_threshold": 0.7,
            "atrophy_after_days": 90,  # 90天不使用则标记为萎缩
            "mature_threshold_successes": 10,
            "mature_threshold_rate": 0.9,
        }

        # 回调
        self.on_skill_consolidated: Callable[[TaskSkill], None] = None
        self.on_skill_merged: Callable[[TaskSkill, TaskSkill], None] = None
        self.on_skill_atrophied: Callable[[TaskSkill], None] = None

    def consolidate(
        self,
        task_id: str,
        task_description: str,
        execution_records: List[Any],
        task_type: str = "",
    ) -> ConsolidationResult:
        """
        固化任务执行为技能

        Args:
            task_id: 任务 ID
            task_description: 任务描述
            execution_records: 执行记录列表
            task_type: 任务类型

        Returns:
            ConsolidationResult: 固化结果
        """
        with self._lock:
            # 检查是否满足固化条件
            if len(execution_records) < self.config["consolidation_min_steps"]:
                return ConsolidationResult(
                    success=False,
                    message=f"执行步骤太少 ({len(execution_records)})，不满足固化条件"
                )

            # 检查成功率
            successful = sum(1 for r in execution_records if r.success)
            success_rate = successful / len(execution_records) if execution_records else 0
            if success_rate < self.config["consolidation_min_success_rate"]:
                return ConsolidationResult(
                    success=False,
                    message=f"成功率太低 ({success_rate:.0%})，不满足固化条件"
                )

            # 提取工具序列
            tool_sequence = [r.tool_name for r in execution_records if r.tool_name != "no_tool"]

            # 检查是否已存在相似技能
            existing = self.db.find_similar_skills(task_description, threshold=0.6)
            if existing:
                # 更新已有技能
                skill = existing[0]
                skill.use_count += 1
                skill.total_duration += sum(r.duration for r in execution_records)
                skill.avg_duration = skill.total_duration / skill.use_count

                # 更新成功率
                new_rate = (skill.success_rate * (skill.use_count - 1) + success_rate) / skill.use_count
                skill.success_rate = new_rate

                # 更新状态
                if skill.use_count >= self.config["mature_threshold_successes"] and skill.success_rate >= self.config["mature_threshold_rate"]:
                    skill.evolution_status = SkillEvolutionStatus.MATURED

                self.db.update_skill(skill.skill_id, {
                    "use_count": skill.use_count,
                    "success_rate": skill.success_rate,
                    "avg_duration": skill.avg_duration,
                    "evolution_status": skill.evolution_status,
                })

                return ConsolidationResult(
                    success=True,
                    skill_id=skill.skill_id,
                    skill_name=skill.name,
                    message=f"更新已有技能 {skill.name}"
                )

            # 创建新技能
            skill_id = self._generate_skill_id()
            skill_name = self._generate_skill_name(task_description, tool_sequence)

            execution_flow = [
                {
                    "phase": r.phase.value if hasattr(r.phase, 'value') else str(r.phase),
                    "tool": r.tool_name,
                    "args": r.tool_args,
                    "success": r.success,
                    "duration": r.duration,
                }
                for r in execution_records
            ]

            skill = TaskSkill(
                skill_id=skill_id,
                name=skill_name,
                description=task_description,
                trigger_patterns=self._extract_keywords(task_description),
                execution_flow=execution_flow,
                tool_sequence=tool_sequence,
                success_rate=success_rate,
                use_count=1,
                failed_count=successful - len([r for r in execution_records if r.success]),
                avg_duration=sum(r.duration for r in execution_records),
                total_duration=sum(r.duration for r in execution_records),
                evolution_status=SkillEvolutionStatus.SEED,
                metadata={
                    "task_type": task_type,
                    "consolidated_from": task_id,
                }
            )

            self.db.add_skill(skill)

            # 添加索引
            keywords = self._extract_keywords(task_description)
            idx = InsightIndex(
                id=generate_id("idx"),
                keywords=keywords,
                layer=MemoryLayer.L3_TASK_SKILLS,
                target_id=skill.skill_id,
                summary=f"技能: {skill_name}",
            )
            self.db.add_insight_index(idx)

            if self.on_skill_consolidated:
                self.on_skill_consolidated(skill)

            return ConsolidationResult(
                success=True,
                skill_id=skill_id,
                skill_name=skill_name,
                message=f"创建新技能 {skill_name}"
            )

    def find_merge_candidates(self) -> List[MergeSuggestion]:
        """
        查找可合并的技能

        Returns:
            List[MergeSuggestion]: 合并建议列表
        """
        all_skills = self.db.get_all_skills()
        suggestions = []

        for i, skill_a in enumerate(all_skills):
            for skill_b in all_skills[i + 1:]:
                similarity = self._calculate_skill_similarity(skill_a, skill_b)

                if similarity >= self.config["merge_similarity_threshold"]:
                    # 生成合并建议
                    merged_name = self._suggest_merged_name(skill_a, skill_b)
                    reason = self._explain_merge_reason(skill_a, skill_b, similarity)

                    suggestions.append(MergeSuggestion(
                        skill_a=skill_a,
                        skill_b=skill_b,
                        similarity=similarity,
                        suggested_name=merged_name,
                        reason=reason
                    ))

        # 按相似度排序
        suggestions.sort(key=lambda x: x.similarity, reverse=True)
        return suggestions

    def merge_skills(self, skill_a_id: str, skill_b_id: str, new_name: str = None) -> Optional[TaskSkill]:
        """
        合并两个技能

        Args:
            skill_a_id: 技能 A ID
            skill_b_id: 技能 B ID
            new_name: 新技能名称（可选）

        Returns:
            TaskSkill: 合并后的新技能
        """
        with self._lock:
            skill_a = self.db.get_skill(skill_a_id)
            skill_b = self.db.get_skill(skill_b_id)

            if not skill_a or not skill_b:
                return None

            # 合并执行流程（优先使用成功率更高的）
            if skill_a.success_rate >= skill_b.success_rate:
                primary = skill_a
                secondary = skill_b
            else:
                primary = skill_b
                secondary = skill_a

            # 生成新名称
            if not new_name:
                new_name = self._suggest_merged_name(primary, secondary)

            # 创建合并后的技能
            merged_skill = TaskSkill(
                skill_id=generate_id("skill"),
                name=new_name,
                description=f"{primary.description} / {secondary.description}",
                trigger_patterns=list(set(primary.trigger_patterns + secondary.trigger_patterns)),
                execution_flow=primary.execution_flow + secondary.execution_flow,
                tool_sequence=list(set(primary.tool_sequence + secondary.tool_sequence)),
                success_rate=max(primary.success_rate, secondary.success_rate),
                use_count=primary.use_count + secondary.use_count,
                failed_count=primary.failed_count + secondary.failed_count,
                avg_duration=(primary.avg_duration + secondary.avg_duration) / 2,
                total_duration=primary.total_duration + secondary.total_duration,
                evolution_status=SkillEvolutionStatus.MERGED,
                parent_skill_id=skill_a_id,  # 记录父技能
                prerequisites=list(set(primary.prerequisites + secondary.prerequisites)),
                metadata={
                    "merged_from": [skill_a_id, skill_b_id],
                    "primary_skill": primary.skill_id,
                }
            )

            self.db.add_skill(merged_skill)

            # 删除原技能
            self.db.delete_skill(skill_a_id)
            self.db.delete_skill(skill_b_id)

            if self.on_skill_merged:
                self.on_skill_merged(skill_a, skill_b)

            return merged_skill

    def check_atrophy(self) -> List[TaskSkill]:
        """
        检查萎缩技能（长期不使用的技能）

        Returns:
            List[TaskSkill]: 需要标记为萎缩的技能
        """
        atrophied = []
        all_skills = self.db.get_all_skills()
        now = time.time()
        threshold = self.config["atrophy_after_days"] * 24 * 3600

        for skill in all_skills:
            if skill.evolution_status in (SkillEvolutionStatus.MATURED, SkillEvolutionStatus.ATROPHIED):
                continue

            last_used = skill.last_used
            if now - last_used > threshold:
                skill.evolution_status = SkillEvolutionStatus.ATROPHIED
                self.db.update_skill(skill.skill_id, {
                    "evolution_status": SkillEvolutionStatus.ATROPHIED
                })
                atrophied.append(skill)

                if self.on_skill_atrophied:
                    self.on_skill_atrophied(skill)

        return atrophied

    def evolve_skill(self, skill_id: str, feedback: Dict[str, Any]) -> bool:
        """
        基于反馈进化技能

        Args:
            skill_id: 技能 ID
            feedback: 反馈数据 {success: bool, duration: float, error: str}

        Returns:
            bool: 是否成功
        """
        skill = self.db.get_skill(skill_id)
        if not skill:
            return False

        success = feedback.get("success", True)
        duration = feedback.get("duration", 0)

        # 更新使用统计
        skill.use_count += 1
        skill.total_duration += duration
        skill.avg_duration = skill.total_duration / skill.use_count

        if success:
            skill.success_rate = (skill.success_rate * (skill.use_count - 1) + 1.0) / skill.use_count
        else:
            skill.failed_count += 1
            skill.success_rate = (skill.success_rate * (skill.use_count - 1)) / skill.use_count

        # 更新进化状态
        if skill.use_count >= self.config["mature_threshold_successes"] and skill.success_rate >= self.config["mature_threshold_rate"]:
            skill.evolution_status = SkillEvolutionStatus.MATURED
        elif skill.use_count >= 3 and skill.success_rate >= 0.7:
            skill.evolution_status = SkillEvolutionStatus.GROWING
        elif skill.failed_count > skill.use_count * 0.5:
            skill.evolution_status = SkillEvolutionStatus.ATROPHIED

        self.db.update_skill(skill_id, {
            "use_count": skill.use_count,
            "success_rate": skill.success_rate,
            "avg_duration": skill.avg_duration,
            "failed_count": skill.failed_count,
            "evolution_status": skill.evolution_status,
            "last_used": time.time(),
        })

        return True

    def get_skill_tree(self) -> Dict[str, Any]:
        """
        获取技能树（用于可视化）

        Returns:
            Dict: 技能树结构
        """
        all_skills = self.db.get_all_skills()

        # 按状态分组
        by_status = {}
        for skill in all_skills:
            status = skill.evolution_status.value if isinstance(skill.evolution_status, SkillEvolutionStatus) else skill.evolution_status
            if status not in by_status:
                by_status[status] = []
            by_status[status].append({
                "id": skill.skill_id,
                "name": skill.name,
                "use_count": skill.use_count,
                "success_rate": skill.success_rate,
            })

        # 构建树状结构
        root = {
            "name": "技能库",
            "children": []
        }

        for status, skills in by_status.items():
            status_node = {
                "name": f"{status} ({len(skills)})",
                "children": [
                    {"name": s["name"], "value": s["use_count"]}
                    for s in skills
                ]
            }
            root["children"].append(status_node)

        return root

    # ============ 辅助方法 ============

    def _generate_skill_id(self) -> str:
        """生成技能 ID"""
        return generate_id("skill")

    def _generate_skill_name(self, description: str, tool_sequence: List[str]) -> str:
        """生成技能名称"""
        # 取描述前15个字符
        base = description[:15] if len(description) >= 15 else description
        # 移除特殊字符
        import re
        base = re.sub(r'[^\w\u4e00-\u9fff]', '_', base)
        # 添加工具提示
        if tool_sequence:
            primary_tool = tool_sequence[0]
            return f"{base}_{primary_tool}"
        return base

    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        import re
        words = re.findall(r'[\w]+', text.lower())
        stopwords = {'的', '了', '是', '在', '和', '与', '或', '一个', '这个', '那', '帮我', '请'}
        keywords = [w for w in words if len(w) > 1 and w not in stopwords]
        return keywords[:10]

    def _calculate_skill_similarity(self, skill_a: TaskSkill, skill_b: TaskSkill) -> float:
        """计算两个技能的相似度"""
        # 工具序列相似度
        tools_a = set(skill_a.tool_sequence)
        tools_b = set(skill_b.tool_sequence)
        if tools_a and tools_b:
            tool_similarity = len(tools_a & tools_b) / len(tools_a | tools_b)
        else:
            tool_similarity = 0

        # 触发模式相似度
        patterns_a = set(skill_a.trigger_patterns)
        patterns_b = set(skill_b.trigger_patterns)
        if patterns_a and patterns_b:
            pattern_similarity = len(patterns_a & patterns_b) / len(patterns_a | patterns_b)
        else:
            pattern_similarity = 0

        return (tool_similarity + pattern_similarity) / 2

    def _suggest_merged_name(self, skill_a: TaskSkill, skill_b: TaskSkill) -> str:
        """建议合并后的名称"""
        # 取两个名称的公共部分
        name_a = skill_a.name
        name_b = skill_b.name

        # 找到公共前缀
        common = ""
        for i in range(min(len(name_a), len(name_b))):
            if name_a[i] == name_b[i]:
                common += name_a[i]
            else:
                break

        if common and len(common) >= 3:
            return f"{common}_merged"
        else:
            return f"merged_{skill_a.name[:8]}_{skill_b.name[:8]}"

    def _explain_merge_reason(self, skill_a: TaskSkill, skill_b: TaskSkill, similarity: float) -> str:
        """解释合并原因"""
        common_tools = set(skill_a.tool_sequence) & set(skill_b.tool_sequence)
        reasons = []
        if common_tools:
            reasons.append(f"共享工具: {', '.join(common_tools)}")
        if similarity >= 0.8:
            reasons.append("高度相似")
        elif similarity >= 0.5:
            reasons.append("部分重叠")
        return "; ".join(reasons) if reasons else "功能相近"
