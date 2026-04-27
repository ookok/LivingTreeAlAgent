#!/usr/bin/env python3
"""
PlatformHubPanel - 统一内置平台面板
LivingTreeAI 核心控制中心
"""

import sys
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class PanelType(Enum):
    """面板类型"""
    OVERVIEW = "overview"           # 总览
    SYSTEM = "system"               # 系统设置
    USER = "user"                   # 用户管理
    AGENT = "agent"                 # 智能体管理
    WORKSPACE = "workspace"         # 工作区
    IDE = "ide"                     # IDE设置
    BROWSER = "browser"             # 浏览器
    FILE = "file"                   # 文件管理
    PROXY = "proxy"                 # 代理设置
    MORE = "more"                   # 更多设置


@dataclass
class PanelMetrics:
    """面板指标"""
    active_agents: int = 0
    running_tasks: int = 0
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    disk_usage: float = 0.0
    network_status: str = "connected"
    uptime_seconds: int = 0
    last_error: Optional[str] = None


@dataclass
class AgentInfo:
    """智能体信息"""
    id: str
    name: str
    type: str
    status: str  # idle, running, paused, error
    tasks_completed: int = 0
    current_task: Optional[str] = None
    created_at: float = 0
    last_active: float = 0


@dataclass
class WorkspaceInfo:
    """工作区信息"""
    id: str
    name: str
    path: str
    is_active: bool = False
    file_count: int = 0
    last_modified: float = 0


class PlatformHubPanel:
    """
    统一内置平台面板
    整合所有平台管理功能于一身
    """
    
    def __init__(self):
        """初始化平台面板"""
        self._metrics = PanelMetrics()
        self._agents: Dict[str, AgentInfo] = {}
        self._workspaces: Dict[str, WorkspaceInfo] = {}
        self._active_panel = PanelType.OVERVIEW
        self._settings: Dict[str, Any] = {}
        
        logger.info("PlatformHubPanel 初始化完成")
    
    # ==================== 面板切换 ====================
    
    def switch_panel(self, panel_type: PanelType) -> bool:
        """切换面板"""
        self._active_panel = panel_type
        logger.info(f"切换到面板: {panel_type.value}")
        return True
    
    def get_active_panel(self) -> PanelType:
        """获取当前面板"""
        return self._active_panel
    
    # ==================== 系统总览 ====================
    
    def get_overview_data(self) -> Dict[str, Any]:
        """获取总览数据"""
        return {
            'panel_type': self._active_panel.value,
            'metrics': {
                'active_agents': self._metrics.active_agents,
                'running_tasks': self._metrics.running_tasks,
                'cpu_usage': self._metrics.cpu_usage,
                'memory_usage': self._metrics.memory_usage,
                'disk_usage': self._metrics.disk_usage,
                'network_status': self._metrics.network_status,
                'uptime_seconds': self._metrics.uptime_seconds,
            },
            'agents': [self._format_agent(a) for a in self._agents.values()],
            'workspaces': [self._format_workspace(w) for w in self._workspaces.values()],
            'recent_errors': [self._metrics.last_error] if self._metrics.last_error else [],
        }
    
    def _format_agent(self, agent: AgentInfo) -> Dict[str, Any]:
        """格式化智能体信息"""
        return {
            'id': agent.id,
            'name': agent.name,
            'type': agent.type,
            'status': agent.status,
            'tasks_completed': agent.tasks_completed,
            'current_task': agent.current_task,
        }
    
    def _format_workspace(self, ws: WorkspaceInfo) -> Dict[str, Any]:
        """格式化工作区信息"""
        return {
            'id': ws.id,
            'name': ws.name,
            'path': ws.path,
            'is_active': ws.is_active,
            'file_count': ws.file_count,
        }
    
    # ==================== 智能体管理 ====================
    
    def register_agent(self, agent_id: str, name: str, agent_type: str) -> bool:
        """注册智能体"""
        if agent_id in self._agents:
            logger.warning(f"智能体 {agent_id} 已存在")
            return False
        
        self._agents[agent_id] = AgentInfo(
            id=agent_id,
            name=name,
            type=agent_type,
            status='idle',
            created_at=__import__('time').time()
        )
        
        self._metrics.active_agents = len(self._agents)
        logger.info(f"注册智能体: {name} ({agent_type})")
        return True
    
    def update_agent_status(self, agent_id: str, status: str, 
                           current_task: Optional[str] = None) -> bool:
        """更新智能体状态"""
        if agent_id not in self._agents:
            logger.error(f"智能体 {agent_id} 不存在")
            return False
        
        agent = self._agents[agent_id]
        agent.status = status
        agent.current_task = current_task
        agent.last_active = __import__('time').time()
        
        if status == 'idle' and current_task is None:
            agent.tasks_completed += 1
        
        return True
    
    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """获取智能体信息"""
        if agent_id not in self._agents:
            return None
        return self._format_agent(self._agents[agent_id])
    
    def list_agents(self, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出智能体"""
        agents = list(self._agents.values())
        if status_filter:
            agents = [a for a in agents if a.status == status_filter]
        return [self._format_agent(a) for a in agents]
    
    def unregister_agent(self, agent_id: str) -> bool:
        """注销智能体"""
        if agent_id not in self._agents:
            return False
        
        del self._agents[agent_id]
        self._metrics.active_agents = len(self._agents)
        logger.info(f"注销智能体: {agent_id}")
        return True
    
    # ==================== 工作区管理 ====================
    
    def add_workspace(self, ws_id: str, name: str, path: str) -> bool:
        """添加工作区"""
        if ws_id in self._workspaces:
            return False
        
        self._workspaces[ws_id] = WorkspaceInfo(
            id=ws_id,
            name=name,
            path=path,
            is_active=False,
            created_at=__import__('time').time()
        )
        
        logger.info(f"添加工作区: {name}")
        return True
    
    def set_active_workspace(self, ws_id: str) -> bool:
        """设置活跃工作区"""
        # 取消所有活跃状态
        for ws in self._workspaces.values():
            ws.is_active = False
        
        # 设置新的活跃工作区
        if ws_id in self._workspaces:
            self._workspaces[ws_id].is_active = True
            logger.info(f"切换到工作区: {ws_id}")
            return True
        
        return False
    
    def get_active_workspace(self) -> Optional[Dict[str, Any]]:
        """获取活跃工作区"""
        for ws in self._workspaces.values():
            if ws.is_active:
                return self._format_workspace(ws)
        return None
    
    def list_workspaces(self) -> List[Dict[str, Any]]:
        """列出所有工作区"""
        return [self._format_workspace(ws) for ws in self._workspaces.values()]
    
    # ==================== 系统设置 ====================
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """获取设置"""
        return self._settings.get(key, default)
    
    def set_setting(self, key: str, value: Any) -> bool:
        """设置值"""
        self._settings[key] = value
        logger.info(f"设置更新: {key} = {value}")
        return True
    
    def get_all_settings(self) -> Dict[str, Any]:
        """获取所有设置"""
        return self._settings.copy()
    
    # ==================== 指标更新 ====================
    
    def update_metrics(self, **kwargs) -> bool:
        """更新指标"""
        for key, value in kwargs.items():
            if hasattr(self._metrics, key):
                setattr(self._metrics, key, value)
        return True
    
    def get_metrics(self) -> Dict[str, Any]:
        """获取指标"""
        return {
            'active_agents': self._metrics.active_agents,
            'running_tasks': self._metrics.running_tasks,
            'cpu_usage': self._metrics.cpu_usage,
            'memory_usage': self._metrics.memory_usage,
            'disk_usage': self._metrics.disk_usage,
            'network_status': self._metrics.network_status,
            'uptime_seconds': self._metrics.uptime_seconds,
        }
    
    # ==================== 健康检查 ====================
    
    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        issues = []
        
        # 检查内存
        if self._metrics.memory_usage > 90:
            issues.append("内存使用率过高")
        
        # 检查CPU
        if self._metrics.cpu_usage > 90:
            issues.append("CPU使用率过高")
        
        # 检查网络
        if self._metrics.network_status != "connected":
            issues.append("网络连接断开")
        
        # 检查智能体
        error_agents = [a.id for a in self._agents.values() if a.status == 'error']
        if error_agents:
            issues.append(f"有 {len(error_agents)} 个智能体错误")
        
        return {
            'healthy': len(issues) == 0,
            'issues': issues,
            'metrics': self.get_metrics()
        }


# ==================== 全局实例 ====================

_platform_hub: Optional[PlatformHubPanel] = None


def get_platform_hub() -> PlatformHubPanel:
    """获取全局平台面板实例"""
    global _platform_hub
    if _platform_hub is None:
        _platform_hub = PlatformHubPanel()
    return _platform_hub


# ==================== CLI 工具 ====================

def main():
    """命令行工具"""
    import argparse
    
    parser = argparse.ArgumentParser(description='PlatformHubPanel 管理工具')
    parser.add_argument('command', choices=['status', 'list-agents', 'list-workspaces', 'health'],
                       help='命令')
    
    args = parser.parse_args()
    hub = get_platform_hub()
    
    if args.command == 'status':
        print("平台状态:")
        print(f"  活跃智能体: {hub._metrics.active_agents}")
        print(f"  运行任务: {hub._metrics.running_tasks}")
        print(f"  CPU: {hub._metrics.cpu_usage}%")
        print(f"  内存: {hub._metrics.memory_usage}%")
        print(f"  网络: {hub._metrics.network_status}")
    
    elif args.command == 'list-agents':
        for agent in hub.list_agents():
            print(f"  {agent['name']} ({agent['type']}) - {agent['status']}")
    
    elif args.command == 'list-workspaces':
        for ws in hub.list_workspaces():
            print(f"  {ws['name']} - {ws['path']} {'(活跃)' if ws['is_active'] else ''}")
    
    elif args.command == 'health':
        health = hub.health_check()
        print(f"健康状态: {'✅ 正常' if health['healthy'] else '❌ 异常'}")
        if health['issues']:
            print("问题:")
            for issue in health['issues']:
                print(f"  - {issue}")


if __name__ == "__main__":
    main()
