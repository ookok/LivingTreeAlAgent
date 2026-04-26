"""
GlobalModelRouter + Handler 使用 Demo

展示：
1. 异步调用Handler
2. 同步调用便捷函数
3. HandlerFactory动态创建
4. GlobalModelRouter直接调用
5. 流式调用
6. 自定义Handler
"""

import asyncio
import time
from client.src.business.global_model_router import (
    GlobalModelRouter,
    ModelCapability,
    RoutingStrategy,
    get_global_router,
    HandlerFactory,
    ChatHandler,
    CodeGenerationHandler,
    TranslationHandler,
    SummarizationHandler,
    ReasoningHandler,
    call_model_sync,
    translate,
    summarize,
    review_code,
    analyze_data,
)


# ============= Demo 1: 异步调用Handler =============

async def demo_async_handler():
    """Demo 1: 异步调用Handler"""
    print("\n" + "="*60)
    print("Demo 1: 异步调用Handler")
    print("="*60)
    
    # 方式1: 直接创建Handler
    print("\n1.1 直接创建ChatHandler:")
    chat_handler = ChatHandler()
    response = await chat_handler.handle("解释什么是异步编程")
    print(f"响应: {response[:100]}...")
    
    # 方式2: 使用HandlerFactory
    print("\n1.2 使用HandlerFactory创建:")
    code_handler = HandlerFactory.create_handler(ModelCapability.CODE_GENERATION)
    response = await code_handler.handle("写一个Python快速排序")
    print(f"响应: {response[:100]}...")
    
    # 方式3: 带参数的Handler
    print("\n1.3 TranslationHandler (带参数):")
    trans_handler = TranslationHandler(source_lang="zh", target_lang="en")
    response = await trans_handler.handle("你好，世界！")
    print(f"翻译结果: {response}")
    
    print("\n1.4 SummarizationHandler (带参数):")
    summary_handler = SummarizationHandler(max_length=50)
    long_text = """
    人工智能（AI）是计算机科学的一个分支，旨在创建能够执行通常需要人类智能的任务的系统。
    这些任务包括视觉感知、语音识别、决策和语言翻译。
    AI可以分为弱AI（执行特定任务）和强AI（具有通用智能）。
    近年来，深度学习、大模型（如GPT、Qwen）取得了突破性进展。
    """
    response = await summary_handler.handle(long_text)
    print(f"摘要: {response}")


# ============= Demo 2: 同步调用便捷函数 =============

def demo_sync_functions():
    """Demo 2: 同步调用便捷函数"""
    print("\n" + "="*60)
    print("Demo 2: 同步调用便捷函数")
    print("="*60)
    
    # translate()
    print("\ntranslate():")
    result = translate("Hello, World!", source_lang="en", target_lang="zh")
    print(f"翻译结果: {result}")
    
    # summarize()
    print("\nsummarize():")
    long_text = "人工智能是计算机科学的重要分支。它致力于创建智能系统。"
    result = summarize(long_text, max_length=20)
    print(f"摘要: {result}")
    
    # review_code()
    print("\nreview_code():")
    code = """
def add(a, b):
    return a + b
"""
    result = review_code(code)
    print(f"代码审查: {result[:100]}...")
    
    # analyze_data()
    print("\nanalyze_data():")
    question = "分析一下最近的人工智能发展趋势"
    result = analyze_data(question)
    print(f"数据分析: {result[:100]}...")


# ============= Demo 3: GlobalModelRouter直接调用 =============

async def demo_router_direct():
    """Demo 3: GlobalModelRouter直接调用"""
    print("\n" + "="*60)
    print("Demo 3: GlobalModelRouter直接调用")
    print("="*60)
    
    router = get_global_router()
    
    # 3.1: 异步调用
    print("\n3.1 异步调用 (call_model):")
    response = await router.call_model(
        capability=ModelCapability.CHAT,
        prompt="用一句话解释机器学习",
        system_prompt="你是一个AI老师，用简单的话解释复杂概念。"
    )
    print(f"响应: {response[:100]}...")
    
    # 3.2: 同步调用
    print("\n3.2 同步调用 (call_model_sync):")
    response = call_model_sync(
        capability=ModelCapability.SUMMARIZATION,
        prompt="这是一个很长的文本，需要摘要。" * 10,
        system_prompt="你是一个摘要助手。"
    )
    print(f"摘要: {response[:100]}...")
    
    # 3.3: 指定路由策略
    print("\n3.3 指定路由策略 (质量优先):")
    response = await router.call_model(
        capability=ModelCapability.REASONING,
        prompt="证明：1+1=2",
        strategy=RoutingStrategy.QUALITY
    )
    print(f"响应: {response[:100]}...")
    
    # 3.4: 查看路由统计
    print("\n3.4 路由统计:")
    stats = router.get_stats()
    print(f"统计: {stats}")


# ============= Demo 4: 流式调用 =============

async def demo_streaming():
    """Demo 4: 流式调用"""
    print("\n" + "="*60)
    print("Demo 4: 流式调用")
    print("="*60)
    
    router = get_global_router()
    
    print("\n4.1 流式输出:")
    print("响应: ", end="", flush=True)
    
    async for chunk in router.call_model_stream(
        capability=ModelCapability.CHAT,
        prompt="数到5，每个数字单独一行",
        system_prompt="你是一个流式输出助手。"
    ):
        print(chunk, end="", flush=True)
    
    print("\n\n4.2 流式+推理:")
    print("推理过程: ", end="", flush=True)
    
    async for chunk in router.call_model_stream(
        capability=ModelCapability.REASONING,
        prompt="逐步计算：3 + 5 * 2",
        system_prompt="你是一个推理助手，分步思考。"
    ):
        print(chunk, end="", flush=True)
    
    print("\n")


# ============= Demo 5: Fallback机制 =============

async def demo_fallback():
    """Demo 5: Fallback机制（模型失败时自动切换）"""
    print("\n" + "="*60)
    print("Demo 5: Fallback机制")
    print("="*60)
    
    router = get_global_router()
    
    print("\n5.1 调用（带fallback）:")
    response = await router.call_model_with_fallback(
        capability=ModelCapability.CHAT,
        prompt="Hello, World!",
        system_prompt="You are a helpful assistant."
    )
    print(f"响应: {response[:100]}...")
    
    print("\n5.2 查看模型列表:")
    models = router.list_models(capability=ModelCapability.CHAT)
    for m in models[:3]:  # 只显示前3个
        print(f"  - {m['name']} (质量: {m['quality']}, 速度: {m['speed']})")


# ============= Demo 6: 自定义Handler =============

class PoetryHandler(ChatHandler):
    """自定义诗歌生成Handler"""
    
    async def handle(self, prompt: str, system_prompt: str = "", **kwargs) -> str:
        # 增强提示
        poetry_prompt = f"写一首关于{prompt}的短诗"
        
        return await super().handle(
            prompt=poetry_prompt,
            system_prompt="你是一个诗人。只输出诗歌，不要解释。"
        )
    
    def get_capability(self) -> ModelCapability:
        return ModelCapability.CONTENT_GENERATION


async def demo_custom_handler():
    """Demo 6: 自定义Handler"""
    print("\n" + "="*60)
    print("Demo 6: 自定义Handler")
    print("="*60)
    
    # 6.1: 直接使用自定义Handler
    print("\n6.1 直接使用PoetryHandler:")
    poet = PoetryHandler()
    response = await poet.handle("春天")
    print(f"诗歌:\n{response}\n")
    
    # 6.2: 注册到HandlerFactory
    print("\n6.2 注册到HandlerFactory:")
    HandlerFactory.register_handler(ModelCapability.CONTENT_GENERATION, PoetryHandler)
    
    # 现在通过Factory创建的就是自定义Handler了
    handler = HandlerFactory.create_handler(ModelCapability.CONTENT_GENERATION)
    print(f"Handler类型: {type(handler).__name__}")
    
    response = await handler.handle("秋天")
    print(f"诗歌:\n{response}\n")


# ============= Demo 7: 批量调用 =============

async def demo_batch_calls():
    """Demo 7: 批量调用（并发）"""
    print("\n" + "="*60)
    print("Demo 7: 批量调用（并发）")
    print("="*60)
    
    router = get_global_router()
    
    prompts = [
        "解释什么是Python",
        "解释什么是Java",
        "解释什么是C++",
    ]
    
    print(f"\n7.1 并发调用 {len(prompts)} 个请求:")
    start = time.time()
    
    # 并发调用
    tasks = [
        router.call_model(
            capability=ModelCapability.CHAT,
            prompt=prompt
        )
        for prompt in prompts
    ]
    
    results = await asyncio.gather(*tasks)
    
    elapsed = time.time() - start
    print(f"完成！耗时: {elapsed:.2f}秒")
    
    for i, result in enumerate(results):
        print(f"\nQ: {prompts[i]}")
        print(f"A: {result[:50]}...")


# ============= 主函数 =============

async def main():
    """主函数"""
    print("\n" + "="*60)
    print("GlobalModelRouter + Handler Demo")
    print("="*60)
    
    # 运行所有demo
    await demo_async_handler()
    demo_sync_functions()
    await demo_router_direct()
    await demo_streaming()
    await demo_fallback()
    await demo_custom_handler()
    await demo_batch_calls()
    
    print("\n" + "="*60)
    print("所有Demo完成！")
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
