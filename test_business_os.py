# -*- coding: utf-8 -*-
"""
Business OS 测试脚本
=================

测试 Business OS 的核心功能
"""

import sys
import os

# 添加到路径
sys.path.insert(0, 'f:/mhzyapp/LivingTreeAlAgent')

# 直接执行模块
if __name__ == "__main__":
    # 测试 Business Parser
    print("=" * 60)
    print("测试 1: 业务解析器")
    print("=" * 60)
    
    # 动态导入
    exec(open('f:/mhzyapp/LivingTreeAlAgent/core/business_os/business_types.py', encoding='utf-8').read())
    exec(open('f:/mhzyapp/LivingTreeAlAgent/core/business_os/business_parser.py', encoding='utf-8').read())
    
    parser = BusinessParser()
    
    test_cases = [
        "实现供应商管理系统，包括供应商信息管理、招标流程、合同管理",
        "实现一个P2P采购流程，包括供应商管理、招标、合同签订、付款，金额超过10万需要经理审批",
        "员工管理系统，包括员工信息管理、入职流程、请假审批",
    ]
    
    for i, description in enumerate(test_cases, 1):
        print(f"\n--- 测试用例 {i} ---")
        print(f"描述: {description}")
        
        model = parser.parse(description)
        
        print(f"\n业务领域: {model.domain}")
        print(f"\n识别实体 ({len(model.entities)}):")
        for entity in model.entities:
            print(f"  - {entity.name} ({entity.type.value})")
        
        print(f"\n推断流程 ({len(model.processes)}):")
        for process in model.processes:
            print(f"  - {process.name} ({process.type.value})")
        
        print(f"\n抽取规则 ({len(model.rules)}):")
        for rule in model.rules[:5]:
            print(f"  - {rule.name}")
            if rule.condition:
                print(f"    条件: {rule.condition}")
    
    print("\n" + "=" * 60)
    print("测试 2: Entity Mapper & Code Generator")
    print("=" * 60)
    
    # 加载剩余模块
    exec(open('f:/mhzyapp/LivingTreeAlAgent/core/business_os/entity_mapper.py', encoding='utf-8').read())
    exec(open('f:/mhzyapp/LivingTreeAlAgent/core/business_os/code_generator.py', encoding='utf-8').read())
    
    mapper = EntityMapper(tech_stack=["python", "fastapi", "postgresql"])
    generator = CodeGenerator(tech_stack=["python", "fastapi", "postgresql"])
    
    # 测试映射
    technical_model = mapper.map(model)
    
    print(f"\n生成数据模型 ({len(technical_model.data_models)}):")
    for dm in technical_model.data_models:
        print(f"  - {dm.name} ({dm.table_name})")
        for field in dm.fields[:5]:
            print(f"      - {field.name}: {field.type.value}")
    
    print(f"\n生成服务 ({len(technical_model.services)}):")
    for svc in technical_model.services:
        print(f"  - {svc.name} ({len(svc.methods)} 方法)")
    
    print(f"\n生成 API ({len(technical_model.apis)}):")
    for api in technical_model.apis[:5]:
        print(f"  - {api.method} {api.path}")
    
    # 生成代码
    result = generator.generate(technical_model)
    
    print(f"\n生成代码文件 ({result.file_count}):")
    for filename in sorted(result.files.keys()):
        lines = result.files[filename].count('\n') + 1
        print(f"  - {filename} ({lines} 行)")
    
    print("\n" + "=" * 60)
    print("✅ 测试完成!")
    print("=" * 60)
