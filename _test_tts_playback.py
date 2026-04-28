"""验证并播放生成的 WAV 文件"""
import os, wave, struct, sys

wav_path = "d:/mhzyapp/LivingTreeAlAgent/_tts_test_output.wav"

if not os.path.exists(wav_path):
    print(f"文件不存在: {wav_path}")
    sys.exit(1)

size = os.path.getsize(wav_path)
print(f"WAV 文件验证: {wav_path}")
print(f"文件大小: {size} bytes ({size/1024:.1f} KB)")

with open(wav_path, "rb") as f:
    header = f.read(44)
    print(f"RIFF: {header[0:4]}")
    print(f"WAVE: {header[8:12]}")

    # 读取 wav 参数
    with wave.open(wav_path, "rb") as w:
        channels = w.getnchannels()
        sampwidth = w.getsampwidth()
        framerate = w.getframerate()
        nframes = w.getnframes()
        duration = nframes / framerate
        print(f"声道数: {channels} (1=单声道, 2=立体声)")
        print(f"采样位宽: {sampwidth * 8} bit")
        print(f"采样率: {framerate} Hz")
        print(f"帧数: {nframes}")
        print(f"时长: {duration:.2f} 秒")

print("\n尝试用 Python 播放...")
try:
    import winsound
    winsound.PlaySound(wav_path, winsound.SND_FILENAME)
    print("播放完毕!")
except Exception as e:
    print(f"winsound 播放失败: {e}")
    print("WAV 文件已生成，可手动打开验证")
