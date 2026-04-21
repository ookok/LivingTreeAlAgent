#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Diagnosis Dashboard - 诊断仪表板
=================================

功能：
1. 系统健康度概览
2. 错误趋势分析
3. 热点问题展示
4. 自动修复统计

Usage:
    dashboard = DiagnosisDashboard()
    html = dashboard.generate_html()

    # 或者在 PyQt6 中使用
    widget = dashboard.get_widget()
"""

import os
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from pathlib import Path

from .structured_logger import ErrorCategory, get_logger, _LOG_DIR
from .diagnosis_engine import DiagnosisEngine, get_diagnosis_engine
from .auto_fix import AutoFixSystem, get_fix_system
from .task_monitor import TaskMonitor, get_task_monitor


class DiagnosisDashboard:
    """
    诊断仪表板

    生成可视化仪表板的 HTML 或 PyQt6 组件
    """

    def __init__(self):
        self.logger = get_logger("dashboard")

        # 子系统引用
        self.diagnosis_engine = get_diagnosis_engine()
        self.fix_system = get_fix_system()
        self.task_monitor = get_task_monitor()

        # 日志目录
        self.log_dir = _LOG_DIR

    def generate_html(self, title: str = "LivingTreeAI Diagnosis Dashboard") -> str:
        """
        生成 HTML 仪表板

        Returns:
            str HTML 内容
        """
        # 收集数据
        stats = self._collect_stats()
        recent_errors = self._get_recent_errors()
        health_summary = self.task_monitor.get_statistics()
        fix_stats = self.fix_system.knowledge_base.strategy_scores

        html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>{title}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f1419; color: #e7e9ea; padding: 20px; }}
.container {{ max-width: 1400px; margin: 0 auto; }}
.header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; }}
h1 {{ color: #2e7d32; font-size: 24px; }}
.timestamp {{ color: #8899a6; font-size: 14px; }}

.stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 30px; }}
.stat-card {{ background: #192734; border-radius: 12px; padding: 20px; }}
.stat-card .label {{ color: #8899a6; font-size: 12px; text-transform: uppercase; margin-bottom: 8px; }}
.stat-card .value {{ font-size: 32px; font-weight: 600; }}
.stat-card .sub {{ color: #8899a6; font-size: 12px; margin-top: 4px; }}
.stat-card.green .value {{ color: #2e7d32; }}
.stat-card.yellow .value {{ color: #f5a623; }}
.stat-card.red .value {{ color: #e02432; }}
.stat-card.blue .value {{ color: #1d9bf0; }}

.health-bar {{ display: flex; height: 8px; border-radius: 4px; overflow: hidden; background: #22303c; margin-top: 12px; }}
.health-segment {{ transition: width 0.3s; }}

.section {{ background: #192734; border-radius: 12px; padding: 20px; margin-bottom: 20px; }}
.section-title {{ font-size: 16px; font-weight: 600; margin-bottom: 16px; color: #e7e9ea; }}

.error-list {{ max-height: 300px; overflow-y: auto; }}
.error-item {{ display: flex; align-items: center; padding: 12px; border-bottom: 1px solid #22303c; }}
.error-item:last-child {{ border-bottom: none; }}
.error-code {{ background: #22303c; padding: 4px 8px; border-radius: 4px; font-family: monospace; font-size: 12px; margin-right: 12px; }}
.error-category {{ color: #8899a6; font-size: 13px; flex: 1; }}
.error-time {{ color: #8899a6; font-size: 12px; }}

.chart-container {{ height: 200px; background: #22303c; border-radius: 8px; padding: 16px; }}
.bar-chart {{ display: flex; align-items: flex-end; justify-content: space-around; height: 160px; padding-top: 20px; }}
.bar {{ width: 40px; background: linear-gradient(to top, #2e7d32, #4caf50); border-radius: 4px 4px 0 0; transition: height 0.3s; position: relative; }}
.bar-label {{ position: absolute; bottom: -24px; left: 50%; transform: translateX(-50%); font-size: 11px; color: #8899a6; white-space: nowrap; }}
.bar-value {{ position: absolute; top: -20px; left: 50%; transform: translateX(-50%); font-size: 11px; color: #e7e9ea; }}

.alert-box {{ background: #2d1f1f; border: 1px solid #e02432; border-radius: 8px; padding: 16px; margin-bottom: 16px; }}
.alert-box.warning {{ background: #2d2a1f; border-color: #f5a623; }}
.alert-box.info {{ background: #1f2d3d; border-color: #1d9bf0; }}
.alert-title {{ font-weight: 600; margin-bottom: 8px; }}
.alert-box.critical .alert-title {{ color: #e02432; }}
.alert-box.warning .alert-title {{ color: #f5a623; }}
.alert-box.info .alert-title {{ color: #1d9bf0; }}
.alert-content {{ font-size: 14px; color: #8899a6; }}

.btn {{ background: #2e7d32; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 14px; }}
.btn:hover {{ background: #388e3c; }}
.btn:disabled {{ background: #5a7d62; cursor: not-allowed; }}

.refresh-info {{ text-align: center; color: #8899a6; font-size: 12px; margin-top: 20px; }}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>[TREE] LivingTreeAI 诊断仪表板</h1>
        <span class="timestamp">更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</span>
    </div>

    <!-- 概览统计 -->
    <div class="stats-grid">
        <div class="stat-card green">
            <div class="label">健康任务</div>
            <div class="value">{health_summary['active_tasks']}</div>
            <div class="sub">当前运行</div>
        </div>
        <div class="stat-card blue">
            <div class="label">已完成</div>
            <div class="value">{stats['completed']}</div>
            <div class="sub">历史统计</div>
        </div>
        <div class="stat-card yellow">
            <div class="label">待处理</div>
            <div class="value">{stats['pending']}</div>
            <div class="sub">需关注</div>
        </div>
        <div class="stat-card red">
            <div class="label">失败/超时</div>
            <div class="value">{stats['failed']}</div>
            <div class="sub">需干预</div>
        </div>
    </div>

    <!-- 健康度指示器 -->
    <div class="section">
        <div class="section-title">系统健康度</div>
        <div class="health-bar">
            <div class="health-segment" style="width: {health_summary['health_pct']}%; background: #2e7d32;"></div>
            <div class="health-segment" style="width: {health_summary['warning_pct']}%; background: #f5a623;"></div>
            <div class="health-segment" style="width: {health_summary['critical_pct']}%; background: #e02432;"></div>
        </div>
        <div style="display: flex; justify-content: space-between; margin-top: 8px; font-size: 12px; color: #8899a6;">
            <span>健康 {health_summary['health_pct']}%</span>
            <span>警告 {health_summary['warning_pct']}%</span>
            <span>危险 {health_summary['critical_pct']}%</span>
        </div>
    </div>

    <!-- 告警信息 -->
    {self._generate_alerts(stats)}

    <!-- 错误分布 -->
    <div class="section">
        <div class="section-title">错误分类分布</div>
        <div class="chart-container">
            <div class="bar-chart">
                {self._generate_error_bars(stats)}
            </div>
        </div>
    </div>

    <!-- 最近错误 -->
    <div class="section">
        <div class="section-title">最近错误</div>
        <div class="error-list">
            {self._generate_error_list(recent_errors)}
        </div>
    </div>

    <!-- 修复统计 -->
    <div class="section">
        <div class="section-title">自动修复统计</div>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px;">
            {self._generate_fix_stats(fix_stats)}
        </div>
    </div>

    <div class="refresh-info">
        页面将每 30 秒自动刷新 | 最后更新: {datetime.now().strftime('%H:%M:%S')}
    </div>
</div>

<script>
// 自动刷新
setInterval(() => location.reload(), 30000);
</script>
</body>
</html>"""

        return html

    def _collect_stats(self) -> Dict[str, Any]:
        """收集统计数据"""
        monitor_stats = self.task_monitor.get_statistics()
        diag_stats = self.diagnosis_engine.get_statistics()

        total = monitor_stats['completed_tasks'] + monitor_stats['failed_tasks'] + monitor_stats['timed_out_tasks']
        if total == 0:
            completed_pct, failed_pct, pending_pct = 0, 0, 100
        else:
            completed_pct = monitor_stats['completed_tasks'] / total * 100
            failed_pct = (monitor_stats['failed_tasks'] + monitor_stats['timed_out_tasks']) / total * 100
            pending_pct = 100 - completed_pct - failed_pct

        # 错误分类统计
        category_dist = diag_stats.get('category_distribution', {})

        return {
            'completed': monitor_stats['completed_tasks'],
            'failed': monitor_stats['failed_tasks'] + monitor_stats['timed_out_tasks'],
            'pending': monitor_stats['active_tasks'],
            'total': total,
            'completed_pct': completed_pct,
            'failed_pct': failed_pct,
            'pending_pct': pending_pct,
            'health_pct': max(0, 100 - failed_pct - pending_pct * 0.5),
            'warning_pct': pending_pct * 0.5,
            'critical_pct': failed_pct,
            'category_distribution': category_dist,
        }

    def _get_recent_errors(self, limit: int = 10) -> List[Dict]:
        """获取最近错误"""
        errors = []
        error_file = self.log_dir / "diagnostic.jsonl"

        if error_file.exists():
            try:
                with open(error_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    for line in lines[-limit:]:
                        try:
                            errors.append(json.loads(line))
                        except:
                            pass
            except:
                pass

        return errors

    def _generate_alerts(self, stats: Dict) -> str:
        """生成告警框"""
        alerts = []

        if stats['failed'] > 0:
            alerts.append(f"""
            <div class="alert-box critical">
                <div class="alert-title">⚠ 有任务失败需要处理</div>
                <div class="alert-content">最近有 {stats['failed']} 个任务失败或超时，建议检查任务详情并手动干预。</div>
            </div>
            """)

        if stats['pending'] > 5:
            alerts.append(f"""
            <div class="alert-box warning">
                <div class="alert-title">📋 较多任务等待中</div>
                <div class="alert-content">当前有 {stats['pending']} 个任务正在运行或等待中。</div>
            </div>
            """)

        if stats['completed_pct'] > 90:
            alerts.append(f"""
            <div class="alert-box info">
                <div class="alert-title">✓ 系统运行良好</div>
                <div class="alert-content">任务成功率达到 {stats['completed_pct']:.1f}%。</div>
            </div>
            """)

        return ''.join(alerts) if alerts else ''

    def _generate_error_bars(self, stats: Dict) -> str:
        """生成错误分布柱状图"""
        categories = {
            'NETWORK': '网络',
            'RESOURCE': '资源',
            'AI_MODEL': 'AI模型',
            'TIMEOUT': '超时',
            'CONFIG': '配置',
            'OTHER': '其他'
        }

        dist = stats.get('category_distribution', {})
        total = sum(dist.values()) if dist else 1
        max_val = max(dist.values()) if dist else 1

        bars = []
        for cat_key, cat_name in categories.items():
            count = dist.get(cat_key, 0)
            height = (count / max_val * 100) if max_val > 0 else 0
            bars.append(f"""
            <div class="bar" style="height: {height}%;">
                <span class="bar-value">{count}</span>
                <span class="bar-label">{cat_name}</span>
            </div>
            """)

        return ''.join(bars)

    def _generate_error_list(self, errors: List) -> str:
        """生成错误列表"""
        if not errors:
            return '<div style="color: #8899a6; padding: 20px; text-align: center;">暂无错误记录</div>'

        items = []
        for err in errors[:10]:
            code = err.get('error_code', 'N/A')
            cat = err.get('error_category', 'UNKNOWN')
            time = err.get('timestamp', '')[:19] if err.get('timestamp') else ''
            msg = err.get('message', '')[:60]

            items.append(f"""
            <div class="error-item">
                <span class="error-code">{code}</span>
                <span class="error-category">[{cat}] {msg}</span>
                <span class="error-time">{time}</span>
            </div>
            """)

        return ''.join(items)

    def _generate_fix_stats(self, fix_stats: Dict) -> str:
        """生成修复统计"""
        if not fix_stats:
            return '<div style="color: #8899a6;">暂无修复记录</div>'

        stats_html = []
        for strategy, (success, total) in list(fix_stats.items())[:6]:
            rate = (success / total * 100) if total > 0 else 0
            stats_html.append(f"""
            <div style="background: #22303c; padding: 12px; border-radius: 8px; text-align: center;">
                <div style="font-size: 12px; color: #8899a6;">{strategy.value}</div>
                <div style="font-size: 20px; color: #2e7d32;">{rate:.0f}%</div>
                <div style="font-size: 11px; color: #8899a6;">{success}/{total}</div>
            </div>
            """)

        return ''.join(stats_html)

    def save_html(self, output_path: Optional[str] = None):
        """保存 HTML 到文件"""
        if output_path is None:
            output_path = self.log_dir / "diagnosis_dashboard.html"

        html = self.generate_html()
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)

        self.logger.info(f"Dashboard saved to {output_path}")
        return str(output_path)


def generate_dashboard_html() -> str:
    """便捷函数：生成仪表板 HTML"""
    dashboard = DiagnosisDashboard()
    return dashboard.generate_html()


if __name__ == "__main__":
    # 测试仪表板
    dashboard = DiagnosisDashboard()
    html = dashboard.generate_html()

    # 保存
    output_path = dashboard.save_html()
    print(f"Dashboard generated: {output_path}")
    print(f"Size: {len(html)} bytes")
