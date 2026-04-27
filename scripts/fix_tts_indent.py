# -*- coding: utf-8 -*-
"""
fix_tts_indent.py - 修复 TTS 方法缩进问题
1. 把文件末尾的 TTS 方法移入 EIWizardChat 类
2. 修改 _add_message 让助手消息自动朗读
"""
import re

FILE = r"f:\mhzyapp\LivingTreeAlAgent\client\src\presentation\wizards\ei_wizard_chat.py"

with open(FILE, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 找到关键行号
class_start = None
name_main_line = None
tts_start = None

for i, line in enumerate(lines):
    if line.startswith('class EIWizardChat('):
        class_start = i
    if '__name__' in line and '__main__' in line:
        name_main_line = i
        break

print(f"class EIWizardChat 起始行: {class_start}")
print(f"__main__ 起始行: {name_main_line}")

# 找到 TTS 方法起始位置（在 __main__ 之后）
if name_main_line:
    for i in range(name_main_line + 1, len(lines)):
        if '# ── TTS' in lines[i] or '_toggle_tts' in lines[i]:
            tts_start = i
            break

print(f"TTS 方法起始行: {tts_start}")

if tts_start is None:
    print("⚠ TTS 方法未找到，可能已修复")
    # 检查 _add_message 是否已调用 _speak_text
    content = ''.join(lines)
    if '_speak_text(content)' in content:
        print("✅ _add_message 已包含 TTS 调用")
    else:
        print("⚠️ _add_message 未包含 TTS 调用")
    import sys
    sys.exit(0)

# 提取 TTS 方法（从 tts_start 到文件末尾）
tts_lines = lines[tts_start:]
print(f"提取 TTS 方法：{len(tts_lines)} 行")

# 为 TTS 方法添加缩进（8 个空格 = 类方法级别）
indented_tts = []
for line in tts_lines:
    if line.strip() == '':
        indented_tts.append(line)
    else:
        indented_tts.append('        ' + line)

# 在 __main__ 之前插入 TTS 方法
# 找到 __main__ 行，在这之前插入
insert_pos = name_main_line
while insert_pos > 0 and lines[insert_pos].strip() == '':
    insert_pos -= 1
insert_pos += 1  # 插入到 __main__ 之前的空行

new_lines = lines[:insert_pos] + ['\n'] + indented_tts + ['\n'] + lines[insert_pos:tts_start]

# 写回文件（先不写，检查是否正确）
print(f"新文件行数：{len(new_lines)}")

# 检查 _add_message 是否调用 _speak_text
content = ''.join(new_lines)
if '_speak_text(content)' not in content:
    # 需要修改 _add_message
    old = "                self._update_last_assistant_message(content)\n"
    new = ("                self._update_last_assistant_message(content)\n"
            "                # TTS 朗读（如果已开启）\n"
            "                if hasattr(self, 'tts_btn') and self.tts_btn.isChecked():\n"
            "                    self._speak_text(content)\n")
    if old in content:
        content = content.replace(old, new)
        print("[✅] _add_message 已添加 TTS 调用")
    else:
        print("[⚠️] 找不到 _add_message 锚点")

# 写回文件
with open(FILE, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"\n✅ 修复完成！")
print(f"   建议运行：python -m py_compile \"{FILE}\"")
