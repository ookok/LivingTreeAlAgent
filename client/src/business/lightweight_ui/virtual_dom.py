"""
虚拟DOM实现

高效的虚拟DOM实现，支持批量更新、差异对比、
异步更新和智能缓存
from __future__ import annotations
"""

from typing import Dict, List, Optional, Any, Callable, Set
from dataclasses import dataclass, field
from datetime import datetime
import threading
import logging

from .models import ComponentType, UIState

logger = logging.getLogger(__name__)


@dataclass
class VirtualNode:
    """
    虚拟DOM节点
    
    表示一个UI组件的虚拟表示，包含类型、属性、子节点等信息
    """
    node_type: str
    key: Optional[str] = None
    props: Dict[str, Any] = field(default_factory=dict)
    children: List[VirtualNode] = field(default_factory=list)
    state: Optional[UIState] = None
    ref: Optional[Any] = None
    
    def __hash__(self):
        return hash((self.node_type, self.key))
    
    def __eq__(self, other):
        if not isinstance(other, VirtualNode):
            return False
        return self.node_type == other.node_type and self.key == other.key
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "type": self.node_type,
            "key": self.key,
            "props": self.props,
            "children": [c.to_dict() if isinstance(c, VirtualNode) else c for c in self.children],
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> VirtualNode:
        """从字典创建"""
        children = []
        for child in data.get("children", []):
            if isinstance(child, dict):
                children.append(cls.from_dict(child))
            else:
                children.append(child)
        
        return cls(
            node_type=data.get("type", "div"),
            key=data.get("key"),
            props=data.get("props", {}),
            children=children,
        )
    
    def clone(self) -> VirtualNode:
        """克隆节点"""
        return VirtualNode(
            node_type=self.node_type,
            key=self.key,
            props=self.props.copy(),
            children=[c.clone() if isinstance(c, VirtualNode) else c for c in self.children],
            state=self.state.clone() if self.state else None,
            ref=self.ref,
        )


class DiffResult:
    """Diff结果"""
    def __init__(self):
        self.additions: List[VirtualNode] = []
        self.deletions: List[VirtualNode] = []
        self.updates: List[tuple[VirtualNode, VirtualNode]] = []
        self.moves: List[tuple[VirtualNode, VirtualNode, int]] = []  # (old, new, new_index)
    
    def has_changes(self) -> bool:
        """是否有变化"""
        return bool(self.additions or self.deletions or self.updates or self.moves)


class DOMPatcher:
    """
    DOM差异对比与补丁应用
    
    实现了高效的虚拟DOM diff算法，用于最小化实际DOM操作
    """
    
    def __init__(self):
        self._keyed_nodes: Dict[str, VirtualNode] = {}
        self._max_key_length = 1000
    
    def diff(self, old_tree: VirtualNode, new_tree: VirtualNode) -> DiffResult:
        """
        对比两棵虚拟DOM树
        
        Args:
            old_tree: 旧树
            new_tree: 新树
            
        Returns:
            DiffResult: 差异结果
        """
        result = DiffResult()
        self._diff_nodes(old_tree, new_tree, result, 0)
        return result
    
    def _diff_nodes(
        self,
        old_node: Optional[VirtualNode],
        new_node: Optional[VirtualNode],
        result: DiffResult,
        depth: int
    ):
        """递归对比节点"""
        # 处理新旧节点存在情况
        if old_node is None and new_node is None:
            return
        
        if old_node is None:
            # 新增节点
            result.additions.append(new_node)
            return
        
        if new_node is None:
            # 删除节点
            result.deletions.append(old_node)
            return
        
        # 类型变化，重新创建
        if old_node.node_type != new_node.node_type:
            result.deletions.append(old_node)
            result.additions.append(new_node)
            return
        
        # Key不同，视为替换
        if old_node.key is not None and new_node.key is not None:
            if old_node.key != new_node.key:
                result.deletions.append(old_node)
                result.additions.append(new_node)
                return
        
        # 对比属性
        old_props = old_node.props or {}
        new_props = new_node.props or {}
        
        if old_props != new_props:
            result.updates.append((old_node, new_node))
        
        # 递归对比子节点
        self._diff_children(old_node.children, new_node.children, result, depth + 1)
    
    def _diff_children(
        self,
        old_children: List,
        new_children: List,
        result: DiffResult,
        depth: int
    ):
        """对比子节点列表"""
        old_keyed = {c.key: c for c in old_children if isinstance(c, VirtualNode) and c.key}
        new_keyed = {c.key: c for c in new_children if isinstance(c, VirtualNode) and c.key}
        
        old_unkeyed = [c for c in old_children if not (isinstance(c, VirtualNode) and c.key)]
        new_unkeyed = [c for c in new_children if not (isinstance(c, VirtualNode) and c.key)]
        
        # 处理有key的节点
        for key in set(old_keyed.keys()) | set(new_keyed.keys()):
            old_node = old_keyed.get(key)
            new_node = new_keyed.get(key)
            
            if old_node and new_node:
                self._diff_nodes(old_node, new_node, result, depth)
            elif old_node:
                result.deletions.append(old_node)
            else:
                result.additions.append(new_node)
        
        # 处理无key的节点（使用索引）
        max_len = max(len(old_unkeyed), len(new_unkeyed))
        for i in range(max_len):
            old_child = old_unkeyed[i] if i < len(old_unkeyed) else None
            new_child = new_unkeyed[i] if i < len(new_unkeyed) else None
            
            if isinstance(old_child, VirtualNode) and isinstance(new_child, VirtualNode):
                self._diff_nodes(old_child, new_child, result, depth)
            else:
                self._diff_nodes(old_child, new_child, result, depth)
    
    def patch(self, diff: DiffResult, callback: Optional[Callable] = None):
        """
        应用补丁
        
        Args:
            diff: 差异结果
            callback: 应用补丁后的回调函数
        """
        # 按顺序应用补丁
        for deletion in diff.deletions:
            if callback:
                callback({"type": "delete", "node": deletion})
        
        for addition in diff.additions:
            if callback:
                callback({"type": "add", "node": addition})
        
        for old_node, new_node in diff.updates:
            if callback:
                callback({"type": "update", "old": old_node, "new": new_node})
        
        for old_node, new_node, index in diff.moves:
            if callback:
                callback({"type": "move", "old": old_node, "new": new_node, "index": index})


class VirtualDOM:
    """
    虚拟DOM管理器
    
    管理组件的虚拟DOM表示，支持批量更新、异步更新和缓存
    """
    
    def __init__(self, max_cache_size: int = 1000):
        self._trees: Dict[str, VirtualNode] = {}  # component_id -> virtual tree
        self._update_queue: Set[str] = set()
        self._lock = threading.Lock()
        self._max_cache_size = max_cache_size
        self._cache: Dict[str, VirtualNode] = {}
        self._patcher = DOMPatcher()
        self._update_callbacks: Dict[str, Callable] = {}
        self._running = False
        self._update_interval = 16  # ms，约60fps
    
    def start(self):
        """启动虚拟DOM"""
        self._running = True
    
    def stop(self):
        """停止虚拟DOM"""
        self._running = False
        with self._lock:
            self._update_queue.clear()
    
    def register_component(self, component_id: str, tree: VirtualNode, callback: Optional[Callable] = None):
        """
        注册组件的虚拟DOM
        
        Args:
            component_id: 组件ID
            tree: 虚拟树
            callback: 更新回调
        """
        with self._lock:
            old_tree = self._trees.get(component_id)
            self._trees[component_id] = tree
            self._update_callbacks[component_id] = callback
            
            # 缓存旧树用于diff
            if old_tree:
                cache_key = f"{component_id}_{id(old_tree)}"
                self._cache[cache_key] = old_tree
                self._cleanup_cache()
    
    def update_component(self, component_id: str, tree: VirtualNode):
        """
        更新组件的虚拟DOM
        
        Args:
            component_id: 组件ID
            tree: 新的虚拟树
        """
        with self._lock:
            self._trees[component_id] = tree
            self._update_queue.add(component_id)
    
    def schedule_update(self, component_id: str):
        """
        调度更新
        
        Args:
            component_id: 组件ID
        """
        with self._lock:
            self._update_queue.add(component_id)
    
    def flush_updates(self) -> Dict[str, DiffResult]:
        """
        刷新所有待更新
        
        Returns:
            Dict[str, DiffResult]: 组件ID -> 差异结果
        """
        results = {}
        
        with self._lock:
            queue = self._update_queue.copy()
            self._update_queue.clear()
        
        for component_id in queue:
            old_tree = self._trees.get(component_id)
            
            # 获取新树（可能通过回调重新渲染）
            callback = self._update_callbacks.get(component_id)
            if callback:
                new_tree = callback()
            else:
                continue
            
            if old_tree is None or new_tree is None:
                continue
            
            # Diff
            diff = self._diff_trees(old_tree, new_tree)
            if diff.has_changes():
                results[component_id] = diff
                self._trees[component_id] = new_tree
                
                # 应用补丁
                self._patcher.patch(diff)
        
        return results
    
    def _diff_trees(self, old_tree: VirtualNode, new_tree: VirtualNode) -> DiffResult:
        """对比两棵树"""
        return self._patcher.diff(old_tree, new_tree)
    
    def _cleanup_cache(self):
        """清理过大的缓存"""
        if len(self._cache) > self._max_cache_size:
            # 删除一半最旧的缓存
            items = sorted(self._cache.items(), key=lambda x: x[1].state.created_at if hasattr(x[1], 'state') else datetime.now())
            for key, _ in items[:len(items) // 2]:
                del self._cache[key]
    
    def get_tree(self, component_id: str) -> Optional[VirtualNode]:
        """获取组件的虚拟树"""
        return self._trees.get(component_id)
    
    def get_update_queue_size(self) -> int:
        """获取更新队列大小"""
        with self._lock:
            return len(self._update_queue)
    
    def render_to_string(self, component_id: str) -> str:
        """
        将虚拟DOM渲染为HTML字符串
        
        Args:
            component_id: 组件ID
            
        Returns:
            HTML字符串
        """
        tree = self._trees.get(component_id)
        if tree is None:
            return ""
        return self._render_node(tree)
    
    def _render_node(self, node: VirtualNode) -> str:
        """渲染单个节点为HTML"""
        if not isinstance(node, VirtualNode):
            # 文本节点
            return str(node)
        
        # 构建属性字符串
        attrs = []
        for key, value in (node.props or {}).items():
            if value is not None and value is not False and value is not True:
                attrs.append(f'{key}="{value}"')
            elif value is True:
                attrs.append(key)
        
        attrs_str = " " + " ".join(attrs) if attrs else ""
        
        # 渲染子节点
        children_str = ""
        for child in node.children:
            children_str += self._render_node(child)
        
        # 自闭合标签
        void_elements = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
        
        if node.node_type in void_elements:
            return f"<{node.node_type}{attrs_str}>"
        else:
            return f"<{node.node_type}{attrs_str}>{children_str}</{node.node_type}>"


# 创建默认实例
_default_vdom = None


def get_virtual_dom() -> VirtualDOM:
    """获取默认虚拟DOM实例"""
    global _default_vdom
    if _default_vdom is None:
        _default_vdom = VirtualDOM()
    return _default_vdom


__all__ = [
    "VirtualNode",
    "DiffResult",
    "DOMPatcher",
    "VirtualDOM",
    "get_virtual_dom",
]
