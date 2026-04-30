"""
自适应进化系统 - Self-Evolution Pipeline

与现有系统架构集成：
- 使用现有的 ModelFitter 进行硬件自适应模型选择（不硬编码）
- 使用现有的 SelfEvolutionOrchestrator 进行自我进化协调
- 使用现有的 EvolutionEvaluator 进行模型评估
- 使用现有的 LearningEngine 进行数据收集（数据飞轮）
- 使用现有的 ActiveLearningLoop 进行主动学习

四层架构：
1. 感知层 - 硬件指纹 + 意图识别 + 系统监控
2. 决策层 - 资源仲裁 + 任务路由 + 训练调度
3. 执行层 - 推理引擎 + RAG引擎 + 训练引擎
4. 进化层 - 数据飞轮 + 模型评估 + 热替换部署

自动进化窗口：凌晨 2:00 - 6:00
"""

import asyncio
import json
import time
import platform
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from loguru import logger
from datetime import datetime, timedelta


@dataclass
class HardwareProfile:
    """硬件配置文件"""
    os_type: str = ""
    gpu_name: str = ""
    gpu_vram_gb: int = 0
    cpu_cores: int = 0
    ram_gb: int = 0
    arch: str = ""


@dataclass
class SystemState:
    """系统状态"""
    hardware_profile: HardwareProfile = field(default_factory=HardwareProfile)
    system_load: Dict = field(default_factory=dict)
    current_model: str = ""
    active_tasks: List[str] = field(default_factory=list)
    evolution_status: str = "idle"
    last_evolution_time: Optional[datetime] = None
    evaluation_metrics: Dict = field(default_factory=dict)
    model_fit_results: List = field(default_factory=list)


@dataclass
class EvolutionConfig:
    """进化配置"""
    enabled: bool = True
    data_collection_threshold: int = 100
    evaluation_interval_hours: int = 24
    deployment_window_start: int = 2
    deployment_window_end: int = 6
    min_idle_time_minutes: int = 60
    auto_deploy: bool = True
    rollback_on_failure: bool = True


class AdaptiveSystem:
    """
    自适应进化系统
    
    核心特性：
    - 使用 ModelFitter 进行硬件自适应模型选择（完全动态，不硬编码）
    - 集成现有 SelfEvolutionOrchestrator、EvolutionEvaluator、LearningEngine
    - 支持凌晨 2-6 点静默进化窗口
    - 完整的数据飞轮和模型评估集成
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
        """初始化感知层 - 使用 ModelFitter 的 SystemResources"""
        from infrastructure.model_fitter import SystemResources
        
        self._hardware_profiler = SystemResources()
        
        sys = self._hardware_profiler
        self._state.hardware_profile = HardwareProfile(
            os_type=sys.os_type,
            gpu_name=self._detect_gpu_name(),
            gpu_vram_gb=int(sys.gpu_vram_gb),
            cpu_cores=sys.cpu_cores,
            ram_gb=int(sys.ram_gb),
            arch=platform.machine()
        )
        self._logger.info(f"硬件指纹: {self._state.hardware_profile.gpu_name} ({self._state.hardware_profile.gpu_vram_gb}GB VRAM, {self._state.hardware_profile.ram_gb}GB RAM)")
    
    def _detect_gpu_name(self) -> str:
        """检测 GPU 名称"""
        try:
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            name = pynvml.nvmlDeviceGetName(handle).decode('utf-8')
            pynvml.nvmlShutdown()
            return name
        except:
            pass
        
        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
        
        return "Unknown"
    
    def _init_decision_layer(self):
        """初始化决策层 - 使用 ModelFitter 进行硬件自适应模型选择"""
        from infrastructure.model_fitter import get_model_fitter
        
        self._model_fitter = get_model_fitter()
        
        # 使用 ModelFitter 动态选择最佳模型（不硬编码）
        self._select_optimal_model()
    
    def _select_optimal_model(self):
        """使用 ModelFitter 动态选择最佳模型（完全不硬编码）"""
        try:
            # 获取所有适配的模型及其评分
            fit_results = self._model_fitter.fit("qwen")
            self._state.model_fit_results = fit_results
            
            if fit_results:
                # 选择评分最高的模型
                best_model, score, reason = fit_results[0]
                self._state.current_model = best_model
                self._logger.info(f"ModelFitter 选择最佳模型: {best_model} (评分: {score}/100)")
                self._logger.info(f"选择原因: {reason}")
                
                # 记录备选模型
                for model, s, r in fit_results[1:3]:
                    self._logger.info(f"  备选: {model} ({s}/100) - {r}")
            else:
                # 降级方案：使用默认模型
                self._state.current_model = "qwen3.5:latest"
                self._logger.warning("ModelFitter 未找到适配模型，使用默认: qwen3.5:latest")
                
        except Exception as e:
            self._logger.error(f"ModelFitter 模型选择失败: {e}")
            self._state.current_model = "qwen3.5:latest"
    
    def _init_execution_layer(self):
        """初始化执行层"""
        try:
            from .business.smolllm2.ollama_runner import OllamaRunner
            self._inference_engine = OllamaRunner()
            self._logger.info("✓ 集成 OllamaRunner")
        except Exception as e:
            self._logger.warning(f"OllamaRunner 加载失败: {e}")
            self._inference_engine = None
        
        try:
            from .business.fusion_rag.rag_engine import RAGEngine
            self._rag_engine = RAGEngine()
            self._logger.info("✓ 集成 RAGEngine")
        except Exception as e:
            self._logger.warning(f"RAGEngine 加载失败: {e}")
            self._rag_engine = None
    
    def _init_evolution_layer(self):
        """初始化进化层 - 集成现有组件"""
        self._logger.info("初始化进化层组件...")
        
        # 1. 自我进化协调器 - 核心进化引擎
        try:
            from .business.self_evolution.self_evolution_orchestrator import (
                SelfEvolutionOrchestrator
            )
            self._evolution_orchestrator = SelfEvolutionOrchestrator(
                project_root=str(Path.cwd()),
                auto_approve=False
            )
            self._logger.info("✓ 集成 SelfEvolutionOrchestrator")
        except Exception as e:
            self._logger.warning(f"SelfEvolutionOrchestrator 加载失败: {e}")
            self._evolution_orchestrator = None
        
        # 2. 量化评估框架 - 模型评估（修复导入路径）
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent))
            
            from business.evolution_engine.evaluator.evolution_evaluator import (
                EvolutionEvaluator, EvaluationMode
            )
            self._evaluator = EvolutionEvaluator(str(Path.cwd()))
            self._evaluation_mode = EvaluationMode
            self._logger.info("✓ 集成 EvolutionEvaluator")
        except Exception as e:
            self._logger.warning(f"EvolutionEvaluator 加载失败: {e}")
            self._evaluator = None
        
        # 3. 强化学习引擎 - 数据飞轮核心
        try:
            from .business.evolution_engine.memory.learning_engine import (
                get_learning_engine
            )
            self._learning_engine = get_learning_engine()
            self._logger.info("✓ 集成 LearningEngine (数据飞轮)")
        except Exception as e:
            self._logger.warning(f"LearningEngine 加载失败: {e}")
            self._learning_engine = None
        
        # 4. 主动学习循环
        try:
            from .business.self_evolution.active_learning_loop import (
                ActiveLearningLoop
            )
            self._active_learning_loop = ActiveLearningLoop()
            self._logger.info("✓ 集成 ActiveLearningLoop")
        except Exception as e:
            self._logger.warning(f"ActiveLearningLoop 加载失败: {e}")
            self._active_learning_loop = None
        
        # 5. 训练调度器 - MS-SWIFT集成
        try:
            from .training.ms_swift_integration import get_training_scheduler
            self._training_scheduler = get_training_scheduler()
            self._logger.info("✓ 集成 TrainingScheduler (MS-SWIFT)")
        except Exception as e:
            self._logger.warning(f"TrainingScheduler 加载失败: {e}")
            self._training_scheduler = None
        
        # 6. 双数据飞轮组件（修复导入路径）
        try:
            from .business.self_evolution.hard_variant_generator import (
                HardVariantGenerator
            )
            from .business.self_evolution.train_with_variants import (
                VariantTrainer
            )
            from .business.self_evolution.tool_self_repairer import (
                ToolSelfRepairer
            )
            self._variant_generator = HardVariantGenerator()
            self._variant_trainer = VariantTrainer()
            self._tool_repairer = ToolSelfRepairer()
            self._logger.info("✓ 集成双数据飞轮组件")
        except Exception as e:
            self._logger.warning(f"双数据飞轮组件加载失败: {e}")
            self._variant_generator = None
            self._variant_trainer = None
            self._tool_repairer = None
        
        self._logger.info("进化层初始化完成")
    
    def _start_background_tasks(self):
        """启动后台任务"""
        loop = asyncio.get_event_loop()
        
        # 系统监控任务（每30秒）
        self._background_tasks.append(
            loop.create_task(self._monitor_system())
        )
        
        # 进化调度任务（每小时检查，凌晨 2-6 点执行）
        self._background_tasks.append(
            loop.create_task(self._schedule_evolution())
        )
        
        # 数据收集任务（每10分钟）
        self._background_tasks.append(
            loop.create_task(self._collect_data_periodically())
        )
        
        # 评估任务（每天凌晨3点执行）
        self._background_tasks.append(
            loop.create_task(self._schedule_evaluation())
        )
        
        self._logger.info(f"后台任务启动完成（进化窗口: {self._config.deployment_window_start}:00 - {self._config.deployment_window_end}:00）")
    
    async def _monitor_system(self):
        """系统监控任务"""
        while True:
            try:
                self._state.system_load = {
                    "cpu": self._hardware_profiler.cpu_percent() if hasattr(self._hardware_profiler, 'cpu_percent') else 0,
                    "memory": self._hardware_profiler.virtual_memory().percent if hasattr(self._hardware_profiler, 'virtual_memory') else 0,
                    "gpu": self._hardware_profiler.gpu_vram_gb,
                    "timestamp": datetime.now().isoformat()
                }
                
                await asyncio.sleep(30)
            except Exception as e:
                self._logger.error(f"系统监控异常: {e}")
                await asyncio.sleep(60)
    
    async def _collect_data_periodically(self):
        """定期收集数据（数据飞轮）"""
        while True:
            try:
                if self._learning_engine:
                    stats = self._learning_engine.get_statistics()
                    self._logger.debug(f"数据飞轮统计: {stats}")
                
                await asyncio.sleep(600)
            except Exception as e:
                self._logger.error(f"数据收集异常: {e}")
                await asyncio.sleep(600)
    
    async def _schedule_evaluation(self):
        """评估调度任务（每天凌晨3点）"""
        while True:
            try:
                now = datetime.now()
                
                if now.hour == 3 and now.minute < 10:
                    await self._execute_evaluation()
                
                await asyncio.sleep(3600)
            except Exception as e:
                self._logger.error(f"评估调度异常: {e}")
                await asyncio.sleep(3600)
    
    async def _schedule_evolution(self):
        """进化调度任务（凌晨2-6点静默窗口）"""
        while True:
            try:
                if self._check_evolution_ready():
                    await self._execute_evolution_pipeline()
                
                await asyncio.sleep(3600)
            except Exception as e:
                self._logger.error(f"进化调度异常: {e}")
                await asyncio.sleep(3600)
    
    def _check_evolution_ready(self) -> bool:
        """检查是否满足进化条件"""
        if not self._config.enabled:
            return False
        
        now = datetime.now()
        hour = now.hour
        
        # 检查是否在静默进化窗口内（凌晨2-6点）
        if not (self._config.deployment_window_start <= hour < self._config.deployment_window_end):
            return False
        
        if not self._is_system_idle():
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
        """执行完整进化流水线（静默进化窗口内执行）"""
        self._logger.info("========== 开始静默进化流水线 ==========")
        self._state.evolution_status = "running"
        
        try:
            self._logger.info(f"[阶段1] 数据飞轮: 收集交互数据")
            if self._learning_engine:
                stats = self._learning_engine.get_statistics()
                self._logger.info(f"  学习统计: {stats.get('total_samples', 0)} 样本")
            
            self._logger.info("[阶段2] 自我进化: 执行进化计划")
            if self._evolution_orchestrator:
                session = await self._evolution_orchestrator.auto_evolve_once()
                self._logger.info(f"  进化完成: {session.phase}")
            
            self._logger.info("[阶段3] 双数据飞轮: 变体生成与训练")
            if self._variant_generator and self._variant_trainer:
                variants = await self._variant_generator.generate_variants(max_cases=5)
                self._logger.info(f"  生成了 {len(variants)} 个变体")
                
                report = await self._variant_trainer.train(max_variants=5)
                self._logger.info(f"  训练准确率: {report.get('accuracy', 0):.1%}")
            
            self._logger.info("[阶段4] 模型评估")
            await self._execute_evaluation()
            
            self._logger.info("[阶段5] 主动学习")
            if self._active_learning_loop:
                await self._active_learning_loop.learn_specific_topic("系统优化")
            
            self._state.last_evolution_time = datetime.now()
            self._logger.info("进化流水线完成")
            
        except Exception as e:
            self._logger.error(f"进化流水线异常: {e}")
        finally:
            self._state.evolution_status = "idle"
            self._logger.info("========== 进化流水线结束 ==========")
    
    async def _execute_evaluation(self):
        """执行模型评估"""
        if not self._evaluator:
            self._logger.warning("评估器不可用")
            return
        
        try:
            self._logger.info("执行模型评估...")
            result = self._evaluator.evaluate(mode=self._evaluation_mode.QUICK)
            
            self._state.evaluation_metrics = {
                "timestamp": datetime.now().isoformat(),
                "evaluators": self._evaluator.get_stats(),
                "capability_report": self._evaluator.get_capability_report()
            }
            
            self._logger.info(f"评估完成: {len(result.metrics)} 指标")
            
        except Exception as e:
            self._logger.error(f"评估执行失败: {e}")
    
    def process_query(self, query: str) -> Dict:
        """处理用户查询"""
        intent = self._classify_intent(query)
        
        if intent == "document_query" and self._rag_engine:
            result = self._rag_engine.query(query)
            source = "RAG"
        elif intent == "simple_qa" and self._rag_engine:
            rag_result = self._rag_engine.query(query)
            if rag_result.get("success") and rag_result.get("confidence", 0) > 0.7:
                result = rag_result
                source = "RAG"
            elif self._inference_engine:
                result = self._inference_engine.generate(query, model_name=self._state.current_model)
                source = "LLM"
            else:
                result = {"response": "暂无法处理查询"}
                source = "fallback"
        elif self._inference_engine:
            result = self._inference_engine.generate(query, model_name=self._state.current_model)
            source = "LLM"
        else:
            result = {"response": "暂无法处理查询"}
            source = "fallback"
        
        if self._learning_engine:
            self._learning_engine.record_interaction({
                "query": query,
                "intent": intent,
                "source": source,
                "response": result.get("response", ""),
                "timestamp": datetime.now().isoformat()
            })
        
        return {
            "response": result.get("response", ""),
            "intent": intent,
            "source": source
        }
    
    def _classify_intent(self, query: str) -> str:
        """意图分类"""
        query_lower = query.lower()
        
        if any(keyword in query_lower for keyword in ["文档", "文件", "查找", "搜索", "知识库"]):
            return "document_query"
        elif any(keyword in query_lower for keyword in ["写代码", "代码", "编程", "python", "java", "function"]):
            return "code_generation"
        elif any(keyword in query_lower for keyword in ["解释", "分析", "为什么", "原理", "复杂"]):
            return "complex_reasoning"
        else:
            return "simple_qa"
    
    def start_evolution_engine(self):
        """启动进化引擎"""
        if self._evolution_orchestrator:
            self._evolution_orchestrator.start_auto_evolution(interval_hours=24)
    
    def stop_evolution_engine(self):
        """停止进化引擎"""
        if self._evolution_orchestrator:
            self._evolution_orchestrator.stop_auto_evolution()
    
    def trigger_evolution(self):
        """手动触发进化（用于测试）"""
        loop = asyncio.get_event_loop()
        loop.create_task(self._execute_evolution_pipeline())
    
    def trigger_evaluation(self):
        """手动触发评估"""
        loop = asyncio.get_event_loop()
        loop.create_task(self._execute_evaluation())
    
    def get_system_state(self) -> SystemState:
        """获取系统状态"""
        return self._state
    
    def get_evaluation_report(self) -> Dict:
        """获取评估报告"""
        if not self._evaluator:
            return {"error": "评估器不可用"}
        return self._evaluator.get_capability_report()
    
    def get_evolution_status(self) -> Dict:
        """获取进化状态"""
        if not self._evolution_orchestrator:
            return {"error": "进化协调器不可用"}
        return self._evolution_orchestrator.get_status()
    
    def get_model_fit_results(self) -> List:
        """获取模型适配结果"""
        return self._state.model_fit_results
    
    def shutdown(self):
        """关闭系统"""
        self._logger.info("关闭自适应进化系统...")
        
        for task in self._background_tasks:
            task.cancel()
        
        self.stop_evolution_engine()
        
        self._logger.info("自适应进化系统已关闭")


_adaptive_system_instance = None

def get_adaptive_system() -> AdaptiveSystem:
    """获取自适应系统实例"""
    global _adaptive_system_instance
    if _adaptive_system_instance is None:
        _adaptive_system_instance = AdaptiveSystem()
    return _adaptive_system_instance


if __name__ == "__main__":
    print("=" * 60)
    print("自适应进化系统测试")
    print("=" * 60)
    
    system = get_adaptive_system()
    state = system.get_system_state()
    
    print(f"当前模型: {state.current_model}")
    print(f"GPU: {state.hardware_profile.gpu_name} ({state.hardware_profile.gpu_vram_gb}GB)")
    print(f"CPU: {state.hardware_profile.cpu_cores} cores")
    print(f"内存: {state.hardware_profile.ram_gb}GB")
    
    print("\n模型适配结果:")
    fit_results = system.get_model_fit_results()
    for i, (model, score, reason) in enumerate(fit_results[:3], 1):
        print(f"  {i}. {model} - 评分: {score}/100")
    
    print("\n集成组件状态:")
    print(f"  - ModelFitter: ✓ 已集成（硬件自适应）")
    print(f"  - SelfEvolutionOrchestrator: {'✓ 已集成' if system._evolution_orchestrator else '✗ 未集成'}")
    print(f"  - EvolutionEvaluator: {'✓ 已集成' if system._evaluator else '✗ 未集成'}")
    print(f"  - LearningEngine: {'✓ 已集成' if system._learning_engine else '✗ 未集成'}")
    print(f"  - ActiveLearningLoop: {'✓ 已集成' if system._active_learning_loop else '✗ 未集成'}")
    print(f"  - TrainingScheduler: {'✓ 已集成' if system._training_scheduler else '✗ 未集成'}")
    print(f"  - 双数据飞轮组件: {'✓ 已集成' if system._variant_generator else '✗ 未集成'}")
    
    print(f"\n自动进化配置:")
    print(f"  - 进化窗口: 凌晨 {system._config.deployment_window_start}:00 - {system._config.deployment_window_end}:00")
    print(f"  - 评估间隔: {system._config.evaluation_interval_hours} 小时")
    print(f"  - 自动部署: {'开启' if system._config.auto_deploy else '关闭'}")
    
    print("\n" + "=" * 60)