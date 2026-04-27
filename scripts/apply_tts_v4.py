#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TTS 功能集成脚本 v4
为 ei_wizard_chat.py 添加 nano-TTS 语音朗读功能
"""

import sys

FILE = r'f:\mhzyapp\LivingTreeAlAgent\client\src\presentation\wizards\ei_wizard_chat.py'

with open(FILE, 'r', encoding='utf-8') as f:
    lines = f.readlines()

result = []
i = 0
while i < len(lines):
    line = lines[i]
    
    # ================================================================
    # 1. 在导入区添加 TTS 检测（在 MSG_ACTIONS_SUPPORT 块后面）
    # ================================================================
    if 'logger.warning("消息操作模块导入失败，相关功能不可用")' in line:
        result.append(line)
        i += 1
        # 添加空行和 TTS 导入块
        tts_import = '''
# 导入 TTS 语音朗读支持
try:
    import edge_tts
    from client.src.business.living_tree_ai.voice.voice_adapter import (
        MossTTSAdapter, VoiceConfig
    )
    TTS_AVAILABLE = True
    _tts_adapter = MossTTSAdapter()
    logger.info('[TTS] edge-tts 已安装，TTS 功能可用')
except Exception as e:
    TTS_AVAILABLE = False
    _tts_adapter = None
    logger.warning(f'[TTS] TTS 功能不可用：{e}')
'''
        result.append(tts_import)
        continue
    
    # ================================================================
    # 2. 在输入栏 voice_btn 后添加 TTS 按钮
    # ================================================================
    if "input_layout.addWidget(self.voice_btn)" in line and "tts_btn" not in "".join(lines[max(0,i-5):i+5]):
        result.append(line)
        i += 1
        # 添加 TTS 按钮代码
        tts_btn_code = '''
        # TTS 语音朗读按钮
        self.tts_btn = QPushButton('🔊')
        self.tts_btn.setFixedSize(40, 40)
        self.tts_btn.setToolTip('语音朗读（点击开启/关闭）')
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
        result.append(tts_btn_code)
        continue
    
    # ================================================================
    # 3. 在 _add_message 的助手分支添加 TTS 调用
    # ================================================================
    if "self.current_assistant_bubble = bubble" in line and "tts" not in "".join(lines[max(0,i-20):i]):
        result.append(line)
        i += 1
        # 添加 TTS 调用
        tts_call = '''
        # TTS 语音朗读（如果已开启）
        if hasattr(self, 'tts_btn') and self.tts_btn.isChecked():
            self._speak_text(content)
'''
        result.append(tts_call)
        continue
    
    # ================================================================
    # 4. 在 EIWizardChat 类末尾添加 TTS 方法
    #    定位：在 _on_voice_recognize_error 方法后面，但在类外
    # ================================================================
    if '_on_voice_recognize_error' in line and line.strip().startswith('def '):
        # 找到这个方法结束的位置
        result.append(line)
        i += 1
        while i < len(lines):
            result.append(lines[i])
            # 检查方法是否结束（下一行是空行或下一个 def 或类结束）
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                # 如果下一行是类方法定义或类结束，说明当前方法已结束
                if (next_line.strip().startswith('def ') or 
                    next_line.strip().startswith('class ') or
                    (next_line.strip() == '' and i + 2 < len(lines) and 
                     lines[i + 2].strip().startswith('class '))):
                    i += 1
                    break
            i += 1
        
        # 添加 TTS 方法
        tts_methods = '''
    
    # ── TTS 语音朗读功能 ─────────────────────────────────────────
    
    def _toggle_tts(self, checked: bool):
        """切换 TTS 语音朗读开关"""
        if checked:
            if not TTS_AVAILABLE:
                self._add_message('assistant', '⚠️ TTS 语音库未安装，请运行：pip install edge-tts')
                self.tts_btn.setChecked(False)
                return
            self.tts_btn.setText('🔇')
            self.tts_btn.setToolTip('语音朗读（已开启，点击关闭）')
            self._add_message('assistant', '🔊 语音朗读已开启，我将朗读回复。')
        else:
            self.tts_btn.setText('🔊')
            self.tts_btn.setToolTip('语音朗读（点击开启/关闭）')
            self._add_message('assistant', '🔇 语音朗读已关闭。')
    
    def _speak_text(self, text: str):
        """语音朗读文本（在线程中执行，避免阻塞 UI）"""
        if not TTS_AVAILABLE or not _tts_adapter:
            return
        import threading
        import re
        def _worker():
            try:
                import tempfile
                from PySide6.QtCore import QMetaObject, Qt
                # 清理文本（去掉 emoji 和特殊符号）
                clean = re.sub(r'[^\\u4e00-\\u9fff\\u3000-\\u303f\\uff00-\\uffef\\w\\s,.!?;:，。！？；：]', '', text)
                clean = clean[:200]  # 限制长度
                if not clean.strip():
                    return
                with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
                    tmp_path = f.name
                result = _tts_adapter.synthesize_sync(clean, output_path=tmp_path)
                if result.success:
                    QMetaObject.invokeMethod(
                        self, '_on_tts_audio_ready',
                        Qt.ConnectionType.QueuedConnection,
                        QMetaObject.Qt_string(tmp_path)
                    )
            except Exception as e:
                logger.error(f'[TTS] 朗读失败: {e}')
        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
    
    @Slot(str)
    def _on_tts_audio_ready(self, audio_path: str):
        """TTS 音频就绪，播放音频"""
        try:
            from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
            from PySide6.QtCore import QUrl, QTimer
            if not hasattr(self, '_tts_player'):
                self._tts_player = QMediaPlayer()
                self._tts_audio_output = QAudioOutput()
                self._tts_player.setAudioOutput(self._tts_audio_output)
            self._tts_player.stop()
            self._tts_player.setSource(QUrl.fromLocalFile(audio_path))
            self._tts_player.play()
            # 5秒后清理临时文件
            QTimer.singleShot(5000, lambda: self._cleanup_tts_file(audio_path))
        except Exception as e:
            logger.error(f'[TTS] 播放失败: {e}')
    
    def _cleanup_tts_file(self, path: str):
        """清理 TTS 临时音频文件"""
        try:
            import os
            os.unlink(path)
        except:
            pass
'''
        result.append(tts_methods)
        continue
    
    # 默认：添加当前行
    result.append(line)
    i += 1

# 写回文件
with open(FILE, 'w', encoding='utf-8') as f:
    f.write(''.join(result))

print('[OK] TTS 功能已成功添加到 ei_wizard_chat.py')
print('[INFO] 修改内容：')
print('  1. TTS 导入检测（模块顶部）')
print('  2. TTS 按钮（输入栏，voice_btn 后面）')
print('  3. TTS 调用（_add_message 助手分支）')
print('  4. TTS 方法（_toggle_tts, _speak_text, _on_tts_audio_ready, _cleanup_tts_file）')
