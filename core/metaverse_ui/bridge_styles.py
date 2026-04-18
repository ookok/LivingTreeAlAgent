"""
全息样式与动画系统 - 舰桥风格
提供科幻风格样式表、动画效果和视觉组件
"""

from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, Qt
from PyQt6.QtGui import QColor, QPalette, QFont, QPainter, QPen, QBrush, QLinearGradient
from PyQt6.QtWidgets import QGraphicsDropShadowEffect, QGraphicsBlurEffect
from PyQt6.QtCore import QObject, QRect, QSize, pyqtProperty, QPointF
import math

# ═══════════════════════════════════════════════════════════════════════════════
# 全息色彩方案
# ═══════════════════════════════════════════════════════════════════════════════

class HolographicColors:
    """全息色彩调色板"""
    
    # 基础色彩
    BACKGROUND_DEEP = "#050510"        # 深空背景
    BACKGROUND_MAIN = "#0a0a1a"       # 主背景
    BACKGROUND_PANEL = "#0d1025"       # 面板背景
    BACKGROUND_CARD = "#121530"        # 卡片背景
    
    # 全息蓝色系
    HOLO_PRIMARY = "#00d4ff"           # 主全息蓝
    HOLO_SECONDARY = "#0088cc"         # 次全息蓝
    HOLO_DIM = "#004466"               # 暗淡蓝
    HOLO_GLOW = "#00ffff"              # 发光青
    
    # 全息绿色系 (成功/在线)
    HOLO_GREEN = "#00ff88"
    HOLO_GREEN_DIM = "#00aa55"
    
    # 全息橙色系 (警告/外部)
    HOLO_ORANGE = "#ff8800"
    HOLO_ORANGE_DIM = "#aa5500"
    
    # 全息紫色系 (AI/特殊)
    HOLO_PURPLE = "#aa44ff"
    HOLO_PURPLE_DIM = "#6622aa"
    
    # 全息红色系 (错误/危险)
    HOLO_RED = "#ff3366"
    HOLO_RED_DIM = "#aa2244"
    
    # 全息金色系 (高价值/交易)
    HOLO_GOLD = "#ffd700"
    HOLO_GOLD_DIM = "#aa8800"
    
    # 文本色彩
    TEXT_PRIMARY = "#e0e8ff"           # 主文本
    TEXT_SECONDARY = "#8899bb"        # 次文本
    TEXT_DIM = "#445566"              # 暗淡文本
    
    # 边框
    BORDER_NORMAL = "#1a2a4a"
    BORDER_ACTIVE = "#00d4ff"
    BORDER_GLOW = "#00ffff44"


class HolographicFonts:
    """全息字体配置"""
    
    @staticmethod
    def get_font(size: int = 12, weight: int = QFont.Weight.Normal) -> QFont:
        font = QFont()
        font.setFamilies(["Microsoft YaHei UI", "Segoe UI", "SF Pro Display"])
        font.setPointSize(size)
        font.setWeight(weight)
        return font
    
    @staticmethod
    def mono_font(size: int = 11) -> QFont:
        font = QFont()
        font.setFamilies(["JetBrains Mono", "Consolas", "SF Mono"])
        font.setPointSize(size)
        return font


# ═══════════════════════════════════════════════════════════════════════════════
# 全息样式表
# ═══════════════════════════════════════════════════════════════════════════════

def get_bridge_stylesheet() -> str:
    """获取完整舰桥样式表"""
    return f"""
    /* ═══════════════════════════════════════════════════════════════════════
       舰桥指挥台 - 元宇宙UI样式表
       ═══════════════════════════════════════════════════════════════════════ */
    
    /* 全局样式 */
    QWidget {{
        background-color: {HolographicColors.BACKGROUND_MAIN};
        color: {HolographicColors.TEXT_PRIMARY};
        font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
    }}
    
    /* 主面板 */
    QFrame#BridgePanel {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {HolographicColors.BACKGROUND_PANEL},
            stop:1 {HolographicColors.BACKGROUND_DEEP});
        border: 1px solid {HolographicColors.BORDER_NORMAL};
        border-radius: 8px;
    }}
    
    /* 全息卡片 */
    QFrame#HoloCard {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 {HolographicColors.BACKGROUND_CARD}44,
            stop:0.5 {HolographicColors.BACKGROUND_CARD}66,
            stop:1 {HolographicColors.BACKGROUND_CARD}33);
        border: 1px solid {HolographicColors.BORDER_NORMAL};
        border-radius: 12px;
        padding: 8px;
    }}
    
    /* 全息卡片 - 悬停 */
    QFrame#HoloCard:hover {{
        border: 1px solid {HolographicColors.HOLO_PRIMARY};
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 {HolographicColors.HOLO_PRIMARY}11,
            stop:0.5 {HolographicColors.HOLO_PRIMARY}22,
            stop:1 {HolographicColors.HOLO_PRIMARY}11);
    }}
    
    /* 全息按钮 */
    QPushButton#HoloButton {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {HolographicColors.HOLO_PRIMARY}33,
            stop:1 {HolographicColors.HOLO_PRIMARY}11);
        border: 1px solid {HolographicColors.HOLO_PRIMARY};
        border-radius: 6px;
        color: {HolographicColors.HOLO_PRIMARY};
        padding: 8px 16px;
        font-weight: bold;
    }}
    
    QPushButton#HoloButton:hover {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {HolographicColors.HOLO_PRIMARY}66,
            stop:1 {HolographicColors.HOLO_PRIMARY}33);
        border: 1px solid {HolographicColors.HOLO_GLOW};
        color: {HolographicColors.HOLO_GLOW};
    }}
    
    QPushButton#HoloButton:pressed {{
        background: {HolographicColors.HOLO_PRIMARY}88;
    }}
    
    /* 次要按钮 */
    QPushButton#HoloButtonSecondary {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {HolographicColors.HOLO_SECONDARY}33,
            stop:1 {HolographicColors.HOLO_SECONDARY}11);
        border: 1px solid {HolographicColors.HOLO_SECONDARY};
        border-radius: 6px;
        color: {HolographicColors.HOLO_SECONDARY};
        padding: 8px 16px;
    }}
    
    /* 危险按钮 */
    QPushButton#HoloButtonDanger {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {HolographicColors.HOLO_RED}33,
            stop:1 {HolographicColors.HOLO_RED}11);
        border: 1px solid {HolographicColors.HOLO_RED};
        border-radius: 6px;
        color: {HolographicColors.HOLO_RED};
        padding: 8px 16px;
    }}
    
    /* 成功按钮 */
    QPushButton#HoloButtonSuccess {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {HolographicColors.HOLO_GREEN}33,
            stop:1 {HolographicColors.HOLO_GREEN}11);
        border: 1px solid {HolographicColors.HOLO_GREEN};
        border-radius: 6px;
        color: {HolographicColors.HOLO_GREEN};
        padding: 8px 16px;
    }}
    
    /* 全息标签 */
    QLabel#HoloLabel {{
        color: {HolographicColors.TEXT_PRIMARY};
        font-size: 14px;
    }}
    
    QLabel#HoloLabelTitle {{
        color: {HolographicColors.HOLO_PRIMARY};
        font-size: 18px;
        font-weight: bold;
    }}
    
    QLabel#HoloLabelDim {{
        color: {HolographicColors.TEXT_DIM};
        font-size: 12px;
    }}
    
    /* HUD数据标签 */
    QLabel#HUDLabel {{
        color: {HolographicColors.HOLO_GLOW};
        font-family: "JetBrains Mono", "Consolas", monospace;
        font-size: 12px;
        background: {HolographicColors.HOLO_PRIMARY}11;
        border: 1px solid {HolographicColors.HOLO_PRIMARY}44;
        border-radius: 4px;
        padding: 2px 6px;
    }}
    
    /* Tab标签 */
    QTabWidget::pane {{
        border: 1px solid {HolographicColors.BORDER_NORMAL};
        border-radius: 8px;
        background: {HolographicColors.BACKGROUND_PANEL};
    }}
    
    QTabBar::tab {{
        background: {HolographicColors.BACKGROUND_CARD};
        color: {HolographicColors.TEXT_SECONDARY};
        padding: 8px 16px;
        margin-right: 4px;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
    }}
    
    QTabBar::tab:selected {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 {HolographicColors.HOLO_PRIMARY}44,
            stop:1 {HolographicColors.BACKGROUND_PANEL});
        color: {HolographicColors.HOLO_PRIMARY};
        border-bottom: 2px solid {HolographicColors.HOLO_PRIMARY};
    }}
    
    QTabBar::tab:hover:!selected {{
        background: {HolographicColors.HOLO_PRIMARY}22;
        color: {HolographicColors.TEXT_PRIMARY};
    }}
    
    /* 输入框 */
    QLineEdit {{
        background: {HolographicColors.BACKGROUND_DEEP};
        border: 1px solid {HolographicColors.BORDER_NORMAL};
        border-radius: 6px;
        color: {HolographicColors.TEXT_PRIMARY};
        padding: 8px 12px;
        selection-background-color: {HolographicColors.HOLO_PRIMARY}66;
    }}
    
    QLineEdit:focus {{
        border: 1px solid {HolographicColors.HOLO_PRIMARY};
        background: {HolographicColors.HOLO_PRIMARY}11;
    }}
    
    /* 文本编辑 */
    QTextEdit, QPlainTextEdit {{
        background: {HolographicColors.BACKGROUND_DEEP};
        border: 1px solid {HolographicColors.BORDER_NORMAL};
        border-radius: 6px;
        color: {HolographicColors.TEXT_PRIMARY};
        selection-background-color: {HolographicColors.HOLO_PRIMARY}66;
    }}
    
    /* 滚动条 */
    QScrollBar:vertical {{
        background: {HolographicColors.BACKGROUND_DEEP};
        width: 8px;
        border-radius: 4px;
    }}
    
    QScrollBar::handle:vertical {{
        background: {HolographicColors.HOLO_PRIMARY}66;
        border-radius: 4px;
        min-height: 30px;
    }}
    
    QScrollBar::handle:vertical:hover {{
        background: {HolographicColors.HOLO_PRIMARY};
    }}
    
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    
    /* 分隔线 */
    QFrame#HDivider {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 transparent,
            stop:0.5 {HolographicColors.HOLO_PRIMARY}66,
            stop:1 transparent);
        max-height: 1px;
    }}
    
    QFrame#VDivider {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 transparent,
            stop:0.5 {HolographicColors.HOLO_PRIMARY}66,
            stop:1 transparent);
        max-width: 1px;
    }}
    
    /* 进度条 */
    QProgressBar {{
        background: {HolographicColors.BACKGROUND_DEEP};
        border: 1px solid {HolographicColors.BORDER_NORMAL};
        border-radius: 6px;
        height: 20px;
        text-align: center;
        color: {HolographicColors.TEXT_PRIMARY};
    }}
    
    QProgressBar::chunk {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 {HolographicColors.HOLO_PRIMARY},
            stop:1 {HolographicColors.HOLO_GLOW});
        border-radius: 5px;
    }}
    
    /* 滑块 */
    QSlider::groove:horizontal {{
        background: {HolographicColors.BACKGROUND_DEEP};
        height: 4px;
        border-radius: 2px;
        border: 1px solid {HolographicColors.BORDER_NORMAL};
    }}
    
    QSlider::handle:horizontal {{
        background: {HolographicColors.HOLO_PRIMARY};
        width: 14px;
        height: 14px;
        margin: -5px 0;
        border-radius: 7px;
        border: 2px solid {HolographicColors.HOLO_GLOW};
    }}
    
    QSlider::sub-page:horizontal {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 {HolographicColors.HOLO_PRIMARY},
            stop:1 {HolographicColors.HOLO_SECONDARY});
        border-radius: 2px;
    }}
    
    /* 列表 */
    QListWidget {{
        background: {HolographicColors.BACKGROUND_DEEP};
        border: 1px solid {HolographicColors.BORDER_NORMAL};
        border-radius: 6px;
        color: {HolographicColors.TEXT_PRIMARY};
        outline: none;
    }}
    
    QListWidget::item {{
        padding: 8px;
        border-bottom: 1px solid {HolographicColors.BORDER_NORMAL}44;
    }}
    
    QListWidget::item:selected {{
        background: {HolographicColors.HOLO_PRIMARY}33;
        color: {HolographicColors.HOLO_PRIMARY};
    }}
    
    QListWidget::item:hover:!selected {{
        background: {HolographicColors.HOLO_PRIMARY}22;
    }}
    
    /* 工具提示 */
    QToolTip {{
        background: {HolographicColors.BACKGROUND_CARD};
        border: 1px solid {HolographicColors.HOLO_PRIMARY};
        color: {HolographicColors.TEXT_PRIMARY};
        padding: 6px 10px;
        border-radius: 4px;
    }}
    
    /* 菜单 */
    QMenu {{
        background: {HolographicColors.BACKGROUND_PANEL};
        border: 1px solid {HolographicColors.BORDER_NORMAL};
        border-radius: 6px;
        padding: 4px;
    }}
    
    QMenu::item {{
        padding: 8px 24px;
        border-radius: 4px;
    }}
    
    QMenu::item:selected {{
        background: {HolographicColors.HOLO_PRIMARY}33;
        color: {HolographicColors.HOLO_PRIMARY};
    }}
    
    /* 状态指示器 */
    QLabel#StatusOnline {{
        color: {HolographicColors.HOLO_GREEN};
    }}
    
    QLabel#StatusOffline {{
        color: {HolographicColors.HOLO_RED};
    }}
    
    QLabel#StatusWarning {{
        color: {HolographicColors.HOLO_ORANGE};
    }}
    
    /* 脉冲动画效果 */
    @keyframes pulse {{
        0%, 100% {{ opacity: 1; }}
        50% {{ opacity: 0.5; }}
    }}
    
    /* 发光效果 */
    @keyframes glow {{
        0%, 100% {{ text-shadow: 0 0 5px {HolographicColors.HOLO_PRIMARY}; }}
        50% {{ text-shadow: 0 0 20px {HolographicColors.HOLO_PRIMARY}, 0 0 30px {HolographicColors.HOLO_GLOW}; }}
    }}
    """


# ═══════════════════════════════════════════════════════════════════════════════
# 全息动画效果
# ═══════════════════════════════════════════════════════════════════════════════

class HolographicPulseEffect(QObject):
    """脉冲发光效果"""
    
    def __init__(self, target, color: QColor = None):
        super().__init__()
        self.target = target
        self.color = color or QColor(HolographicColors.HOLO_PRIMARY)
        self._opacity = 1.0
        self._anim = QPropertyAnimation(self, b"opacity")
        self._anim.setDuration(1500)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.3)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._anim.setLoopCount(-1)  # 无限循环
    
    def start(self):
        self._anim.start()
    
    def stop(self):
        self._anim.stop()
    
    @pyqtProperty(float)
    def opacity(self) -> float:
        return self._opacity
    
    @opacity.setter
    def opacity(self, value: float):
        self._opacity = value
        # 应用到目标 (需要目标支持 setStyleSheet 或 alpha)
        if hasattr(self.target, 'setStyleSheet'):
            base = self.target.styleSheet()
            # 简化处理：透明度通过样式实现
            pass


class HolographicGlowAnimation:
    """全息发光动画"""
    
    @staticmethod
    def create_pulse_animation(target, duration: int = 1500) -> QPropertyAnimation:
        """创建脉冲动画"""
        anim = QPropertyAnimation(target, b"windowOpacity")
        anim.setDuration(duration)
        anim.setStartValue(1.0)
        anim.setEndValue(0.7)
        anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        anim.setLoopCount(-1)
        return anim
    
    @staticmethod
    def create_float_animation(target, property_name: bytes, start: float, end: float, duration: int = 2000) -> QPropertyAnimation:
        """创建浮动动画"""
        anim = QPropertyAnimation(target, property_name)
        anim.setDuration(duration)
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.setEasingCurve(QEasingCurve.Type.SineCurve)
        anim.setLoopCount(-1)
        return anim
    
    @staticmethod
    def create_glow_effect(color: QColor = None, blur_radius: int = 20) -> QGraphicsBlurEffect:
        """创建发光模糊效果"""
        glow = QGraphicsBlurEffect()
        glow.setBlurRadius(blur_radius)
        glow.setColor(color or QColor(HolographicColors.HOLO_PRIMARY))
        return glow
    
    @staticmethod
    def create_shadow_effect(color: QColor = None, offset: QPointF = None) -> QGraphicsDropShadowEffect:
        """创建阴影效果"""
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(color or QColor(HolographicColors.HOLO_PRIMARY))
        shadow.setOffset(offset or QPointF(0, 0))
        return shadow


# ═══════════════════════════════════════════════════════════════════════════════
# 全息绘图工具
# ═══════════════════════════════════════════════════════════════════════════════

class HolographicPainter:
    """全息绘图辅助类"""
    
    @staticmethod
    def draw_holographic_border(painter: QPainter, rect: QRect, color: QColor = None, width: int = 2):
        """绘制全息边框"""
        pen = QPen(color or QColor(HolographicColors.HOLO_PRIMARY), width)
        painter.setPen(pen)
        painter.drawRect(rect)
    
    @staticmethod
    def draw_glow_line(painter: QPainter, start: QPointF, end: QPointF, color: QColor = None, width: int = 2):
        """绘制发光线条"""
        # 外发光
        pen_glow = QPen(color or QColor(HolographicColors.HOLO_PRIMARY))
        pen_glow.setWidth(width + 4)
        pen_glow.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen_glow)
        painter.drawLine(start, end)
        
        # 内线
        pen_inner = QPen(color or QColor(HolographicColors.HOLO_GLOW))
        pen_inner.setWidth(width)
        pen_inner.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen_inner)
        painter.drawLine(start, end)
    
    @staticmethod
    def draw_holographic_circle(painter: QPainter, center: QPointF, radius: float, color: QColor = None):
        """绘制全息圆环"""
        color = color or QColor(HolographicColors.HOLO_PRIMARY)
        
        # 外发光
        pen_glow = QPen(color.lighter(200))
        pen_glow.setWidth(4)
        painter.setPen(pen_glow)
        painter.drawEllipse(center, radius, radius)
        
        # 主圆环
        pen_main = QPen(color)
        pen_main.setWidth(2)
        painter.setPen(pen_main)
        painter.drawEllipse(center, radius, radius)
        
        # 高光点
        brush = QBrush(color.lighter(150))
        painter.setBrush(brush)
        painter.drawEllipse(center, radius * 0.15, radius * 0.15)
    
    @staticmethod
    def draw_grid(painter: QPainter, rect: QRect, spacing: int = 40, color: QColor = None):
        """绘制全息网格"""
        color = color or QColor(HolographicColors.HOLO_PRIMARY)
        color.setAlpha(30)
        pen = QPen(color)
        pen.setWidth(1)
        painter.setPen(pen)
        
        # 垂直线
        for x in range(rect.left(), rect.right(), spacing):
            painter.drawLine(x, rect.top(), x, rect.bottom())
        
        # 水平线
        for y in range(rect.top(), rect.bottom(), spacing):
            painter.drawLine(rect.left(), y, rect.right(), y)


# ═══════════════════════════════════════════════════════════════════════════════
# 导航球样式
# ═══════════════════════════════════════════════════════════════════════════════

NAV_SPHERE_STYLESHEET = f"""
QFrame#NavSphere {{
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.8,
        stop:0 {HolographicColors.HOLO_PRIMARY}22,
        stop:0.5 {HolographicColors.HOLO_SECONDARY}11,
        stop:1 transparent);
    border: 2px solid {HolographicColors.HOLO_PRIMARY}66;
    border-radius: 50px;
}}

QLabel#NavSphereLabel {{
    color: {HolographicColors.HOLO_PRIMARY};
    font-size: 10px;
    font-weight: bold;
}}
"""


# ═══════════════════════════════════════════════════════════════════════════════
# 全息卡片组件
# ═══════════════════════════════════════════════════════════════════════════════

def create_holo_card_style(border_color: str = None, glow: bool = True) -> str:
    """创建动态全息卡片样式"""
    bc = border_color or HolographicColors.HOLO_PRIMARY
    glow_css = f"""
    box-shadow: 0 0 15px {bc}44, inset 0 0 20px {bc}11;
    """ if glow else ""
    
    return f"""
    QFrame {{
        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
            stop:0 {HolographicColors.BACKGROUND_CARD}aa,
            stop:0.3 {HolographicColors.BACKGROUND_CARD}cc,
            stop:0.7 {HolographicColors.BACKGROUND_PANEL}aa,
            stop:1 {HolographicColors.BACKGROUND_CARD}66);
        border: 1px solid {bc}66;
        border-radius: 12px;
        {glow_css}
    }}
    """


def create_pulse_animation_css(anim_id: str = "pulse", color: str = None) -> str:
    """创建脉冲动画CSS"""
    c = color or HolographicColors.HOLO_PRIMARY
    return f"""
    QFrame#{anim_id} {{
        animation: pulse 2s ease-in-out infinite;
    }}
    """


# ═══════════════════════════════════════════════════════════════════════════════
# 导出
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    'HolographicColors',
    'HolographicFonts',
    'HolographicPainter',
    'HolographicPulseEffect',
    'HolographicGlowAnimation',
    'get_bridge_stylesheet',
    'create_holo_card_style',
    'NAV_SPHERE_STYLESHEET',
]
