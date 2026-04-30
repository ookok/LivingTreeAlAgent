import subprocess
import json
import os

class ModelManager:
    def __init__(self, ollama_url="http://localhost:11434"):
        self.ollama_url = ollama_url

    def is_ollama_running(self):
        try:
            result = subprocess.run(
                ['curl', '-f', '-s', '-m', '5', f'{self.ollama_url}/api/tags'],
                capture_output=True
            )
            return result.returncode == 0
        except Exception:
            return False

    def list_models(self):
        try:
            result = subprocess.run(
                ['curl', '-s', '-m', '10', f'{self.ollama_url}/api/tags'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return data.get('models', [])
            return []
        except Exception:
            return []

    def is_model_installed(self, model_name):
        models = self.list_models()
        return any(model.get('name', '').startswith(model_name) for model in models)

    def pull_model(self, model_name):
        print(f"📥 开始下载模型: {model_name}")
        try:
            result = subprocess.run(
                ['ollama', 'pull', model_name],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print(f"✅ {model_name} 下载完成")
                return True
            else:
                print(f"❌ 下载失败: {result.stderr}")
                return False
        except FileNotFoundError:
            print("❌ 未找到 ollama 命令，请先安装 Ollama")
            return False
        except Exception as e:
            print(f"❌ 下载异常: {e}")
            return False

    def ensure_model(self, model_name):
        if not self.is_ollama_running():
            print("⚠️  Ollama 服务未启动，请先启动 Ollama")
            return False

        if self.is_model_installed(model_name):
            print(f"✅ 模型 {model_name} 已安装")
            return True

        print(f"📦 模型 {model_name} 未安装，正在下载...")
        return self.pull_model(model_name)

    def run(self, model_name):
        return self.ensure_model(model_name)

if __name__ == "__main__":
    import sys
    model_name = sys.argv[1] if len(sys.argv) > 1 else "llama3"
    
    manager = ModelManager()
    manager.run(model_name)