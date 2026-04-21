"""
意图理解引擎 - IntentUnderstandingEngine
核心理念：理解用户想做什么

功能：
1. 多模态输入解析（文本/截图/语音/文件）
2. 部署目标识别
3. 技术栈检测
4. 环境需求分析
5. 风险评估
"""

import re
import os
import json
import hashlib
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class IntentType(Enum):
    """意图类型"""
    DEPLOY = "deploy"                    # 部署应用
    CONFIGURE = "configure"              # 配置服务
    UPDATE = "update"                    # 更新应用
    SCALE = "scale"                      # 扩缩容
    MONITOR = "monitor"                  # 监控查看
    BACKUP = "backup"                    # 备份数据
    RESTORE = "restore"                  # 恢复数据
    UNKNOWN = "unknown"                  # 未知


class TechStack(Enum):
    """技术栈类型"""
    PYTHON = "python"
    NODEJS = "nodejs"
    JAVA = "java"
    GOLANG = "golang"
    RUST = "rust"
    DOTNET = "dotnet"
    PHP = "php"
    STATIC = "static"                    # 静态网站
    DOCKER = "docker"
    DATABASE = "database"
    UNKNOWN = "unknown"


class RiskLevel(Enum):
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class IntentResult:
    """意图理解结果"""
    intent_type: IntentType
    confidence: float
    target_description: str
    tech_stack: TechStack
    deployment_type: str                  # 'docker'/'vm'/'bare_metal'/'serverless'
    environment: Dict[str, Any]            # 环境需求
    risk_level: RiskLevel
    risk_factors: List[str]
    requirements: List[str]               # 必需的条件
    suggestions: List[str]                # 建议
    raw_input: str                        # 原始输入
    parsed_at: datetime = field(default_factory=datetime.now)


class IntentUnderstandingEngine:
    """
    意图理解引擎

    分析用户输入，理解部署需求
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init()
        return cls._instance

    def _init(self):
        self._keywords_map = self._build_keywords_map()
        self._tech_patterns = self._build_tech_patterns()
        self._risk_patterns = self._build_risk_patterns()
        self._analyze_count = 0

    def _build_keywords_map(self) -> Dict[IntentType, List[str]]:
        """构建关键词映射"""
        return {
            IntentType.DEPLOY: [
                '部署', '上线', '发布', '安装', '搭建', '创建',
                'deploy', 'install', 'setup', 'launch', 'start'
            ],
            IntentType.CONFIGURE: [
                '配置', '设置', '调整', '修改',
                'config', 'configure', 'setup', 'adjust'
            ],
            IntentType.UPDATE: [
                '更新', '升级', '迭代',
                'update', 'upgrade', 'upgrade'
            ],
            IntentType.SCALE: [
                '扩容', '缩容', '扩展',
                'scale', 'expand', 'shrink'
            ],
            IntentType.MONITOR: [
                '监控', '查看', '状态', '日志',
                'monitor', 'check', 'status', 'log'
            ],
            IntentType.BACKUP: [
                '备份', '导出',
                'backup', 'export'
            ],
            IntentType.RESTORE: [
                '恢复', '导入', '还原',
                'restore', 'import', 'recover'
            ]
        }

    def _build_tech_patterns(self) -> Dict[TechStack, Dict[str, Any]]:
        """构建技术栈识别模式"""
        return {
            TechStack.PYTHON: {
                'keywords': ['python', 'python3', 'django', 'flask', 'fastapi', 'pip'],
                'files': ['requirements.txt', 'setup.py', 'pyproject.toml', 'Pipfile'],
                'dockerfile_patterns': ['python:', 'FROM python', 'pip install']
            },
            TechStack.NODEJS: {
                'keywords': ['node', 'nodejs', 'npm', 'yarn', 'pnpm', 'express', 'nextjs', 'react'],
                'files': ['package.json', 'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml'],
                'dockerfile_patterns': ['node:', 'FROM node', 'npm install']
            },
            TechStack.JAVA: {
                'keywords': ['java', 'maven', 'gradle', 'spring', 'tomcat'],
                'files': ['pom.xml', 'build.gradle', 'application.properties'],
                'dockerfile_patterns': ['java:', 'FROM openjdk', 'maven']
            },
            TechStack.GOLANG: {
                'keywords': ['golang', 'go ', 'go mod'],
                'files': ['go.mod', 'go.sum'],
                'dockerfile_patterns': ['golang:', 'FROM golang']
            },
            TechStack.RUST: {
                'keywords': ['rust', 'cargo', 'rustc'],
                'files': ['Cargo.toml', 'Cargo.lock'],
                'dockerfile_patterns': ['rust:', 'FROM rust']
            },
            TechStack.DOCKER: {
                'keywords': ['docker', 'container', '镜像', '容器'],
                'files': ['Dockerfile', 'docker-compose.yml', 'docker-compose.yaml']
            },
            TechStack.DATABASE: {
                'keywords': ['mysql', 'postgresql', 'postgres', 'mongodb', 'redis', '数据库'],
                'files': ['.env', 'config.json']
            }
        }

    def _build_risk_patterns(self) -> Dict[RiskLevel, List[str]]:
        """构建风险识别模式"""
        return {
            RiskLevel.CRITICAL: [
                r'rm\s+-rf', r'drop\s+table', r'delete\s+from', r'--no-check-certificate',
                r'chmod\s+777', r'eval\s*\(', r'exec\s*\(', r'system\s*\('
            ],
            RiskLevel.HIGH: [
                r'sudo', r'root', r'passwd', r'chmod', r'kill', r'\|\s*sh',
                r'wget.*\|', r'curl.*\|', r'>\s*/dev/', r'2>&1'
            ],
            RiskLevel.MEDIUM: [
                r'yum\s+install', r'apt\s+install', r'apk\s+add', r'pip\s+install',
                r'npm\s+install', r'docker\s+run', r'service\s+restart'
            ],
            RiskLevel.LOW: [
                r'ls', r'cat', r'grep', r'cd', r'pwd', r'mkdir', r'echo'
            ]
        }

    def analyze(self, user_input: str, context: Optional[Dict] = None) -> IntentResult:
        """
        分析用户输入，理解意图

        Args:
            user_input: 用户输入（文本描述）
            context: 额外上下文信息

        Returns:
            IntentResult: 意图理解结果
        """
        self._analyze_count += 1
        context = context or {}

        # 1. 识别意图类型
        intent_type, intent_confidence = self._detect_intent(user_input)

        # 2. 检测技术栈
        tech_stack, tech_confidence = self._detect_tech_stack(user_input, context)

        # 3. 分析环境需求
        environment = self._analyze_environment(user_input, tech_stack, context)

        # 4. 风险评估
        risk_level, risk_factors = self._assess_risk(user_input, environment)

        # 5. 生成需求和建议
        requirements = self._generate_requirements(intent_type, tech_stack, environment)
        suggestions = self._generate_suggestions(intent_type, tech_stack, environment)

        # 6. 确定部署类型
        deployment_type = self._determine_deployment_type(tech_stack, environment)

        # 综合置信度
        confidence = (intent_confidence * 0.4 + tech_confidence * 0.3 + (1 - risk_level.value / 3) * 0.3)

        return IntentResult(
            intent_type=intent_type,
            confidence=confidence,
            target_description=self._extract_target_description(user_input),
            tech_stack=tech_stack,
            deployment_type=deployment_type,
            environment=environment,
            risk_level=risk_level,
            risk_factors=risk_factors,
            requirements=requirements,
            suggestions=suggestions,
            raw_input=user_input
        )

    def _detect_intent(self, text: str) -> tuple:
        """检测意图类型"""
        text_lower = text.lower()
        scores = {}

        for intent_type, keywords in self._keywords_map.items():
            score = sum(1 for kw in keywords if kw.lower() in text_lower)
            if score > 0:
                scores[intent_type] = score

        if not scores:
            return IntentType.UNKNOWN, 0.5

        best_intent = max(scores, key=scores.get)
        confidence = min(scores[best_intent] / 3, 1.0)

        return best_intent, confidence

    def _detect_tech_stack(self, text: str, context: Dict) -> tuple:
        """检测技术栈"""
        text_lower = text.lower()
        scores = {}

        # 从文本中检测
        for tech, patterns in self._tech_patterns.items():
            score = 0
            # 关键词匹配
            for kw in patterns.get('keywords', []):
                if kw.lower() in text_lower:
                    score += 2
            # 文件匹配
            for f in patterns.get('files', []):
                if f in text_lower:
                    score += 3
            if score > 0:
                scores[tech] = score

        # 从上下文中检测（如已上传文件）
        if 'detected_files' in context:
            for tech, patterns in self._tech_patterns.items():
                for f in patterns.get('files', []):
                    if any(f in detected for detected in context['detected_files']):
                        scores[tech] = scores.get(tech, 0) + 5

        if not scores:
            return TechStack.UNKNOWN, 0.3

        best_tech = max(scores, key=scores.get)
        confidence = min(scores[best_tech] / 5, 1.0)

        return best_tech, confidence

    def _analyze_environment(self, text: str, tech_stack: TechStack, context: Dict) -> Dict[str, Any]:
        """分析环境需求"""
        env = {
            'os_type': 'linux',           # 默认Linux
            'os_distro': None,
            'cpu_cores': 2,
            'memory_mb': 2048,
            'disk_gb': 20,
            'network_required': True,
            'ports': [],
            'dependencies': [],
            'environment_type': 'production'  # production/development
        }

        text_lower = text.lower()

        # 检测OS
        if any(kw in text_lower for kw in ['windows', 'win', 'powershell']):
            env['os_type'] = 'windows'
        elif any(kw in text_lower for kw in ['mac', 'darwin', 'homebrew']):
            env['os_type'] = 'macos'

        # 检测配置要求
        if '开发环境' in text or 'dev' in text_lower:
            env['environment_type'] = 'development'

        # 检测资源要求
        mem_match = re.search(r'(\d+)\s*[GM]B?', text)
        if mem_match:
            mem_value = int(mem_match.group(1))
            env['memory_mb'] = mem_value * 1024 if 'G' in mem_match.group(0) else mem_value

        cpu_match = re.search(r'(\d+)\s*[核个]', text)
        if cpu_match:
            env['cpu_cores'] = int(cpu_match.group(1))

        # 检测端口
        port_matches = re.findall(r'(\d{4,5})(?:\s*(?:端口|port|:))?', text)
        env['ports'] = [int(p) for p in port_matches if 80 <= int(p) <= 65535][:10]

        # 技术栈特定依赖
        if tech_stack == TechStack.PYTHON:
            env['dependencies'] = ['python3', 'pip']
        elif tech_stack == TechStack.NODEJS:
            env['dependencies'] = ['nodejs', 'npm']
        elif tech_stack == TechStack.JAVA:
            env['dependencies'] = ['java', 'maven']

        return env

    def _assess_risk(self, text: str, environment: Dict) -> tuple:
        """评估风险"""
        risk_level = RiskLevel.LOW
        risk_factors = []

        text_lower = text.lower()

        # 检查危险命令模式
        for level, patterns in self._risk_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    if level.value > risk_level.value:
                        risk_level = level
                    risk_factors.append(f"检测到危险模式: {pattern}")

        # 检查权限要求
        if 'sudo' in text_lower or 'root' in text_lower:
            if risk_level.value < RiskLevel.MEDIUM.value:
                risk_level = RiskLevel.MEDIUM
            risk_factors.append("需要sudo/root权限")

        # 检查生产环境
        if environment.get('environment_type') == 'production':
            if '更新' in text or '升级' in text:
                risk_factors.append("生产环境更新有风险")

        # 检查数据操作
        if any(kw in text_lower for kw in ['删除', 'drop', 'delete', 'truncate']):
            risk_level = RiskLevel(max(risk_level.value, RiskLevel.HIGH.value))
            risk_factors.append("涉及数据删除操作")

        return risk_level, risk_factors

    def _generate_requirements(self, intent_type: IntentType, tech_stack: TechStack, environment: Dict) -> List[str]:
        """生成需求列表"""
        requirements = []

        # 基础需求
        requirements.append(f"目标服务器: {environment['os_type']}")

        if environment['cpu_cores'] > 0:
            requirements.append(f"CPU: {environment['cpu_cores']}核")
        if environment['memory_mb'] > 0:
            requirements.append(f"内存: {environment['memory_mb']}MB")

        # 技术栈特定
        if tech_stack == TechStack.PYTHON:
            requirements.append("Python 3.8+")
            requirements.append("pip包管理器")
        elif tech_stack == TechStack.NODEJS:
            requirements.append("Node.js 14+")
            requirements.append("npm/yarn/pnpm")

        # 端口需求
        if environment['ports']:
            requirements.append(f"需要开放端口: {', '.join(map(str, environment['ports']))}")

        # 网络需求
        if environment['network_required']:
            requirements.append("网络连接（下载依赖）")

        return requirements

    def _generate_suggestions(self, intent_type: IntentType, tech_stack: TechStack, environment: Dict) -> List[str]:
        """生成建议列表"""
        suggestions = []

        # 风险建议
        if environment.get('environment_type') == 'production':
            suggestions.append("建议先在测试环境验证")
            suggestions.append("开启回滚机制")

        # 技术建议
        if tech_stack == TechStack.PYTHON:
            suggestions.append("推荐使用虚拟环境隔离依赖")
            suggestions.append("使用requirements.txt管理依赖")
        elif tech_stack == TechStack.NODEJS:
            suggestions.append("推荐使用package-lock.json锁定版本")
            suggestions.append("生产环境建议使用pnpm提升安装速度")

        # 安全建议
        suggestions.append("使用非root用户运行服务")
        suggestions.append("配置防火墙规则限制访问")

        return suggestions

    def _determine_deployment_type(self, tech_stack: TechStack, environment: Dict) -> str:
        """确定部署类型"""
        if tech_stack == TechStack.DOCKER:
            return 'docker'
        elif environment.get('environment_type') == 'development':
            return 'direct'
        elif tech_stack in [TechStack.PYTHON, TechStack.NODEJS]:
            return 'virtualenv'  # 虚拟环境部署
        else:
            return 'systemd'  # 系统服务

    def _extract_target_description(self, text: str) -> str:
        """提取目标描述"""
        # 移除命令和参数，保留核心描述
        cleaned = re.sub(r'\$\s*', '', text)  # 移除$提示符
        cleaned = re.sub(r'\s+-\w+', '', cleaned)  # 移除短参数
        cleaned = re.sub(r'\s+--[\w-]+', '', cleaned)  # 移除长参数
        cleaned = cleaned.strip()

        # 限制长度
        if len(cleaned) > 100:
            cleaned = cleaned[:100] + "..."

        return cleaned

    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        return {
            "analyze_count": self._analyze_count
        }


# 全局单例
intent_engine = IntentUnderstandingEngine()
