#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Git 集成组件
=============

功能：
1. 显示 Git 状态（modified, staged, untracked）
2. 暂存/取消暂存文件
3. 提交更改
4. 查看提交历史
5. 推送到远程仓库
6. 拉取更新
7. 分支管理

Author: LivingTreeAI Agent
Date: 2026-04-26
"""

import os
import subprocess
from typing import Optional, List, Dict
from dataclasses import dataclass, field


# ── 数据结构 ─────────────────────────────────────────────────────

@dataclass
class GitFileStatus:
    """Git 文件状态"""
    file_path: str
    status: str  # 'modified', 'added', 'deleted', 'renamed', 'untracked'
    staged: bool = False


@dataclass
class GitCommit:
    """Git 提交"""
    commit_hash: str
    author: str
    date: str
    message: str


# ── Git 集成管理器 ─────────────────────────────────────────────

class GitManager:
    """
    Git 管理器
    
    功能：
    1. 获取 Git 状态
    2. 暂存/提交/推送
    3. 查看历史
    4. 分支操作
    """
    
    def __init__(self, repo_path: str):
        """
        初始化 Git 管理器
        
        Args:
            repo_path: 仓库路径
        """
        self.repo_path = repo_path
    
    def is_git_repo(self) -> bool:
        """
        检查是否是 Git 仓库
        
        Returns:
            bool: 是否是 Git 仓库
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=self.repo_path,
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def get_status(self) -> List[GitFileStatus]:
        """
        获取 Git 状态
        
        Returns:
            List[GitFileStatus]: 文件状态列表
        """
        if not self.is_git_repo():
            return []
        
        try:
            # 获取状态（porcelain 格式）
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.repo_path,
                capture_output=True,
                text=True
            )
            
            files = []
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                
                # 解析状态行
                staged_status = line[0]  # 暂存区状态
                working_status = line[1]  # 工作区状态
                file_path = line[3:].strip()
                
                # 确定状态
                if staged_status == 'A' or working_status == '?':
                    status = 'untracked'
                    staged = (staged_status == 'A')
                elif staged_status == 'M' or working_status == 'M':
                    status = 'modified'
                    staged = (staged_status == 'M')
                elif staged_status == 'D' or working_status == 'D':
                    status = 'deleted'
                    staged = (staged_status == 'D')
                elif staged_status == 'R':
                    status = 'renamed'
                    staged = True
                else:
                    status = 'unknown'
                    staged = False
                
                files.append(GitFileStatus(
                    file_path=file_path,
                    status=status,
                    staged=staged
                ))
            
            return files
            
        except Exception as e:
            print(f"获取 Git 状态失败: {e}")
            return []
    
    def stage_file(self, file_path: str) -> bool:
        """
        暂存文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 是否成功
        """
        try:
            result = subprocess.run(
                ["git", "add", file_path],
                cwd=self.repo_path,
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception as e:
            print(f"暂存文件失败: {e}")
            return False
    
    def unstage_file(self, file_path: str) -> bool:
        """
        取消暂存文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 是否成功
        """
        try:
            result = subprocess.run(
                ["git", "reset", "HEAD", file_path],
                cwd=self.repo_path,
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception as e:
            print(f"取消暂存失败: {e}")
            return False
    
    def stage_all(self) -> bool:
        """
        暂存所有文件
        
        Returns:
            bool: 是否成功
        """
        try:
            result = subprocess.run(
                ["git", "add", "-A"],
                cwd=self.repo_path,
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception as e:
            print(f"暂存所有文件失败: {e}")
            return False
    
    def commit(self, message: str) -> bool:
        """
        提交更改
        
        Args:
            message: 提交信息
            
        Returns:
            bool: 是否成功
        """
        try:
            result = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=self.repo_path,
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception as e:
            print(f"提交失败: {e}")
            return False
    
    def push(self, remote: str = "origin", branch: str = "main") -> Tuple[bool, str]:
        """
        推送到远程仓库
        
        Args:
            remote: 远程仓库名
            branch: 分支名
            
        Returns:
            Tuple[bool, str]: (是否成功, 输出信息)
        """
        try:
            result = subprocess.run(
                ["git", "push", remote, branch],
                cwd=self.repo_path,
                capture_output=True,
                text=True
            )
            return (result.returncode == 0, result.stdout + result.stderr)
        except Exception as e:
            return (False, str(e))
    
    def pull(self, remote: str = "origin", branch: str = "main") -> Tuple[bool, str]:
        """
        拉取更新
        
        Args:
            remote: 远程仓库名
            branch: 分支名
            
        Returns:
            Tuple[bool, str]: (是否成功, 输出信息)
        """
        try:
            result = subprocess.run(
                ["git", "pull", remote, branch],
                cwd=self.repo_path,
                capture_output=True,
                text=True
            )
            return (result.returncode == 0, result.stdout + result.stderr)
        except Exception as e:
            return (False, str(e))
    
    def get_history(self, limit: int = 50) -> List[GitCommit]:
        """
        获取提交历史
        
        Args:
            limit: 返回的记录数
            
        Returns:
            List[GitCommit]: 提交列表
        """
        try:
            result = subprocess.run(
                [
                    "git", "log",
                    f"--max-count={limit}",
                    "--pretty=format:%H|%an|%ad|%s",
                    "--date=short"
                ],
                cwd=self.repo_path,
                capture_output=True,
                text=True
            )
            
            commits = []
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                
                parts = line.split('|', 3)
                if len(parts) == 4:
                    commits.append(GitCommit(
                        commit_hash=parts[0],
                        author=parts[1],
                        date=parts[2],
                        message=parts[3]
                    ))
            
            return commits
            
        except Exception as e:
            print(f"获取提交历史失败: {e}")
            return []
    
    def get_branches(self) -> List[str]:
        """
        获取所有分支
        
        Returns:
            List[str]: 分支列表
        """
        try:
            result = subprocess.run(
                ["git", "branch", "-a"],
                cwd=self.repo_path,
                capture_output=True,
                text=True
            )
            
            branches = []
            for line in result.stdout.strip().split('\n'):
                branch = line.strip().lstrip('* ')
                if branch:
                    branches.append(branch)
            
            return branches
            
        except Exception as e:
            print(f"获取分支失败: {e}")
            return []
    
    def checkout_branch(self, branch: str) -> bool:
        """
        切换分支
        
        Args:
            branch: 分支名
            
        Returns:
            bool: 是否成功
        """
        try:
            result = subprocess.run(
                ["git", "checkout", branch],
                cwd=self.repo_path,
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception as e:
            print(f"切换分支失败: {e}")
            return False
    
    def create_branch(self, branch: str) -> bool:
        """
        创建并切换到新分支
        
        Args:
            branch: 新分支名
            
        Returns:
            bool: 是否成功
        """
        try:
            result = subprocess.run(
                ["git", "checkout", "-b", branch],
                cwd=self.repo_path,
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception as e:
            print(f"创建分支失败: {e}")
            return False


# ── Git 集成面板 ─────────────────────────────────────────────

class GitIntegrationPanel(QWidget):
    """
    Git 集成面板
    
    功能：
    - 显示 Git 状态
    - 暂存/提交/推送
    - 查看历史
    - 分支管理
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.repo_path: str = ""
        self.git_manager: Optional[GitManager] = None
        self._init_ui()
        self._connect_signals()
    
    def _init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # 标题
        title_label = QLabel("🔧 Git 集成")
        title_label.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #FFFFFF; padding: 4px 0;"
        )
        layout.addWidget(title_label)
        
        # 工具栏
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        
        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.setFixedSize(80, 32)
        self.refresh_btn.setStyleSheet(self._get_button_style())
        toolbar_layout.addWidget(self.refresh_btn)
        
        self.stage_all_btn = QPushButton("➕ 暂存所有")
        self.stage_all_btn.setFixedSize(100, 32)
        self.stage_all_btn.setStyleSheet(self._get_button_style())
        toolbar_layout.addWidget(self.stage_all_btn)
        
        toolbar_layout.addStretch()
        
        self.pull_btn = QPushButton("⬇️ 拉取")
        self.pull_btn.setFixedSize(80, 32)
        self.pull_btn.setStyleSheet(self._get_button_style())
        toolbar_layout.addWidget(self.pull_btn)
        
        self.push_btn = QPushButton("⬆️ 推送")
        self.push_btn.setFixedSize(80, 32)
        self.push_btn.setStyleSheet(self._get_button_style())
        toolbar_layout.addWidget(self.push_btn)
        
        layout.addLayout(toolbar_layout)
        
        # 提交信息输入
        self.commit_edit = QLineEdit()
        self.commit_edit.setPlaceholderText("输入提交信息...")
        self.commit_edit.setStyleSheet("""
            QLineEdit {
                background: #3E3E42;
                color: #D4D4D4;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 6px 8px;
                font-size: 13px;
            }
        """)
        layout.addWidget(self.commit_edit)
        
        # 提交按钮
        self.commit_btn = QPushButton("✅ 提交")
        self.commit_btn.setFixedHeight(32)
        self.commit_btn.setStyleSheet("""
            QPushButton {
                background: #0E639C;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background: #1177BB; }
            QPushButton:disabled { background: #555555; }
        """)
        layout.addWidget(self.commit_btn)
        
        # 分割视图（文件状态 + 提交历史）
        split_layout = QHBoxLayout()
        split_layout.setContentsMargins(0, 0, 0, 0)
        split_layout.setSpacing(8)
        
        # 文件状态树
        self.status_tree = QTreeWidget()
        self.status_tree.setHeaderLabels(["文件", "状态"])
        self.status_tree.setColumnWidth(0, 300)
        self.status_tree.setStyleSheet(self._get_tree_style())
        split_layout.addWidget(self.status_tree, 1)
        
        # 提交历史树
        self.history_tree = QTreeWidget()
        self.history_tree.setHeaderLabels(["哈希", "作者", "日期", "信息"])
        self.history_tree.setColumnWidth(0, 80)
        self.history_tree.setColumnWidth(1, 100)
        self.history_tree.setColumnWidth(2, 80)
        self.history_tree.setStyleSheet(self._get_tree_style())
        split_layout.addWidget(self.history_tree, 1)
        
        layout.addLayout(split_layout, 1)
        
        # 状态栏
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet(
            "color: #D4D4D4; font-size: 11px; padding: 4px 0;"
        )
        layout.addWidget(self.status_label)
    
    def _get_button_style(self) -> str:
        """获取按钮样式"""
        return """
            QPushButton {
                background: #3E3E42;
                color: #D4D4D4;
                border: 1px solid #555555;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover { background: #4A4A4E; }
            QPushButton:disabled { background: #555555; }
        """
    
    def _get_tree_style(self) -> str:
        """获取树形控件样式"""
        return """
            QTreeWidget {
                background: #1E1E1E;
                color: #D4D4D4;
                border: 1px solid #3E3E42;
                font-family: Consolas, 'Courier New', monospace;
                font-size: 12px;
            }
            QTreeWidget::item {
                padding: 2px 4px;
            }
            QTreeWidget::item:selected {
                background: #094771;
                color: #FFFFFF;
            }
            QTreeWidget::item:hover {
                background: #2A2D2E;
            }
        """
    
    def _connect_signals(self):
        """连接信号"""
        self.refresh_btn.clicked.connect(self._refresh)
        self.stage_all_btn.clicked.connect(self._stage_all)
        self.commit_btn.clicked.connect(self._commit)
        self.push_btn.clicked.connect(self._push)
        self.pull_btn.clicked.connect(self._pull)
    
    def set_repo_path(self, path: str):
        """
        设置仓库路径
        
        Args:
            path: 仓库路径
        """
        self.repo_path = path
        self.git_manager = GitManager(path)
        
        if self.git_manager.is_git_repo():
            self.status_label.setText(f"Git 仓库: {path}")
            self._refresh()
        else:
            self.status_label.setText("不是 Git 仓库")
    
    def _refresh(self):
        """刷新 Git 状态"""
        if not self.git_manager:
            return
        
        # 清空现有内容
        self.status_tree.clear()
        self.history_tree.clear()
        
        # 获取状态
        files = self.git_manager.get_status()
        
        # 分类显示
        staged_files = [f for f in files if f.staged]
        modified_files = [f for f in files if not f.staged and f.status == 'modified']
        untracked_files = [f for f in files if f.status == 'untracked']
        
        if staged_files:
            staged_item = QTreeWidgetItem(self.status_tree)
            staged_item.setText(0, "📦 已暂存")
            for file in staged_files:
                file_item = QTreeWidgetItem(staged_item)
                file_item.setText(0, f"  {file.file_path}")
                file_item.setText(1, "已暂存")
        
        if modified_files:
            modified_item = QTreeWidgetItem(self.status_tree)
            modified_item.setText(0, "📝 已修改")
            for file in modified_files:
                file_item = QTreeWidgetItem(modified_item)
                file_item.setText(0, f"  {file.file_path}")
                file_item.setText(1, "已修改")
        
        if untracked_files:
            untracked_item = QTreeWidgetItem(self.status_tree)
            untracked_item.setText(0, "❓ 未跟踪")
            for file in untracked_files:
                file_item = QTreeWidgetItem(untracked_item)
                file_item.setText(0, f"  {file.file_path}")
                file_item.setText(1, "未跟踪")
        
        # 获取历史
        commits = self.git_manager.get_history(limit=50)
        
        for commit in commits:
            commit_item = QTreeWidgetItem(self.history_tree)
            commit_item.setText(0, commit.commit_hash[:8])
            commit_item.setText(1, commit.author)
            commit_item.setText(2, commit.date)
            commit_item.setText(3, commit.message)
        
        # 更新状态
        total_files = len(files)
        self.status_label.setText(f"Git 状态: {total_files} 个文件已修改")
    
    def _stage_all(self):
        """暂存所有文件"""
        if not self.git_manager:
            return
        
        if self.git_manager.stage_all():
            self.status_label.setText("已暂存所有文件")
            self._refresh()
        else:
            self.status_label.setText("暂存失败")
    
    def _commit(self):
        """提交更改"""
        if not self.git_manager:
            return
        
        message = self.commit_edit.text().strip()
        if not message:
            QMessageBox.warning(self, "警告", "请输入提交信息")
            return
        
        if self.git_manager.commit(message):
            self.commit_edit.clear()
            self.status_label.setText(f"提交成功: {message}")
            self._refresh()
        else:
            self.status_label.setText("提交失败")
    
    def _push(self):
        """推送到远程"""
        if not self.git_manager:
            return
        
        success, output = self.git_manager.push()
        
        if success:
            self.status_label.setText("推送成功")
        else:
            self.status_label.setText(f"推送失败: {output}")
        
        self._refresh()
    
    def _pull(self):
        """拉取更新"""
        if not self.git_manager:
            return
        
        success, output = self.git_manager.pull()
        
        if success:
            self.status_label.setText("拉取成功")
        else:
            self.status_label.setText(f"拉取失败: {output}")
        
        self._refresh()


# ── 测试 ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    
    app = QApplication(sys.argv)
    
    window = QMainWindow()
    window.setWindowTitle("Git 集成测试")
    window.setGeometry(100, 100, 1000, 700)
    
    central_widget = QWidget()
    window.setCentralWidget(central_widget)
    
    layout = QVBoxLayout(central_widget)
    
    git_panel = GitIntegrationPanel()
    git_panel.set_repo_path(os.getcwd())
    
    layout.addWidget(git_panel)
    
    window.show()
    sys.exit(app.exec())
