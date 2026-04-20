"""
主题系统 — 浅色主题
"""

LIGHT_QSS = """
/* ═══════════════════════════════════════════════════════════════
   全局基础
═══════════════════════════════════════════════════════════════ */
* {
    font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
    font-size: 13px;
    outline: none;
}

QMainWindow, QWidget {
    background-color: transparent;
    color: #333333;
}

QSplitter::handle {
    background-color: #e0e0e0;
    width: 1px;
    height: 1px;
}

QScrollBar:vertical {
    background: transparent;
    width: 6px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #c0c0c0;
    border-radius: 3px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover { background: #a0a0a0; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QScrollBar:horizontal {
    background: transparent;
    height: 6px;
}
QScrollBar::handle:horizontal {
    background: #c0c0c0;
    border-radius: 3px;
}

/* ═══════════════════════════════════════════════════════════════
   左侧会话面板
═══════════════════════════════════════════════════════════════ */
#SessionPanel {
    background-color: transparent;
    border: none;
}

#NewChatButton {
    background-color: transparent;
    color: #333333;
    border: 1px solid #d0d0d0;
    border-radius: 6px;
    padding: 8px 12px;
    text-align: left;
    font-size: 13px;
}
#NewChatButton:hover {
    background-color: #e8e8e8;
    border-color: #c0c0c0;
}

#SessionSearch {
    background-color: #ffffff;
    border: 1px solid #d0d0d0;
    border-radius: 5px;
    padding: 6px 10px;
    color: #333333;
}
#SessionSearch:focus { border-color: #5a5aff; }

#SessionList {
    background-color: transparent;
    border: none;
    outline: none;
}
#SessionList::item {
    padding: 8px 10px;
    border-radius: 5px;
    margin: 1px 4px;
    color: #333333;
}
#SessionList::item:hover  { background-color: #e8e8e8; }
#SessionList::item:selected { background-color: #e8e8f0; color: #333333; }

#SettingsButton {
    background-color: transparent;
    border: none;
    color: #666666;
    padding: 8px;
    text-align: left;
    border-radius: 5px;
}
#SettingsButton:hover { background-color: #e8e8e8; color: #333333; }

/* ═══════════════════════════════════════════════════════════════
   中央聊天面板
═══════════════════════════════════════════════════════════════ */
#ChatPanel {
    background-color: transparent;
}

#ChatTitle {
    font-size: 15px;
    font-weight: 600;
    color: #333333;
    padding: 0 4px;
}

#ChatScrollArea {
    background-color: transparent;
    border: none;
}

#MessageContainer {
    background-color: transparent;
}

/* 消息气泡 */
.UserBubble {
    background-color: #e8e8f0;
    border-radius: 10px;
    padding: 10px 14px;
    max-width: 72%;
    color: #333333;
}
.AssistantBubble {
    background-color: transparent;
    padding: 4px 0;
    color: #333333;
}

/* 工具调用块 */
#ToolBlock {
    background-color: #f5f5f5;
    border: 1px solid #e0e0e0;
    border-left: 3px solid #5a5aff;
    border-radius: 6px;
    padding: 8px 12px;
    margin: 4px 0;
}
#ToolBlockSuccess { border-left-color: #22c55e; }
#ToolBlockError   { border-left-color: #ef4444; }
#ToolBlockRunning { border-left-color: #f59e0b; }

#ToolName { color: #5a5aff; font-weight: 600; font-size: 12px; }
#ToolArgs { color: #666666; font-size: 11px; font-family: "Consolas", monospace; }
#ToolResult { color: #333333; font-size: 12px; font-family: "Consolas", monospace; }

/* 审批卡片 */
#ApprovalCard {
    background-color: #fff8e1;
    border: 1px solid #f59e0b;
    border-radius: 8px;
    padding: 12px 16px;
    margin: 8px 0;
}
#ApprovalTitle { color: #f59e0b; font-weight: 600; }
#AllowButton {
    background-color: #16a34a;
    color: white;
    border: none;
    border-radius: 5px;
    padding: 6px 16px;
    font-weight: 600;
}
#AllowButton:hover { background-color: #15803d; }
#RejectButton {
    background-color: #dc2626;
    color: white;
    border: none;
    border-radius: 5px;
    padding: 6px 16px;
    font-weight: 600;
}
#RejectButton:hover { background-color: #b91c1c; }

/* 输入区 */
#InputArea {
    background-color: #f5f5f5;
    border-top: 1px solid #e0e0e0;
}

#MessageInput {
    background-color: #ffffff;
    border: 1px solid #d0d0d0;
    border-radius: 8px;
    padding: 10px 14px;
    color: #333333;
    font-size: 14px;
    line-height: 1.5;
}
#MessageInput:focus { border-color: #5a5aff; }

#SendButton {
    background-color: #5a5aff;
    color: white;
    border: none;
    border-radius: 7px;
    padding: 10px 18px;
    font-weight: 600;
    font-size: 14px;
}
#SendButton:hover   { background-color: #4a4aef; }
#SendButton:pressed { background-color: #3a3adf; }
#SendButton:disabled { background-color: #c0c0e0; color: #8080a0; }

#StopButton {
    background-color: #fee2e2;
    color: #dc2626;
    border: none;
    border-radius: 7px;
    padding: 10px 18px;
    font-weight: 600;
}
#StopButton:hover { background-color: #fecaca; }

/* ═══════════════════════════════════════════════════════════════
   右侧工作区面板
═══════════════════════════════════════════════════════════════ */
#WorkspacePanel {
    background-color: transparent;
    border: none;
}

#WorkspaceTitle {
    color: #666666;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 4px 8px;
}

#FileTree {
    background-color: transparent;
    border: none;
    color: #333333;
    outline: none;
}
#FileTree::item { padding: 4px 6px; border-radius: 4px; }
#FileTree::item:hover    { background-color: #e8e8e8; }
#FileTree::item:selected { background-color: #e8e8f0; color: #333333; }

#FilePreview {
    background-color: #fafafa;
    border: none;
    color: #333333;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 12px;
    padding: 8px;
    border-radius: 6px;
}

#MemoryView {
    background-color: #fafafa;
    border: none;
    color: #555555;
    font-size: 12px;
    padding: 8px;
    border-radius: 6px;
}

#TabBar::tab {
    background-color: transparent;
    color: #888888;
    padding: 6px 14px;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: 12px;
}
#TabBar::tab:selected { color: #333333; border-bottom-color: #5a5aff; }
#TabBar::tab:hover    { color: #555555; }

/* ═══════════════════════════════════════════════════════════════
   状态栏
═══════════════════════════════════════════════════════════════ */
#StatusBar {
    background-color: #f0f0f0;
    border-top: 1px solid #e0e0e0;
    padding: 3px 12px;
}
#StatusLabel { color: #888888; font-size: 11px; }
#StatusIndicator { font-size: 11px; }

/* ═══════════════════════════════════════════════════════════════
   设置对话框
═══════════════════════════════════════════════════════════════ */
QDialog {
    background-color: #ffffff;
}
QLabel { color: #333333; }
QLineEdit, QSpinBox, QComboBox {
    background-color: #ffffff;
    border: 1px solid #d0d0d0;
    border-radius: 5px;
    padding: 6px 10px;
    color: #333333;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus { border-color: #5a5aff; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background-color: #ffffff;
    border: 1px solid #d0d0d0;
    selection-background-color: #e8e8f0;
    color: #333333;
}

QPushButton {
    background-color: #ffffff;
    color: #333333;
    border: 1px solid #d0d0d0;
    border-radius: 5px;
    padding: 7px 16px;
}
QPushButton:hover   { background-color: #f5f5f5; }
QPushButton:pressed { background-color: #e8e8e8; }

QPushButton#SaveButton {
    background-color: #5a5aff;
    border-color: #5a5aff;
    color: white;
    font-weight: 600;
}
QPushButton#SaveButton:hover { background-color: #4a4aef; }

QGroupBox {
    color: #666666;
    border: 1px solid #e0e0e0;
    border-radius: 6px;
    margin-top: 8px;
    padding-top: 12px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: #888888;
}
"""
