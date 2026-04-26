#!/usr/bin/env python3
"""
测试 mogoo.com.cn 端点

验证：
1. 端点连通性
2. GlobalModelRouter 调用
3. Handler 调用
"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "client"))

from client.src.business.global_model_router import (
    get_global_router,
    ModelCapability,
    call_model_sync,
    ChatHandler,
    TranslationHandler,
)


def log(msg):
    """写入日志文件（避免控制台编码问题）"""
    with open("test_result.txt", "a", encoding="utf-8") as f:
        f.write(msg + "\n")
    print(msg)  # 也打印到控制台（可能失败，但文件已保存）


def test_sync():
    """同步测试"""
    log("\n" + "="*60)
    log("同步测试 (call_model_sync)")
    log("="*60)
    
    # 测试1: 简单对话
    log("\n测试1: 简单对话 (mogoo_qwen)")
    try:
        response = call_model_sync(
            capability=ModelCapability.CHAT,
            prompt="用一句话介绍你自己",
            system_prompt="你是一个AI助手。",
            model_id="mogoo_qwen"  # 明确指定模型
        )
        log(f"响应: {response[:200]}...")
    except Exception as e:
        log(f"错误: {e}")
    
    # 测试2: 翻译
    log("\n测试2: 翻译 (mogoo_qwen)")
    try:
        from client.src.business.global_model_router import translate
        result = translate("Hello, World!", source_lang="en", target_lang="zh")
        log(f"翻译结果: {result}")
    except Exception as e:
        log(f"错误: {e}")


async def test_async():
    """异步测试"""
    log("\n" + "="*60)
    log("异步测试 (GlobalModelRouter.call_model)")
    log("="*60)
    
    router = get_global_router()
    
    # 测试3: 异步对话
    log("\n测试3: 异步对话 (mogoo_qwen)")
    try:
        response = await router.call_model(
            capability=ModelCapability.CHAT,
            prompt="解释什么是人工智能",
            system_prompt="你是一个AI老师。",
            model_id="mogoo_qwen"  # 明确指定模型
        )
        log(f"响应: {response[:200]}...")
    except Exception as e:
        log(f"错误: {e}")
    
    # 测试4: 查看路由统计
    log("\n测试4: 路由统计")
    try:
        stats = router.get_stats()
        log(f"统计: {stats}")
    except Exception as e:
        log(f"错误: {e}")


def main():
    """主函数"""
    # 清空结果文件
    with open("test_result.txt", "w", encoding="utf-8") as f:
        f.write("="*60 + "\n")
        f.write("测试 mogoo.com.cn 端点\n")
        f.write("="*60 + "\n")
    
    log("\n" + "="*60)
    log("测试 mogoo.com.cn 端点")
    log("="*60)
    
    # 同步测试
    test_sync()
    
    # 异步测试
    asyncio.run(test_async())
    
    log("\n" + "="*60)
    log("所有测试完成！结果已保存到 test_result.txt")
    log("="*60 + "\n")


if __name__ == "__main__":
    main()
