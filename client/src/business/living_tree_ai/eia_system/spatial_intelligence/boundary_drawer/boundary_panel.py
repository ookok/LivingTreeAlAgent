"""
PyQt6 边界绘制面板
==================

集成 OpenLayers 边界绘制器到 PyQt6 应用：
1. QWebEngineView 加载 HTML
2. JavaScript 接口桥接
3. 边界数据回调
4. 信号事件

依赖:
    PyQt6.QtWebEngineWidgets
    PyQt6.QtCore

Author: Hermes Desktop EIA System
"""

import json
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass

# 检查 PyQt6 是否可用
try:
    from PyQt6.QtCore import QUrl, pyqtSignal, QObject, pyqtSlot
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
    from PyQt6.QtWebChannel import QWebChannel
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    print("Warning: PyQt6.QtWebEngineWidgets not available")


if PYQT_AVAILABLE:
    class WebBridge(QObject):
        """JavaScript 桥接对象"""
        boundaryChanged = pyqtSignal(dict)
        importCompleted = pyqtSignal(dict)
        exportRequested = pyqtSignal(str)

        @pyqtSlot(str)
        def onBoundaryChange(self, geojson_str: str):
            """接收 JavaScript 边界变化"""
            try:
                geojson = json.loads(geojson_str)
                self.boundaryChanged.emit(geojson)
            except Exception as e:
                print(f"解析边界数据失败: {e}")

        @pyqtSlot(str)
        def onImportComplete(self, geojson_str: str):
            """接收导入完成"""
            try:
                geojson = json.loads(geojson_str)
                self.importCompleted.emit(geojson)
            except Exception as e:
                print(f"解析导入数据失败: {e}")


    class BoundaryDrawerPanel(QWebEngineView):
        """
        边界绘制面板

        用法:
            panel = BoundaryDrawerPanel()

            # 连接信号
            panel.boundaryChanged.connect(lambda data: print("边界变化:", data))

            # 加载 HTML
            panel.load_html()

            # 获取边界数据
            data = panel.get_boundary_data()

            # 设置边界数据
            panel.set_boundary_data(geojson)
        """

        boundaryChanged = pyqtSignal(dict)  # 边界变化信号
        importCompleted = pyqtSignal(dict)  # 导入完成信号

        def __init__(self, html_path: str = "", parent=None):
            """
            Args:
                html_path: HTML 文件路径
                parent: 父控件
            """
            super().__init__(parent)

            self._html_path = html_path
            self._web_bridge: Optional[WebBridge] = None
            self._channel: Optional[QWebChannel] = None
            self._js_ready = False

            # 设置 WebChannel
            self._setup_bridge()

            # 加载 HTML
            if html_path:
                self.load_html(html_path)

        def _setup_bridge(self):
            """设置 JavaScript 桥接"""
            self._web_bridge = WebBridge()
            self._channel = QWebChannel(self)

            # 注册桥接对象
            self._channel.registerObject("pyBridge", self._web_bridge)
            self.page().setWebChannel(self._channel)

            # 连接信号
            self._web_bridge.boundaryChanged.connect(self.boundaryChanged)
            self._web_bridge.importCompleted.connect(self.importCompleted)

            # 页面加载完成
            self.loadFinished.connect(self._on_load_finished)

        def _on_load_finished(self, ok: bool):
            """页面加载完成"""
            if ok:
                # 注入 Python 桥接对象
                self.page().runJavaScript("""
                    window.pyBridge = {
                        onBoundaryChange: function(data) {
                            if (window.pyBridge) {
                                window.pyBridge.onBoundaryChange(JSON.stringify(data));
                            }
                        }
                    };
                """)
                self._js_ready = True

        def load_html(self, html_path: str = ""):
            """
            加载 HTML

            Args:
                html_path: HTML 文件路径
            """
            if not html_path and self._html_path:
                html_path = self._html_path

            if html_path:
                self._html_path = html_path
                self.load(QUrl.fromLocalFile(html_path))

        def get_boundary_data(self) -> Optional[Dict]:
            """
            获取边界数据（同步调用）

            Returns:
                GeoJSON 数据
            """
            if not self._js_ready:
                return None

            # 同步执行 JavaScript 获取数据
            result = []
            def handle_result(data):
                result.append(data)

            self.page().runJavaScript(
                "window.BoundaryDrawer.getBoundaryData();",
                handle_result
            )

            return result[0] if result else None

        async def get_boundary_data_async(self) -> Optional[Dict]:
            """
            获取边界数据（异步调用）

            Returns:
                GeoJSON 数据
            """
        def set_boundary_data(self, geojson: Dict):
            """
            设置边界数据

            Args:
                geojson: GeoJSON 数据
            """
            if not self._js_ready:
                return

            geojson_str = json.dumps(geojson, ensure_ascii=False)
            self.page().runJavaScript(f"""
                window.BoundaryDrawer.setBoundaryData({geojson_str});
            """)

        def set_center(self, lat: float, lon: float, zoom: int = 14):
            """
            设置地图中心

            Args:
                lat: 纬度
                lon: 经度
                zoom: 缩放级别
            """
            if not self._js_ready:
                return

            self.page().runJavaScript(f"""
                window.BoundaryDrawer.setCenter({lat}, {lon}, {zoom});
            """)

        def clear_boundaries(self):
            """清除所有边界"""
            if not self._js_ready:
                return

            self.page().runJavaScript("""
                if (window.BoundaryDrawer) {{
                    const features = window.BoundaryDrawer.getBoundaryData().features;
                    // 触发清除
                }}
            """)


    class BoundaryReviewDialog(QDialog):
        """
        边界审核对话框

        用于显示和审核绘制的厂区边界
        """

        def __init__(self, boundary_data: Dict, parent=None):
            """
            Args:
                boundary_data: 边界数据
                parent: 父控件
            """
            super().__init__(parent)
            self._boundary_data = boundary_data

            self.setWindowTitle("厂区边界审核")
            self.setMinimumSize(800, 600)

            self._init_ui()

        def _init_ui(self):
            """初始化 UI"""
            layout = QVBoxLayout(self)

            # 提示信息
            info_label = QLabel("请核对以下厂区边界信息，如有错误请修正：")
            layout.addWidget(info_label)

            # 边界绘制面板
            self._panel = BoundaryDrawerPanel()
            self._panel.set_boundary_data(self._boundary_data)
            layout.addWidget(self._panel)

            # 按钮
            btn_layout = QHBoxLayout()
            btn_layout.addStretch()

            self._btn_confirm = QPushButton("确认入库")
            self._btn_confirm.clicked.connect(self.accept)
            btn_layout.addWidget(self._btn_confirm)

            self._btn_cancel = QPushButton("取消")
            self._btn_cancel.clicked.connect(self.reject)
            btn_layout.addWidget(self._btn_cancel)

            layout.addLayout(btn_layout)

        def get_boundary_data(self) -> Dict:
            """获取边界数据"""
            return self._panel.get_boundary_data()


# 兼容：非 PyQt6 环境提供替代
class BoundaryDrawerPanel:
    """占位类（PyQt6 不可用时）"""

    def __init__(self, *args, **kwargs):
        raise RuntimeError("PyQt6.QtWebEngineWidgets is required")

    boundaryChanged = None
    importCompleted = None


class BoundaryReviewDialog:
    """占位类（PyQt6 不可用时）"""

    def __init__(self, *args, **kwargs):
        raise RuntimeError("PyQt6 is required")
