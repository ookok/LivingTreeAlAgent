"""OpenHarness 权限治理系统集成"""

from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass


@dataclass
class Permission:
    """权限定义"""
    name: str
    description: str
    default: bool = False
    scope: str = "global"  # global, tool, skill, plugin


@dataclass
class Hook:
    """钩子定义"""
    name: str
    description: str
    callback: Callable
    events: List[str] = None
    priority: int = 0


class PermissionSystem:
    """OpenHarness 权限治理系统"""
    
    def __init__(self):
        """初始化权限系统"""
        self.permissions: Dict[str, Permission] = {}
        self.hooks: Dict[str, Hook] = {}
        self._register_builtin_permissions()
        self._register_builtin_hooks()
    
    def _register_builtin_permissions(self):
        """注册内置权限"""
        builtin_permissions = [
            Permission(
                name="read_file",
                description="读取文件权限",
                default=True,
                scope="tool"
            ),
            Permission(
                name="write_file",
                description="写入文件权限",
                default=False,
                scope="tool"
            ),
            Permission(
                name="run_command",
                description="执行系统命令权限",
                default=False,
                scope="tool"
            ),
            Permission(
                name="web_search",
                description="网络搜索权限",
                default=True,
                scope="skill"
            ),
            Permission(
                name="code_execution",
                description="代码执行权限",
                default=False,
                scope="skill"
            )
        ]
        
        for permission in builtin_permissions:
            self.permissions[permission.name] = permission
        
        print(f"[PermissionSystem] 加载了 {len(builtin_permissions)} 个内置权限")
    
    def _register_builtin_hooks(self):
        """注册内置钩子"""
        builtin_hooks = [
            Hook(
                name="before_tool_execution",
                description="工具执行前钩子",
                callback=self._before_tool_execution,
                events=["tool_execution"],
                priority=10
            ),
            Hook(
                name="after_tool_execution",
                description="工具执行后钩子",
                callback=self._after_tool_execution,
                events=["tool_execution"],
                priority=5
            ),
            Hook(
                name="before_skill_loading",
                description="技能加载前钩子",
                callback=self._before_skill_loading,
                events=["skill_loading"],
                priority=10
            )
        ]
        
        for hook in builtin_hooks:
            self.hooks[hook.name] = hook
        
        print(f"[PermissionSystem] 加载了 {len(builtin_hooks)} 个内置钩子")
    
    def register_permission(self, permission: Permission):
        """注册权限"""
        self.permissions[permission.name] = permission
        print(f"[PermissionSystem] 注册权限: {permission.name} - {permission.description}")
    
    def register_hook(self, hook: Hook):
        """注册钩子"""
        self.hooks[hook.name] = hook
        print(f"[PermissionSystem] 注册钩子: {hook.name} - {hook.description}")
    
    def check_permission(self, permission_name: str) -> bool:
        """检查权限"""
        permission = self.permissions.get(permission_name)
        if permission:
            return permission.default
        return False
    
    def grant_permission(self, permission_name: str):
        """授予权限"""
        if permission_name in self.permissions:
            self.permissions[permission_name].default = True
            print(f"[PermissionSystem] 授予权限: {permission_name}")
        else:
            print(f"[PermissionSystem] 权限不存在: {permission_name}")
    
    def revoke_permission(self, permission_name: str):
        """撤销权限"""
        if permission_name in self.permissions:
            self.permissions[permission_name].default = False
            print(f"[PermissionSystem] 撤销权限: {permission_name}")
        else:
            print(f"[PermissionSystem] 权限不存在: {permission_name}")
    
    def execute_hook(self, event: str, **kwargs) -> List[Any]:
        """执行钩子"""
        results = []
        for hook in self.hooks.values():
            if event in (hook.events or []):
                try:
                    result = hook.callback(**kwargs)
                    results.append(result)
                    print(f"[PermissionSystem] 执行钩子成功: {hook.name}")
                except Exception as e:
                    print(f"[PermissionSystem] 执行钩子失败 {hook.name}: {e}")
        return results
    
    def get_all_permissions(self) -> List[Dict[str, Any]]:
        """获取所有权限"""
        return [
            {
                "name": permission.name,
                "description": permission.description,
                "default": permission.default,
                "scope": permission.scope
            }
            for permission in self.permissions.values()
        ]
    
    def get_all_hooks(self) -> List[Dict[str, Any]]:
        """获取所有钩子"""
        return [
            {
                "name": hook.name,
                "description": hook.description,
                "events": hook.events,
                "priority": hook.priority
            }
            for hook in self.hooks.values()
        ]
    
    # 内置钩子实现
    def _before_tool_execution(self, **kwargs):
        """工具执行前钩子"""
        tool_name = kwargs.get("tool_name")
        print(f"[Hook] 工具执行前: {tool_name}")
        
        # 检查权限
        if tool_name in self.permissions:
            if not self.check_permission(tool_name):
                raise PermissionError(f"Permission denied for tool: {tool_name}")
        
        return {"status": "allowed"}
    
    def _after_tool_execution(self, **kwargs):
        """工具执行后钩子"""
        tool_name = kwargs.get("tool_name")
        result = kwargs.get("result")
        print(f"[Hook] 工具执行后: {tool_name} - 结果: {result}")
        return {"status": "completed"}
    
    def _before_skill_loading(self, **kwargs):
        """技能加载前钩子"""
        skill_name = kwargs.get("skill_name")
        print(f"[Hook] 技能加载前: {skill_name}")
        return {"status": "loading"}
