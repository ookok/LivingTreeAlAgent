# -*- coding: utf-8 -*-
"""
Print语句迁移脚本
=================

自动将print语句替换为logger调用

使用方法:
    python scripts/migrate_print_to_logging.py                    # 迁移core目录
    python scripts/migrate_print_to_logging.py --module ui       # 迁移ui目录
    python scripts/migrate_print_to_logging.py --file core/test.py  # 迁移单个文件
    python scripts/migrate_print_to_logging.py --dry-run         # 仅预览不修改
    python scripts/migrate_print_to_logging.py --all              # 迁移所有Python文件

迁移规则:
    print("message")           → logger.info("message")
    print("a", "b")           → logger.info("a b")
    print(f"value={x}")      → logger.info(f"value={x}")
    print("error", file=...)  → logger.error("error")

作者: LivingTree AI Team
日期: 2026-04-24
"""

import os
import re
import sys
import argparse
from pathlib import Path
from typing import List, Tuple, Optional


# ============================================================================
# 配置
# ============================================================================

# 迁移优先级 (按优先级顺序处理)
PRIORITY_MODULES = [
    "core/agent",
    "core/intent",
    "core/memory",
    "core/task",
    "core/skill",
    "core/expert",
    "core/model",
    "core/knowledge",
    "core/unified",
    "core/unified_cache",
    "ui",
]

# 跳过的文件和目录
SKIP_PATTERNS = [
    "test_",           # 测试文件
    "_test_",          # 测试文件
    "__pycache__",
    ".pyc",
    "node_modules",
    ".venv",
    "venv",
    "env",
    "examples/",       # 示例代码
    "demo_",           # 示例代码
]

# print正则表达式
PRINT_PATTERN = re.compile(r'print\s*\((.*?)\)', re.DOTALL)

# ============================================================================
# 迁移逻辑
# ============================================================================

class PrintMigrator:
    """Print语句迁移器"""

    def __init__(self, module_name: str = "core"):
        self.module_name = module_name
        self.changes: List[Tuple[str, int, str, str]] = []  # (file, line, old, new)

    def _get_logger_name(self, file_path: str) -> str:
        """根据文件路径生成logger名称"""
        # 移除扩展名和路径前缀
        rel_path = file_path

        # 转换为模块名
        rel_path = rel_path.replace("\\", "/")
        rel_path = rel_path.replace("/", ".")
        rel_path = rel_path.replace(".py", "")

        # 移除前缀
        for prefix in ["core.", "ui.", "app.", "scripts."]:
            if rel_path.startswith(prefix):
                rel_path = rel_path[len(prefix):]
                break

        return f"{self.module_name}.{rel_path}" if self.module_name else rel_path

    def _should_add_import(self, content: str) -> bool:
        """检查是否需要添加import"""
        return "from client.src.business.logger import" not in content and "import client.src.business.logger" not in content

    def _add_import(self, content: str, module_path: str) -> str:
        """添加import语句"""
        logger_name = self._get_logger_name(module_path)

        # 在import区域添加
        import_line = f"from client.src.business.logger import get_logger\nlogger = get_logger('{logger_name}')\n"

        # 查找最后一个import语句的位置
        lines = content.split('\n')
        insert_pos = 0

        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('import ') or stripped.startswith('from '):
                insert_pos = i + 1

        lines.insert(insert_pos, import_line)
        return '\n'.join(lines)

    def _analyze_print_args(self, args: str) -> Tuple[str, str]:
        """
        分析print参数，返回 (level, message_template)

        level: debug/info/warning/error
        """
        args = args.strip()

        # 检查关键字参数
        if 'file=sys.stderr' in args or 'file=__stderr__' in args:
            return 'error', args.split(',')[0].strip() if ',' in args else args

        # 检查DEBUG/WARNING/ERROR等标记
        lower_args = args.lower()
        if 'error' in lower_args or 'exception' in lower_args:
            return 'error', args
        if 'warning' in lower_args or 'warn' in lower_args:
            return 'warning', args
        if 'debug' in lower_args:
            return 'debug', args

        return 'info', args

    def _convert_print_to_log(self, match: re.Match, file_path: str) -> str:
        """将print语句转换为logger调用"""
        args = match.group(1).strip()

        level, message = self._analyze_print_args(args)

        # 处理多参数
        if ',' in message:
            # print("a", "b") -> logger.info("a b")
            parts = message.split(',')
            message = ' + " " + '.join(p.strip() for p in parts if p.strip())
            return f'logger.{level}({message})'

        return f'logger.{level}({message})'

    def migrate_file(self, file_path: str, dry_run: bool = False) -> int:
        """
        迁移单个文件

        返回: 迁移的print语句数量
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return 0

        original_content = content
        line_num = 0

        # 替换print语句
        new_content = PRINT_PATTERN.sub(
            lambda m: self._convert_print_to_log(m, file_path),
            content
        )

        # 统计替换数量
        old_matches = PRINT_PATTERN.findall(original_content)
        count = len(old_matches)

        if count > 0 and not dry_run:
            # 添加import
            if self._should_add_import(new_content):
                new_content = self._add_import(new_content, file_path)

            # 写回文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

        return count

    def migrate_directory(self, dir_path: str, dry_run: bool = False, recursive: bool = True) -> int:
        """
        迁移目录下的所有Python文件

        返回: 总迁移数量
        """
        total = 0
        py_files = list(Path(dir_path).rglob("*.py") if recursive else Path(dir_path).glob("*.py"))

        for py_file in py_files:
            # 检查是否跳过
            skip = False
            for pattern in SKIP_PATTERNS:
                if pattern in str(py_file):
                    skip = True
                    break

            if skip:
                continue

            count = self.migrate_file(str(py_file), dry_run)
            if count > 0:
                total += count
                status = "[DRY RUN]" if dry_run else ""
                print(f"  {status} {py_file}: {count} print statements")

        return total


# ============================================================================
# 主程序
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Print语句迁移工具 - 替换为logger调用",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python migrate_print_to_logging.py                    # 迁移core目录
  python migrate_print_to_logging.py --module ui       # 迁移ui目录
  python migrate_print_to_logging.py --file core/test.py  # 迁移单个文件
  python migrate_print_to_logging.py --dry-run         # 仅预览不修改
  python migrate_print_to_logging.py --all              # 迁移所有Python文件
        """
    )

    parser.add_argument(
        '--module', '-m',
        default='core',
        help='要迁移的模块 (default: core)'
    )

    parser.add_argument(
        '--file', '-f',
        help='单个文件路径'
    )

    parser.add_argument(
        '--dir', '-d',
        help='目录路径 (覆盖--module)'
    )

    parser.add_argument(
        '--dry-run', '-n',
        action='store_true',
        help='仅预览不修改'
    )

    parser.add_argument(
        '--all', '-a',
        action='store_true',
        help='迁移所有Python文件'
    )

    parser.add_argument(
        '--priority',
        action='store_true',
        help='按优先级顺序迁移核心模块'
    )

    args = parser.parse_args()

    # 创建迁移器
    migrator = PrintMigrator(args.module)

    print("=" * 60)
    print("LivingTree AI - Print语句迁移工具")
    print("=" * 60)

    if args.dry_run:
        print("[DRY RUN MODE - 仅预览，不修改文件]")
        print()

    # 确定迁移范围
    if args.file:
        # 单文件
        print(f"迁移文件: {args.file}")
        total = migrator.migrate_file(args.file, args.dry_run)

    elif args.all:
        # 所有Python文件
        print(f"迁移所有Python文件...")
        base_path = Path(__file__).parent.parent
        total = migrator.migrate_directory(str(base_path), args.dry_run)

    elif args.priority:
        # 按优先级迁移
        print("按优先级迁移核心模块...")
        base_path = Path(__file__).parent.parent
        total = 0

        for module in PRIORITY_MODULES:
            module_path = base_path / module
            if module_path.exists():
                print(f"\n处理模块: {module}")
                count = migrator.migrate_directory(str(module_path), args.dry_run)
                total += count

    elif args.dir:
        # 指定目录
        print(f"迁移目录: {args.dir}")
        total = migrator.migrate_directory(args.dir, args.dry_run)

    else:
        # 默认core目录
        base_path = Path(__file__).parent.parent
        module_path = base_path / args.module
        print(f"迁移模块: {args.module}")
        print(f"路径: {module_path}")
        total = migrator.migrate_directory(str(module_path), args.dry_run)

    print()
    print("=" * 60)
    if args.dry_run:
        print(f"预计迁移: {total} 个print语句")
    else:
        print(f"已迁移: {total} 个print语句")
    print("=" * 60)


if __name__ == "__main__":
    main()
