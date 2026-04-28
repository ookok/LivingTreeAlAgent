# -*- coding: utf-8 -*-
"""TTS 直接测试 - 验证 Windows SAPI 是否正常工作"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import pythoncom
import win32com.client

def test_tts():
    print("=" * 50)
    print("TTS 直接测试")
    print("=" * 50)

    # 初始化 COM
    pythoncom.CoInitialize()
    print("[OK] COM initialized")

    # 创建语音合成器
    speaker = win32com.client.Dispatch("SAPI.SpVoice")
    print("[OK] SpVoice created")

    # 获取可用语音列表
    voices = speaker.GetVoices()
    print(f"\n可用语音 ({voices.Count} 个):")
    for v in voices:
        print(f"  - {v.GetDescription()}")

    # 测试朗读 - 中文
    print("\n--- 测试朗读 ---")
    test_text = "你好，这是 Windows SAPI 语音合成测试。如果你能听到这段话，说明TTS工作正常。"
    print(f"朗读内容: {test_text[:30]}...")

    try:
        # Speak 是异步的，会立即返回
        # 我们使用 WaitUntilDone 来等待完成
        speaker.Speak(test_text, 1)  # 1 = SVSFlagsAsync
        print("[OK] Speak async started")
        # 等待完成
        speaker.WaitUntilDone(-1)  # -1 = 无限等待
        print("[OK] Speak completed")
    except Exception as e:
        print(f"[ERROR] Speak failed: {e}")

    print("\n[OK] TTS 测试完成")

if __name__ == "__main__":
    test_tts()
