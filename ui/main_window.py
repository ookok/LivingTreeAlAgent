# -*- coding: utf-8 -*-
"""
LivingTree AI Agent - PyDracula Main Window

Main window with PyDracula theme support and LivingTree integration.
Business logic bindings for Chat, IDE, and Settings panels.
"""

import sys
import os
from pathlib import Path

# Qt imports with fallback
try:
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import (
        QMainWindow, QApplication, QWidget, QStackedWidget,
        QFrame, QVBoxLayout, QHBoxLayout, QGridLayout,
        QLabel, QPushButton, QLineEdit, QTextEdit,
        QScrollArea, QSlider, QCheckBox, QRadioButton,
        QComboBox, QTableWidget, QHeaderView, QPlainTextEdit,
        QGroupBox, QFormLayout, QSpinBox, QTabWidget
    )
    QT_BINDING = "PySide6"
except ImportError:
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtGui import QIcon
    from PyQt6.QtWidgets import (
        QMainWindow, QApplication, QWidget, QStackedWidget,
        QFrame, QVBoxLayout, QHBoxLayout, QGridLayout,
        QLabel, QPushButton, QLineEdit, QTextEdit,
        QScrollArea, QSlider, QCheckBox, QRadioButton,
        QComboBox, QTableWidget, QHeaderView, QPlainTextEdit,
        QGroupBox, QFormLayout, QSpinBox, QTabWidget
    )
    QT_BINDING = "PyQt6"

from .modules.ui_settings import Settings
from .modules.ui_functions import UIFunctions
from .theme_manager import get_theme_manager

# Enable High DPI
os.environ["QT_FONT_DPI"] = "96"


class Ui_MainWindow:
    """UI setup class - generated from Qt Designer"""

    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(1280, 720)
        MainWindow.setMinimumSize(940, 560)

        # Central widget
        self.styleSheet = QWidget(MainWindow)
        self.styleSheet.setObjectName("styleSheet")

        # Main layout
        self.appMargins = QVBoxLayout(self.styleSheet)
        self.appMargins.setSpacing(0)
        self.appMargins.setContentsMargins(10, 10, 10, 10)

        # Background frame
        self.bgApp = QFrame(self.styleSheet)
        self.bgApp.setObjectName("bgApp")
        self.bgApp.setFrameShape(QFrame.NoFrame)
        self.bgApp.setFrameShadow(QFrame.Raised)

        # App layout
        self.appLayout = QHBoxLayout(self.bgApp)
        self.appLayout.setSpacing(0)
        self.appLayout.setContentsMargins(0, 0, 0, 0)

        # LEFT MENU
        self._setup_left_menu()

        # CONTENT AREA
        self._setup_content_area()

        MainWindow.setCentralWidget(self.styleSheet)

        self.retranslateUi(MainWindow)

    def _setup_left_menu(self):
        """Setup left menu"""
        self.leftMenuBg = QFrame(self.bgApp)
        self.leftMenuBg.setObjectName("leftMenuBg")
        self.leftMenuBg.setMinimumSize(60, 0)
        self.leftMenuBg.setMaximumSize(60, 16777215)
        self.leftMenuBg.setFrameShape(QFrame.NoFrame)
        self.leftMenuBg.setFrameShadow(QFrame.Raised)

        leftMenuLayout = QVBoxLayout(self.leftMenuBg)
        leftMenuLayout.setSpacing(0)
        leftMenuLayout.setContentsMargins(0, 0, 0, 0)

        # Top logo area
        topLogoInfo = QFrame(self.leftMenuBg)
        topLogoInfo.setObjectName("topLogoInfo")
        topLogoInfo.setMinimumSize(0, 50)
        topLogoInfo.setMaximumSize(16777215, 50)

        self.titleLeftApp = QLabel(topLogoInfo)
        self.titleLeftApp.setObjectName("titleLeftApp")
        self.titleLeftApp.setText("LivingTree")
        self.titleLeftApp.setGeometry(10, 8, 160, 20)

        self.titleLeftDescription = QLabel(topLogoInfo)
        self.titleLeftDescription.setObjectName("titleLeftDescription")
        self.titleLeftDescription.setText("AI Agent")
        self.titleLeftDescription.setGeometry(10, 27, 160, 16)

        leftMenuLayout.addWidget(topLogoInfo)

        # Menu frame
        leftMenuFrame = QFrame(self.leftMenuBg)
        leftMenuFrame.setObjectName("leftMenuFrame")
        leftMenuFrame.setFrameShape(QFrame.NoFrame)

        menuLayout = QVBoxLayout(leftMenuFrame)
        menuLayout.setSpacing(0)
        menuLayout.setContentsMargins(0, 0, 0, 0)

        # Toggle button
        toggleBox = QFrame(leftMenuFrame)
        toggleBox.setObjectName("toggleBox")
        toggleBox.setMaximumSize(16777215, 45)

        self.toggleButton = QPushButton(toggleBox)
        self.toggleButton.setObjectName("toggleButton")
        self.toggleButton.setMinimumSize(0, 45)
        self.toggleButton.setCursor(Qt.PointingHandCursor)
        self.toggleButton.setText("Menu")

        toggleLayout = QVBoxLayout(toggleBox)
        toggleLayout.setSpacing(0)
        toggleLayout.setContentsMargins(0, 0, 0, 0)
        toggleLayout.addWidget(self.toggleButton)

        menuLayout.addWidget(toggleBox)

        # Top menu buttons
        self.topMenu = QFrame(leftMenuFrame)
        self.topMenu.setObjectName("topMenu")
        self.topMenu.setFrameShape(QFrame.NoFrame)

        topMenuLayout = QVBoxLayout(self.topMenu)
        topMenuLayout.setSpacing(0)
        topMenuLayout.setContentsMargins(0, 0, 0, 0)

        self.btn_home = self._create_menu_button("Home", objectName="btn_home")
        self.btn_chat = self._create_menu_button("Chat", objectName="btn_chat")
        self.btn_ide = self._create_menu_button("IDE", objectName="btn_ide")
        self.btn_knowledge = self._create_menu_button("Knowledge", objectName="btn_knowledge")
        self.btn_tools = self._create_menu_button("Tools", objectName="btn_tools")
        self.btn_user_settings = self._create_menu_button("User", objectName="btn_user_settings")
        self.btn_system_settings = self._create_menu_button("System", objectName="btn_system_settings")

        topMenuLayout.addWidget(self.btn_home)
        topMenuLayout.addWidget(self.btn_chat)
        topMenuLayout.addWidget(self.btn_ide)
        topMenuLayout.addWidget(self.btn_knowledge)
        topMenuLayout.addWidget(self.btn_tools)
        topMenuLayout.addWidget(self.btn_user_settings)
        topMenuLayout.addWidget(self.btn_system_settings)

        menuLayout.addWidget(self.topMenu, 0, Qt.AlignTop)

        # Bottom menu
        self.bottomMenu = QFrame(leftMenuFrame)
        self.bottomMenu.setObjectName("bottomMenu")
        self.bottomMenu.setFrameShape(QFrame.NoFrame)

        bottomMenuLayout = QVBoxLayout(self.bottomMenu)
        bottomMenuLayout.setSpacing(0)
        bottomMenuLayout.setContentsMargins(0, 0, 0, 0)

        self.btn_theme = self._create_menu_button("Theme", objectName="btn_theme")

        bottomMenuLayout.addWidget(self.btn_theme)

        menuLayout.addWidget(self.bottomMenu, 0, Qt.AlignBottom)

        leftMenuLayout.addWidget(leftMenuFrame)
        self.appLayout.addWidget(self.leftMenuBg)

        # Extra left box (hidden by default)
        self.extraLeftBox = QFrame(self.bgApp)
        self.extraLeftBox.setObjectName("extraLeftBox")
        self.extraLeftBox.setMinimumSize(0, 0)
        self.extraLeftBox.setMaximumSize(0, 16777215)
        self.extraLeftBox.setFrameShape(QFrame.NoFrame)
        self.appLayout.addWidget(self.extraLeftBox)

    def _create_menu_button(self, text, objectName=None):
        """Create a menu button"""
        btn = QPushButton(self.topMenu)
        if objectName:
            btn.setObjectName(objectName)
        btn.setMinimumSize(0, 45)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setText(text)
        return btn

    def _setup_content_area(self):
        """Setup main content area"""
        self.contentBox = QFrame(self.bgApp)
        self.contentBox.setObjectName("contentBox")
        self.contentBox.setFrameShape(QFrame.NoFrame)

        contentLayout = QVBoxLayout(self.contentBox)
        contentLayout.setSpacing(0)
        contentLayout.setContentsMargins(0, 0, 0, 0)

        # Top bar
        self._setup_top_bar(contentLayout)

        # Content bottom
        self.contentBottom = QFrame(self.contentBox)
        self.contentBottom.setObjectName("contentBottom")
        self.contentBottom.setFrameShape(QFrame.NoFrame)

        bottomLayout = QVBoxLayout(self.contentBottom)
        bottomLayout.setSpacing(0)
        bottomLayout.setContentsMargins(0, 0, 0, 0)

        # Main content area
        self._setup_main_content(bottomLayout)

        # Bottom bar
        self._setup_bottom_bar(bottomLayout)

        contentLayout.addWidget(self.contentBottom)
        self.appLayout.addWidget(self.contentBox)

    def _setup_top_bar(self, parentLayout):
        """Setup top bar with title and buttons"""
        self.contentTopBg = QFrame(self.contentBox)
        self.contentTopBg.setObjectName("contentTopBg")
        self.contentTopBg.setMinimumSize(0, 50)
        self.contentTopBg.setMaximumSize(16777215, 50)
        self.contentTopBg.setFrameShape(QFrame.NoFrame)

        topLayout = QHBoxLayout(self.contentTopBg)
        topLayout.setSpacing(0)
        topLayout.setContentsMargins(0, 0, 10, 0)

        # Title
        leftBox = QFrame(self.contentTopBg)
        leftBox.setObjectName("leftBox")

        leftLayout = QHBoxLayout(leftBox)
        leftLayout.setSpacing(0)
        leftLayout.setContentsMargins(0, 0, 0, 0)

        self.titleRightInfo = QLabel(leftBox)
        self.titleRightInfo.setObjectName("titleRightInfo")
        self.titleRightInfo.setText("LivingTree AI Agent")
        leftLayout.addWidget(self.titleRightInfo)

        topLayout.addWidget(leftBox)

        # Right buttons
        self.rightButtons = QFrame(self.contentTopBg)
        self.rightButtons.setObjectName("rightButtons")
        self.rightButtons.setMinimumSize(0, 28)

        rightLayout = QHBoxLayout(self.rightButtons)
        rightLayout.setSpacing(5)
        rightLayout.setContentsMargins(0, 0, 0, 0)

        self.settingsTopBtn = QPushButton(self.rightButtons)
        self.settingsTopBtn.setObjectName("settingsTopBtn")
        self.settingsTopBtn.setMinimumSize(28, 28)
        self.settingsTopBtn.setMaximumSize(28, 28)
        self.settingsTopBtn.setCursor(Qt.PointingHandCursor)
        self.settingsTopBtn.setText("")

        self.minimizeAppBtn = QPushButton(self.rightButtons)
        self.minimizeAppBtn.setObjectName("minimizeAppBtn")
        self.minimizeAppBtn.setMinimumSize(28, 28)
        self.minimizeAppBtn.setMaximumSize(28, 28)
        self.minimizeAppBtn.setCursor(Qt.PointingHandCursor)
        self.minimizeAppBtn.setText("")

        self.maximizeRestoreAppBtn = QPushButton(self.rightButtons)
        self.maximizeRestoreAppBtn.setObjectName("maximizeRestoreAppBtn")
        self.maximizeRestoreAppBtn.setMinimumSize(28, 28)
        self.maximizeRestoreAppBtn.setMaximumSize(28, 28)
        self.maximizeRestoreAppBtn.setCursor(Qt.PointingHandCursor)
        self.maximizeRestoreAppBtn.setText("")

        self.closeAppBtn = QPushButton(self.rightButtons)
        self.closeAppBtn.setObjectName("closeAppBtn")
        self.closeAppBtn.setMinimumSize(28, 28)
        self.closeAppBtn.setMaximumSize(28, 28)
        self.closeAppBtn.setCursor(Qt.PointingHandCursor)
        self.closeAppBtn.setText("")

        rightLayout.addWidget(self.settingsTopBtn)
        rightLayout.addWidget(self.minimizeAppBtn)
        rightLayout.addWidget(self.maximizeRestoreAppBtn)
        rightLayout.addWidget(self.closeAppBtn)

        topLayout.addWidget(self.rightButtons, 0, Qt.AlignRight)
        parentLayout.addWidget(self.contentTopBg)

    def _setup_main_content(self, parentLayout):
        """Setup main content pages"""
        contentFrame = QFrame(self.contentBottom)
        contentFrame.setObjectName("content")
        contentFrame.setFrameShape(QFrame.NoFrame)

        contentLayout = QHBoxLayout(contentFrame)
        contentLayout.setSpacing(0)
        contentLayout.setContentsMargins(0, 0, 0, 0)

        # Pages container
        pagesContainer = QFrame(contentFrame)
        pagesContainer.setObjectName("pagesContainer")
        pagesContainer.setFrameShape(QFrame.NoFrame)

        pagesLayout = QVBoxLayout(pagesContainer)
        pagesLayout.setSpacing(0)
        pagesLayout.setContentsMargins(10, 10, 10, 10)

        self.stackedWidget = QStackedWidget(pagesContainer)
        self.stackedWidget.setObjectName("stackedWidget")

        # Home page
        self.home = self._create_home_page()
        self.stackedWidget.addWidget(self.home)

        # Chat page
        self.chat = self._create_chat_page()
        self.stackedWidget.addWidget(self.chat)

        # IDE page
        self.ide = self._create_ide_page()
        self.stackedWidget.addWidget(self.ide)

        # Knowledge page
        self.knowledge = self._create_knowledge_page()
        self.stackedWidget.addWidget(self.knowledge)

        # Tools page
        self.tools = self._create_tools_page()
        self.stackedWidget.addWidget(self.tools)

        # User Settings page
        self.user_settings = self._create_user_settings_page()
        self.stackedWidget.addWidget(self.user_settings)

        # System Settings page
        self.system_settings = self._create_system_settings_page()
        self.stackedWidget.addWidget(self.system_settings)

        pagesLayout.addWidget(self.stackedWidget)
        contentLayout.addWidget(pagesContainer)

        # Extra right box (hidden by default)
        self.extraRightBox = QFrame(contentFrame)
        self.extraRightBox.setObjectName("extraRightBox")
        self.extraRightBox.setMinimumSize(0, 0)
        self.extraRightBox.setMaximumSize(0, 16777215)
        self.extraRightBox.setFrameShape(QFrame.NoFrame)

        # Theme settings panel
        self._setup_theme_panel()

        contentLayout.addWidget(self.extraRightBox)
        parentLayout.addWidget(contentFrame)

    def _create_home_page(self):
        """Create home page"""
        home = QWidget()
        homeLayout = QVBoxLayout(home)

        welcome = QLabel(home)
        welcome.setText("Welcome to LivingTree AI Agent")
        welcome.setAlignment(Qt.AlignCenter)
        homeLayout.addWidget(welcome)

        desc = QLabel(home)
        desc.setText("A modern AI agent framework with PyDracula UI")
        desc.setAlignment(Qt.AlignCenter)
        homeLayout.addWidget(desc)

        homeLayout.addStretch()
        return home

    def _create_chat_page(self):
        """Create chat page"""
        chat = QWidget()
        chatLayout = QVBoxLayout(chat)

        self.chatInput = QLineEdit(chat)
        self.chatInput.setPlaceholderText("Type your message here...")
        chatLayout.addWidget(self.chatInput)

        self.chatOutput = QTextEdit(chat)
        self.chatOutput.setReadOnly(True)
        chatLayout.addWidget(self.chatOutput)

        self.sendBtn = QPushButton("Send", chat)
        chatLayout.addWidget(self.sendBtn)

        return chat

    def _create_ide_page(self):
        """Create IDE page with code editor"""
        page = QWidget()
        mainLayout = QVBoxLayout(page)

        # Header with language selector
        headerFrame = QFrame(page)
        headerLayout = QHBoxLayout(headerFrame)

        title = QLabel("💻 AI Code Editor")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        headerLayout.addWidget(title)

        headerLayout.addStretch()

        # Language selector
        langLabel = QLabel("Language:")
        headerLayout.addWidget(langLabel)

        self.ideLanguageCombo = QComboBox(headerFrame)
        self.ideLanguageCombo.addItems(["Python", "JavaScript", "TypeScript", "Java", "Go", "Rust", "C++", "HTML", "CSS"])
        headerLayout.addWidget(self.ideLanguageCombo)

        # Button frame
        btnFrame = QFrame(headerFrame)
        btnLayout = QHBoxLayout(btnFrame)
        btnLayout.setSpacing(5)

        self.btnIdeGenerate = QPushButton("✨ Generate", btnFrame)
        self.btnIdeExecute = QPushButton("▶ Run", btnFrame)
        self.btnIdeExplain = QPushButton("📖 Explain", btnFrame)
        self.btnIdeClear = QPushButton("🗑️ Clear", btnFrame)

        btnLayout.addWidget(self.btnIdeGenerate)
        btnLayout.addWidget(self.btnIdeExecute)
        btnLayout.addWidget(self.btnIdeExplain)
        btnLayout.addWidget(self.btnIdeClear)

        headerLayout.addWidget(btnFrame)
        mainLayout.addWidget(headerFrame)

        # Code editor area
        self.ideEditor = QPlainTextEdit(page)
        self.ideEditor.setPlaceholderText("# Write your code here or describe what you want to build...\n\n# Example: Create a function to calculate fibonacci numbers")
        mainLayout.addWidget(self.ideEditor)

        # Output area
        outputLabel = QLabel("Output:")
        mainLayout.addWidget(outputLabel)

        self.ideOutput = QTextEdit(page)
        self.ideOutput.setReadOnly(True)
        self.ideOutput.setMaximumHeight(150)
        self.ideOutput.setPlaceholderText("Execution results will appear here...")
        mainLayout.addWidget(self.ideOutput)

        # Status bar
        self.ideStatus = QLabel("Ready")
        self.ideStatus.setStyleSheet("color: gray; padding: 2px;")
        mainLayout.addWidget(self.ideStatus)

        return page

    def _create_user_settings_page(self):
        """Create user settings page"""
        page = QWidget()
        mainLayout = QVBoxLayout(page)

        # Header
        header = QLabel("👤 User Settings")
        header.setStyleSheet("font-size: 18px; font-weight: bold; padding: 10px;")
        mainLayout.addWidget(header)

        # Scroll area for settings
        scroll = QScrollArea(page)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        content = QWidget()
        contentLayout = QVBoxLayout(content)

        # Appearance section
        appearanceGroup = QGroupBox("🎨 Appearance", content)
        appearanceLayout = QFormLayout(appearanceGroup)

        self.userThemeCombo = QComboBox()
        self.userThemeCombo.addItems(["Dark", "Light", "Follow System"])
        appearanceLayout.addRow("Theme:", self.userThemeCombo)

        self.userFontSize = QSpinBox()
        self.userFontSize.setRange(10, 24)
        self.userFontSize.setValue(14)
        appearanceLayout.addRow("Font Size:", self.userFontSize)

        self.userLangCombo = QComboBox()
        self.userLangCombo.addItems(["中文", "English"])
        appearanceLayout.addRow("Language:", self.userLangCombo)

        contentLayout.addWidget(appearanceGroup)

        # Chat section
        chatGroup = QGroupBox("💬 Chat", content)
        chatLayout = QFormLayout(chatGroup)

        self.chatAutoSave = QCheckBox()
        self.chatAutoSave.setChecked(True)
        chatLayout.addRow("Auto-save Chat:", self.chatAutoSave)

        self.chatShowTime = QCheckBox()
        self.chatShowTime.setChecked(True)
        chatLayout.addRow("Show Timestamps:", self.chatShowTime)

        self.chatMaxHistory = QSpinBox()
        self.chatMaxHistory.setRange(100, 10000)
        self.chatMaxHistory.setSingleStep(100)
        self.chatMaxHistory.setValue(1000)
        chatLayout.addRow("Max History:", self.chatMaxHistory)

        contentLayout.addWidget(chatGroup)

        # Notifications section
        notifGroup = QGroupBox("🔔 Notifications", content)
        notifLayout = QFormLayout(notifGroup)

        self.notifEnabled = QCheckBox()
        self.notifEnabled.setChecked(True)
        notifLayout.addRow("Enable:", self.notifEnabled)

        self.notifSound = QCheckBox()
        self.notifSound.setChecked(True)
        notifLayout.addRow("Sound:", self.notifSound)

        contentLayout.addWidget(notifGroup)

        # Buttons
        btnFrame = QFrame(content)
        btnLayout = QHBoxLayout(btnFrame)
        btnLayout.addStretch()

        self.btnSaveUserSettings = QPushButton("💾 Save", btnFrame)
        self.btnResetUserSettings = QPushButton("🔄 Reset", btnFrame)

        btnLayout.addWidget(self.btnSaveUserSettings)
        btnLayout.addWidget(self.btnResetUserSettings)
        contentLayout.addWidget(btnFrame)

        contentLayout.addStretch()
        scroll.setWidget(content)
        mainLayout.addWidget(scroll)

        return page

    def _create_system_settings_page(self):
        """Create system settings page"""
        page = QWidget()
        mainLayout = QVBoxLayout(page)

        # Header
        header = QLabel("⚙️ System Settings")
        header.setStyleSheet("font-size: 18px; font-weight: bold; padding: 10px;")
        mainLayout.addWidget(header)

        # Tab widget for system settings
        tabs = QTabWidget(page)

        # Ollama tab
        ollamaTab = QWidget()
        ollamaLayout = QFormLayout(ollamaTab)

        self.ollamaUrl = QLineEdit()
        self.ollamaUrl.setText("http://localhost:11434")
        ollamaLayout.addRow("Ollama URL:", self.ollamaUrl)

        self.ollamaDefaultModel = QLineEdit()
        self.ollamaDefaultModel.setPlaceholderText("qwen2.5:7b")
        ollamaLayout.addRow("Default Model:", self.ollamaDefaultModel)

        self.ollamaKeepAlive = QSpinBox()
        self.ollamaKeepAlive.setRange(1, 60)
        self.ollamaKeepAlive.setValue(5)
        self.ollamaKeepAlive.setSuffix(" min")
        ollamaLayout.addRow("Keep Alive:", self.ollamaKeepAlive)

        tabs.addTab(ollamaTab, "🤖 Ollama")

        # Agent tab
        agentTab = QWidget()
        agentLayout = QFormLayout(agentTab)

        self.agentMaxIterations = QSpinBox()
        self.agentMaxIterations.setRange(1, 200)
        self.agentMaxIterations.setValue(90)
        agentLayout.addRow("Max Iterations:", self.agentMaxIterations)

        self.agentTemperature = QSlider(Qt.Horizontal)
        self.agentTemperature.setRange(0, 100)
        self.agentTemperature.setValue(70)
        agentLayout.addRow("Temperature:", self.agentTemperature)

        self.agentStreaming = QCheckBox()
        self.agentStreaming.setChecked(True)
        agentLayout.addRow("Streaming:", self.agentStreaming)

        tabs.addTab(agentTab, "🧠 Agent")

        # Search tab
        searchTab = QWidget()
        searchLayout = QFormLayout(searchTab)

        self.searchCacheTtl = QSpinBox()
        self.searchCacheTtl.setRange(10, 1440)
        self.searchCacheTtl.setValue(60)
        self.searchCacheTtl.setSuffix(" min")
        searchLayout.addRow("Cache TTL:", self.searchCacheTtl)

        self.serperKey = QLineEdit()
        self.serperKey.setPlaceholderText("Optional")
        searchLayout.addRow("Serper API Key:", self.serperKey)

        tabs.addTab(searchTab, "🔍 Search")

        # Storage tab
        storageTab = QWidget()
        storageLayout = QFormLayout(storageTab)

        self.modelsDir = QLineEdit()
        self.modelsDir.setPlaceholderText("Leave empty for default")
        storageLayout.addRow("Models Directory:", self.modelsDir)

        tabs.addTab(storageTab, "💾 Storage")

        mainLayout.addWidget(tabs)

        # Buttons
        btnFrame = QFrame(page)
        btnLayout = QHBoxLayout(btnFrame)
        btnLayout.addStretch()

        self.btnSaveSystemSettings = QPushButton("💾 Save", btnFrame)
        self.btnResetSystemSettings = QPushButton("🔄 Reset", btnFrame)

        btnLayout.addWidget(self.btnSaveSystemSettings)
        btnLayout.addWidget(self.btnResetSystemSettings)
        mainLayout.addWidget(btnFrame)

        return page

    def _setup_theme_panel(self):
        """Setup theme settings panel"""
        rightLayout = QVBoxLayout(self.extraRightBox)
        rightLayout.setSpacing(0)
        rightLayout.setContentsMargins(0, 0, 0, 0)

        # Theme detail bar
        themeDetail = QFrame(self.extraRightBox)
        themeDetail.setObjectName("themeSettingsTopDetail")
        themeDetail.setMaximumSize(16777215, 3)
        rightLayout.addWidget(themeDetail)

        # Content settings
        contentSettings = QFrame(self.extraRightBox)
        contentSettings.setObjectName("contentSettings")
        contentSettings.setFrameShape(QFrame.NoFrame)

        settingsLayout = QVBoxLayout(contentSettings)
        settingsLayout.setSpacing(0)
        settingsLayout.setContentsMargins(0, 0, 0, 0)

        # Theme buttons
        topMenus = QFrame(contentSettings)
        topMenus.setObjectName("topMenus")

        menusLayout = QVBoxLayout(topMenus)
        menusLayout.setSpacing(0)
        menusLayout.setContentsMargins(0, 0, 0, 0)

        self.btn_light_theme = QPushButton("Light Theme", topMenus)
        self.btn_light_theme.setObjectName("btn_light_theme")
        self.btn_light_theme.setMinimumSize(0, 45)
        self.btn_light_theme.setCursor(Qt.PointingHandCursor)

        self.btn_dark_theme = QPushButton("Dark Theme", topMenus)
        self.btn_dark_theme.setObjectName("btn_dark_theme")
        self.btn_dark_theme.setMinimumSize(0, 45)
        self.btn_dark_theme.setCursor(Qt.PointingHandCursor)

        menusLayout.addWidget(self.btn_light_theme)
        menusLayout.addWidget(self.btn_dark_theme)

        settingsLayout.addWidget(topMenus, 0, Qt.AlignTop)
        rightLayout.addWidget(contentSettings)

    def _setup_bottom_bar(self, parentLayout):
        """Setup bottom bar"""
        self.bottomBar = QFrame(self.contentBottom)
        self.bottomBar.setObjectName("bottomBar")
        self.bottomBar.setMinimumSize(0, 22)
        self.bottomBar.setMaximumSize(16777215, 22)
        self.bottomBar.setFrameShape(QFrame.NoFrame)

        bottomLayout = QHBoxLayout(self.bottomBar)
        bottomLayout.setSpacing(0)
        bottomLayout.setContentsMargins(0, 0, 0, 0)

        self.creditsLabel = QLabel(self.bottomBar)
        self.creditsLabel.setObjectName("creditsLabel")
        self.creditsLabel.setText("LivingTree AI Agent")

        self.version = QLabel(self.bottomBar)
        self.version.setObjectName("version")
        self.version.setText("v1.0.0")

        self.frame_size_grip = QFrame(self.bottomBar)
        self.frame_size_grip.setObjectName("frame_size_grip")
        self.frame_size_grip.setMinimumSize(20, 0)
        self.frame_size_grip.setMaximumSize(20, 16777215)

        bottomLayout.addWidget(self.creditsLabel)
        bottomLayout.addWidget(self.version)
        bottomLayout.addWidget(self.frame_size_grip)

        parentLayout.addWidget(self.bottomBar)

    def retranslateUi(self, MainWindow):
        """Translate UI texts"""
        MainWindow.setWindowTitle("LivingTree AI Agent")
        self.titleLeftApp.setText("LivingTree")
        self.titleLeftDescription.setText("AI Agent v1.0")
        self.toggleButton.setText("Menu")
        self.btn_home.setText("Home")
        self.btn_chat.setText("Chat")
        self.btn_ide.setText("IDE")
        self.btn_knowledge.setText("Knowledge")
        self.btn_tools.setText("Tools")
        self.btn_user_settings.setText("User")
        self.btn_system_settings.setText("System")
        self.titleRightInfo.setText("LivingTree AI Agent")
        self.btn_theme.setText("Theme")
        self.btn_light_theme.setText("Light Theme")
        self.btn_dark_theme.setText("Dark Theme")
        self.creditsLabel.setText("LivingTree AI Agent")
        self.version.setText("v1.0.0")


class MainWindow(QMainWindow):
    """LivingTree Main Window with PyDracula Theme"""

    def __init__(self):
        super().__init__()

        # Setup UI
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # Theme manager
        self.theme_manager = get_theme_manager()

        # Business logic bindings
        self._bindings_initialized = False

        # Apply default theme (light)
        self._apply_theme()

        # Connect signals
        self._connect_signals()

        # Initialize bindings after UI is ready
        QTimer.singleShot(100, self._initialize_bindings)

        # Show window
        self.show()

    def _initialize_bindings(self):
        """Initialize business logic bindings"""
        if self._bindings_initialized:
            return

        try:
            from .bindings import ChatBinding, IDEBinding, SettingsBinding

            # Chat binding
            self.chat_binding = ChatBinding(self)
            self.chat_binding.bind_ui(
                self.ui.chatInput,
                self.ui.chatOutput,
                self.ui.sendBtn
            )
            self.chat_binding.initialize()
            self.chat_binding.message_received.connect(self._on_chat_message_received)

            # IDE binding
            self.ide_binding = IDEBinding(self)
            self.ide_binding.bind_ui(
                self.ui.ideEditor,
                self.ui.ideOutput,
                self.ui.ideStatus
            )
            self.ide_binding.initialize()
            self.ide_binding.code_generated.connect(self._on_code_generated)
            self.ide_binding.execution_result.connect(self._on_execution_result)
            self.ide_binding.error_occurred.connect(self._on_ide_error)

            # Settings binding
            self.settings_binding = SettingsBinding(self)
            self.settings_binding.initialize()

            # Connect IDE buttons
            self.ui.btnIdeGenerate.clicked.connect(self._on_ide_generate)
            self.ui.btnIdeExecute.clicked.connect(self._on_ide_execute)
            self.ui.btnIdeExplain.clicked.connect(self._on_ide_explain)
            self.ui.btnIdeClear.clicked.connect(self._on_ide_clear)
            self.ui.ideLanguageCombo.currentTextChanged.connect(self._on_language_changed)

            # Connect user settings buttons
            self.ui.btnSaveUserSettings.clicked.connect(self._on_save_user_settings)
            self.ui.btnResetUserSettings.clicked.connect(self._on_reset_user_settings)

            # Connect system settings buttons
            self.ui.btnSaveSystemSettings.clicked.connect(self._on_save_system_settings)
            self.ui.btnResetSystemSettings.clicked.connect(self._on_reset_system_settings)

            # User theme changes
            self.ui.userThemeCombo.currentIndexChanged.connect(self._on_user_theme_changed)

            self._bindings_initialized = True
            print("[MainWindow] Business bindings initialized")

        except Exception as e:
            print(f"[MainWindow] Binding initialization error: {e}")
            import traceback
            traceback.print_exc()

    def _apply_theme(self):
        """Apply current theme"""
        is_light = self.theme_manager.is_light
        self.theme_manager.apply_theme(self.ui.styleSheet)

        # Update menu styles
        self.theme_manager.on_theme_changed(self._on_theme_changed)

    def _on_theme_changed(self, is_light: bool):
        """Handle theme change"""
        self.theme_manager.apply_theme(self.ui.styleSheet)

    def _connect_signals(self):
        """Connect UI signals"""
        # Toggle menu
        self.ui.toggleButton.clicked.connect(lambda: UIFunctions.toggleMenu(self, True))

        # Menu buttons
        self.ui.btn_home.clicked.connect(lambda: self._show_page("home"))
        self.ui.btn_chat.clicked.connect(lambda: self._show_page("chat"))
        self.ui.btn_ide.clicked.connect(lambda: self._show_page("ide"))
        self.ui.btn_knowledge.clicked.connect(lambda: self._show_page("knowledge"))
        self.ui.btn_tools.clicked.connect(lambda: self._show_page("tools"))
        self.ui.btn_user_settings.clicked.connect(lambda: self._show_page("user_settings"))
        self.ui.btn_system_settings.clicked.connect(lambda: self._show_page("system_settings"))

        # Theme buttons
        self.ui.btn_light_theme.clicked.connect(lambda: self._set_theme("light"))
        self.ui.btn_dark_theme.clicked.connect(lambda: self._set_theme("dark"))
        self.ui.btn_theme.clicked.connect(self._toggle_theme)

        # Settings top button
        self.ui.settingsTopBtn.clicked.connect(lambda: UIFunctions.toggleRightBox(self, True))

        # UI definitions
        UIFunctions.uiDefinitions(self)

        # Legacy theme combo (keep for compatibility)
        self.themeToggle = self.ui.userThemeCombo  # Alias for compatibility
        if hasattr(self.ui, 'themeToggle'):
            self.ui.themeToggle.currentIndexChanged.connect(
                lambda idx: self._set_theme(self.ui.themeToggle.currentData() if hasattr(self.ui.themeToggle, 'currentData') else "dark")
            )

        # Set initial theme
        current_theme = "dark" if self.theme_manager.is_dark else "light"
        if hasattr(self.ui, 'themeToggle') and hasattr(self.ui.themeToggle, 'findData'):
            idx = self.ui.themeToggle.findData(current_theme)
            if idx >= 0:
                self.ui.themeToggle.setCurrentIndex(idx)

    def _show_page(self, page_name: str):
        """Show a specific page"""
        pages = {
            "home": self.ui.home,
            "chat": self.ui.chat,
            "ide": self.ui.ide,
            "knowledge": self.ui.knowledge,
            "tools": self.ui.tools,
            "user_settings": self.ui.user_settings,
            "system_settings": self.ui.system_settings,
        }

        if page_name in pages:
            self.ui.stackedWidget.setCurrentWidget(pages[page_name])
            UIFunctions.resetStyle(self, f"btn_{page_name}", self.theme_manager.is_light)
            UIFunctions.selectStandardMenu(self, f"btn_{page_name}", self.theme_manager.is_light)

    def _set_theme(self, theme: str):
        """Set theme"""
        is_light = theme == "light"
        self.theme_manager.set_theme(is_light)

        # Update combo box
        idx = self.ui.themeToggle.findData(theme)
        if idx >= 0:
            self.ui.themeToggle.blockSignals(True)
            self.ui.themeToggle.setCurrentIndex(idx)
            self.ui.themeToggle.blockSignals(False)

    def _toggle_theme(self):
        """Toggle between light and dark theme"""
        self.theme_manager.toggle_theme()

        # Update combo box
        theme = "light" if self.theme_manager.is_light else "dark"
        if hasattr(self.ui, 'userThemeCombo'):
            idx = self.ui.userThemeCombo.findText(theme.capitalize())
            if idx >= 0:
                self.ui.userThemeCombo.blockSignals(True)
                self.ui.userThemeCombo.setCurrentIndex(idx)
                self.ui.userThemeCombo.blockSignals(False)

    def _on_user_theme_changed(self, index):
        """Handle user theme selection"""
        themes = ["dark", "light", "auto"]
        if index < len(themes):
            theme = themes[index]
            if theme == "dark":
                self._set_theme("dark")
            elif theme == "light":
                self._set_theme("light")
            # auto - follow system (use dark as default)

    # ============ IDE Panel Handlers ============

    def _on_ide_generate(self):
        """Handle IDE generate button"""
        if hasattr(self, 'ide_binding'):
            self.ide_binding.generate_code()

    def _on_ide_execute(self):
        """Handle IDE execute button"""
        if hasattr(self, 'ide_binding'):
            self.ide_binding.execute_code()

    def _on_ide_explain(self):
        """Handle IDE explain button"""
        if hasattr(self, 'ide_binding'):
            self.ide_binding.explain_code()

    def _on_ide_clear(self):
        """Handle IDE clear button"""
        self.ui.ideEditor.clear()
        self.ui.ideOutput.clear()
        self.ui.ideStatus.setText("Ready")

    def _on_language_changed(self, language: str):
        """Handle language selection"""
        if hasattr(self, 'ide_binding'):
            self.ide_binding.set_language(language)

    def _on_code_generated(self, code: str, language: str):
        """Handle code generation result"""
        self.ui.ideOutput.append(f"<b style='color: #4CAF50;'>✨ Generated {language} code:</b>")
        self.ui.ideStatus.setText(f"Generated: {language}")

    def _on_execution_result(self, result: dict):
        """Handle execution result"""
        success = result.get('success', False)
        output = result.get('output', '')
        error = result.get('error', '')

        if success:
            self.ui.ideOutput.append(f"<b style='color: #4CAF50;'>✅ Execution successful:</b>")
            self.ui.ideOutput.append(f"<pre>{output}</pre>")
        else:
            self.ui.ideOutput.append(f"<b style='color: #F44336;'>❌ Execution failed:</b>")
            self.ui.ideOutput.append(f"<pre style='color: #F44336;'>{error}</pre>")

    def _on_ide_error(self, error: str):
        """Handle IDE error"""
        self.ui.ideOutput.append(f"<b style='color: #F44336;'>⚠️ Error:</b> {error}")
        self.ui.ideStatus.setText("Error")

    # ============ Chat Panel Handlers ============

    def _on_chat_message_received(self, message: dict):
        """Handle incoming chat message"""
        role = message.get('role', 'assistant')
        content = message.get('content', '')

        if role == 'user':
            prefix = "👤 You"
            color = "#4CAF50"
        elif role == 'assistant':
            prefix = "🤖 AI"
            color = "#2196F3"
        else:
            prefix = "ℹ️"
            color = "#9E9E9E"

        html = f'''
        <div style="margin: 8px 0;">
            <span style="color: {color}; font-weight: bold;">{prefix}:</span>
            <span style="color: #E0E0E0;">{content}</span>
        </div>
        '''
        self.ui.chatOutput.append(html)

    # ============ Settings Panel Handlers ============

    def _on_save_user_settings(self):
        """Save user settings"""
        try:
            from client.src.business.config import load_config, save_config
            config = load_config()

            # Update from UI
            theme_map = {0: "dark", 1: "light", 2: "auto"}
            config.theme = theme_map.get(self.ui.userThemeCombo.currentIndex(), "dark")
            config.font_size = self.ui.userFontSize.value()

            save_config(config)
            self._show_settings_notification("User settings saved!")
        except Exception as e:
            self._show_settings_error(f"Failed to save: {e}")

    def _on_reset_user_settings(self):
        """Reset user settings to defaults"""
        self.ui.userThemeCombo.setCurrentIndex(0)
        self.ui.userFontSize.setValue(14)
        self.ui.userLangCombo.setCurrentIndex(0)
        self.ui.chatAutoSave.setChecked(True)
        self.ui.chatShowTime.setChecked(True)
        self.ui.chatMaxHistory.setValue(1000)
        self.ui.notifEnabled.setChecked(True)
        self.ui.notifSound.setChecked(True)

    def _on_save_system_settings(self):
        """Save system settings"""
        try:
            from client.src.business.config import load_config, save_config
            config = load_config()

            # Ollama settings
            config.ollama.base_url = self.ui.ollamaUrl.text()
            config.ollama.default_model = self.ui.ollamaDefaultModel.text()
            config.ollama.keep_alive = f"{self.ui.ollamaKeepAlive.value()}m"

            # Agent settings
            config.agent.max_iterations = self.ui.agentMaxIterations.value()
            config.agent.temperature = self.ui.agentTemperature.value() / 100.0
            config.agent.streaming = self.ui.agentStreaming.isChecked()

            # Search settings
            config.search.cache_ttl_minutes = self.ui.searchCacheTtl.value()

            # Storage settings
            if self.ui.modelsDir.text():
                config.model_path.models_dir = self.ui.modelsDir.text()

            save_config(config)
            self._show_settings_notification("System settings saved!")
        except Exception as e:
            self._show_settings_error(f"Failed to save: {e}")

    def _on_reset_system_settings(self):
        """Reset system settings to defaults"""
        self.ui.ollamaUrl.setText("http://localhost:11434")
        self.ui.ollamaDefaultModel.clear()
        self.ui.ollamaKeepAlive.setValue(5)
        self.ui.agentMaxIterations.setValue(90)
        self.ui.agentTemperature.setValue(70)
        self.ui.agentStreaming.setChecked(True)
        self.ui.searchCacheTtl.setValue(60)
        self.ui.serperKey.clear()
        self.ui.modelsDir.clear()

    def _show_settings_notification(self, message: str):
        """Show settings notification"""
        self.ui.ideOutput.append(f"<b style='color: #4CAF50;'>✅ {message}</b>")

    def _show_settings_error(self, message: str):
        """Show settings error"""
        self.ui.ideOutput.append(f"<b style='color: #F44336;'>❌ {message}</b>")

    # Resize event
    def resizeEvent(self, event):
        UIFunctions.resize_grips(self)
        super().resizeEvent(event)

    # Mouse press event
    def mousePressEvent(self, event):
        self.dragPos = event.globalPos()
        super().mousePressEvent(event)


def run_app():
    """Run the LivingTree UI application"""
    app = QApplication(sys.argv)
    app.setApplicationName("LivingTree AI Agent")

    window = MainWindow()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_app()
