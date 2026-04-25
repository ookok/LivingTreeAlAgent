"""
Honcho 用户建模系统
==================

参考 Hermes Agent 的用户建模机制：
- 学习用户的沟通风格和偏好
- 识别用户方言和表达习惯
- 持续优化交互体验

核心功能：
1. 用户画像 - 记录用户基本信息
2. 偏好学习 - 从交互中学习偏好
3. 方言识别 - 适应用户的表达方式
4. 上下文保持 - 记住跨会话信息

Author: Hermes Desktop Team
Date: 2026-04-25
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class Dialect(Enum):
    """用户方言类型"""
    FORMAL = "formal"           # 正式
    CASUAL = "casual"           # 随意
    TECHNICAL = "technical"     # 技术性
    BRIEF = "brief"             # 简洁
    VERBOSE = "verbose"         # 详细
    MIXED = "mixed"             # 混合


class CommunicationStyle(Enum):
    """沟通风格"""
    DIRECT = "direct"           # 直接给出答案
    EXPLAINING = "explaining"   # 解释过程
    QUESTIONING = "questioning" # 询问确认
    COLLABORATIVE = "collaborative"  # 协作式


@dataclass
class UserPreference:
    """用户偏好"""
    # 输出风格
    preferred_style: CommunicationStyle = CommunicationStyle.EXPLAINING
    detail_level: str = "medium"  # low, medium, high
    include_reasoning: bool = True
    format_code: bool = True
    
    # 响应格式
    use_emoji: bool = False
    use_chinese: bool = True
    response_language: str = "zh-CN"
    
    # 交互偏好
    ask_before_action: bool = True
    show_progress: bool = True
    auto_explain_errors: bool = True
    
    # 技术偏好
    preferred_code_style: str = "pep8"
    comment_level: str = "moderate"  # minimal, moderate, detailed
    variable_naming: str = "snake_case"
    
    # 学习状态
    confidence: float = 1.0
    last_updated: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "preferred_style": self.preferred_style.value,
            "detail_level": self.detail_level,
            "include_reasoning": self.include_reasoning,
            "format_code": self.format_code,
            "use_emoji": self.use_emoji,
            "use_chinese": self.use_chinese,
            "response_language": self.response_language,
            "ask_before_action": self.ask_before_action,
            "show_progress": self.show_progress,
            "auto_explain_errors": self.auto_explain_errors,
            "preferred_code_style": self.preferred_code_style,
            "comment_level": self.comment_level,
            "variable_naming": self.variable_naming,
            "confidence": self.confidence,
            "last_updated": self.last_updated.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "UserPreference":
        """从字典创建"""
        pref = cls()
        for key, value in data.items():
            if hasattr(pref, key):
                if isinstance(value, str) and hasattr(CommunicationStyle, value.upper()):
                    setattr(pref, key, CommunicationStyle[value.upper()])
                else:
                    setattr(pref, key, value)
        return pref


@dataclass
class UserProfile:
    """用户画像"""
    user_id: str
    name: Optional[str] = None
    role: Optional[str] = None  # developer, manager, designer, etc.
    dialect: Dialect = Dialect.MIXED
    
    # 学习到的偏好
    preferences: UserPreference = field(default_factory=UserPreference)
    
    # 已知习惯
    known_triggers: List[str] = field(default_factory=list)  # 用户常用的触发词
    known_phrases: List[str] = field(default_factory=list)  # 用户常用的短语
    known_commands: List[str] = field(default_factory=list)  # 用户常用的命令
    
    # 上下文记忆
    project_context: Dict[str, Any] = field(default_factory=dict)
    recent_tasks: List[Dict] = field(default_factory=list)
    completed_work: List[str] = field(default_factory=list)
    
    # 学习统计
    total_interactions: int = 0
    last_seen: datetime = field(default_factory=datetime.now)
    learning_version: int = 1
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "user_id": self.user_id,
            "name": self.name,
            "role": self.role,
            "dialect": self.dialect.value,
            "preferences": self.preferences.to_dict(),
            "known_triggers": self.known_triggers,
            "known_phrases": self.known_phrases,
            "known_commands": self.known_commands,
            "project_context": self.project_context,
            "recent_tasks": self.recent_tasks[-10:],  # 只保留最近10个
            "completed_work": self.completed_work[-20:],
            "total_interactions": self.total_interactions,
            "last_seen": self.last_seen.isoformat(),
            "learning_version": self.learning_version,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "UserProfile":
        """从字典创建"""
        pref_data = data.pop("preferences", {})
        dialect_str = data.pop("dialect", "mixed")
        
        profile = cls(**data)
        profile.preferences = UserPreference.from_dict(pref_data)
        
        try:
            profile.dialect = Dialect(dialect_str)
        except ValueError:
            profile.dialect = Dialect.MIXED
            
        return profile


class HonchoUserModeling:
    """
    Honcho 用户建模系统
    
    从交互中学习用户偏好，持续优化用户体验
    
    Usage:
        honcho = HonchoUserModeling()
        
        # 记录交互
        honcho.record_interaction(
            query="帮我写一个快速排序",
            response="好的，这是快速排序...",
            user_feedback="太棒了！正是我想要的",
            context={"task_type": "code_generation"}
        )
        
        # 获取用户画像
        profile = honcho.get_profile("default")
        
        # 应用偏好
        adapted_response = honcho.adapt_response(base_response, profile)
    """
    
    def __init__(self, persistence_path: Optional[str] = None):
        """
        初始化 Honcho
        
        Args:
            persistence_path: 用户数据持久化路径
        """
        self.persistence_path = persistence_path
        self._profiles: Dict[str, UserProfile] = {}
        self._interaction_buffer: List[Dict] = []
        self._max_buffer_size = 100
        
        # 方言关键词
        self._dialect_indicators: Dict[Dialect, List[str]] = {
            Dialect.FORMAL: ["请", "麻烦", "能否", "谢谢", "您好", "尊敬"],
            Dialect.CASUAL: ["帮我", "搞", "搞一下", "搞定了", "ok", "好的"],
            Dialect.TECHNICAL: ["API", "SDK", "函数", "模块", "架构", "protocol"],
            Dialect.BRIEF: ["跑", "执行", "搞定", "OK", "done"],
            Dialect.VERBOSE: ["详细", "完整", "全面", "具体", "深入"],
        }
        
        # 风格指示词
        self._style_indicators: Dict[CommunicationStyle, List[str]] = {
            CommunicationStyle.DIRECT: ["直接", "给我", "就", "只要", "只需要"],
            CommunicationStyle.EXPLAINING: ["为什么", "解释", "说明", "原因", "因为"],
            CommunicationStyle.QUESTIONING: ["吗", "吗？", "是否", "要不要", "你看"],
            CommunicationStyle.COLLABORATIVE: ["我们", "一起", "合作", "讨论", "你觉得"],
        }
        
        self._load_profiles()
        
    def _load_profiles(self):
        """加载持久化的用户数据"""
        if not self.persistence_path:
            return
            
        import json
        import os
        
        profile_file = os.path.join(self.persistence_path, "honcho_profiles.json")
        if os.path.exists(profile_file):
            try:
                with open(profile_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for user_id, profile_data in data.items():
                        self._profiles[user_id] = UserProfile.from_dict(profile_data)
                logger.info(f"[Honcho] 加载了 {len(self._profiles)} 个用户画像")
            except Exception as e:
                logger.warning(f"[Honcho] 加载用户数据失败: {e}")
                
    def _save_profiles(self):
        """保存用户数据"""
        if not self.persistence_path:
            return
            
        import json
        import os
        
        os.makedirs(self.persistence_path, exist_ok=True)
        profile_file = os.path.join(self.persistence_path, "honcho_profiles.json")
        
        try:
            data = {uid: profile.to_dict() for uid, profile in self._profiles.items()}
            with open(profile_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug(f"[Honcho] 保存了 {len(self._profiles)} 个用户画像")
        except Exception as e:
            logger.warning(f"[Honcho] 保存用户数据失败: {e}")
            
    def get_profile(self, user_id: str = "default") -> UserProfile:
        """
        获取用户画像
        
        Args:
            user_id: 用户 ID
            
        Returns:
            用户画像（不存在则创建默认）
        """
        if user_id not in self._profiles:
            self._profiles[user_id] = UserProfile(user_id=user_id)
            logger.info(f"[Honcho] 创建新用户画像: {user_id}")
            
        profile = self._profiles[user_id]
        profile.last_seen = datetime.now()
        return profile
        
    def record_interaction(
        self,
        query: str,
        response: str = "",
        user_feedback: Optional[str] = None,
        user_id: str = "default",
        context: Optional[Dict] = None,
    ):
        """
        记录一次交互
        
        Args:
            query: 用户查询
            response: 助手响应
            user_feedback: 用户反馈
            user_id: 用户 ID
            context: 上下文信息
        """
        profile = self.get_profile(user_id)
        profile.total_interactions += 1
        
        # 记录交互
        interaction = {
            "query": query,
            "response": response,
            "feedback": user_feedback,
            "context": context or {},
            "timestamp": datetime.now().isoformat(),
        }
        self._interaction_buffer.append(interaction)
        
        # 定期学习（每10次交互）
        if profile.total_interactions % 10 == 0:
            self._learn_from_buffer(profile)
            
        # 学习触发词和短语
        self._learn_triggers(query, profile)
        
        # 从反馈学习
        if user_feedback:
            self._learn_from_feedback(user_feedback, profile)
            
        # 检测方言
        self._detect_dialect(query, profile)
        
        # 检测风格偏好
        self._detect_style_preference(query, profile)
        
        # 更新最近任务
        if context:
            self._update_recent_tasks(context, profile)
            
        # 持久化
        self._save_profiles()
        
    def _learn_triggers(self, query: str, profile: UserProfile):
        """学习触发词和短语"""
        words = query.split()
        
        # 学习短语（连续2-3个词）
        for i in range(len(words) - 1):
            phrase = ' '.join(words[i:i+2])
            if phrase not in profile.known_phrases:
                profile.known_phrases.append(phrase)
                
        # 学习单字触发词（用户特有的习惯用语）
        if len(query) < 20 and not any(c.isdigit() for c in query):
            # 简短的命令式查询可能是用户的习惯触发
            for word in words[:2]:
                if word not in profile.known_triggers and len(word) > 1:
                    profile.known_triggers.append(word)
                    
        # 限制列表大小
        profile.known_phrases = profile.known_phrases[-50:]
        profile.known_triggers = profile.known_triggers[-30:]
        
    def _learn_from_feedback(self, feedback: str, profile: UserProfile):
        """从用户反馈学习"""
        feedback_lower = feedback.lower()
        
        # 正面反馈
        positive_words = ["好", "棒", "赞", "完美", "正是", "谢谢", "great", "good", "perfect"]
        negative_words = ["不对", "不是", "错了", "不好", "差", "wrong", "bad", "not"]
        
        is_positive = any(w in feedback_lower for w in positive_words)
        is_negative = any(w in feedback_lower for w in negative_words)
        
        # 调整偏好置信度
        if is_positive:
            profile.preferences.confidence = min(1.0, profile.preferences.confidence * 1.05)
        elif is_negative:
            profile.preferences.confidence = max(0.3, profile.preferences.confidence * 0.9)
            
        # 检测详细程度偏好
        if any(w in feedback_lower for w in ["太简单", "太basic", "not detailed"]):
            profile.preferences.detail_level = "high"
        elif any(w in feedback_lower for w in ["太复杂", "太多了", "too much"]):
            profile.preferences.detail_level = "low"
            
        profile.preferences.last_updated = datetime.now()
        
    def _detect_dialect(self, query: str, profile: UserProfile):
        """检测用户方言"""
        query_lower = query.lower()
        
        dialect_scores: Dict[Dialect, int] = {d: 0 for d in Dialect}
        
        for dialect, indicators in self._dialect_indicators.items():
            for indicator in indicators:
                if indicator in query_lower:
                    dialect_scores[dialect] += 1
                    
        # 找出最高分
        max_score = max(dialect_scores.values())
        if max_score > 0:
            detected = max(dialect_scores, key=dialect_scores.get)
            if dialect_scores[detected] > dialect_scores.get(profile.dialect, 0):
                profile.dialect = detected
                logger.debug(f"[Honcho] 检测到方言: {detected.value}")
                
    def _detect_style_preference(self, query: str, profile: UserProfile):
        """检测沟通风格偏好"""
        query_lower = query.lower()
        
        style_scores: Dict[CommunicationStyle, int] = {s: 0 for s in CommunicationStyle}
        
        for style, indicators in self._style_indicators.items():
            for indicator in indicators:
                if indicator in query_lower:
                    style_scores[style] += 1
                    
        max_score = max(style_scores.values())
        if max_score > 0:
            detected = max(style_scores, key=style_scores.get)
            if style_scores[detected] > 2:  # 至少匹配2个词
                profile.preferences.preferred_style = detected
                
    def _update_recent_tasks(self, context: Dict, profile: UserProfile):
        """更新最近任务"""
        task = {
            "type": context.get("task_type", "unknown"),
            "description": context.get("description", "")[:100],
            "timestamp": datetime.now().isoformat(),
        }
        
        profile.recent_tasks.append(task)
        profile.recent_tasks = profile.recent_tasks[-20:]
        
    def _learn_from_buffer(self, profile: UserProfile):
        """从交互缓冲区学习"""
        if not self._interaction_buffer:
            return
            
        # 分析最近的交互
        recent = self._interaction_buffer[-10:]
        
        # 统计成功/失败
        successful = sum(1 for i in recent if i.get("feedback") and 
                        any(w in i["feedback"].lower() for w in ["好", "棒", "ok", "good", "perfect"]))
        failed = len(recent) - successful
        
        # 如果失败率高，建议调整
        if failed > 6:
            logger.info(f"[Honcho] 检测到交互质量下降: 成功率 {successful}/{len(recent)}")
            profile.learning_version += 1
            
        # 清空缓冲区
        self._interaction_buffer = []
        
    def adapt_response(
        self,
        base_response: str,
        user_id: str = "default",
        profile: Optional[UserProfile] = None,
    ) -> str:
        """
        根据用户偏好调整响应
        
        Args:
            base_response: 基础响应
            user_id: 用户 ID
            profile: 可选的用户画像（避免重复查找）
            
        Returns:
            调整后的响应
        """
        if profile is None:
            profile = self.get_profile(user_id)
            
        pref = profile.preferences
        adapted = base_response
        
        # 调整详细程度
        if pref.detail_level == "low":
            # 精简响应
            adapted = self._simplify_response(adapted)
        elif pref.detail_level == "high":
            # 增强响应
            adapted = self._expand_response(adapted)
            
        # 添加解释
        if pref.include_reasoning and "reasoning" not in adapted.lower():
            adapted = self._add_reasoning(adapted)
            
        # 语言适配
        if pref.response_language == "zh-CN" and not self._contains_chinese(adapted):
            # 可以在此处添加翻译逻辑
            pass
            
        return adapted
        
    def _simplify_response(self, response: str) -> str:
        """精简响应"""
        # 移除多余解释
        lines = response.split('\n')
        simplified = []
        for line in lines:
            # 保留标题和关键信息
            if len(line) < 200 or ':' in line or '#' in line:
                simplified.append(line)
        return '\n'.join(simplified) if simplified else response
        
    def _expand_response(self, response: str) -> str:
        """增强响应"""
        # 添加更详细的说明
        if "```" in response:
            response += "\n\n> 以上代码可直接使用。"
        return response
        
    def _add_reasoning(self, response: str) -> str:
        """添加推理说明"""
        return f"**分析：**\n{response}\n\n**结论：** 如上所示。"
        
    def _contains_chinese(self, text: str) -> bool:
        """检查是否包含中文"""
        return bool(re.search(r'[\u4e00-\u9fff]', text))
        
    def adapt_query(
        self,
        query: str,
        user_id: str = "default",
    ) -> str:
        """
        适配用户查询风格
        
        将用户的简短表达转换为完整的查询
        
        Args:
            query: 用户查询
            user_id: 用户 ID
            
        Returns:
            适配后的查询
        """
        profile = self.get_profile(user_id)
        
        # 简短命令扩展
        expansions = {
            "跑": "执行并运行",
            "测": "测试",
            "查": "查询",
            "看": "查看",
            "写": "编写",
        }
        
        adapted = query
        for short, full in expansions.items():
            if query.startswith(short) and len(query) < 10:
                adapted = f"{full}{query[1:]}"
                break
                
        return adapted
        
    def get_context_for_query(
        self,
        query: str,
        user_id: str = "default",
    ) -> Dict[str, Any]:
        """
        获取查询相关上下文
        
        Args:
            query: 用户查询
            user_id: 用户 ID
            
        Returns:
            上下文字典
        """
        profile = self.get_profile(user_id)
        
        context = {
            "project": profile.project_context,
            "recent_tasks": profile.recent_tasks[-3:],
            "dialect": profile.dialect.value,
            "style": profile.preferences.preferred_style.value,
        }
        
        # 查找相关的已完成工作
        query_keywords = set(query.lower().split())
        related_work = [
            w for w in profile.completed_work
            if any(kw in w.lower() for kw in query_keywords)
        ]
        
        if related_work:
            context["related_completed"] = related_work[:5]
            
        return context
        
    def remember_completed_work(
        self,
        description: str,
        user_id: str = "default",
    ):
        """记录完成的工作"""
        profile = self.get_profile(user_id)
        profile.completed_work.append(description)
        profile.completed_work = profile.completed_work[-50:]
        self._save_profiles()
        
    def update_project_context(
        self,
        key: str,
        value: Any,
        user_id: str = "default",
    ):
        """更新项目上下文"""
        profile = self.get_profile(user_id)
        profile.project_context[key] = value
        self._save_profiles()
        
    def get_report(self, user_id: str = "default") -> Dict[str, Any]:
        """
        获取用户画像报告
        
        Returns:
            用户分析报告
        """
        profile = self.get_profile(user_id)
        
        return {
            "user_id": user_id,
            "name": profile.name,
            "role": profile.role,
            "dialect": profile.dialect.value,
            "style": profile.preferences.preferred_style.value,
            "detail_level": profile.preferences.detail_level,
            "total_interactions": profile.total_interactions,
            "known_triggers_count": len(profile.known_triggers),
            "known_phrases_count": len(profile.known_phrases),
            "recent_tasks_count": len(profile.recent_tasks),
            "completed_work_count": len(profile.completed_work),
            "confidence": profile.preferences.confidence,
            "learning_version": profile.learning_version,
        }
