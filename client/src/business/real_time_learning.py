"""
Real-Time Learning Service - 实时学习循环服务

核心功能：
1. 后台学习任务 - 持续分析用户行为数据
2. 模式发现 - 从交互数据中发现规律
3. 组件优化 - 基于反馈优化组件选择策略
4. 自适应更新 - 实时更新推荐模型

设计理念：
- 持续学习：无需人工干预，自动从数据中学习
- 增量更新：每次学习只处理新增数据
- 低延迟：快速响应用户行为变化
"""

import asyncio
import json
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class LearningPhase(Enum):
    """学习阶段"""
    COLLECTING = "collecting"       # 数据收集
    ANALYZING = "analyzing"         # 数据分析
    PATTERN_DISCOVERY = "pattern_discovery"  # 模式发现
    OPTIMIZING = "optimizing"       # 策略优化
    UPDATING = "updating"           # 模型更新


@dataclass
class LearningTask:
    """学习任务"""
    task_id: str
    phase: LearningPhase
    status: str  # pending, running, completed, failed
    progress: float  # 0-100
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None


@dataclass
class PatternUpdate:
    """模式更新"""
    pattern_id: str
    trigger: str
    actions: List[str]
    confidence: float
    update_type: str  # new, updated, deprecated


class RealTimeLearningService:
    """
    实时学习服务
    
    核心特性：
    1. 后台持续学习循环
    2. 增量模式发现
    3. 自适应组件优化
    4. 实时策略更新
    """
    
    def __init__(self):
        # 学习任务队列
        self._task_queue: asyncio.Queue = asyncio.Queue()
        
        # 当前运行任务
        self._current_task: Optional[LearningTask] = None
        
        # 学习循环任务
        self._learning_loop_task: Optional[asyncio.Task] = None
        
        # 数据缓存（用于增量学习）
        self._data_cache: List[Dict[str, Any]] = []
        self._last_processed_time: Optional[datetime] = None
        
        # 学习统计
        self._learning_stats: Dict[str, Any] = {
            "total_learning_cycles": 0,
            "patterns_discovered": 0,
            "strategies_updated": 0,
            "last_learning_time": None
        }
        
        # 更新订阅者
        self._subscribers: List[Callable] = []
        
        # 学习间隔（秒）
        self._learning_interval = 30  # 默认30秒学习一次
        
        # 最小数据量阈值
        self._min_data_threshold = 5
        
        logger.info("✅ RealTimeLearningService 初始化完成")
    
    async def start(self):
        """启动学习服务"""
        if self._learning_loop_task:
            logger.warning("学习服务已在运行中")
            return
        
        self._learning_loop_task = asyncio.create_task(self._learning_loop())
        logger.info("✅ 实时学习服务已启动")
    
    async def stop(self):
        """停止学习服务"""
        if self._learning_loop_task:
            self._learning_loop_task.cancel()
            self._learning_loop_task = None
            logger.info("✅ 实时学习服务已停止")
    
    async def _learning_loop(self):
        """主学习循环"""
        while True:
            try:
                # 等待学习间隔
                await asyncio.sleep(self._learning_interval)
                
                # 执行学习周期
                await self._execute_learning_cycle()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"学习循环异常: {e}")
    
    async def _execute_learning_cycle(self):
        """执行一次学习周期"""
        self._learning_stats["total_learning_cycles"] += 1
        self._learning_stats["last_learning_time"] = datetime.now().isoformat()
        
        logger.info(f"🔄 开始第 {self._learning_stats['total_learning_cycles']} 次学习周期")
        
        # 阶段1: 收集数据
        await self._collect_data()
        
        # 阶段2: 分析数据
        analysis_result = await self._analyze_data()
        
        # 阶段3: 发现模式
        patterns = await self._discover_patterns(analysis_result)
        
        # 阶段4: 优化策略
        updates = await self._optimize_strategies(patterns)
        
        # 阶段5: 更新模型
        await self._update_models(updates)
        
        # 通知订阅者
        await self._notify_subscribers(updates)
        
        logger.info(f"✅ 学习周期完成，发现 {len(patterns)} 个新模式")
    
    async def _collect_data(self):
        """收集新数据"""
        try:
            from business.evolutionary_learning import get_evolutionary_learning_service
            
            service = get_evolutionary_learning_service()
            records = service._behavior_records
            
            # 只处理新增数据
            if self._last_processed_time:
                new_records = [r for r in records if r.timestamp > self._last_processed_time]
            else:
                new_records = records[-self._min_data_threshold:]
            
            self._data_cache.extend(new_records)
            
            if new_records:
                self._last_processed_time = new_records[-1].timestamp
                logger.debug(f"收集到 {len(new_records)} 条新数据")
        
        except Exception as e:
            logger.error(f"数据收集失败: {e}")
    
    async def _analyze_data(self) -> Dict[str, Any]:
        """分析数据"""
        if len(self._data_cache) < self._min_data_threshold:
            return {"insufficient_data": True}
        
        analysis = {
            "total_records": len(self._data_cache),
            "intent_distribution": defaultdict(int),
            "component_usage": defaultdict(int),
            "success_rates": defaultdict(list),
            "context_patterns": []
        }
        
        for record in self._data_cache:
            # 统计意图分布
            content = record.data.get('content', '')
            intent = self._detect_intent(content)
            analysis["intent_distribution"][intent] += 1
            
            # 统计组件使用
            component_id = record.data.get('component_id')
            if component_id:
                analysis["component_usage"][component_id] += 1
            
            # 统计成功率
            feedback = record.data.get('feedback')
            if feedback:
                analysis["success_rates"][component_id].append(1 if feedback == 'helpful' else 0)
        
        # 计算平均成功率
        for comp_id, rates in analysis["success_rates"].items():
            if rates:
                analysis["success_rates"][comp_id] = sum(rates) / len(rates)
            else:
                analysis["success_rates"][comp_id] = 0.5
        
        return analysis
    
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
    
    async def _discover_patterns(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """发现新模式"""
        if analysis.get('insufficient_data'):
            return []
        
        patterns = []
        
        # 发现意图-组件关联模式
        intent_component_counts = defaultdict(lambda: defaultdict(int))
        
        for record in self._data_cache:
            content = record.data.get('content', '')
            intent = self._detect_intent(content)
            component_id = record.data.get('component_id', 'unknown')
            
            intent_component_counts[intent][component_id] += 1
        
        # 提取高频模式
        for intent, components in intent_component_counts.items():
            for component_id, count in components.items():
                if count >= 2:  # 至少出现2次
                    patterns.append({
                        "pattern_id": f"{intent}_{component_id}",
                        "trigger": intent,
                        "action": component_id,
                        "confidence": min(count / 5, 1.0),
                        "support": count
                    })
        
        return patterns
    
    async def _optimize_strategies(self, patterns: List[Dict[str, Any]]) -> List[PatternUpdate]:
        """优化策略"""
        updates = []
        
        try:
            from business.dynamic_ui_engine import get_dynamic_ui_engine
            
            engine = get_dynamic_ui_engine()
            
            for pattern in patterns:
                component_id = pattern['action']
                gene = engine.get_component_gene(component_id)
                
                if gene:
                    # 更新组件成功率
                    gene.success_rate = (gene.success_rate * gene.usage_count + pattern['confidence']) / (gene.usage_count + 1)
                    gene.usage_count += 1
                    
                    updates.append(PatternUpdate(
                        pattern_id=pattern['pattern_id'],
                        trigger=pattern['trigger'],
                        actions=[pattern['action']],
                        confidence=pattern['confidence'],
                        update_type="updated" if gene.usage_count > 1 else "new"
                    ))
            
            self._learning_stats["strategies_updated"] += len(updates)
            
        except Exception as e:
            logger.error(f"策略优化失败: {e}")
        
        return updates
    
    async def _update_models(self, updates: List[PatternUpdate]):
        """更新推荐模型"""
        try:
            from business.evolutionary_learning import get_evolutionary_learning_service
            
            service = get_evolutionary_learning_service()
            
            for update in updates:
                # 添加或更新交互模式
                if update.pattern_id not in service._interaction_patterns:
                    service._interaction_patterns[update.pattern_id] = service._interaction_patterns.__class__(
                        pattern_id=update.pattern_id,
                        trigger=update.trigger,
                        actions=update.actions,
                        confidence=update.confidence
                    )
                    self._learning_stats["patterns_discovered"] += 1
                else:
                    existing = service._interaction_patterns[update.pattern_id]
                    existing.confidence = (existing.confidence + update.confidence) / 2
                    existing.usage_count += 1
            
        except Exception as e:
            logger.error(f"模型更新失败: {e}")
    
    async def _notify_subscribers(self, updates: List[PatternUpdate]):
        """通知订阅者"""
        for subscriber in self._subscribers:
            try:
                await subscriber(updates)
            except Exception as e:
                logger.error(f"通知订阅者失败: {e}")
    
    def subscribe(self, callback: Callable):
        """订阅学习更新"""
        self._subscribers.append(callback)
    
    def unsubscribe(self, callback: Callable):
        """取消订阅"""
        self._subscribers.remove(callback)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取学习统计"""
        return self._learning_stats
    
    def set_learning_interval(self, seconds: int):
        """设置学习间隔"""
        self._learning_interval = seconds
        logger.info(f"学习间隔已设置为 {seconds} 秒")
    
    async def trigger_immediate_learning(self) -> Dict[str, Any]:
        """触发立即学习"""
        logger.info("🔔 手动触发学习")
        await self._execute_learning_cycle()
        return self.get_stats()


# 全局单例
_global_real_time_learning_service: Optional[RealTimeLearningService] = None


def get_real_time_learning_service() -> RealTimeLearningService:
    """获取全局实时学习服务单例"""
    global _global_real_time_learning_service
    if _global_real_time_learning_service is None:
        _global_real_time_learning_service = RealTimeLearningService()
    return _global_real_time_learning_service


# 测试函数
async def test_real_time_learning():
    """测试实时学习服务"""
    print("🧪 测试实时学习服务")
    print("="*60)
    
    service = get_real_time_learning_service()
    
    # 启动服务
    print("\n🚀 启动学习服务")
    await service.start()
    
    # 添加模拟数据
    print("\n📝 添加模拟数据")
    from business.evolutionary_learning import get_evolutionary_learning_service, BehaviorType
    
    learning_service = get_evolutionary_learning_service()
    session_id = learning_service.create_session("test_user")
    
    # 模拟用户行为
    for i in range(10):
        learning_service.record_behavior(
            user_id="test_user",
            session_id=session_id,
            behavior_type=BehaviorType.MESSAGE_SENT,
            data={"content": f"上传监测数据{i}", "component_id": "file_upload"},
            context={"intent": "upload"}
        )
        learning_service.record_behavior(
            user_id="test_user",
            session_id=session_id,
            behavior_type=BehaviorType.FEEDBACK_PROVIDED,
            data={"feedback": "helpful", "component_id": "file_upload"}
        )
    
    print("   已添加20条模拟行为记录")
    
    # 触发立即学习
    print("\n🔄 触发立即学习")
    stats = await service.trigger_immediate_learning()
    print(f"   学习周期: {stats['total_learning_cycles']}")
    print(f"   发现模式: {stats['patterns_discovered']}")
    print(f"   更新策略: {stats['strategies_updated']}")
    
    # 等待一点时间让后台学习运行
    print("\n⏳ 等待后台学习...")
    await asyncio.sleep(2)
    
    # 获取最终统计
    final_stats = service.get_stats()
    print(f"\n📊 最终统计:")
    print(f"   总学习周期: {final_stats['total_learning_cycles']}")
    print(f"   发现模式数: {final_stats['patterns_discovered']}")
    print(f"   更新策略数: {final_stats['strategies_updated']}")
    print(f"   最后学习时间: {final_stats['last_learning_time']}")
    
    # 停止服务
    print("\n🛑 停止学习服务")
    await service.stop()
    
    print("\n🎉 实时学习服务测试完成！")
    return True


if __name__ == "__main__":
    asyncio.run(test_real_time_learning())