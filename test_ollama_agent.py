# 测试本地ollama API服务和Agent初始化
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath('.'))

from core.config import load_config
from core.ollama_client import OllamaClient
from core.agent import HermesAgent

def test_ollama_connection():
    """测试Ollama API连接"""
    print("测试 Ollama API 连接...")
    
    # 加载配置
    config = load_config()
    print(f"配置加载成功: base_url={config.ollama.base_url}, model={config.ollama.default_model}")
    
    # 初始化Ollama客户端
    client = OllamaClient(config.ollama)
    
    # 测试API连接
    try:
        version = client.get_version()
        print(f"✅ Ollama API 连接成功: version={version}")
        return True
    except Exception as e:
        print(f"❌ Ollama API 连接失败: {e}")
        return False

def test_model_list():
    """测试模型列表"""
    print("\n测试模型列表...")
    
    # 加载配置
    config = load_config()
    client = OllamaClient(config.ollama)
    
    try:
        models = client.list_models()
        print(f"✅ 模型列表获取成功: {len(models)} 个模型")
        for model in models:
            print(f"  - {model['name']}")
        return True
    except Exception as e:
        print(f"❌ 模型列表获取失败: {e}")
        return False

def test_model_usage():
    """测试模型使用"""
    print("\n测试模型使用...")
    
    # 加载配置
    config = load_config()
    client = OllamaClient(config.ollama)
    
    try:
        # 测试简单的模型调用
        prompt = "你好，你是一个智能助手"
        response = client.chat([{"role": "user", "content": prompt}])
        print(f"✅ 模型调用成功")
        print(f"  输入: {prompt}")
        print(f"  输出: {response['message']['content'][:100]}...")
        return True
    except Exception as e:
        print(f"❌ 模型调用失败: {e}")
        return False

def test_agent_initialization():
    """测试Agent初始化"""
    print("\n测试 Agent 初始化...")
    
    try:
        # 加载配置
        config = load_config()
        
        # 初始化Agent
        agent = HermesAgent(config)
        print("✅ Agent 初始化成功")
        print(f"  模型: {config.ollama.default_model}")
        print(f"  工具集: {config.agent.enabled_toolsets}")
        
        # 测试Agent调用
        test_prompt = "解释什么是人工智能"
        print(f"\n测试 Agent 调用: {test_prompt}")
        
        # 使用流式输出
        for chunk in agent.stream(test_prompt):
            if chunk.choices and chunk.choices[0].delta:
                content = chunk.choices[0].delta.get("content", "")
                if content:
                    print(content, end="")
        print()
        
        print("✅ Agent 调用成功")
        return True
        
    except Exception as e:
        print(f"❌ Agent 初始化或调用失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    print("=" * 60)
    print("本地 Ollama API 服务测试")
    print("=" * 60)
    
    tests = [
        test_ollama_connection,
        test_model_list,
        test_model_usage,
        test_agent_initialization
    ]
    
    all_passed = True
    
    for test in tests:
        success = test()
        if not success:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 所有测试通过！本地 Ollama API 服务和 Agent 初始化正常")
    else:
        print("❌ 部分测试失败，请检查配置和服务状态")
    print("=" * 60)

if __name__ == "__main__":
    main()