# -*- coding: utf-8 -*-
"""
统一佣金系统 - PyQt6 UI面板
Unified Commission System - PyQt6 Panel

提供可视化的佣金配置、打赏、订单管理界面
"""

import logging
from typing import Any, Dict, Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QTabWidget, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QLineEdit, QComboBox,
    QSpinBox, QDoubleSpinBox, QTextEdit, QGroupBox,
    QFormLayout, QScrollArea, QFrame, QProgressBar,
    QMessageBox, QDialog, QListWidget, QCheckBox,
    QRadioButton, QButtonGroup, QStatusBar,
    QToolBar, QSplitter, QDialogButtonBox
)

logger = logging.getLogger(__name__)


class CommissionTestWorker(QThread):
    """支付测试工作线程"""
    finished = pyqtSignal(dict)
    progress = pyqtSignal(int, str)
    
    def __init__(self, commission_system, provider):
        super().__init__()
        self.system = commission_system
        self.provider = provider
    
    def run(self):
        try:
            self.progress.emit(30, "正在测试连接...")
            result = self.system.test_payment_connection(self.provider)
            self.progress.emit(100, "测试完成")
            self.finished.emit(result)
        except Exception as e:
            self.finished.emit({"success": False, "message": str(e)})


class CommissionPanel(QWidget):
    """
    佣金系统主面板
    
    提供以下功能:
    - 模块配置管理
    - 打赏下单
    - 订单管理
    - 结算查看
    - 统计分析
    """
    
    def __init__(self, parent=None, commission_system=None):
        super().__init__(parent)
        
        self.system = commission_system
        
        self._init_ui()
    
    def set_commission_system(self, system):
        """设置佣金系统实例"""
        self.system = system
        self.refresh_all()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        
        # 创建标签页
        self.tabs = QTabWidget()
        
        # 添加各标签页
        self.tabs.addTab(self._create_module_config_tab(), "模块配置")
        self.tabs.addTab(self._create_reward_tab(), "打赏下单")
        self.tabs.addTab(self._create_orders_tab(), "订单管理")
        self.tabs.addTab(self._create_statistics_tab(), "统计分析")
        self.tabs.addTab(self._create_settings_tab(), "系统设置")
        
        layout.addWidget(self.tabs)
    
    def _create_module_config_tab(self) -> QWidget:
        """创建模块配置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 模块列表
        self.module_list = QListWidget()
        self.module_list.itemClicked.connect(self._on_module_selected)
        layout.addWidget(QLabel("选择模块:"))
        layout.addWidget(self.module_list)
        
        # 模块配置表单
        config_group = QGroupBox("模块配置")
        config_layout = QFormLayout()
        
        self.config_name = QLineEdit()
        self.config_desc = QLineEdit()
        self.config_enabled = QCheckBox()
        self.config_min = QDoubleSpinBox()
        self.config_min.setRange(0.01, 10000)
        self.config_max = QDoubleSpinBox()
        self.config_max.setRange(0.01, 100000)
        self.config_rate = QDoubleSpinBox()
        self.config_rate.setRange(0, 0.1)
        self.config_rate.setDecimals(6)
        self.config_rate.setSingleStep(0.0001)
        
        config_layout.addRow("显示名称:", self.config_name)
        config_layout.addRow("描述:", self.config_desc)
        config_layout.addRow("启用:", self.config_enabled)
        config_layout.addRow("最低金额:", self.config_min)
        config_layout.addRow("最高金额:", self.config_max)
        config_layout.addRow("佣金比例:", self.config_rate)
        
        config_group.setLayout(config_layout)
        layout.addWidget(config_group)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        self.btn_save_config = QPushButton("保存配置")
        self.btn_save_config.clicked.connect(self._save_module_config)
        self.btn_reset_config = QPushButton("重置")
        self.btn_reset_config.clicked.connect(self._reset_module_config)
        btn_layout.addWidget(self.btn_save_config)
        btn_layout.addWidget(self.btn_reset_config)
        layout.addLayout(btn_layout)
        
        # 填充模块列表
        self._refresh_module_list()
        
        return widget
    
    def _create_reward_tab(self) -> QWidget:
        """创建打赏下单标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 模块选择
        module_group = QGroupBox("选择模块")
        module_layout = QVBoxLayout()
        
        self.module_buttons = QButtonGroup()
        self.module_radios = {}
        
        modules = [
            ("deep_search", "深度搜索", "高级搜索功能"),
            ("creation", "智能创作", "AI辅助创作"),
            ("stock_futures", "股票期货", "金融数据分析"),
            ("game", "游戏娱乐", "休闲娱乐"),
            ("ide", "智能IDE", "代码开发助手"),
        ]
        
        for module_id, name, desc in modules:
            radio = QRadioButton(f"{name} - {desc}")
            self.module_radios[module_id] = radio
            self.module_buttons.addButton(radio)
            self.module_buttons.setId(radio, len(self.module_radios))
            module_layout.addWidget(radio)
        
        # 默认选择第一个
        if self.module_radios:
            list(self.module_radios.values())[0].setChecked(True)
        
        self.module_buttons.buttonClicked.connect(self._on_reward_module_changed)
        module_group.setLayout(module_layout)
        layout.addWidget(module_group)
        
        # 金额选择
        amount_group = QGroupBox("选择金额")
        amount_layout = QGridLayout()
        
        self.amount_buttons = QButtonGroup()
        self.amount_radios = {}
        
        amounts = [5, 10, 20, 50, 100, 200]
        for i, amt in enumerate(amounts):
            radio = QRadioButton(f"¥{amt}")
            self.amount_radios[amt] = radio
            self.amount_buttons.addButton(radio)
            self.amount_buttons.setId(radio, i)
            amount_layout.addWidget(radio, i // 3, i % 3)
        
        if amounts:
            amounts[1] if len(amounts) > 1 else amounts[0]
            self.amount_radios[amounts[1] if len(amounts) > 1 else amounts[0]].setChecked(True)
        
        amount_group.setLayout(amount_layout)
        layout.addWidget(amount_group)
        
        # 自定义金额
        custom_layout = QHBoxLayout()
        custom_layout.addWidget(QLabel("自定义金额:"))
        self.custom_amount = QDoubleSpinBox()
        self.custom_amount.setRange(1, 10000)
        self.custom_amount.setValue(50)
        self.custom_amount.setPrefix("¥")
        custom_layout.addWidget(self.custom_amount)
        layout.addLayout(custom_layout)
        
        # 佣金预览
        preview_group = QGroupBox("佣金预览")
        preview_layout = QFormLayout()
        
        self.preview_original = QLabel("¥0.00")
        self.preview_commission = QLabel("¥0.00")
        self.preview_total = QLabel("¥0.00")
        
        preview_layout.addRow("原始金额:", self.preview_original)
        preview_layout.addRow("佣金:", self.preview_commission)
        preview_layout.addRow("总计:", self.preview_total)
        
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)
        
        # 支付方式
        payment_group = QGroupBox("支付方式")
        payment_layout = QHBoxLayout()
        
        self.payment_combo = QComboBox()
        self.payment_combo.addItem("微信支付", "wechat")
        self.payment_combo.addItem("支付宝", "alipay")
        payment_layout.addWidget(self.payment_combo)
        
        payment_group.setLayout(payment_layout)
        layout.addWidget(payment_group)
        
        # 下单按钮
        self.btn_create_order = QPushButton("立即打赏")
        self.btn_create_order.clicked.connect(self._create_order)
        self.btn_create_order.setMinimumHeight(50)
        layout.addWidget(self.btn_create_order)
        
        # 初始化预览
        self._update_preview()
        
        return widget
    
    def _create_orders_tab(self) -> QWidget:
        """创建订单管理标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 筛选工具栏
        toolbar = QHBoxLayout()
        
        toolbar.addWidget(QLabel("订单状态:"))
        self.order_status_filter = QComboBox()
        self.order_status_filter.addItem("全部", None)
        self.order_status_filter.addItem("待支付", "pending")
        self.order_status_filter.addItem("已支付", "paid")
        self.order_status_filter.addItem("已完成", "completed")
        self.order_status_filter.addItem("已退款", "refunded")
        self.order_status_filter.currentIndexChanged.connect(self._refresh_orders)
        toolbar.addWidget(self.order_status_filter)
        
        self.btn_refresh_orders = QPushButton("刷新")
        self.btn_refresh_orders.clicked.connect(self._refresh_orders)
        toolbar.addWidget(self.btn_refresh_orders)
        
        layout.addLayout(toolbar)
        
        # 订单表格
        self.orders_table = QTableWidget()
        self.orders_table.setColumnCount(7)
        self.orders_table.setHorizontalHeaderLabels([
            "订单号", "模块", "金额", "佣金", "状态", "时间", "操作"
        ])
        self.orders_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.orders_table)
        
        return widget
    
    def _create_statistics_tab(self) -> QWidget:
        """创建统计分析标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 概览卡片
        overview_layout = QGridLayout()
        
        self.stat_total_orders = self._create_stat_card("总订单数", "0")
        self.stat_total_amount = self._create_stat_card("总金额", "¥0.00")
        self.stat_total_commission = self._create_stat_card("总佣金", "¥0.00")
        self.stat_paid_orders = self._create_stat_card("已支付订单", "0")
        
        overview_layout.addWidget(self.stat_total_orders, 0, 0)
        overview_layout.addWidget(self.stat_total_amount, 0, 1)
        overview_layout.addWidget(self.stat_total_commission, 0, 2)
        overview_layout.addWidget(self.stat_paid_orders, 0, 3)
        
        layout.addLayout(overview_layout)
        
        # 模块统计
        stat_group = QGroupBox("模块统计")
        stat_layout = QVBoxLayout()
        
        self.module_stats_table = QTableWidget()
        self.module_stats_table.setColumnCount(4)
        self.module_stats_table.setHorizontalHeaderLabels([
            "模块", "订单数", "总金额", "总佣金"
        ])
        stat_layout.addWidget(self.module_stats_table)
        
        stat_group.setLayout(stat_layout)
        layout.addWidget(stat_group)
        
        self.btn_refresh_stats = QPushButton("刷新统计")
        self.btn_refresh_stats.clicked.connect(self._refresh_statistics)
        layout.addWidget(self.btn_refresh_stats)
        
        return widget
    
    def _create_settings_tab(self) -> QWidget:
        """创建系统设置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        # 全局配置
        global_group = QGroupBox("全局配置")
        global_layout = QFormLayout()
        
        self.global_rate = QDoubleSpinBox()
        self.global_rate.setRange(0, 0.1)
        self.global_rate.setDecimals(6)
        self.global_rate.setSingleStep(0.0001)
        
        self.global_min_commission = QDoubleSpinBox()
        self.global_min_commission.setRange(0, 10)
        self.global_min_commission.setDecimals(2)
        
        self.global_max_order = QDoubleSpinBox()
        self.global_max_order.setRange(100, 1000000)
        
        global_layout.addRow("默认佣金比例:", self.global_rate)
        global_layout.addRow("最低佣金:", self.global_min_commission)
        global_layout.addRow("单笔最大金额:", self.global_max_order)
        
        global_group.setLayout(global_layout)
        scroll_layout.addWidget(global_group)
        
        # 支付配置
        payment_group = QGroupBox("支付配置")
        payment_layout = QFormLayout()
        
        self.payment_enabled = QCheckBox()
        self.payment_default = QComboBox()
        self.payment_default.addItem("微信支付", "wechat")
        self.payment_default.addItem("支付宝", "alipay")
        
        payment_layout.addRow("启用支付:", self.payment_enabled)
        payment_layout.addRow("默认方式:", self.payment_default)
        
        payment_group.setLayout(payment_layout)
        scroll_layout.addWidget(payment_group)
        
        # 测试连接
        test_group = QGroupBox("连接测试")
        test_layout = QHBoxLayout()
        
        self.btn_test_wechat = QPushButton("测试微信支付")
        self.btn_test_wechat.clicked.connect(lambda: self._test_payment("wechat"))
        self.btn_test_alipay = QPushButton("测试支付宝")
        self.btn_test_alipay.clicked.connect(lambda: self._test_payment("alipay"))
        
        test_layout.addWidget(self.btn_test_wechat)
        test_layout.addWidget(self.btn_test_alipay)
        
        test_group.setLayout(test_layout)
        scroll_layout.addWidget(test_group)
        
        # 配置导入导出
        export_group = QGroupBox("配置导入导出")
        export_layout = QHBoxLayout()
        
        self.btn_export_config = QPushButton("导出配置")
        self.btn_export_config.clicked.connect(self._export_config)
        self.btn_import_config = QPushButton("导入配置")
        self.btn_import_config.clicked.connect(self._import_config)
        
        export_layout.addWidget(self.btn_export_config)
        export_layout.addWidget(self.btn_import_config)
        
        export_group.setLayout(export_layout)
        scroll_layout.addWidget(export_group)
        
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        # 保存按钮
        self.btn_save_settings = QPushButton("保存所有设置")
        self.btn_save_settings.clicked.connect(self._save_settings)
        layout.addWidget(self.btn_save_settings)
        
        return widget
    
    def _create_stat_card(self, title: str, value: str) -> QFrame:
        """创建统计卡片"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(frame)
        
        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_label = QLabel(value)
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value_label.setStyleSheet("font-size: 20px; font-weight: bold;")
        
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        
        # 保存value标签引用
        frame.value_label = value_label
        
        return frame
    
    # ========== 事件处理 ==========
    
    def _refresh_module_list(self):
        """刷新模块列表"""
        self.module_list.clear()
        
        if self.system:
            configs = self.system.get_all_modules_config()
            for module_id, config in configs.items():
                display_name = config.get("display_name", module_id)
                item_text = f"{display_name} ({module_id})"
                self.module_list.addItem(item_text)
    
    def _on_module_selected(self, item):
        """模块选择变化"""
        if not self.system or not item:
            return
        
        text = item.text()
        # 提取模块ID
        module_id = text.split("(")[-1].rstrip(")")
        
        config = self.system.get_module_config(module_id)
        if config:
            self.config_name.setText(config.get("display_name", ""))
            self.config_desc.setText(config.get("description", ""))
            self.config_enabled.setChecked(config.get("enabled", True))
            self.config_min.setValue(config.get("min_amount", 1))
            self.config_max.setValue(config.get("max_amount", 10000))
            self.config_rate.setValue(config.get("commission_rate", 0.0003))
    
    def _save_module_config(self):
        """保存模块配置"""
        if not self.system:
            return
        
        current_item = self.module_list.currentItem()
        if not current_item:
            return
        
        text = current_item.text()
        module_id = text.split("(")[-1].rstrip(")")
        
        config = {
            "display_name": self.config_name.text(),
            "description": self.config_desc.text(),
            "enabled": self.config_enabled.isChecked(),
            "min_amount": self.config_min.value(),
            "max_amount": self.config_max.value(),
            "commission_rate": self.config_rate.value(),
        }
        
        if self.system.update_module_config(module_id, config):
            self.system.save_config()
            QMessageBox.information(self, "成功", "配置已保存")
        else:
            QMessageBox.warning(self, "失败", "配置保存失败")
    
    def _reset_module_config(self):
        """重置模块配置"""
        self._on_module_selected(self.module_list.currentItem())
    
    def _on_reward_module_changed(self):
        """打赏模块变化"""
        self._update_preview()
    
    def _update_preview(self):
        """更新佣金预览"""
        if not self.system:
            return
        
        # 获取选中的模块
        selected_module = None
        for module_id, radio in self.module_radios.items():
            if radio.isChecked():
                selected_module = module_id
                break
        
        if not selected_module:
            return
        
        # 获取选中的金额
        selected_amount = self.custom_amount.value()
        
        # 计算佣金
        preview = self.system.get_commission_preview(selected_module, selected_amount)
        
        self.preview_original.setText(f"¥{preview['original_amount']:.2f}")
        self.preview_commission.setText(f"¥{preview['commission_amount']:.2f}")
        self.preview_total.setText(f"¥{preview['total_amount']:.2f}")
    
    def _create_order(self):
        """创建订单"""
        if not self.system:
            QMessageBox.warning(self, "错误", "佣金系统未初始化")
            return
        
        # 获取选中的模块
        selected_module = None
        for module_id, radio in self.module_radios.items():
            if radio.isChecked():
                selected_module = module_id
                break
        
        if not selected_module:
            QMessageBox.warning(self, "错误", "请选择模块")
            return
        
        amount = self.custom_amount.value()
        provider = self.payment_combo.currentData()
        
        # 创建订单
        result = self.system.create_order(
            module=selected_module,
            amount=amount,
            user_id="local_user",
            provider=provider,
            subject=f"{selected_module}打赏支持"
        )
        
        if result.get("success"):
            order_id = result.get("order_id")
            preview = result.get("commission_preview", {})
            
            msg = f"订单创建成功！\n\n订单号: {order_id}\n金额: ¥{preview.get('total_amount', amount):.2f}\n\n请使用{provider}扫码支付"
            
            QMessageBox.information(self, "订单已创建", msg)
            self._refresh_orders()
        else:
            QMessageBox.warning(self, "创建失败", result.get("message", "未知错误"))
    
    def _refresh_orders(self):
        """刷新订单列表"""
        if not self.system:
            return
        
        status = self.order_status_filter.currentData()
        orders = self.system.list_orders(status=status.value() if status else None)
        
        self.orders_table.setRowCount(len(orders))
        
        for row, order in enumerate(orders):
            self.orders_table.setItem(row, 0, QTableWidgetItem(order.order_id))
            self.orders_table.setItem(row, 1, QTableWidgetItem(order.module_type.value))
            self.orders_table.setItem(row, 2, QTableWidgetItem(f"¥{order.total_amount:.2f}"))
            self.orders_table.setItem(row, 3, QTableWidgetItem(f"¥{order.commission_amount:.2f}"))
            self.orders_table.setItem(row, 4, QTableWidgetItem(order.status.value))
            self.orders_table.setItem(row, 5, QTableWidgetItem(
                order.created_at.strftime("%Y-%m-%d %H:%M") if order.created_at else ""
            ))
            
            # 操作按钮
            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(0, 0, 0, 0)
            
            refund_btn = QPushButton("退款")
            refund_btn.clicked.connect(lambda checked, oid=order.order_id: self._refund_order(oid))
            btn_layout.addWidget(refund_btn)
            
            self.orders_table.setCellWidget(row, 6, btn_widget)
    
    def _refund_order(self, order_id: str):
        """退款订单"""
        reply = QMessageBox.question(
            self, "确认退款",
            f"确定要退款订单 {order_id} 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            result = self.system.refund_order(order_id)
            
            if result.get("success"):
                QMessageBox.information(self, "成功", "退款成功")
                self._refresh_orders()
            else:
                QMessageBox.warning(self, "失败", result.get("message", "退款失败"))
    
    def _refresh_statistics(self):
        """刷新统计"""
        if not self.system:
            return
        
        stats = self.system.get_statistics()
        
        # 更新卡片
        self.stat_total_orders.value_label.setText(str(stats.get("total_orders", 0)))
        self.stat_total_amount.value_label.setText(f"¥{stats.get('total_amount', 0):.2f}")
        self.stat_total_commission.value_label.setText(f"¥{stats.get('total_commission', 0):.2f}")
        self.stat_paid_orders.value_label.setText(str(stats.get("paid_orders", 0)))
        
        # 更新模块表格
        module_stats = stats.get("module_stats", {})
        self.module_stats_table.setRowCount(len(module_stats))
        
        for row, (module_id, m_stats) in enumerate(module_stats.items()):
            self.module_stats_table.setItem(row, 0, QTableWidgetItem(module_id))
            self.module_stats_table.setItem(row, 1, QTableWidgetItem(str(m_stats.get("order_count", 0))))
            self.module_stats_table.setItem(row, 2, QTableWidgetItem(f"¥{m_stats.get('total_amount', 0):.2f}"))
            self.module_stats_table.setItem(row, 3, QTableWidgetItem(f"¥{m_stats.get('total_commission', 0):.2f}"))
    
    def _test_payment(self, provider: str):
        """测试支付连接"""
        if not self.system:
            return
        
        self.btn_test_wechat.setEnabled(False)
        self.btn_test_alipay.setEnabled(False)
        
        result = self.system.test_payment_connection(provider)
        
        if result.get("success"):
            QMessageBox.information(self, "测试成功", result.get("message", "连接正常"))
        else:
            QMessageBox.warning(self, "测试失败", result.get("message", "连接失败"))
        
        self.btn_test_wechat.setEnabled(True)
        self.btn_test_alipay.setEnabled(True)
    
    def _export_config(self):
        """导出配置"""
        if not self.system:
            return
        
        config = self.system.export_config("yaml")
        
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "导出配置", "commission_config.yaml", "YAML Files (*.yaml)"
        )
        
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(config)
                QMessageBox.information(self, "成功", f"配置已导出到 {path}")
            except Exception as e:
                QMessageBox.warning(self, "失败", f"导出失败: {str(e)}")
    
    def _import_config(self):
        """导入配置"""
        if not self.system:
            return
        
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "导入配置", "", "YAML Files (*.yaml);;JSON Files (*.json)"
        )
        
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    config = f.read()
                
                if self.system.import_config(config):
                    QMessageBox.information(self, "成功", "配置已导入")
                    self.refresh_all()
                else:
                    QMessageBox.warning(self, "失败", "配置导入失败")
            except Exception as e:
                QMessageBox.warning(self, "失败", f"导入失败: {str(e)}")
    
    def _save_settings(self):
        """保存设置"""
        if not self.system:
            return
        
        if self.system.save_config():
            QMessageBox.information(self, "成功", "设置已保存")
        else:
            QMessageBox.warning(self, "失败", "设置保存失败")
    
    def refresh_all(self):
        """刷新所有数据"""
        self._refresh_module_list()
        self._refresh_orders()
        self._refresh_statistics()
