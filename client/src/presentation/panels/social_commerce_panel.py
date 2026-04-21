# ui/social_commerce_panel.py
# 社交化撮合引擎 UI 面板

from typing import List, Dict, Optional
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QFrame, QGroupBox,
    QTextEdit, QProgressBar, QTabWidget, QComboBox,
    QSpinBox, QTableWidget, QTableWidgetItem, QHeaderView,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
import logging

logger = logging.getLogger(__name__)


class MatchCandidateCard(QFrame):
    """匹配候选卡片"""
    clicked = pyqtSignal(str)

    STRENGTH_COLORS = {
        "PERFECT": "#4CAF50",
        "STRONG": "#8BC34A",
        "MEDIUM": "#FFC107",
        "WEAK": "#9E9E9E",
    }

    def __init__(self, candidate: Dict, parent=None):
        super().__init__(parent)
        self.candidate_id = candidate.get("id", "")
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            QFrame { background-color: #f8f8f8; border: 1px solid #ddd;
                     border-radius: 8px; padding: 10px; margin: 5px; }
            QFrame:hover { border-color: #4CAF50; background-color: #f0f8f0; }
        """)
        self._build_ui(candidate)

    def _build_ui(self, c: Dict):
        layout = QVBoxLayout()
        # 匹配强度
        strength = c.get("match_strength", "MEDIUM")
        color = self.STRENGTH_COLORS.get(strength, "#9E9E9E")
        layout.addWidget(QLabel(
            f"<span style='color: {color};'>●</span> <b>{strength}</b> "
            f"| 📍{c.get('geo_score', 0):.0%} ⏰{c.get('time_score', 0):.0%}"
        ))
        # 商品
        if c.get("buyer_wants"):
            layout.addWidget(QLabel(f"<b>买家:</b> {', '.join(c['buyer_wants'][:3])}"))
        if c.get("seller_offers"):
            layout.addWidget(QLabel(f"<b>卖家:</b> {', '.join(c['seller_offers'][:3])}"))
        # 原因
        reasons = c.get("match_reasons", [])
        if reasons:
            layout.addWidget(QLabel(f"<span style='color:#666;'>原因: {', '.join(reasons[:2])}</span>"))
        # 按钮
        btn = QPushButton("🤝 连接")
        btn.clicked.connect(lambda: self.clicked.emit(self.candidate_id))
        layout.addWidget(btn)
        self.setLayout(layout)


class SocialCommercePanel(QWidget):
    """社交化撮合引擎面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._start_refresh_timer()

    def _init_ui(self):
        layout = QVBoxLayout()
        # 标题
        title = QLabel("🔮 智能撮合引擎")
        title.setFont(QFont("Microsoft YaHei", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(self._create_market_tab(), "🎯 匹配广场")
        tabs.addTab(self._create_sessions_tab(), "💬 会话")
        tabs.addTab(self._create_credit_tab(), "⭐ 信用")
        layout.addWidget(tabs)
        self.setLayout(layout)

    def _create_market_tab(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout()
        # 筛选
        fl = QHBoxLayout()
        fl.addWidget(QLabel("筛选:"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["全部", "🔥 强匹配", "📍 附近", "⏰ 即时可交易"])
        fl.addWidget(self.filter_combo)
        fl.addStretch()
        l.addLayout(fl)
        # 统计
        self.stats_label = QLabel("暂无数据")
        self.stats_label.setStyleSheet("color:#666;padding:5px;")
        l.addWidget(self.stats_label)
        # 列表
        self.match_list = QListWidget()
        l.addWidget(self.match_list)
        # 详情
        self.match_detail = QTextEdit()
        self.match_detail.setReadOnly(True)
        self.match_detail.setMaximumHeight(120)
        l.addWidget(self.match_detail)
        # 按钮
        bl = QHBoxLayout()
        self.btn_create = QPushButton("🤝 创建撮合")
        self.btn_create.clicked.connect(self._do_create_match)
        bl.addWidget(self.btn_create)
        l.addLayout(bl)
        w.setLayout(l)
        return w

    def _create_sessions_tab(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout()
        self.session_list = QListWidget()
        l.addWidget(self.session_list)
        self.session_detail = QTextEdit()
        self.session_detail.setReadOnly(True)
        self.session_detail.setMaximumHeight(150)
        l.addWidget(self.session_detail)
        bl = QHBoxLayout()
        for txt, slot in [("✅ 接受", self._do_accept), ("💰 报价", self._do_offer),
                          ("🤝 成交", self._do_confirm), ("❌ 取消", self._do_cancel)]:
            btn = QPushButton(txt)
            btn.clicked.connect(slot)
            bl.addWidget(btn)
        l.addLayout(bl)
        w.setLayout(l)
        return w

    def _create_credit_tab(self) -> QWidget:
        w = QWidget()
        l = QVBoxLayout()
        # 信用分卡片
        g = QGroupBox("我的信用")
        gl = QVBoxLayout()
        self.credit_label = QLabel("信用分: --")
        self.credit_label.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        gl.addWidget(self.credit_label)
        self.credit_bar = QProgressBar()
        self.credit_bar.setMaximum(100)
        gl.addWidget(self.credit_bar)
        self.expertise_label = QLabel("专长: --")
        gl.addWidget(self.expertise_label)
        g.setLayout(gl)
        l.addWidget(g)
        # 凭证链
        g2 = QGroupBox("凭证链")
        g2l = QVBoxLayout()
        self.chain_list = QListWidget()
        g2l.addWidget(self.chain_list)
        self.btn_verify = QPushButton("🔍 验证链")
        self.btn_verify.clicked.connect(self._do_verify)
        g2l.addWidget(self.btn_verify)
        g2.setLayout(g2l)
        l.addWidget(g2)
        l.addStretch()
        w.setLayout(l)
        return w

    def _start_refresh_timer(self):
        QTimer.singleShot(500, self.refresh_matches)

    def refresh_matches(self):
        """刷新匹配数据"""
        try:
            from core.social_commerce import get_matchmaking_engine, get_intent_radar
            engine = get_matchmaking_engine()
            radar = get_intent_radar()

            # 获取统计
            stats = engine.get_stats()
            self.stats_label.setText(
                f"总候选: {stats['total_sessions']} | "
                f"进行中: {stats['negotiating']} | "
                f"已完成: {stats['completed']}"
            )

            # 刷新信用
            self._refresh_credit()

        except Exception as e:
            logger.error(f"刷新匹配失败: {e}")
            self.stats_label.setText(f"加载失败: {e}")

    def _refresh_credit(self):
        """刷新信用显示"""
        try:
            from core.social_commerce import get_credit_network
            credit = get_credit_network()
            # 简化：显示总览
            self.credit_label.setText("信用分: 初始化中...")
            self.credit_bar.setValue(50)
            self.expertise_label.setText("专长: 待分析")
        except Exception as e:
            logger.error(f"刷新信用失败: {e}")

    def on_match_clicked(self, item: QListWidgetItem):
        """点击匹配候选"""
        self.match_detail.append(f"已选择候选: {item.text()}")

    def _do_create_match(self):
        QMessageBox.information(self, "提示", "请先在列表中选择匹配候选")

    def _do_accept(self):
        QMessageBox.information(self, "提示", "接受撮合")

    def _do_offer(self):
        QMessageBox.information(self, "提示", "报价功能")

    def _do_confirm(self):
        QMessageBox.information(self, "提示", "确认成交")

    def _do_cancel(self):
        QMessageBox.information(self, "提示", "取消会话")

    def _do_verify(self):
        QMessageBox.information(self, "验证", "链验证功能")


# 独立窗口
class SocialCommerceWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Living Tree AI - 社交化撮合引擎")
        self.setMinimumSize(800, 600)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(SocialCommercePanel())
        self.setLayout(layout)


def show_social_commerce_panel():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    w = SocialCommerceWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    show_social_commerce_panel()