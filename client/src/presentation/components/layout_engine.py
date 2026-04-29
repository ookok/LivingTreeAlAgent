"""
流式布局引擎 - 智能布局

负责智能布局管理，支持：
1. 动态布局计算
2. 响应式布局
3. 流式内容渲染
4. 自适应布局调整
"""

from typing import List, Dict, Any, Optional, Tuple
from loguru import logger

from PyQt6.QtWidgets import (
    QWidget, QLayout, QVBoxLayout, QHBoxLayout, 
    QGridLayout, QFormLayout, QScrollArea,
    QSizePolicy, QSpacerItem
)
from PyQt6.QtCore import Qt, QSize, QRect

from .ui_descriptor import UIComponent, LayoutType, ControlType


class LayoutEngine:
    """
    流式布局引擎
    
    核心功能：
    1. 根据UI组件描述智能计算布局
    2. 支持响应式布局调整
    3. 流式内容渲染支持
    4. 动态布局优化
    """
    
    def __init__(self):
        self._logger = logger.bind(component="LayoutEngine")
        self._layout_cache: Dict[str, QLayout] = {}
        self._parent_widgets: Dict[str, QWidget] = {}
    
    def layout_component(self, component: UIComponent, parent: QWidget) -> QWidget:
        """
        布局UI组件并返回顶层控件
        
        Args:
            component: UI组件描述
            parent: 父控件
            
        Returns:
            布局后的顶层控件
        """
        widget = self._create_widget_for_component(component, parent)
        
        if widget:
            self._apply_layout(widget, component)
            self._parent_widgets[component.id] = widget
        
        return widget
    
    def _create_widget_for_component(self, component: UIComponent, parent: QWidget) -> Optional[QWidget]:
        """为组件创建基础控件"""
        from .control_factory import ControlFactory
        
        factory = ControlFactory()
        return factory.create_widget(component, parent)
    
    def _apply_layout(self, widget: QWidget, component: UIComponent):
        """应用布局到控件"""
        layout = self._create_layout(component.layout)
        widget.setLayout(layout)
        
        # 设置布局属性
        self._configure_layout(layout, component.layout_config)
        
        # 添加子控件
        self._add_children_to_layout(layout, component, widget)
        
        # 缓存布局
        self._layout_cache[component.id] = layout
    
    def _create_layout(self, layout_type: LayoutType) -> QLayout:
        """根据布局类型创建布局管理器"""
        if layout_type == LayoutType.HORIZONTAL:
            return QHBoxLayout()
        elif layout_type == LayoutType.VERTICAL:
            return QVBoxLayout()
        elif layout_type == LayoutType.GRID:
            return QGridLayout()
        elif layout_type == LayoutType.FLEX:
            return QHBoxLayout()  # 使用HBox模拟Flex
        else:
            return QVBoxLayout()
    
    def _configure_layout(self, layout: QLayout, config: Dict[str, Any]):
        """配置布局属性"""
        # 设置间距
        spacing = config.get("spacing", 8)
        layout.setSpacing(spacing)
        
        # 设置边距
        margins = config.get("margins", [0, 0, 0, 0])
        if len(margins) == 4:
            layout.setContentsMargins(*margins)
        
        # 设置对齐方式
        alignment = config.get("alignment")
        if alignment:
            # 转换对齐方式
            align_map = {
                "top": Qt.AlignmentFlag.AlignTop,
                "bottom": Qt.AlignmentFlag.AlignBottom,
                "left": Qt.AlignmentFlag.AlignLeft,
                "right": Qt.AlignmentFlag.AlignRight,
                "center": Qt.AlignmentFlag.AlignCenter,
                "top_left": Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                "top_right": Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
                "bottom_left": Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft,
                "bottom_right": Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight,
            }
            layout.setAlignment(align_map.get(alignment, Qt.AlignmentFlag.AlignTop))
    
    def _add_children_to_layout(self, layout: QLayout, component: UIComponent, parent: QWidget):
        """将子组件添加到布局"""
        for child in component.children:
            child_widget = self.layout_component(child, parent)
            if child_widget:
                self._add_widget_to_layout(layout, child_widget, child)
    
    def _add_widget_to_layout(self, layout: QLayout, widget: QWidget, component: UIComponent):
        """将控件添加到布局"""
        # 获取布局配置
        config = component.layout_config
        
        # 设置大小策略
        size_policy = QSizePolicy(
            QSizePolicy.Policy.Preferred if config.get("expand", False) else QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Preferred if config.get("expand", False) else QSizePolicy.Policy.Minimum
        )
        widget.setSizePolicy(size_policy)
        
        # 设置拉伸因子
        stretch = config.get("stretch", 0)
        
        # 根据布局类型添加
        if isinstance(layout, QHBoxLayout) or isinstance(layout, QVBoxLayout):
            layout.addWidget(widget, stretch)
        elif isinstance(layout, QGridLayout):
            row = config.get("row", 0)
            col = config.get("col", 0)
            row_span = config.get("row_span", 1)
            col_span = config.get("col_span", 1)
            layout.addWidget(widget, row, col, row_span, col_span)
        else:
            layout.addWidget(widget)
    
    def layout_sequential(self, components: List[UIComponent], parent: QWidget) -> QWidget:
        """
        顺序布局多个组件
        
        Args:
            components: 组件列表
            parent: 父控件
            
        Returns:
            包含所有组件的容器控件
        """
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        for component in components:
            widget = self.layout_component(component, container)
            if widget:
                layout.addWidget(widget)
        
        return container
    
    def layout_grid(self, components: List[UIComponent], columns: int, parent: QWidget) -> QWidget:
        """
        网格布局组件
        
        Args:
            components: 组件列表
            columns: 列数
            parent: 父控件
            
        Returns:
            包含所有组件的网格容器
        """
        container = QWidget(parent)
        layout = QGridLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        for i, component in enumerate(components):
            row = i // columns
            col = i % columns
            widget = self.layout_component(component, container)
            if widget:
                layout.addWidget(widget, row, col)
        
        return container
    
    def layout_flow(self, components: List[UIComponent], parent: QWidget) -> QWidget:
        """
        流式布局组件（自动换行）
        
        Args:
            components: 组件列表
            parent: 父控件
            
        Returns:
            包含所有组件的流式容器
        """
        container = QWidget(parent)
        
        # 创建滚动区域支持大内容
        scroll_area = QScrollArea(parent)
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(container)
        
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # 当前行布局
        current_row = None
        current_row_width = 0
        row_max_height = 0
        
        for component in components:
            widget = self.layout_component(component, container)
            if not widget:
                continue
            
            # 获取控件首选大小
            size_hint = widget.sizeHint()
            widget_width = size_hint.width()
            widget_height = size_hint.height()
            
            # 如果是新行或当前行放不下，创建新行
            if current_row is None or current_row_width + widget_width > container.width() - 32:
                if current_row is not None:
                    # 完成当前行
                    layout.addLayout(current_row)
                    
                    # 设置行高
                    for i in range(current_row.count()):
                        item = current_row.itemAt(i)
                        if item:
                            widget_item = item.widget()
                            if widget_item:
                                widget_item.setFixedHeight(row_max_height)
                
                current_row = QHBoxLayout()
                current_row.setSpacing(8)
                current_row_width = 0
                row_max_height = 0
            
            current_row.addWidget(widget)
            current_row_width += widget_width + 8
            row_max_height = max(row_max_height, widget_height)
        
        # 添加最后一行
        if current_row is not None:
            layout.addLayout(current_row)
        
        return scroll_area
    
    def create_scrollable_container(self, content_widget: QWidget, parent: QWidget = None) -> QScrollArea:
        """创建可滚动容器"""
        scroll_area = QScrollArea(parent)
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(content_widget)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
        """)
        return scroll_area
    
    def calculate_optimal_size(self, component: UIComponent) -> QSize:
        """计算组件的最佳大小"""
        base_width = 200
        base_height = 40
        
        # 根据控件类型调整
        if component.type in [ControlType.TEXTAREA, ControlType.LIST]:
            base_height = 120
        elif component.type == ControlType.TABLE:
            row_count = len(component.data.get("rows", []))
            base_height = max(100, row_count * 30 + 40)
        elif component.type == ControlType.CARD:
            base_height = 150
        elif component.type == ControlType.FORM:
            field_count = len(component.form_fields)
            base_height = field_count * 60 + 80
        
        return QSize(base_width, base_height)
    
    def update_layout(self, component_id: str, new_config: Dict[str, Any]):
        """更新组件布局配置"""
        layout = self._layout_cache.get(component_id)
        if layout:
            self._configure_layout(layout, new_config)
            
            # 更新父控件
            widget = self._parent_widgets.get(component_id)
            if widget:
                widget.update()
                widget.adjustSize()
    
    def remove_component(self, component_id: str):
        """移除组件布局"""
        layout = self._layout_cache.get(component_id)
        if layout:
            # 清除布局中的所有控件
            while layout.count() > 0:
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            
            del self._layout_cache[component_id]
        
        if component_id in self._parent_widgets:
            del self._parent_widgets[component_id]
    
    def clear_layout(self, parent_widget: QWidget):
        """清除父控件的布局"""
        layout = parent_widget.layout()
        if layout:
            while layout.count() > 0:
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
    
    def optimize_layout(self, parent_widget: QWidget, available_size: QSize):
        """优化布局以适应可用空间"""
        layout = parent_widget.layout()
        if not layout:
            return
        
        # 根据可用空间调整布局
        if available_size.width() < 480:
            # 窄屏模式：垂直堆叠
            self._convert_to_vertical(layout)
        elif available_size.width() < 768:
            # 中等屏幕：两列布局
            self._convert_to_columns(layout, 2)
        else:
            # 宽屏模式：保持原有布局
            pass
    
    def _convert_to_vertical(self, layout: QLayout):
        """转换为垂直布局"""
        if isinstance(layout, QHBoxLayout):
            # 创建新的垂直布局
            parent = layout.parentWidget()
            if parent:
                new_layout = QVBoxLayout(parent)
                
                # 移动所有控件到新布局
                while layout.count() > 0:
                    item = layout.takeAt(0)
                    if item.widget():
                        new_layout.addWidget(item.widget())
                    elif item.layout():
                        new_layout.addLayout(item.layout())
                
                parent.setLayout(new_layout)
    
    def _convert_to_columns(self, layout: QLayout, columns: int):
        """转换为多列布局"""
        parent = layout.parentWidget()
        if not parent:
            return
        
        # 收集所有控件
        widgets = []
        while layout.count() > 0:
            item = layout.takeAt(0)
            if item.widget():
                widgets.append(item.widget())
        
        # 创建网格布局
        grid_layout = QGridLayout(parent)
        grid_layout.setSpacing(8)
        
        for i, widget in enumerate(widgets):
            row = i // columns
            col = i % columns
            grid_layout.addWidget(widget, row, col)
        
        parent.setLayout(grid_layout)
    
    def animate_layout_change(self, widget: QWidget, duration: int = 300):
        """为布局变化添加动画效果"""
        from PyQt6.QtCore import QPropertyAnimation, QEasingCurve
        
        animation = QPropertyAnimation(widget, b"geometry")
        animation.setDuration(duration)
        animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        
        start_geometry = widget.geometry()
        end_geometry = QRect(
            start_geometry.x(),
            start_geometry.y(),
            start_geometry.width(),
            start_geometry.height()
        )
        
        animation.setStartValue(start_geometry)
        animation.setEndValue(end_geometry)
        animation.start()