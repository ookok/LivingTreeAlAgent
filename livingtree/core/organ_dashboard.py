"""Organ Layer Dashboard — QGIS Layer Panel for LivingTree's 12 organs.

Visual layer tree showing each organ's:
  - Active / Dormant / Healthy / Degraded status
  - Sub-modules with real-time metrics
  - Data flow direction between organs
  - Expand/collapse tree nodes
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from loguru import logger


class OrganStatus(str, Enum):
    ACTIVE = "active"       # running, healthy
    IDLE = "idle"           # running, no current activity
    DEGRADED = "degraded"   # running, but reduced performance
    DORMANT = "dormant"     # not running
    ERROR = "error"         # failed


ORGAN_DEFINITIONS = [
    {"id": "eyes", "name": "👁️ 视觉", "modules": ["modern_ocr", "doc_layout", "om_weather"], "layer": 1,
     "description": "OCR识别 · 文档分析 · 天气感知", "flow_to": ["brain"]},
    {"id": "ears", "name": "👂 听觉", "modules": ["event_bus", "mcp_discovery", "resource_tree"], "layer": 2,
     "description": "事件总线 · MCP工具发现 · 资源搜索", "flow_to": ["brain"]},
    {"id": "brain", "name": "🧠 意识", "modules": ["phenomenal_consciousness", "godelian_self", "emergence_detector", "predictability_engine"], "layer": 3,
     "description": "现象意识 · 哥德尔自指 · 涌现检测 · 可预测性", "flow_to": ["heart", "hands"]},
    {"id": "heart", "name": "❤️ 心脏", "modules": ["xiaoshu", "life_engine", "launch"], "layer": 4,
     "description": "自主生长守护 · 内在驱动力", "flow_to": ["lungs", "blood"]},
    {"id": "lungs", "name": "🫁 呼吸", "modules": ["kv_cache", "lazy_index", "context_budget"], "layer": 5,
     "description": "KV缓存 · 懒索引 · Token预算", "flow_to": ["brain"]},
    {"id": "liver", "name": "🫀 肝脏", "modules": ["safety", "cofee_engine", "quality_guard"], "layer": 6,
     "description": "安全守卫 · CoFEE验证 · 质量防护", "flow_to": ["hands"]},
    {"id": "blood", "name": "🩸 血液", "modules": ["economic_engine", "thermo_budget", "spatial_reward"], "layer": 7,
     "description": "经济编排 · 热力学预算 · Token流", "flow_to": ["hands", "legs"]},
    {"id": "hands", "name": "🤲 双手", "modules": ["research_team", "code_crafter", "tool_market"], "layer": 8,
     "description": "研究员团队 · 代码工匠 · 工具市场", "flow_to": ["legs"]},
    {"id": "legs", "name": "🦵 双腿", "modules": ["sandbox_executor", "ssh_authorizer", "docker_deploy"], "layer": 9,
     "description": "沙盒执行 · SSH授权 · Docker部署", "flow_to": []},
    {"id": "bones", "name": "🦴 骨骼", "modules": ["pipeline_orchestrator", "gtsm_planner", "unified_pipeline"], "layer": 10,
     "description": "流水线编排 · GTSM规划 · 统一管道", "flow_to": ["brain", "hands"]},
    {"id": "immune", "name": "🛡️ 免疫", "modules": ["safety_policy", "hallucination_guard", "injection_detect"], "layer": 11,
     "description": "安全策略 · 幻觉守卫 · 注入检测", "flow_to": ["brain", "liver"]},
    {"id": "reproductive", "name": "🌱 生殖", "modules": ["cell_mitosis", "knowledge_seed", "offspring_birth"], "layer": 12,
     "description": "细胞分裂 · 知识种子 · 后代诞生", "flow_to": []},
]


class OrganDashboard:
    """QGIS Layer Panel for the 12-organ system."""

    def __init__(self):
        self._organs: dict[str, dict] = {}
        for org in ORGAN_DEFINITIONS:
            self._organs[org["id"]] = {**org, "status": OrganStatus.IDLE.value, "metrics": {}}

    def update_status(self, organ_id: str, status: OrganStatus, metrics: dict = None):
        if organ_id in self._organs:
            self._organs[organ_id]["status"] = status.value
            if metrics:
                self._organs[organ_id]["metrics"] = metrics

    def get_organ(self, organ_id: str) -> dict:
        return self._organs.get(organ_id, {})

    def refresh_from_health(self):
        """Sync status from SystemHealth monitor."""
        try:
            from .system_health import get_system_health
            health = get_system_health()
            stats = health.stats()
            hstatus = stats.get("last_status", "healthy")

            status_map = {
                "healthy": OrganStatus.ACTIVE,
                "degraded": OrganStatus.DEGRADED,
                "critical": OrganStatus.ERROR,
            }
            default_status = status_map.get(hstatus, OrganStatus.IDLE)

            for oid in self._organs:
                self._organs[oid]["status"] = default_status.value
        except Exception:
            pass

    def render_html(self) -> str:
        """Render the 12-organ layer tree as HTML."""
        self.refresh_from_health()

        layers = []
        for org in ORGAN_DEFINITIONS:
            oid = org["id"]
            state = self._organs.get(oid, {})
            status = state.get("status", "idle")
            metrics = state.get("metrics", {})

            status_color = {"active": "var(--accent)", "idle": "var(--dim)", "degraded": "var(--warn)", "dormant": "#555", "error": "var(--err)"}.get(status, "var(--dim)")
            status_icon = {"active": "🟢", "idle": "⚪", "degraded": "🟡", "dormant": "⏸", "error": "🔴"}.get(status, "⚪")

            modules_html = ""
            for mod in org["modules"]:
                mod_status = "🟢" if status == "active" else ("🟡" if status == "degraded" else "⚪")
                metric_val = metrics.get(mod, "")
                metric_display = f'<span style="font-size:8px;color:var(--dim);margin-left:4px">{metric_val}</span>' if metric_val else ""
                modules_html += f'<div style="font-size:9px;padding:1px 0 1px 16px;color:var(--dim)">{mod_status} {mod}{metric_display}</div>'

            flow_to = org.get("flow_to", [])
            flow_display = " → ".join(f'<span style="color:var(--accent)">{f}</span>' for f in flow_to) if flow_to else ""

            layers.append(f'''
            <div style="margin:2px 0;padding:4px 8px;border-left:3px solid {status_color};background:rgba(255,255,255,.01)">
              <div style="display:flex;justify-content:space-between;align-items:center">
                <span style="font-size:12px;color:{status_color}">{status_icon} <b>{org["name"]}</b></span>
                <span style="font-size:9px;color:var(--dim)">{status}</span>
              </div>
              <div style="font-size:9px;color:var(--dim);margin:2px 0">{org["description"]}</div>
              {modules_html}
              <div style="font-size:8px;color:var(--dim);margin-top:2px">流出: {flow_display or "—"}</div>
            </div>''')

        active_count = sum(1 for o in self._organs.values() if o["status"] == "active")
        degraded_count = sum(1 for o in self._organs.values() if o["status"] == "degraded")

        return f'''<div class="card">
<h2>🫀 器官层面板 <span style="font-size:10px;color:var(--dim);font-weight:400">— QGIS Layer Tree 风格</span></h2>
<div style="font-size:9px;color:var(--dim);margin:4px 0;display:flex;gap:12px">
  <span>活跃 <b style="color:var(--accent)">{active_count}</b></span>
  <span>退化 <b style="color:var(--warn)">{degraded_count}</b></span>
  <span>休眠 <b style="color:var(--dim)">{12 - active_count - degraded_count}</b></span>
  <span>🟢活跃 · 🟡退化 · ⚪空闲 · 🔴故障</span>
</div>
<div style="max-height:500px;overflow-y:auto">
{"".join(layers)}
</div>
<div style="font-size:9px;color:var(--dim);margin-top:8px;text-align:center">
  12器官系统 — 每个器官独立模块, 数据流可视化 · refresh_from_health 自动同步</div>
</div>'''


_instance: Optional[OrganDashboard] = None


def get_organ_dashboard() -> OrganDashboard:
    global _instance
    if _instance is None:
        _instance = OrganDashboard()
    return _instance
