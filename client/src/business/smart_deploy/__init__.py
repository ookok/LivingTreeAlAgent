"""
智能轻量化部署模块 - Smart Deployment System
核心理念：零配置启动、智能适应、自愈执行、安全模拟

四层架构：
1. 用户交互层 - 多模态输入、富文本编辑、沙箱模拟、部署仪表板
2. 智能决策层 - 意图理解、环境分析、策略生成、错误预测
3. 执行引擎层 - 跨平台适配、并发控制、障碍解决、回滚引擎
4. 安全保障层 - 静态分析、沙箱模拟、权限控制、审计追踪

创新功能（V2.0）：
- health_score: 部署健康度评分系统（让每次部署都有风险分数）
- adaptive_timeout: 自适应超时机制（告别随便设30秒）
- smart_advisor: 智能部署顾问（AI帮你选择最佳部署时机）

主要模块：
- intent_understanding: 意图理解引擎
- environment_analyzer: 环境分析器
- strategy_generator: 策略生成器
- sandbox_executor: 沙箱模拟器
- deployment_engine: 部署执行引擎
- obstacle_resolver: 障碍自动解决器
- multi_mode_input: 多模态输入系统
- learning_system: 新手学习系统
"""

from .intent_understanding import (
    IntentUnderstandingEngine, IntentType, TechStack, RiskLevel, IntentResult
)
from .environment_analyzer import (
    EnvironmentAnalyzer, ServerType, ServerCapability, ServerInfo
)
from .strategy_generator import (
    StrategyGenerator, DeploymentStrategy, DeploymentStep, GeneratedScript, StrategyOption
)
from .sandbox_executor import (
    SandboxExecutor, SandboxStatus, StepStatus, SandboxConfig, SandboxReport, StepResult
)
from .deployment_engine import (
    DeploymentEngine, DeploymentStatus, ServerDeployment, DeploymentResult
)
from .obstacle_resolver import (
    ObstacleResolver, ObstacleType, Obstacle, Solution, ResolutionResult
)
from .multi_mode_input import (
    MultiModeInputHandler, InputMode, ParsedInput
)
from .learning_system import (
    LearningSystem, SkillLevel, Skill, Achievement, DailyTask, UserProgress, Explanation
)
from .health_score import (
    DeploymentHealthScore, HealthScore, HealthLevel, RiskFactor, DeploymentRecord
)
from .adaptive_timeout import (
    AdaptiveTimeout, TimeoutConfig
)
from .smart_advisor import (
    SmartDeployAdvisor, DeployAdvice, AdviceLevel, BestTimeWindow
)

__version__ = "2.0.0"
__all__ = [
    # 意图理解
    'IntentUnderstandingEngine', 'IntentType', 'TechStack', 'RiskLevel', 'IntentResult',

    # 环境分析
    'EnvironmentAnalyzer', 'ServerType', 'ServerCapability', 'ServerInfo',

    # 策略生成
    'StrategyGenerator', 'DeploymentStrategy', 'DeploymentStep', 'GeneratedScript', 'StrategyOption',

    # 沙箱模拟
    'SandboxExecutor', 'SandboxStatus', 'StepStatus', 'SandboxConfig', 'SandboxReport', 'StepResult',

    # 部署执行
    'DeploymentEngine', 'DeploymentStatus', 'ServerDeployment', 'DeploymentResult',

    # 障碍解决
    'ObstacleResolver', 'ObstacleType', 'Obstacle', 'Solution', 'ResolutionResult',

    # 多模态输入
    'MultiModeInputHandler', 'InputMode', 'ParsedInput',

    # 学习系统
    'LearningSystem', 'SkillLevel', 'Skill', 'Achievement', 'DailyTask', 'UserProgress', 'Explanation',

    # 健康度评分
    'DeploymentHealthScore', 'HealthScore', 'HealthLevel', 'RiskFactor', 'DeploymentRecord',

    # 自适应超时
    'AdaptiveTimeout', 'TimeoutConfig',

    # 智能顾问
    'SmartDeployAdvisor', 'DeployAdvice', 'AdviceLevel', 'BestTimeWindow',
]

# 全局实例
intent_engine = IntentUnderstandingEngine()
env_analyzer = EnvironmentAnalyzer()
strategy_gen = StrategyGenerator()
sandbox = SandboxExecutor()
deploy_engine = DeploymentEngine()
obstacle_resolver = ObstacleResolver()
multi_input = MultiModeInputHandler()
learning = LearningSystem()
health_score = DeploymentHealthScore()
adaptive_timeout = AdaptiveTimeout()
smart_advisor = SmartDeployAdvisor()
