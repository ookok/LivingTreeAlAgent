"""
声音引擎 - Sound Engine
舰桥操作系统音效和语音反馈
"""

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtMultimedia import QSoundEffect
from PyQt6.QtCore import QUrl
import os
import hashlib

# 尝试导入pywin32用于Windows语音
try:
    import win32com.client
    import pythoncom
    _HAS_WIN_SPEAK = True
except ImportError:
    _HAS_WIN_SPEAK = False


# ═══════════════════════════════════════════════════════════════════════════════
# 内置音效生成
# ═══════════════════════════════════════════════════════════════════════════════

def _generate_beep(frequency: int = 800, duration: int = 100, volume: float = 0.3) -> bytes:
    """生成简单的蜂鸣音效 (WAV格式)"""
    import struct
    import wave
    import io
    
    sample_rate = 44100
    n_samples = int(sample_rate * duration / 1000)
    
    # 生成正弦波
    samples = []
    for i in range(n_samples):
        t = i / sample_rate
        # 淡入淡出
        envelope = min(1.0, min(i / 1000, (n_samples - i) / 1000))
        value = int(32767 * volume * envelope * (i % 100 < 50))  # 方波
        samples.append(struct.pack('<h', value))
    
    # 写入WAV
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(b''.join(samples))
    
    return buffer.getvalue()


# ═══════════════════════════════════════════════════════════════════════════════
# 音效定义
# ═══════════════════════════════════════════════════════════════════════════════

class SoundEffects:
    """内置音效"""
    
    # 基础音效 (频率, 时长ms, 音量)
    BOOT = (440, 200, 0.2)         # 启动
    SHUTDOWN = (330, 300, 0.2)     # 关闭
    ENGAGE = (880, 150, 0.3)       # 进入
    DISENGAGE = (660, 150, 0.3)    # 退出
    NAVIGATE = (523, 100, 0.2)     # 导航
    ALERT = (1000, 200, 0.4)       # 警告
    SUCCESS = (880, 100, 0.3)      # 成功
    ERROR = (200, 300, 0.4)        # 错误
    SCAN = (660, 150, 0.2)         # 扫描
    MESSAGE = (1200, 80, 0.15)     # 消息
    TRADE = (1000, 100, 0.3)       # 交易
    COIN = (2000, 50, 0.2)          # 金币
    PULSE = (440, 50, 0.1)         # 脉冲


# ═══════════════════════════════════════════════════════════════════════════════
# 声音引擎
# ═══════════════════════════════════════════════════════════════════════════════

class SoundEngine(QObject):
    """
    声音引擎
    提供舰桥操作系统的音效和语音反馈
    """
    
    # 信号
    sound_played = pyqtSignal(str)  # 音效名称
    voice_finished = pyqtSignal()   # 语音结束
    
    def __init__(self, enabled: bool = True):
        super().__init__()
        self._enabled = enabled
        self._volume = 0.5
        self._muted = False
        
        # 音效缓存
        self._effect_cache = {}
        
        # Windows语音
        self._speaker = None
        if _HAS_WIN_SPEAK:
            try:
                pythoncom.CoInitialize()
                self._speaker = win32com.client.Dispatch("SAPI.SpVoice")
            except Exception:
                self._speaker = None
    
    @property
    def enabled(self) -> bool:
        return self._enabled
    
    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value
    
    @property
    def volume(self) -> float:
        return self._volume
    
    @volume.setter
    def volume(self, value: float):
        self._volume = max(0, min(1, value))
    
    def play_sound(self, sound_name: str):
        """
        播放音效
        
        Args:
            sound_name: 音效名称
                - boot: 启动
                - shutdown: 关闭
                - engage: 进入
                - disengage: 退出
                - navigate: 导航
                - alert: 警告
                - success: 成功
                - error: 错误
                - scan: 扫描
                - message: 消息
                - trade: 交易
                - coin: 金币
                - pulse: 脉冲
        """
        if not self._enabled or self._muted:
            return
        
        # 获取音效参数
        sound_map = {
            "boot": SoundEffects.BOOT,
            "shutdown": SoundEffects.SHUTDOWN,
            "engage": SoundEffects.ENGAGE,
            "disengage": SoundEffects.DISENGAGE,
            "navigate": SoundEffects.NAVIGATE,
            "alert": SoundEffects.ALERT,
            "success": SoundEffects.SUCCESS,
            "error": SoundEffects.ERROR,
            "scan": SoundEffects.SCAN,
            "message": SoundEffects.MESSAGE,
            "trade": SoundEffects.TRADE,
            "coin": SoundEffects.COIN,
            "pulse": SoundEffects.PULSE,
        }
        
        params = sound_map.get(sound_name, SoundEffects.PULSE)
        frequency, duration, vol = params
        
        # 使用系统蜂鸣
        try:
            import winsound
            winsound.Beep(int(frequency), duration)
            self.sound_played.emit(sound_name)
        except Exception:
            # 备用：静默忽略
            pass
    
    def play_voice(self, text: str, rate: int = 0):
        """
        播放语音
        
        Args:
            text: 要朗读的文本
            rate: 语速 (-10 到 10)
        """
        if not self._enabled or self._muted:
            return

        # 尝试直接朗读
        if self._speaker:
            try:
                if hasattr(self._speaker, "Rate"):
                    self._speaker.Rate = max(-10, min(10, rate))
                self._speaker.Speak(text, 1)
                self._speaker.WaitUntilDone(-1)
                self.voice_finished.emit()
                return
            except Exception:
                pass

        # 回退到 winsound（需要先有 WAV 文件）
        try:
            import winsound, tempfile, os, hashlib
            txt_hash = hashlib.md5(text.encode("utf-8")).hexdigest()[:8]
            wav_path = os.path.join(tempfile.gettempdir(), f"lt_tts_{txt_hash}.wav")
            if os.path.exists(wav_path):
                winsound.PlaySound(wav_path, winsound.SND_FILENAME)
                self.voice_finished.emit()
        except Exception:
            pass
    
    def play_voice_cn(self, text: str):
        """
        播放中文语音 - Windows SAPI
        策略：直接 Speak（实时播放）失败则用 WAV 文件落地 + winsound 播放
        """
        if not self._enabled or self._muted:
            return

        # 方案 A：直接实时朗读（失败则走方案 B）
        if self._speaker:
            try:
                speaker = win32com.client.Dispatch("SAPI.SpVoice")
                # 查找中文语音
                for voice in speaker.GetVoices():
                    desc = voice.GetDescription()
                    if "Chinese" in desc or "Huihui" in desc:
                        speaker.Voice = voice
                        break
                speaker.Speak(text, 1)  # 1 = SVSFAsync
                # 等待朗读完成
                speaker.WaitUntilDone(-1)
                self.voice_finished.emit()
                return
            except Exception as e:
                print(f"[SoundEngine] 直接朗读失败: {e}，尝试 WAV 文件方案")

        # 方案 B：生成 WAV 文件 + winsound 播放（最可靠）
        try:
            import tempfile, os as _os

            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            file_stream = win32com.client.Dispatch("SAPI.SpFileStream")
            audio_format = win32com.client.Dispatch("SAPI.SpAudioFormat")

            # 16kHz 16bit 单声道（中文语音优化）
            audio_format.Type = 11  # SAFT16kHz16BitMono
            file_stream.Format = audio_format

            # 生成临时文件
            temp_dir = tempfile.gettempdir()
            # 用文本 hash 确保不同内容不同文件
            import hashlib
            txt_hash = hashlib.md5(text.encode("utf-8")).hexdigest()[:8]
            wav_path = _os.path.join(temp_dir, f"lt_tts_{txt_hash}.wav")

            file_stream.Open(wav_path, 3)  # SSFMCreateForWrite
            speaker.AudioOutputStream = file_stream

            # 选中中文语音
            for voice in speaker.GetVoices():
                desc = voice.GetDescription()
                if "Chinese" in desc or "Huihui" in desc:
                    speaker.Voice = voice
                    break

            speaker.Speak(text)
            file_stream.Close()
            speaker.AudioOutputStream = None

            # winsound 播放（最可靠，不依赖 COM 线程模型）
            import winsound
            winsound.PlaySound(wav_path, winsound.SND_FILENAME)

            self.voice_finished.emit()
        except Exception as e:
            print(f"[SoundEngine] WAV 方案也失败: {e}")
            import traceback
            traceback.print_exc()
    
    def mute(self):
        """静音"""
        self._muted = True
    
    def unmute(self):
        """取消静音"""
        self._muted = False
    
    def toggle_mute(self) -> bool:
        """切换静音状态"""
        self._muted = not self._muted
        return self._muted


# ═══════════════════════════════════════════════════════════════════════════════
# 叙事台词 - 生命之树版本
# ═══════════════════════════════════════════════════════════════════════════════

class NarrativeLines:
    """🌳 生命之树叙事台词"""

    # 启动
    BOOT_LINES = [
        "生命之树正在苏醒...",
        "根系开始向远方延伸...",
        "林间的光芒正在唤醒",
    ]

    # 欢迎
    WELCOME_LINES = [
        "欢迎回来，旅人。林间交易的风已经开始流动，发现 {count} 个潜在信号。",
        "您好，森林旅人。当前根系状态良好，{nodes} 个共生伙伴在线。",
        "检测到新活动，{count} 条消息等待。信使叶灵随时待命。",
    ]

    # 交易
    TRADE_LINES = [
        "新的果实成熟了，等待交换...",
        "风媒牵线成功，发现潜在的交易伙伴...",
        "落叶归根，交易达成，年轮烙印已更新",
    ]

    # 嫁接/装配
    GRAFT_LINES = [
        "根系装配园开启，开始搜寻良种...",
        "嫁接过程开始，新苗正在扎根...",
        "嫁接成功，新能力已在林间绽放",
    ]

    # 警告
    WARNING_LINES = [
        "林间起了风浪，请注意...",
        "根系信号波动，连接可能不稳定",
        "有新消息如晨露般降临",
    ]

    # 成功
    SUCCESS_LINES = [
        "能量在枝干中流动，一切就绪",
        "新的共生连接已建立",
        "雨露渗透成功，知识已融入沃土",
    ]

    @classmethod
    def get_welcome_line(cls, count: int = 0, nodes: int = 0) -> str:
        """获取欢迎台词"""
        import random
        line = random.choice(cls.WELCOME_LINES)
        return line.format(count=count, nodes=nodes)

    @classmethod
    def get_trade_line(cls) -> str:
        """获取交易台词"""
        import random
        return random.choice(cls.TRADE_LINES)

    @classmethod
    def get_boot_line(cls) -> str:
        """获取启动台词"""
        import random
        return random.choice(cls.BOOT_LINES)

    @classmethod
    def get_graft_line(cls) -> str:
        """获取嫁接台词"""
        import random
        return random.choice(cls.GRAFT_LINES)


# ═══════════════════════════════════════════════════════════════════════════════
# 单例
# ═══════════════════════════════════════════════════════════════════════════════

_sound_engine_instance = None

def get_sound_engine() -> SoundEngine:
    """获取声音引擎单例"""
    global _sound_engine_instance
    if _sound_engine_instance is None:
        _sound_engine_instance = SoundEngine()
    return _sound_engine_instance


def create_sound_engine(enabled: bool = True) -> SoundEngine:
    """创建新的声音引擎"""
    global _sound_engine_instance
    _sound_engine_instance = SoundEngine(enabled)
    return _sound_engine_instance
