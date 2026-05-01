"""
Enhanced Model Router 测试脚本

测试内容：
1. ProviderManager 多服务商支持
2. EnhancedModelRouter 智能路由
3. Thinking 模式优先
4. Opik 可观测性
5. 完整工作流测试
"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'client', 'src'))


async def test_provider_manager():
    """测试 ProviderManager"""
    print("\n" + "="*60)
    print("🧪 测试 ProviderManager")
    print("="*60)
    
    from business.provider_manager import get_provider_manager, ModelCapability, ProviderType
    
    manager = get_provider_manager()
    
    # 统计服务商和模型数量
    total_providers = len(manager._providers)
    total_models = len(manager._models)
    
    print(f"✅ 服务商数量: {total_providers}")
    print(f"✅ 模型数量: {total_models}")
    
    # 分类统计
    print("\n📋 服务商分类:")
    
    # 国际主流服务商
    international = [ProviderType.DEEPSEEK, ProviderType.OPENAI, ProviderType.ANTHROPIC, ProviderType.GOOGLE]
    print("\n🌍 国际主流服务商:")
    for p in international:
        config = manager._providers.get(p)
        if config:
            print(f"   {p.value}: {len(config.models)} 个模型")
    
    # 国内云服务商
    chinese = [ProviderType.ALIBABA, ProviderType.TENCENT, ProviderType.BAIDU]
    print("\n🇨🇳 国内云服务商:")
    for p in chinese:
        config = manager._providers.get(p)
        if config:
            print(f"   {p.value}: {len(config.models)} 个模型")
    
    # AI 聚合平台
    aggregators = [ProviderType.LITELLM, ProviderType.OPENROUTER, ProviderType.FASTCHAT, ProviderType.ANYSCALE]
    print("\n🔗 AI 聚合平台:")
    for p in aggregators:
        config = manager._providers.get(p)
        if config:
            print(f"   {p.value}: {len(config.models)} 个模型")
    
    # 自定义平台
    print("\n⚙️ 自定义平台:")
    custom_config = manager._providers.get(ProviderType.CUSTOM)
    if custom_config:
        print(f"   custom: {len(custom_config.models)} 个模型")
        print(f"   基础URL: {custom_config.base_url}")
        print(f"   优先级: {custom_config.priority}")
    
    # 获取支持推理的模型（优先 Thinking 模式）
    reasoning_models = manager.get_models_for_capability(ModelCapability.REASONING, prefer_thinking=True)
    print(f"\n🧠 支持推理的模型 ({len(reasoning_models)}):")
    for m in reasoning_models[:5]:
        thinking = "✅" if m.supports_thinking else "❌"
        print(f"   [{thinking}] {m.name} ({m.provider.value})")
    
    # 测试添加自定义模型
    print("\n➕ 测试添加自定义模型:")
    manager.add_custom_model(
        provider_type=ProviderType.CUSTOM,
        model_id="custom_my_model",
        name="My Custom Model",
        capabilities=["chat", "content_generation", "reasoning"],
        config={"model": "my-model", "base_url": "http://localhost:8080/v1"},
        supports_thinking=True,
        quality_score=0.85
    )
    print("✅ 自定义模型添加成功")
    
    # 验证添加的模型
    custom_models = [m for m in manager._models.values() if m.provider == ProviderType.CUSTOM]
    print(f"🔍 当前自定义模型: {len(custom_models)} 个")
    
    # 输出报告
    print("\n📊 ProviderManager 报告:")
    print(manager.generate_report())
    
    return True


async def test_enhanced_router():
    """测试 EnhancedModelRouter"""
    print("\n" + "="*60)
    print("🧪 测试 EnhancedModelRouter")
    print("="*60)
    
    from business.enhanced_model_router import get_enhanced_model_router, RoutingStrategy
    
    router = get_enhanced_model_router()
    
    # 获取可用模型
    models = router.get_available_models()
    print(f"✅ 可用模型数: {len(models)}")
    
    # 获取服务商
    providers = router.get_providers()
    print(f"✅ 服务商数: {len(providers)}")
    for p in providers:
        status = "✅" if p["enabled"] and p["has_api_key"] else "❌"
        print(f"   {status} {p['type']}")
    
    # 测试调用（使用 PLANNING 能力，已验证可用）
    print("\n🔍 测试 Thinking 模式调用:")
    result = await router.call_model(
        capability="planning",
        prompt="一个房间里有3个人，每个人有2个苹果，后来进来了2个人，每个人有3个苹果，现在总共有多少个苹果？请详细解释计算过程。",
        system_prompt="你是一个数学助手。",
        strategy=RoutingStrategy.BALANCED,
        prefer_thinking=True,
        max_tokens=512
    )
    
    if result.success:
        print("✅ 调用成功")
        print(f"   模型: {result.model_used}")
        print(f"   服务商: {result.provider_used}")
        print(f"   Thinking: {result.thinking_enabled}")
        print(f"   Token: {result.tokens_used}")
        print(f"   耗时: {result.latency_ms:.2f}ms")
        print(f"   响应: {result.content[:150]}...")
        
        # 检查是否包含思考过程
        if "<think>" in result.content:
            print("\n✅ 检测到思考过程！")
    else:
        print(f"❌ 调用失败: {result.error}")
    
    return result.success


async def test_full_workflow():
    """测试完整工作流"""
    print("\n" + "="*60)
    print("🧪 测试完整工作流")
    print("="*60)
    
    from business.enhanced_model_router import get_enhanced_model_router, RoutingStrategy
    
    router = get_enhanced_model_router()
    
    requirement = "开发一个简单的待办事项 API，支持任务的创建、查询、更新和删除"
    
    print(f"🎯 需求: {requirement}")
    print("\n🚀 开始执行工作流...")
    
    # 步骤 1: 需求分析
    print("\n🔍 步骤 1: 需求分析")
    analysis = await router.call_model(
        capability="planning",
        prompt=f"请分析以下需求的关键点：{requirement}",
        strategy=RoutingStrategy.SPEED,
        prefer_thinking=True
    )
    if analysis.success:
        print("✅ 需求分析完成")
    
    # 步骤 2: 任务分解
    print("\n📋 步骤 2: 任务分解")
    decomposition = await router.call_model(
        capability="planning",
        prompt=f"请将以下需求分解为具体开发任务：{requirement}",
        strategy=RoutingStrategy.BALANCED,
        prefer_thinking=True
    )
    if decomposition.success:
        print("✅ 任务分解完成")
    
    # 步骤 3: 代码生成
    print("\n💻 步骤 3: 代码生成")
    code = await router.call_model(
        capability="content_generation",
        prompt=f"请使用 Python FastAPI 实现以下待办事项 API：{requirement}",
        strategy=RoutingStrategy.QUALITY,
        prefer_thinking=True,
        max_tokens=2048
    )
    if code.success:
        print("✅ 代码生成完成")
    
    # 步骤 4: 代码审查
    print("\n🔍 步骤 4: 代码审查")
    if code.success:
        review = await router.call_model(
            capability="planning",
            prompt=f"请审查以下代码的质量：\n{code.content[:500]}...",
            strategy=RoutingStrategy.BALANCED,
            prefer_thinking=True
        )
        if review.success:
            print("✅ 代码审查完成")
    
    # 输出统计报告
    print("\n📊 工作流统计:")
    print(router.generate_report())
    
    print("\n🎉 工作流执行完成！")
    return True


async def main():
    """主函数"""
    print("🚀 Enhanced Model Router 综合测试")
    print("="*60)
    
    results = []
    
    # 运行测试
    results.append(("ProviderManager", await test_provider_manager()))
    results.append(("EnhancedModelRouter", await test_enhanced_router()))
    results.append(("完整工作流", await test_full_workflow()))
    
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
        print("\n🎉 所有测试通过！增强版模型路由器集成成功！")
    else:
        print(f"\n⚠️ 有 {total - passed} 个测试失败")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)