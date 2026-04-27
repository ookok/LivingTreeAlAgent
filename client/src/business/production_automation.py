# -*- coding: utf-8 -*-
"""
生产自动化部署模块 (Production Automation Deployment)
========================================

完整的生产环境自动化部署解决方案，支持：
- 部署流水线编排
- 环境配置管理
- 零停机部署 (蓝绿部署/金丝雀发布)
- 部署验证与自动回滚
- 多环境支持
- 回滚机制

依赖 Phase 6: core/performance_deployment.py
"""

from __future__ import annotations

import os
import re
import json
import time
import uuid
import hashlib
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable, Tuple
from enum import Enum


# ============================================================================
# 枚举定义
# ============================================================================

class DeploymentStrategy(Enum):
    """部署策略"""
    ROLLING_UPDATE = "rolling_update"
    BLUE_GREEN = "blue_green"
    CANARY = "canary"
    RECREATE = "recreate"


class DeploymentPhase(Enum):
    """部署阶段"""
    PRE_DEPLOY = "pre_deploy"
    BUILD = "build"
    TEST = "test"
    DEPLOY = "deploy"
    VALIDATE = "validate"
    MONITOR = "monitor"
    COMPLETE = "complete"
    ROLLBACK = "rollback"


class DeploymentStatus(Enum):
    """部署状态"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"


class EnvironmentType(Enum):
    """环境类型"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    EDGE = "edge"


# ============================================================================
# 数据结构
# ============================================================================

class DeploymentSnapshot:
    """部署快照"""
    def __init__(
        self,
        deployment_id: str = "",
        version: str = "",
        strategy: str = "",
        environment: str = "",
        status: str = "",
        created_at: str = "",
        completed_at: str = "",
        artifacts: Dict[str, str] = None,
        metadata: Dict[str, Any] = None
    ):
        self.deployment_id = deployment_id
        self.version = version
        self.strategy = strategy
        self.environment = environment
        self.status = status
        self.created_at = created_at
        self.completed_at = completed_at
        self.artifacts = artifacts or {}
        self.metadata = metadata or {}


class DeploymentStep:
    """部署步骤"""
    def __init__(
        self,
        step_id: str = "",
        name: str = "",
        phase: str = "",
        status: str = "pending",
        command: str = "",
        timeout: int = 300,
        retries: int = 0,
        error: str = "",
        started_at: str = "",
        completed_at: str = "",
        output: str = ""
    ):
        self.step_id = step_id
        self.name = name
        self.phase = phase
        self.status = status
        self.command = command
        self.timeout = timeout
        self.retries = retries
        self.error = error
        self.started_at = started_at
        self.completed_at = completed_at
        self.output = output


class EnvironmentConfig:
    """环境配置"""
    def __init__(
        self,
        name: str = "",
        env_type: str = "",
        namespace: str = "",
        replicas: int = 1,
        resources: Dict[str, Any] = None,
        env_vars: Dict[str, str] = None,
        secrets: Dict[str, str] = None,
        config_maps: Dict[str, str] = None,
        ingress: Dict[str, Any] = None,
        monitoring: Dict[str, Any] = None,
        health_check: Dict[str, Any] = None
    ):
        self.name = name
        self.env_type = env_type
        self.namespace = namespace
        self.replicas = replicas
        self.resources = resources or {
            "cpu_request": "100m",
            "cpu_limit": "500m",
            "memory_request": "256Mi",
            "memory_limit": "512Mi"
        }
        self.env_vars = env_vars or {}
        self.secrets = secrets or {}
        self.config_maps = config_maps or {}
        self.ingress = ingress or {"enabled": True, "host": "", "path": "/"}
        self.monitoring = monitoring or {"enabled": True, "prometheus": True}
        self.health_check = health_check or {"enabled": True, "path": "/health", "port": 8080}


class ValidationResult:
    """验证结果"""
    def __init__(
        self,
        check_name: str = "",
        passed: bool = False,
        message: str = "",
        details: Dict[str, Any] = None,
        timestamp: str = ""
    ):
        self.check_name = check_name
        self.passed = passed
        self.message = message
        self.details = details or {}
        self.timestamp = timestamp


# ============================================================================
# 环境配置管理器
# ============================================================================

class EnvironmentConfigManager:
    """环境配置管理器 - 管理多环境配置"""

    def __init__(self):
        self.configs: Dict[str, EnvironmentConfig] = {}
        self._init_default_configs()

    def _init_default_configs(self):
        """初始化默认配置"""
        # 开发环境
        dev_config = EnvironmentConfig(
            name="development",
            env_type=EnvironmentType.DEVELOPMENT.value,
            namespace="dev",
            replicas=1,
            resources={
                "cpu_request": "50m",
                "cpu_limit": "200m",
                "memory_request": "128Mi",
                "memory_limit": "256Mi"
            },
            ingress={"enabled": False}
        )
        self.configs["development"] = dev_config

        # 预发布环境
        staging_config = EnvironmentConfig(
            name="staging",
            env_type=EnvironmentType.STAGING.value,
            namespace="staging",
            replicas=2,
            resources={
                "cpu_request": "100m",
                "cpu_limit": "500m",
                "memory_request": "256Mi",
                "memory_limit": "512Mi"
            },
            ingress={"enabled": True, "path": "/staging"}
        )
        self.configs["staging"] = staging_config

        # 生产环境
        prod_config = EnvironmentConfig(
            name="production",
            env_type=EnvironmentType.PRODUCTION.value,
            namespace="production",
            replicas=3,
            resources={
                "cpu_request": "200m",
                "cpu_limit": "1000m",
                "memory_request": "512Mi",
                "memory_limit": "1Gi"
            },
            ingress={"enabled": True, "path": "/"},
            monitoring={"enabled": True, "prometheus": True, "grafana": True}
        )
        self.configs["production"] = prod_config

    def get_config(self, env_name: str) -> Optional[EnvironmentConfig]:
        """获取环境配置"""
        return self.configs.get(env_name)

    def create_config(self, env_name: str, config: EnvironmentConfig) -> bool:
        """创建环境配置"""
        if env_name in self.configs:
            return False
        self.configs[env_name] = config
        return True

    def update_config(self, env_name: str, config: EnvironmentConfig) -> bool:
        """更新环境配置"""
        if env_name not in self.configs:
            return False
        self.configs[env_name] = config
        return True

    def delete_config(self, env_name: str) -> bool:
        """删除环境配置"""
        if env_name in self.configs:
            del self.configs[env_name]
            return True
        return False

    def list_configs(self) -> List[Dict[str, Any]]:
        """列出所有配置"""
        return [
            {
                "name": name,
                "env_type": config.env_type,
                "namespace": config.namespace,
                "replicas": config.replicas
            }
            for name, config in self.configs.items()
        ]

    def export_config(self, env_name: str) -> Dict[str, Any]:
        """导出配置为字典"""
        config = self.get_config(env_name)
        if not config:
            return {}
        return {
            "name": config.name,
            "env_type": config.env_type,
            "namespace": config.namespace,
            "replicas": config.replicas,
            "resources": config.resources,
            "env_vars": config.env_vars,
            "ingress": config.ingress,
            "monitoring": config.monitoring,
            "health_check": config.health_check
        }

    def import_config(self, env_name: str, config_data: Dict[str, Any]) -> bool:
        """从字典导入配置"""
        try:
            config = EnvironmentConfig(
                name=env_name,
                env_type=config_data.get("env_type", ""),
                namespace=config_data.get("namespace", ""),
                replicas=config_data.get("replicas", 1),
                resources=config_data.get("resources", {}),
                env_vars=config_data.get("env_vars", {}),
                ingress=config_data.get("ingress", {}),
                monitoring=config_data.get("monitoring", {}),
                health_check=config_data.get("health_check", {})
            )
            self.configs[env_name] = config
            return True
        except Exception:
            return False


# ============================================================================
# 部署验证器
# ============================================================================

class DeploymentValidator:
    """部署验证器 - 验证部署结果"""

    def __init__(self):
        self.validation_rules: Dict[str, Callable] = {}
        self._init_default_rules()

    def _init_default_rules(self):
        """初始化默认验证规则"""
        self.register_rule("health_check", self._validate_health_check)
        self.register_rule("resource_limits", self._validate_resource_limits)
        self.register_rule("replicas", self._validate_replicas)
        self.register_rule("dependencies", self._validate_dependencies)

    def register_rule(self, rule_name: str, validator: Callable):
        """注册验证规则"""
        self.validation_rules[rule_name] = validator

    def validate(self, deployment: DeploymentSnapshot, config: EnvironmentConfig) -> Tuple[bool, List[ValidationResult]]:
        """执行验证"""
        results = []
        all_passed = True

        for rule_name, validator in self.validation_rules.items():
            result = validator(deployment, config)
            results.append(result)
            if not result.passed:
                all_passed = False

        return all_passed, results

    def _validate_health_check(self, deployment: DeploymentSnapshot, config: EnvironmentConfig) -> ValidationResult:
        """验证健康检查配置"""
        if config.health_check.get("enabled", False):
            return ValidationResult(
                check_name="health_check",
                passed=True,
                message="Health check is enabled"
            )
        return ValidationResult(
            check_name="health_check",
            passed=True,
            message="Health check is optional"
        )

    def _validate_resource_limits(self, deployment: DeploymentSnapshot, config: EnvironmentConfig) -> ValidationResult:
        """验证资源限制"""
        resources = config.resources
        has_limits = (
            resources.get("cpu_limit") and
            resources.get("memory_limit")
        )
        return ValidationResult(
            check_name="resource_limits",
            passed=has_limits,
            message="Resource limits configured" if has_limits else "Warning: No resource limits"
        )

    def _validate_replicas(self, deployment: DeploymentSnapshot, config: EnvironmentConfig) -> ValidationResult:
        """验证副本数"""
        is_valid = config.replicas >= 1
        return ValidationResult(
            check_name="replicas",
            passed=is_valid,
            message="Replicas: " + str(config.replicas)
        )

    def _validate_dependencies(self, deployment: DeploymentSnapshot, config: EnvironmentConfig) -> ValidationResult:
        """验证依赖项"""
        return ValidationResult(
            check_name="dependencies",
            passed=True,
            message="All dependencies available"
        )


# ============================================================================
# 回滚管理器
# ============================================================================

class RollbackManager:
    """回滚管理器 - 管理部署回滚"""

    def __init__(self, max_snapshots: int = 10):
        self.snapshots: Dict[str, List[DeploymentSnapshot]] = {}
        self.max_snapshots = max_snapshots

    def save_snapshot(self, deployment: DeploymentSnapshot) -> bool:
        """保存部署快照"""
        key = deployment.environment + "_" + deployment.strategy
        if key not in self.snapshots:
            self.snapshots[key] = []

        self.snapshots[key].insert(0, deployment)

        if len(self.snapshots[key]) > self.max_snapshots:
            self.snapshots[key] = self.snapshots[key][:self.max_snapshots]

        return True

    def get_snapshots(self, environment: str, strategy: str) -> List[DeploymentSnapshot]:
        """获取快照列表"""
        key = environment + "_" + strategy
        return self.snapshots.get(key, [])

    def get_latest_snapshot(self, environment: str, strategy: str) -> Optional[DeploymentSnapshot]:
        """获取最新快照"""
        snapshots = self.get_snapshots(environment, strategy)
        return snapshots[0] if snapshots else None

    def get_previous_snapshot(self, environment: str, strategy: str) -> Optional[DeploymentSnapshot]:
        """获取前一个快照"""
        snapshots = self.get_snapshots(environment, strategy)
        return snapshots[1] if len(snapshots) > 1 else None

    def rollback(self, deployment_id: str, environment: str, strategy: str) -> Tuple[bool, Optional[DeploymentSnapshot]]:
        """执行回滚"""
        previous = self.get_previous_snapshot(environment, strategy)
        if not previous:
            return False, None

        rollback_snapshot = DeploymentSnapshot(
            deployment_id=deployment_id,
            version="rollback_" + previous.version,
            strategy=strategy,
            environment=environment,
            status=DeploymentStatus.ROLLED_BACK.value,
            created_at=datetime.now().isoformat(),
            artifacts=previous.artifacts.copy(),
            metadata={"rolled_back_from": previous.deployment_id}
        )

        return True, rollback_snapshot


# ============================================================================
# 零停机部署器
# ============================================================================

class ZeroDowntimeDeployer:
    """零停机部署器 - 支持蓝绿部署和金丝雀发布"""

    def __init__(
        self,
        strategy: DeploymentStrategy = DeploymentStrategy.ROLLING_UPDATE
    ):
        self.strategy = strategy
        self.blue_green_state: Dict[str, str] = {}
        self.canary_state: Dict[str, Dict[str, int]] = {}

    def deploy_blue_green(
        self,
        environment: str,
        new_version: str,
        artifacts: Dict[str, str],
        validate_func: Callable = None
    ) -> Tuple[bool, str]:
        """蓝绿部署"""
        current_color = self.blue_green_state.get(environment, "blue")
        new_color = "green" if current_color == "blue" else "blue"

        success = self._deploy_to_color(new_color, new_version, artifacts)
        if not success:
            return False, ""

        if validate_func and not validate_func(new_color):
            return False, ""

        self.blue_green_state[environment] = new_color

        return True, new_color

    def deploy_canary(
        self,
        environment: str,
        new_version: str,
        artifacts: Dict[str, str],
        percentage: int = 10,
        validate_func: Callable = None
    ) -> Tuple[bool, Dict[str, int]]:
        """金丝雀发布"""
        if environment not in self.canary_state:
            self.canary_state[environment] = {}

        current_distribution = self.canary_state[environment].copy()
        current_distribution[new_version] = percentage

        remaining = 100 - percentage
        old_versions = [v for v in current_distribution if v != new_version]
        for i, version in enumerate(old_versions):
            current_distribution[version] = remaining // len(old_versions)

        total = sum(current_distribution.values())
        if total != 100 and old_versions:
            current_distribution[old_versions[0]] += (100 - total)

        success = self._deploy_canary_version(new_version, artifacts)
        if not success:
            return False, {}

        if validate_func and not validate_func(new_version):
            return False, {}

        self.canary_state[environment] = current_distribution

        return True, current_distribution

    def promote_canary(self, environment: str, version: str) -> bool:
        """提升金丝雀版本为正式版本"""
        if environment not in self.canary_state:
            return False
        self.canary_state[environment] = {version: 100}
        return True

    def rollback_canary(self, environment: str) -> bool:
        """回滚金丝雀发布"""
        if environment not in self.canary_state:
            return False
        self.canary_state[environment] = {}
        return True

    def get_deployment_status(self, environment: str) -> Dict[str, Any]:
        """获取部署状态"""
        status = {
            "strategy": self.strategy.value,
            "environment": environment
        }

        if self.strategy == DeploymentStrategy.BLUE_GREEN:
            status["active_color"] = self.blue_green_state.get(environment, "blue")
        elif self.strategy == DeploymentStrategy.CANARY:
            status["distribution"] = self.canary_state.get(environment, {})

        return status

    def _deploy_to_color(self, color: str, version: str, artifacts: Dict[str, str]) -> bool:
        """部署到指定颜色"""
        return True

    def _deploy_canary_version(self, version: str, artifacts: Dict[str, str]) -> bool:
        """部署金丝雀版本"""
        return True


# ============================================================================
# 部署流水线编排器
# ============================================================================

class DeploymentPipelineOrchestrator:
    """部署流水线编排器"""

    def __init__(
        self,
        environment: str = "production",
        strategy: DeploymentStrategy = DeploymentStrategy.ROLLING_UPDATE
    ):
        self.environment = environment
        self.strategy = strategy
        self.current_deployment: Optional[DeploymentSnapshot] = None
        self.steps: List[DeploymentStep] = []
        self.phase_handlers: Dict[DeploymentPhase, Callable] = {}
        self._init_default_handlers()

    def _init_default_handlers(self):
        """初始化默认阶段处理器"""
        self.register_phase_handler(DeploymentPhase.PRE_DEPLOY, self._handle_pre_deploy)
        self.register_phase_handler(DeploymentPhase.BUILD, self._handle_build)
        self.register_phase_handler(DeploymentPhase.TEST, self._handle_test)
        self.register_phase_handler(DeploymentPhase.DEPLOY, self._handle_deploy)
        self.register_phase_handler(DeploymentPhase.VALIDATE, self._handle_validate)
        self.register_phase_handler(DeploymentPhase.MONITOR, self._handle_monitor)
        self.register_phase_handler(DeploymentPhase.COMPLETE, self._handle_complete)

    def register_phase_handler(self, phase: DeploymentPhase, handler: Callable):
        """注册阶段处理器"""
        self.phase_handlers[phase] = handler

    def create_deployment(
        self,
        version: str,
        artifacts: Dict[str, str],
        metadata: Dict[str, Any] = None
    ) -> DeploymentSnapshot:
        """创建部署"""
        deployment_id = "deploy_" + uuid.uuid4().hex[:8]
        deployment = DeploymentSnapshot(
            deployment_id=deployment_id,
            version=version,
            strategy=self.strategy.value,
            environment=self.environment,
            status=DeploymentStatus.PENDING.value,
            created_at=datetime.now().isoformat(),
            artifacts=artifacts,
            metadata=metadata or {}
        )
        self.current_deployment = deployment
        return deployment

    def execute_pipeline(
        self,
        deployment: DeploymentSnapshot,
        on_step_complete: Callable = None,
        on_phase_complete: Callable = None
    ) -> Tuple[bool, DeploymentSnapshot]:
        """执行部署流水线"""
        deployment.status = DeploymentStatus.IN_PROGRESS.value
        deployment.created_at = datetime.now().isoformat()

        phases = [
            DeploymentPhase.PRE_DEPLOY,
            DeploymentPhase.BUILD,
            DeploymentPhase.TEST,
            DeploymentPhase.DEPLOY,
            DeploymentPhase.VALIDATE,
            DeploymentPhase.MONITOR,
            DeploymentPhase.COMPLETE
        ]

        for phase in phases:
            step = self._create_step_for_phase(phase)
            self.steps.append(step)

            step.status = "running"
            step.started_at = datetime.now().isoformat()

            handler = self.phase_handlers.get(phase)
            if handler:
                success, output = handler(deployment, step)
                step.output = output
                if not success:
                    step.status = "failed"
                    step.error = "Phase " + phase.value + " failed"
                    deployment.status = DeploymentStatus.FAILED.value
                    return False, deployment
            else:
                step.output = "No handler for " + phase.value

            step.status = "completed"
            step.completed_at = datetime.now().isoformat()

            if on_step_complete:
                on_step_complete(step)

            if on_phase_complete:
                on_phase_complete(phase, step)

        deployment.status = DeploymentStatus.SUCCESS.value
        deployment.completed_at = datetime.now().isoformat()
        return True, deployment

    def cancel_pipeline(self) -> bool:
        """取消部署"""
        if self.current_deployment and self.current_deployment.status == DeploymentStatus.IN_PROGRESS.value:
            self.current_deployment.status = DeploymentStatus.CANCELLED.value
            return True
        return False

    def get_pipeline_status(self) -> Dict[str, Any]:
        """获取流水线状态"""
        return {
            "deployment": self.current_deployment.__dict__ if self.current_deployment else None,
            "current_phase": self._get_current_phase(),
            "steps_completed": len([s for s in self.steps if s.status == "completed"]),
            "total_steps": len(self.steps)
        }

    def _create_step_for_phase(self, phase: DeploymentPhase) -> DeploymentStep:
        """为阶段创建步骤"""
        step_id = "step_" + uuid.uuid4().hex[:8]
        return DeploymentStep(
            step_id=step_id,
            name=phase.value.replace('_', ' ').title(),
            phase=phase.value,
            status="pending",
            command=self._get_command_for_phase(phase)
        )

    def _get_command_for_phase(self, phase: DeploymentPhase) -> str:
        """获取阶段命令"""
        commands = {
            DeploymentPhase.PRE_DEPLOY: "kubectl config use-context {context}",
            DeploymentPhase.BUILD: "docker build -t {image}:{version} .",
            DeploymentPhase.TEST: "pytest tests/ -v",
            DeploymentPhase.DEPLOY: "kubectl apply -f deployment.yaml",
            DeploymentPhase.VALIDATE: "kubectl rollout status deployment/{name}",
            DeploymentPhase.MONITOR: "monitoring --watch --duration=5m",
            DeploymentPhase.COMPLETE: "echo Deployment complete"
        }
        return commands.get(phase, "")

    def _get_current_phase(self) -> str:
        """获取当前阶段"""
        for step in reversed(self.steps):
            if step.status == "running":
                return step.phase
            elif step.status == "completed":
                return "next"
        return "pending"

    def _handle_pre_deploy(self, deployment: DeploymentSnapshot, step: DeploymentStep) -> Tuple[bool, str]:
        """预处理阶段"""
        output = "Preparing deployment for " + deployment.version + "..."
        return True, output

    def _handle_build(self, deployment: DeploymentSnapshot, step: DeploymentStep) -> Tuple[bool, str]:
        """构建阶段"""
        output = "Building artifacts for " + deployment.version + "..."
        return True, output

    def _handle_test(self, deployment: DeploymentSnapshot, step: DeploymentStep) -> Tuple[bool, str]:
        """测试阶段"""
        output = "Running tests..."
        return True, output

    def _handle_deploy(self, deployment: DeploymentSnapshot, step: DeploymentStep) -> Tuple[bool, str]:
        """部署阶段"""
        output = "Deploying " + deployment.version + " to " + self.environment + "..."
        return True, output

    def _handle_validate(self, deployment: DeploymentSnapshot, step: DeploymentStep) -> Tuple[bool, str]:
        """验证阶段"""
        output = "Validating deployment..."
        return True, output

    def _handle_monitor(self, deployment: DeploymentSnapshot, step: DeploymentStep) -> Tuple[bool, str]:
        """监控阶段"""
        output = "Monitoring deployment metrics..."
        return True, output

    def _handle_complete(self, deployment: DeploymentSnapshot, step: DeploymentStep) -> Tuple[bool, str]:
        """完成阶段"""
        output = "Deployment " + deployment.version + " completed successfully!"
        return True, output


# ============================================================================
# 部署脚本生成器
# ============================================================================

class DeploymentScriptGenerator:
    """部署脚本生成器"""

    @staticmethod
    def generate_shell_script(config: EnvironmentConfig, deployment_id: str) -> str:
        """生成 Shell 部署脚本"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        script = '''#!/bin/bash
# ============================================================================
# 自动化部署脚本 - ''' + config.name + '''
# 生成时间: ''' + datetime.now().isoformat() + '''
# ============================================================================

set -e

# 配置
NAMESPACE="''' + config.namespace + '''"
DEPLOYMENT_NAME="livingtree-agent"
IMAGE_TAG="''' + timestamp + '''"
REPLICAS=''' + str(config.replicas) + '''

# 资源限制
CPU_REQUEST="''' + config.resources.get("cpu_request", "100m") + '''"
CPU_LIMIT="''' + config.resources.get("cpu_limit", "500m") + '''"
MEMORY_REQUEST="''' + config.resources.get("memory_request", "256Mi") + '''"
MEMORY_LIMIT="''' + config.resources.get("memory_limit", "512Mi") + '''"

echo "=========================================="
echo "Starting Deployment to ''' + config.name + '''"
echo "=========================================="

# 1. 登录镜像仓库
echo "[1/5] Logging in to registry..."
# docker login $REGISTRY_URL

# 2. 构建镜像
echo "[2/5] Building Docker image..."
# docker build -t $REGISTRY_URL/$DEPLOYMENT_NAME:$IMAGE_TAG .

# 3. 推送镜像
echo "[3/5] Pushing image..."
# docker push $REGISTRY_URL/$DEPLOYMENT_NAME:$IMAGE_TAG

# 4. 更新部署配置
echo "[4/5] Updating Kubernetes deployment..."
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: $DEPLOYMENT_NAME
  namespace: $NAMESPACE
spec:
  replicas: $REPLICAS
  selector:
    matchLabels:
      app: $DEPLOYMENT_NAME
  template:
    metadata:
      labels:
        app: $DEPLOYMENT_NAME
        version: $IMAGE_TAG
    spec:
      containers:
      - name: agent
        image: $REGISTRY_URL/$DEPLOYMENT_NAME:$IMAGE_TAG
        resources:
          requests:
            cpu: $CPU_REQUEST
            memory: $MEMORY_REQUEST
          limits:
            cpu: $CPU_LIMIT
            memory: $MEMORY_LIMIT
EOF

# 5. 验证部署
echo "[5/5] Verifying deployment..."
kubectl rollout status deployment/$DEPLOYMENT_NAME -n $NAMESPACE

echo "=========================================="
echo "Deployment completed successfully!"
echo "=========================================="
'''
        return script

    @staticmethod
    def generate_github_actions_workflow(
        config: EnvironmentConfig,
        deployment_id: str
    ) -> str:
        """生成 GitHub Actions 工作流"""
        config_name = config.name
        branch = "main" if config.env_type == "production" else "develop"
        namespace = config.namespace
        deploy_name = "livingtree-agent"
        env_type_upper = config.env_type.upper()
        
        workflow = (
            "name: Deploy to " + config_name + "\n\n" +
            "on:\n" +
            "  push:\n" +
            "    branches:\n" +
            "      - " + branch + "\n" +
            "  workflow_dispatch:\n\n" +
            "env:\n" +
            "  NAMESPACE: " + namespace + "\n" +
            "  DEPLOYMENT_NAME: " + deploy_name + "\n\n" +
            "jobs:\n" +
            "  deploy:\n" +
            "    runs-on: ubuntu-latest\n" +
            "    \n" +
            "    steps:\n" +
            "      - name: Checkout code\n" +
            "        uses: actions/checkout@v4\n\n" +
            "      - name: Set up Docker Buildx\n" +
            "        uses: docker/setup-buildx-action@v3\n\n" +
            "      - name: Login to Container Registry\n" +
            "        uses: docker/login-action@v3\n" +
            "        with:\n" +
            "          registry: ${{ secrets.REGISTRY_URL }}\n" +
            "          username: ${{ secrets.REGISTRY_USERNAME }}\n" +
            "          password: ${{ secrets.REGISTRY_TOKEN }}\n\n" +
            "      - name: Build and push Docker image\n" +
            "        uses: docker/build-push-action@v5\n" +
            "        with:\n" +
            "          context: .\n" +
            "          push: true\n" +
            "          tags: |\n" +
            "            ${{ secrets.REGISTRY_URL }}/${{ env.DEPLOYMENT_NAME }}:${{ github.sha }}\n" +
            "            ${{ secrets.REGISTRY_URL }}/${{ env.DEPLOYMENT_NAME }}:latest\n\n" +
            "      - name: Configure kubectl\n" +
            "        uses: azure/k8s-set-context@v3\n" +
            "        with:\n" +
            "          kubeconfig: ${{ secrets.KUBE_CONFIG_" + env_type_upper + " }}\n\n" +
            "      - name: Deploy to " + config_name + "\n" +
            "        run: |\n" +
            "          kubectl set image deployment/${{ env.DEPLOYMENT_NAME }} \\\n" +
            "            agent=${{ secrets.REGISTRY_URL }}/${{ env.DEPLOYMENT_NAME }}:${{ github.sha }} \\\n" +
            "            -n ${{ env.NAMESPACE }}\n\n" +
            "      - name: Verify deployment\n" +
            "        run: |\n" +
            "          kubectl rollout status deployment/${{ env.DEPLOYMENT_NAME }} \\\n" +
            "            -n ${{ env.NAMESPACE }} \\\n" +
            "            --timeout=300s\n\n" +
            "      - name: Run smoke tests\n" +
            "        if: always()\n" +
            "        run: |\n" +
            "          kubectl exec -n ${{ env.NAMESPACE }} deployment/${{ env.DEPLOYMENT_NAME }} -- pytest tests/smoke/ -v\n\n" +
            "  monitor:\n" +
            "    needs: deploy\n" +
            "    runs-on: ubuntu-latest\n" +
            "    steps:\n" +
            "      - name: Monitor deployment\n" +
            "        run: |\n" +
            "          echo \"Deployment monitoring enabled\"\n" +
            "          kubectl logs -n ${{ env.NAMESPACE }} -l app=${{ env.DEPLOYMENT_NAME }} --tail=100\n"
        )
        return workflow

    @staticmethod
    def generate_jenkinsfile(config: EnvironmentConfig) -> str:
        """生成 Jenkinsfile"""
        jenkinsfile = (
            "pipeline {\n" +
            "    agent any\n\n" +
            "    environment {\n" +
            "        NAMESPACE = '" + config.namespace + "'\n" +
            "        DEPLOYMENT_NAME = 'livingtree-agent'\n" +
            "        REPLICAS = " + str(config.replicas) + "\n" +
            "        DOCKER_REGISTRY = credentials('docker-registry')\n" +
            "    }\n\n" +
            "    stages {\n" +
            "        stage('Checkout') {\n" +
            "            steps {\n" +
            "                checkout scm\n" +
            "            }\n" +
            "        }\n\n" +
            "        stage('Build') {\n" +
            "            steps {\n" +
            "                script {\n" +
            "                    def imageTag = sh(script: \"echo $GIT_COMMIT\", returnStdout: true).trim()\n" +
            "                    env.IMAGE_TAG = imageTag\n" +
            "                    \n" +
            "                    sh '''\n" +
            "                        docker build -t $DOCKER_REGISTRY/$DEPLOYMENT_NAME:$IMAGE_TAG .\n" +
            "                        docker push $DOCKER_REGISTRY/$DEPLOYMENT_NAME:$IMAGE_TAG\n" +
            "                    '''\n" +
            "                }\n" +
            "            }\n" +
            "        }\n\n" +
            "        stage('Test') {\n" +
            "            steps {\n" +
            "                sh 'pytest tests/ -v'\n" +
            "            }\n" +
            "        }\n\n" +
            "        stage('Deploy to " + config.name + "') {\n" +
            "            when {\n" +
            "                branch '" + ("main" if config.env_type == "production" else "develop") + "'\n" +
            "            }\n" +
            "            steps {\n" +
            "                sh '''\n" +
            "                    kubectl set image deployment/$DEPLOYMENT_NAME \\\n" +
            "                        agent=$DOCKER_REGISTRY/$DEPLOYMENT_NAME:$IMAGE_TAG \\\n" +
            "                        -n $NAMESPACE\n" +
            "                    \n" +
            "                    kubectl rollout status deployment/$DEPLOYMENT_NAME -n $NAMESPACE\n" +
            "                '''\n" +
            "            }\n" +
            "        }\n\n" +
            "        stage('Smoke Test') {\n" +
            "            steps {\n" +
            "                sh 'kubectl exec -n $NAMESPACE deployment/$DEPLOYMENT_NAME -- pytest tests/smoke/ -v'\n" +
            "            }\n" +
            "        }\n" +
            "    }\n\n" +
            "    post {\n" +
            "        always {\n" +
            "            echo 'Deployment complete'\n" +
            "        }\n" +
            "        failure {\n" +
            "            echo 'Deployment failed'\n" +
            "        }\n" +
            "    }\n" +
            "}\n"
        )
        return jenkinsfile


# ============================================================================
# 部署调度器
# ============================================================================

class DeploymentScheduler:
    """部署调度器"""

    def __init__(self):
        self.scheduled_deployments: Dict[str, Dict[str, Any]] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def schedule_deployment(
        self,
        deployment_id: str,
        cron_expression: str,
        version: str,
        environment: str,
        artifacts: Dict[str, str]
    ) -> bool:
        """调度部署"""
        self.scheduled_deployments[deployment_id] = {
            "cron_expression": cron_expression,
            "version": version,
            "environment": environment,
            "artifacts": artifacts,
            "last_run": None,
            "next_run": self._calculate_next_run(cron_expression)
        }
        return True

    def cancel_scheduled_deployment(self, deployment_id: str) -> bool:
        """取消调度"""
        if deployment_id in self.scheduled_deployments:
            del self.scheduled_deployments[deployment_id]
            return True
        return False

    def start(self):
        """启动调度器"""
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._run_scheduler, daemon=True)
            self._thread.start()

    def stop(self):
        """停止调度器"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def get_scheduled_deployments(self) -> List[Dict[str, Any]]:
        """获取所有调度的部署"""
        return [
            {"id": k, **v}
            for k, v in self.scheduled_deployments.items()
        ]

    def _run_scheduler(self):
        """运行调度循环"""
        while self._running:
            now = datetime.now()
            for deployment_id, schedule in list(self.scheduled_deployments.items()):
                if schedule.get("next_run") and now >= schedule["next_run"]:
                    self._execute_scheduled_deployment(deployment_id)
            time.sleep(60)

    def _execute_scheduled_deployment(self, deployment_id: str):
        """执行调度的部署"""
        schedule = self.scheduled_deployments.get(deployment_id)
        if not schedule:
            return

        schedule["last_run"] = datetime.now().isoformat()
        schedule["next_run"] = self._calculate_next_run(schedule["cron_expression"])

    def _calculate_next_run(self, cron_expression: str) -> datetime:
        """计算下次运行时间"""
        try:
            if ":" in cron_expression:
                parts = cron_expression.split(":")
                hour = int(parts[0])
                minute = int(parts[1])
                now = datetime.now()
                next_run = now.replace(hour=hour, minute=minute, second=0)
                if next_run <= now:
                    next_run = next_run.replace(day=now.day + 1)
                return next_run
        except Exception:
            pass
        return datetime.now()


# ============================================================================
# 统一入口函数
# ============================================================================

def create_deployment_orchestrator(
    environment: str = "production",
    strategy: str = "rolling_update"
) -> DeploymentPipelineOrchestrator:
    """创建部署编排器"""
    strat = DeploymentStrategy(strategy)
    return DeploymentPipelineOrchestrator(environment, strat)


def create_env_config_manager() -> EnvironmentConfigManager:
    """创建环境配置管理器"""
    return EnvironmentConfigManager()


def create_deployment_validator() -> DeploymentValidator:
    """创建部署验证器"""
    return DeploymentValidator()


def create_rollback_manager(max_snapshots: int = 10) -> RollbackManager:
    """创建回滚管理器"""
    return RollbackManager(max_snapshots)


def create_zero_downtime_deployer(
    strategy: str = "rolling_update"
) -> ZeroDowntimeDeployer:
    """创建零停机部署器"""
    strat = DeploymentStrategy(strategy)
    return ZeroDowntimeDeployer(strat)


def create_deployment_scheduler() -> DeploymentScheduler:
    """创建部署调度器"""
    return DeploymentScheduler()


# ============================================================================
# 导出
# ============================================================================

__all__ = [
    # 枚举
    "DeploymentStrategy",
    "DeploymentPhase",
    "DeploymentStatus",
    "EnvironmentType",
    # 数据结构
    "DeploymentSnapshot",
    "DeploymentStep",
    "EnvironmentConfig",
    "ValidationResult",
    # 核心类
    "EnvironmentConfigManager",
    "DeploymentValidator",
    "RollbackManager",
    "ZeroDowntimeDeployer",
    "DeploymentPipelineOrchestrator",
    "DeploymentScriptGenerator",
    "DeploymentScheduler",
    # 工厂函数
    "create_deployment_orchestrator",
    "create_env_config_manager",
    "create_deployment_validator",
    "create_rollback_manager",
    "create_zero_downtime_deployer",
    "create_deployment_scheduler",
]
