"""
专家模型训练流水线 - ExpertTrainingPipeline

阶段3: 整合查询收集、蒸馏数据生成和模型微调，端到端训练专家小模型。

核心功能:
1. 自动收集高频查询
2. 生成蒸馏数据
3. 调用 fine_tune_expert.py 训练模型
4. 验证和部署训练好的模型

使用方法:
    pipeline = ExpertTrainingPipeline()

    # 短期方案：专家提示注入（无需训练）
    result = pipeline.chat_with_expert_prompt("分析茅台股票")

    # 中期方案：生成蒸馏数据
    pairs = pipeline.collect_and_generate(min_freq=10)

    # 长期方案：训练专家模型
    pipeline.train_expert(
        domain="金融",
        data_path="data/distillation/训练数据.jsonl"
    )
"""

import json
import subprocess
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Callable, Any
from datetime import datetime
from pathlib import Path
from enum import Enum

from .query_collector import QueryCollector, QueryRecord
from .distillation_pipeline import DistillationEnhancer, DistillationPair, AugmentationStrategy
from .router import ExpertRouter, QueryDomain, RoutingDecision
from .fine_tune_expert import FineTuner, TrainConfig


class PipelineStage(Enum):
    """流水线阶段"""
    SHORT_TERM = "short_term"    # 短期：提示注入
    MID_TERM = "mid_term"        # 中期：蒸馏数据收集
    LONG_TERM = "long_term"      # 长期：模型微调


@dataclass
class ExpertModel:
    """专家模型"""
    domain: str
    model_id: str
    model_path: str
    created_at: str
    training_samples: int
    base_model: str = "qwen2.5:1.5b"
    status: str = "active"

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class TrainingJob:
    """训练任务"""
    job_id: str
    domain: str
    stage: PipelineStage
    status: str  # pending/running/completed/failed
    config: Dict[str, Any]
    result: Optional[Dict] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None


class ExpertTrainingPipeline:
    """
    专家模型训练流水线

    三阶段方案：
    1. 短期：专家提示注入（无需训练）
    2. 中期：收集蒸馏数据
    3. 长期：微调专家模型

    Example:
        pipeline = ExpertTrainingPipeline(llm_caller=l4_call)

        # 短期方案
        result = pipeline.chat_with_expert_prompt("分析茅台", domain="金融")

        # 中期方案
        pairs = pipeline.collect_and_generate(min_freq=5)

        # 长期方案
        pipeline.train_expert(domain="金融", data_path="训练数据.jsonl")
    """

    def __init__(
        self,
        llm_caller: Optional[Callable] = None,
        storage_dir: str = "data/distillation",
        expert_models_dir: str = "models/experts"
    ):
        self.llm_caller = llm_caller
        self.storage_dir = Path(storage_dir)
        self.expert_models_dir = Path(expert_models_dir)

        # 创建子目录
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.expert_models_dir.mkdir(parents=True, exist_ok=True)

        # 初始化组件
        self.query_collector = QueryCollector(
            storage_dir=str(self.storage_dir / "queries"),
            llm_caller=llm_caller
        )

        self.distillation_enhancer = DistillationEnhancer(
            llm_caller=llm_caller,
            output_dir=str(self.storage_dir / "enhanced")
        )

        self.router = ExpertRouter()

        # 专家模型注册表
        self.experts_file = self.expert_models_dir / "experts.json"
        self._experts: Dict[str, ExpertModel] = {}
        self._load_experts()

        # 训练任务
        self._jobs: Dict[str, TrainingJob] = {}

    def _load_experts(self):
        """加载已注册的专家模型"""
        if self.experts_file.exists():
            with open(self.experts_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._experts = {k: ExpertModel(**v) for k, v in data.items()}

    def _save_experts(self):
        """保存专家模型注册表"""
        with open(self.experts_file, "w", encoding="utf-8") as f:
            data = {k: v.to_dict() for k, v in self._experts.items()}
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ═══════════════════════════════════════════════════════════════════════
    # 阶段1: 短期方案 - 专家提示注入（无需训练）
    # ═══════════════════════════════════════════════════════════════════════

    def chat_with_expert_prompt(
        self,
        query: str,
        domain: Optional[str] = None,
        use_expert_template: bool = True
    ) -> str:
        """
        短期方案：使用专家提示模板

        无需训练，直接用专家提示增强 LLM 输出。

        Args:
            query: 用户查询
            domain: 领域（自动检测或指定）
            use_expert_template: 是否使用专家模板

        Returns:
            LLM 回答
        """
        # 领域检测
        if not domain:
            routing = self.router.decide(query)
            domain = routing.primary_domain.value

        # 获取专家提示
        if use_expert_template:
            expert_prompt = self._get_expert_prompt(query, domain)
        else:
            expert_prompt = query

        # 调用 LLM
        if self.llm_caller:
            return self.llm_caller(expert_prompt, "")
        return f"[专家模式] {expert_prompt}"

    def _get_expert_prompt(self, query: str, domain: str) -> str:
        """生成专家提示"""
        prompts = {
            "金融": f"""你是一位资深金融分析师，拥有20年投资经验。请对以下问题给出专业分析：

问题：{query}

请从以下维度分析：
1. 基本面分析
2. 估值判断
3. 风险评估
4. 投资建议

保持专业、客观的风格。""",

            "技术": f"""你是一位全栈技术专家，擅长架构设计和性能优化。请对以下技术问题给出专业解答：

问题：{query}

请包含：
1. 技术原理
2. 最佳实践
3. 代码示例（如适用）
4. 注意事项

保持技术严谨的风格。""",

            "法律": f"""你是一位资深律师，精通合同法和商业法规。请对以下法律问题给出专业意见：

问题：{query}

请从法律角度分析：
1. 相关法律规定
2. 权利义务关系
3. 风险点识别
4. 建议措施

保持严谨专业的风格。""",

            "医疗": f"""你是一位主任医师，专注于临床诊断。请对以下医疗问题给出专业建议：

问题：{query}

请包含：
1. 症状分析
2. 可能诊断
3. 检查建议
4. 治疗方案

注意：这仅供参考，具体请遵医嘱。""",

            "通用": f"""你是一位知识渊博的专业助手。请回答：

问题：{query}

请给出全面、准确的回答。"""
        }

        return prompts.get(domain, prompts["通用"])

    # ═══════════════════════════════════════════════════════════════════════
    # 阶段2: 中期方案 - 收集和生成蒸馏数据
    # ═══════════════════════════════════════════════════════════════════════

    def record_query(
        self,
        query: str,
        user_id: str = "",
        response: str = "",
        response_time: float = 0.0
    ) -> QueryRecord:
        """
        记录用户查询

        Args:
            query: 用户查询
            user_id: 用户ID
            response: LLM 回答
            response_time: 响应时间

        Returns:
            QueryRecord
        """
        return self.query_collector.record(query, user_id, response, response_time)

    def batch_record_queries(self, queries: List[str], user_id: str = "") -> List[QueryRecord]:
        """批量记录查询"""
        return self.query_collector.batch_record(queries, user_id)

    def collect_and_generate(
        self,
        min_freq: int = 5,
        augment: bool = True,
        augmentation_strategy: AugmentationStrategy = AugmentationStrategy.PARAPHRASE
    ) -> List[DistillationPair]:
        """
        收集高频查询并生成蒸馏数据

        Args:
            min_freq: 最小频率阈值
            augment: 是否数据增强
            augmentation_strategy: 增强策略

        Returns:
            DistillationPair 列表
        """
        # 获取高频查询
        queries = self.query_collector.get_high_freq_queries(min_freq)

        # 生成蒸馏数据
        pairs = self.distillation_enhancer.generate_from_queries(
            queries,
            generate_rationale=True
        )

        # 数据增强
        if augment:
            pairs = self.distillation_enhancer.augment(pairs, augmentation_strategy)

        # 质量过滤
        pairs = self.distillation_enhancer.filter_quality(pairs)

        return pairs

    def export_distillation_data(
        self,
        pairs: List[DistillationPair],
        filename: str,
        format: str = "llama_factory"
    ) -> Path:
        """
        导出蒸馏数据

        Args:
            pairs: 蒸馏数据
            filename: 文件名
            format: 格式

        Returns:
            输出路径
        """
        return self.distillation_enhancer.export(pairs, filename, format)

    def get_collection_stats(self) -> Dict[str, Any]:
        """获取收集统计"""
        collector_stats = self.query_collector.get_stats_summary()
        domain_stats = self.query_collector.get_domain_stats()

        return {
            "collector": collector_stats,
            "domains": [
                {
                    "domain": s.domain,
                    "count": s.query_count,
                    "percentage": s.percentage,
                    "top_queries": s.top_queries
                }
                for s in domain_stats
            ]
        }

    # ═══════════════════════════════════════════════════════════════════════
    # 阶段3: 长期方案 - 微调专家模型
    # ═══════════════════════════════════════════════════════════════════════

    def train_expert(
        self,
        domain: str,
        data_path: str,
        base_model: str = "qwen2.5:1.5b",
        epochs: int = 3,
        batch_size: int = 2,
        use_unsloth: bool = False
    ) -> str:
        """
        训练专家模型

        实际调用 fine_tune_expert.py 进行训练。

        Args:
            domain: 领域名称
            data_path: 训练数据路径
            base_model: 基础模型
            epochs: 训练轮数
            batch_size: 批大小
            use_unsloth: 是否使用 Unsloth

        Returns:
            job_id
        """
        job_id = f"job_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # 创建训练任务
        job = TrainingJob(
            job_id=job_id,
            domain=domain,
            stage=PipelineStage.LONG_TERM,
            status="running",
            config={
                "base_model": base_model,
                "data_path": data_path,
                "epochs": epochs,
                "batch_size": batch_size,
                "use_unsloth": use_unsloth
            },
            started_at=datetime.now().isoformat()
        )
        self._jobs[job_id] = job

        # 调用 fine_tune_expert.py
        try:
            config = TrainConfig(
                base_model=base_model,
                data_path=data_path,
                output_dir=str(self.expert_models_dir / domain),
                epochs=epochs,
                batch_size=batch_size,
                use_unsloth=use_unsloth
            )

            tuner = FineTuner(config)

            # 准备数据
            train_data = tuner.prepare_data(
                data_path,
                str(self.expert_models_dir / domain / "data")
            )

            # 训练
            if use_unsloth:
                tuner.train_with_unsloth(train_data)
            else:
                llm_config = tuner.generate_llama_factory_config(
                    f"{config.output_dir}/data/train.jsonl",
                    f"{config.output_dir}/data/val.jsonl"
                )
                # 检查是否有 llamafactory-cli
                try:
                    tuner.train_with_llama_factory(llm_config)
                except FileNotFoundError:
                    # 生成脚本供用户手动运行
                    script_path = Path(config.output_dir) / "train.sh"
                    script = f"""#!/bin/bash
# 专家模型训练脚本
llamafactory-cli train {llm_config}
"""
                    with open(script_path, "w", encoding="utf-8") as f:
                        f.write(script)
                    job.status = "pending"
                    job.result = {"script_path": str(script_path)}
                    return job_id

            # 训练成功，注册模型
            expert = ExpertModel(
                domain=domain,
                model_id=f"expert_{domain}_{datetime.now().strftime('%Y%m%d')}",
                model_path=str(self.expert_models_dir / domain),
                created_at=datetime.now().isoformat(),
                training_samples=len(open(data_path).readlines()),
                base_model=base_model
            )

            self._experts[domain] = expert
            self._save_experts()

            # 更新任务状态
            job.status = "completed"
            job.completed_at = datetime.now().isoformat()
            job.result = {"model_id": expert.model_id, "model_path": expert.model_path}

        except Exception as e:
            job.status = "failed"
            job.error = str(e)
            job.completed_at = datetime.now().isoformat()

        return job_id

    def get_training_job(self, job_id: str) -> Optional[TrainingJob]:
        """获取训练任务状态"""
        return self._jobs.get(job_id)

    def register_expert(
        self,
        domain: str,
        model_id: str,
        model_path: str
    ):
        """
        手动注册专家模型

        Args:
            domain: 领域
            model_id: 模型ID
            model_path: 模型路径
        """
        expert = ExpertModel(
            domain=domain,
            model_id=model_id,
            model_path=model_path,
            created_at=datetime.now().isoformat(),
            training_samples=0
        )

        self._experts[domain] = expert
        self._save_experts()

        # 注册到路由
        self.router.register_expert(
            QueryDomain.from_name(domain),
            model_id,
            model_path
        )

    def get_experts(self) -> List[ExpertModel]:
        """获取已注册的专家模型"""
        return list(self._experts.values())

    def get_available_domains(self) -> List[str]:
        """获取可用领域"""
        return list(self._experts.keys())

    # ═══════════════════════════════════════════════════════════════════════
    # 端到端使用
    # ═══════════════════════════════════════════════════════════════════════

    def smart_chat(self, query: str, prefer_expert: bool = True) -> Dict[str, Any]:
        """
        智能聊天：自动选择最佳策略

        策略选择：
        1. 有专家模型 → 使用专家模型
        2. 有高频查询数据 → 使用专家提示
        3. 默认 → 普通 LLM

        Args:
            query: 用户查询
            prefer_expert: 是否优先使用专家

        Returns:
            {"strategy": ..., "response": ..., "domain": ..., "confidence": ...}
        """
        # 路由决策
        routing = self.router.decide(query)

        # 检查是否有专家模型
        if routing.expert_model and prefer_expert:
            return {
                "strategy": "expert_model",
                "response": f"[专家模型 {routing.expert_model}] 回答: {query[:50]}...",
                "domain": routing.primary_domain.value,
                "confidence": routing.confidence,
                "routing": routing
            }

        # 检查是否是高频领域
        domain_stats = self.query_collector.get_domain_stats()
        high_freq_domains = {s.domain for s in domain_stats if s.percentage > 20}

        if routing.primary_domain.value in high_freq_domains:
            # 使用专家提示
            response = self.chat_with_expert_prompt(query, routing.primary_domain.value)
            return {
                "strategy": "expert_prompt",
                "response": response,
                "domain": routing.primary_domain.value,
                "confidence": routing.confidence,
                "routing": routing
            }

        # 默认 LLM
        if self.llm_caller:
            response = self.llm_caller(query, "")
        else:
            response = query

        return {
            "strategy": "llm_default",
            "response": response,
            "domain": routing.primary_domain.value,
            "confidence": routing.confidence,
            "routing": routing
        }

    def get_full_stats(self) -> Dict[str, Any]:
        """获取完整统计"""
        return {
            "collection": self.get_collection_stats(),
            "experts": {
                "count": len(self._experts),
                "domains": [e.domain for e in self._experts.values()]
            },
            "jobs": {
                "total": len(self._jobs),
                "running": sum(1 for j in self._jobs.values() if j.status == "running"),
                "completed": sum(1 for j in self._jobs.values() if j.status == "completed"),
                "failed": sum(1 for j in self._jobs.values() if j.status == "failed")
            }
        }


# ═══════════════════════════════════════════════════════════════════════════════
# 便捷函数
# ═══════════════════════════════════════════════════════════════════════════════

def create_pipeline(llm_caller: Optional[Callable] = None) -> "ExpertTrainingPipeline":
    """创建专家训练流水线"""
    return ExpertTrainingPipeline(llm_caller=llm_caller)


def quick_start(llm_caller: Optional[Callable] = None) -> "ExpertTrainingPipeline":
    """快速启动（推荐）"""
    return ExpertTrainingPipeline(llm_caller=llm_caller)
