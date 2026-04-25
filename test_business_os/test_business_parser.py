"""
BusinessParser 测试
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 避免导入 core.__init__ 中的复杂依赖
import importlib.util

# 直接加载 business_parser 模块
spec = importlib.util.spec_from_file_location(
    "business_parser",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "core", "business_os", "business_parser.py")
)
business_parser_module = importlib.util.module_from_spec(spec)

# 注入基础模块
class MockLogger:
    def info(self, msg): print(f"[INFO] {msg}")
    def debug(self, msg): print(f"[DEBUG] {msg}")
    def warning(self, msg): print(f"[WARNING] {msg}")
    def error(self, msg): print(f"[ERROR] {msg}")

class MockConfig:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def get_instance(cls):
        return cls()
    
    def get(self, key, default=None):
        return default

# Mock 模块
import types
mock_modules = {
    'core.logger': types.ModuleType('core.logger'),
    'core.config.unified_config': types.ModuleType('core.config.unified_config'),
}
mock_modules['core.logger'].get_logger = lambda x: MockLogger()
mock_modules['core.config.unified_config'].UnifiedConfig = MockConfig

sys.modules['core'] = types.ModuleType('core')
sys.modules['core.logger'] = mock_modules['core.logger']
sys.modules['core.config'] = types.ModuleType('core.config')
sys.modules['core.config.unified_config'] = mock_modules['core.config.unified_config']
sys.modules['core.config'] = types.ModuleType('core.config')

# 加载模块
spec.loader.exec_module(business_parser_module)

# 导出
BusinessParser = business_parser_module.BusinessParser
BusinessModel = business_parser_module.BusinessModel
EntityType = business_parser_module.EntityType
RuleType = business_parser_module.RuleType
parse_business = business_parser_module.parse_business


def test_supplier_management():
    """测试供应商管理系统解析"""
    description = """
    实现供应商管理系统，包括：
    - 供应商信息管理（录入、审核、评级）
    - 招标流程（发布、投标、开标、评标）
    - 合同管理（创建、审批、签署）
    - 付款审批（申请、复核、支付）
    
    金额超过10万需要总经理审批。
    """
    
    parser = BusinessParser()
    model = parser.parse(description)
    
    print("\n" + "="*60)
    print("测试: 供应商管理系统")
    print("="*60)
    print(f"\n领域: {model.domain}")
    print(f"实体数量: {len(model.entities)}")
    print(f"流程数量: {len(model.processes)}")
    print(f"规则数量: {len(model.rules)}")
    print(f"权限数量: {len(model.permissions)}")
    
    print("\n【实体列表】")
    for e in model.entities:
        print(f"  {e.name} ({e.entity_type.value}) - 置信度: {e.confidence}")
    
    print("\n【流程列表】")
    for p in model.processes:
        print(f"  {p.name}:")
        print(f"    步骤: {' -> '.join(p.steps)}")
        print(f"    参与者: {', '.join(p.participants)}")
    
    print("\n【规则列表】")
    for r in model.rules:
        print(f"  {r.name} ({r.rule_type.value})")
        print(f"    条件: {r.condition}")
        print(f"    动作: {r.action}")
    
    assert len(model.entities) > 0, "应该识别到实体"
    assert len(model.processes) > 0, "应该识别到流程"
    print("\n[PASS] 测试通过!")


def test_hr_management():
    """测试人力资源管理系统解析"""
    description = """
    实现员工管理系统，包括：
    - 招聘流程（需求、筛选、面试、录用）
    - 入职流程（offer、合同、入职手续）
    - 考勤管理（打卡、请假、加班）
    - 离职流程（申请、交接、结算）
    
    试用期不能超过6个月。
    """
    
    model = parse_business(description)
    
    print("\n" + "="*60)
    print("测试: 人力资源管理系统")
    print("="*60)
    print(f"\n领域: {model.domain}")
    
    print("\n【实体列表】")
    for e in model.entities:
        print(f"  {e.name} ({e.entity_type.value})")
    
    print("\n【规则列表】")
    for r in model.rules:
        if r.rule_type == RuleType.CONSTRAINT:
            print(f"  {r.name}")
            print(f"    条件: {r.condition}")
    
    assert len(model.entities) > 0
    print("\n[PASS] 测试通过!")


def test_project_management():
    """测试项目管理系统解析"""
    description = """
    实现项目管理系统，包括：
    - 项目立项（申请、审批、立项）
    - 任务管理（分配、执行、跟踪）
    - 风险管理（识别、评估、应对）
    - 项目验收（交付、评审、归档）
    """
    
    model = parse_business(description)
    
    print("\n" + "="*60)
    print("测试: 项目管理系统")
    print("="*60)
    print(f"\n领域: {model.domain}")
    print(f"流程数量: {len(model.processes)}")
    
    for p in model.processes:
        print(f"\n  {p.name}: {' -> '.join(p.steps)}")
    
    # 项目管理描述中的流程
    assert len(model.processes) >= 1, f"预期至少1个流程，实际{len(model.processes)}个"
    print("\n[PASS] 测试通过!")


def test_model_serialization():
    """测试模型序列化"""
    description = "实现供应商管理系统，包括招标、签约、付款流程。金额超过10万需要审批。"
    
    model = parse_business(description)
    
    # 测试 to_dict
    data = model.to_dict()
    assert "entities" in data
    assert "processes" in data
    assert "rules" in data
    
    # 测试 to_json
    json_str = model.to_json()
    assert len(json_str) > 0
    
    # 测试 summary
    summary = model.summary()
    assert "实体数量" in summary
    
    print("\n" + "="*60)
    print("测试: 模型序列化")
    print("="*60)
    print(f"\nJSON长度: {len(json_str)} 字符")
    print(f"摘要:\n{model.summary()}")
    
    print("\n[PASS] 测试通过!")


if __name__ == "__main__":
    print("="*60)
    print("BusinessParser 测试套件")
    print("="*60)
    
    test_supplier_management()
    test_hr_management()
    test_project_management()
    test_model_serialization()
    
    print("\n" + "="*60)
    print("所有测试通过! [PASS]")
    print("="*60)
