"""
测试 caveman LLM 输出压缩工具
"""

import sys
import os
import asyncio

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'client', 'src'))

async def test_caveman():
    print("测试 caveman LLM 输出压缩工具...")

    # 测试 CavemanTool
    print("\n[1] 测试 CavemanTool...")

    try:
        from business.tools.caveman_tool import CavemanTool, CompressionLevel
        
        tool = CavemanTool()
        print(f"✓ CavemanTool 初始化成功")
        print(f"✓ caveman 可用: {'是' if tool.is_available() else '否'}")
        
        if tool.is_available():
            # 测试不同压缩级别
            test_text = """这是一段用于测试的文本内容，包含多个段落和不同类型的内容。

第一段落：介绍 caveman 工具的功能和用途。caveman 是一个强大的 LLM 输出压缩工具，可以将输出 token 减少约 75%。

第二段落：测试不同压缩级别的效果。支持四种压缩级别：Lite、Full、Ultra 和文言文模式。

第三段落：代码示例。
def hello_world():
    print("Hello, World!")
    return True

这是最后一段，用于测试压缩效果。"""
            
            print(f"\n✓ 测试文本长度: {len(test_text)} 字符")
            
            for level in ["lite", "full", "ultra", "wenyan"]:
                print(f"\n--- 测试 {level} 级别 ---")
                result = await tool.execute(text=test_text, level=level)
                
                if result["success"]:
                    ratio = result["compression_ratio"]
                    print(f"✓ 压缩率: {ratio:.1%}")
                    print(f"✓ 压缩后长度: {result['compressed_length']} 字符")
                    print(f"✓ 压缩后内容:\n{result['compressed_text'][:150]}...")
                else:
                    print(f"✗ 压缩失败: {result['message']}")
        else:
            print("⚠️ caveman 不可用，跳过压缩测试")
            
    except Exception as e:
        print(f"✗ 测试 CavemanTool 失败: {e}")

    # 测试 GlobalModelRouter 中的 caveman 集成
    print("\n[2] 测试 GlobalModelRouter caveman 集成...")

    try:
        from business.global_model_router import GlobalModelRouter, CompressionLevel
        
        router = GlobalModelRouter()
        
        print(f"✓ GlobalModelRouter 初始化成功")
        print(f"✓ caveman 可用: {'是' if router.is_caveman_available() else '否'}")
        print(f"✓ caveman 启用: {'是' if router.is_caveman_enabled() else '否'}")
        print(f"✓ 压缩级别: {router.get_caveman_level().value}")
        print(f"✓ 最小 token 数: {router.get_caveman_min_tokens()}")
        
        # 测试启用/禁用 caveman
        router.enable_caveman(True)
        print(f"✓ 启用 caveman 后状态: {'是' if router.is_caveman_enabled() else '否'}")
        
        router.set_caveman_level("ultra")
        print(f"✓ 设置压缩级别为 ultra")
        
        router.set_caveman_min_tokens(100)
        print(f"✓ 设置最小 token 数为 100")
        
        router.enable_caveman(False)
        print(f"✓ 禁用 caveman 后状态: {'是' if router.is_caveman_enabled() else '否'}")
        
    except Exception as e:
        print(f"✗ 测试 GlobalModelRouter caveman 集成失败: {e}")

    print("\n🎉 所有测试完成!")

if __name__ == "__main__":
    asyncio.run(test_caveman())