"""
测试命令面板功能 - 独立测试脚本
"""

import sys
import os

# 设置路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'client', 'src'))

# 直接读取文件内容执行，避免包导入问题
command_palette_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'client', 'src', 'presentation', 'components', 'command_palette.py'
)

with open(command_palette_path, 'r', encoding='utf-8') as f:
    code = f.read()
    exec(code)

# 现在可以使用 CommandPalette, Command, CommandCategory
print("测试命令面板功能...")

# 测试 1: 创建命令面板并检查默认命令
palette = CommandPalette()
commands = palette.get_all_commands()
print(f"✓ 加载了 {len(commands)} 个默认命令")

# 测试 2: 检查常用命令
shortcuts = [cmd["shortcut"] for cmd in commands]
assert "/analyze" in shortcuts, "缺少 /analyze 命令"
assert "/report" in shortcuts, "缺少 /report 命令"
assert "/search" in shortcuts, "缺少 /search 命令"
assert "/help" in shortcuts, "缺少 /help 命令"
print("✓ 常用命令都已注册")

# 测试 3: 解析命令
parsed = palette.parse_command("/search query=python")
assert parsed is not None
assert parsed["shortcut"] == "/search"
# 检查参数是否正确解析
params = parsed["parameters"]
print(f"  解析参数: {params}")
assert "query" in params, f"参数解析失败: {params}"
print("✓ 命令解析正常")

# 测试 4: 执行命令
result = palette.execute_command("/help")
assert result is not None
assert result["command"] == "帮助"
print("✓ 命令执行正常")

# 测试 5: 命令建议
suggestions = palette.suggest_commands("/ana")
assert len(suggestions) > 0
assert any(s["shortcut"] == "/analyze" for s in suggestions)
print("✓ 命令建议正常")

# 测试 6: 注册自定义命令
def custom_handler(**kwargs):
    return {"custom": True}

custom_cmd = Command(
    name="自定义命令",
    description="测试",
    category=CommandCategory.OTHER,
    shortcut="/custom",
    handler=custom_handler
)
palette.register_command(custom_cmd)
assert "/custom" in [cmd["shortcut"] for cmd in palette.get_all_commands()]
print("✓ 自定义命令注册正常")

print("\n🎉 所有测试通过!")
