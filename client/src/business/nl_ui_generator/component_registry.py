"""
Component Registry - 动态组件注册表
=====================================

动态组件注册和管理，支持用户自定义组件。

功能:
- 注册新组件
- 组件冲突检测
- 组件版本管理
- 组件文档生成
"""

import json
import time
import hashlib
from typing import Optional, Any, Callable, Dict, List
from dataclasses import dataclass, field
from enum import Enum


class ComponentType(Enum):
    """组件类型"""
    BUTTON = "button"
    INPUT = "input"
    CONTAINER = "container"
    TEXT = "text"
    IMAGE = "image"
    LIST = "list"
    CARD = "card"
    MODAL = "modal"
    CUSTOM = "custom"


@dataclass
class ComponentDefinition:
    """组件定义"""
    id: str
    name: str
    type: ComponentType
    description: str = ""

    # 组件结构
    template: dict = field(default_factory=dict)  # 模板定义
    default_props: dict = field(default_factory=dict)  # 默认属性
    prop_schema: dict = field(default_factory=dict)  # 属性schema

    # 样式
    default_style: dict = field(default_factory=dict)

    # 行为
    events: dict = field(default_factory=dict)  # 事件定义
    methods: list = field(default_factory=list)  # 方法列表

    # 依赖
    dependencies: list = field(default_factory=list)
    assets: list = field(default_factory=list)

    # 元数据
    version: str = "1.0.0"
    author: str = "system"
    tags: list = field(default_factory=list)
    documentation: str = ""

    # 状态
    enabled: bool = True
    deprecated: bool = False
    deprecation_message: str = ""

    def __post_init__(self):
        if isinstance(self.type, str):
            self.type = ComponentType(self.type)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value if isinstance(self.type, ComponentType) else self.type,
            "description": self.description,
            "template": self.template,
            "default_props": self.default_props,
            "prop_schema": self.prop_schema,
            "default_style": self.default_style,
            "events": self.events,
            "methods": self.methods,
            "dependencies": self.dependencies,
            "assets": self.assets,
            "version": self.version,
            "author": self.author,
            "tags": self.tags,
            "documentation": self.documentation,
            "enabled": self.enabled,
            "deprecated": self.deprecated,
            "deprecation_message": self.deprecation_message,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ComponentDefinition":
        return cls(
            id=data["id"],
            name=data["name"],
            type=ComponentType(data.get("type", "custom")),
            description=data.get("description", ""),
            template=data.get("template", {}),
            default_props=data.get("default_props", {}),
            prop_schema=data.get("prop_schema", {}),
            default_style=data.get("default_style", {}),
            events=data.get("events", {}),
            methods=data.get("methods", []),
            dependencies=data.get("dependencies", []),
            assets=data.get("assets", []),
            version=data.get("version", "1.0.0"),
            author=data.get("author", "system"),
            tags=data.get("tags", []),
            documentation=data.get("documentation", ""),
            enabled=data.get("enabled", True),
            deprecated=data.get("deprecated", False),
            deprecation_message=data.get("deprecation_message", ""),
        )


@dataclass
class DynamicComponent:
    """动态创建的组件实例"""
    instance_id: str
    definition_id: str
    props: dict
    style: dict
    children: list = field(default_factory=list)
    created_at: float = 0
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()

    def to_dict(self) -> dict:
        return {
            "instance_id": self.instance_id,
            "definition_id": self.definition_id,
            "props": self.props,
            "style": self.style,
            "children": self.children,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


class ComponentRegistry:
    """组件注册表"""

    # 内置组件
    BUILTIN_COMPONENTS = [
        ComponentDefinition(
            id="builtin.button",
            name="按钮",
            type=ComponentType.BUTTON,
            description="基础按钮组件",
            template={
                "type": "button",
                "text": "{{text}}",
            },
            default_props={
                "text": "按钮",
                "variant": "primary",
                "disabled": False,
            },
            prop_schema={
                "text": {"type": "string", "label": "文本"},
                "variant": {"type": "select", "label": "样式", "options": ["primary", "secondary", "danger"]},
                "disabled": {"type": "boolean", "label": "禁用"},
            },
            events={
                "onClick": "点击事件",
                "onHover": "悬停事件",
            },
        ),
        ComponentDefinition(
            id="builtin.input",
            name="输入框",
            type=ComponentType.INPUT,
            description="文本输入组件",
            template={
                "type": "input",
                "placeholder": "{{placeholder}}",
            },
            default_props={
                "placeholder": "请输入...",
                "type": "text",
                "disabled": False,
            },
            prop_schema={
                "placeholder": {"type": "string", "label": "占位文本"},
                "type": {"type": "select", "label": "输入类型", "options": ["text", "password", "number"]},
            },
            events={
                "onChange": "内容变化",
                "onFocus": "获得焦点",
                "onBlur": "失去焦点",
            },
        ),
        ComponentDefinition(
            id="builtin.text",
            name="文本",
            type=ComponentType.TEXT,
            description="文本显示组件",
            template={
                "type": "text",
                "content": "{{content}}",
            },
            default_props={
                "content": "文本内容",
                "size": "normal",
            },
            prop_schema={
                "content": {"type": "string", "label": "文本内容"},
                "size": {"type": "select", "label": "大小", "options": ["small", "normal", "large"]},
            },
        ),
        ComponentDefinition(
            id="builtin.container",
            name="容器",
            type=ComponentType.CONTAINER,
            description="布局容器组件",
            template={
                "type": "container",
                "layout": "{{layout}}",
            },
            default_props={
                "layout": "vertical",
                "spacing": 8,
            },
            prop_schema={
                "layout": {"type": "select", "label": "布局", "options": ["vertical", "horizontal", "grid"]},
                "spacing": {"type": "number", "label": "间距"},
            },
        ),
        ComponentDefinition(
            id="builtin.card",
            name="卡片",
            type=ComponentType.CARD,
            description="卡片容器组件",
            template={
                "type": "card",
                "shadow": True,
            },
            default_props={
                "title": "卡片标题",
                "content": "",
                "shadow": True,
            },
            prop_schema={
                "title": {"type": "string", "label": "标题"},
                "content": {"type": "text", "label": "内容"},
                "shadow": {"type": "boolean", "label": "阴影"},
            },
        ),
    ]

    def __init__(self):
        self.components: Dict[str, ComponentDefinition] = {}
        self.instances: Dict[str, DynamicComponent] = {}
        self.categories: Dict[str, List[str]] = {}  # 分类 -> 组件ID列表

        # 加载内置组件
        self._load_builtin_components()

        # 统计
        self.stats = {
            "total_registrations": 0,
            "total_instances": 0,
        }

    def _load_builtin_components(self):
        """加载内置组件"""
        for comp in self.BUILTIN_COMPONENTS:
            self.components[comp.id] = comp
            self._add_to_category(comp)

    def _add_to_category(self, component: ComponentDefinition):
        """添加到分类"""
        category = component.type.value
        if category not in self.categories:
            self.categories[category] = []
        if component.id not in self.categories[category]:
            self.categories[category].append(component.id)

    def register(
        self,
        definition: ComponentDefinition,
        allow_override: bool = False,
    ) -> tuple[bool, str]:
        """
        注册组件

        Args:
            definition: 组件定义
            allow_override: 是否允许覆盖现有组件

        Returns:
            (success, message): 注册是否成功及消息
        """
        # 检查冲突
        if definition.id in self.components:
            if not allow_override:
                return False, f"组件ID '{definition.id}' 已存在"

            # 检查是否为内置组件
            if definition.id.startswith("builtin."):
                return False, "不能覆盖内置组件"

        # 检查冲突（基于名称和类型）
        for comp in self.components.values():
            if comp.name == definition.name and comp.type == definition.type and comp.id != definition.id:
                return False, f"存在同名组件: {definition.name} ({comp.type.value})"

        # 注册组件
        self.components[definition.id] = definition
        self._add_to_category(definition)

        self.stats["total_registrations"] += 1

        return True, "注册成功"

    def unregister(self, component_id: str) -> bool:
        """
        注销组件

        Args:
            component_id: 组件ID

        Returns:
            是否成功注销
        """
        if component_id.startswith("builtin."):
            return False  # 不能注销内置组件

        if component_id in self.components:
            component = self.components.pop(component_id)

            # 从分类中移除
            category = component.type.value
            if category in self.categories:
                if component_id in self.categories[category]:
                    self.categories[category].remove(component_id)

            return True

        return False

    def get(self, component_id: str) -> Optional[ComponentDefinition]:
        """获取组件定义"""
        return self.components.get(component_id)

    def get_all(self, include_disabled: bool = False) -> List[ComponentDefinition]:
        """获取所有组件"""
        components = []
        for comp in self.components.values():
            if include_disabled or comp.enabled:
                components.append(comp)
        return components

    def get_by_category(self, category: str) -> List[ComponentDefinition]:
        """获取指定分类的组件"""
        component_ids = self.categories.get(category, [])
        return [self.components[cid] for cid in component_ids if cid in self.components]

    def get_by_tag(self, tag: str) -> List[ComponentDefinition]:
        """获取包含指定标签的组件"""
        return [c for c in self.components.values() if tag in c.tags]

    def search(self, query: str, limit: int = 10) -> List[ComponentDefinition]:
        """
        搜索组件

        Args:
            query: 搜索查询
            limit: 返回数量限制

        Returns:
            匹配的组件列表
        """
        query = query.lower()
        results = []

        for comp in self.components.values():
            if not comp.enabled or comp.deprecated:
                continue

            score = 0

            # ID匹配
            if query in comp.id.lower():
                score += 3

            # 名称匹配
            if query in comp.name.lower():
                score += 5

            # 描述匹配
            if query in comp.description.lower():
                score += 2

            # 标签匹配
            for tag in comp.tags:
                if query in tag.lower():
                    score += 1

            if score > 0:
                results.append((score, comp))

        # 按分数排序
        results.sort(key=lambda x: x[0], reverse=True)
        return [comp for _, comp in results[:limit]]

    def check_conflict(self, definition: ComponentDefinition) -> Optional[str]:
        """
        检查组件冲突

        Args:
            definition: 组件定义

        Returns:
            冲突描述，或None表示无冲突
        """
        # 检查ID冲突
        if definition.id in self.components:
            existing = self.components[definition.id]
            if existing.name != definition.name:
                return f"ID冲突: '{definition.id}' 已被 '{existing.name}' 使用"

        # 检查名称+类型冲突
        for comp in self.components.values():
            if comp.id == definition.id:
                continue
            if comp.name == definition.name and comp.type == definition.type:
                return f"存在同名组件: {comp.name} ({comp.type.value})"

        return None

    # ========== 组件实例管理 ==========

    def create_instance(
        self,
        component_id: str,
        props: dict = None,
        style: dict = None,
        instance_id: str = None,
    ) -> tuple[Optional[DynamicComponent], str]:
        """
        创建组件实例

        Args:
            component_id: 组件定义ID
            props: 实例属性
            style: 实例样式
            instance_id: 实例ID，默认自动生成

        Returns:
            (instance, message): 实例和消息
        """
        definition = self.get(component_id)
        if not definition:
            return None, f"组件 '{component_id}' 不存在"

        if not definition.enabled:
            return None, f"组件 '{component_id}' 已禁用"

        # 生成实例ID
        if not instance_id:
            instance_id = f"{component_id}_{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}"

        # 合并属性
        merged_props = {**definition.default_props, **(props or {})}

        # 合并样式
        merged_style = {**definition.default_style, **(style or {})}

        instance = DynamicComponent(
            instance_id=instance_id,
            definition_id=component_id,
            props=merged_props,
            style=merged_style,
        )

        self.instances[instance_id] = instance
        self.stats["total_instances"] += 1

        return instance, "创建成功"

    def get_instance(self, instance_id: str) -> Optional[DynamicComponent]:
        """获取组件实例"""
        return self.instances.get(instance_id)

    def update_instance(self, instance_id: str, **kwargs) -> bool:
        """更新组件实例"""
        instance = self.instances.get(instance_id)
        if not instance:
            return False

        if "props" in kwargs:
            instance.props.update(kwargs["props"])
        if "style" in kwargs:
            instance.style.update(kwargs["style"])
        if "children" in kwargs:
            instance.children = kwargs["children"]

        return True

    def destroy_instance(self, instance_id: str) -> bool:
        """销毁组件实例"""
        if instance_id in self.instances:
            del self.instances[instance_id]
            return True
        return False

    # ========== 文档生成 ==========

    def generate_documentation(self, component_id: str) -> str:
        """
        生成组件文档

        Args:
            component_id: 组件ID

        Returns:
            Markdown格式文档
        """
        component = self.get(component_id)
        if not component:
            return f"组件 '{component_id}' 不存在"

        doc = f"""# {component.name}

**类型**: {component.type.value}
**ID**: `{component.id}`
**版本**: {component.version}
**作者**: {component.author}

## 描述

{component.description or "无描述"}

## 属性

"""

        # 属性表格
        if component.prop_schema:
            doc += "| 属性名 | 类型 | 说明 |\n"
            doc += "|--------|------|------|\n"
            for prop_name, prop_info in component.prop_schema.items():
                prop_type = prop_info.get("type", "string")
                prop_label = prop_info.get("label", prop_name)
                options = prop_info.get("options", [])
                if options:
                    prop_label += f" (可选: {', '.join(options)})"
                doc += f"| `{prop_name}` | {prop_type} | {prop_label} |\n"

        # 事件
        if component.events:
            doc += "\n## 事件\n\n"
            for event_name, event_desc in component.events.items():
                doc += f"- `{event_name}`: {event_desc}\n"

        # 方法
        if component.methods:
            doc += "\n## 方法\n\n"
            for method in component.methods:
                doc += f"- `{method}`\n"

        # 标签
        if component.tags:
            doc += f"\n**标签**: {', '.join(component.tags)}\n"

        return doc

    def export_components(self) -> str:
        """导出所有组件为JSON"""
        return json.dumps(
            [comp.to_dict() for comp in self.components.values()],
            ensure_ascii=False,
            indent=2,
        )

    def import_components(self, json_str: str) -> tuple[int, int]:
        """
        从JSON导入组件

        Args:
            json_str: JSON字符串

        Returns:
            (imported_count, failed_count)
        """
        try:
            data = json.loads(json_str)
            imported = 0
            failed = 0

            for comp_data in data:
                try:
                    comp = ComponentDefinition.from_dict(comp_data)
                    success, _ = self.register(comp, allow_override=True)
                    if success:
                        imported += 1
                    else:
                        failed += 1
                except Exception:
                    failed += 1

            return imported, failed
        except Exception:
            return 0, 0


# 全局单例
_registry_instance: Optional[ComponentRegistry] = None


def get_component_registry() -> ComponentRegistry:
    """获取组件注册表单例"""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = ComponentRegistry()
    return _registry_instance