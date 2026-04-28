"""
TTS 语音文件生成测试 - 验证 Windows SAPI 是否能生成 WAV 文件
"""
import os, sys, traceback

print("=== TTS WAV 文件生成测试 ===\n")

try:
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()

    speaker = win32com.client.Dispatch("SAPI.SpVoice")

    # 1. 列出可用语音
    voices = speaker.GetVoices()
    print(f"[1] 系统可用语音 ({voices.Count} 个):")
    for v in voices:
        print(f"    - {v.GetDescription()}")

    # 2. 选中中文语音
    cn_voice = None
    for v in voices:
        desc = v.GetDescription()
        if "Chinese" in desc or "Huihui" in desc:
            cn_voice = v
            break

    if cn_voice:
        speaker.Voice = cn_voice
        print(f"\n[2] 选中中文语音: {cn_voice.GetDescription()}")
    else:
        print("\n[2] 未找到中文语音，使用默认")

    # 3. 生成 WAV 文件（SAPI 16kHz 16bit 单声道）
    wav_path = "d:/mhzyapp/LivingTreeAlAgent/_tts_test_output.wav"
    if os.path.exists(wav_path):
        os.remove(wav_path)

    # 创建文件流
    file_stream = win32com.client.Dispatch("SAPI.SpFileStream")
    audio_format = win32com.client.Dispatch("SAPI.SpAudioFormat")

    # 设置格式：16kHz 16bit 单声道 (SAPI 枚举值)
    # 11 = SAFT16kHz16BitMono
    audio_format.Type = 11
    file_stream.Format = audio_format
    file_stream.Open(wav_path, 3)  # 3 = SSFMCreateForWrite

    # 将语音输出定向到文件流
    speaker.AudioOutputStream = file_stream

    # 朗读文本
    test_text = "你好！我是生命之树AI，你的 AI 桌面助手。"
    print(f"\n[3] 生成 WAV 文件: {wav_path}")
    print(f"    朗读文本: {test_text}")
    speaker.Speak(test_text)

    # 关闭流
    file_stream.Close()
    speaker.AudioOutputStream = None

    # 4. 验证文件
    if os.path.exists(wav_path):
        size = os.path.getsize(wav_path)
        print(f"\n[4] WAV 文件生成成功!")
        print(f"    文件大小: {size} bytes ({size/1024:.1f} KB)")

        # 读取并检查 WAV 头
        with open(wav_path, "rb") as f:
            header = f.read(44)
            if header[:4] == b"RIFF" and header[8:12] == b"WAVE":
                print(f"    WAV 头验证: OK (RIFF/WAVE)")
            else:
                print(f"    WAV 头验证: FAIL")
                print(f"    Header hex: {header[:16].hex()}")
    else:
        print(f"\n[4] 文件生成失败!")

    print("\n=== 测试完成 ===")

except Exception as e:
    print(f"ERROR: {e}")
    traceback.print_exc()
