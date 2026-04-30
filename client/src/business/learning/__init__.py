"""
学习模块 (Learning Module)

整合 Wondering 的三个核心技术：
1. 知识图谱编辑器 - 自定义模式
2. 主动学习引擎 - 主动学习机制
3. 长程掌握算法 - 长程掌握算法

使用方式：
from business.learning import (
    get_knowledge_graph_editor,
    get_active_learning_engine,
    get_long_term_mastery,
    LearningSystem
)
"""

from .knowledge_graph_editor import (
    KnowledgeGraphEditor,
    get_knowledge_graph_editor,
    KnowledgeNode,
    KnowledgeEdge,
    LearningPath,
    UserPreference
)

from .active_learning_engine import (
    ActiveLearningEngine,
    get_active_learning_engine,
    QuizQuestion,
    QuizResult,
    PracticeSession,
    ReviewSchedule
)

from .long_term_mastery import (
    LongTermMasteryAlgorithm,
    get_long_term_mastery,
    MemoryTrace,
    ForgettingCurvePrediction,
    MasteryState
)

from .adaptive_learning_manager import (
    AdaptiveLearningManager,
    get_adaptive_learning_manager,
    LearningAdaptation,
    adapt_for_user,
    get_user_adaptation
)


class LearningSystem:
    """学习系统统一接口"""
    
    def __init__(self):
        self._graph_editor = get_knowledge_graph_editor()
        self._active_learning = get_active_learning_engine()
        self._long_term_mastery = get_long_term_mastery()
    
    # ===== 知识图谱编辑器 =====
    
    def add_knowledge_node(self, **kwargs):
        """添加知识节点"""
        return self._graph_editor.add_node(**kwargs)
    
    def update_knowledge_node(self, node_id: str, **kwargs):
        """更新知识节点"""
        self._graph_editor.update_node(node_id, **kwargs)
    
    def set_difficulty_level(self, node_id: str, level: int):
        """设置难度等级"""
        self._graph_editor.set_difficulty_level(node_id, level)
    
    def set_preference_weight(self, node_id: str, weight: float):
        """设置偏好权重"""
        self._graph_editor.set_preference_weight(node_id, weight)
    
    def add_relation_edge(self, source_id: str, target_id: str, relation: str = "related"):
        """添加关系边"""
        self._graph_editor.add_edge(source_id, target_id, relation)
    
    def create_user_preference(self, user_id: str, **kwargs):
        """创建用户偏好"""
        return self._graph_editor.create_user_preference(user_id, **kwargs)
    
    def update_user_preference(self, user_id: str, **kwargs):
        """更新用户偏好"""
        self._graph_editor.update_user_preference(user_id, **kwargs)
    
    def generate_learning_path(self, user_id: str, topic: str = None, target_difficulty: int = None):
        """生成学习路径"""
        return self._graph_editor.generate_learning_path(user_id, topic, target_difficulty)
    
    def get_knowledge_node(self, node_id: str):
        """获取知识节点"""
        return self._graph_editor.get_node(node_id)
    
    # ===== 主动学习引擎 =====
    
    def generate_quiz(self, topic: str, difficulty: int = 3, count: int = 5):
        """生成测验题目"""
        return self._active_learning.generate_quiz(topic, difficulty, count)
    
    def create_practice_session(self, user_id: str, topic: str, difficulty: int = 3, question_count: int = 5):
        """创建练习会话"""
        return self._active_learning.create_practice_session(user_id, topic, difficulty, question_count)
    
    def submit_answer(self, session_id: str, question_id: str, user_answer: int, response_time_ms: int = 0):
        """提交答案"""
        return self._active_learning.submit_answer(session_id, question_id, user_answer, response_time_ms)
    
    def evaluate_mastery(self, user_id: str, topic: str = None):
        """评估掌握程度"""
        return self._active_learning.evaluate_mastery(user_id, topic)
    
    def get_review_schedule(self, user_id: str):
        """获取复习计划"""
        return self._active_learning.schedule_review(user_id)
    
    # ===== 长程掌握算法 =====
    
    def record_knowledge_access(self, user_id: str, node_id: str, mastery_score: float = 0.0):
        """记录知识访问"""
        self._long_term_mastery.record_access(user_id, node_id, mastery_score)
    
    def predict_forgetting_curve(self, user_id: str, node_id: str, prediction_days: int = 30):
        """预测遗忘曲线"""
        return self._long_term_mastery.predict_forgetting_curve(user_id, node_id, prediction_days)
    
    def get_mastery_state(self, user_id: str, node_id: str):
        """获取掌握状态"""
        return self._long_term_mastery.get_mastery_state(user_id, node_id)
    
    def optimize_retrieval(self, user_id: str, node_ids: list):
        """优化检索顺序"""
        return self._long_term_mastery.optimize_retrieval(user_id, node_ids)
    
    def get_user_memory_summary(self, user_id: str):
        """获取用户记忆摘要"""
        return self._long_term_mastery.get_user_memory_summary(user_id)


# 全局学习系统实例
_learning_system_instance = None

def get_learning_system() -> LearningSystem:
    """获取学习系统实例"""
    global _learning_system_instance
    if _learning_system_instance is None:
        _learning_system_instance = LearningSystem()
    return _learning_system_instance


# 便捷导出
__all__ = [
    # 编辑器
    "KnowledgeGraphEditor",
    "get_knowledge_graph_editor",
    "KnowledgeNode",
    "KnowledgeEdge",
    "LearningPath",
    "UserPreference",
    
    # 主动学习
    "ActiveLearningEngine",
    "get_active_learning_engine",
    "QuizQuestion",
    "QuizResult",
    "PracticeSession",
    "ReviewSchedule",
    
    # 长程掌握
    "LongTermMasteryAlgorithm",
    "get_long_term_mastery",
    "MemoryTrace",
    "ForgettingCurvePrediction",
    "MasteryState",
    
    # 自适应管理器
    "AdaptiveLearningManager",
    "get_adaptive_learning_manager",
    "LearningAdaptation",
    "adapt_for_user",
    "get_user_adaptation",
    
    # 统一接口
    "LearningSystem",
    "get_learning_system"
]