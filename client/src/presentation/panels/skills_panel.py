"""
技能与专家角色管理面板
内置 mattpocock/skills (21个) + agency-agents-zh (211个专家角色)
支持：浏览、搜索、启用/禁用、编辑技能与专家角色
架构设计：技能/专家角色变化 → 通知各个智能体（通过AgentRegistry）
"""

import json
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Set

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem,
    QMessageBox, QSplitter, QTextEdit, QTabWidget,
    QComboBox, QProgressBar, QTextBrowser,
)
from PyQt6.QtGui import QTextCursor


# ── 技能发现与管理主界面 ─────────────────────────────────────────────────────────

class SkillsPanel(QWidget):
    """
    技能与专家角色管理面板
    
    架构设计：
    - 技能/专家角色启用/禁用时，通过 AgentRegistry 通知各个智能体
    - 支持用户编辑技能/专家角色的 SKILL.md 文件
    """
    skill_activated = pyqtSignal(str)   # skill 名称（仅供UI使用）
    agent_activated = pyqtSignal(str)   # agent 角色名称（仅供UI使用）

    def __init__(self, parent=None):
        super().__init__(parent)
        self._skills_dirs = self._find_skills_dirs()
        self._agents_dir = self._find_agents_dir()
        self._all_skills: List[Dict] = []
        self._active_skills: Set[str] = set()   # 已启用的技能
        self._active_agents: Set[str] = set()   # 已启用的专家角色
        
        # UI 组件（用于更新进度）
        self.progress_bar: Optional[QProgressBar] = None
        self.update_detail_text: Optional[QTextBrowser] = None
        
        # 获取 AgentRegistry 实例（用于通知各个智能体）
        from client.src.business.agent_registry import get_agent_registry
        self._agent_registry = get_agent_registry()
        
        self._init_ui()
        self._load_all_skills()
        self._load_active_skills()
        self._load_active_agents()
        self._refresh_list()
        self._refresh_agents_list()
        self._refresh_active()
        self._notify_agents_skill_change()   # 初始通知各个智能体（技能）
        self._notify_agents_change()         # 初始通知各个智能体（专家角色）

    # ── 初始化 ─────────────────────────────────────────────────────────────────

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # 标题
        title = QLabel("🧠 技能与专家角色")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)

        desc = QLabel("浏览和启用内置技能库 · mattpocock/skills (21) · agency-agents-zh (211)")
        desc.setStyleSheet("font-size: 14px; color: #666;")
        layout.addWidget(desc)

        # 工具栏（自动更新）
        toolbar = QHBoxLayout()
        self.check_updates_btn = QPushButton("🔄 检查更新")
        self.check_updates_btn.clicked.connect(self._check_updates)
        self.update_all_btn = QPushButton("⬇️ 更新全部")
        self.update_all_btn.clicked.connect(self._update_all)
        self.update_status_label = QLabel("")
        self.update_status_label.setStyleSheet("color: #888; font-size: 12px;")
        toolbar.addWidget(self.check_updates_btn)
        toolbar.addWidget(self.update_all_btn)
        toolbar.addWidget(self.update_status_label)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # 标签页
        tabs = QTabWidget()

        # Tab1: 技能库
        skills_tab = QWidget()
        self._build_skills_tab(skills_tab)
        tabs.addTab(skills_tab, "⚡ 技能库")

        # Tab2: 专家角色
        agents_tab = QWidget()
        self._build_agents_tab(agents_tab)
        tabs.addTab(agents_tab, "👤 专家角色")

        # Tab3: 已启用
        active_tab = QWidget()
        self._build_active_tab(active_tab)
        tabs.addTab(active_tab, "✅ 已启用")

        layout.addWidget(tabs)

        # 进度条（默认隐藏）
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ccc;
                border-radius: 5px;
                text-align: center;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 5px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # 更新详情（默认隐藏）
        self.update_detail_text = QTextBrowser()
        self.update_detail_text.setVisible(False)
        self.update_detail_text.setMaximumHeight(200)
        self.update_detail_text.setStyleSheet("""
            QTextBrowser {
                border: 1px solid #ccc;
                border-radius: 5px;
                padding: 10px;
                background-color: #f9f9f9;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
            }
        """)
        layout.addWidget(self.update_detail_text)

    def _build_skills_tab(self, tab: QWidget):
        """构建技能库标签页"""
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        # 搜索栏
        search_layout = QHBoxLayout()
        search_label = QLabel("搜索:")
        self.skills_search = QLineEdit()
        self.skills_search.setPlaceholderText("搜索技能名称、描述...")
        self.skills_search.textChanged.connect(self._filter_skills)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.skills_search)
        search_layout.addSpacing(20)
        source_label = QLabel("来源:")
        self.source_combo = QComboBox()
        self.source_combo.addItems(["全部", "mattpocock", "agency", "自定义"])
        self.source_combo.currentTextChanged.connect(self._filter_skills)
        search_layout.addWidget(source_label)
        search_layout.addWidget(self.source_combo)
        search_layout.addStretch()
        layout.addLayout(search_layout)

        # 分割器：列表 + 详情
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：技能列表
        left = QWidget()
        left_layout = QVBoxLayout(left)
        self.skills_list = QListWidget()
        self.skills_list.itemClicked.connect(self._on_skill_selected)
        self.skills_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        left_layout.addWidget(self.skills_list)
        splitter.addWidget(left)

        # 右侧：技能详情 + 操作
        right = QWidget()
        right_layout = QVBoxLayout(right)

        self.skill_name_label = QLabel("选择一个技能")
        self.skill_name_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        right_layout.addWidget(self.skill_name_label)

        self.skill_desc_label = QLabel("")
        self.skill_desc_label.setWordWrap(True)
        self.skill_desc_label.setStyleSheet("color: #555; font-size: 13px;")
        right_layout.addWidget(self.skill_desc_label)

        self.skill_source_label = QLabel("")
        self.skill_source_label.setStyleSheet("color: #888; font-size: 12px;")
        right_layout.addWidget(self.skill_source_label)

        # 详情文本
        self.skill_detail = QTextEdit()
        self.skill_detail.setReadOnly(True)
        self.skill_detail.setPlaceholderText("技能详细说明...")
        right_layout.addWidget(self.skill_detail)

        # 操作按钮
        btn_layout = QHBoxLayout()
        self.enable_skill_btn = QPushButton("✅ 启用技能")
        self.enable_skill_btn.clicked.connect(self._enable_selected_skill)
        self.disable_skill_btn = QPushButton("❌ 禁用技能")
        self.disable_skill_btn.clicked.connect(self._disable_selected_skill)
        self.disable_skill_btn.setEnabled(False)
        self.edit_skill_btn = QPushButton("✏️ 编辑")
        self.edit_skill_btn.clicked.connect(self._edit_selected_skill)
        self.edit_skill_btn.setEnabled(False)
        btn_layout.addWidget(self.enable_skill_btn)
        btn_layout.addWidget(self.disable_skill_btn)
        btn_layout.addWidget(self.edit_skill_btn)
        btn_layout.addStretch()
        right_layout.addLayout(btn_layout)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter)

    def _build_agents_tab(self, tab: QWidget):
        """构建专家角色标签页（支持启用/禁用/编辑）"""
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        # 搜索栏
        search_layout = QHBoxLayout()
        search_label = QLabel("搜索:")
        self.agents_search = QLineEdit()
        self.agents_search.setPlaceholderText("搜索专家角色名称、部门...")
        self.agents_search.textChanged.connect(self._filter_agents)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.agents_search)
        search_layout.addSpacing(20)
        dept_label = QLabel("部门:")
        self.dept_combo = QComboBox()
        self.dept_combo.addItem("全部")
        self.dept_combo.currentTextChanged.connect(self._filter_agents)
        search_layout.addWidget(dept_label)
        search_layout.addWidget(self.dept_combo)
        search_layout.addStretch()
        layout.addLayout(search_layout)

        # 分割器：列表 + 详情
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：专家角色列表
        left = QWidget()
        left_layout = QVBoxLayout(left)
        self.agents_list = QListWidget()
        self.agents_list.itemClicked.connect(self._on_agent_selected)
        self.agents_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        left_layout.addWidget(self.agents_list)
        splitter.addWidget(left)

        # 右侧：专家角色详情 + 操作
        right = QWidget()
        right_layout = QVBoxLayout(right)

        self.agent_name_label = QLabel("选择一个专家角色")
        self.agent_name_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        right_layout.addWidget(self.agent_name_label)

        self.agent_desc_label = QLabel("")
        self.agent_desc_label.setWordWrap(True)
        self.agent_desc_label.setStyleSheet("color: #555; font-size: 13px;")
        right_layout.addWidget(self.agent_desc_label)

        self.agent_dept_label = QLabel("")
        self.agent_dept_label.setStyleSheet("color: #888; font-size: 12px;")
        right_layout.addWidget(self.agent_dept_label)

        # 详情文本
        self.agent_detail = QTextEdit()
        self.agent_detail.setReadOnly(True)
        self.agent_detail.setPlaceholderText("专家角色详细说明...")
        right_layout.addWidget(self.agent_detail)

        # 操作按钮
        btn_layout = QHBoxLayout()
        self.enable_agent_btn = QPushButton("✅ 启用专家角色")
        self.enable_agent_btn.clicked.connect(self._enable_selected_agent)
        self.disable_agent_btn = QPushButton("❌ 禁用专家角色")
        self.disable_agent_btn.clicked.connect(self._disable_selected_agent)
        self.disable_agent_btn.setEnabled(False)
        self.edit_agent_btn = QPushButton("✏️ 编辑")
        self.edit_agent_btn.clicked.connect(self._edit_selected_agent)
        self.edit_agent_btn.setEnabled(False)
        btn_layout.addWidget(self.enable_agent_btn)
        btn_layout.addWidget(self.disable_agent_btn)
        btn_layout.addWidget(self.edit_agent_btn)
        btn_layout.addStretch()
        right_layout.addLayout(btn_layout)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter)

    def _build_active_tab(self, tab: QWidget):
        """构建已启用标签页（显示已启用的技能和专家角色）"""
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        info = QLabel("以下技能和专家角色当前已启用，可在对话中直接使用：")
        info.setStyleSheet("color: #555;")
        layout.addWidget(info)

        self.active_list = QListWidget()
        layout.addWidget(self.active_list)

        btn_layout = QHBoxLayout()
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.clicked.connect(self._refresh_active)
        btn_layout.addWidget(refresh_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    # ── 数据加载 ─────────────────────────────────────────────────────────────

    def _find_skills_dirs(self) -> List[Path]:
        """查找所有技能目录（优先项目内置目录）"""
        dirs = []
        project_root = Path(__file__).parent.parent.parent
        
        # 1. 项目内置目录（最高优先级）
        builtin = project_root / ".livingtree" / "skills"
        if builtin.exists():
            dirs.append(builtin)
        
        # 2. 用户级目录（.workbuddy/skills/）
        user_dir = Path.home() / ".workbuddy" / "skills"
        if user_dir.exists() and user_dir not in dirs:
            dirs.append(user_dir)
        
        # 3. 项目级 .workbuddy 目录（兼容旧路径）
        project_workbuddy = project_root / ".workbuddy" / "skills"
        if project_workbuddy.exists() and project_workbuddy not in dirs:
            dirs.append(project_workbuddy)
        
        return dirs

    def _find_agents_dir(self) -> Optional[Path]:
        """查找专家角色目录（优先项目内置目录）"""
        project_root = Path(__file__).parent.parent.parent
        
        # 1. 项目内置目录（.livingtree/skills/agency-agents-zh/）
        builtin = project_root / ".livingtree" / "skills" / "agency-agents-zh"
        if builtin.exists():
            return builtin
        
        # 2. 项目 .workbuddy 目录
        project_wb = project_root / ".workbuddy" / "skills" / "agency-agents-zh"
        if project_wb.exists():
            return project_wb
        
        # 3. 用户级目录
        user_wb = Path.home() / ".workbuddy" / "skills" / "agency-agents-zh"
        if user_wb.exists():
            return user_wb
        
        return None

    def _load_all_skills(self):
        """加载所有技能和专家角色"""
        self._all_skills.clear()

        # 1. 加载 skills 目录下的技能（mattpocock 等）
        for d in self._skills_dirs:
            if not d.exists():
                continue
            for skill_dir in sorted(d.iterdir()):
                if not skill_dir.is_dir() or skill_dir.name.startswith('.'):
                    continue
                skill_md = skill_dir / "SKILL.md"
                if skill_md.exists():
                    meta = self._parse_skill_md(skill_md)
                    meta["dir"] = str(skill_dir)
                    meta["source"] = self._guess_source(skill_dir)
                    self._all_skills.append(meta)

        # 2. 加载 agency-agents-zh 专家角色
        if self._agents_dir and self._agents_dir.exists():
            self._load_agents_as_skills()

    def _parse_skill_md(self, path: Path) -> Dict:
        """解析 SKILL.md，提取 YAML frontmatter"""
        meta = {
            "name": path.parent.name,
            "description": "",
            "location": "",
            "source": "unknown",
            "content_preview": "",
            "full_path": str(path),
        }
        try:
            text = path.read_text(encoding="utf-8")
            if text.startswith("---"):
                parts = text.split("---", 2)
                if len(parts) >= 3:
                    fm_text = parts[1].strip()
                    try:
                        import yaml
                        fm = yaml.safe_load(fm_text) or {}
                        meta["name"] = fm.get("name", meta["name"])
                        meta["description"] = fm.get("description", "")
                        meta["location"] = fm.get("location", "")
                    except Exception:
                        pass
                    meta["content_preview"] = parts[2][:500].strip()
            else:
                meta["content_preview"] = text[:500].strip()
        except Exception:
            pass
        return meta

    def _guess_source(self, skill_dir: Path) -> str:
        """猜测技能来源"""
        path_str = str(skill_dir)
        if "mattpocock" in path_str:
            return "mattpocock"
        if "agency" in path_str:
            return "agency"
        return "custom"

    def _load_agents_as_skills(self):
        """将 agency-agents-zh 角色加载为技能列表项"""
        skip_dirs = {".git", "scripts", "integrations", ".github", "examples"}
        for dept_dir in self._agents_dir.iterdir():
            if not dept_dir.is_dir() or dept_dir.name.startswith('.') or dept_dir.name in skip_dirs:
                continue
            for md_file in dept_dir.glob("*.md"):
                if md_file.name.startswith("README"):
                    continue
                meta = self._parse_agent_md(md_file, dept_dir.name)
                if meta:
                    self._all_skills.append(meta)

    def _parse_agent_md(self, path: Path, department: str) -> Optional[Dict]:
        """解析专家角色 .md 文件"""
        try:
            text = path.read_text(encoding="utf-8")
            return {
                "name": path.stem,
                "description": text[:200].strip().replace("\n", " "),
                "location": "user",
                "source": f"agency-{department}",
                "department": department,
                "content_preview": text[:500],
                "full_path": str(path),
                "dir": str(path.parent),
            }
        except Exception:
            return None

    def _load_active_skills(self):
        """加载已启用的技能列表"""
        active_file = Path.home() / ".workbuddy" / "active_skills.json"
        if active_file.exists():
            try:
                data = json.loads(active_file.read_text(encoding="utf-8"))
                self._active_skills = set(data.get("active", []))
            except Exception:
                pass

    def _load_active_agents(self):
        """加载已启用的专家角色列表"""
        active_file = Path.home() / ".workbuddy" / "active_agents.json"
        if active_file.exists():
            try:
                data = json.loads(active_file.read_text(encoding="utf-8"))
                self._active_agents = set(data.get("active", []))
            except Exception:
                pass

    # ── 保存与通知 ─────────────────────────────────────────────────────────────

    def _save_active_skills(self):
        """保存已启用的技能列表，并通知智能体"""
        active_file = Path.home() / ".workbuddy" / "active_skills.json"
        active_file.parent.mkdir(parents=True, exist_ok=True)
        data = {"active": sorted(self._active_skills)}
        active_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        
        # 通知各个智能体（架构设计：技能变化 → 通知智能体）
        self._notify_agents_skill_change()

    def _save_active_agents(self):
        """保存已启用的专家角色列表，并通知智能体"""
        active_file = Path.home() / ".workbuddy" / "active_agents.json"
        active_file.parent.mkdir(parents=True, exist_ok=True)
        data = {"active": sorted(self._active_agents)}
        active_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        
        # 通知各个智能体（架构设计：专家角色变化 → 通知智能体）
        self._notify_agents_change()

    def _notify_agents_skill_change(self):
        """
        通知各个智能体技能变化（架构核心方法）
        
        设计原则：
        - SkillsPanel 不直接通知UI组件
        - 而是通过 AgentRegistry 通知所有已注册的智能体
        - 智能体自己决定如何响应技能变化
        """
        if hasattr(self, '_agent_registry'):
            self._agent_registry.notify_skill_change(self._active_skills)
            print(f"[SkillsPanel] 已通知智能体技能变化: {len(self._active_skills)} 个启用技能")

    def _notify_agents_change(self):
        """
        通知各个智能体专家角色变化（架构核心方法）
        
        设计原则：
        - 专家角色变化时，通过 AgentRegistry 通知所有已注册的智能体
        - 智能体自己决定如何响应专家角色变化
        """
        if hasattr(self, '_agent_registry'):
            self._agent_registry.notify_agent_change(self._active_agents)
            print(f"[SkillsPanel] 已通知智能体专家角色变化: {len(self._active_agents)} 个启用专家角色")

    # ── UI 刷新 ─────────────────────────────────────────────────────────────────

    def _refresh_list(self):
        """刷新技能列表"""
        self.skills_list.clear()
        query = self.skills_search.text().lower() if hasattr(self, 'skills_search') else ""
        source_filter = self.source_combo.currentText() if hasattr(self, 'source_combo') else "全部"

        for skill in self._all_skills:
            # 只显示技能（非专家角色）
            if skill["source"].startswith("agency"):
                continue
            # 来源过滤
            if source_filter != "全部":
                if source_filter == "mattpocock" and skill["source"] != "mattpocock":
                    continue
                if source_filter == "agency" and not skill["source"].startswith("agency"):
                    continue
                if source_filter == "自定义" and skill["source"] != "custom":
                    continue
            # 搜索过滤
            if query:
                haystack = (skill["name"] + skill["description"]).lower()
                if query not in haystack:
                    continue

            item_text = f"[{skill['source']}] {skill['name']}"
            if skill["name"] in self._active_skills:
                item_text = "✅ " + item_text
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, skill)
            self.skills_list.addItem(item)

    def _refresh_agents_list(self):
        """刷新专家角色列表"""
        self.agents_list.clear()
        if not self._agents_dir:
            return
        query = self.agents_search.text().lower() if hasattr(self, 'agents_search') else ""
        dept_filter = self.dept_combo.currentText() if hasattr(self, 'dept_combo') else "全部"

        # 更新部门下拉框
        if hasattr(self, 'dept_combo') and self.dept_combo.count() == 1:
            skip = {".git", "scripts", "integrations", ".github", "examples"}
            for d in self._agents_dir.iterdir():
                if d.is_dir() and not d.name.startswith('.') and d.name not in skip:
                    self.dept_combo.addItem(d.name)

        for skill in self._all_skills:
            # 只显示专家角色
            if not skill["source"].startswith("agency"):
                continue
            if dept_filter != "全部" and skill.get("department", "") != dept_filter:
                continue
            if query:
                if query not in skill["name"].lower() and query not in skill.get("department", "").lower():
                    continue
            
            # 标记已启用的专家角色
            item_text = f"[{skill.get('department','')}] {skill['name']}"
            if skill["name"] in self._active_agents:
                item_text = "✅ " + item_text
            
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, skill)
            self.agents_list.addItem(item)

    def _refresh_active(self):
        """刷新已启用列表（显示已启用的技能和专家角色）"""
        self.active_list.clear()
        
        # 显示已启用的技能
        for name in sorted(self._active_skills):
            self.active_list.addItem(f"⚡ [技能] {name}")
        
        # 显示已启用的专家角色
        for name in sorted(self._active_agents):
            self.active_list.addItem(f"👤 [专家] {name}")

    def _filter_skills(self):
        self._refresh_list()

    def _filter_agents(self):
        self._refresh_agents_list()

    # ── 事件处理（技能） ───────────────────────────────────────────────────────

    def _on_skill_selected(self, item: QListWidgetItem):
        """技能选中事件"""
        skill = item.data(Qt.ItemDataRole.UserRole)
        if not skill:
            return
        self.skill_name_label.setText(skill["name"])
        self.skill_desc_label.setText(skill.get("description", "无描述"))
        self.skill_source_label.setText(f"来源: {skill['source']}  |  路径: {skill.get('dir', '')}")
        self.skill_detail.setPlainText(skill.get("content_preview", "")[:2000])

        is_active = skill["name"] in self._active_skills
        self.enable_skill_btn.setEnabled(not is_active)
        self.disable_skill_btn.setEnabled(is_active)
        self.edit_skill_btn.setEnabled(True)  # 允许编辑

    def _enable_selected_skill(self):
        """启用选中的技能"""
        item = self.skills_list.currentItem()
        if not item:
            return
        skill = item.data(Qt.ItemDataRole.UserRole)
        if not skill:
            return
        self._active_skills.add(skill["name"])
        self._save_active_skills()
        self._refresh_list()
        self._refresh_active()
        self.skill_name_label.setText(skill["name"] + " ✅ 已启用")
        QMessageBox.information(self, "启用成功", f"技能 [{skill['name']}] 已启用，可在对话中使用。")

    def _disable_selected_skill(self):
        """禁用选中的技能"""
        item = self.skills_list.currentItem()
        if not item:
            return
        skill = item.data(Qt.ItemDataRole.UserRole)
        if not skill:
            return
        self._active_skills.discard(skill["name"])
        self._save_active_skills()
        self._refresh_list()
        self._refresh_active()
        self.skill_name_label.setText(skill["name"] + " ❌ 已禁用")

    def _edit_selected_skill(self):
        """编辑选中的技能（打开编辑器）"""
        item = self.skills_list.currentItem()
        if not item:
            return
        skill = item.data(Qt.ItemDataRole.UserRole)
        if not skill:
            return
        
        file_path = skill.get("full_path", "")
        if not file_path or not Path(file_path).exists():
            QMessageBox.warning(self, "无法编辑", f"找不到文件: {file_path}")
            return
        
        self._open_editor(file_path)

    # ── 事件处理（专家角色） ─────────────────────────────────────────────────

    def _on_agent_selected(self, item: QListWidgetItem):
        """专家角色选中事件"""
        skill = item.data(Qt.ItemDataRole.UserRole)
        if not skill:
            return
        self.agent_name_label.setText(skill["name"])
        self.agent_desc_label.setText(skill.get("description", "无描述"))
        self.agent_dept_label.setText(f"部门: {skill.get('department', '')}  |  路径: {skill.get('dir', '')}")
        self.agent_detail.setPlainText(skill.get("content_preview", "")[:2000])

        is_active = skill["name"] in self._active_agents
        self.enable_agent_btn.setEnabled(not is_active)
        self.disable_agent_btn.setEnabled(is_active)
        self.edit_agent_btn.setEnabled(True)  # 允许编辑

    def _enable_selected_agent(self):
        """启用选中的专家角色"""
        item = self.agents_list.currentItem()
        if not item:
            return
        skill = item.data(Qt.ItemDataRole.UserRole)
        if not skill:
            return
        self._active_agents.add(skill["name"])
        self._save_active_agents()
        self._refresh_agents_list()
        self._refresh_active()
        self.agent_name_label.setText(skill["name"] + " ✅ 已启用")
        QMessageBox.information(self, "启用成功", f"专家角色 [{skill['name']}] 已启用，可在对话中使用。")

    def _disable_selected_agent(self):
        """禁用选中的专家角色"""
        item = self.agents_list.currentItem()
        if not item:
            return
        skill = item.data(Qt.ItemDataRole.UserRole)
        if not skill:
            return
        self._active_agents.discard(skill["name"])
        self._save_active_agents()
        self._refresh_agents_list()
        self._refresh_active()
        self.agent_name_label.setText(skill["name"] + " ❌ 已禁用")

    def _edit_selected_agent(self):
        """编辑选中的专家角色（打开编辑器）"""
        item = self.agents_list.currentItem()
        if not item:
            return
        skill = item.data(Qt.ItemDataRole.UserRole)
        if not skill:
            return
        
        file_path = skill.get("full_path", "")
        if not file_path or not Path(file_path).exists():
            QMessageBox.warning(self, "无法编辑", f"找不到文件: {file_path}")
            return
        
        self._open_editor(file_path)

    def _open_editor(self, file_path: str):
        """
        打开编辑器编辑文件
        
        尝试使用系统默认编辑器打开文件。
        Windows: 使用 notepad 或系统默认程序
        """
        try:
            if os.name == 'nt':  # Windows
                os.startfile(file_path)
            else:  # Linux/Mac
                subprocess.run(['xdg-open', file_path], check=True)
        except Exception as e:
            QMessageBox.warning(self, "打开编辑器失败", f"无法打开编辑器: {e}\n\n文件路径: {file_path}")

    # ── 自动更新功能 ─────────────────────────────────────────

    def _check_updates(self):
        """检查更新（按钮回调）"""
        self.update_status_label.setText("正在检查更新...")
        self.check_updates_btn.setEnabled(False)
        self.update_all_btn.setEnabled(False)

        try:
            from client.src.business.skill_updater import get_skill_updater
            updater = get_skill_updater()
            check_results = updater.check_updates()

            has_update = False
            status_parts = []

            for directory, has_upd, status in check_results:
                status_parts.append(f"{Path(directory).name}: {status}")
                if has_upd:
                    has_update = True

            status_text = "  |  ".join(status_parts)
            if has_update:
                self.update_status_label.setText("🔔 有可用更新！  |  " + status_text)
                self.update_all_btn.setEnabled(True)  # 启用"更新全部"按钮
            else:
                self.update_status_label.setText("✅ " + status_text)

        except Exception as e:
            self.update_status_label.setText(f"❌ 检查失败: {e}")
            print(f"[SkillsPanel] 检查更新失败: {e}")

        finally:
            self.check_updates_btn.setEnabled(True)

    def _update_all(self):
        """更新全部（按钮回调）"""
        self.update_status_label.setText("正在更新...")
        self.check_updates_btn.setEnabled(False)
        self.update_all_btn.setEnabled(False)

        # 显示进度条
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        # 隐藏之前的更新详情
        self.update_detail_text.setVisible(False)

        try:
            from client.src.business.skill_updater import get_skill_updater
            updater = get_skill_updater()

            # 定义进度回调函数
            def progress_callback(current, total, message):
                """更新进度条"""
                if total > 0:
                    percent = int(current * 100 / total)
                    self.progress_bar.setValue(percent)
                self.update_status_label.setText(message)
                # 强制处理事件，确保 UI 更新
                from PyQt6.QtCore import QCoreApplication
                QCoreApplication.processEvents()

            # 执行更新（带进度回调）
            update_results = updater.update_all(progress_callback=progress_callback)

            # 更新完成，进度条设为 100%
            self.progress_bar.setValue(100)

            success_count = sum(1 for r in update_results if r["success"] and r.get("updated"))
            failed_count = sum(1 for r in update_results if not r["success"])

            if success_count > 0:
                # 更新成功，重载技能列表
                self._load_all_skills()
                self._refresh_list()
                self._refresh_agents_list()
                self._refresh_active()

                status_text = f"✅ 已更新 {success_count} 个目录"
                if failed_count > 0:
                    status_text += f"，{failed_count} 个失败"
                self.update_status_label.setText(status_text)

                # 显示更新详情
                self._show_update_details(update_results)

                QMessageBox.information(self, "更新成功", f"已成功更新 {success_count} 个技能目录。\n\n请查看更新详情。")
            else:
                status_text = f"❌ 更新失败（{failed_count} 个）"
                self.update_status_label.setText(status_text)

        except Exception as e:
            self.update_status_label.setText(f"❌ 更新失败: {e}")
            print(f"[SkillsPanel] 更新失败: {e}")
            QMessageBox.warning(self, "更新失败", str(e))

        finally:
            # 隐藏进度条
            self.progress_bar.setVisible(False)

            self.check_updates_btn.setEnabled(True)
            self.update_all_btn.setEnabled(True)

    def _show_update_details(self, update_results):
        """
        显示更新详情（哪些文件被更新、更新内容）

        Args:
            update_results: update_all() 的返回结果
        """
        # 清空之前的详情
        self.update_detail_text.clear()

        # 显示更新详情
        detail_lines = ["📊 更新详情\n"]

        for result in update_results:
            if not result.get("updated"):
                continue

            dir_name = Path(result["dir"]).name
            detail_lines.append(f"\n📁 {dir_name}")

            # 显示更新的文件列表
            files = result.get("files", [])
            if files:
                for file_info in files:
                    file_name = file_info.get("file", "")
                    status = file_info.get("status", "")

                    # 状态解释
                    status_text = ""
                    if status == "A":
                        status_text = "✅ 新增"
                    elif status == "M":
                        status_text = "📝 修改"
                    elif status == "D":
                        status_text = "❌ 删除"
                    elif status.startswith("R"):
                        status_text = "🔄 重命名"
                    else:
                        status_text = status

                    detail_lines.append(f"  {status_text}: {file_name}")
            else:
                detail_lines.append("  （无文件变更详情）")

        # 如果没有更新详情
        if len(detail_lines) <= 1:
            detail_lines.append("\n（无详细更新信息）")

        # 显示详情
        self.update_detail_text.setVisible(True)
        self.update_detail_text.setPlainText("\n".join(detail_lines))

        # 滚动到顶部
        cursor = self.update_detail_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        self.update_detail_text.setTextCursor(cursor)


# ── 导出供主窗口使用 ─────────────────────────────────────────────────────────

def create_skills_panel(parent=None) -> QWidget:
    """工厂函数：创建技能面板"""
    return SkillsPanel(parent=parent)
