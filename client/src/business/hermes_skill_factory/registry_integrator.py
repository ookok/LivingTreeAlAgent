"""
SkillRegistryIntegrator - 技能注册中心集成器

将生成的技能集成到现有技能注册系统中。
"""

from typing import Dict, Any, Optional, List
from loguru import logger
import os
import importlib.util

from client.src.business.skill_evolution.skill_registry import SkillRegistry, PermissionLevel
from client.src.business.tools.base_tool import BaseTool


class SkillRegistryIntegrator:
    """技能注册中心集成器"""

    def __init__(self):
        self._logger = logger.bind(component="SkillRegistryIntegrator")
        self._skill_registry = SkillRegistry()
        self._tool_registry = None
        self._init_tool_registry()

    def _init_tool_registry(self):
        """初始化工具注册中心"""
        try:
            from client.src.business.tools.tool_registry import ToolRegistry
            self._tool_registry = ToolRegistry.get_instance()
            self._logger.info("已连接到工具注册中心")
        except ImportError as e:
            self._logger.warning(f"无法连接到工具注册中心: {e}")

    def register_tool(self, tool_instance: BaseTool) -> bool:
        """
        注册工具到工具注册中心
        
        Args:
            tool_instance: BaseTool 实例
            
        Returns:
            是否成功
        """
        if not self._tool_registry:
            self._logger.warning("工具注册中心不可用")
            return False

        try:
            tool_instance.register()
            self._logger.info(f"已注册工具: {tool_instance.name}")
            return True
        except Exception as e:
            self._logger.error(f"注册工具失败 {tool_instance.name}: {e}")
            return False

    def register_skill(self, skill_id: str, name: str, description: str, 
                       category: str = "general", permission_level: str = "public",
                       team_id: Optional[str] = None) -> bool:
        """
        注册技能到技能注册中心
        
        Args:
            skill_id: 技能 ID
            name: 技能名称
            description: 技能描述
            category: 技能类别
            permission_level: 权限级别 (public/team/private)
            team_id: 团队 ID
            
        Returns:
            是否成功
        """
        try:
            level = PermissionLevel[permission_level.upper()]
            self._skill_registry.register_skill(
                skill_id=skill_id,
                name=name,
                description=description,
                category=category,
                permission_level=level,
                team_id=team_id
            )
            self._logger.info(f"已注册技能: {name}")
            return True
        except Exception as e:
            self._logger.error(f"注册技能失败 {name}: {e}")
            return False

    def register_from_module(self, module_path: str) -> List[str]:
        """
        从模块注册所有工具
        
        Args:
            module_path: 模块文件路径
            
        Returns:
            成功注册的工具名称列表
        """
        registered = []
        
        try:
            # 导入模块
            spec = importlib.util.spec_from_file_location("skill_module", module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # 查找 BaseTool 子类
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and 
                    hasattr(attr, '__bases__') and
                    any(base.__name__ == 'BaseTool' for base in attr.__mro__)):
                    
                    if attr_name == 'BaseTool':
                        continue
                    
                    try:
                        # 创建实例并注册
                        tool_instance = attr()
                        if self.register_tool(tool_instance):
                            registered.append(tool_instance.name)
                    except Exception as e:
                        self._logger.error(f"注册工具失败 {attr_name}: {e}")
            
            self._logger.info(f"从模块注册了 {len(registered)} 个工具")
            
        except Exception as e:
            self._logger.error(f"从模块注册失败 {module_path}: {e}")
        
        return registered

    def register_from_directory(self, directory: str) -> List[str]:
        """
        从目录注册所有工具
        
        Args:
            directory: 目录路径
            
        Returns:
            成功注册的工具名称列表
        """
        registered = []
        
        for filename in os.listdir(directory):
            if filename.endswith("_tool.py"):
                filepath = os.path.join(directory, filename)
                module_registered = self.register_from_module(filepath)
                registered.extend(module_registered)
        
        return registered

    def publish_skill(self, skill_id: str, user_id: str = "system") -> bool:
        """
        发布技能
        
        Args:
            skill_id: 技能 ID
            user_id: 用户 ID
            
        Returns:
            是否成功
        """
        try:
            self._skill_registry.publish_skill(skill_id, user_id)
            self._logger.info(f"已发布技能: {skill_id}")
            return True
        except Exception as e:
            self._logger.error(f"发布技能失败 {skill_id}: {e}")
            return False

    def deprecate_skill(self, skill_id: str, user_id: str = "system") -> bool:
        """
        废弃技能
        
        Args:
            skill_id: 技能 ID
            user_id: 用户 ID
            
        Returns:
            是否成功
        """
        try:
            self._skill_registry.deprecate_skill(skill_id, user_id)
            self._logger.info(f"已废弃技能: {skill_id}")
            return True
        except Exception as e:
            self._logger.error(f"废弃技能失败 {skill_id}: {e}")
            return False

    def get_skill(self, skill_id: str) -> Optional[Any]:
        """获取技能信息"""
        return self._skill_registry.get_skill(skill_id)

    def list_skills(self, **kwargs) -> List[Any]:
        """列出技能"""
        return self._skill_registry.list_skills(**kwargs)

    def get_stats(self) -> Dict[str, Any]:
        """获取注册中心统计信息"""
        skill_stats = self._skill_registry.get_stats()
        
        tool_stats = {}
        if self._tool_registry:
            tool_stats = self._tool_registry.get_stats()
        
        return {
            "skill_registry": skill_stats,
            "tool_registry": tool_stats
        }

    def create_team(self, team_id: str, name: str) -> bool:
        """
        创建团队
        
        Args:
            team_id: 团队 ID
            name: 团队名称
            
        Returns:
            是否成功
        """
        try:
            self._skill_registry.create_team(team_id, name)
            self._logger.info(f"已创建团队: {name}")
            return True
        except Exception as e:
            self._logger.error(f"创建团队失败 {name}: {e}")
            return False

    def add_user_to_team(self, team_id: str, user_id: str) -> bool:
        """
        添加用户到团队
        
        Args:
            team_id: 团队 ID
            user_id: 用户 ID
            
        Returns:
            是否成功
        """
        try:
            self._skill_registry.add_user_to_team(team_id, user_id)
            self._logger.info(f"已添加用户 {user_id} 到团队 {team_id}")
            return True
        except Exception as e:
            self._logger.error(f"添加用户到团队失败: {e}")
            return False

    def sync_skills(self, source_dir: str):
        """
        同步目录中的所有技能到注册中心
        
        Args:
            source_dir: 技能文件目录
        """
        self._logger.info(f"开始同步技能目录: {source_dir}")
        
        # 注册所有工具
        registered = self.register_from_directory(source_dir)
        
        # 为每个注册的工具创建对应的技能记录
        for tool_name in registered:
            self.register_skill(
                skill_id=tool_name,
                name=tool_name.replace("_", " ").title(),
                description=f"自动生成的技能: {tool_name}",
                category="general"
            )
        
        self._logger.info(f"同步完成，已注册 {len(registered)} 个技能")