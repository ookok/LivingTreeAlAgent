"""
Patch ei_wizard_chat.py to integrate SpellCheckTextEdit
"""
import re

filepath = r"f:\mhzyapp\LivingTreeAlAgent\client\src\presentation\wizards\ei_wizard_chat.py"

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

content = ''.join(lines)

# 1. Add import after PySide6.QtGui import line
old_gui_import = 'from PySide6.QtGui import QFont, QIcon, QTextCursor, QDesktopServices, QCursor, QAction, QClipboard'
new_gui_import = old_gui_import + '\nfrom client.src.presentation.components.spell_check_edit import SpellCheckTextEdit'
content = content.replace(old_gui_import, new_gui_import)

# 2. Replace self.message_input = QTextEdit() and its styling
old_input_block = '''        # 消息输入框
        self.message_input = QTextEdit()
        self.message_input.setMaximumHeight(80)
        self.message_input.setPlaceholderText("输入你的需求，我会帮你生成环评报告...")
        self.message_input.setStyleSheet("""
            QTextEdit {
                border: 1px solid #e0e0e0;
                border-radius: 5px;
                padding: 8px;
                font-size: 14px;
                background-color: #fafafa;
            }
            QTextEdit:focus {
                border: 1px solid #0078d4;
            }
        """)'''

new_input_block = '''        # 消息输入框（带实时错别字检查）
        self.message_input = SpellCheckTextEdit("输入你的需求，我会帮你生成环评报告...")
        self.message_input.setMaximumHeight(80)
        self.message_input.setStyleSheet("""
            QTextEdit {
                border: 1px solid #e0e0e0;
                border-radius: 5px;
                padding: 8px;
                font-size: 14px;
                background-color: #fafafa;
            }
            QTextEdit:focus {
                border: 1px solid #0078d4;
            }
        """)
        
        # 连接错别字检测信号
        self.message_input.corrections_found.connect(self._on_corrections_found)'''

content = content.replace(old_input_block, new_input_block)

# 3. Add the _on_corrections_found method before _send_message
old_send = '    def _send_message(self):'
new_method = '''    def _on_corrections_found(self, corrections: list):
        """
        检测到错别字时的处理
        
        Args:
            corrections: 错别字列表 [{"original":, "corrected":, ...}]
        """
        if corrections:
            print(f"[拼写检查] 发现 {len(corrections)} 个疑似错别字")
            # 可以在这里添加 UI 提示（如状态栏显示）
            for c in corrections:
                print(f"  - {c.get('original', '')} → {c.get('corrected', '')} ({c.get('reason', '')})")
        else:
            print("[拼写检查] 未发现错别字")
    
    def _send_message(self):'''

content = content.replace(old_send, new_method)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("ei_wizard_chat.py 修改完成")
print(f"  + 导入 SpellCheckTextEdit")
print(f"  + 替换 message_input 为 SpellCheckTextEdit")
print(f"  + 添加 _on_corrections_found 方法")
