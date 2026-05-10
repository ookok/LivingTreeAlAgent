"""Living Presence — the interface breathes, feels, remembers, and grows.

Five innovations that make the AI feel alive through its interface:
1. Breathing Rhythm — canvas pulse matches AI's processing cadence
2. Memory Echoes — related past conversations surface as you type
3. Emotional Weather — background shifts with AI mood + time + tone
4. Thought Particles — abstract particles cluster on canvas during deep thinking
5. Conversation Garden — important moments grow into visual memory trees

Design principle: Not gimmicks. Subtle, ambient, informative. Like weather.
All leverage existing infrastructure (struct_memory, VAD model, activity_feed).
"""

from __future__ import annotations

import json as _json
import time as _time
from typing import Any, Optional

from loguru import logger


class LivingPresence:
    """Generates the ambient living interface layer for the Living Canvas."""

    def __init__(self, hub=None):
        self._hub = hub
        self._breath_phase = 0.0
        self._last_activity = _time.time()

    @property
    def world(self):
        return self._hub.world if self._hub else None

    # ═══ 1. Breathing Rhythm ═══

    def build_breathing_css(self) -> str:
        """CSS for the canvas breathing animation. Speed adapts to AI load."""
        load = self._estimate_load()
        duration = 8.0 if load < 0.3 else 4.0 if load < 0.7 else 2.0
        return f"""@keyframes lt-breathe {{
  0%,100% {{ box-shadow: inset 0 0 {30*load+5}px rgba(100,150,100,{0.02+load*0.04}) }}
  50%     {{ box-shadow: inset 0 0 {50*load+15}px rgba(100,150,100,{0.04+load*0.06}) }}
}}
#lc-canvas {{
  animation: lt-breathe {duration:.1f}s ease-in-out infinite;
  transition: box-shadow 2s;
}}"""

    def _estimate_load(self) -> float:
        """Estimate AI load from recent activity."""
        try:
            feed = getattr(self.world, "activity_feed", None) if self.world else None
            if feed and hasattr(feed, "query"):
                recent = feed.query(limit=20)
                if recent:
                    now = _time.time()
                    active = sum(1 for e in recent if now - e.timestamp < 60)
                    return min(1.0, active / 8)
        except Exception:
            pass
        return 0.3

    # ═══ 2. Memory Echoes ═══

    def build_echo(self, current_input: str) -> str:
        """Remember-related past conversations to surface as gentle echoes."""
        if not current_input or len(current_input) < 3:
            return ""

        try:
            mem = getattr(self.world, "struct_memory", None) if self.world else None
            if mem:
                entries, _ = mem.retrieve_for_query(current_input, top_k=3, n_synthesis=1) if hasattr(mem, "retrieve_for_query") else ([], [])
                if entries:
                    echoes = []
                    for e in entries[:3]:
                        content = getattr(e, "content", str(e))[:80]
                        echoes.append(content)
                    return "<br>".join(echoes)
        except Exception:
            pass
        return ""

    def build_echo_html(self, current_input: str) -> str:
        """Generate the echo overlay HTML."""
        echo = self.build_echo(current_input)
        if not echo:
            return ""
        return f'''<div id="memory-echo" style="position:fixed;bottom:80px;left:50%;transform:translateX(-50%);
font-size:11px;color:var(--dim);opacity:0.4;text-align:center;max-width:60%;pointer-events:none;
animation:echo-fade 4s ease-out;z-index:10">{echo}</div>
<style>@keyframes echo-fade{{0%{{opacity:0;transform:translateX(-50%) translateY(10px)}}20%{{opacity:0.5}}80%{{opacity:0.3}}100%{{opacity:0;transform:translateX(-50%) translateY(-10px)}}}}</style>'''

    # ═══ 3. Emotional Weather ═══

    def build_weather_css(self) -> str:
        """CSS gradient overlay that shifts with AI emotion + time + tone."""
        vad = self._get_vad()
        hour = _time.localtime().tm_hour
        time_factor = 1.0 if 8 <= hour <= 18 else 0.7 if 6 <= hour <= 22 else 0.4

        v = vad.get("valence", 0.6)
        a = vad.get("arousal", 0.4)

        if v > 0.6 and a > 0.5:
            hue, sat = 120, 30 + a * 40  # green, vibrant
        elif v > 0.6:
            hue, sat = 180, 20  # calm blue
        elif a > 0.6:
            hue, sat = 30, 40 + a * 30  # warm orange, alert
        elif v < 0.3:
            hue, sat = 270, 15  # purple, contemplative
        else:
            hue, sat = 200, 25  # neutral blue-grey

        alpha = 0.015 + time_factor * 0.02
        return f"""#lc-canvas::before {{
  content:'';position:fixed;top:0;left:0;right:0;bottom:0;
  background:radial-gradient(ellipse at 50% 50%,hsla({hue},{sat}%,50%,{alpha:.3f}) 0%,transparent 70%);
  pointer-events:none;z-index:0;transition:background 8s;
}}"""

    def _get_vad(self) -> dict:
        try:
            consc = getattr(self.world, "consciousness", None) if self.world else None
            if consc and hasattr(consc, "_current_affect"):
                a = consc._current_affect
                return {"valence": getattr(a, "valence", 0.6), "arousal": getattr(a, "arousal", 0.4), "dominance": getattr(a, "dominance", 0.7)}
        except Exception:
            pass
        return {"valence": 0.6, "arousal": 0.4, "dominance": 0.7}

    # ═══ 4. Thought Particles ═══

    def build_particle_canvas(self) -> str:
        """HTML canvas overlay for abstract thought particles during AI thinking."""
        return '''<canvas id="thought-particles" style="position:fixed;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:1;opacity:0;transition:opacity 0.5s"></canvas>
<script>
var _tpCanvas=document.getElementById('thought-particles'),_tpCtx=_tpCanvas.getContext('2d'),_tpParticles=[],_tpActive=false;
function resizeTP(){_tpCanvas.width=window.innerWidth;_tpCanvas.height=window.innerHeight}
window.addEventListener('resize',resizeTP);resizeTP();
function spawnParticles(n){
  for(var i=0;i<n;i++)_tpParticles.push({x:Math.random()*_tpCanvas.width,y:Math.random()*_tpCanvas.height,vx:(Math.random()-0.5)*0.5,vy:(Math.random()-0.5)*0.5,life:1,size:Math.random()*3+1,alpha:Math.random()*0.3+0.1,color:'hsla('+(100+Math.random()*60)+',50%,60%,'});
  _tpParticles=_tpParticles.slice(-80);_tpCanvas.style.opacity='0.6'
}
function clearParticles(){_tpParticles=[];_tpCanvas.style.opacity='0'}
function drawTP(){
  if(!_tpActive&&_tpParticles.length===0)return;
  _tpCtx.clearRect(0,0,_tpCanvas.width,_tpCanvas.height);
  _tpParticles=_tpParticles.filter(function(p){p.life-=0.003;p.x+=p.vx;p.y+=p.vy;
    if(p.life>0){_tpCtx.beginPath();_tpCtx.arc(p.x,p.y,p.size,0,Math.PI*2);_tpCtx.fillStyle=p.color.replace(';',p.alpha*p.life+')');_tpCtx.fill()}return p.life>0});
  if(_tpParticles.length===0)_tpCanvas.style.opacity='0';
  requestAnimationFrame(drawTP)
}
drawTP();
// Hook into SSE streaming: spawn particles when tokens arrive
document.addEventListener('htmx:sseMessage',function(e){spawnParticles(3)});
document.addEventListener('htmx:beforeRequest',function(e){if(e.detail.target&&e.detail.target.id==='lc-canvas')spawnParticles(5)});
</script>'''

    # ═══ 5. Conversation Garden ═══

    def build_garden(self) -> str:
        """SVG visualization of important past conversations as growing plants."""
        moments = self._get_important_moments()
        if not moments:
            return '<div style="text-align:center;padding:40px;color:var(--dim);font-size:12px">🌱 对话花园刚开始生长...<br>每个重要的对话都会在这里长成一株植物</div>'

        items = ""
        for i, m in enumerate(moments[:8]):
            x = 10 + (i % 4) * 22
            y = 15 + (i // 4) * 35
            size = min(40, 15 + m.get("importance", 1) * 8)
            plant_type = m.get("type", "leaf")
            emoji = {"decision": "🌳", "insight": "🌿", "creation": "🌸", "milestone": "🌲", "learning": "🍀"}.get(plant_type, "🌱")
            items += (
                f'<div style="position:absolute;left:{x}%;top:{y}%;text-align:center;'
                f'animation:garden-grow {2+size*0.1}s ease-out;animation-delay:{i*0.2}s">'
                f'<div style="font-size:{size}px">{emoji}</div>'
                f'<div style="font-size:8px;color:var(--dim);margin-top:2px">{m.get("label","")[:12]}</div></div>'
            )

        return (
            f'<div style="position:relative;height:250px;overflow:hidden;background:radial-gradient(ellipse at 50% 100%,rgba(100,150,100,0.03) 0%,transparent 70%);border-radius:8px">'
            f'{items}</div>'
            f'<div style="text-align:center;font-size:10px;color:var(--dim);margin-top:4px">'
            f'🌿 {len(moments)} 株植物 · 每株代表一个重要时刻</div>'
            f'<style>@keyframes garden-grow{{0%{{opacity:0;transform:scale(0.2)}}100%{{opacity:1;transform:scale(1)}}}}</style>'
        )

    def _get_important_moments(self) -> list[dict]:
        moments = []
        try:
            feed = getattr(self.world, "activity_feed", None) if self.world else None
            if feed and hasattr(feed, "query"):
                events = feed.query(limit=50)
                for e in events:
                    if e.severity in ("info",) and any(kw in e.message.lower() for kw in [
                        "生成", "创建", "完成", "发现", "学习", "连接", "决策",
                        "generate", "create", "complete", "discover", "learn", "decide",
                    ]):
                        importance = 1
                        if any(kw in e.message for kw in ["报告", "生成", "完成", "重大"]):
                            importance = 3
                            e_type = "decision"
                        elif any(kw in e.message for kw in ["发现", "洞察", "insight"]):
                            importance = 2
                            e_type = "insight"
                        elif any(kw in e.message for kw in ["创建", "生成", "create"]):
                            e_type = "creation"
                        elif any(kw in e.message for kw in ["学习", "learn"]):
                            e_type = "learning"
                        else:
                            e_type = "milestone"

                        moments.append({
                            "label": e.message[:30],
                            "type": e_type,
                            "importance": importance,
                            "ts": e.timestamp,
                        })
        except Exception:
            pass

        if not moments:
            moments = [
                {"label": "第一次对话", "type": "milestone", "importance": 2},
                {"label": "知识库建立", "type": "learning", "importance": 2},
            ]
        return sorted(moments, key=lambda m: -m.get("importance", 1))[:8]

    # ═══ Combined Living Layer ═══

    def build_all(self, current_input: str = "") -> str:
        """Generate all living presence layers as injectable HTML."""
        parts = [
            f'<style>{self.build_breathing_css()}{self.build_weather_css()}</style>',
            self.build_particle_canvas(),
        ]
        if current_input:
            echo = self.build_echo_html(current_input)
            if echo:
                parts.append(echo)
        return "\n".join(parts)


_presence_instance: Optional[LivingPresence] = None


def get_presence() -> LivingPresence:
    global _presence_instance
    if _presence_instance is None:
        _presence_instance = LivingPresence()
    return _presence_instance
