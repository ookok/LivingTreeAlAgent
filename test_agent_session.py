#!/usr/bin/env python3
"""
测试 Agent 会话消息调用
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
_root = Path(__file__).parent
sys.path.insert(0, str(_root))

from core.agent import HermesAgent, AgentCallbacks
from core.config import AppConfig


def test_agent_session():
    """测试 Agent 会话消息调用"""
    print("=== 测试 Agent 会话消息 ===")
    
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
        print(f"会话 ID: {agent.session_id}")
        
        # 等待模型客户端初始化完成
        print("\n等待模型客户端初始化...")
        import time
        start_time = time.time()
        while not agent.ollama and not agent.model:
            if time.time() - start_time > 30:  # 增加超时时间到30秒
                print("模型客户端初始化超时")
                break
            time.sleep(1)
            print(f"等待中... {int(time.time() - start_time)}s")
            # 检查内部状态
            if hasattr(agent, '_priority_loader'):
                try:
                    backends = agent._priority_loader.check_backend_availability()
                    print(f"可用后端: {[b.name for b in backends if b.available]}")
                except Exception as e:
                    print(f"检查后端时出错: {e}")
        
        # 检查模型客户端状态
        print(f"Ollama 客户端: {agent.ollama}")
        print(f"本地模型: {agent.model}")
        print(f"当前后端: {getattr(agent, '_current_backend', 'None')}")
        print(f"_use_unified: {getattr(agent, '_use_unified', 'None')}")
        
        # 测试发送消息
        print("\n发送测试消息...")
        print("用户: 你好")
        
        # 测试直接调用Ollama客户端
        print("\n直接测试 Ollama 客户端...")
        try:
            from core.ollama_client import ChatMessage
            
            # 测试后端健康检查
            print("测试后端健康检查...")
            is_online = False
            
            # 根据后端类型调用不同的方法
            if hasattr(agent.model, 'ping'):
                # Ollama 后端
                try:
                    is_online = agent.model.ping()
                    print(f"后端在线: {is_online}")
                    
                    if is_online and hasattr(agent.model, 'version'):
                        version = agent.model.version()
                        print(f"Ollama 版本: {version}")
                        
                        # 测试模型列表
                        if hasattr(agent.model, 'list_models'):
                            models = agent.model.list_models()
                            print(f"可用模型数量: {len(models)}")
                            for model in models:
                                print(f"  - {model.name}")
                            
                            # 检查是否有可用模型
                            if not models:
                                print("\n⚠️  未找到可用模型，请先下载模型")
                                print("你可以使用以下命令下载模型:")
                                print("  ollama pull llama2")
                                print("  ollama pull gemma:2b")
                                print("  ollama pull qwen2.5:0.5b")
                                print("\n请下载模型后再运行测试")
                            else:
                                # 使用第一个可用模型
                                model_name = models[0].name
                                print(f"\n使用模型: {model_name}")
                                print("发送消息到后端...")
                                
                                # 测试聊天
                                messages = [ChatMessage(role="user", content="你好")]
                                
                                # 直接测试chat方法
                                try:
                                    for chunk in agent.model.chat(messages, model=model_name):
                                        print(f"\n后端响应: {chunk}")
                                        if chunk.error:
                                            print(f"\n后端错误: {chunk.error}")
                                            break
                                        if chunk.delta:
                                            print(f"后端消息: {chunk.delta}")
                                        if chunk.done:
                                            print("\n后端对话完成")
                                            break
                                except Exception as e:
                                    print(f"聊天测试出错: {e}")
                                    import traceback
                                    traceback.print_exc()
                except Exception as e:
                    print(f"健康检查出错: {e}")
            else:
                # 其他后端
                print("使用非 Ollama 后端，跳过健康检查")
                is_online = True
            
            if not is_online:
                print("\n❌  后端服务未运行，请启动服务后再测试")
        except Exception as e:
            print(f"\nOllama 调用出错: {e}")
            import traceback
            traceback.print_exc()
        
        # 测试 Agent 调用
        print("\n测试 Agent 调用...")
        print("Agent: ", end="")
        try:
            response = agent.send_message("你好")
            print(f"\n获取响应生成器: {response}")
            print("开始迭代响应...")
            for i, chunk in enumerate(response):
                print(f"\n收到 chunk {i}: {chunk}")
                if chunk.error:
                    print(f"\n错误: {chunk.error}")
                    break
                if chunk.delta:
                    print(f"收到内容: {chunk.delta}")
                    print(chunk.delta, end="", flush=True)
                if chunk.done:
                    print("\n对话完成")
                    break
        except Exception as e:
            print(f"\n发送消息时出错: {e}")
            import traceback
            traceback.print_exc()
        
        # 测试第二次消息
        print("\n发送第二次消息...")
        print("用户: 你是谁？")
        
        print("Agent: ", end="")
        for chunk in agent.send_message("你是谁？"):
            if chunk.error:
                print(f"\n错误: {chunk.error}")
                break
            if chunk.delta:
                print(chunk.delta, end="", flush=True)
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
    test_agent_session()
