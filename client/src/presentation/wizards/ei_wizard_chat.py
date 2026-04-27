"""
EIWizard - 环评报告生成向导（极简聊天界面）
===============================================

采用自我学习策略 + 极简聊天界面设计。

设计理念：
1. 极简 UI - 类似 ChatGPT 的聊天界面
2. 对话式需求澄清 - Agent 通过对话引导用户输入
3. 自我学习 - 不预置判断逻辑，让 Agent 自己学习

Author: LivingTreeAI Agent
Date: 2026-04-27
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QScrollArea, QWidget, QLabel, QTextEdit, QPushButton,
    QFileDialog, QMessageBox,
)
from PySide6.QtCore import Qt, Signal, Slot, QTimer, QUrl
from PySide6.QtGui import QFont, QIcon, QTextCursor, QDesktopServices

import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)


class MessageBubble(QWidget):
    """消息气泡组件"""
    
    def __init__(self, role: str, content: str = "", parent=None):
        """
        初始化消息气泡
        
        Args:
            role: 'user' 或 'assistant'
            content: 消息内容
            parent: 父组件
        """
        super().__init__(parent)
        self.role = role
        self.content = content
        self.init_ui()
    
    def init_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 5, 10, 5)
        
        # 创建气泡标签
        self.bubble_label = QLabel(self.content)
        self.bubble_label.setWordWrap(True)
        self.bubble_label.setMaximumWidth(600)
        self.bubble_label.setStyleSheet(self._get_bubble_style())
        
        if self.role == 'user':
            # 用户消息：右侧，蓝色背景
            layout.addStretch()
            layout.addWidget(self.bubble_label)
        else:
            # 助手消息：左侧，灰色背景
            layout.addWidget(self.bubble_label)
            layout.addStretch()
        
        self.setLayout(layout)
    
    def _get_bubble_style(self) -> str:
        """获取气泡样式"""
        if self.role == 'user':
            return """
                QLabel {
                    background-color: #0078d4;
                    color: white;
                    border-radius: 10px;
                    padding: 10px;
                    font-size: 14px;
                }
            """
        else:
            return """
                QLabel {
                    background-color: #f0f0f0;
                    color: #333;
                    border-radius: 10px;
                    padding: 10px;
                    font-size: 14px;
                }
            """
    
    def update_content(self, content: str):
        """更新消息内容（用于流式输出）"""
        self.content = content
        self.bubble_label.setText(content)


class ImageBubble(QWidget):
    """图片消息气泡（P2 新增）"""
    
    def __init__(self, image_path: str, role: str = 'user', parent=None):
        """
        初始化图片气泡
        
        Args:
            image_path: 图片路径
            role: 'user' 或 'assistant'
            parent: 父组件
        """
        super().__init__(parent)
        self.image_path = image_path
        self.role = role
        self.init_ui()
    
    def init_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 5, 10, 5)
        
        # 创建图片标签
        from PySide6.QtGui import QPixmap
        from PySide6.QtCore import Qt
        
        self.image_label = QLabel()
        pixmap = QPixmap(self.image_path)
        
        # 缩放图片（最大宽度 300px）
        scaled_pixmap = pixmap.scaledToWidth(
            300, Qt.TransformationMode.SmoothTransformation
        )
        self.image_label.setPixmap(scaled_pixmap)
        self.image_label.setStyleSheet("""
            QLabel {
                border: 1px solid #e0e0e0;
                border-radius: 10px;
                padding: 5px;
                background-color: white;
            }
        """)
        
        # 点击图片打开原图
        self.image_label.mousePressEvent = self._open_image
        
        if self.role == 'user':
            # 用户消息：右侧
            layout.addStretch()
            layout.addWidget(self.image_label)
        else:
            # 助手消息：左侧
            layout.addWidget(self.image_label)
            layout.addStretch()
        
        self.setLayout(layout)
    
    def _open_image(self, event):
        """点击图片打开原图"""
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.image_path))


class FileBubble(QWidget):
    """文件消息气泡（P2 新增）"""
    
    def __init__(self, file_path: str, role: str = 'user', parent=None):
        """
        初始化文件气泡
        
        Args:
            file_path: 文件路径
            role: 'user' 或 'assistant'
            parent: 父组件
        """
        super().__init__(parent)
        self.file_path = file_path
        self.role = role
        self.init_ui()
    
    def init_ui(self):
        from PySide6.QtGui import QFont
        
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 5, 10, 5)
        
        # 创建文件图标和名称标签
        container = QWidget()
        container.setStyleSheet("""
            QWidget {
                border: 1px solid #e0e0e0;
                border-radius: 10px;
                padding: 10px;
                background-color: white;
            }
            QWidget:hover {
                background-color: #f5f5f5;
            }
        """)
        container.mousePressEvent = self._open_file
        
        container_layout = QVBoxLayout(container)
        
        # 文件图标
        icon_label = QLabel("📄")
        icon_label.setStyleSheet("font-size: 32px;")
        container_layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignCenter)
        
        # 文件名称
        from pathlib import Path
        filename = Path(self.file_path).name
        name_label = QLabel(filename)
        name_label.setStyleSheet("""
            font-size: 12px;
            color: #333333;
            padding: 5px;
        """)
        name_label.setWordWrap(True)
        name_label.setMaximumWidth(200)
        container_layout.addWidget(name_label)
        
        if self.role == 'user':
            # 用户消息：右侧
            layout.addStretch()
            layout.addWidget(container)
        else:
            # 助手消息：左侧
            layout.addWidget(container)
            layout.addStretch()
        
        self.setLayout(layout)
    
    def _open_file(self, event):
        """点击文件打开"""
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.file_path))


class EIWizardChat(QWidget):
    """
    环评报告生成向导（极简聊天界面）
    
    采用对话式需求澄清：
    1. Agent 询问用户需求
    2. 用户回复
    3. Agent 分析问题，引导用户提供更多信息
    4. 自动调用工具完成任务
    """
    
    # 信号
    task_started = Signal(str)  # 任务开始（任务ID）
    task_completed = Signal(dict)  # 任务完成（结果）
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.message_history = []
        self.current_assistant_bubble = None
        self.agent_available = False
        
        # 任务状态轮询
        self.current_task_id = None
        self.poll_timer = QTimer()
        self.poll_timer.timeout.connect(self._on_timer_timeout)
        self.poll_interval = 5000  # 5秒轮询一次
        
        # 初始化 Agent
        self._init_agent()
        
        # 初始化 UI
        self.init_ui()
        
        # 显示欢迎消息
        self._show_welcome()
    
    def _init_agent(self):
        """初始化 EIAgent"""
        try:
            from client.src.business.ei_agent.ei_agent_adapter import (
                get_ei_agent_adapter,
                submit_ei_task,
            )
            self.adapter = get_ei_agent_adapter()
            self.submit_task = submit_ei_task
            self.agent_available = True
            logger.info("[EIWizardChat] EIAgent 初始化成功")
        except Exception as e:
            logger.warning(f"[EIWizardChat] EIAgent 初始化失败: {e}")
            self.adapter = None
            self.submit_task = None
    
    def init_ui(self):
        """初始化 UI（极简设计）"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 1. 聊天历史显示区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #fafafa;
                border: none;
            }
        """)
        
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_layout.addStretch()
        
        self.scroll_area.setWidget(self.scroll_content)
        layout.addWidget(self.scroll_area, 1)
        
        # 2. 输入区域（极简）
        input_container = QWidget()
        input_container.setStyleSheet("""
            QWidget {
                background-color: white;
                border-top: 1px solid #e0e0e0;
            }
        """)
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(10, 10, 10, 10)
        
        # 文件上传按钮（P2 新增）
        self.upload_btn = QPushButton("📎")
        self.upload_btn.setFixedSize(40, 40)
        self.upload_btn.setToolTip("上传文件（图片、文档等）")
        self.upload_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #e0e0e0;
                border-radius: 5px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
            }
        """)
        self.upload_btn.clicked.connect(self._upload_file)
        input_layout.addWidget(self.upload_btn)
        
        # 语音输入按钮（P2 新增）
        self.voice_btn = QPushButton("🎤")
        self.voice_btn.setFixedSize(40, 40)
        self.voice_btn.setToolTip("语音输入（开发中）")
        self.voice_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #e0e0e0;
                border-radius: 5px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
            }
            QPushButton:checked {
                background-color: #ff4444;
                color: white;
            }
        """)
        self.voice_btn.setCheckable(True)
        self.voice_btn.clicked.connect(self._toggle_voice_input)
        input_layout.addWidget(self.voice_btn)
        
        # 消息输入框
        self.message_input = QTextEdit()
        self.message_input.setMaximumHeight(80)
        self.message_input.setPlaceholderText("输入你的需求，我会帮你生成环评报告...")
        self.message_input.setStyleSheet("""
            QTextEdit {
                border: 1px solid #e0e0e0;
                border-radius: 5px;
                padding: 8px;
                font-size: 14px;
                background-color: #fafafa;
            }
            QTextEdit:focus {
                border: 1px solid #0078d4;
            }
        """)
        
        # Ctrl+Enter 发送
        # 注意：PySide6 的快捷键设置需要额外处理
        
        input_layout.addWidget(self.message_input, 1)
        
        # 发送按钮
        self.send_btn = QPushButton("发送")
        self.send_btn.setFixedSize(80, 40)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.send_btn.clicked.connect(self._send_message)
        input_layout.addWidget(self.send_btn)
        
        layout.addWidget(input_container)
        
        self.setLayout(layout)
    
    def _show_welcome(self):
        """显示欢迎消息"""
        welcome_text = """👋 你好！我是环评助手。

我可以帮你：
- 📄 生成环评报告
- 🔍 查询环保法规
- 📊 计算污染物排放
- 🗺️ 分析环境敏感点
- 📝 学习 Word 模板格式

请告诉我你需要什么帮助？"""
        
        self._add_message('assistant', welcome_text)
    
    def _send_message(self):
        """发送消息"""
        message = self.message_input.toPlainText().strip()
        if not message:
            return
        
        # 显示用户消息
        self._add_message('user', message)
        
        # 清空输入框
        self.message_input.clear()
        
        # 处理消息
        self._process_message(message)
    
    def _process_message(self, message: str):
        """处理用户消息（调用 Agent）"""
        if not self.agent_available:
            self._add_message('assistant', "⚠️ EIAgent 不可用，请检查系统配置。")
            return
        
        # 显示"正在思考"提示
        self._add_message('assistant', "🤔 正在思考...")
        
        # 调用 Agent（异步）
        try:
            # 提交任务给 EIAgent
            task_id = self.submit_task(
                task_type="report_generation",  # 默认任务类型
                params={"message": message}
            )
            
            # 启动定时器，轮询任务状态
            self._check_task_status(task_id)
            
        except Exception as e:
            logger.error(f"[EIWizardChat] 调用 Agent 失败: {e}")
            self._update_last_assistant_message(f"❌ 调用失败: {str(e)}")
    
    def _check_task_status(self, task_id: str):
        """检查任务状态（异步轮询）"""
        self.current_task_id = task_id
        
        # 更新 UI 显示任务已提交
        self._update_last_assistant_message(
            f"✅ 任务已提交（ID: {task_id}）\n\n⏳ 正在处理中..."
        )
        
        # 启动定时器，每隔 5 秒检查一次任务状态
        self.poll_timer.start(self.poll_interval)
        
        logger.info(f"[EIWizardChat] 启动任务状态轮询: {task_id}")
    
    def _on_timer_timeout(self):
        """定时器超时 - 检查任务状态"""
        if not self.current_task_id:
            self.poll_timer.stop()
            return
        
        try:
            # 查询任务状态
            from client.src.business.ei_agent.ei_agent_adapter import get_ei_agent_adapter
            adapter = get_ei_agent_adapter()
            
            status = adapter.get_task_status(self.current_task_id)
            
            if status is None:
                # 任务不存在
                self.poll_timer.stop()
                self._update_last_assistant_message(
                    f"❌ 任务不存在或已丢失（ID: {self.current_task_id}）"
                )
                self.current_task_id = None
                return
            
            # 根据状态更新 UI
            if status.value == "COMPLETED":
                # 任务完成
                self.poll_timer.stop()
                self._on_task_completed(self.current_task_id)
                self.current_task_id = None
                
            elif status.value == "FAILED":
                # 任务失败
                self.poll_timer.stop()
                result = adapter.get_task_result(self.current_task_id)
                error_msg = result.get("error", "未知错误") if result else "任务执行失败"
                self._update_last_assistant_message(
                    f"❌ 任务失败（ID: {self.current_task_id}）\n\n错误：{error_msg}"
                )
                self.current_task_id = None
                
            elif status.value == "CANCELLED":
                # 任务被取消
                self.poll_timer.stop()
                self._update_last_assistant_message(
                    f"⚠️ 任务已取消（ID: {self.current_task_id}）"
                )
                self.current_task_id = None
                
            else:
                # 任务仍在运行（PENDING, RUNNING）
                # 更新 UI 显示进度（可以显示旋转动画或进度条）
                logger.debug(f"[EIWizardChat] 任务运行中: {self.current_task_id} - {status.value}")
                
        except Exception as e:
            logger.error(f"[EIWizardChat] 检查任务状态失败: {e}")
            # 继续执行，不停止定时器
    
    def _on_task_completed(self, task_id: str):
        """任务完成处理"""
        try:
            from client.src.business.ei_agent.ei_agent_adapter import get_ei_agent_adapter
            adapter = get_ei_agent_adapter()
            
            # 获取任务结果
            result = adapter.get_task_result(task_id)
            
            if not result:
                self._update_last_assistant_message(
                    f"✅ 任务完成（ID: {task_id}）\n\n（无返回结果）"
                )
                return
            
            # 格式化结果
            formatted_result = self._format_task_result(result)
            
            # 更新 UI
            self._update_last_assistant_message(
                f"✅ 任务完成（ID: {task_id}）\n\n{formatted_result}"
            )
            
            logger.info(f"[EIWizardChat] 任务完成: {task_id}")
            
        except Exception as e:
            logger.error(f"[EIWizardChat] 处理任务结果失败: {e}")
            self._update_last_assistant_message(
                f"✅ 任务完成（ID: {task_id}）\n\n⚠️ 结果解析失败: {str(e)}"
            )
    
    def _format_task_result(self, result: Dict) -> str:
        """格式化任务结果（用于显示）"""
        task_type = result.get("task_type", "unknown")
        
        if task_type == "report_generation":
            # 报告生成
            project_name = result.get("project_name", "")
            report_path = result.get("report_path", "")
            message = result.get("message", "")
            
            return f"""📄 报告生成完成

**项目名称**: {project_name}
**报告路径**: {report_path}
**状态**: {message}

---
✅ 已解析 {result.get('parsed_attachments_count', 0)} 个附件
✅ 检索到 {result.get('regulations_count', 0)} 条相关法规
"""
            
        elif task_type == "regulation_retrieval":
            # 法规检索
            regulations = result.get("regulations", [])
            count = result.get("count", 0)
            
            if count == 0:
                return "📚 法规检索完成\n\n未找到相关法规。"
            
            lines = [f"📚 法规检索完成，找到 {count} 条相关法规：\n"]
            for i, reg in enumerate(regulations[:5], 1):  # 最多显示5条
                title = reg.get("title", "未知标题")
                score = reg.get("score", 0)
                lines.append(f"{i}. **{title}**（相关度: {score:.2f}）")
            
            if count > 5:
                lines.append(f"\n...还有 {count - 5} 条法规未显示")
            
            return "\n".join(lines)
            
        else:
            # 其他任务类型，直接转换为字符串
            import json
            try:
                return json.dumps(result, ensure_ascii=False, indent=2)
            except:
                return str(result)
    
    def _add_message(self, role: str, content: str):
        """添加消息到聊天历史"""
        self.message_history.append({'role': role, 'content': content})
        
        # 创建消息气泡
        bubble = MessageBubble(role, content)
        self.scroll_layout.insertWidget(self.scroll_layout.count() - 1, bubble)
        
        # 如果是助手消息，保存引用（用于更新）
        if role == 'assistant':
            self.current_assistant_bubble = bubble
        
        # 滚动到底部
        self._scroll_to_bottom()
    
    def _update_last_assistant_message(self, content: str):
        """更新最后一个助手消息（用于流式输出）"""
        if self.current_assistant_bubble:
            self.current_assistant_bubble.update_content(content)
        else:
            self._add_message('assistant', content)
    
    def _scroll_to_bottom(self):
        """滚动到底部"""
        scrollbar = self.scroll_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def append_stream_chunk(self, chunk: str):
        """追加流式输出内容"""
        if not self.current_assistant_bubble:
            self._add_message('assistant', chunk)
        else:
            current_content = self.current_assistant_bubble.content
            self.current_assistant_bubble.update_content(current_content + chunk)
    
    def clear_history(self):
        """清空聊天历史"""
        # 删除所有消息气泡
        while self.scroll_layout.count() > 1:  # 保留最后的 stretch
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.message_history = []
        self.current_assistant_bubble = None
        
        # 显示欢迎消息
        self._show_welcome()
    
    # ── P2 功能：文件上传 ────────────────────────────────────────────────────
    
    def _upload_file(self):
        """上传文件（图片、文档等）"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择文件",
            "",
            "所有文件 (*);;图片文件 (*.png *.jpg *.jpeg *.gif *.bmp *.webp);;文档文件 (*.pdf *.doc *.docx *.xls *.xlsx);;文本文件 (*.txt *.md *.csv)"
        )
        
        if not file_path:
            return
        
        # 判断文件类型
        file_ext = Path(file_path).suffix.lower()
        
        # 图片文件
        if file_ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']:
            self._add_image_message(file_path)
            
        # 文档文件
        elif file_ext in ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.txt', '.md', '.csv']:
            self._add_file_message(file_path)
            
        # 其他文件
        else:
            self._add_file_message(file_path)
    
    def _add_image_message(self, image_path: str):
        """添加图片消息（用户上传的图片）"""
        # 创建图片气泡
        bubble = ImageBubble(image_path, role='user')
        self.scroll_layout.insertWidget(self.scroll_layout.count() - 1, bubble)
        
        # 记录到历史
        self.message_history.append({
            'role': 'user',
            'content': f"[图片: {Path(image_path).name}]",
            'type': 'image',
            'path': image_path
        })
        
        # 滚动到底部
        self._scroll_to_bottom()
        
        # TODO: 将图片发送给 Agent 处理
        self._process_image(image_path)
    
    def _add_file_message(self, file_path: str):
        """添加文件消息（用户上传的文件）"""
        # 创建文件气泡
        bubble = FileBubble(file_path, role='user')
        self.scroll_layout.insertWidget(self.scroll_layout.count() - 1, bubble)
        
        # 记录到历史
        self.message_history.append({
            'role': 'user',
            'content': f"[文件: {Path(file_path).name}]",
            'type': 'file',
            'path': file_path
        })
        
        # 滚动到底部
        self._scroll_to_bottom()
        
        # TODO: 将文件发送给 Agent 处理
        self._process_file(file_path)
    
    def _process_image(self, image_path: str):
        """处理图片（发送给 Agent）"""
        # 显示"正在处理"消息
        self._add_message('assistant', f"🖼️ 正在分析图片: {Path(image_path).name}...")
        
        # TODO: 调用 Agent 处理图片（OCR、图像识别等）
        # 这里可以调用 intelligent_ocr 工具或视觉模型
        
        # 模拟处理完成
        QTimer.singleShot(2000, lambda: self._update_last_assistant_message(
            f"🖼️ 图片分析完成: {Path(image_path).name}\n\n（图片识别功能开发中...）"
        ))
    
    def _process_file(self, file_path: str):
        """处理文件（发送给 Agent）"""
        # 显示"正在处理"消息
        self._add_message('assistant', f"📄 正在解析文件: {Path(file_path).name}...")
        
        # TODO: 调用 Agent 处理文件（OCR、文档解析等）
        # 这里可以调用 intelligent_ocr 工具
        
        # 模拟处理完成
        QTimer.singleShot(2000, lambda: self._update_last_assistant_message(
            f"📄 文件解析完成: {Path(file_path).name}\n\n（文档解析功能开发中...）"
        ))
    
    # ── P2 功能：语音输入 ────────────────────────────────────────────────────
    
    def _toggle_voice_input(self, checked: bool):
        """切换语音输入状态"""
        if checked:
            # 开始录音
            self.voice_btn.setText("⏺️")  # 录音中图标
            self.voice_btn.setToolTip("点击停止录音")
            self._start_voice_recording()
        else:
            # 停止录音
            self.voice_btn.setText("🎤")
            self.voice_btn.setToolTip("语音输入（开发中）")
            self._stop_voice_recording()
    
    def _start_voice_recording(self):
        """开始语音录音"""
        # TODO: 实现语音录音功能
        # 可以使用 sounddevice、pyaudio 等库录音
        # 然后使用 speech_recognition 或 Whisper 进行语音识别
        
        self._add_message('assistant', "🎤 语音输入功能开发中...\n\n（需要安装语音识别库）")
        
        # 模拟录音 3 秒后自动停止
        QTimer.singleShot(3000, lambda: self.voice_btn.setChecked(False))
    
    def _stop_voice_recording(self):
        """停止语音录音"""
        # TODO: 停止录音，并进行语音识别
        pass
    
    def _on_voice_recognized(self, text: str):
        """语音识别完成"""
        # 将识别结果填入输入框
        self.message_input.setText(text)
        
        # 可选：自动发送
        # self._send_message()


# ============================================================
# 主窗口（可选，用于独立运行）
# ============================================================

class EIWizardWindow(QWidget):
    """EIWizard 主窗口（极简设计）"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("环评助手")
        self.setMinimumSize(800, 600)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # 标题栏（极简）
        title_bar = QWidget()
        title_bar.setStyleSheet("""
            QWidget {
                background-color: #0078d4;
                color: white;
                padding: 10px;
            }
        """)
        title_layout = QHBoxLayout(title_bar)
        title_label = QLabel("环评助手")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        
        # 清空按钮
        clear_btn = QPushButton("清空")
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: white;
                border: 1px solid white;
                border-radius: 3px;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.2);
            }
        """)
        clear_btn.clicked.connect(self._clear_chat)
        title_layout.addWidget(clear_btn)
        
        layout.addWidget(title_bar)
        
        # 聊天界面
        self.chat_widget = EIWizardChat()
        layout.addWidget(self.chat_widget, 1)
        
        self.setLayout(layout)
    
    def _clear_chat(self):
        """清空聊天历史"""
        self.chat_widget.clear_history()


if __name__ == '__main__':
    import sys
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    window = EIWizardWindow()
    window.show()
    sys.exit(app.exec())
