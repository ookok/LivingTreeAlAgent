"""
蒸馏数据增强器 - DistillationEnhancer

阶段2: 基于真实查询生成高质量蒸馏数据

核心功能:
1. 基于 QueryCollector 的真实查询生成蒸馏数据
2. 使用 L4 模型生成专家级回答
3. 数据增强：同义改写、难度调整
4. 自动领域标注和质量过滤

使用方法:
    enhancer = DistillationEnhancer(llm_caller=l4_call)

    # 基于真实查询生成
    pairs = enhancer.generate_from_queries(collector.get_high_freq_queries())

    # 数据增强
    augmented = enhancer.augment(pairs, strategy="paraphrase")

    # 质量过滤
    filtered = enhancer.filter_quality(augmented)
"""

import json
import re
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Callable, Any, Tuple
from datetime import datetime
from pathlib import Path
from enum import Enum


class AugmentationStrategy(Enum):
    """增强策略"""
    PARAPHRASE = "paraphrase"      # 同义改写
    DIFFICULTY_UP = "difficulty_up"  # 难度提升
    DIFFICULTY_DOWN = "difficulty_down"  # 难度降低
    CONTEXT_EXPAND = "context_expand"  # 上下文扩展
    CONTRASTIVE = "contrastive"  # 对比增强


@dataclass
class DistillationPair:
    """蒸馏问答对"""
    id: str
    query: str
    response: str
    domain: str
    difficulty: str
    rationale: str = ""
    source: str = "auto"  # auto/manual/enriched
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return asdict(self)

    def to_llama_factory_format(self) -> Dict:
        return {
            "instruction": self.query,
            "input": "",
            "output": f"{self.rationale}\n\n{self.response}" if self.rationale else self.response
        }

    def to_sharegpt_format(self) -> Dict:
        return {
            "conversations": [
                {"from": "human", "value": self.query},
                {"from": "gpt", "value": self.response}
            ],
            "domain": self.domain,
            "difficulty": self.difficulty
        }


class DistillationEnhancer:
    """
    蒸馏数据增强器

    将高频查询转化为高质量蒸馏数据。

    Example:
        enhancer = DistillationEnhancer(llm_caller=l4_call)

        # 生成
        pairs = enhancer.generate_from_queries(queries)

        # 增强
        augmented = enhancer.augment(pairs, strategy=AugmentationStrategy.PARAPHRASE)

        # 过滤
        filtered = enhancer.filter_quality(augmented)

        # 导出
        enhancer.export(filtered, "train_data.jsonl")
    """

    DIFFICULTY_KEYWORDS = {
        "简单": ["是什么", "什么是", "定义", "介绍", "告诉我"],
        "中等": ["分析", "比较", "区别", "如何", "怎么", "评估", "建议"],
        "困难": ["深入", "详细", "全面", "系统", "综合", "多维度", "复杂"],
        "专家": ["专家", "资深", "学术", "研究", "框架", "架构设计", "体系"]
    }

    def __init__(
        self,
        llm_caller: Optional[Callable] = None,
        output_dir: str = "data/distillation/enhanced",
        quality_threshold: float = 0.7
    ):
        self.llm_caller = llm_caller
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.quality_threshold = quality_threshold
        self._pair_id = 0

    def _generate_id(self) -> str:
        """生成唯一ID"""
        self._pair_id += 1
        return f"pair_{datetime.now().strftime('%Y%m%d')}_{self._pair_id}"

    def _assess_difficulty(self, query: str) -> str:
        """评估查询难度"""
        query_lower = query.lower()
        for difficulty, keywords in reversed(list(self.DIFFICULTY_KEYWORDS.items())):
            if any(kw in query_lower for kw in keywords):
                return difficulty
        return "中等"

    def _extract_rationale(self, response: str) -> Tuple[str, str]:
        """从回答中提取推理过程"""
        # 尝试识别推理标记
        patterns = [
            (r"【?分析】?:?\s*(.*?)(?=【|\n\n|$)", r"【?结论】?:?\s*(.*)"),
            (r"【?推理】?:?\s*(.*?)(?=【|\n\n|$)", r"【?答案】?:?\s*(.*)"),
            (r"首先[，,]?(.*?)[，,]?其次[，,]?(.*?)[，,]?最后[，,]?(.*)", r"(.*)")
        ]

        # 简单策略：按段落分割
        paragraphs = response.split("\n\n")
        if len(paragraphs) >= 2:
            # 假设第一段是推理，后面是结论
            return paragraphs[0].strip(), "\n\n".join(paragraphs[1:]).strip()

        return "", response.strip()

    def _call_llm(self, prompt: str, system: str = "") -> str:
        """调用 LLM"""
        if self.llm_caller:
            return self.llm_caller(prompt, system)
        return f"专家级回答：{prompt}"

    def generate_from_queries(
        self,
        queries: List[Any],
        domain: Optional[str] = None,
        generate_rationale: bool = True
    ) -> List[DistillationPair]:
        """
        从查询列表生成蒸馏数据

        Args:
            queries: QueryRecord 列表或字符串列表
            domain: 强制指定领域
            generate_rationale: 是否生成推理过程

        Returns:
            DistillationPair 列表
        """
        pairs = []

        for item in queries:
            # 统一处理
            if isinstance(item, str):
                query = item
                item_domain = domain or "通用"
                response = ""
            else:
                query = getattr(item, "query", str(item))
                item_domain = domain or getattr(item, "domain", "通用")
                response = getattr(item, "response", "") or ""

            # 获取/生成回答
            if not response:
                system_prompts = {
                    "金融": "你是一位资深金融分析师，请给出专业的分析回答，展示推理过程。",
                    "技术": "你是一位资深技术专家，请给出专业的技术解答，展示推理过程。",
                    "法律": "你是一位资深律师，请给出专业的法律建议，展示推理过程。",
                    "医疗": "你是一位主任医师，请给出专业的医疗建议，展示推理过程。",
                    "通用": "你是一位知识渊博的助手，请给出详细的回答。"
                }
                system = system_prompts.get(item_domain, system_prompts["通用"])
                response = self._call_llm(
                    f"问题：{query}\n\n请给出详细的分析和结论。",
                    system
                )

            # 提取推理过程
            rationale, clean_response = self._extract_rationale(response) if generate_rationale else ("", response)

            pairs.append(DistillationPair(
                id=self._generate_id(),
                query=query,
                response=clean_response,
                domain=item_domain,
                difficulty=self._assess_difficulty(query),
                rationale=rationale,
                source="auto",
                metadata={"original_response": response}
            ))

        return pairs

    def augment(
        self,
        pairs: List[DistillationPair],
        strategy: AugmentationStrategy = AugmentationStrategy.PARAPHRASE,
        num_variations: int = 2
    ) -> List[DistillationPair]:
        """
        数据增强

        Args:
            pairs: 原始问答对
            strategy: 增强策略
            num_variations: 每条生成变体数量

        Returns:
            增强后的问答对
        """
        augmented = []

        for pair in pairs:
            if strategy == AugmentationStrategy.PARAPHRASE:
                variations = self._paraphrase(pair, num_variations)
            elif strategy == AugmentationStrategy.DIFFICULTY_UP:
                variations = self._increase_difficulty(pair, num_variations)
            elif strategy == AugmentationStrategy.DIFFICULTY_DOWN:
                variations = self._decrease_difficulty(pair, num_variations)
            elif strategy == AugmentationStrategy.CONTEXT_EXPAND:
                variations = self._expand_context(pair, num_variations)
            elif strategy == AugmentationStrategy.CONTRASTIVE:
                variations = self._generate_contrastive(pair, num_variations)
            else:
                variations = [pair]

            augmented.extend(variations)

        return pairs + augmented

    def _paraphrase(self, pair: DistillationPair, num: int) -> List[DistillationPair]:
        """同义改写"""
        prompt = f"""请将以下问题改写为{num}个不同的表达方式，保持语义不变：

原问题：{pair.query}

要求：
1. 改写后的句子结构要有变化
2. 可以改变问法（是什么→什么叫→定义是等）
3. 保持专业性和清晰度

输出格式：
1. [改写1]
2. [改写2]
"""

        result = self._call_llm(prompt)
        variations = []

        # 解析结果
        for line in result.split("\n"):
            line = line.strip()
            if line and line[0].isdigit():
                # 提取改写
                new_query = re.sub(r"^\d+[.、)]\s*", "", line)
                variations.append(DistillationPair(
                    id=self._generate_id(),
                    query=new_query,
                    response=pair.response,
                    domain=pair.domain,
                    difficulty=pair.difficulty,
                    rationale=pair.rationale,
                    source="enriched",
                    metadata={"parent_id": pair.id, "strategy": "paraphrase"}
                ))

        return variations[:num]

    def _increase_difficulty(self, pair: DistillationPair, num: int) -> List[DistillationPair]:
        """增加难度"""
        prompt = f"""将以下问题改写为更深入、更复杂的形式：

原问题：{pair.query}

要求：
1. 添加专业术语
2. 增加复杂度（多维度、对比、综合分析等）
3. 要求更详细的分析

输出：改写后的问题"""

        result = self._call_llm(prompt)

        return [DistillationPair(
            id=self._generate_id(),
            query=result.strip(),
            response=pair.response,
            domain=pair.domain,
            difficulty="困难",
            rationale=pair.rationale,
            source="enriched",
            metadata={"parent_id": pair.id, "strategy": "difficulty_up"}
        )] * min(num, 1)

    def _decrease_difficulty(self, pair: DistillationPair, num: int) -> List[DistillationPair]:
        """降低难度"""
        prompt = f"""将以下问题改写为更简单、更易懂的形式：

原问题：{pair.query}

要求：
1. 使用更简单的词汇
2. 聚焦核心问题
3. 降低专业门槛

输出：改写后的问题"""

        result = self._call_llm(prompt)

        return [DistillationPair(
            id=self._generate_id(),
            query=result.strip(),
            response=pair.response,
            domain=pair.domain,
            difficulty="简单",
            rationale=pair.rationale,
            source="enriched",
            metadata={"parent_id": pair.id, "strategy": "difficulty_down"}
        )] * min(num, 1)

    def _expand_context(self, pair: DistillationPair, num: int) -> List[DistillationPair]:
        """扩展上下文"""
        variations = []

        for _ in range(min(num, 1)):
            variations.append(DistillationPair(
                id=self._generate_id(),
                query=f"假设在{pair.domain}领域，{pair.query}",
                response=pair.response,
                domain=pair.domain,
                difficulty=pair.difficulty,
                rationale=pair.rationale,
                source="enriched",
                metadata={"parent_id": pair.id, "strategy": "context_expand"}
            ))

        return variations

    def _generate_contrastive(self, pair: DistillationPair, num: int) -> List[DistillationPair]:
        """生成对比问答"""
        prompt = f"""为以下问题生成一个反面案例或错误观点：

问题：{pair.query}
回答：{pair.response}

要求：
1. 指出常见的错误理解
2. 对比正确vs错误的观点
3. 简短精炼

输出：错误观点的表述"""

        result = self._call_llm(prompt)

        return [DistillationPair(
            id=self._generate_id(),
            query=f"关于'{pair.query}'的常见误解是什么？",
            response=result.strip(),
            domain=pair.domain,
            difficulty=pair.difficulty,
            rationale="",
            source="enriched",
            metadata={"parent_id": pair.id, "strategy": "contrastive"}
        )] * min(num, 1)

    def filter_quality(self, pairs: List[DistillationPair]) -> List[DistillationPair]:
        """
        质量过滤

        过滤条件：
        1. 回答长度适中（50-2000字）
        2. 与问题相关度高
        3. 无明显重复模式
        """
        filtered = []

        for pair in pairs:
            # 长度检查
            if len(pair.response) < 50 or len(pair.response) > 2000:
                continue

            # 重复检查
            if self._has_repetition(pair.response):
                continue

            # 关键词匹配
            if not self._is_relevant(pair):
                continue

            filtered.append(pair)

        return filtered

    def _has_repetition(self, text: str) -> bool:
        """检查重复"""
        lines = text.split("\n")
        unique_lines = set(l.strip() for l in lines if l.strip())
        # 如果唯一行数少于总行数的一半，认为有重复
        return len(unique_lines) < len(lines) * 0.5

    def _is_relevant(self, pair: DistillationPair) -> bool:
        """检查相关性"""
        # 简单的关键词匹配
        query_words = set(pair.query)
        response_words = set(pair.response)
        overlap = len(query_words & response_words)

        # 基本要求：回答包含问句中的部分词
        return overlap >= 2

    def export(
        self,
        pairs: List[DistillationPair],
        filename: str,
        format: str = "jsonl"
    ) -> Path:
        """
        导出蒸馏数据

        Args:
            pairs: 问答对列表
            filename: 文件名
            format: 格式 (jsonl/llama_factory/sharegpt/json)

        Returns:
            输出路径
        """
        output_path = self.output_dir / filename

        with open(output_path, "w", encoding="utf-8") as f:
            for pair in pairs:
                if format == "llama_factory":
                    line = json.dumps(pair.to_llama_factory_format(), ensure_ascii=False)
                elif format == "sharegpt":
                    line = json.dumps(pair.to_sharegpt_format(), ensure_ascii=False)
                else:
                    line = json.dumps(pair.to_dict(), ensure_ascii=False)
                f.write(line + "\n")

        return output_path

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "output_dir": str(self.output_dir),
            "quality_threshold": self.quality_threshold
        }
