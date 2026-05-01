"""
Qt WebEngine + Vue.js 混合架构主应用

核心架构：
- Qt WebEngine 作为容器
- Vue.js 作为前端框架
- QWebChannel 实现 Python ↔ JavaScript 通信
- 后端服务通过桥接暴露给前端

设计理念：
- 原生性能 + Web 灵活性
- 渐进式迁移策略
- 保持现有 Python 业务逻辑不变
"""

import sys
import json
import asyncio
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QSplitter, QWidget, QVBoxLayout,
    QStatusBar, QMenuBar, QMenu, QToolBar, QMessageBox
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtCore import (
    QObject, pyqtSlot, pyqtProperty, QUrl, Qt, QTimer
)
from PyQt6.QtGui import QAction, QIcon

# 导入后端服务
sys.path.insert(0, str(Path(__file__).parent))

from business.dynamic_ui_engine import get_dynamic_ui_engine
from business.ui_adapter import get_ui_adapter
from business.evolutionary_learning import get_evolutionary_learning_service
from business.real_time_learning import get_real_time_learning_service
from business.ab_test_framework import get_ab_test_framework
from business.user_preference_model import get_user_preference_model


class BackendBridge(QObject):
    """
    Python ↔ JavaScript 通信桥接类
    
    暴露后端服务方法给前端调用
    """
    
    def __init__(self):
        super().__init__()
        
        # 初始化后端服务
        self._ui_engine = get_dynamic_ui_engine()
        self._ui_adapter = get_ui_adapter()
        self._learning_service = get_evolutionary_learning_service()
        self._rt_learning = get_real_time_learning_service()
        self._ab_test = get_ab_test_framework()
        self._preference_model = get_user_preference_model()
        
        # 当前用户ID（实际应用中应从登录系统获取）
        self._current_user_id = "default_user"
        
        # 启动实时学习服务
        asyncio.ensure_future(self._rt_learning.start())
        
        logger.info("✅ BackendBridge 初始化完成")
    
    @pyqtSlot(str, result=str)
    def generateUI(self, context_json):
        """
        根据上下文生成动态UI
        
        Args:
            context_json: JSON格式的上下文数据
        
        Returns:
            JSON格式的UI Schema
        """
        try:
            context = json.loads(context_json) if context_json else {}
            schema = self._ui_engine.generate_ui(context)
            return self._ui_adapter.export_ui_schema(schema)
        except Exception as e:
            logger.error(f"生成UI失败: {e}")
            return json.dumps({"error": str(e)})
    
    @pyqtSlot(str, str, result=str)
    def handleEvent(self, event_type, payload_json):
        """
        处理前端事件
        
        Args:
            event_type: 事件类型
            payload_json: JSON格式的事件数据
        
        Returns:
            JSON格式的处理结果
        """
        try:
            payload = json.loads(payload_json) if payload_json else {}
            result = self._ui_adapter.handle_event({
                "event_type": event_type,
                "component_id": payload.get("component_id"),
                "payload": payload
            })
            return json.dumps(result)
        except Exception as e:
            logger.error(f"处理事件失败: {e}")
            return json.dumps({"success": False, "error": str(e)})
    
    @pyqtSlot(str, result=str)
    def getEvolutionMetrics(self, user_id):
        """获取进化指标"""
        try:
            metrics = self._learning_service.get_evolution_metrics()
            return json.dumps(metrics)
        except Exception as e:
            logger.error(f"获取进化指标失败: {e}")
            return json.dumps({})
    
    @pyqtSlot(str, str, result=str)
    def recordBehavior(self, user_id, behavior_json):
        """记录用户行为"""
        try:
            from business.evolutionary_learning import BehaviorType
            
            behavior_data = json.loads(behavior_json)
            behavior_type = behavior_data.get("type", "message_sent")
            
            behavior_type_map = {
                "message_sent": BehaviorType.MESSAGE_SENT,
                "file_uploaded": BehaviorType.FILE_UPLOADED,
                "form_submitted": BehaviorType.FORM_SUBMITTED,
                "suggestion_clicked": BehaviorType.SUGGESTION_CLICKED,
                "feedback_provided": BehaviorType.FEEDBACK_PROVIDED
            }
            
            self._learning_service.record_behavior(
                user_id=user_id,
                session_id="current_session",
                behavior_type=behavior_type_map.get(behavior_type, BehaviorType.ACTION_EXECUTED),
                data=behavior_data.get("data", {})
            )
            
            return json.dumps({"success": True})
        except Exception as e:
            logger.error(f"记录行为失败: {e}")
            return json.dumps({"success": False, "error": str(e)})
    
    @pyqtSlot(str, str, result=str)
    def recommendComponents(self, user_id, context_json):
        """推荐组件"""
        try:
            context = json.loads(context_json) if context_json else {}
            recommendations = self._preference_model.recommend_components(user_id, context)
            return json.dumps(recommendations)
        except Exception as e:
            logger.error(f"推荐组件失败: {e}")
            return json.dumps([])
    
    @pyqtSlot(str, str, result=str)
    def personalizeUI(self, user_id, ui_schema_json):
        """个性化UI"""
        try:
            ui_schema = json.loads(ui_schema_json) if ui_schema_json else {}
            personalized = self._preference_model.personalize_ui(user_id, ui_schema)
            return json.dumps(personalized)
        except Exception as e:
            logger.error(f"个性化UI失败: {e}")
            return ui_schema_json
    
    @pyqtSlot(str, result=str)
    def getLearningStats(self, user_id):
        """获取学习统计"""
        try:
            stats = self._rt_learning.get_stats()
            return json.dumps(stats)
        except Exception as e:
            logger.error(f"获取学习统计失败: {e}")
            return json.dumps({})
    
    @pyqtSlot(result=str)
    def getDefaultContext(self):
        """获取默认上下文"""
        return json.dumps({
            "user_id": self._current_user_id,
            "session_id": "current_session",
            "timestamp": asyncio.get_event_loop().time()
        })


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("环评智能工作台 - AI-Centric Pipeline")
        self.setMinimumSize(1200, 800)
        
        # 初始化UI
        self._init_ui()
        
        # 初始化后端桥接
        self._init_backend()
        
        # 加载前端应用
        self._load_frontend()
        
        logger.info("✅ 主窗口初始化完成")
    
    def _init_ui(self):
        """初始化UI布局"""
        # 创建状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("系统已启动")
        
        # 创建菜单栏
        self._init_menu_bar()
        
        # 创建工具栏
        self._init_tool_bar()
        
        # 创建中央布局
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 创建WebEngine视图
        self.web_view = QWebEngineView()
        self.splitter.addWidget(self.web_view)
        
        # 设置中央部件
        self.setCentralWidget(self.splitter)
    
    def _init_menu_bar(self):
        """初始化菜单栏"""
        menu_bar = QMenuBar()
        
        # 文件菜单
        file_menu = QMenu("文件", self)
        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        menu_bar.addMenu(file_menu)
        
        # 视图菜单
        view_menu = QMenu("视图", self)
        refresh_action = QAction("刷新页面", self)
        refresh_action.triggered.connect(self.web_view.reload)
        view_menu.addAction(refresh_action)
        menu_bar.addMenu(view_menu)
        
        # 帮助菜单
        help_menu = QMenu("帮助", self)
        about_action = QAction("关于", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
        menu_bar.addMenu(help_menu)
        
        self.setMenuBar(menu_bar)
    
    def _init_tool_bar(self):
        """初始化工具栏"""
        tool_bar = QToolBar()
        
        # 刷新按钮
        refresh_btn = QAction("刷新", self)
        refresh_btn.triggered.connect(self.web_view.reload)
        tool_bar.addAction(refresh_btn)
        
        # 学习统计按钮
        stats_btn = QAction("学习统计", self)
        stats_btn.triggered.connect(self._show_learning_stats)
        tool_bar.addAction(stats_btn)
        
        # 偏好设置按钮
        prefs_btn = QAction("偏好设置", self)
        prefs_btn.triggered.connect(self._show_preferences)
        tool_bar.addAction(prefs_btn)
        
        self.addToolBar(tool_bar)
    
    def _init_backend(self):
        """初始化后端通信"""
        # 创建WebChannel
        self.channel = QWebChannel()
        
        # 创建后端桥接对象
        self.backend = BackendBridge()
        self.channel.registerObject("backend", self.backend)
        
        # 绑定到WebEngine
        self.web_view.page().setWebChannel(self.channel)
    
    def _load_frontend(self):
        """加载前端应用"""
        # 尝试加载本地构建的前端文件
        frontend_path = Path(__file__).parent.parent / "frontend" / "dist" / "index.html"
        
        if frontend_path.exists():
            self.web_view.load(QUrl.fromLocalFile(str(frontend_path)))
        else:
            # 如果没有构建文件，加载开发服务器
            # 开发模式：http://localhost:5173
            self.web_view.load(QUrl("http://localhost:5173"))
            
            # 显示提示
            self.status_bar.showMessage("开发模式：连接到 http://localhost:5173")
    
    def _show_about(self):
        """显示关于对话框"""
        QMessageBox.about(self, "关于", "环评智能工作台 v1.0\n\n基于 Qt WebEngine + Vue.js 构建")
    
    def _show_learning_stats(self):
        """显示学习统计"""
        try:
            stats = self.backend.getLearningStats("default_user")
            stats_data = json.loads(stats)
            
            message = "\n".join([
                f"学习周期: {stats_data.get('total_learning_cycles', 0)}",
                f"发现模式: {stats_data.get('patterns_discovered', 0)}",
                f"更新策略: {stats_data.get('strategies_updated', 0)}",
                f"最后学习: {stats_data.get('last_learning_time', '未知')}"
            ])
            
            QMessageBox.information(self, "学习统计", message)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"获取统计失败: {e}")
    
    def _show_preferences(self):
        """显示偏好设置"""
        QMessageBox.information(self, "偏好设置", "偏好设置功能开发中...")
    
    def closeEvent(self, event):
        """关闭事件处理"""
        # 停止实时学习服务
        asyncio.ensure_future(self.backend._rt_learning.stop())
        event.accept()


def main():
    """主入口"""
    global logger
    
    # 配置日志
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(message)s"
    )
    logger = logging.getLogger(__name__)
    
    logger.info("🚀 启动环评智能工作台")
    
    # 创建应用
    app = QApplication(sys.argv)
    
    # 创建主窗口
    window = MainWindow()
    window.show()
    
    # 启动事件循环
    sys.exit(app.exec())


if __name__ == "__main__":
    main()