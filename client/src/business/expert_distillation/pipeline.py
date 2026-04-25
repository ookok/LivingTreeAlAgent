"""
专家蒸馏流水线 - ExpertDistillationPipeline

整合所有组件，提供端到端的专家蒸馏能力。
"""

from typing import Optional, Callable, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .data_generator import DistillationDataGenerator, QATriple, quick_generate
from .template_library import ExpertTemplateLibrary
from .router import ExpertRouter, RoutingDecision, QueryDomain, RouteStrategy
from .l4_caller import L4EnhancedCaller, L4CallResult


@dataclass
class PipelineConfig:
    """流水线配置"""
    # LLM 配置
    llm_call_fn: Optional[Callable] = None
    llm_base_url: str = "http://www.mogoo.com.cn:8899/v1"

    # 专家模型配置
    expert_models_dir: str = "models/experts"
    auto_load_experts: bool = True

    # 数据生成配置
    distillation_data_dir: str = "data/distillation"
    default_samples_per_topic: int = 50

    # 路由配置
    enable_routing: bool = True
    routing_threshold: float = 0.7

    # 缓存配置
    enable_cache: bool = True
    cache_ttl_seconds: int = 3600


class ExpertDistillationPipeline:
    """
    专家蒸馏流水线

    整合数据生成、模板管理、路由决策、L4调用，提供一站式蒸馏能力。

    Example:
        pipeline = ExpertDistillationPipeline()

        # 短期方案：专家提示注入
        result = pipeline.chat("分析这只股票", domain="金融")

        # 中期方案：生成蒸馏数据
        qa_list = pipeline.generate_distillation_data(
            domain="金融",
            topics=["估值", "财报", "走势"]
        )
        pipeline.save_distillation_data(qa_list)

        # 训练专家模型（需要外部工具）
        # pipeline.prepare_training_data(qa_list, output_dir="data/fin_train")
    """

    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or PipelineConfig()

        # 初始化组件
        self.data_generator = DistillationDataGenerator(
            llm_caller=self.config.llm_call_fn,
            output_dir=self.config.distillation_data_dir
        )
        self.template_library = ExpertTemplateLibrary()
        self.router = ExpertRouter() if self.config.enable_routing else None
        self.l4_caller = L4EnhancedCaller(
            llm_call_fn=self.config.llm_call_fn,
            router=self.router,
            template_library=self.template_library
        )

        # 确保目录存在
        Path(self.config.expert_models_dir).mkdir(parents=True, exist_ok=True)
        Path(self.config.distillation_data_dir).mkdir(parents=True, exist_ok=True)

        # 统计
        self.session_stats = {
            "chat_calls": 0,
            "data_generated": 0,
            "experts_loaded": []
        }

    def chat(self, query: str, domain: Optional[str] = None) -> L4CallResult:
        """
        聊天接口（短期方案：专家提示注入）

        Args:
            query: 用户查询
            domain: 指定领域

        Returns:
            L4CallResult
        """
        self.session_stats["chat_calls"] += 1
        return self.l4_caller.call(query, domain)

    def generate_distillation_data(
        self,
        domain: str,
        topics: Optional[List[str]] = None,
        samples_per_topic: Optional[int] = None
    ) -> List[QATriple]:
        """
        生成蒸馏数据（中期方案）

        Args:
            domain: 领域
            topics: 主题列表
            samples_per_topic: 每主题样本数

        Returns:
            QATriple 列表
        """
        samples = samples_per_topic or self.config.default_samples_per_topic

        # 使用增强调用生成高质量数据
        def enhanced_generator(query, system):
            result = self.l4_caller.call(query, domain)
            return f"{result.reasoning}\n\n{result.response}"

        # 临时替换数据生成器的调用函数
        original_caller = self.data_generator.llm_caller
        self.data_generator.llm_caller = enhanced_generator

        qa_list = self.data_generator.generate_dataset(
            domain=domain,
            topics=topics,
            samples_per_topic=samples
        )

        # 恢复
        self.data_generator.llm_caller = original_caller

        self.session_stats["data_generated"] += len(qa_list)
        return qa_list

    def save_distillation_data(
        self,
        qa_list: List[QATriple],
        format: str = "llama_factory"
    ) -> Path:
        """
        保存蒸馏数据

        Args:
            qa_list: 问答数据
            format: 格式 (jsonl/json/llama_factory/sharegpt)

        Returns:
            保存路径
        """
        return self.data_generator.save_dataset(qa_list, format=format)

    def prepare_training_data(
        self,
        qa_list: List[QATriple],
        output_dir: str = "data/training",
        format: str = "llama_factory"
    ) -> Dict[str, Path]:
        """
        准备训练数据（用于微调）

        生成符合 LLaMA-Factory 或其他训练框架格式的数据文件。

        Args:
            qa_list: 蒸馏数据
            output_dir: 输出目录
            format: 输出格式

        Returns:
            输出的文件路径
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # 按领域分组
        by_domain: Dict[str, List[QATriple]] = {}
        for qa in qa_list:
            by_domain.setdefault(qa.domain, []).append(qa)

        output_files = {}
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 1. 合并数据
        if format == "llama_factory":
            merged_path = output_path / f"merged_{timestamp}.jsonl"
            with open(merged_path, "w", encoding="utf-8") as f:
                for qa in qa_list:
                    f.write(qa.to_llama_factory_format().__repr__() + "\n")
            output_files["merged"] = merged_path

        # 2. 分领域数据
        for domain, domain_qa in by_domain.items():
            domain_path = output_path / f"{domain}_{timestamp}.jsonl"
            with open(domain_path, "w", encoding="utf-8") as f:
                for qa in domain_qa:
                    f.write(qa.to_llama_factory_format().__repr__() + "\n")
            output_files[domain] = domain_path

        # 3. 训练配置示例
        config_path = output_path / "train_config.yaml"
        config_content = f"""# LLaMA-Factory 训练配置
model:
  name_or_path: qwen2.5:1.5b
  template: qwen

finetuning_type: lora
lora:
  target: all
  rank: 16
  alpha: 32
  dropout: 0.05

dataset:
  # 使用生成的数据
  {timestamp}_train.jsonl
  # 可添加更多领域数据

output_dir: {self.config.expert_models_dir}/fin_{domain}
"""
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(config_content)
        output_files["config"] = config_path

        return output_files

    def register_expert_model(
        self,
        domain: str,
        model_id: str,
        model_path: str,
        priority: int = 0
    ):
        """
        注册专家模型到路由

        Args:
            domain: 领域
            model_id: 模型标识
            model_path: 模型路径
            priority: 优先级
        """
        if self.router:
            self.router.register_expert(
                QueryDomain.from_name(domain),
                model_id,
                model_path,
                priority
            )
            self.session_stats["experts_loaded"].append(model_id)

    def chat_with_expert(
        self,
        query: str,
        domain: str,
        use_expert_only: bool = False
    ) -> Dict[str, Any]:
        """
        带专家路由的聊天

        Args:
            query: 查询
            domain: 领域
            use_expert_only: 是否仅使用专家模型

        Returns:
            {"strategy": ..., "result": ..., "expert_output": ..., "l4_output": ...}
        """
        if not self.router:
            result = self.chat(query, domain)
            return {"strategy": "l4_only", "result": result}

        # 路由决策
        routing = self.router.decide(query, QueryDomain.from_name(domain))

        if use_expert_only or routing.strategy == RouteStrategy.EXPERT_MODEL:
            # 使用专家模型（如果有注册）
            if routing.expert_model:
                expert_result = self._call_expert_model(routing.expert_model, query)
                return {"strategy": "expert", "result": expert_result, "routing": routing}
            else:
                # 回退到 L4
                result = self.chat(query, domain)
                return {"strategy": "fallback_l4", "result": result, "routing": routing}

        elif routing.strategy == RouteStrategy.HYBRID:
            # 混合模式
            expert_result = self._call_expert_model(routing.expert_model, query) if routing.expert_model else None
            l4_result = self.chat(query, domain)
            return {
                "strategy": "hybrid",
                "expert_output": expert_result,
                "l4_output": l4_result,
                "routing": routing
            }

        else:
            # L4
            result = self.chat(query, domain)
            return {"strategy": "l4", "result": result, "routing": routing}

    def _call_expert_model(self, model_id: str, query: str) -> str:
        """调用专家模型（需要实际集成）"""
        # 这里应该调用实际的专家模型
        # 目前返回模拟结果
        return f"[专家模型 {model_id}] 的回答: {query[:50]}..."

    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        return {
            "session": self.session_stats,
            "data_generator": self.data_generator.get_stats(),
            "l4_caller": self.l4_caller.get_stats(),
            "template_library": self.template_library.get_stats()
        }


# 便捷函数
def create_pipeline(**kwargs) -> ExpertDistillationPipeline:
    """创建流水线"""
    config = PipelineConfig(**kwargs)
    return ExpertDistillationPipeline(config)
