# -*- coding: utf-8 -*-
"""
批量Print迁移脚本
=================

自动扫描并替换多个文件中的print语句为logger调用

使用方法:
    python scripts/batch_migrate_prints.py --list core/agent_chat.py unified_cache.py

作者: LivingTree AI Team
日期: 2026-04-24
"""

import re
import sys
from pathlib import Path


def migrate_file(file_path: str) -> int:
    """
    迁移单个文件

    Returns:
        迁移的print语句数量
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return 0

    original = content

    # 1. 添加import (如果没有)
    if 'from client.src.business.logger import get_logger' not in content:
        # 找到import区域
        lines = content.split('\n')
        import_pos = 0

        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('import ') or stripped.startswith('from '):
                import_pos = i + 1

        # 生成模块名
        module_name = file_path.replace('\\', '/').replace('/', '.').replace('.py', '')
        for prefix in ['core.', 'ui.', 'app.', 'scripts.']:
            if module_name.startswith(prefix):
                module_name = module_name[len(prefix):]
                break

        import_line = f"from client.src.business.logger import get_logger\nlogger = get_logger('{module_name}')\n"
        lines.insert(import_pos, import_line)
        content = '\n'.join(lines)

    # 2. 替换print语句
    # 简单print
    content = re.sub(
        r'print\((["\'])(.*?)\1\)',
        lambda m: f'logger.info({m.group(1)}{m.group(2)}{m.group(1)})',
        content
    )

    # f-string print
    content = re.sub(
        r'print\(f(["\'])(.*?)\1\)',
        lambda m: f'logger.info(f{m.group(1)}{m.group(2)}{m.group(1)})',
        content
    )

    # 变量print
    content = re.sub(
        r'print\(f"',
        'logger.info(f"',
        content
    )

    # 格式化print
    content = re.sub(
        r'print\(([^)]+)\)',
        lambda m: f'logger.info({m.group(1)})',
        content
    )

    # 统计替换数量
    old_prints = re.findall(r'print\(', original)
    new_prints = re.findall(r'logger\.(info|debug|warning|error)\(', content)

    count = len(old_prints) - len(re.findall(r'print\(', content))

    if count > 0:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

    return count


def main():
    if len(sys.argv) < 2:
        print("Usage: python batch_migrate_prints.py <file1> [file2] ...")
        sys.exit(1)

    total = 0
    for file_path in sys.argv[1:]:
        path = Path(file_path)
        if not path.exists():
            print(f"File not found: {file_path}")
            continue

        count = migrate_file(str(path))
        if count > 0:
            print(f"Migrated {path}: {count} print statements")
            total += count

    print(f"\nTotal: {total} print statements migrated")


if __name__ == "__main__":
    main()
