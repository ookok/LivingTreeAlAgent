import json
import os

CONFIG_PATH = 'config/user_config.json'

DEFAULT_CONFIG = {
    "ollama_url": "http://localhost:11434",
    "default_model": "llama3",
    "theme": "light",
    "auto_update": True,
    "auto_heal": True,
    "log_level": "info"
}

class ConfigWizard:
    def __init__(self):
        self.config = DEFAULT_CONFIG.copy()

    def run(self):
        print("👋 欢迎使用 LivingTreeAI！")
        print("请回答几个简单问题，我来帮您配置。")
        print("-" * 50)

        self.config["ollama_url"] = self._prompt(
            "Ollama 服务地址",
            DEFAULT_CONFIG["ollama_url"]
        )

        self.config["default_model"] = self._prompt(
            "默认使用的模型",
            DEFAULT_CONFIG["default_model"]
        )

        self.config["theme"] = self._prompt(
            "界面主题 (light/dark)",
            DEFAULT_CONFIG["theme"],
            validator=lambda x: x in ["light", "dark"]
        )

        self.config["auto_update"] = self._prompt_yes_no(
            "是否启用自动更新检测",
            DEFAULT_CONFIG["auto_update"]
        )

        self.config["auto_heal"] = self._prompt_yes_no(
            "是否启用自动故障恢复",
            DEFAULT_CONFIG["auto_heal"]
        )

        self._save_config()
        print("-" * 50)
        print("✅ 配置完成！")
        return self.config

    def _prompt(self, message, default, validator=None):
        while True:
            value = input(f"{message} (默认: {default}): ").strip() or default
            if validator and not validator(value):
                print(f"❌ 无效输入，请重新输入")
                continue
            return value

    def _prompt_yes_no(self, message, default):
        yes_no = "Y" if default else "N"
        while True:
            value = input(f"{message} (Y/N, 默认: {yes_no}): ").strip().upper() or yes_no
            if value in ["Y", "N"]:
                return value == "Y"
            print("❌ 请输入 Y 或 N")

    def _save_config(self):
        os.makedirs('config', exist_ok=True)
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
        print(f"📝 配置已保存到 {CONFIG_PATH}")

    @staticmethod
    def load_config():
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return {**DEFAULT_CONFIG, **config}
            except Exception:
                return DEFAULT_CONFIG.copy()
        return DEFAULT_CONFIG.copy()

    @staticmethod
    def exists():
        return os.path.exists(CONFIG_PATH)

if __name__ == "__main__":
    wizard = ConfigWizard()
    wizard.run()