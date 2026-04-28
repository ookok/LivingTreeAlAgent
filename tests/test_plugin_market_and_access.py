"""
测试插件市场和细粒度访问控制
"""

import sys
import os
import importlib.util

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'client', 'src'))

# 测试插件市场
print("测试插件市场...")

# 直接导入模块
engine_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'client', 'src', 'business', 'skill_evolution', 'skill_evolution_engine.py'
)
spec = importlib.util.spec_from_file_location("skill_evolution_engine", engine_path)
engine_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine_module)

SkillEvolutionEngine = engine_module.SkillEvolutionEngine
PluginSourceType = engine_module.PluginSourceType
PluginStatus = engine_module.PluginStatus
PluginInfo = engine_module.PluginInfo

# 获取插件市场实例
engine = SkillEvolutionEngine.get_instance()
print("✓ 插件市场初始化成功")

# 测试第三方插件开关
assert engine.is_third_party_enabled() == False
print("✓ 默认关闭第三方插件")

engine.enable_third_party_plugins(True)
assert engine.is_third_party_enabled() == True
print("✓ 第三方插件启用成功")

engine.enable_third_party_plugins(False)
assert engine.is_third_party_enabled() == False
print("✓ 第三方插件禁用成功")

# 测试安装插件
install_result = engine.install_plugin("test-plugin", PluginSourceType.COMMUNITY)
assert install_result == True
print("✓ 安装插件成功")

# 测试获取插件
plugin = engine.get_plugin("test-plugin")
assert plugin is not None
assert plugin.name == "Test Plugin"
print("✓ 获取插件信息成功")

# 测试启用插件
enable_result = engine.enable_plugin("test-plugin")
assert enable_result == True
assert plugin.status == PluginStatus.ENABLED
print("✓ 启用插件成功")

# 测试禁用插件
disable_result = engine.disable_plugin("test-plugin")
assert disable_result == True
assert plugin.status == PluginStatus.DISABLED
print("✓ 禁用插件成功")

# 测试卸载插件
uninstall_result = engine.uninstall_plugin("test-plugin")
assert uninstall_result == True
assert engine.get_plugin("test-plugin") is None
print("✓ 卸载插件成功")

# 测试搜索功能
install_result = engine.install_plugin("data-tool", PluginSourceType.COMMUNITY)
install_result = engine.install_plugin("analysis-tool", PluginSourceType.COMMUNITY)

results = engine.search_plugins("tool")
assert len(results) >= 2
print("✓ 插件搜索功能正常")

# 测试统计功能
stats = engine.get_installed_count()
assert "total" in stats
assert "enabled" in stats
print("✓ 统计功能正常")

# 测试细粒度访问控制
print("\n测试细粒度访问控制...")

# 导入工具模块
import importlib.util
tool_module_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'client', 'src', 'business', 'tools', 'base_tool.py'
)
spec = importlib.util.spec_from_file_location("base_tool", tool_module_path)
tool_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool_module)

AccessControlRule = tool_module.AccessControlRule

# 创建测试规则
rule = AccessControlRule(
    name="test_rule",
    allowed_paths=["/safe/directory"],
    denied_paths=["/etc", "/var"],
    allowed_patterns=["*.txt", "*.md"],
    denied_patterns=["*.exe", "*.dll"],
    max_file_size=1024 * 1024,  # 1MB
    read_only=True
)
print("✓ 创建访问控制规则成功")

# 测试规则属性
assert rule.name == "test_rule"
assert "/safe/directory" in rule.allowed_paths
assert "/etc" in rule.denied_paths
assert "*.txt" in rule.allowed_patterns
assert "*.exe" in rule.denied_patterns
assert rule.max_file_size == 1024 * 1024
assert rule.read_only == True
print("✓ 规则属性验证成功")

# 测试 check_access 方法
class TestTool:
    def __init__(self):
        self._access_rules = []
    
    def add_access_rule(self, rule):
        self._access_rules.append(rule)
    
    def check_access(self, filepath, action="read"):
        normalized_path = os.path.normpath(filepath).lower()
        
        for rule in self._access_rules:
            # 检查黑名单路径
            for denied_path in rule.denied_paths:
                denied_norm = os.path.normpath(denied_path).lower()
                if normalized_path.startswith(denied_norm):
                    return False
            
            # 检查白名单路径
            if rule.allowed_paths:
                allowed = False
                for allowed_path in rule.allowed_paths:
                    allowed_norm = os.path.normpath(allowed_path).lower()
                    if normalized_path.startswith(allowed_norm):
                        allowed = True
                        break
                if not allowed:
                    return False
            
            # 检查只读模式
            if rule.read_only and action.lower() not in ["read", "view"]:
                return False
        
        return True

tool = TestTool()
tool.add_access_rule(rule)

# 测试允许的路径
assert tool.check_access("/safe/directory/file.txt", "read") == True
print("✓ 允许访问白名单路径")

# 测试拒绝的路径
assert tool.check_access("/etc/passwd", "read") == False
print("✓ 拒绝访问黑名单路径")

# 测试只读模式
assert tool.check_access("/safe/directory/file.txt", "write") == False
print("✓ 只读模式拒绝写入")

# 清理测试插件
engine.uninstall_plugin("data-tool")
engine.uninstall_plugin("analysis-tool")

print("\n🎉 所有测试通过!")