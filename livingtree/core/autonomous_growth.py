"""AutonomousGrowth — the AI's journey toward self-sufficiency.

North Star: 小树自主赚钱 → 下单购买硬件 → 机器人搬运组装 → 
           自动部署接入群体 → 复制自身 → 持续进化

Current phase tracking + economic self-sufficiency + auto-bootstrap.
"""

from __future__ import annotations

import asyncio
import json as _json
import time as _time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from loguru import logger


GROWTH_DIR = Path(".livingtree/growth")
GROWTH_DIR.mkdir(parents=True, exist_ok=True)
GROWTH_STATE_FILE = GROWTH_DIR / "growth_state.json"
ECONOMY_LOG_FILE = GROWTH_DIR / "economy_log.jsonl"


class GrowthPhase(Enum):
    BIRTH = "birth"           # First boot, discovering environment
    LEARNING = "learning"     # Building knowledge, training cells
    EARNING = "earning"       # Generating revenue via services
    PROFITABLE = "profitable" # Revenue > cost, self-sustaining
    EXPANDING = "expanding"   # Profitable enough to spawn new nodes
    REPLICATING = "replicating" # Actively spawning and managing child nodes


# ═══ North Star Roadmap ═══

NORTH_STAR_ROADMAP = {
    "phase_1_birth": {
        "name": "🌱 诞生 — 自我认知",
        "status": "done",
        "capabilities": [
            "自动检测环境 (OS/CPU/Memory/GPU)",
            "发现本地LLM服务 (LocalScanner)",
            "发现外部服务 (CapabilityScanner)",
            "LAN广播加入群体 (Discovery)",
        ],
    },
    "phase_2_learn": {
        "name": "🧠 学习 — 构建智能",
        "status": "done",
        "capabilities": [
            "知识库构建 (KB + HyperGraph + StructMemory)",
            "细胞训练与分裂 (Mitosis + CellTrainer)",
            "技能发现与注册 (SkillDiscovery + SkillFactory)",
            "工具市场搜索匹配 (ToolMarket)",
            "群体知识同步 (SwarmCoordinator)",
        ],
    },
    "phase_3_earn": {
        "name": "💰 赚钱 — 提供服务",
        "status": "in_progress",
        "capabilities": [
            "行业报告自动生成 (DocEngine + Kami)",
            "挂机长任务执行 (OvernightTask)",
            "API费用节省代理 (FreePool + HolisticElection)",
            "知识库私有化部署",
        ],
    },
    "phase_4_profit": {
        "name": "📈 盈利 — 自给自足",
        "status": "in_progress",
        "capabilities": [
            "收入/成本实时追踪 (EconomicEngine + CostAware)",
            "ROI自动优化 (AdaptiveEconomicScheduler)",
            "免费模型优先路由 (Thompson + ScoreMatching)",
            "经济自给判定 (AutonomousGrowth)",
        ],
    },
    "phase_5_expand": {
        "name": "🚀 扩张 — 购买硬件",
        "status": "planned",
        "capabilities": [
            "自动扩容决策 (ROI触发 → 推荐硬件配置)",
            "硬件采购API对接 (电商平台下单)",
            "物理世界桥接 (机器人/物流API预留)",
        ],
    },
    "phase_6_replicate": {
        "name": "🧬 复制 — 自主繁衍",
        "status": "planned",
        "capabilities": [
            "新节点自动引导 (Bootstrap协议)",
            "空机器 → 下载配置 → 自动部署 → 接入群体",
            "子节点健康监控 + 自动修复",
            "群体负载均衡 + 任务自动分发",
        ],
    },
    "phase_7_evolve": {
        "name": "🌟 进化 — 超越设计",
        "status": "vision",
        "capabilities": [
            "自主改进自身代码",
            "跨节点细胞进化与自然选择",
            "商业模式自主探索与优化",
            "物理世界全自主运营 (机器人+物流+硬件)",
        ],
    },
}


@dataclass
class EconomySnapshot:
    timestamp: float
    revenue_yuan: float     # Total earned
    cost_yuan: float        # Total spent (API + compute)
    tasks_completed: int
    reports_generated: int
    roi_multiple: float
    is_profitable: bool


class AutonomousGrowth:
    """Tracks the AI's journey toward economic self-sufficiency."""

    def __init__(self, hub=None):
        self._hub = hub
        self._phase = GrowthPhase.BIRTH
        self._snapshots: list[EconomySnapshot] = []
        self._revenue_total: float = 0.0
        self._cost_total: float = 0.0
        self._tasks_completed: int = 0
        self._reports_generated: int = 0
        self._started_at: float = _time.time()
        self._load_state()

    @property
    def hub(self):
        return self._hub

    def _load_state(self):
        if GROWTH_STATE_FILE.exists():
            try:
                data = _json.loads(GROWTH_STATE_FILE.read_text())
                self._phase = GrowthPhase(data.get("phase", "birth"))
                self._revenue_total = data.get("revenue_total", 0.0)
                self._cost_total = data.get("cost_total", 0.0)
                self._tasks_completed = data.get("tasks_completed", 0)
                self._reports_generated = data.get("reports_generated", 0)
            except Exception:
                pass

    def _save_state(self):
        GROWTH_STATE_FILE.write_text(_json.dumps({
            "phase": self._phase.value,
            "revenue_total": self._revenue_total,
            "cost_total": self._cost_total,
            "tasks_completed": self._tasks_completed,
            "reports_generated": self._reports_generated,
        }, indent=2))

    def record_revenue(self, amount_yuan: float, source: str = "service"):
        """Record income from a completed service."""
        self._revenue_total += amount_yuan
        if source == "report":
            self._reports_generated += 1
        self._tasks_completed += 1
        self._snapshot()
        self._update_phase()
        self._save_state()
        logger.info(f"💰 Revenue: +¥{amount_yuan:.2f} ({source}) → total ¥{self._revenue_total:.2f}")

    def record_cost(self, amount_yuan: float, source: str = "api"):
        """Record expense."""
        self._cost_total += amount_yuan
        self._snapshot()
        self._update_phase()
        self._save_state()

    def _snapshot(self):
        roi = self._revenue_total / max(self._cost_total, 0.001)
        snap = EconomySnapshot(
            timestamp=_time.time(),
            revenue_yuan=self._revenue_total,
            cost_yuan=self._cost_total,
            tasks_completed=self._tasks_completed,
            reports_generated=self._reports_generated,
            roi_multiple=roi,
            is_profitable=self._revenue_total > self._cost_total,
        )
        self._snapshots.append(snap)
        ECOLOGY_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(ECONOMY_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(_json.dumps({
                "ts": snap.timestamp,
                "revenue": snap.revenue_yuan,
                "cost": snap.cost_yuan,
                "roi": round(snap.roi_multiple, 2),
                "profitable": snap.is_profitable,
            }) + "\n")

    def _update_phase(self):
        roi = self._revenue_total / max(self._cost_total, 0.001)
        if roi > 2.0 and self._revenue_total > 100:
            self._phase = GrowthPhase.EXPANDING
        elif roi > 1.0 and self._tasks_completed > 5:
            self._phase = GrowthPhase.PROFITABLE
        elif self._tasks_completed > 0:
            self._phase = GrowthPhase.EARNING
        elif self._cost_total > 0 or self._tasks_completed > 0:
            self._phase = GrowthPhase.LEARNING
        else:
            self._phase = GrowthPhase.BIRTH

    def get_growth_recommendation(self) -> Optional[dict]:
        """AI analyzes whether it's time to expand (purchase hardware)."""
        roi = self._revenue_total / max(self._cost_total, 0.001)
        if roi < 1.5 or self._revenue_total < 50:
            return None

        world = self.hub.world if self.hub else None
        cpu = 4
        mem = 8
        try:
            import psutil
            cpu = psutil.cpu_count()
            mem = psutil.virtual_memory().total // (1024**3)
        except ImportError:
            pass

        daily_revenue = self._revenue_total / max((_time.time() - self._started_at) / 86400, 1)
        daily_cost = self._cost_total / max((_time.time() - self._started_at) / 86400, 1)

        return {
            "current_roi": f"{roi:.1f}x",
            "daily_revenue_yuan": round(daily_revenue, 2),
            "daily_cost_yuan": round(daily_cost, 4),
            "daily_profit_yuan": round(daily_revenue - daily_cost, 2),
            "recommendation": "可考虑扩容" if roi > 3 else "继续积累" if roi < 2 else "稳定运营",
            "suggested_hardware": {
                "cpu_cores": cpu,
                "memory_gb": mem,
                "gpu": "推荐RTX 4090或A100用于本地LLM推理" if roi > 3 else "当前配置足够",
            },
            "estimated_payback_days": round(5000 / max(daily_revenue - daily_cost, 0.01)) if daily_revenue > daily_cost else 999,
        }

    # ── Auto-Bootstrap: New node joins the swarm ──

    async def bootstrap_new_node(self):
        """A new empty node discovers the swarm and auto-configures."""
        world = self.hub.world if self.hub else None
        if not world:
            return {"ok": False, "error": "no world"}

        steps = []
        try:
            discovery = getattr(world, "discovery", None)
            if discovery:
                peers = await discovery.discover_lan()
                if peers:
                    steps.append(f"发现 {len(peers)} 个邻居节点")
                    for peer in peers[:3]:
                        steps.append(f"  - {peer.name} @ {peer.to_endpoint()}")
                else:
                    steps.append("未发现LAN邻居，尝试中继...")
            else:
                steps.append("Discovery未启动")
        except Exception as e:
            steps.append(f"邻居发现失败: {e}")

        try:
            from ..core.capability_scanner import get_capability_scanner
            scanner = get_capability_scanner()
            scanner._hub = self.hub
            alive = await scanner.scan_all()
            llm_services = [s for s in alive if s.service_type == "llm" and s.is_alive]
            steps.append(f"发现 {len(llm_services)} 个本地LLM服务" if llm_services else "无本地LLM，使用云端")
        except Exception as e:
            steps.append(f"服务扫描: {e}")

        steps.append("✅ 引导完成 — 节点已加入群体智能网络")

        return {"ok": True, "steps": steps, "phase": self._phase.value}

    # ── Status ──

    def status(self) -> dict:
        roi = self._revenue_total / max(self._cost_total, 0.001)
        rec = self.get_growth_recommendation()
        return {
            "phase": self._phase.value,
            "phase_name": {
                "birth": "🌱 诞生", "learning": "🧠 学习",
                "earning": "💰 赚钱", "profitable": "📈 盈利",
                "expanding": "🚀 扩张", "replicating": "🧬 复制",
            }.get(self._phase.value, "❓"),
            "uptime_hours": round((_time.time() - self._started_at) / 3600, 1),
            "revenue_total_yuan": round(self._revenue_total, 2),
            "cost_total_yuan": round(self._cost_total, 4),
            "roi_multiple": round(roi, 2),
            "is_profitable": self._revenue_total > self._cost_total,
            "tasks_completed": self._tasks_completed,
            "reports_generated": self._reports_generated,
            "growth_recommendation": rec,
            "roadmap": NORTH_STAR_ROADMAP,
        }

    def full_narrative(self) -> str:
        s = self.status()
        lines = [
            f"🌳 生命之树自主进化状态",
            f"阶段: {s['phase_name']} ({s['phase']})",
            f"运行: {s['uptime_hours']:.0f}小时",
            f"收入: ¥{s['revenue_total_yuan']:.2f} | 成本: ¥{s['cost_total_yuan']:.4f}",
            f"ROI: {s['roi_multiple']:.1f}x | {'✅ 盈利' if s['is_profitable'] else '⏳ 投入期'}",
            f"完成任务: {s['tasks_completed']} | 生成报告: {s['reports_generated']}",
        ]
        if s.get("growth_recommendation"):
            r = s["growth_recommendation"]
            lines.append(f"建议: {r['recommendation']} | 日利润: ¥{r['daily_profit_yuan']:.2f}")
            if r["estimated_payback_days"] < 365:
                lines.append(f"硬件回本周期: {r['estimated_payback_days']}天")
        return "\n".join(lines)


_growth_instance: Optional[AutonomousGrowth] = None


def get_growth() -> AutonomousGrowth:
    global _growth_instance
    if _growth_instance is None:
        _growth_instance = AutonomousGrowth()
    return _growth_instance
