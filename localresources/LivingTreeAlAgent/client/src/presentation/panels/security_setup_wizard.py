# ui/security_setup_wizard.py
# 安全设置向导 - 首次运行引导 UI

"""
安全设置向导 UI

功能：
1. 欢迎页面 - 介绍安全设置必要性
2. 防火墙设置 - 自动/手动添加防火墙规则
3. 杀毒软件信任 - 检测并引导用户信任
4. 安全状态总结 - 展示最终安全状态
"""

import sys
from pathlib import Path
from typing import Optional

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# PyQt6 导入
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QWizard, QWizardPage, QTextEdit, QCheckBox, QProgressBar,
    QListWidget, QListWidgetItem, QGroupBox, QScrollArea,
    QWidget, QStackedWidget, QMessageBox, QApplication
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QIcon, QPixmap, QColor, QTextCursor

# 日志
import logging
logger = logging.getLogger(__name__)


class SecurityCheckThread(QThread):
    """安全检查后台线程"""
    finished = pyqtSignal(dict)
    progress = pyqtSignal(str, int)

    def run(self):
        from core.security import (
            get_security_manager,
            get_firewall_manager,
            get_antivirus_helper,
        )

        results = {}

        self.progress.emit("正在检查防火墙...", 20)
        fw_manager = get_firewall_manager()
        results["firewall"] = fw_manager.get_firewall_status()

        self.progress.emit("正在检测杀毒软件...", 50)
        av_helper = get_antivirus_helper()
        status, products = av_helper.get_antivirus_status()
        results["antivirus"] = {
            "status": status.value,
            "products": [p.to_dict() for p in products],
        }

        self.progress.emit("正在评估安全级别...", 80)
        sec_manager = get_security_manager()
        results["security"] = sec_manager.get_security_report()

        self.progress.emit("检查完成", 100)
        self.finished.emit(results)


class WelcomePage(QWizardPage):
    """欢迎页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("欢迎使用 Living Tree AI 安全设置向导")
        self.setSubTitle("让我们确保应用能够正常运行")

        layout = QVBoxLayout()
        layout.setSpacing(20)

        # 欢迎图标
        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setText("🔒")
        icon_label.setStyleSheet("font-size: 72px;")
        layout.addWidget(icon_label)

        # 说明文本
        desc = QLabel(
            "<h3>为了确保 Living Tree AI 能够正常工作</h3>"
            "<p>我们需要进行以下安全设置：</p>"
            "<ul>"
            "<li>📡 <b>网络通信</b> - P2P 穿透与节点连接需要网络访问</li>"
            "<li>🛡️ <b>防火墙规则</b> - 添加例外让应用能够被其他节点发现</li>"
            "<li>🔐 <b>杀毒软件信任</b> - 防止安全软件误拦截应用</li>"
            "</ul>"
            "<p>这些设置只需要在首次运行时完成。</p>"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("""
            QLabel {
                background-color: #f5f5f5;
                border-radius: 8px;
                padding: 20px;
            }
        """)
        layout.addWidget(desc)

        # 不再显示选项
        self.chk_dont_show = QCheckBox("下次启动不再显示此向导")
        self.registerField("dontShow*", self.chk_dont_show)
        layout.addWidget(self.chk_dont_show)

        self.setLayout(layout)


class FirewallPage(QWizardPage):
    """防火墙设置页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("防火墙设置")
        self.setSubTitle("添加防火墙例外规则允许应用网络通信")

        layout = QVBoxLayout()
        layout.setSpacing(15)

        # 说明
        desc = QLabel(
            "<p>Living Tree AI 需要以下网络端口进行通信：</p>"
            "<table border='1' cellpadding='5' style='border-collapse: collapse;'>"
            "<tr><td><b>P2P 发现端口</b></td><td>UDP 40000-60000</td></tr>"
            "<tr><td><b>中继服务器</b></td><td>TCP 8766</td></tr>"
            "<tr><td><b>Web UI</b></td><td>TCP 8765</td></tr>"
            "<tr><td><b>局域网聊天</b></td><td>UDP 5000-5100</td></tr>"
            "</table>"
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # 状态显示
        self.status_label = QLabel("正在检查防火墙状态...")
        self.status_label.setStyleSheet("color: #666; padding: 10px;")
        layout.addWidget(self.status_label)

        # 规则列表
        self.rules_list = QListWidget()
        layout.addWidget(QLabel("当前防火墙规则:"))
        layout.addWidget(self.rules_list)

        # 按钮组
        btn_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("🔄 刷新状态")
        self.btn_refresh.clicked.connect(self.refresh_status)
        btn_layout.addWidget(self.btn_refresh)

        self.btn_add_rules = QPushButton("✅ 添加防火墙规则")
        self.btn_add_rules.clicked.connect(self.add_rules)
        self.btn_add_rules.setEnabled(False)
        btn_layout.addWidget(self.btn_add_rules)

        layout.addLayout(btn_layout)

        self.setLayout(layout)

        # 延迟刷新
        QTimer.singleShot(500, self.refresh_status)

    def refresh_status(self):
        """刷新防火墙状态"""
        from core.security import get_firewall_manager

        self.status_label.setText("正在检查...")
        QApplication.processEvents()

        try:
            manager = get_firewall_manager()
            status = manager.get_firewall_status()

            self.rules_list.clear()

            if status["is_admin"]:
                self.status_label.setText(
                    f"<span style='color: green;'>✅ 管理员权限</span> - 可以修改防火墙规则"
                )
                self.btn_add_rules.setEnabled(True)
            else:
                self.status_label.setText(
                    "<span style='color: orange;'>⚠️ 需要管理员权限</span> - 请以管理员身份运行应用"
                )
                self.btn_add_rules.setEnabled(False)

            for rule in status["app_rules"]:
                item = QListWidgetItem(f"✓ {rule.get('DisplayName', 'Unknown')}")
                self.rules_list.addItem(item)

        except Exception as e:
            self.status_label.setText(f"<span style='color: red;'>检查失败: {e}</span>")
            logger.error(f"防火墙状态检查失败: {e}")

    def add_rules(self):
        """添加防火墙规则"""
        from core.security import get_firewall_manager

        self.btn_add_rules.setEnabled(False)
        self.status_label.setText("正在添加防火墙规则...")

        try:
            manager = get_firewall_manager()
            success, message = manager.add_app_rules()

            if success:
                self.status_label.setText(f"<span style='color: green;'>✅ {message}</span>")
                self.refresh_status()
            else:
                self.status_label.setText(f"<span style='color: red;'>❌ {message}</span>")

        except Exception as e:
            self.status_label.setText(f"<span style='color: red;'>添加失败: {e}</span>")
            logger.error(f"添加防火墙规则失败: {e}")

        finally:
            self.btn_add_rules.setEnabled(True)


class AntivirusPage(QWizardPage):
    """杀毒软件信任页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("杀毒软件信任设置")
        self.setSubTitle("将 Living Tree AI 添加到杀毒软件信任列表")

        layout = QVBoxLayout()
        layout.setSpacing(15)

        # 检测结果
        self.detected_label = QLabel("正在检测杀毒软件...")
        self.detected_label.setStyleSheet("padding: 10px; background: #f0f0f0; border-radius: 5px;")
        layout.addWidget(self.detected_label)

        # 信任步骤
        self.steps_group = QGroupBox("信任设置步骤")
        steps_layout = QVBoxLayout()

        self.steps_text = QTextEdit()
        self.steps_text.setReadOnly(True)
        self.steps_text.setMaximumHeight(200)
        steps_layout.addWidget(self.steps_text)

        self.btn_open_settings = QPushButton("🔗 打开信任设置页面")
        self.btn_open_settings.clicked.connect(self.open_trust_settings)
        steps_layout.addWidget(self.btn_open_settings)

        self.steps_group.setLayout(steps_layout)
        layout.addWidget(self.steps_group)

        # 一键信任（仅 Windows Defender）
        self.btn_defender = QPushButton("🛡️ 一键添加到 Windows Defender 排除项")
        self.btn_defender.clicked.connect(self.add_to_defender)
        self.btn_defender.setVisible(False)
        layout.addWidget(self.btn_defender)

        # 完成确认
        self.chk_trusted = QCheckBox("我已添加 Living Tree AI 到信任列表")
        self.registerField("antivirusTrusted*", self.chk_trusted)
        layout.addWidget(self.chk_trusted)

        self.setLayout(layout)

        # 延迟检测
        QTimer.singleShot(500, self.detect_antivirus)

    def detect_antivirus(self):
        """检测杀毒软件"""
        from core.security import get_antivirus_helper

        try:
            helper = get_antivirus_helper()
            status, products = helper.get_antivirus_status()

            if products:
                product_names = [p.name for p in products]
                self.detected_label.setText(
                    f"<span style='color: green;'>✅ 检测到杀毒软件:</span> {', '.join(product_names)}"
                )

                # 显示信任步骤
                if products:
                    guide = helper.get_trust_guide(products[0].name)
                    if guide:
                        steps_html = f"<h4>{guide.antivirus_name} 信任步骤:</h4><ol>"
                        for step in guide.steps:
                            steps_html += f"<li>{step}</li>"
                        steps_html += "</ol>"
                        self.steps_text.setHtml(steps_html)

                    # Windows Defender 一键信任
                    if any("defender" in p.name.lower() for p in products):
                        self.btn_defender.setVisible(True)

            else:
                self.detected_label.setText(
                    "<span style='color: orange;'>⚠️ 未检测到杀毒软件</span> - 建议启用杀毒软件保护"
                )
                self.steps_text.setHtml("<p>未检测到杀毒软件，请确保系统安全。</p>")

        except Exception as e:
            self.detected_label.setText(f"<span style='color: red;'>检测失败: {e}</span>")
            logger.error(f"杀毒软件检测失败: {e}")

    def open_trust_settings(self):
        """打开信任设置页面"""
        from core.security import get_antivirus_helper

        try:
            helper = get_antivirus_helper()
            products = helper.detect_antivirus()

            if products:
                # 尝试打开第一个产品的设置
                helper.open_trust_settings(products[0].name)
            else:
                # 打开通用设置
                QMessageBox.information(
                    self,
                    "提示",
                    "请手动打开您的杀毒软件，添加 Living Tree AI 到信任列表。"
                )

        except Exception as e:
            logger.error(f"打开信任设置失败: {e}")

    def add_to_defender(self):
        """添加到 Windows Defender"""
        from core.security import get_antivirus_helper, get_security_manager

        try:
            helper = get_antivirus_helper()
            sec_mgr = get_security_manager()

            # 添加应用目录到排除
            app_path = sec_mgr.config.app_data_dir

            success, message = helper.add_to_defender_exclusions(app_path)

            if success:
                QMessageBox.information(self, "成功", message)
                self.chk_trusted.setChecked(True)
            else:
                QMessageBox.warning(self, "失败", message)

        except Exception as e:
            logger.error(f"添加 Defender 排除失败: {e}")


class SummaryPage(QWizardPage):
    """总结页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("安全设置完成")
        self.setSubTitle("查看最终安全状态")

        layout = QVBoxLayout()
        layout.setSpacing(15)

        # 结果显示
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        layout.addWidget(self.result_text)

        self.setLayout(layout)

    def initializePage(self):
        """页面初始化时更新结果"""
        from core.security import get_security_manager

        try:
            manager = get_security_manager()
            report = manager.get_security_report()

            html = "<h2>🔒 安全状态报告</h2>"

            # 安全级别
            level = report.get("security_level", "unknown")
            level_color = {"trusted": "green", "partial": "orange", "blocked": "red"}.get(level, "gray")
            html += f"<p>安全级别: <span style='color: {level_color};'><b>{level.upper()}</b></span></p>"

            # 防火墙
            fw = report.get("firewall", {})
            html += f"<h3>🛡️ 防火墙</h3>"
            html += f"<p>状态: {fw.get('status', 'unknown')}</p>"
            html += f"<p>应用规则: {fw.get('app_rules_count', 0)} 条</p>"

            # 杀毒软件
            av = report.get("antivirus", {})
            html += f"<h3>🔐 杀毒软件</h3>"
            html += f"<p>状态: {av.get('status', 'unknown')}</p>"
            detected = av.get("detected", [])
            if detected:
                html += f"<p>检测到: {', '.join(detected)}</p>"

            # 问题
            issues = report.get("issues", [])
            if issues:
                html += "<h3>⚠️ 待解决问题</h3><ul>"
                for issue in issues:
                    html += f"<li>{issue}</li>"
                html += "</ul>"

            # 建议
            recommendations = report.get("recommendations", [])
            if recommendations:
                html += "<h3>💡 建议</h3><ul>"
                for rec in recommendations:
                    html += f"<li>{rec}</li>"
                html += "</ul>"

            self.result_text.setHtml(html)

        except Exception as e:
            self.result_text.setHtml(f"<p style='color: red;'>获取安全报告失败: {e}</p>")
            logger.error(f"获取安全报告失败: {e}")


class SecuritySetupWizard(QWizard):
    """安全设置向导"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Living Tree AI 安全设置向导")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setMinimumSize(600, 500)

        # 添加页面
        self.addPage(self._create_welcome_page())
        self.addPage(self._create_firewall_page())
        self.addPage(self._create_antivirus_page())
        self.addPage(self._create_summary_page())

        # 按钮文本
        self.setButtonText(QWizard.WizardButton.NextButton, "下一步 >")
        self.setButtonText(QWizard.WizardButton.BackButton, "< 上一步")
        self.setButtonText(QWizard.WizardButton.FinishButton, "完成")
        self.setButtonText(QWizard.WizardButton.CancelButton, "取消")

        self.finished.connect(self._on_finished)

    def _create_welcome_page(self) -> WelcomePage:
        page = WelcomePage()
        return page

    def _create_firewall_page(self) -> FirewallPage:
        page = FirewallPage()
        return page

    def _create_antivirus_page(self) -> AntivirusPage:
        page = AntivirusPage()
        return page

    def _create_summary_page(self) -> SummaryPage:
        page = SummaryPage()
        return page

    def _on_finished(self, result):
        """向导完成"""
        if result:
            # 标记首次运行完成
            from core.security import get_security_manager
            manager = get_security_manager()
            manager.complete_first_run_setup()

            logger.info("安全设置向导完成")


def show_security_wizard():
    """显示安全设置向导"""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    wizard = SecuritySetupWizard()
    wizard.show()

    return wizard.exec()


if __name__ == "__main__":
    show_security_wizard()