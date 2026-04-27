"""
Model Router 监控面板
PyQt6 UI 界面，显示模型状态和告警
"""

import logging
from typing import Dict, Any

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QGroupBox, QGridLayout, QMessageBox,
)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QColor

logger = logging.getLogger(__name__)


class ModelRouterMonitorPanel(QWidget):
    """
    Model Router 监控面板
    
    功能：
    1. 显示模型总数 / 可用数
    2. 显示每个模型的状态
    3. 告警（如果所有模型都不可用）
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._router = None
        self._init_ui()
        self._setup_timer()

    def _init_ui(self):
        """构建UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # 标题
        title = QLabel("📊 Model Router 监控")
        title.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #333333;
            padding-bottom: 8px;
        """)
        layout.addWidget(title)

        # 概览卡片
        self._overview_group = QGroupBox("概览")
        overview_layout = QGridLayout(self._overview_group)

        self._total_label = QLabel("总模型数: --")
        self._available_label = QLabel("可用模型数: --")
        self._cache_label = QLabel("缓存大小: --")

        overview_layout.addWidget(self._total_label, 0, 0)
        overview_layout.addWidget(self._available_label, 0, 1)
        overview_layout.addWidget(self._cache_label, 1, 0)

        layout.addWidget(self._overview_group)

        # 模型列表
        self._models_group = QGroupBox("模型列表")
        models_layout = QVBoxLayout(self._models_group)

        self._models_info_label = QLabel("加载中...")
        self._models_info_label.setWordWrap(True)
        self._models_info_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        models_layout.addWidget(self._models_info_label)

        layout.addWidget(self._models_group)

        # 告警区域
        self._alert_group = QGroupBox("告警")
        alert_layout = QVBoxLayout(self._alert_group)
        self._alert_label = QLabel("✅ 无告警")
        self._alert_label.setStyleSheet("color: green; font-weight: bold;")
        alert_layout.addWidget(self._alert_label)
        layout.addWidget(self._alert_group)

        layout.addStretch()

    def _setup_timer(self):
        """设置定时器，定期刷新"""
        self._timer = QTimer()
        self._timer.timeout.connect(self._refresh)
        self._timer.start(5000)  # 每 5 秒刷新一次

        # 立即刷新一次
        self._refresh()

    def _refresh(self):
        """刷新监控数据"""
        try:
            from client.src.business.global_model_router import get_global_router
            self._router = get_global_router()
            stats = self._router.get_stats()

            # 更新概览
            total = stats.get("total_models", 0)
            available = stats.get("available_models", 0)
            cache_size = stats.get("cache_size", 0)

            self._total_label.setText(f"总模型数: {total}")
            self._available_label.setText(f"可用模型数: {available}")
            self._cache_label.setText(f"缓存大小: {cache_size}")

            # 更新模型列表
            models_info = []
            for model_id, model in self._router.models.items():
                status = "✅ 可用" if model.is_available else "❌ 不可用"
                models_info.append(f"• {model.name} ({model_id}): {status}")

            self._models_info_label.setText("\n".join(models_info) if models_info else "无模型")

            # 更新告警
            if available == 0:
                self._alert_label.setText("⚠️ 告警：所有模型都不可用！")
                self._alert_label.setStyleSheet("color: red; font-weight: bold;")
            elif available < total:
                self._alert_label.setText(f"⚠️ 警告：{total - available} 个模型不可用")
                self._alert_label.setStyleSheet("color: orange; font-weight: bold;")
            else:
                self._alert_label.setText("✅ 无告警")
                self._alert_label.setStyleSheet("color: green; font-weight: bold;")

        except Exception as e:
            logger.error(f"刷新监控数据失败: {e}")
            self._alert_label.setText(f"❌ 刷新失败: {e}")
            self._alert_label.setStyleSheet("color: red;")

    def closeEvent(self, event):
        """关闭事件，停止定时器"""
        self._timer.stop()
        super().closeEvent(event)
