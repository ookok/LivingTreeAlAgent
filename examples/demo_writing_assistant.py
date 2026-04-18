"""
写作助手演示脚本
演示本地/远程模型切换和写作功能
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_remote_api():
    """测试远程 API（不需要本地模型）"""
    print("=" * 60)
    print("测试 1: 远程 API 模式")
    print("=" * 60)

    try:
        from core.writing_assistant import WritingAssistant

        assistant = WritingAssistant(
            use_local=False,
            remote_api_url="https://api.deepseek.com/v1",
            remote_api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
            remote_model="deepseek-chat",
        )

        print("\n✅ 远程 API 连接成功")
        print("\n测试生成功能:")
        result = assistant.generate_text(
            prompt="请写一段武侠小说的开篇，主角是一个隐居的剑客",
            style="novel",
            max_tokens=256,
        )
        print(f"生成结果:\n{result[:200]}...")

        return True

    except Exception as e:
        print(f"❌ 远程 API 测试失败: {e}")
        return False


def test_local_model():
    """测试本地模型"""
    print("\n" + "=" * 60)
    print("测试 2: 本地模型模式")
    print("=" * 60)

    try:
        from core.writing_assistant import WritingAssistant

        assistant = WritingAssistant(
            use_local=True,
            n_ctx=8192,
            n_threads=12,
        )

        print("\n✅ 本地模型加载成功")
        print("\n测试润色功能:")
        sample = "他走进房间，看到桌子上有一封信。他打开信，看到里面的内容，很惊讶。"
        polished = assistant.polish_text(sample, style="elegant")
        print(f"原文: {sample}")
        print(f"润色后: {polished}")

        return True

    except Exception as e:
        print(f"❌ 本地模型测试失败: {e}")
        print("提示: 请确保已安装 llama-cpp-python 并下载 GGUF 模型")
        return False


def test_batch_processing():
    """测试批量处理"""
    print("\n" + "=" * 60)
    print("测试 3: 批量处理模式")
    print("=" * 60)

    try:
        from core.writing_assistant import WritingAssistant

        assistant = WritingAssistant(use_local=False)

        tasks = [
            {
                "type": "polish",
                "params": {
                    "text": "今天的天气很好，阳光明媚，适合出门散步。",
                    "style": "elegant",
                }
            },
            {
                "type": "generate",
                "params": {
                    "prompt": "描述一个雨夜的街道场景",
                    "style": "poetic",
                    "max_tokens": 256,
                }
            },
        ]

        results = assistant.batch_process(tasks)

        print("\n批量处理结果:")
        for i, result in enumerate(results):
            print(f"\n--- 任务 {i + 1} ---")
            print(result)

        return True

    except Exception as e:
        print(f"❌ 批量处理测试失败: {e}")
        return False


def test_remote_client_presets():
    """测试远程客户端预设"""
    print("\n" + "=" * 60)
    print("测试 4: 远程客户端预设")
    print("=" * 60)

    try:
        from core.remote_api_client import create_client_from_preset, PROVIDER_PRESETS

        print("\n可用预设:")
        for name in PROVIDER_PRESETS:
            config = PROVIDER_PRESETS[name]
            print(f"  - {name}: {config['model']} @ {config['api_url']}")

        return True

    except Exception as e:
        print(f"❌ 预设测试失败: {e}")
        return False


def main():
    print("🤖 Hermes Desktop - 写作助手演示")
    print("=" * 60)
    print()

    results = []

    # 测试远程 API（推荐，首先测试）
    results.append(("远程 API", test_remote_api()))

    # 测试本地模型（可选，需要安装 llama-cpp-python）
    print("\n是否测试本地模型? (需要 llama-cpp-python 和 GGUF 模型)")
    results.append(("本地模型", test_local_model()))

    # 测试批量处理
    results.append(("批量处理", test_batch_processing()))

    # 测试预设
    results.append(("预设配置", test_remote_client_presets()))

    # 总结
    print("\n" + "=" * 60)
    print("📊 测试结果总结")
    print("=" * 60)

    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {name}: {status}")

    passed_count = sum(1 for _, p in results if p)
    print(f"\n通过率: {passed_count}/{len(results)}")


if __name__ == "__main__":
    main()
