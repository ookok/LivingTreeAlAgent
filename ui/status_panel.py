"""
状态面板 - StatusPanel
显示 Hermes Agent 各组件状态
参考 hermes-agent status 命令的设计
"""

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QGroupBox, QScrollArea,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QStackedWidget, QCheckBox,
)
from PyQt6.QtGui import QFont

import os
import json
import socket
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from core.config import get_hermes_home, get_env_value
from core.providers import get_all_configured_providers, has_api_key, get_label


class StatusCard(QFrame):
    """状态卡片"""
    
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title = title
        self._init_ui()
    
    def _init_ui(self):
        self.setStyleSheet("""
            StatusCard {
                background: #1e1e1e;
                border: 1px solid #333;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        
        # 标题
        title_label = QLabel(self.title)
        title_label.setStyleSheet("""
            color: #888;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
        """)
        layout.addWidget(title_label)
        
        # 内容
        self.content_label = QLabel()
        self.content_label.setStyleSheet("""
            color: #e8e8e8;
            font-size: 14px;
            font-weight: 500;
        """)
        layout.addWidget(self.content_label)
        
        # 详情
        self.detail_label = QLabel()
        self.detail_label.setStyleSheet("color: #666; font-size: 11px;")
        self.detail_label.setWordWrap(True)
        layout.addWidget(self.detail_label)
    
    def set_status(self, status: bool, text: str = "", detail: str = ""):
        """设置状态"""
        color = "#4ade80" if status else "#f87171"  # green or red
        icon = "OK" if status else "FAIL"
        self.content_label.setText(f'<span style="color: {color};">{icon}</span> {text}')
        self.detail_label.setText(detail)
    
    def set_content(self, content: str, detail: str = ""):
        """设置内容"""
        self.content_label.setText(content)
        self.detail_label.setText(detail)


class ApiKeyStatusWidget(QWidget):
    """API Key 状态显示"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        
        # API Keys 列表
        self.keys = {
            "OpenRouter": "OPENROUTER_API_KEY",
            "OpenAI": "OPENAI_API_KEY",
            "Anthropic": "ANTHROPIC_API_KEY",
            "DeepSeek": "DEEPSEEK_API_KEY",
            "阿里云": "DASHSCOPE_API_KEY",
            "GLM/Z.AI": "GLM_API_KEY",
            "Kimi": "KIMI_API_KEY",
            "MiniMax": "MINIMAX_API_KEY",
            "HuggingFace": "HF_TOKEN",
            "Firecrawl": "FIRECRAWL_API_KEY",
            "Tavily": "TAVILY_API_KEY",
            "Serper": "SERPER_API_KEY",
        }
        
        for name, env_var in self.keys.items():
            row = self._create_key_row(name, env_var)
            layout.addLayout(row)
    
    def _create_key_row(self, name: str, env_var: str) -> QHBoxLayout:
        """创建 Key 行"""
        layout = QHBoxLayout()
        layout.setSpacing(12)
        
        # 名称
        name_label = QLabel(name)
        name_label.setFixedWidth(100)
        name_label.setStyleSheet("color: #ccc;")
        layout.addWidget(name_label)
        
        # 状态
        has_key = bool(get_env_value(env_var))
        status_label = QLabel()
        if has_key:
            key = get_env_value(env_var)
            masked = key[:4] + "..." + key[-4:] if len(key) > 12 else "***"
            status_label.setText(f'<span style="color: #4ade80;">OK</span> {masked}')
        else:
            status_label.setText('<span style="color: #f87171;">NOT SET</span>')
        layout.addWidget(status_label, 1)
        
        return layout
    
    def refresh(self):
        """刷新状态"""
        # 重新构建 UI
        self._init_ui()


class ProviderStatusWidget(QWidget):
    """提供商状态显示"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self.refresh()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # 标题
        title = QLabel("Configured Providers / 已配置的提供商")
        title.setStyleSheet("color: #888; font-size: 12px; font-weight: 600;")
        layout.addWidget(title)
        
        # 提供商列表
        self.provider_layout = QVBoxLayout()
        self.provider_layout.setSpacing(6)
        layout.addLayout(self.provider_layout)
        
        layout.addStretch()
    
    def refresh(self):
        """刷新状态"""
        # 清除现有
        while self.provider_layout.count():
            item = self.provider_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 获取已配置的提供商
        configured = get_all_configured_providers()
        
        if not configured:
            empty_label = QLabel('<span style="color: #f87171;">No providers configured</span>')
            empty_label.setStyleSheet("padding: 20px;")
            self.provider_layout.addWidget(empty_label)
            return
        
        for provider_id in configured:
            row = self._create_provider_row(provider_id)
            self.provider_layout.addLayout(row)
    
    def _create_provider_row(self, provider_id: str) -> QHBoxLayout:
        """创建提供商行"""
        layout = QHBoxLayout()
        layout.setSpacing(12)
        
        # 标签
        label = get_label(provider_id)
        name_label = QLabel(label)
        name_label.setFixedWidth(160)
        name_label.setStyleSheet("color: #e8e8e8;")
        layout.addWidget(name_label)
        
        # 状态
        status_label = QLabel('<span style="color: #4ade80;">ACTIVE</span>')
        layout.addWidget(status_label, 1)
        
        return layout


class SessionStatusWidget(QWidget):
    """会话状态显示"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # 标题
        title = QLabel("Sessions / 会话")
        title.setStyleSheet("color: #888; font-size: 12px; font-weight: 600;")
        layout.addWidget(title)
        
        # 会话表格
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Name", "Status", "Model", "Last Active"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setStyleSheet("""
            QTableWidget {
                background: #1a1a1a;
                color: #ccc;
                border: none;
                border-radius: 6px;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QTableWidget::item:selected {
                background: #353585;
            }
            QHeaderView::section {
                background: #252525;
                color: #888;
                padding: 8px;
                border: none;
            }
        """)
        layout.addWidget(self.table)
        
        self.refresh()
    
    def refresh(self):
        """刷新会话列表"""
        self.table.setRowCount(0)
        
        # 读取会话文件
        hermes_home = get_hermes_home()
        sessions_file = hermes_home / "sessions" / "sessions.json"
        
        if sessions_file.exists():
            try:
                with open(sessions_file, "r", encoding="utf-8") as f:
                    sessions = json.load(f)
                
                for i, session in enumerate(sessions[:10]):  # 最多显示 10 个
                    self.table.insertRow(i)
                    self.table.setItem(i, 0, QTableWidgetItem(session.get("name", "")))
                    self.table.setItem(i, 1, QTableWidgetItem(session.get("status", "active")))
                    self.table.setItem(i, 2, QTableWidgetItem(session.get("model", "")))
                    self.table.setItem(i, 3, QTableWidgetItem(session.get("last_active", "")))
            except Exception:
                pass


class GatewayStatusWidget(QWidget):
    """Gateway 状态显示"""
    
    gateway_started = pyqtSignal()
    gateway_stopped = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self.refresh()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # 状态卡片
        status_card = QFrame()
        status_card.setStyleSheet("""
            QFrame {
                background: #1a1a1a;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        status_layout = QVBoxLayout(status_card)
        
        self.status_label = QLabel()
        self.status_label.setStyleSheet("font-size: 16px; font-weight: 600;")
        status_layout.addWidget(self.status_label)
        
        self.info_label = QLabel()
        self.info_label.setStyleSheet("color: #888; font-size: 12px;")
        status_layout.addWidget(self.info_label)
        
        layout.addWidget(status_card)
        
        # 端口状态
        port_card = QFrame()
        port_card.setStyleSheet("""
            QFrame {
                background: #1a1a1a;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        port_layout = QHBoxLayout(port_card)
        
        port_label = QLabel("Port 18789:")
        port_label.setStyleSheet("color: #888;")
        port_layout.addWidget(port_label)
        
        self.port_status = QLabel()
        port_layout.addWidget(self.port_status, 1)
        
        layout.addWidget(port_card)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        self.start_btn = QPushButton("Start Gateway")
        self.start_btn.clicked.connect(self._on_start)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background: #4ade80;
                color: #1a1a1a;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }
            QPushButton:hover { background: #22c55e; }
        """)
        btn_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("Stop Gateway")
        self.stop_btn.clicked.connect(self._on_stop)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background: #f87171;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }
            QPushButton:hover { background: #ef4444; }
        """)
        btn_layout.addWidget(self.stop_btn)
        
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background: #333;
                color: #ccc;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover { background: #444; }
        """)
        btn_layout.addWidget(self.refresh_btn)
        
        layout.addLayout(btn_layout)
        layout.addStretch()
    
    def refresh(self):
        """刷新状态"""
        hermes_home = get_hermes_home()
        pid_file = hermes_home / "gateway.pid"
        
        running = False
        pid = None
        
        if pid_file.exists():
            try:
                raw = pid_file.read_text().strip()
                if raw:
                    data = json.loads(raw) if raw.startswith("{") else {"pid": int(raw)}
                    pid = int(data["pid"])
                    os.kill(pid, 0)
                    running = True
            except Exception:
                running = False
        
        # 更新 UI
        if running:
            self.status_label.setText('<span style="color: #4ade80;">RUNNING</span>')
            self.info_label.setText(f"PID: {pid}")
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
        else:
            self.status_label.setText('<span style="color: #f87171;">STOPPED</span>')
            self.info_label.setText("Gateway is not running")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
        
        # 检查端口
        port_in_use = self._check_port(18789)
        if port_in_use:
            self.port_status.setText('<span style="color: #4ade80;">In Use</span>')
        else:
            self.port_status.setText('<span style="color: #f87171;">Available</span>')
    
    def _check_port(self, port: int) -> bool:
        """检查端口是否被占用"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(("127.0.0.1", port))
            sock.close()
            return result == 0
        except Exception:
            return False
    
    def _on_start(self):
        """启动 Gateway"""
        try:
            import subprocess
            import sys
            import os
            
            # 获取 gateway 脚本路径
            gateway_script = Path(__file__).parent.parent / "core" / "gateway" / "main.py"
            if not gateway_script.exists():
                # 尝试其他可能路径
                gateway_script = Path(__file__).parent.parent.parent / "core" / "gateway" / "main.py"
            
            if not gateway_script.exists():
                QMessageBox.warning(
                    self, 
                    "提示", 
                    "未找到 Gateway 启动脚本:\n" + str(gateway_script)
                )
                return
            
            # 获取 Hermes 主目录
            hermes_home = get_hermes_home()
            hermes_home.mkdir(parents=True, exist_ok=True)
            
            # 启动 gateway 进程
            process = subprocess.Popen(
                [sys.executable, str(gateway_script)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(gateway_script.parent),
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
            )
            
            # 保存 PID
            pid_file = hermes_home / "gateway.pid"
            pid_file.write_text(json.dumps({"pid": process.pid, "started_at": datetime.now().isoformat()}))
            
            # 更新 UI
            self.refresh()
            self.gateway_started.emit()
            QMessageBox.information(self, "成功", f"Gateway 已启动 (PID: {process.pid})")
            
        except FileNotFoundError as e:
            QMessageBox.critical(self, "错误", f"Gateway 启动失败:\n{str(e)}")
        except Exception as e:
            logger.error(f"Gateway 启动失败: {e}")
            QMessageBox.critical(self, "错误", f"Gateway 启动失败:\n{str(e)}")
    
    def _on_stop(self):
        """停止 Gateway"""
        hermes_home = get_hermes_home()
        pid_file = hermes_home / "gateway.pid"
        
        if pid_file.exists():
            try:
                import signal
                raw = pid_file.read_text().strip()
                data = json.loads(raw) if raw.startswith("{") else {"pid": int(raw)}
                pid = int(data["pid"])
                os.kill(pid, signal.SIGTERM)
            except Exception:
                pass
        
        self.refresh()
        self.gateway_stopped.emit()


class StatusPanel(QWidget):
    """状态面板主组件"""
    
    status_refreshed = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        
        # 自动刷新定时器
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh)
        self.refresh_timer.setInterval(30000)  # 30 秒
    
    def _init_ui(self):
        self.setStyleSheet("background: #151515;")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        # 标题栏
        header = QHBoxLayout()
        
        title = QLabel("Status / 状态")
        title.setStyleSheet("""
            color: #e8e8e8;
            font-size: 20px;
            font-weight: 700;
        """)
        header.addWidget(title)
        
        header.addStretch()
        
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background: #333;
                color: #ccc;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
            }
            QPushButton:hover { background: #444; }
        """)
        header.addWidget(self.refresh_btn)
        
        layout.addLayout(header)
        
        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(16)
        
        # 第一行：基础信息
        row1 = QHBoxLayout()
        row1.setSpacing(16)
        
        # Hermes Home
        home_card = QFrame()
        home_card.setStyleSheet("""
            QFrame {
                background: #1e1e1e;
                border: 1px solid #333;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        home_layout = QVBoxLayout(home_card)
        
        home_title = QLabel("Hermes Home")
        home_title.setStyleSheet("color: #888; font-size: 11px; font-weight: 600;")
        home_layout.addWidget(home_title)
        
        self.home_label = QLabel()
        self.home_label.setStyleSheet("color: #e8e8e8; font-size: 13px;")
        home_layout.addWidget(self.home_label)
        
        row1.addWidget(home_card, 1)
        
        # Python 版本
        py_card = QFrame()
        py_card.setStyleSheet(home_card.styleSheet())
        py_layout = QVBoxLayout(py_card)
        
        py_title = QLabel("Python")
        py_title.setStyleSheet("color: #888; font-size: 11px; font-weight: 600;")
        py_layout.addWidget(py_title)
        
        self.py_label = QLabel()
        self.py_label.setStyleSheet("color: #e8e8e8; font-size: 13px;")
        py_layout.addWidget(self.py_label)
        
        row1.addWidget(py_card, 1)
        
        # .env 状态
        env_card = QFrame()
        env_card.setStyleSheet(home_card.styleSheet())
        env_layout = QVBoxLayout(env_card)
        
        env_title = QLabel(".env File")
        env_title.setStyleSheet("color: #888; font-size: 11px; font-weight: 600;")
        env_layout.addWidget(env_title)
        
        self.env_label = QLabel()
        self.env_label.setStyleSheet("color: #e8e8e8; font-size: 13px;")
        env_layout.addWidget(self.env_label)
        
        row1.addWidget(env_card, 1)
        
        content_layout.addLayout(row1)
        
        # 第二行：API Keys
        apikey_section = QLabel("API Keys / API 密钥")
        apikey_section.setStyleSheet("color: #888; font-size: 12px; font-weight: 600;")
        content_layout.addWidget(apikey_section)
        
        self.apikey_widget = ApiKeyStatusWidget()
        content_layout.addWidget(self.apikey_widget)
        
        # 第三行：Gateway
        gateway_section = QLabel("Gateway Service / 网关服务")
        gateway_section.setStyleSheet("color: #888; font-size: 12px; font-weight: 600;")
        content_layout.addWidget(gateway_section)
        
        self.gateway_widget = GatewayStatusWidget()
        content_layout.addWidget(self.gateway_widget)
        
        # 第四行：Sessions
        sessions_section = QLabel("Sessions / 会话")
        sessions_section.setStyleSheet("color: #888; font-size: 12px; font-weight: 600;")
        content_layout.addWidget(sessions_section)
        
        self.session_widget = SessionStatusWidget()
        content_layout.addWidget(self.session_widget)
        
        content_layout.addStretch()
        
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        # 初始刷新
        self.refresh()
    
    def refresh(self):
        """刷新所有状态"""
        import sys
        
        # Hermes Home
        hermes_home = get_hermes_home()
        self.home_label.setText(str(hermes_home))
        
        # Python 版本
        self.py_label.setText(sys.version.split()[0])
        
        # .env 状态
        env_path = hermes_home / ".env"
        if env_path.exists():
            self.env_label.setText('<span style="color: #4ade80;">exists</span>')
        else:
            self.env_label.setText('<span style="color: #f87171;">not found</span>')
        
        # 刷新各个组件
        self.apikey_widget.refresh()
        self.gateway_widget.refresh()
        self.session_widget.refresh()
        
        self.status_refreshed.emit(self._collect_status())
    
    def _collect_status(self) -> Dict[str, Any]:
        """收集状态数据"""
        return {
            "hermes_home": str(get_hermes_home()),
            "providers": get_all_configured_providers(),
        }
    
    def start_auto_refresh(self):
        """开始自动刷新"""
        self.refresh_timer.start()
    
    def stop_auto_refresh(self):
        """停止自动刷新"""
        self.refresh_timer.stop()
