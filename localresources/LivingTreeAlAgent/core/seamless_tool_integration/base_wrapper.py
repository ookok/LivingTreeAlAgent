"""
Base Wrapper & Manager - 基础封装与管理器

提供工具封装的基类和统一管理接口
"""

from typing import Optional, Dict, List, Any, Callable, Type
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum


class ToolCategory(Enum):
    """工具类别"""
    AIR_QUALITY = "air_quality"       # 大气质量预测
    WATER_QUALITY = "water_quality"   # 水质预测
    NOISE = "noise"                   # 噪声预测
    SOIL = "soil"                     # 土壤预测
    ECOLOGICAL = "ecological"         # 生态预测
    CUSTOM = "custom"                 # 自定义


@dataclass
class ToolMetadata:
    """工具元数据"""
    tool_id: str
    name: str
    category: ToolCategory
    version: str
    description: str
    author: str = ""
    homepage: str = ""
    license: str = ""

    # 能力
    capabilities: List[str] = field(default_factory=list)
    input_formats: List[str] = field(default_factory=list)
    output_formats: List[str] = field(default_factory=list)

    # 需求
    hardware_requirements: Dict[str, str] = field(default_factory=dict)
    software_requirements: List[str] = field(default_factory=list)


class BaseToolWrapper(ABC):
    """
    工具封装基类

    所有工具封装都应该继承此类

    使用示例：
    ```python
    class MyToolWrapper(BaseToolWrapper):
        def get_metadata(self):
            return ToolMetadata(
                tool_id="mytool",
                name="我的工具",
                category=ToolCategory.AIR_QUALITY,
                ...
            )

        def check_availability(self) -> bool:
            return True

        def deploy(self, progress_callback):
            pass

        def execute(self, project_data, callback):
            pass
    ```
    """

    def __init__(self):
        self._is_deployed = False

    @abstractmethod
    def get_metadata(self) -> ToolMetadata:
        """获取工具元数据"""
        pass

    @abstractmethod
    def check_availability(self) -> bool:
        """检查工具是否可用"""
        pass

    @abstractmethod
    def deploy(self, progress_callback: Optional[Callable] = None) -> bool:
        """部署工具"""
        pass

    @abstractmethod
    def execute(
        self,
        project_data: Any,
        progress_callback: Optional[Callable] = None,
        **kwargs
    ) -> Any:
        """
        执行工具

        Args:
            project_data: 项目数据
            progress_callback: 进度回调

        Returns:
            执行结果
        """
        pass

    @abstractmethod
    def cleanup(self):
        """清理资源"""
        pass

    @property
    def is_ready(self) -> bool:
        """工具是否就绪"""
        return self._is_deployed and self.check_availability()


# 全局工具注册表
_TOOL_WRAPPERS: Dict[str, Type[BaseToolWrapper]] = {}


def register_tool_wrapper(tool_id: str, wrapper_class: Type[BaseToolWrapper]):
    """
    注册工具封装类

    Args:
        tool_id: 工具ID
        wrapper_class: 封装类
    """
    _TOOL_WRAPPERS[tool_id] = wrapper_class


def get_tool_wrapper(tool_id: str) -> Optional[BaseToolWrapper]:
    """
    获取工具封装实例

    Args:
        tool_id: 工具ID

    Returns:
        封装实例或None
    """
    wrapper_class = _TOOL_WRAPPERS.get(tool_id)
    if wrapper_class:
        return wrapper_class()
    return None


def list_registered_tools() -> List[str]:
    """列出所有已注册的工具ID"""
    return list(_TOOL_WRAPPERS.keys())


# 预注册的工具封装
def _register_builtin_tools():
    """注册内置工具封装"""
    from .model_deployer import ModelDeployer
    from .input_generator import InputGenerator, ProjectData
    from .tool_executor import ToolExecutor
    from .result_parser import ResultParser

    # 这些将在实际使用时动态加载
    pass


# 自动注册
_register_builtin_tools()
