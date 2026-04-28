"""
WorkflowPanel - 可视化工作流编辑器面板

基于 PyQt6 实现的 DAG 工作流拖拽编辑器，类似 Archon 的 Web 控制台。

功能：
1. 可视化工作流节点展示
2. 支持拖拽创建和连接节点
3. 支持条件分支、循环、并行执行
4. 工作流验证和导出
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGraphicsView, QGraphicsScene,
    QGraphicsItem, QGraphicsRectItem, QGraphicsTextItem, QGraphicsLineItem,
    QPushButton, QToolBar, QComboBox, QLineEdit, QLabel, QSplitter,
    QTreeWidget, QTreeWidgetItem, QDialog, QFormLayout, QMessageBox
)
from PyQt6.QtCore import (
    Qt, QPointF, QRectF, QMimeData, QObject, pyqtSignal, QEvent
)
from PyQt6.QtGui import (
    QPen, QBrush, QColor, QFont, QDrag, QPainter, QIcon
)
from loguru import logger
import json


class WorkflowNodeItem(QGraphicsRectItem):
    """工作流节点图形项"""
    
    def __init__(self, node_id, node_type, name, x=0, y=0):
        super().__init__(x, y, 120, 60)
        self.node_id = node_id
        self.node_type = node_type
        self.name = name
        
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        
        # 根据节点类型设置颜色
        self._set_node_style()
        
        # 添加标签
        self.label = QGraphicsTextItem(name, self)
        self.label.setPos(10, 20)
        self.label.setFont(QFont("Arial", 10))
        
        # 连接点
        self.input_port = QPointF(60, 0)
        self.output_port = QPointF(60, 60)
        
        # 选中状态
        self._is_selected = False
    
    def _set_node_style(self):
        """设置节点样式"""
        colors = {
            "start": QColor(0, 180, 0),
            "end": QColor(180, 0, 0),
            "action": QColor(0, 100, 200),
            "condition": QColor(200, 150, 0),
            "loop": QColor(150, 0, 200),
            "parallel": QColor(100, 150, 100)
        }
        
        color = colors.get(self.node_type, QColor(100, 100, 100))
        self.setBrush(QBrush(color))
        self.setPen(QPen(Qt.GlobalColor.black, 2))
        
        # 选中时高亮
        self.setOpacity(0.9)
    
    def itemChange(self, change, value):
        """处理位置变化，通知连接更新"""
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            # 更新所有连接
            for connection in self._connections:
                connection.update_line()
        return super().itemChange(change, value)
    
    def add_connection(self, connection):
        """添加连接"""
        if not hasattr(self, '_connections'):
            self._connections = []
        self._connections.append(connection)
    
    def get_input_port(self):
        """获取输入端口位置（相对于场景）"""
        return self.mapToScene(self.input_port)
    
    def get_output_port(self):
        """获取输出端口位置（相对于场景）"""
        return self.mapToScene(self.output_port)
    
    def paint(self, painter, option, widget=None):
        """绘制节点"""
        super().paint(painter, option, widget)
        
        # 绘制端口
        painter.setBrush(QBrush(Qt.GlobalColor.white))
        painter.setPen(QPen(Qt.GlobalColor.black, 2))
        
        # 输入端口（顶部）
        input_pos = self.mapToScene(self.input_port)
        painter.drawEllipse(input_pos.x() - 5, input_pos.y() - 5, 10, 10)
        
        # 输出端口（底部）
        output_pos = self.mapToScene(self.output_port)
        painter.drawEllipse(output_pos.x() - 5, output_pos.y() - 5, 10, 10)


class ConnectionItem(QGraphicsLineItem):
    """连接线条项"""
    
    def __init__(self, from_node, to_node):
        super().__init__()
        self.from_node = from_node
        self.to_node = to_node
        
        self.setPen(QPen(Qt.GlobalColor.darkGray, 2))
        self.setZValue(-1)
        
        from_node.add_connection(self)
        to_node.add_connection(self)
        
        self.update_line()
    
    def update_line(self):
        """更新线条位置"""
        start = self.from_node.get_output_port()
        end = self.to_node.get_input_port()
        self.setLine(start.x(), start.y(), end.x(), end.y())


class WorkflowScene(QGraphicsScene):
    """工作流场景"""
    
    node_selected = pyqtSignal(str)
    connection_created = pyqtSignal(str, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._nodes = {}
        self._connections = []
        self._connecting_from = None
        self._temp_line = None
        
        self.setBackgroundBrush(QBrush(QColor(30, 30, 35)))
    
    def add_node(self, node_id, node_type, name, x=0, y=0):
        """添加节点"""
        node = WorkflowNodeItem(node_id, node_type, name, x, y)
        self.addItem(node)
        self._nodes[node_id] = node
        return node
    
    def get_node(self, node_id):
        """获取节点"""
        return self._nodes.get(node_id)
    
    def remove_node(self, node_id):
        """移除节点"""
        node = self._nodes.get(node_id)
        if node:
            # 移除相关连接
            connections_to_remove = []
            for conn in self._connections:
                if conn.from_node == node or conn.to_node == node:
                    connections_to_remove.append(conn)
            
            for conn in connections_to_remove:
                self.remove_connection(conn)
            
            self.removeItem(node)
            del self._nodes[node_id]
    
    def add_connection(self, from_node_id, to_node_id):
        """添加连接"""
        from_node = self._nodes.get(from_node_id)
        to_node = self._nodes.get(to_node_id)
        
        if from_node and to_node:
            connection = ConnectionItem(from_node, to_node)
            self.addItem(connection)
            self._connections.append(connection)
            self.connection_created.emit(from_node_id, to_node_id)
    
    def remove_connection(self, connection):
        """移除连接"""
        if connection in self._connections:
            self.removeItem(connection)
            self._connections.remove(connection)
    
    def mousePressEvent(self, event):
        """处理鼠标按下事件"""
        item = self.itemAt(event.scenePos(), QTransform())
        
        if isinstance(item, WorkflowNodeItem):
            self.node_selected.emit(item.node_id)
            self._connecting_from = item
            # 创建临时连接线
            self._temp_line = QGraphicsLineItem()
            self._temp_line.setPen(QPen(Qt.GlobalColor.blue, 2, Qt.PenStyle.DashLine))
            self.addItem(self._temp_line)
        
        elif event.button() == Qt.MouseButton.RightButton:
            # 右键取消连接
            if self._temp_line:
                self.removeItem(self._temp_line)
                self._temp_line = None
            self._connecting_from = None
        
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """处理鼠标移动事件"""
        if self._connecting_from and self._temp_line:
            start = self._connecting_from.get_output_port()
            end = event.scenePos()
            self._temp_line.setLine(start.x(), start.y(), end.x(), end.y())
        
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """处理鼠标释放事件"""
        if self._connecting_from:
            item = self.itemAt(event.scenePos(), QTransform())
            
            if isinstance(item, WorkflowNodeItem) and item != self._connecting_from:
                # 创建连接
                self.add_connection(self._connecting_from.node_id, item.node_id)
            
            # 清理临时线条
            if self._temp_line:
                self.removeItem(self._temp_line)
                self._temp_line = None
            
            self._connecting_from = None
        
        super().mouseReleaseEvent(event)
    
    def clear_all(self):
        """清空场景"""
        self._connections.clear()
        self._nodes.clear()
        self.clear()


class WorkflowPanel(QWidget):
    """工作流编辑器面板"""
    
    def __init__(self):
        super().__init__()
        self._init_ui()
        self._workflow_data = {}
    
    def _init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # 工具栏
        toolbar = QToolBar()
        layout.addWidget(toolbar)
        
        # 新建按钮
        self._btn_new = QPushButton("新建")
        self._btn_new.clicked.connect(self._on_new_workflow)
        toolbar.addWidget(self._btn_new)
        
        # 保存按钮
        self._btn_save = QPushButton("保存")
        self._btn_save.clicked.connect(self._on_save_workflow)
        toolbar.addWidget(self._btn_save)
        
        # 加载按钮
        self._btn_load = QPushButton("加载")
        self._btn_load.clicked.connect(self._on_load_workflow)
        toolbar.addWidget(self._btn_load)
        
        # 验证按钮
        self._btn_validate = QPushButton("验证")
        self._btn_validate.clicked.connect(self._on_validate_workflow)
        toolbar.addWidget(self._btn_validate)
        
        toolbar.addSeparator()
        
        # 添加节点按钮
        self._cb_node_type = QComboBox()
        self._cb_node_type.addItems(["start", "end", "action", "condition", "loop", "parallel"])
        toolbar.addWidget(QLabel("添加节点:"))
        toolbar.addWidget(self._cb_node_type)
        
        self._btn_add_node = QPushButton("添加")
        self._btn_add_node.clicked.connect(self._on_add_node)
        toolbar.addWidget(self._btn_add_node)
        
        # 分割窗口
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
        
        # 场景视图
        self._scene = WorkflowScene()
        self._view = QGraphicsView(self._scene)
        self._view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._view.setRenderHint(QPainter.RenderHint.Antialiasing)
        splitter.addWidget(self._view)
        
        # 属性面板
        self._props_panel = QWidget()
        props_layout = QVBoxLayout()
        self._props_panel.setLayout(props_layout)
        
        # 节点属性
        props_layout.addWidget(QLabel("节点属性"))
        
        self._edit_node_name = QLineEdit()
        self._edit_node_name.setPlaceholderText("节点名称")
        props_layout.addWidget(self._edit_node_name)
        
        self._cb_node_type_edit = QComboBox()
        self._cb_node_type_edit.addItems(["start", "end", "action", "condition", "loop", "parallel"])
        props_layout.addWidget(self._cb_node_type_edit)
        
        self._btn_apply = QPushButton("应用")
        self._btn_apply.clicked.connect(self._on_apply_node_changes)
        props_layout.addWidget(self._btn_apply)
        
        self._btn_delete = QPushButton("删除节点")
        self._btn_delete.clicked.connect(self._on_delete_node)
        props_layout.addWidget(self._btn_delete)
        
        props_layout.addStretch()
        
        splitter.addWidget(self._props_panel)
        
        # 选中的节点
        self._selected_node_id = None
        
        # 连接场景信号
        self._scene.node_selected.connect(self._on_node_selected)
    
    def _on_new_workflow(self):
        """新建工作流"""
        self._scene.clear_all()
        self._workflow_data = {}
        QMessageBox.information(self, "新建", "已创建新工作流")
    
    def _on_save_workflow(self):
        """保存工作流"""
        workflow = self._export_workflow()
        
        import json
        content = json.dumps(workflow, indent=2, ensure_ascii=False)
        
        from PyQt6.QtWidgets import QFileDialog
        filename, _ = QFileDialog.getSaveFileName(
            self, "保存工作流", "", "YAML Files (*.yaml *.yml);;JSON Files (*.json)"
        )
        
        if filename:
            with open(filename, "w", encoding="utf-8") as f:
                if filename.endswith(".json"):
                    f.write(content)
                else:
                    # 转换为 YAML
                    import yaml
                    yaml.dump(workflow, f, default_flow_style=False, allow_unicode=True)
            
            QMessageBox.information(self, "保存成功", f"工作流已保存到 {filename}")
    
    def _on_load_workflow(self):
        """加载工作流"""
        from PyQt6.QtWidgets import QFileDialog
        filename, _ = QFileDialog.getOpenFileName(
            self, "加载工作流", "", "YAML Files (*.yaml *.yml);;JSON Files (*.json)"
        )
        
        if filename:
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    if filename.endswith(".json"):
                        workflow = json.load(f)
                    else:
                        import yaml
                        workflow = yaml.safe_load(f)
                
                self._import_workflow(workflow)
                QMessageBox.information(self, "加载成功", f"工作流已加载")
            except Exception as e:
                QMessageBox.error(self, "加载失败", str(e))
    
    def _on_validate_workflow(self):
        """验证工作流"""
        errors = self._validate_workflow()
        
        if errors:
            QMessageBox.warning(self, "验证失败", "\n".join(errors))
        else:
            QMessageBox.information(self, "验证通过", "工作流验证通过")
    
    def _on_add_node(self):
        """添加节点"""
        node_type = self._cb_node_type.currentText()
        node_id = f"node_{len(self._scene._nodes) + 1}"
        name = node_type.capitalize()
        
        # 在视图中心添加节点
        view_rect = self._view.viewport().rect()
        center = self._view.mapToScene(view_rect.center())
        
        self._scene.add_node(node_id, node_type, name, center.x() - 60, center.y() - 30)
    
    def _on_node_selected(self, node_id):
        """节点选中"""
        self._selected_node_id = node_id
        node = self._scene.get_node(node_id)
        
        if node:
            self._edit_node_name.setText(node.name)
            self._cb_node_type_edit.setCurrentText(node.node_type)
    
    def _on_apply_node_changes(self):
        """应用节点更改"""
        if self._selected_node_id:
            node = self._scene.get_node(self._selected_node_id)
            if node:
                node.name = self._edit_node_name.text()
                node.node_type = self._cb_node_type_edit.currentText()
                node._set_node_style()
                node.label.setPlainText(node.name)
    
    def _on_delete_node(self):
        """删除节点"""
        if self._selected_node_id:
            self._scene.remove_node(self._selected_node_id)
            self._selected_node_id = None
            self._edit_node_name.clear()
    
    def _export_workflow(self):
        """导出工作流"""
        workflow = {
            "name": "未命名工作流",
            "version": "1.0.0",
            "nodes": {},
            "connections": []
        }
        
        # 导出节点
        for node_id, node in self._scene._nodes.items():
            pos = node.pos()
            workflow["nodes"][node_id] = {
                "id": node_id,
                "type": node.node_type,
                "name": node.name,
                "x": pos.x(),
                "y": pos.y()
            }
        
        # 导出连接
        for conn in self._scene._connections:
            workflow["connections"].append({
                "from": conn.from_node.node_id,
                "to": conn.to_node.node_id
            })
        
        return workflow
    
    def _import_workflow(self, workflow):
        """导入工作流"""
        self._scene.clear_all()
        
        # 导入节点
        nodes = workflow.get("nodes", {})
        for node_id, data in nodes.items():
            self._scene.add_node(
                node_id,
                data.get("type", "action"),
                data.get("name", node_id),
                data.get("x", 0),
                data.get("y", 0)
            )
        
        # 导入连接
        connections = workflow.get("connections", [])
        for conn in connections:
            self._scene.add_connection(conn["from"], conn["to"])
    
    def _validate_workflow(self):
        """验证工作流"""
        errors = []
        
        nodes = self._scene._nodes
        connections = self._scene._connections
        
        # 检查是否有开始节点
        has_start = any(node.node_type == "start" for node in nodes.values())
        if not has_start:
            errors.append("缺少开始节点")
        
        # 检查是否有结束节点
        has_end = any(node.node_type == "end" for node in nodes.values())
        if not has_end:
            errors.append("缺少结束节点")
        
        # 检查连接是否形成有效路径
        if connections:
            from_nodes = set(conn.from_node.node_id for conn in connections)
            to_nodes = set(conn.to_node.node_id for conn in connections)
            
            # 检查开始节点是否有输出连接
            start_nodes = [n for n in nodes.values() if n.node_type == "start"]
            for start in start_nodes:
                if start.node_id not in from_nodes:
                    errors.append(f"开始节点 {start.name} 没有输出连接")
            
            # 检查结束节点是否有输入连接
            end_nodes = [n for n in nodes.values() if n.node_type == "end"]
            for end in end_nodes:
                if end.node_id not in to_nodes:
                    errors.append(f"结束节点 {end.name} 没有输入连接")
        
        return errors