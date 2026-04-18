# -*- coding: utf-8 -*-
"""
LocalMarket 测试脚本
=====================

测试去中心化本地商品交易系统的所有模块
"""

import sys
import os
import time

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'core'))

from local_market import (
    Product, ProductManager, ProductCategory, Location,
    Transaction, TransactionManager, TransactionStatus, PaymentType,
    SellerReputation, ReputationManager, ReputationLevel,
    DeliveryTask, DeliveryManager, DeliveryType, DeliveryStatus,
    Dispute, DisputeManager, DisputeStatus,
    CommissionRecord, CommissionCalculator, CommissionType,
)


class TestRunner:
    """测试运行器"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0

    def test(self, name: str, func):
        """运行单个测试"""
        try:
            print(f"\n[Test] {name}")
            result = func()
            if result is None or result is True:
                print(f"  [PASS]")
                self.passed += 1
                return True
            elif isinstance(result, dict) and result.get("skip"):
                print(f"  [SKIP]: {result.get('reason', '')}")
                self.skipped += 1
                return None
            else:
                print(f"  [FAIL]: {result}")
                self.failed += 1
                return False
        except Exception as e:
            print(f"  [ERROR]: {e}")
            self.failed += 1
            return False

    def summary(self):
        """打印测试摘要"""
        total = self.passed + self.failed + self.skipped
        print("\n" + "=" * 60)
        print(f"测试结果: {self.passed}/{total} 通过", end="")
        if self.skipped > 0:
            print(f", {self.skipped} 跳过", end="")
        if self.failed > 0:
            print(f", {self.failed} 失败", end="")
        print()
        print("=" * 60)


def test_product_module(runner: TestRunner):
    """测试商品模块"""
    print("\n" + "=" * 40)
    print("商品模块测试")
    print("=" * 40)

    manager = ProductManager("test_user")

    def test_create_product():
        product = Product(
            title="测试商品",
            description="这是一个测试商品",
            category=ProductCategory.ELECTRONICS,
            price=999.99,
        )
        pid = manager.publish_product(product)
        assert pid, "Product ID should not be empty"
        return True

    def test_search_product():
        results = manager.search_products(query="测试")
        return len(results) > 0

    def test_location():
        loc1 = Location(39.9042, 116.4074, "北京", "朝阳区", "北京")
        loc2 = Location(39.9142, 116.4174, "北京", "海淀区", "北京")

        distance = loc1.distance_to(loc2)
        assert distance > 0, "Distance should be positive"

        geohash = loc1.get_geo_hash()
        assert len(geohash) > 0, "Geohash should not be empty"

        return True

    def test_product_update():
        products = manager.get_my_products()
        if not products:
            return {"skip": True, "reason": "No products to update"}

        product = products[0]
        success = manager.update_product(product.product_id, price=888.88)
        return success

    def test_product_delete():
        products = manager.get_my_products()
        if not products:
            return {"skip": True, "reason": "No products to delete"}

        product = products[0]
        success = manager.delete_product(product.product_id)
        return success

    runner.test("创建商品", test_create_product)
    runner.test("搜索商品", test_search_product)
    runner.test("地理位置", test_location)
    runner.test("更新商品", test_product_update)
    runner.test("删除商品", test_product_delete)


def test_transaction_module(runner: TestRunner):
    """测试交易模块"""
    print("\n" + "=" * 40)
    print("交易模块测试")
    print("=" * 40)

    buyer_mgr = TransactionManager("buyer_001")
    seller_mgr = TransactionManager("seller_001")

    tx_id = None

    def test_create_transaction():
        nonlocal tx_id
        product_snapshot = {"title": "iPhone", "price": 6999}

        tx = buyer_mgr.create_transaction(
            buyer_id="buyer_001",
            seller_id="seller_001",
            product_id="prod_001",
            product_snapshot=product_snapshot,
            price=6500,
            payment_type=PaymentType.ESCROW,
        )

        tx_id = tx.transaction_id
        assert tx_id, "Transaction ID should not be empty"
        return True

    def test_accept_transaction():
        nonlocal tx_id
        if not tx_id:
            return {"skip": True, "reason": "No transaction to accept"}

        success = seller_mgr.accept_transaction(tx_id)
        return success

    def test_negotiate():
        nonlocal tx_id
        if not tx_id:
            return {"skip": True, "reason": "No transaction to negotiate"}

        offer = buyer_mgr.propose_counter_offer(
            transaction_id=tx_id,
            buyer_id="buyer_001",
            new_price=6000,
            message="便宜点吧",
        )
        assert offer.price == 6000
        return True

    def test_accept_offer():
        nonlocal tx_id
        if not tx_id:
            return {"skip": True, "reason": "No offer to accept"}

        # 找到pending的offer
        for oid, offer in buyer_mgr.pending_offers.items():
            if offer.transaction_id == tx_id:
                success = seller_mgr.accept_offer(oid)
                return success

        return {"skip": True, "reason": "No pending offer found"}

    def test_payment_flow():
        nonlocal tx_id
        if not tx_id:
            return {"skip": True, "reason": "No transaction"}

        tx = buyer_mgr.get_transaction(tx_id)
        assert tx.final_price == 6000, f"Price should be 6000, got {tx.final_price}"

        # 锁定支付
        success = buyer_mgr.lock_payment(tx_id)
        return success

    def test_cancel():
        nonlocal tx_id
        if not tx_id:
            return {"skip": True, "reason": "No transaction to cancel"}

        # 创建一个新交易来取消
        new_tx = buyer_mgr.create_transaction(
            buyer_id="buyer_001",
            seller_id="seller_001",
            product_id="prod_002",
            product_snapshot={"title": "测试"},
            price=100,
        )

        success = buyer_mgr.cancel_transaction(new_tx.transaction_id, "测试取消")
        return success

    runner.test("创建交易", test_create_transaction)
    runner.test("接受交易", test_accept_transaction)
    runner.test("协商价格", test_negotiate)
    runner.test("接受还价", test_accept_offer)
    runner.test("支付流程", test_payment_flow)
    runner.test("取消交易", test_cancel)


def test_reputation_module(runner: TestRunner):
    """测试信誉模块"""
    print("\n" + "=" * 40)
    print("信誉模块测试")
    print("=" * 40)

    manager = ReputationManager("user_001")

    def test_initial_reputation():
        rep = manager.get_reputation("user_001")
        assert rep.score == 100, f"Initial score should be 100, got {rep.score}"
        return True

    def test_add_feedback():
        fb = manager.add_feedback(
            transaction_id="tx_001",
            reviewer_id="buyer_001",
            reviewee_id="user_001",
            role="seller",
            rating=5,
            comment="很好！",
        )

        assert fb.rating == 5
        return True

    def test_reputation_calculation():
        rep = manager.get_reputation("user_001")
        assert rep.score > 100, "Score should increase after positive feedback"
        return True

    def test_level():
        rep = manager.get_reputation("user_001")
        level = rep.level
        assert isinstance(level, ReputationLevel)
        return True

    def test_leaderboard():
        # 添加一些测试数据
        manager.reputations["user_002"] = SellerReputation(user_id="user_002", score=150)
        manager.reputations["user_003"] = SellerReputation(user_id="user_003", score=80)

        leaderboard = manager.get_leaderboard()
        assert len(leaderboard) > 0
        assert leaderboard[0]["score"] >= leaderboard[1]["score"]
        return True

    runner.test("初始信誉", test_initial_reputation)
    runner.test("添加反馈", test_add_feedback)
    runner.test("信誉计算", test_reputation_calculation)
    runner.test("等级计算", test_level)
    runner.test("排行榜", test_leaderboard)


def test_delivery_module(runner: TestRunner):
    """测试交付模块"""
    print("\n" + "=" * 40)
    print("交付模块测试")
    print("=" * 40)

    manager = DeliveryManager("seller_001")
    task_id = None

    def test_create_delivery():
        nonlocal task_id
        task = manager.create_delivery_task(
            transaction_id="tx_001",
            sender_id="seller_001",
            receiver_id="buyer_001",
            product_id="prod_001",
            product_snapshot={"title": "iPhone"},
            delivery_type=DeliveryType.DELIVERY,
            pickup_info={
                "address": "朝阳区某某路",
                "location": {"lat": 39.9, "lon": 116.4},
            },
            dropoff_info={
                "address": "海淀区某某街",
                "location": {"lat": 39.95, "lon": 116.3},
            },
            delivery_fee=15.0,
        )

        task_id = task.task_id
        assert task.pickup_code, "Pickup code should be generated"
        assert task.delivery_code, "Delivery code should be generated"
        return True

    def test_arrange_courier():
        nonlocal task_id
        if not task_id:
            return {"skip": True, "reason": "No task"}

        success = manager.arrange_courier(task_id, "courier_001")
        return success

    def test_verify_codes():
        nonlocal task_id
        if not task_id:
            return {"skip": True, "reason": "No task"}

        task = manager.get_task(task_id)
        assert task.verify_pickup_code(task.pickup_code)
        assert task.verify_delivery_code(task.delivery_code)
        assert not task.verify_pickup_code("WRONG")
        return True

    def test_cancel_delivery():
        nonlocal task_id
        if not task_id:
            return {"skip": True, "reason": "No task"}

        # 创建新任务取消
        new_task = manager.create_delivery_task(
            transaction_id="tx_002",
            sender_id="seller_001",
            receiver_id="buyer_001",
            product_id="prod_002",
            product_snapshot={"title": "测试"},
            delivery_type=DeliveryType.PICKUP,
            pickup_info={"address": "测试地址", "location": {}},
            dropoff_info={"address": "", "location": {}},
        )

        success = manager.cancel_delivery(new_task.task_id, "测试取消")
        return success

    runner.test("创建交付任务", test_create_delivery)
    runner.test("安排配送员", test_arrange_courier)
    runner.test("验证码", test_verify_codes)
    runner.test("取消交付", test_cancel_delivery)


def test_dispute_module(runner: TestRunner):
    """测试争议模块"""
    print("\n" + "=" * 40)
    print("争议模块测试")
    print("=" * 40)

    rep_mgr = ReputationManager("admin")
    manager = DisputeManager("buyer_001", rep_mgr)

    # 注册仲裁员
    manager.register_as_arbitrator("arb_001")
    manager.register_as_arbitrator("arb_002")
    manager.register_as_arbitrator("arb_003")

    dispute_id = None

    def test_create_dispute():
        nonlocal dispute_id
        dispute = manager.create_dispute(
            transaction_id="tx_001",
            initiator_id="buyer_001",
            respondent_id="seller_001",
            dispute_type="not_delivered",
            description="付款后未收到货",
        )

        dispute_id = dispute.dispute_id
        assert dispute_id
        return True

    def test_arbitrator_selection():
        nonlocal dispute_id
        if not dispute_id:
            return {"skip": True, "reason": "No dispute"}

        dispute = manager.get_my_disputes()[0]
        assert len(dispute.arbitrator_ids) > 0, "Arbitrators should be selected"
        return True

    def test_submit_vote():
        nonlocal dispute_id
        if not dispute_id:
            return {"skip": True, "reason": "No dispute"}

        dispute = manager.get_my_disputes()[0]
        if dispute.arbitrator_ids:
            arb_id = dispute.arbitrator_ids[0]
            success = manager.submit_vote(
                dispute_id=dispute.dispute_id,
                arbitrator_id=arb_id,
                decision="buyer",
                reason="卖家未发货",
            )
            return success

        return {"skip": True, "reason": "No arbitrators"}

    def test_rate_arbitration():
        nonlocal dispute_id
        if not dispute_id:
            return {"skip": True, "reason": "No dispute"}

        dispute = manager.get_my_disputes()[0]
        success = manager.rate_arbitration(
            dispute.dispute_id,
            "buyer_001",
            5,
        )
        return success

    runner.test("创建争议", test_create_dispute)
    runner.test("仲裁员选择", test_arbitrator_selection)
    runner.test("提交投票", test_submit_vote)
    runner.test("评价仲裁", test_rate_arbitration)


def test_commission_module(runner: TestRunner):
    """测试佣金模块"""
    print("\n" + "=" * 40)
    print("佣金模块测试")
    print("=" * 40)

    calculator = CommissionCalculator("node_001")

    def test_discovery_commission():
        records = calculator.calculate_discovery_commission(
            transaction_id="tx_001",
            transaction_amount=1000.0,
            discovery_node_id="node_002",
            referrer_id="node_003",
        )

        assert len(records) == 2, "Should have discovery and referral commissions"

        discovery = next(r for r in records if r.commission_type == CommissionType.DISCOVERY)
        assert discovery.recipient_id == "node_002"
        assert discovery.commission_amount == 100.0, f"10% of 1000 = 100, got {discovery.commission_amount}"

        referral = next(r for r in records if r.commission_type == CommissionType.REFERRAL)
        assert referral.recipient_id == "node_003"
        assert referral.commission_amount == 50.0, f"5% of 1000 = 50, got {referral.commission_amount}"

        return True

    def test_witness_commission():
        records = calculator.calculate_witness_commission(
            transaction_id="tx_001",
            transaction_amount=1000.0,
            witness_ids=["node_004", "node_005"],
        )

        assert len(records) == 2, "Should have 2 witness commissions"

        # 5% total, split between 2 witnesses = 2.5% each
        for record in records:
            assert record.commission_amount == 25.0, f"2.5% of 1000 = 25, got {record.commission_amount}"

        return True

    def test_mark_paid():
        records = calculator.calculate_discovery_commission(
            transaction_id="tx_002",
            transaction_amount=500.0,
            discovery_node_id="node_002",
        )

        record = records[0]
        success = calculator.mark_paid(record.record_id)
        assert success

        stats = calculator.get_total_commissions("node_002")
        assert stats["total_paid"] > 0

        return True

    def test_commission_summary():
        summary = calculator.get_commission_summary()
        assert summary["total_records"] > 0
        assert "by_type" in summary
        return True

    runner.test("发现佣金", test_discovery_commission)
    runner.test("见证佣金", test_witness_commission)
    runner.test("标记支付", test_mark_paid)
    runner.test("佣金汇总", test_commission_summary)


def main():
    """运行所有测试"""
    print("=" * 60)
    print("LocalMarket 去中心化本地商品交易系统测试")
    print("=" * 60)

    runner = TestRunner()

    test_product_module(runner)
    test_transaction_module(runner)
    test_reputation_module(runner)
    test_delivery_module(runner)
    test_dispute_module(runner)
    test_commission_module(runner)

    runner.summary()


if __name__ == "__main__":
    main()
