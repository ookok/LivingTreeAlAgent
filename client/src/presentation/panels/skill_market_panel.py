"""
SkillMarketPanel - 技能市场面板

参考 Multica 的技能系统设计，提供技能浏览、评分和下载功能。

功能：
1. 浏览可用技能
2. 技能评分与反馈
3. 技能下载与安装
4. 技能搜索与筛选
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QPushButton,
    QLineEdit, QComboBox, QRatingBar, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QIcon
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from typing import List, Dict, Optional
import asyncio


class SkillCategory(Enum):
    """技能类别"""
    GENERAL = "general"
    NETWORK = "network"
    DOCUMENT = "document"
    DATABASE = "database"
    TASK = "task"
    LEARNING = "learning"
    GEO = "geo"
    SIMULATION = "simulation"


@dataclass
class MarketSkill:
    """技能市场中的技能"""
    skill_id: str
    name: str
    description: str
    category: SkillCategory
    author: str
    version: str
    rating: float
    download_count: int
    last_update: datetime
    is_installed: bool = False


class SkillCard(QListWidgetItem):
    """技能卡片"""
    
    def __init__(self, skill: MarketSkill):
        super().__init__()
        self.skill = skill
        self._update_display()
    
    def _update_display(self):
        """更新显示"""
        icon = self._get_category_icon()
        self.setIcon(icon)
        
        # 构建卡片内容
        text = f"<b>{self.skill.name}</b>"
        text += f"<br><small>{self.skill.description[:80]}...</small>"
        text += f"<br><span style='color:#6c757d'>作者: {self.skill.author}</span>"
        text += f" | <span style='color:#6c757d'>版本: {self.skill.version}</span>"
        text += f"<br>⭐ {self.skill.rating} | 📥 {self.skill.download_count}"
        
        self.setText(text)
    
    def _get_category_icon(self):
        """获取类别图标"""
        icons = {
            SkillCategory.GENERAL: "📋",
            SkillCategory.NETWORK: "🌐",
            SkillCategory.DOCUMENT: "📄",
            SkillCategory.DATABASE: "💾",
            SkillCategory.TASK: "✅",
            SkillCategory.LEARNING: "🧠",
            SkillCategory.GEO: "🌍",
            SkillCategory.SIMULATION: "🔬"
        }
        return QIcon.fromTheme(icons.get(self.skill.category, "📋"))


class SkillMarketPanel(QWidget):
    """
    技能市场面板
    
    设计理念：
    1. 可视化浏览技能
    2. 支持搜索和筛选
    3. 技能评分与反馈
    4. 一键安装技能
    """
    
    skill_installed = pyqtSignal(MarketSkill)
    skill_rated = pyqtSignal(str, int)
    
    def __init__(self):
        super().__init__()
        self.skills: Dict[str, MarketSkill] = {}
        self.init_ui()
    
    def init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout()
        
        # 搜索和筛选栏
        search_layout = QHBoxLayout()
        
        # 搜索框
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索技能...")
        self.search_edit.textChanged.connect(self._filter_skills)
        search_layout.addWidget(self.search_edit)
        
        # 类别筛选
        self.category_combo = QComboBox()
        self.category_combo.addItem("全部类别")
        for cat in SkillCategory:
            self.category_combo.addItem(cat.value)
        self.category_combo.currentTextChanged.connect(self._filter_skills)
        search_layout.addWidget(self.category_combo)
        
        # 排序选择
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["热门程度", "评分", "更新时间", "下载量"])
        search_layout.addWidget(self.sort_combo)
        
        layout.addLayout(search_layout)
        
        # 技能列表
        self.skill_list = QListWidget()
        self.skill_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.skill_list.itemClicked.connect(self._on_skill_click)
        layout.addWidget(self.skill_list)
        
        # 详情面板
        self.detail_panel = QWidget()
        self.detail_layout = QVBoxLayout(self.detail_panel)
        layout.addWidget(self.detail_panel)
        
        self.setLayout(layout)
        
        # 加载模拟数据
        self._load_mock_skills()
    
    def _load_mock_skills(self):
        """加载模拟技能数据"""
        mock_skills = [
            MarketSkill(
                skill_id="1",
                name="网页爬虫",
                description="支持自适应解析、反爬绕过、并发爬取的网页内容提取工具",
                category=SkillCategory.NETWORK,
                author="系统",
                version="1.0",
                rating=4.8,
                download_count=1250,
                last_update=datetime(2026, 4, 28),
                is_installed=True
            ),
            MarketSkill(
                skill_id="2",
                name="深度搜索",
                description="基于 Tier1-4 免费 API 的分层搜索系统",
                category=SkillCategory.NETWORK,
                author="系统",
                version="1.0",
                rating=4.6,
                download_count=980,
                last_update=datetime(2026, 4, 27),
                is_installed=True
            ),
            MarketSkill(
                skill_id="3",
                name="文档解析",
                description="支持 TXT/DOCX/PDF 格式的文档解析工具",
                category=SkillCategory.DOCUMENT,
                author="系统",
                version="1.0",
                rating=4.5,
                download_count=870,
                last_update=datetime(2026, 4, 26),
                is_installed=True
            ),
            MarketSkill(
                skill_id="4",
                name="Markdown 转换",
                description="将 HTML/PDF/DOCX 转换为 Markdown 格式",
                category=SkillCategory.DOCUMENT,
                author="系统",
                version="1.0",
                rating=4.4,
                download_count=650,
                last_update=datetime(2026, 4, 25),
                is_installed=False
            ),
            MarketSkill(
                skill_id="5",
                name="知识图谱",
                description="实体-关系建模与查询的知识图谱系统",
                category=SkillCategory.DATABASE,
                author="系统",
                version="1.0",
                rating=4.7,
                download_count=720,
                last_update=datetime(2026, 4, 24),
                is_installed=True
            ),
            MarketSkill(
                skill_id="6",
                name="任务分解",
                description="分析/设计/写作类任务的智能分解工具",
                category=SkillCategory.TASK,
                author="系统",
                version="1.0",
                rating=4.3,
                download_count=540,
                last_update=datetime(2026, 4, 23),
                is_installed=True
            ),
            MarketSkill(
                skill_id="7",
                name="距离计算",
                description="基于 Haversine 公式的地理距离计算工具",
                category=SkillCategory.GEO,
                author="系统",
                version="1.0",
                rating=4.2,
                download_count=430,
                last_update=datetime(2026, 4, 22),
                is_installed=False
            ),
            MarketSkill(
                skill_id="8",
                name="高程数据",
                description="获取指定坐标高程数据（SRTM/GTOPO30）",
                category=SkillCategory.GEO,
                author="系统",
                version="1.0",
                rating=4.1,
                download_count=380,
                last_update=datetime(2026, 4, 21),
                is_installed=False
            ),
            MarketSkill(
                skill_id="9",
                name="技能进化",
                description="L0-L4 分层记忆系统的技能进化引擎",
                category=SkillCategory.LEARNING,
                author="系统",
                version="1.0",
                rating=4.9,
                download_count=1100,
                last_update=datetime(2026, 4, 28),
                is_installed=True
            ),
            MarketSkill(
                skill_id="10",
                name="大气扩散模型",
                description="基于 AERMOD 的大气影响模拟工具",
                category=SkillCategory.SIMULATION,
                author="系统",
                version="1.0",
                rating=4.0,
                download_count=250,
                last_update=datetime(2026, 4, 20),
                is_installed=False
            )
        ]
        
        for skill in mock_skills:
            self.skills[skill.skill_id] = skill
        
        self._refresh_list()
    
    def _refresh_list(self):
        """刷新技能列表"""
        self.skill_list.clear()
        
        # 筛选和排序
        skills = list(self.skills.values())
        
        # 按类别筛选
        category = self.category_combo.currentText()
        if category != "全部类别":
            skills = [s for s in skills if s.category.value == category]
        
        # 按关键词搜索
        keyword = self.search_edit.text().lower()
        if keyword:
            skills = [s for s in skills if keyword in s.name.lower() or keyword in s.description.lower()]
        
        # 排序
        sort_by = self.sort_combo.currentText()
        if sort_by == "评分":
            skills.sort(key=lambda x: x.rating, reverse=True)
        elif sort_by == "下载量":
            skills.sort(key=lambda x: x.download_count, reverse=True)
        elif sort_by == "更新时间":
            skills.sort(key=lambda x: x.last_update, reverse=True)
        
        # 添加到列表
        for skill in skills:
            item = SkillCard(skill)
            self.skill_list.addItem(item)
    
    def _filter_skills(self):
        """过滤技能"""
        self._refresh_list()
    
    def _on_skill_click(self, item):
        """点击技能卡片"""
        if isinstance(item, SkillCard):
            self._show_skill_detail(item.skill)
    
    def _show_skill_detail(self, skill: MarketSkill):
        """显示技能详情"""
        # 清空详情面板
        for i in reversed(range(self.detail_layout.count())):
            self.detail_layout.itemAt(i).widget().setParent(None)
        
        # 添加详情内容
        title_label = QLabel(f"<h2>{skill.name}</h2>")
        self.detail_layout.addWidget(title_label)
        
        desc_label = QLabel(f"<p>{skill.description}</p>")
        desc_label.setWordWrap(True)
        self.detail_layout.addWidget(desc_label)
        
        info_layout = QHBoxLayout()
        info_layout.addWidget(QLabel(f"<b>类别:</b> {skill.category.value}"))
        info_layout.addWidget(QLabel(f"<b>作者:</b> {skill.author}"))
        info_layout.addWidget(QLabel(f"<b>版本:</b> {skill.version}"))
        self.detail_layout.addLayout(info_layout)
        
        stats_layout = QHBoxLayout()
        stats_layout.addWidget(QLabel(f"⭐ {skill.rating}"))
        stats_layout.addWidget(QLabel(f"📥 {skill.download_count} 次下载"))
        stats_layout.addWidget(QLabel(f"📅 {skill.last_update.strftime('%Y-%m-%d')}"))
        self.detail_layout.addLayout(stats_layout)
        
        # 操作按钮
        btn_layout = QHBoxLayout()
        
        if skill.is_installed:
            status_btn = QPushButton("✓ 已安装")
            status_btn.setEnabled(False)
            btn_layout.addWidget(status_btn)
        else:
            install_btn = QPushButton("安装技能")
            install_btn.clicked.connect(lambda: self._install_skill(skill))
            btn_layout.addWidget(install_btn)
        
        rate_btn = QPushButton("评分")
        rate_btn.clicked.connect(lambda: self._show_rating_dialog(skill))
        btn_layout.addWidget(rate_btn)
        
        self.detail_layout.addLayout(btn_layout)
    
    def _install_skill(self, skill: MarketSkill):
        """安装技能"""
        asyncio.create_task(self._perform_install(skill))
    
    async def _perform_install(self, skill: MarketSkill):
        """执行安装"""
        # 模拟安装过程
        await asyncio.sleep(1)
        
        skill.is_installed = True
        skill.download_count += 1
        self._refresh_list()
        self.skill_installed.emit(skill)
    
    def _show_rating_dialog(self, skill: MarketSkill):
        """显示评分对话框"""
        from PyQt6.QtWidgets import QDialog, QFormLayout, QSpinBox, QTextEdit
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"评分: {skill.name}")
        
        layout = QFormLayout(dialog)
        
        rating_spin = QSpinBox()
        rating_spin.setRange(1, 5)
        rating_spin.setValue(int(skill.rating))
        layout.addRow("评分 (1-5):", rating_spin)
        
        feedback_edit = QTextEdit()
        feedback_edit.setPlaceholderText("输入反馈意见...")
        layout.addRow("反馈:", feedback_edit)
        
        ok_btn = QPushButton("提交")
        ok_btn.clicked.connect(lambda: self._submit_rating(skill, rating_spin.value(), feedback_edit.toPlainText()))
        layout.addWidget(ok_btn)
        
        dialog.exec()
    
    def _submit_rating(self, skill: MarketSkill, rating: int, feedback: str):
        """提交评分"""
        # 更新评分（简单实现：取平均值）
        skill.rating = (skill.rating * 10 + rating) / 11
        self._refresh_list()
        self.skill_rated.emit(skill.skill_id, rating)