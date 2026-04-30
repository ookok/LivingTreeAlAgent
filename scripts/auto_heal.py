import subprocess
import time
import os
import sys
import signal

class AutoHealer:
    def __init__(self, health_check_url="http://localhost:8000/health", check_interval=30):
        self.health_check_url = health_check_url
        self.check_interval = check_interval
        self.service_process = None
        self.running = True

    def check_health(self):
        try:
            result = subprocess.run(
                ['curl', '-f', '-s', '-m', '10', self.health_check_url],
                capture_output=True,
                timeout=15
            )
            return result.returncode == 0
        except Exception:
            return False

    def start_service(self):
        print("🔄 启动 LivingTreeAI 服务...")
        if sys.platform.startswith('win'):
            self.service_process = subprocess.Popen(
                [sys.executable, 'main.py', 'client'],
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
        else:
            self.service_process = subprocess.Popen(
                [sys.executable, 'main.py', 'client']
            )
        print(f"✅ 服务已启动 (PID: {self.service_process.pid})")

    def stop_service(self):
        if self.service_process:
            print("🛑 停止服务...")
            try:
                if sys.platform.startswith('win'):
                    subprocess.run(['taskkill', '/F', '/T', '/PID', str(self.service_process.pid)],
                                   capture_output=True)
                else:
                    os.kill(self.service_process.pid, signal.SIGTERM)
                    self.service_process.wait(timeout=10)
            except Exception as e:
                print(f"⚠️  停止服务时出错: {e}")
            self.service_process = None

    def run(self):
        print("🚀 LivingTreeAI 自动健康检测服务启动")
        print(f"📋 健康检查间隔: {self.check_interval}秒")
        print(f"📍 检查地址: {self.health_check_url}")
        print("按 Ctrl+C 停止监控")
        print("-" * 50)

        self.start_service()

        try:
            while self.running:
                time.sleep(self.check_interval)
                
                if not self.check_health():
                    print("❌ 检测到服务异常")
                    self.stop_service()
                    time.sleep(3)
                    self.start_service()
                else:
                    print(f"✅ 服务正常运行 (PID: {self.service_process.pid})")

        except KeyboardInterrupt:
            print("\n👋 收到停止信号")
            self.running = False
            self.stop_service()
            print("✅ 监控服务已停止")

if __name__ == "__main__":
    healer = AutoHealer()
    healer.run()