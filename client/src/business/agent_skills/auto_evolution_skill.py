"""
自进化技能系统
==============

参考 Hermes Agent 的自进化记忆机制：
- 从交互中自动识别可复用的模式
- 将重复出现的任务序列转化为技能
- 持续优化技能成功率

核心流程：
1. 模式检测 - 识别重复的任务序列
2. 技能种子创建 - 从模式生成技能草稿
3. 技能学习 - 通过使用改进技能
4. 技能稳定 - 高成功率后标记为稳定

Author: Hermes Desktop Team
Date: 2026-04-25
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from collections import Counter
import hashlib

from business.agent_skills.skill_registry import (
    SkillRegistry, 
    SkillManifest, 
    SkillCategory,
    SkillInput,
    SkillOutput,
    AgentType,
    OutputType,
    SkillEvolution,
)

logger = logging.getLogger(__name__)


@dataclass
class InteractionPattern:
    """交互模式"""
    pattern_id: str
    trigger: str                    # 触发词/查询
    action_sequence: List[str]     # 执行的操作序列
    context_keywords: List[str]    # 上下文关键词
    frequency: int = 1              # 出现频率
    success_count: int = 0         # 成功次数
    last_seen: datetime = field(default_factory=datetime.now)
    embedding_hint: str = ""       # 向量嵌入提示


@dataclass
class SkillSeed:
    """技能种子"""
    name: str
    description: str
    trigger_phrases: List[str]
    suggested_agent: AgentType
    suggested_inputs: List[SkillInput]
    suggested_outputs: List[SkillOutput]
    suggested_tools: List[str]
    source_patterns: List[str]      # 来源模式 ID
    confidence: float = 0.5        # 置信度


@dataclass
class EvolutionCandidate:
    """进化候选"""
    skill_id: str
    reason: str                     # 进化原因
    improvement_suggestion: str    # 改进建议
    evidence: List[str]            # 证据列表
    priority: int = 5              # 优先级 1-10


class PatternDetector:
    """
    模式检测器
    
    从交互历史中检测可复用的模式
    """
    
    def __init__(self, min_frequency: int = 3, min_action_length: int = 2):
        self.min_frequency = min_frequency
        self.min_action_length = min_action_length
        self._pattern_buffer: List[InteractionPattern] = []
        self._pattern_cache: Dict[str, InteractionPattern] = {}
        
    def record_interaction(
        self,
        query: str,
        actions: List[str],
        success: bool = True
    ):
        """
        记录一次交互
        
        Args:
            query: 用户查询
            actions: 执行的操作列表
            success: 是否成功
        """
        if len(actions) < self.min_action_length:
            return
            
        # 提取关键词
        keywords = self._extract_keywords(query)
        
        # 生成模式签名
        action_sig = self._generate_signature(actions)
        query_sig = self._normalize_query(query)
        
        pattern_key = f"{query_sig}:{action_sig}"
        
        if pattern_key in self._pattern_cache:
            # 更新已有模式
            pattern = self._pattern_cache[pattern_key]
            pattern.frequency += 1
            pattern.last_seen = datetime.now()
            if success:
                pattern.success_count += 1
        else:
            # 创建新模式
            pattern = InteractionPattern(
                pattern_id=hashlib.md5(pattern_key.encode()).hexdigest()[:8],
                trigger=query,
                action_sequence=actions,
                context_keywords=keywords,
                frequency=1,
                success_count=1 if success else 0,
                embedding_hint=query_sig,
            )
            self._pattern_cache[pattern_key] = pattern
            self._pattern_buffer.append(pattern)
            
        logger.debug(f"[PatternDetector] 记录交互: 频率={pattern.frequency}")
        
    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        # 移除停用词
        stopwords = {'的', '了', '是', '在', '和', '与', '或', '我', '你', '他', '她', '它', '这', '那', '什么', '怎么', '如何'}
        words = re.findall(r'[\w]+', text.lower())
        keywords = [w for w in words if w not in stopwords and len(w) > 1]
        
        # 返回频率最高的词
        counter = Counter(keywords)
        return [w for w, _ in counter.most_common(5)]
        
    def _normalize_query(self, query: str) -> str:
        """规范化查询"""
        # 移除具体数值和特定名词，保留意图
        normalized = re.sub(r'\d+', '{N}', query)
        normalized = re.sub(r'[A-Za-z0-9_.]+@[a-z]+\.[a-z]+', '{EMAIL}', normalized)
        normalized = re.sub(r'https?://\S+', '{URL}', normalized)
        # 移除多余空格
        normalized = ' '.join(normalized.split())
        return normalized.lower()
        
    def _generate_signature(self, actions: List[str]) -> str:
        """生成操作序列签名"""
        # 只保留操作类型，去除参数
        action_types = []
        for action in actions:
            # 提取操作名（如 "read_file", "execute_command"）
            match = re.match(r'^(\w+)', action)
            if match:
                action_types.append(match.group(1))
        return '->'.join(action_types)
        
    def detect_patterns(self) -> List[InteractionPattern]:
        """
        检测高频模式
        
        Returns:
            高频且成功的模式列表
        """
        candidates = []
        
        for pattern in self._pattern_cache.values():
            if pattern.frequency >= self.min_frequency:
                success_rate = pattern.success_count / pattern.frequency
                # 过滤掉成功率过低的模式
                if success_rate >= 0.5:
                    candidates.append(pattern)
        
        # 按频率和成功率排序
        candidates.sort(
            key=lambda p: (p.frequency, p.success_count / p.frequency),
            reverse=True
        )
        
        logger.info(f"[PatternDetector] 检测到 {len(candidates)} 个高频模式")
        return candidates


class SkillSeedGenerator:
    """
    技能种子生成器
    
    从检测到的模式生成技能种子
    """
    
    def __init__(self):
        self._intent_keywords: Dict[str, List[str]] = {
            "planning": ["计划", "规划", "设计", "架构", "方案", "plan", "design"],
            "development": ["开发", "编写", "实现", "写代码", "build", "code"],
            "testing": ["测试", "测试用例", "验证", "test", "verify"],
            "review": ["审查", "检查", "review", "analyze", "分析"],
            "deployment": ["部署", "发布", "上线", "deploy", "release"],
            "debugging": ["调试", "修复", "debug", "fix", "error"],
        }
        
        self._agent_keywords: Dict[AgentType, List[str]] = {
            AgentType.CODE_EXPERT: ["代码", "函数", "类", "实现", "code", "function"],
            AgentType.PLANNER: ["计划", "规划", "方案", "strategy", "plan"],
            AgentType.RESEARCHER: ["研究", "分析", "调研", "research", "analyze"],
            AgentType.WRITER: ["写", "文档", "文章", "write", "document"],
            AgentType.REVIEWER: ["审查", "检查", "review", "check"],
        }
        
    def generate_seed(self, pattern: InteractionPattern) -> SkillSeed:
        """
        从模式生成技能种子
        
        Args:
            pattern: 检测到的交互模式
            
        Returns:
            技能种子
        """
        # 确定类别
        category = self._infer_category(pattern.trigger)
        
        # 确定代理类型
        agent = self._infer_agent(pattern.trigger, pattern.action_sequence)
        
        # 生成输入定义
        inputs = self._generate_inputs(pattern)
        
        # 生成输出定义
        outputs = self._generate_outputs(pattern)
        
        # 推断需要的工具
        tools = self._infer_tools(pattern.action_sequence)
        
        # 生成触发词
        triggers = self._generate_triggers(pattern)
        
        confidence = min(pattern.frequency / 10, 1.0) * (pattern.success_count / pattern.frequency)
        
        return SkillSeed(
            name=self._generate_name(pattern, category),
            description=f"从 {pattern.frequency} 次使用中学习到的 {category.value} 技能",
            trigger_phrases=triggers,
            suggested_agent=agent,
            suggested_inputs=inputs,
            suggested_outputs=outputs,
            suggested_tools=tools,
            source_patterns=[pattern.pattern_id],
            confidence=confidence,
        )
        
    def _infer_category(self, trigger: str) -> SkillCategory:
        """推断技能类别"""
        trigger_lower = trigger.lower()
        
        for category, keywords in self._intent_keywords.items():
            for keyword in keywords:
                if keyword in trigger_lower:
                    try:
                        return SkillCategory(category)
                    except ValueError:
                        pass
                        
        return SkillCategory.DEVELOPMENT
        
    def _infer_agent(self, trigger: str, actions: List[str]) -> AgentType:
        """推断代理类型"""
        trigger_lower = trigger.lower()
        actions_str = ' '.join(actions).lower()
        
        for agent, keywords in self._agent_keywords.items():
            for keyword in keywords:
                if keyword in trigger_lower or keyword in actions_str:
                    return agent
                    
        return AgentType.GENERAL
        
    def _generate_inputs(self, pattern: InteractionPattern) -> List[SkillInput]:
        """生成输入定义"""
        inputs = [
            SkillInput(
                name="query",
                description="用户的自然语言查询",
                type="string",
                required=True,
            )
        ]
        
        # 根据上下文添加额外输入
        if "文件" in pattern.trigger or "file" in pattern.trigger.lower():
            inputs.append(SkillInput(
                name="file_path",
                description="目标文件路径",
                type="string",
                required=False,
            ))
            
        return inputs
        
    def _generate_outputs(self, pattern: InteractionPattern) -> List[SkillOutput]:
        """生成输出定义"""
        outputs = [OutputType.TEXT]
        
        # 根据操作推断输出
        actions_str = ' '.join(pattern.action_sequence).lower()
        if 'write' in actions_str or '写入' in actions_str:
            outputs.append(OutputType.FILE)
        if 'code' in actions_str or '代码' in actions_str:
            outputs.append(OutputType.CODE)
            
        return [SkillOutput(type=o) for o in set(outputs)]
        
    def _infer_tools(self, actions: List[str]) -> List[str]:
        """推断需要的工具"""
        tools = set()
        
        for action in actions:
            action_lower = action.lower()
            if 'read' in action_lower or '读取' in action_lower:
                tools.add('read_file')
            if 'write' in action_lower or '写入' in action_lower:
                tools.add('write_to_file')
            if 'execute' in action_lower or '执行' in action_lower:
                tools.add('execute_command')
            if 'search' in action_lower or '搜索' in action_lower:
                tools.add('search_content')
            if 'delete' in action_lower or '删除' in action_lower:
                tools.add('delete_file')
                
        return list(tools)
        
    def _generate_triggers(self, pattern: InteractionPattern) -> List[str]:
        """生成触发词"""
        triggers = pattern.context_keywords[:3]
        
        # 添加原始触发词的简化版本
        simplified = pattern.trigger[:50] if len(pattern.trigger) > 50 else pattern.trigger
        triggers.append(simplified)
        
        return list(set(triggers))[:5]
        
    def _generate_name(self, pattern: InteractionPattern, category: SkillCategory) -> str:
        """生成技能名称"""
        keywords = pattern.context_keywords[:2]
        if keywords:
            return f"{category.value.title()}-{'-'.join(keywords)}"
        return f"{category.value.title()}-Skill-{pattern.pattern_id}"


class AutoEvolutionSkill:
    """
    自进化技能系统
    
    核心功能：
    1. 模式检测 - 从交互中学习
    2. 技能生成 - 创建新技能
    3. 持续改进 - 优化现有技能
    
    Usage:
        evolution = AutoEvolutionSkill(registry)
        
        # 记录交互
        evolution.record_interaction(
            query="帮我分析代码质量问题",
            actions=["read_file", "analyze_code", "report_issues"],
            success=True
        )
        
        # 检测候选技能
        candidates = evolution.detect_skill_candidates()
        
        # 创建新技能
        if candidates:
            seed = candidates[0]
            evolution.create_skill_from_seed(seed)
    """
    
    def __init__(
        self,
        registry: SkillRegistry,
        min_pattern_frequency: int = 3,
        auto_create_threshold: float = 0.8,
    ):
        self.registry = registry
        self.pattern_detector = PatternDetector(min_frequency=min_pattern_frequency)
        self.seed_generator = SkillSeedGenerator()
        self.auto_create_threshold = auto_create_threshold
        self._created_seeds: set = set()  # 避免重复创建
        
    def record_interaction(
        self,
        query: str,
        actions: List[str],
        success: bool = True
    ):
        """
        记录一次交互
        
        Args:
            query: 用户查询
            actions: 执行的操作列表
            success: 是否成功
        """
        self.pattern_detector.record_interaction(query, actions, success)
        
    def detect_skill_candidates(self) -> List[SkillSeed]:
        """
        检测可创建的技能候选
        
        Returns:
            技能种子列表
        """
        patterns = self.pattern_detector.detect_patterns()
        candidates = []
        
        for pattern in patterns:
            seed = self.seed_generator.generate_seed(pattern)
            
            # 过滤掉已创建的
            if seed.source_patterns[0] in self._created_seeds:
                continue
                
            # 过滤置信度过低的
            if seed.confidence >= self.auto_create_threshold:
                candidates.append(seed)
                self._created_seeds.add(seed.source_patterns[0])
                
        logger.info(f"[AutoEvolutionSkill] 检测到 {len(candidates)} 个技能候选")
        return candidates
        
    def create_skill_from_seed(
        self,
        seed: SkillSeed,
        evolution_note: str = ""
    ) -> Optional[SkillManifest]:
        """
        从种子创建技能
        
        Args:
            seed: 技能种子
            evolution_note: 进化说明
            
        Returns:
            创建的技能清单
        """
        # 创建技能 ID
        skill_id = f"auto-{seed.name.lower().replace(' ', '-')[:30]}-{datetime.now().strftime('%Y%m%d')}"
        
        manifest = SkillManifest(
            id=skill_id,
            name=seed.name,
            description=seed.description,
            category=SkillCategory.LEARNING,
            trigger_phrases=seed.trigger_phrases,
            agent=seed.suggested_agent,
            inputs=seed.suggested_inputs,
            outputs=seed.suggested_outputs,
            tools=seed.suggested_tools,
            evolution=SkillEvolution.SEED,
            metadata={
                "confidence": seed.confidence,
                "source_patterns": seed.source_patterns,
                "auto_created": True,
            },
        )
        
        # 注册技能
        self.registry.register(manifest, content=self._generate_default_content(seed))
        
        logger.info(f"[AutoEvolutionSkill] 创建技能: {manifest.name} (ID: {manifest.id})")
        return manifest
        
    def _generate_default_content(self, seed: SkillSeed) -> str:
        """生成默认技能内容"""
        inputs_str = '\n'.join(f"- {inp.name}: {inp.description}" for inp in seed.suggested_inputs)
        outputs_str = ', '.join(o.type.value for o in seed.suggested_outputs)
        tools_str = ', '.join(seed.suggested_tools)
        
        return f"""# {seed.name}

{seed.description}

## 输入参数
{inputs_str}

## 输出类型
{outputs_str}

## 需要的工具
{tools_str}

## 触发条件
- {', '.join(seed.trigger_phrases[:3])}

---
*此技能由 AutoEvolutionSkill 自动生成*
*来源模式: {', '.join(seed.source_patterns)}*
*置信度: {seed.confidence:.2%}*
"""
        
    def suggest_improvements(self) -> List[EvolutionCandidate]:
        """
        建议技能改进
        
        分析现有技能的失败案例，生成改进建议
        
        Returns:
            改进建议列表
        """
        candidates = []
        
        for skill in self.registry.list_skills():
            # 检查学习中的技能
            if skill.evolution == SkillEvolution.LEARNING:
                evidence = [
                    f"成功率: {skill.success_rate:.1%}",
                    f"使用次数: {skill.usage_count}",
                ]
                
                candidates.append(EvolutionCandidate(
                    skill_id=skill.id,
                    reason="技能处于学习状态，需要改进",
                    improvement_suggestion="分析失败案例，调整触发词或优化执行逻辑",
                    evidence=evidence,
                    priority=8,
                ))
                
            # 检查低成功率技能
            elif skill.usage_count >= 5 and skill.success_rate < 0.6:
                candidates.append(EvolutionCandidate(
                    skill_id=skill.id,
                    reason=f"成功率较低 ({skill.success_rate:.1%})",
                    improvement_suggestion="考虑调整触发词或标记为待删除",
                    evidence=[f"成功率: {skill.success_rate:.1%}"],
                    priority=6,
                ))
                
        return sorted(candidates, key=lambda c: c.priority, reverse=True)
        
    def evolve_skill(
        self,
        skill_id: str,
        improvements: Dict[str, Any],
        evolution_note: str
    ) -> Optional[SkillManifest]:
        """
        改进现有技能
        
        Args:
            skill_id: 技能 ID
            improvements: 改进内容
            evolution_note: 进化说明
            
        Returns:
            改进后的技能
        """
        old_skill = self.registry.get_skill(skill_id)
        if not old_skill:
            logger.warning(f"[AutoEvolutionSkill] 技能不存在: {skill_id}")
            return None
            
        # 创建新版本
        new_skill = SkillManifest(
            id=f"{old_skill.id}-v2",
            name=old_skill.name,
            description=improvements.get("description", old_skill.description),
            category=old_skill.category,
            trigger_phrases=improvements.get("trigger_phrases", old_skill.trigger_phrases),
            agent=old_skill.agent,
            inputs=improvements.get("inputs", old_skill.inputs),
            outputs=old_skill.outputs,
            tools=improvements.get("tools", old_skill.tools),
            evolution=SkillEvolution.STABLE,
        )
        
        return self.registry.evolve_skill(
            old_skill.id,
            new_skill,
            content=improvements.get("content", ""),
            evolution_note=evolution_note,
        )
        
    def get_evolution_report(self) -> Dict[str, Any]:
        """
        获取进化报告
        
        Returns:
            进化统计报告
        """
        stats = self.registry.get_stats()
        
        return {
            "total_skills": stats["total_skills"],
            "learning_skills": stats.get("learning_skills", 0),
            "seed_skills": stats.get("seed_skills", 0),
            "stable_skills": stats["total_skills"] - stats.get("learning_skills", 0) - stats.get("seed_skills", 0),
            "detected_patterns": len(self.pattern_detector._pattern_cache),
            "created_seeds": len(self._created_seeds),
            "improvement_suggestions": len(self.suggest_improvements()),
        }
