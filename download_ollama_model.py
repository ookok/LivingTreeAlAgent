# 下载 Ollama 模型
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath('.'))

from core.ollama_client import OllamaClient
from core.config import load_config

def download_model(model_name):
    """下载 Ollama 模型"""
    print(f"正在下载模型: {model_name}")
    
    # 加载配置
    config = load_config()
    client = OllamaClient(config.ollama)
    
    try:
        # 检查模型是否已存在
        existing_models = client.list_models()
        if any(m.name == model_name for m in existing_models):
            print(f"模型 {model_name} 已存在，跳过下载")
            return True
        
        # 下载模型（这里我们使用系统命令，因为 Ollama API 不直接支持下载）
        import subprocess
        
        print(f"执行命令: ollama pull {model_name}")
        result = subprocess.run(
            ["ollama", "pull", model_name],
            capture_output=True,
            text=True,
            cwd=os.getcwd()
        )
        
        if result.returncode == 0:
            print(f"✅ 模型 {model_name} 下载成功")
            return True
        else:
            print(f"❌ 模型 {model_name} 下载失败: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ 下载模型时出错: {e}")
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("Ollama 模型下载")
    print("=" * 60)
    
    # 下载 qwen3.5:2b 模型（较小，适合测试）
    success = download_model("qwen3.5:2b")
    
    if success:
        print("\n🎉 模型下载成功！")
        print("现在可以运行 test_ollama_agent_fixed.py 测试 Agent 功能")
    else:
        print("\n❌ 模型下载失败，请检查网络连接和 Ollama 服务状态")
    
    print("=" * 60)

if __name__ == "__main__":
    main()