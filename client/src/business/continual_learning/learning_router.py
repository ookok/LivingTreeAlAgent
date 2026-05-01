"""
学习路由器 - 统一学习管理接口

功能：
1. 协调EWC保护、渐进网络、元学习和课程学习
2. 统一任务学习入口
3. 学习策略选择
4. 学习进度跟踪
"""

import time
from typing import Dict, List, Any, Optional
from loguru import logger


class LearningRouter:
    """
    学习路由器 - 协调持续学习的各个组件
    
    学习流程：
    1. 接收学习请求
    2. 选择学习策略
    3. 执行学习
    4. 保护知识（EWC）
    5. 更新任务记忆
    """
    
    def __init__(self):
        self._logger = logger.bind(component="LearningRouter")
        
        # 延迟加载组件
        self._ewc_protection = None
        self._progressive_net = None
        self._meta_learner = None
        self._curriculum_manager = None
        self._task_memory = None
    
    def _init_components(self):
        """延迟初始化组件"""
        if self._ewc_protection is None:
            from .ewc_protection import EWCProtection
            from .progressive_net import ProgressiveNetwork, TaskType
            from .meta_learning import MetaLearner
            from .curriculum_manager import CurriculumManager
            from .task_memory import TaskMemory
            
            self._ewc_protection = EWCProtection()
            self._progressive_net = ProgressiveNetwork()
            self._meta_learner = MetaLearner()
            self._curriculum_manager = CurriculumManager()
            self._task_memory = TaskMemory()
            
            self._logger.info("学习组件初始化完成")
    
    def learn_task(self, task_id: str, task_name: str, knowledge: Dict[str, Any],
                  task_type: str = "other") -> bool:
        """
        学习新任务
        
        Args:
            task_id: 任务ID
            task_name: 任务名称
            knowledge: 知识内容
            task_type: 任务类型
        
        Returns:
            是否成功
        """
        self._init_components()
        
        try:
            # 1. 添加到渐进网络
            task_type_enum = self._get_task_type_enum(task_type)
            module_id = self._progressive_net.add_task(task_id, task_name, task_type_enum)
            
            # 2. 添加到任务记忆
            self._task_memory.add_task(task_id, task_name, task_type_enum, knowledge)
            
            # 3. 应用EWC保护（模拟权重）
            model_weights = self._simulate_model_weights(knowledge)
            self._ewc_protection.protect_task(task_id, model_weights)
            
            # 4. 更新元学习器
            self._meta_learner.meta_train([{
                'task_id': task_id,
                'task_name': task_name,
                'type': task_type,
                'difficulty': 'medium',
                'data': knowledge
            }])
            
            self._logger.info(f"学习任务成功: {task_name}")
            
            # 发布学习完成事件
            self._publish_learning_event(task_id, task_name, 'completed', {
                'knowledge_size': len(knowledge),
                'task_type': task_type
            })
            
            return True
        
        except Exception as e:
            self._logger.error(f"学习任务失败 {task_name}: {e}")
            
            # 发布学习失败事件
            self._publish_learning_event(task_id, task_name, 'failed', {
                'error': str(e)
            })
            
            return False
    
    def _publish_learning_event(self, task_id: str, task_name: str, status: str, data: Dict):
        """发布学习事件"""
        try:
            from client.src.business.integration_layer import EventType, publish
            
            event_type = EventType.LEARNING_COMPLETED if status == 'completed' else EventType.LEARNING_FAILED
            
            event_data = {
                'task_id': task_id,
                'task_name': task_name,
                'status': status,
                **data
            }
            
            publish(event_type, 'continual_learning', event_data)
        except ImportError:
            pass
    
    def _get_task_type_enum(self, task_type: str):
        """获取任务类型枚举"""
        from .progressive_net import TaskType
        
        type_map = {
            'classification': TaskType.CLASSIFICATION,
            'regression': TaskType.REGRESSION,
            'reasoning': TaskType.REASONING,
            'generation': TaskType.GENERATION
        }
        
        return type_map.get(task_type.lower(), TaskType.OTHER)
    
    def _simulate_model_weights(self, knowledge: Dict) -> Dict:
        """模拟模型权重（用于EWC）"""
        weights = {}
        
        for i, (key, value) in enumerate(knowledge.items()):
            if isinstance(value, (int, float)):
                import numpy as np
                weights[f'layer_{i}_param_{key}'] = np.array([float(value)])
        
        return weights
    
    def recall_task(self, task_id: str) -> Dict:
        """
        回忆任务
        
        Args:
            task_id: 任务ID
        
        Returns:
            任务信息
        """
        self._init_components()
        
        task = self._task_memory.get_task(task_id)
        
        if not task:
            return {'success': False, 'message': '任务未找到'}
        
        return {
            'success': True,
            'task_id': task.task_id,
            'task_name': task.task_name,
            'task_type': task.task_type.value,
            'performance': task.performance,
            'learned_at': task.learned_at,
            'last_used': task.last_used,
            'usage_count': task.usage_count
        }
    
    def meta_learn(self, training_tasks: List[str]) -> Dict:
        """
        元学习
        
        Args:
            training_tasks: 任务ID列表
        
        Returns:
            元学习结果
        """
        self._init_components()
        
        # 获取任务详情
        tasks_data = []
        for task_id in training_tasks:
            task = self._task_memory.get_task(task_id)
            if task:
                tasks_data.append({
                    'task_id': task.task_id,
                    'task_name': task.task_name,
                    'type': task.task_type.value,
                    'difficulty': 'medium'
                })
        
        result = self._meta_learner.meta_train(tasks_data)
        
        return {
            'success': result.success,
            'strategy_improvement': result.strategy_improvement,
            'faster_adaptation': result.faster_adaptation,
            'better_generalization': result.better_generalization,
            'meta_knowledge': result.meta_knowledge,
            'elapsed_time': result.elapsed_time
        }
    
    def curriculum_learn(self, lessons: List[Dict], difficulty_order: Optional[List[int]] = None) -> Dict:
        """
        课程学习
        
        Args:
            lessons: 课程列表
            difficulty_order: 难度顺序
        
        Returns:
            学习结果
        """
        self._init_components()
        
        # 添加课程
        lesson_ids = self._curriculum_manager.add_lessons(lessons)
        
        # 创建学习路径
        path_id = self._curriculum_manager.create_learning_path(
            name="课程学习路径",
            lesson_ids=lesson_ids,
            order_type=self._curriculum_manager.CurriculumOrder.ADAPTIVE
        )
        
        # 开始学习
        self._curriculum_manager.start_path(path_id)
        
        # 模拟学习过程
        results = []
        for i in range(len(lesson_ids)):
            next_lesson = self._curriculum_manager.get_next_lesson()
            
            if next_lesson:
                # 模拟学习
                score = 0.7 + (i / len(lesson_ids)) * 0.3
                self._curriculum_manager.complete_lesson(next_lesson.lesson_id, score)
                
                results.append({
                    'lesson': next_lesson.name,
                    'status': 'completed',
                    'score': round(score, 2)
                })
        
        progress = self._curriculum_manager.get_path_progress(path_id)
        
        return {
            'completed': len(results),
            'lessons': results,
            'final_performance': progress['progress'],
            'path_id': path_id
        }
    
    def transfer_knowledge(self, source_task_id: str, target_task_id: str) -> bool:
        """
        知识迁移
        
        Args:
            source_task_id: 源任务ID
            target_task_id: 目标任务ID
        
        Returns:
            是否成功
        """
        self._init_components()
        
        return self._progressive_net.transfer_knowledge(source_task_id, target_task_id)
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        self._init_components()
        
        return {
            'ewc': self._ewc_protection.get_stats(),
            'progressive_net': self._progressive_net.get_network_summary(),
            'meta_learner': self._meta_learner.get_stats(),
            'curriculum': self._curriculum_manager.get_stats(),
            'task_memory': self._task_memory.get_stats()
        }
    
    def get_all_tasks(self) -> List[Dict]:
        """获取所有任务"""
        self._init_components()
        
        tasks = self._task_memory.get_all_tasks()
        
        return [
            {
                'task_id': task.task_id,
                'task_name': task.task_name,
                'task_type': task.task_type.value,
                'performance': task.performance,
                'learned_at': task.learned_at,
                'last_used': task.last_used,
                'usage_count': task.usage_count
            }
            for task in tasks
        ]


# 单例模式
_router_instance = None

def get_learning_router() -> LearningRouter:
    """获取学习路由器实例"""
    global _router_instance
    if _router_instance is None:
        _router_instance = LearningRouter()
    return _router_instance