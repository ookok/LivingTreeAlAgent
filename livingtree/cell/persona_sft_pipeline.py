"""PersonaSFTPipeline — auto-generate PersonaVLM-style SFT datasets.

PersonaVLM (CVPR 2026): 78k SFT samples for training persona extraction and
personalized response generation from conversation-persona pairs.

This pipeline auto-generates training data in 4 memory type templates:
  - Core Identity: name, role, self-description, key traits
  - Semantic Facts: domain knowledge, preferences, expertise
  - Episodic Memories: user experiences, projects, events
  - Procedural Habits: workflows, tool preferences, interaction patterns

Usage:
    pipeline = PersonaSFTPipeline()
    samples = pipeline.generate(user_id="user_123", conversations=[...])
    pipeline.export_jsonl(samples, "persona_sft_data.jsonl")
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

EXTRACTION_PROMPT = """从以下对话中提取用户的个性化信息，按4种记忆类型分类：

1. 核心身份 (Core Identity): 姓名、角色、自我描述
2. 语义事实 (Semantic Facts): 用户的专业知识、偏好、能力
3. 情景记忆 (Episodic): 用户的经历、项目、事件
4. 程序习惯 (Procedural Habits): 工作流程、工具偏好、交互模式

对话内容:
{conversation}

返回 JSON 格式:
{{"core_identity": {{"name": "", "role": "", "self_description": ""}},
 "semantic_facts": ["事实1", "事实2"],
 "episodic_memories": [{{"event": "", "context": "", "outcome": ""}}],
 "procedural_habits": ["习惯1", "习惯2"]}}
"""

RESPONSE_GEN_PROMPT = """根据以下用户画像生成个性化的回答:

用户画像:
{persona_context}

当前对话:
{current_conversation}

要求:
- 回答应符合用户的专业水平和技术深度
- 引用用户已知的偏好和习惯
- 保持用户喜欢的交流风格
"""


@dataclass
class PersonaSFTSample:
    sample_id: str
    instruction: str
    input_text: str
    output_text: str
    memory_type: str
    persona_facts: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.sample_id,
            "instruction": self.instruction,
            "input": self.input_text,
            "output": self.output_text,
            "memory_type": self.memory_type,
            "persona_facts": self.persona_facts,
        }


class PersonaSFTPipeline:
    """Auto-generate SFT datasets for PersonaVLM-style persona training."""

    MEMORY_TYPES = ["core_identity", "semantic_facts", "episodic_memories",
                    "procedural_habits"]

    def __init__(self):
        self._samples: list[PersonaSFTSample] = []
        self._counter = 1

    def generate(self, conversations: list[str],
                 user_id: str = "default",
                 existing_facts: dict[str, Any] = None) -> list[PersonaSFTSample]:
        combined = "\n".join(conversations[-20:])

        if existing_facts:
            persona_facts = existing_facts
        else:
            persona_facts = self._extract_persona_heuristic(combined)

        samples = []
        samples.extend(self._gen_core_identity_samples(combined, persona_facts))
        samples.extend(self._gen_semantic_fact_samples(combined, persona_facts))
        samples.extend(self._gen_episodic_samples(combined, persona_facts))
        samples.extend(self._gen_procedural_samples(combined, persona_facts))
        samples.extend(self._gen_response_alignment_samples(conversations, persona_facts))

        self._samples.extend(samples)
        logger.info(f"PersonaSFT: generated {len(samples)} samples for {user_id}")
        return samples

    def _gen_core_identity_samples(self, conv: str,
                                   facts: dict) -> list[PersonaSFTSample]:
        samples = []
        core = facts.get("core_identity", {})
        name = core.get("name", "")
        role = core.get("role", "")

        if name:
            samples.append(self._make_sample(
                "从对话中提取用户姓名",
                conv[:500],
                f"用户姓名: {name}",
                "core_identity", facts,
            ))

        if role:
            samples.append(self._make_sample(
                "从对话中提取用户的职业角色",
                conv[:500],
                f"用户角色: {role}",
                "core_identity", facts,
            ))

        return samples

    def _gen_semantic_fact_samples(self, conv: str,
                                   facts: dict) -> list[PersonaSFTSample]:
        samples = []
        sem_facts = facts.get("semantic_facts", [])
        for fact in sem_facts[:5]:
            samples.append(self._make_sample(
                "从对话中提取用户的偏好或知识",
                conv[:500],
                f"用户事实: {fact}",
                "semantic_facts", facts,
            ))
        return samples

    def _gen_episodic_samples(self, conv: str,
                              facts: dict) -> list[PersonaSFTSample]:
        samples = []
        episodes = facts.get("episodic_memories", [])
        for ep in episodes[:3]:
            if isinstance(ep, dict):
                event = ep.get("event", "")
            else:
                event = str(ep)
            samples.append(self._make_sample(
                "从对话中提取用户经历",
                conv[:500],
                f"用户经历: {event}",
                "episodic_memories", facts,
            ))
        return samples

    def _gen_procedural_samples(self, conv: str,
                                facts: dict) -> list[PersonaSFTSample]:
        samples = []
        habits = facts.get("procedural_habits", [])
        for habit in habits[:3]:
            samples.append(self._make_sample(
                "从对话中提取用户的工作习惯",
                conv[:500],
                f"用户习惯: {habit}",
                "procedural_habits", facts,
            ))
        return samples

    def _gen_response_alignment_samples(self, conversations: list[str],
                                        facts: dict) -> list[PersonaSFTSample]:
        samples = []
        if len(conversations) < 1:
            return samples

        latest = conversations[-1]
        persona_ctx = self._format_persona_context(facts)
        if not persona_ctx.strip():
            persona_ctx = "用户画像暂不明确"

        prompt = RESPONSE_GEN_PROMPT.format(
            persona_context=persona_ctx,
            current_conversation=latest[:800],
        )

        samples.append(self._make_sample(
            "根据用户画像生成个性化回答",
            latest[:500],
            prompt,
            "response_alignment", facts,
        ))
        return samples

    def _extract_persona_heuristic(self, text: str) -> dict[str, Any]:
        facts: dict[str, Any] = {
            "core_identity": {},
            "semantic_facts": [],
            "episodic_memories": [],
            "procedural_habits": [],
        }

        name_match = re.search(r"我(?:叫|是)\s*([\u4e00-\u9fff]{2,4})", text)
        if name_match:
            facts["core_identity"]["name"] = name_match.group(1)

        role_match = re.search(r"我是[一]?[个]?([\u4e00-\u9fff]{2,10}(?:工程师|设计师|分析师|开发者|经理))", text)
        if role_match:
            facts["core_identity"]["role"] = role_match.group(1)

        preference_matches = re.findall(r"(?:我喜欢|我偏好|我习惯)([\u4e00-\u9fff]{4,40})", text)
        facts["semantic_facts"].extend(p[:50] for p in preference_matches[:5])

        experience_matches = re.findall(r"(?:我做过|我参与过|我经历过|我曾经)([\u4e00-\u9fff]{4,60})", text)
        for exp in experience_matches[:3]:
            facts["episodic_memories"].append({"event": exp[:50], "context": "", "outcome": ""})

        tool_mentions = set()
        for tool in ["Git", "Docker", "PyCharm", "VSCode", "Vim", "终端", "命令行"]:
            if tool.lower() in text.lower():
                tool_mentions.add(tool)
        if tool_mentions:
            habits_text = f"偏好使用: {', '.join(sorted(tool_mentions))}"
            facts["procedural_habits"].append(habits_text)

        return facts

    def _make_sample(self, instruction: str, input_text: str,
                     output_text: str, memory_type: str,
                     facts: dict) -> PersonaSFTSample:
        sample_id = f"p_{self._counter:06d}_{memory_type}"
        self._counter += 1
        return PersonaSFTSample(
            sample_id=sample_id,
            instruction=instruction,
            input_text=input_text,
            output_text=output_text,
            memory_type=memory_type,
            persona_facts=facts,
        )

    @staticmethod
    def _format_persona_context(facts: dict) -> str:
        parts = []
        core = facts.get("core_identity", {})
        if core:
            items = [f"{k}: {v}" for k, v in core.items() if v]
            if items:
                parts.append("核心身份: " + ", ".join(items))

        sem = facts.get("semantic_facts", [])
        if sem:
            parts.append("语义事实: " + "; ".join(sem[:5]))

        episodes = facts.get("episodic_memories", [])
        if episodes:
            ep_texts = []
            for ep in episodes[:3]:
                if isinstance(ep, dict):
                    ep_texts.append(ep.get("event", ""))
                else:
                    ep_texts.append(str(ep))
            parts.append("经历: " + "; ".join(filter(None, ep_texts)))

        habits = facts.get("procedural_habits", [])
        if habits:
            parts.append("习惯: " + "; ".join(habits[:3]))

        return "\n".join(parts)

    def export_jsonl(self, samples: list[PersonaSFTSample],
                     path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            for s in samples:
                f.write(json.dumps(s.to_dict(), ensure_ascii=False) + "\n")
        logger.info(f"PersonaSFT: exported {len(samples)} samples to {path}")

    def stats(self) -> dict:
        by_type = {}
        for s in self._samples:
            by_type[s.memory_type] = by_type.get(s.memory_type, 0) + 1
        return {"total_samples": len(self._samples), "by_memory_type": by_type}


_persona_sft: PersonaSFTPipeline | None = None


def get_persona_sft_pipeline() -> PersonaSFTPipeline:
    global _persona_sft
    if _persona_sft is None:
        _persona_sft = PersonaSFTPipeline()
    return _persona_sft


__all__ = [
    "PersonaSFTPipeline", "PersonaSFTSample",
    "EXTRACTION_PROMPT", "RESPONSE_GEN_PROMPT",
    "get_persona_sft_pipeline",
]
