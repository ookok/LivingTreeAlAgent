"""
挂载部署 (Deployment Bay)

目标：注入运行环境，动态生效。

路由注册：注册到全局工具表（ext:opendataloader）
能力广播：通知 Hermes 新能力可用
热重载：部分模块可立即调用，部分需重启服务
"""

import json
import asyncio
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Callable, Any
from enum import Enum


class DeployStatus(Enum):
    """部署状态"""
    PENDING = "pending"
    DEPLOYING = "deploying"
    DEPLOYED = "deployed"
    FAILED = "failed"
    HOT_RELOAD = "hot_reload"    # 热重载
    COLD_RELOAD = "cold_reload"   # 冷重启


@dataclass
class DeployedModule:
    """已部署模块"""
    name: str
    version: str = "1.0.0"
    description: str = ""

    # 路径信息
    module_path: str = ""
    entry_point: str = ""
    adapter_path: str = ""

    # 工具合约
    tool_contract: dict = None

    # 状态
    status: DeployStatus = DeployStatus.PENDING
    is_enabled: bool = True
    is_hot_reload: bool = False  # 是否支持热重载

    # 统计
    call_count: int = 0
    last_called: float = 0.0

    # 依赖
    dependencies: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.tool_contract is None:
            self.tool_contract = {}

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "module_path": self.module_path,
            "entry_point": self.entry_point,
            "adapter_path": self.adapter_path,
            "tool_contract": self.tool_contract,
            "status": self.status.value,
            "is_enabled": self.is_enabled,
            "is_hot_reload": self.is_hot_reload,
            "call_count": self.call_count,
            "last_called": self.last_called,
            "dependencies": self.dependencies,
        }


class DeploymentBay:
    """挂载部署 - 动态部署管理"""

    # 全局工具注册表路径
    TOOL_REGISTRY_PATH = Path.home() / ".hermes-desktop" / "modules" / "tool_registry.json"

    def __init__(self):
        self._deployed_modules: dict[str, DeployedModule] = {}
        self._tool_registry: dict[str, dict] = {}
        self._listeners: list[Callable] = []

        # 加载现有注册表
        self._load_registry()

    def _load_registry(self):
        """加载工具注册表"""
        if self.TOOL_REGISTRY_PATH.exists():
            try:
                self._tool_registry = json.loads(
                    self.TOOL_REGISTRY_PATH.read_text(encoding='utf-8')
                )
            except Exception:
                self._tool_registry = {}

    def _save_registry(self):
        """保存工具注册表"""
        self.TOOL_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.TOOL_REGISTRY_PATH.write_text(
            json.dumps(self._tool_registry, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )

    def register_listener(self, callback: Callable):
        """注册状态变更监听器"""
        self._listeners.append(callback)

    async def _notify_listeners(self, event: str, module: DeployedModule):
        """通知监听器"""
        for listener in self._listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(event, module)
                else:
                    listener(event, module)
            except Exception:
                pass

    async def deploy(
        self,
        module_name: str,
        repo_info: dict,
        installation_result: dict,
        adapter_path: str,
        tool_contract: dict,
        hot_reload: bool = True
    ) -> DeployedModule:
        """
        部署模块

        Args:
            module_name: 模块名称
            repo_info: 仓库信息
            installation_result: 安装结果
            adapter_path: 适配器路径
            tool_contract: 工具合约
            hot_reload: 是否支持热重载

        Returns:
            DeployedModule: 部署后的模块
        """
        module = DeployedModule(
            name=f"ext:{module_name}",
            version=installation_result.get("runtime_version", "1.0.0"),
            description=repo_info.get("description", ""),
            module_path=installation_result.get("module_path", ""),
            entry_point=installation_result.get("entry_point", ""),
            adapter_path=adapter_path,
            tool_contract=tool_contract,
            status=DeployStatus.DEPLOYING,
            is_hot_reload=hot_reload,
        )

        self._deployed_modules[module.name] = module

        # 注册到全局工具表
        self._tool_registry[module.name] = {
            "name": module.name,
            "entry_point": module.entry_point,
            "adapter_path": module.adapter_path,
            "contract": tool_contract,
            "is_enabled": True,
            "is_hot_reload": hot_reload,
        }

        self._save_registry()

        # 广播部署事件
        await self._notify_listeners("module_deployed", module)

        # 更新状态
        module.status = DeployStatus.DEPLOYED if hot_reload else DeployStatus.COLD_RELOAD

        return module

    async def undeploy(self, module_name: str) -> bool:
        """
        卸载模块

        Args:
            module_name: 模块名称

        Returns:
            bool: 是否成功
        """
        full_name = module_name if module_name.startswith("ext:") else f"ext:{module_name}"

        if full_name not in self._deployed_modules:
            return False

        module = self._deployed_modules[full_name]
        module.status = DeployStatus.FAILED
        module.is_enabled = False

        # 从注册表移除
        if full_name in self._tool_registry:
            del self._tool_registry[full_name]
            self._save_registry()

        # 广播卸载事件
        await self._notify_listeners("module_undeployed", module)

        return True

    async def enable_module(self, module_name: str) -> bool:
        """启用模块"""
        full_name = module_name if module_name.startswith("ext:") else f"ext:{module_name}"

        if full_name in self._tool_registry:
            self._tool_registry[full_name]["is_enabled"] = True
            self._save_registry()
            return True
        return False

    async def disable_module(self, module_name: str) -> bool:
        """禁用模块"""
        full_name = module_name if module_name.startswith("ext:") else f"ext:{module_name}"

        if full_name in self._tool_registry:
            self._tool_registry[full_name]["is_enabled"] = False
            self._save_registry()
            return True
        return False

    async def execute_module(
        self,
        module_name: str,
        action: str,
        **kwargs
    ) -> dict:
        """
        执行模块

        Args:
            module_name: 模块名称
            action: 操作
            **kwargs: 参数

        Returns:
            dict: 执行结果
        """
        full_name = module_name if module_name.startswith("ext:") else f"ext:{module_name}"

        if full_name not in self._deployed_modules:
            return {"success": False, "error": f"模块未部署: {full_name}"}

        module = self._deployed_modules[full_name]

        if not module.is_enabled:
            return {"success": False, "error": f"模块已禁用: {full_name}"}

        try:
            # 更新统计
            module.call_count += 1
            module.last_called = asyncio.get_event_loop().time()

            # 执行调用
            result = await self._call_adapter(module, action, kwargs)

            return {
                "success": True,
                "module": full_name,
                "result": result,
            }

        except Exception as e:
            return {
                "success": False,
                "module": full_name,
                "error": str(e)
            }

    async def _call_adapter(
        self,
        module: DeployedModule,
        action: str,
        params: dict
    ) -> Any:
        """调用适配器"""
        # TODO: 实现真正的适配器调用
        # 目前是模拟实现
        await asyncio.sleep(0.1)
        return {
            "action": action,
            "params": params,
            "result": f"{module.name} executed {action} successfully"
        }

    def list_deployed(self) -> list[dict]:
        """列出已部署模块"""
        return [m.to_dict() for m in self._deployed_modules.values()]

    def get_module(self, module_name: str) -> Optional[DeployedModule]:
        """获取模块"""
        full_name = module_name if module_name.startswith("ext:") else f"ext:{module_name}"
        return self._deployed_modules.get(full_name)

    def get_tool_registry(self) -> dict:
        """获取工具注册表"""
        return self._tool_registry

    def is_enabled(self, module_name: str) -> bool:
        """检查模块是否启用"""
        full_name = module_name if module_name.startswith("ext:") else f"ext:{module_name}"
        entry = self._tool_registry.get(full_name, {})
        return entry.get("is_enabled", False)

    def format_deployed_modules(self) -> str:
        """格式化已部署模块列表"""
        if not self._deployed_modules:
            return "📦 **暂无已部署模块**\n请通过装配坞安装新模块。"

        lines = ["📦 **已部署模块**\n"]

        for module in self._deployed_modules.values():
            status_icon = {
                DeployStatus.DEPLOYED: "🟢",
                DeployStatus.COLD_RELOAD: "🔵",
                DeployStatus.FAILED: "🔴",
            }.get(module.status, "⚪")

            hot_icon = "⚡" if module.is_hot_reload else "❄️"

            lines.append(f"{status_icon} **{module.name}** {hot_icon}")
            lines.append(f"   版本: {module.version}")
            lines.append(f"   描述: {module.description or '无'}")
            lines.append(f"   调用次数: {module.call_count}")

        return "\n".join(lines)