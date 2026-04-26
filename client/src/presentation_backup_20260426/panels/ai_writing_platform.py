"""
AI 智能写作平台（现代笔记 + 自动化创作）
=======================================

设计理念：
- AI Agent 驱动：对话式创作，AI 辅助生成
- 分层生成架构：世界观 → 大纲 → 卷 → 章 → 段落
- 知识图谱：保持角色、剧情、世界观一致性
- 多文体支持：小说、论文、博客、报告等
- 自动化流水线：批量生成、预览、发布

核心功能：
1. 作品/项目管理
2. 世界观设定管理
3. 角色/势力管理
4. 多层级大纲（卷/章/节）
5. AI 辅助生成（多种模式）
6. 实时预览
7. 多格式导出
8. 多平台发布

Author: Hermes Desktop Team
Date: 2026-04-22
"""

import json
import logging
import time
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict
from enum import Enum

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QSplitter, QTreeWidget, QTreeWidgetItem,
    QListWidget, QListWidgetItem, QFrame, QTabWidget,
    QGroupBox, QScrollArea, QStackedWidget, QProgressBar,
    QMessageBox, QFileDialog, QComboBox, QSpinBox,
    QTextBrowser, QGridLayout, QFormLayout, QCheckBox,
    QTextEdit,
)
from PyQt6.QtGui import QFont, QColor

logger = logging.getLogger(__name__)

# 样式常量
STYLE_PRIMARY_BTN = """
    QPushButton {
        background: #10B981;
        color: white;
        border: none;
        border-radius: 8px;
        padding: 10px 20px;
        font-size: 14px;
        font-weight: bold;
    }
    QPushButton:hover { background: #059669; }
    QPushButton:pressed { background: #047857; }
"""

STYLE_SECONDARY_BTN = """
    QPushButton {
        background: white;
        color: #10B981;
        border: 2px solid #10B981;
        border-radius: 8px;
        padding: 8px 16px;
        font-size: 13px;
        font-weight: bold;
    }
    QPushButton:hover { background: #ECFDF5; }
"""

STYLE_CARD = """
    QFrame {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
    }
"""


# ═══════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════

class WritingGenre(Enum):
    """写作体裁"""
    FANTASY_NOVEL = "玄幻小说"
    WUXIA_NOVEL = "武侠小说"
    SCI_FI_NOVEL = "科幻小说"
    ROMANCE_NOVEL = "言情小说"
    MYSTERY_NOVEL = "悬疑小说"
    ACADEMIC_PAPER = "学术论文"
    BLOG_POST = "博客文章"
    TECHNICAL_DOC = "技术文档"
    BUSINESS_REPORT = "商业报告"
    SCRIPT = "剧本"
    POETRY = "诗歌"
    OTHER = "其他"


class WritingMode(Enum):
    """写作模式"""
    MANUAL = "手动写作"
    AI_ASSIST = "AI 辅助"
    AI_GENERATE = "AI 生成"
    AI_CONTINUATION = "AI 续写"
    AI_EXPAND = "AI 扩写"
    AI_SUMMARIZE = "AI 摘要"


@dataclass
class WorldSetting:
    """世界观设定"""
    name: str = ""
    description: str = ""
    rules: List[str] = field(default_factory=list)
    locations: List[Dict] = field(default_factory=list)
    factions: List[Dict] = field(default_factory=list)
    magic_system: Dict = field(default_factory=dict)
    timeline: List[Dict] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)


@dataclass
class Character:
    """角色"""
    id: str = ""
    name: str = ""
    description: str = ""
    role: str = ""  # 主角/配角/反派
    personality: str = ""
    background: str = ""
    abilities: List[str] = field(default_factory=list)
    relationships: Dict[str, str] = field(default_factory=dict)
    status: str = "active"  # active/dead/unknown
    metadata: Dict = field(default_factory=dict)


@dataclass
class Chapter:
    """章节"""
    id: str = ""
    title: str = ""
    number: int = 0
    volume_id: str = ""
    outline: str = ""
    content: str = ""
    word_count: int = 0
    status: str = "draft"  # draft/review/published
    notes: str = ""
    characters_involved: List[str] = field(default_factory=list)
    locations: List[str] = field(default_factory=list)
    plot_points: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)


@dataclass
class Volume:
    """卷"""
    id: str = ""
    title: str = ""
    number: int = 0
    description: str = ""
    chapters: List[Chapter] = field(default_factory=list)
    word_count: int = 0
    status: str = "draft"
    metadata: Dict = field(default_factory=dict)


@dataclass
class NovelProject:
    """小说项目"""
    id: str = ""
    title: str = ""
    author: str = ""
    genre: str = WritingGenre.FANTASY_NOVEL.value
    synopsis: str = ""
    target_word_count: int = 3000000  # 300万字
    current_word_count: int = 0
    world_setting: WorldSetting = field(default_factory=WorldSetting)
    characters: List[Character] = field(default_factory=list)
    volumes: List[Volume] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    metadata: Dict = field(default_factory=dict)


# ═══════════════════════════════════════════
# AI 写作引擎
# ═══════════════════════════════════════════

class AIWritingEngine:
    """
    AI 写作引擎
    
    负责：
    1. 基于世界观生成内容
    2. 保持角色一致性
    3. 剧情连贯性
    4. 自动化批量生成
    """
    
    def __init__(self):
        self.project: Optional[NovelProject] = None
        self.generation_context: Dict[str, Any] = {}
        
    def set_project(self, project: NovelProject):
        """设置当前项目"""
        self.project = project
        self._build_generation_context()
    
    def _build_generation_context(self):
        """构建生成上下文"""
        if not self.project:
            return
            
        self.generation_context = {
            "title": self.project.title,
            "genre": self.project.genre,
            "synopsis": self.project.synopsis,
            "world_setting": {
                "name": self.project.world_setting.name,
                "rules": self.project.world_setting.rules,
                "magic_system": self.project.world_setting.magic_system,
            },
            "characters": [
                {
                    "name": c.name,
                    "role": c.role,
                    "personality": c.personality,
                    "abilities": c.abilities,
                }
                for c in self.project.characters
            ],
            "volumes": [
                {"title": v.title, "description": v.description}
                for v in self.project.volumes
            ],
        }
    
    async def generate_chapter(
        self,
        chapter: Chapter,
        previous_chapter: Optional[Chapter] = None,
        mode: WritingMode = WritingMode.AI_GENERATE,
    ) -> str:
        """
        生成章节内容
        
        Args:
            chapter: 章节大纲
            previous_chapter: 前一章内容（用于连贯性）
            mode: 生成模式
            
        Returns:
            生成的章节内容
        """
        if not self.project:
            return "[错误：未设置项目]"
        
        # 构建提示词
        prompt = self._build_chapter_prompt(chapter, previous_chapter, mode)
        
        # 调用 AI（模拟）
        # 实际需要集成 Ollama 或其他 LLM
        content = await self._call_llm(prompt)
        
        return content
    
    def _build_chapter_prompt(
        self,
        chapter: Chapter,
        previous_chapter: Optional[Chapter],
        mode: WritingMode,
    ) -> str:
        """构建章节生成提示词"""
        ctx = self.generation_context
        
        prompt = f"""你是专业的{ctx['genre']}小说作家。请根据以下信息生成章节内容。

## 作品信息
- 标题: {ctx['title']}
- 类型: {ctx['genre']}
- 简介: {ctx['synopsis']}

## 世界观
{ctx['world_setting'].get('name', '未设定')}
规则: {', '.join(ctx['world_setting'].get('rules', []))}

## 主要角色
{chr(10).join(f"- {c['name']} ({c['role']}): {c['personality']}" for c in ctx['characters'][:10])}

## 章节信息
- 标题: {chapter.title}
- 章节号: 第 {chapter.number} 章
- 大纲: {chapter.outline}
- 涉及角色: {', '.join(chapter.characters_involved)}
- 场景: {', '.join(chapter.locations)}

## 前一章内容（参考）
{previous_chapter.content[:500] if previous_chapter else '无'}

## 要求
1. 字数约 3000 字
2. 保持角色性格一致
3. 剧情连贯
4. 语言生动，有画面感
5. 使用中文

请生成章节正文：
"""
        return prompt
    
    async def _call_llm(self, prompt: str) -> str:
        """调用 LLM（模拟）"""
        await asyncio.sleep(2)  # 模拟延迟
        
        # 模拟生成
        return f"""（AI 生成的章节内容）

本章讲述了精彩的故事...

[这是模拟内容，实际应该调用 LLM API]

（约 3000 字）"""
    
    async def generate_volume_outline(self, volume: Volume) -> List[Chapter]:
        """生成卷的章节大纲"""
        # 根据卷描述生成章节列表
        chapters = []
        for i in range(1, 11):  # 默认每卷10章
            chapter = Chapter(
                id=f"ch_{volume.id}_{i}",
                title=f"第{i}章",
                number=i,
                volume_id=volume.id,
                outline="待补充",
                status="draft",
            )
            chapters.append(chapter)
        
        return chapters
    
    async def batch_generate_chapters(
        self,
        chapters: List[Chapter],
        callback=None,
    ) -> List[Chapter]:
        """批量生成章节"""
        results = []
        
        for i, chapter in enumerate(chapters):
            prev_chapter = results[-1] if results else None
            content = await self.generate_chapter(chapter, prev_chapter)
            chapter.content = content
            chapter.word_count = len(content)
            results.append(chapter)
            
            if callback:
                callback(i + 1, len(chapters), chapter)
        
        return results


# ═══════════════════════════════════════════
# UI 面板
# ═══════════════════════════════════════════

class AIWritingPanel(QWidget):
    """AI 智能写作面板"""
    
    # 信号
    project_saved = pyqtSignal(dict)
    chapter_generated = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_state()
        self._init_ui()
        self._load_sample_project()
    
    def _init_state(self):
        """初始化状态"""
        self.project: Optional[NovelProject] = None
        self.writing_engine = AIWritingEngine()
        self.current_chapter: Optional[Chapter] = None
        
        # 写作模式
        self.current_mode = WritingMode.AI_ASSIST
        
        # 生成进度
        self.generation_progress = {"current": 0, "total": 0}

    def _init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 顶部工具栏
        self._setup_toolbar(layout)

        # 主内容区（三栏布局）
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：项目结构
        left_panel = self._create_structure_panel()
        main_splitter.addWidget(left_panel)

        # 中间：写作区
        center_panel = self._create_writing_area()
        main_splitter.addWidget(center_panel)

        # 右侧：AI 助手
        right_panel = self._create_ai_panel()
        main_splitter.addWidget(right_panel)

        # 设置比例
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 2)
        main_splitter.setStretchFactor(2, 1)

        layout.addWidget(main_splitter)

        # 底部状态栏
        self._setup_status_bar(layout)

    def _setup_toolbar(self, parent_layout: QVBoxLayout):
        """设置顶部工具栏"""
        toolbar = QFrame()
        toolbar.setStyleSheet("background: white; border-bottom: 1px solid #e5e7eb;")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(16, 10, 16, 10)

        # 标题
        title = QLabel("✍️ AI 智能写作平台")
        title.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        toolbar_layout.addWidget(title)

        toolbar_layout.addSpacing(20)

        # 新建项目
        new_btn = QPushButton("📁 新建项目")
        new_btn.setStyleSheet(STYLE_SECONDARY_BTN)
        new_btn.clicked.connect(self._on_new_project)
        toolbar_layout.addWidget(new_btn)

        # 打开项目
        open_btn = QPushButton("📂 打开项目")
        open_btn.setStyleSheet(STYLE_SECONDARY_BTN)
        open_btn.clicked.connect(self._on_open_project)
        toolbar_layout.addWidget(open_btn)

        # 保存
        save_btn = QPushButton("💾 保存")
        save_btn.setStyleSheet(STYLE_PRIMARY_BTN)
        save_btn.clicked.connect(self._on_save_project)
        toolbar_layout.addWidget(save_btn)

        toolbar_layout.addStretch()

        # 项目信息
        self.project_label = QLabel("未打开项目")
        self.project_label.setStyleSheet("font-size: 13px; color: #6B7280;")
        toolbar_layout.addWidget(self.project_label)

        parent_layout.addWidget(toolbar)

    def _create_structure_panel(self) -> QWidget:
        """创建项目结构面板（左侧）"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # 选项卡
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #e5e7eb;
                border-radius: 8px;
            }
            QTabBar::tab {
                padding: 8px 12px;
            }
        """)

        # 大纲树
        outline_tab = self._create_outline_tab()
        tabs.addTab(outline_tab, "📑 大纲")

        # 角色管理
        character_tab = self._create_character_tab()
        tabs.addTab(character_tab, "👥 角色")

        # 世界观
        world_tab = self._create_world_tab()
        tabs.addTab(world_tab, "🌍 世界观")

        layout.addWidget(tabs)

        return widget

    def _create_outline_tab(self) -> QWidget:
        """创建大纲标签"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)

        # 工具栏
        btn_layout = QHBoxLayout()
        add_volume_btn = QPushButton("➕ 新建卷")
        add_volume_btn.clicked.connect(self._on_add_volume)
        btn_layout.addWidget(add_volume_btn)

        add_chapter_btn = QPushButton("➕ 新建章")
        add_chapter_btn.clicked.connect(self._on_add_chapter)
        btn_layout.addWidget(add_chapter_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 大纲树
        self.outline_tree = QTreeWidget()
        self.outline_tree.setHeaderLabels(["标题", "状态", "字数"])
        self.outline_tree.setColumnWidth(0, 200)
        self.outline_tree.itemClicked.connect(self._on_chapter_selected)
        layout.addWidget(self.outline_tree)

        return widget

    def _create_character_tab(self) -> QWidget:
        """创建角色管理标签"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)

        # 添加按钮
        add_char_btn = QPushButton("➕ 新建角色")
        add_char_btn.clicked.connect(self._on_add_character)
        layout.addWidget(add_char_btn)

        # 角色列表
        self.character_list = QListWidget()
        self.character_list.itemClicked.connect(self._on_character_selected)
        layout.addWidget(self.character_list)

        return widget

    def _create_world_tab(self) -> QWidget:
        """创建世界观标签"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)

        # 世界观名称
        form = QFormLayout()
        
        self.world_name_input = QLineEdit()
        self.world_name_input.setPlaceholderText("世界观名称")
        form.addRow("名称:", self.world_name_input)

        self.world_desc_input = QTextEdit()
        self.world_desc_input.setMaximumHeight(100)
        self.world_desc_input.setPlaceholderText("世界观描述")
        form.addRow("描述:", self.world_desc_input)

        layout.addLayout(form)

        # 保存按钮
        save_btn = QPushButton("💾 保存世界观")
        save_btn.clicked.connect(self._on_save_world_setting)
        layout.addWidget(save_btn)

        layout.addStretch()

        return widget

    def _create_writing_area(self) -> QWidget:
        """创建写作区（中间）"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # 章节标题
        title_layout = QHBoxLayout()
        self.chapter_title_label = QLabel("选择章节开始写作")
        self.chapter_title_label.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        title_layout.addWidget(self.chapter_title_label)

        title_layout.addStretch()

        # 写作模式选择
        mode_label = QLabel("模式:")
        title_layout.addWidget(mode_label)
        
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([m.value for m in WritingMode])
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        title_layout.addWidget(self.mode_combo)

        layout.addLayout(title_layout)

        # 写作编辑器
        self.editor = QTextEdit()
        self.editor.setStyleSheet("""
            QTextEdit {
                border: 1px solid #e5e7eb;
                border-radius: 12px;
                padding: 16px;
                font-size: 15px;
                line-height: 1.8;
                font-family: "Microsoft YaHei", sans-serif;
            }
        """)
        self.editor.setPlaceholderText("开始写作...")
        layout.addWidget(self.editor)

        # 底部工具栏
        bottom_layout = QHBoxLayout()
        
        # 字数统计
        self.word_count_label = QLabel("字数: 0")
        bottom_layout.addWidget(self.word_count_label)

        bottom_layout.addStretch()

        # AI 生成按钮
        ai_generate_btn = QPushButton("🤖 AI 生成")
        ai_generate_btn.setStyleSheet(STYLE_PRIMARY_BTN)
        ai_generate_btn.clicked.connect(self._on_ai_generate)
        bottom_layout.addWidget(ai_generate_btn)

        # AI 续写按钮
        ai_continue_btn = QPushButton("✍️ AI 续写")
        ai_continue_btn.setStyleSheet(STYLE_SECONDARY_BTN)
        ai_continue_btn.clicked.connect(self._on_ai_continue)
        bottom_layout.addWidget(ai_continue_btn)

        # 预览按钮
        preview_btn = QPushButton("👁️ 预览")
        preview_btn.setStyleSheet(STYLE_SECONDARY_BTN)
        preview_btn.clicked.connect(self._on_preview)
        bottom_layout.addWidget(preview_btn)

        layout.addLayout(bottom_layout)

        return widget

    def _create_ai_panel(self) -> QWidget:
        """创建 AI 助手面板（右侧）"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # AI 对话区
        ai_group = QGroupBox("🤖 AI 写作助手")
        ai_layout = QVBoxLayout()

        # 对话历史
        self.ai_chat_scroll = QScrollArea()
        self.ai_chat_scroll.setWidgetResizable(True)
        self.ai_chat_content = QWidget()
        self.ai_chat_layout = QVBoxLayout(self.ai_chat_content)
        self.ai_chat_layout.addStretch()
        self.ai_chat_scroll.setWidget(self.ai_chat_content)
        ai_layout.addWidget(self.ai_chat_scroll)

        # 输入框
        self.ai_input = QLineEdit()
        self.ai_input.setPlaceholderText("输入写作指令...")
        self.ai_input.returnPressed.connect(self._on_ai_command)
        ai_layout.addWidget(self.ai_input)

        # 快捷操作
        quick_layout = QHBoxLayout()
        quick_actions = [
            ("📝 分析剧情", self._on_analyze_plot),
            ("🎭 角色一致性", self._on_check_consistency),
            ("📊 生成报告", self._on_generate_report),
        ]
        for text, callback in quick_actions:
            btn = QPushButton(text)
            btn.setStyleSheet("""
                QPushButton {
                    background: #F3F4F6;
                    border: 1px solid #E5E7EB;
                    border-radius: 12px;
                    padding: 6px 10px;
                    font-size: 11px;
                }
            """)
            btn.clicked.connect(callback)
            quick_layout.addWidget(btn)
        
        ai_layout.addLayout(quick_layout)

        ai_group.setLayout(ai_layout)
        layout.addWidget(ai_group)

        # 批量生成区
        batch_group = QGroupBox("⚡ 批量生成")
        batch_layout = QVBoxLayout()

        self.target_chapters_spin = QSpinBox()
        self.target_chapters_spin.setRange(1, 100)
        self.target_chapters_spin.setValue(10)
        batch_layout.addWidget(QLabel("目标章节数:"))
        batch_layout.addWidget(self.target_chapters_spin)

        self.progress_bar = QProgressBar()
        batch_layout.addWidget(self.progress_bar)

        batch_generate_btn = QPushButton("🚀 开始批量生成")
        batch_generate_btn.setStyleSheet(STYLE_PRIMARY_BTN)
        batch_generate_btn.clicked.connect(self._on_batch_generate)
        batch_layout.addWidget(batch_generate_btn)

        batch_group.setLayout(batch_layout)
        layout.addWidget(batch_group)

        layout.addStretch()

        return widget

    def _setup_status_bar(self, parent_layout: QVBoxLayout):
        """设置状态栏"""
        status_frame = QFrame()
        status_frame.setStyleSheet("background: #F9FAFB; border-top: 1px solid #e5e7eb;")
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(16, 6, 16, 6)

        self.status_label = QLabel("就绪")
        status_layout.addWidget(self.status_label)

        status_layout.addStretch()

        self.total_words_label = QLabel("总字数: 0")
        status_layout.addWidget(self.total_words_label)

        self.chapters_label = QLabel("章节: 0")
        status_layout.addWidget(self.chapters_label)

        parent_layout.addWidget(status_frame)

    # ─── 事件处理 ──────────────────────────────────

    def _on_new_project(self):
        """新建项目"""
        self.project = NovelProject(
            id=f"proj_{int(time.time())}",
            title="未命名作品",
            author="作者",
            genre=WritingGenre.FANTASY_NOVEL.value,
            target_word_count=3000000,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )
        self.writing_engine.set_project(self.project)
        self._update_ui()
        self._set_status("✅ 已创建新项目")

    def _on_open_project(self):
        """打开项目"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "打开项目", "", "JSON Files (*.json)"
        )
        if not file_path:
            return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.project = NovelProject(**data)
            self.writing_engine.set_project(self.project)
            self._update_ui()
            self._set_status(f"✅ 已打开项目: {self.project.title}")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"打开项目失败: {e}")

    def _on_save_project(self):
        """保存项目"""
        if not self.project:
            QMessageBox.warning(self, "提示", "请先创建或打开项目")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存项目", self.project.title, "JSON Files (*.json)"
        )
        if not file_path:
            return
        
        try:
            data = asdict(self.project)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self._set_status(f"✅ 项目已保存: {file_path}")
            self.project_saved.emit(data)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败: {e}")

    def _on_add_volume(self):
        """新建卷"""
        if not self.project:
            QMessageBox.warning(self, "提示", "请先创建项目")
            return
        
        from PyQt6.QtWidgets import QInputDialog
        title, ok = QInputDialog.getText(self, "新建卷", "卷名:")
        if not ok or not title:
            return
        
        volume = Volume(
            id=f"vol_{len(self.project.volumes)}",
            title=title,
            number=len(self.project.volumes) + 1,
            status="draft",
        )
        self.project.volumes.append(volume)
        self._update_outline_tree()
        self._set_status(f"✅ 已添加卷: {title}")

    def _on_add_chapter(self):
        """新建章节"""
        if not self.project:
            QMessageBox.warning(self, "提示", "请先创建项目")
            return
        
        from PyQt6.QtWidgets import QInputDialog
        title, ok = QInputDialog.getText(self, "新建章节", "章节标题:")
        if not ok or not title:
            return
        
        # 找到最后一卷
        if not self.project.volumes:
            QMessageBox.warning(self, "提示", "请先创建卷")
            return
        
        volume = self.project.volumes[-1]
        chapter = Chapter(
            id=f"ch_{volume.id}_{len(volume.chapters)}",
            title=title,
            number=len(volume.chapters) + 1,
            volume_id=volume.id,
            outline="待补充",
            status="draft",
        )
        volume.chapters.append(chapter)
        self._update_outline_tree()
        self._set_status(f"✅ 已添加章节: {title}")

    def _on_chapter_selected(self, item: QTreeWidgetItem, column: int):
        """选择章节"""
        chapter_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not chapter_id or not self.project:
            return
        
        # 查找章节
        for volume in self.project.volumes:
            for chapter in volume.chapters:
                if chapter.id == chapter_id:
                    self.current_chapter = chapter
                    self._load_chapter_to_editor(chapter)
                    return

    def _on_ai_generate(self):
        """AI 生成章节"""
        if not self.current_chapter:
            QMessageBox.warning(self, "提示", "请先选择章节")
            return
        
        self._set_status("🤖 AI 正在生成章节...")
        self.editor.setPlaceholderText("AI 生成中...")
        
        QTimer.singleShot(100, lambda: self._do_ai_generate())

    async def _do_ai_generate(self):
        """执行 AI 生成"""
        try:
            content = await self.writing_engine.generate_chapter(self.current_chapter)
            self.current_chapter.content = content
            self.current_chapter.word_count = len(content)
            self.editor.setPlainText(content)
            self._update_word_count()
            self._set_status("✅ AI 生成完成")
        except Exception as e:
            self._set_status(f"❌ 生成失败: {e}")

    def _on_ai_continue(self):
        """AI 续写"""
        if not self.current_chapter:
            QMessageBox.warning(self, "提示", "请先选择章节")
            return
        
        self._set_status("✍️ AI 正在续写...")
        # 实现续写逻辑

    def _on_preview(self):
        """预览"""
        if not self.current_chapter:
            return
        
        content = self.editor.toPlainText()
        QMessageBox.information(
            self,
            "预览",
            f"## {self.current_chapter.title}\n\n{content[:1000]}..."
        )

    def _on_ai_command(self):
        """AI 命令"""
        command = self.ai_input.text().strip()
        if not command:
            return
        
        self._add_ai_message("user", command)
        self.ai_input.clear()
        
        # 处理命令
        self._process_ai_command(command)

    def _on_analyze_plot(self):
        """分析剧情"""
        self._add_ai_message("user", "请分析当前剧情走向")
        self._process_ai_command("分析剧情")

    def _on_check_consistency(self):
        """检查角色一致性"""
        self._add_ai_message("user", "检查角色一致性")
        self._process_ai_command("检查角色一致性")

    def _on_generate_report(self):
        """生成报告"""
        self._add_ai_message("user", "生成写作报告")
        self._process_ai_command("生成报告")

    def _on_batch_generate(self):
        """批量生成"""
        if not self.project:
            QMessageBox.warning(self, "提示", "请先创建项目")
            return
        
        count = self.target_chapters_spin.value()
        self._set_status(f"⚡ 开始批量生成 {count} 章...")
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(count)
        
        # 实现批量生成逻辑

    def _on_mode_changed(self, mode: str):
        """写作模式变更"""
        self.current_mode = WritingMode(mode)
        self._set_status(f"已切换到: {mode}")

    def _on_add_character(self):
        """添加角色"""
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "新建角色", "角色名:")
        if not ok or not name:
            return
        
        if self.project:
            char = Character(
                id=f"char_{len(self.project.characters)}",
                name=name,
                role="待定",
            )
            self.project.characters.append(char)
            self._update_character_list()
            self._set_status(f"✅ 已添加角色: {name}")

    def _on_character_selected(self, item: QListWidgetItem):
        """选择角色"""
        pass

    def _on_save_world_setting(self):
        """保存世界观"""
        if self.project:
            self.project.world_setting.name = self.world_name_input.text()
            self.project.world_setting.description = self.world_desc_input.toPlainText()
            self._set_status("✅ 世界观已保存")

    # ─── UI 辅助方法 ──────────────────────────────────

    def _update_ui(self):
        """更新 UI"""
        if self.project:
            self.project_label.setText(f"📖 {self.project.title}")
            self._update_outline_tree()
            self._update_character_list()
            self._update_stats()
        else:
            self.project_label.setText("未打开项目")

    def _update_outline_tree(self):
        """更新大纲树"""
        if not self.project:
            return
        
        self.outline_tree.clear()
        
        for volume in self.project.volumes:
            vol_item = QTreeWidgetItem([
                f"📚 {volume.title}",
                volume.status,
                str(sum(c.word_count for c in volume.chapters))
            ])
            vol_item.setData(0, Qt.ItemDataRole.UserRole, volume.id)
            vol_item.setExpanded(True)
            
            for chapter in volume.chapters:
                ch_item = QTreeWidgetItem([
                    f"📄 {chapter.title}",
                    chapter.status,
                    str(chapter.word_count)
                ])
                ch_item.setData(0, Qt.ItemDataRole.UserRole, chapter.id)
                vol_item.addChild(ch_item)
            
            self.outline_tree.addTopLevelItem(vol_item)
        
        self.chapters_label.setText(f"章节: {sum(len(v.chapters) for v in self.project.volumes)}")

    def _update_character_list(self):
        """更新角色列表"""
        if not self.project:
            return
        
        self.character_list.clear()
        for char in self.project.characters:
            item = QListWidgetItem(f"👤 {char.name} ({char.role})")
            item.setData(Qt.ItemDataRole.UserRole, char.id)
            self.character_list.addItem(item)

    def _update_stats(self):
        """更新统计"""
        if not self.project:
            return
        
        total_words = sum(
            c.word_count 
            for v in self.project.volumes 
            for c in v.chapters
        )
        self.total_words_label.setText(f"总字数: {total_words:,}")
        self.project.current_word_count = total_words

    def _update_word_count(self):
        """更新字数统计"""
        content = self.editor.toPlainText()
        self.word_count_label.setText(f"字数: {len(content):,}")

    def _load_chapter_to_editor(self, chapter: Chapter):
        """加载章节到编辑器"""
        self.chapter_title_label.setText(f"📄 {chapter.title}")
        self.editor.setPlainText(chapter.content)
        self._update_word_count()

    def _set_status(self, message: str):
        """设置状态"""
        self.status_label.setText(message)

    def _add_ai_message(self, role: str, content: str):
        """添加 AI 对话消息"""
        label = QLabel(content)
        label.setWordWrap(True)
        label.setStyleSheet(f"""
            QLabel {{
                background: {'#10B981' if role == 'user' else 'white'};
                color: {'white' if role == 'user' else '#1F2937'};
                border-radius: 12px;
                padding: 8px 12px;
            }}
        """)
        self.ai_chat_layout.insertWidget(self.ai_chat_layout.count() - 1, label)

    def _process_ai_command(self, command: str):
        """处理 AI 命令"""
        # 模拟 AI 响应
        response = f"已收到指令：{command}\n\nAI 正在处理..."
        self._add_ai_message("assistant", response)

    def _load_sample_project(self):
        """加载示例项目"""
        self._add_ai_message("assistant", 
            "👋 欢迎使用 AI 智能写作平台！\n\n"
            "我可以帮你：\n"
            "1. 📖 创建小说项目\n"
            "2. 🌍 设定世界观\n"
            "3. 👥 管理角色\n"
            "4. 📑 编写大纲\n"
            "5. 🤖 AI 自动生成章节\n"
            "6. 🚀 批量生成\n\n"
            "先创建一个新项目吧！"
        )

