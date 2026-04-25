"""
PyQt6测试指挥官测试
"""

import pytest
import asyncio
from pyqt6_test_commander import (
    AITestCommander,
    TestTask,
    ExternalAppController,
    ScreenMonitor,
    TestExecutor,
    TaskPriority
)


class TestAITestCommander:
    """AI测试指挥官测试"""
    
    def setup_method(self):
        self.commander = AITestCommander()
        
    def test_add_task(self):
        """测试添加任务"""
        task = self.commander.add_task(
            description="测试登录功能",
            target_app="app.exe",
            priority=TaskPriority.HIGH
        )
        
        assert task is not None
        assert task.priority == TaskPriority.HIGH
        
    def test_get_status(self):
        """测试获取状态"""
        status = self.commander.get_task_status()
        
        assert 'total' in status
        assert 'pending' in status


class TestExternalAppController:
    """外部应用控制器测试"""
    
    def setup_method(self):
        self.controller = ExternalAppController()
        
    def test_connect_app(self):
        """测试连接应用"""
        result = self.controller.connect_app("desktop", "./app.exe")
        assert result is True
        
    def test_execute_click(self):
        """测试点击动作"""
        from pyqt6_test_commander.external_controller import ControlAction
        
        action = ControlAction(
            action_type='click',
            target='button1',
            parameters={'position': {'x': 100, 'y': 200}}
        )
        
        result = self.controller.execute_action(action)
        assert result['success'] is True


class TestScreenMonitor:
    """屏幕监控器测试"""
    
    def setup_method(self):
        self.monitor = ScreenMonitor()
        
    def test_capture_screen(self):
        """测试截图"""
        screenshot = self.monitor.capture_screen()
        assert screenshot is not None


class TestTestExecutor:
    """测试执行器测试"""
    
    def setup_method(self):
        self.executor = TestExecutor()
        
    def test_execute_test(self):
        """测试执行"""
        steps = [
            {'action': 'click', 'target': 'button1'},
            {'action': 'wait', 'duration': 1},
        ]
        
        result = self.executor.execute_test(steps)
        assert result.status.value in ['passed', 'failed']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
