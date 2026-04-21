"""
Seamless Tool Integration - 无感化外部工具集成框架

核心理念：用户只需要点击按钮，剩下的全部自动完成。
- 自动下载与部署外部工具
- 自动生成输入文件
- 透明执行无需用户配置
- 结果直接可视化呈现

三层架构：
┌─────────────────────────────────────────────────────────────┐
│  用户界面层 (UI Plugin)                                     │
│  • 可视化配置界面                                           │
│  • 进度反馈日志                                             │
│  • 结果图表展示                                             │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  服务封装层 (Wrapper)                                        │
│  • ModelDeployer - 自动部署管理器                           │
│  • InputGenerator - 输入文件生成器                           │
│  • ToolExecutor - 工具执行封装                               │
│  • ResultParser - 结果解析器                                 │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  执行引擎层 (Executor)                                       │
│  • AERMOD - 大气预测模型                                     │
│  • CALPUFF - 扩散模型                                        │
│  • PySPRAY - 开源替代方案                                    │
│  • Cloud API - 云端计算备选                                  │
└─────────────────────────────────────────────────────────────┘
"""

__version__ = "1.0.0"

from .model_deployer import ModelDeployer, ToolInfo, ToolType
from .input_generator import InputGenerator, ProjectData, AermodInputGenerator
from .tool_executor import ToolExecutor, ExecutionResult, ExecutionStatus
from .result_parser import ResultParser, PredictionResult, ConcentrationData
from .cloud_bridge import CloudBridge, CloudExecutionMode
from .base_wrapper import BaseToolWrapper, register_tool_wrapper

# 导出核心类
__all__ = [
    # 版本
    "__version__",
    # 部署管理
    "ModelDeployer",
    "ToolInfo",
    "ToolType",
    # 输入生成
    "InputGenerator",
    "ProjectData",
    "AermodInputGenerator",
    # 执行封装
    "ToolExecutor",
    "ExecutionResult",
    "ExecutionStatus",
    # 结果解析
    "ResultParser",
    "PredictionResult",
    "ConcentrationData",
    # 云端备选
    "CloudBridge",
    "CloudExecutionMode",
    # 基类
    "BaseToolWrapper",
    "register_tool_wrapper",
]


def get_seamless_integration_manager():
    """获取无缝集成管理器单例"""
    from .manager import SeamlessIntegrationManager
    return SeamlessIntegrationManager.get_instance()
