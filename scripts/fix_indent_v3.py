# -*- coding: utf-8 -*-
"""
fix_indent_v3.py - 彻底重建 ei_wizard_chat.py 的缩进
正确识别类方法边界，重建 4 空格（方法定义）+ 8 空格（方法体）
"""
import sys, re

FILE = r"f:\mhzyapp\LivingTreeAlAgent\client\src\presentation\wizards\ei_wizard_chat.py"

with open(FILE, 'r', encoding='utf-8') as f:
    lines = [ln.rstrip('\n\r') for ln in f]

# 找 EIWizardChat 类的范围
in_class = False
class_start = None
class_end = None

for i, ln in enumerate(lines):
    if ln.startswith('class EIWizardChat('):
        in_class = True
        class_start = i
    if in_class and ln.startswith('if __name__'):
        class_end = i
        break

if class_start is None:
    print("ERROR: cannot find EIWizardChat class")
    sys.exit(1)

print(f"[v3] EIWizardChat 类：行 {class_start+1} ~ {class_end+1}")

# 提取类体（不含类定义行）
class_body = lines[class_start+1:class_end]  # 不含 class 定义行
print(f"[v3] 类体行数：{len(class_body)}")

# 方法定义的正则：以 0~4 个空格开头 + def xxx(self
method_re = re.compile(r'^(\s*)def (\w+)\(self')
# TTS 方法（在类体内，但缩进为 0 或 8 个空格）
# 以及 __init__、_init_ui 等

# 第一遍：找到所有方法定义的行号（在类体内）
method_lines = []  # [(line_index_in_class_body, indent_len, method_name)]
for i, ln in enumerate(class_body):
    m = method_re.match(ln)
    if m:
        indent = len(m.group(1))
        name = m.group(2)
        method_lines.append((i, indent, name))

print(f"[v3] 找到 {len(method_lines)} 个方法定义：")
for i, indent, name in method_lines:
    print(f"  行 {class_start+1+i+1}：{name}（原缩进 {indent} 空格）")

# 第二遍：重建缩进
# 每个方法：定义行 4 空格，方法体 8 空格，嵌套块 12+ 空格
new_body = []
current_method = None  # (start_idx, original_indent)
method_idx = 0

i = 0
while i < len(class_body):
    ln = class_body[i]
    
    # 检查是否是方法定义
    if method_idx < len(method_lines) and i == method_lines[method_idx][0]:
        _, orig_indent, name = method_lines[method_idx]
        # 方法定义固定 4 空格
        new_body.append('    def ' + ln.lstrip())
        current_method = (i, orig_indent)
        method_idx += 1
        i += 1
        continue
    
    # 普通行：根据是否在方法内决定缩进
    if current_method is not None:
        _, orig_indent = current_method
        stripped = ln.lstrip()
        if stripped == '':
            new_body.append('')
            i += 1
            continue
        # 原来的缩进是 orig_indent + X，现在要变成 4 + X
        # 即：新缩进 = 4 + (原缩进 - orig_indent)
        current_indent = len(ln) - len(stripped)
        if orig_indent > 0 and current_indent >= orig_indent:
            extra = current_indent - orig_indent
        else:
            # 方法定义行可能已经改了，这里兜底
            extra = max(0, current_indent - 4)
        new_body.append(' ' * (4 + extra) + stripped)
    else:
        # 不在任何方法内（理论上不应该发生）
        new_body.append('    ' + ln.lstrip())
    
    i += 1

# 拼回完整文件
new_lines = lines[:class_start+1] + [''] + new_body + ['', ''] + lines[class_end:]

# 修复可能出现的 def def 错误
fixed_content = '\n'.join(new_lines)
fixed_content = fixed_content.replace('def def ', 'def ')

# 写回
with open(FILE, 'w', encoding='utf-8') as f:
    f.write(fixed_content)

print(f"\n[v3] 完成！共 {len(new_lines)} 行")
print(f"[v3] 正在语法检查...")

# 语法检查
import py_compile
try:
    py_compile.compile(FILE, doraise=True)
    print("[v3] OK：语法检查通过！")
except py_compile.PyCompileError as e:
    print(f"[v3] ERROR: {e}")
    sys.exit(1)
