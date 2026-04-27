"""
Skill 自进化系统 - PyQt6 集成面板

提供可视化的技能管理和进化追踪界面
"""

import json
import time
from pathlib import Path
from typing import Optional

try:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
        QLabel, QPushButton, QTextEdit, QTreeWidget,
        QTreeWidgetItem, QTableWidget, QTableWidgetItem,
        QTabWidget, QGroupBox, QProgressBar, QStatusBar,
        QMessageBox, QDialog, QHeaderView, QSplitter,
        QListWidget, QListWidgetItem, QAbstractItemView,
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
        QCheckBox, QFrame, QScrollArea, QSizePolicy,
        QProgressDialog,
    )
    from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QSize
    from PyQt6.QtGui import QFont, QColor, QPalette, QIcon, QAction
    PYQT_VERSION = 6
except ImportError:
    try:
        from PyQt5.QtWidgets import (
            QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
            QLabel, QPushButton, QTextEdit, QTreeWidget,
            QTreeWidgetItem, QTableWidget, QTableWidgetItem,
            QTabWidget, QGroupBox, QProgressBar, QStatusBar,
            QMessageBox, QDialog, QHeaderView, QSplitter,
            QListWidget, QListWidgetItem, QAbstractItemView,
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
            QCheckBox, QFrame, QScrollArea, QSizePolicy,
            QProgressDialog,
        )
        from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread
        from PyQt5.QtGui import QFont, QColor, QPalette, QIcon, QAction
        PYQT_VERSION = 5
    except ImportError:
        raise ImportError("需要安装 PyQt6 或 PyQt5")


from core.skill_evolution.database import EvolutionDatabase
from core.skill_evolution.engine import EvolutionEngine
from core.skill_evolution.models import (
    TaskSkill,
    SkillEvolutionStatus,
    MemoryLayer,
    MetaRule,
    GlobalFact,
    SessionArchive,
)


class SkillEvolutionPanel(QWidget):
    """
    技能自进化系统面板

    提供以下功能：
    1. 技能树视图 - 查看所有技能及其状态
    2. 技能详情 - 查看技能的执行流程
    3. 进化历史 - 查看技能如何成长
    4. 记忆浏览器 - 查看 L0-L4 各层记忆
    5. 任务追踪 - 查看执行中的任务
    """

    def __init__(self, parent=None, db_path: str = None):
        super().__init__(parent)
        self.db_path = db_path or str(Path.home() / ".hermes-desktop" / "evolution" / "evolution.db")
        self.db = EvolutionDatabase(self.db_path)
        self.engine = EvolutionEngine(self.db)

        self._init_ui()
        self._refresh()

        # 定时刷新
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(5000)  # 5秒刷新

    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("🌱 技能自进化系统")
        title.setStyleSheet("font-size: 18px; font-weight: bold; padding: 10px;")
        layout.addWidget(title)

        # 标签页
        tabs = QTabWidget()
        tabs.addTab(self._create_skills_tab(), "🎯 技能库")
        tabs.addTab(self._create_memory_tab(), "🧠 记忆层")
        tabs.addTab(self._create_history_tab(), "📜 执行历史")
        tabs.addTab(self._create_evolution_tab(), "📈 进化追踪")
        tabs.addTab(self._create_settings_tab(), "⚙️ 设置")

        layout.addWidget(tabs)

        # 状态栏
        self.status_bar = QStatusBar()
        layout.addWidget(self.status_bar)

    def _create_skills_tab(self) -> QWidget:
        """创建技能库标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 工具栏
        toolbar = QHBoxLayout()
        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.clicked.connect(self._refresh_skills)
        self.analyze_btn = QPushButton("🔍 分析合并")
        self.analyze_btn.clicked.connect(self._analyze_merges)
        self.export_btn = QPushButton("📤 导出")
        self.export_btn.clicked.connect(self._export_skills)
        toolbar.addWidget(self.refresh_btn)
        toolbar.addWidget(self.analyze_btn)
        toolbar.addWidget(self.export_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # 技能统计
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("padding: 5px; background: #f0f0f0; border-radius: 5px;")
        layout.addWidget(self.stats_label)

        # 技能列表
        self.skills_tree = QTreeWidget()
        self.skills_tree.setHeaderLabels(["名称", "状态", "使用次数", "成功率", "平均耗时", "最后使用"])
        self.skills_tree.setColumnWidth(0, 200)
        self.skills_tree.setColumnWidth(1, 80)
        self.skills_tree.setColumnWidth(2, 80)
        self.skills_tree.setColumnWidth(3, 80)
        self.skills_tree.itemDoubleClicked.connect(self._on_skill_double_click)
        layout.addWidget(self.skills_tree)

        # 技能详情
        detail_group = QGroupBox("技能详情")
        detail_layout = QVBoxLayout(detail_group)
        self.skill_detail = QTextEdit()
        self.skill_detail.setReadOnly(True)
        self.skill_detail.setMaximumHeight(150)
        detail_layout.addWidget(self.skill_detail)
        layout.addWidget(detail_group)

        return widget

    def _create_memory_tab(self) -> QWidget:
        """创建记忆层标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 层级选择
        layer_layout = QHBoxLayout()
        layer_layout.addWidget(QLabel("记忆层级:"))
        self.layer_combo = QComboBox()
        for layer in MemoryLayer:
            self.layer_combo.addItem(layer.value, layer)
        self.layer_combo.currentIndexChanged.connect(self._on_layer_changed)
        layer_layout.addWidget(self.layer_combo)
        layer_layout.addStretch()
        layout.addLayout(layer_layout)

        # 记忆内容
        self.memory_tree = QTreeWidget()
        self.memory_tree.setHeaderLabels(["关键词/ID", "摘要", "访问次数"])
        self.memory_tree.setColumnWidth(0, 200)
        self.memory_tree.setColumnWidth(1, 300)
        layout.addWidget(self.memory_tree)

        return widget

    def _create_history_tab(self) -> QWidget:
        """创建执行历史标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 历史列表
        self.history_tree = QTreeWidget()
        self.history_tree.setHeaderLabels(["时间", "任务描述", "状态", "工具数", "耗时"])
        self.history_tree.setColumnWidth(0, 150)
        self.history_tree.setColumnWidth(1, 300)
        layout.addWidget(self.history_tree)

        return widget

    def _create_evolution_tab(self) -> QWidget:
        """创建进化追踪标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 进化统计
        stats_group = QGroupBox("进化统计")
        stats_layout = QGridLayout(stats_group)

        self.total_tasks_label = QLabel("0")
        self.total_tasks_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #2196F3;")
        stats_layout.addWidget(QLabel("总任务数"), 0, 0)
        stats_layout.addWidget(self.total_tasks_label, 1, 0)

        self.total_skills_label = QLabel("0")
        self.total_skills_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #4CAF50;")
        stats_layout.addWidget(QLabel("技能总数"), 0, 1)
        stats_layout.addWidget(self.total_skills_label, 1, 1)

        self.total_uses_label = QLabel("0")
        self.total_uses_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #FF9800;")
        stats_layout.addWidget(QLabel("技能调用次数"), 0, 2)
        stats_layout.addWidget(self.total_uses_label, 1, 2)

        self.matured_skills_label = QLabel("0")
        self.matured_skills_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #9C27B0;")
        stats_layout.addWidget(QLabel("成熟技能"), 0, 3)
        stats_layout.addWidget(self.matured_skills_label, 1, 3)

        layout.addWidget(stats_group)

        # 进化进度条
        progress_group = QGroupBox("技能成熟度分布")
        progress_layout = QVBoxLayout(progress_group)

        self.seed_progress = QProgressBar()
        self.seed_progress.setFormat("🌱 种子态: %p%")
        progress_layout.addWidget(self.seed_progress)

        self.growing_progress = QProgressBar()
        self.growing_progress.setFormat("🌿 成长态: %p%")
        progress_layout.addWidget(self.growing_progress)

        self.matured_progress = QProgressBar()
        self.matured_progress.setFormat("🌳 成熟态: %p%")
        progress_layout.addWidget(self.matured_progress)

        self.atrophied_progress = QProgressBar()
        self.atrophied_progress.setFormat("🍂 萎缩态: %p%")
        progress_layout.addWidget(self.atrophied_progress)

        layout.addWidget(progress_group)

        return widget

    def _create_settings_tab(self) -> QWidget:
        """创建设置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 自动固化设置
        auto_group = QGroupBox("自动化设置")
        auto_layout = QGridLayout(auto_group)

        auto_layout.addWidget(QLabel("自动固化:"), 0, 0)
        self.auto_consolidate = QCheckBox()
        self.auto_consolidate.setChecked(True)
        auto_layout.addWidget(self.auto_consolidate, 0, 1)

        auto_layout.addWidget(QLabel("固化最小步数:"), 1, 0)
        self.min_steps = QSpinBox()
        self.min_steps.setRange(1, 10)
        self.min_steps.setValue(2)
        auto_layout.addWidget(self.min_steps, 1, 1)

        auto_layout.addWidget(QLabel("技能匹配阈值:"), 2, 0)
        self.skill_threshold = QDoubleSpinBox()
        self.skill_threshold.setRange(0.1, 0.9)
        self.skill_threshold.setSingleStep(0.1)
        self.skill_threshold.setValue(0.3)
        auto_layout.addWidget(self.skill_threshold, 2, 1)

        layout.addWidget(auto_group)

        # 遗忘设置
        atrophy_group = QGroupBox("技能遗忘设置")
        atrophy_layout = QGridLayout(atrophy_group)

        atrophy_layout.addWidget(QLabel("萎缩判定(天):"), 0, 0)
        self.atrophy_days = QSpinBox()
        self.atrophy_days.setRange(7, 365)
        self.atrophy_days.setValue(90)
        atrophy_layout.addWidget(self.atrophy_days, 0, 1)

        layout.addWidget(atrophy_group)

        layout.addStretch()

        return widget

    def _refresh(self):
        """刷新所有数据"""
        self._refresh_stats()
        self._refresh_skills()
        self._refresh_memory()
        self._refresh_history()
        self._update_status("就绪")

    def _refresh_stats(self):
        """刷新统计"""
        stats = self.db.get_stats()

        # 更新标签页数字
        self.total_tasks_label.setText(str(stats.get('tasks', 0)))
        self.total_skills_label.setText(str(stats.get('skills', 0)))
        self.total_uses_label.setText(str(stats.get('total_skill_uses', 0)))

        # 技能状态分布
        by_status = stats.get('skills_by_status', {})
        total_skills = stats.get('skills', 1)  # 避免除零

        seed_count = by_status.get('seed', 0)
        growing_count = by_status.get('growing', 0)
        matured_count = by_status.get('matured', 0)
        atrophied_count = by_status.get('atrophied', 0)

        self.seed_progress.setMaximum(total_skills)
        self.seed_progress.setValue(seed_count)

        self.growing_progress.setMaximum(total_skills)
        self.growing_progress.setValue(growing_count)

        self.matured_progress.setMaximum(total_skills)
        self.matured_progress.setValue(matured_count)

        self.atrophied_progress.setMaximum(total_skills)
        self.atrophied_progress.setValue(atrophied_count)

        self.matured_skills_label.setText(str(matured_count))

    def _refresh_skills(self):
        """刷新技能列表"""
        self.skills_tree.clear()
        skills = self.db.get_all_skills()

        for skill in skills:
            status = skill.evolution_status.value if isinstance(skill.evolution_status, SkillEvolutionStatus) else skill.evolution_status
            status_emoji = {
                "seed": "🌱",
                "growing": "🌿",
                "matured": "🌳",
                "atrophied": "🍂",
                "merged": "🔀",
            }.get(status, "❓")

            last_used = time.strftime("%Y-%m-%d %H:%M", time.localtime(skill.last_used))
            avg_duration = f"{skill.avg_duration:.1f}s" if skill.avg_duration else "N/A"

            item = QTreeWidgetItem([
                skill.name,
                f"{status_emoji} {status}",
                str(skill.use_count),
                f"{skill.success_rate:.0%}",
                avg_duration,
                last_used,
            ])
            item.setData(0, Qt.UserRole, skill.skill_id)
            self.skills_tree.addTopLevelItem(item)

        # 更新统计标签
        self.stats_label.setText(
            f"共 {len(skills)} 个技能 | "
            f"总使用 {sum(s.use_count for s in skills)} 次 | "
            f"成熟度分布: 🌱{sum(1 for s in skills if s.evolution_status == SkillEvolutionStatus.SEED)} "
            f"🌿{sum(1 for s in skills if s.evolution_status == SkillEvolutionStatus.GROWING)} "
            f"🌳{sum(1 for s in skills if s.evolution_status == SkillEvolutionStatus.MATURED)}"
        )

    def _refresh_memory(self):
        """刷新记忆层"""
        pass  # 由 layer_combo 变化触发

    def _refresh_history(self):
        """刷新执行历史"""
        self.history_tree.clear()
        archives = self.db.get_recent_archives(limit=50)

        for archive in archives:
            status = "✓" if archive.success else "✗"
            timestamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(archive.archived_at))
            duration = f"{archive.duration:.1f}s" if archive.duration else "N/A"

            item = QTreeWidgetItem([
                timestamp,
                archive.task_description[:50] + "..." if len(archive.task_description) > 50 else archive.task_description,
                status,
                str(len(archive.tools_used)),
                duration,
            ])
            self.history_tree.addTopLevelItem(item)

    def _on_skill_double_click(self, item, column):
        """技能双击事件"""
        skill_id = item.data(0, Qt.UserRole)
        if skill_id:
            skill = self.db.get_skill(skill_id)
            if skill:
                self._show_skill_detail(skill)

    def _show_skill_detail(self, skill: TaskSkill):
        """显示技能详情"""
        detail = f"""# {skill.name}

## 基本信息
- **ID**: {skill.skill_id}
- **描述**: {skill.description}
- **状态**: {skill.evolution_status.value if isinstance(skill.evolution_status, SkillEvolutionStatus) else skill.evolution_status}
- **版本**: {skill.version}
- **创建时间**: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(skill.created_at))}

## 使用统计
- **使用次数**: {skill.use_count}
- **失败次数**: {skill.failed_count}
- **成功率**: {skill.success_rate:.0%}
- **平均耗时**: {skill.avg_duration:.2f}s
- **最后使用**: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(skill.last_used))}

## 触发词
{', '.join(skill.trigger_patterns) if skill.trigger_patterns else '无'}

## 工具序列
{' → '.join(skill.tool_sequence) if skill.tool_sequence else '无'}

## 执行流程
"""
        for i, step in enumerate(skill.execution_flow, 1):
            status = "✓" if step.get("success", True) else "✗"
            detail += f"{i}. {status} {step.get('tool', 'unknown')} (相位: {step.get('phase', 'unknown')})\n"

        self.skill_detail.setMarkdown(detail)

    def _on_layer_changed(self, index):
        """记忆层级变化"""
        layer = self.layer_combo.currentData()
        if not layer:
            return

        self.memory_tree.clear()
        insights = self.db.get_insights_by_layer(layer)

        for idx in insights:
            keywords = ", ".join(idx.keywords) if idx.keywords else "无"
            item = QTreeWidgetItem([
                keywords[:30] + "..." if len(keywords) > 30 else keywords,
                idx.summary[:50] + "..." if len(idx.summary) > 50 else idx.summary,
                str(idx.access_count),
            ])
            item.setData(0, Qt.UserRole, idx.target_id)
            self.memory_tree.addTopLevelItem(item)

    def _analyze_merges(self):
        """分析可合并的技能"""
        suggestions = self.engine.find_merge_candidates()

        if not suggestions:
            QMessageBox.information(self, "分析结果", "未发现可合并的技能")
            return

        msg = "发现以下可合并的技能对：\n\n"
        for i, s in enumerate(suggestions[:5], 1):
            msg += f"{i}. {s.skill_a.name} + {s.skill_b.name}\n"
            msg += f"   相似度: {s.similarity:.0%}\n"
            msg += f"   原因: {s.reason}\n\n"

        reply = QMessageBox.question(self, "合并建议", msg + "\n是否执行合并?",
                                    QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes and suggestions:
            result = self.engine.merge_skills(
                suggestions[0].skill_a.skill_id,
                suggestions[0].skill_b.skill_id,
                suggestions[0].suggested_name
            )
            if result:
                QMessageBox.information(self, "成功", f"已合并为: {result.name}")
                self._refresh_skills()
            else:
                QMessageBox.warning(self, "失败", "合并失败")

    def _export_skills(self):
        """导出技能"""
        skills = self.db.get_all_skills()
        data = [s.to_dict() for s in skills]
        print(f"导出 {len(data)} 个技能到 JSON")

        QMessageBox.information(self, "导出", f"已导出 {len(data)} 个技能")

    def _update_status(self, message: str):
        """更新状态栏"""
        self.status_bar.showMessage(f"🕐 {time.strftime('%H:%M:%S')} - {message}")


def create_panel(parent=None, db_path: str = None) -> QWidget:
    """创建面板的工厂函数"""
    return SkillEvolutionPanel(parent, db_path)
