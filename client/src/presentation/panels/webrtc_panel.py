"""
WebRTC 视频通话面板

集成到 PyQt6 的 WebRTC 视频通话与直播界面
"""

import asyncio
import logging
import os
import sys
import threading
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QUrl, Qt, pyqtSignal, QTimer
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QLineEdit, QTextEdit, QComboBox, QTabWidget,
                             QGroupBox, QFormLayout, QSpinBox, QCheckBox, QProgressBar,
                             QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox)

logger = logging.getLogger(__name__)


class WebRTCCallbacks:
    """JavaScript 回调接口"""

    def __init__(self, panel):
        self.panel = panel

    def create_room(self, room_name: str, user_name: str, peer_id: str):
        """创建房间"""
        asyncio.ensure_future(self.panel._create_room_async(room_name, user_name, peer_id))

    def join_room(self, room_id: str, user_name: str, peer_id: str):
        """加入房间"""
        asyncio.ensure_future(self.panel._join_room_async(room_id, user_name, peer_id))

    def set_ice_config(self, config: dict):
        """设置 ICE 配置"""
        self.panel._inject_ice_config(config)

    def set_room_info(self, info: dict):
        """设置房间信息"""
        logger.info(f"房间信息: {info}")


class WebRTCPanel(QWidget):
    """
    WebRTC 视频通话面板

    功能:
    - 房间创建/加入
    - 实时视频通话
    - 直播推流
    - 云端 TURN 配置
    """

    # 信号
    room_created = pyqtSignal(str, str)  # room_id, room_name
    participant_joined = pyqtSignal(str, str)  # room_id, peer_id
    stream_started = pyqtSignal(str)  # room_id
    stream_stopped = pyqtSignal(str)  # room_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("WebRTC 视频通话")
        self.setMinimumSize(900, 600)

        # 组件
        self.signaling_server = None
        self.ice_selector = None
        self.stream_router = None
        self._server_task = None
        self._loop = None
        self._server_thread = None

        # 加载配置
        self._load_config()

        # UI
        self._init_ui()

        # 启动信令服务器
        self._start_signaling_server()

    def _load_config(self):
        """加载配置"""
        config_path = Path(__file__).parent.parent / "config" / "webrtc_config.json"
        self._config = {
            "signaling_host": "0.0.0.0",
            "signaling_port": 8080,
            "cloud_turn_url": "",
            "cloud_turn_user": "",
            "cloud_turn_credential": "",
            "auto_select_ice": True,
        }

        if config_path.exists():
            import json
            try:
                self._config.update(json.loads(config_path.read_text()))
            except Exception:
                pass

    def _init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)

        # Tab
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Tab 1: 通话面板
        self._init_call_tab()

        # Tab 2: TURN 配置
        self._init_turn_tab()

        # Tab 3: 直播管理
        self._init_live_tab()

        # Tab 4: 日志
        self._init_log_tab()

    def _init_call_tab(self):
        """通话面板"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # WebRTC 视图
        self.webview = QWebEngineView()
        self.webview.setMinimumHeight(400)

        # 加载本地 HTML
        html_path = Path(__file__).parent.parent / "assets" / "webrtc" / "index.html"
        if html_path.exists():
            self.webview.setUrl(QUrl.fromLocalFile(str(html_path.absolute())))
        else:
            # 加载内置页面
            self.webview.setHtml(self._get_embedded_html())

        # 页面加载完成后设置 JS 回调
        self.webview.page().loadFinished.connect(self._setup_js_callbacks)

        layout.addWidget(self.webview)

        # 控制栏
        controls = QHBoxLayout()

        self.connect_btn = QPushButton("连接")
        self.connect_btn.clicked.connect(self._toggle_connection)
        controls.addWidget(self.connect_btn)

        controls.addStretch()

        # 状态
        self.status_label = QLabel("状态: 未连接")
        controls.addWidget(self.status_label)

        layout.addLayout(controls)
        self.tabs.addTab(tab, "📞 视频通话")

    def _init_turn_tab(self):
        """TURN 配置面板"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # 云端 TURN 配置
        group = QGroupBox("云端 TURN 服务器")
        form = QFormLayout(group)

        self.turn_url_input = QLineEdit()
        self.turn_url_input.setPlaceholderText("turn:your-server.com:3478")
        self.turn_url_input.setText(self._config.get("cloud_turn_url", ""))
        form.addRow("TURN URL:", self.turn_url_input)

        self.turn_user_input = QLineEdit()
        self.turn_user_input.setPlaceholderText("用户名")
        self.turn_user_input.setText(self._config.get("cloud_turn_user", ""))
        form.addRow("用户名:", self.turn_user_input)

        self.turn_pass_input = QLineEdit()
        self.turn_pass_input.setPlaceholderText("密码")
        self.turn_pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.turn_pass_input.setText(self._config.get("cloud_turn_credential", ""))
        form.addRow("密码:", self.turn_pass_input)

        layout.addWidget(group)

        # 本地 TURN
        group2 = QGroupBox("本地 TURN (备用)")
        form2 = QFormLayout(group2)

        self.local_turn_check = QCheckBox("启用本地 TURN 兜底")
        self.local_turn_check.setChecked(True)
        form2.addRow("", self.local_turn_check)

        self.turn_binary_path = QLineEdit()
        self.turn_binary_path.setPlaceholderText("simple-turn.exe 路径")
        form2.addRow("二进制:", self.turn_binary_path)

        layout.addWidget(group2)

        # 探测按钮
        probe_btn = QPushButton("🔍 探测网络环境")
        probe_btn.clicked.connect(self._probe_network)
        layout.addWidget(probe_btn)

        # 探测结果
        self.probe_result = QTextEdit()
        self.probe_result.setReadOnly(True)
        self.probe_result.setMaximumHeight(120)
        layout.addWidget(QLabel("探测结果:"))
        layout.addWidget(self.probe_result)

        layout.addStretch()
        self.tabs.addTab(tab, "⚙️ TURN 配置")

    def _init_live_tab(self):
        """直播管理面板"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # FFmpeg 状态
        ffmpeg_group = QGroupBox("FFmpeg 状态")
        ffmpeg_layout = QHBoxLayout(ffmpeg_group)

        self.ffmpeg_status_label = QLabel("检测中...")
        ffmpeg_layout.addWidget(self.ffmpeg_status_label)

        self.install_ffmpeg_btn = QPushButton("安装 FFmpeg")
        self.install_ffmpeg_btn.clicked.connect(self._install_ffmpeg)
        ffmpeg_layout.addWidget(self.install_ffmpeg_btn)

        layout.addWidget(ffmpeg_group)

        # 直播列表
        self.live_table = QTableWidget()
        self.live_table.setColumnCount(4)
        self.live_table.setHorizontalHeaderLabels(["房间ID", "状态", "观众数", "操作"])
        self.live_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.live_table)

        # 控制按钮
        controls = QHBoxLayout()

        self.start_live_btn = QPushButton("开始直播")
        self.start_live_btn.clicked.connect(self._start_live)
        controls.addWidget(self.start_live_btn)

        self.stop_live_btn = QPushButton("停止直播")
        self.stop_live_btn.clicked.connect(self._stop_live)
        self.stop_live_btn.setEnabled(False)
        controls.addWidget(self.stop_live_btn)

        controls.addStretch()

        # RTMP 推流
        rtmp_group = QGroupBox("RTMP 推流")
        rtmp_layout = QFormLayout(rtmp_group)

        self.rtmp_url_input = QLineEdit()
        self.rtmp_url_input.setPlaceholderText("rtmp://your-server.com/live/stream_key")
        rtmp_layout.addRow("RTMP URL:", self.rtmp_url_input)

        rtmp_buttons = QHBoxLayout()
        self.start_rtmp_btn = QPushButton("开始推流")
        self.start_rtmp_btn.clicked.connect(self._start_rtmp)
        rtmp_buttons.addWidget(self.start_rtmp_btn)

        self.stop_rtmp_btn = QPushButton("停止推流")
        self.stop_rtmp_btn.clicked.connect(self._stop_rtmp)
        self.stop_rtmp_btn.setEnabled(False)
        rtmp_buttons.addWidget(self.stop_rtmp_btn)

        rtmp_layout.addRow("", rtmp_buttons)
        layout.addWidget(rtmp_group)

        layout.addLayout(controls)
        self.tabs.addTab(tab, "📺 直播管理")

        # 检查 FFmpeg 状态
        self._check_ffmpeg_status()

    def _init_log_tab(self):
        """日志面板"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)

        # 控制按钮
        controls = QHBoxLayout()

        self.clear_log_btn = QPushButton("清空日志")
        self.clear_log_btn.clicked.connect(lambda: self.log_text.clear())
        controls.addWidget(self.clear_log_btn)

        controls.addStretch()

        layout.addLayout(controls)
        self.tabs.addTab(tab, "📋 日志")

    def _log(self, msg: str):
        """添加日志"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {msg}")

    def _check_ffmpeg_status(self):
        """检查 FFmpeg 状态"""
        try:
            from core.ffmpeg_tool import get_ffmpeg
            ffmpeg = get_ffmpeg()
            if ffmpeg.available:
                info = ffmpeg.version_info()
                self.ffmpeg_status_label.setText(f"✓ FFmpeg 就绪 ({info.get('version', 'unknown')})")
                self.ffmpeg_status_label.setStyleSheet("color: green;")
                self.install_ffmpeg_btn.setVisible(False)
            else:
                self.ffmpeg_status_label.setText("✗ FFmpeg 未安装")
                self.ffmpeg_status_label.setStyleSheet("color: red;")
                self.install_ffmpeg_btn.setVisible(True)
        except Exception as e:
            self.ffmpeg_status_label.setText(f"检测失败: {e}")
            self.install_ffmpeg_btn.setVisible(True)

    def _install_ffmpeg(self):
        """安装 FFmpeg"""
        self._log("开始下载 FFmpeg...")
        self.install_ffmpeg_btn.setEnabled(False)

        def do_install():
            try:
                import asyncio
                from utils.ffmpeg_setup import install_ffmpeg

                async def install():
                    success, msg = await install_ffmpeg()
                    return success, msg

                loop = asyncio.new_event_loop()
                result = loop.run_until_complete(install())
                loop.close()

                if result[0]:
                    self._log(f"FFmpeg 安装成功: {result[1]}")
                else:
                    self._log(f"FFmpeg 安装失败: {result[1]}")

                # 刷新状态
                self._check_ffmpeg_status()
                self.install_ffmpeg_btn.setEnabled(True)

            except Exception as e:
                self._log(f"FFmpeg 安装出错: {e}")
                self.install_ffmpeg_btn.setEnabled(True)

        threading.Thread(target=do_install, daemon=True).start()

    def _setup_js_callbacks(self):
        """设置 JavaScript 回调"""
        # Recording control callback
        def recording_control(action, params=None):
            params = params or {}
            room_id = params.get('roomId', '')

            if action == 'start':
                self._log(f"开始录制房间: {room_id}")
                # 触发 JS 端开始录制
                self.webview.page().runJavaScript("startRecording()")
            elif action == 'stop':
                self._log(f"停止录制房间: {room_id}")
                self.webview.page().runJavaScript("stopRecording()")

        # Save recording callback
        def save_recording(params=None):
            params = params or {}
            self._log(f"录制已保存: {params}")

        # RTMP control callback
        def rtmp_control(action, params=None):
            params = params or {}
            url = params.get('url', '')

            if action == 'start':
                self._log(f"开始 RTMP 推流: {url}")
            elif action == 'stop':
                self._log(f"停止 RTMP 推流")

        # FFmpeg status callback
        def get_ffmpeg_status():
            try:
                from core.ffmpeg_tool import get_ffmpeg
                ffmpeg = get_ffmpeg()
                return {"available": ffmpeg.available}
            except:
                return {"available": False}

        # 注册到 JS
        self.webview.page().runJavaScript("""
            window.pythonRecordingControl = null;
            window.pythonSaveRecording = null;
            window.pythonRtmpControl = null;
            window.pythonGetFfmpegStatus = null;
        """)

    def _start_rtmp(self):
        """开始 RTMP 推流"""
        url = self.rtmp_url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "警告", "请输入 RTMP 地址")
            return

        self._log(f"开始 RTMP 推流: {url}")
        self.start_rtmp_btn.setEnabled(False)
        self.stop_rtmp_btn.setEnabled(True)

        # 通知 JS
        self.webview.page().runJavaScript(f"""
            window.pythonRtmpControl = function(action, params) {{}};
            document.getElementById('rtmpUrlInput').value = '{url}';
        """)

    def _stop_rtmp(self):
        """停止 RTMP 推流"""
        self._log("停止 RTMP 推流")
        self.start_rtmp_btn.setEnabled(True)
        self.stop_rtmp_btn.setEnabled(False)

    def _start_signaling_server(self):
        """启动信令服务器"""
        try:
            # 在独立线程中运行 asyncio
            def run_server():
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
                self._loop.run_until_complete(self._start_server_async())

            self._server_thread = threading.Thread(target=run_server, daemon=True)
            self._server_thread.start()

            self._log("信令服务器启动中...")
            QTimer.singleShot(1000, lambda: self._log("信令服务器就绪"))

        except Exception as e:
            self._log(f"启动信令服务器失败: {e}")
            logger.error(f"启动信令服务器失败: {e}")

    async def _start_server_async(self):
        """异步启动服务器"""
        try:
            from core.webrtc import SignalingServer
            self.signaling_server = SignalingServer(
                host=self._config["signaling_host"],
                port=self._config["signaling_port"]
            )

            # 设置回调
            self.signaling_server.on_room_created = self._on_room_created
            self.signaling_server.on_participant_joined = self._on_participant_joined
            self.signaling_server.on_participant_left = self._on_participant_left

            await self.signaling_server.start()
            self._log(f"信令服务器已启动: ws://{self._config['signaling_host']}:{self._config['signaling_port']}")

        except Exception as e:
            self._log(f"启动服务器异常: {e}")
            logger.error(f"启动服务器异常: {e}")

    async def _create_room_async(self, room_name: str, user_name: str, peer_id: str):
        """创建房间"""
        if not self.signaling_server:
            return {"success": False, "error": "服务器未启动"}

        try:
            room_id = f"room_{peer_id}"
            self.signaling_server.rooms[room_id] = type('Room', (), {
                'id': room_id,
                'name': room_name,
                'participants': {},
                'is_live': False
            })()

            # 注入 ICE 配置
            await self._inject_ice_config_async()

            self.room_created.emit(room_id, room_name)
            self._log(f"房间已创建: {room_name} ({room_id})")

            return {"success": True, "roomId": room_id}

        except Exception as e:
            self._log(f"创建房间失败: {e}")
            return {"success": False, "error": str(e)}

    async def _join_room_async(self, room_id: str, user_name: str, peer_id: str):
        """加入房间"""
        if not self.signaling_server:
            return {"success": False, "error": "服务器未启动"}

        if room_id not in self.signaling_server.rooms:
            return {"success": False, "error": "房间不存在"}

        # 注入 ICE 配置
        await self._inject_ice_config_async()

        self._log(f"已加入房间: {room_id}")
        return {"success": True, "roomId": room_id}

    async def _inject_ice_config_async(self):
        """异步注入 ICE 配置"""
        try:
            from core.webrtc import select_best_ice_config

            config = await select_best_ice_config(
                cloud_turn_url=self.turn_url_input.text(),
                cloud_turn_user=self.turn_user_input.text(),
                cloud_turn_credential=self.turn_pass_input.text()
            )

            js_config = config.to_js_config()
            self._inject_ice_config(js_config)

        except Exception as e:
            self._log(f"ICE 配置获取失败: {e}")

    def _inject_ice_config(self, config: dict):
        """注入 ICE 配置到 WebView"""
        js = f"window.setIceConfig({config})"
        self.webview.page().runJavaScript(js)
        self._log(f"ICE 配置已更新: {len(config.get('iceServers', []))} 服务器")

    def _probe_network(self):
        """探测网络环境"""
        self.probe_result.clear()
        self.probe_result.append("正在探测...")

        def run_probe():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def probe():
                try:
                    from core.webrtc import select_best_ice_config

                    result = await select_best_ice_config(
                        cloud_turn_url=self.turn_url_input.text(),
                        cloud_turn_user=self.turn_user_input.text(),
                        cloud_turn_credential=self.turn_pass_input.text()
                    )

                    self.probe_result.clear()
                    self.probe_result.append(f"探测完成!")
                    self.probe_result.append(f"ICE 服务器数量: {len(result.ice_servers)}")
                    for i, server in enumerate(result.ice_servers):
                        self.probe_result.append(f"  [{i+1}] {server.urls[0]} ({server.tier.name})")

                    # 注入配置
                    self._inject_ice_config(result.to_js_config())

                except Exception as e:
                    self.probe_result.clear()
                    self.probe_result.append(f"探测失败: {e}")

            loop.run_until_complete(probe())

        threading.Thread(target=run_probe, daemon=True).start()

    def _toggle_connection(self):
        """切换连接状态"""
        if self.connect_btn.text() == "连接":
            self._log("正在连接到信令服务器...")
            self.connect_btn.setText("断开")
            self.status_label.setText("状态: 已连接")
        else:
            self.connect_btn.setText("连接")
            self.status_label.setText("状态: 未连接")

    def _start_live(self):
        """开始直播"""
        self.start_live_btn.setEnabled(False)
        self.stop_live_btn.setEnabled(True)
        self._log("直播已开始")

        js = "window.startLive && window.startLive()"
        self.webview.page().runJavaScript(js)

    def _stop_live(self):
        """停止直播"""
        self.start_live_btn.setEnabled(True)
        self.stop_live_btn.setEnabled(False)
        self._log("直播已停止")

        js = "window.stopLive && window.stopLive()"
        self.webview.page().runJavaScript(js)

    async def _on_room_created(self, room_id: str, room_name: str):
        """房间创建回调"""
        self._log(f"[回调] 房间创建: {room_name}")

    async def _on_participant_joined(self, room_id: str, peer_id: str):
        """参与者加入回调"""
        self._log(f"[回调] 用户加入: {peer_id}")
        self.participant_joined.emit(room_id, peer_id)

    async def _on_participant_left(self, room_id: str, peer_id: str):
        """参与者离开回调"""
        self._log(f"[回调] 用户离开: {peer_id}")

    def _get_embedded_html(self):
        """获取内嵌 HTML (简化版)"""
        return """
        <html><body style="background:#1f2937;color:white;display:flex;align-items:center;justify-content:center;height:100vh;">
        <div style="text-align:center">
            <h2>Hermes WebRTC</h2>
            <p>正在加载...</p>
        </div>
        </body></html>
        """

    def closeEvent(self, event):
        """关闭时清理"""
        if self._loop and self.signaling_server:
            asyncio.ensure_future(self.signaling_server.stop())
        event.accept()
