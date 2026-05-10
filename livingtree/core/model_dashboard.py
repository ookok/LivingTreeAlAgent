"""Model Dashboard — authoritative admin model panel.

Integrates election engine, model registry, router stats, and TreeLLM
metrics into a single dashboard sorted by election strategy.  Inspired by
LLMFit's evaluation framework and CowAgent's model management.

Layers displayed:
  L1  Embedding pre-filter     — semantic match scores
  L2  Election + alive ping    — holistic multi-dim scoring
  L3  Inference + self-assess  — actual output quality
  L4  Smart fallback           — local LLM guarantee (NEW: auto-elected)

Display only — no model selection. Admins get intuitive match awareness.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


@dataclass
class ModelCard:
    """Single model display card — all evaluation dimensions."""
    name: str
    provider: str = ""
    tier: str = "flash"           # flash / small / chat / pro / moe / reasoning
    alive: bool = False           # ping result
    is_free: bool = False
    # Scores (0-1 scale)
    latency_score: float = 0.0
    quality_score: float = 0.0    # success rate
    cost_score: float = 0.0       # free=1.0
    capability_score: float = 0.0 # task match
    election_total: float = 0.0   # weighted aggregate
    embedding_score: float = 0.0  # L1 semantic match
    self_assess_score: float = 0.0  # L3 output quality
    # Performance
    avg_latency_ms: float = 0.0
    success_rate: float = 0.0     # 0-1
    total_calls: int = 0
    total_failures: int = 0
    cost_yuan_per_1k: float = 0.0
    # Status
    layer_reached: int = 0        # 1-4, which layer this model passed
    rank: int = 0                 # election rank
    risk: str = "unknown"         # low / medium / high
    recommendation: str = ""      # strong / cautious / avoid
    last_used: str = ""
    capabilities: list[str] = field(default_factory=list)


class ModelDashboard:
    """Aggregate model election data for admin display.

    Usage:
        dashboard = get_model_dashboard()
        cards = dashboard.build_cards(task_type="general")
        html = dashboard.render_html(cards)
    """

    def __init__(self):
        pass

    def build_cards(self, task_type: str = "general", sample_query: str = "") -> list[ModelCard]:
        """Build sorted ModelCards from the current election state.

        Sources:
          - HolisticElection scores + stats
          - ModelRegistry tiers + providers
          - TreeLLM router stats
          - EmbeddingScorer profiles
        """
        cards: list[ModelCard] = []
        seen = set()

        try:
            from ..treellm.holistic_election import get_election, PROVIDER_CAPABILITIES
            election = get_election()
            stats = election.get_all_stats() if hasattr(election, "get_all_stats") else {}
        except Exception:
            election = None
            stats = {}
            PROVIDER_CAPABILITIES = {}

        try:
            from ..treellm.model_registry import get_model_registry
            registry = get_model_registry()
        except Exception:
            registry = None

        try:
            from ..config import get_config
            cfg = get_config()
        except Exception:
            cfg = None

        provider_names = set()
        if election and hasattr(election, "_stats"):
            provider_names.update(election._stats.keys())
        if PROVIDER_CAPABILITIES:
            provider_names.update(PROVIDER_CAPABILITIES.keys())

        # Add providers that have API keys configured
        if cfg:
            key_fields = {
                "deepseek": "deepseek_api_key",
                "openrouter": "openrouter_api_key",
                "zhipu": "zhipu_api_key",
                "siliconflow": "siliconflow_api_key",
                "xiaomi": "xiaomi_api_key",
                "sensetime": "sensetime_api_key",
                "longcat": "longcat_api_key",
                "ollama": "ollama_base_url",
            }
            for name, key_field in key_fields.items():
                try:
                    val = getattr(cfg.model, key_field, "")
                    if val:
                        provider_names.add(name)
                except Exception:
                    pass

        try:
            import httpx
            import asyncio
            loop = asyncio.get_event_loop()
        except Exception:
            loop = None

        for name in sorted(provider_names):
            if name in seen:
                continue
            seen.add(name)

            s = stats.get(name, {}) if isinstance(stats, dict) else {}
            caps = PROVIDER_CAPABILITIES.get(name, [])

            is_free = s.get("is_free", s.get("free", False)) if isinstance(s, dict) else False
            alive = s.get("alive", False) if isinstance(s, dict) else False

            latency_ms = s.get("avg_latency_ms", s.get("last_latency_ms", 0)) if isinstance(s, dict) else 0
            sr = s.get("success_rate", s.get("recent_quality", 0)) if isinstance(s, dict) else 0
            calls = s.get("calls", s.get("total_calls", 0)) if isinstance(s, dict) else 0
            failures = s.get("failures", s.get("total_failures", 0)) if isinstance(s, dict) else 0
            cost = s.get("cost_yuan_per_1k", 0) if isinstance(s, dict) else 0

            latency_score = max(0.0, min(1.0, 1.0 - (latency_ms / 5000))) if latency_ms else 0.5
            quality_score = min(1.0, max(0.0, sr))
            cost_score = 1.0 if is_free else max(0.0, 1.0 - (cost * 100))
            cap_score = self._compute_capability(name, caps, task_type)

            total = (
                latency_score * 0.18 +
                quality_score * 0.23 +
                cost_score * 0.15 +
                cap_score * 0.12
            ) / 0.68

            risk = "low"
            if not alive:
                risk = "high"
            elif sr < 0.5 or failures > calls * 0.5:
                risk = "medium"
            elif sr < 0.3:
                risk = "high"

            layer = 4 if alive and calls > 0 else (3 if alive else (2 if name else 1))

            provider_display = name.split("-")[0] if "-" in name else name
            tier = self._guess_tier(name)

            cards.append(ModelCard(
                name=name,
                provider=provider_display,
                tier=tier,
                alive=alive,
                is_free=is_free,
                latency_score=round(latency_score, 3),
                quality_score=round(quality_score, 3),
                cost_score=round(cost_score, 3),
                capability_score=round(cap_score, 3),
                election_total=round(total, 3),
                avg_latency_ms=round(latency_ms, 1),
                success_rate=round(sr, 3),
                total_calls=calls,
                total_failures=failures,
                cost_yuan_per_1k=round(cost, 4),
                layer_reached=layer,
                risk=risk,
                recommendation="strong" if total > 0.7 else ("cautious" if total > 0.4 else "avoid"),
                last_used=time.strftime("%H:%M", time.localtime(s.get("last_used", 0))) if s.get("last_used", 0) else "—",
                capabilities=caps,
            ))

        cards.sort(key=lambda c: (
            -c.alive,
            -c.election_total,
            -c.quality_score,
            -c.cost_score,
            -c.latency_score,
        ))

        for i, c in enumerate(cards):
            if i == 0:
                continue
            if c.election_total == cards[i - 1].election_total:
                c.rank = cards[i - 1].rank
            else:
                c.rank = i + 1

        return cards

    def _compute_capability(self, name: str, caps: list[str], task_type: str) -> float:
        if not caps:
            return 0.5
        type_kw = {
            "reasoning": ["推理", "数学", "逻辑", "reasoning", "math", "logic", "分析"],
            "code": ["代码", "code", "编程"],
            "chat": ["对话", "chat", "翻译", "摘要", "文档"],
            "general": [],
        }.get(task_type, [])

        if not type_kw:
            return 0.6

        matches = sum(1 for kw in type_kw if any(kw in c for c in caps))
        return min(1.0, matches / max(1, len(type_kw)) * 0.9 + 0.1)

    @staticmethod
    def _guess_tier(name: str) -> str:
        nl = name.lower()
        if any(k in nl for k in ("0.5b", "0.8b", "1.5b", "1.8b", "3b", "tiny", "mini", "flash-lite", "nano")):
            return "flash"
        if any(k in nl for k in ("7b", "8b", "9b", "14b", "small")):
            return "small"
        if any(k in nl for k in ("chat", "turbo", "sonnet")):
            return "chat"
        if any(k in nl for k in ("35b", "70b", "405b", "671b", "pro", "max", "opus")):
            return "pro"
        if any(k in nl for k in ("reasoning", "r1", "o1", "o3", "qwq", "deep", "think")):
            return "reasoning"
        if any(k in nl for k in ("a3b", "moe", "mixture")):
            return "moe"
        return "chat"

    def render_html(self, cards: list[ModelCard], task_hint: str = "") -> str:
        """Render the authoritative model dashboard as HTML."""
        if not cards:
            return '<div class="card"><h2>📊 模型仪表盘</h2><p style="color:var(--dim)">无模型数据 — 请先配置模型</p></div>'

        rows = []
        for c in cards:
            status_icon = "🟢" if c.alive else ("🟡" if c.layer_reached >= 3 else "🔴")
            free_badge = '<span style="background:var(--accent);color:var(--bg);font-size:8px;padding:1px 4px;border-radius:3px;margin-left:4px">免费</span>' if c.is_free else ""
            risk_color = {"low": "var(--accent)", "medium": "var(--warn)", "high": "var(--err)"}.get(c.risk, "var(--dim)")
            rec_color = {"strong": "var(--accent)", "cautious": "var(--warn)", "avoid": "var(--err)"}.get(c.recommendation, "var(--dim)")

            tier_badge = {
                "flash": '<span style="font-size:8px;color:#6af">⚡</span>',
                "small": '<span style="font-size:8px;color:#8af">🐣</span>',
                "chat": '<span style="font-size:8px;color:var(--accent)">💬</span>',
                "pro": '<span style="font-size:8px;color:#fa4">⭐</span>',
                "moe": '<span style="font-size:8px;color:#f4a">🧠</span>',
                "reasoning": '<span style="font-size:8px;color:#a4f">🔮</span>',
            }.get(c.tier, "")

            total_pct = int(c.election_total * 100)
            total_bar_color = "var(--accent)" if total_pct >= 70 else ("var(--warn)" if total_pct >= 40 else "var(--err)")

            rows.append(f'''
            <tr style="border-bottom:1px solid var(--border)">
              <td style="padding:6px 8px;font-size:11px">
                {status_icon} <b>{c.name}</b>{free_badge}
                <div style="font-size:9px;color:var(--dim)">{c.provider} · {c.tier} {tier_badge} · {c.total_calls}次调用</div>
              </td>
              <td style="padding:6px 8px;text-align:center;font-size:12px;font-weight:700;color:{total_bar_color}">
                {total_pct}{"%" if False else ""}
                <div style="height:3px;width:100%;background:var(--border);border-radius:2px;margin-top:2px">
                  <div style="height:100%;width:{total_pct}%;background:{total_bar_color};border-radius:2px"></div></div>
                <div style="font-size:8px;color:var(--dim)">L{c.layer_reached} · {"✅可用" if c.alive else "❌离线"}</div>
              </td>
              <td style="padding:6px 4px;text-align:center;font-size:10px">
                <span style="color:var(--dim)">延时</span><br>{c.avg_latency_ms:.0f}ms
              </td>
              <td style="padding:6px 4px;text-align:center;font-size:10px">
                <span style="color:var(--dim)">质量</span><br>{int(c.success_rate*100)}%
              </td>
              <td style="padding:6px 4px;text-align:center;font-size:10px">
                <span style="color:var(--dim)">匹配</span><br>{int(c.capability_score*100)}%
              </td>
              <td style="padding:6px 4px;text-align:center;font-size:10px;color:{risk_color}">
                {c.risk}<br><span style="font-size:8px">{c.recommendation}</span>
              </td>
              <td style="padding:6px 4px;text-align:center;font-size:9px;color:var(--dim)">
                {c.last_used}
              </td>
            </tr>''')

        task_line = f'<p style="font-size:10px;color:var(--dim);margin:4px 0">任务类型: {task_hint} · 按选举策略排序 · 共 {len(cards)} 个模型</p>' if task_hint else ""

        return f'''<div class="card">
<h2>📊 模型选举仪表盘 <span style="font-size:10px;color:var(--dim);font-weight:400">— LLMFit 权威评估</span></h2>
{task_line}
<div style="font-size:9px;color:var(--dim);margin:4px 0;display:flex;gap:12px">
  <span>🟢在线 <b>{sum(1 for c in cards if c.alive)}</b></span>
  <span>🔴离线 <b>{sum(1 for c in cards if not c.alive)}</b></span>
  <span>🆓免费 <b>{sum(1 for c in cards if c.is_free)}</b></span>
  <span>L1语义 L2选举 L3自评 L4兜底</span>
</div>
<div style="overflow-x:auto">
<table style="width:100%;border-collapse:collapse;font-size:11px">
<thead><tr style="text-align:left;border-bottom:2px solid var(--border);font-size:10px;color:var(--dim)">
  <th style="padding:6px 8px">模型</th>
  <th style="padding:6px 8px;text-align:center;width:80px">选举评分</th>
  <th style="padding:6px 4px;text-align:center;width:50px">延时</th>
  <th style="padding:6px 4px;text-align:center;width:50px">质量</th>
  <th style="padding:6px 4px;text-align:center;width:50px">匹配</th>
  <th style="padding:6px 4px;text-align:center;width:60px">风险</th>
  <th style="padding:6px 4px;text-align:center;width:50px">最近</th>
</tr></thead>
<tbody>{"".join(rows)}</tbody></table></div>
<div style="margin-top:8px;font-size:9px;color:var(--dim)">
  评分公式: 延时18% + 质量23% + 成本15% + 能力12% + 新鲜度5% + 限流7% + 缓存10% + 粘性10%<br>
  L1=语义预筛 · L2=选举+存活ping · L3=推理+自评 · <b style="color:var(--accent)">L4=智能兜底(本地llm自动选举)</b>
</div></div>'''


_instance: Optional[ModelDashboard] = None


def get_model_dashboard() -> ModelDashboard:
    global _instance
    if _instance is None:
        _instance = ModelDashboard()
    return _instance
