# -*- coding: utf-8 -*-
"""
rebuild_indent.py - 重建 ei_wizard_chat.py 的正确缩进
问题：init_ui() 方法没有正确关闭，导致后面所有方法缩进错误
"""
import sys, re

FILE = r"f:\mhzyapp\LivingTreeAlAgent\client\src\presentation\wizards\ei_wizard_chat.py"

with open(FILE, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 找 EIWizardChat 类的起始和结束
in_class = False
class_lines = []
for i, line in enumerate(lines):
    if line.startswith('class EIWizardChat'):
        in_class = True
    if in_class:
        class_lines.append(i)
    if in_class and line.startswith('if __name__'):
        break

print(f"[rebuild] EIWizardChat 类：行 0 ~ {class_lines[-1]} (共 {len(class_lines)} 行)")

# 方法定义的正则
method_re = re.compile(r'^(\s*)def (\w+)\(self')
class_re = re.compile(r'^class ')

# 重建正确缩进
new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    # 检查方法定义
    m = method_re.match(line)
    if m:
        indent = m.group(1)
        method_name = m.group(2)
        # 类方法应该是 4 空格缩进
        if len(indent) >= 8:
            # 缩进过多，修复为 4 空格
            line = '    def ' + line.lstrip()
            print(f"  [fix] {method_name} 缩进已修复")
    new_lines.append(line)
    i += 1

# 写回
with open(FILE, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print(f"\n[rebuild] 完成！共 {len(new_lines)} 行")
print(f"  运行语法检查：python -m py_compile \"{FILE}\"")
