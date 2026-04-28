"""
测试命令面板功能
"""

import sys
import os

# 添加 client/src 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'client', 'src'))

# 导入命令面板
from presentation.components.command_palette import (
    CommandPalette,
    Command,
    CommandCategory
)


class TestCommandPalette:
    """命令面板测试"""
    
    def test_default_commands(self):
        """测试默认命令加载"""
        palette = CommandPalette()
        
        commands = palette.get_all_commands()
        assert len(commands) > 0
        
        # 检查常用命令是否存在
        shortcuts = [cmd["shortcut"] for cmd in commands]
        assert "/analyze" in shortcuts
        assert "/report" in shortcuts
        assert "/search" in shortcuts
        assert "/help" in shortcuts
    
    def test_parse_command(self):
        """测试命令解析"""
        palette = CommandPalette()
        
        # 测试简单命令
        parsed = palette.parse_command("/analyze")
        assert parsed is not None
        assert parsed["shortcut"] == "/analyze"
        
        # 测试带参数命令
        parsed = palette.parse_command("/search query=test")
        assert parsed is not None
        assert parsed["parameters"].get("query") == "test"
        
        # 测试无效命令
        parsed = palette.parse_command("/unknown_command")
        assert parsed is None
        
        # 测试非命令输入
        parsed = palette.parse_command("普通文本")
        assert parsed is None
    
    def test_execute_command(self):
        """测试命令执行"""
        palette = CommandPalette()
        
        # 执行简单命令
        result = palette.execute_command("/help")
        assert result is not None
        assert result["command"] == "帮助"
        
        # 执行带参数命令
        result = palette.execute_command("/search query=python")
        assert result is not None
        assert result["command"] == "搜索"
        assert result["args"]["query"] == "python"
    
    def test_command_suggestions(self):
        """测试命令建议"""
        palette = CommandPalette()
        
        # 测试前缀匹配
        suggestions = palette.suggest_commands("/ana")
        assert len(suggestions) > 0
        assert any(s["shortcut"] == "/analyze" for s in suggestions)
        
        # 测试完全匹配
        suggestions = palette.suggest_commands("/search")
        assert len(suggestions) == 1
        assert suggestions[0]["shortcut"] == "/search"
        
        # 测试无匹配
        suggestions = palette.suggest_commands("/xyz")
        assert len(suggestions) == 0
    
    def test_register_custom_command(self):
        """测试注册自定义命令"""
        palette = CommandPalette()
        
        def custom_handler(**kwargs):
            return {"custom": True, "args": kwargs}
        
        custom_cmd = Command(
            name="自定义命令",
            description="测试自定义命令",
            category=CommandCategory.OTHER,
            shortcut="/custom",
            handler=custom_handler
        )
        
        palette.register_command(custom_cmd)
        
        # 验证命令已注册
        commands = palette.get_all_commands()
        shortcuts = [cmd["shortcut"] for cmd in commands]
        assert "/custom" in shortcuts
        
        # 执行自定义命令
        result = palette.execute_command("/custom")
        assert result is not None
        assert result["custom"] is True
    
    def test_unregister_command(self):
        """测试注销命令"""
        palette = CommandPalette()
        
        # 注销命令
        result = palette.unregister_command("/clear")
        assert result is True
        
        # 验证命令已注销
        commands = palette.get_all_commands()
        shortcuts = [cmd["shortcut"] for cmd in commands]
        assert "/clear" not in shortcuts
    
    def test_command_history(self):
        """测试命令历史"""
        palette = CommandPalette()
        
        # 执行命令
        palette.execute_command("/help")
        palette.execute_command("/search query=test")
        
        # 检查历史记录
        history = palette.get_command_history()
        assert len(history) == 2
        assert "/search query=test" in history
        assert "/help" in history
        
        # 清空历史
        palette.clear_history()
        history = palette.get_command_history()
        assert len(history) == 0
    
    def test_set_command_handler(self):
        """测试设置命令处理器"""
        palette = CommandPalette()
        
        called = []
        
        def new_handler(**kwargs):
            called.append(True)
            return {"custom_handler": True}
        
        # 设置新处理器
        result = palette.set_command_handler("/help", new_handler)
        assert result is True
        
        # 执行命令
        result = palette.execute_command("/help")
        assert result["custom_handler"] is True
        assert len(called) == 1
    
    def test_get_commands_by_category(self):
        """测试按类别获取命令"""
        palette = CommandPalette()
        
        # 获取分析类命令
        analysis_cmds = palette.get_commands_by_category(CommandCategory.ANALYSIS)
        assert len(analysis_cmds) > 0
        
        # 获取搜索类命令
        search_cmds = palette.get_commands_by_category(CommandCategory.SEARCH)
        assert len(search_cmds) > 0
        
        # 验证类别
        for cmd in analysis_cmds:
            assert cmd.category == CommandCategory.ANALYSIS


if __name__ == "__main__":
    pytest.main([__file__, "-v"])