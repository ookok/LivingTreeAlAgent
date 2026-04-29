"""
对账服务 - Reconciliation Service

每日对账、异常恢复、内外一致性检查

核心功能：
1. 内部一致性检查：tx_ledger vs account_snapshot
2. 外部对账：账本充值 vs 支付网关账单
3. 异常检测与告警
4. 自动修复（可选）
"""

import logging
import threading
import time
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
from datetime import datetime, date, timedelta
from decimal import Decimal

logger = logging.getLogger(__name__)


@dataclass
class ReconciliationResult:
    """对账结果"""
    check_date: date
    check_type: str  # DAILY, MANUAL, AUTO_CHECK

    # 内部一致性
    total_users: int = 0
    inconsistent_users: int = 0
    inconsistent_details: List[Dict] = None

    # 外部对账
    ledger_recharge_total: Decimal = Decimal("0")
    gateway_recharge_total: Decimal = Decimal("0")
    gateway_diff: Decimal = Decimal("0")

    # 状态
    status: str = "PENDING"  # PENDING, PASSED, FAILED, MANUAL_REVIEW
    error_details: str = ""
    errors: List[str] = None

    created_at: float = None
    completed_at: Optional[float] = None

    def __post_init__(self):
        if self.inconsistent_details is None:
            self.inconsistent_details = []
        if self.errors is None:
            self.errors = []
        if self.created_at is None:
            self.created_at = time.time()

    def to_dict(self) -> Dict:
        d = asdict(self)
        d['check_date'] = str(self.check_date)
        d['ledger_recharge_total'] = str(self.ledger_recharge_total)
        d['gateway_recharge_total'] = str(self.gateway_recharge_total)
        d['gateway_diff'] = str(self.gateway_diff)
        return d


class ReconciliationService:
    """
    对账服务

    职责：
    1. 内部一致性检查
    2. 外部对账（模拟）
    3. 生成对账报告
    """

    def __init__(self, ledger=None, snapshot_db=None):
        self.ledger = ledger
        self.snapshot_db = snapshot_db  # 数据库连接或模拟

        # 对账配置
        self.tolerance = Decimal("0.01")  # 金额差异容差

        # 回调
        self._on_anomaly: Optional[callable] = None

    def set_anomaly_callback(self, callback: callable):
        """设置异常告警回调"""
        self._on_anomaly = callback

    def check_internal_consistency(self) -> Tuple[int, List[Dict]]:
        """
        内部一致性检查

        比较 tx_ledger 计算的余额 vs account_snapshot 的余额

        Returns:
            (inconsistent_count, inconsistent_details)
        """
        logger.info("开始内部一致性检查...")

        inconsistencies = []

        # 如果有ledger和snapshot，进行真实检查
        if self.ledger and hasattr(self.ledger, 'account_cache'):
            for user_id, state in self.ledger.account_cache.items():
                # 计算账本余额
                calculated_balance = self._calculate_balance_from_ledger(user_id)

                # 比较快照
                if abs(calculated_balance - state.balance) > self.tolerance:
                    inconsistencies.append({
                        "user_id": user_id,
                        "snapshot_balance": float(state.balance),
                        "calculated_balance": float(calculated_balance),
                        "diff": float(abs(calculated_balance - state.balance))
                    })

        logger.info(f"内部一致性检查完成: {len(inconsistencies)} 个不一致")
        return len(inconsistencies), inconsistencies

    def _calculate_balance_from_ledger(self, user_id: str) -> Decimal:
        """从账本计算用户余额"""
        if not self.ledger:
            return Decimal("0")

        total = Decimal("0")
        for tx in self.ledger.get_user_txs(user_id, limit=10000):
            if tx.op_type.value in ("RECHARGE", "GRANT", "TRANSFER_IN"):
                total += tx.amount
            elif tx.op_type.value in ("CONSUME", "TRANSFER_OUT"):
                total -= tx.amount

        return total

    def check_external_reconciliation(
        self,
        gateway_records: List[Dict],
        check_date: date = None
    ) -> Tuple[Decimal, Decimal, Decimal, List[Dict]]:
        """
        外部对账

        比较账本充值总额 vs 支付网关账单

        Args:
            gateway_records: 支付网关记录 [{order_id, amount, status, time}]
            check_date: 对账日期

        Returns:
            (ledger_total, gateway_total, diff, discrepancies)
        """
        logger.info(f"开始外部对账: {len(gateway_records)} 条网关记录")

        # 计算账本充值总额（这里用模拟数据）
        # 实际应该从数据库查询
        ledger_total = Decimal("0")
        if self.ledger:
            for tx in self.ledger.get_all_txs(limit=10000):
                if tx.op_type.value == "RECHARGE":
                    ledger_total += tx.amount

        # 计算网关总额
        gateway_total = sum(Decimal(str(r.get("amount", 0))) for r in gateway_records)

        diff = abs(ledger_total - gateway_total)

        # 查找差异记录
        discrepancies = []
        if diff > self.tolerance:
            ledger_order_ids = set()
            if self.ledger:
                for tx in self.ledger.get_all_txs(limit=10000):
                    if tx.op_type.value == "RECHARGE" and tx.payment_order_id:
                        ledger_order_ids.add(tx.payment_order_id)

            for record in gateway_records:
                order_id = record.get("order_id", "")
                if order_id and order_id not in ledger_order_ids:
                    discrepancies.append({
                        "order_id": order_id,
                        "amount": record.get("amount"),
                        "gateway_status": record.get("status"),
                        "issue": "账本中不存在该订单"
                    })

        logger.info(f"外部对账完成: 差异={diff}")
        return ledger_total, gateway_total, diff, discrepancies

    def run_daily_reconciliation(self, gateway_records: List[Dict] = None) -> ReconciliationResult:
        """
        执行每日对账

        Args:
            gateway_records: 支付网关记录（可选）

        Returns:
            ReconciliationResult
        """
        check_date = date.today() - timedelta(days=1)  # 昨天
        result = ReconciliationResult(
            check_date=check_date,
            check_type="DAILY"
        )

        start_time = time.time()

        # 1. 内部一致性检查
        inconsistent_count, inconsistencies = self.check_internal_consistency()
        result.total_users = len(inconsistencies) if inconsistencies else 0
        result.inconsistent_users = inconsistent_count
        result.inconsistent_details = inconsistencies[:100]  # 只保留前100条

        # 2. 外部对账（如果提供了网关记录）
        if gateway_records:
            ledger_total, gateway_total, diff, discrepancies = self.check_external_reconciliation(
                gateway_records, check_date
            )
            result.ledger_recharge_total = ledger_total
            result.gateway_recharge_total = gateway_total
            result.gateway_diff = diff

            if discrepancies:
                result.errors.extend([f"订单 {d['order_id']}: {d['issue']}" for d in discrepancies[:10]])

        # 3. 判断状态
        if inconsistent_count > 0 or (gateway_records and result.gateway_diff > self.tolerance):
            result.status = "FAILED"
            if inconsistent_count > 0:
                result.errors.append(f"内部一致性检查失败: {inconsistent_count} 个用户")
            if result.gateway_diff > self.tolerance:
                result.errors.append(f"外部对账差异: {result.gateway_diff}")
        else:
            result.status = "PASSED"

        result.completed_at = time.time()
        duration = result.completed_at - result.created_at

        logger.info(f"每日对账完成: status={result.status}, duration={duration:.2f}s")

        # 触发异常告警
        if result.status == "FAILED" and self._on_anomaly:
            try:
                self._on_anomaly(result)
            except Exception as e:
                logger.error(f"异常告警回调失败: {e}")

        return result

    def run_chain_integrity_check(self) -> Tuple[bool, List[Dict]]:
        """
        检查链完整性

        验证每个用户的交易链是否连续

        Returns:
            (is_valid, broken_chains)
        """
        logger.info("开始链完整性检查...")

        broken_chains = []

        if self.ledger and hasattr(self.ledger, 'verify_chain_integrity'):
            for user_id in self.ledger.user_txs.keys():
                valid, msg = self.ledger.verify_chain_integrity(user_id)
                if not valid:
                    broken_chains.append({
                        "user_id": user_id,
                        "error": msg
                    })

        logger.info(f"链完整性检查完成: {len(broken_chains)} 条断裂")
        return len(broken_chains) == 0, broken_chains

    def get_reconciliation_report(self, result: ReconciliationResult) -> str:
        """生成对账报告"""
        lines = [
            "=" * 50,
            "对账报告",
            "=" * 50,
            f"对账日期: {result.check_date}",
            f"对账类型: {result.check_type}",
            f"状态: {result.status}",
            "",
            "【内部一致性】",
            f"  检查用户数: {result.total_users}",
            f"  不一致用户数: {result.inconsistent_users}",
        ]

        if result.inconsistent_details:
            lines.append("  不一致详情 (前5条):")
            for detail in result.inconsistent_details[:5]:
                lines.append(f"    用户 {detail['user_id']}: 快照={detail['snapshot_balance']}, 计算={detail['calculated_balance']}")

        lines.extend([
            "",
            "【外部对账】",
            f"  账本充值总额: {result.ledger_recharge_total}",
            f"  网关充值总额: {result.gateway_recharge_total}",
            f"  差异: {result.gateway_diff}",
        ])

        if result.errors:
            lines.append("")
            lines.append("【错误详情】")
            for error in result.errors:
                lines.append(f"  - {error}")

        lines.append("")
        lines.append("=" * 50)

        if result.completed_at:
            duration = result.completed_at - result.created_at
            lines.append(f"对账耗时: {duration:.2f}秒")

        return "\n".join(lines)


class ReconciliationScheduler:
    """对账调度器"""

    def __init__(self, reconciliation_service: ReconciliationService):
        self.service = reconciliation_service
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self, hour: int = 2, minute: int = 0):
        """
        启动每日对账调度

        Args:
            hour: 每日对账执行小时（默认凌晨2点）
            minute: 分钟
        """
        if self._running:
            logger.warning("对账调度器已在运行")
            return

        self._running = True
        self._thread = threading.Thread(target=self._schedule_loop, args=(hour, minute), daemon=True)
        self._thread.start()
        logger.info(f"对账调度器已启动: 每天 {hour:02d}:{minute:02d} 执行")

    def stop(self):
        """停止调度"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("对账调度器已停止")

    def _schedule_loop(self, hour: int, minute: int):
        """调度循环"""
        while self._running:
            now = datetime.now()
            target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

            # 如果已过今天的对账时间，等待明天
            if target <= now:
                target += timedelta(days=1)

            wait_seconds = (target - now).total_seconds()
            logger.info(f"下次对账时间: {target}, 等待 {wait_seconds/3600:.1f} 小时")

            time.sleep(min(wait_seconds, 3600))  # 最多睡1小时再检查

            if not self._running:
                break

            # 执行对账
            try:
                logger.info("执行定时对账...")
                result = self.service.run_daily_reconciliation()
                report = self.service.get_reconciliation_report(result)
                logger.info(f"\n{report}")
            except Exception as e:
                logger.error(f"定时对账失败: {e}")
