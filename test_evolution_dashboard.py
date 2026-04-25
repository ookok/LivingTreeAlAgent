#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Evolution Dashboard 测试脚本
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from ui.evolution_dashboard import create_evolution_dashboard


def test_dashboard():
    """测试 Dashboard"""
    print("=" * 60)
    print("Evolution Dashboard 测试")
    print("=" * 60)
    
    app = QApplication(sys.argv)
    
    # 创建 Dashboard（不连接引擎，使用模拟数据）
    dashboard = create_evolution_dashboard()
    
    print("\n✅ Dashboard 创建成功!")
    print("\n📊 功能验证:")
    print("  • 概览标签页 - 指标卡片、进度环、活动列表")
    print("  • 洞察标签页 - 学习洞察卡片")
    print("  • 模式标签页 - 时序/共现/因果/异常模式")
    print("  • 决策标签页 - 决策时间线")
    print("  • 分析标签页 - 根因分析")
    
    # 显示窗口
    dashboard.resize(1200, 800)
    dashboard.show()
    
    print("\n🚀 Dashboard 已启动，按 Ctrl+C 退出")
    print("=" * 60)
    
    # 带引擎的测试（可选）
    try:
        from client.src.business.evolution_engine import create_evolution_engine
        
        print("\n📡 尝试连接 Evolution Engine...")
        engine = create_evolution_engine(project_root=".")
        
        # 更新 dashboard
        dashboard.set_engine(engine)
        
        # 触发刷新
        dashboard.refresh()
        
        print("✅ Evolution Engine 连接成功!")
        print(f"\n📈 当前统计:")
        print(f"  • 总扫描: {dashboard.total_scans_card._value}")
        print(f"  • 总提案: {dashboard.total_proposals_card._value}")
        print(f"  • 成功率: {dashboard.success_rate_card._value}")
        print(f"  • 总信号: {dashboard.total_signals_card._value}")
        
    except Exception as e:
        print(f"\n⚠️  Evolution Engine 连接失败: {e}")
        print("   Dashboard 将以演示模式运行")
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(test_dashboard())
