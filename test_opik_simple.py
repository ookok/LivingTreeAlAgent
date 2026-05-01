"""
Opik 可观测性 + DeepSeek Thinking 模式 独立测试脚本

不依赖项目复杂导入，直接测试核心功能。
"""

import asyncio
import sys
import os
import uuid
from datetime import datetime

# DeepSeek 配置
DEEPSEEK_API_KEY = "sk-f05ded8271b74091a499831999d34437"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"


# ============= 简化版 Opik 观测器 =============

class LlmCallMetrics:
    def __init__(self):
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.latency_ms = 0
        self.cost_usd = 0.0
        self.success = True
        self.error = None
        self.model = ""
        self.provider = ""


class LlmCallRecord:
    def __init__(self, id, timestamp, model, provider, prompt, response, metrics):
        self.id = id
        self.timestamp = timestamp
        self.model = model
        self.provider = provider
        self.prompt = prompt
        self.response = response
        self.metrics = metrics


class SimpleObserver:
    def __init__(self):
        self._call_records = []
        self._metrics_cache = {
            "total_calls": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "success_rate": 0.0,
            "model_usage": {},
            "provider_usage": {}
        }
        
    def record_call(self, model, provider, prompt, response, usage):
        metrics = LlmCallMetrics()
        metrics.prompt_tokens = usage.get("prompt_tokens", 0)
        metrics.completion_tokens = usage.get("completion_tokens", 0)
        metrics.total_tokens = usage.get("total_tokens", 0)
        metrics.model = model
        metrics.provider = provider
        
        # 计算成本
        cost_per_1k = {"deepseek-v4-pro": 0.0005, "deepseek-v4-flash": 0.0002}
        metrics.cost_usd = (metrics.total_tokens / 1000) * cost_per_1k.get(model, 0.0003)
        
        record = LlmCallRecord(
            id=str(uuid.uuid4())[:8],
            timestamp=datetime.now(),
            model=model,
            provider=provider,
            prompt=prompt[:50],
            response=response[:50],
            metrics=metrics
        )
        
        self._call_records.append(record)
        self._update_metrics(metrics)
    
    def _update_metrics(self, metrics):
        self._metrics_cache["total_calls"] += 1
        self._metrics_cache["total_tokens"] += metrics.total_tokens
        self._metrics_cache["total_cost_usd"] += metrics.cost_usd
        
        if metrics.model not in self._metrics_cache["model_usage"]:
            self._metrics_cache["model_usage"][metrics.model] = 0
        self._metrics_cache["model_usage"][metrics.model] += 1
        
        if metrics.provider not in self._metrics_cache["provider_usage"]:
            self._metrics_cache["provider_usage"][metrics.provider] = 0
        self._metrics_cache["provider_usage"][metrics.provider] += 1
    
    def get_metrics(self):
        return self._metrics_cache
    
    def generate_report(self):
        metrics = self.get_metrics()
        
        report = f"""
╔══════════════════════════════════════════════════════════════╗
║                    LLM 可观测性报告                          ║
╠══════════════════════════════════════════════════════════════╣
║  总调用次数:      {metrics['total_calls']:>10} 次             ║
║  总 Token 数:    {metrics['total_tokens']:>10}               ║
║  总成本(USD):    ${metrics['total_cost_usd']:>10.4f}        ║
║  模型使用:       {metrics['model_usage']}                   ║
╚══════════════════════════════════════════════════════════════╝
"""
        return report


# ============= DeepSeek 客户端 =============

class DeepSeekClient:
    def __init__(self, api_key, base_url="https://api.deepseek.com"):
        self.api_key = api_key
        self.base_url = base_url
        self.observer = SimpleObserver()
    
    async def chat_completion(self, model, messages, max_tokens=1024, thinking=False):
        import httpx
        
        url = f"{self.base_url}/chat/completions"
        
        data = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.7
        }
        
        # Thinking 模式参数（DeepSeek V4 Pro 需要对象格式，type 字段值为 enabled/disabled/adaptive）
        if thinking and "pro" in model.lower():
            data["thinking"] = {
                "type": "enabled",
                "thought": True,
                "thought_num": 5,
                "thought_max_token": 512
            }
        
        print(f"📤 发送请求: {model}, Thinking: {thinking}")
        
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json=data
            )
            
            print(f"📥 响应状态: {response.status_code}")
            
            if response.status_code != 200:
                print(f"❌ 请求失败: {response.text}")
                return None
            
            result = response.json()
            
            if result.get("choices"):
                response_text = result["choices"][0]["message"]["content"]
                usage = result.get("usage", {})
                
                # 记录到观测器
                self.observer.record_call(
                    model=model,
                    provider="deepseek",
                    prompt=messages[-1]["content"],
                    response=response_text,
                    usage=usage
                )
                
                return {
                    "response": response_text,
                    "usage": usage,
                    "thinking": thinking
                }
        
        return None


# ============= 测试函数 =============

async def test_deepseek_pro():
    """测试 DeepSeek-V4-Pro"""
    print("\n" + "="*60)
    print("🧪 测试 DeepSeek-V4-Pro")
    print("-"*60)
    
    client = DeepSeekClient(DEEPSEEK_API_KEY)
    
    # 测试普通模式
    print("\n📌 普通模式:")
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
        print("✅ 普通模式成功")
        print(f"   响应: {result1['response']}")
        print(f"   Token: {result1['usage']}")
    else:
        print("❌ 普通模式失败")
    
    # 测试 Thinking 模式
    print("\n🧠 Thinking 模式:")
    result2 = await client.chat_completion(
        model="deepseek-v4-pro",
        messages=[
            {"role": "system", "content": "你是一个数学助手，详细解释你的计算过程。"},
            {"role": "user", "content": "一个房间里有3个人，每个人有2个苹果，后来进来了2个人，每个人有3个苹果，现在总共有多少个苹果？"}
        ],
        max_tokens=1024,
        thinking=True
    )
    
    if result2:
        print("✅ Thinking 模式成功")
        print(f"   响应: {result2['response'][:200]}...")
        print(f"   Token: {result2['usage']}")
    else:
        print("❌ Thinking 模式失败")
    
    # 输出观测器报告
    print("\n📊 可观测性报告:")
    print(client.observer.generate_report())
    
    return result1 is not None and result2 is not None


async def test_deepseek_flash():
    """测试 DeepSeek-V4-Flash"""
    print("\n" + "="*60)
    print("🧪 测试 DeepSeek-V4-Flash")
    print("-"*60)
    
    client = DeepSeekClient(DEEPSEEK_API_KEY)
    
    result = await client.chat_completion(
        model="deepseek-v4-flash",
        messages=[
            {"role": "system", "content": "你是一个友好的助手。"},
            {"role": "user", "content": "请用一句话介绍你自己。"}
        ],
        max_tokens=256,
        thinking=False
    )
    
    if result:
        print("✅ Flash 模型测试成功")
        print(f"   响应: {result['response']}")
        print(f"   Token: {result['usage']}")
        return True
    else:
        print("❌ Flash 模型测试失败")
        return False


async def test_opik_integration():
    """测试 Opik SDK 集成"""
    print("\n" + "="*60)
    print("🧪 测试 Opik SDK 集成")
    print("-"*60)
    
    try:
        from opik import Opik
        from opik.tracing import trace
        
        print("✅ Opik SDK 导入成功")
        
        # 初始化 Opik
        opik_client = Opik(project_name="AI-Pipeline-Test")
        print("✅ Opik 客户端初始化成功")
        
        # 使用 Opik 追踪装饰器
        @trace
        def test_function():
            return {"result": "success"}
        
        result = test_function()
        print(f"✅ Opik 装饰器追踪成功: {result}")
        
        # 使用 trace 上下文
        with trace("llm_call"):
            print("✅ Opik 上下文追踪成功")
        
        return True
    
    except ImportError:
        print("❌ Opik SDK 未安装")
        return False
    except Exception as e:
        print(f"❌ Opik 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主函数"""
    print("🚀 Opik 可观测性 + DeepSeek Thinking 模式 测试")
    print("="*60)
    
    results = []
    
    # 运行测试
    results.append(("Opik SDK 集成", await test_opik_integration()))
    results.append(("DeepSeek-V4-Flash", await test_deepseek_flash()))
    results.append(("DeepSeek-V4-Pro", await test_deepseek_pro()))
    
    # 总结
    print("\n" + "="*60)
    print("📊 测试结果")
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