#!/usr/bin/env python3
"""
Intent Recognition Test Script
Tests intent recognition capability of qwen3.5 models and SmolLM2

Test cases:
1. Simple Q&A -> intent: info_seeking
2. Code error diagnosis -> intent: code_debug
3. Feature implementation request -> intent: explicit_implement
4. Architecture discussion -> intent: architecture_discussion
5. Search request -> intent: search_request
6. Casual chat -> intent: casual_chat
7. Multimodal request -> intent: multimodal_request
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import json
import httpx
import time
import sys

OLLAMA_BASE = "http://localhost:11434"

# 测试用例集
TEST_CASES = [
    {
        "id": 1,
        "user_input": "查一下北京明天的天气",
        "description": "简单问答",
        "expected_intent": "info_seeking",
        "expected_tags": ["query_weather", "simple_question"],
    },
    {
        "id": 2,
        "user_input": "查看系统代码错误",
        "description": "Code review 类型",
        "expected_intent": "code_debug",
        "expected_tags": ["code_review", "error_check"],
    },
    {
        "id": 3,
        "user_input": "我使用ollama运行SmolLM2，能返回json，查看系统代码错误",
        "description": "混合请求(含上下文)",
        "expected_intent": "code_debug",
        "expected_tags": ["ollama", "json_return", "code_check"],
    },
    {
        "id": 4,
        "user_input": "添加一个用户登录功能",
        "description": "功能实现",
        "expected_intent": "explicit_implement",
        "expected_tags": ["feature_add", "login"],
    },
    {
        "id": 5,
        "user_input": "如何用PyQt6做一个漂亮的滑块组件？",
        "description": "技术探讨",
        "expected_intent": "architecture_discussion",
        "expected_tags": ["pyqt6", "ui_design", "how_to"],
    },
    {
        "id": 6,
        "user_input": "帮我搜索一下Python异步编程的最佳实践",
        "description": "搜索请求",
        "expected_intent": "search_request",
        "expected_tags": ["web_search", "best_practice"],
    },
    {
        "id": 7,
        "user_input": "今天心情不错",
        "description": "闲聊",
        "expected_intent": "casual_chat",
        "expected_tags": ["casual", "emotion"],
    },
    {
        "id": 8,
        "user_input": "打开浏览器看看淘宝的首页",
        "description": "浏览器操作请求",
        "expected_intent": "browser_use",
        "expected_tags": ["browser", "taobao", "navigation"],
    },
    {
        "id": 9,
        "user_input": "用qwen3.5:2b测试一下意图识别",
        "description": "模型测试",
        "expected_intent": "model_test",
        "expected_tags": ["qwen35", "intent_test"],
    },
    {
        "id": 10,
        "user_input": "把项目里的所有文件读一遍，整理出依赖关系图",
        "description": "深度分析",
        "expected_intent": "deep_analysis",
        "expected_tags": ["file_read", "dependency_map", "deep_analysis"],
    },
]

# 系统提示 - 给模型的意图分类指令
INTENT_SYSTEM_PROMPT = """你是一个意图理解引擎。分析用户的输入，识别其真实意图。

## 输出格式
严格输出JSON，不要输出任何其他内容：
{
  "intent": "意图分类(从以下选项选择)",
  "confidence": 0-1之间的浮点数,
  "tags": ["相关标签数组", "可以有多个"],
  "sub_intent": "子意图描述",
  "confidence_analysis": "为什么给出这个confidence值"
}

## 意图分类选项
- info_seeking: 信息查询、问答
- code_debug: 代码错误诊断、code review
- explicit_implement: 明确的功能实现请求
- architecture_discussion: 技术架构探讨、方案设计
- search_request: 需要搜索信息
- casual_chat: 闲聊、情感表达
- browser_use: 需要操作浏览器
- model_test: 模型测试、评测相关
- deep_analysis: 需要深度分析代码库或数据
- other: 其他意图

## 用户输入：
{user_input}"""

SYSTEM_PROMPT_SIMPLE = """你是一个轻量级意图分类器。请对以下用户输入进行分类，只输出JSON。

输出格式：
{{
  "intent": "信息获取|代码诊断|功能实现|技术讨论|搜索|闲聊|浏览器|模型测试|深度分析|其他",
  "confidence": 0.5-1.0,
  "tags": ["相关标签"],
  "explanation": "简短说明"
}}

用户输入：{user_input}"""

# Note: SmolLM2 raw prompt template (unused, kept for reference)
PROMPT_SIMPLE_RAW = """你是意图分类器。分类以下输入，只输出JSON：

JSON: {{intent: "类型", confidence: 0-1, tags: ["标签"], explains: "简答说明"}}

类型可以是：信息获取|代码诊断|功能实现|技术讨论|搜索|闲暇|浏览器操作|模型测试|深度分析|其他

输入：{user_input}"""


def call_ollama(model_name: str, user_input: str, prompt_template: str = None) -> dict:
    """调用 Ollama 模型"""
    if prompt_template is None:
        prompt_template = SYSTEM_PROMPT_SIMPLE

    prompt = prompt_template.format(user_input=user_input)

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": INTENT_SYSTEM_PROMPT},
            {"role": "user", "content": user_input},
        ],
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 256,
        },
    }

    try:
        with httpx.Client(timeout=60.0) as client:
            r = client.post(f"{OLLAMA_BASE}/v1/chat/completions", json=payload)
            r.raise_for_status()
            data = r.json()
            content = data["choices"][0]["message"]["content"]
            
            # 尝试解析JSON
            try:
                # 提取JSON部分（有些模型会输出额外文本）
                start = content.find("{")
                end = content.rfind("}") + 1
                if start != -1 and end != start:
                    content = content[start:end]
                result = json.loads(content)
                return result
            except json.JSONDecodeError:
                return {"raw_response": content, "parse_error": True}
                
    except httpx.ConnectError:
        return {"error": "无法连接到Ollama服务", "detail": "请确保Ollama正在运行 (ollama serve)"}
    except Exception as e:
        return {"error": str(e)}


def test_model(model_name: str, name: str):
    """测试单个模型"""
    print(f"\n{'='*80}")
    print(f"【测试模型】{name}")
    print(f"【模型名】{model_name}")
    print(f"{'='*80}")
    
    results = []
    
    for case in TEST_CASES:
        print(f"\n  测试 {case['id']:2d}/{len(TEST_CASES)}: {case['description']}")
        print(f"    用户输入: {case['user_input']}")
        print(f"    期望意图: {case['expected_intent']}")
        
        result = call_ollama(model_name, case['user_input'])
        
        detected_intent = result.get("intent", result.get("raw_response", "N/A"))
        confidence = result.get("confidence", 0)
        tags = result.get("tags", [])
        explanation = result.get("explanation", result.get("explains", ""))
        
        # 评估准确性
        is_correct = detected_intent == case['expected_intent']
        status = "[OK]" if is_correct else "[XX]"
        
        print(f"    {status} 检测意图: {detected_intent}")
        print(f"    置信度: {confidence}")
        print(f"    标签: {tags}")
        print(f"    说明: {explanation}")
        
        results.append({
            "case_id": case['id'],
            "description": case['description'],
            "user_input": case['user_input'],
            "expected_intent": case['expected_intent'],
            "detected_intent": detected_intent,
            "confidence": confidence,
            "tags": tags,
            "explanation": explanation,
            "is_correct": is_correct,
        })
        
        # 等待一下避免太快
        time.sleep(0.5)
    
    # ====== 汇总 ======
    correct_count = sum(1 for r in results if r['is_correct'])
    total = len(results)
    accuracy = correct_count / total * 100
    
    print(f"\n\n{'='*80}")
    print(f"=== {name} 测试汇总 ===")
    print(f"总用例数: {total}")
    print(f"正确: {correct_count}")
    print(f"准确率: {accuracy:.1f}%")
    
    # 分析错误案例
    wrong_cases = [r for r in results if not r['is_correct']]
    if wrong_cases:
        print(f"\n错误案例 ({len(wrong_cases)}个):")
        for r in wrong_cases:
            print(f"  - [{r['case_id']}] {r['description']}")
            print(f"    期望: {r['expected_intent']} -> 检测到: {r['detected_intent']}")
            if r.get('explanation'):
                print(f"    说明: {r['explanation']}")
    
    # 置信度分析
    confidences = [r['confidence'] for r in results]
    avg_confidence = sum(confidences) / len(confidences)
    print(f"\n平均置信度: {avg_confidence:.2f}")
    
    # 高置信度但错误的分析
    high_conf_wrong = [r for r in wrong_cases if r['confidence'] > 0.8]
    if high_conf_wrong:
        print(f"\n高置信度错误 ({len(high_conf_wrong)}个) - 最需要关注:")
        for r in high_conf_wrong:
            print(f"  - [案例{r['case_id']}] 置信度={r['confidence']:.2f}")
            print(f"    期望:{r['expected_intent']} -> 检测到:{r['detected_intent']}")
    
    print(f"\n{'='*80}\n")
    
    return results


def test_raw_response(model_name: str, name: str):
    """测试模型原始响应（不解析JSON）—— 看模型输出格式稳定性"""
    print(f"\n{'='*80}")
    print(f"=== {name} 原始响应测试 ===")
    print(f"{'='*80}")
    
    test_inputs = [
        "查看系统代码错误",
        "帮我搜索Python异步编程",
        "添加用户登录功能",
    ]
    
    for user_input in test_inputs:
        prompt = INTENT_SYSTEM_PROMPT.format(user_input=user_input)
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": INTENT_SYSTEM_PROMPT},
                {"role": "user", "content": user_input},
            ],
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 256},
        }
        
        try:
            with httpx.Client(timeout=60.0) as client:
                r = client.post(f"{OLLAMA_BASE}/v1/chat/completions", json=payload)
                r.raise_for_status()
                content = r.json()["choices"][0]["message"]["content"]
                print(f"\n输入: {user_input}")
                print(f"原始响应:")
                print(f"  {content[:200]}...")
        except Exception as e:
            print(f"\n错误: {e}")


if __name__ == "__main__":
    print("=" * 80)
    print("意图识别测试")
    print(f"Ollama 地址: {OLLAMA_BASE}")
    print("=" * 80)
    
    # 检查 Ollama 服务
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(f"{OLLAMA_BASE}/api/tags")
            models = r.json().get("models", [])
            print(f"\n可用模型 ({len(models)}个):")
            for m in models:
                print(f"  - {m['name']}")
    except Exception as e:
        print(f"\n[错误] 无法连接 Ollama: {e}")
        print("请先运行: ollama serve")
        sys.exit(1)
    
    # 检查模型是否存在
    available = [m['name'] for m in models]
    print("可用完整列表:", available)
    
    # 测试 qwen3.5:2b
    if "qwen3.5:2b" in available:
        qwen_results = test_model("qwen3.5:2b", "qwen3.5:2b")
    else:
        print("⚠️  qwen3.5:2b 未安装，跳过")
        qwen_results = None
    
    # 测试 smollm2
    smollm2_names = [m for m in available if 'smollm' in m.lower()]
    if smollm2_names:
        smollm2_model = smollm2_names[0]
        smollm_results = test_model(smollm2_model, f"SmolLM2 ({smollm2_model})")
    else:
        print("⚠️  SmolLM2 未安装，跳过")
        smollm_results = None
    
    # ====== 对比分析 ======
    print("\n\n")
    print("=" * 80)
    print("=== 对比分析 ===")
    print("=" * 80)
    
    if qwen_results and smollm_results:
        # 合并结果对比
        print(f"\n{'ID':>3} | {'用例':<25} | {'期望':<15} | {'qwen3.5:2b':<15} | {'SmolLM2':<15} | {'一致?'}")
        print("-" * 95)
        
        for qr, sr in zip(qwen_results, smollm_results):
            qwen_correct = "✅" if qr['is_correct'] else "❌"
            smollm_correct = "✅" if sr['is_correct'] else "❌"
            match = "✅" if qr['detected_intent'] == sr['detected_intent'] else "❌"
            
            print(f"{qr['case_id']:>3} | {qr['description']:<23} | {qr['expected_intent']:<13} | "
                  f"{qwen_correct} {qr['detected_intent']:<12} | {smollm_correct} {sr['detected_intent']:<12} | {match}")
        
        # 详细对比统计
        qwen_acc = sum(1 for r in qwen_results if r['is_correct']) / len(qwen_results) * 100
        smollm_acc = sum(1 for r in smollm_results if r['is_correct']) / len(smollm_results) * 100
        
        print(f"\n{'='*80}")
        print(f"{'指标':<25} | {'qwen3.5:2b':<20} | {'SmolLM2':<20}")
        print("-" * 70)
        print(f"{'准确率':<23} | {qwen_acc:>6.1f}%{'':<12} | {smollm_acc:>6.1f}%{'':<12}")
        
        qwen_avg_conf = sum(r['confidence'] for r in qwen_results) / len(qwen_results)
        smollm_avg_conf = sum(r['confidence'] for r in smollm_results) / len(smollm_results)
        print(f"{'平均置信度':<23} | {qwen_avg_conf:>6.2f}{'':<14} | {smollm_avg_conf:>6.2f}{'':<12}")
        
        # 一致性
        consistent = sum(1 for qr, sr in zip(qwen_results, smollm_results) 
                        if qr['detected_intent'] == sr['detected_intent'])
        print(f"{'两模型一致率':<23} | {consistent/len(qwen_results)*100:.1f}%{'':<16} |")
        
        agreed_correct = sum(1 for qr, sr in zip(qwen_results, smollm_results)
                           if qr['detected_intent'] == sr['detected_intent']
                           and qr['is_correct'])
        print(f"{'两模型一致且正确':<23} | {agreed_correct}/{len(qwen_results)}{'':<14} |")
        
        print("=" * 80)
    elif qwen_results:
        print("\n只有 qwen3.5:2b 测试结果，无法对比")
    elif smollm_results:
        print("\n只有 SmolLM2 测试结果，无法对比")
    else:
        print("\n没有可用的模型进行测试")
