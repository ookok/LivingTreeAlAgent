"""
增强浏览器组件

功能特性：
1. 集成QWebEngineView实现网页浏览
2. 自动处理需要登录的网页
3. 支持Cookie管理和会话保持
4. 支持网页截图
5. 支持JavaScript注入
6. 支持下载管理
"""

from typing import Optional, Callable, Dict, Any
from enum import Enum

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QToolBar, QProgressBar, QDialog, QFileDialog, QMessageBox,
    QMenu, QAction
)
from PyQt6.QtCore import Qt, QUrl, pyqtSignal, QPoint
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtWebEngineWidgets import (
    QWebEngineView, QWebEnginePage, QWebEngineProfile,
    QWebEngineDownloadItem
)
from PyQt6.QtWebEngineCore import QWebEngineSettings


class BrowserMode(Enum):
    """浏览器模式"""
    NORMAL = "normal"
    PRIVATE = "private"
    HEADLESS = "headless"


class EnhancedBrowser(QWidget):
    """增强浏览器组件"""
    
    url_changed = pyqtSignal(str)
    title_changed = pyqtSignal(str)
    load_finished = pyqtSignal(bool)
    login_required = pyqtSignal(str)
    download_requested = pyqtSignal(QWebEngineDownloadItem)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode = BrowserMode.NORMAL
        self._profile = None
        self._page = None
        self._login_handlers = {}
        
        self._setup_ui()
        self._setup_profile()
        self._setup_signals()
    
    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 工具栏
        toolbar = QToolBar()
        toolbar.setStyleSheet("""
            QToolBar {
                background-color: #ffffff;
                border-bottom: 1px solid #e5e7eb;
                spacing: 4px;
            }
            QToolButton {
                border: none;
                border-radius: 4px;
                padding: 6px;
            }
            QToolButton:hover {
                background-color: #f3f4f6;
            }
        """)
        
        # 返回按钮
        back_btn = toolbar.addAction("←")
        back_btn.triggered.connect(self._go_back)
        
        # 前进按钮
        forward_btn = toolbar.addAction("→")
        forward_btn.triggered.connect(self._go_forward)
        
        # 刷新按钮
        refresh_btn = toolbar.addAction("↻")
        refresh_btn.triggered.connect(self._refresh_page)
        
        # 地址栏
        self._url_bar = QLineEdit()
        self._url_bar.setPlaceholderText("输入网址...")
        self._url_bar.returnPressed.connect(self._navigate_to_url)
        self._url_bar.setStyleSheet("""
            QLineEdit {
                border: 1px solid #e5e7eb;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #3b82f6;
                outline: none;
            }
        """)
        toolbar.addWidget(self._url_bar)
        
        # 主页按钮
        home_btn = toolbar.addAction("🏠")
        home_btn.triggered.connect(self._go_home)
        
        # 新建标签页
        new_tab_btn = toolbar.addAction("➕")
        new_tab_btn.triggered.connect(self._new_tab)
        
        layout.addWidget(toolbar)
        
        # 进度条
        self._progress_bar = QProgressBar()
        self._progress_bar.setStyleSheet("""
            QProgressBar {
                height: 2px;
                border: none;
                background-color: #e5e7eb;
            }
            QProgressBar::chunk {
                background-color: #3b82f6;
            }
        """)
        layout.addWidget(self._progress_bar)
        
        # Web视图
        self._web_view = QWebEngineView()
        self._web_view.setStyleSheet("background-color: #ffffff;")
        layout.addWidget(self._web_view, 1)
    
    def _setup_profile(self):
        """设置浏览器配置"""
        # 创建持久化配置
        self._profile = QWebEngineProfile.defaultProfile()
        
        # 启用JavaScript
        settings = self._web_view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.PrivateBrowsingEnabled, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.CookiesEnabled, True)
    
    def _setup_signals(self):
        """设置信号连接"""
        self._web_view.urlChanged.connect(self._on_url_changed)
        self._web_view.titleChanged.connect(self._on_title_changed)
        self._web_view.loadProgress.connect(self._on_load_progress)
        self._web_view.loadFinished.connect(self._on_load_finished)
        
        # 下载管理
        self._profile.downloadRequested.connect(self._on_download_requested)
    
    def set_url(self, url: str):
        """设置URL"""
        qurl = QUrl(url)
        if not qurl.isValid():
            # 尝试作为搜索查询
            search_url = QUrl(f"https://www.google.com/search?q={url}")
            self._web_view.load(search_url)
        else:
            self._web_view.load(qurl)
    
    def get_url(self) -> str:
        """获取当前URL"""
        return self._web_view.url().toString()
    
    def set_mode(self, mode: BrowserMode):
        """设置浏览器模式"""
        self._mode = mode
        
        if mode == BrowserMode.PRIVATE:
            self._profile = QWebEngineProfile("private_profile", self)
            self._profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies)
        else:
            self._profile = QWebEngineProfile.defaultProfile()
        
        self._page = QWebEnginePage(self._profile, self._web_view)
        self._web_view.setPage(self._page)
    
    def add_login_handler(self, domain: str, handler: Callable):
        """添加登录处理器"""
        self._login_handlers[domain] = handler
    
    def remove_login_handler(self, domain: str):
        """移除登录处理器"""
        if domain in self._login_handlers:
            del self._login_handlers[domain]
    
    def execute_javascript(self, script: str, callback: Optional[Callable] = None):
        """执行JavaScript"""
        self._web_view.page().runJavaScript(script, callback)
    
    def capture_screenshot(self, callback: Optional[Callable] = None):
        """截取网页截图"""
        self._web_view.grab().save("screenshot.png")
        if callback:
            callback("screenshot.png")
    
    def _navigate_to_url(self):
        """导航到URL"""
        url = self._url_bar.text().strip()
        if url:
            self.set_url(url)
    
    def _go_back(self):
        """后退"""
        if self._web_view.history().canGoBack():
            self._web_view.back()
    
    def _go_forward(self):
        """前进"""
        if self._web_view.history().canGoForward():
            self._web_view.forward()
    
    def _refresh_page(self):
        """刷新页面"""
        self._web_view.reload()
    
    def _go_home(self):
        """返回主页"""
        self.set_url("https://www.google.com")
    
    def _new_tab(self):
        """新建标签页"""
        dialog = QDialog(self)
        dialog.setWindowTitle("新建标签页")
        dialog.setMinimumSize(800, 600)
        
        browser = EnhancedBrowser(dialog)
        browser.set_url("about:blank")
        
        layout = QVBoxLayout(dialog)
        layout.addWidget(browser)
        
        dialog.exec()
    
    def _on_url_changed(self, url: QUrl):
        """URL变化处理"""
        self._url_bar.setText(url.toString())
        self.url_changed.emit(url.toString())
        
        # 检查是否需要登录
        domain = url.host()
        if domain in self._login_handlers:
            self.login_required.emit(domain)
    
    def _on_title_changed(self, title: str):
        """标题变化处理"""
        self.title_changed.emit(title)
    
    def _on_load_progress(self, progress: int):
        """加载进度处理"""
        self._progress_bar.setValue(progress)
    
    def _on_load_finished(self, success: bool):
        """加载完成处理"""
        self._progress_bar.setValue(100)
        self.load_finished.emit(success)
        
        if not success:
            QMessageBox.warning(self, "加载失败", "无法加载该网页")
    
    def _on_download_requested(self, download: QWebEngineDownloadItem):
        """下载请求处理"""
        self.download_requested.emit(download)
        
        # 默认处理
        path, _ = QFileDialog.getSaveFileName(self, "保存文件", download.suggestedFileName())
        if path:
            download.setPath(path)
            download.accept()


class BrowserDialog(QDialog):
    """浏览器对话框"""
    
    def __init__(self, url: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("浏览器")
        self.setMinimumSize(1024, 768)
        self.setWindowFlags(Qt.WindowType.Window)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self._browser = EnhancedBrowser()
        layout.addWidget(self._browser)
        
        if url:
            self._browser.set_url(url)
    
    def set_url(self, url: str):
        """设置URL"""
        self._browser.set_url(url)


# 全局浏览器实例
_browser_instance = None

def get_browser() -> EnhancedBrowser:
    """获取全局浏览器实例"""
    global _browser_instance
    if _browser_instance is None:
        _browser_instance = EnhancedBrowser()
    return _browser_instance


def open_url_in_browser(url: str):
    """在浏览器中打开URL"""
    dialog = BrowserDialog(url)
    dialog.exec()


# 示例使用
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # 打开示例URL
    open_url_in_browser("https://www.example.com")
    
    sys.exit(app.exec())