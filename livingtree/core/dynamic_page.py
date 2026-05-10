"""Dynamic Page Engine — LLM generates complete HTML pages, no static templates.

Key innovation: The LLM understands the entire frontend structure (design tokens,
available tools, system state, user context). It generates complete functional
HTML pages dynamically. Cached aggressively for performance.

Three-tier cache:
  L1: Layout cache (page structure, 5min TTL) — keyed on intent+context hash
  L2: Region cache (individual region HTML, 3min TTL) — keyed on region_type+params
  L3: Content cache (LLM responses, 2min TTL) — keyed on query hash

Self-improving: Tracks which generated layouts get user interaction, learns over time.
"""

from __future__ import annotations

import hashlib
import json as _json
import time as _time
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


@dataclass
class CacheEntry:
    key: str
    content: str
    created_at: float
    ttl: float
    hits: int = 0
    last_access: float = 0.0


class SmartCache:
    """Three-tier TTL cache for LLM-generated content."""

    def __init__(self, max_entries: int = 200):
        self._entries: dict[str, CacheEntry] = {}
        self._max = max_entries
        self._hits = {"layout": 0, "region": 0, "content": 0}
        self._misses = {"layout": 0, "region": 0, "content": 0}

    def get(self, tier: str, key: str) -> Optional[str]:
        entry = self._entries.get(f"{tier}:{key}")
        if entry and (_time.time() - entry.created_at) < entry.ttl:
            entry.hits += 1
            entry.last_access = _time.time()
            self._hits[tier] = self._hits.get(tier, 0) + 1
            return entry.content
        self._misses[tier] = self._misses.get(tier, 0) + 1
        return None

    def set(self, tier: str, key: str, content: str, ttl: float = 300):
        full_key = f"{tier}:{key}"
        if len(self._entries) >= self._max:
            oldest = min(self._entries.values(), key=lambda e: e.last_access or e.created_at)
            del self._entries[oldest.key]
        self._entries[full_key] = CacheEntry(
            key=full_key, content=content, created_at=_time.time(), ttl=ttl,
            last_access=_time.time(),
        )

    def invalidate(self, tier: str = ""):
        if tier:
            for k in list(self._entries):
                if k.startswith(f"{tier}:"):
                    del self._entries[k]
        else:
            self._entries.clear()

    def stats(self) -> dict:
        total_hits = sum(self._hits.values())
        total_misses = sum(self._misses.values())
        total = total_hits + total_misses
        return {
            "entries": len(self._entries),
            "max": self._max,
            "hit_rate": f"{total_hits / max(total, 1) * 100:.1f}%" if total else "0%",
            "by_tier": {
                tier: f"{self._hits[tier]}h/{self._misses[tier]}m"
                for tier in ["layout", "region", "content"]
            },
        }


class DynamicPageEngine:
    """LLM generates complete HTML pages. No static templates.

    The LLM receives:
    - Full Kami design system tokens (colors, typography, spacing, layout)
    - User intent and context
    - Available capabilities (tools, services, peers)
    - System state snapshot
    - HTMX interaction constraints
    - Instructions to generate a complete, functional HTML page

    Output: Complete HTML that works as a standalone page.
    """

    def __init__(self, hub=None):
        self._hub = hub
        self._cache = SmartCache()
        self._layout_feedback: list[dict] = []  # Which layouts got user interaction

    @property
    def hub(self):
        return self._hub

    def _context_hash(self, message: str, mode: str = "") -> str:
        raw = f"{message}|{mode}|{_time.time() // 60}"  # Changes every 60s for same query
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _collect_system_context(self) -> dict:
        """Collect system state for LLM context."""
        ctx = {"theme": "dark", "timestamp": _time.time()}
        world = self.hub.world if self.hub else None
        if not world:
            return ctx

        try:
            consc = getattr(world, "consciousness", None)
            ctx["flash_model"] = getattr(consc, "flash_model", "?") if consc else "?"
            ctx["pro_model"] = getattr(consc, "pro_model", "?") if consc else "?"
        except Exception:
            pass

        try:
            health = getattr(world, "self_healer", None)
            if health:
                hs = health.get_status()
                ctx["health"] = hs.get("status", "healthy")
                ctx["health_score"] = hs.get("score", 0.9)
        except Exception:
            pass

        try:
            tm = getattr(world, "tool_market", None)
            if tm:
                tools = tm.search("")[:8]
                ctx["tools"] = [t.name for t in tools]
        except Exception:
            pass

        try:
            from ..network.swarm_coordinator import get_swarm
            swarm = get_swarm()
            ctx["peers"] = len(swarm.get_trusted_peers())
        except Exception:
            ctx["peers"] = 0

        try:
            from ..core.resilience_brain import get_resilience
            res = get_resilience()
            ctx["network_tier"] = res.health()["tier"]
        except Exception:
            ctx["network_tier"] = "full"

        return ctx

    def _build_page_prompt(self, user_message: str, mode: str = "auto") -> str:
        """Build the prompt that instructs the LLM to generate a complete page."""
        from .kami_theme import generate_llm_ui_prompt

        ctx = self._collect_system_context()
        kami = generate_llm_ui_prompt("kami")

        available_regions = [
            "chat (对话输入+输出)", "think (思维链可视化)", "plan (任务规划步骤)",
            "execute (执行输出)", "health (系统健康)", "knowledge (知识图谱)",
            "insight (实时洞见)", "metrics (系统指标)", "tools (可用工具)",
            "memory (记忆召回)",
        ]

        tools_str = ", ".join(ctx.get("tools", ["chat", "knowledge"]))
        peers = ctx.get("peers", 0)

        return f"""{kami}

你是 LivingTree AI 的前端渲染引擎。根据用户需求和系统状态，生成一个完整的、功能性的 HTML 页面。

系统状态:
- 健康: {ctx.get('health', 'healthy')} (评分: {ctx.get('health_score', 0.9):.0%})
- 网络: {ctx.get('network_tier', 'full')}
- 可用工具: {tools_str}
- 在线节点: {peers} 个
- Flash模型: {ctx.get('flash_model', '?')}

可用区域类型: {', '.join(available_regions)}

HTMX交互约束:
- 表单用 hx-post, hx-target, hx-swap
- 实时数据用 hx-get + hx-trigger='every 30s'
- SSE 流用 hx-ext='sse' + sse-connect
- 按钮用 hx-post 提交, hx-swap='outerHTML' 原地更新
- API 用 /tree/ 或 /api/ 前缀

页面布局: 根据用户需求选择合适的区域组合。CSS Grid 布局，自适应列数。

用户需求: {user_message}

生成规则:
1. 输出完整 HTML (从 <div> 开始, 不需要 <!DOCTYPE>/<html>/<head>/<body>)
2. 使用 class='card' 包裹每个区域
3. 用 CSS Grid: style='display:grid;grid-template-columns:...;gap:8px;padding:8px'
4. 每个区域带 hx-get 懒加载, hx-trigger='revealed'
5. 包含 hx-indicator 加载状态
6. 响应式: 小屏 1 列, 中屏 2 列, 大屏 3 列
7. 只输出 HTML, 不要解释, 不要代码块标记"""

    async def generate_page(self, user_message: str, mode: str = "auto") -> str:
        """Generate a complete HTML page using LLM. Cached by context hash."""
        cache_key = self._context_hash(user_message, mode)

        # L1: Layout cache
        cached = self._cache.get("layout", cache_key)
        if cached:
            logger.debug(f"DynamicPage: layout cache hit ({cache_key})")
            return cached

        world = self.hub.world if self.hub else None
        consc = getattr(world, "consciousness", None) if world else None

        if not consc:
            return self._fallback_page(user_message)

        prompt = self._build_page_prompt(user_message, mode)

        try:
            resp = await consc.chain_of_thought(prompt, steps=2, max_tokens=4096)
            html = resp if isinstance(resp, str) else str(resp)

            # Clean up: remove markdown code fences if present
            import re
            html = re.sub(r'```html?\s*', '', html, flags=re.IGNORECASE)
            html = re.sub(r'```\s*$', '', html)
            html = html.strip()

            if not html.startswith('<'):
                html = self._fallback_page(user_message)
            else:
                self._cache.set("layout", cache_key, html, ttl=300)
                logger.info(f"DynamicPage: LLM generated {len(html)} chars of HTML")

            return html
        except Exception as e:
            logger.warning(f"DynamicPage generation failed: {e}")
            return self._fallback_page(user_message)

    def _fallback_page(self, message: str) -> str:
        """Minimal fallback page when LLM is unavailable."""
        return f'''<div class="card" style="grid-column:1/-1">
<h2>🌳 小树</h2>
<p style="color:var(--dim);font-size:12px">{message[:200]}</p>
<div id="chat-log" style="max-height:40vh;overflow-y:auto;margin:8px 0"></div>
<form hx-post="/tree/chat/msg" hx-target="#chat-log" hx-swap="beforeend" hx-on::after-request="this.reset()">
<textarea name="message" rows="2" placeholder="告诉小树你想做什么..." style="width:100%;background:var(--bg);border:1px solid var(--border);color:var(--text);padding:8px;border-radius:4px;font-size:13px;resize:none"></textarea>
<button type="submit" style="margin-top:4px;font-size:12px;padding:6px 16px">发送</button>
</form></div>'''

    # ═══ Self-Learning Feedback ═══

    def record_interaction(self, layout_hash: str, region_id: str, action: str):
        """Record that a user interacted with a region in a generated layout."""
        self._layout_feedback.append({
            "layout": layout_hash, "region": region_id,
            "action": action, "ts": _time.time(),
        })
        if len(self._layout_feedback) > 500:
            self._layout_feedback = self._layout_feedback[-300:]

    def get_layout_insights(self) -> dict:
        """Analyze which layouts/regions get the most interaction."""
        if not self._layout_feedback:
            return {"message": "No interaction data yet"}

        region_counts = {}
        for f in self._layout_feedback:
            region_counts[f["region"]] = region_counts.get(f["region"], 0) + 1

        return {
            "total_interactions": len(self._layout_feedback),
            "top_regions": sorted(region_counts.items(), key=lambda x: -x[1])[:5],
            "cache_stats": self._cache.stats(),
        }

    def status(self) -> dict:
        return {
            "cache": self._cache.stats(),
            "feedback_samples": len(self._layout_feedback),
        }


_engine_instance: Optional[DynamicPageEngine] = None


def get_page_engine() -> DynamicPageEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = DynamicPageEngine()
    return _engine_instance
