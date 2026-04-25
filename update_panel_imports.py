#!/usr/bin/env python3
"""
更新 client/src/presentation/panels/ 中文件的内部导入引用
将 from ui.xxx import 更新为 from client.src.presentation.panels.xxx import
"""
import re
from pathlib import Path

# 工作目录
WORKSPACE = Path("f:/mhzyapp/LivingTreeAlAgent")
PANELS_DIR = WORKSPACE / "client/src/presentation/panels"

def update_internal_imports():
    """更新 panels 目录中所有文件的内部导入"""
    print("=" * 60)
    print("Updating Internal Imports in client/src/presentation/panels/")
    print("=" * 60)

    # 获取所有 Python 文件
    py_files = list(PANELS_DIR.glob("*.py"))
    print(f"\n[INFO] Found {len(py_files)} Python files to check")

    updated_count = 0

    for filepath in py_files:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # 检查是否有 ui. 的导入
            if "from ui." in content or "import ui." in content:
                # 替换 from ui.xxx import YYY -> from client.src.presentation.panels.xxx import YYY
                content = re.sub(
                    r"from ui\.(\w+) import",
                    r"from client.src.presentation.panels.\1 import",
                    content
                )

                # 替换 import ui.xxx -> import client.src.presentation.panels.xxx
                content = re.sub(
                    r"import ui\.(\w+)",
                    r"import client.src.presentation.panels.\1",
                    content
                )

                # 替换 from ui import xxx -> from client.src.presentation.panels import xxx
                content = re.sub(
                    r"from ui import (\w+)",
                    r"from client.src.presentation.panels import \1",
                    content
                )

                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)

                print(f"[OK] Updated: {filepath.name}")
                updated_count += 1

        except Exception as e:
            print(f"[ERROR] Failed to update {filepath.name}: {e}")

    print("\n" + "=" * 60)
    print(f"[SUMMARY] Updated {updated_count}/{len(py_files)} files")
    print("=" * 60)

if __name__ == "__main__":
    update_internal_imports()
