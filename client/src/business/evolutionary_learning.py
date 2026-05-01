"""
Evolutionary Learning Service - 自进化学习服务

实现基于"自进化"理念的环评工作环境，包含：

1. 感知层（Perception Layer）：多模态信号捕获和行为埋点
2. 记忆层（Memory Layer）：动态知识图谱和自我更新机制
3. 行动层（Action Layer）：动态UI组件生成和强化学习
4. 目标层（Objective Layer）：奖励函数和进化优化

设计理念：
- 不预设业务逻辑，让系统从用户交互中学习
- 基于强化学习的UI进化
- 动态知识图谱作为记忆底座
"""

import json
import asyncio
import uuid
from typing import Dict, Any, Optional, List, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class BehaviorType(Enum):
    """行为类型"""
    MESSAGE_SENT = "message_sent"
    MESSAGE_RECEIVED = "message_received"
    FILE_UPLOADED = "file_uploaded"
    FORM_SUBMITTED = "form_submitted"
    SUGGESTION_CLICKED = "suggestion_clicked"
    ACTION_EXECUTED = "action_executed"
    FEEDBACK_PROVIDED = "feedback_provided"
    REPORT_EXPORTED = "report_exported"
    KNOWLEDGE_ACCESSED = "knowledge_accessed"


class EvolutionStage(Enum):
    """进化阶段"""
    SEED = "seed"              # 初始状态
    IMITATION = "imitation"    # 模仿学习
    PATTERN_DISCOVERY = "pattern_discovery"  # 模式发现
    PROACTIVE_OPTIMIZATION = "proactive_optimization"  # 主动优化


@dataclass
class BehaviorRecord:
    """行为记录"""
    id: str
    user_id: str
    session_id: str
    behavior_type: BehaviorType
    data: Dict[str, Any]
    timestamp: datetime
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InteractionPattern:
    """交互模式"""
    pattern_id: str
    trigger: str  # 触发条件（如"化工项目" + "水源地"）
    actions: List[str]  # 后续动作序列
    confidence: float  # 置信度
    usage_count: int = 0
    success_count: int = 0


@dataclass
class UIComponent:
    """UI组件定义"""
    component_id: str
    type: str  # text_input, select, file_upload, etc.
    label: str
    usage_count: int = 0
    success_rate: float = 0.5
    context_rules: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class RewardSignal:
    """奖励信号"""
    type: str  # compliance, adoption, efficiency
    value: float  # -1 到 1
    timestamp: datetime
    context: Dict[str, Any] = field(default_factory=dict)


class EvolutionaryLearningService:
    """
    自进化学习服务
    
    核心特性：
    1. 行为感知 - 记录用户的每一个交互
    2. 模式发现 - 从数据中自动发现交互规律
    3. 动态UI进化 - 根据学习结果优化组件选择
    4. 奖励机制 - 定义"好"的标准并优化策略
    """
    
    def __init__(self):
        # 行为记录存储
        self._behavior_records: List[BehaviorRecord] = []
        
        # 交互模式库
        self._interaction_patterns: Dict[str, InteractionPattern] = {}
        
        # UI组件基因库
        self._ui_components: Dict[str, UIComponent] = self._init_ui_components()
        
        # 奖励信号历史
        self._reward_signals: List[RewardSignal] = []
        
        # 当前进化阶段
        self._evolution_stage = EvolutionStage.SEED
        
        # 对话上下文存储
        self._sessions: Dict[str, Dict[str, Any]] = {}
        
        # 知识图谱引用（外部依赖）
        self._knowledge_graph = None
        
        # 学习循环任务
        self._learning_task = None
        
        logger.info("✅ EvolutionaryLearningService 初始化完成")
    
    def _init_ui_components(self) -> Dict[str, UIComponent]:
        """初始化基础UI组件库"""
        return {
            "text_input": UIComponent(
                component_id="text_input",
                type="text_input",
                label="文本输入",
                usage_count=0,
                success_rate=0.7
            ),
            "select": UIComponent(
                component_id="select",
                type="select",
                label="下拉选择",
                usage_count=0,
                success_rate=0.8
            ),
            "multi_select": UIComponent(
                component_id="multi_select",
                type="multi_select",
                label="多选框",
                usage_count=0,
                success_rate=0.75
            ),
            "file_upload": UIComponent(
                component_id="file_upload",
                type="file_upload",
                label="文件上传",
                usage_count=0,
                success_rate=0.85
            ),
            "slider": UIComponent(
                component_id="slider",
                type="slider",
                label="滑块",
                usage_count=0,
                success_rate=0.65
            ),
            "textarea": UIComponent(
                component_id="textarea",
                type="textarea",
                label="文本域",
                usage_count=0,
                success_rate=0.72
            ),
            "map": UIComponent(
                component_id="map",
                type="map",
                label="地图标绘",
                usage_count=0,
                success_rate=0.8
            ),
            "table": UIComponent(
                component_id="table",
                type="table",
                label="数据表格",
                usage_count=0,
                success_rate=0.78
            )
        }
    
    def set_knowledge_graph(self, kg):
        """设置知识图谱引用"""
        self._knowledge_graph = kg
    
    def record_behavior(self, user_id: str, session_id: str, 
                        behavior_type: BehaviorType, data: Dict[str, Any],
                        context: Optional[Dict[str, Any]] = None):
        """
        记录用户行为
        
        Args:
            user_id: 用户ID
            session_id: 会话ID
            behavior_type: 行为类型
            data: 行为数据
            context: 上下文信息
        """
        record = BehaviorRecord(
            id=str(uuid.uuid4())[:8],
            user_id=user_id,
            session_id=session_id,
            behavior_type=behavior_type,
            data=data,
            timestamp=datetime.now(),
            context=context or {}
        )
        
        self._behavior_records.append(record)
        
        # 更新组件使用统计
        if behavior_type == BehaviorType.FORM_SUBMITTED:
            self._update_component_stats(data)
        
        # 更新进化阶段
        self._update_evolution_stage()
        
        logger.debug(f"✅ 记录行为: {behavior_type.value}")
    
    def _update_component_stats(self, form_data: Dict[str, Any]):
        """更新组件使用统计"""
        if "formId" in form_data:
            # 简单实现：根据表单ID更新组件使用
            pass
    
    def _update_evolution_stage(self):
        """更新进化阶段"""
        total_records = len(self._behavior_records)
        
        if total_records < 5:
            self._evolution_stage = EvolutionStage.SEED
        elif total_records < 20:
            self._evolution_stage = EvolutionStage.IMITATION
        elif total_records < 50:
            self._evolution_stage = EvolutionStage.PATTERN_DISCOVERY
        else:
            self._evolution_stage = EvolutionStage.PROACTIVE_OPTIMIZATION
    
    def get_evolution_stage(self) -> EvolutionStage:
        """获取当前进化阶段"""
        return self._evolution_stage
    
    async def discover_patterns(self):
        """
        发现交互模式
        
        通过聚类分析从行为数据中发现规律
        """
        if len(self._behavior_records) < 10:
            return
        
        logger.info("🔍 正在进行模式发现...")
        
        # 简单的模式发现：统计连续行为序列
        sequence_counts = defaultdict(int)
        
        # 按会话分组
        sessions = defaultdict(list)
        for record in self._behavior_records:
            sessions[record.session_id].append(record)
        
        # 分析每个会话的行为序列
        for session_id, records in sessions.items():
            # 按时间排序
            records.sort(key=lambda r: r.timestamp)
            
            # 提取行为序列
            sequence = []
            for record in records:
                # 根据消息内容提取关键词
                content = record.data.get('content', '')
                keywords = self._extract_keywords(content)
                if keywords:
                    sequence.extend(keywords)
            
            # 统计二元模式
            for i in range(len(sequence) - 1):
                pattern_key = f"{sequence[i]} -> {sequence[i+1]}"
                sequence_counts[pattern_key] += 1
        
        # 将高频模式添加到模式库
        for pattern_key, count in sequence_counts.items():
            if count >= 3:  # 至少出现3次
                if pattern_key not in self._interaction_patterns:
                    trigger, actions = pattern_key.split(' -> ', 1)
                    self._interaction_patterns[pattern_key] = InteractionPattern(
                        pattern_id=pattern_key,
                        trigger=trigger,
                        actions=[actions],
                        confidence=min(count / 10, 1.0),
                        usage_count=count,
                        success_count=count
                    )
                    logger.info(f"✅ 发现新模式: {pattern_key} (出现 {count} 次)")
    
    def _extract_keywords(self, text: str) -> List[str]:
        """从文本中提取关键词"""
        keywords = []
        
        # 环评相关关键词
        env_keywords = [
            '化工', '化工厂', '水源地', '敏感区', '噪声', '大气', '水',
            '环境', '评价', '环评', '项目', '污染', '监测', '预测',
            '导则', '标准', '报告', '章节', '污染源', '影响'
        ]
        
        for keyword in env_keywords:
            if keyword in text:
                keywords.append(keyword)
        
        return keywords
    
    def suggest_next_action(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        根据上下文建议下一步行动
        
        Args:
            context: 当前上下文
        
        Returns:
            建议的动作列表
        """
        suggestions = []
        
        # 从模式库中查找匹配的模式
        context_text = json.dumps(context)
        
        for pattern in self._interaction_patterns.values():
            if pattern.trigger in context_text:
                # 根据置信度加权
                weight = pattern.confidence * (pattern.success_count / max(pattern.usage_count, 1))
                
                suggestions.append({
                    "action": pattern.actions[0],
                    "confidence": weight,
                    "trigger": pattern.trigger
                })
        
        # 排序并返回前5个
        suggestions.sort(key=lambda x: -x["confidence"])
        return suggestions[:5]
    
    def select_ui_component(self, context: Dict[str, Any]) -> str:
        """
        根据上下文选择最合适的UI组件
        
        Args:
            context: 当前上下文
        
        Returns:
            组件类型
        """
        # 基于强化学习的组件选择
        
        # 简单策略：根据上下文关键词选择
        context_text = json.dumps(context).lower()
        
        if any(k in context_text for k in ['上传', '文件', 'pdf', 'excel']):
            return "file_upload"
        if any(k in context_text for k in ['坐标', '地图', '位置', '敏感区']):
            return "map"
        if any(k in context_text for k in ['监测', '数据', '表格', '数值']):
            return "table"
        if any(k in context_text for k in ['范围', '比例', '数值', '等级']):
            return "slider"
        
        # 默认返回文本输入
        return "text_input"
    
    def generate_form_schema(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        根据上下文生成动态表单
        
        Args:
            context: 当前上下文
        
        Returns:
            表单Schema
        """
        context_text = json.dumps(context).lower()
        
        # 根据上下文生成表单
        if '敏感区' in context_text or '地图' in context_text:
            return {
                "title": "敏感目标标绘",
                "description": "请在地图上圈定敏感目标区域",
                "fields": [
                    {
                        "id": "coordinates",
                        "type": "text_input",
                        "label": "中心点坐标",
                        "placeholder": "例如：32.0603, 118.7969",
                        "required": True
                    },
                    {
                        "id": "radius",
                        "type": "slider",
                        "label": "影响半径(km)",
                        "min": 1,
                        "max": 10,
                        "required": True
                    },
                    {
                        "id": "sensitive_types",
                        "type": "multi_select",
                        "label": "敏感目标类型",
                        "options": [
                            {"value": "water", "label": "水源地"},
                            {"value": "residential", "label": "居民区"},
                            {"value": "school", "label": "学校"},
                            {"value": "hospital", "label": "医院"}
                        ]
                    }
                ]
            }
        
        if '监测' in context_text or '数据' in context_text:
            return {
                "title": "监测数据录入",
                "description": "请填写监测数据",
                "fields": [
                    {
                        "id": "parameter",
                        "type": "text_input",
                        "label": "监测项目",
                        "required": True
                    },
                    {
                        "id": "value",
                        "type": "text_input",
                        "label": "监测值",
                        "required": True
                    },
                    {
                        "id": "unit",
                        "type": "select",
                        "label": "单位",
                        "options": [
                            {"value": "mg/L", "label": "mg/L"},
                            {"value": "μg/m³", "label": "μg/m³"},
                            {"value": "dB(A)", "label": "dB(A)"}
                        ]
                    }
                ]
            }
        
        # 默认表单
        return {
            "title": "补充信息",
            "description": "请补充以下信息",
            "fields": [
                {
                    "id": "content",
                    "type": "textarea",
                    "label": "详细描述",
                    "rows": 4,
                    "placeholder": "请详细描述您的需求..."
                }
            ]
        }
    
    def calculate_reward(self, interaction_data: Dict[str, Any]) -> RewardSignal:
        """
        计算奖励信号
        
        Args:
            interaction_data: 交互数据
        
        Returns:
            奖励信号
        """
        reward = 0.0
        
        # 合规性奖励
        if 'compliance' in interaction_data:
            compliance_score = interaction_data.get('compliance_score', 0)
            reward += (compliance_score - 50) / 100  # -0.5 到 0.5
        
        # 用户采纳奖励
        if interaction_data.get('adopted', False):
            reward += 0.3
        
        # 效率奖励
        if 'time_saved' in interaction_data:
            time_saved = interaction_data.get('time_saved', 0)
            reward += min(time_saved / 60, 0.2)  # 最多+0.2
        
        # 反馈奖励
        feedback = interaction_data.get('feedback', 'neutral')
        if feedback == 'helpful':
            reward += 0.2
        elif feedback == 'not_helpful':
            reward -= 0.3
        
        # 限制范围
        reward = max(-1, min(1, reward))
        
        signal = RewardSignal(
            type="composite",
            value=reward,
            timestamp=datetime.now(),
            context=interaction_data
        )
        
        self._reward_signals.append(signal)
        return signal
    
    def get_evolution_metrics(self) -> Dict[str, float]:
        """获取进化指标"""
        total_records = len(self._behavior_records)
        total_rewards = sum(s.value for s in self._reward_signals)
        pattern_count = len(self._interaction_patterns)
        
        return {
            "compliance_score": self._calculate_compliance_score(),
            "efficiency_score": self._calculate_efficiency_score(),
            "quality_score": self._calculate_quality_score(),
            "pattern_count": pattern_count,
            "total_interactions": total_records,
            "average_reward": total_rewards / max(len(self._reward_signals), 1),
            "evolution_stage": self._evolution_stage.value
        }
    
    def _calculate_compliance_score(self) -> float:
        """计算合规性评分"""
        # 简化实现：基于模式匹配
        env_related_patterns = ['化工', '水源地', '导则', '标准', '敏感区']
        matched = sum(1 for p in self._interaction_patterns if any(k in p for k in env_related_patterns))
        return min(100, matched * 20)
    
    def _calculate_efficiency_score(self) -> float:
        """计算效率评分"""
        # 简化实现：基于平均奖励
        if not self._reward_signals:
            return 50
        avg_reward = sum(s.value for s in self._reward_signals) / len(self._reward_signals)
        return min(100, 50 + avg_reward * 50)
    
    def _calculate_quality_score(self) -> float:
        """计算质量评分"""
        # 简化实现：基于反馈
        if not self._reward_signals:
            return 60
        positive_count = sum(1 for s in self._reward_signals if s.value > 0)
        return min(100, (positive_count / len(self._reward_signals)) * 100)
    
    def start_learning_loop(self):
        """启动学习循环"""
        if self._learning_task:
            return
        
        async def learn():
            while True:
                # 定期发现模式
                await self.discover_patterns()
                
                # 等待一段时间
                await asyncio.sleep(30)  # 每30秒学习一次
        
        self._learning_task = asyncio.create_task(learn())
        logger.info("✅ 学习循环已启动")
    
    def stop_learning_loop(self):
        """停止学习循环"""
        if self._learning_task:
            self._learning_task.cancel()
            self._learning_task = None
            logger.info("✅ 学习循环已停止")
    
    def create_session(self, user_id: str) -> str:
        """创建会话"""
        session_id = str(uuid.uuid4())[:8]
        self._sessions[session_id] = {
            "user_id": user_id,
            "created_at": datetime.now(),
            "context": {}
        }
        return session_id
    
    def update_session_context(self, session_id: str, context: Dict[str, Any]):
        """更新会话上下文"""
        if session_id in self._sessions:
            self._sessions[session_id]["context"].update(context)


# 全局单例
_global_evolutionary_service: Optional[EvolutionaryLearningService] = None


def get_evolutionary_learning_service() -> EvolutionaryLearningService:
    """获取全局自进化学习服务单例"""
    global _global_evolutionary_service
    if _global_evolutionary_service is None:
        _global_evolutionary_service = EvolutionaryLearningService()
    return _global_evolutionary_service


# 测试函数
async def test_evolutionary_service():
    """测试自进化学习服务"""
    print("🧪 测试自进化学习服务")
    print("="*60)
    
    service = get_evolutionary_learning_service()
    
    # 创建会话
    session_id = service.create_session("test_user")
    print(f"\n📤 创建会话: {session_id}")
    
    # 模拟用户行为
    print("\n📝 记录用户行为:")
    
    # 第一轮交互
    service.record_behavior(
        user_id="test_user",
        session_id=session_id,
        behavior_type=BehaviorType.MESSAGE_SENT,
        data={"content": "我要做一个化工厂的环评报告"}
    )
    print("   ✅ 用户发送消息")
    
    service.record_behavior(
        user_id="test_user",
        session_id=session_id,
        behavior_type=BehaviorType.SUGGESTION_CLICKED,
        data={"label": "检索化工环评导则"}
    )
    print("   ✅ 用户点击建议")
    
    # 第二轮交互
    service.record_behavior(
        user_id="test_user",
        session_id=session_id,
        behavior_type=BehaviorType.MESSAGE_SENT,
        data={"content": "项目位于水源地附近"}
    )
    print("   ✅ 用户发送消息")
    
    service.record_behavior(
        user_id="test_user",
        session_id=session_id,
        behavior_type=BehaviorType.FORM_SUBMITTED,
        data={"formId": "sensitive_area", "coordinates": "32.0603, 118.7969"}
    )
    print("   ✅ 用户提交表单")
    
    # 获取进化阶段
    print(f"\n📊 进化阶段: {service.get_evolution_stage().value}")
    
    # 发现模式
    await service.discover_patterns()
    
    # 获取进化指标
    metrics = service.get_evolution_metrics()
    print("\n📈 进化指标:")
    print(f"   合规性: {metrics['compliance_score']:.1f}")
    print(f"   效率: {metrics['efficiency_score']:.1f}")
    print(f"   质量: {metrics['quality_score']:.1f}")
    print(f"   发现模式: {metrics['pattern_count']}")
    
    # 测试组件选择
    print("\n🔧 组件选择测试:")
    context1 = {"content": "上传监测数据Excel"}
    component1 = service.select_ui_component(context1)
    print(f"   '上传Excel' → {component1}")
    
    context2 = {"content": "在地图上标绘敏感区"}
    component2 = service.select_ui_component(context2)
    print(f"   '标绘敏感区' → {component2}")
    
    # 测试表单生成
    print("\n📋 表单生成测试:")
    form = service.generate_form_schema({"content": "敏感区标绘"})
    print(f"   生成表单: {form['title']}")
    
    # 测试奖励计算
    print("\n🎯 奖励计算测试:")
    reward = service.calculate_reward({"compliance_score": 85, "adopted": True})
    print(f"   奖励值: {reward.value:.2f}")
    
    print("\n🎉 自进化学习服务测试完成！")
    return True


if __name__ == "__main__":
    asyncio.run(test_evolutionary_service())