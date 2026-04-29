"""
个性化学习系统
从用户行为中学习，适应用户的编程风格和偏好
"""

import os
import json
import re
import asyncio
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class UserActionType(Enum):
    """用户操作类型"""
    CODE_COMPLETION = "code_completion"
    CODE_GENERATION = "code_generation"
    ERROR_FIX = "error_fix"
    REFACTORING = "refactoring"
    TEST_GENERATION = "test_generation"
    DOCUMENTATION = "documentation"
    SEARCH = "search"
    NAVIGATION = "navigation"
    SETTING_CHANGE = "setting_change"
    FEEDBACK = "feedback"


class FeedbackType(Enum):
    """反馈类型"""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


@dataclass
class UserAction:
    """用户操作"""
    id: str
    action_type: UserActionType
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UserFeedback:
    """用户反馈"""
    id: str
    action_id: str
    feedback_type: FeedbackType
    comment: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class UserProfile:
    """
    用户配置文件
    存储用户的编程风格、偏好和学习状态
    """
    user_id: str
    name: str
    programming_languages: List[str] = field(default_factory=list)
    preferred_frameworks: List[str] = field(default_factory=list)
    coding_style: Dict[str, Any] = field(default_factory=dict)
    learning_goals: List[str] = field(default_factory=list)
    skill_level: Dict[str, str] = field(default_factory=dict)  # 语言 -> 级别
    preferences: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class LearningItem:
    """学习项"""
    id: str
    title: str
    content: str
    difficulty: str  # 初级/中级/高级
    categories: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    estimated_time: int = 0  # 分钟
    completed: bool = False
    completed_at: Optional[datetime] = None


class UserActionTracker:
    """用户操作跟踪器"""
    
    def __init__(self, storage_path: str = None):
        self.storage_path = storage_path or os.path.expanduser("~/.hermes-desktop/user_actions")
        os.makedirs(self.storage_path, exist_ok=True)
        self.actions: List[UserAction] = []
        self.feedback: Dict[str, UserFeedback] = {}
        self._load_actions()
    
    def _load_actions(self):
        """加载用户操作"""
        actions_file = os.path.join(self.storage_path, "actions.json")
        if os.path.exists(actions_file):
            try:
                with open(actions_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for action_data in data.get('actions', []):
                        action = UserAction(
                            id=action_data['id'],
                            action_type=UserActionType(action_data['action_type']),
                            content=action_data['content'],
                            timestamp=datetime.fromisoformat(action_data['timestamp']),
                            metadata=action_data.get('metadata', {})
                        )
                        self.actions.append(action)
                    
                    for feedback_data in data.get('feedback', []):
                        feedback = UserFeedback(
                            id=feedback_data['id'],
                            action_id=feedback_data['action_id'],
                            feedback_type=FeedbackType(feedback_data['feedback_type']),
                            comment=feedback_data.get('comment', ''),
                            timestamp=datetime.fromisoformat(feedback_data['timestamp'])
                        )
                        self.feedback[feedback_data['id']] = feedback
            except Exception as e:
                print(f"加载用户操作失败: {e}")
    
    def _save_actions(self):
        """保存用户操作"""
        actions_file = os.path.join(self.storage_path, "actions.json")
        data = {
            'actions': [],
            'feedback': []
        }
        
        for action in self.actions:
            data['actions'].append({
                'id': action.id,
                'action_type': action.action_type.value,
                'content': action.content,
                'timestamp': action.timestamp.isoformat(),
                'metadata': action.metadata
            })
        
        for feedback in self.feedback.values():
            data['feedback'].append({
                'id': feedback.id,
                'action_id': feedback.action_id,
                'feedback_type': feedback.feedback_type.value,
                'comment': feedback.comment,
                'timestamp': feedback.timestamp.isoformat()
            })
        
        with open(actions_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def track_action(self, action_type: UserActionType, content: str, **metadata) -> str:
        """跟踪用户操作"""
        action_id = f"action_{int(datetime.now().timestamp())}_{hash(content) % 10000}"
        action = UserAction(
            id=action_id,
            action_type=action_type,
            content=content,
            metadata=metadata
        )
        self.actions.append(action)
        self._save_actions()
        return action_id
    
    def add_feedback(self, action_id: str, feedback_type: FeedbackType, comment: str = "") -> str:
        """添加用户反馈"""
        feedback_id = f"feedback_{int(datetime.now().timestamp())}"
        feedback = UserFeedback(
            id=feedback_id,
            action_id=action_id,
            feedback_type=feedback_type,
            comment=comment
        )
        self.feedback[feedback_id] = feedback
        self._save_actions()
        return feedback_id
    
    def get_actions(self, action_type: Optional[UserActionType] = None, limit: int = 100) -> List[UserAction]:
        """获取用户操作"""
        actions = self.actions
        if action_type:
            actions = [a for a in actions if a.action_type == action_type]
        return actions[-limit:]
    
    def get_feedback(self, action_id: str) -> Optional[UserFeedback]:
        """获取用户反馈"""
        for feedback in self.feedback.values():
            if feedback.action_id == action_id:
                return feedback
        return None
    
    def analyze_actions(self) -> Dict[str, Any]:
        """分析用户操作"""
        analysis = {
            'total_actions': len(self.actions),
            'actions_by_type': {},
            'most_frequent_actions': [],
            'recent_actions': []
        }
        
        # 按类型统计
        for action in self.actions:
            action_type = action.action_type.value
            analysis['actions_by_type'][action_type] = analysis['actions_by_type'].get(action_type, 0) + 1
        
        # 最频繁的操作
        most_frequent = sorted(
            analysis['actions_by_type'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        analysis['most_frequent_actions'] = most_frequent
        
        # 最近的操作
        recent = sorted(
            self.actions,
            key=lambda x: x.timestamp,
            reverse=True
        )[:10]
        analysis['recent_actions'] = [
            {
                'type': a.action_type.value,
                'content': a.content[:100],
                'timestamp': a.timestamp.isoformat()
            }
            for a in recent
        ]
        
        return analysis


class PersonalizedLearningSystem:
    """个性化学习系统"""
    
    def __init__(self, storage_path: str = None):
        self.storage_path = storage_path or os.path.expanduser("~/.hermes-desktop/personalized_learning")
        os.makedirs(self.storage_path, exist_ok=True)
        self.user_profiles: Dict[str, UserProfile] = {}
        self.learning_items: Dict[str, LearningItem] = {}
        self.action_tracker = UserActionTracker(os.path.join(self.storage_path, "actions"))
        self._load_profiles()
        self._load_learning_items()
    
    def _load_profiles(self):
        """加载用户配置文件"""
        profiles_file = os.path.join(self.storage_path, "profiles.json")
        if os.path.exists(profiles_file):
            try:
                with open(profiles_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for user_id, profile_data in data.items():
                        profile = UserProfile(
                            user_id=user_id,
                            name=profile_data['name'],
                            programming_languages=profile_data.get('programming_languages', []),
                            preferred_frameworks=profile_data.get('preferred_frameworks', []),
                            coding_style=profile_data.get('coding_style', {}),
                            learning_goals=profile_data.get('learning_goals', []),
                            skill_level=profile_data.get('skill_level', {}),
                            preferences=profile_data.get('preferences', {}),
                            created_at=datetime.fromisoformat(profile_data.get('created_at')),
                            updated_at=datetime.fromisoformat(profile_data.get('updated_at'))
                        )
                        self.user_profiles[user_id] = profile
            except Exception as e:
                print(f"加载用户配置文件失败: {e}")
    
    def _save_profiles(self):
        """保存用户配置文件"""
        profiles_file = os.path.join(self.storage_path, "profiles.json")
        data = {}
        for user_id, profile in self.user_profiles.items():
            data[user_id] = {
                'name': profile.name,
                'programming_languages': profile.programming_languages,
                'preferred_frameworks': profile.preferred_frameworks,
                'coding_style': profile.coding_style,
                'learning_goals': profile.learning_goals,
                'skill_level': profile.skill_level,
                'preferences': profile.preferences,
                'created_at': profile.created_at.isoformat(),
                'updated_at': profile.updated_at.isoformat()
            }
        with open(profiles_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _load_learning_items(self):
        """加载学习项"""
        items_file = os.path.join(self.storage_path, "learning_items.json")
        if os.path.exists(items_file):
            try:
                with open(items_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for item_id, item_data in data.items():
                        item = LearningItem(
                            id=item_id,
                            title=item_data['title'],
                            content=item_data['content'],
                            difficulty=item_data.get('difficulty', '中级'),
                            categories=item_data.get('categories', []),
                            tags=item_data.get('tags', []),
                            estimated_time=item_data.get('estimated_time', 0),
                            completed=item_data.get('completed', False),
                            completed_at=datetime.fromisoformat(item_data.get('completed_at')) if item_data.get('completed_at') else None
                        )
                        self.learning_items[item_id] = item
            except Exception as e:
                print(f"加载学习项失败: {e}")
    
    def _save_learning_items(self):
        """保存学习项"""
        items_file = os.path.join(self.storage_path, "learning_items.json")
        data = {}
        for item_id, item in self.learning_items.items():
            data[item_id] = {
                'title': item.title,
                'content': item.content,
                'difficulty': item.difficulty,
                'categories': item.categories,
                'tags': item.tags,
                'estimated_time': item.estimated_time,
                'completed': item.completed,
                'completed_at': item.completed_at.isoformat() if item.completed_at else None
            }
        with open(items_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def create_user_profile(self, user_id: str, name: str) -> UserProfile:
        """创建用户配置文件"""
        profile = UserProfile(
            user_id=user_id,
            name=name
        )
        self.user_profiles[user_id] = profile
        self._save_profiles()
        return profile
    
    def get_user_profile(self, user_id: str) -> Optional[UserProfile]:
        """获取用户配置文件"""
        return self.user_profiles.get(user_id)
    
    def update_user_profile(self, user_id: str, **updates) -> bool:
        """更新用户配置文件"""
        profile = self.user_profiles.get(user_id)
        if not profile:
            return False
        
        for key, value in updates.items():
            if hasattr(profile, key):
                setattr(profile, key, value)
        profile.updated_at = datetime.now()
        self._save_profiles()
        return True
    
    def add_learning_item(self, title: str, content: str, difficulty: str = "中级", categories: List[str] = None, tags: List[str] = None, estimated_time: int = 0) -> str:
        """添加学习项"""
        item_id = f"learning_{int(datetime.now().timestamp())}"
        item = LearningItem(
            id=item_id,
            title=title,
            content=content,
            difficulty=difficulty,
            categories=categories or [],
            tags=tags or [],
            estimated_time=estimated_time
        )
        self.learning_items[item_id] = item
        self._save_learning_items()
        return item_id
    
    def mark_learning_item_completed(self, item_id: str) -> bool:
        """标记学习项为已完成"""
        item = self.learning_items.get(item_id)
        if not item:
            return False
        item.completed = True
        item.completed_at = datetime.now()
        self._save_learning_items()
        return True
    
    def get_recommendations(self, user_id: str) -> List[LearningItem]:
        """获取学习推荐"""
        profile = self.user_profiles.get(user_id)
        if not profile:
            return []
        
        # 基于用户配置文件生成推荐
        recommendations = []
        for item in self.learning_items.values():
            if item.completed:
                continue
            
            # 基于语言匹配
            language_match = any(lang in item.tags for lang in profile.programming_languages)
            
            # 基于难度匹配
            difficulty_match = True
            if profile.skill_level:
                # 简单的难度匹配逻辑
                pass
            
            if language_match or difficulty_match:
                recommendations.append(item)
        
        # 按估计时间排序
        recommendations.sort(key=lambda x: x.estimated_time)
        return recommendations[:5]
    
    def learn_from_action(self, user_id: str, action_type: UserActionType, content: str, **metadata):
        """从用户操作中学习"""
        # 跟踪操作
        action_id = self.action_tracker.track_action(action_type, content, **metadata)
        
        # 更新用户配置文件
        profile = self.user_profiles.get(user_id)
        if not profile:
            profile = self.create_user_profile(user_id, f"User {user_id}")
        
        # 分析操作内容
        if action_type == UserActionType.CODE_COMPLETION:
            # 学习编程风格
            self._learn_coding_style(profile, content)
        elif action_type == UserActionType.SEARCH:
            # 学习感兴趣的主题
            self._learn_interests(profile, content)
        
        self._save_profiles()
        return action_id
    
    def _learn_coding_style(self, profile: UserProfile, code: str):
        """学习编程风格"""
        # 分析缩进风格
        indent_match = re.search(r'^([ \t]+)', code, re.MULTILINE)
        if indent_match:
            indent = indent_match.group(1)
            if ' ' in indent:
                profile.coding_style['indent_type'] = 'spaces'
                profile.coding_style['indent_size'] = len(indent)
            else:
                profile.coding_style['indent_type'] = 'tabs'
        
        # 分析命名风格
        if re.search(r'[a-z]+_[a-z]+', code):
            profile.coding_style['naming_convention'] = 'snake_case'
        elif re.search(r'[A-Z][a-z]+', code):
            profile.coding_style['naming_convention'] = 'camelCase'
    
    def _learn_interests(self, profile: UserProfile, search_query: str):
        """学习用户兴趣"""
        # 提取关键词
        keywords = search_query.lower().split()
        # 简单的兴趣分析
        for keyword in keywords:
            if keyword in ['python', 'javascript', 'react', 'vue', 'flask', 'django']:
                if keyword not in profile.programming_languages:
                    profile.programming_languages.append(keyword)
    
    def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """获取用户统计信息"""
        profile = self.user_profiles.get(user_id)
        if not profile:
            return {}
        
        stats = {
            'user_id': user_id,
            'name': profile.name,
            'programming_languages': profile.programming_languages,
            'preferred_frameworks': profile.preferred_frameworks,
            'learning_goals': profile.learning_goals,
            'skill_level': profile.skill_level,
            'coding_style': profile.coding_style,
            'completed_learning_items': len([i for i in self.learning_items.values() if i.completed]),
            'total_learning_items': len(self.learning_items)
        }
        
        # 添加操作统计
        action_analysis = self.action_tracker.analyze_actions()
        stats['action_stats'] = action_analysis
        
        return stats
    
    def export_user_data(self, user_id: str, file_path: str) -> bool:
        """导出用户数据"""
        profile = self.user_profiles.get(user_id)
        if not profile:
            return False
        
        data = {
            'profile': {
                'user_id': profile.user_id,
                'name': profile.name,
                'programming_languages': profile.programming_languages,
                'preferred_frameworks': profile.preferred_frameworks,
                'coding_style': profile.coding_style,
                'learning_goals': profile.learning_goals,
                'skill_level': profile.skill_level,
                'preferences': profile.preferences
            },
            'learning_items': [
                {
                    'id': item.id,
                    'title': item.title,
                    'completed': item.completed
                }
                for item in self.learning_items.values()
            ],
            'action_stats': self.action_tracker.analyze_actions()
        }
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"导出用户数据失败: {e}")
            return False


def create_personalized_learning_system(storage_path: str = None) -> PersonalizedLearningSystem:
    """
    创建个性化学习系统
    
    Args:
        storage_path: 存储路径
        
    Returns:
        PersonalizedLearningSystem: 个性化学习系统实例
    """
    return PersonalizedLearningSystem(storage_path)


def get_default_learning_items() -> List[Dict[str, Any]]:
    """
    获取默认学习项
    
    Returns:
        List[Dict[str, Any]]: 默认学习项列表
    """
    return [
        {
            'title': 'Python 基础语法',
            'content': '学习Python的基本语法，包括变量、数据类型、控制流等',
            'difficulty': '初级',
            'categories': ['编程基础'],
            'tags': ['python', 'basics'],
            'estimated_time': 60
        },
        {
            'title': 'React 组件开发',
            'content': '学习React组件的创建、状态管理和生命周期',
            'difficulty': '中级',
            'categories': ['前端开发'],
            'tags': ['react', 'frontend'],
            'estimated_time': 90
        },
        {
            'title': 'Flask 后端开发',
            'content': '学习使用Flask框架构建RESTful API',
            'difficulty': '中级',
            'categories': ['后端开发'],
            'tags': ['flask', 'backend', 'api'],
            'estimated_time': 120
        }
    ]