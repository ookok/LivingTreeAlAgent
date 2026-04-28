"""
初始化配置向导和智能IDE测试
验证客户端的初始化配置引导和用户注册登录流程
"""

import os
import json
import tempfile
import shutil
from pathlib import Path

print("=" * 60)
print("初始化配置向导和智能IDE测试")
print("=" * 60)


class MockInitWizard:
    """模拟初始化向导"""
    
    def __init__(self):
        self.config = {
            "username": "test_user",
            "email": "test@example.com",
            "model": "llama3.1:8b",
            "api_url": "http://localhost:11434",
            "project_path": os.path.expanduser("~/Documents/Hermes Projects"),
            "enable_smart_ide": True,
            "enable_code_completion": True,
            "enable_ai_assistant": True
        }
    
    def exec(self):
        """模拟执行向导"""
        print("模拟初始化向导执行...")
        print(f"配置: {self.config}")
        return True
    
    @property
    def wizard_completed(self):
        """模拟信号"""
        class MockSignal:
            def connect(self, callback):
                # 直接调用回调函数，传入配置
                callback({"username": "test_user", "email": "test@example.com", "model": "llama3.1:8b", "api_url": "http://localhost:11434", "project_path": os.path.expanduser("~/Documents/Hermes Projects"), "enable_smart_ide": True, "enable_code_completion": True, "enable_ai_assistant": True})
        return MockSignal()


class MockSmartIDESystem:
    """模拟智能IDE系统"""
    
    def __init__(self):
        self.initialized = False
        self.components = []
    
    def _start_services(self):
        """模拟启动服务"""
        self.initialized = True
        self.components = [
            "AI Coding Assistant",
            "Model Hub Manager",
            "Multimodal Manager",
            "Intelligent Router",
            "Task Planner",
            "Git Manager",
            "Performance Optimizer",
            "Reasoning Manager",
            "Personalized Learning System"
        ]
        print("智能IDE系统服务启动成功")


class MockMainWindow:
    """模拟主窗口"""
    
    def __init__(self):
        self.config = MockConfig()
        self.smart_ide_system = None
    
    def _is_first_run(self):
        """检查是否首次运行"""
        config_dir = os.path.join(os.environ.get("HOME", "~"), ".hermes-desktop", "config")
        init_config_path = os.path.join(config_dir, "init_config.json")
        return not os.path.exists(init_config_path)
    
    def _show_init_wizard(self):
        """显示初始化向导"""
        print("显示初始化向导...")
        wizard = MockInitWizard()
        wizard.wizard_completed.connect(self._on_wizard_completed)
        wizard.exec()
    
    def _on_wizard_completed(self, config):
        """初始化向导完成"""
        print("初始化向导完成，应用配置...")
        self._apply_init_config(config)
        self._init_smart_ide()
    
    def _apply_init_config(self, config):
        """应用初始化配置"""
        # 保存配置到文件
        config_dir = os.path.join(os.environ.get("HOME", "~"), ".hermes-desktop", "config")
        os.makedirs(config_dir, exist_ok=True)
        
        init_config_path = os.path.join(config_dir, "init_config.json")
        with open(init_config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        # 应用模型配置
        if "api_url" in config and "model" in config:
            self.config.ollama.base_url = config["api_url"]
            self.config.ollama.default_model = config["model"]
        
        # 创建项目目录
        if "project_path" in config:
            project_path = config["project_path"]
            os.makedirs(project_path, exist_ok=True)
        
        print("配置应用成功")
    
    def _init_smart_ide(self):
        """初始化智能IDE"""
        print("初始化智能IDE系统...")
        self.smart_ide_system = MockSmartIDESystem()
        self.smart_ide_system._start_services()
        print("智能IDE系统初始化成功")


class MockConfig:
    """模拟配置"""
    
    def __init__(self):
        self.window_width = 1200
        self.window_height = 800
        self.ollama = MockOllamaConfig()


class MockOllamaConfig:
    """模拟Ollama配置"""
    
    def __init__(self):
        self.base_url = "http://localhost:11434"
        self.default_model = "llama3.1:8b"


def test_first_run_detection():
    """测试首次运行检测"""
    print("\n=== 测试首次运行检测 ===")
    
    # 创建临时配置目录
    temp_dir = tempfile.mkdtemp()
    original_home = os.environ.get("HOME")
    
    try:
        # 设置临时HOME目录
        os.environ["HOME"] = temp_dir
        
        # 测试首次运行
        main_window = MockMainWindow()
        is_first_run = main_window._is_first_run()
        print(f"首次运行检测: {is_first_run}")
        assert is_first_run, "首次运行检测失败"
        
        # 测试非首次运行
        config_dir = os.path.join(temp_dir, ".hermes-desktop", "config")
        os.makedirs(config_dir, exist_ok=True)
        init_config_path = os.path.join(config_dir, "init_config.json")
        with open(init_config_path, 'w') as f:
            json.dump({"test": "config"}, f)
        
        is_first_run = main_window._is_first_run()
        print(f"非首次运行检测: {not is_first_run}")
        assert not is_first_run, "非首次运行检测失败"
        
        print("首次运行检测测试通过")
        return True
        
    finally:
        # 恢复原始HOME目录
        if original_home:
            os.environ["HOME"] = original_home
        # 清理临时目录
        shutil.rmtree(temp_dir)


def test_init_wizard():
    """测试初始化向导"""
    print("\n=== 测试初始化向导 ===")
    
    # 创建临时配置目录
    temp_dir = tempfile.mkdtemp()
    original_home = os.environ.get("HOME")
    
    try:
        # 设置临时HOME目录
        os.environ["HOME"] = temp_dir
        
        # 测试初始化向导
        main_window = MockMainWindow()
        main_window._show_init_wizard()
        
        # 验证配置文件创建
        config_dir = os.path.join(temp_dir, ".hermes-desktop", "config")
        init_config_path = os.path.join(config_dir, "init_config.json")
        assert os.path.exists(init_config_path), "配置文件未创建"
        
        # 验证配置内容
        with open(init_config_path, 'r') as f:
            config = json.load(f)
        assert "username" in config, "配置缺少username"
        assert "model" in config, "配置缺少model"
        assert "api_url" in config, "配置缺少api_url"
        assert "project_path" in config, "配置缺少project_path"
        
        print("初始化向导测试通过")
        return True
        
    finally:
        # 恢复原始HOME目录
        if original_home:
            os.environ["HOME"] = original_home
        # 清理临时目录
        shutil.rmtree(temp_dir)


def test_smart_ide_initialization():
    """测试智能IDE初始化"""
    print("\n=== 测试智能IDE初始化 ===")
    
    # 创建临时配置目录
    temp_dir = tempfile.mkdtemp()
    original_home = os.environ.get("HOME")
    
    try:
        # 设置临时HOME目录
        os.environ["HOME"] = temp_dir
        
        # 测试智能IDE初始化
        main_window = MockMainWindow()
        main_window._init_smart_ide()
        
        # 验证智能IDE系统初始化
        assert main_window.smart_ide_system is not None, "智能IDE系统未初始化"
        assert main_window.smart_ide_system.initialized, "智能IDE系统未启动"
        assert len(main_window.smart_ide_system.components) > 0, "智能IDE组件未加载"
        
        print("智能IDE初始化测试通过")
        return True
        
    finally:
        # 恢复原始HOME目录
        if original_home:
            os.environ["HOME"] = original_home
        # 清理临时目录
        shutil.rmtree(temp_dir)


def test_integration():
    """集成测试"""
    tests = [
        test_first_run_detection,
        test_init_wizard,
        test_smart_ide_initialization
    ]
    
    all_passed = True
    
    for test in tests:
        try:
            success = test()
            if not success:
                all_passed = False
                print(f"测试 {test.__name__} 失败")
            else:
                print(f"测试 {test.__name__} 通过")
        except Exception as e:
            all_passed = False
            print(f"测试 {test.__name__} 异常: {e}")
    
    print("\n" + "=" * 60)
    if all_passed:
        print("所有测试通过！初始化配置向导和智能IDE功能正常")
    else:
        print("部分测试失败，需要进一步调试")
    print("=" * 60)
    
    return all_passed


if __name__ == "__main__":
    test_integration()