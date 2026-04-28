"""
MLWorkflowManager - ML 全流程自动化管理器

参考 ml-intern 的"ML 实习生"设计

功能：
1. ML 任务管理（训练/评估/部署）
2. 工作流编排
3. 自动化流程
4. 模型版本管理
5. 实验追踪

遵循自我进化原则：
- 从实验结果中学习优化超参数
- 自动选择最佳模型
- 支持自动调参
"""

from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from loguru import logger
from datetime import datetime
from enum import Enum
import asyncio


class MLTaskType(Enum):
    """ML 任务类型"""
    TRAINING = "training"
    EVALUATION = "evaluation"
    DEPLOYMENT = "deployment"
    HYPERPARAM_TUNING = "hyperparam_tuning"
    DATA_PREPROCESSING = "data_preprocessing"


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class MLTask:
    """ML 任务"""
    task_id: str
    task_type: MLTaskType
    name: str
    config: Dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class MLExperiment:
    """ML 实验"""
    experiment_id: str
    name: str
    tasks: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    best_model_id: Optional[str] = None
    best_metric: Optional[float] = None


@dataclass
class ModelVersion:
    """模型版本"""
    model_id: str
    version: str
    experiment_id: str
    metrics: Dict[str, float] = field(default_factory=dict)
    path: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    deployed: bool = False


class MLWorkflowManager:
    """
    ML 全流程自动化管理器
    
    参考 ml-intern 的"ML 实习生"设计，实现自动化 ML 工作流。
    
    核心功能：
    1. ML 任务管理（训练/评估/部署）
    2. 工作流编排
    3. 自动化流程
    4. 模型版本管理
    5. 实验追踪
    """

    def __init__(self):
        self._logger = logger.bind(component="MLWorkflowManager")
        self._tasks: Dict[str, MLTask] = {}
        self._experiments: Dict[str, MLExperiment] = {}
        self._models: Dict[str, List[ModelVersion]] = {}
        self._running = False
        self._worker_task = None

    async def start(self):
        """启动工作流管理器"""
        if self._running:
            return
        
        self._running = True
        self._logger.info("启动 ML 工作流管理器")
        self._worker_task = asyncio.create_task(self._worker_loop())

    async def stop(self):
        """停止工作流管理器"""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
        self._logger.info("停止 ML 工作流管理器")

    async def _worker_loop(self):
        """工作线程循环"""
        while self._running:
            # 处理待执行的任务
            pending_tasks = [t for t in self._tasks.values() if t.status == TaskStatus.PENDING]
            
            for task in pending_tasks:
                await self._execute_task(task)
            
            await asyncio.sleep(1)

    async def _execute_task(self, task: MLTask):
        """执行任务"""
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        
        self._logger.info(f"开始执行任务: {task.name}")

        try:
            if task.task_type == MLTaskType.DATA_PREPROCESSING:
                result = await self._execute_data_preprocessing(task)
            elif task.task_type == MLTaskType.TRAINING:
                result = await self._execute_training(task)
            elif task.task_type == MLTaskType.HYPERPARAM_TUNING:
                result = await self._execute_hyperparam_tuning(task)
            elif task.task_type == MLTaskType.EVALUATION:
                result = await self._execute_evaluation(task)
            elif task.task_type == MLTaskType.DEPLOYMENT:
                result = await self._execute_deployment(task)
            else:
                result = {"error": "未知任务类型"}

            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result = result
            
            self._logger.info(f"任务完成: {task.name}")

            # 如果是训练任务，保存模型
            if task.task_type == MLTaskType.TRAINING and "model_id" in result:
                await self._save_model(result["model_id"], task)

            # 触发下一个任务
            await self._trigger_next_task(task)

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now()
            task.error = str(e)
            self._logger.error(f"任务失败: {task.name}, 错误: {e}")

    async def _execute_data_preprocessing(self, task: MLTask) -> Dict[str, Any]:
        """执行数据预处理"""
        config = task.config
        self._logger.info(f"数据预处理: {config.get('input_path')}")
        
        return {
            "status": "completed",
            "output_path": "/data/preprocessed",
            "rows_processed": 10000,
            "features": ["feature1", "feature2", "feature3"]
        }

    async def _execute_training(self, task: MLTask) -> Dict[str, Any]:
        """执行训练任务"""
        config = task.config
        self._logger.info(f"训练模型: {config.get('model_type', 'unknown')}")
        
        # 模拟训练
        await asyncio.sleep(2)
        
        model_id = f"model_{len(self._models) + 1}"
        metrics = {
            "accuracy": 0.85 + (len(self._tasks) % 10) / 100,
            "loss": 0.35 - (len(self._tasks) % 10) / 100,
            "f1_score": 0.82 + (len(self._tasks) % 10) / 100
        }
        
        task.metrics = metrics
        
        return {
            "status": "completed",
            "model_id": model_id,
            "metrics": metrics,
            "epochs": config.get("epochs", 10),
            "batch_size": config.get("batch_size", 32)
        }

    async def _execute_hyperparam_tuning(self, task: MLTask) -> Dict[str, Any]:
        """执行超参数调优"""
        config = task.config
        self._logger.info(f"超参数调优: {config.get('search_space')}")
        
        # 模拟调优过程
        await asyncio.sleep(3)
        
        best_params = {
            "learning_rate": 0.001,
            "batch_size": 64,
            "hidden_units": 256,
            "dropout": 0.3
        }
        
        return {
            "status": "completed",
            "best_params": best_params,
            "best_score": 0.89,
            "trials": 20
        }

    async def _execute_evaluation(self, task: MLTask) -> Dict[str, Any]:
        """执行评估任务"""
        config = task.config
        model_id = config.get("model_id")
        self._logger.info(f"评估模型: {model_id}")
        
        # 模拟评估
        await asyncio.sleep(1)
        
        metrics = {
            "accuracy": 0.87,
            "precision": 0.85,
            "recall": 0.89,
            "f1_score": 0.87,
            "auc": 0.92
        }
        
        return {
            "status": "completed",
            "model_id": model_id,
            "metrics": metrics
        }

    async def _execute_deployment(self, task: MLTask) -> Dict[str, Any]:
        """执行部署任务"""
        config = task.config
        model_id = config.get("model_id")
        self._logger.info(f"部署模型: {model_id}")
        
        # 模拟部署
        await asyncio.sleep(1)
        
        return {
            "status": "completed",
            "model_id": model_id,
            "endpoint": f"http://localhost:8000/models/{model_id}",
            "status": "deployed"
        }

    async def _save_model(self, model_id: str, task: MLTask):
        """保存模型版本"""
        if model_id not in self._models:
            self._models[model_id] = []
        
        version = f"v{len(self._models[model_id]) + 1}"
        
        model_version = ModelVersion(
            model_id=model_id,
            version=version,
            experiment_id=task.config.get("experiment_id", "unknown"),
            metrics=task.metrics,
            path=f"/models/{model_id}/{version}",
            created_at=datetime.now()
        )
        
        self._models[model_id].append(model_version)
        self._logger.info(f"保存模型版本: {model_id} {version}")

    async def _trigger_next_task(self, task: MLTask):
        """触发下一个任务（工作流编排）"""
        # 根据任务类型决定下一步
        workflow_map = {
            MLTaskType.DATA_PREPROCESSING: MLTaskType.TRAINING,
            MLTaskType.HYPERPARAM_TUNING: MLTaskType.TRAINING,
            MLTaskType.TRAINING: MLTaskType.EVALUATION,
            MLTaskType.EVALUATION: MLTaskType.DEPLOYMENT
        }
        
        next_task_type = workflow_map.get(task.task_type)
        if next_task_type:
            # 创建下一个任务
            next_task = MLTask(
                task_id=f"{task.task_id}_next",
                task_type=next_task_type,
                name=f"{task.name} - {next_task_type.value}",
                config={**task.config, "previous_task_id": task.task_id}
            )
            self._tasks[next_task.task_id] = next_task
            self._logger.info(f"触发下一个任务: {next_task.name}")

    def create_experiment(self, experiment_id: str, name: str) -> MLExperiment:
        """创建实验"""
        if experiment_id in self._experiments:
            raise ValueError(f"实验已存在: {experiment_id}")

        experiment = MLExperiment(
            experiment_id=experiment_id,
            name=name
        )
        self._experiments[experiment_id] = experiment
        self._logger.info(f"创建实验: {name}")
        return experiment

    def create_task(
        self,
        task_id: str,
        task_type: MLTaskType,
        name: str,
        config: Optional[Dict[str, Any]] = None,
        experiment_id: Optional[str] = None
    ) -> MLTask:
        """创建 ML 任务"""
        if task_id in self._tasks:
            raise ValueError(f"任务已存在: {task_id}")

        task = MLTask(
            task_id=task_id,
            task_type=task_type,
            name=name,
            config=config or {}
        )
        self._tasks[task_id] = task

        # 如果关联到实验
        if experiment_id and experiment_id in self._experiments:
            self._experiments[experiment_id].tasks.append(task_id)

        self._logger.info(f"创建任务: {name}")
        return task

    def run_workflow(self, workflow_config: Dict[str, Any]):
        """
        运行工作流
        
        Args:
            workflow_config: 工作流配置
        """
        # 解析工作流配置
        steps = workflow_config.get("steps", [])
        
        for step in steps:
            task_type = MLTaskType(step.get("type"))
            task_id = step.get("id")
            name = step.get("name")
            config = step.get("config", {})
            
            self.create_task(task_id, task_type, name, config)

    def get_task(self, task_id: str) -> Optional[MLTask]:
        """获取任务"""
        return self._tasks.get(task_id)

    def list_tasks(self, task_type: Optional[MLTaskType] = None) -> List[MLTask]:
        """列出任务"""
        tasks = list(self._tasks.values())
        if task_type:
            tasks = [t for t in tasks if t.task_type == task_type]
        return tasks

    def list_experiments(self) -> List[MLExperiment]:
        """列出实验"""
        return list(self._experiments.values())

    def get_model_versions(self, model_id: str) -> List[ModelVersion]:
        """获取模型版本"""
        return self._models.get(model_id, [])

    def promote_model(self, model_id: str, version: str):
        """推广模型（标记为最佳版本）"""
        versions = self._models.get(model_id, [])
        for v in versions:
            if v.version == version:
                # 找到关联的实验并更新最佳模型
                for experiment in self._experiments.values():
                    if v.experiment_id == experiment.experiment_id:
                        experiment.best_model_id = model_id
                        experiment.best_metric = v.metrics.get("accuracy")
                self._logger.info(f"推广模型: {model_id} {version}")
                break

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        status_counts = {}
        for status in TaskStatus:
            status_counts[status.value] = sum(1 for t in self._tasks.values() if t.status == status)

        task_type_counts = {}
        for task_type in MLTaskType:
            task_type_counts[task_type.value] = sum(1 for t in self._tasks.values() if t.task_type == task_type)

        total_models = sum(len(versions) for versions in self._models.values())

        return {
            "total_tasks": len(self._tasks),
            "status_counts": status_counts,
            "task_type_counts": task_type_counts,
            "total_experiments": len(self._experiments),
            "total_models": total_models,
            "running": self._running
        }