"""
数据库模型 - Database Models

提供账本的持久化存储接口
"""

import json
import time
import sqlite3
from pathlib import Path
from typing import List, Optional, Dict, Tuple
from decimal import Decimal
from contextlib import contextmanager

from ..transaction import Tx, OpType
from ..ledger import Ledger, AccountState


class LedgerDB:
    """
    账本数据库

    提供 Ledger 的持久化存储
    支持 SQLite
    """

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

        # 创建表
        self._create_tables()

    def _create_tables(self):
        """创建数据库表"""
        cursor = self._conn.cursor()

        # 交易账本表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tx_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tx_hash TEXT UNIQUE NOT NULL,
                prev_tx_hash TEXT NOT NULL,
                user_id TEXT NOT NULL,
                op_type TEXT NOT NULL,
                amount TEXT NOT NULL,
                nonce INTEGER NOT NULL,
                to_user_id TEXT,
                memo TEXT,
                relay_id TEXT,
                created_at REAL NOT NULL
            )
        """)

        # 索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_nonce ON tx_ledger(user_id, nonce)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_prev_hash ON tx_ledger(prev_tx_hash)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON tx_ledger(created_at)")

        # 账户快照表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS account_snapshot (
                user_id TEXT PRIMARY KEY,
                balance TEXT NOT NULL,
                last_nonce INTEGER NOT NULL,
                last_tx_hash TEXT NOT NULL,
                total_in TEXT NOT NULL,
                total_out TEXT NOT NULL,
                updated_at REAL NOT NULL
            )
        """)

        self._conn.commit()

    @contextmanager
    def _transaction(self):
        """事务上下文"""
        try:
            yield self._conn
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    # ────────────────────────────────────────────────────────────────
    # 交易操作
    # ────────────────────────────────────────────────────────────────

    def save_tx(self, tx: Tx) -> bool:
        """保存交易"""
        try:
            cursor = self._conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO tx_ledger
                (tx_hash, prev_tx_hash, user_id, op_type, amount, nonce,
                 to_user_id, memo, relay_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tx.tx_hash,
                tx.prev_tx_hash,
                tx.user_id,
                tx.op_type.value,
                str(tx.amount),
                tx.nonce,
                tx.to_user_id,
                tx.memo,
                tx.relay_id or "",
                tx.created_at
            ))
            self._conn.commit()
            return cursor.rowcount > 0
        except Exception:
            return False

    def get_tx(self, tx_hash: str) -> Optional[Tx]:
        """获取交易"""
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM tx_ledger WHERE tx_hash = ?", (tx_hash,))
        row = cursor.fetchone()

        if not row:
            return None

        return self._row_to_tx(row)

    def get_user_txs(
        self,
        user_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Tx]:
        """获取用户交易"""
        cursor = self._conn.cursor()
        cursor.execute("""
            SELECT * FROM tx_ledger
            WHERE user_id = ?
            ORDER BY nonce ASC
            LIMIT ? OFFSET ?
        """, (user_id, limit, offset))

        return [self._row_to_tx(row) for row in cursor.fetchall()]

    def get_all_txs(self, limit: int = 100, offset: int = 0) -> List[Tx]:
        """获取所有交易"""
        cursor = self._conn.cursor()
        cursor.execute("""
            SELECT * FROM tx_ledger
            ORDER BY id ASC
            LIMIT ? OFFSET ?
        """, (limit, offset))

        return [self._row_to_tx(row) for row in cursor.fetchall()]

    def get_tx_count(self) -> int:
        """获取交易总数"""
        cursor = self._conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM tx_ledger")
        return cursor.fetchone()[0]

    def get_last_tx(self, user_id: str) -> Optional[Tx]:
        """获取用户最后一笔交易"""
        cursor = self._conn.cursor()
        cursor.execute("""
            SELECT * FROM tx_ledger
            WHERE user_id = ?
            ORDER BY nonce DESC
            LIMIT 1
        """, (user_id,))
        row = cursor.fetchone()
        return self._row_to_tx(row) if row else None

    def _row_to_tx(self, row: sqlite3.Row) -> Tx:
        """行转交易"""
        return Tx(
            tx_hash=row['tx_hash'],
            prev_tx_hash=row['prev_tx_hash'],
            user_id=row['user_id'],
            op_type=OpType(row['op_type']),
            amount=Decimal(row['amount']),
            nonce=row['nonce'],
            to_user_id=row['to_user_id'],
            memo=row['memo'] or "",
            relay_id=row['relay_id'] or None,
            created_at=row['created_at']
        )

    # ────────────────────────────────────────────────────────────────
    # 账户操作
    # ────────────────────────────────────────────────────────────────

    def save_account_state(self, state: AccountState):
        """保存账户状态"""
        cursor = self._conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO account_snapshot
            (user_id, balance, last_nonce, last_tx_hash, total_in, total_out, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            state.user_id,
            str(state.balance),
            state.last_nonce,
            state.last_tx_hash,
            str(state.total_in),
            str(state.total_out),
            time.time()
        ))
        self._conn.commit()

    def get_account_state(self, user_id: str) -> Optional[AccountState]:
        """获取账户状态"""
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM account_snapshot WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()

        if not row:
            return None

        return AccountState(
            user_id=row['user_id'],
            balance=Decimal(row['balance']),
            last_nonce=row['last_nonce'],
            last_tx_hash=row['last_tx_hash'],
            total_in=Decimal(row['total_in']),
            total_out=Decimal(row['total_out'])
        )

    def get_all_accounts(self) -> List[AccountState]:
        """获取所有账户"""
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM account_snapshot")
        rows = cursor.fetchall()

        return [
            AccountState(
                user_id=row['user_id'],
                balance=Decimal(row['balance']),
                last_nonce=row['last_nonce'],
                last_tx_hash=row['last_tx_hash'],
                total_in=Decimal(row['total_in']),
                total_out=Decimal(row['total_out'])
            )
            for row in rows
        ]

    # ────────────────────────────────────────────────────────────────
    # 批量操作
    # ────────────────────────────────────────────────────────────────

    def bulk_save_txs(self, txs: List[Tx]) -> Tuple[int, int]:
        """
        批量保存交易

        Returns:
            (success_count, fail_count)
        """
        success = 0
        fail = 0

        for tx in txs:
            if self.save_tx(tx):
                success += 1
            else:
                fail += 1

        return success, fail

    def rebuild_ledger(self) -> Ledger:
        """
        从数据库重建账本

        用于节点启动时加载历史数据
        """
        ledger = Ledger(db_path=self.db_path)

        cursor = self._conn.cursor()

        # 加载所有交易
        cursor.execute("SELECT * FROM tx_ledger ORDER BY id ASC")
        for row in cursor.fetchall():
            tx = self._row_to_tx(row)
            if tx.tx_hash not in ledger.txs:
                ledger.txs[tx.tx_hash] = tx
                ledger.tx_order.append(tx.tx_hash)
                ledger.user_txs[tx.user_id].append(tx.tx_hash)

        # 重建账户状态
        for state in self.get_all_accounts():
            ledger.account_cache[state.user_id] = state

        return ledger

    # ────────────────────────────────────────────────────────────────
    # 统计
    # ────────────────────────────────────────────────────────────────

    def get_stats(self) -> Dict:
        """获取统计信息"""
        cursor = self._conn.cursor()

        cursor.execute("SELECT COUNT(*) as count FROM tx_ledger")
        tx_count = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM account_snapshot")
        user_count = cursor.fetchone()['count']

        cursor.execute("SELECT SUM(CAST(amount AS REAL)) as total FROM tx_ledger WHERE op_type IN ('IN', 'TRANSFER_IN')")
        total_in = cursor.fetchone()['total'] or 0

        cursor.execute("SELECT SUM(CAST(amount AS REAL)) as total FROM tx_ledger WHERE op_type IN ('OUT', 'TRANSFER_OUT')")
        total_out = cursor.fetchone()['total'] or 0

        return {
            "tx_count": tx_count,
            "user_count": user_count,
            "total_in": total_in,
            "total_out": total_out,
            "circulating": total_in - total_out
        }

    def close(self):
        """关闭数据库"""
        if self._conn:
            self._conn.close()
            self._conn = None


class PersistentLedger:
    """
    持久化账本

    组合 Ledger + LedgerDB
    提供自动持久化
    """

    def __init__(self, db_path: str = "relay_chain.db"):
        self.db_path = db_path
        self.db = LedgerDB(db_path)

        # 尝试从数据库重建
        self.ledger = self.db.rebuild_ledger()

        # 如果是新建的数据库，设置创世块
        if not self.ledger.tx_order:
            self.ledger.genesis_hash = self.ledger._compute_genesis()

    def add_tx_with_persist(self, tx: Tx) -> Tuple[bool, str]:
        """添加交易并持久化"""
        ok, msg = self.ledger.add_tx(tx)
        if ok:
            self.db.save_tx(tx)
            # 更新账户快照
            state = self.ledger.account_cache.get(tx.user_id)
            if state:
                self.db.save_account_state(state)
        return ok, msg

    def get_balance(self, user_id: str) -> Decimal:
        """获取余额"""
        return self.ledger.get_balance(user_id)

    def get_user_txs(self, user_id: str, limit: int = 100, offset: int = 0) -> List[Tx]:
        """获取用户交易"""
        return self.ledger.get_user_txs(user_id, limit, offset)

    def get_stats(self) -> Dict:
        """获取统计"""
        return self.ledger.get_stats()

    def close(self):
        """关闭"""
        self.db.close()