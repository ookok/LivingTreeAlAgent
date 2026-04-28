#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SmolLM2 GGUF 意图识别测试脚本

SmolLM2-135M 的 GGUF 文件加载通过 core.smolllm2.ollama_runner
它会把 GGUF 文件打包成 Ollama 模型，然后同样通过 /api/chat/completions 调用
"""

import sys
import io
import json
import httpx
import asyncio
import time

OLLAMA_BASE = "http://localhost:11434"

# 相同的测试用例
TEST_CASES = [
    {"id": 1, "input": "查一下北京明天的天气", "exp_intent": "info_seeking", "desc": "简单问答"},
    {"id": 2, "input": "查看系统代码错误", "exp_intent": "code_debug", "desc": "Code review"},
    {"id": 3, "input": "我使用ollama运行SmolLM2，能返回json，查看系统代码错误", "exp_intent": "code_debug", "desc": "混合请求"},
    {"id": 4, "input": "添加一个用户登录功能", "exp_intent": "explicit_implement", "desc": "功能实现"},
    {"id": 5, "input": "如何用PyQt6做一个漂亮的滑块组件？", "exp_intent": "architecture_discussion", "desc": "技术探讨"},
    {"id": 6, "input": "帮我搜索一下Python异步编程的最佳实践", "exp_intent": "search_request", "desc": "搜索请求"},
    {"id": 7, "input": "今天心情不错", "exp_intent": "casual_chat", "desc": "闲聊"},
    {"id": 8, "input": "打开浏览器看看淘宝的首页", "exp_intent": "browser_use", "desc": "浏览器操作"},
    {"id": 9, "input": "用SmolLM2测试一下意图识别", "exp_intent": "model_test", "desc": "模型测试"},
    {"id": 10, "input": "把项目里的所有文件读一遍，整理出依赖关系图", "exp_intent": "deep_analysis", "desc": "深度分析"},
]

# SmolLM2 的系统提示词（参考 core.smolllm2.models.SmolLM2Config.system_prompt）
# 由于 SmolLM2 只有 135M 参数，需要非常简洁的提示
SYSTEM_PROMPT = """你是一个轻量级意图分类器。输出JSON格式结果，不要输出其他内容。

路由选项：cache|local|search|heavy|human
意图选项：greeting|simple_q|format_clean|json_extract|quick_reply|code_simple|search_query|summarize|code_complex|long_writing|reasoning|analysis|unknown

输出格式：
{"route":"local","intent":"format_clean","reason":"说明","confidence":0.9}

用户输入："""

# 更简单的版本（SmolLM2 135M 可能处理不了太复杂的提示）
SYSTEM_PROMPT_SIMPLE = """Intent classify for input. Output JSON only: {"intent":"TYPE","confidence":0.9}
Types: info_search code_fix feature_add tech_talk search casual browser model_test deep_analysis other"""


def call_smollm2(prompt: str, system: str = SYSTEM_PROMPT) -> str:
    """通过 Ollama API 调用 SmolLM2 (通过 ollama create 从 GGUF 创建的本地模型)"""
    
    # 先尝试创建模型（如果还没创建）
    create_model()
    
    payload = {
        "model": "smollm2-135m",  # GGUF 创建的模型名
        "prompt": SYSTEM_PROMPT_SIMPLE,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 128,
        },
    }
    
    try:
        with httpx.Client(timeout=120.0) as client:
            r = client.post(f"{OLLAMA_BASE}/api/generate", json=payload)
            r.raise_for_status()
            result = r.json()
            return result.get("response", "").strip()
    except httpx.ConnectError:
        return "[ERROR] Ollama not running"
    except Exception as e:
        return f"[ERROR] {e}"


def create_model():
    """如果 smollm2-135m 模型不存在，通过 ollama create 从 GGUF 创建"""
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(f"{OLLAMA_BASE}/api/tags")
            models = r.json().get("models", [])
            model_names = [m.get("name") for m in models]
    except:
        model_names = []
    
    if "smollm2-135m" in model_names:
        return True
    
    # 需要找到 GGUF 文件
    import subprocess
    import pathlib
    
    gguf_candidates = [
        pathlib.Path("/models/SmolLM2.gguf"),
        pathlib.Path("models/SmolLM2.gguf"),
        pathlib.Path.home() / ".hermes-desktop/models/*smollm*.gguf",
    ]
    
    # 先检查是否有 models/SmolLM2.gguf
    gguf_path = None
    for p in [pathlib.Path("models/SmolLM2.gguf")]:
        if p.exists():
            gguf_path = p
            break
    
    if not gguf_path:
        print("    ⚠️ 未找到 GGUF 文件，无法创建模型")
        return False
    
    print(f"    创建 smollm2-135m 模型 (from {gguf_path})...")
    result = subprocess.run(
        ["ollama", "create", "smollm2-135m", "-f", "ollama_model_file"],
        capture_output=True,
        text=True,
        timeout=300
    )
    
    return result.returncode == 0


def test_smollm2():
    """测试 SmolLM2"""
    print("\n" + "=" * 80)
    print("[1/2] 测试 SmolLM2-135M (GGUF)")
    print("=" * 80)
    
    results = []
    
    for case in TEST_CASES:
        print(f"\n  测试 {case['id']:2d}/10: {case['desc']}")
        print(f"    输入: {case['input']}")
        print(f"    期望: {case['exp_intent']}")
        
        # 构建提示词（更简洁的版本）
        prompt = SYSTEM_PROMPT_SIMPLE + "\n\n" + case['input']
        
        # 调用模型
        response = call_smollm2(prompt)
        
        print(f"    响应: {response[:100]}")
        
        # 解析结果
        detected_intent = "other"  # 默认
        confidence = 0.5
        reason = ""
        
        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start != -1 and end > start:
                j = json.loads(response[start:end])
                detected_intent = j.get("intent", "other")
                confidence = j.get("confidence", 0.5)
                reason = j.get("reason", j.get("route", ""))
        except:
            pass
        
        is_correct = detected_intent == case['exp_intent']
        status = "[OK]" if is_correct else "[XX]"
        
        print(f"    {status} 意图: {detected_intent}, 置信度: {confidence}")
        print(f"    原因: {reason}")
        
        results.append({
            "case": case,
            "detected_intent": detected_intent,
            "confidence": confidence,
            "reason": reason,
            "is_correct": is_correct,
        })
        
        time.sleep(0.3)
    
    # 汇总
    correct = sum(1 for r in results if r['is_correct'])
    total = len(results)
    acc = correct / total * 100
    avg_conf = sum(r['confidence'] for r in results) / total
    
    print(f"\n  ===== 汇总 ====")
    print(f"  准确率: {correct}/{total} = {acc:.1f}%")
    print(f"  平均置信度: {avg_conf:.2f}")
    
    wrong = [r for r in results if not r['is_correct']]
    if wrong:
        print(f"\n  错误案例:")
        for r in wrong:
            print(f"    - 案例{r['case']['id']}: {r['case']['desc']}")
            print(f"      期望:{r['case']['exp_intent']} -> 检测到:{r['detected_intent']}")
    
    print(f"\n{'='*80}")
    return results


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    
    print("=" * 80)
    print("SmolLM2 GGUF 意图识别测试")
    print("=" * 80)
    
    # 检查 Ollama 状态
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(f"{OLLAMA_BASE}/api/tags")
            models = r.json().get("models", [])
            print(f"\nOllama 可用模型 ({len(models)}个):")
            for m in models:
                print(f"  - {m['name']}")
    except Exception as e:
        print(f"\n[ERROR] Ollama 未运行: {e}")
        sys.exit(1)
    
    model_names = [m['name'] for m in models]
    
    if "smollm2-135m" not in model_names:
        print("\nsmollm2-135m 不在 Ollama 中，尝试通过 GGUF 创建...")
        import subprocess
        import pathlib
        
        gguf_path = pathlib.Path("models/SmolLM2.gguf")
        if gguf_path.exists():
            print(f"  发现 GGUF: {gguf_path}")
            print(f"  文件大小: {gguf_path.stat().st_size / 1024 / 1024:.0f}MB")
            print(f"  尝试创建 Ollama 模型...")
            
            # 创建 ollama model file
            modelfile_path = pathlib.Path("ollama_model_file")
            with open(modelfile_path, 'w') as f:
                f.write(f"FROM SmolLM2.gguf\nPARAMETER temperature 0.1\nPARAMETER num_ctx 2048\n")
            
            result = subprocess.run(
                ["ollama", "create", "smollm2-135m", "-f", "ollama_model_file"],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                print("  ✅ 模型创建成功")
            else:
                print(f"  ❌ 模型创建失败: {result.stderr[:200]}")
        else:
            print("  ❌ 未找到 GGUF 文件")
            sys.exit(1)
    
    # 运行测试
    results = test_smollm2()
