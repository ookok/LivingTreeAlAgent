# -*- coding: utf-8 -*-
"""
do_patch.py - 为 ei_wizard_chat.py 添加 TTS 语音朗读功能
运行：python scripts/do_patch.py
"""
import sys
import os

FILE = r"f:\mhzyapp\LivingTreeAlAgent\client\src\presentation\wizards\ei_wizard_chat.py"

with open(FILE, 'r', encoding='utf-8') as f:
    c = f.read()

modified = False

# ── 1. 导入区添加 TTS 检测 ──────────────────────────
anchor1 = '    logger.warning("消息操作模块导入失败，相关功能不可用")\n'
block1 = (
    '\n'
    '# TTS 语音朗读支持\n'
    'try:\n'
    '    import edge_tts\n'
    '    from client.src.business.living_tree_ai.voice.voice_adapter import (\n'
    '        MossTTSAdapter, VoiceConfig\n'
    '    )\n'
    '    TTS_AVAILABLE = True\n'
    '    _tts_adapter = MossTTSAdapter()\n'
    '    logger.info("[TTS] edge-tts 已安装，TTS 功能可用")\n'
    'except Exception as e:\n'
    '    TTS_AVAILABLE = False\n'
    '    _tts_adapter = None\n'
    '    logger.warning(f"[TTS] TTS 功能不可用：{e}")\n'
)

if anchor1 in c and 'TTS_AVAILABLE' not in c:
    c = c.replace(anchor1, anchor1 + block1)
    print("[1/4] TTS 导入区已添加")
    modified = True
else:
    print("[1/4] 跳过（已存在或找不到锚点）")

# ── 2. 输入栏添加 TTS 切换按钮 ─────────────────────
anchor2 = '        input_layout.addWidget(self.voice_btn)\n'
btn_code = (
    '\n'
    '        # TTS 语音朗读按钮\n'
    '        self.tts_btn = QPushButton("🔊")\n'
    '        self.tts_btn.setFixedSize(40, 40)\n'
    '        self.tts_btn.setToolTip("语音朗读（点击开启/关闭）")\n'
    '        self.tts_btn.setCheckable(True)\n'
    '        self.tts_btn.setChecked(False)\n'
    '        self.tts_btn.setStyleSheet("""\n'
    '            QPushButton {\n'
    '                background-color: transparent;\n'
    '                border: 1px solid #e0e0e0;\n'
    '                border-radius: 5px;\n'
    '                font-size: 16px;\n'
    '            }\n'
    '            QPushButton:hover {\n'
    '                background-color: #f0f0f0;\n'
    '            }\n'
    '            QPushButton:checked {\n'
    '                background-color: #0078d4;\n'
    '                color: white;\n'
    '            }\n'
    '        """)\n'
    '        self.tts_btn.clicked.connect(self._toggle_tts)\n'
    '        input_layout.addWidget(self.tts_btn)\n'
)

if anchor2 in c and 'tts_btn' not in c:
    c = c.replace(anchor2, anchor2 + btn_code)
    print("[2/4] TTS 按钮已添加到输入栏")
    modified = True
else:
    print("[2/4] 跳过（已存在或找不到锚点）")

# ── 3. 修改 _add_message：助手消息自动朗读 ─────────────
old_branch = (
    "            if role == 'assistant':\n"
    "                self._update_last_assistant_message(content)\n"
)
new_branch = (
    "            if role == 'assistant':\n"
    "                self._update_last_assistant_message(content)\n"
    "                # TTS 朗读（如果已开启）\n"
    "                if hasattr(self, 'tts_btn') and self.tts_btn.isChecked():\n"
    "                    self._speak_text(content)\n"
)

if old_branch in c and '_speak_text(content)' not in c:
    c = c.replace(old_branch, new_branch)
    print("[3/4] _add_message() 已添加 TTS 朗读调用")
    modified = True
elif '_speak_text(content)' in c:
    print("[3/4] 跳过（已存在）")
else:
    print("[3/4] 警告：找不到 _add_message 锚点")

# ── 4. 添加 TTS 相关方法 ─────────────────────────────
tts_methods = (
    '\n'
    '    # ── TTS 语音朗读 ─────────────────────────────────────\n'
    '\n'
    '    def _toggle_tts(self, checked: bool):\n'
    '        """切换 TTS 语音朗读开关"""\n'
    '        if checked:\n'
    '            if not TTS_AVAILABLE:\n'
    '                self._add_message("assistant", "⚠️ TTS 语音库未安装，请运行：pip install edge-tts")\\\n'
    '                self.tts_btn.setChecked(False)\n'
    '                return\n'
    '            self.tts_btn.setText("🔇")\n'
    '            self.tts_btn.setToolTip("语音朗读（已开启，点击关闭）")\n'
    '            self._add_message("assistant", "🔊 语音朗读已开启，我将朗读回复。")\\\n'
    '        else:\n'
    '            self.tts_btn.setText("🔊")\n'
    '            self.tts_btn.setToolTip("语音朗读（点击开启/关闭）")\n'
    '            self._add_message("assistant", "🔇 语音朗读已关闭。")\\\n'
    '\n'
    '    def _speak_text(self, text: str):\n'
    '        """语音朗读文本（在线程中执行，避免阻塞 UI）"""\n'
    '        if not TTS_AVAILABLE or not _tts_adapter:\n'
    '            return\n'
    '        import threading\n'
    '        def _worker():\n'
    '            try:\n'
    '                import tempfile, os, re\n'
    '                from PySide6.QtCore import QMetaObject, Qt\n'
    '                clean = re.sub(r"[^\\u4e00-\\u9fff\\u3000-\\u303f\\uff00-\\uffef\\w\\s,.!?;:，。！？；：]"\n'
    '                               "\x20", text)\n'
    '                clean = clean[:200]\n'
    '                if not clean.strip():\n'
    '                    return\n'
    '                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:\n'
    '                    tmp_path = f.name\n'
    '                result = _tts_adapter.synthesize_sync(clean, output_path=tmp_path)\n'
    '                if result.success:\n'
    '                    QMetaObject.invokeMethod(\n'
    '                        self, "_on_tts_audio_ready",\n'
    '                        Qt.ConnectionType.QueuedConnection,\n'
    '                        QMetaObject.Qt_string(tmp_path)\n'
    '                    )\n'
    '                else:\n'
    '                    logger.warning(f"[TTS] 合成失败: {result.error}")\n'
    '            except Exception as e:\n'
    '                logger.error(f"[TTS] 朗读失败: {e}")\n'
    '        thread = threading.Thread(target=_worker, daemon=True)\n'
    '        thread.start()\n'
    '\n'
    '    @Slot(str)\n'
    '    def _on_tts_audio_ready(self, audio_path: str):\n'
    '        """TTS 音频就绪，播放音频"""\n'
    '        try:\n'
    '            from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput\n'
    '            from PySide6.QtCore import QUrl, QTimer\n'
    '            if not hasattr(self, "_tts_player"):\n'
    '                self._tts_player = QMediaPlayer()\n'
    '                self._tts_audio_output = QAudioOutput()\n'
    '                self._tts_player.setAudioOutput(self._tts_audio_output)\n'
    '            self._tts_player.stop()\n'
    '            self._tts_player.setSource(QUrl.fromLocalFile(audio_path))\n'
    '            self._tts_player.play()\n'
    '            QTimer.singleShot(5000, lambda: self._cleanup_tts_file(audio_path))\n'
    '        except Exception as e:\n'
    '            logger.error(f"[TTS] 播放失败: {e}")\n'
    '\n'
    '    def _cleanup_tts_file(self, path: str):\n'
    '        """清理 TTS 临时音频文件"""\n'
    '        try:\n'
    '            import os\n'
    '            os.unlink(path)\n'
    '        except:\n'
    '            pass\n'
)

marker = '\nif __name__ == "__main__":'
if marker in c and '_speak_text' not in c:
    c = c.replace(marker, tts_methods + marker)
    print("[4/4] TTS 方法已添加到文件末尾")
    modified = True
elif '_speak_text' in c:
    print("[4/4] 跳过（方法已存在）")
else:
    print("[4/4] 警告：找不到文件末尾锚点")

# 写回文件
with open(FILE, 'w', encoding='utf-8') as f:
    f.write(c)

print(f"\n{'✅ 修改完成！' if modified else '⚠️ 没有做任何修改'}")
print(f"   文件长度：{len(c)} 字符")
