"""
Nanochat 风格配置系统 - 演示脚本
======================================

展示新配置系统的使用方法。

作者: LivingTree AI Team
日期: 2026-04-25
"""

import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from client.src.business.nanochat_config import config, NanochatConfig


def demo_basic_access():
    """演示 1: 基本访问"""
    print("=" * 60)
    print("演示 1: 基本访问（像访问属性一样简单）")
    print("=" * 60)
    
    # 读取配置
    print(f"Ollama URL: {config.ollama.url}")
    print(f"Ollama Timeout: {config.ollama.timeout}")
    print(f"Default Timeout: {config.timeouts.default}")
    print(f"Default Retries: {config.retries.default}")
    print(f"LLM Temperature: {config.llm.temperature}")
    
    # 检查 API Key
    if config.api_keys.openai:
        print(f"OpenAI API Key: {config.api_keys.openai[:10]}...")
    else:
        print("OpenAI API Key: 未配置")
    
    print()


def demo_modify_config():
    """演示 2: 修改配置（运行时）"""
    print("=" * 60)
    print("演示 2: 修改配置（运行时生效）")
    print("=" * 60)
    
    # 保存旧值
    old_url = config.ollama.url
    
    # 修改配置
    config.ollama.url = "http://new-host:11434"
    print(f"修改后 Ollama URL: {config.ollama.url}")
    
    # 恢复
    config.ollama.url = old_url
    print(f"恢复后 Ollama URL: {config.ollama.url}")
    print()


def demo_shortcut_properties():
    """演示 3: 快捷属性"""
    print("=" * 60)
    print("演示 3: 快捷属性（常用配置）")
    print("=" * 60)
    
    print(f"config.ollama_url = {config.ollama_url}")
    print(f"config.ollama_timeout = {config.ollama_timeout}")
    print(f"config.default_timeout = {config.default_timeout}")
    print(f"config.default_retries = {config.default_retries}")
    print()


def demo_dict_export():
    """演示 4: 导出为字典（调试用）"""
    print("=" * 60)
    print("演示 4: 导出为字典（调试/序列化）")
    print("=" * 60)
    
    d = config.to_dict()
    print("配置字典（前 500 字符）:")
    import json
    d_str = json.dumps(d, indent=2, default=str)
    print(d_str[:500] + "..." if len(d_str) > 500 else d_str)
    print()


def demo_env_override():
    """演示 5: 从环境变量加载（部署用）"""
    print("=" * 60)
    print("演示 5: 从环境变量加载（部署用）")
    print("=" * 60)
    
    # 设置测试环境变量
    os.environ["LIVINGTREE_OLLAMA_URL"] = "http://env-override:11434"
    os.environ["LIVINGTREE_TIMEOUTS_DEFAULT"] = "60"
    
    # 创建新配置实例并加载环境变量
    new_config = NanochatConfig()
    new_config.load_from_env()
    
    print(f"从环境变量加载后 Ollama URL: {new_config.ollama.url}")
    print(f"从环境变量加载后 Default Timeout: {new_config.timeouts.default}")
    
    # 清理
    del os.environ["LIVINGTREE_OLLAMA_URL"]
    del os.environ["LIVINGTREE_TIMEOUTS_DEFAULT"]
    print()


def demo_compatibility_layer():
    """演示 6: 兼容层（旧代码继续工作）"""
    print("=" * 60)
    print("演示 6: 兼容层（旧代码继续工作）")
    print("=" * 60)
    
    import warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        
        # 旧 API 仍然工作（但会显示弃用警告）
        from client.src.business.config import UnifiedConfig
        
        old_config = UnifiedConfig.get_instance()
        url = old_config.get("endpoints.ollama.url")
        
        print(f"旧 API 仍然工作: {url}")
        print(f"弃用警告数量: {len(w)}")
        
        if len(w) > 0:
            print(f"警告信息: {w[0].message}")
    
    print()


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("Nanochat 风格配置系统 - 演示")
    print("=" * 60 + "\n")
    
    # 运行所有演示
    demo_basic_access()
    demo_modify_config()
    demo_shortcut_properties()
    demo_dict_export()
    demo_env_override()
    demo_compatibility_layer()
    
    print("=" * 60)
    print("✅ 所有演示完成")
    print("=" * 60)
    print("\n💡 建议:")
    print("  1. 新代码使用: from client.src.business.nanochat_config import config")
    print("  2. 旧代码逐步迁移，兼容层会显示弃用警告")
    print("  3. 查看迁移指南: docs/配置迁移指南_Nanochat风格.md\n")


if __name__ == "__main__":
    main()
