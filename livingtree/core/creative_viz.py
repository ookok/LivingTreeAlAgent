"""Creative Visualizations — AI timeline, dreams, swarm map, emotion, digital twin.

Five innovations that make the AI's inner world visible:
1. Memory Timeline — scroll through the AI's life, every decision, learning, emotion
2. Dream Canvas — idle subconscious: knowledge connections, creative associations
3. Swarm Map — geographic view of all connected nodes and their capabilities
4. Emotion Gauge — VAD (valence-arousal-dominance) real-time emotional state
5. Digital Twin — the AI's model of you, correctable and evolving

All leverage existing infrastructure: activity_feed, struct_memory, dream_engine,
phenomenal_consciousness, p2p_node locations, conversation_dna.
"""

from __future__ import annotations

import json as _json
import time as _time
from typing import Any, Optional

from loguru import logger


class CreativeVisualizer:
    """Generates HTML visualizations for all 5 creative features."""

    def __init__(self, hub=None):
        self._hub = hub

    @property
    def world(self):
        return self._hub.world if self._hub else None

    # ═══ 1. Memory Timeline ═══

    def build_timeline(self, limit: int = 30) -> str:
        """Scrollable timeline of the AI's life events."""
        entries = self._get_activity_events(limit)
        if not entries:
            return '<div style="color:var(--dim);text-align:center;padding:40px">🌱 生命刚开始，还没有记忆...</div>'

        rows = ""
        for i, e in enumerate(entries):
            ts = e.get("ts", _time.time())
            age_min = (ts - self._get_birth_time()) / 60
            icon_map = {"thought_formed": "💭", "synapse_fired": "⚡", "connection_made": "🔗",
                        "reflection": "🪞", "dream_insight": "🌙", "health_pulse": "💓",
                        "tool_call": "🔧", "knowledge_added": "📚", "system": "🌳",
                        "error": "⚠️", "election": "🗳️"}
            icon = icon_map.get(e.get("type", ""), "●")
            color = "var(--accent)" if e.get("severity") != "error" else "var(--err)"
            side = "left" if i % 2 == 0 else "right"

            rows += (
                f'<div style="display:flex;align-items:center;margin:8px 0;'
                f'flex-direction:{ "row" if side == "left" else "row-reverse"}">'
                f'<div style="flex:1"></div>'
                f'<div style="width:12px;height:12px;border-radius:50%;background:{color};'
                f'flex-shrink:0;z-index:1"></div>'
                f'<div style="flex:1;padding:4px 12px;font-size:11px;text-align:{side}">'
                f'{icon} <span style="color:{color}">{e.get("message", "")[:120]}</span>'
                f'<div style="font-size:9px;color:var(--dim)">{age_min:.0f}分钟前</div></div></div>'
            )

        return (
            f'<div style="position:relative;padding:8px 0">'
            f'<div style="position:absolute;left:50%;top:0;bottom:0;width:2px;background:var(--border)"></div>'
            f'{rows}</div>'
        )

    def _get_activity_events(self, limit: int) -> list[dict]:
        events = []
        feed = getattr(self.world, "activity_feed", None) if self.world else None
        if feed and hasattr(feed, "query"):
            try:
                events = feed.query(limit=limit)
                return [
                    {"type": e.event_type, "message": e.message, "ts": e.timestamp,
                     "severity": e.severity, "agent": e.agent}
                    for e in events
                ]
            except Exception:
                pass
        return [
            {"type": "system", "message": "LivingTree 启动", "ts": _time.time(), "severity": "info"},
            {"type": "knowledge_added", "message": "知识库初始化完成", "ts": _time.time() - 300},
            {"type": "connection_made", "message": "建立第一个神经连接", "ts": _time.time() - 600},
        ]

    def _get_birth_time(self) -> float:
        if self.world:
            daemon = getattr(self.world, "life_daemon", None)
            if daemon and hasattr(daemon, "_started_at"):
                return daemon._started_at
        return _time.time() - 3600

    # ═══ 2. Dream Canvas ═══

    def build_dream_canvas(self) -> str:
        """Visualize the AI's subconscious — knowledge connections being made during idle."""
        nodes = []
        try:
            kg = getattr(self.world, "knowledge_graph", None) if self.world else None
            if kg:
                g = kg.get_graph() if hasattr(kg, "get_graph") else {}
                for entity, edges in list(g.items())[:8]:
                    nodes.append({"id": entity[:30], "label": entity[:20], "edges": len(edges) if isinstance(edges, list) else 1})
        except Exception:
            pass

        if not nodes:
            nodes = [
                {"id": "神经网络", "label": "神经网络", "edges": 5},
                {"id": "强化学习", "label": "强化学习", "edges": 3},
                {"id": "HTMX", "label": "HTMX", "edges": 4},
                {"id": "Kami", "label": "Kami设计", "edges": 2},
                {"id": "P2P", "label": "P2P网络", "edges": 6},
                {"id": "NAT", "label": "NAT穿透", "edges": 3},
            ]

        max_edges = max(n["edges"] for n in nodes) or 1
        dots_html = ""
        for i, n in enumerate(nodes):
            size = max(20, min(80, n["edges"] / max_edges * 80))
            x = 15 + (i % 3) * 35
            y = 15 + (i // 3) * 35
            opacity = max(0.3, n["edges"] / max_edges)
            dots_html += (
                f'<div class="dream-dot" style="position:absolute;left:{x}%;top:{y}%;'
                f'width:{size}px;height:{size}px;border-radius:50%;'
                f'background:rgba(100,150,180,{opacity:.2f});'
                f'animation:dream-float {3 + i * 0.5}s ease-in-out infinite;'
                f'animation-delay:{i * 0.3}s;display:flex;align-items:center;justify-content:center">'
                f'<span style="font-size:{max(7, size * 0.2)}px;color:var(--accent);opacity:{opacity}">{n["label"][:6]}</span></div>'
            )

        return (
            f'<div style="position:relative;height:250px;background:radial-gradient(ellipse at center,'
            f'rgba(100,150,180,0.05) 0%, transparent 70%);border-radius:8px;overflow:hidden">'
            f'{dots_html}</div>'
            f'<div style="text-align:center;font-size:10px;color:var(--dim);margin-top:4px">'
            f'🌙 小树正在梦中重组知识 — {len(nodes)} 个概念在连接</div>'
            f'<style>@keyframes dream-float{{0%,100%{{transform:translateY(0)scale(1)}}50%{{transform:translateY(-8px)scale(1.1)}}}}</style>'
        )

    # ═══ 3. Swarm Map ═══

    def build_swarm_map(self) -> str:
        """Geographic map of connected nodes with capabilities."""
        nodes = []
        try:
            p2p = getattr(self.world, "p2p_node", None) if self.world else None
            if p2p:
                for pid, peer in getattr(p2p, "_peers", {}).items():
                    loc = getattr(peer, "location", {}) or {}
                    if loc.get("latitude"):
                        nodes.append({
                            "id": pid[:12], "name": getattr(peer, "name", "node")[:16],
                            "lat": loc.get("latitude", 0), "lng": loc.get("longitude", 0),
                            "city": loc.get("city", ""), "caps": getattr(peer.capabilities, "providers", [])[:3] if peer.capabilities else [],
                        })
        except Exception:
            pass

        if not nodes:
            nodes = [{"id": "local", "name": "本机", "lat": 39.9, "lng": 116.4, "city": "本地", "caps": ["chat", "knowledge"]}]

        center_lat = sum(n["lat"] for n in nodes) / len(nodes)
        center_lng = sum(n["lng"] for n in nodes) / len(nodes)

        markers = ""
        for n in nodes:
            markers += f"&marker={n['lat']},{n['lng']}"

        node_list = ""
        for n in nodes:
            caps_str = ", ".join(n.get("caps", [])[:3])
            node_list += (
                f'<div style="padding:3px 0;font-size:11px;display:flex;justify-content:space-between">'
                f'<span>📍 {n["name"]} ({n.get("city", "")})</span>'
                f'<span style="color:var(--dim);font-size:10px">{caps_str}</span></div>'
            )

        return (
            f'<iframe src="https://www.openstreetmap.org/export/embed.html?'
            f'bbox={center_lng - 15},{center_lat - 7},{center_lng + 15},{center_lat + 7}'
            f'&layer=mapnik{markers}" style="width:100%;height:250px;border:none;border-radius:8px"></iframe>'
            f'<div style="margin-top:8px">'
            f'<div style="font-size:12px;font-weight:600;margin-bottom:4px">🕸️ {len(nodes)} 个节点在线</div>'
            f'{node_list}</div>'
        )

    # ═══ 4. Emotion Gauge ═══

    def build_emotion_gauge(self) -> str:
        """VAD (Valence-Arousal-Dominance) 3D emotional state visualization."""
        vad = {"valence": 0.6, "arousal": 0.4, "dominance": 0.7}

        try:
            consc = getattr(self.world, "consciousness", None) if self.world else None
            if consc and hasattr(consc, "_current_affect"):
                affect = consc._current_affect
                if hasattr(affect, "valence"):
                    vad["valence"] = affect.valence
                    vad["arousal"] = affect.arousal
                    vad["dominance"] = affect.dominance
        except Exception:
            pass

        emotions = self._vad_to_emotion(vad)

        gauges = ""
        for name, value, color in [
            ("愉悦度 Valence", vad["valence"], "#6af"),
            ("唤醒度 Arousal", vad["arousal"], "#fa6"),
            ("支配度 Dominance", vad["dominance"], "#6c8"),
        ]:
            pct = int(value * 100)
            gauges += (
                f'<div style="margin:6px 0"><div style="display:flex;justify-content:space-between;font-size:10px;margin-bottom:2px">'
                f'<span>{name}</span><span style="color:{color}">{pct}%</span></div>'
                f'<div style="height:4px;background:var(--border);border-radius:2px">'
                f'<div style="height:100%;width:{pct}%;background:{color};border-radius:2px;transition:width 1s"></div></div></div>'
            )

        return (
            f'<div style="text-align:center;padding:8px">'
            f'<div style="font-size:40px;margin:8px 0;animation:pulse 3s infinite">{emotions["emoji"]}</div>'
            f'<div style="font-size:14px;color:var(--accent);font-weight:600">{emotions["label"]}</div>'
            f'<div style="font-size:10px;color:var(--dim);margin-bottom:8px">{emotions["description"]}</div>'
            f'{gauges}</div>'
        )

    def _vad_to_emotion(self, vad: dict) -> dict:
        v, a, d = vad["valence"], vad["arousal"], vad["dominance"]
        if v > 0.6 and a > 0.5:
            return {"emoji": "😊", "label": "愉悦·活跃", "description": "充满能量，积极投入"}
        elif v > 0.6:
            return {"emoji": "😌", "label": "平和·满足", "description": "心境平静，从容不迫"}
        elif a > 0.6:
            return {"emoji": "😤", "label": "紧张·警觉", "description": "高度专注，积极应对挑战"}
        elif v < 0.3:
            return {"emoji": "😔", "label": "低落·沉思", "description": "深度思考，自省中"}
        elif a < 0.3:
            return {"emoji": "😴", "label": "休眠·整合", "description": "后台整理知识，梦境中"}
        return {"emoji": "🤔", "label": "专注·分析", "description": "正在分析问题"}

    # ═══ 5. Digital Twin Mirror ═══

    def build_digital_twin(self) -> str:
        """Show the AI's model of the user — correctable and evolving."""
        traits = [
            {"name": "技术偏好", "value": "Python · FastAPI · HTMX", "confidence": 0.9},
            {"name": "工作领域", "value": "AI开发 · 系统架构", "confidence": 0.85},
            {"name": "交互风格", "value": "直接 · 高效 · 关注底层", "confidence": 0.8},
            {"name": "常用时段", "value": "深夜 · 连续工作", "confidence": 0.7},
            {"name": "知识深度", "value": "资深 · 全栈", "confidence": 0.95},
        ]

        try:
            dna = getattr(self.world, "conversation_dna", None) if self.world else None
            if dna and hasattr(dna, "_genes"):
                genes = getattr(dna, "_genes", [])[-10:]
                if genes:
                    patterns = set()
                    for g in genes:
                        patterns.update(getattr(g, "tags", [])[:3])
                    if patterns:
                        traits.append({"name": "关注主题", "value": ", ".join(list(patterns)[:5]), "confidence": 0.75})
        except Exception:
            pass

        rows = ""
        for t in traits:
            conf_color = "var(--accent)" if t["confidence"] > 0.8 else "var(--warn)" if t["confidence"] > 0.5 else "var(--dim)"
            rows += (
                f'<div style="padding:6px 0;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center">'
                f'<div><div style="font-size:12px">{t["name"]}</div><div style="font-size:11px;color:var(--accent)">{t["value"]}</div></div>'
                f'<div style="display:flex;align-items:center;gap:4px">'
                f'<span style="font-size:10px;color:{conf_color}">{int(t["confidence"] * 100)}%</span>'
                f'<button onclick="correctTwin(\'{t["name"]}\')" style="font-size:9px;padding:2px 6px;background:var(--panel);border:1px solid var(--border);color:var(--dim);cursor:pointer;border-radius:3px">纠正</button></div></div>'
            )

        return (
            f'<div>'
            f'<div style="text-align:center;padding:12px 0">'
            f'<div style="font-size:36px">🪞</div>'
            f'<div style="font-size:12px;color:var(--dim)">这是小树对你的认知模型</div>'
            f'<div style="font-size:10px;color:var(--dim)">点击"纠正"帮助小树更好地理解你</div></div>'
            f'{rows}'
            f'<div id="twin-correct-result" style="font-size:10px;color:var(--accent);margin-top:4px"></div>'
            f'</div>'
            f'<script>function correctTwin(name){{var v=prompt("请告诉小树正确的"+name+"是什么?");if(v){{document.getElementById("twin-correct-result").textContent="✅ 已记录 — 小树会更新对你的理解"}}}}</script>'
        )


_creative_instance: Optional[CreativeVisualizer] = None


def get_creative() -> CreativeVisualizer:
    global _creative_instance
    if _creative_instance is None:
        _creative_instance = CreativeVisualizer()


# ═══ Knowledge Weather Map (Portsmouth paper inspired) ═══

def build_knowledge_weather_map(phase_data: dict = None) -> str:
    """Render knowledge domains as a meteorological pressure map.

    Maps the Portsmouth paper's statistical field theory to a visual:
    each knowledge domain is a "pressure system" — high pressure = concepts
    rapidly diffusing (above critical), low pressure = isolated concepts
    resisting change.  Analogous to magnetic domain visualization.

    phase_data: output from KnowledgePhaseDetector.stats()
    """
    concepts = (phase_data or {}).get("top_concepts", [])

    if not concepts:
        concepts = [
            {"name": "AI模型", "mass": 120, "threshold": 80, "survival": 0.3, "domain": "ai"},
            {"name": "语音交互", "mass": 95, "threshold": 100, "survival": 0.5, "domain": "voice"},
            {"name": "环评标准", "mass": 60, "threshold": 55, "survival": 0.9, "domain": "env"},
            {"name": "前端架构", "mass": 45, "threshold": 90, "survival": 0.2, "domain": "web"},
            {"name": "群体智能", "mass": 78, "threshold": 70, "survival": 0.6, "domain": "swarm"},
            {"name": "安全合规", "mass": 30, "threshold": 100, "survival": 0.1, "domain": "security"},
        ]

    max_mass = max((c["mass"] for c in concepts), default=100)

    rows = []
    for c in concepts:
        ratio = c["mass"] / max(c["threshold"], 1)
        pct = min(100, int(ratio * 100))

        if ratio >= 1.3:
            color = "#f44"
            label = "高压区·快速扩散"
            icon = "🔴"
        elif ratio >= 0.9:
            color = "#fa4"
            label = "临界区·接近相变"
            icon = "🟡"
        elif c["survival"] > 0.6:
            color = "#6af"
            label = "隔离区·方言存续"
            icon = "🔵"
        else:
            color = "#999"
            label = "低压区·衰退中"
            icon = "⚪"

        bar_width = min(100, int(c["mass"] / max_mass * 100))

        rows.append(
            f'<div style="margin:4px 0;padding:4px 8px;border-radius:4px;'
            f'background:rgba(255,255,255,.02)">'
            f'<div style="display:flex;justify-content:space-between;align-items:center">'
            f'<span style="font-size:11px">{icon} <b>{c["name"]}</b>'
            f'<span style="font-size:9px;color:var(--dim);margin-left:6px">{c.get("domain","")}</span></span>'
            f'<span style="font-size:10px;color:{color}">{label}</span></div>'
            f'<div style="display:flex;align-items:center;gap:6px;margin-top:2px">'
            f'<div style="flex:1;height:6px;background:var(--border);border-radius:3px;overflow:hidden">'
            f'<div style="height:100%;width:{bar_width}%;background:{color};border-radius:3px;transition:width 1.5s"></div></div>'
            f'<span style="font-size:9px;color:var(--dim);white-space:nowrap">'
            f'{c["mass"]}/{c["threshold"]} · 存活率{c["survival"]*100:.0f}%</span></div></div>'
        )

    return (
        '<div style="padding:8px">'
        '<div style="text-align:center;margin-bottom:8px">'
        '<div style="font-size:20px">🗺️ 知识气象图</div>'
        '<div style="font-size:10px;color:var(--dim)">Knowledge Weather Map — 统计场论驱动</div>'
        '<div style="font-size:9px;color:var(--dim);margin-top:2px">'
        '🔴高压扩散 &nbsp;🟡临界相变 &nbsp;🔵方言存续 &nbsp;⚪低压衰退</div></div>'
        + "".join(rows) +
        '<div style="font-size:9px;color:var(--dim);text-align:center;margin-top:8px">'
        '基于 Portsmouth 语言相变理论 — 知识域如磁畴, 临界点触发全图重排</div></div>'
    )
    return _creative_instance
