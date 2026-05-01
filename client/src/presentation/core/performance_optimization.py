"""
性能优化模块 - Performance Optimization

功能：
1. QWebEngine 性能配置
2. WebGL 加速
3. 渲染优化
4. 内存管理
"""

from PyQt6.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
from PyQt6.QtCore import QUrl, Qt


class OptimizedWebEngineView(QWebEngineView):
    """
    优化的WebEngine视图
    
    性能优化策略：
    1. 启用硬件加速
    2. 优化JavaScript执行
    3. 缓存策略优化
    4. 禁用不必要功能
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_performance_settings()
        self._init_profile()
    
    def _init_performance_settings(self):
        """初始化性能相关设置"""
        settings = self.settings()
        
        # 启用硬件加速
        settings.setAttribute(QWebEngineSettings.WebAttribute.AcceleratedCompositingEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.GraphicsAccelerationEnabled, True)
        
        # 优化JavaScript
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, True)
        
        # 禁用不必要的功能
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.AllowRunningInsecureContent, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.AllowGeolocationOnInsecureOrigins, False)
        
        # 启用平滑滚动
        settings.setAttribute(QWebEngineSettings.WebAttribute.SmoothScrollingEnabled, True)
        
        # 启用触摸支持（针对触摸屏设备）
        settings.setAttribute(QWebEngineSettings.WebAttribute.TouchEnabled, True)
    
    def _init_profile(self):
        """初始化自定义配置文件"""
        # 创建持久化配置文件
        self._profile = QWebEngineProfile("hermes_profile")
        
        # 设置缓存大小（50MB）
        self._profile.setHttpCacheMaximumSize(50 * 1024 * 1024)
        
        # 设置缓存路径
        import os
        cache_path = os.path.join(os.path.expanduser("~"), ".hermes", "cache")
        os.makedirs(cache_path, exist_ok=True)
        self._profile.setCachePath(cache_path)
        
        # 设置存储路径
        storage_path = os.path.join(os.path.expanduser("~"), ".hermes", "storage")
        os.makedirs(storage_path, exist_ok=True)
        self._profile.setPersistentStoragePath(storage_path)
        
        # 启用离线Web应用支持
        self._profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        
        # 创建自定义页面
        page = QWebEnginePage(self._profile, self)
        self.setPage(page)
    
    def load_optimized(self, url):
        """优化的加载方法"""
        # 启用资源预加载
        self.page().profile().clearHttpCache()
        
        # 加载URL
        self.load(QUrl(url))
    
    def clear_cache(self):
        """清理缓存"""
        self._profile.clearHttpCache()
        self._profile.clearAllVisitedLinks()
    
    def get_memory_usage(self):
        """获取内存使用情况"""
        return {
            'cache_size': self._profile.httpCacheMaximumSize(),
            'storage_path': self._profile.persistentStoragePath()
        }