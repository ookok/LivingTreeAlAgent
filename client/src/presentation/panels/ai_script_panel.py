"""
AI Script Panel - 智能脚本生成UI面板
====================================

提供自然语言脚本生成、执行、管理的完整UI

Author: Hermes Desktop Team
"""

import asyncio
from datetime import datetime
from typing import List, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QLineEdit, QComboBox, QListWidget, QListWidgetItem,
    QTabWidget, QFrame, QGroupBox, QProgressBar, QSplitter,
    QStatusBar, QMenuBar, QMenu, QToolBar, QDialog, QDialogButtonBox,
    QFormLayout, QSpinBox, QCheckBox, QScrollArea, QSizePolicy,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QFont, QAction, QIcon, QPalette, QColor, QTextCursor


class AIScriptPanel(QWidget):
    """
    AI脚本生成面板

    功能：
    1. 自然语言输入 → AI脚本生成
    2. 脚本市场 → 浏览/安装/分享
    3. 沙箱执行 → 安全运行脚本
    4. 调试工具 → 变量查看/断点
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # 组件
        self.engine = None
        self.sandbox = None
        self.market = None

        # 状态
        self.current_script_id = None
        self.is_generating = False
        self.generated_code = ""

        self._init_ui()
        self._init_components()

    def _init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)

        # 顶部工具栏
        toolbar = self._create_toolbar()
        main_layout.addLayout(toolbar)

        # 主内容区
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：导航栏
        left_panel = self._create_left_panel()
        splitter.addWidget(left_panel)

        # 中间：代码编辑器
        center_panel = self._create_center_panel()
        splitter.addWidget(center_panel)

        # 右侧：输出/信息
        right_panel = self._create_right_panel()
        splitter.addWidget(right_panel)

        # 设置比例
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 2)

        main_layout.addWidget(splitter)

        # 底部状态栏
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("就绪")
        main_layout.addWidget(self.status_bar)

        self.setLayout(main_layout)

    def _create_toolbar(self) -> QHBoxLayout:
        """创建工具栏"""
        toolbar = QHBoxLayout()

        # 标题
        title = QLabel("🤖 AI脚本生成器")
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        toolbar.addWidget(title)

        toolbar.addStretch()

        # 快捷按钮
        self.new_script_btn = QPushButton("📝 新建")
        self.new_script_btn.clicked.connect(self._new_script)
        toolbar.addWidget(self.new_script_btn)

        self.generate_btn = QPushButton("✨ 生成")
        self.generate_btn.setStyleSheet("background: #4CAF50; color: white;")
        self.generate_btn.clicked.connect(self._generate_script)
        toolbar.addWidget(self.generate_btn)

        self.execute_btn = QPushButton("▶️ 执行")
        self.execute_btn.setStyleSheet("background: #2196F3; color: white;")
        self.execute_btn.clicked.connect(self._execute_script)
        toolbar.addWidget(self.execute_btn)

        self.save_btn = QPushButton("💾 保存")
        self.save_btn.clicked.connect(self._save_script)
        toolbar.addWidget(self.save_btn)

        self.share_btn = QPushButton("📤 分享")
        self.share_btn.clicked.connect(self._share_script)
        toolbar.addWidget(self.share_btn)

        return toolbar

    def _create_left_panel(self) -> QWidget:
        """创建左侧面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)

        # 搜索框
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍 搜索脚本...")
        self.search_box.textChanged.connect(self._on_search)
        layout.addWidget(self.search_box)

        # 标签页
        self.left_tabs = QTabWidget()

        # 脚本列表
        self.script_list = QListWidget()
        self.script_list.itemClicked.connect(self._on_script_select)
        self.left_tabs.addTab(self.script_list, "📜 我的脚本")

        # 市场
        self.market_list = QListWidget()
        self.market_list.itemClicked.connect(self._on_market_select)
        self.left_tabs.addTab(self.market_list, "🏪 市场")

        layout.addWidget(self.left_tabs)

        # 分类筛选
        self.category_combo = QComboBox()
        self.category_combo.addItems(['全部', '网络', '工具', '分析', '自动化'])
        self.category_combo.currentTextChanged.connect(self._on_category_change)
        layout.addWidget(self.category_combo)

        return widget

    def _create_center_panel(self) -> QWidget:
        """创建中心面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)

        # 自然语言输入
        input_group = QGroupBox("💬 描述你的需求")
        input_layout = QVBoxLayout()

        self.input_box = QTextEdit()
        self.input_box.setPlaceholderText(
            "用自然语言描述你想要的功能...\n\n"
            "例如：\n"
            "• '创建一个显示数据分析的面板'\n"
            "• '自动将GitHub链接转国内镜像'\n"
            "• '帮我批量重命名文件夹中的图片'\n"
            "• '写一个API调用并可视化结果'"
        )
        self.input_box.setMaximumHeight(120)
        input_layout.addWidget(self.input_box)

        # 意图识别显示
        self.intent_label = QLabel("🎯 识别意图: 等待输入...")
        self.intent_label.setStyleSheet("color: gray;")
        input_layout.addWidget(self.intent_label)

        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

        # 代码编辑器
        editor_group = QGroupBox("📄 生成的代码")
        editor_layout = QVBoxLayout()

        # 编辑器工具栏
        editor_toolbar = QHBoxLayout()
        editor_toolbar.addWidget(QLabel("脚本ID:"))
        self.script_id_label = QLabel("-")
        self.script_id_label.setStyleSheet("color: #666;")
        editor_toolbar.addWidget(self.script_id_label)
        editor_toolbar.addStretch()

        self.safety_label = QLabel("🛡️ 安全: -")
        self.safety_label.setStyleSheet("color: green;")
        editor_toolbar.addWidget(self.safety_label)

        editor_layout.addLayout(editor_toolbar)

        # 代码区域
        self.code_editor = QTextEdit()
        self.code_editor.setPlaceholderText("# 生成的代码将显示在这里...")
        self.code_editor.setFont(QFont("Consolas", 10))
        self.code_editor.setStyleSheet("""
            QTextEdit {
                background: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
            }
        """)
        editor_layout.addWidget(self.code_editor)

        editor_group.setLayout(editor_layout)
        layout.addWidget(editor_group)

        return widget

    def _create_right_panel(self) -> QWidget:
        """创建右侧面板"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)

        # 输出区
        output_group = QGroupBox("📋 执行结果")
        output_layout = QVBoxLayout()

        self.output_box = QTextEdit()
        self.output_box.setReadOnly(True)
        self.output_box.setFont(QFont("Consolas", 9))
        self.output_box.setStyleSheet("""
            QTextEdit {
                background: #f5f5f5;
                border: 1px solid #ddd;
            }
        """)
        output_layout.addWidget(self.output_box)

        # 执行信息
        exec_info = QHBoxLayout()
        self.exec_time_label = QLabel("⏱️ 耗时: -")
        exec_info.addWidget(self.exec_time_label)
        exec_info.addStretch()
        self.memory_label = QLabel("💾 内存: -")
        exec_info.addWidget(self.memory_label)

        output_layout.addLayout(exec_info)

        output_group.setLayout(output_layout)
        layout.addWidget(output_group)

        # 安全警告
        warning_group = QGroupBox("⚠️ 安全警告")
        warning_layout = QVBoxLayout()

        self.warning_box = QTextEdit()
        self.warning_box.setReadOnly()
        self.warning_box.setMaximumHeight(80)
        self.warning_box.setStyleSheet("""
            QTextEdit {
                background: #fff3e0;
                border: 1px solid #ffcc80;
            }
        """)
        warning_layout.addWidget(self.warning_box)

        warning_group.setLayout(warning_layout)
        layout.addWidget(warning_group)

        # 建议
        suggestion_group = QGroupBox("💡 优化建议")
        suggestion_layout = QVBoxLayout()

        self.suggestion_box = QTextEdit()
        self.suggestion_box.setReadOnly()
        self.suggestion_box.setMaximumHeight(60)
        self.suggestion_box.setStyleSheet("""
            QTextEdit {
                background: #e3f2fd;
                border: 1px solid #90caf9;
            }
        """)
        suggestion_layout.addWidget(self.suggestion_box)

        suggestion_group.setLayout(suggestion_layout)
        layout.addWidget(suggestion_group)

        return widget

    def _init_components(self):
        """初始化组件"""
        try:
            from client.src.business.ai_script_generator import (
                get_ai_script_engine,
                get_script_sandbox,
                get_script_market
            )

            self.engine = get_ai_script_engine()
            self.sandbox = get_script_sandbox()
            self.market = get_script_market()

            # 加载脚本列表
            self._refresh_script_list()
            self._refresh_market_list()

            self.status_bar.showMessage("组件初始化完成")

        except Exception as e:
            self.status_bar.showMessage(f"初始化失败: {str(e)}")

    def _refresh_script_list(self):
        """刷新脚本列表"""
        self.script_list.clear()

        if not self.market:
            return

        scripts = self.market.list_scripts()

        for script in scripts:
            if script.get('is_builtin'):
                continue  # 内置脚本不显示在"我的脚本"

            item = QListWidgetItem(f"📜 {script['name']}")
            item.setData(Qt.ItemDataRole.UserRole, script)
            self.script_list.addItem(item)

    def _refresh_market_list(self):
        """刷新市场列表"""
        self.market_list.clear()

        if not self.market:
            return

        category = self.category_combo.currentText()
        if category == '全部':
            category = None

        scripts = self.market.list_scripts(category=category)

        for script in scripts:
            icon = '🔒' if script.get('safety_level') == 'safe' else '⚠️'
            item = QListWidgetItem(
                f"{icon} {script['name']} - ⭐{script.get('rating', 0)} - 📥{script.get('downloads', 0)}"
            )
            item.setData(Qt.ItemDataRole.UserRole, script)
            self.market_list.addItem(item)

    def _on_search(self, text: str):
        """搜索脚本"""
        # 简单的过滤
        for i in range(self.market_list.count()):
            item = self.market_list.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def _on_category_change(self, category: str):
        """分类筛选"""
        self._refresh_market_list()

    def _on_script_select(self, item: QListWidgetItem):
        """选择脚本"""
        script = item.data(Qt.ItemDataRole.UserRole)
        if not script:
            return

        self._load_script(script)

    def _on_market_select(self, item: QListWidgetItem):
        """选择市场脚本"""
        script = item.data(Qt.ItemDataRole.UserRole)
        if not script:
            return

        self._show_script_detail(script)

    def _load_script(self, script: dict):
        """加载脚本"""
        self.current_script_id = script.get('script_id')

        # 获取完整脚本
        full_script = self.market.get_script(self.current_script_id)
        if full_script:
            self.code_editor.setPlainText(full_script.get('code', ''))
            self.script_id_label.setText(self.current_script_id or '-')
            self.generated_code = full_script.get('code', '')

        self.status_bar.showMessage(f"已加载: {script.get('name')}")

    def _show_script_detail(self, script: dict):
        """显示脚本详情"""
        detail = f"""
📦 {script.get('name')}

作者: {script.get('author', 'Unknown')}
分类: {script.get('category', 'general')}
标签: {', '.join(script.get('tags', []))}
安全: {script.get('safety_level', 'unknown')}

⭐ 评分: {script.get('rating', 0)}
📥 下载: {script.get('downloads', 0)}

描述:
{script.get('description', '无')}
"""

        # 显示在输入框作为参考
        self.input_box.setPlainText(f"# 参考: {script.get('name')}\n# {script.get('description')}")

        QMessageBox.information(self, "脚本详情", detail)

    async     def _generate_script(self):
        """生成脚本"""
        if not self.engine:
            self.status_bar.showMessage("引擎未初始化")
            return

        description = self.input_box.toPlainText().strip()
        if not description:
            self.status_bar.showMessage("请输入需求描述")
            return

        if self.is_generating:
            return

        self.is_generating = True
        self.generate_btn.setEnabled(False)
        self.status_bar.showMessage("🤔 AI正在分析需求...")

        try:
            # 识别意图
            intent = self.engine.recognize_intent(description)
            self.intent_label.setText(f"🎯 识别意图: {intent.primary_intent} (置信度: {intent.confidence:.1%})")

            # 生成代码
            self.status_bar.showMessage("✨ 正在生成代码...")
            result = await self.engine.generate(description)

            if result.success:
                # 显示代码
                self.code_editor.setPlainText(result.script.code)
                self.generated_code = result.script.code
                self.current_script_id = result.script.script_id
                self.script_id_label.setText(self.current_script_id)

                # 安全信息
                safety_level = result.script.metadata.get('safety_level', 'unknown')
                self.safety_label.setText(f"🛡️ 安全: {safety_level}")

                # 警告
                self.warning_box.setPlainText('\n'.join(result.warnings) if result.warnings else "✅ 未检测到危险操作")

                # 建议
                self.suggestion_box.setPlainText('\n'.join(result.suggestions) if result.suggestions else "无")

                self.status_bar.showMessage(f"✅ 生成完成: {self.current_script_id}")
            else:
                self.status_bar.showMessage(f"❌ 生成失败: {result.error_message}")
                self.warning_box.setPlainText(f"错误: {result.error_message}")

        except Exception as e:
            self.status_bar.showMessage(f"❌ 生成异常: {str(e)}")

        finally:
            self.is_generating = False
            self.generate_btn.setEnabled(True)

    def _execute_script(self):
        """执行脚本"""
        if not self.sandbox:
            self.status_bar.showMessage("沙箱未初始化")
            return

        code = self.code_editor.toPlainText().strip()
        if not code:
            self.status_bar.showMessage("没有可执行的代码")
            return

        self.execute_btn.setEnabled(False)
        self.status_bar.showMessage("▶️ 执行中...")
        self.output_box.clear()

        try:
            result = self.sandbox.execute_script(
                script_id=self.current_script_id or "temp",
                code=code,
                timeout=30
            )

            if result.success:
                self.output_box.setPlainText(result.output or "(无输出)")
                self.exec_time_label.setText(f"⏱️ 耗时: {result.execution_time:.2f}s")
                self.memory_label.setText(f"💾 内存: {result.memory_peak_mb:.1f}MB")

                if result.warnings:
                    self.warning_box.append("\n" + "\n".join(result.warnings))

                self.status_bar.showMessage("✅ 执行完成")
            else:
                self.output_box.setPlainText(f"❌ 执行错误:\n{result.error}")
                self.status_bar.showMessage("❌ 执行失败")

        except Exception as e:
            self.output_box.setPlainText(f"异常: {str(e)}")
            self.status_bar.showMessage("❌ 执行异常")

        finally:
            self.execute_btn.setEnabled(True)

    def _new_script(self):
        """新建脚本"""
        self.input_box.clear()
        self.code_editor.clear()
        self.output_box.clear()
        self.warning_box.clear()
        self.suggestion_box.clear()
        self.intent_label.setText("🎯 识别意图: 等待输入...")
        self.script_id_label.setText("-")
        self.safety_label.setText("🛡️ 安全: -")
        self.current_script_id = None
        self.generated_code = ""
        self.status_bar.showMessage("已新建脚本")

    def _save_script(self):
        """保存脚本"""
        if not self.market:
            return

        code = self.code_editor.toPlainText().strip()
        if not code:
            self.status_bar.showMessage("没有可保存的代码")
            return

        # 简单的保存对话框
        name = f"脚本_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        description = self.input_box.toPlainText()[:100] or "AI生成的脚本"

        script_id = self.market.publish_script(
            name=name,
            description=description,
            code=code
        )

        if script_id:
            self.current_script_id = script_id
            self._refresh_script_list()
            self.status_bar.showMessage(f"✅ 已保存: {script_id}")
        else:
            self.status_bar.showMessage("❌ 保存失败")

    def _share_script(self):
        """分享脚本"""
        if not self.market:
            return

        if not self.current_script_id:
            self.status_bar.showMessage("请先生成或加载脚本")
            return

        # 导出到临时文件
        export_path = f"./temp/{self.current_script_id}.zip"
        if self.market.export_script(self.current_script_id, export_path):
            QMessageBox.information(
                self, "分享成功",
                f"脚本已导出到:\n{export_path}\n\n可以发送给其他用户导入使用。"
            )
        else:
            QMessageBox.warning(self, "分享失败", "无法导出脚本")


# 便捷函数
def create_ai_script_panel() -> AIScriptPanel:
    """创建AI脚本面板"""
    return AIScriptPanel()
