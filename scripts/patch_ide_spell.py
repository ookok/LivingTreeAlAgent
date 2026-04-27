"""
Patch ide/panel.py to integrate SpellCheckTextEdit
"""
filepath = r"f:\mhzyapp\LivingTreeAlAgent\client\src\presentation\modules\ide\panel.py"

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

content = ''.join(lines)

# 1. Add import after the last import block
old_import = 'from ..theme import theme_manager'
new_import = old_import + '\nfrom ..components.spell_check_edit import SpellCheckTextEdit'
content = content.replace(old_import, new_import)

# 2. Replace self.message_input = QTextEdit() and its placeholder/style
old_input = '''        self.message_input = QTextEdit()
        self.message_input.setMaximumHeight(100)
        self.message_input.setPlaceholderText("输入你的需求，我会自动生成/修改代码...\n\n示例：\n- 创建一个用户登录模块\n- 修改homepage.py，添加深色模式切换按钮\n- 帮我优化这段代码的速度")
        self.message_input.setStyleSheet("""
            QTextEdit {
                background-color: #252526;
                color: #d4d4d4;
                border: 1px solid #3e3e42;
                border-radius: 5px;
                padding: 8px;
            }
        """)'''

new_input = '''        self.message_input = SpellCheckTextEdit("输入你的需求，我会自动生成/修改代码...\n\n示例：\n- 创建一个用户登录模块\n- 修改homepage.py，添加深色模式切换按钮\n- 帮我优化这段代码的速度")
        self.message_input.setMaximumHeight(100)
        self.message_input.setStyleSheet("""
            QTextEdit {
                background-color: #252526;
                color: #d4d4d4;
                border: 1px solid #3e3e42;
                border-radius: 5px;
                padding: 8px;
            }
        """)
        
        # 连接错别字检测信号
        self.message_input.corrections_found.connect(self._on_corrections_found)'''

content = content.replace(old_input, new_input)

# 3. Add _on_corrections_found method before send_message
old_send = '    def send_message(self):'
new_method = '''    def _on_corrections_found(self, corrections: list):
        """
        检测到错别字时的处理
        
        Args:
            corrections: 错别字列表 [{"original":, "corrected":, ...}]
        """
        if corrections:
            print(f"[IDE拼写检查] 发现 {len(corrections)} 个疑似错别字")
        else:
            print("[IDE拼写检查] 未发现错别字")
    
    def send_message(self):'''

content = content.replace(old_send, new_method)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("ide/panel.py 修改完成")
print(f"  + 导入 SpellCheckTextEdit")
print(f"  + 替换 message_input 为 SpellCheckTextEdit")
print(f"  + 添加 _on_corrections_found 方法")
