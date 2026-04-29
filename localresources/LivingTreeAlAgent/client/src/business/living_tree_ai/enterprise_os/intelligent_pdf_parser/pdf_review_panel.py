"""
PDF解析结果校验面板 (PDF Review Panel)

人机协同校验界面，用于确认AI解析结果。

功能：
1. 左侧：AI提取的数据表格（可编辑）
2. 右侧：PDF预览
3. 底部：操作按钮（确认入库/修正/取消）

使用方式：
1. AI解析完成后，低置信度结果自动弹出此面板
2. 用户核对数据，修正错误
3. 点击确认，数据入库
4. 修正数据反馈给AI，持续优化
"""

import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ==================== 数据模型 ====================

@dataclass
class ReviewField:
    """待审核字段"""
    key: str
    label: str
    original_value: str
    corrected_value: Optional[str] = None
    is_modified: bool = False
    is_required: bool = False

    def to_dict(self) -> Dict:
        return {
            "key": self.key,
            "label": self.label,
            "original_value": self.original_value,
            "corrected_value": self.corrected_value,
            "is_modified": self.is_modified,
            "is_required": self.is_required
        }


@dataclass
class ReviewResult:
    """审核结果"""
    accepted: bool                    # 是否接受
    report_id: str                    # 报告ID
    corrections: List[Dict]           # 修正数据
    feedback_to_ai: bool = True       # 是否反馈给AI

    def to_dict(self) -> Dict:
        return {
            "accepted": self.accepted,
            "report_id": self.report_id,
            "corrections": self.corrections,
            "feedback_to_ai": self.feedback_to_ai
        }


# ==================== PyQt6 校验面板 ====================

try:
    from PyQt6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
        QPushButton, QLabel, QTextEdit, QSplitter, QHeaderView,
        QAbstractItemView, QMessageBox
    )
    from PyQt6.QtCore import Qt, pyqtSignal
    from PyQt6.QtGui import QFont
    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False
    logger.warning("PyQt6 not available, PDF Review Panel will not be fully functional")


if PYQT_AVAILABLE:
    class PDFReviewPanel(QDialog):
        """
        PDF解析结果校验面板

        信号：
        - accepted: 用户确认数据
        - corrected: 用户修正数据
        - cancelled: 用户取消
        """

        accepted = pyqtSignal(dict)    # 发送审核结果
        corrected = pyqtSignal(dict)  # 发送修正数据
        cancelled = pyqtSignal()       # 发送取消信号

        def __init__(
            self,
            parsed_data: Dict[str, Any],
            pdf_path: str,
            parent=None
        ):
            """
            初始化校验面板

            Args:
                parsed_data: AI解析结果
                pdf_path: PDF文件路径
                parent: 父窗口
            """
            super().__init__(parent)
            self.parsed_data = parsed_data
            self.pdf_path = pdf_path
            self.review_fields: List[ReviewField] = []

            self._init_ui()
            self._populate_data()

        def _init_ui(self):
            """初始化UI"""
            self.setWindowTitle("📋 PDF解析结果校验")
            self.setMinimumSize(1200, 700)

            # 主布局
            main_layout = QVBoxLayout(self)

            # 标题
            title_label = QLabel("🔍 请核对以下解析结果，如有错误请修正：")
            title_label.setFont(QFont("Microsoft YaHei", 10))
            main_layout.addWidget(title_label)

            # 分割器：左侧表格 + 右侧PDF预览
            splitter = QSplitter(Qt.Orientation.Horizontal)

            # 左侧：数据表格
            left_widget = self._create_data_table()
            splitter.addWidget(left_widget)

            # 右侧：PDF预览（预留）
            right_widget = self._create_pdf_preview()
            splitter.addWidget(right_widget)

            # 设置分割比例
            splitter.setStretchFactor(0, 3)
            splitter.setStretchFactor(1, 2)

            main_layout.addWidget(splitter)

            # 置信度提示
            confidence = self.parsed_data.get("confidence", 0)
            confidence_label = QLabel(
                f"📊 AI解析置信度：{confidence * 100:.1f}% "
                f"{'✅ 可自动入库' if confidence > 0.9 else '⚠️ 请人工核对'}"
            )
            confidence_label.setFont(QFont("Microsoft YaHei", 9))
            main_layout.addWidget(confidence_label)

            # 按钮栏
            button_layout = QHBoxLayout()
            button_layout.addStretch()

            self.btn_confirm = QPushButton("✅ 确认入库")
            self.btn_confirm.setStyleSheet("""
                QPushButton { background-color: #4CAF50; color: white;
                              padding: 8px 20px; border: none; border-radius: 4px; }
                QPushButton:hover { background-color: #45a049; }
            """)
            self.btn_confirm.clicked.connect(self._on_confirm)

            self.btn_correct = QPushButton("💾 保存修正")
            self.btn_correct.setStyleSheet("""
                QPushButton { background-color: #2196F3; color: white;
                              padding: 8px 20px; border: none; border-radius: 4px; }
                QPushButton:hover { background-color: #1976D2; }
            """)
            self.btn_correct.clicked.connect(self._on_correct)

            self.btn_cancel = QPushButton("❌ 取消")
            self.btn_cancel.setStyleSheet("""
                QPushButton { background-color: #9e9e9e; color: white;
                              padding: 8px 20px; border: none; border-radius: 4px; }
                QPushButton:hover { background-color: #757575; }
            """)
            self.btn_cancel.clicked.connect(self._on_cancel)

            button_layout.addWidget(self.btn_confirm)
            button_layout.addWidget(self.btn_correct)
            button_layout.addWidget(self.btn_cancel)

            main_layout.addLayout(button_layout)

        def _create_data_table(self) -> "QWidget":
            """创建数据表格"""
            widget = QWidget()
            layout = QVBoxLayout(widget)
            layout.setContentsMargins(0, 0, 0, 0)

            # 基本信息表格
            basic_label = QLabel("📝 基本信息")
            basic_label.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
            layout.addWidget(basic_label)

            self.basic_table = QTableWidget()
            self.basic_table.setColumnCount(3)
            self.basic_table.setHorizontalHeaderLabels(["字段", "AI解析值", "修正值"])
            self.basic_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
            self.basic_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            self.basic_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            self.basic_table.setAlternatingRowColors(True)
            self.basic_table.itemChanged.connect(self._on_item_changed)
            layout.addWidget(self.basic_table)

            # 监测点位表格
            points_label = QLabel("🌡️ 监测点位")
            points_label.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
            layout.addWidget(points_label)

            self.points_table = QTableWidget()
            self.points_table.setColumnCount(6)
            self.points_table.setHorizontalHeaderLabels([
                "点位ID", "点位名称", "污染物", "浓度", "标准", "是否达标"
            ])
            self.points_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            self.points_table.setAlternatingRowColors(True)
            layout.addWidget(self.points_table)

            return widget

        def _create_pdf_preview(self) -> "QWidget":
            """创建PDF预览"""
            widget = QWidget()
            layout = QVBoxLayout(widget)
            layout.setContentsMargins(0, 0, 0, 0)

            label = QLabel("📄 PDF预览")
            label.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
            layout.addWidget(label)

            # TODO: 集成PDF预览控件
            # 目前显示占位符
            placeholder = QLabel(f"文件：{self.pdf_path}\n\n（PDF预览区域）")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setStyleSheet("""
                QLabel { background-color: #f5f5f5; border: 1px solid #ddd;
                         padding: 20px; border-radius: 4px; }
            """)
            layout.addWidget(placeholder)

            return widget

        def _populate_data(self):
            """填充数据"""
            # 基本信息
            basic_fields = [
                ("company_name", "企业名称", self.parsed_data.get("company_name", "")),
                ("credit_code", "信用代码", self.parsed_data.get("credit_code", "")),
                ("monitoring_date", "监测日期", self.parsed_data.get("monitoring_date", "")),
                ("monitoring_purpose", "监测目的", self.parsed_data.get("monitoring_purpose", "")),
                ("monitoring_agency", "监测机构", self.parsed_data.get("monitoring_agency", "")),
                ("agency_qualification", "资质编号", self.parsed_data.get("agency_qualification", "")),
            ]

            self.basic_table.setRowCount(len(basic_fields))
            for row, (key, label, value) in enumerate(basic_fields):
                self.basic_table.setItem(row, 0, QTableWidgetItem(label))
                self.basic_table.item(row, 0).setFlags(Qt.ItemFlag.ItemIsEnabled)

                self.basic_table.setItem(row, 1, QTableWidgetItem(str(value) if value else ""))
                self.basic_table.item(row, 1).setFlags(Qt.ItemFlag.ItemIsEnabled)

                correction_item = QTableWidgetItem("")
                correction_item.setToolTip("如需修正，请在此输入")
                self.basic_table.setItem(row, 2, correction_item)

                # 记录字段
                self.review_fields.append(ReviewField(
                    key=key,
                    label=label,
                    original_value=str(value) if value else ""
                ))

            # 监测点位
            monitoring_points = self.parsed_data.get("monitoring_points", [])
            self.points_table.setRowCount(0)

            for point in monitoring_points:
                point_id = point.get("point_id", "")
                point_name = point.get("point_name", "")
                parameters = point.get("parameters", [])

                for param in parameters:
                    row = self.points_table.rowCount()
                    self.points_table.insertRow(row)

                    self.points_table.setItem(row, 0, QTableWidgetItem(point_id))
                    self.points_table.item(row, 0).setFlags(Qt.ItemFlag.ItemIsEnabled)

                    self.points_table.setItem(row, 1, QTableWidgetItem(point_name))
                    self.points_table.item(row, 1).setFlags(Qt.ItemFlag.ItemIsEnabled)

                    self.points_table.setItem(row, 2, QTableWidgetItem(param.get("pollutant", "")))
                    self.points_table.item(row, 2).setFlags(Qt.ItemFlag.ItemIsEnabled)

                    conc = param.get("concentration", "")
                    unit = param.get("unit", "")
                    conc_str = f"{conc} {unit}" if conc else ""
                    self.points_table.setItem(row, 3, QTableWidgetItem(conc_str))
                    self.points_table.item(row, 3).setFlags(Qt.ItemFlag.ItemIsEnabled)

                    std = param.get("standard", "")
                    self.points_table.setItem(row, 4, QTableWidgetItem(str(std) if std else ""))
                    self.points_table.item(row, 4).setFlags(Qt.ItemFlag.ItemIsEnabled)

                    is_compliant = param.get("is_compliant", True)
                    status_text = "✅ 达标" if is_compliant else "❌ 超标"
                    status_item = QTableWidgetItem(status_text)
                    status_item.setBackground(
                        Qt.GlobalColor.green if is_compliant else Qt.GlobalColor.red
                    )
                    self.points_table.setItem(row, 5, status_item)
                    self.points_table.item(row, 5).setFlags(Qt.ItemFlag.ItemIsEnabled)

        def _on_item_changed(self, item: QTableWidgetItem):
            """表格项被修改"""
            if item.column() == 2:  # 修正列
                row = item.row()
                if row < len(self.review_fields):
                    field = self.review_fields[row]
                    field.corrected_value = item.text()
                    field.is_modified = bool(item.text().strip())

        def _on_confirm(self):
            """确认入库"""
            reply = QMessageBox.question(
                self,
                "确认入库",
                "确认接受当前数据并入库？\n\n（修正数据将不会被保存）",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                result = ReviewResult(
                    accepted=True,
                    report_id=self.parsed_data.get("report_id", ""),
                    corrections=[],
                    feedback_to_ai=False
                )
                self.accepted.emit(result.to_dict())
                self.close()

        def _on_correct(self):
            """保存修正"""
            # 收集修正数据
            corrections = []

            for field in self.review_fields:
                if field.is_modified and field.corrected_value:
                    corrections.append({
                        "key": field.key,
                        "label": field.label,
                        "original_value": field.original_value,
                        "corrected_value": field.corrected_value
                    })

            if not corrections:
                QMessageBox.information(
                    self,
                    "无修正",
                    "您没有修改任何数据",
                    QMessageBox.StandardButton.Ok
                )
                return

            reply = QMessageBox.question(
                self,
                "保存修正",
                f"确定保存 {len(corrections)} 项修正数据？\n\n"
                f"修正数据将反馈给AI，持续优化解析准确性。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                result = ReviewResult(
                    accepted=True,
                    report_id=self.parsed_data.get("report_id", ""),
                    corrections=corrections,
                    feedback_to_ai=True
                )
                self.corrected.emit(result.to_dict())
                self.close()

        def _on_cancel(self):
            """取消"""
            reply = QMessageBox.question(
                self,
                "取消",
                "确定取消吗？解析结果将不会保存。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.cancelled.emit()
                self.close()


# ==================== 独立函数 ====================

def show_review_dialog(
    parsed_data: Dict[str, Any],
    pdf_path: str,
    parent=None
) -> Optional[ReviewResult]:
    """
    显示校验对话框

    Args:
        parsed_data: AI解析结果
        pdf_path: PDF文件路径
        parent: 父窗口

    Returns:
        ReviewResult 或 None（如果取消）
    """
    if not PYQT_AVAILABLE:
        logger.warning("PyQt6 not available, cannot show review dialog")
        return None

    dialog = PDFReviewPanel(parsed_data, pdf_path, parent)

    result_holder = {"result": None}

    def on_accepted(data):
        result_holder["result"] = ReviewResult(
            accepted=True,
            report_id=data.get("report_id", ""),
            corrections=data.get("corrections", []),
            feedback_to_ai=data.get("feedback_to_ai", True)
        )

    def on_cancelled():
        result_holder["result"] = ReviewResult(
            accepted=False,
            report_id="",
            corrections=[]
        )

    dialog.accepted.connect(on_accepted)
    dialog.cancelled.connect(on_cancelled)

    dialog.exec()

    return result_holder["result"]