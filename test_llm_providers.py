"""Test all configured LLM providers — list free/limited-free models."""
import asyncio, json, time, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import aiohttp

PROVIDERS = {
    "deepseek":    "https://api.deepseek.com/v1",
    "longcat":     "https://api.longcat.chat/openai/v1",
    "qwen":        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "siliconflow": "https://api.siliconflow.cn/v1",
    "zhipu":       "https://open.bigmodel.cn/api/paas/v4",
    "spark":       "https://maas-api.cn-huabei-1.xf-yun.com/v2",
    "modelscope":  "https://api-inference.modelscope.cn/v1",
    "bailing":     "https://api.baichuan-ai.com/v1",
    "stepfun":     "https://api.stepfun.com/v1",
    "xiaomi":      "https://api.xiaomimimo.com/v1",
    "mofang":      "https://ai.gitee.com/v1",
    "nvidia":      "https://integrate.api.nvidia.com/v1",
    "aliyun":      "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "internlm":    "https://api.intern-ai.org.cn/v1",
    "web2api":     "http://localhost:5001/v1",
    "opencode":    "http://localhost:4096/v1",
}

# Known free models per provider (manually curated)
FREE_MODELS = {
    "deepseek":    ["deepseek-chat", "deepseek-reasoner"],
    "siliconflow": ["Qwen/Qwen2.5-7B-Instruct", "Qwen/Qwen2.5-32B-Instruct", "deepseek-ai/DeepSeek-V3", "Pro/Llama-3.3-70B-Instruct"],
    "qwen":        ["qwen-turbo", "qwen-plus", "qwen-max"],
    "zhipu":       ["glm-4-flash", "glm-4-air"],
    "spark":       ["spark-lite", "spark-pro-128k"],
    "modelscope":  ["Qwen/Qwen2.5-7B-Instruct", "Qwen/Qwen2.5-72B-Instruct"],
    "bailing":     ["Baichuan4", "Baichuan3-Turbo"],
    "stepfun":     ["step-1-flash", "step-1-8k"],
    "longcat":     ["longcat-flash"],
}

async def ping_provider(name, url, timeout=8):
    """Ping provider — try /models endpoint."""
    t0 = time.time()
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{url}/models", timeout=aiohttp.ClientTimeout(total=timeout)) as r:
                latency = (time.time() - t0) * 1000
                if r.status == 200:
                    data = await r.json()
                    models = data.get("data", []) if isinstance(data, dict) else data
                    model_ids = [m.get("id", "") for m in models if isinstance(m, dict)]
                    return {"status": "✅", "latency": f"{latency:.0f}ms", "models": len(model_ids), "ids": model_ids[:10]}
                elif r.status == 401:
                    return {"status": "🔒 需API Key", "latency": f"{latency:.0f}ms"}
                else:
                    return {"status": f"❌ HTTP {r.status}", "latency": f"{latency:.0f}ms"}
    except asyncio.TimeoutError:
        return {"status": "⏱️ 超时", "latency": ">8s"}
    except Exception as e:
        return {"status": f"❌ {str(e)[:40]}", "latency": "-"}

async def main():
    print("=" * 70)
    print("   LivingTree LLM Provider Test — Free Model Scanner")
    print("=" * 70)

    results = {}
    tasks = {name: ping_provider(name, url) for name, url in PROVIDERS.items()}
    gathered = await asyncio.gather(*tasks.values())
    for (name, _), result in zip(tasks.items(), gathered):
        results[name] = result

    # Print results
    print(f"\n{'Provider':<15} {'Status':<25} {'Latency':>8}  {'Models':>8}")
    print("-" * 70)

    for name, url in PROVIDERS.items():
        r = results.get(name, {})
        status = r.get("status", "?")
        lat = r.get("latency", "-")
        count = r.get("models", 0) if isinstance(r.get("models"), int) else 0
        free_ids = FREE_MODELS.get(name, [])
        free_str = f"  🆓 {', '.join(free_ids[:4])}" if free_ids else ""
        print(f"{name:<15} {status:<25} {lat:>8}  {count:>6}{free_str}")

    # Summary
    online = sum(1 for r in results.values() if "✅" in str(r.get("status", "")))
    print(f"\n{'='*70}")
    print(f"  Online: {online}/{len(PROVIDERS)}  |  providers with /models accessible")
    print(f"  Web2API: http://localhost:5001  |  OpenCode: http://localhost:4096")
    print(f"{'='*70}")

    # Free models by provider
    print("\n📋 Free/Limited-Free Models by Provider:")
    for name, models in FREE_MODELS.items():
        if name in results and "✅" in str(results[name].get("status", "")):
            print(f"  {name}: {', '.join(models)}")
        else:
            print(f"  {name}: {', '.join(models)} [offline — models from registry]")

if __name__ == "__main__":
    asyncio.run(main())
