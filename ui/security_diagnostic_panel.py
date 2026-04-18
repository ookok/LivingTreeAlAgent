# ui/security_diagnostic_panel.py
# 安全助手诊断面板 - 内嵌式诊断工具

"""
安全助手诊断面板

功能：
1. 实时安全状态显示
2. 一键诊断
3. 问题快速修复
4. 诊断报告导出
"""

import sys
from pathlib import Path
from typing import Optional

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QProgressBar, QGroupBox, QListWidget,
    QListWidgetItem, QScrollArea, QFrame, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
    QMessageBox, QToolButton
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor

import logging
logger = logging.getLogger(__name__)


class SecurityDiagnosticPanel(QWidget):
    """
    安全助手诊断面板

    可以嵌入到主窗口设置页面中
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(400)

        self._init_ui()
        self._start_auto_refresh()

    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        layout.setSpacing(10)

        # 标题栏
        title_layout = QHBoxLayout()
        title = QLabel("🛡️ 安全助手")
        title.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        title_layout.addWidget(title)
        title_layout.addStretch()

        self.btn_refresh = QPushButton("🔄 刷新")
        self.btn_refresh.clicked.connect(self.run_diagnostic)
        title_layout.addWidget(self.btn_refresh)

        self.btn_fix = QPushButton("🔧 一键修复")
        self.btn_fix.clicked.connect(self.one_click_fix)
        title_layout.addWidget(self.btn_fix)

        layout.addLayout(title_layout)

        # 安全状态卡片
        self.status_card = self._create_status_card()
        layout.addWidget(self.status_card)

        # Tab 页
        tabs = QTabWidget()

        # 诊断结果 Tab
        tabs.addTab(self._create_diagnostic_tab(), "📊 诊断结果")

        # 防火墙 Tab
        tabs.addTab(self._create_firewall_tab(), "🛡️ 防火墙")

        # 杀毒软件 Tab
        tabs.addTab(self._create_antivirus_tab(), "🔐 杀毒软件")

        # 行为日志 Tab
        tabs.addTab(self._create_log_tab(), "📋 行为日志")

        layout.addWidget(tabs)

        self.setLayout(layout)

    def _create_status_card(self) -> QFrame:
        """创建状态卡片"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.StyledPanel)
        frame.setStyleSheet("""
            QFrame {
                background-color: #f8f8f8;
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 15px;
            }
        """)

        layout = QVBoxLayout()

        # 状态行
        status_layout = QHBoxLayout()

        self.status_icon = QLabel("⏳")
        self.status_icon.setStyleSheet("font-size: 24px;")
        status_layout.addWidget(self.status_icon)

        status_text_layout = QVBoxLayout()
        self.status_title = QLabel("正在检查安全状态...")
        self.status_title.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        status_text_layout.addWidget(self.status_title)

        self.status_desc = QLabel("请稍候")
        self.status_desc.setStyleSheet("color: #666;")
        status_text_layout.addWidget(self.status_desc)

        status_layout.addLayout(status_text_layout)
        status_layout.addStretch()

        layout.addLayout(status_layout)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumHeight(6)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                background-color: #e0e0e0;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)

        frame.setLayout(layout)
        return frame

    def _create_diagnostic_tab(self) -> QWidget:
        """创建诊断结果 Tab"""
        widget = QWidget()
        layout = QVBoxLayout()

        # 问题列表
        self.problem_list = QListWidget()
        self.problem_list.setAlternatingRowColors(True)
        layout.addWidget(QLabel("<b>发现的问题:</b>"))
        layout.addWidget(self.problem_list)

        # 建议列表
        layout.addWidget(QLabel("<b>修复建议:</b>"))
        self.suggestion_list = QListWidget()
        layout.addWidget(self.suggestion_list)

        # 导出按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_export = QPushButton("📥 导出诊断报告")
        self.btn_export.clicked.connect(self.export_report)
        btn_layout.addWidget(self.btn_export)

        layout.addLayout(btn_layout)

        widget.setLayout(layout)
        return widget

    def _create_firewall_tab(self) -> QWidget:
        """创建防火墙 Tab"""
        widget = QWidget()
        layout = QVBoxLayout()

        # 状态显示
        self.fw_status = QLabel("正在检查...")
        layout.addWidget(self.fw_status)

        # 规则列表
        layout.addWidget(QLabel("<b>防火墙规则:</b>"))
        self.fw_rules = QListWidget()
        layout.addWidget(self.fw_rules)

        # 操作按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_add_fw = QPushButton("➕ 添加规则")
        self.btn_add_fw.clicked.connect(self.add_firewall_rules)
        btn_layout.addWidget(self.btn_add_fw)

        self.btn_check_fw = QPushButton("🔍 检查")
        self.btn_check_fw.clicked.connect(self.check_firewall)
        btn_layout.addWidget(self.btn_check_fw)

        layout.addLayout(btn_layout)

        widget.setLayout(layout)
        return widget

    def _create_antivirus_tab(self) -> QWidget:
        """创建杀毒软件 Tab"""
        widget = QWidget()
        layout = QVBoxLayout()

        # 检测结果
        self.av_status = QLabel("正在检测...")
        layout.addWidget(self.av_status)

        # 信任指南
        layout.addWidget(QLabel("<b>信任设置步骤:</b>"))
        self.av_steps = QTextEdit()
        self.av_steps.setReadOnly(True)
        self.av_steps.setMaximumHeight(150)
        layout.addWidget(self.av_steps)

        # 操作按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_open_av = QPushButton("🔗 打开设置")
        self.btn_open_av.clicked.connect(self.open_antivirus_settings)
        btn_layout.addWidget(self.btn_open_av)

        self.btn_defender_exclude = QPushButton("🛡️ Defender排除")
        self.btn_defender_exclude.clicked.connect(self.add_defender_exclusion)
        btn_layout.addWidget(self.btn_defender_exclude)

        layout.addLayout(btn_layout)

        widget.setLayout(layout)
        return widget

    def _create_log_tab(self) -> QWidget:
        """创建行为日志 Tab"""
        widget = QWidget()
        layout = QVBoxLayout()

        # 日志过滤器
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("筛选:"))
        self.log_filter = QCheckBox("只看高风险")
        self.log_filter.stateChanged.connect(self.filter_logs)
        filter_layout.addWidget(self.log_filter)
        filter_layout.addStretch()

        layout.addLayout(filter_layout)

        # 日志列表
        self.log_list = QListWidget()
        self.log_list.setAlternatingRowColors(True)
        layout.addWidget(self.log_list)

        # 导出按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_export_logs = QPushButton("📥 导出日志")
        self.btn_export_logs.clicked.connect(self.export_logs)
        btn_layout.addWidget(self.btn_export_logs)

        layout.addLayout(btn_layout)

        widget.setLayout(layout)
        return widget

    def _start_auto_refresh(self):
        """启动自动刷新"""
        QTimer.singleShot(1000, self.run_diagnostic)

    def run_diagnostic(self):
        """运行诊断"""
        from core.security import (
            get_security_manager,
            get_firewall_manager,
            get_antivirus_helper,
            get_behavior_monitor,
            SecurityLevel,
        )

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(20)
        self.status_title.setText("正在检查防火墙...")
        QApplication.processEvents()

        try:
            # 获取各模块状态
            sec_mgr = get_security_manager()
            fw_mgr = get_firewall_manager()
            av_helper = get_antivirus_helper()
            behavior_mgr = get_behavior_monitor()

            # 安全状态
            sec_status = sec_mgr.get_status()
            self.progress_bar.setValue(40)

            # 防火墙状态
            fw_status = fw_mgr.get_firewall_status()
            self.progress_bar.setValue(60)

            # 杀毒软件
            av_stat, av_products = av_helper.get_antivirus_status()
            self.progress_bar.setValue(80)

            # 行为日志
            recent_events = behavior_mgr.get_events(limit=20)
            self.progress_bar.setValue(100)

            # 更新 UI
            self._update_status_card(sec_status)
            self._update_firewall_tab(fw_status)
            self._update_antivirus_tab(av_stat, av_products, av_helper)
            self._update_log_tab(recent_events)

            # 更新问题列表
            self._update_problems(sec_status, fw_status, av_stat)

            self.progress_bar.setVisible(False)

        except Exception as e:
            logger.error(f"安全诊断失败: {e}")
            self.status_title.setText("诊断失败")
            self.status_desc.setText(str(e))
            self.progress_bar.setVisible(False)

    def _update_status_card(self, status):
        """更新状态卡片"""
        from core.security import SecurityLevel

        level = status.level

        if level == SecurityLevel.TRUSTED:
            self.status_icon.setText("✅")
            self.status_title.setText("安全状态: 良好")
            self.status_desc.setText("所有安全检查通过")
            self.status_card.setStyleSheet("""
                QFrame {
                    background-color: #e8f5e9;
                    border: 1px solid #4CAF50;
                    border-radius: 8px;
                    padding: 15px;
                }
            """)
        elif level == SecurityLevel.PARTIAL:
            self.status_icon.setText("⚠️")
            self.status_title.setText("安全状态: 需要注意")
            self.status_desc.setText(f"发现 {len(status.issues)} 个问题")
            self.status_card.setStyleSheet("""
                QFrame {
                    background-color: #fff3e0;
                    border: 1px solid #ff9800;
                    border-radius: 8px;
                    padding: 15px;
                }
            """)
        else:
            self.status_icon.setText("❌")
            self.status_title.setText("安全状态: 存在风险")
            self.status_desc.setText(f"发现 {len(status.issues)} 个严重问题")
            self.status_card.setStyleSheet("""
                QFrame {
                    background-color: #ffebee;
                    border: 1px solid #f44336;
                    border-radius: 8px;
                    padding: 15px;
                }
            """)

    def _update_firewall_tab(self, fw_status):
        """更新防火墙 Tab"""
        self.fw_rules.clear()

        if fw_status.get("is_admin"):
            self.fw_status.setText(
                f"<span style='color: green;'>✅ 管理员权限 | 防火墙已启用</span>"
            )
        else:
            self.fw_status.setText(
                "<span style='color: orange;'>⚠️ 需要管理员权限</span>"
            )

        for rule in fw_status.get("app_rules", []):
            name = rule.get("DisplayName", "Unknown")
            enabled = "✓" if rule.get("Enabled") else "✗"
            self.fw_rules.addItem(f"{enabled} {name}")

    def _update_antivirus_tab(self, av_status, products, helper):
        """更新杀毒软件 Tab"""
        from core.security import AntivirusStatus

        if products:
            names = [p.name for p in products]
            self.av_status.setText(
                f"<span style='color: green;'>✅ 检测到: {', '.join(names)}</span>"
            )

            # 显示信任步骤
            guide = helper.get_trust_guide(products[0].name)
            if guide:
                steps_html = f"<h4>{guide.antivirus_name}:</h4><ol>"
                for step in guide.steps:
                    steps_html += f"<li>{step}</li>"
                steps_html += "</ol>"
                self.av_steps.setHtml(steps_html)
        else:
            self.av_status.setText("<span style='color: orange;'>⚠️ 未检测到杀毒软件</span>")
            self.av_steps.setHtml("<p>建议启用杀毒软件保护系统安全</p>")

    def _update_log_tab(self, events):
        """更新日志 Tab"""
        self.log_list.clear()

        for event in events:
            from core.security import RiskLevel

            risk_color = {
                RiskLevel.NONE: "#999",
                RiskLevel.LOW: "#4CAF50",
                RiskLevel.MEDIUM: "#ff9800",
                RiskLevel.HIGH: "#f44336",
                RiskLevel.CRITICAL: "#9c27b0",
            }.get(event.risk_level, "#999")

            time_str = event.timestamp.strftime("%H:%M:%S")
            text = f"<span style='color: #666;'>[{time_str}]</span> "
            text += f"<span style='color: {risk_color};'>[{event.risk_level.value}]</span> "
            text += f"{event.description}"

            item = QListWidgetItem(text)
            self.log_list.addItem(item)

    def _update_problems(self, sec_status, fw_status, av_status):
        """更新问题列表"""
        from core.security import AntivirusStatus, FirewallStatus

        self.problem_list.clear()
        self.suggestion_list.clear()

        # 防火墙问题
        if not fw_status.get("is_admin"):
            self.problem_list.addItem("⚠️ 需要管理员权限修改防火墙")
            self.suggestion_list.addItem("💡 请以管理员身份运行应用")

        # 杀毒软件问题
        if av_status == AntivirusStatus.NOT_INSTALLED:
            self.problem_list.addItem("⚠️ 未检测到杀毒软件")
            self.suggestion_list.addItem("💡 建议安装杀毒软件保护系统")

        # 安全级别问题
        if sec_status.issues:
            for issue in sec_status.issues:
                self.problem_list.addItem(f"⚠️ {issue}")

        if sec_status.recommendations:
            for rec in sec_status.recommendations:
                self.suggestion_list.addItem(f"💡 {rec}")

        if self.problem_list.count() == 0:
            self.problem_list.addItem("✅ 未发现安全问题")

    def one_click_fix(self):
        """一键修复"""
        from core.security import get_firewall_manager, get_security_manager

        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setWindowTitle("一键修复")
        msg.setText("即将执行以下操作:\n\n1. 添加防火墙规则 (需要管理员)\n2. 添加 Windows Defender 排除项\n\n是否继续?")

        if msg.exec() == QMessageBox.StandardButton.Ok:
            try:
                # 添加防火墙规则
                fw_mgr = get_firewall_manager()
                if fw_mgr.is_admin():
                    success, msg_text = fw_mgr.add_app_rules()
                    logger.info(f"防火墙规则添加: {msg_text}")

                # 添加 Defender 排除
                from core.security import get_antivirus_helper
                av_helper = get_antivirus_helper()
                av_helper.add_to_defender_exclusions(
                    get_security_manager().config.app_data_dir
                )

                QMessageBox.information(
                    self,
                    "修复完成",
                    "安全修复已完成，请重新运行诊断检查结果。"
                )

                self.run_diagnostic()

            except Exception as e:
                QMessageBox.warning(self, "修复失败", f"修复过程中出错: {e}")

    def add_firewall_rules(self):
        """添加防火墙规则"""
        from core.security import get_firewall_manager

        fw_mgr = get_firewall_manager()

        if not fw_mgr.is_admin():
            QMessageBox.warning(
                self,
                "权限不足",
                "需要管理员权限。请以管理员身份运行应用。"
            )
            return

        success, msg = fw_mgr.add_app_rules()

        if success:
            QMessageBox.information(self, "成功", msg)
            self.run_diagnostic()
        else:
            QMessageBox.warning(self, "失败", msg)

    def check_firewall(self):
        """检查防火墙"""
        self.run_diagnostic()

    def open_antivirus_settings(self):
        """打开杀毒软件设置"""
        from core.security import get_antivirus_helper

        helper = get_antivirus_helper()
        products = helper.detect_antivirus()

        if products:
            helper.open_trust_settings(products[0].name)
        else:
            QMessageBox.information(
                self,
                "提示",
                "请手动打开杀毒软件，添加 Living Tree AI 到信任列表。"
            )

    def add_defender_exclusion(self):
        """添加 Defender 排除"""
        from core.security import get_antivirus_helper, get_security_manager

        helper = get_antivirus_helper()
        sec_mgr = get_security_manager()

        success, msg = helper.add_to_defender_exclusions(sec_mgr.config.app_data_dir)

        if success:
            QMessageBox.information(self, "成功", msg)
        else:
            QMessageBox.warning(self, "失败", msg)

    def filter_logs(self):
        """过滤日志"""
        # 重新运行诊断以刷新日志
        self.run_diagnostic()

    def export_report(self):
        """导出诊断报告"""
        from core.security import get_security_manager
        import json

        try:
            sec_mgr = get_security_manager()
            report = sec_mgr.get_security_report()

            # 生成文件
            from PyQt6.QtWidgets import QFileDialog
            path, _ = QFileDialog.getSaveFileName(
                self,
                "保存诊断报告",
                f"security_report_{sec_mgr._last_check.strftime('%Y%m%d_%H%M%S')}.json",
                "JSON Files (*.json)"
            )

            if path:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(report, f, ensure_ascii=False, indent=2)

                QMessageBox.information(self, "导出成功", f"报告已保存到:\n{path}")

        except Exception as e:
            QMessageBox.warning(self, "导出失败", str(e))

    def export_logs(self):
        """导出日志"""
        from core.security import get_behavior_monitor
        import json

        try:
            monitor = get_behavior_monitor()
            events = [e.to_dict() for e in monitor._events]

            from PyQt6.QtWidgets import QFileDialog
            path, _ = QFileDialog.getSaveFileName(
                self,
                "保存行为日志",
                "behavior_logs.json",
                "JSON Files (*.json)"
            )

            if path:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(events, f, ensure_ascii=False, indent=2)

                QMessageBox.information(self, "导出成功", f"日志已保存到:\n{path}")

        except Exception as e:
            QMessageBox.warning(self, "导出失败", str(e))


# 独立的诊断窗口
class SecurityDiagnosticWindow(QWidget):
    """独立的安全诊断窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Living Tree AI - 安全助手")
        self.setMinimumSize(700, 500)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.panel = SecurityDiagnosticPanel()
        layout.addWidget(self.panel)

        self.setLayout(layout)


def show_security_diagnostic():
    """显示安全诊断窗口"""
    from PyQt6.QtWidgets import QApplication
    import sys

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    window = SecurityDiagnosticWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    show_security_diagnostic()