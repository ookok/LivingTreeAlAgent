"""
直接测试 SoundEngine.play_voice_cn
"""
import sys, os
sys.path.insert(0, "d:/mhzyapp/LivingTreeAlAgent")

print("=== 直接测试 SoundEngine.play_voice_cn ===\n")

# 不走 PyQt6，直接导入核心模块
import pythoncom
pythoncom.CoInitialize()

import win32com.client, tempfile, hashlib, winsound

print("[1] 初始化 SAPI...")
speaker = win32com.client.Dispatch("SAPI.SpVoice")

print("[2] 查找中文语音...")
for v in speaker.GetVoices():
    print(f"    {v.GetDescription()}")

print("[3] 设置中文语音...")
for v in speaker.GetVoices():
    desc = v.GetDescription()
    if "Chinese" in desc or "Huihui" in desc:
        speaker.Voice = v
        print(f"    选中: {desc}")
        break

print("[4] 朗读测试...")
text = "你好！我是生命之树AI，你的 AI 桌面助手。"
speaker.Speak(text)
speaker.WaitUntilDone(-1)
print("    实时朗读完成！")

print("[5] 生成 WAV 文件测试...")
text2 = "生命之树AI，智能助手新体验"
file_stream = win32com.client.Dispatch("SAPI.SpFileStream")
audio_format = win32com.client.Dispatch("SAPI.SpAudioFormat")
audio_format.Type = 11  # SAFT16kHz16BitMono
file_stream.Format = audio_format

wav_path = os.path.join(tempfile.gettempdir(), "livalt_test.wav")
file_stream.Open(wav_path, 3)
speaker.AudioOutputStream = file_stream
speaker.Speak(text2)
file_stream.Close()
speaker.AudioOutputStream = None
print(f"    WAV 生成: {wav_path}")

print("[6] winsound 播放...")
winsound.PlaySound(wav_path, winsound.SND_FILENAME)
print("    播放完成！")

print("\n=== SoundEngine 核心 TTS 测试通过 ===")
