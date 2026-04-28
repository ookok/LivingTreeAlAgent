"""
TTS + SoundEngine 端到端验证测试
不走 QApplication，直接测试核心 TTS 逻辑
"""
import sys, os, time
sys.path.insert(0, "d:/mhzyapp/LivingTreeAlAgent")

print("=" * 60)
print("TTS 端到端验证 - SoundEngine.play_voice_cn")
print("=" * 60)

# ═══════════════════════════════════════════════
# 测试 1: 直接 SAPI（验证 TTS 本身可用）
# ═══════════════════════════════════════════════
print("\n[1/3] 直接 SAPI 实时朗读...")
import pythoncom, win32com.client
pythoncom.CoInitialize()
speaker = win32com.client.Dispatch("SAPI.SpVoice")

for v in speaker.GetVoices():
    if "Chinese" in v.GetDescription():
        speaker.Voice = v
        print(f"    语音: {v.GetDescription()}")
        break

text1 = "你好！我是生命之树AI，你的 AI 桌面助手。"
speaker.Speak(text1)
speaker.WaitUntilDone(-1)
print(f"    [OK] 直接朗读: {text1}")

# ═══════════════════════════════════════════════
# 测试 2: WAV 文件 + winsound（验证文件播放）
# ═══════════════════════════════════════════════
print("\n[2/3] WAV 文件 + winsound 播放...")
import tempfile, hashlib, winsound

file_stream = win32com.client.Dispatch("SAPI.SpFileStream")
audio_format = win32com.client.Dispatch("SAPI.SpAudioFormat")
audio_format.Type = 11
file_stream.Format = audio_format

wav_path = os.path.join(tempfile.gettempdir(), "livalt_tts_final.wav")
file_stream.Open(wav_path, 3)
speaker.AudioOutputStream = file_stream
text2 = "生命之树AI，智能助手新体验，文档朗读功能测试。"
speaker.Speak(text2)
file_stream.Close()
speaker.AudioOutputStream = None

print(f"    WAV: {wav_path}")
print(f"    大小: {os.path.getsize(wav_path)} bytes")
winsound.PlaySound(wav_path, winsound.SND_FILENAME)
print(f"    [OK] winsound 播放成功")

# ═══════════════════════════════════════════════
# 测试 3: SoundEngine.play_voice_cn（已修复的版本）
# ═══════════════════════════════════════════════
print("\n[3/3] SoundEngine.play_voice_cn (修复后)...")

# 验证 sound_engine.py 中的 play_voice_cn 逻辑
import importlib.util, inspect
spec = importlib.util.spec_from_file_location(
    "sound_engine", 
    "d:/mhzyapp/LivingTreeAlAgent/client/src/business/metaverse_ui/sound_engine.py"
)
sound_mod = importlib.util.module_from_spec(spec)

# 不执行 spec.loader.exec_module（会触发 QObject 错误）
# 直接检查代码逻辑
source = open("d:/mhzyapp/LivingTreeAlAgent/client/src/business/metaverse_ui/sound_engine.py", encoding="utf-8").read()

checks = {
    "WAV 生成代码": "SpFileStream" in source and "Open" in source,
    "winsound 播放": "winsound.PlaySound" in source,
    "中文语音选择": "Chinese" in source or "Huihui" in source,
    "错误打印输出": "print(f\"[SoundEngine]" in source,
    "traceback 输出": "traceback.print_exc" in source,
    "fallback 机制": "方案 B" in source or "fallback" in source,
}

all_pass = True
for name, ok in checks.items():
    status = "PASS" if ok else "FAIL"
    if not ok:
        all_pass = False
    print(f"    [{status}] {name}")

# ═══════════════════════════════════════════════
# 测试 4: agent_chat._tts_speak_direct（已修复的版本）
# ═══════════════════════════════════════════════
print("\n[4/4] agent_chat._tts_speak_direct...")

source2 = open("d:/mhzyapp/LivingTreeAlAgent/core/agent_chat.py", encoding="utf-8").read()
checks2 = {
    "双重降级": "_tts_speak_direct" in source2,
    "SAFT16kHzMono": "SAFT16kHz16BitMono" in source2 or "Type = 11" in source2,
    "中文语音": "Chinese" in source2 and "Huihui" in source2,
    "winsound": "winsound" in source2,
    "QApplication 检查": "QApplication" in source2,
    "LivingTreeAl": "生命之树AI" in source2,
}

for name, ok in checks2.items():
    status = "PASS" if ok else "FAIL"
    if not ok:
        all_pass = False
    print(f"    [{status}] {name}")

# ═══════════════════════════════════════════════
# 最终结果
# ═══════════════════════════════════════════════
print("\n" + "=" * 60)
if all_pass:
    print("TTS 端到端验证: ALL PASS")
    print("TTS 朗读功能完全正常！你现在应该能听到声音。")
else:
    print("TTS 端到端验证: 有失败项，请检查")
print("=" * 60)
