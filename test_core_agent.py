#!/usr/bin/env python3
"""
测试 Core Hermes Agent 模型加载和调用
"""

import sys
import time
from pathlib import Path

# 添加项目根目录到路径
_root = Path(__file__).parent
sys.path.insert(0, str(_root))

from core.agent import HermesAgent, AgentCallbacks
from core.config import AppConfig
from core.ollama_client import OllamaClient


def test_ollama_connection():
    """测试 Ollama 连接"""
    print("=== 测试 Ollama 连接 ===")
    try:
        from core.config import OllamaConfig
        ollama_config = OllamaConfig()
        client = OllamaClient(ollama_config)
        
        print(f"Ollama URL: {ollama_config.base_url}")
        
        # 测试 ping
        online = client.ping()
        print(f"Ollama 在线: {online}")
        
        if online:
            version = client.version()
            print(f"Ollama 版本: {version}")
            
            # 测试模型列表
            models = client.list_models()
            print(f"可用模型数量: {len(models)}")
            for model in models:
                print(f"  - {model.name}")
        
        return online
    except Exception as e:
        print(f"Ollama 连接测试失败: {e}")
        return False


def test_agent():
    """测试 Agent 模型加载和调用"""
    print("=== 测试 Core Hermes Agent ===")
    
    # 测试 Ollama 连接
    ollama_online = test_ollama_connection()
    if not ollama_online:
        print("Ollama 未运行，无法测试 Agent")
        return
    
    # 创建配置
    cfg = AppConfig()
    print("配置创建完成")
    
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
        
        # 测试 Ollama 直接调用
        print("\n测试 Ollama 直接调用...")
        try:
            from core.ollama_client import ChatMessage
            import threading
            import time
            
            messages = [ChatMessage(role="user", content="你好，Hermes！")]
            print("发送消息到 Ollama...")
            print("注意: 首次使用模型时，Ollama 会自动下载模型，这可能需要几分钟时间...")
            
            # 设置超时机制
            result = {"chunks": [], "error": None}
            
            def ollama_call():
                try:
                    for chunk in agent.ollama.chat(messages, model="qwen2.5:0.5b"):
                        result["chunks"].append(chunk)
                        if chunk.error:
                            result["error"] = chunk.error
                            break
                        if chunk.delta:
                            print(chunk.delta, end="", flush=True)
                        if chunk.done:
                            break
                except Exception as e:
                    result["error"] = str(e)
            
            # 启动线程
            thread = threading.Thread(target=ollama_call)
            thread.daemon = True
            thread.start()
            
            # 等待最多60秒
            thread.join(timeout=60)
            
            if thread.is_alive():
                print("\nOllama 调用超时，可能正在下载模型...")
            else:
                if result["error"]:
                    print(f"\nOllama 错误: {result['error']}")
                else:
                    print("\nOllama 对话完成")
        except Exception as e:
            print(f"\nOllama 调用出错: {e}")
            import traceback
            traceback.print_exc()
        
        # 测试 Agent 调用
        print("\n测试 Agent 调用...")
        start_time = time.time()
        print("等待响应...")
        print(f"使用模型: qwen2.5:0.5b")
        print("注意: 如果模型未下载，Ollama 会自动下载，这可能需要一些时间...")
        
        try:
            print("调用 agent.send_message...")
            response_generator = agent.send_message("你好，Hermes！")
            print("获取响应生成器...")
            for chunk in response_generator:
                print(f"获取到 chunk: {chunk}")
                if chunk.error:
                    print(f"\n错误: {chunk.error}")
                    break
                if chunk.delta:
                    print(chunk.delta, end="", flush=True)
                if chunk.done:
                    print("\n对话完成")
                    break
        except Exception as e:
            print(f"\n发送消息时出错: {e}")
            import traceback
            traceback.print_exc()
        
        elapsed = time.time() - start_time
        print(f"响应时间: {elapsed:.2f} 秒")
        
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
