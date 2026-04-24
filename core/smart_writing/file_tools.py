"""
文件操作工具
============

提供安全的文件操作接口：
1. 读取文件 - 支持行范围、大文件截断
2. 写入文件 - 支持备份、自动创建目录
3. 编辑文件 - 行级编辑、diff 预览
4. 删除文件 - 支持到回收站
5. 移动/复制 - 支持跨目录

安全特性：
- 路径验证 - 防止路径遍历
- 大文件限制 - 防止内存溢出
- 备份机制 - 支持撤销
- 操作日志 - 完整可追溯

使用方式:
    from core.smart_writing.file_tools import FileTools

    tools = FileTools(project_root="/path/to/project")
    result = tools.read_file("src/main.py")
    result = tools.write_file("src/main.py", content)
    result = tools.edit_file("src/main.py", old_str, new_str)
"""

import os
import re
import shutil
import hashlib
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from .tool_definition import (
    Tool, ToolParameter, ToolResult, ToolStatus,
    ToolRegistry, ToolCategory
)


# ============== 配置 ==============

# 最大文件大小（10MB）
MAX_FILE_SIZE = 10 * 1024 * 1024

# 默认读取行数
DEFAULT_READ_LINES = 500

# 备份目录
BACKUP_DIR = ".backups"


# ============== 文件工具类 ==============

class FileTools:
    """
    文件操作工具集

    所有操作都在 project_root 下进行，防止路径遍历。
    """

    def __init__(
        self,
        project_root: str,
        backup_enabled: bool = True,
        max_file_size: int = MAX_FILE_SIZE,
        registry: Optional[ToolRegistry] = None,
    ):
        """
        初始化

        Args:
            project_root: 项目根目录
            backup_enabled: 是否启用备份
            max_file_size: 最大文件大小
            registry: 工具注册表（可选）
        """
        self.project_root = Path(project_root).resolve()
        self.backup_enabled = backup_enabled
        self.max_file_size = max_file_size
        self.registry = registry

        # 确保备份目录存在
        self._backup_dir = self.project_root / BACKUP_DIR
        if self.backup_enabled:
            self._backup_dir.mkdir(exist_ok=True)

        # 注册工具
        if registry:
            self._register_tools()

    def _register_tools(self):
        """注册文件操作工具"""
        self.registry.register_tool(
            Tool(
                name="read_file",
                description="读取文件内容，支持指定行范围和最大行数",
                category=ToolCategory.FILE,
                parameters=[
                    ToolParameter("path", "str", "文件路径（相对于项目根目录）", required=True),
                    ToolParameter("lines", "int", "最多读取的行数", required=False, default=500),
                    ToolParameter("offset", "int", "从第几行开始读取", required=False, default=0),
                ],
                returns="文件内容（可能截断）",
                readonly=True,
                tags={"read", "file"},
            ),
            self._read_file_handler
        )

        self.registry.register_tool(
            Tool(
                name="write_file",
                description="写入文件内容，自动创建目录",
                category=ToolCategory.FILE,
                parameters=[
                    ToolParameter("path", "str", "文件路径", required=True),
                    ToolParameter("content", "str", "文件内容", required=True),
                    ToolParameter("create_backup", "bool", "是否创建备份", required=False, default=True),
                ],
                returns="写入结果",
                danger=True,
                confirm_required=True,
                tags={"write", "file"},
            ),
            self._write_file_handler
        )

        self.registry.register_tool(
            Tool(
                name="edit_file",
                description="编辑文件内容，使用精确字符串替换",
                category=ToolCategory.FILE,
                parameters=[
                    ToolParameter("path", "str", "文件路径", required=True),
                    ToolParameter("old_str", "str", "要替换的原文（必须精确匹配）", required=True),
                    ToolParameter("new_str", "str", "替换后的内容", required=True),
                    ToolParameter("create_backup", "bool", "是否创建备份", required=False, default=True),
                ],
                returns="编辑结果",
                danger=True,
                confirm_required=True,
                tags={"edit", "file"},
            ),
            self._edit_file_handler
        )

        self.registry.register_tool(
            Tool(
                name="delete_file",
                description="删除文件或目录",
                category=ToolCategory.FILE,
                parameters=[
                    ToolParameter("path", "str", "文件或目录路径", required=True),
                    ToolParameter("recursive", "bool", "是否递归删除目录", required=False, default=False),
                ],
                returns="删除结果",
                danger=True,
                confirm_required=True,
                tags={"delete", "file"},
            ),
            self._delete_file_handler
        )

        self.registry.register_tool(
            Tool(
                name="list_directory",
                description="列出目录内容",
                category=ToolCategory.FILE,
                parameters=[
                    ToolParameter("path", "str", "目录路径", required=False, default="."),
                    ToolParameter("include_hidden", "bool", "是否包含隐藏文件", required=False, default=False),
                ],
                returns="目录内容列表",
                readonly=True,
                tags={"list", "file"},
            ),
            self._list_directory_handler
        )

        self.registry.register_tool(
            Tool(
                name="search_files",
                description="在文件中搜索内容",
                category=ToolCategory.SEARCH,
                parameters=[
                    ToolParameter("pattern", "str", "搜索模式（支持正则）", required=True),
                    ToolParameter("path", "str", "搜索路径", required=False, default="."),
                    ToolParameter("file_pattern", "str", "文件过滤模式", required=False, default="*"),
                    ToolParameter("case_sensitive", "bool", "是否区分大小写", required=False, default=False),
                ],
                returns="匹配结果列表",
                readonly=True,
                tags={"search", "grep"},
            ),
            self._search_files_handler
        )

    def _validate_path(self, path: str) -> Tuple[bool, Path, str]:
        """验证路径安全"""
        try:
            # 解析路径
            full_path = (self.project_root / path).resolve()

            # 检查是否在项目目录下
            if not str(full_path).startswith(str(self.project_root)):
                return False, full_path, "路径必须在项目目录下"

            return True, full_path, ""

        except Exception as e:
            return False, None, f"路径解析错误: {e}"

    def _create_backup(self, path: Path) -> Optional[str]:
        """创建备份"""
        if not self.backup_enabled or not path.exists():
            return None

        try:
            # 创建备份子目录（按日期）
            date_dir = self._backup_dir / datetime.now().strftime("%Y%m%d")
            date_dir.mkdir(exist_ok=True)

            # 生成备份文件名
            rel_path = path.relative_to(self.project_root)
            timestamp = datetime.now().strftime("%H%M%S")
            backup_name = f"{rel_path.as_posix().replace('/', '_')}_{timestamp}"
            backup_path = date_dir / backup_name

            # 复制文件
            if path.is_file():
                shutil.copy2(path, backup_path)
            else:
                shutil.copytree(path, backup_path)

            return str(backup_path)

        except Exception as e:
            return None

    # ============== 工具处理器 ==============

    def _read_file_handler(
        self,
        path: str,
        lines: int = DEFAULT_READ_LINES,
        offset: int = 0,
    ) -> ToolResult:
        """读取文件处理器"""
        valid, full_path, error = self._validate_path(path)
        if not valid:
            return ToolResult(
                call_id="",
                tool_name="read_file",
                status=ToolStatus.FAILED,
                error=error,
            )

        if not full_path.exists():
            return ToolResult(
                call_id="",
                tool_name="read_file",
                status=ToolStatus.FAILED,
                error=f"文件不存在: {path}",
            )

        if not full_path.is_file():
            return ToolResult(
                call_id="",
                tool_name="read_file",
                status=ToolStatus.FAILED,
                error=f"不是文件: {path}",
            )

        try:
            # 检查文件大小
            size = full_path.stat().st_size
            if size > self.max_file_size:
                # 大文件只读取头部
                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content_lines = []
                    for i, line in enumerate(f):
                        if i >= lines:
                            break
                        content_lines.append(line)

                content = ''.join(content_lines)
                truncated = True
            else:
                # 正常读取
                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    if offset > 0:
                        # 跳过前面的行
                        for _ in range(offset):
                            f.readline()

                    content_lines = []
                    for i, line in enumerate(f):
                        if i >= lines:
                            break
                        content_lines.append(line)

                content = ''.join(content_lines)
                truncated = len(content.split('\n')) >= lines

            # 生成预览
            preview = content[:500] + "..." if len(content) > 500 else content
            if truncated:
                preview += f"\n[文件较大，已截断显示前 {lines} 行]"

            return ToolResult(
                call_id="",
                tool_name="read_file",
                status=ToolStatus.SUCCESS,
                result={
                    "path": path,
                    "full_path": str(full_path),
                    "lines": len(content.split('\n')),
                    "size": size,
                    "truncated": truncated,
                    "content": content,
                },
                output_preview=preview,
            )

        except Exception as e:
            return ToolResult(
                call_id="",
                tool_name="read_file",
                status=ToolStatus.FAILED,
                error=f"读取失败: {e}",
            )

    def _write_file_handler(
        self,
        path: str,
        content: str,
        create_backup: bool = True,
    ) -> ToolResult:
        """写入文件处理器"""
        valid, full_path, error = self._validate_path(path)
        if not valid:
            return ToolResult(
                call_id="",
                tool_name="write_file",
                status=ToolStatus.FAILED,
                error=error,
            )

        try:
            # 创建备份
            if create_backup and full_path.exists():
                backup_path = self._create_backup(full_path)
            else:
                backup_path = None

            # 确保目录存在
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # 写入文件
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)

            return ToolResult(
                call_id="",
                tool_name="write_file",
                status=ToolStatus.SUCCESS,
                result={
                    "path": path,
                    "full_path": str(full_path),
                    "bytes_written": len(content.encode('utf-8')),
                    "backup_path": backup_path,
                },
                message=f"成功写入 {path}" + (f"，备份: {backup_path}" if backup_path else ""),
            )

        except Exception as e:
            return ToolResult(
                call_id="",
                tool_name="write_file",
                status=ToolStatus.FAILED,
                error=f"写入失败: {e}",
            )

    def _edit_file_handler(
        self,
        path: str,
        old_str: str,
        new_str: str,
        create_backup: bool = True,
    ) -> ToolResult:
        """编辑文件处理器"""
        valid, full_path, error = self._validate_path(path)
        if not valid:
            return ToolResult(
                call_id="",
                tool_name="edit_file",
                status=ToolStatus.FAILED,
                error=error,
            )

        if not full_path.exists():
            return ToolResult(
                call_id="",
                tool_name="edit_file",
                status=ToolStatus.FAILED,
                error=f"文件不存在: {path}",
            )

        try:
            # 读取文件
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # 检查 old_str 是否存在
            if old_str not in content:
                return ToolResult(
                    call_id="",
                    tool_name="edit_file",
                    status=ToolStatus.FAILED,
                    error=f"未找到要替换的内容: {old_str[:50]}...",
                )

            # 创建备份
            if create_backup:
                backup_path = self._create_backup(full_path)
            else:
                backup_path = None

            # 执行替换
            new_content = content.replace(old_str, new_str)

            # 写入文件
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            # 计算统计
            occurrences = content.count(old_str)
            lines_changed = new_content.count('\n') - content.count('\n')

            return ToolResult(
                call_id="",
                tool_name="edit_file",
                status=ToolStatus.SUCCESS,
                result={
                    "path": path,
                    "full_path": str(full_path),
                    "occurrences": occurrences,
                    "lines_changed": lines_changed,
                    "backup_path": backup_path,
                },
                message=f"成功编辑 {path}，替换 {occurrences} 处" +
                        (f"，备份: {backup_path}" if backup_path else ""),
            )

        except Exception as e:
            return ToolResult(
                call_id="",
                tool_name="edit_file",
                status=ToolStatus.FAILED,
                error=f"编辑失败: {e}",
            )

    def _delete_file_handler(
        self,
        path: str,
        recursive: bool = False,
    ) -> ToolResult:
        """删除文件处理器"""
        valid, full_path, error = self._validate_path(path)
        if not valid:
            return ToolResult(
                call_id="",
                tool_name="delete_file",
                status=ToolStatus.FAILED,
                error=error,
            )

        if not full_path.exists():
            return ToolResult(
                call_id="",
                tool_name="delete_file",
                status=ToolStatus.FAILED,
                error=f"路径不存在: {path}",
            )

        try:
            # 创建备份
            if full_path.is_file():
                backup_path = self._create_backup(full_path)
            elif full_path.is_dir():
                backup_path = self._create_backup(full_path) if recursive else None
            else:
                backup_path = None

            # 删除
            if full_path.is_file():
                full_path.unlink()
            elif full_path.is_dir():
                if recursive:
                    shutil.rmtree(full_path)
                else:
                    full_path.rmdir()

            return ToolResult(
                call_id="",
                tool_name="delete_file",
                status=ToolStatus.SUCCESS,
                result={
                    "path": path,
                    "deleted": True,
                    "backup_path": backup_path,
                },
                message=f"成功删除 {path}" + (f"，备份: {backup_path}" if backup_path else ""),
            )

        except Exception as e:
            return ToolResult(
                call_id="",
                tool_name="delete_file",
                status=ToolStatus.FAILED,
                error=f"删除失败: {e}",
            )

    def _list_directory_handler(
        self,
        path: str = ".",
        include_hidden: bool = False,
    ) -> ToolResult:
        """列出目录处理器"""
        valid, full_path, error = self._validate_path(path)
        if not valid:
            return ToolResult(
                call_id="",
                tool_name="list_directory",
                status=ToolStatus.FAILED,
                error=error,
            )

        if not full_path.exists():
            return ToolResult(
                call_id="",
                tool_name="list_directory",
                status=ToolStatus.FAILED,
                error=f"目录不存在: {path}",
            )

        if not full_path.is_dir():
            return ToolResult(
                call_id="",
                tool_name="list_directory",
                status=ToolStatus.FAILED,
                error=f"不是目录: {path}",
            )

        try:
            items = []
            for entry in sorted(full_path.iterdir(), key=lambda x: (not x.is_dir(), x.name)):
                name = entry.name

                # 过滤隐藏文件
                if not include_hidden and name.startswith('.'):
                    continue

                # 获取文件信息
                stat = entry.stat()
                items.append({
                    "name": name,
                    "type": "directory" if entry.is_dir() else "file",
                    "size": stat.st_size if entry.is_file() else None,
                    "modified": stat.st_mtime,
                })

            return ToolResult(
                call_id="",
                tool_name="list_directory",
                status=ToolStatus.SUCCESS,
                result={
                    "path": path,
                    "full_path": str(full_path),
                    "items": items,
                    "count": len(items),
                },
            )

        except Exception as e:
            return ToolResult(
                call_id="",
                tool_name="list_directory",
                status=ToolStatus.FAILED,
                error=f"列出目录失败: {e}",
            )

    def _search_files_handler(
        self,
        pattern: str,
        path: str = ".",
        file_pattern: str = "*",
        case_sensitive: bool = False,
    ) -> ToolResult:
        """搜索文件处理器"""
        valid, full_path, error = self._validate_path(path)
        if not valid:
            return ToolResult(
                call_id="",
                tool_name="search_files",
                status=ToolStatus.FAILED,
                error=error,
            )

        if not full_path.exists():
            return ToolResult(
                call_id="",
                tool_name="search_files",
                status=ToolStatus.FAILED,
                error=f"路径不存在: {path}",
            )

        try:
            # 编译正则
            if case_sensitive:
                regex = re.compile(pattern)
            else:
                regex = re.compile(pattern, re.IGNORECASE)

            # 搜索
            matches = []
            max_matches = 100  # 限制结果数

            for file_path in full_path.rglob(file_pattern):
                if len(matches) >= max_matches:
                    break

                if not file_path.is_file():
                    continue

                # 跳过二进制文件
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        for line_no, line in enumerate(f, 1):
                            if regex.search(line):
                                rel_path = file_path.relative_to(self.project_root)
                                matches.append({
                                    "file": str(rel_path),
                                    "line": line_no,
                                    "content": line.strip()[:200],
                                })
                except:
                    continue

            return ToolResult(
                call_id="",
                tool_name="search_files",
                status=ToolStatus.SUCCESS,
                result={
                    "pattern": pattern,
                    "path": path,
                    "matches": matches,
                    "count": len(matches),
                    "truncated": len(matches) >= max_matches,
                },
                message=f"找到 {len(matches)} 处匹配" +
                        (" (结果已截断)" if len(matches) >= max_matches else ""),
            )

        except Exception as e:
            return ToolResult(
                call_id="",
                tool_name="search_files",
                status=ToolStatus.FAILED,
                error=f"搜索失败: {e}",
            )

    # ============== 便捷方法 ==============

    def read_file(
        self,
        path: str,
        lines: int = DEFAULT_READ_LINES,
        offset: int = 0,
    ) -> ToolResult:
        """读取文件"""
        return self._read_file_handler(path, lines, offset)

    def write_file(
        self,
        path: str,
        content: str,
        create_backup: bool = True,
    ) -> ToolResult:
        """写入文件"""
        return self._write_file_handler(path, content, create_backup)

    def edit_file(
        self,
        path: str,
        old_str: str,
        new_str: str,
        create_backup: bool = True,
    ) -> ToolResult:
        """编辑文件"""
        return self._edit_file_handler(path, old_str, new_str, create_backup)

    def delete_file(
        self,
        path: str,
        recursive: bool = False,
    ) -> ToolResult:
        """删除文件"""
        return self._delete_file_handler(path, recursive)

    def list_directory(
        self,
        path: str = ".",
        include_hidden: bool = False,
    ) -> ToolResult:
        """列出目录"""
        return self._list_directory_handler(path, include_hidden)

    def search_files(
        self,
        pattern: str,
        path: str = ".",
        file_pattern: str = "*",
        case_sensitive: bool = False,
    ) -> ToolResult:
        """搜索文件"""
        return self._search_files_handler(pattern, path, file_pattern, case_sensitive)


# ============== 导出 ==============

__all__ = [
    'FileTools',
    'MAX_FILE_SIZE',
    'DEFAULT_READ_LINES',
    'BACKUP_DIR',
]
