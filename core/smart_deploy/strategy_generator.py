"""
策略生成器 - StrategyGenerator
核心理念：根据意图和环境选择最优部署方案

功能：
1. 部署策略选择
2. 脚本生成
3. 参数优化
4. 方案比较
"""

import hashlib
import re
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging

from .intent_understanding import IntentType, TechStack, IntentUnderstandingEngine
from .environment_analyzer import ServerInfo, ServerCapability

logger = logging.getLogger(__name__)


class DeploymentStrategy(Enum):
    """部署策略"""
    DIRECT = "direct"              # 直接运行
    VIRTUALENV = "virtualenv"      # 虚拟环境
    DOCKER = "docker"              # Docker容器
    SYSTEMD = "systemd"            # 系统服务
    DOCKER_COMPOSE = "docker_compose"  # Docker Compose
    KUBERNETES = "kubernetes"       # K8s


@dataclass
class DeploymentStep:
    """部署步骤"""
    step_id: int
    name: str
    description: str
    command: str
    rollback_command: Optional[str]
    estimated_time_seconds: int
    risk_level: str
    required_permissions: List[str]
    verify_command: Optional[str]


@dataclass
class GeneratedScript:
    """生成的脚本"""
    strategy: DeploymentStrategy
    language: str
    steps: List[DeploymentStep]
    full_script: str
    rollback_script: str
    verify_script: str
    estimated_total_time_seconds: int
    prerequisites: List[str]
    estimated_resources: Dict[str, Any]


@dataclass
class StrategyOption:
    """策略选项"""
    strategy: DeploymentStrategy
    score: float
    pros: List[str]
    cons: List[str]
    estimated_time_minutes: int
    resource_requirements: Dict[str, Any]


class StrategyGenerator:
    """
    策略生成器

    根据意图和环境生成最佳部署策略
    """

    def __init__(self):
        self._intent_engine = IntentUnderstandingEngine()
        self._strategy_templates = self._load_templates()

    def _load_templates(self) -> Dict[str, Any]:
        """加载策略模板"""
        return {
            "python_virtualenv": {
                "setup_commands": [
                    "python3 -m venv venv",
                    "source venv/bin/activate",
                    "pip install -r requirements.txt"
                ],
                "run_command": "source venv/bin/activate && python main.py"
            },
            "nodejs": {
                "setup_commands": ["npm install"],
                "run_command": "npm start"
            },
            "docker": {
                "run_command": "docker build -t {name} . && docker run -d -p {port}:{port} {name}"
            }
        }

    def generate(self, intent_result, server_info: ServerInfo) -> GeneratedScript:
        """生成部署策略和脚本"""
        strategy = self._select_strategy(intent_result, server_info)
        steps = self._generate_steps(intent_result, server_info, strategy)
        full_script = self._generate_full_script(intent_result, server_info, strategy, steps)
        rollback_script = self._generate_rollback_script(steps)
        verify_script = self._generate_verify_script(intent_result, steps)
        total_time = sum(s.estimated_time_seconds for s in steps)

        return GeneratedScript(
            strategy=strategy,
            language="bash" if server_info.server_type.value != "windows" else "powershell",
            steps=steps,
            full_script=full_script,
            rollback_script=rollback_script,
            verify_script=verify_script,
            estimated_total_time_seconds=total_time,
            prerequisites=self._generate_prerequisites(intent_result, server_info, strategy),
            estimated_resources=self._estimate_resources(intent_result, strategy)
        )

    def generate_options(self, intent_result, server_info: ServerInfo) -> List[StrategyOption]:
        """生成多个策略选项"""
        options = []

        for strategy in DeploymentStrategy:
            if self._is_strategy_feasible(strategy, intent_result, server_info):
                option = self._evaluate_strategy(strategy, intent_result, server_info)
                options.append(option)

        options.sort(key=lambda x: x.score, reverse=True)
        return options[:3]

    def _select_strategy(self, intent_result, server_info: ServerInfo) -> DeploymentStrategy:
        """选择最佳策略"""
        options = self.generate_options(intent_result, server_info)
        return options[0].strategy if options else DeploymentStrategy.DIRECT

    def _is_strategy_feasible(self, strategy: DeploymentStrategy, intent_result, server_info: ServerInfo) -> bool:
        """检查策略是否可行"""
        if strategy == DeploymentStrategy.DOCKER:
            return server_info.docker_available
        elif strategy == DeploymentStrategy.SYSTEMD:
            return server_info.server_type.value == "linux"
        elif strategy == DeploymentStrategy.VIRTUALENV:
            return intent_result.tech_stack in [TechStack.PYTHON, TechStack.NODEJS]
        return True

    def _evaluate_strategy(self, strategy: DeploymentStrategy, intent_result, server_info: ServerInfo) -> StrategyOption:
        """评估策略"""
        score = 70.0
        pros = []
        cons = []
        time_estimate = 10

        if strategy == DeploymentStrategy.DIRECT:
            pros = ["简单快速", "资源占用少"]
            cons = ["难以管理", "环境污染风险"]
            time_estimate = 5
        elif strategy == DeploymentStrategy.VIRTUALENV:
            pros = ["环境隔离", "版本控制", "依赖管理"]
            cons = ["需要额外配置"]
            time_estimate = 10
            score += 10
        elif strategy == DeploymentStrategy.DOCKER:
            pros = ["完全隔离", "环境一致", "易于分发"]
            cons = ["需要Docker", "资源占用高"]
            time_estimate = 15
            score += 15 if server_info.docker_available else -50
        elif strategy == DeploymentStrategy.SYSTEMD:
            pros = ["开机自启", "进程管理", "日志记录"]
            cons = ["需要root", "Linux专属"]
            time_estimate = 15
            score += 10 if server_info.server_type.value == "linux" else -50

        if server_info.capability == ServerCapability.LOW:
            if strategy in [DeploymentStrategy.DOCKER, DeploymentStrategy.KUBERNETES]:
                score -= 30

        return StrategyOption(
            strategy=strategy,
            score=score,
            pros=pros,
            cons=cons,
            estimated_time_minutes=time_estimate,
            resource_requirements=self._estimate_resources(intent_result, strategy)
        )

    def _generate_steps(self, intent_result, server_info: ServerInfo, strategy: DeploymentStrategy) -> List[DeploymentStep]:
        """生成部署步骤"""
        steps = []
        step_id = 1

        steps.append(DeploymentStep(
            step_id=step_id,
            name="环境检查",
            description="检查服务器环境和依赖",
            command="echo '检查环境...' && python3 --version && free -h",
            rollback_command=None,
            estimated_time_seconds=10,
            risk_level="low",
            required_permissions=["read"],
            verify_command=None
        ))
        step_id += 1

        if strategy == DeploymentStrategy.VIRTUALENV:
            steps.extend(self._generate_virtualenv_steps(intent_result))
        elif strategy == DeploymentStrategy.DOCKER:
            steps.extend(self._generate_docker_steps(intent_result))
        elif strategy == DeploymentStrategy.SYSTEMD:
            steps.extend(self._generate_systemd_steps(intent_result))

        steps.append(DeploymentStep(
            step_id=step_id,
            name="健康检查",
            description="验证服务是否正常运行",
            command="curl -s http://localhost:8000/health || pgrep -f 'python main.py'",
            rollback_command=None,
            estimated_time_seconds=5,
            risk_level="low",
            required_permissions=["read"],
            verify_command=None
        ))

        return steps

    def _generate_virtualenv_steps(self, intent_result) -> List[DeploymentStep]:
        """生成虚拟环境部署步骤

        根据技术栈自动适配：Python/NodeJS使用虚拟环境，
        其他技术栈使用标准目录隔离
        """
        tech = intent_result.tech_stack

        if tech == TechStack.PYTHON:
            return [
                DeploymentStep(
                    step_id=2,
                    name="创建虚拟环境",
                    description="创建Python虚拟环境",
                    command="python3 -m venv venv",
                    rollback_command="rm -rf venv",
                    estimated_time_seconds=30,
                    risk_level="low",
                    required_permissions=["write"],
                    verify_command="test -d venv/bin/python"
                ),
                DeploymentStep(
                    step_id=3,
                    name="安装依赖",
                    description="安装项目依赖",
                    command="source venv/bin/activate && pip install -r requirements.txt",
                    rollback_command="source venv/bin/activate && pip uninstall -y -r requirements.txt",
                    estimated_time_seconds=120,
                    risk_level="medium",
                    required_permissions=["sudo"],
                    verify_command="source venv/bin/activate && python -c 'import pkg_resources'"
                ),
                DeploymentStep(
                    step_id=4,
                    name="启动服务",
                    description="后台启动服务",
                    command="source venv/bin/activate && nohup python main.py > app.log 2>&1 &",
                    rollback_command="pkill -f 'python main.py'",
                    estimated_time_seconds=10,
                    risk_level="medium",
                    required_permissions=["write"],
                    verify_command="pgrep -f 'python main.py'"
                )
            ]
        elif tech == TechStack.NODEJS:
            return [
                DeploymentStep(
                    step_id=2,
                    name="安装依赖",
                    description="安装Node.js依赖",
                    command="npm install",
                    rollback_command="rm -rf node_modules",
                    estimated_time_seconds=60,
                    risk_level="medium",
                    required_permissions=["sudo"],
                    verify_command="test -d node_modules"
                ),
                DeploymentStep(
                    step_id=3,
                    name="启动服务",
                    description="后台启动服务",
                    command="nohup npm start > app.log 2>&1 &",
                    rollback_command="pkill -f 'npm start'",
                    estimated_time_seconds=10,
                    risk_level="medium",
                    required_permissions=["write"],
                    verify_command="pgrep -f 'node'"
                )
            ]
        elif tech == TechStack.JAVA:
            return [
                DeploymentStep(
                    step_id=2,
                    name="创建项目目录",
                    description="创建应用目录结构",
                    command="mkdir -p /opt/{app_name}/lib /opt/{app_name}/bin",
                    rollback_command="rm -rf /opt/{app_name}",
                    estimated_time_seconds=10,
                    risk_level="low",
                    required_permissions=["sudo"],
                    verify_command="test -d /opt/{app_name}"
                ),
                DeploymentStep(
                    step_id=3,
                    name="构建项目",
                    description="编译Java项目",
                    command="mvn clean package -DskipTests",
                    rollback_command=None,
                    estimated_time_seconds=180,
                    risk_level="medium",
                    required_permissions=["write"],
                    verify_command="test -f target/*.jar"
                ),
                DeploymentStep(
                    step_id=4,
                    name="启动服务",
                    description="后台启动Java服务",
                    command="nohup java -jar target/*.jar > app.log 2>&1 &",
                    rollback_command="pkill -f '.jar'",
                    estimated_time_seconds=30,
                    risk_level="medium",
                    required_permissions=["write"],
                    verify_command="pgrep -f '.jar'"
                )
            ]
        elif tech == TechStack.GO:
            return [
                DeploymentStep(
                    step_id=2,
                    name="编译项目",
                    description="编译Go项目",
                    command="go build -o myapp",
                    rollback_command="rm -f myapp",
                    estimated_time_seconds=60,
                    risk_level="low",
                    required_permissions=["write"],
                    verify_command="test -f myapp"
                ),
                DeploymentStep(
                    step_id=3,
                    name="启动服务",
                    description="后台启动服务",
                    command="nohup ./myapp > app.log 2>&1 &",
                    rollback_command="pkill -f './myapp'",
                    estimated_time_seconds=10,
                    risk_level="medium",
                    required_permissions=["write"],
                    verify_command="pgrep -f './myapp'"
                )
            ]
        elif tech == TechStack.RUST:
            return [
                DeploymentStep(
                    step_id=2,
                    name="编译项目",
                    description="编译Rust项目",
                    command="cargo build --release",
                    rollback_command="rm -rf target/release/myapp",
                    estimated_time_seconds=300,
                    risk_level="medium",
                    required_permissions=["write"],
                    verify_command="test -f target/release/myapp"
                ),
                DeploymentStep(
                    step_id=3,
                    name="启动服务",
                    description="后台启动服务",
                    command="nohup ./target/release/myapp > app.log 2>&1 &",
                    rollback_command="pkill -f 'myapp'",
                    estimated_time_seconds=10,
                    risk_level="medium",
                    required_permissions=["write"],
                    verify_command="pgrep -f 'myapp'"
                )
            ]
        else:
            # 通用部署步骤（适用于静态网站、其他语言等）
            return [
                DeploymentStep(
                    step_id=2,
                    name="创建部署目录",
                    description="创建应用部署目录",
                    command="mkdir -p /var/www/{app_name}",
                    rollback_command="rm -rf /var/www/{app_name}",
                    estimated_time_seconds=10,
                    risk_level="low",
                    required_permissions=["sudo"],
                    verify_command="test -d /var/www/{app_name}"
                ),
                DeploymentStep(
                    step_id=3,
                    name="上传文件",
                    description="复制应用文件到部署目录",
                    command="cp -r ./dist/* /var/www/{app_name}/",
                    rollback_command="rm -rf /var/www/{app_name}/*",
                    estimated_time_seconds=60,
                    risk_level="medium",
                    required_permissions=["sudo"],
                    verify_command="test -f /var/www/{app_name}/index.html"
                ),
                DeploymentStep(
                    step_id=4,
                    name="设置权限",
                    description="配置正确的文件权限",
                    command="chmod -R 755 /var/www/{app_name}",
                    rollback_command=None,
                    estimated_time_seconds=10,
                    risk_level="low",
                    required_permissions=["sudo"],
                    verify_command="ls -la /var/www/{app_name}"
                )
            ]

    def _generate_docker_steps(self, intent_result) -> List[DeploymentStep]:
        """生成Docker部署步骤"""
        name = intent_result.target_description.replace(' ', '-').lower()[:50]
        return [
            DeploymentStep(
                step_id=2,
                name="构建Docker镜像",
                description="构建应用Docker镜像",
                command=f"docker build -t {name}:latest .",
                rollback_command=f"docker rmi {name}:latest",
                estimated_time_seconds=180,
                risk_level="medium",
                required_permissions=["sudo"],
                verify_command="docker images"
            ),
            DeploymentStep(
                step_id=3,
                name="运行容器",
                description="启动Docker容器",
                command=f"docker run -d -p 8000:8000 --name {name} {name}:latest",
                rollback_command=f"docker stop {name} && docker rm {name}",
                estimated_time_seconds=30,
                risk_level="medium",
                required_permissions=["sudo"],
                verify_command=f"docker ps | grep {name}"
            )
        ]

    def _generate_systemd_steps(self, intent_result) -> List[DeploymentStep]:
        """生成Systemd服务部署步骤"""
        service_name = intent_result.target_description.replace(' ', '_').lower()[:50]
        return [
            DeploymentStep(
                step_id=2,
                name="创建服务文件",
                description="创建systemd服务配置",
                command=f"""cat > /tmp/{service_name}.service << 'EOF'
[Unit]
Description={intent_result.target_description}
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/{service_name}
ExecStart=/opt/{service_name}/venv/bin/python main.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF
sudo mv /tmp/{service_name}.service /etc/systemd/system/""",
                rollback_command=f"sudo rm /etc/systemd/system/{service_name}.service",
                estimated_time_seconds=10,
                risk_level="high",
                required_permissions=["sudo"],
                verify_command=f"test -f /etc/systemd/system/{service_name}.service"
            ),
            DeploymentStep(
                step_id=3,
                name="启动服务",
                description="启动并启用服务",
                command=f"sudo systemctl daemon-reload && sudo systemctl start {service_name} && sudo systemctl enable {service_name}",
                rollback_command=f"sudo systemctl stop {service_name} && sudo systemctl disable {service_name}",
                estimated_time_seconds=20,
                risk_level="high",
                required_permissions=["sudo"],
                verify_command=f"sudo systemctl status {service_name}"
            )
        ]

    def _generate_full_script(self, intent_result, server_info: ServerInfo, strategy: DeploymentStrategy, steps: List[DeploymentStep]) -> str:
        """生成完整脚本"""
        lines = [
            "#!/bin/bash",
            f"# 部署脚本 - {intent_result.target_description}",
            f"# 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"# 策略: {strategy.value}",
            "",
            "set -e",
            "",
            "RED='\\033[0;31m'",
            "GREEN='\\033[0;32m'",
            "YELLOW='\\033[1;33m'",
            "NC='\\033[0m'",
            ""
        ]

        for step in steps:
            lines.extend([
                f"echo -e \"${{YELLOW}}[Step {step.step_id}] {step.name}${{NC}}\"",
                f"echo \"{step.description}\"",
                step.command,
                ""
            ])

        lines.append('echo -e "${{GREEN}}部署完成！${{NC}}"')

        return '\n'.join(lines)

    def _generate_rollback_script(self, steps: List[DeploymentStep]) -> str:
        """生成回滚脚本"""
        lines = [
            "#!/bin/bash",
            "# 回滚脚本",
            "",
            "set -e",
            "RED='\\033[0;31m'",
            "GREEN='\\033[0;32m'",
            "NC='\\033[0m'",
            ""
        ]

        for step in reversed(steps):
            if step.rollback_command:
                lines.extend([
                    f"echo -e \"${{RED}}回滚: {step.name}${{NC}}\"",
                    step.rollback_command,
                    ""
                ])

        lines.append('echo -e "${{GREEN}}回滚完成${{NC}}"')

        return '\n'.join(lines)

    def _generate_verify_script(self, intent_result, steps: List[DeploymentStep]) -> str:
        """生成验证脚本"""
        lines = ["#!/bin/bash", "# 验证脚本", ""]

        for step in steps:
            if step.verify_command:
                lines.extend([
                    f"if {step.verify_command}; then",
                    f'    echo "OK: {step.name}"',
                    "else",
                    f'    echo "FAIL: {step.name}"',
                    "    exit 1",
                    "fi",
                    ""
                ])

        return '\n'.join(lines)

    def _generate_prerequisites(self, intent_result, server_info: ServerInfo, strategy) -> List[str]:
        """生成前置条件"""
        prereqs = [
            f"服务器: {server_info.os_version}",
            f"可用内存: {server_info.memory_available_mb}MB"
        ]

        if strategy == DeploymentStrategy.DOCKER:
            prereqs.append(f"Docker: {server_info.docker_version or '未安装'}")

        if intent_result.tech_stack == TechStack.PYTHON:
            prereqs.extend(["Python 3.8+", "pip"])
        elif intent_result.tech_stack == TechStack.NODEJS:
            prereqs.extend(["Node.js 14+", "npm"])

        return prereqs

    def _estimate_resources(self, intent_result, strategy: DeploymentStrategy) -> Dict[str, Any]:
        """估算资源需求"""
        base = {"cpu_cores": 1, "memory_mb": 512, "disk_gb": 5}

        if intent_result.tech_stack == TechStack.PYTHON:
            base["memory_mb"] = 1024
        elif intent_result.tech_stack == TechStack.JAVA:
            base["memory_mb"] = 2048
            base["cpu_cores"] = 2

        if strategy == DeploymentStrategy.DOCKER:
            base["memory_mb"] = int(base["memory_mb"] * 1.5)
            base["disk_gb"] += 2

        return base


strategy_generator = StrategyGenerator()
