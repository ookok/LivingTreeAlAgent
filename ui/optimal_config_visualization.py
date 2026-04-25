# -*- coding: utf-8 -*-
"""
配置可视化组件
==============

提供配置的可视化展示:
1. 雷达图 - 多维度配置对比
2. 进度条 - 配置值可视化
3. 历史趋势图 - 配置变化跟踪

Author: LivingTreeAI Team
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple
from collections import deque


# ── 维度定义 ───────────────────────────────────────────────────────────────


@dataclass
class ConfigDimension:
    """配置维度"""
    name: str
    value: float
    min_value: float = 0
    max_value: float = 10
    unit: str = ""
    
    @property
    def normalized(self) -> float:
        """归一化值 (0-1)"""
        if self.max_value == self.min_value:
            return 0.5
        return (self.value - self.min_value) / (self.max_value - self.min_value)


@dataclass 
class ConfigRadarData:
    """雷达图数据"""
    dimensions: List[ConfigDimension]
    label: str = ""
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'label': self.label,
            'timestamp': self.timestamp,
            'dimensions': [
                {'name': d.name, 'value': d.value, 'normalized': d.normalized}
                for d in self.dimensions
            ]
        }


@dataclass
class ConfigHistoryPoint:
    """历史数据点"""
    timestamp: float
    config: Dict[str, Any]
    score: Optional[float] = None


# ── 配置可视化器 ──────────────────────────────────────────────────────────


class ConfigVisualizer:
    """
    配置可视化器
    
    功能：
    1. 雷达图数据生成
    2. 进度条数据
    3. 历史趋势
    """
    
    # 默认维度
    DEFAULT_DIMENSIONS = [
        ('depth', '深度', 1, 10),
        ('timeout', '超时', 10, 300),
        ('max_retries', '重试', 0, 10),
        ('context_limit', '上下文', 1024, 65536),
        ('max_tokens', 'Token', 256, 32768),
        ('temperature', '温度', 0.0, 2.0),
    ]
    
    def __init__(self):
        # 历史记录
        self._history: deque = deque(maxlen=100)
        
    def create_radar_data(
        self, 
        config: Dict[str, Any], 
        label: str = "",
    ) -> ConfigRadarData:
        """
        创建雷达图数据
        
        Args:
            config: 配置字典
            label: 标签
            
        Returns:
            ConfigRadarData: 雷达图数据
        """
        dimensions = []
        
        for key, name, min_val, max_val in self.DEFAULT_DIMENSIONS:
            if key in config:
                value = config[key]
                # 归一化处理
                if key in ('context_limit', 'max_tokens'):
                    # 对数刻度
                    import math
                    value = math.log2(value + 1) if value > 0 else 0
                    min_val = math.log2(min_val + 1)
                    max_val = math.log2(max_val + 1)
                
                dimensions.append(ConfigDimension(
                    name=name,
                    value=value,
                    min_value=min_val,
                    max_value=max_val,
                ))
        
        return ConfigRadarData(dimensions=dimensions, label=label)
    
    def create_progress_data(
        self, 
        config: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        创建进度条数据
        
        Args:
            config: 配置字典
            
        Returns:
            List[Dict]: 进度条数据列表
        """
        bars = []
        
        # Depth 进度
        if 'depth' in config:
            bars.append({
                'name': '深度 (Depth)',
                'value': config['depth'],
                'max': 10,
                'percent': config['depth'] * 10,
                'color': self._get_depth_color(config['depth']),
            })
        
        # Timeout 进度
        if 'timeout' in config:
            timeout = config['timeout']
            bars.append({
                'name': '超时 (Timeout)',
                'value': timeout,
                'max': 300,
                'percent': min(100, timeout / 300 * 100),
                'color': '#3B82F6',
            })
        
        # Context 进度
        if 'context_limit' in config:
            ctx = config['context_limit']
            bars.append({
                'name': '上下文 (Context)',
                'value': ctx,
                'max': 65536,
                'percent': min(100, ctx / 65536 * 100),
                'color': '#8B5CF6',
            })
        
        return bars
    
    def _get_depth_color(self, depth: int) -> str:
        """获取 depth 对应颜色"""
        if depth <= 2:
            return '#22C55E'  # 绿色
        elif depth <= 4:
            return '#84CC16'  # 黄绿
        elif depth <= 6:
            return '#3B82F6'  # 蓝色
        elif depth <= 8:
            return '#F59E0B'  # 橙色
        else:
            return '#EF4444'  # 红色
    
    def record_history(
        self, 
        config: Dict[str, Any], 
        score: Optional[float] = None,
    ):
        """记录历史配置"""
        self._history.append(ConfigHistoryPoint(
            timestamp=time.time(),
            config=config.copy(),
            score=score,
        ))
    
    def get_trend_data(
        self, 
        key: str,
        limit: int = 20,
    ) -> List[Tuple[float, float]]:
        """
        获取趋势数据
        
        Args:
            key: 配置键
            limit: 限制数量
            
        Returns:
            List[Tuple[float, float]]: (timestamp, value) 列表
        """
        points = []
        for point in list(self._history)[-limit:]:
            if key in point.config:
                points.append((point.timestamp, point.config[key]))
        return points
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        if not self._history:
            return {
                'count': 0,
                'avg_depth': 0,
                'avg_timeout': 0,
            }
        
        depths = [p.config.get('depth', 0) for p in self._history if 'depth' in p.config]
        timeouts = [p.config.get('timeout', 0) for p in self._history if 'timeout' in p.config]
        
        return {
            'count': len(self._history),
            'avg_depth': sum(depths) / len(depths) if depths else 0,
            'avg_timeout': sum(timeouts) / len(timeouts) if timeouts else 0,
            'min_depth': min(depths) if depths else 0,
            'max_depth': max(depths) if depths else 0,
        }


# ── ASCII 雷达图 ──────────────────────────────────────────────────────────


class ASCIIDashboard:
    """ASCII 风格仪表盘"""
    
    def __init__(self, width: int = 60):
        self.width = width
    
    def render_radar(self, data: ConfigRadarData) -> str:
        """渲染雷达图 (ASCII)"""
        lines = []
        
        # 标题
        lines.append(f"[Radar] {data.label or 'Config'}")
        lines.append("=" * self.width)
        
        # 维度条形图
        for dim in data.dimensions:
            bar_width = int(dim.normalized * (self.width - 25))
            bar = "#" * bar_width
            spaces = " " * (self.width - 25 - bar_width)
            
            # 简化名称
            name = dim.name[:6]
            lines.append(f"{name:<6} {dim.value:>6.1f} |{bar}{spaces}|")
        
        lines.append("=" * self.width)
        
        return "\n".join(lines)
    
    def render_progress_bars(self, bars: List[Dict[str, Any]]) -> str:
        """渲染进度条 (ASCII)"""
        lines = []
        
        lines.append("[PROGRESS] Progress Bars")
        lines.append("=" * self.width)
        
        for bar in bars:
            filled = int(bar['percent'] / 100 * (self.width - 30))
            bar_str = "#" * filled + "-" * (self.width - 30 - filled)
            lines.append(f"{bar['name']:<15} [{bar_str}] {bar['percent']:>5.1f}%")
        
        lines.append("=" * self.width)
        
        return "\n".join(lines)
    
    def render_trend(
        self, 
        points: List[Tuple[float, float]], 
        key: str,
    ) -> str:
        """渲染趋势图 (ASCII)"""
        if not points:
            return f"No data for {key}"
        
        lines = []
        lines.append(f"[TREND] Trend: {key}")
        lines.append("=" * self.width)
        
        # 简化时间显示
        values = [v for _, v in points]
        min_val = min(values)
        max_val = max(values)
        
        if max_val == min_val:
            max_val = min_val + 1
        
        # 渲染点
        for timestamp, value in points:
            # 归一化
            norm = (value - min_val) / (max_val - min_val)
            pos = int(norm * (self.width - 20))
            
            bar = " " * pos + "*"
            time_str = time.strftime("%H:%M", time.localtime(timestamp))
            lines.append(f"{time_str} {bar} {value:.1f}")
        
        lines.append("=" * self.width)
        
        return "\n".join(lines)
    
    def render_full_dashboard(
        self,
        config: Dict[str, Any],
        history: List[Dict[str, Any]],
    ) -> str:
        """渲染完整仪表盘"""
        lines = []
        
        # 标题
        lines.append("╔" + "=" * 58 + "╗")
        lines.append("║" + " Optimal Config Dashboard ".center(58) + "║")
        lines.append("╚" + "=" * 58 + "╝")
        
        # 当前配置
        lines.append("\n[CONFIG] Current Config:")
        lines.append("-" * 60)
        for key, value in config.items():
            lines.append(f"  {key:<20} {value}")
        
        # 雷达图
        radar_data = visualizer.create_radar_data(config)
        lines.append("\n" + dashboard.render_radar(radar_data))
        
        # 进度条
        progress_data = visualizer.create_progress_data(config)
        lines.append("\n" + dashboard.render_progress_bars(progress_data))
        
        return "\n".join(lines)


# ── 导出格式 ──────────────────────────────────────────────────────────────


class ConfigExporter:
    """配置导出器"""
    
    @staticmethod
    def to_json(config: Dict[str, Any]) -> str:
        """导出为 JSON"""
        return json.dumps(config, indent=2, ensure_ascii=False)
    
    @staticmethod
    def to_yaml(config: Dict[str, Any]) -> str:
        """导出为 YAML (简化版)"""
        lines = []
        for key, value in config.items():
            if isinstance(value, bool):
                lines.append(f"{key}: {'true' if value else 'false'}")
            elif isinstance(value, (int, float)):
                lines.append(f"{key}: {value}")
            elif isinstance(value, str):
                lines.append(f"{key}: '{value}'")
            elif isinstance(value, list):
                lines.append(f"{key}:")
                for item in value:
                    lines.append(f"  - {item}")
            else:
                lines.append(f"{key}: {value}")
        return "\n".join(lines)
    
    @staticmethod
    def to_python(config: Dict[str, Any]) -> str:
        """导出为 Python 代码"""
        return f"config = {json.dumps(config, indent=4)}"


# ── 工厂函数 ─────────────────────────────────────────────────────────────


def create_visualizer() -> ConfigVisualizer:
    """创建可视化器"""
    return ConfigVisualizer()


def create_dashboard(width: int = 60) -> ASCIIDashboard:
    """创建 ASCII 仪表盘"""
    return ASCIIDashboard(width=width)


# ── 测试入口 ─────────────────────────────────────────────────────────────


if __name__ == "__main__":
    print("=" * 60)
    print("配置可视化组件测试")
    print("=" * 60)
    
    # 测试配置
    config = {
        'depth': 7,
        'timeout': 120.0,
        'max_retries': 4,
        'context_limit': 16384,
        'max_tokens': 8192,
        'temperature': 0.8,
        'use_reasoning': True,
        'use_execution': False,
    }
    
    # 可视化器
    visualizer = create_visualizer()
    
    print("\n[1] 雷达图数据")
    radar_data = visualizer.create_radar_data(config, "Test Config")
    for dim in radar_data.dimensions:
        print(f"  {dim.name}: {dim.value:.2f} ({dim.normalized:.1%})")
    
    print("\n[2] 进度条数据")
    bars = visualizer.create_progress_data(config)
    for bar in bars:
        print(f"  {bar['name']}: {bar['percent']:.1f}%")
    
    # 记录历史
    print("\n[3] 历史趋势")
    for i in range(5):
        test_config = config.copy()
        test_config['depth'] = 3 + i
        visualizer.record_history(test_config, score=0.5 + i * 0.1)
    
    trend = visualizer.get_trend_data('depth')
    print(f"  Recorded {len(trend)} points")
    
    # ASCII 仪表盘
    print("\n[4] ASCII 仪表盘")
    dashboard = create_dashboard(50)
    
    radar_text = dashboard.render_radar(radar_data)
    print(radar_text)
    
    progress_text = dashboard.render_progress_bars(bars)
    print(progress_text)
    
    # 完整仪表盘
    print("\n[5] 完整仪表盘")
    full_text = dashboard.render_full_dashboard(config, [])
    print(full_text)
    
    # 导出
    print("\n[6] 导出格式")
    print("\nJSON:")
    print(ConfigExporter.to_json(config)[:100] + "...")
    
    print("\nYAML:")
    print(ConfigExporter.to_yaml(config))
    
    # 统计
    print("\n[7] 统计信息")
    stats = visualizer.get_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
