"""
Project Match Panel - PyQt6 可视化面板
项目匹配度分析报告的图形化展示
"""

import asyncio
from dataclasses import dataclass
from typing import Optional

# PyQt6 导入
try:
    from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
        QLabel, QPushButton, QLineEdit, QTextEdit,
        QProgressBar, QGroupBox, QFrame, QScrollArea,
        QTabWidget, QTableWidget, QTableWidgetItem,
        QBadge, QProgressDialog
    )
    from PyQt6.QtGui import QFont, QColor, QPalette, QPainter, QPen, QBrush, QLinearGradient
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False

# 现有面板基类
import sys
sys.path.insert(0, 'f:/mhzyapp/LivingTreeAlAgent')
try:
    from ui.a2ui.config import BasePanel
except ImportError:
    BasePanel = QWidget


@dataclass
class MatchDisplayData:
    """用于显示的匹配数据"""
    github_url: str = ""
    local_path: str = ""
    total_score: float = 0.0
    surface_score: float = 0.0
    architectural_score: float = 0.0
    semantic_score: float = 0.0
    match_level: str = ""
    insights: list = None
    suggestions: list = None
    warnings: list = None
    github_info: dict = None
    error: str = ""


class AnalysisWorker(QThread):
    """后台分析工作线程"""
    finished = pyqtSignal(object)
    progress = pyqtSignal(str, int)
    error = pyqtSignal(str)
    
    def __init__(self, github_url: str, local_path: str):
        super().__init__()
        self.github_url = github_url
        self.local_path = local_path
    
    def run(self):
        try:
            from core.project_matcher import analyze_projects
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            self.progress.emit("正在分析 GitHub 项目...", 20)
            result = loop.run_until_complete(
                analyze_projects(self.github_url, self.local_path)
            )
            
            self.progress.emit("正在分析本地项目...", 50)
            
            self.progress.emit("正在匹配分析...", 80)
            
            # 转换为显示数据
            display_data = MatchDisplayData(
                github_url=self.github_url,
                local_path=self.local_path,
                total_score=result.total_score,
                surface_score=result.surface_score,
                architectural_score=result.architectural_score,
                semantic_score=result.semantic_score,
                match_level=result.match_level.value,
                insights=result.insights,
                suggestions=[
                    {'title': s.title, 'description': s.description, 
                     'priority': s.priority, 'type': s.type}
                    for s in result.migration_suggestions
                ],
                warnings=[
                    {'message': w.message, 'severity': w.severity, 
                     'category': w.category, 'recommendation': w.recommendation}
                    for w in result.risk_warnings
                ],
                github_info={
                    'name': result.github_project.name if result.github_project else 'N/A',
                    'owner': result.github_project.owner if result.github_project else 'N/A',
                    'stars': result.github_project.stars if result.github_project else 0,
                    'language': result.github_project.language if result.github_project else 'N/A',
                    'description': result.github_project.description if result.github_project else '',
                }
            )
            
            self.progress.emit("分析完成", 100)
            self.finished.emit(display_data)
            
            loop.close()
            
        except Exception as e:
            self.error.emit(str(e))


class ScoreGauge(QWidget):
    """评分仪表盘组件"""
    
    def __init__(self, score: float = 0, parent=None):
        super().__init__(parent)
        self.score = score
        self.setMinimumSize(120, 120)
    
    def set_score(self, score: float):
        self.score = score
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        width = self.width()
        height = self.height()
        center = width / 2, height / 2
        radius = min(width, height) / 2 - 10
        
        # 背景圆弧
        painter.setPen(QPen(QColor("#E0E0E0"), 12))
        painter.drawArc(
            int(center[0] - radius), int(center[1] - radius),
            int(radius * 2), int(radius * 2),
            45 * 16, 270 * 16
        )
        
        # 分数圆弧
        score_color = self._get_score_color(self.score)
        painter.setPen(QPen(score_color, 12))
        
        angle = int(270 * (self.score / 100))
        painter.drawArc(
            int(center[0] - radius), int(center[1] - radius),
            int(radius * 2), int(radius * 2),
            45 * 16, angle * 16
        )
        
        # 中心文字
        painter.setPen(QColor("#333333"))
        font = QFont("Arial", 20, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(
            int(center[0] - 30), int(center[1] + 8),
            f"{self.score:.0f}"
        )
        
        font_small = QFont("Arial", 10)
        painter.setFont(font_small)
        painter.drawText(
            int(center[0] - 15), int(center[1] + 25),
            "/ 100"
        )
    
    def _get_score_color(self, score: float) -> QColor:
        if score >= 80:
            return QColor("#4CAF50")  # 绿色
        elif score >= 60:
            return QColor("#8BC34A")  # 浅绿
        elif score >= 40:
            return QColor("#FFC107")  # 黄色
        elif score >= 20:
            return QColor("#FF9800")  # 橙色
        else:
            return QColor("#F44336")  # 红色


class ScoreBar(QWidget):
    """分数条组件"""
    
    def __init__(self, label: str, score: float, color: str = "#4CAF50", parent=None):
        super().__init__(parent)
        self.label = label
        self.score = score
        self.color = QColor(color)
        self.setMinimumHeight(30)
    
    def set_score(self, score: float):
        self.score = score
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        # 标签
        painter.setPen(QColor("#333333"))
        font = QFont("Arial", 10)
        painter.setFont(font)
        painter.drawText(5, 18, self.label)
        
        # 背景条
        bar_y = 22
        bar_height = 8
        bar_width = width - 10
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#E0E0E0"))
        painter.drawRoundedRect(5, bar_y, bar_width, bar_height, 4, 4)
        
        # 分数条
        fill_width = int(bar_width * (self.score / 100))
        if fill_width > 0:
            painter.setBrush(self.color)
            painter.drawRoundedRect(5, bar_y, fill_width, bar_height, 4, 4)
        
        # 分数文字
        painter.setPen(QColor("#666666"))
        painter.drawText(width - 45, 18, f"{self.score:.0f}%")


class ProjectMatchPanel(BasePanel if PYQT6_AVAILABLE else QWidget):
    """项目匹配面板主组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        if not PYQT6_AVAILABLE:
            self._show_import_error()
            return
        
        self.worker = None
        self.init_ui()
    
    def _show_import_error(self):
        """显示导入错误"""
        layout = QVBoxLayout()
        label = QLabel("PyQt6 不可用，请安装: pip install PyQt6")
        label.setStyleSheet("color: red; font-size: 14px; padding: 20px;")
        layout.addWidget(label)
        self.setLayout(layout)
    
    def init_ui(self):
        """初始化 UI"""
        main_layout = QVBoxLayout()
        
        # 标题
        title = QLabel("项目匹配度分析器")
        title.setStyleSheet("font-size: 18px; font-weight: bold; padding: 10px;")
        main_layout.addWidget(title)
        
        # 输入区域
        input_group = QGroupBox("输入")
        input_layout = QHBoxLayout()
        
        self.github_input = QLineEdit()
        self.github_input.setPlaceholderText("输入 GitHub 项目 URL (如: https://github.com/user/repo)")
        input_layout.addWidget(QLabel("GitHub:"))
        input_layout.addWidget(self.github_input, 1)
        
        self.local_input = QLineEdit()
        self.local_input.setPlaceholderText("本地项目路径")
        self.local_input.setText("f:/mhzyapp/LivingTreeAlAgent")
        input_layout.addWidget(QLabel("本地:"))
        input_layout.addWidget(self.local_input, 1)
        
        self.analyze_btn = QPushButton("分析")
        self.analyze_btn.clicked.connect(self.start_analysis)
        input_layout.addWidget(self.analyze_btn)
        
        input_group.setLayout(input_layout)
        main_layout.addWidget(input_group)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        # 结果区域
        self.result_area = QScrollArea()
        self.result_area.setWidgetResizable(True)
        self.result_widget = QWidget()
        self.result_layout = QVBoxLayout()
        self.result_widget.setLayout(self.result_layout)
        self.result_area.setWidget(self.result_widget)
        main_layout.addWidget(self.result_area, 1)
        
        # 初始化空状态
        self._show_empty_state()
        
        self.setLayout(main_layout)
    
    def _show_empty_state(self):
        """显示空状态"""
        for i in range(self.result_layout.count()):
            widget = self.result_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        empty_label = QLabel("请输入 GitHub 项目 URL 并点击\"分析\"开始匹配度分析")
        empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_label.setStyleSheet("color: #999; font-size: 14px; padding: 50px;")
        self.result_layout.addWidget(empty_label)
    
    def start_analysis(self):
        """开始分析"""
        github_url = self.github_input.text().strip()
        local_path = self.local_input.text().strip()
        
        if not github_url:
            self.github_input.setFocus()
            return
        
        if not local_path:
            local_path = "f:/mhzyapp/LivingTreeAlAgent"
        
        # 禁用按钮
        self.analyze_btn.setEnabled(False)
        self.analyze_btn.setText("分析中...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # 清除结果
        for i in range(self.result_layout.count()):
            widget = self.result_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        # 启动工作线程
        self.worker = AnalysisWorker(github_url, local_path)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()
    
    def _on_progress(self, message: str, value: int):
        """进度更新"""
        self.progress_bar.setValue(value)
    
    def _on_finished(self, data: MatchDisplayData):
        """分析完成"""
        self.progress_bar.setVisible(False)
        self.analyze_btn.setEnabled(True)
        self.analyze_btn.setText("分析")
        
        if data.error:
            self._show_error(data.error)
        else:
            self._show_results(data)
    
    def _on_error(self, error: str):
        """分析错误"""
        self.progress_bar.setVisible(False)
        self.analyze_btn.setEnabled(True)
        self.analyze_btn.setText("分析")
        self._show_error(error)
    
    def _show_results(self, data: MatchDisplayData):
        """显示结果"""
        for i in range(self.result_layout.count()):
            widget = self.result_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        # 项目信息
        info_group = QGroupBox("项目信息")
        info_layout = QGridLayout()
        
        if data.github_info:
            info_layout.addWidget(QLabel("GitHub 项目:"), 0, 0)
            info_layout.addWidget(QLabel(f"{data.github_info.get('owner', 'N/A')}/{data.github_info.get('name', 'N/A')}"), 0, 1)
            
            info_layout.addWidget(QLabel("Stars:"), 0, 2)
            info_layout.addWidget(QLabel(f"{data.github_info.get('stars', 0)}"), 0, 3)
            
            info_layout.addWidget(QLabel("语言:"), 1, 0)
            info_layout.addWidget(QLabel(f"{data.github_info.get('language', 'N/A')}"), 1, 1)
            
            desc = data.github_info.get('description', '')
            if desc:
                info_layout.addWidget(QLabel("描述:"), 2, 0)
                desc_label = QLabel(desc[:100] + "..." if len(desc) > 100 else desc)
                desc_label.setWordWrap(True)
                info_layout.addWidget(desc_label, 2, 1, 1, 3)
        
        info_layout.addWidget(QLabel("本地项目:"), 3, 0)
        info_layout.addWidget(QLabel(data.local_path), 3, 1, 1, 3)
        
        info_group.setLayout(info_layout)
        self.result_layout.addWidget(info_group)
        
        # 总体评分
        score_group = QGroupBox("总体评分")
        score_layout = QHBoxLayout()
        
        # 主仪表盘
        main_gauge = ScoreGauge(data.total_score)
        main_gauge.setMinimumSize(150, 150)
        score_layout.addWidget(main_gauge, 0, Qt.AlignmentFlag.AlignCenter)
        
        # 分项分数
        scores_layout = QVBoxLayout()
        
        surface_bar = ScoreBar("表层技术栈", data.surface_score, "#2196F3")
        surface_bar.setMinimumHeight(30)
        scores_layout.addWidget(surface_bar)
        
        arch_bar = ScoreBar("架构模式", data.architectural_score, "#9C27B0")
        arch_bar.setMinimumHeight(30)
        scores_layout.addWidget(arch_bar)
        
        semantic_bar = ScoreBar("语义业务", data.semantic_score, "#FF9800")
        semantic_bar.setMinimumHeight(30)
        scores_layout.addWidget(semantic_bar)
        
        # 匹配级别
        level_label = QLabel(f"匹配级别: {self._get_level_text(data.match_level)}")
        level_label.setStyleSheet(f"color: {self._get_level_color(data.match_level)}; font-weight: bold;")
        scores_layout.addWidget(level_label)
        
        score_layout.addLayout(scores_layout, 1)
        score_group.setLayout(score_layout)
        self.result_layout.addWidget(score_group)
        
        # 洞察
        if data.insights:
            insights_group = QGroupBox("关键洞察")
            insights_layout = QVBoxLayout()
            
            for insight in data.insights:
                insight_label = QLabel(f"• {insight}")
                insight_label.setWordWrap(True)
                insights_layout.addWidget(insight_label)
            
            insights_group.setLayout(insights_layout)
            self.result_layout.addWidget(insights_group)
        
        # 建议
        if data.suggestions:
            suggestions_group = QGroupBox("迁移建议")
            suggestions_layout = QVBoxLayout()
            
            for suggestion in data.suggestions[:5]:
                priority_color = {
                    'high': '#F44336',
                    'medium': '#FF9800',
                    'low': '#4CAF50'
                }.get(suggestion['priority'], '#666666')
                
                sug_widget = QWidget()
                sug_layout = QHBoxLayout()
                sug_layout.setContentsMargins(0, 5, 0, 5)
                
                badge = QLabel(f"[{suggestion['priority'].upper()}]")
                badge.setStyleSheet(f"color: {priority_color}; font-weight: bold;")
                sug_layout.addWidget(badge)
                
                title_label = QLabel(f"<b>{suggestion['title']}</b>")
                sug_layout.addWidget(title_label, 1)
                
                sug_widget.setLayout(sug_layout)
                suggestions_layout.addWidget(sug_widget)
                
                desc_label = QLabel(suggestion['description'])
                desc_label.setWordWrap(True)
                desc_label.setStyleSheet("color: #666; padding-left: 50px;")
                suggestions_layout.addWidget(desc_label)
            
            suggestions_group.setLayout(suggestions_layout)
            self.result_layout.addWidget(suggestions_group)
        
        # 风险预警
        if data.warnings:
            warnings_group = QGroupBox("风险预警")
            warnings_layout = QVBoxLayout()
            
            for warning in data.warnings:
                severity_color = {
                    'critical': '#F44336',
                    'high': '#FF5722',
                    'medium': '#FF9800',
                    'low': '#FFC107'
                }.get(warning['severity'], '#666666')
                
                warning_widget = QWidget()
                warning_layout = QVBoxLayout()
                warning_layout.setContentsMargins(5, 5, 5, 5)
                warning_layout.setSpacing(2)
                
                header = QLabel(f"<span style='color:{severity_color};'>[{warning['severity'].upper()}]</span> {warning['message']}")
                header.setWordWrap(True)
                warning_layout.addWidget(header)
                
                rec = QLabel(f"<span style='color:#666;'>建议: {warning['recommendation']}</span>")
                rec.setWordWrap(True)
                warning_layout.addWidget(rec)
                
                warning_widget.setLayout(warning_layout)
                warning_widget.setStyleSheet("background: #FFF3E0; border-radius: 5px; padding: 5px;")
                warnings_layout.addWidget(warning_widget)
            
            warnings_group.setLayout(warnings_layout)
            self.result_layout.addWidget(warnings_group)
        
        # 导出按钮
        export_layout = QHBoxLayout()
        export_btn = QPushButton("导出报告")
        export_btn.clicked.connect(lambda: self._export_report(data))
        export_layout.addStretch()
        export_layout.addWidget(export_btn)
        self.result_layout.addLayout(export_layout)
    
    def _show_error(self, error: str):
        """显示错误"""
        for i in range(self.result_layout.count()):
            widget = self.result_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        error_label = QLabel(f"分析失败: {error}")
        error_label.setStyleSheet("color: #F44336; padding: 20px; font-size: 14px;")
        error_label.setWordWrap(True)
        self.result_layout.addWidget(error_label)
    
    def _get_level_text(self, level: str) -> str:
        """获取级别文本"""
        texts = {
            'excellent': '优秀 - 高度匹配',
            'good': '良好 - 较好匹配',
            'moderate': '中等 - 部分匹配',
            'poor': '较差 - 差异较大',
            'incompatible': '不兼容 - 不建议迁移'
        }
        return texts.get(level, level)
    
    def _get_level_color(self, level: str) -> str:
        """获取级别颜色"""
        colors = {
            'excellent': '#4CAF50',
            'good': '#8BC34A',
            'moderate': '#FFC107',
            'poor': '#FF9800',
            'incompatible': '#F44336'
        }
        return colors.get(level, '#666666')
    
    def _export_report(self, data: MatchDisplayData):
        """导出报告"""
        from PyQt6.QtWidgets import QFileDialog
        import json
        
        filename, _ = QFileDialog.getSaveFileName(
            self, "导出报告", "match_report.json", "JSON Files (*.json)"
        )
        
        if filename:
            report = {
                'github_url': data.github_url,
                'local_path': data.local_path,
                'total_score': data.total_score,
                'surface_score': data.surface_score,
                'architectural_score': data.architectural_score,
                'semantic_score': data.semantic_score,
                'match_level': data.match_level,
                'insights': data.insights,
                'suggestions': data.suggestions,
                'warnings': data.warnings,
                'github_info': data.github_info,
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)


def create_match_panel() -> ProjectMatchPanel:
    """创建匹配面板"""
    return ProjectMatchPanel()


# CLI 模式运行
if __name__ == '__main__':
    import asyncio
    import sys
    
    if PYQT6_AVAILABLE and len(sys.argv) > 1 and sys.argv[1] == '--gui':
        from PyQt6.QtWidgets import QApplication
        
        app = QApplication(sys.argv)
        panel = create_match_panel()
        panel.resize(800, 600)
        panel.show()
        sys.exit(app.exec())
    else:
        # CLI 模式
        async def main():
            if len(sys.argv) < 3:
                print("用法: python project_match_panel.py <github_url> <local_path>")
                print("示例: python project_match_panel.py https://github.com/user/repo f:/project")
                return
            
            github_url = sys.argv[1]
            local_path = sys.argv[2]
            
            print("正在分析项目...")
            result = await analyze_projects(github_url, local_path)
            
            from core.project_matcher import ComprehensiveEvaluator
            evaluator = ComprehensiveEvaluator()
            report = evaluator.generate_text_report(result)
            
            print(report)
        
        asyncio.run(main())
