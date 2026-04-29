# -*- coding: utf-8 -*-
"""
LivingTree UI Functions Module

UI utility functions for PyDracula-based interface.
"""

# GLOBALS
GLOBAL_STATE = False
GLOBAL_TITLE_BAR = True

try:
    from PySide6.QtCore import QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, QTimer, Qt, QEvent
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QPushButton, QSizeGrip
except ImportError:
    from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, QTimer, Qt, QEvent
    from PyQt6.QtGui import QIcon
    from PyQt6.QtWidgets import QPushButton, QSizeGrip

from .ui_settings import Settings


class UIFunctions:
    """UI utility functions"""

    # MAXIMIZE/RESTORE
    @staticmethod
    def maximize_restore(window):
        global GLOBAL_STATE
        status = GLOBAL_STATE
        if status == False:
            window.showMaximized()
            GLOBAL_STATE = True
            window.ui.appMargins.setContentsMargins(0, 0, 0, 0)
            window.ui.maximizeRestoreAppBtn.setToolTip("Restore")
            window.ui.maximizeRestoreAppBtn.setIcon(QIcon(u":/icons/images/icons/icon_restore.png"))
            if hasattr(window, 'left_grip'):
                window.left_grip.hide()
                window.right_grip.hide()
                window.top_grip.hide()
                window.bottom_grip.hide()
        else:
            GLOBAL_STATE = False
            window.showNormal()
            window.resize(window.width()+1, window.height()+1)
            window.ui.appMargins.setContentsMargins(10, 10, 10, 10)
            window.ui.maximizeRestoreAppBtn.setToolTip("Maximize")
            window.ui.maximizeRestoreAppBtn.setIcon(QIcon(u":/icons/images/icons/icon_maximize.png"))
            if hasattr(window, 'left_grip'):
                window.left_grip.show()
                window.right_grip.show()
                window.top_grip.show()
                window.bottom_grip.show()

    @staticmethod
    def returnStatus():
        return GLOBAL_STATE

    @staticmethod
    def setStatus(status):
        global GLOBAL_STATE
        GLOBAL_STATE = status

    # TOGGLE MENU
    @staticmethod
    def toggleMenu(window, enable):
        if enable:
            width = window.ui.leftMenuBg.width()
            maxExtend = Settings.MENU_WIDTH
            standard = 60

            if width == 60:
                widthExtended = maxExtend
            else:
                widthExtended = standard

            animation = QPropertyAnimation(window.ui.leftMenuBg, b"minimumWidth")
            animation.setDuration(Settings.TIME_ANIMATION)
            animation.setStartValue(width)
            animation.setEndValue(widthExtended)
            animation.setEasingCurve(QEasingCurve.InOutQuart)
            animation.start()

    # TOGGLE LEFT BOX
    @staticmethod
    def toggleLeftBox(window, enable):
        if enable:
            width = window.ui.extraLeftBox.width()
            widthRightBox = window.ui.extraRightBox.width()
            maxExtend = Settings.LEFT_BOX_WIDTH
            color = Settings.BTN_LEFT_BOX_COLOR
            standard = 0

            style = window.ui.toggleLeftBox.styleSheet()

            if width == 0:
                widthExtended = maxExtend
                window.ui.toggleLeftBox.setStyleSheet(style + color)
                if widthRightBox != 0:
                    style = window.ui.settingsTopBtn.styleSheet()
                    window.ui.settingsTopBtn.setStyleSheet(style.replace(Settings.BTN_RIGHT_BOX_COLOR, ''))
            else:
                widthExtended = standard
                window.ui.toggleLeftBox.setStyleSheet(style.replace(color, ''))

        UIFunctions.start_box_animation(window, width, widthRightBox, "left")

    # TOGGLE RIGHT BOX
    @staticmethod
    def toggleRightBox(window, enable):
        if enable:
            width = window.ui.extraRightBox.width()
            widthLeftBox = window.ui.extraLeftBox.width()
            maxExtend = Settings.RIGHT_BOX_WIDTH
            color = Settings.BTN_RIGHT_BOX_COLOR
            standard = 0

            style = window.ui.settingsTopBtn.styleSheet()

            if width == 0:
                widthExtended = maxExtend
                window.ui.settingsTopBtn.setStyleSheet(style + color)
                if widthLeftBox != 0:
                    style = window.ui.toggleLeftBox.styleSheet()
                    window.ui.toggleLeftBox.setStyleSheet(style.replace(Settings.BTN_LEFT_BOX_COLOR, ''))
            else:
                widthExtended = standard
                window.ui.settingsTopBtn.setStyleSheet(style.replace(color, ''))

        UIFunctions.start_box_animation(window, widthLeftBox, width, "right")

    @staticmethod
    def start_box_animation(window, left_box_width, right_box_width, direction):
        right_width = 0
        left_width = 0

        if left_box_width == 0 and direction == "left":
            left_width = 240
        else:
            left_width = 0

        if right_box_width == 0 and direction == "right":
            right_width = 240
        else:
            right_width = 0

        left_box = QPropertyAnimation(window.ui.extraLeftBox, b"minimumWidth")
        left_box.setDuration(Settings.TIME_ANIMATION)
        left_box.setStartValue(left_box_width)
        left_box.setEndValue(left_width)
        left_box.setEasingCurve(QEasingCurve.InOutQuart)

        right_box = QPropertyAnimation(window.ui.extraRightBox, b"minimumWidth")
        right_box.setDuration(Settings.TIME_ANIMATION)
        right_box.setStartValue(right_box_width)
        right_box.setEndValue(right_width)
        right_box.setEasingCurve(QEasingCurve.InOutQuart)

        group = QParallelAnimationGroup()
        group.addAnimation(left_box)
        group.addAnimation(right_box)
        group.start()

    # SELECT/DESELECT MENU
    @staticmethod
    def selectMenu(getStyle, is_light=False):
        if is_light:
            select = getStyle + Settings.MENU_SELECTED_STYLESHEET_LIGHT
        else:
            select = getStyle + Settings.MENU_SELECTED_STYLESHEET
        return select

    @staticmethod
    def deselectMenu(getStyle, is_light=False):
        if is_light:
            deselect = getStyle.replace(Settings.MENU_SELECTED_STYLESHEET_LIGHT, "")
        else:
            deselect = getStyle.replace(Settings.MENU_SELECTED_STYLESHEET, "")
        return deselect

    @staticmethod
    def selectStandardMenu(window, widget, is_light=False):
        for w in window.ui.topMenu.findChildren(QPushButton):
            if w.objectName() == widget:
                w.setStyleSheet(UIFunctions.selectMenu(w.styleSheet(), is_light))

    @staticmethod
    def resetStyle(window, widget, is_light=False):
        for w in window.ui.topMenu.findChildren(QPushButton):
            if w.objectName() != widget:
                w.setStyleSheet(UIFunctions.deselectMenu(w.styleSheet(), is_light))

    # IMPORT THEMES FILES QSS/CSS
    @staticmethod
    def theme(window, file, useCustomTheme=True):
        if useCustomTheme:
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    content = f.read()
                window.ui.styleSheet.setStyleSheet(content)
            except Exception as e:
                print(f"Error loading theme: {e}")

    # START - GUI DEFINITIONS
    @staticmethod
    def uiDefinitions(window):
        def dobleClickMaximizeRestore(event):
            if event.type() == QEvent.MouseButtonDblClick:
                QTimer.singleShot(250, lambda: UIFunctions.maximize_restore(window))

        window.ui.titleRightInfo.mouseDoubleClickEvent = dobleClickMaximizeRestore

        if Settings.ENABLE_CUSTOM_TITLE_BAR:
            window.setWindowFlags(Qt.FramelessWindowHint)
            window.setAttribute(Qt.WA_TranslucentBackground)

            def moveWindow(event):
                if UIFunctions.returnStatus():
                    UIFunctions.maximize_restore(window)
                if event.buttons() == Qt.LeftButton:
                    window.move(window.pos() + event.globalPos() - window.dragPos)
                    window.dragPos = event.globalPos()
                    event.accept()

            window.ui.titleRightInfo.mouseMoveEvent = moveWindow

            # CUSTOM GRIPS
            try:
                from ..widgets.custom_grips.custom_grips import CustomGrip
                window.left_grip = CustomGrip(window, Qt.LeftEdge, True)
                window.right_grip = CustomGrip(window, Qt.RightEdge, True)
                window.top_grip = CustomGrip(window, Qt.TopEdge, True)
                window.bottom_grip = CustomGrip(window, Qt.BottomEdge, True)
            except ImportError:
                pass  # Custom grips not available

        else:
            window.ui.appMargins.setContentsMargins(0, 0, 0, 0)
            window.ui.minimizeAppBtn.hide()
            window.ui.maximizeRestoreAppBtn.hide()
            window.ui.closeAppBtn.hide()
            window.ui.frame_size_grip.hide()

        # DROP SHADOW
        try:
            from PySide6.QtWidgets import QGraphicsDropShadowEffect
            from PySide6.QtGui import QColor
            window.shadow = QGraphicsDropShadowEffect(window)
            window.shadow.setBlurRadius(17)
            window.shadow.setXOffset(0)
            window.shadow.setYOffset(0)
            window.shadow.setColor(QColor(0, 0, 0, 150))
            window.ui.bgApp.setGraphicsEffect(window.shadow)
        except ImportError:
            from PyQt6.QtWidgets import QGraphicsDropShadowEffect
            from PyQt6.QtGui import QColor
            window.shadow = QGraphicsDropShadowEffect(window)
            window.shadow.setBlurRadius(17)
            window.shadow.setXOffset(0)
            window.shadow.setYOffset(0)
            window.shadow.setColor(QColor(0, 0, 0, 150))
            window.ui.bgApp.setGraphicsEffect(window.shadow)

        # RESIZE WINDOW
        sizegrip = QSizeGrip(window.ui.frame_size_grip)
        sizegrip.setStyleSheet("width: 20px; height: 20px; margin 0px; padding: 0px;")

        # MINIMIZE
        window.ui.minimizeAppBtn.clicked.connect(lambda: window.showMinimized())

        # MAXIMIZE/RESTORE
        window.ui.maximizeRestoreAppBtn.clicked.connect(lambda: UIFunctions.maximize_restore(window))

        # CLOSE APPLICATION
        window.ui.closeAppBtn.clicked.connect(lambda: window.close())

    @staticmethod
    def resize_grips(window):
        if Settings.ENABLE_CUSTOM_TITLE_BAR and hasattr(window, 'left_grip'):
            window.left_grip.setGeometry(0, 10, 10, window.height())
            window.right_grip.setGeometry(window.width() - 10, 10, 10, window.height())
            window.top_grip.setGeometry(0, 0, window.width(), 10)
            window.bottom_grip.setGeometry(0, window.height() - 10, window.width(), 10)
