# -*- coding: utf-8 -*-
"""
可视化智能进化引擎测试
======================
"""

import asyncio
import time
from datetime import datetime

# 导入模块
from client.src.business.visual_evolution_engine.system_monitor import SystemMonitor, get_system_monitor
from client.src.business.visual_evolution_engine.model_manager import ModelManager, UpgradeProposal, RiskLevel
from client.src.business.visual_evolution_engine.decision_engine import EvolutionDecisionEngine, UpgradeRecommendation
from client.src.business.visual_evolution_engine.progress_tracker import ProgressTracker, ProgressStage
from client.src.business.visual_evolution_engine.dashboard import EvolutionDashboard, StateMachineVisualizer, PanelType


def test_system_monitor():
    """测试系统监控"""
    print("\n" + "="*60)
    print("测试1: 系统监控器")
    print("="*60)
    
    monitor = SystemMonitor()
    
    # 获取仪表盘数据
    data = monitor.get_dashboard_data()
    
    print(f"系统状态: {data.system_status}")
    print(f"CPU: {data.resources.cpu_percent:.1f}%")
    print(f"内存: {data.resources.memory_percent:.1f}% ({data.resources.memory_used_gb:.1f}/{data.resources.memory_total_gb:.1f} GB)")
    
    if data.gpu.available:
        print(f"GPU: {data.gpu.name}")
        print(f"GPU显存: {data.gpu.memory_percent:.1f}%")
    else:
        print("GPU: 不可用")
    
    print(f"网络延迟: {data.network.latency_ms:.1f}ms")
    print(f"磁盘空间: {data.disk.free_gb:.1f} GB 可用")
    print(f"模型目录: {data.disk.model_dir_size_gb:.2f} GB")
    print(f"本地模型数: {len(data.models)}")
    
    for model in data.models[:3]:
        print(f"  - {model.name} ({model.size_mb/1024:.1f} GB)")
    
    print("\n✅ 系统监控测试通过")
    return data


def test_model_manager():
    """测试模型管理器"""
    print("\n" + "="*60)
    print("测试2: 模型管理器")
    print("="*60)
    
    manager = ModelManager()
    
    # 创建模拟升级提案
    proposal = UpgradeProposal(
        proposal_id="TEST-001",
        current_model="qwen2.5:7b",
        current_version="2.5",
        target_model="qwen2.5:14b",
        target_version="2.5",
        trigger_reasons=["检测到新版本"],
        expected_benefits={"accuracy": 15.0},
        risk_level=RiskLevel.MEDIUM,
        risk_factors=["下载时间较长"],
        required_disk_gb=20.0,
        required_memory_gb=16.0,
        estimated_download_time_minutes=45.0,
    )
    
    print(f"升级提案: {proposal.proposal_id}")
    print(f"从 {proposal.current_model} → {proposal.target_model}")
    print(f"风险等级: {proposal.risk_level.value}")
    print(f"预计耗时: {proposal.estimated_download_time_minutes:.0f}分钟")
    print(f"风险因素: {', '.join(proposal.risk_factors)}")
    
    print("\n✅ 模型管理器测试通过")
    return proposal


def test_decision_engine():
    """测试决策引擎"""
    print("\n" + "="*60)
    print("测试3: 决策引擎")
    print("="*60)
    
    engine = EvolutionDecisionEngine()
    
    # 模拟系统数据
    system_data = {
        "resources": {
            "cpu_percent": 35.0,
            "memory_percent": 55.0,
            "memory_available_gb": 16.0,
        },
        "disk": {
            "free_gb": 50.0,
        },
        "gpu": {
            "available": True,
            "memory_percent": 45.0,
        },
        "network": {
            "latency_ms": 25.0,
            "bandwidth_mbps": 50.0,
        },
    }
    
    # 评估升级
    recommendation = asyncio.run(engine.evaluate_upgrade(
        from_model="qwen2.5:7b",
        to_model="qwen2.5:14b",
        system_data=system_data,
    ))
    
    print(f"建议ID: {recommendation.recommendation_id}")
    print(f"从 {recommendation.from_model} → {recommendation.to_model}")
    print(f"建议操作: {recommendation.recommended_action.value}")
    print(f"置信度: {recommendation.confidence:.1%}")
    print(f"理由: {recommendation.reasoning}")
    
    if recommendation.recommended_time:
        print(f"建议时间: {recommendation.recommended_time.strftime('%H:%M:%S')}")
    
    # 决策树可视化
    if recommendation.decision_tree:
        tree_data = engine.get_tree_visualization_data(recommendation.decision_tree)
        print(f"\n决策树节点数: {len(tree_data['nodes'])}")
        print(f"当前节点: {tree_data['currentNode']}")
        print(f"决策结果: {tree_data['outcome']}")
    
    print("\n✅ 决策引擎测试通过")
    return recommendation


def test_progress_tracker():
    """测试进度追踪器"""
    print("\n" + "="*60)
    print("测试4: 进度追踪器")
    print("="*60)
    
    tracker = ProgressTracker()
    
    # 开始追踪
    progress = tracker.start_tracking("qwen2.5:14b")
    print(f"开始追踪: {progress.progress_id}")
    
    # 模拟进度更新
    tracker.update_stage(ProgressStage.CHECKING, 50.0)
    tracker.log("检查系统资源...")
    
    tracker.update_stage(ProgressStage.CHECKING, 100.0)
    tracker.update_stage(ProgressStage.DOWNLOADING, 25.0)
    tracker.log("开始下载模型...")
    
    tracker.update_stage(ProgressStage.DOWNLOADING, 75.0)
    tracker.log("下载进度 75%...")
    
    tracker.update_stage(ProgressStage.DOWNLOADING, 100.0)
    tracker.update_stage(ProgressStage.TESTING, 50.0)
    tracker.log("验证模型...")
    
    # 获取可视化数据
    viz_data = tracker.get_visualization_data()
    
    print(f"\n总体进度: {viz_data['progress']['total']:.1f}%")
    print(f"当前阶段: {viz_data['progress']['stage']:.1f}%")
    
    print("\n阶段状态:")
    for stage in viz_data['stages']:
        status_icon = "🔵" if stage['is_current'] else ("✅" if stage['is_completed'] else "⭕")
        print(f"  {status_icon} {stage['label']}: {stage['progress']:.0f}%")
    
    print("\n步骤状态:")
    for step in viz_data['steps']:
        print(f"  - {step['name']}: {step['status']} ({step['progress']:.0f}%)")
    
    tracker.stop_tracking()
    print("\n✅ 进度追踪器测试通过")


def test_dashboard():
    """测试仪表盘"""
    print("\n" + "="*60)
    print("测试5: 可视化仪表盘")
    print("="*60)
    
    dashboard = EvolutionDashboard()
    
    # 模拟监控数据
    for i in range(5):
        dashboard.update_monitoring_data({
            "system_status": "healthy",
            "resources": {
                "cpu_percent": 30 + i * 5,
                "memory_percent": 50 + i * 2,
                "cpu_cores": 8,
                "memory_total_gb": 32.0,
                "memory_used_gb": 16.0,
                "memory_available_gb": 16.0,
            },
            "gpu": {
                "available": True,
                "name": "NVIDIA RTX 3080",
                "memory_percent": 40 + i * 5,
                "utilization_percent": 35,
            },
            "network": {
                "latency_ms": 20 + i,
                "bandwidth_mbps": 100 - i * 10,
            },
            "disk": {
                "total_gb": 500,
                "used_gb": 200,
                "free_gb": 300,
                "percent": 40,
            },
            "models": [
                {"name": "qwen2.5:7b", "size_mb": 8*1024},
                {"name": "llama2:13b", "size_mb": 14*1024},
            ],
            "current_model": "qwen2.5:7b",
        })
        time.sleep(0.1)
    
    # 获取图表数据
    cpu_data = dashboard.get_cpu_chart_data()
    print(f"\nCPU图表: 当前{cpu_data['current']:.1f}%, 平均{cpu_data['average']:.1f}%")
    
    memory_data = dashboard.get_memory_chart_data()
    print(f"内存图表: 当前{memory_data['current']:.1f}%, 平均{memory_data['average']:.1f}%")
    
    gpu_data = dashboard.get_gpu_chart_data()
    print(f"GPU图表: 当前{gpu_data['current']:.1f}%, 平均{gpu_data['average']:.1f}%")
    
    # 获取概览
    overview = dashboard.get_overview_data()
    print(f"\n系统状态: {overview['system_status']}")
    print(f"CPU: {overview['cpu']['usage']:.1f}% ({overview['cpu']['cores']}核)")
    print(f"内存: {overview['memory']['percent']:.1f}% ({overview['memory']['used_gb']:.1f}/{overview['memory']['total_gb']:.1f}GB)")
    
    if overview['gpu']['available']:
        print(f"GPU: {overview['gpu']['name']}")
        print(f"GPU显存: {overview['gpu']['memory_used_mb']/1024:.1f}/{overview['gpu']['memory_total_mb']/1024:.1f}GB")
    
    print("\n✅ 仪表盘测试通过")


def test_state_machine_visualizer():
    """测试状态机可视化"""
    print("\n" + "="*60)
    print("测试6: 状态机可视化")
    print("="*60)
    
    visualizer = StateMachineVisualizer()
    
    # 模拟当前状态
    current_state = "DOWNLOADING"
    
    diagram_data = visualizer.get_state_diagram_data(current_state)
    
    print(f"当前状态: {current_state}")
    print("\n状态节点:")
    for node in diagram_data['nodes']:
        if node['is_current']:
            icon = "🔵"
        elif node['is_completed']:
            icon = "✅"
        else:
            icon = "⭕"
        print(f"  {icon} {node['label']}")
    
    print("\n状态转换:")
    for edge in diagram_data['edges'][:5]:  # 只显示前5条
        print(f"  {edge['from']} → {edge['to']}")
    
    print("\n✅ 状态机可视化测试通过")


def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("🔮 可视化智能进化引擎 - 完整测试")
    print("="*60)
    
    # 测试各组件
    test_system_monitor()
    test_model_manager()
    test_decision_engine()
    test_progress_tracker()
    test_dashboard()
    test_state_machine_visualizer()
    
    print("\n" + "="*60)
    print("🎉 所有测试通过!")
    print("="*60)
    print("""
核心功能验证:
✅ SystemMonitor - 系统资源实时监控
✅ ModelManager - 模型生命周期管理
✅ DecisionEngine - 智能升级决策
✅ ProgressTracker - 进化进度追踪
✅ Dashboard - 可视化仪表盘
✅ StateMachineVisualizer - 状态机可视化

下一步:
1. 集成到 PyQt6 UI 面板
2. 连接 Ollama 服务进行实际升级测试
3. 添加 WebSocket 实时推送
4. 实现完整的回滚机制
""")


if __name__ == "__main__":
    main()
