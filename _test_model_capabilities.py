"""
模型能力检测测试
================

测试内容：
1. 模式匹配检测
2. Ollama API 检测
3. 多模态内容过滤
4. thinking 模式运行时检测
"""

import time
import sys
sys.path.insert(0, ".")

from core.model_capabilities import (
    ModelCapabilityDetector,
    MultimodalMessageFilter,
    get_capability_detector,
    generate_capability_hint,
    ThinkingCapability,
    MultimodalCapability,
    ModelCapabilities,
)


def test_pattern_detection():
    """测试 1: 模式匹配检测"""
    print("\n" + "=" * 60)
    print("【测试1】模式匹配检测")
    print("=" * 60)
    
    detector = ModelCapabilityDetector()
    
    # 测试各种模型名称
    test_models = [
        # 思考模型
        ("qwen3.6:35b-a3b", True, "qwen3.6 思考模型"),
        ("qwen3.5:4b", True, "qwen3.5 思考模型"),
        ("deepseek-r1:70b", True, "DeepSeek 思考模型"),
        ("qwen3.5:9b", True, "Qwen3.5 9B"),
        
        # 非思考模型
        ("qwen2.5:1.5b", False, "Qwen2.5 普通模型"),
        ("qwen2.5:0.5b", False, "Qwen2.5 最小模型"),
        ("llama3:8b", False, "Llama3 普通模型"),
        ("gemma3:4b", False, "Gemma3 普通模型"),
        ("smollm2:latest", False, "SmolLM2 轻量模型"),
        
        # 多模态模型（thinking 可能不支持）
        ("llava:latest", None, "LLaVA 视觉模型"),  # None 表示不检查 thinking
        ("qwen2.5-vl:7b", None, "Qwen2.5-VL 视觉模型"),
        ("qwen2.5-omni:7b", None, "Qwen2.5-Omni 全能模型"),
        ("whisper:latest", None, "Whisper 音频模型"),
        
        # 通用
        ("gpt-4", False, "GPT-4 (外部 API)"),
        ("claude-3-sonnet", False, "Claude 3 (外部 API)"),
    ]
    
    print()
    print(f"{'模型名称':<25} {'Thinking':<12} {'多模态':<15} {'描述'}")
    print("-" * 70)
    
    all_passed = True
    for model_name, expected_thinking, desc in test_models:
        caps = detector.detect(model_name)
        
        # 检查 thinking
        has_thinking = caps.can_think()
        # expected_thinking=None 表示不检查 thinking
        thinking_ok = expected_thinking is None or has_thinking == expected_thinking
        
        # 检查多模态（如果有）
        multimodal_str = caps.multimodal.value
        if isinstance(expected_thinking, str):
            multi_ok = caps.multimodal.value == expected_thinking
        else:
            multi_ok = True
        
        status = "[OK]" if (thinking_ok and multi_ok) else "[FAIL]"
        if not (thinking_ok and multi_ok):
            all_passed = False
        
        print(f"{model_name:<25} {str(has_thinking):<12} {multimodal_str:<15} {status} {desc}")
    
    print()
    if all_passed:
        print("[OK] All pattern matching tests passed!")
    else:
        print("[FAIL] Some tests failed!")
    
    return all_passed


def test_api_detection():
    """测试 2: Ollama API 检测"""
    print("\n" + "=" * 60)
    print("【测试2】Ollama API 检测")
    print("=" * 60)
    
    detector = ModelCapabilityDetector()
    
    # 获取本地 Ollama 模型
    import subprocess
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            print("[WARN] Cannot get Ollama model list")
            return False
        
        models = []
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("NAME") or line.startswith("-"):
                continue
            name = line.split()[0]
            if name:
                models.append(name)
        
        print(f"\n检测到 {len(models)} 个 Ollama 模型：")
        print("-" * 70)
        
        for model_name in models[:10]:  # 最多显示 10 个
            caps = detector.detect(model_name)
            hint = generate_capability_hint(caps)
            source_tag = {"pattern": "[P]", "api": "[A]", "default": "[D]"}.get(caps.source, "?")
            print(f"{source_tag} {model_name:<30} {hint}")
        
        if len(models) > 10:
            print(f"... 还有 {len(models) - 10} 个模型")
        
        return True
        
    except Exception as e:
        print(f"[WARN] Ollama API detection skipped: {e}")
        return False


def test_multimodal_filter():
    """测试 3: 多模态内容过滤"""
    print("\n" + "=" * 60)
    print("【测试3】多模态消息过滤")
    print("=" * 60)
    
    detector = ModelCapabilityDetector()
    filter = MultimodalMessageFilter(detector)
    
    # 测试消息
    test_messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "分析这张图片"},
                {"type": "image_url", "url": "https://example.com/image.jpg"},
            ]
        },
        {
            "role": "user", 
            "content": "这是一个纯文本问题"
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "听这段音频"},
                {"type": "audio_url", "url": "https://example.com/audio.mp3"},
            ]
        },
    ]
    
    test_cases = [
        ("qwen2.5:1.5b", "纯文本模型"),
        ("llava:latest", "视觉模型"),
        ("qwen2.5-omni:7b", "全能模型"),
    ]
    
    print()
    for model_name, desc in test_cases:
        print(f"\n[M] {model_name} ({desc})")
        print("-" * 50)
        
        filtered, removed = filter.filter_messages(model_name, test_messages)
        
        for i, (orig, filt) in enumerate(zip(test_messages, filtered)):
            print(f"  消息 {i+1}:")
            
            # 显示原始内容
            orig_content = orig["content"]
            if isinstance(orig_content, list):
                types = [c.get("type", "?") for c in orig_content]
                print(f"    原始: {types}")
            else:
                print(f"    原始: text")
            
            # 显示过滤后
            filt_content = filt["content"]
            if isinstance(filt_content, list):
                types = [c.get("type", "?") for c in filt_content]
                print(f"    过滤后: {types}")
            else:
                print(f"    过滤后: text")
        
        if removed:
            print(f"  [WARN] Filtered: {', '.join(removed)}")
        else:
            print(f"  [OK] No content filtered")
    
    return True


def test_capability_summary():
    """测试 4: 能力摘要生成"""
    print("\n" + "=" * 60)
    print("【测试4】能力摘要生成")
    print("=" * 60)
    
    detector = ModelCapabilityDetector()
    
    test_models = [
        "qwen3.6:35b-a3b",
        "qwen2.5:1.5b",
        "llava:latest",
        "qwen2.5-omni:7b",
    ]
    
    print()
    for model_name in test_models:
        caps = detector.detect(model_name)
        summary = caps.get_capability_summary()
        print(f"[S] {model_name}")
        print(f"   {summary}")
        
        # 详细能力
        print(f"   - can_think(): {caps.can_think()}")
        print(f"   - can_stream_think(): {caps.can_stream_think()}")
        print(f"   - supports_image(): {caps.supports_image()}")
        print(f"   - supports_audio(): {caps.supports_audio()}")
        print(f"   - supports_video(): {caps.supports_video()}")
        print()
    
    return True


def test_integration_with_hermes():
    """测试 5: 与 HermesAgent 集成"""
    print("\n" + "=" * 60)
    print("【测试5】HermesAgent 集成模拟")
    print("=" * 60)
    
    from core.agent_progress import ProgressEmitter, ProgressPhase
    
    detector = get_capability_detector()
    
    # 模拟 Agent 选择模型
    test_scenarios = [
        ("帮我分析这张图片", "llava:latest"),
        ("解释量子计算原理", "qwen3.5:9b"),
        ("今天天气怎么样", "qwen2.5:1.5b"),
        ("帮我写一首诗", "qwen3.6:35b-a3b"),
    ]
    
    print()
    for query, model in test_scenarios:
        caps = detector.detect(model)
        
        print(f"[NOTE] 查询: {query}")
        print(f"   模型: {model}")
        print(f"   能力: {caps.get_capability_summary()}")
        
        # 模拟处理逻辑
        if "图片" in query and not caps.supports_image():
            print(f"   [WARN] Model does not support images, will filter image content")
        elif caps.can_stream_think():
            print(f"   [OK] Will enable streaming thinking output")
        else:
            print(f"   [INFO] Thinking not supported or final-only")
        
        print()
    
    return True


def main():
    print("\n" + "=" * 60)
    print("[TEST] Model Capability Detection System")
    print("=" * 60)
    
    results = []
    
    results.append(("模式匹配检测", test_pattern_detection()))
    results.append(("Ollama API 检测", test_api_detection()))
    results.append(("多模态消息过滤", test_multimodal_filter()))
    results.append(("能力摘要生成", test_capability_summary()))
    results.append(("HermesAgent 集成", test_integration_with_hermes()))
    
    print("\n" + "=" * 60)
    print("[S] 测试结果汇总")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "[OK] 通过" if passed else "[FAIL] 失败"
        print(f"  {status}  {name}")
        if not passed:
            all_passed = False
    
    print()
    if all_passed:
        print("All tests passed!")
    else:
        print("Some tests failed, please check")


if __name__ == "__main__":
    main()
