"""
Air Prediction Panel - 大气预测UI面板

提供完整的大气预测功能界面：
- 项目配置
- 工具部署状态
- 参数设置
- 执行进度
- 结果可视化

使用示例：
```python
from ui.air_prediction_panel import AirPredictionPanel

# 创建面板
panel = AirPredictionPanel(parent=self)

# 显示
self.addDockWidget(Qt.RightDockWidgetArea, panel)
```
"""

from typing import Optional, Dict, Any
from datetime import datetime

# PyQt6 导入
try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
        QLabel, QPushButton, QTextEdit, QProgressBar,
        QTabWidget, QGroupBox, QFormLayout, QLineEdit,
        QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox,
        QTableWidget, QTableWidgetItem, QHeaderView,
        QProgressDialog, QMessageBox, QFileDialog,
        QStatusBar, QDockWidget, QScrollArea,
        QFrame, QSizePolicy, QSpacerItem, QListWidget,
        QListWidgetItem, QTreeWidget, QTreeWidgetItem
    )
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, pyqtSlot
    from PyQt6.QtGui import QIcon, QFont, QAction
    HAS_PYQT = True
except ImportError:
    HAS_PYQT = False
    # 创建一个简单的 stub
    class QWidget:
        def __init__(self, *args, **kwargs): pass
        def setLayout(self, layout): pass
        def show(self): pass
    class QVBoxLayout:
        def __init__(self): pass
        def addWidget(self, w): pass
        def addLayout(self, l): pass
    class QLabel:
        def __init__(self, text=""): self.text = text
        def setText(self, text): self.text = text
    class QPushButton:
        def __init__(self, text=""): self.text = text
        def setText(self, text): self.text = text
        def clicked(self): pass
        def setEnabled(self, b): pass


# 大气预测核心
try:
    from core.seamless_tool_integration import (
        SeamlessIntegrationManager, ProjectData, SourceParams,
        MeteorologyData, ReceptorGrid, ScaleType,
        ExecutionStep, ExecutionStatus, PredictionResult
    )
    from core.seamless_tool_integration.result_visualizer import ResultVisualizer
    HAS_CORE = True
except ImportError as e:
    HAS_CORE = False
    print(f"Warning: core module not available: {e}")


class LogDisplay(QTextEdit if HAS_PYQT else object):
    """日志显示控件"""

    def __init__(self, parent=None):
        if HAS_PYQT:
            super().__init__(parent)
            self.setReadOnly(True)
            self.setMaximumHeight(150)
            self.setStyleSheet("""
                QTextEdit {
                    background-color: #1e1e1e;
                    color: #d4d4d4;
                    font-family: 'Consolas', 'Courier New', monospace;
                    font-size: 11px;
                }
            """)

    def append_log(self, message: str, level: str = "INFO"):
        """添加日志"""
        if not HAS_PYQT:
            print(f"[{level}] {message}")
            return

        timestamp = datetime.now().strftime("%H:%M:%S")
        color_map = {
            "INFO": "#4fc3f7",
            "SUCCESS": "#81c784",
            "WARNING": "#ffb74d",
            "ERROR": "#e57373"
        }
        color = color_map.get(level, "#d4d4d4")
        self.append(f'<span style="color: #888;">[{timestamp}]</span> <span style="color: {color};">[{level}]</span> {message}')


class ConfigFormWidget(QFrame if HAS_PYQT else object):
    """配置表单控件"""

    def __init__(self, parent=None):
        if HAS_PYQT:
            super().__init__(parent)
            self._setup_ui()
        self._project_data = None

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        # 基本信息
        basic_group = QGroupBox("📋 基本信息")
        basic_layout = QFormLayout()

        self.project_name_edit = QLineEdit()
        self.project_name_edit.setPlaceholderText("输入项目名称")
        basic_layout.addRow("项目名称:", self.project_name_edit)

        self.location_edit = QLineEdit()
        self.location_edit.setPlaceholderText("如: 南京化学工业园")
        basic_layout.addRow("项目位置:", self.location_edit)

        # 坐标
        coord_layout = QHBoxLayout()
        self.latitude_spin = QDoubleSpinBox()
        self.latitude_spin.setRange(-90, 90)
        self.latitude_spin.setDecimals(6)
        self.latitude_spin.setValue(32.04)
        self.latitude_spin.setSuffix(" °N")

        self.longitude_spin = QDoubleSpinBox()
        self.longitude_spin.setRange(-180, 180)
        self.longitude_spin.setDecimals(6)
        self.longitude_spin.setValue(118.78)
        self.longitude_spin.setSuffix(" °E")

        coord_layout.addWidget(QLabel("纬度:"))
        coord_layout.addWidget(self.latitude_spin)
        coord_layout.addWidget(QLabel("经度:"))
        coord_layout.addWidget(self.longitude_spin)

        basic_layout.addRow("坐标:", coord_layout)
        basic_group.setLayout(basic_layout)
        layout.addWidget(basic_group)

        # 评价尺度
        scale_group = QGroupBox("📐 评价尺度")
        scale_layout = QFormLayout()

        self.scale_combo = QComboBox()
        self.scale_combo.addItems(["局地尺度 (≤50km)", "区域尺度 (>50km)"])
        scale_layout.addRow("评价范围:", self.scale_combo)

        self.terrain_combo = QComboBox()
        self.terrain_combo.addItems(["平坦地形", "复杂地形"])
        scale_layout.addRow("地形类型:", self.terrain_combo)

        self.landuse_combo = QComboBox()
        self.landuse_combo.addItems(["农村", "城市", "郊区"])
        scale_layout.addRow("土地利用:", self.landuse_combo)

        scale_group.setLayout(scale_layout)
        layout.addWidget(scale_group)

        # 预测因子
        pollutant_group = QGroupBox("🧪 预测因子")
        pollutant_layout = QVBoxLayout()

        self.pollutant_checkboxes = {}
        pollutants = ["SO2", "NO2", "NOx", "PM10", "PM2.5", "VOCs", "CO", "O3"]
        for p in pollutants:
            cb = QCheckBox(p)
            if p in ["SO2", "NO2", "PM10", "PM2.5"]:
                cb.setChecked(True)
            self.pollutant_checkboxes[p] = cb
            pollutant_layout.addWidget(cb)

        pollutant_group.setLayout(pollutant_layout)
        layout.addWidget(pollutant_group)

        # 气象数据
        meteo_group = QGroupBox("🌤️ 气象数据")
        meteo_layout = QFormLayout()

        self.meteo_source_combo = QComboBox()
        self.meteo_source_combo.addItems([
            "自动获取（推荐）",
            "手动上传气象文件",
            "使用默认数据"
        ])
        meteo_layout.addRow("数据来源:", self.meteo_source_combo)

        self.station_id_edit = QLineEdit()
        self.station_id_edit.setPlaceholderText("气象站点ID，如: 58362（南京）")
        meteo_layout.addRow("站点ID:", self.station_id_edit)

        self.data_year_spin = QSpinBox()
        self.data_year_spin.setRange(2020, 2030)
        self.data_year_spin.setValue(2024)
        meteo_layout.addRow("数据年份:", self.data_year_spin)

        meteo_group.setLayout(meteo_layout)
        layout.addWidget(meteo_group)

        layout.addStretch()

    def get_project_data(self) -> Optional[ProjectData]:
        """获取项目数据"""
        if not HAS_CORE:
            return None

        # 收集选中的污染物
        selected_pollutants = [
            name for name, cb in self.pollutant_checkboxes.items()
            if cb.isChecked()
        ]

        # 创建项目数据
        project_data = ProjectData(
            project_name=self.project_name_edit.text() or "未命名项目",
            latitude=self.latitude_spin.value(),
            longitude=self.longitude_spin.value(),
            location_name=self.location_edit.text(),
            scale=ScaleType.LOCAL if self.scale_combo.currentIndex() == 0 else ScaleType.REGIONAL,
            pollutants=selected_pollutants,
            land_use=self.landuse_combo.currentText(),
            terrain_type="FLAT" if self.terrain_combo.currentIndex() == 0 else "COMPLEX"
        )

        # 气象数据
        project_data.meteorology = MeteorologyData(
            station_id=self.station_id_edit.text() or "58362",
            data_year=self.data_year_spin.value()
        )

        # 默认受体网格
        project_data.receptor_grid = ReceptorGrid(
            center_x=0,
            center_y=0,
            x_min=-5000,
            x_max=5000,
            y_min=-5000,
            y_max=5000,
            x_step=100,
            y_step=100
        )

        # 添加一个示例污染源
        project_data.emission_sources = [
            SourceParams(
                source_id="S1",
                source_name="主排放口",
                latitude=project_data.latitude,
                longitude=project_data.longitude,
                emission_rate=1.0,
                stack_height=30.0,
                stack_diameter=1.0,
                exit_velocity=5.0,
                exit_temperature=350.0
            )
        ]

        self._project_data = project_data
        return project_data

    def load_from_result(self, result: PredictionResult):
        """从结果加载配置"""
        if not HAS_PYQT or not result:
            return


class ProgressDisplay(QWidget if HAS_PYQT else object):
    """进度显示控件"""

    def __init__(self, parent=None):
        if HAS_PYQT:
            super().__init__(parent)
            self._setup_ui()
        self._current_step = None

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        # 步骤列表
        self.step_list = QListWidget()
        self.step_list.setStyleSheet("""
            QListWidget {
                border: none;
                background-color: transparent;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 4px;
                margin: 2px 0;
            }
            QListWidget::item:selected {
                background-color: transparent;
            }
        """)
        layout.addWidget(QLabel("执行步骤:"))
        layout.addWidget(self.step_list)

        # 进度条
        self.overall_progress = QProgressBar()
        self.overall_progress.setRange(0, 100)
        self.overall_progress.setValue(0)
        layout.addWidget(QLabel("总体进度:"))
        layout.addWidget(self.overall_progress)

        # 当前状态
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("""
            QLabel {
                padding: 10px;
                background-color: #2d2d30;
                border-radius: 4px;
                color: #d4d4d4;
            }
        """)
        layout.addWidget(self.status_label)

    def update_step(self, step: ExecutionStep):
        """更新步骤"""
        if not HAS_PYQT:
            print(f"Step: {step.name} - {step.progress}%")
            return

        self._current_step = step

        # 查找或添加步骤
        found_items = self.step_list.findItems(step.name, Qt.MatchExactly)
        if found_items:
            item = found_items[0]
        else:
            item = QListWidgetItem(step.name)
            self.step_list.addItem(item)

        # 更新状态颜色
        color_map = {
            ExecutionStatus.PENDING: "#666",
            ExecutionStatus.RUNNING: "#4fc3f7",
            ExecutionStatus.COMPLETED: "#81c784",
            ExecutionStatus.FAILED: "#e57373"
        }
        color = color_map.get(step.status, "#666")

        # 更新进度条
        self.overall_progress.setValue(int(step.progress))

        # 更新状态标签
        status_text = f"<b>{step.name}</b><br/>"
        status_text += f"状态: {step.status.value}<br/>"
        if step.message:
            status_text += f"消息: {step.message}"
        self.status_label.setText(status_text)

        # 如果完成，标记为绿色
        if step.status == ExecutionStatus.COMPLETED:
            item.setBackground(Qt.GlobalColor.darkGreen)
            item.setForeground(Qt.GlobalColor.white)


class ResultDisplay(QWidget if HAS_PYQT else object):
    """结果显示控件"""

    def __init__(self, parent=None):
        if HAS_PYQT:
            super().__init__(parent)
            self._setup_ui()
        self._result = None

    def _setup_ui(self):
        """设置UI"""
        layout = QVBoxLayout(self)

        # 标签页
        self.tabs = QTabWidget()

        # 摘要页
        self.summary_tab = QWidget()
        summary_layout = QVBoxLayout(self.summary_tab)

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet("""
            QLabel {
                padding: 15px;
                background-color: #252526;
                border-radius: 4px;
            }
        """)
        summary_layout.addWidget(self.summary_label)

        # 数据表格页
        self.table_tab = QWidget()
        table_layout = QVBoxLayout(self.table_tab)

        self.data_table = QTableWidget()
        self.data_table.setColumnCount(5)
        self.data_table.setHorizontalHeaderLabels(['X(m)', 'Y(m)', '浓度(μg/m³)', '经度', '纬度'])
        self.data_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table_layout.addWidget(self.data_table)

        # 图表页
        self.chart_tab = QWidget()
        chart_layout = QVBoxLayout(self.chart_tab)

        self.chart_label = QLabel("图表将在这里显示...")
        chart_layout.addWidget(self.chart_label)

        self.tabs.addTab(self.summary_tab, "📊 摘要")
        self.tabs.addTab(self.table_tab, "📋 数据表")
        self.tabs.addTab(self.chart_tab, "📈 图表")

        layout.addWidget(self.tabs)

        # 导出按钮
        export_layout = QHBoxLayout()
        self.export_btn = QPushButton("📥 导出报告")
        self.export_btn.clicked.connect(self._on_export)
        export_layout.addWidget(self.export_btn)

        self.export_csv_btn = QPushButton("📊 导出CSV")
        self.export_csv_btn.clicked.connect(self._on_export_csv)
        export_layout.addWidget(self.export_csv_btn)

        layout.addLayout(export_layout)

    def display_result(self, result: PredictionResult):
        """显示结果"""
        if not HAS_PYQT:
            print(f"Result: max_concentration={result.max_concentration}")
            return

        self._result = result

        # 更新摘要
        exceedance_count = result.exceedance_count
        exceedance_text = f'<span style="color: {"#e57373" if exceedance_count > 0 else "#81c784"};">{"⚠️ " + str(exceedance_count) + "个点位超标" if exceedance_count > 0 else "✓ 全部达标"}</span>'

        summary_html = f"""
        <div style="font-family: 'Segoe UI', sans-serif;">
            <h2 style="color: #4fc3f7;">{result.project_name}</h2>
            <p><b>预测工具:</b> {result.tool_type.upper()}</p>
            <p><b>预测时间:</b> {result.prediction_date.strftime('%Y-%m-%d %H:%M')}</p>
            <hr style="border: 1px solid #3c3c3c;">
            <h3 style="color: #ffb74d;">📈 最大浓度</h3>
            <p><b>最大浓度:</b> <span style="font-size: 24px; color: #e57373;">{result.max_concentration:.2f}</span> μg/m³</p>
            <p><b>达标情况:</b> {exceedance_text}</p>
            <hr style="border: 1px solid #3c3c3c;">
            <h3 style="color: #81c784;">📊 统计信息</h3>
            <p><b>评价点数:</b> {result.statistics.get('total_points', 0)}</p>
            <p><b>平均浓度:</b> {result.statistics.get('mean', 0):.2f} μg/m³</p>
            <p><b>最大浓度:</b> {result.statistics.get('max', 0):.2f} μg/m³</p>
            <p><b>最小浓度:</b> {result.statistics.get('min', 0):.2f} μg/m³</p>
            <p><b>标准差:</b> {result.statistics.get('std', 0):.2f}</p>
        </div>
        """
        self.summary_label.setText(summary_html)

        # 更新表格
        self.data_table.setRowCount(len(result.concentration_grid))
        for i, data in enumerate(result.concentration_grid):
            self.data_table.setItem(i, 0, QTableWidgetItem(f"{data.x:.1f}"))
            self.data_table.setItem(i, 1, QTableWidgetItem(f"{data.y:.1f}"))
            self.data_table.setItem(i, 2, QTableWidgetItem(f"{data.concentration:.2f}"))
            self.data_table.setItem(i, 3, QTableWidgetItem(f"{data.longitude:.6f}" if data.longitude else "-"))
            self.data_table.setItem(i, 4, QTableWidgetItem(f"{data.latitude:.6f}" if data.latitude else "-"))

    def _on_export(self):
        """导出报告"""
        if not self._result:
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "导出报告",
            f"{self._result.project_name}_报告.txt",
            "文本文件 (*.txt);;所有文件 (*.*)"
        )

        if filepath:
            try:
                from core.seamless_tool_integration import ReportGenerator
                generator = ReportGenerator(self._result)
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(generator.generate_text_report())
                QMessageBox.information(self, "成功", "报告已导出！")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"导出失败: {str(e)}")

    def _on_export_csv(self):
        """导出CSV"""
        if not self._result:
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "导出数据",
            f"{self._result.project_name}_数据.csv",
            "CSV文件 (*.csv);;所有文件 (*.*)"
        )

        if filepath:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write("X,Y,浓度(μg/m³),经度,纬度\n")
                    for data in self._result.concentration_grid:
                        f.write(f"{data.x:.1f},{data.y:.1f},{data.concentration:.2f},{data.longitude or ''},{data.latitude or ''}\n")
                QMessageBox.information(self, "成功", "数据已导出！")
            except Exception as e:
                QMessageBox.warning(self, "错误", f"导出失败: {str(e)}")


class AirPredictionPanel(QWidget if HAS_PYQT else object):
    """
    大气预测面板

    完整的大气预测功能界面

    使用示例：
    ```python
    from ui.air_prediction_panel import AirPredictionPanel

    panel = AirPredictionPanel()
    panel.show()
    ```
    """

    def __init__(self, parent=None):
        if HAS_PYQT:
            super().__init__(parent)
            self._manager = None
            self._setup_ui()
            self._init_manager()
        else:
            self._manager = None

    def _setup_ui(self):
        """设置UI"""
        # 主布局
        main_layout = QVBoxLayout(self)

        # 标题栏
        title_bar = QHBoxLayout()
        title = QLabel("🌬️ 大气预测")
        title.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #4fc3f7;
            }
        """)
        title_bar.addWidget(title)
        title_bar.addStretch()

        # 工具状态
        self.tool_status_label = QLabel("🔄 检查工具...")
        self.tool_status_label.setStyleSheet("padding: 5px 10px; background-color: #2d2d30; border-radius: 4px;")
        title_bar.addWidget(self.tool_status_label)

        main_layout.addLayout(title_bar)

        # 标签页
        self.tabs = QTabWidget()

        # 配置页
        self.config_tab = ConfigFormWidget()
        scroll = QScrollArea()
        scroll.setWidget(self.config_tab)
        scroll.setWidgetResizable(True)
        self.tabs.addTab(scroll, "⚙️ 配置")

        # 进度页
        progress_widget = QWidget()
        progress_layout = QVBoxLayout(progress_widget)
        self.progress_display = ProgressDisplay()
        progress_layout.addWidget(self.progress_display)

        # 日志
        progress_layout.addWidget(QLabel("📝 执行日志:"))
        self.log_display = LogDisplay()
        progress_layout.addWidget(self.log_display)

        self.tabs.addTab(progress_widget, "🚀 执行")

        # 结果页
        self.result_display = ResultDisplay()
        self.tabs.addTab(self.result_display, "📊 结果")

        main_layout.addWidget(self.tabs)

        # 底部按钮
        button_layout = QHBoxLayout()

        self.check_btn = QPushButton("🔍 检查工具")
        self.check_btn.clicked.connect(self._check_tools)
        button_layout.addWidget(self.check_btn)

        button_layout.addStretch()

        self.run_btn = QPushButton("▶️ 开始预测")
        self.run_btn.setStyleSheet("""
            QPushButton {
                background-color: #4caf50;
                color: white;
                padding: 10px 20px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #666;
            }
        """)
        self.run_btn.clicked.connect(self._run_prediction)
        button_layout.addWidget(self.run_btn)

        main_layout.addLayout(button_layout)

    def _init_manager(self):
        """初始化管理器"""
        if not HAS_CORE:
            self.log_display.append_log("核心模块未加载", "ERROR")
            return

        try:
            self._manager = SeamlessIntegrationManager.get_instance()
            self._manager.set_log_callback(lambda msg: self.log_display.append_log(msg))
            self.log_display.append_log("集成管理器初始化完成")
        except Exception as e:
            self.log_display.append_log(f"初始化失败: {str(e)}", "ERROR")

    def _check_tools(self):
        """检查工具状态"""
        if not self._manager:
            self.log_display.append_log("管理器未初始化", "ERROR")
            return

        self.tool_status_label.setText("🔄 检查中...")
        self.tool_status_label.setStyleSheet("padding: 5px 10px; background-color: #ff9800; border-radius: 4px; color: white;")

        try:
            ready = self._manager.check_tool_ready("aermod")
            if ready:
                self.tool_status_label.setText("✅ AERMOD已就绪")
                self.tool_status_label.setStyleSheet("padding: 5px 10px; background-color: #4caf50; border-radius: 4px; color: white;")
                self.log_display.append_log("AERMOD工具已就绪")
            else:
                self.tool_status_label.setText("⚠️ AERMOD未安装")
                self.tool_status_label.setStyleSheet("padding: 5px 10px; background-color: #ff9800; border-radius: 4px; color: white;")
                self.log_display.append_log("AERMOD工具未安装，点击\"开始预测\"将自动部署", "WARNING")

                # 询问是否部署
                reply = QMessageBox.question(
                    self,
                    "工具未安装",
                    "AERMOD未安装，是否自动下载并部署？",
                    QMessageBox.Yes | QMessageBox.No
                )

                if reply == QMessageBox.Yes:
                    self._deploy_tool("aermod")

        except Exception as e:
            self.tool_status_label.setText("❌ 检查失败")
            self.tool_status_label.setStyleSheet("padding: 5px 10px; background-color: #f44336; border-radius: 4px; color: white;")
            self.log_display.append_log(f"检查失败: {str(e)}", "ERROR")

    def _deploy_tool(self, tool_type: str):
        """部署工具"""
        if not self._manager:
            return

        def on_progress(progress):
            self.log_display.append_log(f"部署进度: {progress.percent}% - {progress.message}")

        self.run_btn.setEnabled(False)
        self.check_btn.setEnabled(False)

        try:
            success = self._manager.ensure_tool_ready(tool_type, progress_callback=on_progress)
            if success:
                self.tool_status_label.setText("✅ AERMOD已就绪")
                self.tool_status_label.setStyleSheet("padding: 5px 10px; background-color: #4caf50; border-radius: 4px; color: white;")
                self.log_display.append_log("AERMOD部署成功！", "SUCCESS")
            else:
                self.log_display.append_log("AERMOD部署失败", "ERROR")
        except Exception as e:
            self.log_display.append_log(f"部署失败: {str(e)}", "ERROR")
        finally:
            self.run_btn.setEnabled(True)
            self.check_btn.setEnabled(True)

    def _run_prediction(self):
        """运行预测"""
        if not self._manager:
            self.log_display.append_log("管理器未初始化", "ERROR")
            return

        # 获取项目数据
        project_data = self.config_tab.get_project_data()
        if not project_data:
            self.log_display.append_log("项目数据无效", "ERROR")
            return

        self.log_display.append_log(f"开始预测: {project_data.project_name}")
        self.tabs.setCurrentIndex(1)  # 切换到执行页
        self.run_btn.setEnabled(False)

        def on_step(step: ExecutionStep):
            self.progress_display.update_step(step)

        try:
            # 运行预测
            result = self._manager.run_prediction(
                project_data=project_data,
                tool_type="aermod",
                progress_callback=on_step
            )

            # 显示结果
            self.result_display.display_result(result)
            self.tabs.setCurrentIndex(2)  # 切换到结果页

            self.log_display.append_log("预测完成！", "SUCCESS")

            # 显示完成消息
            QMessageBox.information(
                self,
                "预测完成",
                f"预测已完成！\n最大浓度: {result.max_concentration:.2f} μg/m³\n"
                f"{'⚠️ 有超标点位' if result.exceedance_count > 0 else '✓ 全部达标'}"
            )

        except Exception as e:
            self.log_display.append_log(f"预测失败: {str(e)}", "ERROR")
            QMessageBox.warning(self, "预测失败", str(e))
        finally:
            self.run_btn.setEnabled(True)

    def get_manager(self):
        """获取管理器"""
        return self._manager


# 如果直接运行
if __name__ == "__main__":
    import sys

    if HAS_PYQT:
        from PyQt6.QtWidgets import QApplication

        app = QApplication(sys.argv)
        window = AirPredictionPanel()
        window.show()
        sys.exit(app.exec())
    else:
        print("PyQt6 not available. This module requires PyQt6 to run the UI.")
