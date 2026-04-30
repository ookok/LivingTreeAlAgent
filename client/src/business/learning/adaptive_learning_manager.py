"""
自适应学习管理器 (Adaptive Learning Manager)

核心功能：
1. 自动分析用户行为和学习进度
2. 自适应调整知识图谱结构和难度
3. 智能生成个性化学习路径
4. 自动优化复习计划
5. 与系统架构深度集成

设计理念：系统自适应，无需用户手动配置
"""

import time
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class LearningAdaptation:
    """学习自适应配置"""
    user_id: str
    optimal_difficulty: int = 3
    learning_speed: float = 1.0
    preferred_topics: List[str] = field(default_factory=list)
    weak_topics: List[str] = field(default_factory=list)
    strong_topics: List[str] = field(default_factory=list)
    engagement_score: float = 0.5
    last_adaptation_time: float = 0.0


class AdaptiveLearningManager:
    """自适应学习管理器"""
    
    ADAPTATION_INTERVAL_HOURS = 24  # 自适应调整间隔
    MIN_ENGAGEMENT_THRESHOLD = 0.3  # 最低参与度阈值
    DIFFICULTY_ADJUSTMENT_STEP = 0.5  # 难度调整步长
    
    def __init__(self):
        self._logger = logger.bind(component="AdaptiveLearningManager")
        
        # 延迟导入避免循环依赖
        from client.src.business.learning.knowledge_graph_editor import get_knowledge_graph_editor
        from client.src.business.learning.active_learning_engine import get_active_learning_engine
        from client.src.business.learning.long_term_mastery import get_long_term_mastery
        
        self._graph_editor = get_knowledge_graph_editor()
        self._active_learning = get_active_learning_engine()
        self._long_term_mastery = get_long_term_mastery()
        
        # 自适应配置缓存
        self._adaptations: Dict[str, LearningAdaptation] = {}
        
        # 系统集成
        self._integrate_with_system()
        
        self._logger.info("自适应学习管理器初始化完成")
    
    def _integrate_with_system(self):
        """与系统架构集成"""
        # 1. 集成自适应系统
        try:
            from client.src.infrastructure.adaptive_system import AdaptiveSystem
            self._adaptive_system = AdaptiveSystem()
            self._logger.info("✓ 集成 AdaptiveSystem")
        except Exception as e:
            self._logger.warning(f"AdaptiveSystem 集成失败: {e}")
            self._adaptive_system = None
        
        # 2. 集成进化引擎
        try:
            from client.src.business.evolution_engine import EvolutionEngine
            self._evolution_engine = EvolutionEngine()
            self._logger.info("✓ 集成 EvolutionEngine")
        except Exception as e:
            self._logger.warning(f"EvolutionEngine 集成失败: {e}")
            self._evolution_engine = None
        
        # 3. 集成知识图谱服务
        try:
            from client.src.business.memory import get_knowledge_graph_service
            self._kg_service = get_knowledge_graph_service()
            self._logger.info("✓ 集成 KnowledgeGraphService")
        except Exception as e:
            self._logger.warning(f"KnowledgeGraphService 集成失败: {e}")
            self._kg_service = None
        
        # 4. 集成模型路由器
        try:
            from client.src.business.smolllm2.router import L0Router
            self._l0_router = L0Router()
            self._logger.info("✓ 集成 L0Router")
        except Exception as e:
            self._logger.warning(f"L0Router 集成失败: {e}")
            self._l0_router = None
    
    async def analyze_user(self, user_id: str) -> LearningAdaptation:
        """
        分析用户学习状态，生成自适应配置
        
        Args:
            user_id: 用户ID
        
        Returns:
            自适应配置
        """
        self._logger.debug(f"分析用户学习状态: {user_id}")
        
        # 获取用户记忆摘要
        memory_summary = self._long_term_mastery.get_user_memory_summary(user_id)
        
        # 获取评估结果
        evaluation = self._active_learning.evaluate_mastery(user_id)
        
        # 分析表现
        avg_score = evaluation.get("average_score", 0.5)
        session_count = evaluation.get("session_count", 0)
        
        # 确定最优难度
        optimal_difficulty = self._calculate_optimal_difficulty(avg_score, session_count)
        
        # 识别强弱主题
        weak_topics, strong_topics = self._identify_topic_strengths(user_id)
        
        # 计算参与度
        engagement_score = self._calculate_engagement(user_id)
        
        # 获取偏好主题（从记忆访问模式推断）
        preferred_topics = self._infer_preferences(user_id)
        
        # 创建自适应配置
        adaptation = LearningAdaptation(
            user_id=user_id,
            optimal_difficulty=optimal_difficulty,
            learning_speed=self._calculate_learning_speed(session_count),
            preferred_topics=preferred_topics,
            weak_topics=weak_topics,
            strong_topics=strong_topics,
            engagement_score=engagement_score,
            last_adaptation_time=time.time()
        )
        
        self._adaptations[user_id] = adaptation
        return adaptation
    
    def _calculate_optimal_difficulty(self, avg_score: float, session_count: int) -> int:
        """计算最优难度等级"""
        # 基于平均分数调整难度
        # 分数越高，难度越高
        base_difficulty = 3
        
        if avg_score >= 0.9:
            base_difficulty = 5
        elif avg_score >= 0.7:
            base_difficulty = 4
        elif avg_score >= 0.5:
            base_difficulty = 3
        elif avg_score >= 0.3:
            base_difficulty = 2
        else:
            base_difficulty = 1
        
        # 考虑练习次数（新手需要更低难度）
        if session_count < 3:
            base_difficulty = max(1, base_difficulty - 1)
        
        return base_difficulty
    
    def _identify_topic_strengths(self, user_id: str) -> Tuple[List[str], List[str]]:
        """识别强弱主题"""
        weak_topics = []
        strong_topics = []
        
        # 获取复习计划
        reviews = self._active_learning.schedule_review(user_id)
        
        for review in reviews:
            if review["last_score"] >= 0.7:
                strong_topics.append(review["topic"])
            elif review["last_score"] < 0.5:
                weak_topics.append(review["topic"])
        
        return weak_topics, strong_topics
    
    def _calculate_engagement(self, user_id: str) -> float:
        """计算用户参与度"""
        # 基于最近活动计算参与度
        memory_summary = self._long_term_mastery.get_user_memory_summary(user_id)
        total_nodes = memory_summary.get("total_nodes", 0)
        
        if total_nodes == 0:
            return 0.3  # 默认参与度
        
        # 参与度 = 掌握良好的节点比例
        avg_strength = memory_summary.get("average_strength", 0.5)
        return min(1.0, avg_strength)
    
    def _calculate_learning_speed(self, session_count: int) -> float:
        """计算学习速度"""
        # 练习次数越多，学习速度越快
        return min(2.0, 1.0 + session_count * 0.1)
    
    def _infer_preferences(self, user_id: str) -> List[str]:
        """从用户行为推断偏好"""
        preferences = []
        
        # 获取用户记忆摘要
        summary = self._long_term_mastery.get_user_memory_summary(user_id)
        
        # 简单实现：返回掌握分布中非零的分类
        for level, info in summary.get("mastery_distribution", {}).items():
            if info.get("count", 0) > 0:
                preferences.append(info.get("label", level))
        
        return preferences[:5]  # 返回前5个偏好
    
    async def adapt_knowledge_graph(self, user_id: str):
        """
        自适应调整知识图谱
        
        根据用户状态自动调整：
        1. 调整节点难度
        2. 更新偏好权重
        3. 生成个性化学习路径
        """
        # 分析用户
        adaptation = await self.analyze_user(user_id)
        
        self._logger.info(f"开始自适应调整: {user_id} - 最优难度: {adaptation.optimal_difficulty}")
        
        # 1. 调整现有节点难度
        await self._adjust_node_difficulties(user_id, adaptation)
        
        # 2. 更新偏好权重
        await self._update_preference_weights(user_id, adaptation)
        
        # 3. 生成/更新学习路径
        await self._generate_adaptive_learning_path(user_id, adaptation)
        
        # 4. 优化复习计划
        await self._optimize_review_schedule(user_id, adaptation)
        
        # 5. 如果集成了进化引擎，通知进化
        if self._evolution_engine:
            await self._notify_evolution(user_id, adaptation)
        
        self._logger.info(f"自适应调整完成: {user_id}")
    
    async def _adjust_node_difficulties(self, user_id: str, adaptation: LearningAdaptation):
        """调整节点难度"""
        # 获取用户相关的节点
        nodes = self._graph_editor.get_nodes_by_category("AI")  # 简化：获取AI分类
        
        for node in nodes:
            # 根据用户表现调整难度
            if node.id in adaptation.weak_topics:
                # 弱主题降低难度
                new_difficulty = max(1, node.difficulty - 1)
            elif node.id in adaptation.strong_topics:
                # 强主题提高难度
                new_difficulty = min(5, node.difficulty + 1)
            else:
                # 其他主题使用最优难度
                new_difficulty = adaptation.optimal_difficulty
            
            if new_difficulty != node.difficulty:
                self._graph_editor.set_difficulty_level(node.id, new_difficulty)
                self._logger.debug(f"调整节点难度: {node.id} -> {new_difficulty}")
    
    async def _update_preference_weights(self, user_id: str, adaptation: LearningAdaptation):
        """更新偏好权重"""
        # 提高偏好主题的权重
        for topic in adaptation.preferred_topics:
            nodes = self._graph_editor.get_nodes_by_category(topic)
            for node in nodes:
                new_weight = min(3.0, node.weight + 0.5)
                self._graph_editor.set_preference_weight(node.id, new_weight)
        
        # 降低弱主题的权重（减少推荐频率）
        for topic in adaptation.weak_topics:
            nodes = self._graph_editor.get_nodes_by_category(topic)
            for node in nodes:
                new_weight = max(0.5, node.weight - 0.2)
                self._graph_editor.set_preference_weight(node.id, new_weight)
    
    async def _generate_adaptive_learning_path(self, user_id: str, adaptation: LearningAdaptation):
        """生成自适应学习路径"""
        # 如果有弱主题，优先推荐弱主题的学习路径
        if adaptation.weak_topics:
            for topic in adaptation.weak_topics[:2]:  # 最多处理2个弱主题
                path = self._graph_editor.generate_learning_path(
                    user_id,
                    topic=topic,
                    target_difficulty=adaptation.optimal_difficulty
                )
                self._logger.debug(f"为弱主题生成路径: {topic} - {path.id}")
        else:
            # 否则生成综合学习路径
            path = self._graph_editor.generate_learning_path(
                user_id,
                target_difficulty=adaptation.optimal_difficulty
            )
            self._logger.debug(f"生成综合学习路径: {path.id}")
    
    async def _optimize_review_schedule(self, user_id: str, adaptation: LearningAdaptation):
        """优化复习计划"""
        # 获取当前复习计划
        reviews = self._active_learning.schedule_review(user_id)
        
        # 调整复习间隔：弱主题更频繁复习
        for review in reviews:
            topic = review["topic"]
            if topic in adaptation.weak_topics:
                # 缩短复习间隔
                new_interval = max(1, review["interval_hours"] // 2)
                self._logger.debug(f"缩短弱主题复习间隔: {topic} -> {new_interval}小时")
            elif topic in adaptation.strong_topics:
                # 延长复习间隔
                new_interval = min(72, review["interval_hours"] * 2)
                self._logger.debug(f"延长强主题复习间隔: {topic} -> {new_interval}小时")
    
    async def _notify_evolution(self, user_id: str, adaptation: LearningAdaptation):
        """通知进化引擎"""
        try:
            await self._evolution_engine.learn_from_feedback({
                "user_id": user_id,
                "adaptation": {
                    "optimal_difficulty": adaptation.optimal_difficulty,
                    "engagement_score": adaptation.engagement_score,
                    "weak_topics": adaptation.weak_topics,
                    "strong_topics": adaptation.strong_topics
                }
            })
        except Exception as e:
            self._logger.warning(f"通知进化引擎失败: {e}")
    
    async def run_periodic_adaptation(self):
        """定期执行自适应调整"""
        while True:
            self._logger.debug("执行定期自适应调整")
            
            # 对所有用户执行自适应
            for user_id in self._adaptations.keys():
                try:
                    await self.adapt_knowledge_graph(user_id)
                except Exception as e:
                    self._logger.error(f"自适应调整失败 {user_id}: {e}")
            
            # 等待下一个周期
            await asyncio.sleep(self.ADAPTATION_INTERVAL_HOURS * 3600)
    
    def get_adaptation(self, user_id: str) -> Optional[LearningAdaptation]:
        """获取用户自适应配置"""
        return self._adaptations.get(user_id)
    
    def start_adaptation_loop(self):
        """启动自适应循环（后台任务）"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.create_task(self.run_periodic_adaptation())
        loop.run_forever()


# 单例模式
_adaptive_learning_manager_instance = None

def get_adaptive_learning_manager() -> AdaptiveLearningManager:
    """获取自适应学习管理器实例"""
    global _adaptive_learning_manager_instance
    if _adaptive_learning_manager_instance is None:
        _adaptive_learning_manager_instance = AdaptiveLearningManager()
    return _adaptive_learning_manager_instance


# 便捷函数
async def adapt_for_user(user_id: str):
    """为用户执行自适应调整"""
    manager = get_adaptive_learning_manager()
    return await manager.adapt_knowledge_graph(user_id)


def get_user_adaptation(user_id: str) -> Optional[LearningAdaptation]:
    """获取用户自适应配置"""
    manager = get_adaptive_learning_manager()
    return manager.get_adaptation(user_id)


if __name__ == "__main__":
    print("=" * 60)
    print("自适应学习管理器测试")
    print("=" * 60)
    
    # 初始化管理器
    manager = get_adaptive_learning_manager()
    
    # 添加测试数据
    print("\n[1] 添加测试知识节点")
    editor = manager._graph_editor
    node1 = editor.add_node("Python基础", "Python是高级编程语言", difficulty=1, category="编程")
    node2 = editor.add_node("机器学习", "机器学习是AI分支", difficulty=3, category="AI")
    node3 = editor.add_node("深度学习", "深度学习是ML子集", difficulty=4, category="AI")
    node4 = editor.add_node("神经网络", "神经网络是DL核心", difficulty=4, category="AI")
    
    # 创建用户偏好
    editor.create_user_preference("user_001", preferred_categories=["AI", "编程"], difficulty_preference=3)
    
    # 记录知识访问（模拟学习行为）
    print("\n[2] 模拟用户学习行为")
    mastery = manager._long_term_mastery
    mastery.record_access("user_001", node1, 0.9)  # 掌握好
    mastery.record_access("user_001", node2, 0.6)  # 一般
    mastery.record_access("user_001", node3, 0.4)  # 较弱
    mastery.record_access("user_001", node4, 0.3)  # 较弱
    
    # 创建练习会话（模拟测试）
    print("\n[3] 模拟练习测试")
    engine = manager._active_learning
    session = engine.create_practice_session("user_001", "AI", difficulty=3, question_count=3)
    for i, q in enumerate(session.questions):
        # 模拟答题：前两题对，后一题错
        answer = q.correct_answer if i < 2 else (q.correct_answer + 1) % 4
        engine.submit_answer(session.id, q.id, answer, response_time_ms=2000)
    
    # 执行自适应调整
    print("\n[4] 执行自适应调整")
    asyncio.run(manager.adapt_knowledge_graph("user_001"))
    
    # 获取自适应配置
    print("\n[5] 自适应配置结果")
    adaptation = manager.get_adaptation("user_001")
    if adaptation:
        print(f"用户ID: {adaptation.user_id}")
        print(f"最优难度: {adaptation.optimal_difficulty}")
        print(f"学习速度: {adaptation.learning_speed:.2f}")
        print(f"参与度: {adaptation.engagement_score:.2f}")
        print(f"偏好主题: {adaptation.preferred_topics}")
        print(f"弱主题: {adaptation.weak_topics}")
        print(f"强主题: {adaptation.strong_topics}")
    
    # 获取用户记忆摘要
    print("\n[6] 用户记忆摘要")
    summary = mastery.get_user_memory_summary("user_001")
    print(f"总节点数: {summary['total_nodes']}")
    print(f"平均强度: {summary['average_strength']:.2f}")
    print(f"需要复习: {summary['needs_review']} 个")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)