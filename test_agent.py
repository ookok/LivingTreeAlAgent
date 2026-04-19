#!/usr/bin/env python3
"""
测试 Hermes Agent 模型加载和调用
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
_root = Path(__file__).parent
sys.path.insert(0, str(_root))

from client.src.infrastructure.config import load_config
from client.src.business.agent import HermesAgent, AgentCallbacks


def test_agent():
    """测试 Agent 模型加载和调用"""
    print("=== 测试 Hermes Agent ===")
    
    # 加载配置
    cfg = load_config()
    print("配置加载完成")
    
    # 定义回调
    def stream_delta(delta):
        print(delta, end="", flush=True)
    
    def thinking(delta):
        print(f"[思考] {delta}", flush=True)
    
    def tool_start(name, args_str):
        print(f"[工具] 开始: {name}", flush=True)
    
    def tool_result(name, result, success):
        print(f"[工具] 结果: {name} {'成功' if success else '失败'}", flush=True)
    
    callbacks = AgentCallbacks(
        stream_delta=stream_delta,
        thinking=thinking,
        tool_start=tool_start,
        tool_result=tool_result
    )
    
    # 创建 Agent
    print("创建 Agent...")
    try:
        agent = HermesAgent(config=cfg, callbacks=callbacks, backend="ollama")
        print("Agent 创建成功")
        
        # 测试发送消息
        print("\n发送测试消息...")
        print("用户: 你好，Hermes！")
        
        # 迭代流式响应
        for chunk in agent.send_message("你好，Hermes！"):
            if chunk.error:
                print(f"\n错误: {chunk.error}")
                break
            if chunk.done:
                print("\n对话完成")
                break
        
        # 获取会话统计
        stats = agent.get_session_stats()
        if stats:
            print(f"\n会话统计: {stats.get_summary()}")
        
        # 关闭 Agent
        agent.close()
        print("\n测试完成")
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_agent()
