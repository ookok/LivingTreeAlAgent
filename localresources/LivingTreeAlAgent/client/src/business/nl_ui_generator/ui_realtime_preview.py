"""
UI Realtime Preview - UI实时预览
=================================

支持UI变更的实时预览、对比和确认。

功能:
- 克隆模板生成预览
- 应用变更并显示差异
- 用户确认后保存
- 预览窗口管理
"""

import uuid
import copy
import asyncio
from typing import Optional, Any, Callable, Awaitable, Protocol
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict


class PreviewStatus(Enum):
    """预览状态"""
    PENDING = "pending"      # 待确认
    CONFIRMED = "confirmed"  # 已确认
    REJECTED = "rejected"    # 已拒绝
    EXPIRED = "expired"      # 已过期


@dataclass
class PreviewChange:
    """预览变更"""
    change_type: str  # add, modify, remove, move, resize
    target_id: str    # 目标组件ID
    property_name: str = ""
    old_value: Any = None
    new_value: Any = None
    position: dict = None  # 新位置
    size: dict = None      # 新尺寸
    metadata: dict = field(default_factory=dict)


@dataclass
class PreviewResult:
    """预览结果"""
    preview_id: str
    template_id: str
    status: PreviewStatus
    changes: list[PreviewChange] = field(default_factory=list)
    original_template: dict = None  # 原始模板快照
    modified_template: dict = None  # 修改后的模板
    diff: dict = field(default_factory=dict)
    created_at: float = 0
    confirmed_at: float = 0
    expires_at: float = 0
    user_feedback: str = ""


class PreviewWindow:
    """预览窗口（抽象）"""

    def __init__(self, preview_id: str):
        self.preview_id = preview_id
        self.content = None
        self.callbacks = defaultdict(list)

    def set_content(self, content: dict):
        """设置预览内容"""
        self.content = content

    def on_confirm(self, callback: Callable):
        """注册确认回调"""
        self.callbacks["confirm"].append(callback)

    def on_reject(self, callback: Callable):
        """注册拒绝回调"""
        self.callbacks["reject"].append(callback)

    async def confirm(self):
        """确认预览"""
        for callback in self.callbacks["confirm"]:
            if asyncio.iscoroutinefunction(callback):
                await callback(self.content)
            else:
                callback(self.content)

    async def reject(self):
        """拒绝预览"""
        for callback in self.callbacks["reject"]:
            if asyncio.iscoroutinefunction(callback):
                await callback()
            else:
                callback()


class UIRealtimePreview:
    """UI实时预览管理器"""

    def __init__(self):
        self.previews: dict[str, PreviewResult] = {}
        self.preview_windows: dict[str, PreviewWindow] = {}
        self.template_cache: dict[str, dict] = {}  # 模板缓存
        self.auto_cleanup_seconds = 300  # 5分钟后自动清理

    def create_preview(
        self,
        template_id: str,
        original_template: dict,
        changes: list[PreviewChange],
    ) -> PreviewResult:
        """
        创建预览

        Args:
            template_id: 模板ID
            original_template: 原始模板
            changes: 要应用的变更

        Returns:
            PreviewResult: 预览结果
        """
        import time

        preview_id = f"preview_{uuid.uuid4().hex[:12]}"
        created_at = time.time()

        # 深拷贝原始模板
        modified = copy.deepcopy(original_template)

        # 应用变更
        for change in changes:
            self._apply_change(modified, change)

        # 计算差异
        diff = self._compute_diff(original_template, modified)

        result = PreviewResult(
            preview_id=preview_id,
            template_id=template_id,
            status=PreviewStatus.PENDING,
            changes=changes,
            original_template=original_template,
            modified_template=modified,
            diff=diff,
            created_at=created_at,
            expires_at=created_at + self.auto_cleanup_seconds,
        )

        self.previews[preview_id] = result
        return result

    def _apply_change(self, template: dict, change: PreviewChange):
        """应用单个变更到模板"""
        components = template.get("components", [])

        if change.change_type == "add":
            # 添加组件
            new_component = {
                "id": change.target_id,
                "type": change.new_value.get("type", "button"),
                "name": change.new_value.get("name", change.target_id),
                "text": change.new_value.get("text", ""),
                "position": change.position or {"x": 0, "y": 0},
                "size": change.size or {"width": 100, "height": 40},
            }
            components.append(new_component)

        elif change.change_type == "modify":
            # 修改组件属性
            for comp in components:
                if comp.get("id") == change.target_id:
                    if change.property_name:
                        comp[change.property_name] = change.new_value
                    break

        elif change.change_type == "remove":
            # 移除组件
            template["components"] = [c for c in components if c.get("id") != change.target_id]

        elif change.change_type == "move":
            # 移动组件位置
            for comp in components:
                if comp.get("id") == change.target_id:
                    if change.position:
                        comp["position"] = change.position
                    break

        elif change.change_type == "resize":
            # 调整组件大小
            for comp in components:
                if comp.get("id") == change.target_id:
                    if change.size:
                        comp["size"] = change.size
                    break

        template["components"] = components

    def _compute_diff(self, original: dict, modified: dict) -> dict:
        """计算两个模板之间的差异"""
        diff = {
            "added": [],
            "removed": [],
            "modified": [],
        }

        orig_ids = {c.get("id") for c in original.get("components", [])}
        mod_ids = {c.get("id") for c in modified.get("components", [])}

        # 新增的组件
        diff["added"] = list(mod_ids - orig_ids)

        # 移除的组件
        diff["removed"] = list(orig_ids - mod_ids)

        # 修改的组件
        orig_map = {c.get("id"): c for c in original.get("components", [])}
        mod_map = {c.get("id"): c for c in modified.get("components", [])}

        for comp_id in orig_ids & mod_ids:
            orig_comp = orig_map[comp_id]
            mod_comp = mod_map[comp_id]
            if orig_comp != mod_comp:
                diff["modified"].append({
                    "id": comp_id,
                    "changes": self._get_component_changes(orig_comp, mod_comp)
                })

        return diff

    def _get_component_changes(self, orig: dict, mod: dict) -> list:
        """获取组件的具体变更"""
        changes = []
        for key in set(orig.keys()) | set(mod.keys()):
            if orig.get(key) != mod.get(key):
                changes.append({
                    "property": key,
                    "old": orig.get(key),
                    "new": mod.get(key),
                })
        return changes

    def get_preview(self, preview_id: str) -> Optional[PreviewResult]:
        """获取预览"""
        return self.previews.get(preview_id)

    async def confirm_preview(self, preview_id: str) -> bool:
        """
        确认预览

        Args:
            preview_id: 预览ID

        Returns:
            是否确认成功
        """
        import time

        preview = self.previews.get(preview_id)
        if not preview:
            return False

        if preview.status != PreviewStatus.PENDING:
            return False

        preview.status = PreviewStatus.CONFIRMED
        preview.confirmed_at = time.time()

        # 通知窗口
        window = self.preview_windows.get(preview_id)
        if window:
            await window.confirm()

        return True

    async def reject_preview(self, preview_id: str) -> bool:
        """
        拒绝预览

        Args:
            preview_id: 预览ID

        Returns:
            是否拒绝成功
        """
        import time

        preview = self.previews.get(preview_id)
        if not preview:
            return False

        preview.status = PreviewStatus.REJECTED

        # 通知窗口
        window = self.preview_windows.get(preview_id)
        if window:
            await window.reject()

        return True

    def cleanup_expired_previews(self):
        """清理过期的预览"""
        import time
        current_time = time.time()

        expired_ids = [
            pid for pid, p in self.previews.items()
            if p.status == PreviewStatus.PENDING and p.expires_at < current_time
        ]

        for pid in expired_ids:
            self.previews[pid].status = PreviewStatus.EXPIRED

        return len(expired_ids)

    def render_preview_html(self, preview_id: str) -> Optional[str]:
        """
        渲染预览为HTML

        Args:
            preview_id: 预览ID

        Returns:
            HTML字符串
        """
        preview = self.get_preview(preview_id)
        if not preview:
            return None

        template = preview.modified_template
        components = template.get("components", [])

        html_parts = ["""
        <div class="preview-container" style="font-family: Arial, sans-serif; padding: 20px;">
            <h3>预览面板</h3>
            <div class="preview-changes" style="margin-bottom: 20px; padding: 10px; background: #f5f5f5; border-radius: 4px;">
                <strong>变更摘要：</strong>
                <span style="color: green;">+{} 新增</span> |
                <span style="color: red;">-{} 移除</span> |
                <span style="color: blue;">~{} 修改</span>
            </div>
            <div class="preview-components">
        """.format(
            len(preview.diff.get("added", [])),
            len(preview.diff.get("removed", [])),
            len(preview.diff.get("modified", [])),
        )]

        for comp in components:
            comp_type = comp.get("type", "unknown")
            comp_id = comp.get("id", "")
            comp_name = comp.get("name", comp_id)
            comp_text = comp.get("text", "")
            position = comp.get("position", {})
            size = comp.get("size", {})
            style = comp.get("style", {})

            x = position.get("x", 0)
            y = position.get("y", 0)
            width = size.get("width", 100)
            height = size.get("height", 40)

            bg_color = style.get("background_color", "#007acc")
            text_color = style.get("text_color", "#ffffff")
            border_radius = style.get("border_radius", 4)

            if comp_type == "button":
                html_parts.append(f"""
                <div id="{comp_id}" class="preview-component" style="
                    position: relative;
                    left: {x}px;
                    top: {y}px;
                    width: {width}px;
                    height: {height}px;
                    background-color: {bg_color};
                    color: {text_color};
                    border-radius: {border_radius}px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    cursor: pointer;
                    margin: 5px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                ">
                    {comp_text or comp_name}
                </div>
                """)
            elif comp_type == "input":
                html_parts.append(f"""
                <div id="{comp_id}" class="preview-component" style="
                    position: relative;
                    left: {x}px;
                    top: {y}px;
                    width: {width}px;
                    height: {height}px;
                    margin: 5px;
                ">
                    <input type="text" placeholder="{comp.get('placeholder', '请输入...')}" style="
                        width: 100%;
                        height: 100%;
                        padding: 8px;
                        border: 1px solid #ccc;
                        border-radius: 4px;
                    " />
                </div>
                """)
            else:
                html_parts.append(f"""
                <div id="{comp_id}" class="preview-component" style="
                    position: relative;
                    left: {x}px;
                    top: {y}px;
                    padding: 10px;
                    margin: 5px;
                    border: 1px dashed #ccc;
                    border-radius: 4px;
                ">
                    <strong>{comp_name}</strong>: {comp_text}
                </div>
                """)

        html_parts.append("""
            </div>
            <div class="preview-actions" style="margin-top: 20px;">
                <button onclick="confirmPreview()" style="padding: 10px 20px; background: #4CAF50; color: white; border: none; border-radius: 4px; cursor: pointer; margin-right: 10px;">应用变更</button>
                <button onclick="rejectPreview()" style="padding: 10px 20px; background: #f44336; color: white; border: none; border-radius: 4px; cursor: pointer;">取消</button>
            </div>
        </div>
        """)

        return "\n".join(html_parts)


# 全局单例
_preview_instance: Optional[UIRealtimePreview] = None


def get_preview() -> UIRealtimePreview:
    """获取预览管理器单例"""
    global _preview_instance
    if _preview_instance is None:
        _preview_instance = UIRealtimePreview()
    return _preview_instance