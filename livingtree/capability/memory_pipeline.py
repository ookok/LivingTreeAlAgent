"""Memory-Driven Pipeline — StructMem suggests optimized pipelines for repeated tasks.

When StructMem detects that similar tasks have been performed multiple times,
it analyzes the historical patterns and suggests an optimized pipeline
configuration. Pipelines evolve as more data accumulates — filters that
were frequently removed get dropped, glean steps that improve results get
more iterations.

Usage:
    mp = MemoryPipeline(struct_memory, conversation_dna)
    
    # Auto-called when intent recognition detects domain:
    suggestion = await mp.suggest(intent, domain)
    
    # Track pipeline performance for evolution:
    mp.record_result(pipeline_config, success_rate)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class PipelineTemplate:
    name: str
    domain: str
    steps: list[dict]
    success_rates: list[float] = field(default_factory=list)
    usage_count: int = 0
    avg_tokens: int = 0
    evolution_generation: int = 0

    def avg_success(self) -> float:
        return sum(self.success_rates) / max(len(self.success_rates), 1)

    def should_evolve(self) -> bool:
        if self.usage_count < 5:
            return False
        if self.avg_success() < 0.6:
            return True
        return False

    def evolve(self) -> dict:
        self.evolution_generation += 1

        if self.steps and self.steps[0].get("op") == "extract":
            if self.avg_success() > 0.85 and len(self.steps) > 2:
                for s in self.steps:
                    if s.get("op") == "glean":
                        s["params"] = s.get("params", {})
                        s["params"]["max_iterations"] = s["params"].get("max_iterations", 1) + 1

            if self.avg_success() < 0.6 and len(self.steps) > 3:
                to_remove = [s for s in self.steps if s.get("op") in ("sort",)]
                self.steps = [s for s in self.steps if s not in to_remove]

        return {
            "generation": self.evolution_generation,
            "steps_after": len(self.steps),
            "avg_success": self.avg_success(),
        }

    def to_dict(self) -> dict:
        return {
            "name": self.name, "domain": self.domain, "steps": self.steps,
            "usage_count": self.usage_count, "avg_success": self.avg_success(),
            "avg_tokens": self.avg_tokens, "generation": self.evolution_generation,
        }


class MemoryPipeline:

    MERGE_SIMILARITY = 0.6

    def __init__(self, struct_memory: Any = None, conversation_dna: Any = None):
        self._struct_mem = struct_memory
        self._dna = conversation_dna
        self._templates: dict[str, PipelineTemplate] = {}

    async def suggest(self, intent: str, domain: str = "") -> dict:
        if self._dna:
            dna_suggestion = self._dna.suggest(intent, domain)
            if dna_suggestion.get("found"):
                return {
                    **dna_suggestion,
                    "source": "conversation_dna",
                    "template_name": f"{domain}_pipeline",
                }

        if self._struct_mem:
            try:
                entries, synthesis = await self._struct_mem.retrieve_for_query(intent)
                if synthesis:
                    pipeline_hints = [s.content for s in synthesis[:3] if "pipeline" in s.content.lower() or "extract" in s.content.lower()]
                    if pipeline_hints:
                        return {
                            "found": True,
                            "source": "struct_mem",
                            "domain": domain,
                            "hints": pipeline_hints,
                            "message": "Found related pipeline patterns in memory",
                        }
            except Exception as e:
                logger.debug(f"Memory pipeline suggest: {e}")

        return {"found": False, "message": "No pipeline patterns found"}

    def record_result(self, pipeline_config: dict, success_rate: float, tokens: int = 0) -> PipelineTemplate:
        name = pipeline_config.get("name", "unknown")
        domain = pipeline_config.get("domain", "general")

        if name not in self._templates:
            self._templates[name] = PipelineTemplate(
                name=name,
                domain=domain,
                steps=pipeline_config.get("steps", []),
            )

        template = self._templates[name]
        template.success_rates.append(success_rate)
        template.usage_count += 1
        template.avg_tokens = (template.avg_tokens * (template.usage_count - 1) + tokens) // template.usage_count

        if template.should_evolve():
            evolved = template.evolve()
            logger.info(f"Pipeline {name} evolved to gen {evolved['generation']} ({len(template.steps)} steps)")

        return template

    def get_best_template(self, domain: str = "") -> PipelineTemplate | None:
        candidates = [t for t in self._templates.values() if not domain or t.domain == domain]
        if not candidates:
            return None
        return max(candidates, key=lambda t: t.avg_success() * t.usage_count)

    def get_stats(self) -> dict:
        return {
            "templates": len(self._templates),
            "total_usage": sum(t.usage_count for t in self._templates.values()),
            "evolved": sum(1 for t in self._templates.values() if t.evolution_generation > 0),
            "templates_detail": [t.to_dict() for t in self._templates.values()],
        }
