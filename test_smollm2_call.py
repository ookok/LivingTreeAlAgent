#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 SmolLM2 模型调用
"""

import asyncio
from core.smolllm2.ollama_runner import get_runner_manager
from core.smolllm2.models import SmolLM2Config


async def test_smollm2_call():
    """测试 SmolLM2 模型调用"""
    print("开始测试 SmolLM2 模型调用")
    print("=" * 60)
    
    try:
        # 获取 Runner 管理器
        manager = await get_runner_manager()
        
        # 确保模型就绪
        print("确保模型就绪...")
        ready = await manager.ensure_ready()
        print(f"模型就绪状态: {ready}")
        
        # 获取 Runner
        runner = await manager.get_runner()
        print(f"使用模型: {runner.config.ollama_model_name}")
        
        # 构建测试提示词
        system_prompt = "你是一个轻量级意图分类器。任务：对用户输入进行快速分类。"
        user_input = "五一南京有哪些地方值得玩"
        prompt = f"{system_prompt}\n\n用户输入：{user_input}\n\n只输出JSON，不要其他内容。"
        
        # 测试生成
        print("\n测试模型生成...")
        response = await runner.generate(prompt)
        print(f"模型响应: {response}")
        
        # 测试对话
        print("\n测试模型对话...")
        messages = [
            {"role": "user", "content": user_input}
        ]
        chat_response = await runner.chat(messages)
        print(f"模型对话响应: {chat_response}")
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("测试完成")


if __name__ == "__main__":
    asyncio.run(test_smollm2_call())
