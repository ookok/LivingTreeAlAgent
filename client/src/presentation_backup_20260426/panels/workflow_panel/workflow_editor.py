"""工作流编辑器面板"""

from typing import Any
from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QRectF, QLineF, QSizeF, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QListWidget, QListWidgetItem, QLabel, QPushButton,
    QTextEdit, QLineEdit, QComboBox, QSpinBox,
    QGroupBox, QScrollArea, QSizePolicy, QGraphicsView,
    QGraphicsScene, QGraphicsProxyWidget, QGraphicsItem,
    QMenuBar, QMenu, QToolBar, QStatusBar, QDialog,
    QDialogButtonBox, QFormLayout, QTabWidget, QWidget,
    QMenu, QAction, QGraphicsLineItem, QGraphicsPathItem,
    QGraphicsEllipseItem, QGraphicsTextItem, QCheckBox,
    QProgressBar, QPlainTextEdit
)
from PyQt6.QtGui import (
    QAction, QColor, QPen, QBrush, QPainter, QPainterPath,
    QFont, QMouseEvent, QWheelEvent, QContextMenuEvent,
    QKeyEvent, QCursor, QTransform, QPixmap
)

import sys
import os
import uuid

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.living_tree_ai.workflow import (
    Workflow, WorkflowNodeModel, NodeConnection,
    NodeType, NodeStatus, WorkflowStatus,
    NodeRegistry, get_registry, register_builtin_nodes,
    TaskChainConverter, WorkflowExecutor, WorkflowValidator,
    register_ai_templates, WorkflowGenerator, get_workflow_generator,
    NodeDiscoverer, get_node_discoverer
)


class ConnectionGraphicsItem(QGraphicsPathItem):
    """连接图形项"""
    
    def __init__(self, connection: NodeConnection, parent=None):
        super().__init__(parent)
        self.connection = connection
        self.setPen(QPen(QColor("#4CAF50"), 2))
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.update_path()
    
    def update_path(self):
        """更新连接路径"""
        # 这里需要根据实际的节点位置计算路径
        # 暂时使用默认路径
        path = QPainterPath()
        path.moveTo(100, 200)
        path.lineTo(300, 200)
        self.setPath(path)


class PortGraphicsItem(QGraphicsEllipseItem):
    """端口图形项"""
    
    def __init__(self, port_id, name, direction, parent=None):
        super().__init__(0, 0, 10, 10, parent)
        self.port_id = port_id
        self.name = name
        self.direction = direction  # "input" or "output"
        self.setBrush(QBrush(QColor("#4CAF50")))
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)


class NodeGraphicsItem(QGraphicsProxyWidget):
    """节点图形项"""
    
    def __init__(self, node_model: WorkflowNodeModel, parent=None):
        super().__init__(parent)
        self.node_model = node_model
        self.node_widget = NodeWidget(node_model)
        self.setWidget(self.node_widget)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
                      QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.ports = []
        self._create_ports()
    
    def get_node_id(self):
        return self.node_model.node_id
    
    def _create_ports(self):
        """创建端口"""
        # 输入端口
        for i, inp in enumerate(self.node_model.inputs):
            port = PortGraphicsItem(inp.port_id, inp.name, "input", self)
            port.setPos(-15, 30 + i * 20)
            self.ports.append(port)
        
        # 输出端口
        for i, out in enumerate(self.node_model.outputs):
            port = PortGraphicsItem(out.port_id, out.name, "output", self)
            port.setPos(self.boundingRect().width() + 5, 30 + i * 20)
            self.ports.append(port)
    
    def itemChange(self, change, value):
        """项目变化"""
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            # 触发节点移动信号
            if hasattr(self.parent(), 'node_moved'):
                self.parent().node_moved.emit(self.node_model.node_id, value)
        return super().itemChange(change, value)


class NodeWidget(QWidget):
    """节点控件"""
    
    def __init__(self, node_model: WorkflowNodeModel):
        super().__init__()
        self.node_model = node_model
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 节点标题
        title_layout = QHBoxLayout()
        title_label = QLabel(f"{self._get_icon()} {self.node_model.name}")
        title_label.setStyleSheet("font-weight: bold; color: white;")
        title_layout.addWidget(title_label)
        self.setStyleSheet("background-color: #2b2b2b; border-radius: 5px;")
        
        # 节点类型标签
        type_label = QLabel(self.node_model.node_type.value if hasattr(self.node_model.node_type, 'value') else str(self.node_model.node_type))
        type_label.setStyleSheet("color: #888; font-size: 10px;")
        title_layout.addWidget(type_label)
        title_layout.addStretch()
        
        layout.addLayout(title_layout)
        
        # 输入端口
        if self.node_model.inputs:
            input_group = QGroupBox("输入")
            input_layout = QVBoxLayout()
            for inp in self.node_model.inputs:
                input_layout.addWidget(QLabel(f"• {inp.name}"))
            input_group.setLayout(input_layout)
            layout.addWidget(input_group)
        
        # 输出端口
        if self.node_model.outputs:
            output_group = QGroupBox("输出")
            output_layout = QVBoxLayout()
            for out in self.node_model.outputs:
                output_layout.addWidget(QLabel(f"• {out.name}"))
            output_group.setLayout(output_layout)
            layout.addWidget(output_group)
        
        # 状态指示
        self.status_label = QLabel(f"状态: {self.node_model.status.value if hasattr(self.node_model.status, 'value') else 'idle'}")
        self.status_label.setStyleSheet("color: #4CAF50;")
        layout.addWidget(self.status_label)
    
    def _get_icon(self) -> str:
        """获取节点图标"""
        icon_map = {
            "start": "▶",
            "end": "■",
            "llm": "🤖",
            "tool": "🔧",
            "knowledge": "📚",
            "condition": "🔀",
            "loop": "🔄",
            "template": "📝",
            "transformer": "🔄",
            "browser_use": "🌐"
        }
        node_type = self.node_model.node_type.value if hasattr(self.node_model.node_type, 'value') else str(self.node_model.node_type)
        return icon_map.get(node_type, "●")
    
    def update_status(self, status: NodeStatus):
        """更新状态"""
        self.node_model.status = status
        status_text = status.value if hasattr(status, 'value') else str(status)
        self.status_label.setText(f"状态: {status_text}")
        
        color_map = {
            "idle": "#888",
            "running": "#FFC107",
            "completed": "#4CAF50",
            "failed": "#F44336",
            "waiting": "#2196F3"
        }
        self.status_label.setStyleSheet(f"color: {color_map.get(status_text, '#888')};")
        
        # 更新节点边框颜色
        border_color = color_map.get(status_text, "#444")
        self.setStyleSheet(f"background-color: #2b2b2b; border: 2px solid {border_color}; border-radius: 5px;")


class WorkflowCanvas(QGraphicsView):
    """工作流画布"""
    
    node_selected = pyqtSignal(str)
    node_moved = pyqtSignal(str, QPointF)
    node_connected = pyqtSignal(str, str, str, str)  # source_id, source_port, target_id, target_port
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(True)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._node_items = {}
        self._connection_items = {}
        self._drag_start_port = None
        self._temp_connection = None
        self._show_grid = True
        self._grid_size = 20
        self._show_snapping = True
        self._selected_node_id = None
    
    def add_node(self, node_model: WorkflowNodeModel) -> NodeGraphicsItem:
        """添加节点到画布"""
        item = NodeGraphicsItem(node_model)
        self.scene.addItem(item)
        item.setPos(QPointF(node_model.position.x, node_model.position.y))
        self._node_items[node_model.node_id] = item
        return item
    
    def remove_node(self, node_id: str):
        """从画布移除节点"""
        if node_id in self._node_items:
            item = self._node_items[node_id]
            self.scene.removeItem(item)
            del self._node_items[node_id]
            
            # 移除相关连接
            connections_to_remove = []
            for conn_id, conn_item in self._connection_items.items():
                conn = conn_item.connection
                if conn.source_node_id == node_id or conn.target_node_id == node_id:
                    connections_to_remove.append(conn_id)
            
            for conn_id in connections_to_remove:
                self.remove_connection(conn_id)
    
    def add_connection(self, connection: NodeConnection) -> ConnectionGraphicsItem:
        """添加连接到画布"""
        item = ConnectionGraphicsItem(connection)
        self.scene.addItem(item)
        self._connection_items[connection.connection_id] = item
        return item
    
    def remove_connection(self, connection_id: str):
        """从画布移除连接"""
        if connection_id in self._connection_items:
            item = self._connection_items[connection_id]
            self.scene.removeItem(item)
            del self._connection_items[connection_id]
    
    def get_node_item(self, node_id: str) -> NodeGraphicsItem:
        """获取节点图形项"""
        return self._node_items.get(node_id)
    
    def clear(self):
        """清空画布"""
        self.scene.clear()
        self._node_items.clear()
        self._connection_items.clear()
    
    def set_show_grid(self, show: bool):
        """设置是否显示网格"""
        self._show_grid = show
        self.update()
    
    def set_grid_size(self, size: int):
        """设置网格大小"""
        self._grid_size = size
        self.update()
    
    def set_show_snapping(self, show: bool):
        """设置是否启用对齐"""
        self._show_snapping = show
    
    def mousePressEvent(self, event):
        """鼠标按下事件"""
        item = self.itemAt(event.pos())
        if isinstance(item, PortGraphicsItem):
            # 开始拖拽连接
            self._drag_start_port = item
            self._temp_connection = QGraphicsLineItem()
            self._temp_connection.setPen(QPen(QColor("#4CAF50"), 2, Qt.PenStyle.DashLine))
            self.scene.addItem(self._temp_connection)
        elif isinstance(item, NodeGraphicsItem):
            # 选中节点
            self._selected_node_id = item.get_node_id()
            self.node_selected.emit(self._selected_node_id)
        else:
            # 清空选择
            self._selected_node_id = None
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        if self._temp_connection and self._drag_start_port:
            # 更新临时连接
            start_pos = self._drag_start_port.mapToScene(self._drag_start_port.boundingRect().center())
            end_pos = self.mapToScene(event.pos())
            self._temp_connection.setLine(QLineF(start_pos, end_pos))
        elif self._show_snapping:
            # 启用对齐功能
            pass
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        if self._temp_connection and self._drag_start_port:
            # 检查是否连接到目标端口
            item = self.itemAt(event.pos())
            if isinstance(item, PortGraphicsItem) and item != self._drag_start_port:
                # 确保源和目标端口方向相反
                if self._drag_start_port.direction != item.direction:
                    # 创建连接
                    source_node = self._drag_start_port.parentItem()
                    target_node = item.parentItem()
                    
                    if isinstance(source_node, NodeGraphicsItem) and isinstance(target_node, NodeGraphicsItem):
                        connection = NodeConnection(
                            connection_id=str(uuid.uuid4())[:8],
                            source_node_id=source_node.get_node_id(),
                            source_port=self._drag_start_port.port_id,
                            target_node_id=target_node.get_node_id(),
                            target_port=item.port_id
                        )
                        self.add_connection(connection)
                        self.node_connected.emit(
                            source_node.get_node_id(),
                            self._drag_start_port.port_id,
                            target_node.get_node_id(),
                            item.port_id
                        )
            
            # 移除临时连接
            self.scene.removeItem(self._temp_connection)
            self._temp_connection = None
            self._drag_start_port = None
        super().mouseReleaseEvent(event)
    
    def wheelEvent(self, event):
        """滚轮事件 - 缩放画布"""
        zoom_factor = 1.1
        if event.angleDelta().y() < 0:
            zoom_factor = 1 / zoom_factor
        
        self.scale(zoom_factor, zoom_factor)
        event.accept()
    
    def drawBackground(self, painter: QPainter, rect: QRectF):
        """绘制背景"""
        super().drawBackground(painter, rect)
        
        # 绘制网格
        if self._show_grid:
            painter.setPen(QPen(QColor("#444"), 0.5))
            
            # 绘制垂直线
            left = int(rect.left()) - (int(rect.left()) % self._grid_size)
            right = int(rect.right())
            for x in range(left, right, self._grid_size):
                painter.drawLine(x, int(rect.top()), x, int(rect.bottom()))
            
            # 绘制水平线
            top = int(rect.top()) - (int(rect.top()) % self._grid_size)
            bottom = int(rect.bottom())
            for y in range(top, bottom, self._grid_size):
                painter.drawLine(int(rect.left()), y, int(rect.right()), y)


class NodePalette(QListWidget):
    """节点调色板"""
    
    node_dragged = pyqtSignal(str, dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._load_nodes()
    
    def _setup_ui(self):
        self.setDragEnabled(True)
        self.setMaximumWidth(150)
        self.setAlternatingRowColors(True)
    
    def _load_nodes(self):
        """加载节点列表"""
        register_builtin_nodes()
        registry = get_registry()
        
        # 自动发现 OpenHarness 工具和技能节点
        from core.living_tree_ai.workflow import get_node_discoverer
        discoverer = get_node_discoverer()
        discoverer.register_discovered_nodes(registry)
        
        categories = registry.get_categories()
        
        for category in categories:
            category_item = QListWidgetItem(f"━━ {category} ━━")
            category_item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.addItem(category_item)
            
            nodes = registry.get_by_category(category)
            for node in nodes:
                item = QListWidgetItem(f"  {node.icon} {node.name}")
                item.setData(Qt.ItemDataRole.UserRole, {
                    "node_type": node.node_type,
                    "name": node.name,
                    "description": node.description
                })
                self.addItem(item)
    
    def mousePressEvent(self, event):
        """鼠标按下事件"""
        item = self.currentItem()
        if item and item.flags() != Qt.ItemFlag.NoItemFlags:
            data = item.data(Qt.ItemDataRole.UserRole)
            if data:
                self.node_dragged.emit(item.text().strip(), data)
        super().mousePressEvent(event)


class PropertyPanel(QWidget):
    """属性面板"""
    
    property_changed = pyqtSignal(str, dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_node = None
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 标题
        title = QLabel("节点属性")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)
        
        # 属性表单
        self.form_layout = QFormLayout()
        self.form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addLayout(self.form_layout)
        
        # 节点名称
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("节点名称")
        self.form_layout.addRow("名称:", self.name_edit)
        
        # 节点描述
        self.desc_edit = QTextEdit()
        self.desc_edit.setPlaceholderText("节点描述")
        self.desc_edit.setMaximumHeight(60)
        self.form_layout.addRow("描述:", self.desc_edit)
        
        # 配置标签页
        self.config_tabs = QTabWidget()
        self.form_layout.addRow("配置:", self.config_tabs)
        
        # 通用配置
        general_tab = QWidget()
        general_layout = QFormLayout(general_tab)
        self.config_tabs.addTab(general_tab, "通用")
        
        # 添加空状态提示
        empty_label = QLabel("选择节点以编辑属性")
        empty_label.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(empty_label)
        
        layout.addStretch()
    
    def set_node(self, node: WorkflowNodeModel):
        """设置当前节点"""
        self.current_node = node
        
        # 清空表单
        while self.config_tabs.count() > 1:
            self.config_tabs.removeTab(1)
        
        if node:
            # 设置基本信息
            self.name_edit.setText(node.name)
            self.desc_edit.setText(node.description)
            
            # 添加配置项
            config = node.config
            
            # 特殊处理 browser-use 节点
            if node.node_type == "browser_use" or (hasattr(node.node_type, 'value') and node.node_type.value == "browser_use"):
                # 创建 browser-use 配置标签页
                browser_tab = QWidget()
                browser_layout = QFormLayout(browser_tab)
                self.config_tabs.addTab(browser_tab, "浏览器自动化")
                
                # 任务类型选择
                task_type_combo = QComboBox()
                task_type_combo.addItems(["execute", "navigate", "extract_content", "fill_form", "search", "screenshot"])
                task_type = config.get("task_type", "execute")
                task_type_combo.setCurrentText(task_type)
                task_type_combo.currentTextChanged.connect(lambda t: self._on_config_changed("task_type", t))
                browser_layout.addRow("任务类型:", task_type_combo)
                
                # 结果变量名
                result_var_edit = QLineEdit(config.get("result_variable", "browser_result"))
                result_var_edit.textChanged.connect(lambda t: self._on_config_changed("result_variable", t))
                browser_layout.addRow("结果变量名:", result_var_edit)
                
                # 浏览器配置
                use_cloud_check = QCheckBox()
                use_cloud_check.setChecked(config.get("browser_config", {}).get("use_cloud", False))
                use_cloud_check.stateChanged.connect(lambda s: self._on_browser_config_changed("use_cloud", s == Qt.CheckState.Checked))
                browser_layout.addRow("使用云浏览器:", use_cloud_check)
                
                # 任务参数
                task_params = config.get("task_params", {})
                
                # 根据任务类型显示不同的参数
                if task_type == "execute":
                    task_edit = QTextEdit(task_params.get("task", ""))
                    task_edit.setMaximumHeight(80)
                    task_edit.textChanged.connect(lambda: self._on_task_param_changed("task", task_edit.toPlainText()))
                    browser_layout.addRow("任务描述:", task_edit)
                elif task_type == "navigate":
                    url_edit = QLineEdit(task_params.get("url", ""))
                    url_edit.textChanged.connect(lambda t: self._on_task_param_changed("url", t))
                    browser_layout.addRow("目标 URL:", url_edit)
                elif task_type == "extract_content":
                    url_edit = QLineEdit(task_params.get("url", ""))
                    url_edit.textChanged.connect(lambda t: self._on_task_param_changed("url", t))
                    browser_layout.addRow("目标 URL:", url_edit)
                    
                    selector_edit = QLineEdit(task_params.get("selector", ""))
                    selector_edit.textChanged.connect(lambda t: self._on_task_param_changed("selector", t))
                    browser_layout.addRow("CSS 选择器:", selector_edit)
                elif task_type == "fill_form":
                    url_edit = QLineEdit(task_params.get("url", ""))
                    url_edit.textChanged.connect(lambda t: self._on_task_param_changed("url", t))
                    browser_layout.addRow("目标 URL:", url_edit)
                    
                    form_data_edit = QTextEdit(str(task_params.get("form_data", {})))
                    form_data_edit.setMaximumHeight(80)
                    form_data_edit.textChanged.connect(lambda: self._on_task_param_changed("form_data", form_data_edit.toPlainText()))
                    browser_layout.addRow("表单数据:", form_data_edit)
                elif task_type == "search":
                    query_edit = QLineEdit(task_params.get("query", ""))
                    query_edit.textChanged.connect(lambda t: self._on_task_param_changed("query", t))
                    browser_layout.addRow("搜索查询:", query_edit)
                    
                    engine_edit = QLineEdit(task_params.get("engine", "google"))
                    engine_edit.textChanged.connect(lambda t: self._on_task_param_changed("engine", t))
                    browser_layout.addRow("搜索引擎:", engine_edit)
                elif task_type == "screenshot":
                    url_edit = QLineEdit(task_params.get("url", ""))
                    url_edit.textChanged.connect(lambda t: self._on_task_param_changed("url", t))
                    browser_layout.addRow("目标 URL:", url_edit)
                    
                    path_edit = QLineEdit(task_params.get("path", "screenshot.png"))
                    path_edit.textChanged.connect(lambda t: self._on_task_param_changed("path", t))
                    browser_layout.addRow("保存路径:", path_edit)
            else:
                # 通用配置
                for key, value in config.items():
                    if isinstance(value, str):
                        edit = QLineEdit(value)
                        edit.setPlaceholderText(key)
                        edit.textChanged.connect(lambda t, k=key: self._on_config_changed(k, t))
                        self.config_tabs.currentWidget().layout().addRow(f"{key}:", edit)
                    elif isinstance(value, int) or isinstance(value, float):
                        spin = QSpinBox()
                        spin.setValue(int(value))
                        spin.valueChanged.connect(lambda v, k=key: self._on_config_changed(k, v))
                        self.config_tabs.currentWidget().layout().addRow(f"{key}:", spin)
    
    def _on_config_changed(self, key: str, value):
        """配置项改变"""
        if self.current_node:
            self.current_node.config[key] = value
            self.property_changed.emit(self.current_node.node_id, self.current_node.config)
    
    def _on_browser_config_changed(self, key: str, value):
        """浏览器配置改变"""
        if self.current_node:
            if "browser_config" not in self.current_node.config:
                self.current_node.config["browser_config"] = {}
            self.current_node.config["browser_config"][key] = value
            self.property_changed.emit(self.current_node.node_id, self.current_node.config)
    
    def _on_task_param_changed(self, key: str, value):
        """任务参数改变"""
        if self.current_node:
            if "task_params" not in self.current_node.config:
                self.current_node.config["task_params"] = {}
            self.current_node.config["task_params"][key] = value
            self.property_changed.emit(self.current_node.node_id, self.current_node.config)


class ExecutionPanel(QWidget):
    """执行面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 标题
        title = QLabel("执行状态")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)
        
        # 执行进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # 执行状态标签
        self.status_label = QLabel("状态: 就绪")
        layout.addWidget(self.status_label)
        
        # 执行日志
        log_group = QGroupBox("执行日志")
        log_layout = QVBoxLayout()
        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setMaximumHeight(100)
        log_layout.addWidget(self.log_edit)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        layout.addStretch()
    
    def update_status(self, status: str, message: str):
        """更新执行状态"""
        self.status_label.setText(f"状态: {status}")
        self.log_edit.appendPlainText(f"[{status}] {message}")
    
    def update_progress(self, progress: int):
        """更新执行进度"""
        self.progress_bar.setValue(progress)
    
    def clear(self):
        """清空执行面板"""
        self.progress_bar.setValue(0)
        self.status_label.setText("状态: 就绪")
        self.log_edit.clear()


class WorkflowEditorPanel(QWidget):
    """工作流编辑器面板"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.workflow = None
        self._setup_ui()
        self._create_actions()
        self._connect_signals()
    
    def _setup_ui(self):
        """设置 UI"""
        main_layout = QVBoxLayout(self)
        
        # 创建菜单栏
        menubar = QMenuBar()
        main_layout.addWidget(menubar)
        
        # 文件菜单
        file_menu = menubar.addMenu("文件")
        file_menu.addAction(QAction("新建", self, triggered=self.new_workflow))
        file_menu.addAction(QAction("打开", self, triggered=self.open_workflow))
        file_menu.addAction(QAction("保存", self, triggered=self.save_workflow))
        file_menu.addSeparator()
        
        # 模板子菜单
        template_menu = file_menu.addMenu("模板")
        template_menu.addAction(QAction("保存为模板", self, triggered=self.save_as_template))
        template_menu.addAction(QAction("导入模板", self, triggered=self.import_template))
        template_menu.addAction(QAction("导出模板", self, triggered=self.export_template))
        template_menu.addAction(QAction("管理模板", self, triggered=self.manage_templates))
        
        file_menu.addSeparator()
        file_menu.addAction(QAction("退出", self))
        
        # 编辑菜单
        edit_menu = menubar.addMenu("编辑")
        edit_menu.addAction(QAction("撤销", self))
        edit_menu.addAction(QAction("重做", self))
        edit_menu.addSeparator()
        self.delete_action = QAction("删除节点", self, triggered=self.delete_selected_node)
        edit_menu.addAction(self.delete_action)
        
        # 视图菜单
        view_menu = menubar.addMenu("视图")
        self.grid_action = QAction("显示网格", self, checkable=True, checked=True, triggered=self.toggle_grid)
        view_menu.addAction(self.grid_action)
        self.snap_action = QAction("启用对齐", self, checkable=True, checked=True, triggered=self.toggle_snapping)
        view_menu.addAction(self.snap_action)
        view_menu.addSeparator()
        view_menu.addAction(QAction("放大", self, triggered=lambda: self.zoom(1.1)))
        view_menu.addAction(QAction("缩小", self, triggered=lambda: self.zoom(0.9)))
        view_menu.addAction(QAction("重置缩放", self, triggered=self.reset_zoom))
        
        # 帮助菜单
        help_menu = menubar.addMenu("帮助")
        help_menu.addAction(QAction("关于", self))
        
        # 创建工具栏
        toolbar = QToolBar()
        toolbar.addAction(QAction("▶ 运行", self, triggered=self.execute_workflow))
        toolbar.addAction(QAction("⏹ 停止", self))
        toolbar.addSeparator()
        toolbar.addAction(QAction("📋 模板", self, triggered=self.show_template_dialog))
        toolbar.addAction(QAction("🤖 自动生成", self, triggered=self.show_auto_generate_dialog))
        toolbar.addSeparator()
        toolbar.addAction(QAction("🔄 刷新", self))
        main_layout.addWidget(toolbar)
        
        # 创建主分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左侧：节点调色板
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(QLabel("<b>节点调色板</b>"))
        self.node_palette = NodePalette()
        left_layout.addWidget(self.node_palette)
        splitter.addWidget(left_panel)
        
        # 中间：工作流画布
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.addWidget(QLabel("<b>工作流画布</b>"))
        self.canvas = WorkflowCanvas()
        center_layout.addWidget(self.canvas)
        
        # 执行面板
        self.execution_panel = ExecutionPanel()
        center_layout.addWidget(self.execution_panel)
        
        splitter.addWidget(center_panel)
        
        # 右侧：属性面板
        self.property_panel = PropertyPanel()
        splitter.addWidget(self.property_panel)
        
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)
        splitter.setStretchFactor(2, 2)
        
        main_layout.addWidget(splitter)
        
        # 创建状态栏
        self.statusbar = QStatusBar()
        self.statusbar.showMessage("就绪")
        main_layout.addWidget(self.statusbar)
        
        # 创建新工作流
        self.new_workflow()
    
    def _create_actions(self):
        """创建动作"""
        pass
    
    def _connect_signals(self):
        """连接信号"""
        self.node_palette.node_dragged.connect(self._on_node_dragged)
        self.canvas.node_selected.connect(self._on_node_selected)
        self.canvas.node_connected.connect(self._on_node_connected)
        self.property_panel.property_changed.connect(self._on_property_changed)
    
    def _on_node_dragged(self, text: str, data: dict):
        """节点拖拽"""
        node_type = data["node_type"]
        node_name = data["name"]
        self.add_node_to_canvas(node_type, node_name)
    
    def _on_node_selected(self, node_id: str):
        """节点选中"""
        if self.workflow:
            node = self.workflow.get_node(node_id)
            if node:
                self.property_panel.set_node(node)
                self.statusbar.showMessage(f"选中节点: {node.name}")
    
    def _on_node_connected(self, source_id: str, source_port: str, target_id: str, target_port: str):
        """节点连接"""
        connection = NodeConnection(
            connection_id=str(uuid.uuid4())[:8],
            source_node_id=source_id,
            source_port=source_port,
            target_node_id=target_id,
            target_port=target_port
        )
        self.workflow.add_connection(connection)
        self.statusbar.showMessage(f"连接节点: {source_id} -> {target_id}")
    
    def _on_property_changed(self, node_id: str, config: dict):
        """属性改变"""
        if self.workflow:
            node = self.workflow.get_node(node_id)
            if node:
                self.statusbar.showMessage(f"更新节点: {node.name}")
    
    def delete_selected_node(self):
        """删除选中节点"""
        # 这里需要实现删除选中节点的逻辑
        # 暂时简单实现
        self.statusbar.showMessage("删除节点功能开发中")
    
    def toggle_grid(self):
        """切换网格显示"""
        show = not self.canvas._show_grid
        self.canvas.set_show_grid(show)
        self.grid_action.setChecked(show)
        self.statusbar.showMessage(f"{'显示' if show else '隐藏'}网格")
    
    def toggle_snapping(self):
        """切换对齐功能"""
        show = not self.canvas._show_snapping
        self.canvas.set_show_snapping(show)
        self.snap_action.setChecked(show)
        self.statusbar.showMessage(f"{'启用' if show else '禁用'}对齐")
    
    def zoom(self, factor: float):
        """缩放画布"""
        self.canvas.scale(factor, factor)
        self.statusbar.showMessage(f"缩放: {factor}")
    
    def reset_zoom(self):
        """重置缩放"""
        self.canvas.resetTransform()
        self.statusbar.showMessage("重置缩放")
    
    def open_workflow(self):
        """打开工作流"""
        self.statusbar.showMessage("打开工作流功能开发中")
    
    def save_workflow(self):
        """保存工作流"""
        self.statusbar.showMessage("保存工作流功能开发中")
    
    def new_workflow(self):
        """创建新工作流"""
        self.workflow = Workflow(
            workflow_id="",
            name="新工作流",
            description="描述工作流"
        )
        
        # 添加开始节点
        start_node = WorkflowNodeModel(
            node_id="start",
            node_type=NodeType.START,
            name="开始",
            position={"x": 100, "y": 200}
        )
        self.workflow.add_node(start_node)
        
        # 添加结束节点
        end_node = WorkflowNodeModel(
            node_id="end",
            node_type=NodeType.END,
            name="结束",
            position={"x": 600, "y": 200}
        )
        self.workflow.add_node(end_node)
        
        # 添加到画布
        self.canvas.clear()
        for node in self.workflow.nodes:
            self.canvas.add_node(node)
        
        self.statusbar.showMessage("创建新工作流")
    
    def add_node_to_canvas(self, node_type: str, name: str):
        """添加节点到画布"""
        node_type_enum = NodeType(node_type) if isinstance(node_type, str) else node_type
        
        node = WorkflowNodeModel(
            node_id=f"{node_type}_{len(self.workflow.nodes)}",
            node_type=node_type_enum,
            name=name,
            position={"x": 300, "y": 200}
        )
        
        self.workflow.add_node(node)
        self.canvas.add_node(node)
        self.statusbar.showMessage(f"添加节点: {name}")
    
    def _execution_callback(self, node_id: str, status: str, result: Any):
        """执行状态回调"""
        if node_id == "workflow":
            # 工作流整体状态
            if status == "completed":
                self.execution_panel.update_status("完成", "工作流执行完成")
                self.execution_panel.update_progress(100)
                self.statusbar.showMessage("工作流执行成功")
            elif status == "failed":
                self.execution_panel.update_status("失败", f"工作流执行失败: {result}")
                self.statusbar.showMessage("工作流执行失败")
        else:
            # 单个节点状态
            node = self.workflow.get_node(node_id)
            if node:
                # 更新节点状态
                node_item = self.canvas.get_node_item(node_id)
                if node_item:
                    node_status = NodeStatus(status)
                    node_item.node_widget.update_status(node_status)
                
                # 更新执行面板
                if status == "running":
                    self.execution_panel.update_status("运行中", f"执行节点: {node.name}")
                elif status == "completed":
                    self.execution_panel.update_status("完成", f"节点 {node.name} 执行完成")
                elif status == "failed":
                    self.execution_panel.update_status("失败", f"节点 {node.name} 执行失败: {result}")
    
    def execute_workflow(self):
        """执行工作流"""
        if not self.workflow:
            return
        
        # 清空执行面板
        self.execution_panel.clear()
        
        # 验证工作流
        validator = WorkflowValidator()
        is_valid, errors = validator.validate(self.workflow)
        
        if not is_valid:
            error_msg = "\n".join([f"{e.error_type}: {e.message}" for e in errors])
            print(f"[WorkflowEditor] 工作流验证失败:\n{error_msg}")
            self.statusbar.showMessage("工作流验证失败")
            self.execution_panel.update_status("错误", f"工作流验证失败: {error_msg}")
            return
        
        # 创建执行器
        executor = WorkflowExecutor()
        
        # 计算执行进度
        total_nodes = len([n for n in self.workflow.nodes if n.node_type != NodeType.START and n.node_type != NodeType.END])
        executed_nodes = 0
        
        # 自定义回调函数，添加进度计算
        def custom_callback(node_id: str, status: str, result: Any):
            nonlocal executed_nodes
            
            # 调用原始回调
            self._execution_callback(node_id, status, result)
            
            # 更新进度
            if node_id != "workflow" and status == "completed":
                executed_nodes += 1
                if total_nodes > 0:
                    progress = int((executed_nodes / total_nodes) * 100)
                    self.execution_panel.update_progress(progress)
        
        # 异步执行
        async def run():
            self.statusbar.showMessage("执行工作流...")
            self.execution_panel.update_status("开始", "开始执行工作流")
            
            result = await executor.execute(
                self.workflow,
                callback=custom_callback
            )
            
            if result.success:
                self.execution_panel.update_status("完成", "工作流执行成功")
                self.execution_panel.update_progress(100)
                print(f"[WorkflowEditor] 执行结果: {result.success}")
            else:
                self.execution_panel.update_status("失败", f"工作流执行失败: {result.error}")
                print(f"[WorkflowEditor] 错误: {result.error}")
        
        import asyncio
        asyncio.run(run())
    
    def save_as_template(self):
        """保存为模板"""
        from core.living_tree_ai.workflow import WorkflowTemplate, TemplateManager
        import uuid
        
        # 创建模板对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("保存为模板")
        layout = QVBoxLayout(dialog)
        
        # 模板名称
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("模板名称:"))
        name_edit = QLineEdit()
        name_edit.setText(self.workflow.name if self.workflow else "新模板")
        name_layout.addWidget(name_edit)
        layout.addLayout(name_layout)
        
        # 模板描述
        desc_layout = QHBoxLayout()
        desc_layout.addWidget(QLabel("模板描述:"))
        desc_edit = QTextEdit()
        desc_edit.setText(self.workflow.description if self.workflow else "")
        desc_edit.setMaximumHeight(80)
        desc_layout.addWidget(desc_edit)
        layout.addLayout(desc_layout)
        
        # 标签
        tags_layout = QHBoxLayout()
        tags_layout.addWidget(QLabel("标签:"))
        tags_edit = QLineEdit()
        tags_edit.setPlaceholderText("用逗号分隔多个标签")
        tags_layout.addWidget(tags_edit)
        layout.addLayout(tags_layout)
        
        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(button_box)
        
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # 创建模板
            template = WorkflowTemplate(
                template_id=str(uuid.uuid4())[:8],
                name=name_edit.text(),
                description=desc_edit.toPlainText(),
                workflow=self.workflow,
                tags=[tag.strip() for tag in tags_edit.text().split(",") if tag.strip()]
            )
            
            # 保存模板
            manager = TemplateManager()
            manager.save_template(template)
            
            self.statusbar.showMessage(f"模板保存成功: {template.name}")
    
    def import_template(self):
        """导入模板"""
        from core.living_tree_ai.workflow import TemplateManager
        from PyQt6.QtWidgets import QFileDialog
        
        # 选择文件
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入模板", "", "JSON Files (*.json)"
        )
        
        if file_path:
            manager = TemplateManager()
            template = manager.import_template(file_path)
            
            if template:
                # 加载模板到工作流
                self.workflow = template.workflow
                self.canvas.clear()
                for node in self.workflow.nodes:
                    self.canvas.add_node(node)
                
                self.statusbar.showMessage(f"模板导入成功: {template.name}")
            else:
                self.statusbar.showMessage("模板导入失败")
    
    def export_template(self):
        """导出模板"""
        from core.living_tree_ai.workflow import TemplateManager
        from PyQt6.QtWidgets import QFileDialog, QInputDialog
        
        # 选择模板
        manager = TemplateManager()
        templates = manager.list_templates()
        
        if not templates:
            self.statusbar.showMessage("没有可用的模板")
            return
        
        # 显示模板列表
        template_names = [t.name for t in templates]
        template_name, ok = QInputDialog.getItem(
            self, "选择模板", "选择要导出的模板:", template_names, 0, False
        )
        
        if ok:
            # 找到选中的模板
            selected_template = next((t for t in templates if t.name == template_name), None)
            if selected_template:
                # 选择保存路径
                file_path, _ = QFileDialog.getSaveFileName(
                    self, "导出模板", f"{selected_template.name}.json", "JSON Files (*.json)"
                )
                
                if file_path:
                    success = manager.export_template(selected_template.template_id, file_path)
                    if success:
                        self.statusbar.showMessage(f"模板导出成功: {file_path}")
                    else:
                        self.statusbar.showMessage("模板导出失败")
    
    def manage_templates(self):
        """管理模板"""
        from core.living_tree_ai.workflow import TemplateManager
        from PyQt6.QtWidgets import QListWidget, QVBoxLayout, QPushButton, QMessageBox
        
        # 创建管理对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("管理模板")
        dialog.resize(400, 300)
        
        layout = QVBoxLayout(dialog)
        
        # 模板列表
        template_list = QListWidget()
        layout.addWidget(template_list)
        
        # 加载模板
        manager = TemplateManager()
        templates = manager.list_templates()
        
        for template in templates:
            item = QListWidgetItem(f"{template.name} - {template.description[:50]}...")
            item.setData(Qt.ItemDataRole.UserRole, template.template_id)
            template_list.addItem(item)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        load_button = QPushButton("加载模板")
        delete_button = QPushButton("删除模板")
        
        button_layout.addWidget(load_button)
        button_layout.addWidget(delete_button)
        layout.addLayout(button_layout)
        
        # 加载模板
        def load_selected_template():
            selected_items = template_list.selectedItems()
            if selected_items:
                template_id = selected_items[0].data(Qt.ItemDataRole.UserRole)
                template = manager.load_template(template_id)
                if template:
                    self.workflow = template.workflow
                    self.canvas.clear()
                    for node in self.workflow.nodes:
                        self.canvas.add_node(node)
                    dialog.accept()
                    self.statusbar.showMessage(f"模板加载成功: {template.name}")
        
        # 删除模板
        def delete_selected_template():
            selected_items = template_list.selectedItems()
            if selected_items:
                template_id = selected_items[0].data(Qt.ItemDataRole.UserRole)
                template = manager.load_template(template_id)
                if template:
                    reply = QMessageBox.question(
                        self, "删除模板", f"确定要删除模板 '{template.name}' 吗?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    if reply == QMessageBox.StandardButton.Yes:
                        success = manager.delete_template(template_id)
                        if success:
                            template_list.takeItem(template_list.row(selected_items[0]))
                            self.statusbar.showMessage(f"模板删除成功: {template.name}")
        
        load_button.clicked.connect(load_selected_template)
        delete_button.clicked.connect(delete_selected_template)
        
        dialog.exec()
    
    def show_template_dialog(self):
        """显示模板选择对话框"""
        from PyQt6.QtWidgets import QListWidget, QVBoxLayout, QPushButton, QDialog
        
        # 创建模板对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("选择 AI 工作流模板")
        dialog.resize(400, 300)
        
        layout = QVBoxLayout(dialog)
        
        # 模板列表
        template_list = QListWidget()
        layout.addWidget(template_list)
        
        # 加载 AI 模板
        generator = get_workflow_generator()
        templates = generator.list_templates()
        
        for template in templates:
            item = QListWidgetItem(f"{template['name']} - {template['description'][:50]}...")
            item.setData(Qt.ItemDataRole.UserRole, template['id'])
            template_list.addItem(item)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        load_button = QPushButton("加载模板")
        cancel_button = QPushButton("取消")
        
        button_layout.addWidget(load_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        
        # 加载模板
        def load_selected_template():
            selected_items = template_list.selectedItems()
            if selected_items:
                template_id = selected_items[0].data(Qt.ItemDataRole.UserRole)
                workflow = generator.generate_from_template(template_id)
                if workflow:
                    self.workflow = workflow
                    self.canvas.clear()
                    for node in self.workflow.nodes:
                        # 转换为 WorkflowNodeModel
                        node_model = WorkflowNodeModel(
                            node_id=node.id,
                            node_type=NodeType(node.type),
                            name=node.name,
                            position=node.position,
                            config=node.config
                        )
                        self.canvas.add_node(node_model)
                    dialog.accept()
                    self.statusbar.showMessage(f"模板加载成功: {workflow.name}")
        
        load_button.clicked.connect(load_selected_template)
        cancel_button.clicked.connect(dialog.reject)
        
        dialog.exec()
    
    def show_auto_generate_dialog(self):
        """显示自动生成对话框"""
        from PyQt6.QtWidgets import QVBoxLayout, QLineEdit, QPushButton, QDialog, QLabel, QTextEdit
        
        # 创建自动生成对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("自动生成工作流")
        dialog.resize(400, 200)
        
        layout = QVBoxLayout(dialog)
        
        # 任务描述
        layout.addWidget(QLabel("任务描述:"))
        task_edit = QTextEdit()
        task_edit.setPlaceholderText("请描述您想要执行的任务，例如：'对文本进行情感分析' 或 '生成代码'")
        layout.addWidget(task_edit)
        
        # 按钮
        button_layout = QHBoxLayout()
        
        generate_button = QPushButton("生成工作流")
        cancel_button = QPushButton("取消")
        
        button_layout.addWidget(generate_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        
        # 生成工作流
        def generate_workflow():
            task_description = task_edit.toPlainText()
            if not task_description:
                self.statusbar.showMessage("请输入任务描述")
                return
            
            generator = get_workflow_generator()
            workflow = generator.generate_from_task(task_description)
            
            if workflow:
                self.workflow = workflow
                self.canvas.clear()
                for node in self.workflow.nodes:
                    # 转换为 WorkflowNodeModel
                    node_model = WorkflowNodeModel(
                        node_id=node.id,
                        node_type=NodeType(node.type),
                        name=node.name,
                        position=node.position,
                        config=node.config
                    )
                    self.canvas.add_node(node_model)
                dialog.accept()
                self.statusbar.showMessage(f"工作流生成成功: {workflow.name}")
            else:
                self.statusbar.showMessage("无法生成工作流，请尝试更详细的描述")
        
        generate_button.clicked.connect(generate_workflow)
        cancel_button.clicked.connect(dialog.reject)
        
        dialog.exec()
