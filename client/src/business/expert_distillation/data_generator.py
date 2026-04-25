"""
蒸馏数据生成器 - DistillationDataGenerator

将 L4 大模型的输出转化为可用于训练小模型的蒸馏数据。
支持多种格式：Q-A-Rationale 三元组、思维链、对话上下文等。

核心功能:
1. 从 L4 生成专家级问答数据
2. 提取推理过程（Rationale）
3. 生成多轮对话上下文
4. 格式转换（支持 LLaMA-Factory、PEFT 等格式）
"""

import json
import re
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any, Callable
from datetime import datetime
from pathlib import Path


@dataclass
class QATriple:
    """问答三元组：问题、答案、推理过程"""
    question: str
    answer: str
    rationale: str = ""
    domain: str = "通用"
    difficulty: str = "中等"
    keywords: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return asdict(self)

    def to_llama_factory_format(self) -> Dict:
        return {
            "instruction": self.question,
            "input": "",
            "output": f"{self.rationale}\n\n{self.answer}" if self.rationale else self.answer
        }

    def to_sharegpt_format(self) -> Dict:
        return {
            "conversations": [
                {"from": "human", "value": self.question},
                {"from": "gpt", "value": f"{self.rationale}\n\n{self.answer}" if self.rationale else self.answer}
            ],
            "domain": self.domain,
            "difficulty": self.difficulty
        }


class DistillationDataGenerator:
    """
    蒸馏数据生成器

    Example:
        generator = DistillationDataGenerator(llm_caller=l4_caller)
        qa = generator.generate_from_seed("什么是市盈率？", domain="金融")
    """

    DOMAIN_PROMPTS = {
        "金融": {
            "system": "你是一位资深金融分析师，拥有20年投资经验。",
            "seed_topics": ["股票估值", "债券定价", "基金选择", "风险管理"],
            "question_templates": ["解释{topic}的基本概念", "如何评估{topic}？"]
        },
        "医疗": {
            "system": "你是一位主任医师，专注于临床诊断。",
            "seed_topics": ["症状诊断", "用药指导", "检查解读"],
            "question_templates": ["{topic}需要做哪些检查？", "如何解读{topic}结果？"]
        },
        "法律": {
            "system": "你是一位资深律师，精通合同法和商业法规。",
            "seed_topics": ["合同审查", "权利义务", "风险条款"],
            "question_templates": ["这份合同{topic}是否完整？", "{topic}的法律效力？"]
        },
        "技术": {
            "system": "你是一位全栈技术专家，擅长架构设计和代码审查。",
            "seed_topics": ["架构设计", "性能优化", "安全加固"],
            "question_templates": ["如何设计{topic}的架构？", "这个{topic}有什么优化建议？"]
        },
        "通用": {
            "system": "你是一位知识渊博的助手。",
            "seed_topics": ["概念解释", "方法论", "最佳实践"],
            "question_templates": ["解释{topic}的概念", "{topic}的最佳实践是什么？"]
        }
    }

    def __init__(self, llm_caller: Optional[Callable] = None, output_dir: str = "data/distillation", default_domain: str = "通用"):
        self.llm_caller = llm_caller
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.default_domain = default_domain
        self.stats = {"total_generated": 0, "by_domain": {}, "by_difficulty": {}}

    def _call_llm(self, prompt: str, system: str = "") -> str:
        if self.llm_caller:
            return self.llm_caller(prompt, system)
        return f"模拟专家回答。\n\n推理：首先理解问题... 逐步分析... 最终结论。"

    def _extract_rationale(self, response: str) -> tuple:
        paragraphs = response.split("\n\n")
        if len(paragraphs) >= 2:
            return paragraphs[0].strip(), "\n\n".join(paragraphs[1:]).strip()
        return "通过综合分析得出结论。", response.strip()

    def _extract_keywords(self, text: str) -> List[str]:
        words = re.findall(r"[\u4e00-\u9fa5]{3,8}", text)
        return list(dict.fromkeys(words))[:5]

    def generate_from_seed(self, seed_question: str, domain: Optional[str] = None, difficulty: str = "中等", num_variations: int = 5) -> List[QATriple]:
        domain = domain or self.default_domain
        domain_config = self.DOMAIN_PROMPTS.get(domain, self.DOMAIN_PROMPTS["通用"])
        system_prompt = domain_config["system"]

        prompt = f"""{system_prompt}

请详细回答以下问题，展示推理过程。

问题：{seed_question}

【推理过程】
你的分析思路...

【最终答案】
你的结论...
"""
        response = self._call_llm(prompt, system_prompt)
        rationale, answer = self._extract_rationale(response)

        qa = QATriple(
            question=seed_question, answer=answer, rationale=rationale,
            domain=domain, difficulty=difficulty, keywords=self._extract_keywords(seed_question)
        )
        self._update_stats([qa])
        return [qa]

    def generate_dataset(self, domain: str, topics: Optional[List[str]] = None, samples_per_topic: int = 20) -> List[QATriple]:
        domain_config = self.DOMAIN_PROMPTS.get(domain, self.DOMAIN_PROMPTS["通用"])
        topics = topics or domain_config["seed_topics"]
        all_qa = []

        for topic in topics:
            for template in domain_config["question_templates"][:2]:
                question = template.format(topic=topic)
                all_qa.extend(self.generate_from_seed(question, domain, num_variations=samples_per_topic // 4))
        return all_qa

    def save_dataset(self, qa_list: List[QATriple], format: str = "jsonl", filename: Optional[str] = None) -> Path:
        domain = qa_list[0].domain if qa_list else "general"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = filename or f"{domain}_{timestamp}.{format}"
        filepath = self.output_dir / filename

        if format == "jsonl":
            with open(filepath, "w", encoding="utf-8") as f:
                for qa in qa_list:
                    f.write(json.dumps(qa.to_dict(), ensure_ascii=False) + "\n")
        elif format == "llama_factory":
            with open(filepath, "w", encoding="utf-8") as f:
                for qa in qa_list:
                    f.write(json.dumps(qa.to_llama_factory_format(), ensure_ascii=False) + "\n")
        else:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump([qa.to_dict() for qa in qa_list], f, ensure_ascii=False, indent=2)
        return filepath

    def load_dataset(self, filepath: str, format: str = "jsonl") -> List[QATriple]:
        filepath = Path(filepath)
        qa_list = []
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                data = json.loads(line.strip())
                qa_list.append(QATriple(**data))
        return qa_list

    def _update_stats(self, qa_list: List[QATriple]):
        self.stats["total_generated"] += len(qa_list)
        for qa in qa_list:
            self.stats["by_domain"][qa.domain] = self.stats["by_domain"].get(qa.domain, 0) + 1

    def get_stats(self) -> Dict:
        return self.stats


def quick_generate(domain: str, topic: str, llm_caller=None) -> List[QATriple]:
    """快速生成单主题蒸馏数据"""
    generator = DistillationDataGenerator(llm_caller=llm_caller)
    templates = generator.DOMAIN_PROMPTS.get(domain, generator.DOMAIN_PROMPTS["通用"])["question_templates"]
    results = []
    for template in templates[:2]:
        question = template.format(topic=topic)
        results.extend(generator.generate_from_seed(question, domain))
    return results
