"""
Time Forecast Panel - 时间预测面板
===================================

PyQt6 实现的时间序列预测界面。
"""

from typing import Optional, List
from pathlib import Path

try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
        QTextEdit, QFileDialog, QComboBox, QProgressBar, QListWidget,
        QListWidgetItem, QGroupBox, QFormLayout, QCheckBox, QSpinBox,
        QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
        QMessageBox, QApplication, QStyle, QLineEdit
    )
    from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
    from PyQt6.QtGui import QFont
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False
    # Mock classes
    class QWidget: pass
    class Qt: pass
    class pyqtSignal: pass


from ..core.time_forecast import (
    TimeSeriesData, DataLoader, Forecaster, ForecastModel,
    ForecastResult, TimesFMAdapter, TimesFMConfig,
    ForecastVisualizer, PlotType
)


class ForecastWorker(QThread):
    """预测工作线程"""
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(ForecastResult)
    error = pyqtSignal(str)

    def __init__(self, data: TimeSeriesData, horizon: int, model_type: str):
        super().__init__()
        self.data = data
        self.horizon = horizon
        self.model_type = model_type

    def run(self):
        try:
            self.progress.emit(10, 100, "初始化预测器...")

            forecaster = Forecaster()
            model_map = {
                "auto": ForecastModel.LINEAR,
                "linear": ForecastModel.LINEAR,
                "arima": ForecastModel.ARIMA,
                "ema": ForecastModel.EXPONENTIAL_SMOOTHING,
                "sma": ForecastModel.SIMPLE_MOVING_AVERAGE,
                "nn": ForecastModel.NEURAL_NETWORK,
            }

            model = model_map.get(self.model_type, ForecastModel.LINEAR)

            self.progress.emit(30, 100, f"训练模型 ({model.value})...")

            result = forecaster.forecast(self.data, self.horizon, model)

            self.progress.emit(90, 100, "生成可视化...")
            self.progress.emit(100, 100, "完成!")

            self.finished.emit(result)

        except Exception as e:
            self.error.emit(str(e))


class TimeForecastPanel(QWidget if PYQT6_AVAILABLE else object):
    """时间预测面板"""

    TAB_FORECAST = "⏱️ 预测"
    TAB_DATA = "📊 数据"
    TAB_SETTINGS = "⚙️ 设置"

    def __init__(self, parent=None):
        if not PYQT6_AVAILABLE:
            raise ImportError("PyQt6 is required for this panel")

        super().__init__(parent)
        self.current_data: Optional[TimeSeriesData] = None
        self.current_forecast: Optional[ForecastResult] = None
        self.worker: Optional[ForecastWorker] = None

        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 创建标签页
        tabs = QTabWidget()
        tabs.addTab(self._create_forecast_tab(), self.TAB_FORECAST)
        tabs.addTab(self._create_data_tab(), self.TAB_DATA)
        tabs.addTab(self._create_settings_tab(), self.TAB_SETTINGS)

        layout.addWidget(tabs)

    def _create_forecast_tab(self) -> QWidget:
        """创建预测标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 数据选择区
        data_group = QGroupBox("📁 数据源")
        data_layout = QHBoxLayout()

        self.data_path_label = QLabel("未加载数据")
        self.data_path_label.setStyleSheet("color: #666; padding: 5px;")

        self.load_data_btn = QPushButton("加载数据")
        self.load_data_btn.clicked.connect(self._load_data)

        self.generate_sample_btn = QPushButton("生成示例")
        self.generate_sample_btn.clicked.connect(self._generate_sample_data)

        data_layout.addWidget(QLabel("数据:"))
        data_layout.addWidget(self.data_path_label, 1)
        data_layout.addWidget(self.load_data_btn)
        data_layout.addWidget(self.generate_sample_btn)

        data_group.setLayout(data_layout)
        layout.addWidget(data_group)

        # 预测设置区
        settings_group = QGroupBox("🔧 预测设置")
        settings_layout = QFormLayout()

        # 预测范围
        self.horizon_spin = QSpinBox()
        self.horizon_spin.setRange(1, 1000)
        self.horizon_spin.setValue(12)
        self.horizon_spin.setSuffix(" 步")
        settings_layout.addRow("预测范围:", self.horizon_spin)

        # 模型选择
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "自动选择 (Auto)",
            "线性回归 (Linear)",
            "ARIMA",
            "指数平滑 (EMA)",
            "移动平均 (SMA)",
            "神经网络 (NN)"
        ])
        settings_layout.addRow("预测模型:", self.model_combo)

        # 显示选项
        self.show_confidence_cb = QCheckBox("显示置信区间")
        self.show_confidence_cb.setChecked(True)
        settings_layout.addRow("", self.show_confidence_cb)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_label = QLabel()
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.progress_label)

        # 按钮区
        btn_layout = QHBoxLayout()

        self.predict_btn = QPushButton("🚀 开始预测")
        self.predict_btn.clicked.connect(self._start_forecast)
        self.predict_btn.setEnabled(False)

        self.plot_btn = QPushButton("📈 绘图")
        self.plot_btn.clicked.connect(self._plot_forecast)
        self.plot_btn.setEnabled(False)

        self.export_btn = QPushButton("💾 导出结果")
        self.export_btn.clicked.connect(self._export_forecast)
        self.export_btn.setEnabled(False)

        btn_layout.addWidget(self.predict_btn)
        btn_layout.addWidget(self.plot_btn)
        btn_layout.addWidget(self.export_btn)

        layout.addLayout(btn_layout)

        # 预测结果显示
        result_group = QGroupBox("📋 预测结果")
        result_layout = QVBoxLayout()

        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setMaximumHeight(200)

        result_layout.addWidget(self.result_text)
        result_group.setLayout(result_layout)
        layout.addWidget(result_group, 1)

        # 预览区
        preview_group = QGroupBox("👁️ 预览")
        preview_layout = QVBoxLayout()

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setPlaceholderText("预测图表将在此显示...")

        preview_layout.addWidget(self.preview_text)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group, 2)

        return widget

    def _create_data_tab(self) -> QWidget:
        """创建数据标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 数据统计
        stats_group = QGroupBox("📊 数据统计")
        stats_layout = QFormLayout()

        self.stats_label = QLabel("未加载数据")
        stats_layout.addRow("数据信息:", self.stats_label)

        self.data_length = QLabel("-")
        stats_layout.addRow("数据点数:", self.data_length)

        self.data_mean = QLabel("-")
        stats_layout.addRow("均值:", self.data_mean)

        self.data_std = QLabel("-")
        stats_layout.addRow("标准差:", self.data_std)

        self.data_range = QLabel("-")
        stats_layout.addRow("范围:", self.data_range)

        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        # 异常检测
        anomaly_group = QGroupBox("⚠️ 异常检测")
        anomaly_layout = QVBoxLayout()

        self.anomaly_threshold = QSpinBox()
        self.anomaly_threshold.setRange(1, 10)
        self.anomaly_threshold.setValue(3)
        self.anomaly_threshold.setSuffix(" 标准差")

        self.detect_anomaly_btn = QPushButton("🔍 检测异常")
        self.detect_anomaly_btn.clicked.connect(self._detect_anomalies)
        self.detect_anomaly_btn.setEnabled(False)

        anomaly_layout.addWidget(QLabel("检测阈值:"))
        anomaly_layout.addWidget(self.anomaly_threshold)
        anomaly_layout.addWidget(self.detect_anomaly_btn)

        anomaly_group.setLayout(anomaly_layout)
        layout.addWidget(anomaly_group)

        # 数据预览
        preview_group = QGroupBox("👁️ 数据预览")
        preview_layout = QVBoxLayout()

        self.data_preview = QTextEdit()
        self.data_preview.setReadOnly(True)
        self.data_preview.setPlaceholderText("数据预览...")

        preview_layout.addWidget(self.data_preview)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group, 1)

        return widget

    def _create_settings_tab(self) -> QWidget:
        """创建设置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # TimesFM 设置
        timesfm_group = QGroupBox("🤖 TimesFM 设置")
        timesfm_layout = QFormLayout()

        self.timesfm_enabled = QCheckBox("启用 TimesFM (如已安装)")
        timesfm_layout.addRow("", self.timesfm_enabled)

        self.timesfm_backend = QComboBox()
        self.timesfm_backend.addItems(["PyTorch (推荐)", "Flax (JAX)", "内置轻量方案"])
        timesfm_layout.addRow("后端:", self.timesfm_backend)

        self.max_context = QSpinBox()
        self.max_context.setRange(128, 16384)
        self.max_context.setValue(512)
        self.timesfm_layout.addRow("最大上下文:", self.max_context)

        self.max_horizon = QSpinBox()
        self.max_horizon.setRange(16, 1024)
        self.max_horizon.setValue(128)
        timesfm_layout.addRow("最大预测范围:", self.max_horizon)

        self.use_quantile = QCheckBox("使用分位数预测")
        self.use_quantile.setChecked(True)
        timesfm_layout.addRow("", self.use_quantile)

        timesfm_group.setLayout(timesfm_layout)
        layout.addWidget(timesfm_group)

        # 可视化设置
        viz_group = QGroupBox("📈 可视化设置")
        viz_layout = QFormLayout()

        self.viz_format = QComboBox()
        self.viz_format.addItems(["Matplotlib (PNG)", "Plotly (HTML)", "ASCII (终端)"])
        viz_layout.addRow("图表格式:", self.viz_format)

        self.fig_width = QSpinBox()
        self.fig_width.setRange(6, 24)
        self.fig_width.setValue(12)
        viz_layout.addRow("宽度 (英寸):", self.fig_width)

        self.fig_height = QSpinBox()
        self.fig_height.setRange(4, 16)
        self.fig_height.setValue(6)
        viz_layout.addRow("高度 (英寸):", self.fig_height)

        viz_group.setLayout(viz_layout)
        layout.addWidget(viz_group)

        # 输出设置
        output_group = QGroupBox("📤 输出设置")
        output_layout = QFormLayout()

        self.output_dir = QLineEdit()
        self.output_dir.setPlaceholderText("./forecast_results")
        output_layout.addRow("输出目录:", self.output_dir)

        output_group.setLayout(output_layout)
        layout.addWidget(output_group)

        layout.addStretch()

        return widget

    def _load_data(self):
        """加载数据文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择数据文件",
            "",
            "CSV 文件 (*.csv);;所有文件 (*.*)"
        )

        if file_path:
            try:
                loader = DataLoader()
                self.current_data = loader.load(file_path)

                self.data_path_label.setText(file_path)
                self.data_path_label.setStyleSheet("color: #333; padding: 5px;")

                self._update_data_display()
                self.predict_btn.setEnabled(True)
                self.detect_anomaly_btn.setEnabled(True)

                QMessageBox.information(self, "加载成功", f"数据已加载:\n{file_path}")

            except Exception as e:
                QMessageBox.critical(self, "加载失败", f"无法加载数据:\n{str(e)}")

    def _generate_sample_data(self):
        """生成示例数据"""
        import numpy as np
        from datetime import datetime, timedelta

        n_points = 100
        t = np.arange(n_points)

        # 生成带有趋势和季节性的数据
        values = 100 + 0.5 * t + 10 * np.sin(2 * np.pi * t / 20) + np.random.randn(n_points) * 5

        timestamps = [datetime.now() - timedelta(days=n_points - i) for i in range(n_points)]

        self.current_data = TimeSeriesData(
            name="sample_data",
            values=values.tolist(),
            timestamps=timestamps
        )

        self.data_path_label.setText("[示例数据]")
        self.data_path_label.setStyleSheet("color: #4CAF50; padding: 5px;")

        self._update_data_display()
        self.predict_btn.setEnabled(True)
        self.detect_anomaly_btn.setEnabled(True)

        QMessageBox.information(self, "生成成功", "示例时间序列数据已生成!")

    def _update_data_display(self):
        """更新数据显示"""
        if not self.current_data:
            return

        data = self.current_data

        # 统计信息
        self.stats_label.setText(f"{data.name} ({data.frequency.value})")
        self.data_length.setText(str(data.length))
        self.data_mean.setText(f"{data.mean:.4f}")
        self.data_std.setText(f"{data.std:.4f}")
        self.data_range.setText(f"{data.min:.4f} ~ {data.max:.4f}")

        # 数据预览 (前20个点)
        preview_lines = ["前 20 个数据点:", "-" * 40]
        for i, (ts, val) in enumerate(zip(data.timestamps[:20], data.values[:20])):
            if hasattr(ts, 'strftime'):
                ts_str = ts.strftime("%Y-%m-%d")
            else:
                ts_str = str(ts)
            preview_lines.append(f"{i+1:3d}. {ts_str}: {val:.4f}")

        self.data_preview.setPlainText("\n".join(preview_lines))

    def _detect_anomalies(self):
        """检测异常值"""
        if not self.current_data:
            return

        threshold = self.anomaly_threshold.value()
        anomaly_indices = self.current_data.detect_anomalies(threshold=threshold)

        if not anomaly_indices:
            QMessageBox.information(self, "异常检测", "未检测到异常值!")
        else:
            QMessageBox.information(
                self, "异常检测",
                f"检测到 {len(anomaly_indices)} 个异常值!\n\n索引: {anomaly_indices[:20]}..."
            )

    def _start_forecast(self):
        """开始预测"""
        if not self.current_data:
            QMessageBox.warning(self, "错误", "请先加载数据")
            return

        horizon = self.horizon_spin.value()
        model_text = self.model_combo.currentText().split("(")[0].strip().lower()

        model_map = {
            "自动选择": "auto",
            "线性回归": "linear",
            "arima": "arima",
            "指数平滑": "ema",
            "移动平均": "sma",
            "神经网络": "nn",
        }

        model_key = model_map.get(model_text, "auto")

        # 开始预测
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.predict_btn.setEnabled(False)

        self.worker = ForecastWorker(self.current_data, horizon, model_key)
        self.worker.progress.connect(self._on_forecast_progress)
        self.worker.finished.connect(self._on_forecast_finished)
        self.worker.error.connect(self._on_forecast_error)

        self.worker.start()

    def _on_forecast_progress(self, current: int, total: int, message: str):
        """预测进度更新"""
        if total > 0:
            value = int(current / total * 100)
            self.progress_bar.setValue(value)
        self.progress_label.setText(message)

    def _on_forecast_finished(self, result: ForecastResult):
        """预测完成"""
        self.current_forecast = result
        self.progress_bar.setVisible(False)
        self.predict_btn.setEnabled(True)
        self.plot_btn.setEnabled(True)
        self.export_btn.setEnabled(True)

        # 显示预测结果
        self._update_forecast_display(result)

        QMessageBox.information(self, "预测完成", "预测已完成!\n点击「绘图」查看可视化结果。")

    def _on_forecast_error(self, error: str):
        """预测错误"""
        self.progress_bar.setVisible(False)
        self.predict_btn.setEnabled(True)
        self.progress_label.setText("预测失败")

        QMessageBox.critical(self, "预测失败", f"预测过程中出错:\n{error}")

    def _update_forecast_display(self, result: ForecastResult):
        """更新预测结果显示"""
        lines = [
            "=" * 50,
            f"预测结果",
            "=" * 50,
            f"模型: {result.model_name}",
            f"预测范围: {result.horizon} 步",
            f"置信度: {result.confidence:.0%}",
            "",
            "预测值 (前 10 步):",
            "-" * 30,
        ]

        for i, val in enumerate(result.point_forecast[:10]):
            lines.append(f"  {i+1:3d}. {val:.4f}")

        if len(result.point_forecast) > 10:
            lines.append(f"  ... (共 {len(result.point_forecast)} 步)")

        lines.extend([
            "",
            "分位数区间 (前 5 步):",
            "-" * 30,
        ])

        for i in range(min(5, len(result.point_forecast))):
            lower = result.lower_bound[i]
            upper = result.upper_bound[i]
            lines.append(f"  {i+1}. [{lower:.4f}, {upper:.4f}]")

        self.result_text.setPlainText("\n".join(lines))

    def _plot_forecast(self):
        """绘制预测图"""
        if not self.current_data or not self.current_forecast:
            return

        try:
            visualizer = ForecastVisualizer()

            # 使用 ASCII 预览
            ascii_plot = visualizer.plot_to_ascii(
                self.current_data,
                self.current_forecast,
                width=70,
                height=15
            )

            self.preview_text.setPlainText(ascii_plot)

            QMessageBox.information(
                self, "绘图成功",
                "ASCII 图表已生成!\n(高级图表请使用 Plotly 格式)"
            )

        except Exception as e:
            QMessageBox.critical(self, "绘图失败", f"生成图表时出错:\n{str(e)}")

    def _export_forecast(self):
        """导出预测结果"""
        if not self.current_forecast:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存预测结果",
            "forecast_result.txt",
            "文本文件 (*.txt);;CSV 文件 (*.csv);;JSON 文件 (*.json)"
        )

        if file_path:
            try:
                if file_path.endswith('.json'):
                    import json
                    result_dict = self.current_forecast.to_dict()
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(result_dict, f, ensure_ascii=False, indent=2)
                elif file_path.endswith('.csv'):
                    import csv
                    with open(file_path, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        writer.writerow(['Step', 'Forecast', 'Lower', 'Upper'])
                        for i in range(len(self.current_forecast.point_forecast)):
                            writer.writerow([
                                i + 1,
                                self.current_forecast.point_forecast[i],
                                self.current_forecast.lower_bound[i],
                                self.current_forecast.upper_bound[i]
                            ])
                else:
                    # 文本文件
                    lines = ["预测结果", "=" * 40]
                    lines.append(f"模型: {self.current_forecast.model_name}")
                    lines.append(f"预测范围: {self.current_forecast.horizon}")
                    lines.append("")
                    lines.append("预测值:")
                    for i, val in enumerate(self.current_forecast.point_forecast):
                        lines.append(f"  {i+1}: {val:.4f}")

                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write("\n".join(lines))

                QMessageBox.information(self, "导出成功", f"结果已保存至:\n{file_path}")

            except Exception as e:
                QMessageBox.critical(self, "导出失败", f"导出时出错:\n{str(e)}")
