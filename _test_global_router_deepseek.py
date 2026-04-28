"""
测试 GlobalModelRouter 调用 DeepSeek LLM

验证：
1. GlobalModelRouter 能正常加载 DeepSeek 配置
2. call_model_sync() 能正常调用 DeepSeek API
3. 路由策略正常工作
"""

import sys
import os

# 确保项目根目录在 sys.path 中
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def test_global_router_deepseek():
    """测试 GlobalModelRouter 调用 DeepSeek"""
    print("\n" + "=" * 60)
    print("🌐 测试 GlobalModelRouter 调用 DeepSeek")
    print("=" * 60)
    
    try:
        from client.src.business.global_model_router import (
            get_global_router,
            ModelCapability,
            RoutingStrategy,
            call_model_sync
        )
        from client.src.business.global_model_router import logger
        import logging
        
        # 设置日志级别（查看详细调用信息）
        logging.basicConfig(level=logging.DEBUG)
        
        print("\n✅ 导入 GlobalModelRouter 成功")
        
        # 获取全局路由器实例
        router = get_global_router()
        print(f"✅ 获取 GlobalModelRouter 实例成功")
        
        # 查看已加载的模型
        print(f"\n📊 已加载的模型列表:")
        for model_id, model_info in router.models.items():
            print(f"   - {model_id}: {model_info.name} (后端: {model_info.backend.value})")
        
        # 测试 1: 使用 DeepSeek-V4-Flash（快速模型）
        print(f"\n{"=" * 60}")
        print(f"🧪 测试 1: DeepSeek-V4-Flash（快速模型）")
        print(f"{"=" * 60}")
        
        try:
            response = call_model_sync(
                capability=ModelCapability.CHAT,  # 对话能力
                prompt="请用一句话介绍什么是环境影响评价（EIA）？",
                system_prompt="你是一个环评专家。请用简洁、专业的语言回答问题。",
                strategy=RoutingStrategy.SPEED,  # 速度优先（应该选择 flash 模型）
                use_cache=False
            )
            
            if response:
                print(f"✅ 调用成功！")
                print(f"📄 回复内容:\n{response}\n")
            else:
                print(f"❌ 调用失败：返回为空")
                
        except Exception as e:
            print(f"❌ 调用失败: {e}")
            import traceback
            traceback.print_exc()
        
        # 测试 2: 使用 DeepSeek-V4-Pro（高级模型）
        print(f"\n{"=" * 60}")
        print(f"🧪 测试 2: DeepSeek-V4-Pro（高级模型）")
        print(f"{"=" * 60}")
        
        try:
            response = call_model_sync(
                capability=ModelCapability.REASONING,  # 推理能力
                prompt="环评报告包含哪些主要章节？请列出并简要说明。",
                system_prompt="你是一个环评专家。请详细、专业地回答问题。",
                strategy=RoutingStrategy.QUALITY,  # 质量优先（应该选择 pro 模型）
                use_cache=False
            )
            
            if response:
                print(f"✅ 调用成功！")
                print(f"📄 回复内容:\n{response}\n")
            else:
                print(f"❌ 调用失败：返回为空")
                
        except Exception as e:
            print(f"❌ 调用失败: {e}")
            import traceback
            traceback.print_exc()
        
        # 测试 3: 自动路由（让路由器自动选择模型）
        print(f"\n{"=" * 60}")
        print(f"🧪 测试 3: 自动路由（AUTO 策略）")
        print(f"{"=" * 60}")
        
        try:
            response = call_model_sync(
                capability=ModelCapability.CONTENT_GENERATION,  # 内容生成
                prompt="解释一下「环境敏感点」在环评中的含义。",
                system_prompt="你是一个环评专家。",
                strategy=RoutingStrategy.AUTO,  # 自动选择
                use_cache=False
            )
            
            if response:
                print(f"✅ 调用成功！")
                print(f"📄 回复内容:\n{response}\n")
            else:
                print(f"❌ 调用失败：返回为空")
                
        except Exception as e:
            print(f"❌ 调用失败: {e}")
            import traceback
            traceback.print_exc()
        
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
    print("🚀 开始测试 GlobalModelRouter + DeepSeek")
    
    success = test_global_router_deepseek()
    
    if success:
        print("\n🎉 所有测试通过！")
    else:
        print("\n❌ 部分测试失败，请检查日志")
