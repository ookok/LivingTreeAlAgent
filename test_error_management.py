#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试错误日志管理系统
=====================

测试错误日志记录、分类和自动诊断功能。
"""

import os
import sys
import json
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.error_management import get_error_logger, get_auto_diagnoser

def test_error_logging():
    """测试错误日志记录功能"""
    print("\n=== 测试错误日志记录 ===")
    
    error_logger = get_error_logger()
    
    # 测试1: UI初始化错误
    print("\n1. 测试UI初始化错误...")
    try:
        raise AttributeError("type object 'GlobalColor' has no attribute 'lightBlue'")
    except Exception as e:
        error_entry = error_logger.log_error(e, component="main_window", context={"action": "initialize"})
        print(f"   ✓ 错误记录成功: {error_entry['error_code']}")
        print(f"   ✓ 错误类型: {error_entry['error_type']}")
        print(f"   ✓ 诊断结果: {error_entry['diagnosis']['probable_cause']}")
    
    # 测试2: 模型加载错误
    print("\n2. 测试模型加载错误...")
    try:
        raise ValueError("ModelBackend.GGUF is not a valid attribute")
    except Exception as e:
        error_entry = error_logger.log_error(e, component="model_manager", context={"action": "load_model"})
        print(f"   ✓ 错误记录成功: {error_entry['error_code']}")
        print(f"   ✓ 错误类型: {error_entry['error_type']}")
        print(f"   ✓ 诊断结果: {error_entry['diagnosis']['probable_cause']}")
    
    # 测试3: 网络错误
    print("\n3. 测试网络错误...")
    try:
        raise TimeoutError("Connection timeout after 5000ms")
    except Exception as e:
        error_entry = error_logger.log_error(e, component="network", context={"action": "connect"})
        print(f"   ✓ 错误记录成功: {error_entry['error_code']}")
        print(f"   ✓ 错误类型: {error_entry['error_type']}")
        print(f"   ✓ 诊断结果: {error_entry['diagnosis']['probable_cause']}")
    
    # 测试4: 配置错误
    print("\n4. 测试配置错误...")
    try:
        raise KeyError("Config key 'model_path' is missing")
    except Exception as e:
        error_entry = error_logger.log_error(e, component="config", context={"action": "load"})
        print(f"   ✓ 错误记录成功: {error_entry['error_code']}")
        print(f"   ✓ 错误类型: {error_entry['error_type']}")
        print(f"   ✓ 诊断结果: {error_entry['diagnosis']['probable_cause']}")
    
    # 测试5: 依赖错误
    print("\n5. 测试依赖错误...")
    try:
        raise ImportError("No module named 'nonexistent_module'")
    except Exception as e:
        error_entry = error_logger.log_error(e, component="dependencies", context={"action": "import"})
        print(f"   ✓ 错误记录成功: {error_entry['error_code']}")
        print(f"   ✓ 错误类型: {error_entry['error_type']}")
        print(f"   ✓ 诊断结果: {error_entry['diagnosis']['probable_cause']}")

def test_auto_diagnosis():
    """测试自动诊断功能"""
    print("\n=== 测试自动诊断 ===")
    
    diagnoser = get_auto_diagnoser()
    
    # 诊断最近错误
    print("\n1. 诊断最近错误...")
    diagnosis = diagnoser.diagnose_recent_errors()
    print(f"   ✓ 诊断完成，状态: {diagnosis['status']}")
    print(f"   ✓ 错误数量: {diagnosis.get('error_count', 0)}")
    
    if diagnosis.get('recommendations'):
        print("\n2. 修复建议:")
        for i, rec in enumerate(diagnosis['recommendations'], 1):
            print(f"   {i}. {rec['description']} (优先级: {rec['priority']})")
            for j, suggestion in enumerate(rec['suggestions'], 1):
                print(f"      {j}. {suggestion}")
    
    # 生成诊断报告
    print("\n3. 生成诊断报告...")
    report = diagnoser.generate_diagnostic_report()
    print(f"   ✓ 报告生成成功")
    print(f"   ✓ 系统信息: {report['system_info']['os']} {report['system_info']['os_version']}")
    print(f"   ✓ Python版本: {report['system_info']['python_version'].strip()}")
    print(f"   ✓ 错误统计: {json.dumps(report['error_stats'], indent=2)}")

def test_error_trends():
    """测试错误趋势分析"""
    print("\n=== 测试错误趋势分析 ===")
    
    error_logger = get_error_logger()
    trends = error_logger.analyze_error_trends()
    
    print(f"\n1. 错误趋势:")
    print(f"   ✓ 总错误数: {trends['total_errors']}")
    print(f"   ✓ 错误类型分布: {json.dumps(trends['errors_by_type'], indent=2)}")
    print(f"   ✓ 错误严重程度分布: {json.dumps(trends['errors_by_severity'], indent=2)}")
    
    if trends['most_common_error']:
        print(f"   ✓ 最常见错误: {trends['most_common_error']['type']} (出现 {trends['most_common_error']['count']} 次)")

def main():
    """主测试函数"""
    print("开始测试错误日志管理系统...")
    print("=" * 60)
    
    try:
        test_error_logging()
        test_auto_diagnosis()
        test_error_trends()
        
        print("\n" + "=" * 60)
        print("测试完成！所有功能正常运行。")
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
