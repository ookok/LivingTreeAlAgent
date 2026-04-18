"""
PyQt6 专家系统管理面板
提供人格管理、技能包管理和导入导出功能
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QListWidget, QListWidgetItem, QTextEdit, QPushButton,
    QLabel, QLineEdit, QComboBox, QSplitter, QGroupBox,
    QFormLayout, QCheckBox, QSpinBox, QScrollArea,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QDialog, QDialogButtonBox, QFileDialog, QMessageBox,
    QProgressBar, QToolBar, QStatusBar, QFrame, QInputDialog
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QIcon, QFont, QAction, QColor, QTextCursor

from typing import Optional, Dict, List, Any
import json
from datetime import datetime
from pathlib import Path

from . import (
    ExpertRepository, ExportManager, 
    Persona, Skill,
    BUILTIN_PERSONAS, BUILTIN_SKILLS,
    SOCIAL_ROLES
)


class PersonaEditorDialog(QDialog):
    """人格编辑器对话框"""
    
    def __init__(self, persona: Optional[Persona] = None, parent=None):
        super().__init__(parent)
        self.persona = persona
        self.is_edit = persona is not None
        self.init_ui()
        if persona:
            self.load_persona(persona)
    
    def init_ui(self):
        self.setWindowTitle("编辑人格" if self.is_edit else "新建人格")
        self.setMinimumSize(700, 600)
        
        layout = QVBoxLayout(self)
        
        # 基本信息
        basic_group = QGroupBox("基本信息")
        basic_layout = QFormLayout()
        
        self.name_edit = QLineEdit()
        self.id_edit = QLineEdit()
        self.domain_combo = QComboBox()
        self.domain_combo.addItems([
            "general", "business", "legal", "engineering", 
            "academic", "education", "environment", "analytics"
        ])
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(80)
        
        basic_layout.addRow("名称:", self.name_edit)
        basic_layout.addRow("ID:", self.id_edit)
        basic_layout.addRow("领域:", self.domain_combo)
        basic_layout.addRow("描述:", self.description_edit)
        basic_group.setLayout(basic_layout)
        layout.addWidget(basic_group)
        
        # 系统提示词
        prompt_group = QGroupBox("系统提示词")
        prompt_layout = QVBoxLayout()
        
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText("输入系统提示词...")
        self.prompt_edit.setMinimumHeight(150)
        prompt_layout.addWidget(self.prompt_edit)
        prompt_group.setLayout(prompt_layout)
        layout.addWidget(prompt_group)
        
        # 触发条件
        trigger_group = QGroupBox("触发条件")
        trigger_layout = QVBoxLayout()
        
        self.trigger_text = QTextEdit()
        self.trigger_text.setPlaceholderText(
            "格式示例：\n"
            "- role: enterprise_manager (权重: 2.0)\n"
            "- concern: 成本 (阈值: 0.7)\n"
            "- expertise: expert\n"
            "- keyword: 技术方案"
        )
        self.trigger_text.setMinimumHeight(100)
        trigger_layout.addWidget(self.trigger_text)
        trigger_group.setLayout(trigger_layout)
        layout.addWidget(trigger_group)
        
        # 按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def load_persona(self, persona: Persona):
        """加载人格数据"""
        self.name_edit.setText(persona.name)
        self.id_edit.setText(persona.id)
        self.id_edit.setEnabled(False)
        self.domain_combo.setCurrentText(persona.domain)
        self.description_edit.setText(persona.description or "")
        self.prompt_edit.setText(persona.system_prompt or "")
        
        conditions = []
        for cond in persona.trigger_conditions:
            cond_type = cond.get("type", "")
            value = cond.get("value", "")
            weight = cond.get("weight", 1.0)
            threshold = cond.get("threshold", "")
            
            line = f"- {cond_type}: {value} (权重: {weight})"
            if threshold:
                line += f" (阈值: {threshold})"
            conditions.append(line)
        
        self.trigger_text.setText("\n".join(conditions))
    
    def get_persona_data(self) -> Dict:
        """获取编辑后的人格数据"""
        import re
        
        trigger_conditions = []
        for line in self.trigger_text.toPlainText().split("\n"):
            line = line.strip()
            if not line.startswith("-"):
                continue
            
            parts = line[1:].strip().split(":")
            if len(parts) < 2:
                continue
            
            cond_type = parts[0].strip()
            rest = ":".join(parts[1:]).strip()
            
            cond = {"type": cond_type, "value": rest, "weight": 1.0}
            
            weight_match = re.search(r'\(权重[:：]\s*([\d.]+)\)', rest)
            if weight_match:
                cond["weight"] = float(weight_match.group(1))
                rest = re.sub(r'\s*\(权重[:：][\d.]+\)', '', rest)
            
            threshold_match = re.search(r'\(阈值[:：]\s*([\d.]+)\)', rest)
            if threshold_match:
                cond["threshold"] = float(threshold_match.group(1))
                rest = re.sub(r'\s*\(阈值[:：][\d.]+\)', '', rest)
            
            cond["value"] = rest
            trigger_conditions.append(cond)
        
        return {
            "id": self.id_edit.text(),
            "name": self.name_edit.text(),
            "domain": self.domain_combo.currentText(),
            "description": self.description_edit.toPlainText(),
            "system_prompt": self.prompt_edit.toPlainText(),
            "trigger_conditions": trigger_conditions,
            "traits": {},
            "skill_ids": [],
        }
    
    def validate(self) -> bool:
        """验证输入"""
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "验证失败", "请输入人格名称")
            return False
        if not self.id_edit.text().strip():
            QMessageBox.warning(self, "验证失败", "请输入人格 ID")
            return False
        return True


class SkillEditorDialog(QDialog):
    """技能包编辑器对话框"""
    
    def __init__(self, skill: Optional[Skill] = None, parent=None):
        super().__init__(parent)
        self.skill = skill
        self.is_edit = skill is not None
        self.init_ui()
        if skill:
            self.load_skill(skill)
    
    def init_ui(self):
        self.setWindowTitle("编辑技能包" if self.is_edit else "新建技能包")
        self.setMinimumSize(600, 550)
        
        layout = QVBoxLayout(self)
        
        # 基本信息
        basic_group = QGroupBox("基本信息")
        basic_layout = QFormLayout()
        
        self.name_edit = QLineEdit()
        self.id_edit = QLineEdit()
        self.category_combo = QComboBox()
        self.category_combo.addItems([
            "general", "business", "legal", "engineering",
            "academic", "education", "environment"
        ])
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(60)
        
        basic_layout.addRow("名称:", self.name_edit)
        basic_layout.addRow("ID:", self.id_edit)
        basic_layout.addRow("分类:", self.category_combo)
        basic_layout.addRow("描述:", self.description_edit)
        basic_group.setLayout(basic_layout)
        layout.addWidget(basic_group)
        
        # 触发关键词
        keywords_group = QGroupBox("触发关键词")
        keywords_layout = QVBoxLayout()
        
        self.keywords_edit = QLineEdit()
        self.keywords_edit.setPlaceholderText("用逗号分隔，如：成本，预算，ROI")
        keywords_layout.addWidget(self.keywords_edit)
        keywords_group.setLayout(keywords_layout)
        layout.addWidget(keywords_group)
        
        # 技能指令
        instructions_group = QGroupBox("技能指令")
        instructions_layout = QVBoxLayout()
        
        self.instructions_edit = QTextEdit()
        self.instructions_edit.setMinimumHeight(120)
        instructions_layout.addWidget(self.instructions_edit)
        instructions_group.setLayout(instructions_layout)
        layout.addWidget(instructions_group)
        
        # 示例提示词
        prompts_group = QGroupBox("示例提示词")
        prompts_layout = QVBoxLayout()
        
        self.prompts_edit = QTextEdit()
        self.prompts_edit.setPlaceholderText("每行一个示例...")
        self.prompts_edit.setMinimumHeight(80)
        prompts_layout.addWidget(self.prompts_edit)
        prompts_group.setLayout(prompts_layout)
        layout.addWidget(prompts_group)
        
        # 按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def load_skill(self, skill: Skill):
        """加载技能包数据"""
        self.name_edit.setText(skill.name)
        self.id_edit.setText(skill.id)
        self.id_edit.setEnabled(False)
        self.category_combo.setCurrentText(skill.category)
        self.description_edit.setText(skill.description or "")
        self.keywords_edit.setText(", ".join(skill.trigger_keywords))
        self.instructions_edit.setText(skill.instructions or "")
        self.prompts_edit.setText("\n".join(skill.prompts))
    
    def get_skill_data(self) -> Dict:
        """获取编辑后的技能包数据"""
        keywords = [kw.strip() for kw in self.keywords_edit.text().split(",") if kw.strip()]
        prompts = [p.strip() for p in self.prompts_edit.toPlainText().split("\n") if p.strip()]
        
        return {
            "id": self.id_edit.text(),
            "name": self.name_edit.text(),
            "category": self.category_combo.currentText(),
            "description": self.description_edit.toPlainText(),
            "trigger_keywords": keywords,
            "trigger_domains": [],
            "instructions": self.instructions_edit.toPlainText(),
            "prompts": prompts,
            "tool_names": [],
        }
    
    def validate(self) -> bool:
        """验证输入"""
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "验证失败", "请输入技能包名称")
            return False
        return True


class ExpertPanel(QWidget):
    """
    专家系统管理面板
    
    提供：
    - 人格库管理（查看、编辑、导入、导出）
    - 技能包管理
    - 用户画像显示
    - 导入导出功能
    """
    
    persona_selected = pyqtSignal(str)
    skill_selected = pyqtSignal(str)
    
    def __init__(self, expert_system=None, parent=None):
        super().__init__(parent)
        self.expert_system = expert_system
        self.repository = ExpertRepository()
        self.export_manager = ExportManager(self.repository)
        self.init_ui()
    
    def init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        
        self.tabs = QTabWidget()
        
        self.persona_tab = self._create_persona_tab()
        self.tabs.addTab(self.persona_tab, "👤 人格库")
        
        self.skill_tab = self._create_skill_tab()
        self.tabs.addTab(self.skill_tab, "🛠️ 技能包")
        
        self.import_export_tab = self._create_import_export_tab()
        self.tabs.addTab(self.import_export_tab, "📦 导入导出")
        
        self.profile_tab = self._create_profile_tab()
        self.tabs.addTab(self.profile_tab, "👥 用户画像")
        
        layout.addWidget(self.tabs)
        
        self._refresh_personas()
        self._refresh_skills()
    
    def _create_persona_tab(self) -> QWidget:
        """创建人格库页面"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        
        left_panel = QVBoxLayout()
        
        toolbar = QHBoxLayout()
        
        self.persona_search = QLineEdit()
        self.persona_search.setPlaceholderText("搜索人格...")
        self.persona_search.textChanged.connect(self._filter_personas)
        toolbar.addWidget(self.persona_search)
        
        add_btn = QPushButton("新建")
        add_btn.clicked.connect(self._add_persona)
        toolbar.addWidget(add_btn)
        
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self._refresh_personas)
        toolbar.addWidget(refresh_btn)
        
        left_panel.addLayout(toolbar)
        
        self.persona_list = QListWidget()
        self.persona_list.itemClicked.connect(self._on_persona_clicked)
        self.persona_list.itemDoubleClicked.connect(self._edit_persona)
        left_panel.addWidget(self.persona_list)
        
        filter_layout = QHBoxLayout()
        self.show_builtin_check = QCheckBox("显示内置")
        self.show_builtin_check.setChecked(True)
        self.show_builtin_check.stateChanged.connect(self._refresh_personas)
        filter_layout.addWidget(self.show_builtin_check)
        filter_layout.addStretch()
        left_panel.addLayout(filter_layout)
        
        layout.addLayout(left_panel, 1)
        
        self.persona_detail = QTextEdit()
        self.persona_detail.setReadOnly(True)
        layout.addWidget(self.persona_detail, 2)
        
        return widget
    
    def _create_skill_tab(self) -> QWidget:
        """创建技能包页面"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        
        left_panel = QVBoxLayout()
        
        toolbar = QHBoxLayout()
        
        self.skill_search = QLineEdit()
        self.skill_search.setPlaceholderText("搜索技能包...")
        self.skill_search.textChanged.connect(self._filter_skills)
        toolbar.addWidget(self.skill_search)
        
        add_btn = QPushButton("新建")
        add_btn.clicked.connect(self._add_skill)
        toolbar.addWidget(add_btn)
        
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self._refresh_skills)
        toolbar.addWidget(refresh_btn)
        
        left_panel.addLayout(toolbar)
        
        self.skill_list = QListWidget()
        self.skill_list.itemClicked.connect(self._on_skill_clicked)
        self.skill_list.itemDoubleClicked.connect(self._edit_skill)
        left_panel.addWidget(self.skill_list)
        
        layout.addLayout(left_panel, 1)
        
        self.skill_detail = QTextEdit()
        self.skill_detail.setReadOnly(True)
        layout.addWidget(self.skill_detail, 2)
        
        return widget
    
    def _create_import_export_tab(self) -> QWidget:
        """创建导入导出页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 导入区
        import_group = QGroupBox("导入")
        import_layout = QVBoxLayout()
        
        file_import_layout = QHBoxLayout()
        self.import_path_edit = QLineEdit()
        self.import_path_edit.setPlaceholderText("选择文件...")
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._browse_import_file)
        file_import_layout.addWidget(self.import_path_edit)
        file_import_layout.addWidget(browse_btn)
        import_layout.addLayout(file_import_layout)
        
        import_buttons = QHBoxLayout()
        import_file_btn = QPushButton("导入文件")
        import_file_btn.clicked.connect(self._import_from_file)
        import_url_btn = QPushButton("从 URL 导入")
        import_url_btn.clicked.connect(self._import_from_url)
        import_buttons.addWidget(import_file_btn)
        import_buttons.addWidget(import_url_btn)
        import_buttons.addStretch()
        import_layout.addLayout(import_buttons)
        
        import_group.setLayout(import_layout)
        layout.addWidget(import_group)
        
        # 导出区
        export_group = QGroupBox("导出")
        export_layout = QVBoxLayout()
        
        options_layout = QHBoxLayout()
        self.export_builtin_check = QCheckBox("包含内置")
        self.export_builtin_check.setChecked(False)
        options_layout.addWidget(self.export_builtin_check)
        options_layout.addStretch()
        export_layout.addLayout(options_layout)
        
        export_buttons = QHBoxLayout()
        export_single_btn = QPushButton("导出选中人格")
        export_single_btn.clicked.connect(self._export_single_persona)
        export_all_md_btn = QPushButton("导出全部 (Markdown)")
        export_all_md_btn.clicked.connect(self._export_all_markdown)
        export_zip_btn = QPushButton("导出为 ZIP")
        export_zip_btn.clicked.connect(self._export_to_zip)
        export_buttons.addWidget(export_single_btn)
        export_buttons.addWidget(export_all_md_btn)
        export_buttons.addWidget(export_zip_btn)
        export_layout.addLayout(export_buttons)
        
        export_group.setLayout(export_layout)
        layout.addWidget(export_group)
        
        # 批量导入
        batch_group = QGroupBox("批量导入 (ZIP)")
        batch_layout = QVBoxLayout()
        
        batch_layout_inner = QHBoxLayout()
        self.batch_import_path_edit = QLineEdit()
        self.batch_import_path_edit.setPlaceholderText("选择 ZIP 文件...")
        browse_batch_btn = QPushButton("浏览...")
        browse_batch_btn.clicked.connect(self._browse_batch_file)
        batch_layout_inner.addWidget(self.batch_import_path_edit)
        batch_layout_inner.addWidget(browse_batch_btn)
        batch_layout.addLayout(batch_layout_inner)
        
        batch_import_btn = QPushButton("批量导入")
        batch_import_btn.clicked.connect(self._batch_import)
        batch_layout.addWidget(batch_import_btn)
        
        batch_group.setLayout(batch_layout)
        layout.addWidget(batch_group)
        
        self.import_status = QLabel("")
        layout.addWidget(self.import_status)
        
        layout.addStretch()
        return widget
    
    def _create_profile_tab(self) -> QWidget:
        """创建用户画像页面"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        self.profile_display = QTextEdit()
        self.profile_display.setReadOnly(True)
        layout.addWidget(self.profile_display)
        
        refresh_btn = QPushButton("刷新画像")
        refresh_btn.clicked.connect(self._refresh_profile)
        layout.addWidget(refresh_btn)
        
        preset_group = QGroupBox("快速切换用户角色")
        preset_layout = QHBoxLayout()
        
        roles = [
            ("企业管理者", "enterprise_manager"),
            ("政府官员", "government_official"),
            ("工程师", "engineer"),
            ("研究人员", "researcher"),
            ("学生", "student"),
        ]
        
        for name, role_id in roles:
            btn = QPushButton(name)
            btn.clicked.connect(lambda checked, r=role_id: self._switch_role(r))
            preset_layout.addWidget(btn)
        
        preset_layout.addStretch()
        preset_group.setLayout(preset_layout)
        layout.addWidget(preset_group)
        
        return widget
    
    # 人格库操作
    def _refresh_personas(self):
        self.persona_list.clear()
        show_builtin = self.show_builtin_check.isChecked()
        
        for persona in self.repository.get_all_personas():
            if not show_builtin and persona.is_builtin:
                continue
            
            search_text = self.persona_search.text().lower()
            if search_text:
                if search_text not in persona.name.lower() and \
                   search_text not in persona.id.lower():
                    continue
            
            item = QListWidgetItem(f"📋 {persona.name}")
            item.setData(Qt.ItemDataRole.UserRole, persona.id)
            
            if persona.is_builtin:
                item.setForeground(QColor(128, 128, 128))
            
            self.persona_list.addItem(item)
    
    def _filter_personas(self):
        self._refresh_personas()
    
    def _on_persona_clicked(self, item: QListWidgetItem):
        persona_id = item.data(Qt.ItemDataRole.UserRole)
        persona = self.repository.get_persona(persona_id)
        
        if persona:
            content = self.export_manager.export_persona_markdown(persona_id)
            if content:
                self.persona_detail.setMarkdown(content)
    
    def _add_persona(self):
        dialog = PersonaEditorDialog(parent=self)
        if dialog.exec():
            data = dialog.get_persona_data()
            persona = Persona(**data)
            
            if self.repository.add_persona(persona):
                self._refresh_personas()
                QMessageBox.information(self, "成功", "人格创建成功")
            else:
                QMessageBox.warning(self, "失败", "人格 ID 已存在")
    
    def _edit_persona(self, item: QListWidgetItem):
        persona_id = item.data(Qt.ItemDataRole.UserRole)
        persona = self.repository.get_persona(persona_id)
        
        if not persona:
            return
        
        dialog = PersonaEditorDialog(persona, parent=self)
        if dialog.exec():
            data = dialog.get_persona_data()
            updated = Persona(**data)
            updated.is_builtin = persona.is_builtin
            
            if self.repository.update_persona(updated):
                self._refresh_personas()
                QMessageBox.information(self, "成功", "人格更新成功")
    
    # 技能包操作
    def _refresh_skills(self):
        self.skill_list.clear()
        
        for skill in self.repository.get_all_skills():
            search_text = self.skill_search.text().lower()
            if search_text:
                if search_text not in skill.name.lower() and \
                   search_text not in skill.id.lower():
                    continue
            
            item = QListWidgetItem(f"🛠️ {skill.name}")
            item.setData(Qt.ItemDataRole.UserRole, skill.id)
            
            if skill.is_builtin:
                item.setForeground(QColor(128, 128, 128))
            
            self.skill_list.addItem(item)
    
    def _filter_skills(self):
        self._refresh_skills()
    
    def _on_skill_clicked(self, item: QListWidgetItem):
        skill_id = item.data(Qt.ItemDataRole.UserRole)
        content = self.export_manager.export_skill_markdown(skill_id)
        if content:
            self.skill_detail.setMarkdown(content)
    
    def _add_skill(self):
        dialog = SkillEditorDialog(parent=self)
        if dialog.exec():
            data = dialog.get_skill_data()
            skill = Skill(**data)
            
            if self.repository.add_skill(skill):
                self._refresh_skills()
                QMessageBox.information(self, "成功", "技能包创建成功")
            else:
                QMessageBox.warning(self, "失败", "技能包 ID 已存在")
    
    def _edit_skill(self, item: QListWidgetItem):
        skill_id = item.data(Qt.ItemDataRole.UserRole)
        skill = self.repository.get_skill(skill_id)
        
        if not skill:
            return
        
        dialog = SkillEditorDialog(skill, parent=self)
        if dialog.exec():
            data = dialog.get_skill_data()
            updated = Skill(**data)
            updated.is_builtin = skill.is_builtin
            
            if self.repository.update_skill(updated):
                self._refresh_skills()
                QMessageBox.information(self, "成功", "技能包更新成功")
    
    # 导入导出操作
    def _browse_import_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择文件", "",
            "支持的文件 (*.md *.json);;所有文件 (*)"
        )
        if path:
            self.import_path_edit.setText(path)
    
    def _import_from_file(self):
        path = self.import_path_edit.text().strip()
        if not path:
            QMessageBox.warning(self, "错误", "请选择文件")
            return
        
        result = self.export_manager.import_from_file(path)
        
        if result.get("success"):
            self.import_status.setText(f"✅ {result.get('message')}")
            self._refresh_personas()
            self._refresh_skills()
        else:
            self.import_status.setText(f"❌ {result.get('message')}")
    
    def _import_from_url(self):
        url, ok = QInputDialog.getText(self, "从 URL 导入", "请输入 URL:")
        if ok and url:
            result = self.export_manager.import_from_url(url)
            
            if result.get("success"):
                self.import_status.setText(f"✅ {result.get('message')}")
                self._refresh_personas()
                self._refresh_skills()
            else:
                self.import_status.setText(f"❌ {result.get('message')}")
    
    def _export_single_persona(self):
        current_item = self.persona_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "错误", "请先选择人格")
            return
        
        persona_id = current_item.data(Qt.ItemDataRole.UserRole)
        path, _ = QFileDialog.getSaveFileName(
            self, "保存人格", f"{persona_id}.md",
            "Markdown (*.md);;JSON (*.json)"
        )
        
        if path:
            if path.endswith('.json'):
                content = self.export_manager.export_persona_json(persona_id)
            else:
                content = self.export_manager.export_persona_markdown(persona_id)
            
            if content:
                Path(path).write_text(content, encoding='utf-8')
                self.import_status.setText(f"✅ 已导出到 {path}")
    
    def _export_all_markdown(self):
        path = QFileDialog.getExistingDirectory(self, "选择导出目录")
        if path:
            results = self.export_manager.export_all_markdown(path)
            count = len(results["personas"]) + len(results["skills"])
            self.import_status.setText(f"✅ 已导出 {count} 个文件到 {path}")
    
    def _export_to_zip(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "导出为 ZIP", "expert_export.zip",
            "ZIP 压缩包 (*.zip)"
        )
        
        if path:
            include_builtin = self.export_builtin_check.isChecked()
            
            if self.export_manager.export_to_zip(path, include_builtin):
                self.import_status.setText(f"✅ 已导出到 {path}")
            else:
                self.import_status.setText("❌ 导出失败")
    
    def _browse_batch_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 ZIP 文件", "", "ZIP 文件 (*.zip)"
        )
        if path:
            self.batch_import_path_edit.setText(path)
    
    def _batch_import(self):
        path = self.batch_import_path_edit.text().strip()
        if not path:
            QMessageBox.warning(self, "错误", "请选择 ZIP 文件")
            return
        
        result = self.export_manager.import_from_zip(path)
        
        self.import_status.setText(result.get("message", "未知错误"))
        
        if result.get("success"):
            self._refresh_personas()
            self._refresh_skills()
    
    # 用户画像操作
    def _refresh_profile(self):
        if not self.expert_system:
            self.profile_display.setPlainText("专家系统未初始化")
            return
        
        profile = self.expert_system.get_current_profile("default")
        
        lines = [
            "# 用户画像",
            "",
            f"**用户ID**: {profile.user_id}",
            f"**消息数**: {profile.message_count}",
            f"**置信度**: {profile.confidence:.0%}",
            f"**更新时间**: {datetime.fromtimestamp(profile.updated_at).strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## 社会角色",
            "",
        ]
        
        if profile.social_roles:
            for role, score in sorted(profile.social_roles.items(), key=lambda x: x[1], reverse=True):
                role_name = SOCIAL_ROLES.get(role, {}).get("name", role)
                lines.append(f"- {role_name}: {score:.0%}")
        else:
            lines.append("（尚未识别）")
        
        lines.extend([
            "",
            "## 核心关切",
            "",
        ])
        
        if profile.core_concerns:
            for concern, weight in sorted(profile.core_concerns.items(), key=lambda x: x[1], reverse=True):
                lines.append(f"- {concern}: {weight:.0%}")
        else:
            lines.append("（尚未识别）")
        
        lines.extend([
            "",
            f"## 知识水平: {profile.expertise_level}",
            f"## 决策风格: {profile.decision_style}",
            f"## 沟通偏好: {profile.communication_preference}",
        ])
        
        self.profile_display.setMarkdown("\n".join(lines))
    
    def _switch_role(self, role_id: str):
        if not self.expert_system:
            return
        
        profile = self.expert_system.get_current_profile("default")
        profile.social_roles[role_id] = 0.9
        profile.confidence = 0.8
        
        self.expert_system.profile_parser._save_profiles()
        self._refresh_profile()
        
        role_name = SOCIAL_ROLES.get(role_id, {}).get("name", role_id)
        QMessageBox.information(self, "角色切换", f"已切换到: {role_name}")
