"""
社区权益中心面板 - CommunityRightsPanel
=========================================

提供用户权益查看、基金状态、税务透明等功能

Author: Hermes Desktop Team
"""

import asyncio
from datetime import datetime
from typing import List, Dict, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QTabWidget, QTextEdit,
    QLineEdit, QComboBox, QSpinBox, QGroupBox, QGridLayout,
    QScrollArea, QFrame, QProgressBar, QListWidget, QListWidgetItem,
    QDialog, QDialogButtonBox, QFormLayout, QTabBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QIcon, QPalette, QColor


class RightsTableModel:
    """权益表格模型"""
    COLUMNS = ['ID', '名称', '类型', '来源', '发放日期', '到期日期', '状态', '条款']

    @staticmethod
    def format_right(right: Dict) -> List[str]:
        """格式化权益数据"""
        right_type_names = {
            'service_quota': '服务配额',
            'digital_asset': '数字资产',
            'platform_privilege': '平台特权',
            'physical_goods': '实物商品',
        }
        source_names = {
            'community_fund': '社区基金',
            'earn': '积分兑换',
            'purchase': '购买',
            'promotion': '活动奖励',
        }

        return [
            right.get('id', '')[:16],
            right.get('name', ''),
            right_type_names.get(right.get('right_type', ''), right.get('right_type', '')),
            source_names.get(right.get('source', ''), right.get('source', '')),
            right.get('granted_at', '')[:10] if right.get('granted_at') else '-',
            right.get('expires_at', '')[:10] if right.get('expires_at') else '永久',
            '有效' if not right.get('is_expired') else '已过期',
            '不可转让/不可变现',
        ]


class CommunityRightsPanel(QWidget):
    """
    社区权益中心面板

    功能：
    1. 我的权益 - 查看用户所有权益
    2. 权益商店 - 查看可兑换权益
    3. 基金报告 - 查看社区基金状态
    4. 税务透明 - 查看税务信息
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.manager = None
        self.current_user_id = "default_user"  # TODO: 接入真实用户系统
        self._init_ui()
        self._init_manager()

    def _init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)

        # 标题栏
        title_bar = QHBoxLayout()
        title = QLabel("🏛️ 社区共建者权益中心")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        title_bar.addWidget(title)
        title_bar.addStretch()

        # 刷新按钮
        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.clicked.connect(self._refresh_data)
        title_bar.addWidget(self.refresh_btn)

        main_layout.addLayout(title_bar)

        # 标签页
        self.tabs = QTabWidget()

        # 1. 我的权益页
        self.my_rights_tab = self._create_my_rights_tab()
        self.tabs.addTab(self.my_rights_tab, "📋 我的权益")

        # 2. 权益商店页
        self.store_tab = self._create_store_tab()
        self.tabs.addTab(self.store_tab, "🏪 权益商店")

        # 3. 基金报告页
        self.fund_tab = self._create_fund_tab()
        self.tabs.addTab(self.fund_tab, "💰 基金报告")

        # 4. 税务透明页
        self.tax_tab = self._create_tax_tab()
        self.tabs.addTab(self.tax_tab, "📜 税务透明")

        main_layout.addWidget(self.tabs)

        # 状态栏
        self.status_bar = QLabel("就绪")
        self.status_bar.setStyleSheet("color: gray; padding: 5px;")
        main_layout.addWidget(self.status_bar)

        self.setLayout(main_layout)

    def _create_my_rights_tab(self) -> QWidget:
        """创建我的权益页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 统计卡片
        stats_layout = QHBoxLayout()

        # 权益总数
        self.total_rights_card = self._create_stat_card("总权益数", "0", "#4CAF50")
        stats_layout.addWidget(self.total_rights_card)

        # 服务配额
        self.service_card = self._create_stat_card("服务配额", "0", "#2196F3")
        stats_layout.addWidget(self.service_card)

        # 数字资产
        self.digital_card = self._create_stat_card("数字资产", "0", "#FF9800")
        stats_layout.addWidget(self.digital_card)

        # 平台特权
        self.privilege_card = self._create_stat_card("平台特权", "0", "#9C27B0")
        stats_layout.addWidget(self.privilege_card)

        layout.addLayout(stats_layout)

        # 权益列表
        list_label = QLabel("📜 权益列表")
        list_label.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        layout.addWidget(list_label)

        self.rights_table = QTableWidget()
        self.rights_table.setColumns(RightsTableModel.COLUMNS)
        self.rights_table.setColumnCount(len(RightsTableModel.COLUMNS))
        self.rights_table.setHorizontalHeaderLabels(RightsTableModel.COLUMNS)
        self.rights_table.setAlternatingRowColors(True)
        self.rights_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.rights_table)

        # 筛选栏
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("筛选:"))

        self.filter_combo = QComboBox()
        self.filter_combo.addItems(['全部', '服务配额', '数字资产', '平台特权', '实物商品'])
        self.filter_combo.currentTextChanged.connect(self._filter_rights)
        filter_layout.addWidget(self.filter_combo)

        self.include_expired_cb = QPushButton("显示过期权益")
        self.include_expired_cb.setCheckable(True)
        self.include_expired_cb.clicked.connect(self._refresh_data)
        filter_layout.addWidget(self.include_expired_cb)

        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        return widget

    def _create_store_tab(self) -> QWidget:
        """创建权益商店页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 商店说明
        notice = QLabel(
            "🏪 权益商店\n"
            "• 所有权益仅限本人使用，不可转让、不可交易、不可变现\n"
            "• 权益由平台赠予，具体发放以平台通知为准\n"
            "• 如有疑问请联系客服"
        )
        notice.setStyleSheet("""
            background: #E3F2FD;
            border: 1px solid #2196F3;
            border-radius: 5px;
            padding: 10px;
        """)
        layout.addWidget(notice)

        # 权益网格
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        self.store_layout = QGridLayout(container)

        scroll.setWidget(container)
        layout.addWidget(scroll)

        return widget

    def _create_fund_tab(self) -> QWidget:
        """创建基金报告页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 分配规则说明
        rules_group = QGroupBox("💰 基金分配规则")
        rules_layout = QVBoxLayout()

        rules = [
            ("👥 用户回馈", "50%", "根据贡献积分分配数字权益"),
            ("🚀 平台发展", "30%", "用于功能研发和基础设施"),
            ("📦 运营储备", "20%", "应对突发情况和未来发展"),
        ]

        for name, ratio, desc in rules:
            row = QHBoxLayout()
            row.addWidget(QLabel(f"<b>{name}</b>"))
            ratio_label = QLabel(f"<font color='blue'>{ratio}</font>")
            ratio_label.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
            row.addWidget(ratio_label)
            row.addWidget(QLabel(desc))
            row.addStretch()
            rules_layout.addLayout(row)

        rules_group.setLayout(rules_layout)
        layout.addWidget(rules_group)

        # 账户状态
        self.fund_status = QTextEdit()
        self.fund_status.setReadOnly(True)
        self.fund_status.setMaximumHeight(150)
        self.fund_status.setPlaceholderText("基金账户状态将显示在这里...")
        layout.addWidget(self.fund_status)

        # 历史报告
        history_label = QLabel("📊 历史基金报告")
        history_label.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        layout.addWidget(history_label)

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(5)
        self.history_table.setHorizontalHeaderLabels(['期间', '总盈利', '用户回馈', '税务支出', '状态'])
        layout.addWidget(self.history_table)

        return widget

    def _create_tax_tab(self) -> QWidget:
        """创建税务透明页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 税务说明
        tax_notice = QLabel(
            "📜 税务透明说明\n\n"
            "本平台采用「赠予」税务模式：\n"
            "• 平台作为赠予方，承担所有税款\n"
            "• 用户获得的是税后权益，无需额外缴税\n"
            "• 税务信息透明公开，可审计追溯\n\n"
            "依据：《个人所得税法》偶然所得相关规定"
        )
        tax_notice.setStyleSheet("""
            background: #FFF3E0;
            border: 1px solid #FF9800;
            border-radius: 5px;
            padding: 15px;
        """)
        layout.addWidget(tax_notice)

        # 税务预览
        preview_group = QGroupBox("🔍 权益税务预览")
        preview_layout = QFormLayout()

        self.tax_preview_combo = QComboBox()
        self.tax_preview_combo.currentTextChanged.connect(self._update_tax_preview)
        preview_layout.addRow("选择权益:", self.tax_preview_combo)

        self.tax_preview_text = QTextEdit()
        self.tax_preview_text.setReadOnly(True)
        self.tax_preview_text.setMaximumHeight(150)
        preview_layout.addRow("税务信息:", self.tax_preview_text)

        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)

        # 税务历史
        history_label = QLabel("📊 税务申报历史")
        history_label.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        layout.addWidget(history_label)

        self.tax_history = QTextEdit()
        self.tax_history.setReadOnly(True)
        layout.addWidget(self.tax_history)

        return widget

    def _create_stat_card(self, title: str, value: str, color: str) -> QFrame:
        """创建统计卡片"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: white;
                border: 2px solid {color};
                border-radius: 8px;
                padding: 10px;
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title_label = QLabel(title)
        title_label.setStyleSheet("color: gray;")
        layout.addWidget(title_label)

        value_label = QLabel(value)
        value_label.setFont(QFont("Microsoft YaHei", 20, QFont.Weight.Bold))
        value_label.setStyleSheet(f"color: {color};")
        layout.addWidget(value_label)

        return card

    def _init_manager(self):
        """初始化管理器"""
        try:
            from client.src.business.community_rights import get_community_rights_manager
            self.manager = get_community_rights_manager()
            self._refresh_data()
        except Exception as e:
            self.status_bar.setText(f"初始化失败: {str(e)}")

    async def _refresh_data(self):
        """刷新数据"""
        if not self.manager:
            return

        self.status_bar.setText("正在刷新...")
        self.refresh_btn.setEnabled(False)

        try:
            # 获取用户权益
            include_expired = self.include_expired_cb.isChecked()
            rights = await self.manager.get_user_rights(self.current_user_id, include_expired)

            # 更新统计卡片
            total = len(rights)
            service = sum(1 for r in rights if r.right_type.value == 'service_quota')
            digital = sum(1 for r in rights if r.right_type.value == 'digital_asset')
            privilege = sum(1 for r in rights if r.right_type.value == 'platform_privilege')

            self.total_rights_card.findChildren(QLabel)[1].setText(str(total))
            self.service_card.findChildren(QLabel)[1].setText(str(service))
            self.digital_card.findChildren(QLabel)[1].setText(str(digital))
            self.privilege_card.findChildren(QLabel)[1].setText(str(privilege))

            # 更新表格
            self.rights_table.setRowCount(len(rights))
            for i, right in enumerate(rights):
                items = RightsTableModel.format_right(right.to_dict())
                for j, item_text in enumerate(items):
                    item = QTableWidgetItem(item_text)
                    if j == 6:  # 状态列
                        if '已过期' in item_text:
                            item.setBackground(QColor('#FFCDD2'))
                        else:
                            item.setBackground(QColor('#C8E6C9'))
                    self.rights_table.setItem(i, j, item)

            # 更新商店
            self._refresh_store()

            # 更新基金状态
            await self._refresh_fund_status()

            # 更新税务预览
            definitions = self.manager.get_right_definitions()
            self.tax_preview_combo.clear()
            for d in definitions:
                self.tax_preview_combo.addItem(f"{d['name']} (¥{d['cost']:.2f})", d['id'])

            self.status_bar.setText(f"已加载 {total} 项权益")
            self.refresh_btn.setEnabled(True)

        except Exception as e:
            self.status_bar.setText(f"刷新失败: {str(e)}")
            self.refresh_btn.setEnabled(True)

    def _refresh_store(self):
        """刷新商店"""
        if not self.manager:
            return

        definitions = self.manager.get_right_definitions()

        # 清除现有商品
        while self.store_layout.count():
            item = self.store_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 添加商品卡片
        for i, d in enumerate(definitions):
            card = self._create_store_item(d)
            row = i // 3
            col = i % 3
            self.store_layout.addWidget(card, row, col)

    def _create_store_item(self, definition: Dict) -> QFrame:
        """创建商店商品卡片"""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #E0E0E0;
                border-radius: 8px;
                padding: 15px;
            }
            QFrame:hover {
                border: 2px solid #4CAF50;
            }
        """)

        layout = QVBoxLayout(card)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 图标
        type_icons = {
            'service_quota': '⚡',
            'digital_asset': '🎨',
            'platform_privilege': '👑',
            'physical_goods': '📦',
        }
        icon_label = QLabel(type_icons.get(definition['type'], '📦'))
        icon_label.setFont(QFont("Microsoft YaHei", 30))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        # 名称
        name_label = QLabel(f"<b>{definition['name']}</b>")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name_label)

        # 描述
        desc_label = QLabel(definition['description'][:30] + "...")
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(desc_label)

        # 成本
        cost_label = QLabel(f"平台成本: ¥{definition['cost']:.2f}")
        cost_label.setStyleSheet("color: #4CAF50;")
        cost_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(cost_label)

        # 状态
        if definition['cost'] == 0:
            status = QLabel("🎁 赠予")
            status.setStyleSheet("background: #4CAF50; color: white; border-radius: 3px; padding: 2px 8px;")
        else:
            status = QLabel("⏳ 待开放")
            status.setStyleSheet("background: #FFC107; color: white; border-radius: 3px; padding: 2px 8px;")
        status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(status)

        return card

    def _filter_rights(self, filter_text: str):
        """筛选权益"""
        if not hasattr(self, '_all_rights'):
            return

        type_map = {
            '全部': None,
            '服务配额': 'service_quota',
            '数字资产': 'digital_asset',
            '平台特权': 'platform_privilege',
            '实物商品': 'physical_goods',
        }

        target_type = type_map.get(filter_text)
        filtered = self._all_rights

        if target_type:
            filtered = [r for r in filtered if r.right_type.value == target_type]

        self.rights_table.setRowCount(len(filtered))
        for i, right in enumerate(filtered):
            items = RightsTableModel.format_right(right.to_dict())
            for j, item_text in enumerate(items):
                item = QTableWidgetItem(item_text)
                self.rights_table.setItem(i, j, item)

    async def _refresh_fund_status(self):
        """刷新基金状态"""
        if not self.manager:
            return

        try:
            fund_status = await self.manager.fund.get_fund_status()
            status_text = "【基金账户状态】\n\n"

            for purpose, data in fund_status.get('accounts', {}).items():
                status_text += f"• {purpose}: 余额 ¥{data['balance']:.2f}\n"
                status_text += f"  累计流入: ¥{data['total_inflow']:.2f}\n"
                status_text += f"  累计流出: ¥{data['total_outflow']:.2f}\n\n"

            self.fund_status.setPlainText(status_text)
        except Exception as e:
            self.fund_status.setPlainText(f"获取基金状态失败: {str(e)}")

    def _update_tax_preview(self, combo_text: str):
        """更新税务预览"""
        if not self.manager:
            return

        try:
            data = self.tax_preview_combo.currentData()
            if not data:
                return

            tax_info = self.manager.get_tax_preview(data)
            if tax_info:
                preview = f"【{combo_text}的税务信息】\n\n"
                preview += "展示信息:\n"
                for k, v in tax_info.get('展示信息', {}).items():
                    preview += f"  • {k}: {v}\n"
                preview += "\n税务说明:\n"
                for k, v in tax_info.get('税务说明', {}).items():
                    preview += f"  • {k}: {v}\n"
                preview += f"\n合规提示: {tax_info.get('合规提示', '')}"

                self.tax_preview_text.setPlainText(preview)
        except Exception as e:
            self.tax_preview_text.setPlainText(f"预览失败: {str(e)}")


# 便捷函数
def create_community_rights_panel() -> CommunityRightsPanel:
    """创建社区权益面板"""
    return CommunityRightsPanel()
