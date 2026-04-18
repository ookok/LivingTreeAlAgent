"""
插件注册中心

实现企业合规能力的插件化架构。

核心功能：
1. 插件生命周期管理
2. 插件接口定义
3. 插件市场
4. 插件编排
"""

import json
import importlib
import inspect
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Type
from enum import Enum
from datetime import datetime


# ==================== 数据模型 ====================

class PluginType(Enum):
    """插件类型"""
    DOCUMENT_GENERATOR = "document_generator"     # 文档生成
    DECLARATION = "declaration"                  # 申报执行
    DATA_SYNC = "data_sync"                       # 数据同步
    VALIDATION = "validation"                     # 验证审核
    KNOWLEDGE_PACKAGE = "knowledge_package"       # 知识包
    INTEGRATION = "integration"                   # 系统集成


class PluginStatus(Enum):
    """插件状态"""
    REGISTERED = "registered"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"
    UPDATING = "updating"


@dataclass
class PluginInfo:
    """插件信息"""
    plugin_id: str
    name: str
    version: str
    plugin_type: PluginType
    description: str = ""
    author: str = ""
    homepage: str = ""

    # 依赖
    dependencies: List[str] = field(default_factory=list)  # 依赖的插件ID
    conflicts: List[str] = field(default_factory=list)     # 冲突的插件

    # 接口
    interfaces: List[str] = field(default_factory=list)    # 提供的接口
    requires_interfaces: List[str] = field(default_factory=list)  # 需要的接口

    # 配置
    config_schema: Dict = field(default_factory=dict)     # 配置JSON Schema
    default_config: Dict = field(default_factory=dict)

    # 状态
    status: PluginStatus = PluginStatus.REGISTERED
    enabled_at: Optional[datetime] = None
    last_executed: Optional[datetime] = None

    # 统计
    execution_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    avg_execution_time_ms: float = 0.0

    # 评分
    rating: float = 0.0
    install_count: int = 0

    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class PluginInstance:
    """插件实例"""
    instance_id: str
    plugin_id: str
    plugin: Any                                    # 插件实例对象
    config: Dict = field(default_factory=dict)
    status: PluginStatus = PluginStatus.DISABLED
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class PluginMarketItem:
    """插件市场条目"""
    item_id: str
    plugin_info: PluginInfo
    install_script: str = ""                      # 安装脚本
    uninstall_script: str = ""                    # 卸载脚本
    thumbnail: str = ""                           # 缩略图
    screenshots: List[str] = field(default_factory=list)
    changelog: str = ""
    tags: List[str] = field(default_factory=list)
    pricing: str = "free"                         # free/paid/subscription
    license: str = "MIT"


# ==================== 插件接口定义 ====================

class IDocumentGeneratorPlugin:
    """文档生成插件接口"""

    async def generate_document(
        self,
        context: Dict,
        template_type: str,
        output_format: str = "docx"
    ) -> Dict:
        """
        生成文档

        Args:
            context: 上下文（包含企业Profile数据）
            template_type: 模板类型
            output_format: 输出格式

        Returns:
            {"success": True, "file_path": "...", "metadata": {...}}
        """
        raise NotImplementedError


class IDeclarationPlugin:
    """申报插件接口"""

    async def execute_declaration(
        self,
        declaration_type: str,
        profile_data: Dict,
        form_data: Dict
    ) -> Dict:
        """
        执行申报

        Returns:
            {"success": True, "submission_id": "...", "receipt": {...}}
        """
        raise NotImplementedError

    async def check_status(self, submission_id: str) -> Dict:
        """检查申报状态"""
        raise NotImplementedError


class IDataSyncPlugin:
    """数据同步插件接口"""

    async def pull_data(
        self,
        source_system: str,
        data_types: List[str]
    ) -> Dict:
        """从源系统拉取数据"""
        raise NotImplementedError

    async def push_data(
        self,
        target_system: str,
        data: Dict
    ) -> Dict:
        """推送数据到目标系统"""
        raise NotImplementedError


class IKnowledgePackagePlugin:
    """知识包插件接口"""

    async def load_knowledge(self) -> Dict:
        """加载知识包"""
        raise NotImplementedError

    async def query(self, query_text: str, top_k: int = 5) -> List[Dict]:
        """查询知识"""
        raise NotImplementedError


# ==================== 内置插件示例 ====================

BUILTIN_PLUGINS = {
    "env_business_license": {
        "name": "工商营业执照插件",
        "version": "1.0.0",
        "type": PluginType.DECLARATION,
        "description": "支持营业执照的在线申领、变更、注销",
        "author": "System",
        "interfaces": ["IDeclarationPlugin"],
        "target_systems": ["国家市场监督管理总局"],
        "capabilities": ["register", "change", "cancel"]
    },
    "env_tax_filing": {
        "name": "税务申报插件",
        "version": "1.0.0",
        "type": PluginType.DECLARATION,
        "description": "支持各类税务申报自动化",
        "author": "System",
        "interfaces": ["IDeclarationPlugin"],
        "target_systems": ["国家税务总局电子税务局"],
        "capabilities": ["monthly", "quarterly", "annual"]
    },
    "env_pollution_permit": {
        "name": "排污许可证插件",
        "version": "1.0.0",
        "type": PluginType.DECLARATION,
        "description": "支持排污许可证申领、变更、续期",
        "author": "System",
        "interfaces": ["IDeclarationPlugin"],
        "target_systems": ["全国排污许可管理信息平台"],
        "capabilities": ["apply", "change", "renew", "report"]
    },
    "env_eia_document": {
        "name": "环评文档生成插件",
        "version": "1.0.0",
        "type": PluginType.DOCUMENT_GENERATOR,
        "description": "智能生成环评报告及相关文档",
        "author": "System",
        "interfaces": ["IDocumentGeneratorPlugin"],
        "template_types": ["eia_report", "eia_table", "environmental_backup"]
    },
    "env_knowledge": {
        "name": "环保知识包",
        "version": "1.0.0",
        "type": PluginType.KNOWLEDGE_PACKAGE,
        "description": "环保法规、标准、技术规范知识库",
        "author": "System",
        "interfaces": ["IKnowledgePackagePlugin"],
        "knowledge_areas": ["environmental_law", "emission_standards", "monitoring_methods"]
    },
    "env_smart_browser": {
        "name": "环保智能浏览器插件",
        "version": "1.0.0",
        "type": PluginType.INTEGRATION,
        "description": "政府网站智能填报浏览器",
        "author": "System",
        "interfaces": [],
        "capabilities": ["auto_login", "form_recognition", "auto_fill", "captcha_solve"]
    }
}


# ==================== 插件注册中心 ====================

class PluginRegistry:
    """
    插件注册中心

    核心功能：
    1. 插件注册与发现
    2. 插件生命周期管理
    3. 插件市场
    4. 插件编排执行
    """

    def __init__(self):
        self._plugins: Dict[str, PluginInfo] = {}          # plugin_id -> info
        self._instances: Dict[str, PluginInstance] = {}   # instance_id -> instance
        self._plugin_classes: Dict[str, Type] = {}        # plugin_id -> class
        self._market: Dict[str, PluginMarketItem] = {}     # market item_id -> item

        # 加载内置插件
        self._load_builtin_plugins()

    def _load_builtin_plugins(self):
        """加载内置插件"""
        for plugin_id, config in BUILTIN_PLUGINS.items():
            self.register_plugin(
                plugin_id=plugin_id,
                name=config["name"],
                version=config["version"],
                plugin_type=config["type"],
                description=config["description"],
                author=config["author"],
                interfaces=config.get("interfaces", [])
            )

    def register_plugin(
        self,
        plugin_id: str,
        name: str,
        version: str,
        plugin_type: PluginType,
        description: str = "",
        author: str = "",
        dependencies: List[str] = None,
        interfaces: List[str] = None,
        config_schema: Dict = None,
        default_config: Dict = None
    ) -> bool:
        """
        注册插件

        Args:
            plugin_id: 插件唯一ID
            name: 插件名称
            version: 版本号
            plugin_type: 插件类型
            description: 描述
            author: 作者
            dependencies: 依赖
            interfaces: 提供的接口
            config_schema: 配置Schema
            default_config: 默认配置

        Returns:
            是否成功
        """
        if plugin_id in self._plugins:
            return False

        plugin_info = PluginInfo(
            plugin_id=plugin_id,
            name=name,
            version=version,
            plugin_type=plugin_type,
            description=description,
            author=author,
            dependencies=dependencies or [],
            interfaces=interfaces or [],
            config_schema=config_schema or {},
            default_config=default_config or {}
        )

        self._plugins[plugin_id] = plugin_info
        return True

    def register_plugin_class(
        self,
        plugin_id: str,
        plugin_class: Type
    ):
        """注册插件类"""
        self._plugin_classes[plugin_id] = plugin_class

    def enable_plugin(
        self,
        plugin_id: str,
        config: Dict = None
    ) -> Optional[str]:
        """
        启用插件

        Args:
            plugin_id: 插件ID
            config: 配置

        Returns:
            instance_id
        """
        plugin_info = self._plugins.get(plugin_id)
        if not plugin_info:
            return None

        # 检查依赖
        for dep in plugin_info.dependencies:
            if dep not in self._instances:
                raise ValueError(f"Missing dependency: {dep}")

        # 创建实例
        instance_id = f"{plugin_id}:{datetime.now().strftime('%Y%m%d%H%M%S')}"
        plugin_class = self._plugin_classes.get(plugin_id)

        plugin_instance = None
        if plugin_class:
            try:
                plugin_instance = plugin_class()
            except:
                plugin_instance = object()

        instance = PluginInstance(
            instance_id=instance_id,
            plugin_id=plugin_id,
            plugin=plugin_instance,
            config=config or plugin_info.default_config,
            status=PluginStatus.ENABLED
        )

        self._instances[instance_id] = instance
        plugin_info.status = PluginStatus.ENABLED
        plugin_info.enabled_at = datetime.now()

        return instance_id

    def disable_plugin(self, instance_id: str) -> bool:
        """禁用插件"""
        instance = self._instances.get(instance_id)
        if not instance:
            return False

        instance.status = PluginStatus.DISABLED
        return True

    def get_plugin(self, instance_id: str) -> Optional[Any]:
        """获取插件实例"""
        instance = self._instances.get(instance_id)
        return instance.plugin if instance else None

    def list_plugins(
        self,
        plugin_type: PluginType = None,
        status: PluginStatus = None
    ) -> List[PluginInfo]:
        """列出插件"""
        plugins = list(self._plugins.values())

        if plugin_type:
            plugins = [p for p in plugins if p.plugin_type == plugin_type]

        if status:
            plugins = [p for p in plugins if p.status == status]

        return plugins

    def list_enabled_plugins(self) -> List[PluginInstance]:
        """列出已启用的插件"""
        return [
            i for i in self._instances.values()
            if i.status == PluginStatus.ENABLED
        ]

    # ==================== 插件市场 ====================

    def publish_to_market(
        self,
        plugin_id: str,
        tags: List[str] = None,
        pricing: str = "free",
        changelog: str = ""
    ) -> bool:
        """发布到插件市场"""
        plugin_info = self._plugins.get(plugin_id)
        if not plugin_info:
            return False

        item = PluginMarketItem(
            item_id=plugin_id,
            plugin_info=plugin_info,
            tags=tags or [],
            pricing=pricing,
            changelog=changelog
        )

        self._market[plugin_id] = item
        plugin_info.install_count += 1

        return True

    def get_market_items(
        self,
        plugin_type: PluginType = None,
        tag: str = None,
        search: str = None
    ) -> List[PluginMarketItem]:
        """获取市场条目"""
        items = list(self._market.values())

        if plugin_type:
            items = [i for i in items if i.plugin_info.plugin_type == plugin_type]

        if tag:
            items = [i for i in items if tag in i.tags]

        if search:
            search = search.lower()
            items = [
                i for i in items
                if search in i.plugin_info.name.lower()
                or search in i.plugin_info.description.lower()
            ]

        return items

    # ==================== 插件编排 ====================

    async def execute_chain(
        self,
        chain_name: str,
        context: Dict,
        plugin_ids: List[str],
        **kwargs
    ) -> List[Dict]:
        """
        执行插件链

        Args:
            chain_name: 链名称
            context: 上下文数据
            plugin_ids: 插件ID列表

        Returns:
            每步的执行结果
        """
        results = []
        current_context = context.copy()

        for plugin_id in plugin_ids:
            instance = self._instances.get(plugin_id)
            if not instance or instance.status != PluginStatus.ENABLED:
                results.append({
                    "plugin_id": plugin_id,
                    "success": False,
                    "error": "Plugin not enabled"
                })
                continue

            plugin = instance.plugin
            start_time = datetime.now()

            try:
                # 根据插件类型调用不同接口
                if isinstance(plugin, IDocumentGeneratorPlugin):
                    result = await plugin.generate_document(
                        current_context,
                        kwargs.get("template_type", ""),
                        kwargs.get("output_format", "docx")
                    )
                elif isinstance(plugin, IDeclarationPlugin):
                    result = await plugin.execute_declaration(
                        kwargs.get("declaration_type", ""),
                        current_context,
                        kwargs.get("form_data", {})
                    )
                elif isinstance(plugin, IDataSyncPlugin):
                    result = await plugin.pull_data(
                        kwargs.get("source_system", ""),
                        kwargs.get("data_types", [])
                    )
                elif isinstance(plugin, IKnowledgePackagePlugin):
                    result = await plugin.load_knowledge()
                else:
                    # 通用调用
                    if hasattr(plugin, "execute"):
                        result = await plugin.execute(current_context)
                    else:
                        result = {"success": True, "data": current_context}

                # 更新上下文
                if result.get("success"):
                    current_context.update(result.get("data", {}))

                # 记录执行
                self._record_execution(
                    plugin_id, True,
                    (datetime.now() - start_time).total_seconds() * 1000
                )

                results.append({
                    "plugin_id": plugin_id,
                    "success": True,
                    "result": result
                })

            except Exception as e:
                self._record_execution(
                    plugin_id, False,
                    (datetime.now() - start_time).total_seconds() * 1000
                )

                results.append({
                    "plugin_id": plugin_id,
                    "success": False,
                    "error": str(e)
                })

        return results

    def _record_execution(
        self,
        plugin_id: str,
        success: bool,
        execution_time_ms: float
    ):
        """记录执行统计"""
        plugin_info = self._plugins.get(plugin_id)
        if not plugin_info:
            return

        plugin_info.execution_count += 1
        if success:
            plugin_info.success_count += 1
        else:
            plugin_info.failure_count += 1

        # 更新平均执行时间
        current_avg = plugin_info.avg_execution_time_ms
        count = plugin_info.execution_count
        plugin_info.avg_execution_time_ms = (
            (current_avg * (count - 1) + execution_time_ms) / count
        )

    def get_execution_stats(self, plugin_id: str = None) -> Dict:
        """获取执行统计"""
        if plugin_id:
            plugin_info = self._plugins.get(plugin_id)
            if not plugin_info:
                return {}

            return {
                "plugin_id": plugin_id,
                "name": plugin_info.name,
                "execution_count": plugin_info.execution_count,
                "success_count": plugin_info.success_count,
                "failure_count": plugin_info.failure_count,
                "success_rate": (
                    plugin_info.success_count / plugin_info.execution_count
                    if plugin_info.execution_count > 0 else 0
                ),
                "avg_execution_time_ms": plugin_info.avg_execution_time_ms
            }

        return {
            pid: self.get_execution_stats(pid)
            for pid in self._plugins.keys()
        }


# ==================== 单例模式 ====================

_plugin_registry: Optional[PluginRegistry] = None


def get_plugin_registry() -> PluginRegistry:
    """获取插件注册中心单例"""
    global _plugin_registry
    if _plugin_registry is None:
        _plugin_registry = PluginRegistry()
    return _plugin_registry
