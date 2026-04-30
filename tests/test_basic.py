# -*- coding: utf-8 -*-
"""
基础功能测试
验证项目的基本导入和核心功能
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestBasicImports:
    """测试基本导入功能"""
    
    def test_config_import(self):
        """测试配置系统导入"""
        from client.src.business.nanochat_config import config
        assert config is not None
        assert hasattr(config, 'ollama')
    
    def test_event_bus_import(self):
        """测试事件总线导入"""
        from client.src.business.shared.event_bus import EventBus, get_event_bus
        event_bus = get_event_bus()
        assert event_bus is not None
    
    def test_logger_import(self):
        """测试日志系统导入"""
        from client.src.business.logger import logger
        assert logger is not None
    
    def test_config_wizard_import(self):
        """测试配置向导导入"""
        from scripts.config_wizard import ConfigWizard
        wizard = ConfigWizard()
        assert wizard is not None
    
    def test_check_import(self):
        """测试检查工具导入"""
        from scripts.check import EnvironmentChecker
        checker = EnvironmentChecker()
        assert checker is not None
    
    def test_model_manager_import(self):
        """测试模型管理器导入"""
        from scripts.model_manager import ModelManager
        manager = ModelManager()
        assert manager is not None
    
    def test_auto_update_import(self):
        """测试自动更新导入"""
        from scripts.auto_update import AutoUpdater
        updater = AutoUpdater()
        assert updater is not None


class TestMainEntry:
    """测试主入口"""
    
    def test_main_module_exists(self):
        """测试主模块存在"""
        assert os.path.exists('main.py')
    
    def test_client_main_exists(self):
        """测试客户端主模块存在"""
        assert os.path.exists('client/src/main.py')
    
    def test_run_scripts_exists(self):
        """测试启动脚本存在"""
        assert os.path.exists('run.bat')
        assert os.path.exists('run.sh')


class TestConfigSystem:
    """测试配置系统"""
    
    def test_default_config(self):
        """测试默认配置"""
        from scripts.config_wizard import ConfigWizard
        config = ConfigWizard.load_config()
        assert config['ollama_url'] == 'http://localhost:11434'
        assert 'default_model' in config
        assert config['theme'] == 'light'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])