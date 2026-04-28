"""
BudgetManager - 预算管理器

实现成本认知系统的第二层：预算管理

核心功能：
- 为每个任务分配预算
- 管理多种预算类型（任务预算、会话预算、日预算）
- 提供预算分配策略

借鉴企业预算管理理念：分级管控、动态调整

Author: LivingTreeAI Agent
Date: 2026-04-28
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger
import time
from datetime import datetime, timedelta


class BudgetType(Enum):
    """预算类型"""
    TASK = "task"         # 单个任务的预算
    SESSION = "session"   # 单次对话的总预算
    DAILY = "daily"       # 一天的总预算
    PROJECT = "project"   # 项目预算


class BudgetStatus(Enum):
    """预算状态"""
    NORMAL = "normal"           # 正常
    WARNING = "warning"         # 警告（接近预算上限）
    EXCEEDED = "exceeded"       # 已超预算


@dataclass
class Budget:
    """
    预算对象
    """
    budget_id: str
    budget_type: BudgetType
    amount_usd: float           # 预算金额（USD）
    spent_usd: float = 0.0      # 已消耗金额（USD）
    remaining_usd: float = 0.0  # 剩余金额（USD）
    status: BudgetStatus = BudgetStatus.NORMAL
    created_at: float = field(default_factory=lambda: time.time())
    updated_at: float = field(default_factory=lambda: time.time())
    
    def __post_init__(self):
        """初始化剩余金额"""
        self.remaining_usd = self.amount_usd
    
    def spend(self, amount: float) -> bool:
        """
        消耗预算
        
        Args:
            amount: 消耗金额（USD）
            
        Returns:
            是否消耗成功（剩余预算足够时返回True）
        """
        if amount <= self.remaining_usd:
            self.spent_usd += amount
            self.remaining_usd -= amount
            self.updated_at = time.time()
            self._update_status()
            return True
        else:
            return False
    
    def _update_status(self):
        """更新预算状态"""
        ratio = self.spent_usd / self.amount_usd
        
        if ratio >= 1.0:
            self.status = BudgetStatus.EXCEEDED
        elif ratio >= 0.8:
            self.status = BudgetStatus.WARNING
        else:
            self.status = BudgetStatus.NORMAL
    
    def reset(self):
        """重置预算"""
        self.spent_usd = 0.0
        self.remaining_usd = self.amount_usd
        self.status = BudgetStatus.NORMAL
        self.updated_at = time.time()


@dataclass
class SessionBudget:
    """
    会话预算（包含多层预算）
    """
    session_id: str
    task_budget: Budget = None
    session_budget: Budget = None
    daily_budget: Budget = None
    
    def get_total_spent(self) -> float:
        """获取总消耗"""
        total = 0.0
        if self.task_budget:
            total += self.task_budget.spent_usd
        if self.session_budget:
            total += self.session_budget.spent_usd
        return total
    
    def can_spend(self, amount: float) -> bool:
        """
        判断是否可以消耗指定金额
        
        Args:
            amount: 要消耗的金额（USD）
            
        Returns:
            是否可以消耗
        """
        # 检查所有层级的预算
        if self.task_budget and not self.task_budget.spend(amount):
            return False
        if self.session_budget and not self.session_budget.spend(amount):
            return False
        if self.daily_budget and not self.daily_budget.spend(amount):
            return False
        
        return True


class BudgetManager:
    """
    预算管理器
    
    管理多种类型的预算：
    1. 任务预算：单个任务的预算
    2. 会话预算：单次对话的总预算
    3. 日预算：一天的总预算
    4. 项目预算：项目级预算
    
    预算分配策略：
    - 简单任务 → 低预算（0.01 USD）
    - 中等任务 → 中预算（0.1 USD）
    - 复杂任务 → 高预算（1 USD）
    """
    
    def __init__(self):
        self._logger = logger.bind(component="BudgetManager")
        
        # 预算存储
        self._budgets: Dict[str, Budget] = {}
        self._session_budgets: Dict[str, SessionBudget] = {}
        
        # 默认预算配置
        self._default_budgets = {
            BudgetType.TASK: {
                "simple": 0.01,
                "medium": 0.1,
                "complex": 1.0,
                "expert": 5.0
            },
            BudgetType.SESSION: 5.0,    # 默认会话预算 5 USD
            BudgetType.DAILY: 10.0,     # 默认日预算 10 USD
        }
        
        # 初始化日预算
        self._init_daily_budget()
        
        self._logger.info("✅ BudgetManager 初始化完成")
    
    def _init_daily_budget(self):
        """初始化日预算"""
        today = datetime.now().strftime("%Y-%m-%d")
        daily_budget_id = f"daily_{today}"
        
        if daily_budget_id not in self._budgets:
            budget = Budget(
                budget_id=daily_budget_id,
                budget_type=BudgetType.DAILY,
                amount_usd=self._default_budgets[BudgetType.DAILY]
            )
            self._budgets[daily_budget_id] = budget
            self._logger.debug(f"📅 初始化日预算: {daily_budget_id}")
    
    def create_session_budget(self, session_id: str) -> SessionBudget:
        """
        创建会话预算
        
        Args:
            session_id: 会话ID
            
        Returns:
            会话预算对象
        """
        # 获取今日日预算
        today = datetime.now().strftime("%Y-%m-%d")
        daily_budget_id = f"daily_{today}"
        
        # 创建会话预算
        session_budget = SessionBudget(
            session_id=session_id,
            session_budget=Budget(
                budget_id=f"session_{session_id}",
                budget_type=BudgetType.SESSION,
                amount_usd=self._default_budgets[BudgetType.SESSION]
            ),
            daily_budget=self._budgets.get(daily_budget_id)
        )
        
        self._session_budgets[session_id] = session_budget
        self._logger.debug(f"🔄 创建会话预算: {session_id}")
        
        return session_budget
    
    def get_session_budget(self, session_id: str) -> Optional[SessionBudget]:
        """获取会话预算"""
        return self._session_budgets.get(session_id)
    
    def allocate_task_budget(self, session_id: str, complexity: str = "medium") -> float:
        """
        为任务分配预算
        
        Args:
            session_id: 会话ID
            complexity: 任务复杂度（simple/medium/complex/expert）
            
        Returns:
            分配的预算金额（USD）
        """
        # 获取预算配置
        budget_amount = self._default_budgets[BudgetType.TASK].get(complexity, 0.1)
        
        # 创建任务预算
        task_budget = Budget(
            budget_id=f"task_{session_id}_{int(time.time())}",
            budget_type=BudgetType.TASK,
            amount_usd=budget_amount
        )
        
        # 更新会话预算
        session_budget = self._session_budgets.get(session_id)
        if session_budget:
            session_budget.task_budget = task_budget
            self._budgets[task_budget.budget_id] = task_budget
        
        self._logger.debug(f"💰 分配任务预算: {session_id} -> ${budget_amount}")
        
        return budget_amount
    
    def spend_budget(self, session_id: str, amount: float) -> bool:
        """
        消耗预算
        
        Args:
            session_id: 会话ID
            amount: 消耗金额（USD）
            
        Returns:
            是否消耗成功
        """
        session_budget = self._session_budgets.get(session_id)
        if not session_budget:
            self._logger.warning(f"会话预算不存在: {session_id}")
            return False
        
        success = session_budget.can_spend(amount)
        
        if success:
            self._logger.debug(f"💸 消耗预算: {session_id} -> ${amount}")
        else:
            self._logger.warning(f"❌ 预算不足: {session_id}, 需要 ${amount}")
        
        return success
    
    def get_budget_status(self, session_id: str) -> Dict[str, Any]:
        """
        获取预算状态
        
        Args:
            session_id: 会话ID
            
        Returns:
            预算状态信息
        """
        session_budget = self._session_budgets.get(session_id)
        if not session_budget:
            return {"error": "会话预算不存在"}
        
        return {
            "session_id": session_id,
            "task": {
                "spent": session_budget.task_budget.spent_usd if session_budget.task_budget else 0.0,
                "remaining": session_budget.task_budget.remaining_usd if session_budget.task_budget else 0.0,
                "total": session_budget.task_budget.amount_usd if session_budget.task_budget else 0.0,
                "status": session_budget.task_budget.status.value if session_budget.task_budget else "none"
            },
            "session": {
                "spent": session_budget.session_budget.spent_usd if session_budget.session_budget else 0.0,
                "remaining": session_budget.session_budget.remaining_usd if session_budget.session_budget else 0.0,
                "total": session_budget.session_budget.amount_usd if session_budget.session_budget else 0.0,
                "status": session_budget.session_budget.status.value if session_budget.session_budget else "none"
            },
            "daily": {
                "spent": session_budget.daily_budget.spent_usd if session_budget.daily_budget else 0.0,
                "remaining": session_budget.daily_budget.remaining_usd if session_budget.daily_budget else 0.0,
                "total": session_budget.daily_budget.amount_usd if session_budget.daily_budget else 0.0,
                "status": session_budget.daily_budget.status.value if session_budget.daily_budget else "none"
            }
        }
    
    def check_budget_available(self, session_id: str, required_amount: float) -> bool:
        """
        检查预算是否足够
        
        Args:
            session_id: 会话ID
            required_amount: 需要的金额（USD）
            
        Returns:
            是否足够
        """
        session_budget = self._session_budgets.get(session_id)
        if not session_budget:
            return False
        
        total_remaining = 0.0
        
        if session_budget.task_budget:
            total_remaining += session_budget.task_budget.remaining_usd
        if session_budget.session_budget:
            total_remaining += session_budget.session_budget.remaining_usd
        
        return total_remaining >= required_amount
    
    def update_budget(self, budget_id: str, new_amount: float):
        """
        更新预算金额
        
        Args:
            budget_id: 预算ID
            new_amount: 新的预算金额（USD）
        """
        if budget_id in self._budgets:
            budget = self._budgets[budget_id]
            budget.amount_usd = new_amount
            budget.remaining_usd = new_amount - budget.spent_usd
            budget.updated_at = time.time()
            self._logger.info(f"🔧 更新预算: {budget_id} -> ${new_amount}")
    
    def reset_session_budget(self, session_id: str):
        """重置会话预算"""
        session_budget = self._session_budgets.get(session_id)
        if session_budget:
            if session_budget.task_budget:
                session_budget.task_budget.reset()
            if session_budget.session_budget:
                session_budget.session_budget.reset()
            self._logger.info(f"🔄 重置会话预算: {session_id}")
    
    def cleanup_expired_budgets(self):
        """清理过期预算（如昨日的日预算）"""
        today = datetime.now().strftime("%Y-%m-%d")
        expired_budgets = []
        
        for budget_id, budget in self._budgets.items():
            if budget.budget_type == BudgetType.DAILY and budget_id != f"daily_{today}":
                expired_budgets.append(budget_id)
        
        for budget_id in expired_budgets:
            del self._budgets[budget_id]
        
        if expired_budgets:
            self._logger.info(f"🗑️ 清理过期预算: {len(expired_budgets)} 个")


# 创建全局实例
budget_manager = BudgetManager()


def get_budget_manager() -> BudgetManager:
    """获取预算管理器实例"""
    return budget_manager


# 测试函数
async def test_budget_manager():
    """测试预算管理器"""
    import sys
    logger.remove()
    logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)
    
    print("=" * 60)
    print("测试 BudgetManager")
    print("=" * 60)
    
    manager = BudgetManager()
    
    # 1. 创建会话预算
    print("\n[1] 测试创建会话预算...")
    session_id = "test_session_001"
    session_budget = manager.create_session_budget(session_id)
    print(f"    ✓ 创建会话预算: {session_id}")
    print(f"    ✓ 会话预算金额: ${session_budget.session_budget.amount_usd}")
    
    # 2. 分配任务预算
    print("\n[2] 测试分配任务预算...")
    task_budget = manager.allocate_task_budget(session_id, "complex")
    print(f"    ✓ 分配任务预算: ${task_budget}")
    
    # 3. 测试消耗预算
    print("\n[3] 测试消耗预算...")
    success = manager.spend_budget(session_id, 0.5)
    print(f"    ✓ 消耗 $0.5: {'成功' if success else '失败'}")
    
    success = manager.spend_budget(session_id, 0.6)
    print(f"    ✓ 再消耗 $0.6: {'成功' if success else '失败'}")
    
    # 4. 测试预算状态
    print("\n[4] 测试预算状态...")
    status = manager.get_budget_status(session_id)
    print(f"    ✓ 任务预算状态: {status['task']['status']}")
    print(f"    ✓ 任务已消耗: ${status['task']['spent']:.2f}")
    print(f"    ✓ 任务剩余: ${status['task']['remaining']:.2f}")
    print(f"    ✓ 会话预算状态: {status['session']['status']}")
    
    # 5. 测试预算检查
    print("\n[5] 测试预算检查...")
    available = manager.check_budget_available(session_id, 0.5)
    print(f"    ✓ 预算是否足够 $0.5: {'是' if available else '否'}")
    
    # 6. 测试重置预算
    print("\n[6] 测试重置预算...")
    manager.reset_session_budget(session_id)
    status = manager.get_budget_status(session_id)
    print(f"    ✓ 重置后任务已消耗: ${status['task']['spent']:.2f}")
    
    print("\n" + "=" * 60)
    print("🎉 所有测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_budget_manager())