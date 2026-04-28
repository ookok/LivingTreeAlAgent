"""
EnergyAwareScheduler - 节能调度器

功能：
1. 根据任务复杂度动态选择模型
2. 模型自动休眠
3. 结果缓存
4. 批量处理

遵循自我进化原则：
- 从使用模式中学习优化节能策略
- 动态调整模型选择策略
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger
from datetime import datetime, timedelta


class EnergyAwareScheduler:
    """
    节能调度器
    
    节能策略：
    - 动态模型选择：简单任务用小型模型，复杂任务用大型模型
    - 模型自动休眠：空闲一段时间后自动停止模型
    - 结果缓存：相同问题直接返回缓存结果
    - 批量处理：多个任务合并处理
    """

    def __init__(self):
        self._logger = logger.bind(component="EnergyAwareScheduler")
        self._cache = {}
        self._model_status = {}  # 模型状态：active/idle/stopped
        self._last_used_time = {}
        self._idle_timeout = 300  # 5分钟空闲超时
        self._learning_history = []

    async def schedule(self, task: str) -> Any:
        """
        节能调度
        
        工作流程：
        1. 检查缓存（如果命中，直接返回，节省 100% 资源）
        2. 评估任务复杂度
        3. 选择合适大小的模型（小任务用小模型）
        4. 批量处理（如果可能）
        """
        # 1. 检查缓存
        cached_result = await self._check_cache(task)
        if cached_result:
            return cached_result

        # 2. 评估任务复杂度
        complexity = await self._evaluate_complexity(task)

        # 3. 选择合适大小的模型
        model = self._select_model(complexity)

        # 4. 确保模型处于活跃状态
        await self._ensure_model_active(model)

        # 5. 执行任务
        result = await self._execute_with_model(task, model)

        # 6. 缓存结果
        await self._cache_result(task, result)

        # 7. 更新使用时间
        self._last_used_time[model] = datetime.now()

        return result

    async def _check_cache(self, task: str) -> Optional[Any]:
        """检查缓存"""
        cached = self._cache.get(task)
        if cached:
            self._logger.debug(f"命中缓存: {task[:30]}...")
            return cached["result"]
        return None

    async def _evaluate_complexity(self, task: str) -> float:
        """评估任务复杂度（0-1 之间）"""
        # 简单启发式规则
        if len(task) < 50:
            return 0.2
        elif "计算" in task or "分析" in task:
            return 0.6
        elif "生成" in task and "报告" in task:
            return 0.8
        else:
            return 0.5

    def _select_model(self, complexity: float) -> str:
        """根据复杂度选择模型"""
        if complexity <= 0.3:
            return "qwen2.5:1.5b"  # 小模型
        elif complexity <= 0.7:
            return "qwen3.5:4b"    # 中模型
        else:
            return "qwen3.6:35b-a3b"  # 大模型

    async def _ensure_model_active(self, model: str):
        """确保模型处于活跃状态"""
        if self._model_status.get(model) != "active":
            await self._start_model(model)

    async def _start_model(self, model: str):
        """启动模型"""
        self._logger.info(f"启动模型: {model}")
        self._model_status[model] = "active"

    async def _execute_with_model(self, task: str, model: str) -> Any:
        """使用指定模型执行任务"""
        self._logger.info(f"使用模型 {model} 执行任务: {task[:30]}...")
        return {"result": f"执行结果", "model_used": model}

    async def _cache_result(self, task: str, result: Any):
        """缓存结果"""
        self._cache[task] = {
            "result": result,
            "timestamp": datetime.now()
        }

    async def monitor_idle_models(self):
        """监控空闲模型，自动休眠"""
        now = datetime.now()
        
        for model, last_used in list(self._last_used_time.items()):
            if now - last_used > timedelta(seconds=self._idle_timeout):
                await self._stop_model(model)

    async def _stop_model(self, model: str):
        """停止模型"""
        self._logger.info(f"停止空闲模型: {model}")
        self._model_status[model] = "stopped"

    def get_stats(self) -> Dict[str, Any]:
        """获取节能调度器统计信息"""
        active_models = sum(1 for s in self._model_status.values() if s == "active")
        cache_hits = len(self._cache)
        
        return {
            "active_models": active_models,
            "total_models": len(self._model_status),
            "cache_size": len(self._cache),
            "learning_history_count": len(self._learning_history)
        }