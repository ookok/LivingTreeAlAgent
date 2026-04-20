#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试错误日志轮转功能
===================

测试错误日志只保留最新的5条。
"""

import os
import sys
import json
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.error_management import get_error_logger

def test_error_log_rotation():
    """测试错误日志轮转功能"""
    print("\n=== 测试错误日志轮转功能 ===")
    
    error_logger = get_error_logger()
    
    # 清除旧的错误日志
    error_dir = Path(os.path.expanduser('~/.living_tree_ai/errors'))
    if error_dir.exists():
        for file in error_dir.glob('error_*.json'):
            file.unlink()
        print("   ✓ 已清除旧的错误日志")
    
    # 生成6个错误，应该只保留最新的5个
    for i in range(6):
        try:
            raise ValueError(f"Test error {i+1}")
        except Exception as e:
            error_entry = error_logger.log_error(e, component="test", context={"test_case": i+1})
            print(f"   ✓ 生成错误 {i+1}: {error_entry['error_code']}")
    
    # 检查错误日志文件数量
    error_files = list(error_dir.glob('error_*.json'))
    error_files.sort()
    
    print(f"\n=== 结果检查 ===")
    print(f"   错误日志文件数量: {len(error_files)}")
    print(f"   预期: 5")
    
    for i, file in enumerate(error_files, 1):
        print(f"   {i}. {file.name}")
    
    # 检查错误历史记录长度
    print(f"\n   错误历史记录长度: {len(error_logger.error_history)}")
    print(f"   预期: 5")
    
    # 验证结果
    if len(error_files) == 5 and len(error_logger.error_history) == 5:
        print("\n✅ 测试通过！错误日志只保留最新的5条")
        return True
    else:
        print("\n❌ 测试失败！错误日志数量不符合预期")
        return False

def main():
    """主测试函数"""
    print("开始测试错误日志轮转功能...")
    print("=" * 60)
    
    try:
        success = test_error_log_rotation()
        
        print("\n" + "=" * 60)
        if success:
            print("测试完成！错误日志轮转功能正常工作。")
        else:
            print("测试失败！请检查错误日志轮转功能。")
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
