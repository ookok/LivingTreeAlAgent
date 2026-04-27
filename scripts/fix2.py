# -*- coding: utf-8 -*-
"""
fix2.py - 修复 TTS 方法缩进 + 让助手消息自动朗读
只输出 ASCII，避免 PowerShell 编码错误
"""
import sys

FILE = r"f:\mhzyapp\LivingTreeAlAgent\client\src\presentation\wizards\ei_wizard_chat.py"

with open(FILE, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 找关键行号
main_idx = None
tts_idx = None
for i, line in enumerate(lines):
    if '__name__' in line and '__main__' in line:
        main_idx = i
    if tts_idx is None and ('def _toggle_tts' in line or '# TTS' in line):
        tts_idx = i

print("[fix2] main_idx =", main_idx)
print("[fix2] tts_idx  =", tts_idx)

if main_idx is None:
    print("[fix2] ERROR: cannot find __main__")
    sys.exit(1)

if tts_idx is None:
    print("[fix2] TTS methods not found - may already be fixed")
    # 检查 _add_message 是否调用 _speak_text
    content = ''.join(lines)
    if '_speak_text(content)' in content:
        print("[fix2] OK: _add_message already calls _speak_text")
    else:
        print("[fix2] WARNING: _add_message does NOT call _speak_text")
    sys.exit(0)

# 提取 TTS 方法并在每行前加 8 个空格（类方法缩进）
tts_block = lines[tts_idx:]
indented = []
for ln in tts_block:
    if ln.strip() == '':
        indented.append(ln)
    else:
        indented.append('        ' + ln)

print("[fix2] tts_block length =", len(tts_block))

# 在 __main__ 之前插入（找最后一个非空的类内容行）
insert_idx = main_idx
while insert_idx > 0 and lines[insert_idx].strip() == '':
    insert_idx -= 1
insert_idx += 1  # 插在 __main__ 前面的空行处

new_lines = lines[:insert_idx] + ['\n'] + indented + ['\n'] + lines[insert_idx:tts_idx]

print("[fix2] new file length =", len(new_lines))

# 修复 _add_message 调用 TTS
content = ''.join(new_lines)
old_str = "                self._update_last_assistant_message(content)\n"
new_str = ("                self._update_last_assistant_message(content)\n"
           "                # TTS 朗读（如果已开启）\n"
           "                if hasattr(self, 'tts_btn') and self.tts_btn.isChecked():\n"
           "                    self._speak_text(content)\n")

if old_str in content and '_speak_text(content)' not in content:
    content = content.replace(old_str, new_str)
    print("[fix2] _add_message now calls _speak_text")
elif '_speak_text(content)' in content:
    print("[fix2] _add_message already calls _speak_text")
else:
    print("[fix2] WARNING: could not patch _add_message")

# 写回
with open(FILE, 'w', encoding='utf-8') as f:
    f.write(content)

print("[fix2] DONE - file written")
print("[fix2] new file size =", len(content))
