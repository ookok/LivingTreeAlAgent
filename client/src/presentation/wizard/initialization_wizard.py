"""
LivingTree AI Agent - 系统初始化向导

首次启动时引导用户完成：
1. Welcome 欢迎页
2. Ollama 连接配置 (基础服务)
3. 模型下载/选择 (L0/L1)
4. Agent 初始化配置
5. 专家模块选择
6. 预览与确认
7. 完成并启动
"""
from enum import Enum
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QMessageBox,
    QLabel, QLineEdit, QPushButton, QRadioButton,
    QGroupBox, QFormLayout, QCheckBox,
    QFrame, QWidget, QScrollArea,
    QProgressBar, QTextBrowser,
    QApplication, QStackedWidget,
    QDialogButtonBox,
)
from PyQt6.QtGui import QPainter, QColor, QFont, QIcon

from client.src.business.config import (
    AppConfig, OllamaConfig, ModelPathConfig,
    ModelMarketConfig, AgentConfig, ModelStoreConfig,
    DEFAULT_CONFIG, load_config, save_config, _get_config_dir,
)


class WizardStep(Enum):
    WELCOME = 0
    L0_L1_CONFIG = 1
    MODEL_CONFIG = 2
    AGENT_CONFIG = 3
    EXPERT_CHECK = 4
    REVIEW = 5
    COMPLETE = 6


class InitializationWizard(QDialog):
    """
    系统初始化向导
    7 步流程引导用户完成首次配置
    """

    wizard_completed = pyqtSignal(object)  # 完成时发送 AppConfig

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = AppConfig()
        self.config_path = _get_config_dir() / "config.json"
        self._current_step = WizardStep.WELCOME
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("🌳 欢迎使用 LivingTree AI Agent")
        self.setMinimumSize(850, 620)
        self.resize(900, 680)

        # 主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 顶部状态栏
        header = self._create_header()
        layout.addWidget(header, 1)

        # 内容区 - 堆叠 widget
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background: #f0f2f5;")
        layout.addWidget(self.stack, 1)

        # 底部按钮
        footer = self._create_footer()
        layout.addWidget(footer, 1)

        # 添加所有步骤页面
        self.stack.addWidget(self._create_welcome_page())
        self.stack.addWidget(self._create_model_page())
        self.stack.addWidget(self._create_agent_page())
        self.stack.addWidget(self._create_review_page())
        self.stack.addWidget(self._create_complete_page())

        self.stack.setCurrentIndex(0)

    def _create_header(self) -> QFrame:
        """创建顶部步骤条"""
        frame = QFrame()
        frame.setFixedHeight(80)
        frame.setStyleSheet("""
            QFrame {
                background: #ffffff;
                border-bottom: 1px solid #e5e7eb;
            }
        """)

        lay = QVBoxLayout(frame)
        lay.setContentsMargins(30, 10, 30, 5)

        # 步骤指示器
        step_names = ["欢迎", "模型配置", "代理设置", "完成"]
        lay.addWidget(QLabel("🌳 快速配置向导"))

        self.step_labels = []
        h_lay = QHBoxLayout()
        h_lay.setSpacing(0)

        for i, step_name in enumerate(step_names):
            # 步骤圆圈
            circle = QFrame()
            circle.setFixedSize(32, 32)
            circle.setStyleSheet("""
                QFrame {
                    background: #e5e7eb;
                    border-radius: 16px;
                    color: #9ca3af;
                }
                QFrame.active {
                    background: #3b82f6;
                    color: white;
                }
            """)
            circle.setObjectName(f"step_{i}")
            label = QLabel(str(i + 1))
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("color: inherit; font-weight: bold;")
            lay = QHBoxLayout(circle)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.addWidget(label)
            h_lay.addWidget(circle)
            self.step_labels.append((circle, step_name))

            # 连接线
            if i < len(step_names) - 1:
                line = QFrame()
                line.setFixedHeight(2)
                line.setStyleSheet("background: #e5e7eb;")
                line.setFixedWidth(60)
                h_lay.addWidget(line)

        # 更新步骤样式
        self._update_step_indicator(0)

        h_lay.addStretch()
        lay.addLayout(h_lay)

        return frame

    def _update_step_indicator(self, step_idx: int):
        for i, (circle, name) in enumerate(self.step_labels):
            if i <= step_idx:
                circle.setStyleSheet("background: #3b82f6; border-radius: 16px;")
                circle.findChildren(QLabel)[0].setStyleSheet("color: white;")
            else:
                circle.setStyleSheet("background: #e5e7eb; border-radius: 16px;")
                circle.findChildren(QLabel)[0].setStyleSheet("color: #9ca3af;")

    def _create_footer(self) -> QWidget:
        """创建底部导航按钮"""
        widget = QWidget()
        widget.setStyleSheet("background: #ffffff; border-top: 1px solid #e5e7eb;")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(30, 12, 30, 12)

        self.btn_prev = QPushButton("← 上一步")
        self.btn_prev.setFixedHeight(38)
        self.btn_prev.setDisabled(True)
        self.btn_prev.clicked.connect(self._go_prev)
        layout.addWidget(self.btn_prev)

        layout.addStretch()

        self.btn_next = QPushButton("下一步 →")
        self.btn_next.setFixedHeight(38)
        self.btn_next.setMinimumWidth(120)
        self.btn_next.setStyleSheet("""
            QPushButton {
                background: #3b82f6;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #2563eb;
            }
            QPushButton:disabled {
                background: #9ca3af;
            }
        """)
        self.btn_next.clicked.connect(self._go_next)
        layout.addWidget(self.btn_next)

        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setFixedHeight(38)
        self.btn_cancel.clicked.connect(self.reject)
        layout.addWidget(self.btn_cancel)

        return widget

    def _create_welcome_page(self) -> QWidget:
        """第 1 步：欢迎页"""
        page = QWidget()
        page.setStyleSheet("background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);")
        lay = QVBoxLayout(page)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(20)

        # 大图标
        icon = QLabel("🌳")
        icon.setFixedSize(100, 100)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("font-size: 80px;")
        lay.addWidget(icon)

        title = QLabel("🌳 欢迎使用 LivingTree AI Agent")
        title.setStyleSheet("""
            font-size: 36px;
            font-weight: bold;
            color: white;
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(title)

        subtitle = QLabel("只需几步即可完成配置，开始您的智能代理之旅")
        subtitle.setStyleSheet("font-size: 16px; color: rgba(255,255,255,0.8);")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(subtitle)

        lay.addSpacing(30)

        features = [
            ("🔍", "多源深度搜索", "支持搜索引擎与本地知识库"),
            ("🧠", "本地大模型", "基于 Ollama 与 GGUF 模型"),
            ("🛠️", "AI 智能助手", "Agent 自动执行复杂任务"),
            ("☁️", "企业功能", "P2P 存储/云盘/商城"),
        ]

        grid_layout = QFormLayout()
        grid_layout.setSpacing(16)
        for icon, name, desc in features:
            group = QGroupBox()
            group.setStyleSheet("color: white;")
            grp_lay = QVBoxLayout(group)
            grp_title = QLabel(f"{icon} {name}")
            grp_title.setStyleSheet("font-size: 16px; font-weight: bold; color: white;")
            grp_desc = QLabel(desc)
            grp_desc.setStyleSheet("color: rgba(255,255,255,0.7); font-size: 13px;")
            grp_layout = QVBoxLayout(group)
            grp_layout.setContentsMargins(12, 12, 12, 12)
            grp_layout.setSpacing(6)
            grp_layout.addWidget(grp_title)
            grp_layout.addWidget(grp_desc)
            grid_layout.addRow(group)

        lay.addLayout(grid_layout)
        return page

    def _create_model_page(self) -> QWidget:
        """第 2 步：模型配置页"""
        page = QWidget()
        lay = QFormLayout(page)
        lay.setSpacing(16)

        # Ollama 设置
        ollama_frame = QGroupBox("Ollama 服务")
        ollama_frame.setStyleSheet("color: #334155;")
        ollama_layout = QVBoxLayout(ollama_frame)
        ollama_layout.setSpacing(12)

        self.ollama_url_input = QLineEdit(self.config.ollama.base_url)
        self.ollama_url_input.setPlaceholderText("http://localhost:11434")
        self.ollama_url_input.setFixedHeight(40)
        ollama_layout.addWidget(QLabel("服务地址:"))
        ollama_layout.addWidget(self.ollama_url_input)

        self.ollama_model_input = QLineEdit()
        self.ollama_model_input.setPlaceholderText("qwen2.5:7b")
        self.ollama_model_input.setFixedHeight(40)
        ollama_layout.addWidget(QLabel("默认模型:"))
        ollama_layout.addWidget(self.ollama_model_input)

        lay.addRow(ollama_frame)

        # 模型路径
        path_frame = QGroupBox("模型路径")
        path_frame.setStyleSheet("color: #334155;")
        path_layout = QVBoxLayout(path_frame)
        path_layout.setSpacing(12)

        self.models_dir_input = QLineEdit()
        self.models_dir_input.setPlaceholderText("/path/to/models")
        self.models_dir_input.setFixedHeight(40)
        path_layout.addWidget(QLabel("模型存储目录:"))
        path_layout.addWidget(self.models_dir_input)

        # 模型市场
        market_frame = QGroupBox("模型市场")
        market_frame.setStyleSheet("color: #334155;")
        market_layout = QVBoxLayout(market_frame)
        market_layout.setSpacing(12)

        self.hf_token_input = QLineEdit()
        self.hf_token_input.setPlaceholderText("hf_xxxx")
        self.hf_token_input.setFixedHeight(40)
        market_layout.addWidget(QLabel("HuggingFace Token (可选):"))
        market_layout.addWidget(self.hf_token_input)

        lay.addRow(path_frame)
        lay.addRow(market_frame)

        return page

    def _create_agent_page(self) -> QWidget:
        """第 3 步：Agent 配置页"""
        page = QWidget()
        lay = QFormLayout(page)
        lay.setSpacing(16)

        agent_frame = QGroupBox("Agent 基础设置")
        agent_frame.setStyleSheet("color: #334155;")
        agent_layout = QVBoxLayout(agent_frame)
        agent_layout.setSpacing(12)

        self.agent_max_iter_input = QSpinBox()
        self.agent_max_iter_input.setRange(10, 500)
        self.agent_max_iter_input.setValue(90)
        agent_layout.addWidget(QLabel("最大迭代次数:"))
        agent_layout.addWidget(self.agent_max_iter_input)

        self.agent_temperature_input = QSpinBox()
        self.agent_temperature_input.setRange(0, 200)
        self.agent_temperature_input.setValue(70)
        self.agent_temperature_input.setSuffix(" / 100")
        agent_layout.addWidget(QLabel("Temperature:") + QLabel(" (0-1.00)"))
        agent_layout.addWidget(self.agent_temperature_input)

        self.streaming_cb = QCheckBox("启用流式输出")
        self.streaming_cb.setChecked(True)
        agent_layout.addWidget(self.streaming_cb)

        lay.addRow(agent_frame)

        # P2P配置
        p2p_frame = QGroupBox("存储配置")
        p2p_frame.setStyleSheet("color: #334155;")
        p2p_layout = QVBoxLayout(p2p_frame)
        p2p_layout.setSpacing(12)

        self.enable_p2p_cb = QCheckBox("启用 P2P 模型发现")
        self.enable_p2p_cb.setChecked(True)
        p2p_layout.addWidget(self.enable_p2p_cb)

        lay.addRow(p2p_frame)
        return page

    def _create_review_page(self) -> QWidget:
        """第 4 步：配置预览与确认"""
        page = QWidget()
        main_lay = QVBoxLayout(page)

        summary = QTextBrowser()
        summary.setHtml(f"""
            <h2 style='color:#1f2937;'>⚙️ 配置预览</h2>
            <table style='width:100%; border-collapse:collapse;'>
                <tr style='border-bottom:1px solid #e5e7eb;'>
                    <td style='padding:10px; font-weight:bold; color:#64748B;'>Ollama 地址</td>
                    <td style='padding:10px;'>{self.ollama_url_input.text()}</td>
                </tr>
                <tr style='border-bottom:1px solid #e5e7eb;'>
                    <td style='padding:10px; font-weight:bold; color:#64748B;'>默认模型</td>
                    <td style='padding:10px;'>{self.ollama_model_input.text() or "未设置"}</td>
                </tr>
                <tr style='border-bottom:1px solid #e5e7eb;'>
                    <td style='padding:10px; font-weight:bold; color:#64748B;'>模型目录</td>
                    <td style='padding:10px;'>{self.models_dir_input.text() or "默认"}</td>
                </tr>
                <tr style='border-bottom:1px solid #e5e7eb;'>
                    <td style='padding:10px; font-weight:bold; color:#64748B;'>Agent 迭代次数</td>
                    <td style='padding:10px;'>{self.agent_max_iter_input.value()}</td>
                </tr>
                <tr style='border-bottom:1px solid #e5e7eb;'>
                    <td style='padding:10px; font-weight:bold; color:#64748B;'>流式输出</td>
                    <td style='padding:10px;'>{"✅ 启用" if self.streaming_cb.isChecked() else "❌ 禁用"}</td>
                </tr>
                <tr style='border-bottom:1px solid #e5e7eb;'>
                    <td style='padding:10px; font-weight:bold; color:#64748B;'>P2P 存储</td>
                    <td style='padding:10px;'>{"✅ 启用" if self.enable_p2p_cb.isChecked() else "❌ 禁用"}</td>
                </tr>
            </table>
        """)
        summary.setMaximumHeight(300)
        summary.setEnabled(False)
        main_lay.addWidget(summary)

        return page

    def _create_complete_page(self) -> QWidget:
        """第 5 步：完成页"""
        page = QWidget()
        page.setStyleSheet("background: linear-gradient(135deg, #10b981 0%, #059669 100%);")
        lay = QVBoxLayout(page)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(20)

        check_icon = QLabel("✅")
        check_icon.setFixedSize(100, 100)
        check_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        check_icon.setStyleSheet("font-size: 80px;")
        lay.addWidget(check_icon)

        title = QLabel("🎉 配置完成!")
        title.setStyleSheet("""
            font-size: 36px;
            font-weight: bold;
            color: white;
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(title)

        desc = QLabel("点击「启动」开始使用 LivingTree AI Agent")
        desc.setStyleSheet("font-size: 16px; color: rgba(255,255,255,0.8);")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(desc)

        return page

    def _go_next(self):
        """前进到下一步"""
        current_idx = self.stack.currentIndex()

        # 保存页面数据
        if current_idx == WizardStep.L0_L1_CONFIG.value:
            self._save_model_data()
        elif current_idx == WizardStep.MODEL_CONFIG.value:
            self._save_agent_data()

        # 切换到预览页
        if current_idx == WizardStep.AGENT_CONFIG.value:
            self.stack.setCurrentIndex(WizardStep.REVIEW.value)
            return

        # 最后一步：保存并关闭
        if current_idx == WizardStep.REVIEW.value:
            self._save_config()
            self._show_success()
            return

        # 普通前进
        next_idx = min(current_idx + 1, self.stack.count() - 1)
        self.stack.setCurrentIndex(next_idx)
        self._update_step_indicator(next_idx)

        # 更新按钮状态
        self.btn_prev.setDisabled(next_idx == 0)
        if next_idx == self.stack.count() - 1:
            self.btn_next.setText("启动 →")
            self.btn_next.setStyleSheet("""
                QPushButton {
                    background: #10b981;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: #059669;
                }
            """)
        else:
            self.btn_next.setText("下一步 →")
            self.btn_next.setStyleSheet("""
                QPushButton {
                    background: #3b82f6;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: #2563eb;
                }
            """)

    def _go_prev(self):
        """后退到上一步"""
        current_idx = self.stack.currentIndex()
        if current_idx > 0:
            self.stack.setCurrentIndex(current_idx - 1)
            self._update_step_indicator(current_idx - 1)
            self.btn_prev.setDisabled(self.stack.currentIndex() == 0)

    def _save_model_data(self):
        """保存模型页数据"""
        pass

    def _save_agent_data(self):
        """保存 Agent 页数据"""
        pass

    def _save_config(self):
        """保存最终配置"""
        # 构建 OllamaConfig
        try:
            self.config.ollama = OllamaConfig(
                base_url=self.ollama_url_input.text() or "http://localhost:11434",
                default_model=self.ollama_model_input.text() or "",
            )
        except:
            self.config.ollama = OllamaConfig(
                base_url="http://localhost:11434",
            )

        # AgentConfig
        self.config.agent = AgentConfig(
            max_iterations=self.agent_max_iter_input.value(),
            temperature=self.agent_temperature_input.value() / 100.0,
            streaming=self.streaming_cb.isChecked(),
        )

        # P2P 配置
        if hasattr(self.config, 'model_store'):
            self.config.model_store.enable_p2p = self.enable_p2p_cb.isChecked()

        # 保存配置
        if self.ollama_model_input.text().strip():
            try:
                save_config(self.config)
            except Exception as e:
                QMessageBox.warning(self, "保存失败", f"配置保存失败: {e}")
                return

        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        save_config(self.config)

        self.wizard_completed.emit(self.config)
        self.accept()

    def _show_success(self):
        """显示成功对话框"""
        QMessageBox.information(
            self,
            "配置已保存",
            "配置已成功保存！即将启动 LivingTree AI Agent...",
            QMessageBox.StandardButton.Ok,
            QMessageBox.StandardButton.Ok,
        )
        self.accept()


def run_initialization_wizard(parent=None) -> bool:
    """
    运行初始化向导
    Returns:
        bool: 用户是否完成配置
    """
    wizard = InitializationWizard(parent or QApplication.activeWindow())
    result = wizard.exec()
    return result == QDialog.DialogCode.Accepted


if __name__ == '__main__':
    import sys
    app = QApplication(sys.argv)
    wizard = InitializationWizard()
    wizard.wizard_completed.connect(lambda cfg: print(f"✅ 配置已保存: {cfg.ollama.base_url}"))
    wizard.show()
    sys.exit(app.exec())
