"""
User Preference Model - 用户偏好模型

核心功能：
1. 用户画像构建 - 基于行为数据构建用户画像
2. 偏好学习 - 从用户行为中学习偏好
3. 个性化推荐 - 根据偏好推荐组件和布局
4. 自适应调整 - 根据用户反馈持续优化

设计理念：
- 无监督学习用户偏好
- 多维度用户画像
- 实时偏好更新
- 个性化UI体验
"""

import json
import asyncio
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class UserRole(Enum):
    """用户角色"""
    ADMIN = "admin"           # 管理员
    ENGINEER = "engineer"     # 工程师
    MANAGER = "manager"       # 项目经理
    REVIEWER = "reviewer"     # 评审专家
    GUEST = "guest"           # 访客


class PreferenceCategory(Enum):
    """偏好类别"""
    COMPONENT = "component"   # 组件偏好
    LAYOUT = "layout"         # 布局偏好
    CONTENT = "content"       # 内容偏好
    INTERACTION = "interaction"  # 交互偏好
    THEME = "theme"           # 主题偏好


@dataclass
class UserProfile:
    """用户画像"""
    user_id: str
    role: UserRole = UserRole.GUEST
    preferences: Dict[str, float] = field(default_factory=dict)  # 偏好评分
    behavior_patterns: Dict[str, int] = field(default_factory=dict)  # 行为模式
    interaction_history: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class PreferencePrediction:
    """偏好预测"""
    component_id: str
    score: float  # 偏好分数 0-1
    confidence: float  # 置信度 0-1
    reason: Optional[str] = None


class UserPreferenceModel:
    """
    用户偏好模型
    
    核心特性：
    1. 用户画像构建 - 基于行为数据构建多维画像
    2. 偏好学习 - 从交互中学习用户偏好
    3. 个性化推荐 - 根据偏好推荐最优组件
    4. 自适应调整 - 实时更新偏好模型
    """
    
    def __init__(self):
        # 用户画像存储
        self._user_profiles: Dict[str, UserProfile] = {}
        
        # 默认偏好（新用户使用）
        self._default_preferences = {
            "text_input": 0.8,
            "select": 0.75,
            "button": 0.9,
            "card": 0.7,
            "vertical_layout": 0.85,
            "minimal_theme": 0.7
        }
        
        # 偏好权重调整因子
        self._learning_rate = 0.1  # 学习率
        
        logger.info("✅ UserPreferenceModel 初始化完成")
    
    def get_or_create_profile(self, user_id: str) -> UserProfile:
        """获取或创建用户画像"""
        if user_id not in self._user_profiles:
            self._user_profiles[user_id] = UserProfile(user_id=user_id)
            # 初始化默认偏好
            self._user_profiles[user_id].preferences.update(self._default_preferences)
            logger.info(f"✅ 创建新用户画像: {user_id}")
        
        return self._user_profiles[user_id]
    
    def update_profile(self, user_id: str, updates: Dict[str, Any]):
        """更新用户画像"""
        profile = self.get_or_create_profile(user_id)
        
        if 'role' in updates:
            profile.role = UserRole(updates['role'])
        
        profile.updated_at = datetime.now()
    
    def record_interaction(self, user_id: str, interaction: Dict[str, Any]):
        """
        记录用户交互
        
        Args:
            user_id: 用户ID
            interaction: 交互数据
        """
        profile = self.get_or_create_profile(user_id)
        
        # 添加到历史
        profile.interaction_history.append({
            **interaction,
            "timestamp": datetime.now().isoformat()
        })
        
        # 限制历史长度
        if len(profile.interaction_history) > 100:
            profile.interaction_history = profile.interaction_history[-100:]
        
        # 更新行为模式统计
        action_type = interaction.get('action_type', 'unknown')
        profile.behavior_patterns[action_type] = profile.behavior_patterns.get(action_type, 0) + 1
        
        # 学习偏好
        self._learn_preferences(user_id, interaction)
        
        profile.updated_at = datetime.now()
    
    def _learn_preferences(self, user_id: str, interaction: Dict[str, Any]):
        """从交互中学习偏好"""
        profile = self.get_or_create_profile(user_id)
        
        # 提取关键信息
        component_id = interaction.get('component_id')
        feedback = interaction.get('feedback')
        success = interaction.get('success', True)
        
        if component_id:
            # 计算奖励
            reward = 0.0
            if feedback == 'helpful':
                reward = 0.3
            elif feedback == 'not_helpful':
                reward = -0.3
            elif success:
                reward = 0.1
            else:
                reward = -0.1
            
            # 更新偏好分数（使用增量学习）
            current_score = profile.preferences.get(component_id, 0.5)
            new_score = current_score + self._learning_rate * reward
            
            # 限制在0-1范围内
            profile.preferences[component_id] = max(0, min(1, new_score))
            
            logger.debug(f"更新偏好: {component_id} = {profile.preferences[component_id]:.3f}")
    
    def predict_preferences(self, user_id: str, context: Dict[str, Any]) -> List[PreferencePrediction]:
        """
        预测用户偏好
        
        Args:
            user_id: 用户ID
            context: 当前上下文
        
        Returns:
            偏好预测列表（按分数排序）
        """
        profile = self.get_or_create_profile(user_id)
        
        predictions = []
        
        # 获取当前上下文相关的组件
        intent = self._detect_intent(context.get('text', ''))
        relevant_components = self._get_relevant_components(intent)
        
        for component_id in relevant_components:
            # 获取偏好分数
            score = profile.preferences.get(component_id, 0.5)
            
            # 计算置信度（基于交互次数）
            interaction_count = sum(1 for i in profile.interaction_history 
                                   if i.get('component_id') == component_id)
            confidence = min(interaction_count / 10, 1.0)
            
            # 添加预测
            predictions.append(PreferencePrediction(
                component_id=component_id,
                score=score,
                confidence=confidence,
                reason=self._explain_prediction(component_id, profile)
            ))
        
        # 排序
        predictions.sort(key=lambda p: -p.score)
        
        return predictions
    
    def _detect_intent(self, text: str) -> str:
        """简单的意图检测"""
        text = text.lower()
        
        if any(k in text for k in ['上传', '文件']):
            return 'upload'
        if any(k in text for k in ['填写', '表单']):
            return 'form_fill'
        if any(k in text for k in ['地图', '标绘']):
            return 'map'
        if any(k in text for k in ['报告', '生成']):
            return 'report'
        return 'general'
    
    def _get_relevant_components(self, intent: str) -> List[str]:
        """根据意图获取相关组件"""
        component_map = {
            'upload': ['file_upload', 'button', 'text'],
            'form_fill': ['text_input', 'select', 'textarea', 'button', 'card'],
            'map': ['map', 'text_input', 'slider', 'button'],
            'report': ['select', 'multi_select', 'button', 'card', 'chart'],
            'general': ['text_input', 'button', 'card', 'text']
        }
        
        return component_map.get(intent, ['text_input', 'button', 'card'])
    
    def _explain_prediction(self, component_id: str, profile: UserProfile) -> str:
        """解释预测原因"""
        score = profile.preferences.get(component_id, 0.5)
        
        if score >= 0.7:
            return "用户之前多次使用并反馈良好"
        elif score >= 0.5:
            return "用户对该组件有一定偏好"
        elif score >= 0.3:
            return "用户偶尔使用该组件"
        else:
            return "用户较少使用该组件"
    
    def recommend_components(self, user_id: str, context: Dict[str, Any], 
                            top_n: int = 3) -> List[str]:
        """
        推荐组件
        
        Args:
            user_id: 用户ID
            context: 当前上下文
            top_n: 返回前N个推荐
        
        Returns:
            组件ID列表
        """
        predictions = self.predict_preferences(user_id, context)
        return [p.component_id for p in predictions[:top_n]]
    
    def personalize_ui(self, user_id: str, ui_schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        个性化UI
        
        Args:
            user_id: 用户ID
            ui_schema: 原始UI Schema
        
        Returns:
            个性化后的UI Schema
        """
        profile = self.get_or_create_profile(user_id)
        predictions = self.predict_preferences(user_id, {})
        
        # 创建个性化副本
        personalized = json.loads(json.dumps(ui_schema))
        
        # 根据偏好调整组件顺序
        if 'components' in personalized:
            components = personalized['components']
            
            # 为每个组件分配偏好分数
            def get_component_score(component: Dict[str, Any]) -> float:
                comp_id = component.get('id', '')
                # 尝试从预测中获取分数
                for pred in predictions:
                    if pred.component_id in comp_id or comp_id in pred.component_id:
                        return pred.score
                return 0.5
            
            # 根据偏好排序组件（保留原有的组顺序）
            personalized['components'] = sorted(
                components,
                key=get_component_score,
                reverse=True
            )
        
        # 应用主题偏好
        theme = profile.preferences.get('theme', 'minimal')
        personalized['theme'] = theme
        
        return personalized
    
    def get_profile(self, user_id: str) -> Optional[UserProfile]:
        """获取用户画像"""
        return self._user_profiles.get(user_id)
    
    def get_preferences(self, user_id: str) -> Dict[str, float]:
        """获取用户偏好"""
        profile = self.get_or_create_profile(user_id)
        return profile.preferences
    
    def reset_preferences(self, user_id: str):
        """重置用户偏好"""
        if user_id in self._user_profiles:
            self._user_profiles[user_id].preferences = dict(self._default_preferences)
            self._user_profiles[user_id].interaction_history = []
            logger.info(f"✅ 重置用户偏好: {user_id}")
    
    async def batch_update_profiles(self, interactions: List[Dict[str, Any]]):
        """批量更新用户画像"""
        for interaction in interactions:
            user_id = interaction.get('user_id')
            if user_id:
                self.record_interaction(user_id, interaction)


# 全局单例
_global_user_preference_model: Optional[UserPreferenceModel] = None


def get_user_preference_model() -> UserPreferenceModel:
    """获取全局用户偏好模型单例"""
    global _global_user_preference_model
    if _global_user_preference_model is None:
        _global_user_preference_model = UserPreferenceModel()
    return _global_user_preference_model


# 测试函数
async def test_user_preference_model():
    """测试用户偏好模型"""
    print("🧪 测试用户偏好模型")
    print("="*60)
    
    model = get_user_preference_model()
    
    # 创建用户画像
    print("\n👤 创建用户画像")
    profile = model.get_or_create_profile("test_engineer")
    print(f"   用户ID: {profile.user_id}")
    print(f"   角色: {profile.role.value}")
    
    # 更新用户角色
    print("\n🔄 更新用户角色")
    model.update_profile("test_engineer", {"role": "engineer"})
    profile = model.get_profile("test_engineer")
    print(f"   更新后角色: {profile.role.value}")
    
    # 模拟用户交互
    print("\n📝 模拟用户交互")
    interactions = [
        {"component_id": "file_upload", "action_type": "upload", "feedback": "helpful"},
        {"component_id": "text_input", "action_type": "input", "success": True},
        {"component_id": "file_upload", "action_type": "upload", "success": True},
        {"component_id": "button", "action_type": "click", "success": True},
        {"component_id": "select", "action_type": "select", "feedback": "helpful"},
        {"component_id": "textarea", "action_type": "input", "success": True},
        {"component_id": "file_upload", "action_type": "upload", "feedback": "helpful"},
        {"component_id": "card", "action_type": "view", "success": True},
    ]
    
    for i, interaction in enumerate(interactions):
        model.record_interaction("test_engineer", interaction)
        if (i + 1) % 4 == 0:
            print(f"   已记录 {i + 1} 次交互")
    
    # 获取偏好
    print("\n🎯 获取用户偏好")
    preferences = model.get_preferences("test_engineer")
    print("   偏好分数:")
    for comp, score in sorted(preferences.items(), key=lambda x: -x[1])[:5]:
        print(f"     {comp}: {score:.3f}")
    
    # 预测偏好
    print("\n🔮 预测偏好")
    context = {"text": "上传监测数据"}
    predictions = model.predict_preferences("test_engineer", context)
    print("   预测结果:")
    for pred in predictions:
        print(f"     {pred.component_id}: 分数={pred.score:.3f}, 置信度={pred.confidence:.3f}")
    
    # 推荐组件
    print("\n✨ 推荐组件")
    recommendations = model.recommend_components("test_engineer", context, top_n=3)
    print(f"   推荐组件: {recommendations}")
    
    # 个性化UI
    print("\n🎨 个性化UI")
    test_ui = {
        "id": "test_form",
        "type": "vertical",
        "components": [
            {"id": "name", "type": "text_input", "label": "姓名"},
            {"id": "submit", "type": "button", "label": "提交"},
            {"id": "upload", "type": "file_upload", "label": "上传文件"},
            {"id": "select", "type": "select", "label": "选择类型"}
        ]
    }
    
    personalized = model.personalize_ui("test_engineer", test_ui)
    component_types = [c['type'] for c in personalized['components']]
    print(f"   个性化后组件顺序: {component_types}")
    
    # 测试新用户
    print("\n🆕 测试新用户")
    new_prefs = model.get_preferences("new_user")
    print(f"   新用户默认偏好数量: {len(new_prefs)}")
    
    print("\n🎉 用户偏好模型测试完成！")
    return True


if __name__ == "__main__":
    asyncio.run(test_user_preference_model())