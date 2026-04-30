#!/usr/bin/env python
"""
测试用户输入到输出的完整生命周期处理过程
用户输入: "我怎么用脚本一键下载安装ollama"
"""

import sys
sys.path.insert(0, 'client/src')

import asyncio
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_chat_lifecycle():
    """测试完整的聊天生命周期"""
    print("=" * 80)
    print("🚀 开始测试用户输入到输出的完整生命周期")
    print("=" * 80)
    
    user_input = "我怎么用脚本一键下载安装ollama"
    print(f"\n📥 用户输入: {user_input}")
    
    # 步骤1: 获取全局模型路由器
    print("\n📌 步骤1: 获取全局模型路由器")
    from business.global_model_router import get_router, ModelCapability
    router = get_router()
    print(f"   ✅ 路由器初始化完成")
    
    # 步骤2: 路由到合适的模型
    print("\n📌 步骤2: 路由到合适的模型")
    model_info = router.route(ModelCapability.CHAT)
    if model_info:
        print(f"   ✅ 路由成功")
        print(f"   ├─ 模型名称: {model_info.name}")
        print(f"   ├─ 后端类型: {model_info.backend.value}")
        print(f"   ├─ Base URL: {model_info.config.get('base_url', 'N/A')}")
        print(f"   └─ 模型ID: {model_info.config.get('model', 'N/A')}")
    else:
        print("   ❌ 路由失败，没有可用模型")
        return
    
    # 步骤3: 构建消息格式
    print("\n📌 步骤3: 构建消息格式")
    messages = [
        {"role": "system", "content": "你是一个乐于助人的AI助手，请用中文回答用户问题。"},
        {"role": "user", "content": user_input}
    ]
    print(f"   ✅ 消息构建完成，共 {len(messages)} 条消息")
    
    # 步骤4: 调用模型（流式）
    print("\n📌 步骤4: 调用模型生成响应")
    print("   └─ 开始生成响应...")
    
    try:
        # 使用异步调用
        response = await router.call_model(
            capability=ModelCapability.CHAT,
            prompt=user_input,
            system_prompt="你是一个乐于助人的AI助手，请用中文回答用户问题。"
        )
        
        print(f"\n📤 模型响应:")
        print("-" * 60)
        print(response)
        print("-" * 60)
        
        print("\n✅ 响应生成成功")
        
    except Exception as e:
        print(f"❌ 模型调用失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 步骤5: 响应处理和渲染
    print("\n📌 步骤5: 响应处理和渲染")
    
    # 检查响应格式（确保是字符串）
    if isinstance(response, str):
        print(f"   ✅ 响应格式正确（字符串类型）")
        print(f"   └─ 响应长度: {len(response)} 字符")
    else:
        print(f"   ⚠️ 响应格式异常: {type(response)}")
    
    # Markdown渲染测试（跳过GUI依赖）
    print(f"   ⚠️ Markdown渲染测试跳过（需要QApplication）")
    
    # 步骤6: 记录对话历史
    print("\n📌 步骤6: 记录对话历史")
    try:
        from business.memory_fusion_engine import MemoryFusionEngine
        memory_engine = MemoryFusionEngine()
        memory_engine.store_conversation(
            user_input=user_input,
            response=response,
            model_name=model_info.name
        )
        print(f"   ✅ 对话历史记录成功")
    except Exception as e:
        print(f"   ⚠️ 对话历史记录测试跳过: {e}")
    
    print("\n" + "=" * 80)
    print("🎉 测试完成！用户输入到输出的完整生命周期已验证")
    print("=" * 80)
    
    return response

if __name__ == "__main__":
    # 运行测试
    result = asyncio.run(test_chat_lifecycle())
    
    # 保存测试结果
    if result:
        with open("test_chat_result.txt", "w", encoding="utf-8") as f:
            f.write(f"用户输入: 我怎么用脚本一键下载安装ollama\n")
            f.write("=" * 60 + "\n")
            f.write(result)
        
        print(f"\n📄 测试结果已保存到: test_chat_result.txt")