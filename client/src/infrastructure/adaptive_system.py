"""
自适应进化系统 - Self-Evolution Pipeline

整合硬件感知、模型路由、RAG、模型训练、自适应能力于一体，
实现用户无感知的静默进化。

四层架构：
1. 感知层 - 硬件指纹 + 意图识别 + 系统监控
2. 决策层 - 资源仲裁 + 任务路由 + 训练调度
3. 执行层 - 推理引擎 + RAG引擎 + 训练引擎
4. 进化层 - 数据飞轮 + 模型评估 + 热替换部署
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from loguru import logger
from datetime import datetime, timedelta


@dataclass
class SystemState:
    """系统状态"""
    hardware_profile: Dict = field(default_factory=dict)
    system_load: Dict = field(default_factory=dict)
    current_model: str = ""
    active_tasks: List[str] = field(default_factory=list)
    training_queue: List[str] = field(default_factory=list)
    evolution_status: str = "idle"  # idle, collecting, evaluating, deploying
    last_evolution_time: Optional[datetime] = None
    data_flywheel_count: int = 0


@dataclass
class EvolutionConfig:
    """进化配置"""
    enabled: bool = True
    data_collection_threshold: int = 100  # 触发训练的数据量阈值
    evaluation_interval_hours: int = 24
    deployment_window_start: int = 2  # 部署窗口开始时间（凌晨2点）
    deployment_window_end: int = 6  # 部署窗口结束时间（凌晨6点）
    min_idle_time_minutes: int = 60  # 最小空闲时间要求
    auto_deploy: bool = True  # 是否自动部署
    rollback_on_failure: bool = True  # 失败时是否回滚


class AdaptiveSystem:
    """
    自适应进化系统
    
    实现用户无感知的静默进化：
    1. 持续收集高质量交互数据
    2. 自动判断是否需要训练
    3. 在系统空闲时执行训练
    4. 自动评估新模型
    5. 无缝热替换部署
    """
    
    def __init__(self):
        self._logger = logger.bind(component="AdaptiveSystem")
        self._state = SystemState()
        self._config = EvolutionConfig()
        
        # 初始化各层组件
        self._init_perception_layer()
        self._init_decision_layer()
        self._init_execution_layer()
        self._init_evolution_layer()
        
        # 启动后台任务
        self._background_tasks = []
        self._start_background_tasks()
        
        self._logger.info("自适应进化系统初始化完成")
    
    def _init_perception_layer(self):
        """初始化感知层"""
        from .system_resources import SystemResources
        from .intent_classifier import IntentClassifier
        
        self._hardware_profiler = SystemResources()
        self._intent_classifier = IntentClassifier()
        
        # 生成初始硬件指纹
        self._state.hardware_profile = self._hardware_profiler.get_hardware_profile()
        self._logger.info(f"硬件指纹生成完成: {self._state.hardware_profile.get('gpu_name', 'Unknown')}")
    
    def _init_decision_layer(self):
        """初始化决策层"""
        from .training.ms_swift_integration import TrainingScheduler
        
        self._training_scheduler = TrainingScheduler()
        
        # 加载配置预设
        self._load_config_preset()
    
    def _init_execution_layer(self):
        """初始化执行层"""
        from .ollama_runner import OllamaRunner
        from ..business.fusion_rag.rag_engine import RAGEngine
        
        self._inference_engine = OllamaRunner()
        self._rag_engine = RAGEngine()
    
    def _init_evolution_layer(self):
        """初始化进化层"""
        from .evolution.data_flywheel import DataFlywheel
        from .evolution.model_evaluator import ModelEvaluator
        from .evolution.hotswap_deployer import HotswapDeployer
        
        self._data_flywheel = DataFlywheel()
        self._model_evaluator = ModelEvaluator()
        self._hotswap_deployer = HotswapDeployer()
        
        # 加载数据飞轮统计
        self._state.data_flywheel_count = self._data_flywheel.get_record_count()
    
    def _load_config_preset(self):
        """加载硬件匹配的配置预设"""
        profile = self._state.hardware_profile
        gpu_vram = profile.get("gpu_vram_gb", 0)
        ram_gb = profile.get("ram_gb", 0)
        
        # 根据硬件选择预设
        if gpu_vram >= 48:
            preset = "performance_high"
            model = "Qwen3.6-35B-A3B-Q4_K_M"
        elif gpu_vram >= 16:
            preset = "performance"
            model = "Qwen3.6-14B-A3B-Q4_K_M"
        elif gpu_vram >= 8:
            preset = "balanced"
            model = "Qwen3.5-7B-Q4_K_M"
        elif ram_gb >= 32:
            preset = "balanced"
            model = "Qwen3.5-4B-Q4_K_M"
        else:
            preset = "lightweight"
            model = "Qwen3.5-2B-Q4_K_M"
        
        self._state.current_model = model
        self._logger.info(f"硬件匹配预设: {preset}, 模型: {model}")
    
    def _start_background_tasks(self):
        """启动后台任务"""
        loop = asyncio.get_event_loop()
        
        # 系统监控任务（每30秒）
        self._background_tasks.append(
            loop.create_task(self._monitor_system())
        )
        
        # 数据收集任务（持续运行）
        self._background_tasks.append(
            loop.create_task(self._collect_data())
        )
        
        # 进化调度任务（每小时检查）
        self._background_tasks.append(
            loop.create_task(self._schedule_evolution())
        )
        
        self._logger.info("后台任务启动完成")
    
    async def _monitor_system(self):
        """系统监控任务"""
        while True:
            try:
                # 更新系统负载
                self._state.system_load = {
                    "cpu": self._hardware_profiler.get_cpu_usage(),
                    "memory": self._hardware_profiler.get_memory_usage(),
                    "gpu": self._hardware_profiler.get_gpu_usage() if self._hardware_profiler.has_gpu() else 0,
                    "timestamp": datetime.now().isoformat()
                }
                
                await asyncio.sleep(30)
            except Exception as e:
                self._logger.error(f"系统监控异常: {e}")
                await asyncio.sleep(60)
    
    async def _collect_data(self):
        """数据收集任务"""
        while True:
            try:
                # 收集交互数据
                new_records = self._data_flywheel.collect_recent_interactions()
                if new_records > 0:
                    self._state.data_flywheel_count += new_records
                    self._logger.debug(f"收集到 {new_records} 条新数据，累计 {self._state.data_flywheel_count} 条")
                
                await asyncio.sleep(60)
            except Exception as e:
                self._logger.error(f"数据收集异常: {e}")
                await asyncio.sleep(300)
    
    async def _schedule_evolution(self):
        """进化调度任务"""
        while True:
            try:
                # 检查是否满足进化条件
                if self._check_evolution_ready():
                    await self._execute_evolution_pipeline()
                
                await asyncio.sleep(3600)  # 每小时检查一次
            except Exception as e:
                self._logger.error(f"进化调度异常: {e}")
                await asyncio.sleep(3600)
    
    def _check_evolution_ready(self) -> bool:
        """检查是否满足进化条件"""
        # 检查是否启用进化
        if not self._config.enabled:
            return False
        
        # 检查数据量阈值
        if self._state.data_flywheel_count < self._config.data_collection_threshold:
            return False
        
        # 检查时间窗口（凌晨2-6点）
        now = datetime.now()
        hour = now.hour
        if not (self._config.deployment_window_start <= hour < self._config.deployment_window_end):
            return False
        
        # 检查系统是否空闲
        if not self._is_system_idle():
            return False
        
        # 检查距离上次进化的时间
        if self._state.last_evolution_time:
            time_since_last = datetime.now() - self._state.last_evolution_time
            if time_since_last < timedelta(hours=self._config.evaluation_interval_hours):
                return False
        
        return True
    
    def _is_system_idle(self) -> bool:
        """检查系统是否空闲"""
        load = self._state.system_load
        return (
            load.get("cpu", 100) < 20 and
            load.get("memory", 100) < 40 and
            load.get("gpu", 100) < 10
        )
    
    async def _execute_evolution_pipeline(self):
        """执行进化流水线"""
        self._logger.info("========== 开始进化流水线 ==========")
        self._state.evolution_status = "collecting"
        
        try:
            # 阶段1: 数据准备
            self._logger.info("阶段1: 数据准备")
            dataset_path = await self._prepare_training_data()
            
            # 阶段2: 模型训练
            self._state.evolution_status = "training"
            self._logger.info("阶段2: 模型训练")
            trained_model_path = await self._execute_training(dataset_path)
            
            if not trained_model_path:
                self._logger.warning("训练失败，跳过后续步骤")
                return
            
            # 阶段3: 模型评估
            self._state.evolution_status = "evaluating"
            self._logger.info("阶段3: 模型评估")
            evaluation_result = await self._evaluate_model(trained_model_path)
            
            if not evaluation_result.get("success"):
                self._logger.warning("评估未通过，跳过部署")
                return
            
            # 阶段4: 热替换部署
            self._state.evolution_status = "deploying"
            self._logger.info("阶段4: 热替换部署")
            deployment_result = await self._deploy_model(trained_model_path)
            
            if deployment_result.get("success"):
                self._logger.info("✅ 进化完成！")
                self._state.last_evolution_time = datetime.now()
                self._state.data_flywheel_count = 0  # 重置计数器
            
        except Exception as e:
            self._logger.error(f"进化流水线异常: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            self._state.evolution_status = "idle"
            self._logger.info("========== 进化流水线结束 ==========")
    
    async def _prepare_training_data(self) -> str:
        """准备训练数据"""
        self._logger.info("清洗和格式化训练数据...")
        dataset_path = self._data_flywheel.prepare_training_dataset()
        self._logger.info(f"训练数据集准备完成: {dataset_path}")
        return dataset_path
    
    async def _execute_training(self, dataset_path: str) -> Optional[str]:
        """执行模型训练"""
        self._logger.info(f"开始训练，数据集: {dataset_path}")
        
        from .training.ms_swift_integration import TrainingConfig
        
        config = TrainingConfig(
            model_name=self._get_base_model_for_training(),
            dataset_name=dataset_path,
            output_dir="./output/evolution",
            training_type="lora",
            epochs=3,
            batch_size=8
        )
        
        result = self._training_scheduler.schedule_training(config)
        
        # 等待训练完成（最多24小时）
        timeout = 24 * 60 * 60
        start_time = time.time()
        
        while self._training_scheduler.is_training():
            if time.time() - start_time > timeout:
                self._logger.error("训练超时")
                return None
            await asyncio.sleep(60)
        
        # 检查结果
        if result.get("success"):
            return result.get("model_path")
        else:
            self._logger.error(f"训练失败: {result.get('error')}")
            return None
    
    def _get_base_model_for_training(self) -> str:
        """获取用于训练的基础模型"""
        # 根据当前模型选择合适的训练模型
        current = self._state.current_model
        
        if "35B" in current or "32B" in current:
            return "Qwen/Qwen3.5-4B"
        elif "14B" in current:
            return "Qwen/Qwen3.5-4B"
        elif "8B" in current or "7B" in current:
            return "Qwen/Qwen3.5-2B"
        else:
            return "Qwen/Qwen3.5-2B"
    
    async def _evaluate_model(self, model_path: str) -> Dict:
        """评估新模型"""
        self._logger.info(f"评估模型: {model_path}")
        
        result = self._model_evaluator.evaluate(
            model_path,
            self._state.current_model
        )
        
        if result.get("winner") == "new":
            self._logger.info("新模型胜出！")
            return {"success": True, **result}
        else:
            self._logger.info("新模型未胜出")
            return {"success": False, **result}
    
    async def _deploy_model(self, model_path: str) -> Dict:
        """部署新模型"""
        self._logger.info(f"部署模型: {model_path}")
        
        result = self._hotswap_deployer.deploy(
            model_path,
            rollback_on_failure=self._config.rollback_on_failure
        )
        
        if result.get("success"):
            # 更新当前模型
            self._state.current_model = result.get("new_model_name", self._state.current_model)
            self._logger.info(f"模型更新为: {self._state.current_model}")
        
        return result
    
    def process_query(self, query: str) -> Dict:
        """处理用户查询（完整流程）"""
        # 1. 意图识别
        intent = self._intent_classifier.classify(query)
        
        # 2. 路由决策
        if intent == "document_query":
            # RAG 查询
            result = self._rag_engine.query(query)
            source = "RAG"
        elif intent == "simple_qa":
            # 尝试 RAG 回答
            rag_result = self._rag_engine.query(query)
            if rag_result.get("success") and rag_result.get("confidence", 0) > 0.7:
                result = rag_result
                source = "RAG"
            else:
                # 回退到 LLM
                result = self._inference_engine.generate(query)
                source = "LLM"
        else:
            # complex_reasoning, code_generation
            result = self._inference_engine.generate(query)
            source = "LLM"
        
        # 3. 收集交互数据（用于进化）
        self._data_flywheel.record_interaction({
            "query": query,
            "intent": intent,
            "source": source,
            "response": result.get("response", ""),
            "timestamp": datetime.now().isoformat()
        })
        
        return {
            "response": result.get("response", ""),
            "intent": intent,
            "source": source,
            "confidence": result.get("confidence", 0)
        }
    
    def get_system_state(self) -> SystemState:
        """获取系统状态"""
        return self._state
    
    def get_evolution_config(self) -> EvolutionConfig:
        """获取进化配置"""
        return self._config
    
    def update_evolution_config(self, **kwargs):
        """更新进化配置"""
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)
        self._logger.info(f"进化配置已更新: {kwargs}")
    
    def shutdown(self):
        """关闭系统"""
        self._logger.info("关闭自适应进化系统...")
        
        # 取消后台任务
        for task in self._background_tasks:
            task.cancel()
        
        # 保存状态
        self._save_state()
        
        self._logger.info("自适应进化系统已关闭")
    
    def _save_state(self):
        """保存系统状态"""
        state_dir = Path.home() / ".livingtree_agent" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        
        state_data = {
            "current_model": self._state.current_model,
            "last_evolution_time": self._state.last_evolution_time.isoformat() if self._state.last_evolution_time else None,
            "data_flywheel_count": self._state.data_flywheel_count,
            "evolution_status": self._state.evolution_status
        }
        
        (state_dir / "system_state.json").write_text(
            json.dumps(state_data, indent=2)
        )


# 全局实例
_adaptive_system_instance = None

def get_adaptive_system() -> AdaptiveSystem:
    """获取自适应系统实例"""
    global _adaptive_system_instance
    if _adaptive_system_instance is None:
        _adaptive_system_instance = AdaptiveSystem()
    return _adaptive_system_instance


# 测试代码
if __name__ == "__main__":
    print("=" * 60)
    print("自适应进化系统测试")
    print("=" * 60)
    
    # 初始化系统
    system = get_adaptive_system()
    
    # 获取状态
    state = system.get_system_state()
    print(f"当前模型: {state.current_model}")
    print(f"硬件: {state.hardware_profile.get('gpu_name', 'Unknown')}")
    print(f"数据飞轮计数: {state.data_flywheel_count}")
    print(f"进化状态: {state.evolution_status}")
    
    # 处理测试查询
    print("\n处理查询...")
    result = system.process_query("什么是人工智能？")
    print(f"意图: {result['intent']}")
    print(f"来源: {result['source']}")
    print(f"响应长度: {len(result['response'])} 字符")
    
    print("\n" + "=" * 60)