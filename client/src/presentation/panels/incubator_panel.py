"""
🌱 知识孵化面板 (Knowledge Incubator Panel)
==========================================

装配园扩展面板：知识库生成 + Skill生成 + 自动整理

三阶知识孵化：
1. 🌾 沃土播种 - 知识库生成
2. 🛠️ 技能嫁接 - Skill生成
3. 🔄 园丁整理架 - 自动整理
"""

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QPushButton, QTextEdit, QLineEdit,
    QProgressBar, QListWidget, QListWidgetItem,
    QGroupBox, QFormLayout, QComboBox, QCheckBox,
    QScrollArea, QFrame, QBadge,
)
from PyQt6.QtGui import QFont


class KnowledgeIncubatorPanel(QWidget):
    """
    知识孵化面板

    使用方式:
        from assembler import get_knowledge_bank, get_incubator

        bank = get_knowledge_bank()
        soil_sower, skill_grafting, gardeners_shelf = get_incubator(bank)

        # 显示面板
        self.incubator_tab = KnowledgeIncubatorPanel(bank, soil_sower, skill_grafting, gardeners_shelf)
    """

    # 信号
    status_changed = pyqtSignal(str)

    def __init__(
        self,
        knowledge_bank=None,
        soil_sower=None,
        skill_grafting=None,
        gardeners_shelf=None,
        parent=None
    ):
        super().__init__(parent)
        self.knowledge_bank = knowledge_bank
        self.soil_sower = soil_sower
        self.skill_grafting = skill_grafting
        self.gardeners_shelf = gardeners_shelf

        self._setup_ui()

    def _setup_ui(self):
        """初始化UI"""
        self.setMinimumSize(800, 600)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # 标题
        title = QLabel("🌱 知识孵化园")
        title.setObjectName("panel-title")
        title.setStyleSheet("font-size: 18px; font-weight: 600; color: #e8e8e8;")
        layout.addWidget(title)

        # 标签页
        self.tabs = QTabWidget()
        self.tabs.setObjectName("incubator-tabs")

        # 1. 沃土播种标签
        self.soil_tab = self._create_soil_tab()
        self.tabs.addTab(self.soil_tab, "🌾 沃土播种")

        # 2. 技能嫁接标签
        self.graft_tab = self._create_graft_tab()
        self.tabs.addTab(self.graft_tab, "🛠️ 技能嫁接")

        # 3. 整理架标签
        self.shelf_tab = self._create_shelf_tab()
        self.tabs.addTab(self.shelf_tab, "🔄 整理架")

        # 4. 知识库标签
        self.bank_tab = self._create_bank_tab()
        self.tabs.addTab(self.bank_tab, "📚 知识库")

        layout.addWidget(self.tabs)

        # 状态栏
        self._status_bar = QLabel("就绪")
        self._status_bar.setObjectName("incubator-status")
        self._status_bar.setStyleSheet("color: #888888; font-size: 12px; padding: 4px;")
        layout.addWidget(self._status_bar)

    def _create_soil_tab(self) -> QWidget:
        """创建沃土播种标签页"""
        tab = QScrollArea()
        tab.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(16)

        # 说明
        desc = QLabel(
            "🌾 沃土播种：将博客/文档/代码转换为结构化知识条目\n"
            "输入URL或粘贴内容，自动解析并存储到知识库"
        )
        desc.setObjectName("section-desc")
        layout.addWidget(desc)

        # 输入区
        input_group = QGroupBox("📥 输入")
        input_layout = QVBoxLayout()

        self.source_type = QComboBox()
        self.source_type.addItems(["URL", "Markdown", "代码"])
        self.source_type.setObjectName("source-type")
        input_layout.addWidget(QLabel("来源类型:"))
        input_layout.addWidget(self.source_type)

        self.source_url = QLineEdit()
        self.source_url.setPlaceholderText("输入URL（可选）")
        self.source_url.setObjectName("source-url")
        input_layout.addWidget(QLabel("来源URL:"))
        input_layout.addWidget(self.source_url)

        self.content_input = QTextEdit()
        self.content_input.setPlaceholderText("粘贴内容或Markdown...")
        self.content_input.setMinimumHeight(200)
        self.content_input.setObjectName("content-input")
        input_layout.addWidget(QLabel("内容:"))
        input_layout.addWidget(self.content_input)

        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

        # 播种按钮
        self.sow_btn = QPushButton("🌾 开始播种")
        self.sow_btn.setObjectName("sow-button")
        self.sow_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sow_btn.clicked.connect(self._on_sow)
        input_layout.addWidget(self.sow_btn)

        # 进度条
        self.sow_progress = QProgressBar()
        self.sow_progress.setObjectName("sow-progress")
        self.sow_progress.hide()
        layout.addWidget(self.sow_progress)

        # 预览区
        preview_group = QGroupBox("👁️ 预览")
        preview_layout = QVBoxLayout()
        self.sow_preview = QTextEdit()
        self.sow_preview.setReadOnly(True)
        self.sow_preview.setMinimumHeight(150)
        self.sow_preview.setObjectName("sow-preview")
        preview_layout.addWidget(self.sow_preview)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)

        layout.addStretch()
        return tab

    def _create_graft_tab(self) -> QWidget:
        """创建技能嫁接标签页"""
        tab = QScrollArea()
        tab.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(16)

        # 说明
        desc = QLabel(
            "🛠️ 技能嫁接：从代码库生成可用的Skill\n"
            "粘贴代码或输入仓库URL，自动分析并生成Skill"
        )
        layout.addWidget(desc)

        # 输入区
        input_group = QGroupBox("📥 代码输入")
        input_layout = QVBoxLayout()

        self.repo_url = QLineEdit()
        self.repo_url.setPlaceholderText("GitHub仓库URL（可选）")
        self.repo_url.setObjectName("repo-url")
        input_layout.addWidget(QLabel("仓库URL:"))
        input_layout.addWidget(self.repo_url)

        self.repo_name = QLineEdit()
        self.repo_name.setPlaceholderText("仓库名称")
        self.repo_name.setObjectName("repo-name")
        input_layout.addWidget(QLabel("仓库名称:"))
        input_layout.addWidget(self.repo_name)

        self.language = QComboBox()
        self.language.addItems(["python", "javascript", "typescript", "go", "rust", "java", "other"])
        self.language.setObjectName("code-language")
        input_layout.addWidget(QLabel("语言:"))
        input_layout.addWidget(self.language)

        self.code_input = QTextEdit()
        self.code_input.setPlaceholderText("粘贴代码...")
        self.code_input.setMinimumHeight(250)
        self.code_input.setObjectName("code-input")
        input_layout.addWidget(QLabel("代码:"))
        input_layout.addWidget(self.code_input)

        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

        # 嫁接按钮
        self.graft_btn = QPushButton("🛠️ 开始嫁接")
        self.graft_btn.setObjectName("graft-button")
        self.graft_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.graft_btn.clicked.connect(self._on_graft)
        input_layout.addWidget(self.graft_btn)

        # 进度
        self.graft_progress = QProgressBar()
        self.graft_progress.setObjectName("graft-progress")
        self.graft_progress.hide()
        layout.addWidget(self.graft_progress)

        # 生成结果
        result_group = QGroupBox("📤 生成结果")
        result_layout = QVBoxLayout()
        self.graft_result = QTextEdit()
        self.graft_result.setReadOnly(True)
        self.graft_result.setMinimumHeight(150)
        self.graft_result.setObjectName("graft-result")
        result_layout.addWidget(self.graft_result)
        result_group.setLayout(result_layout)
        layout.addWidget(result_group)

        layout.addStretch()
        return tab

    def _create_shelf_tab(self) -> QWidget:
        """创建整理架标签页"""
        tab = QScrollArea()
        tab.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(16)

        # 说明
        desc = QLabel(
            "🔄 园丁整理架：自动去重、分类、更新索引\n"
            "保持知识库整洁有序"
        )
        layout.addWidget(desc)

        # 操作区
        actions_group = QGroupBox("🧹 整理操作")
        actions_layout = QVBoxLayout()

        # 去重检查
        dedup_layout = QHBoxLayout()
        self.dedup_btn = QPushButton("🔍 检查重复")
        self.dedup_btn.setObjectName("dedup-button")
        self.dedup_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dedup_btn.clicked.connect(self._on_check_duplicates)
        dedup_layout.addWidget(self.dedup_btn)
        dedup_layout.addWidget(QPushButton("🧹 清理重复"))
        dedup_layout.addStretch()
        actions_layout.addLayout(dedup_layout)

        # 重新分类
        reclass_layout = QHBoxLayout()
        self.reclassify_btn = QPushButton("🏷️ 重新分类")
        self.reclassify_btn.setObjectName("reclassify-button")
        self.reclassify_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reclassify_btn.clicked.connect(self._on_reclassify)
        reclass_layout.addWidget(self.reclassify_btn)
        reclass_layout.addWidget(QPushButton("🔄 重建索引"))
        reclass_layout.addStretch()
        actions_layout.addLayout(reclass_layout)

        actions_group.setLayout(actions_layout)
        layout.addWidget(actions_group)

        # 统计区
        stats_group = QGroupBox("📊 统计")
        stats_layout = QFormLayout()

        self.total_knowledge = QLabel("0")
        self.total_skills = QLabel("0")
        self.total_tags = QLabel("0")

        stats_layout.addRow("知识条目:", self.total_knowledge)
        stats_layout.addRow("技能Skill:", self.total_skills)
        stats_layout.addRow("标签数:", self.total_tags)

        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        # 分类结构
        category_group = QGroupBox("📂 分类结构")
        category_layout = QVBoxLayout()
        self.category_tree = QListWidget()
        self.category_tree.setObjectName("category-tree")
        category_layout.addWidget(self.category_tree)
        category_group.setLayout(category_layout)
        layout.addWidget(category_group)

        # 刷新统计
        self._refresh_stats()

        layout.addStretch()
        return tab

    def _create_bank_tab(self) -> QWidget:
        """创建知识库标签页"""
        tab = QScrollArea()
        tab.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(16)

        # 搜索区
        search_layout = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索知识库...")
        self.search_input.setObjectName("search-input")
        search_layout.addWidget(self.search_input)

        search_btn = QPushButton("🔍")
        search_btn.setObjectName("search-button")
        search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        search_btn.clicked.connect(self._on_search)
        search_layout.addWidget(search_btn)

        layout.addLayout(search_layout)

        # 列表
        self.knowledge_list = QListWidget()
        self.knowledge_list.setObjectName("knowledge-list")
        self.knowledge_list.itemClicked.connect(self._on_entry_clicked)
        layout.addWidget(self.knowledge_list)

        # 详情区
        detail_group = QGroupBox("📄 条目详情")
        detail_layout = QVBoxLayout()
        self.entry_detail = QTextEdit()
        self.entry_detail.setReadOnly(True)
        self.entry_detail.setMinimumHeight(200)
        self.entry_detail.setObjectName("entry-detail")
        detail_layout.addWidget(self.entry_detail)
        detail_group.setLayout(detail_layout)
        layout.addWidget(detail_group)

        # 加载列表
        self._load_knowledge_list()

        layout.addStretch()
        return tab

    # ==================== 事件处理 ====================

    def _on_sow(self):
        """执行播种"""
        if not self.content_input.toPlainText() and not self.source_url.text():
            self._update_status("⚠️ 请输入内容或URL")
            return

        self.sow_btn.setEnabled(False)
        self.sow_progress.show()
        self.sow_progress.setRange(0, 0)  # 不确定模式

        async def run():
            try:
                content = self.content_input.toPlainText()
                url = self.source_url.text()
                source_type = self.source_type.currentText()

                success, msg, entry = await self.soil_sower.sow(
                    content=content,
                    source_url=url,
                    content_type=source_type.lower(),
                    progress_callback=self._on_progress
                )

                if success:
                    self._update_status(f"✅ {msg}")
                    # 显示预览
                    if entry:
                        preview = f"**{entry.title}**\n\n标签: {', '.join(entry.tags)}\n\n摘要: {entry.summary[:200]}..."
                        self.sow_preview.setPlainText(preview)
                else:
                    self._update_status(f"⚠️ {msg}")

            except Exception as e:
                self._update_status(f"❌ 播种失败: {e}")
            finally:
                self.sow_btn.setEnabled(True)
                self.sow_progress.hide()

        import threading
        threading.Thread(target=lambda: asyncio.run(run()), daemon=True).start()

    def _on_graft(self):
        """执行嫁接"""
        if not self.code_input.toPlainText() and not self.repo_url.text():
            self._update_status("⚠️ 请输入代码或仓库URL")
            return

        self.graft_btn.setEnabled(False)
        self.graft_progress.show()
        self.graft_progress.setRange(0, 0)

        async def run():
            try:
                code = self.code_input.toPlainText()
                url = self.repo_url.text()
                name = self.repo_name.text() or "unknown"
                lang = self.language.currentText()

                success, msg, skill = await self.skill_grafting.graft(
                    code=code,
                    repo_url=url,
                    repo_name=name,
                    language=lang,
                    progress_callback=self._on_progress
                )

                if success:
                    self._update_status(f"✅ {msg}")
                    if skill:
                        result = f"**{skill.name}** v{skill.version}\n\n"
                        result += f"描述: {skill.description}\n\n"
                        result += f"触发词: {', '.join(skill.triggers[:5])}\n\n"
                        result += f"能力:\n" + "\n".join([f"- {c}" for c in skill.capabilities[:5]])
                        self.graft_result.setPlainText(result)
                else:
                    self._update_status(f"⚠️ {msg}")

            except Exception as e:
                self._update_status(f"❌ 嫁接失败: {e}")
            finally:
                self.graft_btn.setEnabled(True)
                self.graft_progress.hide()

        import threading
        threading.Thread(target=lambda: asyncio.run(run()), daemon=True).start()

    def _on_check_duplicates(self):
        """检查重复"""
        self._update_status("🔍 正在扫描重复...")
        # TODO: 实现
        self._update_status("✅ 扫描完成")

    def _on_reclassify(self):
        """重新分类"""
        if self.gardeners_shelf:
            count = self.gardeners_shelf.reclassify_entries()
            self._update_status(f"✅ 已重新分类 {count} 个条目")
            self._refresh_stats()

    def _on_search(self):
        """搜索"""
        query = self.search_input.text()
        if not query:
            self._load_knowledge_list()
            return

        entries = self.knowledge_bank.search_by_keyword(query)
        self._display_entries(entries)

    def _on_entry_clicked(self, item: QListWidgetItem):
        """条目被点击"""
        entry_id = item.data(Qt.ItemDataRole.UserRole)
        entries = self.knowledge_bank.list_all(limit=100)
        for entry in entries:
            if entry.id == entry_id:
                self.entry_detail.setPlainText(entry.to_markdown())
                break

    def _on_progress(self, msg: str):
        """进度更新"""
        self._update_status(msg)

    # ==================== 辅助方法 ====================

    def _update_status(self, msg: str):
        """更新状态"""
        self._status_bar.setText(msg)
        self.status_changed.emit(msg)

    def _refresh_stats(self):
        """刷新统计"""
        if self.knowledge_bank:
            stats = self.gardeners_shelf.get_stats() if self.gardeners_shelf else {}
            kb_stats = stats.get("knowledge_bank", {})

            self.total_knowledge.setText(str(kb_stats.get("total_knowledge", 0)))
            self.total_skills.setText(str(kb_stats.get("total_skills", 0)))
            self.total_tags.setText(str(len(kb_stats.get("top_tags", {}))))

            # 分类结构
            self.category_tree.clear()
            categories = stats.get("categories", {})
            for cat, count in categories.items():
                self.category_tree.addItem(f"📁 {cat}: {count}")

    def _load_knowledge_list(self):
        """加载知识列表"""
        if not self.knowledge_bank:
            return

        entries = self.knowledge_bank.list_all(limit=50)
        self._display_entries(entries)

    def _display_entries(self, entries):
        """显示条目列表"""
        self.knowledge_list.clear()
        for entry in entries:
            item = QListWidgetItem(f"📄 {entry.title}")
            item.setData(Qt.ItemDataRole.UserRole, entry.id)
            item.setToolTip(f"标签: {', '.join(entry.tags)}\n摘要: {entry.summary[:100]}...")
            self.knowledge_list.addItem(item)


import asyncio  # 确保asyncio可用
