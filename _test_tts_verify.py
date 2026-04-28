# -*- coding: utf-8 -*-
"""TTS 验证测试 - 检查 pywin32 + SAPI 是否正常"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def test_tts():
    print("=" * 50)
    print("TTS 验证测试")
    print("=" * 50)

    # 1. 检查 pywin32
    print("\n[1] pywin32 检查...")
    try:
        import win32com.client
        print("  [OK] win32com.client 可导入")
    except ImportError as e:
        print(f"  [FAIL] 无法导入: {e}")
        return

    # 2. 检查 COM 组件
    print("\n[2] SAPI SpVoice 检查...")
    try:
        import pythoncom
        pythoncom.CoInitialize()
        print("  [OK] COM 初始化成功")
    except Exception as e:
        print(f"  [FAIL] COM 初始化失败: {e}")
        return

    # 3. 创建语音合成器
    print("\n[3] 创建 SpVoice 对象...")
    try:
        speaker = win32com.client.Dispatch("SAPI.SpVoice")
        print("  [OK] SpVoice 创建成功")
    except Exception as e:
        print(f"  [FAIL] 无法创建 SpVoice: {e}")
        return

    # 4. 获取可用语音
    print("\n[4] 获取可用语音...")
    try:
        voices = speaker.GetVoices()
        print(f"  语音数量: {voices.Count}")
        for v in voices:
            desc = v.GetDescription()
            print(f"  - {desc}")
    except Exception as e:
        print(f"  [WARN] 获取语音列表失败: {e}")

    # 5. 尝试朗读（简短测试）
    print("\n[5] 朗读测试...")
    test_text = "TTS 语音合成测试。如果你能听到这段话，说明语音引擎工作正常。"
    print(f"  朗读内容: {test_text[:20]}...")
    try:
        # 同步朗读（不设置 SPF_IS_FILENAME 标志）
        # 使用 WaitUntilDone 等待完成
        speaker.Speak(test_text)
        print("  [OK] Speak 已调用（同步等待中...）")
        # 注意：在非交互环境可能无法听到声音，但 API 调用应该成功
        print("  [OK] 朗读完成")
    except Exception as e:
        print(f"  [FAIL] Speak 失败: {e}")

    print("\n[OK] TTS 验证完成")

if __name__ == "__main__":
    test_tts()
