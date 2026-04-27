"""
ToolSelfRepairer - 工具自我修复器

基于 SelfReflectionEngine 的工具自我修复系统。

修复策略：
1. 缺失依赖 → 使用 PackageManagerInstaller 安装
2. 导入错误 → 安装缺失模块
3. 语法错误 → 使用 LLM 修复代码
4. 配置错误 → 修复配置
5. 工具未找到 → 使用 NaturalLanguageToolAdder 安装

Author: LivingTreeAI Agent
Date: 2026-04-28
"""

import asyncio
import json
import re
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from loguru import logger

from client.src.business.self_evolution.package_manager_installer import (
    PackageManagerInstaller,
    PackageSpec,
)
from client.src.business.tools.tool_registry import ToolRegistry
from client.src.business.global_model_router import GlobalModelRouter


class RepairStrategy(Enum):
    """修复策略"""
    INSTALL_DEPENDENCY = "install_dependency"
    FIX_CODE = "fix_code"
    FIX_CONFIG = "fix_config"
    REINSTALL_TOOL = "reinstall_tool"
    UPDATE_REGISTRY = "update_registry"
    UNKNOWN = "unknown"


class RepairResult:
    """修复结果"""
    
    def __init__(
        self,
        success: bool,
        strategy: RepairStrategy,
        message: str,
        details: Optional[Dict] = None,
    ):
        self.success = success
        self.strategy = strategy
        self.message = message
        self.details = details or {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "strategy": self.strategy.value,
            "message": self.message,
            "details": self.details,
        }


class ToolSelfRepairer:
    """
    工具自我修复器
    
    功能：
    1. 分析工具执行错误
    2. 确定修复策略
    3. 执行修复
    4. 验证修复结果
    
    用法：
        repairer = ToolSelfRepairer()
        result = await repairer.repair_tool("aermod_tool", error_message)
    """
    
    def __init__(self, llm_client=None):
        """
        初始化工具自我修复器
        
        Args:
            llm_client: LLM 客户端（用于代码修复）
        """
        self._llm = llm_client
        self._router = GlobalModelRouter.get_instance()
        self._installer = PackageManagerInstaller()
        self._logger = logger.bind(component="ToolSelfRepairer")
    
    async def repair_tool(
        self,
        tool_name: str,
        error: str,
        tool_input: Optional[Dict] = None,
        tool_output: Optional[Any] = None,
    ) -> RepairResult:
        """
        修复工具
        
        Args:
            tool_name: 工具名称
            error: 错误信息
            tool_input: 工具输入（可选）
            tool_output: 工具输出（可选）
            
        Returns:
            RepairResult 修复结果
        """
        self._logger.info(f"开始修复工具: {tool_name}")
        self._logger.info(f"错误信息: {error[:200]}")
        
        # 1. 分析错误，确定修复策略
        strategy = self._analyze_error(error)
        self._logger.info(f"修复策略: {strategy.value}")
        
        # 2. 执行修复
        if strategy == RepairStrategy.INSTALL_DEPENDENCY:
            return await self._repair_dependency(tool_name, error)
        
        elif strategy == RepairStrategy.FIX_CODE:
            return await self._repair_code(tool_name, error)
        
        elif strategy == RepairStrategy.FIX_CONFIG:
            return await self._repair_config(tool_name, error)
        
        elif strategy == RepairStrategy.REINSTALL_TOOL:
            return await self._repair_reinstall(tool_name, error)
        
        elif strategy == RepairStrategy.UPDATE_REGISTRY:
            return await self._repair_registry(tool_name, error)
        
        else:
            return RepairResult(
                success=False,
                strategy=RepairStrategy.UNKNOWN,
                message=f"无法识别的修复策略，错误: {error[:200]}",
            )
    
    def _analyze_error(self, error: str) -> RepairStrategy:
        """
        分析错误，确定修复策略
        
        通过错误关键词判断修复策略。
        """
        error_lower = error.lower()
        
        # 缺失依赖
        if any(k in error_lower for k in [
            "no module named",
            "modulenotfounderror",
            "importerror",
            "cannot find",
            "not found",
            "未找到",
            "没有那个文件或目录",
        ]):
            return RepairStrategy.INSTALL_DEPENDENCY
        
        # 语法错误
        if any(k in error_lower for k in [
            "syntaxerror",
            "indentationerror",
            "valueerror",
            "typeerror",
            "attributeerror",
        ]):
            return RepairStrategy.FIX_CODE
        
        # 配置错误
        if any(k in error_lower for k in [
            "configuration",
            "config",
            "setting",
            "permission denied",
            "access denied",
        ]):
            return RepairStrategy.FIX_CONFIG
        
        # 工具未注册
        if any(k in error_lower for k in [
            "tool not found",
            "tool not registered",
            "未找到工具",
        ]):
            return RepairStrategy.UPDATE_REGISTRY
        
        # 默认：重装工具
        return RepairStrategy.REINSTALL_TOOL
    
    async def _repair_dependency(self, tool_name: str, error: str) -> RepairResult:
        """
        修复缺失依赖
        
        从错误信息中提取缺失的包名，然后安装。
        """
        self._logger.info(f"修复缺失依赖: {tool_name}")
        
        # 提取缺失的模块名
        missing_module = self._extract_missing_module(error)
        
        if not missing_module:
            return RepairResult(
                success=False,
                strategy=RepairStrategy.INSTALL_DEPENDENCY,
                message="无法从错误信息中提取缺失模块名",
            )
        
        self._logger.info(f"缺失模块: {missing_module}")
        
        # 构造包规格
        package_spec = PackageSpec(
            tool_name=missing_module,
            package_manager="pip",
            install_command=["pip", "install", missing_module],
            verify_command=["python", "-c", f"import {missing_module}"],
            verify_type="import",
            category="auto_repair",
            description=f"自动修复缺失依赖: {missing_module}",
        )
        
        # 安装
        try:
            result = await self._installer.install(package_spec)
            
            if result.success:
                self._logger.info(f"依赖安装成功: {missing_module}")
                
                # 刷新工具注册表
                from client.src.business.tools.register_all_tools import register_all_tools
                register_all_tools()
                
                return RepairResult(
                    success=True,
                    strategy=RepairStrategy.INSTALL_DEPENDENCY,
                    message=f"成功安装缺失依赖: {missing_module}",
                    details={"installed_package": missing_module},
                )
            else:
                return RepairResult(
                    success=False,
                    strategy=RepairStrategy.INSTALL_DEPENDENCY,
                    message=f"依赖安装失败: {result.message}",
                    details={"error": result.error},
                )
                
        except Exception as e:
            self._logger.error(f"安装依赖时出错: {e}")
            return RepairResult(
                success=False,
                strategy=RepairStrategy.INSTALL_DEPENDENCY,
                message=f"安装依赖时出错: {e}",
            )
    
    def _extract_missing_module(self, error: str) -> Optional[str]:
        """
        从错误信息中提取缺失的模块名
        
        支持多种错误格式：
        - No module named 'xxx'
        - ModuleNotFoundError: No module named "xxx"
        - ImportError: cannot import name 'xxx'
        """
        # 模式 1: No module named 'xxx' 或 "xxx"
        match = re.search(r"no module named ['\"]([^'\"]+)['\"]", error, re.IGNORECASE)
        if match:
            return match.group(1).split('.')[0]  # 取顶层模块名
        
        # 模式 2: cannot import name 'xxx' from 'yyy'
        match = re.search(r"cannot import name ['\"]([^'\"]+)['\"] from ['\"]([^'\"]+)['\"]", error, re.IGNORECASE)
        if match:
            return match.group(2).split('.')[0]
        
        # 模式 3: 文件路径（如 /usr/bin/xxx not found）
        match = re.search(r"(?:not found|未找到):?\s*['\"]?(\w+)['\"]?", error, re.IGNORECASE)
        if match:
            return match.group(1)
        
        # 模式 4: 中文错误信息（如：没有名为 xxx 的模块）
        match = re.search(r"没有(?:名为|叫做)\s*['\"]?(\w+)['\"]?", error)
        if match:
            return match.group(1)
        
        return None
    
    async def _repair_code(self, tool_name: str, error: str) -> RepairResult:
        """
        修复工具代码
        
        使用 LLM 分析错误并修复代码。
        """
        self._logger.info(f"修复工具代码: {tool_name}")
        
        # 1. 找到工具文件
        tool_file = self._find_tool_file(tool_name)
        
        if not tool_file:
            return RepairResult(
                success=False,
                strategy=RepairStrategy.FIX_CODE,
                message=f"未找到工具文件: {tool_name}",
            )
        
        self._logger.info(f"工具文件: {tool_file}")
        
        # 2. 读取工具代码
        try:
            with open(tool_file, 'r', encoding='utf-8') as f:
                code = f.read()
        except Exception as e:
            return RepairResult(
                success=False,
                strategy=RepairStrategy.FIX_CODE,
                message=f"读取工具文件失败: {e}",
            )
        
        # 3. 使用 LLM 修复代码
        fixed_code = await self._fix_code_with_llm(code, error)
        
        if not fixed_code:
            return RepairResult(
                success=False,
                strategy=RepairStrategy.FIX_CODE,
                message="LLM 未能生成修复后的代码",
            )
        
        # 4. 写入修复后的代码
        try:
            # 先备份
            backup_file = f"{tool_file}.backup"
            with open(backup_file, 'w', encoding='utf-8') as f:
                f.write(code)
            
            # 写入修复后的代码
            with open(tool_file, 'w', encoding='utf-8') as f:
                f.write(fixed_code)
            
            self._logger.info(f"代码已修复并写入: {tool_file}")
            
            # 5. 语法检查
            try:
                compile(fixed_code, tool_file, 'exec')
            except SyntaxError as e:
                # 修复后的代码仍有语法错误，恢复备份
                with open(tool_file, 'w', encoding='utf-8') as f:
                    f.write(code)
                return RepairResult(
                    success=False,
                    strategy=RepairStrategy.FIX_CODE,
                    message=f"修复后的代码仍有语法错误: {e}",
                )
            
            # 6. 重新注册工具
            from client.src.business.tools.register_all_tools import register_all_tools
            register_all_tools()
            
            return RepairResult(
                success=True,
                strategy=RepairStrategy.FIX_CODE,
                message=f"成功修复工具代码: {tool_name}",
                details={"tool_file": tool_file, "backup_file": backup_file},
            )
            
        except Exception as e:
            self._logger.error(f"写入修复后的代码失败: {e}")
            return RepairResult(
                success=False,
                strategy=RepairStrategy.FIX_CODE,
                message=f"写入修复后的代码失败: {e}",
            )
    
    def _find_tool_file(self, tool_name: str) -> Optional[str]:
        """查找工具文件"""
        # 从 ToolRegistry 获取工具
        registry = ToolRegistry.get_instance()
        tool = registry.get_tool(tool_name)
        
        if tool and hasattr(tool, '__file__'):
            return tool.__file__
        
        # 搜索工具文件
        tools_dir = Path("client/src/business/tools")
        for py_file in tools_dir.rglob("*.py"):
            if tool_name in py_file.name:
                return str(py_file)
        
        return None
    
    async def _fix_code_with_llm(self, code: str, error: str) -> Optional[str]:
        """
        使用 LLM 修复代码
        
        将代码和错误发送给 LLM，让它生成修复后的代码。
        """
        prompt = f"""你是 Python 代码修复专家。

以下代码有错误：
```
{code[:2000]}
```

错误信息：
```
{error[:500]}
```

请分析错误并修复代码。

要求：
1. 保持原有功能不变
2. 只修复错误，不要重构
3. 输出完整的修复后代码

请以 JSON 格式输出：
{{
    "analysis": "错误分析",
    "fixed_code": "修复后的完整代码"
}}

只输出 JSON，不要有其他内容。"""

        try:
            response = await self._router.call_model_sync(
                capability="code_generation",
                prompt=prompt,
                temperature=0.1,
            )
            
            # 解析响应
            if hasattr(response, 'thinking') and response.thinking:
                text = response.thinking
            elif hasattr(response, 'content') and response.content:
                text = response.content
            else:
                text = str(response)
            
            # 提取 JSON
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return result.get("fixed_code")
            
            return None
            
        except Exception as e:
            self._logger.error(f"LLM 修复代码失败: {e}")
            return None
    
    async def _repair_config(self, tool_name: str, error: str) -> RepairResult:
        """
        修复配置错误
        
        目前是简化版：记录错误，建议手动修复。
        """
        self._logger.info(f"修复配置错误: {tool_name}")
        
        # 使用 LLM 分析配置错误
        prompt = f"""你是配置错误分析专家。

工具名称：{tool_name}
错误信息：
{error[:500]}

请分析：
1. 是什么配置错误？
2. 应该如何修复？

请以 JSON 格式输出：
{{
    "error_type": "错误类型",
    "fix_suggestion": "修复建议",
    "auto_fixable": true/false
}}"""

        try:
            response = await self._router.call_model_sync(
                capability="reasoning",
                prompt=prompt,
                temperature=0.1,
            )
            
            # 解析响应
            if hasattr(response, 'thinking') and response.thinking:
                text = response.thinking
            elif hasattr(response, 'content') and response.content:
                text = response.content
            else:
                text = str(response)
            
            # 提取 JSON
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return RepairResult(
                    success=False,
                    strategy=RepairStrategy.FIX_CONFIG,
                    message=result.get("fix_suggestion", "需要手动修复配置"),
                    details={
                        "error_type": result.get("error_type"),
                        "auto_fixable": result.get("auto_fixable", False),
                    },
                )
            
            return RepairResult(
                success=False,
                strategy=RepairStrategy.FIX_CONFIG,
                message=f"配置错误，需要手动修复: {error[:200]}",
            )
            
        except Exception as e:
            return RepairResult(
                success=False,
                strategy=RepairStrategy.FIX_CONFIG,
                message=f"分析配置错误失败: {e}",
            )
    
    async def _repair_reinstall(self, tool_name: str, error: str) -> RepairResult:
        """
        重装工具
        
        使用 NaturalLanguageToolAdder 重新安装工具。
        """
        self._logger.info(f"重装工具: {tool_name}")
        
        try:
            from client.src.business.self_evolution.natural_language_tool_adder import add_tool_from_text
            
            result = await add_tool_from_text(f"重新安装 {tool_name} 工具")
            
            if result.success:
                return RepairResult(
                    success=True,
                    strategy=RepairStrategy.REINSTALL_TOOL,
                    message=f"成功重装工具: {tool_name}",
                )
            else:
                return RepairResult(
                    success=False,
                    strategy=RepairStrategy.REINSTALL_TOOL,
                    message=f"重装工具失败: {result.message}",
                )
                
        except Exception as e:
            return RepairResult(
                success=False,
                strategy=RepairStrategy.REINSTALL_TOOL,
                message=f"重装工具时出错: {e}",
            )
    
    async def _repair_registry(self, tool_name: str, error: str) -> RepairResult:
        """
        修复工具注册表
        
        重新注册所有工具。
        """
        self._logger.info(f"修复工具注册表: {tool_name}")
        
        try:
            from client.src.business.tools.register_all_tools import register_all_tools
            
            register_all_tools()
            
            # 检查工具是否已注册
            registry = ToolRegistry.get_instance()
            tool = registry.get_tool(tool_name)
            
            if tool:
                return RepairResult(
                    success=True,
                    strategy=RepairStrategy.UPDATE_REGISTRY,
                    message=f"成功注册工具: {tool_name}",
                )
            else:
                return RepairResult(
                    success=False,
                    strategy=RepairStrategy.UPDATE_REGISTRY,
                    message=f"注册工具失败: {tool_name} 未找到",
                )
                
        except Exception as e:
            return RepairResult(
                success=False,
                strategy=RepairStrategy.UPDATE_REGISTRY,
                message=f"修复注册表时出错: {e}",
            )


async def test_tool_self_repairer():
    """测试工具自我修复器"""
    import sys
    
    logger.remove()
    logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)
    
    print("=" * 60)
    print("测试 ToolSelfRepairer")
    print("=" * 60)
    
    # 创建修复器
    repairer = ToolSelfRepairer()
    
    # 测试案例 1：缺失依赖
    print("\n测试案例 1: 缺失依赖")
    error1 = "ModuleNotFoundError: No module named 'flopy'"
    result1 = await repairer.repair_tool("groundwater_tool", error1)
    print(f"  结果: {result1.success}")
    print(f"  消息: {result1.message}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_tool_self_repairer())
