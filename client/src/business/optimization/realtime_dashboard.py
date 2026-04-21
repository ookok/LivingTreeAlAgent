"""
Entroly 风格实时监控仪表盘

提供本地实时监控面板，可视化 token 消耗和成本节省
类似于 Entraly 的 localhost:9378 监控面板
"""

import time
import json
import threading
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import asyncio
from datetime import datetime, timedelta


class MetricType(Enum):
    """指标类型"""
    TOKEN_INPUT = "token_input"
    TOKEN_OUTPUT = "token_output"
    TOKEN_TOTAL = "token_total"
    COST = "cost"
    COST_SAVINGS = "cost_savings"
    API_CALLS = "api_calls"
    LATENCY = "latency"
    ERRORS = "errors"


@dataclass
class MetricRecord:
    """指标记录"""
    timestamp: float
    metric_type: MetricType
    value: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionStats:
    """会话统计"""
    session_id: str
    start_time: float
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_cost: float = 0.0
    cost_savings: float = 0.0
    api_calls: int = 0
    errors: int = 0
    avg_latency: float = 0.0


class CostCalculator:
    """成本计算器"""

    # 价格表（每 1M tokens）
    PRICING = {
        "gpt-4o": {"input": 5.0, "output": 15.0},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4-turbo": {"input": 10.0, "output": 30.0},
        "gpt-3.5-turbo": {"input": 0.5, "output": 1.5},
        "claude-3-opus": {"input": 15.0, "output": 75.0},
        "claude-3-sonnet": {"input": 3.0, "output": 15.0},
        "claude-3-haiku": {"input": 0.25, "output": 1.25},
        "gemini-pro": {"input": 3.5, "output": 10.5},
        "default": {"input": 1.0, "output": 2.0},
    }

    @classmethod
    def calculate_cost(
        cls,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """
        计算 API 调用成本

        Args:
            model: 模型名称
            input_tokens: 输入 token 数
            output_tokens: 输出 token 数

        Returns:
            float: 成本（美元）
        """
        pricing = cls.PRICING.get(model, cls.PRICING["default"])

        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]

        return input_cost + output_cost

    @classmethod
    def calculate_savings(
        cls,
        original_tokens: int,
        optimized_tokens: int,
        model: str
    ) -> float:
        """
        计算节省的成本

        Args:
            original_tokens: 原始 token 数
            optimized_tokens: 优化后 token 数
            model: 模型名称

        Returns:
            float: 节省的成本（美元）
        """
        pricing = cls.PRICING.get(model, cls.PRICING["default"])
        avg_cost_per_token = (pricing["input"] + pricing["output"]) / 2 / 1_000_000

        return (original_tokens - optimized_tokens) * avg_cost_per_token


class MetricsCollector:
    """指标收集器"""

    def __init__(self):
        """初始化收集器"""
        self.records: List[MetricRecord] = []
        self._lock = threading.RLock()
        self.max_records = 10000

    def record(
        self,
        metric_type: MetricType,
        value: float,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        记录指标

        Args:
            metric_type: 指标类型
            value: 指标值
            metadata: 元数据
        """
        record = MetricRecord(
            timestamp=time.time(),
            metric_type=metric_type,
            value=value,
            metadata=metadata or {}
        )

        with self._lock:
            self.records.append(record)

            # 清理旧记录
            if len(self.records) > self.max_records:
                self.records = self.records[-self.max_records:]

    def get_records(
        self,
        metric_type: Optional[MetricType] = None,
        since: Optional[float] = None,
        limit: int = 100
    ) -> List[MetricRecord]:
        """
        获取指标记录

        Args:
            metric_type: 指标类型过滤
            since: 时间过滤（Unix 时间戳）
            limit: 返回数量限制

        Returns:
            List[MetricRecord]: 指标记录列表
        """
        with self._lock:
            records = self.records.copy()

        if metric_type:
            records = [r for r in records if r.metric_type == metric_type]

        if since:
            records = [r for r in records if r.timestamp >= since]

        return records[-limit:]

    def get_stats(self, window_seconds: int = 60) -> Dict[str, Any]:
        """
        获取统计信息

        Args:
            window_seconds: 窗口大小（秒）

        Returns:
            Dict[str, Any]: 统计信息
        """
        now = time.time()
        since = now - window_seconds

        records = self.get_records(since=since)

        stats = {
            "window_seconds": window_seconds,
            "total_records": len(records),
            "metrics": {}
        }

        # 按类型分组统计
        by_type = defaultdict(list)
        for record in records:
            by_type[record.metric_type].append(record.value)

        for metric_type, values in by_type.items():
            if values:
                stats["metrics"][metric_type.value] = {
                    "count": len(values),
                    "sum": sum(values),
                    "avg": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values)
                }

        return stats


class RealtimeDashboard:
    """
    实时监控仪表盘

    提供类似于 Entraly localhost:9378 的监控面板
    """

    def __init__(self, port: int = 9378):
        """初始化仪表盘"""
        self.port = port
        self.collector = MetricsCollector()
        self.cost_calculator = CostCalculator()
        self.sessions: Dict[str, SessionStats] = {}
        self.current_session_id: Optional[str] = None
        self._lock = threading.RLock()
        self._callbacks: List[Callable] = []
        self.is_running = False

        # Web 服务器（可选，可以用 Flask 或 FastAPI）
        self._server = None

    def start_session(self, session_id: Optional[str] = None) -> str:
        """
        开始会话

        Args:
            session_id: 会话 ID

        Returns:
            str: 会话 ID
        """
        session_id = session_id or f"session_{int(time.time() * 1000)}"

        stats = SessionStats(
            session_id=session_id,
            start_time=time.time()
        )

        with self._lock:
            self.sessions[session_id] = stats
            self.current_session_id = session_id

        self.collector.record(MetricType.API_CALLS, 1, {"session_id": session_id, "action": "session_start"})

        return session_id

    def end_session(self, session_id: Optional[str] = None) -> Optional[SessionStats]:
        """结束会话"""
        session_id = session_id or self.current_session_id
        if not session_id:
            return None

        with self._lock:
            if session_id in self.sessions:
                stats = self.sessions[session_id]
                self.collector.record(
                    MetricType.API_CALLS, 1,
                    {"session_id": session_id, "action": "session_end"}
                )
                return stats

        return None

    def record_api_call(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency: float,
        success: bool = True,
        session_id: Optional[str] = None
    ):
        """
        记录 API 调用

        Args:
            model: 模型名称
            input_tokens: 输入 token 数
            output_tokens: 输出 token 数
            latency: 延迟（毫秒）
            success: 是否成功
            session_id: 会话 ID
        """
        session_id = session_id or self.current_session_id
        cost = self.cost_calculator.calculate_cost(model, input_tokens, output_tokens)

        # 记录指标
        self.collector.record(MetricType.TOKEN_INPUT, input_tokens, {"model": model})
        self.collector.record(MetricType.TOKEN_OUTPUT, output_tokens, {"model": model})
        self.collector.record(MetricType.TOKEN_TOTAL, input_tokens + output_tokens, {"model": model})
        self.collector.record(MetricType.COST, cost, {"model": model})
        self.collector.record(MetricType.LATENCY, latency, {"model": model})

        if not success:
            self.collector.record(MetricType.ERRORS, 1, {"model": model})

        # 更新会话统计
        if session_id:
            with self._lock:
                if session_id in self.sessions:
                    stats = self.sessions[session_id]
                    stats.total_tokens += input_tokens + output_tokens
                    stats.input_tokens += input_tokens
                    stats.output_tokens += output_tokens
                    stats.total_cost += cost
                    stats.api_calls += 1
                    if not success:
                        stats.errors += 1

                    # 更新平均延迟
                    stats.avg_latency = (
                        (stats.avg_latency * (stats.api_calls - 1) + latency) / stats.api_calls
                    )

        # 触发回调
        self._notify_callbacks()

    def record_optimization(
        self,
        original_tokens: int,
        optimized_tokens: int,
        model: str,
        session_id: Optional[str] = None
    ):
        """
        记录优化效果

        Args:
            original_tokens: 原始 token 数
            optimized_tokens: 优化后 token 数
            model: 模型名称
            session_id: 会话 ID
        """
        savings = self.cost_calculator.calculate_savings(original_tokens, optimized_tokens, model)

        self.collector.record(
            MetricType.COST_SAVINGS,
            savings,
            {
                "model": model,
                "original_tokens": original_tokens,
                "optimized_tokens": optimized_tokens,
                "savings_percent": (original_tokens - optimized_tokens) / original_tokens * 100 if original_tokens > 0 else 0
            }
        )

        # 更新会话统计
        if session_id:
            with self._lock:
                if session_id in self.sessions:
                    self.sessions[session_id].cost_savings += savings

    def subscribe(self, callback: Callable):
        """订阅更新"""
        self._callbacks.append(callback)

    def unsubscribe(self, callback: Callable):
        """取消订阅"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def _notify_callbacks(self):
        """通知订阅者"""
        for callback in self._callbacks:
            try:
                callback(self.get_snapshot())
            except Exception as e:
                print(f"[Dashboard] 回调错误: {e}")

    def get_snapshot(self) -> Dict[str, Any]:
        """获取当前快照"""
        with self._lock:
            current_stats = None
            if self.current_session_id and self.current_session_id in self.sessions:
                current_stats = self.sessions[self.current_session_id]

            return {
                "timestamp": time.time(),
                "current_session": self._stats_to_dict(current_stats) if current_stats else None,
                "total_sessions": len(self.sessions),
                "recent_stats": self.collector.get_stats(window_seconds=60)
            }

    def _stats_to_dict(self, stats: SessionStats) -> Dict[str, Any]:
        """将会话统计转换为字典"""
        if not stats:
            return {}

        return {
            "session_id": stats.session_id,
            "duration_seconds": time.time() - stats.start_time,
            "total_tokens": stats.total_tokens,
            "input_tokens": stats.input_tokens,
            "output_tokens": stats.output_tokens,
            "total_cost": stats.total_cost,
            "cost_savings": stats.cost_savings,
            "api_calls": stats.api_calls,
            "errors": stats.errors,
            "avg_latency_ms": stats.avg_latency,
            "cost_per_call": stats.total_cost / stats.api_calls if stats.api_calls > 0 else 0
        }

    def get_dashboard_data(self) -> Dict[str, Any]:
        """
        获取仪表盘数据

        类似于 Entraly 的 localhost:9378 返回的数据格式
        """
        snapshot = self.get_snapshot()
        stats = snapshot["current_session"]

        # 计算汇总数据
        total_cost = 0.0
        total_savings = 0.0
        total_tokens = 0

        for session in self.sessions.values():
            total_cost += session.total_cost
            total_savings += session.cost_savings
            total_tokens += session.total_tokens

        return {
            "dashboard": {
                "title": "LivingTree AI Monitor",
                "version": "1.0.0",
                "refresh_rate_ms": 1000
            },
            "current": stats or {},
            "summary": {
                "active_sessions": len(self.sessions),
                "total_cost": total_cost,
                "total_savings": total_savings,
                "total_tokens": total_tokens,
                "savings_percent": total_savings / total_cost * 100 if total_cost > 0 else 0
            },
            "realtime": {
                "tokens_per_minute": self._calculate_rate(MetricType.TOKEN_TOTAL, 60),
                "cost_per_minute": self._calculate_rate(MetricType.COST, 60),
                "api_calls_per_minute": self._calculate_rate(MetricType.API_CALLS, 60),
                "error_rate": self._calculate_error_rate(60)
            },
            "chart_data": self._get_chart_data()
        }

    def _calculate_rate(self, metric_type: MetricType, window_seconds: int) -> float:
        """计算速率"""
        records = self.collector.get_records(metric_type=metric_type, since=time.time() - window_seconds)
        if not records:
            return 0.0
        return sum(r.value for r in records) / (window_seconds / 60)

    def _calculate_error_rate(self, window_seconds: int) -> float:
        """计算错误率"""
        now = time.time()
        since = now - window_seconds

        errors = len(self.collector.get_records(metric_type=MetricType.ERRORS, since=since))
        total = len(self.collector.get_records(metric_type=MetricType.API_CALLS, since=since))

        return errors / total if total > 0 else 0.0

    def _get_chart_data(self) -> Dict[str, List]:
        """获取图表数据"""
        # 最近 5 分钟的数据，每 10 秒一个点
        points = []
        now = time.time()

        for i in range(30):
            t = now - (29 - i) * 10
            records = self.collector.get_records(since=t, limit=100)

            point = {
                "timestamp": t,
                "tokens": sum(r.value for r in records if r.metric_type == MetricType.TOKEN_TOTAL),
                "cost": sum(r.value for r in records if r.metric_type == MetricType.COST),
                "api_calls": sum(r.value for r in records if r.metric_type == MetricType.API_CALLS)
            }
            points.append(point)

        return {
            "tokens": [p["tokens"] for p in points],
            "cost": [p["cost"] for p in points],
            "api_calls": [p["api_calls"] for p in points],
            "timestamps": [datetime.fromtimestamp(p["timestamp"]).strftime("%H:%M:%S") for p in points]
        }

    def export_json(self) -> str:
        """导出为 JSON 格式"""
        return json.dumps(self.get_dashboard_data(), indent=2, ensure_ascii=False)

    def export_html(self) -> str:
        """导出为 HTML 仪表盘页面"""
        data = self.get_dashboard_data()
        summary = data["summary"]
        realtime = data["realtime"]

        return f"""<!DOCTYPE html>
<html>
<head>
    <title>LivingTree AI Monitor</title>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background: #1a1a2e;
            color: #eee;
        }}
        .dashboard {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        h1 {{
            color: #00d4ff;
            text-align: center;
        }}
        .metrics {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .metric-card {{
            background: #16213e;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }}
        .metric-title {{
            font-size: 14px;
            color: #888;
            margin-bottom: 10px;
        }}
        .metric-value {{
            font-size: 32px;
            font-weight: bold;
            color: #00d4ff;
        }}
        .metric-sub {{
            font-size: 12px;
            color: #666;
            margin-top: 5px;
        }}
        .chart {{
            background: #16213e;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 30px;
        }}
        .chart-title {{
            font-size: 18px;
            margin-bottom: 15px;
            color: #fff;
        }}
        .chart-canvas {{
            height: 200px;
            background: #0f3460;
            border-radius: 8px;
        }}
        .status {{
            display: flex;
            gap: 10px;
            align-items: center;
        }}
        .status-dot {{
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #4caf50;
        }}
        .status-dot.error {{
            background: #f44336;
        }}
    </style>
</head>
<body>
    <div class="dashboard">
        <h1>LivingTree AI Monitor</h1>

        <div class="status">
            <div class="status-dot"></div>
            <span>System Online | Port {self.port}</span>
        </div>

        <div class="metrics">
            <div class="metric-card">
                <div class="metric-title">Total Cost</div>
                <div class="metric-value">${{summary['total_cost']:.4f}}</div>
                <div class="metric-sub">Total spent</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Cost Savings</div>
                <div class="metric-value" style="color: #4caf50;">${{summary['total_savings']:.4f}}</div>
                <div class="metric-sub">Saved {{summary['savings_percent']:.1f}}%</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Total Tokens</div>
                <div class="metric-value">{{summary['total_tokens']:,}}</div>
                <div class="metric-sub">{{realtime['tokens_per_minute']:.0f}} / min</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">API Calls</div>
                <div class="metric-value">{{realtime['api_calls_per_minute']:.1f}}</div>
                <div class="metric-sub">calls / min</div>
            </div>
        </div>

        <div class="chart">
            <div class="chart-title">Token Usage (Last 5 min)</div>
            <div class="chart-canvas" id="chart"></div>
        </div>

        <div style="text-align: center; color: #666; font-size: 12px;">
            Data updates every second | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
    </div>

    <script>
        // Simple chart visualization
        const data = {json.dumps(data['chart_data']['tokens'])};
        const canvas = document.getElementById('chart');
        const ctx = canvas.getContext('2d');

        function draw() {{
            ctx.fillStyle = '#0f3460';
            ctx.fillRect(0, 0, canvas.width, canvas.height);

            const max = Math.max(...data);
            const step = canvas.width / data.length;

            ctx.strokeStyle = '#00d4ff';
            ctx.lineWidth = 2;
            ctx.beginPath();

            data.forEach((val, i) => {{
                const x = i * step;
                const y = canvas.height - (val / max * canvas.height);
                if (i === 0) {{
                    ctx.moveTo(x, y);
                }} else {{
                    ctx.lineTo(x, y);
                }}
            }});

            ctx.stroke();
        }}

        draw();
    </script>
</body>
</html>"""


# 全局实例
_global_dashboard: Optional[RealtimeDashboard] = None


def get_dashboard(port: int = 9378) -> RealtimeDashboard:
    """获取仪表盘实例"""
    global _global_dashboard
    if _global_dashboard is None:
        _global_dashboard = RealtimeDashboard(port)
    return _global_dashboard
