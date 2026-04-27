"""
SpellCheckTextEdit - 实时错别字检查输入框（QThread 真正异步版）

功能：
1. 实时检测输入框中的错别字（防抖 500ms）
2. 用红色下划线标注疑似错别字
3. 右键点击错别字显示纠正建议
4. 支持中英文混合文本
5. 真正异步：QThread + signal/slot，零 UI 阻塞

使用方法：
    from client.src.presentation.components.spell_check_edit import SpellCheckTextEdit

    edit = SpellCheckTextEdit()
    edit.setPlaceholderText("输入文本...")
    # 错别字检测信号
    edit.corrections_found.connect(lambda corrections: print(corrections))
    # 纠正建议请求信号
    edit.correction_requested.connect(lambda word, pos: show_menu(word, pos))

Author: LivingTreeAI Agent
Date: 2026-04-28
"""

import re
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import (
    QTimer, Qt, pyqtSignal, QObject,
    QThread, pyqtSlot
)
from PyQt6.QtGui import QTextCharFormat, QTextCursor, QColor
from PyQt6.QtWidgets import QMenu, QTextEdit, QWidget

from loguru import logger


class SpellCheckWorker(QThread):
    """
    错别字检查工作线程（QThread 真正异步）

    在后台线程中调用 TextCorrectionTool，
    通过 Qt signal/slot 将结果传回主线程，零 UI 阻塞。
    """

    # 信号
    finished = pyqtSignal(dict)        # 检查完成 → 发送结果 dict
    error    = pyqtSignal(str)         # 检查失败 → 发送错误信息
    progress = pyqtSignal(int, str)   # 进度更新 (percent, status_msg)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._text: str    = ""
        self._context: str = ""
        self._tool = None   # 延迟初始化，避免跨线程共享对象

    # ------------------------------------------------------------------ #
    # 公有方法（均在主线程调用，在 run() 前设置）
    # ------------------------------------------------------------------ #

    def set_task(self, text: str, context: str = "") -> None:
        """设置待检查文本（由主线程在 start() 前调用）"""
        self._text    = text
        self._context = context

    # ------------------------------------------------------------------ #
    # QThread 入口
    # ------------------------------------------------------------------ #

    def run(self) -> None:
        """
        在线程启动后自动调用。
        所有耗时操作在这里执行，不会阻塞 UI 线程。
        """
        try:
            self.progress.emit(10, "正在加载纠正工具…")

            # 延迟导入 —— 必须在工作线程中 import，不能跨线程共享模块对象
            from client.src.business.tools.text_correction_tool import TextCorrectionTool

            self.progress.emit(30, "正在检查错别字…")

            if self._tool is None:
                self._tool = TextCorrectionTool()

            result: dict = self._tool.correct_text(self._text, self._context)

            self.progress.emit(90, "检查完成，正在回传结果…")
            self.finished.emit(result)

        except Exception as e:
            logger.error(f"[SpellCheckWorker] 检查失败: {e}")
            self.error.emit(str(e))


# -------------------------------------------------------------------------- #
# SpellCheckTextEdit
# -------------------------------------------------------------------------- #

class SpellCheckTextEdit(QTextEdit):
    """
    实时错别字检查输入框

    功能：
    - 实时检测错别字（防抖 500 ms，QThread 异步检查）
    - 红色下划线标注疑似错别字
    - 右键显示纠正建议
    - 支持中英文混合
    """

    # 信号
    corrections_found  = pyqtSignal(list)   # 发现错别字 → [{"word", "corrected", "start", "end"}, ...]
    correction_requested = pyqtSignal(str, int)  # 用户请求纠正建议 → (word, cursor_position)

    def __init__(self, placeholder: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)

        # 防抖定时器
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._on_debounce_timeout)
        self._debounce_delay_ms: int = 500

        # 当前错别字列表 & 位置缓存
        self._corrections: List[Dict] = []
        # 每个元素: (start_char_pos, end_char_pos, correction_dict)
        self._correction_positions: List[Tuple[int, int, Dict]] = []

        # 下划线格式
        self._fmt_underline = QTextCharFormat()
        self._fmt_underline.setUnderlineColor(QColor(255, 0, 0))
        self._fmt_underline.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SingleUnderline)

        # 普通格式（清除下划线）
        self._fmt_normal = QTextCharFormat()
        self._fmt_normal.setUnderlineStyle(QTextCharFormat.UnderlineStyle.NoUnderline)

        # ---- QThread 工作线程 ----
        self._worker: Optional[SpellCheckWorker] = None
        self._worker_thread: Optional[QThread] = None
        # 正在等待结果的文本（用于校验回调是否属于过期请求）
        self._pending_text: str = ""

        # 连接文本变化信号
        self.textChanged.connect(self._on_text_changed)

        # 右键菜单
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    # ==================================================================== #
    # 公有接口
    # ==================================================================== #

    def set_debounce_delay(self, delay_ms: int) -> None:
        """设置防抖延迟（毫秒）"""
        self._debounce_delay_ms = max(100, delay_ms)

    def get_corrections(self) -> List[Dict]:
        """获取当前错别字列表"""
        return self._corrections

    def has_corrections(self) -> bool:
        """是否有错别字"""
        return len(self._corrections) > 0

    def accept_suggestion(self, original: str, corrected: str) -> None:
        """接受纠正建议（供外部调用）"""
        self._apply_correction(original, corrected)

    # ==================================================================== #
    # 内部槽 / 回调
    # ==================================================================== #

    def _on_text_changed(self) -> None:
        """文本变化时触发防抖计时器"""
        self._debounce_timer.stop()
        self._debounce_timer.start(self._debounce_delay_ms)

    def _on_debounce_timeout(self) -> None:
        """防抖到期 → 启动异步检查"""
        text = self.toPlainText().strip()
        if not text:
            self._clear_underlines()
            self._corrections = []
            self.corrections_found.emit([])
            return
        self._check_async(text)

    # ------------------------------------------------------------------ #
    # 真正的 QThread + signal/slot 异步检查
    # ------------------------------------------------------------------ #

    def _check_async(self, text: str) -> None:
        """
        启动工作线程执行错别字检查。

        流程：
        1. 如果已有线程在运行 → 先 quit + wait 优雅退出
        2. 创建 SpellCheckWorker，moveToThread
        3. 连接信号：worker.finished  → _on_worker_finished
                             worker.error     → _on_worker_error
                             worker.progress → _on_worker_progress
                             thread.finished → worker.deleteLater
        4. thread.start() 启动线程
        """
        # 1. 清理旧线程（如果存在且仍在运行）
        self._cleanup_worker()

        # 2. 创建 worker & thread
        self._worker = SpellCheckWorker()
        self._worker_thread = QThread()
        self._worker.moveToThread(self._worker_thread)

        # 3. 跨线程信号连接（Qt.AutoConnection 会自动选择 QueuedConnection）
        self._worker.finished.connect(self._on_worker_finished, Qt.ConnectionType.QueuedConnection)
        self._worker.error.connect(self._on_worker_error, Qt.ConnectionType.QueuedConnection)
        self._worker.progress.connect(self._on_worker_progress, Qt.ConnectionType.QueuedConnection)

        # 线程结束时自动删除 worker（防止内存泄漏）
        self._worker_thread.finished.connect(self._worker.deleteLater)
        self._worker_thread.finished.connect(self._worker_thread.deleteLater)

        # 线程启动时自动执行 worker.run()
        self._worker_thread.started.connect(self._worker.run)

        # 记录当前待检查文本（用于回调校验）
        self._pending_text = text

        # 4. 传入任务参数 & 启动线程
        self._worker.set_task(text, context=self._infer_context())
        self._worker_thread.start()

    def _infer_context(self) -> str:
        """
        从当前文档中推断上下文（简化版）。

        取光标前 200 个字符作为上下文，
        帮助 LLM 更准确地判断错别字。
        """
        cursor = self.textCursor()
        # 移动到文档开头，选取最多 200 个字符
        cursor.movePosition(QTextCursor.MoveOperation.Start, QTextCursor.MoveMode.KeepAnchor)
        cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, 200)
        return cursor.selectedText().strip()

    # ------------------------------------------------------------------ #
    # 工作线程信号回调（均在 UI 线程执行）
    # ------------------------------------------------------------------ #

    def _on_worker_finished(self, result: dict) -> None:
        """
        工作线程完成检查后回调（在 UI 线程执行）。

        Args:
            result: TextCorrectionTool.correct_text() 的返回值
                   { "original_text", "corrected_text", "corrections", "has_error" }
        """
        # 防御：如果当前文本已变化，丢弃过期结果
        current_text = self.toPlainText().strip()
        if self._pending_text and self._pending_text != current_text:
            logger.debug("[SpellCheckTextEdit] 丢弃过期检查结果")
            self._cleanup_worker()
            return

        if result.get("has_error"):
            self._corrections = result.get("corrections", [])
            self._apply_underlines(current_text, self._corrections)
            self.corrections_found.emit(self._corrections)
        else:
            self._clear_underlines()
            self._corrections = []
            self.corrections_found.emit([])

        self._cleanup_worker()

    def _on_worker_error(self, error_msg: str) -> None:
        """工作线程出错时回调"""
        logger.error(f"[SpellCheckTextEdit] 检查失败: {error_msg}")
        self._cleanup_worker()

    def _on_worker_progress(self, percent: int, msg: str) -> None:
        """进度回调（预留接口，目前仅日志）"""
        logger.debug(f"[SpellCheckTextEdit] 进度 {percent}%: {msg}")

    def _cleanup_worker(self) -> None:
        """
        清理工作线程。

        注意：不能在这里直接 quit() + wait()，
        因为线程可能仍在运行。正确做法是：
        1. 调用 thread.quit() 请求事件循环退出
        2. 等待 thread.finished 信号（通过 deleteLater 自动清理）
        """
        if self._worker_thread and self._worker_thread.isRunning():
            self._worker_thread.quit()
            self._worker_thread.wait(3000)  # 最多等 3 秒

        # 将引用置空，下一轮会自动重建
        self._worker       = None
        self._worker_thread = None
        self._pending_text = ""

    # ==================================================================== #
    # 下划线绘制
    # ==================================================================== #

    def _apply_underlines(self, text: str, corrections: List[Dict]) -> None:
        """
        应用红色下划线到错别字位置。

        Args:
            text: 当前文本
            corrections: 纠正建议列表
        """
        self._clear_underlines()
        self._correction_positions.clear()

        cursor: QTextCursor = QTextCursor(self.document())

        for correction in corrections:
            original: str = correction.get("original", "")
            if not original:
                continue

            # 查找原文中所有出现位置（支持同一词多次出现）
            start = 0
            while True:
                pos = text.find(original, start)
                if pos == -1:
                    break
                end_pos = pos + len(original)

                # 应用红色下划线
                cursor.setPosition(pos)
                cursor.movePosition(
                    QTextCursor.MoveOperation.Right,
                    QTextCursor.MoveMode.KeepAnchor,
                    len(original)
                )
                cursor.mergeCharFormat(self._fmt_underline)

                # 记录位置，供右键菜单使用
                self._correction_positions.append((pos, end_pos, correction))

                start = end_pos

    def _clear_underlines(self) -> None:
        """清除所有下划线"""
        cursor: QTextCursor = QTextCursor(self.document())
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.mergeCharFormat(self._fmt_normal)

    # ==================================================================== #
    # 右键菜单
    # ==================================================================== #

    def _show_context_menu(self, pos) -> None:
        """
        显示右键菜单。

        如果光标在错别字上 → 显示纠正建议；
        否则          → 显示标准菜单（剪切/复制/粘贴/全选）。
        """
        cursor = self.cursorForPosition(pos)
        cursor_pos: int = cursor.position()

        # 检测光标是否在某个错别字范围内
        active_correction: Optional[Dict] = None
        for start, end, correction in self._correction_positions:
            if start <= cursor_pos <= end:
                active_correction = correction
                break

        menu = QMenu(self)

        if active_correction:
            original  = active_correction.get("original", "")
            corrected = active_correction.get("corrected", "")
            reason    = active_correction.get("reason", "")

            # 纠正建议动作
            label = f"✅ 纠正为：{corrected}"
            if reason:
                label += f"  ({reason})"
            action = menu.addAction(label)
            action.triggered.connect(
                lambda _checked, o=original, c=corrected: self._apply_correction(o, c)
            )
            menu.addSeparator()

        # ---- 标准编辑菜单 ----
        if self.textCursor().hasSelection():
            cut_action = menu.addAction("剪切")
            cut_action.triggered.connect(self.cut)
            copy_action = menu.addAction("复制")
            copy_action.triggered.connect(self.copy)

        paste_action = menu.addAction("粘贴")
        paste_action.triggered.connect(self.paste)

        select_all_action = menu.addAction("全选")
        select_all_action.triggered.connect(self.selectAll)

        menu.exec(self.viewport().mapToGlobal(pos))

    # ==================================================================== #
    # 纠正应用
    # ==================================================================== #

    def _apply_correction(self, original: str, corrected: str) -> None:
        """
        将原文中的错误词替换为纠正词，并保留光标位置。

        Args:
            original:  原始错误词
            corrected: 纠正后的词
        """
        text = self.toPlainText()
        new_text = text.replace(original, corrected)

        # 保存当前光标位置
        cursor = self.textCursor()
        pos = cursor.position()

        # 替换文本
        self.setPlainText(new_text)

        # 调整光标位置（考虑替换前后长度差异）
        offset = len(corrected) - len(original)
        cursor.setPosition(max(0, pos + offset))
        self.setTextCursor(cursor)

        # 触发重新检查
        self._on_text_changed()

    # ==================================================================== #
    # 析构
    # ==================================================================== #

    def __del__(self) -> None:
        """清理线程资源"""
        self._cleanup_worker()


# -------------------------------------------------------------------------- #
# 便捷函数
# -------------------------------------------------------------------------- #

def create_spell_check_edit(placeholder: str = "", parent: Optional[QWidget] = None) -> SpellCheckTextEdit:
    """
    创建实时错别字检查输入框（便捷函数）

    Args:
        placeholder: 占位符文本
        parent:      父组件

    Returns:
        SpellCheckTextEdit 实例
    """
    return SpellCheckTextEdit(placeholder, parent)


# -------------------------------------------------------------------------- #
# 测试入口
# -------------------------------------------------------------------------- #

if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget, QLabel

    app = QApplication([])

    window = QWidget()
    layout = QVBoxLayout(window)

    label = QLabel("实时错别字检查测试（输入含有错别字的文本）：")
    layout.addWidget(label)

    edit = create_spell_check_edit("输入文本…")
    edit.setMaximumHeight(100)
    layout.addWidget(edit)

    info_label = QLabel("")
    layout.addWidget(info_label)

    def on_corrections_found(corrections):
        if corrections:
            parts = ["发现错别字："]
            for c in corrections:
                parts.append(f"  - {c['original']} → {c['corrected']}  ({c.get('reason', '')})")
            info_label.setText("\n".join(parts))
        else:
            info_label.setText("✅ 未发现错别字")

    edit.corrections_found.connect(on_corrections_found)

    window.resize(500, 300)
    window.show()

    app.exec()
