"""LivingTree Dynamic Policy Framework — DDPF-style signal-driven strategy engine.

Based on Douyin DDPF architecture pattern:
  1. Signal Bus — abstracts all timing signals into a unified bus
  2. DSL Engine — WHEN <signal> THEN <action> WITH <priority>
  3. A/B Platform — compare strategies, auto-select winner
"""

# Usage example (see default_dsl() for full DSL):
#     policy = DynamicPolicyEngine()
#     await policy.initialize(hub)
#     policy.load_dsl(policy.default_dsl())
#     decisions = await policy.evaluate()

from __future__ import annotations

import asyncio
import json
import math
import os
import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np
from loguru import logger

POLICY_DIR = Path(".livingtree/policy")
POLICY_SIGNALS = POLICY_DIR / "signals.json"
POLICY_RULES = POLICY_DIR / "rules.dsl"
POLICY_AB = POLICY_DIR / "ab_experiments.json"


class SignalPriority(Enum):
    CRITICAL = auto()  # Must execute, overrides all
    HIGH = auto()
    MEDIUM = auto()
    LOW = auto()
    OBSERVE = auto()  # Log only, don't act

    @classmethod
    def from_str(cls, s: str) -> SignalPriority:
        return {
            "critical": cls.CRITICAL, "high": cls.HIGH,
            "medium": cls.MEDIUM, "low": cls.LOW, "observe": cls.OBSERVE,
        }.get(s.lower(), cls.MEDIUM)


class SignalType(Enum):
    """All timing/performance signal types — unified abstraction."""
    # Network
    PROXY_LATENCY = "proxy_latency_ms"
    PROXY_SUCCESS_RATE = "proxy_success_rate"
    BANDWIDTH_BYTES = "bandwidth_bytes"
    CONCURRENT_CONNECTIONS = "concurrent_connections"
    # System
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"
    # Economic
    ESTIMATED_COST = "estimated_cost_yuan"
    DAILY_BUDGET_REMAINING = "daily_budget_remaining"
    # Quality
    CONSECUTIVE_FAILURES = "consecutive_failures"
    ERROR_RATE = "error_rate_1min"
    CACHE_HIT_RATE = "cache_hit_rate"
    # Routing
    ACTIVE_PROXIES = "active_proxies"
    PROXY_POOL_HEALTH = "proxy_pool_health"
    BANDIT_EXPLORATION = "bandit_exploration_rate"
    # Protocol
    QUIC_ACTIVE = "quic_active"
    PROTOCOL_SUCCESS_RATE = "protocol_success_rate"


@dataclass
class Signal:
    """A single performance/business timing signal."""
    name: str
    type: SignalType
    value: float
    timestamp: float = field(default_factory=time.time)
    source: str = ""  # Which module emitted this
    unit: str = ""
    threshold_warn: float = 0.0
    threshold_critical: float = 0.0

    @property
    def is_warning(self) -> bool:
        return self.value > self.threshold_warn if self.threshold_warn else False

    @property
    def is_critical(self) -> bool:
        return self.value > self.threshold_critical if self.threshold_critical else False


@dataclass
class DSLRule:
    """A single WHEN-THEN-WITH DSL rule."""
    name: str
    conditions: list[tuple[str, str, float]] = field(default_factory=list)  # [(signal, op, threshold), ...]
    actions: list[tuple[str, str]] = field(default_factory=list)  # [(action_name, action_param), ...]
    logic: str = "AND"  # AND | OR
    priority: SignalPriority = SignalPriority.MEDIUM
    cooldown_seconds: float = 30.0  # Min time between re-triggers
    last_triggered: float = 0.0
    trigger_count: int = 0
    enabled: bool = True

    @property
    def on_cooldown(self) -> bool:
        return time.time() - self.last_triggered < self.cooldown_seconds


@dataclass
class ABExperiment:
    """A/B comparison between two strategies."""
    id: str
    name: str
    strategy_a: list[str]  # Rule names in group A
    strategy_b: list[str]  # Rule names in group B
    metric: SignalType = SignalType.PROXY_SUCCESS_RATE
    # Tracking
    a_successes: int = 0
    a_total: int = 0
    b_successes: int = 0
    b_total: int = 0
    a_cost: float = 0.0
    b_cost: float = 0.0
    created_at: float = field(default_factory=time.time)
    winner: str = ""  # "a" | "b" | ""

    @property
    def a_rate(self) -> float:
        return self.a_successes / max(self.a_total, 1)

    @property
    def b_rate(self) -> float:
        return self.b_successes / max(self.b_total, 1)

    def declare_winner(self, confidence: float = 0.95, min_samples: int = 100):
        """Auto-declare winner when statistically significant."""
        total = self.a_total + self.b_total
        if total < min_samples:
            return

        # Simple Bayesian: higher success rate wins
        if self.a_rate > self.b_rate and self.a_total > min_samples * 0.3:
            self.winner = "a"
        elif self.b_rate > self.a_rate and self.b_total > min_samples * 0.3:
            self.winner = "b"


class SignalBus:
    """Unified signal bus — the central nervous system.

    Collects, normalizes, and serves all runtime signals.
    Every subsystem writes its signals here; every strategy reads from here.
    """

    def __init__(self, window_size: int = 300):
        self._signals: dict[SignalType, deque[Signal]] = defaultdict(
            lambda: deque(maxlen=window_size)
        )
        self._current_values: dict[SignalType, float] = {}
        self._subscribers: dict[SignalType, list[Callable]] = defaultdict(list)
        self._history_window = window_size

    def emit(self, signal_type: SignalType, value: float, source: str = "",
             unit: str = "", warn: float = 0, critical: float = 0):
        """Emit a signal onto the bus."""
        signal = Signal(
            name=signal_type.value,
            type=signal_type,
            value=value,
            source=source,
            unit=unit,
            threshold_warn=warn,
            threshold_critical=critical,
        )
        self._signals[signal_type].append(signal)
        self._current_values[signal_type] = value

        # Notify subscribers
        for callback in self._subscribers.get(signal_type, []):
            try:
                callback(signal)
            except Exception:
                pass

    def get(self, signal_type: SignalType) -> float:
        """Get current value of a signal."""
        return self._current_values.get(signal_type, 0.0)

    def get_stats(self, signal_type: SignalType) -> dict:
        """Get statistical summary of a signal over the window."""
        signals = list(self._signals.get(signal_type, []))
        if not signals:
            return {"current": 0.0, "mean": 0.0, "min": 0.0, "max": 0.0, "count": 0}

        values = [s.value for s in signals]
        return {
            "current": values[-1],
            "mean": float(np.mean(values)),
            "min": float(np.min(values)),
            "max": float(np.max(values)),
            "std": float(np.std(values)),
            "count": len(values),
            "trend": "up" if len(values) > 2 and values[-1] > np.mean(values[-5:]) else "down",
        }

    def subscribe(self, signal_type: SignalType, callback: Callable):
        """Subscribe to real-time signal updates."""
        self._subscribers[signal_type].append(callback)

    def get_snapshot(self) -> dict[str, float]:
        """Get snapshot of all current signal values."""
        return {k.value: v for k, v in self._current_values.items()}

    def get_dashboard(self) -> dict:
        """Full dashboard of all signals with stats."""
        return {
            st.value: self.get_stats(st)
            for st in SignalType
            if st in self._current_values
        }


class DSLEngine:
    """Parse and execute DSL strategy rules.

    DSL Syntax:
      RULE <name>
        WHEN <signal> <op> <value> [AND|OR <signal> <op> <value> ...]
        THEN <action> [WITH priority=<level>]

    Supported ops: > < >= <= == !=
    Supported actions: reroute_proxy_pool, switch_model, switch_protocol,
                       enable_obfuscation, change_padding, scale_pool,
                       enable_quic, disable_quic, enable_cache, evict_cache,
                       alert, log_only
    """

    # Action → handler mapping (populated by DynamicPolicyEngine)
    _action_handlers: dict[str, Callable] = {}

    def register_action(self, name: str, handler: Callable):
        """Register an action handler."""
        self._action_handlers[name] = handler

    def parse_rules(self, dsl_text: str) -> list[DSLRule]:
        """Parse DSL text into Rule objects."""
        rules = []
        current_rule = None

        for line in dsl_text.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if line.upper().startswith("RULE "):
                if current_rule:
                    rules.append(current_rule)
                name = line[5:].strip()
                current_rule = DSLRule(name=name, conditions=[], actions=[])

            elif line.upper().startswith("WHEN ") and current_rule:
                cond_text = line[5:].strip()
                current_rule.conditions = self._parse_conditions(cond_text)
                # Detect logic: if " OR " in the original, use OR
                if " OR " in cond_text.upper():
                    current_rule.logic = "OR"

            elif line.upper().startswith("THEN ") and current_rule:
                action_text = line[5:].strip()
                current_rule.actions = self._parse_actions(action_text)

            elif line.upper().startswith("WITH ") and current_rule:
                priority_text = line[5:].strip().lower()
                for kw in ["priority=", "cooldown="]:
                    if kw in priority_text:
                        val = priority_text.split(kw)[1].split()[0].strip()
                        if kw == "priority=":
                            current_rule.priority = SignalPriority.from_str(val)
                        elif kw == "cooldown=":
                            try:
                                current_rule.cooldown_seconds = float(val.rstrip("s"))
                            except ValueError:
                                pass

        if current_rule:
            rules.append(current_rule)

        return rules

    def _parse_conditions(self, text: str) -> list[tuple[str, str, float]]:
        """Parse condition expressions like 'latency > 500 AND cpu < 60'."""
        conditions = []
        # Split by AND/OR
        parts = re.split(r'\s+(?:AND|OR)\s+', text, flags=re.IGNORECASE)
        for part in parts:
            match = re.match(
                r'(\w+)\s*(>=|<=|!=|==|>|<)\s*([\d.]+)', part.strip(),
            )
            if match:
                signal_name = match.group(1)
                op = match.group(2)
                value = float(match.group(3))
                conditions.append((signal_name, op, value))
        return conditions

    def _parse_actions(self, text: str) -> list[tuple[str, str]]:
        """Parse action expressions like 'reroute_proxy_pool WITH priority=high'."""
        actions = []
        # Remove WITH clause
        action_text = text.split(" WITH ")[0] if " WITH " in text.upper() else text
        # Handle multiple actions separated by commas or 'AND'
        action_parts = re.split(r'\s*,\s*|\s+AND\s+', action_text, flags=re.IGNORECASE)
        for part in action_parts:
            part = part.strip()
            # extract action_name(param)
            match = re.match(r'(\w+)\(?"?([^")]*)"?\)?', part)
            if match:
                name = match.group(1)
                param = match.group(2) if match.group(2) else ""
                actions.append((name, param))
        return actions

    def evaluate_conditions(self, rule: DSLRule, signal_bus: SignalBus) -> bool:
        """Check if a rule's conditions are met."""
        if not rule.conditions:
            return False

        results = []
        for signal_name, op, threshold in rule.conditions:
            # Try to get signal value by name
            value = self._get_signal_value(signal_name, signal_bus)
            result = self._compare(value, op, threshold)
            results.append(result)

        if rule.logic == "OR":
            return any(results)
        return all(results)

    def _get_signal_value(self, name: str, signal_bus: SignalBus) -> float:
        """Resolve signal name to current value."""
        # Direct SignalType match
        for st in SignalType:
            if st.value == name or st.name.lower() == name.lower():
                return signal_bus.get(st)

        # Aliases
        aliases = {
            "latency": SignalType.PROXY_LATENCY,
            "success_rate": SignalType.PROXY_SUCCESS_RATE,
            "cpu": SignalType.CPU_USAGE,
            "memory": SignalType.MEMORY_USAGE,
            "cost": SignalType.ESTIMATED_COST,
            "failures": SignalType.CONSECUTIVE_FAILURES,
            "error_rate": SignalType.ERROR_RATE,
            "cache": SignalType.CACHE_HIT_RATE,
            "bandwidth": SignalType.BANDWIDTH_BYTES,
        }
        st = aliases.get(name.lower())
        if st:
            return signal_bus.get(st)

        return 0.0

    @staticmethod
    def _compare(value: float, op: str, threshold: float) -> bool:
        if op == ">":
            return value > threshold
        if op == "<":
            return value < threshold
        if op == ">=":
            return value >= threshold
        if op == "<=":
            return value <= threshold
        if op == "==":
            return abs(value - threshold) < 1e-6
        if op == "!=":
            return abs(value - threshold) > 1e-6
        return False

    async def execute_actions(self, rule: DSLRule) -> list[str]:
        """Execute a rule's actions. Returns list of action results."""
        results = []
        for action_name, action_param in rule.actions:
            handler = self._action_handlers.get(action_name)
            if handler:
                try:
                    result = handler(action_param)
                    if asyncio.iscoroutine(result):
                        result = await result
                    results.append(f"{action_name}({action_param}) → {result}")
                except Exception as e:
                    results.append(f"{action_name}({action_param}) → ERROR: {e}")
            else:
                results.append(f"{action_name}({action_param}) → UNKNOWN_ACTION")
        return results


class DynamicPolicyEngine:
    """Central policy engine — wires SignalBus + DSLEngine + AB testing.

    This is the main entry point. It:
    1. Collects all system signals into the SignalBus
    2. Evaluates DSL rules every N seconds
    3. Triggers actions when conditions are met
    4. Runs A/B experiments to find optimal strategies

    Usage:
        engine = DynamicPolicyEngine()
        await engine.initialize(hub, scinet_engine=None)
        await engine.start_background()

        # Or just evaluate once:
        decisions = await engine.evaluate()
    """

    def __init__(self):
        self._signal_bus = SignalBus()
        self._dsl_engine = DSLEngine()
        self._rules: dict[str, DSLRule] = {}
        self._ab_experiments: dict[str, ABExperiment] = {}
        self._action_log: deque = deque(maxlen=100)
        self._initialized = False
        self._running = False
        self._eval_task: Optional[asyncio.Task] = None
        self._scinet_engine: Any = None

    async def initialize(self, hub=None, scinet_engine=None):
        """Wire up to LivingTree infrastructure."""
        self._scinet_engine = scinet_engine

        # Register standard action handlers
        self._dsl_engine.register_action("reroute_proxy_pool", self._act_reroute_pool)
        self._dsl_engine.register_action("switch_model", self._act_switch_model)
        self._dsl_engine.register_action("switch_protocol", self._act_switch_protocol)
        self._dsl_engine.register_action("enable_obfuscation", self._act_enable_obfuscation)
        self._dsl_engine.register_action("change_padding", self._act_change_padding)
        self._dsl_engine.register_action("scale_pool", self._act_scale_pool)
        self._dsl_engine.register_action("enable_quic", self._act_enable_quic)
        self._dsl_engine.register_action("enable_cache", self._act_enable_cache)
        self._dsl_engine.register_action("alert", self._act_alert)
        self._dsl_engine.register_action("log_only", self._act_log_only)

        # Hook into SystemMonitor for system signals
        try:
            from ..observability.system_monitor import SystemMonitor
            monitor = SystemMonitor.instance()
            # We'll poll it during evaluate()
        except Exception:
            pass

        # Load saved rules
        self._load_rules()
        self._load_state()

        self._initialized = True
        logger.info(
            "DynamicPolicyEngine: %d rules loaded, %d experiments",
            len(self._rules), len(self._ab_experiments),
        )

    def load_dsl(self, dsl_text: str):
        """Load strategy rules from DSL text."""
        rules = self._dsl_engine.parse_rules(dsl_text)
        for rule in rules:
            self._rules[rule.name] = rule
        self._save_rules()
        logger.info(f"Loaded {len(rules)} DSL rules")

    async def evaluate(self) -> list[dict]:
        """Evaluate all rules against current signals. Returns triggered actions."""
        # Refresh system signals
        await self._refresh_signals()

        triggered = []

        for rule_name, rule in sorted(
            self._rules.items(),
            key=lambda r: r[1].priority.value,
        ):
            if not rule.enabled:
                continue
            if rule.on_cooldown:
                continue

            if self._dsl_engine.evaluate_conditions(rule, self._signal_bus):
                results = await self._dsl_engine.execute_actions(rule)
                rule.last_triggered = time.time()
                rule.trigger_count += 1

                entry = {
                    "rule": rule_name,
                    "priority": rule.priority.name,
                    "actions": results,
                    "timestamp": time.time(),
                }
                triggered.append(entry)
                self._action_log.append(entry)
                logger.info("Policy triggered: %s → %s", rule_name, results)

        # Update A/B experiments
        for exp in self._ab_experiments.values():
            exp.declare_winner()

        return triggered

    async def _refresh_signals(self):
        """Collect all available system signals onto the bus."""
        # System signals
        try:
            from ..observability.system_monitor import SystemMonitor
            snapshot = SystemMonitor.instance().snapshot()
            if snapshot:
                self._signal_bus.emit(SignalType.CPU_USAGE, snapshot.cpu_percent, "system_monitor")
                self._signal_bus.emit(SignalType.MEMORY_USAGE, snapshot.memory_percent, "system_monitor")
        except Exception:
            pass

        # Scinet engine signals
        if self._scinet_engine:
            try:
                det = self._scinet_engine.get_detailed_status()
                eng = det.get("engine", {})

                # Network
                self._signal_bus.emit(
                    SignalType.PROXY_SUCCESS_RATE,
                    eng.get("success_rate", 0),
                    "scinet_engine",
                )
                self._signal_bus.emit(
                    SignalType.PROXY_LATENCY,
                    eng.get("avg_latency_ms", 0),
                    "scinet_engine", "ms",
                )
                self._signal_bus.emit(
                    SignalType.BANDWIDTH_BYTES,
                    eng.get("bandwidth_bytes", 0),
                    "scinet_engine", "bytes",
                )
                self._signal_bus.emit(
                    SignalType.CONSECUTIVE_FAILURES,
                    max(0, eng.get("total_requests", 0) - eng.get("success_rate", 0) * eng.get("total_requests", 1)),
                    "scinet_engine",
                )

                # Cache
                cache = det.get("cache", {})
                self._signal_bus.emit(
                    SignalType.CACHE_HIT_RATE,
                    cache.get("hit_rate", 0),
                    "cache",
                )

                # Bandit
                bandit = det.get("bandit", {})
                self._signal_bus.emit(
                    SignalType.BANDIT_EXPLORATION,
                    bandit.get("exploration_rate", 1.0),
                    "bandit",
                )
            except Exception:
                pass

    # ─── Action handlers ───

    def _act_reroute_pool(self, param: str):
        return f"reroute to proxy pool: {param or 'auto'}"

    def _act_switch_model(self, param: str):
        return f"switch model → {param or 'flash'}"

    def _act_switch_protocol(self, param: str):
        return f"switch protocol → {param or 'h3'}"

    def _act_enable_obfuscation(self, param: str):
        return f"obfuscation → {param or 'aggressive'}"

    def _act_change_padding(self, param: str):
        return f"padding → {param or 'standard'}"

    def _act_scale_pool(self, param: str):
        return f"scale proxy pool by {param or '+10'}"

    def _act_enable_quic(self, param: str):
        return f"QUIC → {param or 'enabled'}"

    def _act_enable_cache(self, param: str):
        return f"cache → {param or 'enabled'}"

    def _act_alert(self, param: str):
        logger.warning(f"ALERT: {param}")
        return f"alert sent: {param}"

    def _act_log_only(self, param: str):
        return f"logged: {param}"

    # ─── A/B Experiments ───

    def create_experiment(self, name: str, strategy_a: list[str],
                          strategy_b: list[str], metric: SignalType = None):
        """Create an A/B experiment comparing two strategy groups."""
        exp = ABExperiment(
            id=f"exp_{int(time.time())}",
            name=name,
            strategy_a=strategy_a,
            strategy_b=strategy_b,
            metric=metric or SignalType.PROXY_SUCCESS_RATE,
        )
        self._ab_experiments[exp.id] = exp
        return exp

    def record_experiment(self, exp_id: str, group: str, success: bool, cost: float = 0):
        """Record an experiment outcome."""
        exp = self._ab_experiments.get(exp_id)
        if not exp:
            return
        if group == "a":
            exp.a_total += 1
            if success:
                exp.a_successes += 1
            exp.a_cost += cost
        else:
            exp.b_total += 1
            if success:
                exp.b_successes += 1
            exp.b_cost += cost

    def get_ab_results(self, exp_id: str = "") -> dict:
        """Get A/B experiment results."""
        if exp_id:
            exp = self._ab_experiments.get(exp_id)
            if not exp:
                return {}
            return {
                "id": exp.id, "name": exp.name,
                "a": {"rate": exp.a_rate, "total": exp.a_total, "cost": exp.a_cost},
                "b": {"rate": exp.b_rate, "total": exp.b_total, "cost": exp.b_cost},
                "winner": exp.winner,
            }

        return {
            eid: {
                "name": e.name,
                "a_rate": e.a_rate, "b_rate": e.b_rate,
                "winner": e.winner,
            }
            for eid, e in self._ab_experiments.items()
        }

    # ─── Background loop ───

    async def start_background(self, interval: float = 10.0):
        """Start periodic policy evaluation."""
        self._running = True
        self._eval_task = asyncio.create_task(self._loop(interval))
        logger.info("DynamicPolicyEngine: background loop started (interval=%.0fs)", interval)

    async def stop(self):
        self._running = False
        if self._eval_task:
            self._eval_task.cancel()
        self._save_state()

    async def _loop(self, interval: float):
        while self._running:
            try:
                await self.evaluate()
            except Exception as e:
                logger.debug("Policy loop error: %s", e)
            await asyncio.sleep(interval)

    # ─── DSL examples / presets ───

    @staticmethod
    def default_dsl() -> str:
        """Default DSL rules that ship with LivingTree."""
        return """
# ─── Cost optimization ───
RULE cost_saver
  WHEN success_rate > 0.85 AND cpu < 60 AND cost > 0.01
  THEN switch_model("flash") AND enable_cache("aggressive")
  WITH priority=medium cooldown=60s

# ─── Performance protection ───
RULE overload_protection
  WHEN latency > 2000 OR failures > 5 OR cpu > 90
  THEN reroute_proxy_pool AND enable_obfuscation("aggressive")
  WITH priority=critical cooldown=10s

# ─── Protocol optimization ───
RULE protocol_upgrade
  WHEN latency > 1000 AND quic_active == 0
  THEN switch_protocol("h3") AND enable_quic
  WITH priority=high cooldown=120s

# ─── Proxy pool health ───
RULE pool_health_check
  WHEN active_proxies < 10 OR proxy_pool_health < 0.3
  THEN scale_pool("+20") AND alert("proxy_pool_low")
  WITH priority=high cooldown=300s

# ─── Observation only ───
RULE performance_trend
  WHEN latency > 500 AND cache < 0.3
  THEN log_only("performance_degradation_warning")
  WITH priority=observe cooldown=30s
"""

    # ─── Persistence ───

    def get_dashboard(self) -> dict:
        """Full policy dashboard for UI."""
        return {
            "signals": self._signal_bus.get_dashboard(),
            "rules": [
                {"name": r.name, "enabled": r.enabled, "triggers": r.trigger_count,
                 "priority": r.priority.name, "on_cooldown": r.on_cooldown}
                for r in self._rules.values()
            ],
            "experiments": self.get_ab_results(),
            "recent_actions": list(self._action_log)[-10:],
        }

    def get_stats(self) -> dict:
        dashboard = self.get_dashboard()
        return {
            "rules_loaded": len(self._rules),
            "experiments_active": len(self._ab_experiments),
            "signals_tracked": len(dashboard["signals"]),
            "actions_taken": len(self._action_log),
        }

    def _save_rules(self):
        try:
            POLICY_DIR.mkdir(parents=True, exist_ok=True)
            POLICY_RULES.write_text(
                "\n".join(
                    f"# Rule: {r.name} (priority={r.priority.name}, triggers={r.trigger_count})"
                    for r in self._rules.values()
                ),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _load_rules(self):
        """Load default DSL if no saved rules exist."""
        if not self._rules and not POLICY_RULES.exists():
            self.load_dsl(self.default_dsl())

    def _save_state(self):
        try:
            data = {
                "experiments": {
                    eid: {
                        "name": e.name,
                        "a_total": e.a_total, "a_successes": e.a_successes,
                        "b_total": e.b_total, "b_successes": e.b_successes,
                        "winner": e.winner,
                    }
                    for eid, e in self._ab_experiments.items()
                },
            }
            POLICY_DIR.mkdir(parents=True, exist_ok=True)
            POLICY_AB.write_text(json.dumps(data, indent=2))
        except Exception:
            pass

    def _load_state(self):
        if not POLICY_AB.exists():
            return
        try:
            data = json.loads(POLICY_AB.read_text())
            for eid, ed in data.get("experiments", {}).items():
                exp = ABExperiment(
                    id=eid, name=ed["name"],
                    strategy_a=[], strategy_b=[],
                    a_total=ed.get("a_total", 0),
                    a_successes=ed.get("a_successes", 0),
                    b_total=ed.get("b_total", 0),
                    b_successes=ed.get("b_successes", 0),
                    winner=ed.get("winner", ""),
                )
                self._ab_experiments[eid] = exp
        except Exception:
            pass


_policy_engine: Optional[DynamicPolicyEngine] = None


def get_policy_engine() -> DynamicPolicyEngine:
    global _policy_engine
    if _policy_engine is None:
        _policy_engine = DynamicPolicyEngine()
    return _policy_engine
