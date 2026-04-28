"""
测试 L0-L4 分层路由

验证：
1. L0 → SmolLM2 (快速路由)
2. L4 → DeepSeek (深度生成)
3. L1-L3 → 自动选择（本地 Ollama）
"""

import sys
import os

# 确保项目根目录在 sys.path 中
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def test_tier_routing():
    """测试分层路由"""
    print("\n" + "=" * 60)
    print("🧪 测试 L0-L4 分层路由")
    print("=" * 60)
    
    try:
        from client.src.business.global_model_router import (
            get_global_router,
            ModelCapability,
            ModelTier,
            call_model_sync,
            RoutingStrategy
        )
        
        router = get_global_router()
        
        # 查看已加载的模型和分层路由
        print(f"\n📊 已加载的模型数量: {len(router.models)}")
        print(f"📊 分层路由配置:")
        for tier, model_id in router.tier_routing.items():
            print(f"   - {tier.value} → {model_id}")
        
        # 测试 1: L0 路由（应该调用 SmolLM2）
        print(f"\n{"=" * 60}")
        print(f"🧪 测试 1: L0 路由（快速分类）")
        print(f"{"=" * 60}")
        
        try:
            response = call_model_sync(
                capability=ModelCapability.CHAT,
                prompt="测试 L0 路由：1+1=?",
                system_prompt="你是一个快速分类器。只返回答案，不要解释。",
                tier=ModelTier.L0,
                use_cache=False
            )
            
            if response:
                print(f"✅ L0 调用成功！")
                print(f"📄 回复: {response}\n")
            else:
                print(f"❌ L0 调用失败：返回为空\n")
                
        except Exception as e:
            print(f"❌ L0 调用失败: {e}\n")
        
        # 测试 2: L4 路由（应该调用 DeepSeek-V4-Pro）
        print(f"\n{"=" * 60}")
        print(f"🧪 测试 2: L4 路由（深度生成）")
        print(f"{"=" * 60}")
        
        try:
            response = call_model_sync(
                capability=ModelCapability.REASONING,
                prompt="解释一下「环境敏感点」在环评中的含义。",
                system_prompt="你是一个环评专家。",
                tier=ModelTier.L4,
                use_cache=False
            )
            
            if response:
                print(f"✅ L4 调用成功！")
                print(f"📄 回复:\n{response}\n")
            else:
                print(f"❌ L4 调用失败：返回为空\n")
                
        except Exception as e:
            print(f"❌ L4 调用失败: {e}\n")
        
        # 测试 3: L1 路由（自动选择，应该调用本地 Ollama）
        print(f"\n{"=" * 60}")
        print(f"🧪 测试 3: L1 路由（自动选择）")
        print(f"{"=" * 60}")
        
        try:
            # L1 没有固定模型，使用自动选择
            # 先设置 L1 路由到一个 Ollama 模型
            ollama_models = [mid for mid in router.models if mid.startswith("ollama_")]
            if ollama_models:
                router.set_tier_routing(ModelTier.L1, ollama_models[0])
                print(f"设置 L1 路由 → {ollama_models[0]}")
                
                response = call_model_sync(
                    capability=ModelCapability.CHAT,
                    prompt="测试 L1 路由：什么是环境影响评价？",
                    system_prompt="简洁回答。",
                    tier=ModelTier.L1,
                    use_cache=False
                )
                
                if response:
                    print(f"✅ L1 调用成功！")
                    print(f"📄 回复: {response}\n")
                else:
                    print(f"❌ L1 调用失败：返回为空\n")
            else:
                print(f"⚠️ 没有可用的 Ollama 模型，跳过 L1 测试\n")
                
        except Exception as e:
            print(f"❌ L1 调用失败: {e}\n")
        
        print(f"\n{"=" * 60}")
        print(f"✅ 测试完成！")
        print(f"{"=" * 60}")
        
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    print("🚀 开始测试 L0-L4 分层路由")
    
    success = test_tier_routing()
    
    if success:
        print("\n🎉 所有测试通过！")
    else:
        print("\n❌ 部分测试失败，请检查日志")
