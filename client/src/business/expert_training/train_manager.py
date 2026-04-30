"""
训练管理器模块 (Training Manager)

整合所有训练模块的统一入口：
1. 训练数据构造器
2. 思维链构造器
3. 任务设计框架
4. 训练策略
5. 评估体系
6. 工业知识发现系统（闭环治理）

实现端到端的工业专家训练流程，基于工业场景知识发现闭环治理体系：
- 源头治理：数据准入、术语归一化、元数据tagging
- 检索对齐：分层检索、行业过滤、上下文改写
- 输出验证：多维度打分、阈值过滤、来源归因
- 持续进化：负反馈学习、专家校准、图谱更新

集成共享基础设施：
- 依赖注入容器
- 配置中心
- 事件总线
"""

import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# 导入共享基础设施
from client.src.business.shared import (
    Container,
    ConfigCenter,
    EventBus,
    Term,
    get_container,
    get_config,
    get_event_bus,
    EVENTS
)


@dataclass
class TrainingProgress:
    """训练进度"""
    stage: int = 1
    epoch: int = 0
    total_epochs: int = 0
    current_task: str = ""
    samples_processed: int = 0
    total_samples: int = 0
    status: str = "idle"  # idle, preparing, training, evaluating, completed


@dataclass
class TrainingConfig:
    """训练配置"""
    output_dir: str = "./experiments"
    target_industry: str = "机械制造"
    model_name: str = "Qwen/Qwen2.5-7B-Instruct"
    gpu_memory_gb: int = 64
    enable_reasoning_chain: bool = True


class TrainingManager:
    """
    训练管理器
    
    整合所有训练模块，提供统一的训练管理接口：
    1. 数据准备 → 构造训练样本和思维链
    2. 阶段训练 → 按阶段执行渐进式训练
    3. 评估测试 → 执行KPI评估
    4. 报告生成 → 生成综合训练报告
    5. 知识发现 → 基于闭环治理体系的知识检索
    
    基于工业场景知识发现闭环治理体系：
    - 源头治理：数据准入、术语归一化、元数据tagging
    - 检索对齐：分层检索、行业过滤、上下文改写
    - 输出验证：多维度打分、阈值过滤、来源归因
    - 持续进化：负反馈学习、专家校准、图谱更新
    
    集成共享基础设施：
    - 依赖注入容器：通过容器获取子模块，消除循环依赖
    - 配置中心：统一管理训练配置，支持动态调整
    - 事件总线：发布/订阅训练事件，解耦模块通信
    """
    
    def __init__(self, config: Optional[TrainingConfig] = None):
        # 获取共享基础设施
        self.container = get_container()
        self.config_center = get_config()
        self.event_bus = get_event_bus()
        
        # 配置（优先使用配置中心）
        self.config = config or TrainingConfig()
        self._load_config_from_center()
        
        # 通过依赖注入获取子模块
        self.data_constructor = self._resolve_module("data_constructor")
        self.reasoning_builder = self._resolve_module("reasoning_builder")
        self.task_framework = self._resolve_module("task_framework")
        self.training_strategy = self._resolve_module("training_strategy")
        self.evaluation_system = self._resolve_module("evaluation_system")
        
        # 初始化工业知识发现系统（闭环治理体系）
        self.knowledge_discovery = self._resolve_module("knowledge_discovery")
        if self.knowledge_discovery:
            self.knowledge_discovery.set_target_industry(self.config.target_industry)
        
        # 训练进度
        self.progress = TrainingProgress()
        
        # 创建输出目录
        Path(self.config.output_dir).mkdir(parents=True, exist_ok=True)
        
        # 订阅事件
        self._subscribe_to_events()
        
        print("[TrainingManager] 初始化完成（已集成依赖注入、配置中心、事件总线）")
    
    def _load_config_from_center(self):
        """从配置中心加载配置"""
        # 从配置中心读取训练相关配置
        training_config = self.config_center.get("training", {})
        
        if training_config:
            self.config.output_dir = training_config.get("output_dir", self.config.output_dir)
            self.config.target_industry = training_config.get("target_industry", self.config.target_industry)
            self.config.model_name = training_config.get("model_name", self.config.model_name)
            self.config.gpu_memory_gb = training_config.get("gpu_memory_gb", self.config.gpu_memory_gb)
            self.config.enable_reasoning_chain = training_config.get("enable_reasoning_chain", self.config.enable_reasoning_chain)
        
        print(f"[TrainingManager] 从配置中心加载配置完成")
    
    def _resolve_module(self, module_name: str):
        """通过依赖注入容器解析模块"""
        try:
            return self.container.resolve(module_name)
        except Exception as e:
            # 如果容器中没有注册，尝试手动创建
            print(f"[TrainingManager] 容器中未找到 {module_name}，尝试手动创建")
            return self._create_module_fallback(module_name)
    
    def _create_module_fallback(self, module_name: str):
        """模块创建降级方案"""
        try:
            if module_name == "data_constructor":
                from .data_constructor import create_data_constructor
                return create_data_constructor()
            elif module_name == "reasoning_builder":
                from .reasoning_chain_builder import create_reasoning_chain_builder
                return create_reasoning_chain_builder()
            elif module_name == "task_framework":
                from .task_framework import create_task_framework
                return create_task_framework()
            elif module_name == "training_strategy":
                from .training_strategy import create_training_strategy
                return create_training_strategy()
            elif module_name == "evaluation_system":
                from .evaluation_system import create_evaluation_system
                return create_evaluation_system()
            elif module_name == "knowledge_discovery":
                from client.src.business.fusion_rag import create_industrial_knowledge_discovery
                return create_industrial_knowledge_discovery()
            elif module_name == "term_table_builder":
                from .term_table_builder import create_auto_term_table_builder
                return create_auto_term_table_builder()
            elif module_name == "feedback_learner":
                from client.src.business.fusion_rag import create_feedback_learner
                return create_feedback_learner()
            else:
                return None
        except Exception as e:
            print(f"[TrainingManager] 创建 {module_name} 失败: {e}")
            return None
    
    def _subscribe_to_events(self):
        """订阅事件总线"""
        # 订阅训练相关事件
        self.event_bus.subscribe(EVENTS["TERM_ADDED"], self._on_term_added)
        self.event_bus.subscribe(EVENTS["DOCUMENT_VALIDATED"], self._on_document_validated)
        self.event_bus.subscribe(EVENTS["FEEDBACK_RECORDED"], self._on_feedback_recorded)
        
        print("[TrainingManager] 事件订阅完成")
    
    def _on_term_added(self, event):
        """处理术语添加事件"""
        print(f"[TrainingManager] 收到术语添加事件: {event}")
        # 可以在这里更新训练数据或触发增量训练
    
    def _on_document_validated(self, event):
        """处理文档验证事件"""
        print(f"[TrainingManager] 收到文档验证事件: {event}")
    
    def _on_feedback_recorded(self, event):
        """处理反馈记录事件"""
        print(f"[TrainingManager] 收到反馈记录事件: {event}")
        # 可以在这里触发增量训练
    
    def prepare_data(self, source_configs: Optional[List[Dict]] = None, 
                    synthetic_count: int = 5000):
        """
        准备训练数据
        
        Args:
            source_configs: 数据源配置列表
            synthetic_count: 合成样本数量
        """
        self.progress.status = "preparing"
        
        # 添加数据源
        if source_configs:
            for source in source_configs:
                self.data_constructor.add_source(
                    name=source["name"],
                    source_type=source["type"],
                    path=source["path"],
                    priority=source.get("priority", 1)
                )
        
        # 从数据源构造样本
        for source_name in self.data_constructor.sources:
            source = self.data_constructor.sources[source_name]
            
            if source.type == "project_doc":
                self.data_constructor.construct_from_project_docs(source_name)
            elif source.type == "simulation_report":
                self.data_constructor.construct_from_simulation_reports(source_name)
            elif source.type == "expert_revision":
                self.data_constructor.construct_from_expert_revisions(source_name)
        
        # 生成合成样本
        self.data_constructor.generate_synthetic_samples(synthetic_count)
        
        # 如果启用思维链，构造思维链样本
        if self.config.enable_reasoning_chain:
            self._construct_reasoning_chains()
        
        # 导出训练数据
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.data_constructor.export_to_json(
            f"{self.config.output_dir}/training_data_{timestamp}.json"
        )
        
        if self.config.enable_reasoning_chain:
            self.reasoning_builder.export_to_json(
                f"{self.config.output_dir}/reasoning_chains_{timestamp}.json"
            )
        
        self.progress.total_samples = self.data_constructor.total_samples
        print(f"[TrainingManager] 数据准备完成，共 {self.progress.total_samples} 条样本")
    
    def prepare_knowledge_base_data(self, kb_docs: List[Dict[str, str]]):
        """
        从知识库准备训练数据（基于闭环治理体系）
        
        Args:
            kb_docs: 知识库文档列表，每个文档包含 {"id", "title", "content", "source_type", "source"}
        """
        print("[TrainingManager] 从知识库准备训练数据")
        
        # 使用知识发现系统添加文档（带准入验证）
        for doc in kb_docs:
            success = self.knowledge_discovery.add_document(
                doc_id=doc["id"],
                title=doc["title"],
                content=doc["content"],
                source_type=doc.get("source_type", "internal"),
                source=doc.get("source", "unknown")
            )
            
            if success:
                # 如果文档通过验证，添加到训练数据构造器
                self.data_constructor.add_entry(
                    instruction=f"分析文档: {doc['title']}",
                    input_data=doc["content"],
                    output="",
                    task_type="analysis",
                    stage=2,
                    source=f"kb_{doc['id']}"
                )
        
        # 更新统计
        kb_stats = self.knowledge_discovery.get_stats()
        print(f"[TrainingManager] 知识库数据准备完成")
        print(f"  - 已验证文档: {kb_stats['governance']['total_docs_checked']}")
        print(f"  - 通过文档: {kb_stats['governance']['passed_docs']}")
        print(f"  - 拒绝文档: {kb_stats['governance']['rejected_docs']}")
    
    def discover_knowledge(self, query: str, top_k: int = 10) -> Dict[str, Any]:
        """
        使用知识发现系统进行检索（基于闭环治理体系）
        
        Args:
            query: 用户查询
            top_k: 返回数量
            
        Returns:
            知识发现结果
        """
        result = self.knowledge_discovery.discover(query, top_k)
        
        return {
            "query": result.query,
            "normalized_query": result.normalized_query,
            "answer": result.final_answer,
            "reasoning": result.reasoning,
            "uncertainty": result.uncertainty,
            "confidence_score": result.confidence_score,
            "sources": result.sources,
            "document_count": len(result.documents)
        }
    
    def record_knowledge_feedback(self, query: str, doc_id: str, content: str, feedback_type: str):
        """
        记录知识发现的用户反馈（用于持续进化）
        
        Args:
            query: 用户查询
            doc_id: 文档ID
            content: 文档内容
            feedback_type: 反馈类型 (irrelevant/relevant/uncertain)
        """
        self.knowledge_discovery.record_feedback(query, doc_id, content, feedback_type)
        print(f"[TrainingManager] 已记录反馈: {feedback_type}")
    
    def add_knowledge_synonym(self, dialect_term: str, standard_term: str):
        """
        添加行业同义词（用于术语归一化）
        
        Args:
            dialect_term: 方言/内部术语
            standard_term: 标准术语
        """
        self.knowledge_discovery.add_synonym(self.config.target_industry, dialect_term, standard_term)
        print(f"[TrainingManager] 已添加同义词: {dialect_term} -> {standard_term}")
    
    def _construct_reasoning_chains(self):
        """构造思维链样本"""
        # 为不同任务类型生成思维链样本
        selection_samples = [
            ("为化工厂强腐蚀环境选择流量计，介质为硫酸，温度80℃", "selection"),
            ("为汽车发动机测试台选择温度传感器，测量范围-40~200℃", "selection"),
            ("为食品加工厂选择液位计，介质为酱油，温度50℃", "selection")
        ]
        
        diagnosis_samples = [
            ("电机运行时异响且温度升高", "diagnosis"),
            ("流量计读数波动大", "diagnosis"),
            ("泵出口压力不足", "diagnosis")
        ]
        
        comparison_samples = [
            ("方案A使用304不锈钢成本低，方案B使用316不锈钢耐腐蚀性好", "comparison")
        ]
        
        for input_data, task_type in selection_samples:
            self.reasoning_builder.build_selection_chain(
                instruction="根据给定条件选择合适的工业设备",
                input_data=input_data,
                domain=self.config.target_industry
            )
        
        for input_data, task_type in diagnosis_samples:
            self.reasoning_builder.build_diagnosis_chain(
                instruction="分析故障原因并给出解决方案",
                input_data=input_data,
                domain=self.config.target_industry
            )
        
        for input_data, task_type in comparison_samples:
            self.reasoning_builder.build_comparison_chain(
                instruction="对比两个方案并给出建议",
                input_data=input_data,
                domain=self.config.target_industry
            )
        
        print(f"[TrainingManager] 构造了 {self.reasoning_builder.total_samples} 条思维链样本")
    
    def run_stage_training(self, stage: int):
        """
        执行单个阶段的训练
        
        Args:
            stage: 训练阶段 (1-4)
        """
        if stage < 1 or stage > 4:
            raise ValueError("阶段必须在1-4之间")
        
        self.progress.stage = stage
        self.progress.status = "training"
        
        # 配置训练策略
        self.training_strategy.configure_for_stage(stage)
        self.training_strategy.configure_for_hardware(self.config.gpu_memory_gb)
        self.training_strategy.set_model(self.config.model_name)
        
        # 获取当前阶段任务
        stage_config = self.task_framework.stage_configs[stage]
        tasks = self.task_framework.get_stage_tasks(stage)
        
        print(f"[TrainingManager] 开始阶段 {stage}: {stage_config.name}")
        print(f"[TrainingManager] 目标数据量: {stage_config.target_data_count}")
        print(f"[TrainingManager] 任务列表: {[t.name for t in tasks]}")
        
        # 模拟训练过程
        for epoch in range(self.training_strategy.hyper_params.num_train_epochs):
            self.progress.epoch = epoch + 1
            self.progress.total_epochs = self.training_strategy.hyper_params.num_train_epochs
            
            print(f"[TrainingManager] 阶段 {stage} - Epoch {epoch + 1}/{self.progress.total_epochs}")
            
            # 标记任务完成
            for task in tasks:
                self.task_framework.complete_task(task.task_id)
        
        # 更新进度
        self.progress.status = "completed"
        self.task_framework.advance_stage()
        
        print(f"[TrainingManager] 阶段 {stage} 训练完成")
    
    def run_full_training(self):
        """执行完整的四阶段训练"""
        print("[TrainingManager] 开始完整训练流程")
        
        for stage in [1, 2, 3, 4]:
            self.run_stage_training(stage)
            
            # 阶段评估
            if stage <= 3:
                self.evaluate_stage(stage)
            
            # 保存阶段模型
            self.save_stage_model(stage)
        
        print("[TrainingManager] 完整训练流程完成")
    
    def evaluate_stage(self, stage: int):
        """
        评估当前阶段
        
        Args:
            stage: 阶段编号
        """
        self.progress.status = "evaluating"
        
        print(f"[TrainingManager] 评估阶段 {stage}")
        
        # 运行评估
        for case_id in self.evaluation_system.test_cases:
            # 模拟模型输出（实际应调用真实模型）
            model_output = self._generate_simulated_output(case_id)
            
            # 评估
            result = self.evaluation_system.evaluate(case_id, model_output)
            
            # 随机添加专家评分
            import random
            if random.random() < 0.3:
                rating = random.randint(3, 5)
                self.evaluation_system.add_expert_rating(case_id, rating, "专家评分")
        
        # 生成评估报告
        report = self.evaluation_system.generate_report()
        self._print_report_summary(report)
        
        # 导出报告
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.evaluation_system.export_report(
            f"{self.config.output_dir}/evaluation_report_stage{stage}_{timestamp}.json"
        )
        
        self.progress.status = "completed"
    
    def _generate_simulated_output(self, case_id: str) -> str:
        """生成模拟模型输出（用于演示）"""
        test_case = self.evaluation_system.test_cases.get(case_id)
        if not test_case:
            return "无法处理此请求"
        
        # 根据任务类型生成不同输出
        if "selection" in case_id.lower():
            return f"推荐选用电磁流量计，材质建议哈氏C-276。需确认介质浓度等参数。"
        elif "calculation" in case_id.lower():
            return f"根据GB/T 8163标准计算，所需壁厚约为1.07mm。"
        elif "validation" in case_id.lower():
            return f"符合要求。IT7级公差在50mm尺寸段的标准公差为0.025mm。"
        elif "diagnosis" in case_id.lower():
            return f"可能原因包括轴承损坏、润滑不足、过载。建议优先检查轴承状态。"
        elif "comparison" in case_id.lower():
            return f"建议选择方案B，长期可靠性更优。"
        else:
            return f"已完成分析。结果：符合要求。"
    
    def _print_report_summary(self, report: Dict[str, Any]):
        """打印报告摘要"""
        print("=" * 60)
        print("评估报告摘要")
        print("=" * 60)
        print(f"总测试用例: {report['total_test_cases']}")
        print(f"总评估次数: {report['total_evaluations']}")
        print(f"通过率: {report['pass_rate']:.2%}")
        print("\nKPI指标:")
        for kpi, value in report['kpis'].items():
            threshold = report['thresholds'].get(kpi, 0.0)
            status = "✓" if (kpi == "hallucination_rate" and value <= threshold) or \
                           (kpi != "hallucination_rate" and value >= threshold) else "✗"
            print(f"  {kpi}: {value:.4f} (阈值: {threshold}, {status})")
        print("=" * 60)
    
    def save_stage_model(self, stage: int):
        """
        保存阶段模型
        
        Args:
            stage: 阶段编号
        """
        model_dir = Path(f"{self.config.output_dir}/stage{stage}_model")
        model_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存配置
        config_path = model_dir / "training_config.json"
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump({
                "stage": stage,
                "model_name": self.config.model_name,
                "target_industry": self.config.target_industry,
                "lora_rank": self.training_strategy.lora_config.r,
                "batch_size": self.training_strategy.hyper_params.per_device_train_batch_size,
                "epochs": self.training_strategy.hyper_params.num_train_epochs,
                "saved_at": datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)
        
        print(f"[TrainingManager] 阶段 {stage} 模型配置已保存到 {model_dir}")
    
    def generate_training_plan(self) -> Dict[str, Any]:
        """生成完整训练计划"""
        plan = {
            "config": {
                "target_industry": self.config.target_industry,
                "model_name": self.config.model_name,
                "gpu_memory_gb": self.config.gpu_memory_gb,
                "output_dir": self.config.output_dir,
                "enable_reasoning_chain": self.config.enable_reasoning_chain
            },
            "phases": [],
            "estimated_duration_weeks": 12
        }
        
        for stage in [1, 2, 3, 4]:
            stage_config = self.task_framework.stage_configs[stage]
            tasks = self.task_framework.get_stage_tasks(stage)
            
            phase = {
                "stage": stage,
                "name": stage_config.name,
                "duration_weeks": stage_config.duration_weeks,
                "description": stage_config.description,
                "target_data_count": stage_config.target_data_count,
                "tasks": [{"id": t.task_id, "name": t.name, "difficulty": t.difficulty} for t in tasks],
                "evaluation_metrics": stage_config.evaluation_metrics
            }
            
            plan["phases"].append(phase)
        
        return plan
    
    def get_progress(self) -> TrainingProgress:
        """获取训练进度"""
        return self.progress
    
    def get_stats(self) -> Dict[str, Any]:
        """获取综合统计信息"""
        return {
            "config": {
                "target_industry": self.config.target_industry,
                "model_name": self.config.model_name,
                "gpu_memory_gb": self.config.gpu_memory_gb
            },
            "data_constructor": self.data_constructor.get_stats(),
            "reasoning_builder": self.reasoning_builder.get_stats(),
            "task_framework": self.task_framework.get_stats(),
            "training_strategy": self.training_strategy.get_stats(),
            "evaluation_system": self.evaluation_system.get_stats(),
            "knowledge_discovery": self.knowledge_discovery.get_stats(),
            "progress": {
                "stage": self.progress.stage,
                "status": self.progress.status,
                "samples_processed": self.progress.samples_processed,
                "total_samples": self.progress.total_samples
            }
        }


def create_train_manager(config: Optional[TrainingConfig] = None) -> TrainingManager:
    """创建训练管理器实例"""
    return TrainingManager(config)


__all__ = [
    "TrainingManager",
    "TrainingProgress",
    "TrainingConfig",
    "create_train_manager"
]