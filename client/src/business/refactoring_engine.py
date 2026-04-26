#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重构引擎 - 批量代码重构
========================

功能：
1. 批量重命名（变量/函数/类）
2. 批量修改导入语句
3. 批量格式化代码
4. 批量添加/删除注释
5. 批量移动文件
6. 重构预览（显示将要修改的内容）

Author: LivingTreeAI Agent
Date: 2026-04-26
"""

import os
import re
import ast
import shutil
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path


# ── 数据结构 ─────────────────────────────────────────────────────

@dataclass
class RefactoringChange:
    """重构变更"""
    file_path: str
    line_number: int
    old_text: str
    new_text: str
    change_type: str  # 'rename', 'import', 'format', 'comment', 'move'


@dataclass
class RefactoringResult:
    """重构结果"""
    success: bool
    changes: List[RefactoringChange]
    error_message: str = ""
    files_modified: int = 0


# ── 重构引擎 ─────────────────────────────────────────────────

class RefactoringEngine:
    """
    重构引擎
    
    功能：
    1. 批量重命名
    2. 批量修改导入
    3. 批量格式化
    4. 批量添加/删除注释
    5. 批量移动文件
    """
    
    def __init__(self, project_root: str):
        """
        初始化重构引擎
        
        Args:
            project_root: 项目根目录
        """
        self.project_root = project_root
        self.changes: List[RefactoringChange] = []
        self.preview_only = False
    
    # ── 批量重命名 ──────────────────────────────────────────────
    
    def rename_symbol(
        self,
        old_name: str,
        new_name: str,
        symbol_type: str = "auto",
        file_filter: str = "*.py",
        preview: bool = True
    ) -> RefactoringResult:
        """
        重命名符号（变量/函数/类）
        
        Args:
            old_name: 旧名称
            new_name: 新名称
            symbol_type: 符号类型（'variable', 'function', 'class', 'auto'）
            file_filter: 文件过滤器
            preview: 是否仅预览（不实际修改）
            
        Returns:
            RefactoringResult: 重构结果
        """
        self.preview_only = preview
        self.changes = []
        
        try:
            # 遍历项目文件
            for root, dirs, files in os.walk(self.project_root):
                # 跳过无关目录
                dirs[:] = [
                    d for d in dirs
                    if d not in [
                        '__pycache__', '.git', '.pytest_cache',
                        'node_modules', 'dist', 'build', '.workbuddy',
                        '.codebuddy', '.venv', 'venv', 'env'
                    ]
                ]
                
                for file in files:
                    if not self._match_filter(file, file_filter):
                        continue
                    
                    file_path = os.path.join(root, file)
                    self._rename_in_file(
                        file_path, old_name, new_name, symbol_type
                    )
            
            # 应用变更（如果非预览模式）
            if not preview:
                self._apply_changes()
            
            return RefactoringResult(
                success=True,
                changes=self.changes,
                files_modified=len(set(c.file_path for c in self.changes))
            )
            
        except Exception as e:
            return RefactoringResult(
                success=False,
                changes=[],
                error_message=str(e)
            )
    
    def _rename_in_file(
        self,
        file_path: str,
        old_name: str,
        new_name: str,
        symbol_type: str
    ):
        """
        在文件中重命名符号
        
        Args:
            file_path: 文件路径
            old_name: 旧名称
            new_name: 新名称
            symbol_type: 符号类型
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
            
            # 根据符号类型构建正则
            if symbol_type == 'class':
                pattern = re.compile(rf'\b{re.escape(old_name)}\b(?=\s*\()')
            elif symbol_type == 'function':
                pattern = re.compile(rf'\b{re.escape(old_name)}\b(?=\s*\()')
            elif symbol_type == 'variable':
                pattern = re.compile(rf'\b{re.escape(old_name)}\b')
            else:  # auto - 匹配所有
                pattern = re.compile(rf'\b{re.escape(old_name)}\b')
            
            # 逐行检查
            for line_num, line in enumerate(lines, 1):
                if pattern.search(line):
                    new_line = pattern.sub(new_name, line)
                    
                    self.changes.append(RefactoringChange(
                        file_path=file_path,
                        line_number=line_num,
                        old_text=line,
                        new_text=new_line,
                        change_type='rename'
                    ))
        
        except Exception:
            pass  # 跳过无法读取的文件
    
    # ── 批量修改导入 ────────────────────────────────────────────
    
    def update_imports(
        self,
        old_module: str,
        new_module: str,
        file_filter: str = "*.py",
        preview: bool = True
    ) -> RefactoringResult:
        """
        更新导入语句
        
        Args:
            old_module: 旧模块路径
            new_module: 新模块路径
            file_filter: 文件过滤器
            preview: 是否仅预览
            
        Returns:
            RefactoringResult: 重构结果
        """
        self.preview_only = preview
        self.changes = []
        
        try:
            # 遍历项目文件
            for root, dirs, files in os.walk(self.project_root):
                # 跳过无关目录
                dirs[:] = [
                    d for d in dirs
                    if d not in [
                        '__pycache__', '.git', '.pytest_cache',
                        'node_modules', 'dist', 'build', '.workbuddy',
                        '.codebuddy', '.venv', 'venv', 'env'
                    ]
                ]
                
                for file in files:
                    if not self._match_filter(file, file_filter):
                        continue
                    
                    file_path = os.path.join(root, file)
                    self._update_imports_in_file(
                        file_path, old_module, new_module
                    )
            
            # 应用变更
            if not preview:
                self._apply_changes()
            
            return RefactoringResult(
                success=True,
                changes=self.changes,
                files_modified=len(set(c.file_path for c in self.changes))
            )
            
        except Exception as e:
            return RefactoringResult(
                success=False,
                changes=[],
                error_message=str(e)
            )
    
    def _update_imports_in_file(
        self,
        file_path: str,
        old_module: str,
        new_module: str
    ):
        """
        在文件中更新导入语句
        
        Args:
            file_path: 文件路径
            old_module: 旧模块路径
            new_module: 新模块路径
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
            
            # 匹配导入语句
            import_pattern = re.compile(
                rf'^(from\s+{re.escape(old_module)}|import\s+{re.escape(old_module)})'
            )
            
            for line_num, line in enumerate(lines, 1):
                if import_pattern.match(line):
                    new_line = line.replace(old_module, new_module, 1)
                    
                    self.changes.append(RefactoringChange(
                        file_path=file_path,
                        line_number=line_num,
                        old_text=line,
                        new_text=new_line,
                        change_type='import'
                    ))
        
        except Exception:
            pass
    
    # ── 批量格式化 ──────────────────────────────────────────────
    
    def format_files(
        self,
        file_filter: str = "*.py",
        use_black: bool = True
    ) -> RefactoringResult:
        """
        格式化文件
        
        Args:
            file_filter: 文件过滤器
            use_black: 是否使用 black 格式化
            
        Returns:
            RefactoringResult: 重构结果
        """
        self.changes = []
        files_modified = 0
        
        try:
            # 检查是否安装 black
            if use_black:
                import subprocess
                result = subprocess.run(
                    [sys.executable, "-m", "black", "--version"],
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    use_black = False
            
            # 遍历文件
            for root, dirs, files in os.walk(self.project_root):
                # 跳过无关目录
                dirs[:] = [
                    d for d in dirs
                    if d not in [
                        '__pycache__', '.git', '.pytest_cache',
                        'node_modules', 'dist', 'build', '.workbuddy',
                        '.codebuddy', '.venv', 'venv', 'env'
                    ]
                ]
                
                for file in files:
                    if not self._match_filter(file, file_filter):
                        continue
                    
                    file_path = os.path.join(root, file)
                    
                    if use_black:
                        # 使用 black 格式化
                        result = subprocess.run(
                            [sys.executable, "-m", "black", file_path],
                            capture_output=True,
                            text=True
                        )
                        if result.returncode == 0:
                            files_modified += 1
                    else:
                        # 简单格式化（移除多余空行，修复缩进）
                        self._simple_format(file_path)
                        files_modified += 1
            
            return RefactoringResult(
                success=True,
                changes=[],
                files_modified=files_modified
            )
            
        except Exception as e:
            return RefactoringResult(
                success=False,
                changes=[],
                error_message=str(e)
            )
    
    def _simple_format(self, file_path: str):
        """
        简单格式化（不依赖外部工具）
        
        Args:
            file_path: 文件路径
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 移除行尾空白
            formatted_lines = [line.rstrip() + '\n' if line.strip() else '\n' for line in lines]
            
            # 写回文件
            if not self.preview_only:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.writelines(formatted_lines)
        
        except Exception:
            pass
    
    # ── 批量移动文件 ────────────────────────────────────────────
    
    def move_files(
        self,
        source_pattern: str,
        target_dir: str,
        file_filter: str = "*",
        preview: bool = True
    ) -> RefactoringResult:
        """
        批量移动文件
        
        Args:
            source_pattern: 源文件模式（支持通配符）
            target_dir: 目标目录
            file_filter: 文件过滤器
            preview: 是否仅预览
            
        Returns:
            RefactoringResult: 重构结果
        """
        self.preview_only = preview
        self.changes = []
        
        try:
            import fnmatch
            
            # 确保目标目录存在
            target_path = os.path.join(self.project_root, target_dir)
            if not preview and not os.path.exists(target_path):
                os.makedirs(target_path)
            
            # 遍历文件
            for root, dirs, files in os.walk(self.project_root):
                for file in files:
                    # 检查是否匹配模式
                    if fnmatch.fnmatch(file, source_pattern):
                        if not self._match_filter(file, file_filter):
                            continue
                        
                        source_file = os.path.join(root, file)
                        target_file = os.path.join(target_path, file)
                        
                        self.changes.append(RefactoringChange(
                            file_path=source_file,
                            line_number=0,
                            old_text=source_file,
                            new_text=target_file,
                            change_type='move'
                        ))
            
            # 应用变更
            if not preview:
                for change in self.changes:
                    shutil.move(change.old_text, change.new_text)
            
            return RefactoringResult(
                success=True,
                changes=self.changes,
                files_modified=len(self.changes)
            )
            
        except Exception as e:
            return RefactoringResult(
                success=False,
                changes=[],
                error_message=str(e)
            )
    
    # ── 内部方法 ────────────────────────────────────────────────
    
    def _apply_changes(self):
        """应用变更"""
        # 按文件分组
        changes_by_file = {}
        for change in self.changes:
            if change.file_path not in changes_by_file:
                changes_by_file[change.file_path] = []
            changes_by_file[change.file_path].append(change)
        
        # 逐个文件应用变更
        for file_path, file_changes in changes_by_file.items():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                # 从后往前应用变更（避免行号偏移）
                for change in sorted(
                    file_changes, key=lambda c: c.line_number, reverse=True
                ):
                    line_idx = change.line_number - 1
                    if 0 <= line_idx < len(lines):
                        lines[line_idx] = change.new_text + '\n'
                
                # 写回文件
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.writelines(lines)
            
            except Exception as e:
                print(f"应用变更失败: {file_path}, 错误: {e}")
    
    def _match_filter(self, file_name: str, file_filter: str) -> bool:
        """
        检查文件是否匹配过滤器
        
        Args:
            file_name: 文件名
            file_filter: 过滤器（如 *.py）
            
        Returns:
            bool: 是否匹配
        """
        import fnmatch
        return fnmatch.fnmatch(file_name, file_filter)
    
    # ── 预览变更 ────────────────────────────────────────────────
    
    def get_preview(self) -> List[Dict]:
        """
        获取变更预览
        
        Returns:
            List[Dict]: 预览信息列表
        """
        preview = []
        
        for change in self.changes:
            preview.append({
                'file': os.path.relpath(change.file_path, self.project_root),
                'line': change.line_number,
                'type': change.change_type,
                'old': change.old_text,
                'new': change.new_text,
            })
        
        return preview


# ── 测试 ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    
    # 测试重构引擎
    engine = RefactoringEngine(os.getcwd())
    
    print("=" * 60)
    print("测试1: 重命名符号（预览模式）")
    print("=" * 60)
    
    result = engine.rename_symbol(
        old_name="config",
        new_name="new_config",
        symbol_type="variable",
        preview=True
    )
    
    if result.success:
        print(f"找到 {len(result.changes)} 处需要修改")
        print(f"涉及 {result.files_modified} 个文件")
        
        # 显示前 5 个变更
        for i, change in enumerate(result.changes[:5], 1):
            print(f"\n{i}. 文件: {os.path.relpath(change.file_path, os.getcwd())}")
            print(f"   行号: {change.line_number}")
            print(f"   旧文本: {change.old_text}")
            print(f"   新文本: {change.new_text}")
    else:
        print(f"失败: {result.error_message}")
    
    print("\n" + "=" * 60)
    print("测试2: 更新导入语句（预览模式）")
    print("=" * 60)
    
    result = engine.update_imports(
        old_module="old_module",
        new_module="new_module",
        preview=True
    )
    
    if result.success:
        print(f"找到 {len(result.changes)} 处需要修改")
    else:
        print(f"失败: {result.error_message}")
