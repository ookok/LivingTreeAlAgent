# -*- coding: utf-8 -*-
"""
生产自动化部署测试
"""

import sys
import os
import time
import importlib.util
from collections import defaultdict

# 加载模块
def load_module_from_core(name):
    spec = importlib.util.spec_from_file_location(
        name,
        os.path.join(os.path.dirname(__file__), "..", "core", f"{name}.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

# 尝试加载 production_automation
try:
    prod_auto = load_module_from_core("production_automation")
    print("[OK] Module loaded successfully")
except Exception as e:
    print(f"[FAIL] Failed to load module: {e}")
    sys.exit(1)

# 导出需要的内容
DeploymentStrategy = prod_auto.DeploymentStrategy
DeploymentPhase = prod_auto.DeploymentPhase
DeploymentStatus = prod_auto.DeploymentStatus
EnvironmentType = prod_auto.EnvironmentType
DeploymentSnapshot = prod_auto.DeploymentSnapshot
DeploymentStep = prod_auto.DeploymentStep
EnvironmentConfig = prod_auto.EnvironmentConfig
ValidationResult = prod_auto.ValidationResult
EnvironmentConfigManager = prod_auto.EnvironmentConfigManager
DeploymentValidator = prod_auto.DeploymentValidator
RollbackManager = prod_auto.RollbackManager
ZeroDowntimeDeployer = prod_auto.ZeroDowntimeDeployer
DeploymentPipelineOrchestrator = prod_auto.DeploymentPipelineOrchestrator
DeploymentScriptGenerator = prod_auto.DeploymentScriptGenerator
DeploymentScheduler = prod_auto.DeploymentScheduler
create_deployment_orchestrator = prod_auto.create_deployment_orchestrator
create_env_config_manager = prod_auto.create_env_config_manager
create_deployment_validator = prod_auto.create_deployment_validator
create_rollback_manager = prod_auto.create_rollback_manager
create_zero_downtime_deployer = prod_auto.create_zero_downtime_deployer
create_deployment_scheduler = prod_auto.create_deployment_scheduler


def test_env_config_manager():
    """测试环境配置管理器"""
    print("\n[Test 1] EnvironmentConfigManager")

    manager = create_env_config_manager()

    # 列出默认配置
    configs = manager.list_configs()
    assert len(configs) == 3, f"Expected 3 configs, got {len(configs)}"
    print(f"  [OK] Default configs: {[c['name'] for c in configs]}")

    # 获取生产配置
    prod_config = manager.get_config("production")
    assert prod_config is not None, "Production config not found"
    assert prod_config.replicas == 3, f"Expected 3 replicas, got {prod_config.replicas}"
    print(f"  [OK] Production config: {prod_config.replicas} replicas")

    # 创建自定义配置
    custom = EnvironmentConfig(
        name="custom",
        env_type="custom",
        namespace="custom",
        replicas=2
    )
    success = manager.create_config("custom", custom)
    assert success, "Failed to create custom config"
    print(f"  [OK] Custom config created")

    # 导出/导入配置
    exported = manager.export_config("production")
    assert "name" in exported, "Export failed"
    print(f"  [OK] Config export works")

    manager.delete_config("custom")

    return True


def test_deployment_validator():
    """测试部署验证器"""
    print("\n[Test 2] DeploymentValidator")

    validator = create_deployment_validator()

    # 创建测试数据
    deployment = DeploymentSnapshot(
        deployment_id="test_001",
        version="v1.0.0",
        strategy="rolling_update",
        environment="production",
        status="success"
    )

    config = EnvironmentConfig(
        name="production",
        env_type="production",
        namespace="prod",
        replicas=3,
        health_check={"enabled": True, "path": "/health"},
        resources={"cpu_limit": "1", "memory_limit": "1Gi"}
    )

    # 执行验证
    passed, results = validator.validate(deployment, config)
    assert passed, f"Validation failed: {[r.message for r in results if not r.passed]}"
    print(f"  [OK] All {len(results)} validation rules passed")

    # 检查特定规则
    for result in results:
        if result.check_name == "health_check":
            assert result.passed, "Health check validation failed"
            print(f"  [OK] Health check: {result.message}")

    return True


def test_rollback_manager():
    """测试回滚管理器"""
    print("\n[Test 3] RollbackManager")

    manager = create_rollback_manager(max_snapshots=5)

    # 保存快照
    snapshot1 = DeploymentSnapshot(
        deployment_id="deploy_001",
        version="v1.0.0",
        strategy="rolling_update",
        environment="production",
        status="success",
        artifacts={"image": "app:v1.0.0"}
    )
    manager.save_snapshot(snapshot1)
    print(f"  [OK] Snapshot v1.0.0 saved")

    snapshot2 = DeploymentSnapshot(
        deployment_id="deploy_002",
        version="v1.0.1",
        strategy="rolling_update",
        environment="production",
        status="success",
        artifacts={"image": "app:v1.0.1"}
    )
    manager.save_snapshot(snapshot2)
    print(f"  [OK] Snapshot v1.0.1 saved")

    # 获取快照
    latest = manager.get_latest_snapshot("production", "rolling_update")
    assert latest.version == "v1.0.1", f"Expected v1.0.1, got {latest.version}"
    print(f"  [OK] Latest snapshot: {latest.version}")

    previous = manager.get_previous_snapshot("production", "rolling_update")
    assert previous.version == "v1.0.0", f"Expected v1.0.0, got {previous.version}"
    print(f"  [OK] Previous snapshot: {previous.version}")

    # 执行回滚
    success, rollback = manager.rollback("deploy_003", "production", "rolling_update")
    assert success, "Rollback failed"
    print(f"  [OK] Rollback to {rollback.metadata.get('rolled_back_from')} successful")

    return True


def test_zero_downtime_deployer():
    """测试零停机部署器"""
    print("\n[Test 4] ZeroDowntimeDeployer")

    # 测试蓝绿部署
    blue_green = create_zero_downtime_deployer("blue_green")
    success, color = blue_green.deploy_blue_green(
        "production",
        "v2.0.0",
        {"image": "app:v2.0.0"}
    )
    assert success, "Blue-green deployment failed"
    print(f"  [OK] Blue-green: deployed to {color}")

    status = blue_green.get_deployment_status("production")
    assert status["active_color"] == color, "Color mismatch"
    print(f"  [OK] Active color: {status['active_color']}")

    # 测试金丝雀发布
    canary = create_zero_downtime_deployer("canary")
    success, distribution = canary.deploy_canary(
        "production",
        "v2.1.0",
        {"image": "app:v2.1.0"},
        percentage=20
    )
    assert success, "Canary deployment failed"
    print(f"  [OK] Canary: {distribution}")

    # 提升金丝雀
    success = canary.promote_canary("production", "v2.1.0")
    assert success, "Promote failed"
    print(f"  [OK] Canary promoted to 100%")

    return True


def test_deployment_pipeline():
    """测试部署流水线"""
    print("\n[Test 5] DeploymentPipelineOrchestrator")

    orchestrator = create_deployment_orchestrator("production", "rolling_update")

    # 创建部署
    deployment = orchestrator.create_deployment(
        version="v2.0.0",
        artifacts={"image": "app:v2.0.0", "config": "prod.yaml"}
    )
    assert deployment.status == "pending", "Wrong initial status"
    print(f"  [OK] Created deployment: {deployment.deployment_id}")

    # 步骤完成计数
    step_count = [0]

    def on_step_complete(step):
        step_count[0] += 1

    # 执行流水线
    success, result = orchestrator.execute_pipeline(
        deployment,
        on_step_complete=on_step_complete
    )
    assert success, f"Pipeline failed: {result.status}"
    assert result.status == "success", f"Wrong final status: {result.status}"
    print(f"  [OK] Pipeline executed successfully ({step_count[0]} steps)")

    # 检查状态
    status = orchestrator.get_pipeline_status()
    assert status["deployment"]["version"] == "v2.0.0"
    print(f"  [OK] Pipeline status: {status['steps_completed']}/{status['total_steps']} steps")

    return True


def test_deployment_script_generator():
    """测试部署脚本生成器"""
    print("\n[Test 6] DeploymentScriptGenerator")

    config = EnvironmentConfig(
        name="production",
        env_type="production",
        namespace="prod",
        replicas=3,
        resources={
            "cpu_request": "200m",
            "cpu_limit": "1000m",
            "memory_request": "512Mi",
            "memory_limit": "1Gi"
        }
    )

    # 生成 Shell 脚本
    shell_script = DeploymentScriptGenerator.generate_shell_script(config, "test_001")
    assert "NAMESPACE=\"prod\"" in shell_script
    assert "REPLICAS=3" in shell_script
    lines = shell_script.strip().split("\n")
    print(f"  [OK] Shell script: {len(lines)} lines")

    # 生成 GitHub Actions
    workflow = DeploymentScriptGenerator.generate_github_actions_workflow(config, "test_002")
    assert "Deploy to production" in workflow
    assert "kubectl" in workflow
    lines = workflow.strip().split("\n")
    print(f"  [OK] GitHub Actions: {len(lines)} lines")

    # 生成 Jenkinsfile
    jenkinsfile = DeploymentScriptGenerator.generate_jenkinsfile(config)
    assert "pipeline {" in jenkinsfile
    assert "Deploy to production" in jenkinsfile
    lines = jenkinsfile.strip().split("\n")
    print(f"  [OK] Jenkinsfile: {len(lines)} lines")

    return True


def test_deployment_scheduler():
    """测试部署调度器"""
    print("\n[Test 7] DeploymentScheduler")

    scheduler = create_deployment_scheduler()

    # 调度部署
    success = scheduler.schedule_deployment(
        deployment_id="scheduled_001",
        cron_expression="02:00",
        version="v2.0.0",
        environment="production",
        artifacts={"image": "app:v2.0.0"}
    )
    assert success, "Schedule failed"
    print(f"  [OK] Deployment scheduled: 02:00 daily")

    # 获取调度列表
    scheduled = scheduler.get_scheduled_deployments()
    assert len(scheduled) == 1, f"Expected 1 scheduled, got {len(scheduled)}"
    print(f"  [OK] {len(scheduled)} scheduled deployment(s)")

    # 取消调度
    success = scheduler.cancel_scheduled_deployment("scheduled_001")
    assert success, "Cancel failed"
    print(f"  [OK] Scheduled deployment cancelled")

    return True


def test_integration():
    """集成测试"""
    print("\n[Test 8] Integration Test")

    # 完整的部署流程
    # 1. 配置管理
    config_manager = create_env_config_manager()
    config = config_manager.get_config("production")

    # 2. 创建编排器
    orchestrator = create_deployment_orchestrator("production", "blue_green")

    # 3. 创建零停机部署器
    zero_downtime = create_zero_downtime_deployer("blue_green")

    # 4. 创建回滚管理器
    rollback_mgr = create_rollback_manager()

    # 5. 创建部署
    deployment = orchestrator.create_deployment(
        version="v3.0.0",
        artifacts={"image": "app:v3.0.0"}
    )
    print(f"  [OK] Created deployment: {deployment.deployment_id}")

    # 6. 执行部署
    success, result = orchestrator.execute_pipeline(deployment)
    assert success, "Pipeline failed"
    print(f"  [OK] Pipeline executed: {result.status}")

    # 7. 保存快照
    rollback_mgr.save_snapshot(result)
    print(f"  [OK] Snapshot saved for rollback")

    # 8. 蓝绿部署
    success, color = zero_downtime.deploy_blue_green(
        "production",
        "v3.0.0",
        result.artifacts
    )
    assert success, "Blue-green deployment failed"
    print(f"  [OK] Blue-green deployed: {color}")

    # 9. 验证
    validator = create_deployment_validator()
    passed, results = validator.validate(result, config)
    print(f"  [OK] Validation: {len([r for r in results if r.passed])}/{len(results)} passed")

    return True


def test_quick_start():
    """快速启动测试"""
    print("\n[Test 9] Quick Start")

    # 一行代码完成部署
    orchestrator = create_deployment_orchestrator("production", "rolling_update")
    deployment = orchestrator.create_deployment(
        version="v1.0.0",
        artifacts={"image": "app:v1.0.0"}
    )
    success, result = orchestrator.execute_pipeline(deployment)
    assert success, "Quick start failed"

    print(f"  [OK] Quick start: {result.version} deployed in {result.status}")
    return True


def main():
    """运行所有测试"""
    print("=" * 60)
    print("生产自动化部署测试")
    print("=" * 60)

    tests = [
        ("EnvironmentConfigManager", test_env_config_manager),
        ("DeploymentValidator", test_deployment_validator),
        ("RollbackManager", test_rollback_manager),
        ("ZeroDowntimeDeployer", test_zero_downtime_deployer),
        ("DeploymentPipeline", test_deployment_pipeline),
        ("DeploymentScriptGenerator", test_deployment_script_generator),
        ("DeploymentScheduler", test_deployment_scheduler),
        ("Integration", test_integration),
        ("QuickStart", test_quick_start),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            if test_func():
                print(f"[PASS] {name}")
                passed += 1
            else:
                print(f"[FAIL] {name}")
                failed += 1
        except Exception as e:
            print(f"[FAIL] {name}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print(f"测试结果: {passed}/{len(tests)} 通过")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
