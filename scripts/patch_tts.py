"""
补丁脚本：为 ei_wizard_chat.py 添加 TTS 语音朗读功能
- 导入区：添加 TTS 库检测 + MossTTSAdapter
- 输入栏：在 🎤 按钮后添加 🔊 TTS 切换按钮
- _add_message()：助手消息自动朗读
"""
import re

FILE = r"f:\mhzyapp\LivingTreeAlAgent\client\src\presentation\wizards\ei_wizard_chat.py"

with open(FILE, 'r', encoding='utf-8') as f:
    content = f.read()

original = content

# ── 1. 在导入区添加 TTS 检测（放在 MSG_ACTIONS_SUPPORT 之后） ──────────
tts_import_block = '''
# 导入 TTS 语音朗读支持
try:
    import edge_tts
    from client.src.business.living_tree_ai.voice.voice_adapter import (
        MossTTSAdapter, VoiceConfig, TTSResult
    )
    TTS_AVAILABLE = True
    _tts_adapter = MossTTSAdapter()
    logger.info("[TTS] edge-tts 已安装，TTS 功能可用")
except ImportError as e:
    TTS_AVAILABLE = False
    _tts_adapter = None
    logger.warning(f"[TTS] TTS 功能不可用：{e}")
'''

# 在 MSG_ACTIONS_SUPPORT 块之后插入
anchor = '    logger.warning("消息操作模块导入失败，相关功能不可用")\n'
if anchor in content and 'TTS_AVAILABLE' not in content:
    content = content.replace(anchor, anchor + tts_import_block)
    print("[1/3] TTS 导入区已添加")
else:
    print("[1/3] 跳过（已存在或找不到锚点）")

# ── 2. 在输入栏添加 TTS 切换按钮（放在 voice_btn 之后、message_input 之前） ─
tts_btn_code = '''
        # TTS 语音朗读按钮
        self.tts_btn = QPushButton("🔊")
        self.tts_btn.setFixedSize(40, 40)
        self.tts_btn.setToolTip("语音朗读（点击开启/关闭）")
        self.tts_btn.setCheckable(True)
        self.tts_btn.setChecked(False)
        self.tts_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #e0e0e0;
                border-radius: 5px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
            }
            QPushButton:checked {
                background-color: #0078d4;
                color: white;
            }
        """)
        self.tts_btn.clicked.connect(self._toggle_tts)
        input_layout.addWidget(self.tts_btn)
'''

# 锚点：voice_btn 添加后、message_input 之前
anchor2 = '        input_layout.addWidget(self.voice_btn)\n        \n        # 消息输入框\n        self.message_input = QTextEdit()'
if anchor2 in content and 'tts_btn' not in content:
    content = content.replace(anchor2, '        input_layout.addWidget(self.voice_btn)\n' + tts_btn_code + '\n        # 消息输入框\n        self.message_input = QTextEdit()')
    print("[2/3] TTS 按钮已添加到输入栏")
else:
    print("[2/3] 跳过（已存在或找不到锚点）")

# ── 3. 添加 TTS 相关方法 + 修改 _add_message 支持朗读 ─────────────────────
tts_methods = '''
    # ── TTS 语音朗读 ─────────────────────────────────────────────
    
    def _toggle_tts(self, checked: bool):
        """切换 TTS 语音朗读开关"""
        if checked:
            if not TTS_AVAILABLE:
                self._add_message('assistant', "⚠️ TTS 语音库未安装，请运行：pip install edge-tts")
                self.tts_btn.setChecked(False)
                return
            self.tts_btn.setText("🔇")
            self.tts_btn.setToolTip("语音朗读（已开启，点击关闭）")
            self._add_message('assistant', "🔊 语音朗读已开启，我将朗读回复。")
        else:
            self.tts_btn.setText("🔊")
            self.tts_btn.setToolTip("语音朗读（点击开启/关闭）")
            self._add_message('assistant', "🔇 语音朗读已关闭。")

    def _speak_text(self, text: str):
        """语音朗读文本（在新线程中执行，避免阻塞 UI）"""
        if not TTS_AVAILABLE or not _tts_adapter:
            return
        import threading
        def _worker():
            try:
                import tempfile, os
                from PySide6.QtCore import QMetaObject, Qt
                # 清理文本（去掉 emoji 和特殊符号，避免朗读异常）
                clean = re.sub(r'[^\u4e00-\u9fff\u3000-\u303f\uff00-\uffef\w\s,.!?;:，。！？；：]', '', text)
                clean = clean[:200]  # 限制长度，避免朗读过长
                if not clean.strip():
                    return
                # 同步合成语音（在线程中，不阻塞 UI）
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    tmp_path = f.name
                result = _tts_adapter.synthesize_sync(clean, output_path=tmp_path)
                if result.success:
                    # 在主线程中播放音频
                    QMetaObject.invokeMethod(
                        self, "_on_tts_audio_ready",
                        Qt.ConnectionType.QueuedConnection,
                        QMetaObject.Qt_string(tmp_path)
                    )
                else:
                    logger.warning(f"[TTS] 合成失败: {result.error}")
            except Exception as e:
                logger.error(f"[TTS] 朗读失败: {e}")
        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

    @Slot(str)
    def _on_tts_audio_ready(self, audio_path: str):
        """TTS 音频就绪，播放音频"""
        try:
            from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
            from PySide6.QtCore import QUrl
            if not hasattr(self, '_tts_player'):
                self._tts_player = QMediaPlayer()
                self._tts_audio_output = QAudioOutput()
                self._tts_player.setAudioOutput(self._tts_audio_output)
            self._tts_player.stop()
            self._tts_player.setSource(QUrl.fromLocalFile(audio_path))
            self._tts_player.play()
            # 播放完成后删除临时文件（延迟 5 秒）
            from PySide6.QtCore import QTimer
            QTimer.singleShot(5000, lambda: self._cleanup_tts_file(audio_path))
        except Exception as e:
            logger.error(f"[TTS] 播放失败: {e}")

    def _cleanup_tts_file(self, path: str):
        """清理 TTS 临时音频文件"""
        try:
            import os
            os.unlink(path)
        except:
            pass
'''

# 在文件末尾（if __name__ 之前）插入 TTS 方法
if 'TTS_AVAILABLE' in content and '_speak_text' not in content:
    # 找到 EIWizardChat 类的结束位置（在 if __name__ 之前）
    # 插入到 _check_task_status 方法之后、if __main__ 之前
    anchor3 = '            logger.warning(f"[TTS] 清理临时文件失败: {e}")\n'
    if anchor3 in content:
        # 已存在部分代码，跳过
        print("[3/3] TTS 方法似乎已存在，跳过")
    else:
        # 在文件末尾插入
        insert_anchor = '\nif __name__ == "__main__":'
        if insert_anchor in content:
            content = content.replace(insert_anchor, tts_methods + '\n' + insert_anchor)
            print("[3/3] TTS 方法已添加到文件末尾")
        else:
            content += tts_methods
            print("[3/3] TTS 方法已追加到文件末尾")
else:
    print("[3/3] 跳过（TTS 导入未成功或方法已存在）")

# ── 4. 修改 _add_message 方法，助手消息自动朗读 ──────────────────────────
# 找到助手消息添加后的位置，插入 TTS 调用
# 在 _add_message 方法中，助手消息更新后调用 _speak_text
old_add = "        # 更新最后一条助手消息（用于流式输出）\n            if role == 'assistant':\n                self._update_last_assistant_message(content)"
new_add = """        # 更新最后一条助手消息（用于流式输出）
            if role == 'assistant':
                self._update_last_assistant_message(content)
                # TTS 朗读（如果已开启）
                if hasattr(self, 'tts_btn') and self.tts_btn.isChecked():
                    self._speak_text(content)"""

if old_add in content and '_speak_text' in content:
    content = content.replace(old_add, new_add)
    print("[4/4] _add_message() 已添加 TTS 朗读调用")
else:
    print("[4/4] 跳过 _add_message 修改（找不到锚点或 _speak_text 未定义）")

# 写回文件
with open(FILE, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"\n✅ 完成！修改了 {len(original)} → {len(content)} 字符")
print(f"   建议运行：python -m py_compile \"{FILE}\"  检查语法")
