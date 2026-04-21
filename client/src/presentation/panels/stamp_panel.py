"""
印章生成面板 - Stamp Panel
公司印章生成工具 UI

功能：
- 生成公章/合同章/发票章
- 支持带编号和不带编号
- PDF 骑缝章一键盖章
- 实时预览
- 导出 PNG/PDF

依赖：
- core.company_stamp.CompanyStampGenerator
- core.pdf_stamp.PDFStampTool
"""

from typing import Optional, TYPE_CHECKING
import os

from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QSpinBox,
    QCheckBox, QGroupBox, QScrollArea, QFileDialog,
    QMessageBox, QProgressBar, QTextEdit, QFrame
)
from PyQt6.QtGui import QPixmap, QImage, QFont

# 印章生成器
from core.company_stamp import (
    CompanyStampGenerator, StampConfig, StampType,
    NumberPosition, generate_stamp
)
from core.pdf_stamp import PDFStampTool, PageStampConfig

if TYPE_CHECKING:
    from PIL import Image


class StampPanel(QWidget):
    """
    印章生成面板

    功能：
    1. 印章参数配置（公司名称、类型、编号等）
    2. 实时印章预览
    3. 导出 PNG 图像
    4. PDF 骑缝章盖章
    """

    stamp_generated = pyqtSignal(str)  # 印章生成完成，参数为图像路径

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stamp_generator: Optional[CompanyStampGenerator] = None
        self._current_stamp_img: Optional['Image.Image'] = None
        self._current_stamp_path: Optional[str] = None
        self._pdf_tool: Optional[PDFStampTool] = None
        self._current_pdf_path: Optional[str] = None

        self._build_ui()
        self._connect_signals()

        # 初始生成一个预览
        self._update_preview()

    def _build_ui(self):
        """构建 UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(16, 16, 16, 16)

        # 标题
        title = QLabel("🔐 公司印章生成器")
        title.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #60a5fa;
            padding: 4px 0;
        """)
        main_layout.addWidget(title)

        # 主体区域：左侧配置 + 右侧预览
        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)

        # 左侧：配置区域
        config_area = self._build_config_area()
        content_layout.addWidget(config_area, 1)

        # 右侧：预览区域
        preview_area = self._build_preview_area()
        content_layout.addWidget(preview_area, 1)

        main_layout.addLayout(content_layout)

        # 底部：导出按钮
        export_layout = self._build_export_area()
        main_layout.addLayout(export_layout)

        # PDF 盖章区域
        pdf_area = self._build_pdf_stamp_area()
        main_layout.addWidget(pdf_area)

        main_layout.addStretch()

    def _build_config_area(self) -> QWidget:
        """构建配置区域"""
        group = QGroupBox("印章配置")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #3a3a5e;
                border-radius: 8px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
                color: #9090c0;
            }
        """)

        layout = QGridLayout(group)
        layout.setSpacing(10)

        row = 0

        # 公司名称
        layout.addWidget(QLabel("公司名称:"), row, 0)
        self.company_name_input = QLineEdit()
        self.company_name_input.setPlaceholderText("例如：上海九泽环保科技有限公司")
        self.company_name_input.setMaxLength(20)
        self.company_name_input.setStyleSheet("""
            QLineEdit {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 8px 10px;
                color: #e0e0ff;
            }
        """)
        self.company_name_input.textChanged.connect(self._on_config_changed)
        layout.addWidget(self.company_name_input, row, 1, 1, 2)
        row += 1

        # 印章类型
        layout.addWidget(QLabel("印章类型:"), row, 0)
        self.stamp_type_combo = QComboBox()
        self.stamp_type_combo.addItems(["公章 (圆形)", "合同章 (椭圆)", "发票章 (方形)"])
        self.stamp_type_combo.setCurrentIndex(0)
        self.stamp_type_combo.setStyleSheet("""
            QComboBox {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 8px 10px;
                color: #e0e0ff;
            }
        """)
        self.stamp_type_combo.currentIndexChanged.connect(self._on_config_changed)
        layout.addWidget(self.stamp_type_combo, row, 1, 1, 2)
        row += 1

        # 印章编号
        layout.addWidget(QLabel("印章编号:"), row, 0)
        self.stamp_number_input = QLineEdit()
        self.stamp_number_input.setPlaceholderText("可不填，如：11010100001234")
        self.stamp_number_input.setMaxLength(15)
        self.stamp_number_input.setStyleSheet("""
            QLineEdit {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 8px 10px;
                color: #e0e0ff;
            }
        """)
        self.stamp_number_input.textChanged.connect(self._on_config_changed)
        layout.addWidget(self.stamp_number_input, row, 1, 1, 2)
        row += 1

        # 编号位置
        layout.addWidget(QLabel("编号位置:"), row, 0)
        self.number_pos_combo = QComboBox()
        self.number_pos_combo.addItems(["底部", "右侧"])
        self.number_pos_combo.setCurrentIndex(0)
        self.number_pos_combo.setStyleSheet("""
            QComboBox {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 8px 10px;
                color: #e0e0ff;
            }
        """)
        self.number_pos_combo.currentIndexChanged.connect(self._on_config_changed)
        layout.addWidget(self.number_pos_combo, row, 1, 1, 2)
        row += 1

        # 分辨率
        layout.addWidget(QLabel("分辨率 DPI:"), row, 0)
        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(150, 600)
        self.dpi_spin.setValue(300)
        self.dpi_spin.setSuffix(" DPI")
        self.dpi_spin.setStyleSheet("""
            QSpinBox {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 8px 10px;
                color: #e0e0ff;
            }
        """)
        self.dpi_spin.valueChanged.connect(self._on_config_changed)
        layout.addWidget(self.dpi_spin, row, 1, 1, 2)

        return group

    def _build_preview_area(self) -> QWidget:
        """构建预览区域"""
        group = QGroupBox("印章预览")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #3a3a5e;
                border-radius: 8px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
                color: #9090c0;
            }
        """)

        layout = QVBoxLayout(group)

        # 预览标签
        self.preview_label = QLabel()
        self.preview_label.setMinimumSize(200, 200)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("""
            background: #f5f5f5;
            border: 1px dashed #cccccc;
            border-radius: 8px;
            color: #888888;
            padding: 20px;
        """)
        self.preview_label.setText("正在生成预览...")
        layout.addWidget(self.preview_label)

        # 预览尺寸标签
        self.preview_size_label = QLabel("尺寸: --")
        self.preview_size_label.setStyleSheet("color: #808080; font-size: 11px;")
        self.preview_size_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.preview_size_label)

        return group

    def _build_export_area(self) -> QHBoxLayout:
        """构建导出按钮区域"""
        layout = QHBoxLayout()
        layout.setSpacing(10)

        self.export_png_btn = QPushButton("📥 导出 PNG")
        self.export_png_btn.setStyleSheet("""
            QPushButton {
                background: #2563eb;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #1d4ed8;
            }
            QPushButton:disabled {
                background: #4a4a6a;
                color: #808080;
            }
        """)
        self.export_png_btn.clicked.connect(self._export_png)

        self.regenerate_btn = QPushButton("🔄 重新生成")
        self.regenerate_btn.setStyleSheet("""
            QPushButton {
                background: #3a3a5e;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                color: #e0e0ff;
            }
            QPushButton:hover {
                background: #4a4a7e;
            }
        """)
        self.regenerate_btn.clicked.connect(self._update_preview)

        layout.addWidget(self.export_png_btn)
        layout.addWidget(self.regenerate_btn)
        layout.addStretch()

        return layout

    def _build_pdf_stamp_area(self) -> QWidget:
        """构建 PDF 盖章区域"""
        group = QGroupBox("PDF 骑缝章")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #3a3a5e;
                border-radius: 8px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
                color: #9090c0;
            }
        """)

        layout = QGridLayout(group)
        layout.setSpacing(10)

        row = 0

        # 选择 PDF 文件
        layout.addWidget(QLabel("选择 PDF:"), row, 0)
        self.pdf_path_input = QLineEdit()
        self.pdf_path_input.setPlaceholderText("请选择要盖章的 PDF 文件...")
        self.pdf_path_input.setReadOnly(True)
        self.pdf_path_input.setStyleSheet("""
            QLineEdit {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 8px 10px;
                color: #e0e0ff;
            }
        """)
        layout.addWidget(self.pdf_path_input, row, 1)

        self.browse_pdf_btn = QPushButton("📁 浏览")
        self.browse_pdf_btn.setStyleSheet("""
            QPushButton {
                background: #3a3a5e;
                border: none;
                border-radius: 4px;
                padding: 8px 12px;
                color: #e0e0ff;
            }
            QPushButton:hover {
                background: #4a4a7e;
            }
        """)
        self.browse_pdf_btn.clicked.connect(self._browse_pdf)
        layout.addWidget(self.browse_pdf_btn, row, 2)
        row += 1

        # 页码范围
        layout.addWidget(QLabel("页码范围:"), row, 0)
        page_range_layout = QHBoxLayout()
        self.start_page_spin = QSpinBox()
        self.start_page_spin.setPrefix("从 ")
        self.start_page_spin.setRange(1, 9999)
        self.start_page_spin.setValue(1)
        self.start_page_spin.setStyleSheet("""
            QSpinBox {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 6px 8px;
                color: #e0e0ff;
            }
        """)

        self.end_page_spin = QSpinBox()
        self.end_page_spin.setPrefix("到 ")
        self.end_page_spin.setRange(1, 9999)
        self.end_page_spin.setValue(1)
        self.end_page_spin.setStyleSheet("""
            QSpinBox {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 6px 8px;
                color: #e0e0ff;
            }
        """)

        self.page_count_label = QLabel("(共 0 页)")
        self.page_count_label.setStyleSheet("color: #808080; font-size: 11px;")

        page_range_layout.addWidget(self.start_page_spin)
        page_range_layout.addWidget(self.end_page_spin)
        page_range_layout.addWidget(self.page_count_label)
        page_range_layout.addStretch()
        layout.addLayout(page_range_layout, row, 1, 1, 2)
        row += 1

        # 盖章位置
        layout.addWidget(QLabel("盖章位置:"), row, 0)
        pos_layout = QHBoxLayout()
        self.position_combo = QComboBox()
        self.position_combo.addItems(["右侧骑缝章", "左侧骑缝章"])
        self.position_combo.setCurrentIndex(0)
        self.position_combo.setStyleSheet("""
            QComboBox {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 6px 10px;
                color: #e0e0ff;
            }
        """)
        pos_layout.addWidget(self.position_combo)

        self.opacity_slider_label = QLabel("透明度: 70%")
        self.opacity_slider_label.setStyleSheet("color: #9090c0; font-size: 11px;")
        pos_layout.addWidget(self.opacity_slider_label)

        self.opacity_slider = QSpinBox()
        self.opacity_slider.setRange(30, 100)
        self.opacity_slider.setValue(70)
        self.opacity_slider.setSuffix("%")
        self.opacity_slider.setStyleSheet("""
            QSpinBox {
                background: #252538;
                border: 1px solid #3a3a5e;
                border-radius: 4px;
                padding: 6px 8px;
                color: #e0e0ff;
            }
        """)
        self.opacity_slider.valueChanged.connect(
            lambda v: self.opacity_slider_label.setText(f"透明度: {v}%")
        )
        pos_layout.addWidget(self.opacity_slider)
        pos_layout.addStretch()
        layout.addLayout(pos_layout, row, 1, 1, 2)
        row += 1

        # 预览 & 盖章按钮
        btn_layout = QHBoxLayout()

        self.preview_pdf_btn = QPushButton("👁️ 预览效果")
        self.preview_pdf_btn.setStyleSheet("""
            QPushButton {
                background: #3a3a5e;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                color: #e0e0ff;
            }
            QPushButton:hover {
                background: #4a4a7e;
            }
            QPushButton:disabled {
                background: #2a2a4a;
                color: #606080;
            }
        """)
        self.preview_pdf_btn.clicked.connect(self._preview_pdf_stamp)
        self.preview_pdf_btn.setEnabled(False)
        btn_layout.addWidget(self.preview_pdf_btn)

        self.apply_stamp_btn = QPushButton("✅ 应用骑缝章")
        self.apply_stamp_btn.setStyleSheet("""
            QPushButton {
                background: #059669;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #047857;
            }
            QPushButton:disabled {
                background: #4a4a6a;
                color: #808080;
            }
        """)
        self.apply_stamp_btn.clicked.connect(self._apply_rolling_stamp)
        self.apply_stamp_btn.setEnabled(False)
        btn_layout.addWidget(self.apply_stamp_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout, row, 0, 1, 3)

        return group

    def _connect_signals(self):
        """连接信号"""
        self.start_page_spin.valueChanged.connect(self._on_page_range_changed)
        self.end_page_spin.valueChanged.connect(self._on_page_range_changed)

    def _get_stamp_type(self) -> StampType:
        """获取印章类型"""
        types = ["official", "contract", "invoice"]
        return types[self.stamp_type_combo.currentIndex()]

    def _get_number_position(self) -> NumberPosition:
        """获取编号位置"""
        positions = ["bottom", "right"]
        return positions[self.number_pos_combo.currentIndex()]

    def _get_stamp_config(self) -> StampConfig:
        """获取印章配置"""
        number = self.stamp_number_input.text().strip() or None
        return StampConfig(
            company_name=self.company_name_input.text().strip() or "公司名称",
            stamp_type=self._get_stamp_type(),
            number=number,
            number_position=self._get_number_position(),
            dpi=self.dpi_spin.value()
        )

    def _on_config_changed(self):
        """配置改变，更新预览"""
        self._update_preview()

    def _update_preview(self):
        """更新印章预览"""
        try:
            config = self._get_stamp_config()

            # 生成印章
            generator = CompanyStampGenerator(config)
            self._current_stamp_img = generator.generate()

            # 显示预览
            self._display_preview(self._current_stamp_img)

            # 更新尺寸标签
            w, h = self._current_stamp_img.size
            dpi = config.dpi
            real_w = w * 25.4 / dpi
            real_h = h * 25.4 / dpi
            self.preview_size_label.setText(f"尺寸: {real_w:.1f} x {real_h:.1f} mm (DPI: {dpi})")

            # 启用导出按钮
            self.export_png_btn.setEnabled(True)

        except Exception as e:
            self.preview_label.setText(f"生成失败:\n{str(e)}")
            self.export_png_btn.setEnabled(False)

    def _display_preview(self, img: 'Image.Image'):
        """显示印章预览"""
        # 转换为 Qt 图像
        img_rgb = img.convert('RGB')
        img_bytes = img_rgb.tobytes('raw', 'RGB')

        width, height = img.size
        qimage = QImage(img_bytes, width, height, width * 3, QImage.Format.Format_RGB888)

        # 缩放以适应预览区域
        pixmap = QPixmap.fromImage(qimage)
        scaled_pixmap = pixmap.scaled(
            200, 200,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        self.preview_label.setPixmap(scaled_pixmap)
        self.preview_label.setText("")  # 清除占位文字

    def _export_png(self):
        """导出 PNG"""
        if self._current_stamp_img is None:
            QMessageBox.warning(self, "提示", "请先生成印章")
            return

        # 获取保存路径
        default_name = f"印章_{self.company_name_input.text().strip() or '默认'}.png"
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "保存印章图像",
            default_name,
            "PNG Image (*.png)"
        )

        if not filepath:
            return

        try:
            # 保存
            config = self._get_stamp_config()
            generator = CompanyStampGenerator(config)
            generator.save(filepath)

            self._current_stamp_path = filepath
            self.stamp_generated.emit(filepath)

            QMessageBox.information(self, "成功", f"印章已保存到:\n{filepath}")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败:\n{str(e)}")

    def _browse_pdf(self):
        """浏览 PDF 文件"""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "选择 PDF 文件",
            "",
            "PDF Files (*.pdf)"
        )

        if not filepath:
            return

        self._current_pdf_path = filepath
        self.pdf_path_input.setText(filepath)

        # 获取页数
        try:
            page_count = PDFStampTool.get_pdf_page_count(filepath)
            self.start_page_spin.setRange(1, page_count)
            self.end_page_spin.setRange(1, page_count)
            self.end_page_spin.setValue(page_count)
            self.page_count_label.setText(f"(共 {page_count} 页)")

            self.preview_pdf_btn.setEnabled(True)
            self.apply_stamp_btn.setEnabled(True)

        except Exception as e:
            QMessageBox.warning(self, "错误", f"无法读取 PDF:\n{str(e)}")
            self._current_pdf_path = None
            self.pdf_path_input.clear()

    def _on_page_range_changed(self):
        """页码范围改变"""
        start = self.start_page_spin.value()
        end = self.end_page_spin.value()

        if end < start:
            self.end_page_spin.setValue(start)

    def _preview_pdf_stamp(self):
        """预览 PDF 盖章效果"""
        if not self._current_pdf_path or self._current_stamp_img is None:
            QMessageBox.warning(self, "提示", "请先选择 PDF 文件并生成印章")
            return

        try:
            # 获取 PDF 工具
            pdf_tool = get_pdf_stamp_tool()

            # 加载印章
            pdf_tool.load_stamp_from_image(self._current_stamp_img)

            # 渲染页面预览
            page_num = self.start_page_spin.value() - 1  # 转为 0-based
            preview_img = pdf_tool.preview_stamp_position(
                self._current_pdf_path,
                page_num=page_num,
                config=PageStampConfig(
                    stamp_img=self._current_stamp_img,
                    position="right" if self.position_combo.currentIndex() == 0 else "left",
                    opacity=self.opacity_slider.value() / 100.0
                )
            )

            # 显示预览
            self._show_pdf_preview_window(preview_img)

        except Exception as e:
            QMessageBox.critical(self, "错误", f"预览失败:\n{str(e)}")

    def _show_pdf_preview_window(self, img: 'Image.Image'):
        """显示 PDF 预览窗口"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton

        dialog = QDialog(self)
        dialog.setWindowTitle("PDF 盖章预览")
        dialog.setMinimumSize(600, 800)

        layout = QVBoxLayout(dialog)

        # 图像预览
        img_rgb = img.convert('RGB')
        img_bytes = img_rgb.tobytes('raw', 'RGB')
        width, height = img.size
        qimage = QImage(img_bytes, width, height, width * 3, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimage)

        label = QLabel()
        label.setPixmap(pixmap.scaled(580, 750, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        layout.addWidget(label)

        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.close)
        close_btn.setStyleSheet("""
            QPushButton {
                background: #3a3a5e;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                color: #e0e0ff;
            }
        """)
        layout.addWidget(close_btn)

        dialog.exec()

    def _apply_rolling_stamp(self):
        """应用骑缝章"""
        if not self._current_pdf_path or self._current_stamp_img is None:
            QMessageBox.warning(self, "提示", "请先选择 PDF 文件并生成印章")
            return

        # 获取保存路径
        default_name = self._current_pdf_path.replace('.pdf', '_已盖章.pdf')
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存盖章后的 PDF",
            default_name,
            "PDF Files (*.pdf)"
        )

        if not output_path:
            return

        try:
            # 获取 PDF 工具
            pdf_tool = get_pdf_stamp_tool()

            # 应用骑缝章
            position = "right" if self.position_combo.currentIndex() == 0 else "left"

            pdf_tool.apply_rolling_stamp(
                pdf_path=self._current_pdf_path,
                output_path=output_path,
                stamp_img=self._current_stamp_img,
                position=position,
                opacity=self.opacity_slider.value() / 100.0
            )

            QMessageBox.information(
                self, "成功",
                f"骑缝章已应用到 PDF:\n{output_path}"
            )

            # 打开文件夹
            self._open_file_location(output_path)

        except Exception as e:
            QMessageBox.critical(self, "错误", f"盖章失败:\n{str(e)}")

    def _open_file_location(self, filepath: str):
        """打开文件所在文件夹"""
        import subprocess
        folder = os.path.dirname(filepath)
        try:
            if os.name == 'nt':  # Windows
                os.startfile(folder)
            elif os.name == 'posix':  # macOS / Linux
                subprocess.run(['open', folder] if os.uname().sysname == 'Darwin' else ['xdg-open', folder])
        except:
            pass


# 全局单例
_stamp_panel_instance: Optional[StampPanel] = None


def get_stamp_panel() -> StampPanel:
    """获取印章面板单例"""
    global _stamp_panel_instance
    if _stamp_panel_instance is None:
        _stamp_panel_instance = StampPanel()
    return _stamp_panel_instance