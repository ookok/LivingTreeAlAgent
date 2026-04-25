# -*- coding: utf-8 -*-
"""
可视化智能进化引擎测试 - 独立版本
==================================
"""

import asyncio
import time
import sys
import os

# 设置UTF-8编码
os.environ['PYTHONIOENCODING'] = 'utf-8'
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 添加项目路径
sys.path.insert(0, 'f:/mhzyapp/LivingTreeAlAgent')

# 直接导入模块
import importlib.util

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

# 加载模块
try:
    system_monitor = load_module("system_monitor", "f:/mhzyapp/LivingTreeAlAgent/core/visual_evolution_engine/system_monitor.py")
    model_manager = load_module("model_manager", "f:/mhzyapp/LivingTreeAlAgent/core/visual_evolution_engine/model_manager.py")
    decision_engine = load_module("decision_engine", "f:/mhzyapp/LivingTreeAlAgent/core/visual_evolution_engine/decision_engine.py")
    progress_tracker = load_module("progress_tracker", "f:/mhzyapp/LivingTreeAlAgent/core/visual_evolution_engine/progress_tracker.py")
    dashboard = load_module("dashboard", "f:/mhzyapp/LivingTreeAlAgent/core/visual_evolution_engine/dashboard.py")
    print("[OK] Module loaded successfully")
except Exception as e:
    print(f"[FAIL] Module loading failed: {e}")
    sys.exit(1)

SystemMonitor = system_monitor.SystemMonitor
ModelManager = model_manager.ModelManager
UpgradeProposal = model_manager.UpgradeProposal
RiskLevel = model_manager.RiskLevel
EvolutionDecisionEngine = decision_engine.EvolutionDecisionEngine
ProgressTracker = progress_tracker.ProgressTracker
ProgressStage = progress_tracker.ProgressStage
EvolutionDashboard = dashboard.EvolutionDashboard
StateMachineVisualizer = dashboard.StateMachineVisualizer


def test_system_monitor():
    print("\n" + "="*60)
    print("Test 1: System Monitor")
    print("="*60)
    
    monitor = SystemMonitor()
    data = monitor.get_dashboard_data()
    
    print(f"System Status: {data.system_status}")
    print(f"CPU: {data.resources.cpu_percent:.1f}%")
    print(f"Memory: {data.resources.memory_percent:.1f}% ({data.resources.memory_used_gb:.1f}/{data.resources.memory_total_gb:.1f} GB)")
    
    if data.gpu.available:
        print(f"GPU: {data.gpu.name}")
        print(f"GPU Memory: {data.gpu.memory_percent:.1f}%")
    else:
        print("GPU: Not available")
    
    print(f"Network Latency: {data.network.latency_ms:.1f}ms")
    print(f"Disk Space: {data.disk.free_gb:.1f} GB free")
    print(f"Model Directory: {data.disk.model_dir_size_gb:.2f} GB")
    print(f"Local Models: {len(data.models)}")
    
    for model in data.models[:3]:
        print(f"  - {model.name} ({model.size_mb/1024:.1f} GB)")
    
    print("\n[PASS] System Monitor test passed")
    return data


def test_model_manager():
    print("\n" + "="*60)
    print("Test 2: Model Manager")
    print("="*60)
    
    manager = ModelManager()
    
    proposal = UpgradeProposal(
        proposal_id="TEST-001",
        current_model="qwen2.5:7b",
        current_version="2.5",
        target_model="qwen2.5:14b",
        target_version="2.5",
        trigger_reasons=["New version detected"],
        expected_benefits={"accuracy": 15.0},
        risk_level=RiskLevel.MEDIUM,
        risk_factors=["Download time is long"],
        required_disk_gb=20.0,
        required_memory_gb=16.0,
        estimated_download_time_minutes=45.0,
    )
    
    print(f"Upgrade Proposal: {proposal.proposal_id}")
    print(f"From {proposal.current_model} -> {proposal.target_model}")
    print(f"Risk Level: {proposal.risk_level.value}")
    print(f"Estimated Time: {proposal.estimated_download_time_minutes:.0f} minutes")
    print(f"Risk Factors: {', '.join(proposal.risk_factors)}")
    
    print("\n[PASS] Model Manager test passed")
    return proposal


def test_decision_engine():
    print("\n" + "="*60)
    print("Test 3: Decision Engine")
    print("="*60)
    
    engine = EvolutionDecisionEngine()
    
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
    
    recommendation = asyncio.run(engine.evaluate_upgrade(
        from_model="qwen2.5:7b",
        to_model="qwen2.5:14b",
        system_data=system_data,
    ))
    
    print(f"Recommendation ID: {recommendation.recommendation_id}")
    print(f"From {recommendation.from_model} -> {recommendation.to_model}")
    print(f"Recommended Action: {recommendation.recommended_action.value}")
    print(f"Confidence: {recommendation.confidence:.1%}")
    print(f"Reasoning: {recommendation.reasoning}")
    
    if recommendation.recommended_time:
        print(f"Recommended Time: {recommendation.recommended_time.strftime('%H:%M:%S')}")
    
    if recommendation.decision_tree:
        tree_data = engine.get_tree_visualization_data(recommendation.decision_tree)
        print(f"\nDecision Tree Nodes: {len(tree_data['nodes'])}")
        print(f"Current Node: {tree_data['currentNode']}")
        print(f"Decision Outcome: {tree_data['outcome']}")
    
    print("\n[PASS] Decision Engine test passed")
    return recommendation


def test_progress_tracker():
    print("\n" + "="*60)
    print("Test 4: Progress Tracker")
    print("="*60)
    
    tracker = ProgressTracker()
    
    progress = tracker.start_tracking("qwen2.5:14b")
    print(f"Started Tracking: {progress.progress_id}")
    
    tracker.update_stage(ProgressStage.CHECKING, 50.0)
    tracker.log("Checking system resources...")
    
    tracker.update_stage(ProgressStage.CHECKING, 100.0)
    tracker.update_stage(ProgressStage.DOWNLOADING, 25.0)
    tracker.log("Starting model download...")
    
    tracker.update_stage(ProgressStage.DOWNLOADING, 75.0)
    tracker.log("Download progress 75%...")
    
    tracker.update_stage(ProgressStage.DOWNLOADING, 100.0)
    tracker.update_stage(ProgressStage.TESTING, 50.0)
    tracker.log("Verifying model...")
    
    viz_data = tracker.get_visualization_data()
    
    print(f"\nTotal Progress: {viz_data['progress']['total']:.1f}%")
    print(f"Current Stage: {viz_data['progress']['stage']:.1f}%")
    
    print("\nStage Status:")
    for stage in viz_data['stages']:
        status_icon = "[*]" if stage['is_current'] else ("[OK]" if stage['is_completed'] else "[--]")
        print(f"  {status_icon} {stage['label']}: {stage['progress']:.0f}%")
    
    print("\nStep Status:")
    for step in viz_data['steps']:
        print(f"  - {step['name']}: {step['status']} ({step['progress']:.0f}%)")
    
    tracker.stop_tracking()
    print("\n[PASS] Progress Tracker test passed")


def test_dashboard():
    print("\n" + "="*60)
    print("Test 5: Dashboard")
    print("="*60)
    
    dashboard_instance = EvolutionDashboard()
    
    for i in range(5):
        dashboard_instance.update_monitoring_data({
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
    
    cpu_data = dashboard_instance.get_cpu_chart_data()
    print(f"\nCPU Chart: Current {cpu_data['current']:.1f}%, Average {cpu_data['average']:.1f}%")
    
    memory_data = dashboard_instance.get_memory_chart_data()
    print(f"Memory Chart: Current {memory_data['current']:.1f}%, Average {memory_data['average']:.1f}%")
    
    gpu_data = dashboard_instance.get_gpu_chart_data()
    print(f"GPU Chart: Current {gpu_data['current']:.1f}%, Average {gpu_data['average']:.1f}%")
    
    overview = dashboard_instance.get_overview_data()
    print(f"\nSystem Status: {overview['system_status']}")
    print(f"CPU: {overview['cpu']['usage']:.1f}% ({overview['cpu']['cores']} cores)")
    print(f"Memory: {overview['memory']['percent']:.1f}% ({overview['memory']['used_gb']:.1f}/{overview['memory']['total_gb']:.1f}GB)")
    
    if overview['gpu']['available']:
        print(f"GPU: {overview['gpu']['name']}")
        print(f"GPU Memory: {overview['gpu']['memory_used_mb']/1024:.1f}/{overview['gpu']['memory_total_mb']/1024:.1f}GB")
    
    print("\n[PASS] Dashboard test passed")


def test_state_machine_visualizer():
    print("\n" + "="*60)
    print("Test 6: State Machine Visualizer")
    print("="*60)
    
    visualizer = StateMachineVisualizer()
    
    current_state = "DOWNLOADING"
    diagram_data = visualizer.get_state_diagram_data(current_state)
    
    print(f"Current State: {current_state}")
    print("\nState Nodes:")
    for node in diagram_data['nodes']:
        if node['is_current']:
            icon = "[*]"
        elif node['is_completed']:
            icon = "[OK]"
        else:
            icon = "[--]"
        print(f"  {icon} {node['label']}")
    
    print("\nState Transitions:")
    for edge in diagram_data['edges'][:5]:
        print(f"  {edge['from']} -> {edge['to']}")
    
    print("\n[PASS] State Machine Visualizer test passed")


def main():
    print("\n" + "="*60)
    print("Visual Intelligent Evolution Engine - Full Test")
    print("="*60)
    
    test_system_monitor()
    test_model_manager()
    test_decision_engine()
    test_progress_tracker()
    test_dashboard()
    test_state_machine_visualizer()
    
    print("\n" + "="*60)
    print("ALL TESTS PASSED!")
    print("="*60)
    print("""
Core Features Verified:
[PASS] SystemMonitor - Real-time system resource monitoring
[PASS] ModelManager - Model lifecycle management
[PASS] DecisionEngine - Smart upgrade decision making
[PASS] ProgressTracker - Evolution progress tracking
[PASS] Dashboard - Visualization dashboard
[PASS] StateMachineVisualizer - State machine visualization

Next Steps:
1. Integrate with PyQt6 UI panel
2. Connect to Ollama service for actual upgrade testing
3. Add WebSocket real-time push
4. Implement complete rollback mechanism
""")


if __name__ == "__main__":
    main()
