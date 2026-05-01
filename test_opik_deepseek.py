"""
Opik 可观测性 + DeepSeek Thinking 模式 综合测试脚本

测试内容：
1. Opik SDK 集成测试
2. DeepSeek-V4-Pro Thinking 模式测试
3. LLM 调用追踪与监控
4. 质量评估功能测试
"""

import asyncio
import sys
import os

# DeepSeek 配置
DEEPSEEK_API_KEY = "sk-f05ded8271b74091a499831999d34437"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"


async def test_opik_observability():
    """测试 Opik 可观测性平台"""
    print("\n" + "="*60)
    print("🧪 测试 Opik 可观测性平台")
    print("-"*60)
    
    try:
        from client.src.business.ai_pipeline.opik_observability import (
            OpikObserver,
            LlmCallTracker,
            get_opik_observer
        )
        
        # 获取观测器
        observer = get_opik_observer()
        print("✅ Opik 观测器初始化成功")
        
        # 模拟几次 LLM 调用
        for i in range(3):
            with LlmCallTracker(observer, f"deepseek-v4-pro", "deepseek") as tracker:
                tracker.prompt = f"测试提示词 {i+1}"
                tracker.record_response(f"测试响应 {i+1}", {
                    "prompt_tokens": 20 + i*10,
                    "completion_tokens": 50 + i*20,
                    "total_tokens": 70 + i*30
                })
        
        # 获取指标
        metrics = observer.get_metrics()
        print(f"✅ 指标收集成功")
        print(f"   总调用: {metrics['total_calls']}")
        print(f"   总Token: {metrics['total_tokens']}")
        print(f"   总成本: ${metrics['total_cost_usd']:.4f}")
        print(f"   成功率: {metrics['success_rate']}%")
        
        # 生成报告
        report = observer.generate_report()
        print("\n📊 可观测性报告:")
        print(report)
        
        return True
    except Exception as e:
        print(f"❌ Opik 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_deepseek_thinking_mode():
    """测试 DeepSeek Thinking 模式"""
    print("\n" + "="*60)
    print("🧪 测试 DeepSeek-V4-Pro Thinking 模式")
    print("-"*60)
    
    try:
        from client.src.business.ai_pipeline.opik_observability import DeepSeekClient
        
        client = DeepSeekClient(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
        
        # 测试普通模式
        print("\n📌 普通模式测试:")
        result1 = await client.chat_completion(
            model="deepseek-v4-pro",
            messages=[
                {"role": "system", "content": "你是一个数学助手。"},
                {"role": "user", "content": "一个房间里有3个人，每个人有2个苹果，总共有多少个苹果？"}
            ],
            max_tokens=512,
            thinking=False
        )
        
        if result1:
            print("✅ 普通模式测试成功")
            print(f"   响应: {result1['response'][:100]}...")
        else:
            print("❌ 普通模式测试失败")
        
        # 测试 Thinking 模式
        print("\n🧠 Thinking 模式测试:")
        result2 = await client.chat_completion(
            model="deepseek-v4-pro",
            messages=[
                {"role": "system", "content": "你是一个数学助手，使用思考模式详细解释你的计算过程。"},
                {"role": "user", "content": "一个房间里有3个人，每个人有2个苹果，后来进来了2个人，每个人有3个苹果，现在总共有多少个苹果？请详细解释计算过程。"}
            ],
            max_tokens=1024,
            thinking=True
        )
        
        if result2:
            print("✅ Thinking 模式测试成功")
            print(f"   响应: {result2['response'][:150]}...")
        else:
            print("❌ Thinking 模式测试失败")
        
        return True
    except Exception as e:
        print(f"❌ DeepSeek Thinking 模式测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_quality_evaluation():
    """测试质量评估功能"""
    print("\n" + "="*60)
    print("🧪 测试质量评估功能")
    print("-"*60)
    
    try:
        from client.src.business.ai_pipeline.opik_observability import get_opik_observer
        
        observer = get_opik_observer()
        
        # 测试评估
        prompt = "请解释什么是快速排序算法"
        response = "快速排序是一种高效的排序算法，采用分治策略。它选择一个基准元素，将数组分成两部分，使得左边的元素都小于基准，右边的元素都大于基准，然后递归地对两部分进行排序。时间复杂度平均为O(n log n)。"
        
        evaluation = observer.evaluate_quality(prompt, response)
        
        print(f"✅ 质量评估成功")
        print(f"   相关性: {evaluation['relevance']:.2f}")
        print(f"   连贯性: {evaluation['coherence']:.2f}")
        print(f"   完整性: {evaluation['completeness']:.2f}")
        print(f"   综合评分: {evaluation['overall_score']:.2f}")
        
        return True
    except Exception as e:
        print(f"❌ 质量评估测试失败: {e}")
        return False


async def test_decorator():
    """测试追踪装饰器"""
    print("\n" + "="*60)
    print("🧪 测试 @track_llm_call 装饰器")
    print("-"*60)
    
    try:
        from client.src.business.ai_pipeline.opik_observability import track_llm_call
        
        @track_llm_call(model="deepseek-v4-flash", provider="deepseek")
        async def mock_llm_call(prompt: str):
            """模拟 LLM 调用"""
            return {
                "response": f"响应: {prompt}",
                "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
            }
        
        result = await mock_llm_call("测试装饰器")
        print(f"✅ 装饰器测试成功")
        print(f"   响应: {result}")
        
        return True
    except Exception as e:
        print(f"❌ 装饰器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主函数"""
    print("🚀 Opik 可观测性 + DeepSeek Thinking 模式 综合测试")
    print("="*60)
    
    results = []
    
    # 运行所有测试
    results.append(("Opik 可观测性", await test_opik_observability()))
    results.append(("DeepSeek Thinking 模式", await test_deepseek_thinking_mode()))
    results.append(("质量评估", await test_quality_evaluation()))
    results.append(("追踪装饰器", await test_decorator()))
    
    # 输出总结
    print("\n" + "="*60)
    print("📊 测试结果总结")
    print("="*60)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for name, success in results:
        status = "✅" if success else "❌"
        print(f"   {status} {name}")
    
    print(f"\n   总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！")
    else:
        print(f"\n⚠️ 有 {total - passed} 个测试失败")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)