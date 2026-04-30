import subprocess
import os
import sys

class AutoUpdater:
    def __init__(self):
        self.has_git = self._check_git()

    def _check_git(self):
        try:
            result = subprocess.run(['git', '--version'], capture_output=True)
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def check_updates(self):
        if not self.has_git:
            return False, 0, "Git 未安装"

        try:
            subprocess.run(['git', 'fetch', '--quiet'], capture_output=True)
            result = subprocess.run(
                ['git', 'rev-list', '--count', 'HEAD..origin/master'],
                capture_output=True,
                text=True
            )
            updates = int(result.stdout.strip())
            return True, updates, "检查完成"
        except Exception as e:
            return False, 0, str(e)

    def get_current_version(self):
        if not self.has_git:
            return "未知 (Git未安装)"
        
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--short', 'HEAD'],
                capture_output=True,
                text=True
            )
            return result.stdout.strip()
        except Exception:
            return "未知"

    def apply_update(self):
        if not self.has_git:
            return False, "Git 未安装"

        try:
            print("📥 拉取最新代码...")
            result = subprocess.run(['git', 'pull', '--quiet'], capture_output=True)
            if result.returncode != 0:
                return False, f"拉取失败: {result.stderr.decode()}"

            print("📦 更新依赖...")
            subprocess.run([sys.executable, '-m', 'pip', 'install', '-e', 'client/', '-e', 'server/relay_server/', '-q'],
                          capture_output=True)

            return True, "更新完成"
        except Exception as e:
            return False, str(e)

    def run(self, auto_apply=False):
        print("🔍 检查更新...")
        
        success, updates, message = self.check_updates()
        
        if not success:
            print(f"⚠️  检查失败: {message}")
            return

        current_version = self.get_current_version()
        print(f"📊 当前版本: {current_version}")

        if updates == 0:
            print("✅ 当前已是最新版本")
            return True, "已是最新版本"

        print(f"📥 发现 {updates} 个更新")

        if auto_apply:
            return self.apply_update()
        else:
            try:
                response = input("是否更新? (Y/N): ").strip().upper()
                if response == 'Y':
                    return self.apply_update()
                else:
                    return True, "用户跳过更新"
            except KeyboardInterrupt:
                return True, "用户取消"

if __name__ == "__main__":
    updater = AutoUpdater()
    success, message = updater.run()
    print(message)