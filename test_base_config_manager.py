#!/usr/bin/env python3
"""验证 BaseConfigManager 独立工作（字典模式）"""
import sys
sys.path.insert(0, "client/src")

from pathlib import Path
from client.src.business.base_config_manager import BaseConfigManager

# 字典模式子类
class MyConfigManager(BaseConfigManager):
    def _init_default_config(self):
        return {
            "version": "1.0.0",
            "modules": {
                "deep_search": {"enabled": True, "rate": 0.003},
                "creation": {"enabled": True, "rate": 0.003},
            },
            "payment": {"enabled": False},
        }
    
    def validate(self):
        data = self._get_config_data()
        if data and data.get("version") == "":
            return False
        return True

# 测试 1: 默认配置
mgr = MyConfigManager(config_path=Path("test_config_tmp.json"))
default = mgr._get_config_data()
assert default is not None, "默认配置不应为 None"
assert default["version"] == "1.0.0", f"版本错误: {default['version']}"
print("[PASS] 测试1: 默认配置加载")

# 测试 2: 点路径 get
val = mgr.get("modules.deep_search.enabled")
assert val == True, f"点路径读取失败: {val}"
print("[PASS] 测试2: 点路径 get")

# 测试 3: 点路径 set
mgr.set("modules.deep_search.enabled", False)
val = mgr.get("modules.deep_search.enabled")
assert val == False, f"点路径写入失败: {val}"
print("[PASS] 测试3: 点路径 set")

# 测试 4: save/load
mgr.save()
mgr2 = MyConfigManager(config_path=Path("test_config_tmp.json"))
mgr2.load()
val = mgr2.get("modules.deep_search.enabled")
assert val == False, f"保存/加载失败: {val}"
print("[PASS] 测试4: save/load")

# 测试 5: YAML 格式（如果 pyyaml 可用）
try:
    import yaml
    mgr3 = MyConfigManager(config_path=Path("test_config_tmp.yaml"))
    mgr3.save()
    print("[PASS] 测试5: YAML 保存")
except ImportError:
    print("[SKIP] 测试5: YAML（pyyaml 未安装）")

# 清理
import os
for f in ["test_config_tmp.json", "test_config_tmp.yaml"]:
    if os.path.exists(f):
        os.remove(f)

print("\n[OK] BaseConfigManager 验证通过")
