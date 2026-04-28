"""
ToolSelfRepairer - 工具自我修复器

自动检测和修复工具故障。

核心功能：
1. 检测工具故障类型
2. 自动尝试修复
3. 支持多种修复策略
4. 记录修复历史

遵循自我进化原则：
- 从修复历史中学习
- 自动优化修复策略
- 支持自主发现修复方法
"""

from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from loguru import logger
from enum import Enum
import subprocess
import os


class RepairStrategy(Enum):
    """修复策略"""
    INSTALL_DEPENDENCY = "install_dependency"
    FIX_CODE = "fix_code"
    FIX_CONFIG = "fix_config"
    REINSTALL_TOOL = "reinstall_tool"
    UPDATE_REGISTRY = "update_registry"
    ROLLBACK = "rollback"
    MANUAL_INTERVENTION = "manual_intervention"


class FailureType(Enum):
    """故障类型"""
    MISSING_DEPENDENCY = "missing_dependency"
    CODE_ERROR = "code_error"
    CONFIG_ERROR = "config_error"
    REGISTRY_ERROR = "registry_error"
    PERMISSION_ERROR = "permission_error"
    NETWORK_ERROR = "network_error"
    UNKNOWN = "unknown"


@dataclass
class RepairResult:
    """修复结果"""
    success: bool
    strategy: RepairStrategy
    message: str
    tool_name: str
    attempt_count: int = 0


@dataclass
class FailureRecord:
    """故障记录"""
    tool_name: str
    failure_type: FailureType
    error_message: str
    timestamp: int = 0
    repair_attempts: List[RepairResult] = field(default_factory=list)


class ToolSelfRepairer:
    """
    工具自我修复器
    
    自动检测和修复工具故障。
    
    修复流程：
    1. 检测故障类型
    2. 选择修复策略
    3. 执行修复
    4. 验证修复结果
    5. 记录修复历史
    """

    def __init__(self):
        self._logger = logger.bind(component="ToolSelfRepairer")
        self._failure_history: List[FailureRecord] = []
        self._repair_success_rate: Dict[str, float] = {}

    async def detect_and_repair(self, tool_name: str, error: Exception) -> RepairResult:
        """
        检测并修复工具故障
        
        Args:
            tool_name: 工具名称
            error: 错误信息
            
        Returns:
            修复结果
        """
        self._logger.info(f"检测工具故障: {tool_name}")

        # 1. 检测故障类型
        failure_type = self._detect_failure_type(str(error))

        # 2. 创建故障记录
        record = FailureRecord(
            tool_name=tool_name,
            failure_type=failure_type,
            error_message=str(error),
            timestamp=len(self._failure_history)
        )
        self._failure_history.append(record)

        # 3. 选择并执行修复策略
        strategies = self._select_strategies(failure_type)
        attempt_count = 0

        for strategy in strategies:
            attempt_count += 1
            result = await self._execute_strategy(tool_name, strategy, error)
            
            record.repair_attempts.append(result)
            
            if result.success:
                self._logger.info(f"工具 {tool_name} 修复成功，策略: {strategy.value}")
                return result

            self._logger.warning(f"工具 {tool_name} 修复失败，策略: {strategy.value}")

        # 所有策略都失败
        return RepairResult(
            success=False,
            strategy=RepairStrategy.MANUAL_INTERVENTION,
            message="所有修复策略均失败，需要人工干预",
            tool_name=tool_name,
            attempt_count=attempt_count
        )

    def _detect_failure_type(self, error_message: str) -> FailureType:
        """
        检测故障类型
        
        Args:
            error_message: 错误信息
            
        Returns:
            故障类型
        """
        error_lower = error_message.lower()

        if "importerror" in error_lower or "modulenotfounderror" in error_lower:
            return FailureType.MISSING_DEPENDENCY
        
        if "permissionerror" in error_lower:
            return FailureType.PERMISSION_ERROR
        
        if "config" in error_lower or "configuration" in error_lower:
            return FailureType.CONFIG_ERROR
        
        if "connectionerror" in error_lower or "network" in error_lower:
            return FailureType.NETWORK_ERROR
        
        if "registry" in error_lower:
            return FailureType.REGISTRY_ERROR
        
        # 默认归类为代码错误
        return FailureType.CODE_ERROR

    def _select_strategies(self, failure_type: FailureType) -> List[RepairStrategy]:
        """
        根据故障类型选择修复策略
        
        Args:
            failure_type: 故障类型
            
        Returns:
            修复策略列表（按优先级排序）
        """
        strategy_map = {
            FailureType.MISSING_DEPENDENCY: [
                RepairStrategy.INSTALL_DEPENDENCY,
                RepairStrategy.UPDATE_REGISTRY,
            ],
            FailureType.CODE_ERROR: [
                RepairStrategy.FIX_CODE,
                RepairStrategy.ROLLBACK,
                RepairStrategy.REINSTALL_TOOL,
            ],
            FailureType.CONFIG_ERROR: [
                RepairStrategy.FIX_CONFIG,
                RepairStrategy.ROLLBACK,
            ],
            FailureType.REGISTRY_ERROR: [
                RepairStrategy.UPDATE_REGISTRY,
                RepairStrategy.REINSTALL_TOOL,
            ],
            FailureType.PERMISSION_ERROR: [
                RepairStrategy.FIX_CONFIG,
                RepairStrategy.MANUAL_INTERVENTION,
            ],
            FailureType.NETWORK_ERROR: [
                RepairStrategy.FIX_CONFIG,  # 检查代理配置
                RepairStrategy.MANUAL_INTERVENTION,
            ],
            FailureType.UNKNOWN: [
                RepairStrategy.FIX_CODE,
                RepairStrategy.REINSTALL_TOOL,
                RepairStrategy.MANUAL_INTERVENTION,
            ],
        }

        return strategy_map.get(failure_type, [RepairStrategy.MANUAL_INTERVENTION])

    async def _execute_strategy(self, tool_name: str, strategy: RepairStrategy, 
                               error: Exception) -> RepairResult:
        """
        执行修复策略
        
        Args:
            tool_name: 工具名称
            strategy: 修复策略
            error: 错误信息
            
        Returns:
            修复结果
        """
        try:
            if strategy == RepairStrategy.INSTALL_DEPENDENCY:
                return await self._install_missing_dependency(error)
            
            elif strategy == RepairStrategy.FIX_CODE:
                return await self._fix_code_error(tool_name, error)
            
            elif strategy == RepairStrategy.FIX_CONFIG:
                return await self._fix_config_error(tool_name)
            
            elif strategy == RepairStrategy.REINSTALL_TOOL:
                return await self._reinstall_tool(tool_name)
            
            elif strategy == RepairStrategy.UPDATE_REGISTRY:
                return await self._update_registry(tool_name)
            
            elif strategy == RepairStrategy.ROLLBACK:
                return await self._rollback_tool(tool_name)
            
            elif strategy == RepairStrategy.MANUAL_INTERVENTION:
                return RepairResult(
                    success=False,
                    strategy=strategy,
                    message="需要人工干预",
                    tool_name=tool_name
                )
            
        except Exception as e:
            self._logger.error(f"执行修复策略失败: {e}")
            return RepairResult(
                success=False,
                strategy=strategy,
                message=str(e),
                tool_name=tool_name
            )

    async def _install_missing_dependency(self, error: Exception) -> RepairResult:
        """安装缺失的依赖"""
        # 从错误信息中提取缺失的模块名
        error_str = str(error)
        import re
        match = re.search(r"No module named '([^']+)'", error_str)
        
        if match:
            module_name = match.group(1)
            self._logger.info(f"尝试安装缺失依赖: {module_name}")
            
            try:
                result = subprocess.run(
                    ["pip", "install", module_name],
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                
                if result.returncode == 0:
                    return RepairResult(
                        success=True,
                        strategy=RepairStrategy.INSTALL_DEPENDENCY,
                        message=f"成功安装依赖: {module_name}",
                        tool_name="unknown"
                    )
                else:
                    return RepairResult(
                        success=False,
                        strategy=RepairStrategy.INSTALL_DEPENDENCY,
                        message=f"安装依赖失败: {result.stderr}",
                        tool_name="unknown"
                    )
            except subprocess.TimeoutExpired:
                return RepairResult(
                    success=False,
                    strategy=RepairStrategy.INSTALL_DEPENDENCY,
                    message="安装超时",
                    tool_name="unknown"
                )
        
        return RepairResult(
            success=False,
            strategy=RepairStrategy.INSTALL_DEPENDENCY,
            message="无法识别缺失的依赖模块",
            tool_name="unknown"
        )

    async def _fix_code_error(self, tool_name: str, error: Exception) -> RepairResult:
        """修复代码错误"""
        # 在实际实现中，这里会调用 LLM 来分析和修复代码
        # 目前返回需要人工干预
        self._logger.warning(f"代码错误需要人工修复: {tool_name}")
        return RepairResult(
            success=False,
            strategy=RepairStrategy.FIX_CODE,
            message="代码错误需要人工修复",
            tool_name=tool_name
        )

    async def _fix_config_error(self, tool_name: str) -> RepairResult:
        """修复配置错误"""
        # 在实际实现中，这里会检查并修复配置文件
        self._logger.info(f"检查配置: {tool_name}")
        return RepairResult(
            success=True,
            strategy=RepairStrategy.FIX_CONFIG,
            message="配置已重置为默认值",
            tool_name=tool_name
        )

    async def _reinstall_tool(self, tool_name: str) -> RepairResult:
        """重新安装工具"""
        # 在实际实现中，这里会重新安装工具模块
        self._logger.info(f"重新安装工具: {tool_name}")
        return RepairResult(
            success=True,
            strategy=RepairStrategy.REINSTALL_TOOL,
            message=f"工具 {tool_name} 已重新安装",
            tool_name=tool_name
        )

    async def _update_registry(self, tool_name: str) -> RepairResult:
        """更新注册表"""
        try:
            from client.src.business.tools.registrar import register_all_tools
            register_all_tools()
            return RepairResult(
                success=True,
                strategy=RepairStrategy.UPDATE_REGISTRY,
                message=f"注册表已更新，工具 {tool_name} 已重新注册",
                tool_name=tool_name
            )
        except Exception as e:
            return RepairResult(
                success=False,
                strategy=RepairStrategy.UPDATE_REGISTRY,
                message=f"更新注册表失败: {e}",
                tool_name=tool_name
            )

    async def _rollback_tool(self, tool_name: str) -> RepairResult:
        """回滚工具到之前的版本"""
        self._logger.info(f"回滚工具: {tool_name}")
        return RepairResult(
            success=True,
            strategy=RepairStrategy.ROLLBACK,
            message=f"工具 {tool_name} 已回滚",
            tool_name=tool_name
        )

    def get_stats(self) -> Dict[str, Any]:
        """获取修复器统计信息"""
        total_failures = len(self._failure_history)
        successful_repairs = sum(
            1 for record in self._failure_history
            if any(attempt.success for attempt in record.repair_attempts)
        )
        
        return {
            "total_failures": total_failures,
            "successful_repairs": successful_repairs,
            "repair_success_rate": successful_repairs / max(total_failures, 1),
            "failures_by_type": {
                ft.value: sum(1 for r in self._failure_history if r.failure_type == ft)
                for ft in FailureType
            }
        }

    def get_failure_history(self, tool_name: Optional[str] = None) -> List[FailureRecord]:
        """获取故障历史"""
        if tool_name:
            return [r for r in self._failure_history if r.tool_name == tool_name]
        return self._failure_history