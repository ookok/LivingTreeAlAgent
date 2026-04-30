"""
DocumentSkillPanel - 文档 Skill 管理面板（通用·语义分析版）

功能：
1. 用户粘贴/上传文档 → 自动语义匹配已有 Skill
2. 匹配成功 → 显示匹配结果，可选择加载 Skill
3. 无匹配   → 提示用户是否从当前文档提炼新 Skill
4. 管理已有 Skill（列表 + 删除）

集成位置：
- 可作为独立面板打开
- 也可在聊天界面中，当用户发送含文档的消息时自动弹出

Author: LivingTreeAI Agent
Date: 2026-04-28
"""

import os
import json
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QGroupBox,
    QListWidget, QListWidgetItem, QMessageBox,
    QProgressBar, QFormLayout,
)

from loguru import logger


# --------------------------------------------------------------------------- #
# Worker thread for semantic matching (non-blocking UI)
# --------------------------------------------------------------------------- #

class MatchWorker(QThread):
    """
    Worker thread for semantic skill matching.

    Runs SemanticSkillMatcher.match() in a background thread
    to avoid blocking the UI.
    """
    result_ready = pyqtSignal(list)   # List[Dict] - match results
    error_occurred = pyqtSignal(str)  # str - error message

    def __init__(self, document_text: str, top_k: int = 3):
        super().__init__()
        self._text  = document_text
        self._top_k = top_k

    def run(self) -> None:
        try:
            from business.semantic_skill_matcher import SemanticSkillMatcher
            matcher = SemanticSkillMatcher()
            results = matcher.match(self._text, top_k=self._top_k)
            self.result_ready.emit(results)
        except Exception as e:
            logger.error(f"[MatchWorker] Match failed: {e}")
            self.error_occurred.emit(str(e))


class ExtractWorker(QThread):
    """
    Worker thread for skill extraction.

    Runs DocumentSkillExtractor.extract_skill() in a background thread.
    """
    result_ready    = pyqtSignal(bool, str)  # (success, message/dir_path)
    error_occurred = pyqtSignal(str)          # str - error message

    def __init__(self, document_text: str, skill_name: str, save_dir: str):
        super().__init__()
        self._text       = document_text
        self._skill_name = skill_name
        self._save_dir   = save_dir

    def run(self) -> None:
        try:
            from business.document_skill_extractor import DocumentSkillExtractor
            extractor = DocumentSkillExtractor()
            success, msg = extractor.extract_skill(
                document_text=self._text,
                skill_name=self._skill_name,
                save_dir=self._save_dir,
            )
            self.result_ready.emit(success, msg)
        except Exception as e:
            logger.error(f"[ExtractWorker] Extraction failed: {e}")
            self.error_occurred.emit(str(e))


# --------------------------------------------------------------------------- #
# DocumentSkillPanel
# --------------------------------------------------------------------------- #

class DocumentSkillPanel(QWidget):
    """
    Document Skill management panel.

    Features:
    - Paste/upload document -> auto semantic match
    - Show match results with similarity scores
    - Button to create new Skill from document
    - List existing Skills with delete button
    """

    # Signal: user wants to apply a matched skill
    skill_selected = pyqtSignal(dict)  # Dict - skill info

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._init_ui()
        self._load_skill_list()

    def _init_ui(self) -> None:
        """Initialize UI components"""
        main_layout = QVBoxLayout(self)

        # ---- 1. Document input area ----
        input_group = QGroupBox("文档输入（粘贴或输入文档内容）")
        input_layout = QVBoxLayout(input_group)

        self._text_edit = QTextEdit()
        self._text_edit.setPlaceholderText(
            "请粘贴通知、通报、专家意见等文档内容…\n"
            "系统将自动进行语义分析，匹配已有 Skill。"
        )
        self._text_edit.setMaximumHeight(150)
        input_layout.addWidget(self._text_edit)

        # Buttons: check match / create skill
        btn_layout = QHBoxLayout()
        self._check_btn = QPushButton("🔍 语义匹配检查")
        self._check_btn.clicked.connect(self._on_check_match)
        btn_layout.addWidget(self._check_btn)

        self._create_btn = QPushButton("✨ 提炼为新 Skill")
        self._create_btn.clicked.connect(self._on_create_skill)
        self._create_btn.setEnabled(False)
        btn_layout.addWidget(self._create_btn)
        btn_layout.addStretch()
        input_layout.addLayout(btn_layout)

        # Progress bar (hidden by default)
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        input_layout.addWidget(self._progress)

        main_layout.addWidget(input_group)

        # ---- 2. Match results area ----
        result_group = QGroupBox("语义匹配结果")
        result_layout = QVBoxLayout(result_group)

        self._result_label = QLabel("请在上方输入文档内容，然后点击「语义匹配检查」")
        self._result_label.setWordWrap(True)
        self._result_label.setStyleSheet("padding: 8px; background: #f5f5f5; border-radius: 4px;")
        result_layout.addWidget(self._result_label)

        # Match list (clickable)
        self._match_list = QListWidget()
        self._match_list.itemClicked.connect(self._on_skill_clicked)
        self._match_list.setVisible(False)
        result_layout.addWidget(self._match_list)

        main_layout.addWidget(result_group)

        # ---- 3. Existing Skills list ----
        skills_group = QGroupBox("已提炼的 Skill 列表")
        skills_layout = QVBoxLayout(skills_group)

        self._skill_list = QListWidget()
        self._skill_list.setMaximumHeight(200)
        skills_layout.addWidget(self._skill_list)

        # Delete button
        del_layout = QHBoxLayout()
        self._delete_btn = QPushButton("🗑️ 删除选中 Skill")
        self._delete_btn.clicked.connect(self._on_delete_skill)
        del_layout.addWidget(self._delete_btn)
        del_layout.addStretch()
        skills_layout.addLayout(del_layout)

        main_layout.addWidget(skills_group)

        # ---- Worker threads (created on demand) ----
        self._match_worker:   Optional[MatchWorker]   = None
        self._extract_worker: Optional[ExtractWorker] = None

    # ==================================================================== #
    # Public methods
    # ==================================================================== #

    def set_document(self, text: str) -> None:
        """Set document text programmatically (e.g. from chat interface)"""
        self._text_edit.setPlainText(text)
        self._on_check_match()  # Auto-trigger match

    def get_matched_skill(self) -> Optional[Dict]:
        """Get currently selected skill info"""
        items = self._match_list.selectedItems()
        if items:
            data = items[0].data(Qt.ItemDataRole.UserRole)
            return data
        return None

    # ==================================================================== #
    # UI Slots
    # ==================================================================== #

    def _on_check_match(self) -> None:
        """Check document against existing Skills (semantic match)"""
        text = self._text_edit.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "警告", "请先输入文档内容！")
            return

        self._check_btn.setEnabled(False)
        self._create_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setRange(0, 0)  # Indeterminate
        self._result_label.setText("⏳ 正在进行语义分析，请稍候…")

        # Start worker thread
        self._match_worker = MatchWorker(text, top_k=3)
        self._match_worker.result_ready.connect(self._on_match_finished)
        self._match_worker.error_occurred.connect(self._on_match_error)
        self._match_worker.finished.connect(self._match_worker.deleteLater)
        self._match_worker.start()

    def _on_match_finished(self, results: List[Dict]) -> None:
        """Match worker finished successfully"""
        self._progress.setVisible(False)
        self._check_btn.setEnabled(True)

        if not results:
            self._result_label.setText(
                "⚠️ 未匹配到合适的 Skill。\n\n"
                "💡 是否将此文档提炼为新的 Skill？点击「✨ 提炼为新 Skill」"
            )
            self._create_btn.setEnabled(True)
            self._match_list.setVisible(False)
            return

        # Show results
        best = results[0]
        sim = best.get("similarity", 0.0)
        emoji = "✅" if sim >= 0.75 else "⚠️"

        msg = (
            f"{emoji} <b>最佳匹配</b>：<code>{best.get('name', '')}</code><br>"
            f"   相似度：<b>{sim:.2f}</b><br>"
            f"   描述：{best.get('description', '')}<br>"
        )
        if len(results) > 1:
            msg += f"<br>📋 其他匹配结果请查看下方列表。"

        self._result_label.setText(msg)
        self._create_btn.setEnabled(False)

        # Populate match list
        self._match_list.clear()
        for r in results:
            item_text = f"  相似度 {r.get('similarity', 0.0):.2f}  |  {r.get('name', '')}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, r)
            self._match_list.addItem(item)

        self._match_list.setVisible(True)

    def _on_match_error(self, error_msg: str) -> None:
        """Match worker failed"""
        self._progress.setVisible(False)
        self._check_btn.setEnabled(True)
        self._result_label.setText(f"❌ 语义匹配失败：{error_msg}")
        logger.error(f"[DocumentSkillPanel] Match error: {error_msg}")

    def _on_create_skill(self) -> None:
        """Create new Skill from current document"""
        text = self._text_edit.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "警告", "请先输入文档内容！")
            return

        # Ask for skill name
        from PyQt6.QtWidgets import QInputDialog
        skill_name, ok = QInputDialog.getText(
            self, "Skill 名称", "请输入 Skill 名称：", text="文档检查专家"
        )
        if not ok or not skill_name:
            return

        # Auto-generate save dir
        safe_name = "".join(c for c in skill_name if c.isalnum() or c in "-_").strip()
        save_dir  = f".livingtree/skills/{safe_name}"

        self._create_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setRange(0, 0)
        self._result_label.setText(f"⏳ 正在从文档提炼 Skill「{skill_name}」…")

        # Start worker thread
        self._extract_worker = ExtractWorker(text, skill_name, save_dir)
        self._extract_worker.result_ready.connect(self._on_extract_finished)
        self._extract_worker.error_occurred.connect(self._on_extract_error)
        self._extract_worker.finished.connect(self._extract_worker.deleteLater)
        self._extract_worker.start()

    def _on_extract_finished(self, success: bool, message: str) -> None:
        """Extract worker finished"""
        self._progress.setVisible(False)
        self._create_btn.setEnabled(True)

        if success:
            QMessageBox.information(self, "成功", f"Skill 提炼成功！\n\n保存位置：{message}")
            self._result_label.setText(f"✅ Skill「{self._text_edit.toPlainText()[:20]}…」提炼完成！")
            self._load_skill_list()  # Refresh list
        else:
            QMessageBox.warning(self, "失败", f"Skill 提炼失败：{message}")
            self._result_label.setText(f"❌ Skill 提炼失败：{message}")

    def _on_extract_error(self, error_msg: str) -> None:
        """Extract worker failed"""
        self._progress.setVisible(False)
        self._create_btn.setEnabled(True)
        self._result_label.setText(f"❌ Skill 提炼失败：{error_msg}")
        logger.error(f"[DocumentSkillPanel] Extract error: {error_msg}")

    def _on_skill_clicked(self, item: QListWidgetItem) -> None:
        """User clicked a matched skill in the list"""
        skill_info = item.data(Qt.ItemDataRole.UserRole)
        if skill_info:
            self.skill_selected.emit(skill_info)
            name = skill_info.get("name", "")
            self._result_label.setText(
                f"✅ 已选择 Skill：「{name}」\n\n"
                "系统将在下次遇到类似文档时自动触发此 Skill。"
            )

    def _on_delete_skill(self) -> None:
        """Delete selected Skill"""
        items = self._skill_list.selectedItems()
        if not items:
            QMessageBox.warning(self, "警告", "请先选择要删除的 Skill！")
            return

        item     = items[0]
        skill_dir = item.data(Qt.ItemDataRole.UserRole)
        skill_name = item.text()

        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除 Skill「{skill_name}」吗？\n\n此操作不可恢复！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                import shutil
                shutil.rmtree(skill_dir)
                self._load_skill_list()  # Refresh
                QMessageBox.information(self, "成功", f"Skill「{skill_name}」已删除。")
            except Exception as e:
                QMessageBox.warning(self, "失败", f"删除失败：{str(e)}")

    def _load_skill_list(self) -> None:
        """Load existing Skills into the list"""
        self._skill_list.clear()

        base = os.path.join(
            os.path.dirname(__file__), "..", "..", ".livingtree", "skills"
        )
        base = os.path.abspath(base)

        if not os.path.isdir(base):
            return

        for entry in sorted(os.listdir(base)):
            skill_dir = os.path.join(base, entry)
            skill_md  = os.path.join(skill_dir, "SKILL.md")
            if not os.path.isdir(skill_dir) or not os.path.exists(skill_md):
                continue

            # Read skill name from SKILL.md
            name = entry
            try:
                with open(skill_md, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("name:"):
                            name = line.replace("name:", "").strip()
                            break
            except Exception:
                pass

            item = QListWidgetItem(f"📋  {name}")
            item.setData(Qt.ItemDataRole.UserRole, skill_dir)
            self._skill_list.addItem(item)


# --------------------------------------------------------------------------- #
# Convenience function
# --------------------------------------------------------------------------- #

def create_document_skill_panel(parent: Optional[QWidget] = None) -> DocumentSkillPanel:
    """
    Convenience function: create DocumentSkillPanel.

    Args:
        parent: Parent widget

    Returns:
        DocumentSkillPanel instance
    """
    return DocumentSkillPanel(parent)
