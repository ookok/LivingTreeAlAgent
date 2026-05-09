"""BioAbstractionLayer — separates biological metaphor from engineering code.

Design principle (from community review):
  "Keep 12 organs as architectural view, but code layer uses strict
   engineering naming: Perception/Storage/Reasoning/Execution/Safety."

This module provides a bidirectional mapping so that:
  - Internal code uses engineering names (safety, storage, perception)
  - External API/docs can reference biological names (immunity, blood, eyes)
  - New team members don't need to learn the metaphor to debug code
  - The metaphor remains accessible for demos and user-facing docs
"""

from __future__ import annotations

from typing import Any


# ═══ Bi-directional Mapping ═══

ORGAN_TO_ENGINEERING: dict[str, str] = {
    "eyes": "perception",
    "ears": "events",
    "brain": "consciousness",
    "heart": "proactive_loop",
    "lungs": "context_cache",
    "liver": "safety_filtering",       # note: merged into safety + cofee
    "blood": "resource_flow",
    "hands": "execution",
    "legs": "sandbox",
    "bones": "pipeline_framework",
    "immune": "safety_defense",
    "reproductive": "knowledge_export",
}

ENGINEERING_TO_ORGAN: dict[str, str] = {
    v: k for k, v in ORGAN_TO_ENGINEERING.items()}

# Friendly labels for UI
ORGAN_LABELS: dict[str, dict[str, str]] = {
    "eyes": {"icon": "👁️", "cn": "视觉", "en": "Perception"},
    "ears": {"icon": "👂", "cn": "听觉", "en": "Events"},
    "brain": {"icon": "🧠", "cn": "意识", "en": "Consciousness"},
    "heart": {"icon": "❤️", "cn": "节律", "en": "Proactive Loop"},
    "lungs": {"icon": "🫁", "cn": "缓存", "en": "Context Cache"},
    "liver": {"icon": "🫀", "cn": "过滤", "en": "Safety Filtering"},
    "blood": {"icon": "🩸", "cn": "资源", "en": "Resource Flow"},
    "hands": {"icon": "🤲", "cn": "执行", "en": "Execution"},
    "legs": {"icon": "🦵", "cn": "沙盒", "en": "Sandbox"},
    "bones": {"icon": "🦴", "cn": "框架", "en": "Pipeline"},
    "immune": {"icon": "🛡️", "cn": "防御", "en": "Defense"},
    "reproductive": {"icon": "🌱", "cn": "导出", "en": "Knowledge Export"},
}

# Legacy compatibility: module → organ mapping
MODULE_TO_ORGAN: dict[str, str] = {
    "om_weather": "eyes",
    "lazy_index": "eyes",
    "event_bus": "ears",
    "resource_tree": "ears",
    "phenomenal_consciousness": "brain",
    "godelian_self": "brain",
    "emergence_detector": "brain",
    "xiaoshu": "heart",
    "synaptic_plasticity": "brain",
    "safety": "immune",
    "cofee_engine": "liver",
    "economic_engine": "blood",
    "thermo_budget": "blood",
    "research_team": "hands",
    "gtsm_planner": "hands",
    "unified_pipeline": "bones",
    "action_principle": "bones",
    "hypergraph_store": "brain",
    "graph_introspector": "brain",
}


def organ_name(engineering_name: str) -> str:
    """Convert engineering name to organ name. e.g. 'safety' → 'immune'"""
    return ENGINEERING_TO_ORGAN.get(engineering_name, engineering_name)


def engineering_name(organ_name: str) -> str:
    """Convert organ name to engineering name. e.g. 'liver' → 'safety_filtering'"""
    return ORGAN_TO_ENGINEERING.get(organ_name, organ_name)


def organ_label(organ_name: str) -> dict[str, str]:
    """Get display label for an organ."""
    return ORGAN_LABELS.get(organ_name, {"icon": "❓", "cn": organ_name, "en": organ_name})


def module_organ(module_name: str) -> str:
    """Which organ does a module belong to?"""
    return MODULE_TO_ORGAN.get(module_name, "unknown")


def organ_report_to_display(organ_name: str, status: str, modules: list[str],
                            function: str) -> dict[str, Any]:
    """Build a display-friendly organ status report."""
    label = organ_label(organ_name)
    eng_name = engineering_name(organ_name)
    return {
        "icon": label["icon"],
        "name_cn": label["cn"],
        "name_en": label["en"],
        "engineering_name": eng_name,
        "status": status,
        "modules": modules,
        "function": function,
    }


__all__ = [
    "organ_name", "engineering_name", "organ_label",
    "module_organ", "organ_report_to_display",
    "ORGAN_TO_ENGINEERING", "ENGINEERING_TO_ORGAN",
    "ORGAN_LABELS", "MODULE_TO_ORGAN",
]
