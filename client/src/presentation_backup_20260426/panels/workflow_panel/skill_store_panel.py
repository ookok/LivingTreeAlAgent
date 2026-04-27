"""
技能商店 UI 界面

提供技能的浏览、下载、管理、制作和上传功能
支持 Hermes Agent 技能系统
"""

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTextEdit, QLineEdit, QListWidget,
    QListWidgetItem, QGroupBox, QFrame, QSplitter,
    QComboBox, QCheckBox, QSpinBox, QTabWidget,
    QProgressBar, QMessageBox, QSlider, QTextBrowser,
    QDialog, QDialogButtonBox, QFormLayout, QScrollArea
)
from PyQt6.QtGui import QFont, QColor, QPalette, QIcon
from typing import Dict, Optional, List
import asyncio
import time

from core.living_tree_ai.skills.skill_manager import (
    SkillManager, SkillRegistry, SkillExecutor,
    SkillPlatform, SkillStatus, get_skill_manager, get_skill_registry, get_skill_executor
)


class SkillItemWidget(QWidget):
    """技能项组件"""

    def __init__(self, skill_data: Dict, is_local: bool = True, parent=None):
        super().__init__(parent)
        self.skill_data = skill_data
        self.is_local = is_local

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        # 标题
        title_layout = QHBoxLayout()
        name_label = QLabel(skill_data.get("name", "Unknown"))
        name_label.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        version_label = QLabel(f"v{skill_data.get('version', '1.0.0')}")
        version_label.setFont(QFont("Microsoft YaHei", 10))
        version_label.setStyleSheet("color: #666;")
        title_layout.addWidget(name_label)
        title_layout.addStretch()
        title_layout.addWidget(version_label)
        layout.addLayout(title_layout)

        # 描述
        description = QTextBrowser()
        description.setPlainText(skill_data.get("description", ""))
        description.setMaximumHeight(60)
        description.setStyleSheet("border: none;")
        layout.addWidget(description)

        # 标签
        tags = skill_data.get("tags", [])
        if tags:
            tags_layout = QHBoxLayout()
            for tag in tags[:3]:  # 最多显示3个标签
                tag_label = QLabel(f"#{tag}")
                tag_label.setStyleSheet("""
                    background-color: #e3f2fd;
                    color: #1976d2;
                    padding: 2px 8px;
                    border-radius: 12px;
                    font-size: 10px;
                """)
                tags_layout.addWidget(tag_label)
            tags_layout.addStretch()
            layout.addLayout(tags_layout)

        # 作者和平台
        meta_layout = QHBoxLayout()
        author_label = QLabel(f"作者: {skill_data.get('author', 'Unknown')}")
        author_label.setFont(QFont("Microsoft YaHei", 10))
        platform_label = QLabel(f"平台: {skill_data.get('platform', 'custom')}")
        platform_label.setFont(QFont("Microsoft YaHei", 10))
        meta_layout.addWidget(author_label)
        meta_layout.addStretch()
        meta_layout.addWidget(platform_label)
        layout.addLayout(meta_layout)

        # 操作按钮
        if is_local:
            self._add_local_buttons(layout)
        else:
            self._add_remote_buttons(layout)

        self.setStyleSheet("""
            QWidget {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                background-color: white;
            }
            QWidget:hover {
                border-color: #2196f3;
                background-color: #f8f9fa;
            }
        """)

    def _add_local_buttons(self, layout):
        """添加本地技能按钮"""
        button_layout = QHBoxLayout()

        execute_btn = QPushButton("执行")
        execute_btn.setFixedSize(80, 30)
        execute_btn.clicked.connect(self._on_execute)
        button_layout.addWidget(execute_btn)

        edit_btn = QPushButton("编辑")
        edit_btn.setFixedSize(80, 30)
        edit_btn.clicked.connect(self._on_edit)
        button_layout.addWidget(edit_btn)

        upload_btn = QPushButton("上传")
        upload_btn.setFixedSize(80, 30)
        upload_btn.clicked.connect(self._on_upload)
        button_layout.addWidget(upload_btn)

        delete_btn = QPushButton("删除")
        delete_btn.setFixedSize(80, 30)
        delete_btn.setStyleSheet("color: #f44336;")
        delete_btn.clicked.connect(self._on_delete)
        button_layout.addWidget(delete_btn)

        layout.addLayout(button_layout)

    def _add_remote_buttons(self, layout):
        """添加远程技能按钮"""
        button_layout = QHBoxLayout()

        download_btn = QPushButton("下载")
        download_btn.setFixedSize(100, 30)
        download_btn.setStyleSheet("background-color: #4caf50; color: white;")
        download_btn.clicked.connect(self._on_download)
        button_layout.addWidget(download_btn)

        details_btn = QPushButton("详情")
        details_btn.setFixedSize(80, 30)
        details_btn.clicked.connect(self._on_details)
        button_layout.addWidget(details_btn)

        layout.addLayout(button_layout)

    def _on_execute(self):
        """执行技能"""
        executor = get_skill_executor()
        result = executor.execute_skill(self.skill_data.get("instance_id"), {"test": "data"})
        QMessageBox.information(self, "执行结果", str(result))

    def _on_edit(self):
        """编辑技能"""
        QMessageBox.information(self, "编辑技能", f"编辑技能: {self.skill_data.get('name')}")

    def _on_upload(self):
        """上传技能"""
        dialog = UploadSkillDialog(self.skill_data.get("instance_id"), self)
        dialog.exec()

    def _on_delete(self):
        """删除技能"""
        if QMessageBox.question(self, "确认删除", f"确定要删除技能 {self.skill_data.get('name')} 吗？") == QMessageBox.StandardButton.Yes:
            manager = get_skill_manager()
            manager.delete_skill(self.skill_data.get("instance_id"))
            QMessageBox.information(self, "删除成功", "技能已删除")

    def _on_download(self):
        """下载技能"""
        async def download():
            manager = get_skill_manager()
            platform = SkillPlatform(self.skill_data.get("platform", "hermes"))
            
            if platform == SkillPlatform.HERMES:
                skill = await manager.download_hermes_skill(self.skill_data.get("skill_id"))
            elif platform == SkillPlatform.AGENT_SKILLS:
                skill = await manager.download_agent_skills_skill(self.skill_data.get("skill_id"))
            else:
                QMessageBox.error(self, "下载失败", "不支持的平台")
                return

            if skill:
                QMessageBox.information(self, "下载成功", f"技能 {skill.manifest.name} 下载成功")
            else:
                QMessageBox.error(self, "下载失败", "下载技能失败")

        asyncio.create_task(download())

    def _on_details(self):
        """查看详情"""
        QMessageBox.information(self, "技能详情", str(self.skill_data))


class UploadSkillDialog(QDialog):
    """上传技能对话框"""

    def __init__(self, instance_id: str, parent=None):
        super().__init__(parent)
        self.instance_id = instance_id
        self.setWindowTitle("上传技能")
        self.resize(400, 200)

        layout = QVBoxLayout(self)

        # 平台选择
        platform_group = QGroupBox("选择平台")
        platform_layout = QVBoxLayout()
        
        self.platform_combo = QComboBox()
        self.platform_combo.addItems(["Hermes", "Agent Skills", "Custom"])
        platform_layout.addWidget(self.platform_combo)
        platform_group.setLayout(platform_layout)
        layout.addWidget(platform_group)

        # 上传按钮
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self._on_upload)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _on_upload(self):
        """上传技能"""
        platform_map = {
            "Hermes": SkillPlatform.HERMES,
            "Agent Skills": SkillPlatform.AGENT_SKILLS,
            "Custom": SkillPlatform.CUSTOM
        }

        platform = platform_map.get(self.platform_combo.currentText(), SkillPlatform.CUSTOM)

        async def upload():
            manager = get_skill_manager()
            success = await manager.upload_skill(self.instance_id, platform)
            if success:
                QMessageBox.information(self, "上传成功", "技能上传成功")
                self.accept()
            else:
                QMessageBox.error(self, "上传失败", "技能上传失败")

        asyncio.create_task(upload())


class CreateSkillDialog(QDialog):
    """创建技能对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("创建技能")
        self.resize(500, 400)

        layout = QVBoxLayout(self)

        # 表单
        form_layout = QFormLayout()

        self.name_input = QLineEdit()
        form_layout.addRow("名称:", self.name_input)

        self.description_input = QTextEdit()
        self.description_input.setFixedHeight(100)
        form_layout.addRow("描述:", self.description_input)

        self.author_input = QLineEdit()
        form_layout.addRow("作者:", self.author_input)

        self.platform_combo = QComboBox()
        self.platform_combo.addItems(["Custom", "Hermes", "Agent Skills"])
        form_layout.addRow("平台:", self.platform_combo)

        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("用逗号分隔标签")
        form_layout.addRow("标签:", self.tags_input)

        layout.addLayout(form_layout)

        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self._on_create)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _on_create(self):
        """创建技能"""
        name = self.name_input.text().strip()
        description = self.description_input.toPlainText().strip()
        author = self.author_input.text().strip()
        platform_text = self.platform_combo.currentText()
        tags = [tag.strip() for tag in self.tags_input.text().split(',') if tag.strip()]

        if not name or not description or not author:
            QMessageBox.warning(self, "输入错误", "请填写所有必填字段")
            return

        platform_map = {
            "Custom": SkillPlatform.CUSTOM,
            "Hermes": SkillPlatform.HERMES,
            "Agent Skills": SkillPlatform.AGENT_SKILLS
        }
        platform = platform_map.get(platform_text, SkillPlatform.CUSTOM)

        manager = get_skill_manager()
        skill = manager.create_skill(
            name=name,
            description=description,
            author=author,
            platform=platform,
            tags=tags
        )

        if skill:
            QMessageBox.information(self, "创建成功", f"技能 {name} 创建成功")
            self.accept()
        else:
            QMessageBox.error(self, "创建失败", "技能创建失败")


class SkillStorePanel(QWidget):
    """技能商店面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.skill_manager = get_skill_manager()
        self.skill_registry = get_skill_registry()

        self.setup_ui()
        self.load_local_skills()

    def setup_ui(self):
        """设置 UI"""
        layout = QVBoxLayout(self)

        # 标题
        title_label = QLabel("技能商店")
        title_label.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        layout.addWidget(title_label)

        # 标签页
        self.tab_widget = QTabWidget()

        # 本地技能
        self.local_tab = QWidget()
        self._setup_local_tab()
        self.tab_widget.addTab(self.local_tab, "本地技能")

        # 远程技能
        self.remote_tab = QWidget()
        self._setup_remote_tab()
        self.tab_widget.addTab(self.remote_tab, "远程技能")

        # 创建技能
        self.create_tab = QWidget()
        self._setup_create_tab()
        self.tab_widget.addTab(self.create_tab, "创建技能")

        # 统计信息
        self.stats_tab = QWidget()
        self._setup_stats_tab()
        self.tab_widget.addTab(self.stats_tab, "统计信息")

        layout.addWidget(self.tab_widget)

    def _setup_local_tab(self):
        """设置本地技能标签页"""
        layout = QVBoxLayout(self.local_tab)

        # 搜索
        search_layout = QHBoxLayout()
        self.local_search = QLineEdit()
        self.local_search.setPlaceholderText("搜索本地技能...")
        self.local_search.textChanged.connect(self._filter_local_skills)
        search_btn = QPushButton("搜索")
        search_btn.clicked.connect(self._filter_local_skills)
        search_layout.addWidget(self.local_search)
        search_layout.addWidget(search_btn)
        layout.addLayout(search_layout)

        # 技能列表
        self.local_list = QListWidget()
        self.local_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        layout.addWidget(self.local_list)

        # 刷新按钮
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self.load_local_skills)
        layout.addWidget(refresh_btn)

    def _setup_remote_tab(self):
        """设置远程技能标签页"""
        layout = QVBoxLayout(self.remote_tab)

        # 平台选择
        platform_layout = QHBoxLayout()
        platform_label = QLabel("平台:")
        self.platform_combo = QComboBox()
        self.platform_combo.addItems(["Hermes", "Agent Skills"])
        platform_layout.addWidget(platform_label)
        platform_layout.addWidget(self.platform_combo)
        platform_layout.addStretch()
        layout.addLayout(platform_layout)

        # 搜索
        search_layout = QHBoxLayout()
        self.remote_search = QLineEdit()
        self.remote_search.setPlaceholderText("搜索远程技能...")
        search_btn = QPushButton("搜索")
        search_btn.clicked.connect(self._search_remote_skills)
        search_layout.addWidget(self.remote_search)
        search_layout.addWidget(search_btn)
        layout.addLayout(search_layout)

        # 技能列表
        self.remote_list = QListWidget()
        self.remote_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        layout.addWidget(self.remote_list)

        # 刷新按钮
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self._search_remote_skills)
        layout.addWidget(refresh_btn)

    def _setup_create_tab(self):
        """设置创建技能标签页"""
        layout = QVBoxLayout(self.create_tab)

        create_btn = QPushButton("创建新技能")
        create_btn.setStyleSheet("background-color: #4caf50; color: white; font-size: 14px; padding: 10px;")
        create_btn.clicked.connect(self._create_skill)
        layout.addWidget(create_btn)

        # 提示
        hint_label = QLabel("创建技能后，您可以在本地技能标签页中管理和编辑它。")
        hint_label.setWordWrap(True)
        hint_label.setStyleSheet("color: #666; margin-top: 20px;")
        layout.addWidget(hint_label)

    def _setup_stats_tab(self):
        """设置统计信息标签页"""
        layout = QVBoxLayout(self.stats_tab)

        self.stats_text = QTextBrowser()
        self.stats_text.setStyleSheet("border: 1px solid #e0e0e0; border-radius: 4px;")
        layout.addWidget(self.stats_text)

        refresh_btn = QPushButton("刷新统计")
        refresh_btn.clicked.connect(self._update_stats)
        layout.addWidget(refresh_btn)

        self._update_stats()

    def load_local_skills(self):
        """加载本地技能"""
        self.local_list.clear()

        skills = self.skill_manager.get_all_skills()
        for skill in skills:
            skill_data = {
                "instance_id": skill.instance_id,
                "name": skill.manifest.name,
                "version": skill.manifest.version,
                "description": skill.manifest.description,
                "author": skill.manifest.author,
                "platform": skill.manifest.platform.value,
                "tags": skill.manifest.tags,
                "enabled": skill.enabled,
                "last_used": skill.last_used,
                "usage_count": skill.usage_count
            }

            item = QListWidgetItem()
            widget = SkillItemWidget(skill_data, is_local=True)
            item.setSizeHint(widget.sizeHint())
            self.local_list.addItem(item)
            self.local_list.setItemWidget(item, widget)

    def _filter_local_skills(self):
        """过滤本地技能"""
        query = self.local_search.text().lower()
        self.local_list.clear()

        skills = self.skill_manager.search_skills(query)
        for skill in skills:
            skill_data = {
                "instance_id": skill.instance_id,
                "name": skill.manifest.name,
                "version": skill.manifest.version,
                "description": skill.manifest.description,
                "author": skill.manifest.author,
                "platform": skill.manifest.platform.value,
                "tags": skill.manifest.tags
            }

            item = QListWidgetItem()
            widget = SkillItemWidget(skill_data, is_local=True)
            item.setSizeHint(widget.sizeHint())
            self.local_list.addItem(item)
            self.local_list.setItemWidget(item, widget)

    def _search_remote_skills(self):
        """搜索远程技能"""
        async def search():
            platform_text = self.platform_combo.currentText()
            platform_map = {
                "Hermes": SkillPlatform.HERMES,
                "Agent Skills": SkillPlatform.AGENT_SKILLS
            }
            platform = platform_map.get(platform_text, SkillPlatform.HERMES)

            query = self.remote_search.text()
            skills = await self.skill_registry.search_remote_skills(query, platform)

            self.remote_list.clear()
            for skill in skills:
                item = QListWidgetItem()
                widget = SkillItemWidget(skill, is_local=False)
                item.setSizeHint(widget.sizeHint())
                self.remote_list.addItem(item)
                self.remote_list.setItemWidget(item, widget)

        asyncio.create_task(search())

    def _create_skill(self):
        """创建技能"""
        dialog = CreateSkillDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_local_skills()

    def _update_stats(self):
        """更新统计信息"""
        stats = self.skill_manager.get_skill_stats()
        stats_text = f"""
## 技能统计

### 总体情况
- 总技能数: {stats.get('total_skills', 0)}
- 已启用: {stats.get('enabled_skills', 0)}
- 已禁用: {stats.get('disabled_skills', 0)}

### 按平台分布
"""

        by_platform = stats.get('skills_by_platform', {})
        for platform, count in by_platform.items():
            stats_text += f"- {platform}: {count}\n"

        self.stats_text.setMarkdown(stats_text)


class SkillStoreDialog(QWidget):
    """技能商店对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("技能商店 - Hermes Agent")
        self.resize(800, 600)

        layout = QVBoxLayout(self)
        self.skill_panel = SkillStorePanel()
        layout.addWidget(self.skill_panel)

        self.setLayout(layout)


if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    dialog = SkillStoreDialog()
    dialog.show()
    sys.exit(app.exec())
