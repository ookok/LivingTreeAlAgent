"""
主题系统 — 仿 hermes-webui 深色主题
"""

DARK_QSS = """
/* ═══════════════════════════════════════════════════════════════
   全局基础
═══════════════════════════════════════════════════════════════ */
* {
    font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
    font-size: 13px;
    outline: none;
}

QMainWindow, QWidget {
    background-color: #1a1a1a;
    color: #e8e8e8;
}

QSplitter::handle {
    background-color: #2a2a2a;
    width: 1px;
    height: 1px;
}

QScrollBar:vertical {
    background: transparent;
    width: 6px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #404040;
    border-radius: 3px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover { background: #555555; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QScrollBar:horizontal {
    background: transparent;
    height: 6px;
}
QScrollBar::handle:horizontal {
    background: #404040;
    border-radius: 3px;
}

/* ═══════════════════════════════════════════════════════════════
   左侧会话面板
═══════════════════════════════════════════════════════════════ */
#SessionPanel {
    background-color: #111111;
    border-right: 1px solid #252525;
}

#NewChatButton {
    background-color: transparent;
    color: #e8e8e8;
    border: 1px solid #333333;
    border-radius: 6px;
    padding: 8px 12px;
    text-align: left;
    font-size: 13px;
}
#NewChatButton:hover {
    background-color: #252525;
    border-color: #444444;
}

#SessionSearch {
    background-color: #1e1e1e;
    border: 1px solid #2d2d2d;
    border-radius: 5px;
    padding: 6px 10px;
    color: #cccccc;
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
    color: #cccccc;
}
#SessionList::item:hover  { background-color: #1e1e1e; }
#SessionList::item:selected { background-color: #252550; color: #ffffff; }

#SettingsButton {
    background-color: transparent;
    border: none;
    color: #888888;
    padding: 8px;
    text-align: left;
    border-radius: 5px;
}
#SettingsButton:hover { background-color: #1e1e1e; color: #cccccc; }

/* ═══════════════════════════════════════════════════════════════
   中央聊天面板
═══════════════════════════════════════════════════════════════ */
#ChatPanel {
    background-color: #1a1a1a;
}

#ChatTitle {
    font-size: 15px;
    font-weight: 600;
    color: #e8e8e8;
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
    background-color: #252550;
    border-radius: 10px;
    padding: 10px 14px;
    max-width: 72%;
    color: #e8e8e8;
}
.AssistantBubble {
    background-color: transparent;
    padding: 4px 0;
    color: #e0e0e0;
}

/* 工具调用块 */
#ToolBlock {
    background-color: #1e1e1e;
    border: 1px solid #2d2d2d;
    border-left: 3px solid #5a5aff;
    border-radius: 6px;
    padding: 8px 12px;
    margin: 4px 0;
}
#ToolBlockSuccess { border-left-color: #22c55e; }
#ToolBlockError   { border-left-color: #ef4444; }
#ToolBlockRunning { border-left-color: #f59e0b; }

#ToolName { color: #a0a0ff; font-weight: 600; font-size: 12px; }
#ToolArgs { color: #888888; font-size: 11px; font-family: "Consolas", monospace; }
#ToolResult { color: #cccccc; font-size: 12px; font-family: "Consolas", monospace; }

/* 审批卡片 */
#ApprovalCard {
    background-color: #1e1e1e;
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
    background-color: #111111;
    border-top: 1px solid #252525;
}

#MessageInput {
    background-color: #1e1e1e;
    border: 1px solid #2d2d2d;
    border-radius: 8px;
    padding: 10px 14px;
    color: #e8e8e8;
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
#SendButton:disabled { background-color: #333366; color: #666699; }

#StopButton {
    background-color: #7f1d1d;
    color: #fca5a5;
    border: none;
    border-radius: 7px;
    padding: 10px 18px;
    font-weight: 600;
}
#StopButton:hover { background-color: #991b1b; }

/* ═══════════════════════════════════════════════════════════════
   右侧工作区面板
═══════════════════════════════════════════════════════════════ */
#WorkspacePanel {
    background-color: #111111;
    border-left: 1px solid #252525;
}

#WorkspaceTitle {
    color: #888888;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 4px 8px;
}

#FileTree {
    background-color: transparent;
    border: none;
    color: #cccccc;
    outline: none;
}
#FileTree::item { padding: 4px 6px; border-radius: 4px; }
#FileTree::item:hover    { background-color: #1e1e1e; }
#FileTree::item:selected { background-color: #252550; color: #ffffff; }

#FilePreview {
    background-color: #151515;
    border: none;
    color: #cccccc;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 12px;
    padding: 8px;
    border-radius: 6px;
}

#MemoryView {
    background-color: #151515;
    border: none;
    color: #b0b0b0;
    font-size: 12px;
    padding: 8px;
    border-radius: 6px;
}

#TabBar::tab {
    background-color: transparent;
    color: #666666;
    padding: 6px 14px;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: 12px;
}
#TabBar::tab:selected { color: #e8e8e8; border-bottom-color: #5a5aff; }
#TabBar::tab:hover    { color: #bbbbbb; }

/* ═══════════════════════════════════════════════════════════════
   状态栏
═══════════════════════════════════════════════════════════════ */
#StatusBar {
    background-color: #0d0d0d;
    border-top: 1px solid #1e1e1e;
    padding: 3px 12px;
}
#StatusLabel { color: #555555; font-size: 11px; }
#StatusIndicator { font-size: 11px; }

/* ═══════════════════════════════════════════════════════════════
   设置对话框
═══════════════════════════════════════════════════════════════ */
QDialog {
    background-color: #1a1a1a;
}
QLabel { color: #cccccc; }
QLineEdit, QSpinBox, QComboBox {
    background-color: #252525;
    border: 1px solid #333333;
    border-radius: 5px;
    padding: 6px 10px;
    color: #e8e8e8;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus { border-color: #5a5aff; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background-color: #252525;
    border: 1px solid #333333;
    selection-background-color: #353585;
    color: #e8e8e8;
}

QPushButton {
    background-color: #252525;
    color: #e8e8e8;
    border: 1px solid #333333;
    border-radius: 5px;
    padding: 7px 16px;
}
QPushButton:hover   { background-color: #303030; }
QPushButton:pressed { background-color: #1e1e1e; }

QPushButton#SaveButton {
    background-color: #5a5aff;
    border-color: #5a5aff;
    color: white;
    font-weight: 600;
}
QPushButton#SaveButton:hover { background-color: #4a4aef; }

QGroupBox {
    color: #888888;
    border: 1px solid #2a2a2a;
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
    color: #666666;
}
"""
