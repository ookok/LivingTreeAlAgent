# -*- coding: utf-8 -*-
"""
统一佣金系统 - 功能测试
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_models():
    """测试数据模型"""
    print("=" * 50)
    print("测试数据模型...")
    
    from commission.models import (
        ModuleType, PaymentProvider, OrderStatus,
        PaymentOrder, CommissionResult, ModuleConfig
    )
    
    # 测试枚举
    assert ModuleType.DEEP_SEARCH.value == "deep_search"
    assert PaymentProvider.WECHAT.value == "wechat"
    assert OrderStatus.PENDING.value == "pending"
    
    # 测试订单
    order = PaymentOrder(
        order_id="TEST001",
        module_type=ModuleType.DEEP_SEARCH,
        original_amount=100.0,
        commission_amount=0.03,
        total_amount=100.03
    )
    assert order.order_id == "TEST001"
    assert order.original_amount == 100.0
    
    # 测试序列化
    order_dict = order.to_dict()
    assert order_dict["order_id"] == "TEST001"
    
    # 测试反序列化
    order2 = PaymentOrder.from_dict(order_dict)
    assert order2.order_id == order.order_id
    
    print("✅ 数据模型测试通过")
    return True


def test_config_manager():
    """测试配置管理器"""
    print("=" * 50)
    print("测试配置管理器...")
    
    from commission.config_manager import get_config_manager
    
    config = get_config_manager()
    
    # 测试获取模块配置
    deep_search_config = config.get_module_config("deep_search")
    assert deep_search_config is not None
    assert deep_search_config.module_type.value == "deep_search"
    
    # 测试获取全局配置
    global_config = config.get_global_config()
    assert global_config.app_name == "智能创作平台"
    assert global_config.commission_rate == 0.0003
    
    # 测试配置值获取
    rate = config.get_config_value("global.commission_rate")
    assert rate == 0.0003
    
    # 测试验证
    is_valid, errors = config.validate_config()
    assert is_valid == True or len(errors) == 0
    
    print(f"✅ 配置管理器测试通过")
    print(f"   - 模块数量: {len(ModuleType.__members__)}")
    print(f"   - 默认佣金比例: {global_config.commission_rate}")
    return True


def test_calculator():
    """测试佣金计算"""
    print("=" * 50)
    print("测试佣金计算...")
    
    from commission.calculator import get_calculator
    
    calc = get_calculator()
    
    # 测试佣金计算
    result = calc.calculate_commission("deep_search", 100.0)
    
    assert result.original_amount == 100.0
    assert result.commission_rate == 0.0003
    assert result.commission_amount == 0.03
    assert result.total_amount == 100.03
    
    # 测试结算
    settlement = calc.calculate_settlement(result)
    assert settlement["author_amount"] == 100.0
    assert settlement["developer_amount"] == 0.03
    
    # 测试金额验证
    is_valid, msg = calc.validate_amount("deep_search", 100.0)
    assert is_valid == True
    
    is_valid, msg = calc.validate_amount("deep_search", 0)
    assert is_valid == False
    
    # 测试佣金预览
    preview = calc.get_commission_preview("deep_search", 100.0)
    assert preview["original_amount"] == 100.0
    assert preview["commission_amount"] == 0.03
    
    print(f"✅ 佣金计算测试通过")
    print(f"   - 原始金额: {result.original_amount}")
    print(f"   - 佣金: {result.commission_amount}")
    print(f"   - 总计: {result.total_amount}")
    return True


def test_modules():
    """测试模块"""
    print("=" * 50)
    print("测试模块系统...")
    
    from commission.modules import (
        list_registered_modules, create_module
    )
    from commission.models import ModuleType, PaymentOrder
    
    # 列出已注册模块
    modules = list_registered_modules()
    print(f"   - 已注册模块: {modules}")
    assert len(modules) > 0
    
    # 测试创建模块
    for module_name in modules:
        module = create_module(module_name)
        assert module is not None
        
        info = module.get_module_info()
        assert "name" in info
        assert "commission_rate" in info
    
    # 测试具体模块
    from commission.modules.deep_search import DeepSearchModule
    from commission.modules.creation import CreationModule
    from commission.modules.game import GameModule
    
    ds_module = DeepSearchModule()
    info = ds_module.get_module_info()
    assert info["name"] == "深度搜索"
    
    # 测试功能解锁
    features = ds_module.get_features_by_amount(50)
    assert "去广告" in features
    
    print(f"✅ 模块系统测试通过")
    print(f"   - 模块数量: {len(modules)}")
    return True


def test_payment():
    """测试支付"""
    print("=" * 50)
    print("测试支付系统...")
    
    from commission.payment_factory import get_payment_factory, MockPaymentService
    from commission.models import PaymentProvider
    
    factory = get_payment_factory()
    
    # 测试获取支付服务
    service = factory.get_payment_service("wechat")
    assert service is not None
    
    # 测试创建订单
    order_data = {
        "order_id": "TEST_ORDER_001",
        "module_type": "deep_search",
        "original_amount": 100.0,
        "commission_amount": 0.03,
        "total_amount": 100.03,
        "subject": "测试打赏",
        "body": "测试订单"
    }
    
    result = service.create_order(order_data)
    assert result["success"] == True
    assert "order_id" in result
    assert "qr_code" in result
    
    # 测试模拟支付
    if isinstance(service, MockPaymentService):
        pay_result = service.simulate_payment(result["order_id"])
        assert pay_result["success"] == True
    
    print(f"✅ 支付系统测试通过")
    print(f"   - 订单号: {result['order_id']}")
    print(f"   - 支付二维码: {result['qr_code'][:50]}...")
    return True


def test_database():
    """测试数据库"""
    print("=" * 50)
    print("测试数据库...")
    
    from commission.database import get_commission_database
    from commission.models import PaymentOrder, ModuleType, PaymentProvider, OrderStatus
    
    db = get_commission_database()
    
    # 创建测试订单
    order = PaymentOrder(
        order_id="DB_TEST_001",
        module_type=ModuleType.DEEP_SEARCH,
        provider=PaymentProvider.WECHAT,
        original_amount=50.0,
        commission_amount=0.015,
        total_amount=50.015,
        status=OrderStatus.PENDING,
        subject="测试订单",
        user_id="test_user"
    )
    
    # 保存
    result = db.save_order(order)
    assert result == True
    
    # 查询
    saved_order = db.get_order("DB_TEST_001")
    assert saved_order is not None
    assert saved_order.order_id == "DB_TEST_001"
    assert saved_order.original_amount == 50.0
    
    # 更新状态
    result = db.update_order_status("DB_TEST_001", OrderStatus.PAID)
    assert result == True
    
    # 列表查询
    orders = db.list_orders()
    assert len(orders) > 0
    
    # 统计
    stats = db.get_order_statistics()
    assert "total_orders" in stats
    
    print(f"✅ 数据库测试通过")
    print(f"   - 总订单数: {stats['total_orders']}")
    print(f"   - 总金额: {stats['total_amount']}")
    return True


def test_commission_system():
    """测试佣金系统"""
    print("=" * 50)
    print("测试佣金系统...")
    
    from commission.commission_system import get_commission_system
    
    system = get_commission_system()
    
    # 测试配置
    configs = system.get_all_modules_config()
    assert len(configs) > 0
    
    # 测试佣金预览
    preview = system.get_commission_preview("deep_search", 100.0)
    assert preview["original_amount"] == 100.0
    
    # 测试创建订单
    order_result = system.create_order(
        module="deep_search",
        amount=100.0,
        user_id="test_user",
        subject="测试打赏"
    )
    assert order_result["success"] == True
    order_id = order_result["order_id"]
    
    # 测试获取订单
    order = system.get_order(order_id)
    assert order is not None
    
    # 测试统计
    stats = system.get_statistics()
    assert "total_orders" in stats
    
    print(f"✅ 佣金系统测试通过")
    print(f"   - 模块配置: {len(configs)}")
    print(f"   - 总订单: {stats['total_orders']}")
    return True


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("统一佣金系统 - 功能测试")
    print("=" * 60 + "\n")
    
    tests = [
        ("数据模型", test_models),
        ("配置管理器", test_config_manager),
        ("佣金计算", test_calculator),
        ("模块系统", test_modules),
        ("支付系统", test_payment),
        ("数据库", test_database),
        ("佣金系统", test_commission_system),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ {name}测试失败: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
