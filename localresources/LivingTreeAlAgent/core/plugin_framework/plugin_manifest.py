"""
插件清单 - Plugin Manifest

用于声明和验证插件元数据

文件格式：plugin_manifest.json

示例：
{
    "id": "project_generator",
    "name": "项目生成器",
    "version": "1.0.0",
    "author": "Your Name",
    "description": "脚手架、模板管理、代码生成",
    "plugin_type": "project",
    "view_preference": {
        "preferred_mode": "wizard",
        "default_width": 600,
        "default_height": 400
    },
    "dependencies": ["knowledge_base"],
    "optional_deps": ["ai_chat"],
    "provides": ["templates"],
    "icon": "icons/project.svg",
    "lazy_load": true,
    "single_instance": true
}
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from enum import Enum

from .base_plugin import PluginManifest, PluginType, ViewPreference, ViewMode


class ManifestValidator:
    """
    插件清单验证器

    验证插件清单是否符合规范
    """

    REQUIRED_FIELDS = ["id", "name", "version"]
    OPTIONAL_FIELDS = [
        "author", "description", "plugin_type", "view_preference",
        "dependencies", "optional_deps", "provides", "icon",
        "lazy_load", "single_instance", "css"
    ]

    VALID_PLUGIN_TYPES = [pt.value for pt in PluginType]
    VALID_VIEW_MODES = [vm.value for vm in ViewMode]
    VALID_DOCK_AREAS = ["left", "right", "top", "bottom", "center"]

    @classmethod
    def validate(cls, data: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        验证清单数据

        Args:
            data: 清单数据

        Returns:
            (是否有效, 错误列表)
        """
        errors = []

        # 检查必需字段
        for field in cls.REQUIRED_FIELDS:
            if field not in data:
                errors.append(f"缺少必需字段: {field}")

        # 验证ID格式
        if "id" in data:
            plugin_id = data["id"]
            if not plugin_id.replace("_", "").replace("-", "").isalnum():
                errors.append("ID只能包含字母、数字、下划线和连字符")
            if plugin_id.startswith("_"):
                errors.append("ID不能以下划线开头")

        # 验证版本号格式
        if "version" in data:
            version = data["version"]
            parts = version.split(".")
            if len(parts) != 3:
                errors.append("版本号必须是 x.y.z 格式")
            if not all(p.isdigit() for p in parts):
                errors.append("版本号各部分必须是数字")

        # 验证插件类型
        if "plugin_type" in data:
            if data["plugin_type"] not in cls.VALID_PLUGIN_TYPES:
                errors.append(f"无效的插件类型: {data['plugin_type']}")

        # 验证视图偏好
        if "view_preference" in data:
            vp_errors = cls._validate_view_preference(data["view_preference"])
            errors.extend(vp_errors)

        # 验证依赖
        if "dependencies" in data:
            if not isinstance(data["dependencies"], list):
                errors.append("dependencies 必须是数组")

        if "optional_deps" in data:
            if not isinstance(data["optional_deps"], list):
                errors.append("optional_deps 必须是数组")

        # 验证布尔字段
        for bool_field in ["lazy_load", "single_instance"]:
            if bool_field in data and not isinstance(data[bool_field], bool):
                errors.append(f"{bool_field} 必须是布尔值")

        return len(errors) == 0, errors

    @classmethod
    def _validate_view_preference(cls, vp: Dict) -> List[str]:
        """验证视图偏好"""
        errors = []

        if "preferred_mode" in vp:
            if vp["preferred_mode"] not in cls.VALID_VIEW_MODES:
                errors.append(f"无效的视图模式: {vp['preferred_mode']}")

        if "dock_area" in vp:
            if vp["dock_area"] not in cls.VALID_DOCK_AREAS:
                errors.append(f"无效的停靠区域: {vp['dock_area']}")

        for size_field in ["default_width", "default_height", "min_width", "min_height"]:
            if size_field in vp:
                if not isinstance(vp[size_field], int) or vp[size_field] < 0:
                    errors.append(f"{size_field} 必须是正整数")

        return errors


class ManifestLoader:
    """
    插件清单加载器

    从文件或目录加载插件清单
    """

    @staticmethod
    def load_from_file(file_path: str) -> Optional[PluginManifest]:
        """
        从文件加载清单

        Args:
            file_path: 清单文件路径

        Returns:
            插件清单对象
        """
        if not os.path.exists(file_path):
            return None

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            valid, errors = ManifestValidator.validate(data)
            if not valid:
                raise ValueError(f"清单验证失败: {', '.join(errors)}")

            return ManifestLoader._parse_manifest(data)
        except Exception as e:
            raise RuntimeError(f"加载清单失败 {file_path}: {e}")

    @staticmethod
    def load_from_directory(dir_path: str) -> Optional[PluginManifest]:
        """
        从目录加载清单（查找 manifest.json）

        Args:
            dir_path: 插件目录路径

        Returns:
            插件清单对象
        """
        manifest_path = os.path.join(dir_path, "manifest.json")
        return ManifestLoader.load_from_file(manifest_path)

    @staticmethod
    def _parse_manifest(data: Dict[str, Any]) -> PluginManifest:
        """解析清单数据"""
        # 解析视图偏好
        view_pref = None
        if "view_preference" in data:
            vp_data = data["view_preference"]
            view_pref = ViewPreference(
                preferred_mode=ViewMode(vp_data.get("preferred_mode", "tabbed")),
                dock_area=vp_data.get("dock_area", "left"),
                default_width=vp_data.get("default_width", 400),
                default_height=vp_data.get("default_height", 600),
                min_width=vp_data.get("min_width", 200),
                min_height=vp_data.get("min_height", 150),
                floatable=vp_data.get("floatable", True),
                auto_hide=vp_data.get("auto_hide", False),
                closable=vp_data.get("closable", True),
            )

        # 解析插件类型
        plugin_type = PluginType.CUSTOM
        if "plugin_type" in data:
            plugin_type = PluginType(data["plugin_type"])

        return PluginManifest(
            id=data["id"],
            name=data["name"],
            version=data.get("version", "1.0.0"),
            author=data.get("author", ""),
            description=data.get("description", ""),
            plugin_type=plugin_type,
            view_preference=view_pref,
            dependencies=data.get("dependencies", []),
            optional_deps=data.get("optional_deps", []),
            provides=data.get("provides", []),
            icon=data.get("icon", ""),
            css=data.get("css", ""),
            lazy_load=data.get("lazy_load", True),
            single_instance=data.get("single_instance", True),
        )


class ManifestExporter:
    """
    插件清单导出器

    将清单导出为JSON或写入文件
    """

    @staticmethod
    def to_json(manifest: PluginManifest, indent: int = 2) -> str:
        """
        导出为JSON字符串

        Args:
            manifest: 插件清单
            indent: 缩进

        Returns:
            JSON字符串
        """
        data = manifest.to_dict()
        return json.dumps(data, ensure_ascii=False, indent=indent)

    @staticmethod
    def to_file(manifest: PluginManifest, file_path: str) -> bool:
        """
        导出到文件

        Args:
            manifest: 插件清单
            file_path: 文件路径

        Returns:
            是否成功
        """
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(ManifestExporter.to_json(manifest))
            return True
        except Exception:
            return False

    @staticmethod
    def create_template(
        plugin_id: str,
        name: str,
        plugin_type: str = "custom",
        author: str = ""
    ) -> str:
        """
        创建清单模板

        Args:
            plugin_id: 插件ID
            name: 插件名称
            plugin_type: 插件类型
            author: 作者

        Returns:
            JSON模板字符串
        """
        template = {
            "id": plugin_id,
            "name": name,
            "version": "1.0.0",
            "author": author,
            "description": "",
            "plugin_type": plugin_type,
            "view_preference": {
                "preferred_mode": "tabbed",
                "dock_area": "left",
                "default_width": 400,
                "default_height": 600,
                "min_width": 200,
                "min_height": 150,
                "floatable": True,
                "auto_hide": False,
                "closable": True
            },
            "dependencies": [],
            "optional_deps": [],
            "provides": [],
            "icon": "",
            "lazy_load": True,
            "single_instance": True
        }
        return json.dumps(template, ensure_ascii=False, indent=2)


def create_plugin_skeleton(
    plugin_id: str,
    name: str,
    output_dir: str,
    plugin_type: str = "custom"
) -> bool:
    """
    创建插件骨架

    创建完整的插件目录结构

    Args:
        plugin_id: 插件ID
        name: 插件名称
        output_dir: 输出目录
        plugin_type: 插件类型

    Returns:
        是否成功
    """
    import shutil

    plugin_dir = os.path.join(output_dir, plugin_id)
    if os.path.exists(plugin_dir):
        return False

    try:
        # 创建目录结构
        os.makedirs(plugin_dir)

        # 创建清单文件
        manifest_path = os.path.join(plugin_dir, "manifest.json")
        with open(manifest_path, 'w', encoding='utf-8') as f:
            f.write(ManifestExporter.create_template(plugin_id, name, plugin_type))

        # 创建入口文件
        init_file = os.path.join(plugin_dir, "__init__.py")
        with open(init_file, 'w', encoding='utf-8') as f:
            f.write(f'''"""
{plugin_id} 插件

{name}
"""

from .main_plugin import {to_class_name(plugin_id)}Plugin

__all__ = ['{to_class_name(plugin_id)}Plugin']
''')

        # 创建主插件文件
        main_file = os.path.join(plugin_dir, "main_plugin.py")
        with open(main_file, 'w', encoding='utf-8') as f:
            f.write(f'''"""
{plugin_id} 主插件文件
"""

from core.plugin_framework.base_plugin import (
    BasePlugin, PluginManifest, PluginType,
    ViewPreference, ViewMode
)


class {to_class_name(plugin_id)}Plugin(BasePlugin):
    """{name}插件"""

    def on_init(self) -> None:
        """初始化"""
        pass

    def on_create_widget(self):
        """创建Widget"""
        from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel

        widget = QWidget()
        layout = QVBoxLayout(widget)
        label = QLabel("{name}")
        layout.addWidget(label)
        return widget

    def on_activate(self) -> None:
        """激活"""
        pass

    def on_deactivate(self) -> None:
        """停用"""
        pass


# 插件清单
MANIFEST = PluginManifest(
    id="{plugin_id}",
    name="{name}",
    version="1.0.0",
    description="",
    plugin_type=PluginType.{plugin_type.upper()},
    view_preference=ViewPreference(
        preferred_mode=ViewMode.TABBED,
        dock_area="left",
        default_width=400,
        default_height=600,
    ),
    lazy_load=True,
)
''')

        # 创建资源目录
        icons_dir = os.path.join(plugin_dir, "icons")
        os.makedirs(icons_dir)

        return True
    except Exception:
        return False


def to_class_name(plugin_id: str) -> str:
    """将插件ID转换为类名"""
    parts = plugin_id.replace("-", "_").split("_")
    return "".join(p.capitalize() for p in parts if p)
