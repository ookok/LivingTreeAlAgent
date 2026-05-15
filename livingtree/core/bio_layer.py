"""BioAbstractionLayer — biological metaphor display labels only.

Simplified: organ names are for display/demos only. All internal code uses
engineering names. No reverse mapping (ORGAN_TO_ENGINEERING) — single direction.

Design principle:
  - ENGINEERING_TO_ORGAN + ORGAN_LABELS = display helper, not routing middleware
  - No runtime side effects on TreeLLM routing decisions
"""

from __future__ import annotations

from typing import Any

# ═══ Display Labels ═══

ORGAN_LABELS: dict[str, dict[str, str]] = {
    "perception": {"icon": "👁️", "cn": "视觉", "en": "Perception"},
    "events": {"icon": "👂", "cn": "听觉", "en": "Events"},
    "consciousness": {"icon": "🧠", "cn": "意识", "en": "Consciousness"},
    "proactive_loop": {"icon": "❤️", "cn": "节律", "en": "Proactive Loop"},
    "context_cache": {"icon": "🫁", "cn": "缓存", "en": "Context Cache"},
    "safety_filtering": {"icon": "🫀", "cn": "过滤", "en": "Safety Filtering"},
    "resource_flow": {"icon": "🩸", "cn": "资源", "en": "Resource Flow"},
    "execution": {"icon": "🤲", "cn": "执行", "en": "Execution"},
    "sandbox": {"icon": "🦵", "cn": "沙盒", "en": "Sandbox"},
    "pipeline_framework": {"icon": "🦴", "cn": "框架", "en": "Pipeline"},
    "safety_defense": {"icon": "🛡️", "cn": "防御", "en": "Defense"},
    "knowledge_export": {"icon": "🌱", "cn": "导出", "en": "Knowledge Export"},
}

ENGINEERING_TO_ORGAN: dict[str, str] = {k: k for k in ORGAN_LABELS}


def organ_label(engineering_name: str) -> dict[str, str]:
    return ORGAN_LABELS.get(engineering_name, {"icon": "❓", "cn": engineering_name, "en": engineering_name})


def organ_report_to_display(eng_name: str, status: str, modules: list[str],
                            function: str) -> dict[str, Any]:
    label = organ_label(eng_name)
    return {
        "icon": label["icon"], "name_cn": label["cn"], "name_en": label["en"],
        "engineering_name": eng_name, "status": status,
        "modules": modules, "function": function,
    }


__all__ = ["organ_label", "organ_report_to_display", "ORGAN_LABELS", "ENGINEERING_TO_ORGAN"]
