import os
import sys
import subprocess

class EnvironmentChecker:
    def __init__(self):
        self.checks = [
            ("Python 版本", self._check_python),
            ("客户端代码", self._check_client_code),
            ("配置文件", self._check_config),
            ("Ollama 连接", self._check_ollama),
            ("依赖安装", self._check_dependencies),
            ("Git 安装", self._check_git),
        ]
        self.results = []

    def _check_python(self):
        if sys.version_info >= (3, 11):
            return True, f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        return False, f"需要 Python 3.11+，当前版本: {sys.version_info.major}.{sys.version_info.minor}"

    def _check_client_code(self):
        client_main = os.path.join('client', 'src', 'main.py')
        if os.path.exists(client_main):
            return True, "客户端代码存在"
        return False, f"缺少 {client_main}"

    def _check_config(self):
        config_files = ['config/config.yaml', 'config/unified.yaml']
        exists = [f for f in config_files if os.path.exists(f)]
        if exists:
            return True, f"配置文件: {', '.join(exists)}"
        return False, "缺少配置文件"

    def _check_ollama(self):
        try:
            result = subprocess.run(
                ['curl', '-f', '-s', '-m', '5', 'http://localhost:11434/api/tags'],
                capture_output=True
            )
            if result.returncode == 0:
                return True, "Ollama 连接正常"
            return False, "Ollama 服务未启动或不可达"
        except Exception:
            return False, "无法检查 Ollama (curl 未安装)"

    def _check_dependencies(self):
        try:
            sys.path.insert(0, 'client/src')
            from business.config import UnifiedConfig
            return True, "核心依赖已安装"
        except ImportError as e:
            return False, f"缺少依赖: {e}"

    def _check_git(self):
        try:
            result = subprocess.run(['git', '--version'], capture_output=True)
            return result.returncode == 0, "Git 已安装"
        except FileNotFoundError:
            return False, "Git 未安装"

    def run(self):
        print("🔍 LivingTreeAI 环境自检")
        print("=" * 50)

        all_passed = True
        for name, check_func in self.checks:
            try:
                passed, message = check_func()
                self.results.append((name, passed, message))
                
                if passed:
                    print(f"✅ {name}: {message}")
                else:
                    print(f"❌ {name}: {message}")
                    all_passed = False
            except Exception as e:
                print(f"⚠️  {name}: 检查异常 - {e}")
                all_passed = False

        print("=" * 50)
        if all_passed:
            print("🎉 所有检查通过！可以启动应用")
            return True
        else:
            print("⚠️  部分检查未通过，请根据提示修复")
            return False

if __name__ == "__main__":
    checker = EnvironmentChecker()
    checker.run()