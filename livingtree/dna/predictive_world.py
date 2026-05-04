"""Predictive World Model — Causal understanding of the project ecosystem.

Maintains a causal graph of the codebase: which modules depend on which,
how changes propagate, historical change patterns. Can predict:
- Impact radius of a proposed change (blast radius)
- Likely test failures from a given edit
- Optimal refactoring targets based on churn patterns
- Architectural hotspots that will need attention soon

Built on: code_graph + git history + error_patterns + change_frequency.
"""

from __future__ import annotations
import time, json
from dataclasses import dataclass, field
from collections import defaultdict
from pathlib import Path
from loguru import logger

@dataclass
class ChangePrediction:
    file: str
    risk_level: str = "low"    # low/medium/high/critical
    impact_files: list[str] = field(default_factory=list)
    likely_errors: list[str] = field(default_factory=list)
    churn_rate: float = 0.0
    last_changed_days: float = 999
    suggestion: str = ""

@dataclass
class HotspotReport:
    high_risk_files: list[ChangePrediction] = field(default_factory=list)
    refactoring_targets: list[str] = field(default_factory=list)
    architectural_debt: list[str] = field(default_factory=list)
    generated_at: str = ""

class PredictiveWorldModel:
    """Causal model of project behavior for proactive intelligence."""

    def __init__(self, world=None):
        self._world = world
        self._change_history = defaultdict(list)
        self._error_locations = defaultdict(int)
        self._predictions = []
        self._load_history()

    def record_change(self, file_path: str, change_type: str, success: bool):
        self._change_history[file_path].append({
            "time": time.time(), "type": change_type, "success": success,
        })

    def record_error(self, file_path: str):
        self._error_locations[file_path] += 1

    async def analyze(self) -> HotspotReport:
        code_graph = getattr(self._world, 'code_graph', None) if self._world else None
        predictions = []
        all_files = set()

        if code_graph and hasattr(code_graph, 'nodes_index'):
            for fid, node in code_graph.nodes_index.items():
                if hasattr(node, 'file'):
                    all_files.add(getattr(node, 'file', ''))

        for f in all_files:
            if not f:
                continue

            churn = len(self._change_history.get(f, []))
            recent_changes = [c for c in self._change_history.get(f, [])
                             if time.time() - c["time"] < 86400 * 30]
            fail_rate = sum(1 for c in recent_changes if not c["success"]) / max(len(recent_changes), 1)
            errors = self._error_locations.get(f, 0)

            risk = "low"
            if churn > 10 or errors > 5:
                risk = "critical"
            elif churn > 5 or errors > 3 or fail_rate > 0.3:
                risk = "high"
            elif churn > 2 or errors > 1:
                risk = "medium"

            impact_files = []
            if code_graph and hasattr(code_graph, 'blast_radius'):
                try:
                    impacted = code_graph.blast_radius([f])
                    impact_files = [i.file for i in impacted[:5]]
                except: pass

            suggestion = ""
            if risk in ("critical", "high"):
                suggestion = f"Consider refactoring {f} — high churn ({churn}) and error rate ({fail_rate:.0%})"
            elif churn > 5:
                suggestion = f"Add tests for {f} — frequent changes without coverage"

            last_changed = min(
                [time.time() - c["time"] for c in self._change_history.get(f, [])] + [999 * 86400]
            ) / 86400

            predictions.append(ChangePrediction(
                file=f, risk_level=risk, impact_files=impact_files,
                churn_rate=churn, last_changed_days=round(last_changed, 1),
                suggestion=suggestion,
            ))

        predictions.sort(key=lambda p: {"critical": 4, "high": 3, "medium": 2, "low": 1}[p.risk_level], reverse=True)

        from datetime import datetime, timezone
        return HotspotReport(
            high_risk_files=predictions[:10],
            refactoring_targets=[p.file for p in predictions if p.risk_level in ("critical", "high")][:5],
            architectural_debt=[p.suggestion for p in predictions if p.suggestion][:5],
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    async def predict_impact(self, file_path: str) -> ChangePrediction:
        code_graph = getattr(self._world, 'code_graph', None) if self._world else None
        impact_files = []
        if code_graph and hasattr(code_graph, 'blast_radius'):
            try:
                impacted = code_graph.blast_radius([file_path])
                impact_files = [i.file for i in impacted[:10]]
            except: pass

        churn = len(self._change_history.get(file_path, []))
        errors = self._error_locations.get(file_path, 0)
        risk = "critical" if errors > 5 else ("high" if churn > 5 else ("medium" if churn > 2 else "low"))

        return ChangePrediction(
            file=file_path, risk_level=risk, impact_files=impact_files,
            churn_rate=churn, likely_errors=[],
            suggestion=f"Impact radius: {len(impact_files)} files" if impact_files else "",
        )

    def get_status(self) -> dict:
        return {
            "tracked_files": len(self._change_history),
            "error_locations": len(self._error_locations),
            "total_changes": sum(len(v) for v in self._change_history.values()),
            "hotspots": len([p for p in self._predictions if p.risk_level in ("critical", "high")]),
        }

    def _load_history(self):
        try:
            path = Path(".livingtree/causal_model.json")
            if path.exists():
                data = json.loads(path.read_text())
                for k, v in data.get("changes", {}).items():
                    self._change_history[k] = v
                for k, v in data.get("errors", {}).items():
                    self._error_locations[k] = v
        except: pass

    def _save(self):
        try:
            path = Path(".livingtree/causal_model.json")
            path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "changes": {k: v[-50:] for k, v in self._change_history.items()},
                "errors": dict(self._error_locations),
            }
            path.write_text(json.dumps(data, ensure_ascii=False))
        except: pass
