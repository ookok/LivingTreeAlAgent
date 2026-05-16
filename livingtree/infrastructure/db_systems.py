"""DBSystems — Complete database infrastructure: migrations, NoSQL, graph, pooling, cache, health, seeding, ETL.

Fills ALL remaining database gaps:
  1. Core Table Migrations — versioned schema for all infrastructure tables
  2. NoSQL Backend — Redis (cache/distributed) + MongoDB (document store)
  3. Graph Database — Neo4j driver for knowledge graph
  4. Connection Pool — async pool with health checks
  5. Distributed Cache — Redis-backed with in-memory fallback
  6. DB Health Monitor — per-DB health checks + metrics
  7. Data Seeding — fixture-based test data generation
  8. ETL Pipeline — cross-DB data migration
  9. PostgreSQL/MySQL backends — asyncpg/aiomysql drivers
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from datetime import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from loguru import logger

import aiomysql
import asyncpg
import redis.asyncio as aioredis
from motor.motor_asyncio import AsyncIOMotorClient
from neo4j import AsyncGraphDatabase


# ═══ 1. Core Table Migrations ════════════════════════════════════

@dataclass
class Migration:
    version: int
    name: str
    up: str       # SQL to apply
    down: str     # SQL to rollback
    applied_at: float = 0.0


class CoreMigrationManager:
    """Versioned schema migration for all core infrastructure tables.

    Unlike database/migrations.py (which handles app-level schemas v7-v26),
    this handles the 5 core infrastructure SQLite databases.
    """

    MIGRATIONS: list[Migration] = [
        # LivingStore
        Migration(1, "living_store_v1", """
            CREATE TABLE IF NOT EXISTS store (
                path TEXT PRIMARY KEY, data BLOB, size INTEGER,
                created REAL, accessed REAL, phase TEXT DEFAULT 'liquid'
            )
        """, "DROP TABLE IF EXISTS store"),
        Migration(2, "living_store_v2", """
            ALTER TABLE store ADD COLUMN ttl REAL DEFAULT 0;
            ALTER TABLE store ADD COLUMN compressed INTEGER DEFAULT 0;
        """, "CREATE TABLE store_backup AS SELECT path,data,size,created,accessed FROM store; DROP TABLE store; ALTER TABLE store_backup RENAME TO store"),
        
        # StructMem
        Migration(10, "struct_mem_v1", """
            CREATE TABLE IF NOT EXISTS entries (
                id TEXT PRIMARY KEY, content TEXT, role TEXT,
                session_id TEXT, timestamp REAL, access_count INTEGER DEFAULT 0,
                prominence REAL DEFAULT 0.5, decay_factor REAL DEFAULT 1.0
            )
        """, "DROP TABLE IF EXISTS entries"),
        Migration(11, "struct_mem_v2", """
            CREATE TABLE IF NOT EXISTS synthesis (
                id TEXT PRIMARY KEY, content TEXT, source_entries TEXT,
                timestamp REAL, confidence REAL DEFAULT 0.5
            )
        """, "DROP TABLE IF EXISTS synthesis"),
        
        # KnowledgeBase
        Migration(20, "kb_v1", """
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY, title TEXT, content TEXT,
                domain TEXT, created_at REAL, updated_at REAL,
                word_count INTEGER, source_format TEXT
            )
        """, "DROP TABLE IF EXISTS documents"),
        Migration(21, "kb_v2", """
            CREATE TABLE IF NOT EXISTS vectors (
                id TEXT PRIMARY KEY, doc_id TEXT, embedding BLOB,
                dim INTEGER DEFAULT 128, model TEXT DEFAULT 'local'
            )
        """, "DROP TABLE IF EXISTS vectors"),
        
        # KnowledgeGraph
        Migration(30, "graph_v1", """
            CREATE TABLE IF NOT EXISTS entities (
                id TEXT PRIMARY KEY, label TEXT, properties TEXT,
                created REAL
            )
        """, "DROP TABLE IF EXISTS entities"),
        Migration(31, "graph_v2", """
            CREATE TABLE IF NOT EXISTS edges (
                id TEXT PRIMARY KEY, source_id TEXT, target_id TEXT,
                predicate TEXT, weight REAL DEFAULT 1.0, properties TEXT
            )
        """, "DROP TABLE IF EXISTS edges"),
        
        # Config
        Migration(40, "config_v1", """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY, value TEXT,
                updated_at REAL, source TEXT DEFAULT 'user'
            )
        """, "DROP TABLE IF EXISTS settings"),
        
        # Audit
        Migration(50, "audit_v1", """
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event TEXT, details TEXT, timestamp REAL,
                user_id TEXT DEFAULT '', session_id TEXT DEFAULT ''
            )
        """, "DROP TABLE IF EXISTS audit_log"),
    ]

    def __init__(self, db_path: str):
        self._path = db_path

    async def migrate(self) -> dict:
        """Run all pending migrations."""
        import sqlite3
        conn = sqlite3.connect(self._path)

        # Ensure schema_migrations table
        conn.execute("""CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY, name TEXT, applied_at REAL)""")

        current = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
        applied = 0

        for mig in self.MIGRATIONS:
            if mig.version in current:
                continue
            try:
                for stmt in mig.up.split(";"):
                    stmt = stmt.strip()
                    if stmt:
                        conn.execute(stmt)
                conn.execute("INSERT INTO schema_migrations VALUES(?,?,?)",
                           (mig.version, mig.name, time.time()))
                conn.commit()
                applied += 1
                logger.debug(f"Migration {mig.version}: {mig.name}")
            except Exception as e:
                logger.warning(f"Migration {mig.version} failed: {e}")
                conn.rollback()

        conn.close()
        return {"applied": applied, "total": len(self.MIGRATIONS),
                "pending": len(self.MIGRATIONS) - len(current) - applied}

    async def rollback(self, to_version: int) -> int:
        """Rollback to a specific version."""
        import sqlite3
        conn = sqlite3.connect(self._path)
        rolled = 0

        for mig in reversed(self.MIGRATIONS):
            if mig.version <= to_version:
                break
            try:
                for stmt in mig.down.split(";"):
                    stmt = stmt.strip()
                    if stmt:
                        conn.execute(stmt)
                conn.execute("DELETE FROM schema_migrations WHERE version=?",
                           (mig.version,))
                conn.commit()
                rolled += 1
            except Exception as e:
                logger.warning(f"Rollback {mig.version} failed: {e}")

        conn.close()
        return rolled


# ═══ 2. NoSQL Backends ════════════════════════════════════════════

class RedisBackend:
    """Async Redis client for distributed caching and pub/sub."""

    def __init__(self, url: str = ""):
        self._url = url or "redis://localhost:6379"
        self._client: Any = None

    async def connect(self) -> bool:
        if not aioredis is not None:
            return False
        try:
            self._client = aioredis.from_url(self._url, decode_responses=True)
            await self._client.ping()
            return True
        except Exception:
            self._client = None
            return False

    async def get(self, key: str) -> str | None:
        if self._client:
            return await self._client.get(key)
        return None

    async def set(self, key: str, value: str, ttl: int = 0) -> bool:
        if self._client:
            if ttl > 0:
                await self._client.setex(key, ttl, value)
            else:
                await self._client.set(key, value)
            return True
        return False

    async def delete(self, key: str) -> int:
        if self._client:
            return await self._client.delete(key)
        return 0

    async def cache_get(self, key: str) -> Any:
        """Get JSON-deserialized cache value."""
        raw = await self.get(key)
        return json.loads(raw) if raw else None

    async def cache_set(self, key: str, value: Any, ttl: int = 300) -> bool:
        return await self.set(key, json.dumps(value, default=str), ttl)

    async def publish(self, channel: str, message: str) -> int:
        if self._client:
            return await self._client.publish(channel, message)
        return 0

    async def close(self):
        if self._client:
            await self._client.close()

    @property
    def available(self) -> bool:
        return self._client is not None


class MongoBackend:
    """Async MongoDB client for document storage."""

    def __init__(self, url: str = "", db_name: str = "livingtree"):
        self._url = url or "mongodb://localhost:27017"
        self._db_name = db_name
        self._client: Any = None
        self._db: Any = None

    async def connect(self) -> bool:
        if not AsyncIOMotorClient is not None:
            return False
        try:
            self._client = AsyncIOMotorClient(self._url, serverSelectionTimeoutMS=5000)
            self._db = self._client[self._db_name]
            await self._client.admin.command('ping')
            return True
        except Exception:
            return False

    async def insert(self, collection: str, doc: dict) -> str:
        if self._db:
            result = await self._db[collection].insert_one(doc)
            return str(result.inserted_id)
        return ""

    async def find(self, collection: str, query: dict,
                   limit: int = 100) -> list[dict]:
        if self._db:
            cursor = self._db[collection].find(query).limit(limit)
            docs = await cursor.to_list(length=limit)
            for d in docs:
                d["_id"] = str(d["_id"])
            return docs
        return []

    async def update(self, collection: str, query: dict,
                     update: dict) -> int:
        if self._db:
            result = await self._db[collection].update_many(query, {"$set": update})
            return result.modified_count
        return 0

    async def close(self):
        if self._client:
            self._client.close()

    @property
    def available(self) -> bool:
        return self._client is not None


# ═══ 3. Neo4j Graph Database ════════════════════════════════════

class Neo4jBackend:
    """Async Neo4j driver for knowledge graph storage."""

    def __init__(self, url: str = "", user: str = "", password: str = ""):
        self._url = url or "bolt://localhost:7687"
        self._user = user or "neo4j"
        self._password = password or "password"
        self._driver: Any = None

    async def connect(self) -> bool:
        if not AsyncGraphDatabase is not None:
            return False
        try:
            self._driver = AsyncGraphDatabase.driver(
                self._url, auth=(self._user, self._password))
            await self._driver.verify_connectivity()
            return True
        except Exception:
            return False

    async def create_entity(self, label: str, properties: dict) -> str:
        if not self._driver:
            return ""
        async with self._driver.session() as session:
            result = await session.run(
                f"CREATE (n:{label} $props) RETURN n",
                props=properties,
            )
            record = await result.single()
            return str(record["n"].id) if record else ""

    async def create_relation(self, source_id: int, target_id: int,
                              predicate: str, properties: dict = None) -> bool:
        if not self._driver:
            return False
        async with self._driver.session() as session:
            await session.run(
                "MATCH (a), (b) WHERE id(a)=$sid AND id(b)=$tid "
                f"CREATE (a)-[r:{predicate} $props]->(b)",
                sid=source_id, tid=target_id,
                props=properties or {},
            )
            return True

    async def query(self, cypher: str, params: dict = None) -> list[dict]:
        if not self._driver:
            return []
        async with self._driver.session() as session:
            result = await session.run(cypher, params or {})
            records = await result.data()
            return records

    async def close(self):
        if self._driver:
            await self._driver.close()

    @property
    def available(self) -> bool:
        return self._driver is not None


# ═══ 4. Connection Pool + DB Health ═══════════════════════════════

@dataclass
class PoolStats:
    size: int = 0
    active: int = 0
    idle: int = 0
    max_overflow: int = 5
    hits: int = 0
    misses: int = 0
    errors: int = 0


class AsyncConnectionPool:
    """Async database connection pool with health checks."""

    def __init__(self, db_path: str, pool_size: int = 5,
                 max_overflow: int = 5):
        self._path = db_path
        self._pool_size = pool_size
        self._max_overflow = max_overflow
        self._pool: list[Any] = []
        self._active: set[Any] = set()
        self._lock = asyncio.Semaphore(pool_size + max_overflow)
        self._stats = PoolStats(size=pool_size, max_overflow=max_overflow)

    async def acquire(self):
        """Acquire a connection from the pool."""
        import sqlite3
        await self._lock.acquire()

        if self._pool:
            conn = self._pool.pop()
        else:
            conn = sqlite3.connect(self._path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")

        self._active.add(conn)
        self._stats.active = len(self._active)
        self._stats.idle = len(self._pool)
        return conn

    async def release(self, conn):
        """Return a connection to the pool."""
        self._active.discard(conn)
        if len(self._pool) < self._pool_size:
            self._pool.append(conn)
        else:
            conn.close()
        self._stats.active = len(self._active)
        self._stats.idle = len(self._pool)
        self._lock.release()

    async def health_check(self) -> dict:
        """Check all connections in the pool."""
        results = []
        for conn in list(self._pool) + list(self._active):
            try:
                conn.execute("SELECT 1")
                results.append("ok")
            except Exception:
                results.append("dead")
                self._pool = [c for c in self._pool if c is not conn]
        return {
            "total": len(results),
            "healthy": results.count("ok"),
            "dead": results.count("dead"),
        }

    def stats(self) -> PoolStats:
        return self._stats


class DBHealthMonitor:
    """Monitor health of all database backends."""

    def __init__(self):
        self._checks: dict[str, callable] = {}
        self._history: list[dict] = []

    def register(self, name: str, check_fn: callable):
        self._checks[name] = check_fn

    async def check_all(self) -> dict:
        """Run all registered health checks."""
        results = {}
        for name, check in self._checks.items():
            try:
                ok = await check() if asyncio.iscoroutinefunction(check) else check()
                results[name] = "healthy" if ok else "unhealthy"
            except Exception as e:
                results[name] = f"error: {str(e)[:60]}"

        self._history.append({"timestamp": time.time(), "results": results})
        if len(self._history) > 100:
            self._history = self._history[-100:]
        return results

    def history(self, limit: int = 20) -> list[dict]:
        return self._history[-limit:]


# ═══ 5. Distributed Cache (Redis + In-Memory fallback) ═══════════

class DistributedCache:
    """Two-tier cache: Redis (distributed) + in-memory LRU (local fallback)."""

    def __init__(self, redis_url: str = "", max_local: int = 1000):
        self._redis = RedisBackend(redis_url)
        self._local: dict[str, tuple[Any, float]] = {}  # {key: (value, expiry)}
        self._max_local = max_local
        self._hits = self._misses = 0

    async def connect(self):
        await self._redis.connect()

    async def get(self, key: str) -> Any:
        # Try Redis first
        if self._redis.available:
            val = await self._redis.cache_get(key)
            if val is not None:
                self._hits += 1
                return val

        # Fallback to local
        entry = self._local.get(key)
        if entry and (entry[1] == 0 or entry[1] > time.time()):
            self._hits += 1
            return entry[0]

        self._misses += 1
        return None

    async def set(self, key: str, value: Any, ttl: int = 300):
        # Set in Redis if available
        if self._redis.available:
            await self._redis.cache_set(key, value, ttl)

        # Always set locally
        expiry = time.time() + ttl if ttl > 0 else 0
        self._local[key] = (value, expiry)

        # Evict oldest if over max
        if len(self._local) > self._max_local:
            oldest = min(self._local.keys(),
                        key=lambda k: self._local[k][1] or float('inf'))
            del self._local[oldest]

    async def delete(self, key: str):
        if self._redis.available:
            await self._redis.delete(key)
        self._local.pop(key, None)

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / max(total, 1)

    @property
    def stats(self) -> dict:
        return {"hits": self._hits, "misses": self._misses,
                "hit_rate": f"{self.hit_rate:.1%}",
                "local_entries": len(self._local),
                "redis_available": self._redis.available}


# ═══ 6. Data Seeding / Fixtures ═══════════════════════════════════

class DataSeeder:
    """Generate test data fixtures for all core tables."""

    @staticmethod
    async def seed_knowledge_base(db) -> int:
        """Seed KnowledgeBase with sample documents."""
        docs = [
            {"id": "seed_1", "title": "环评报告模板", "content": "# 环境影响评价报告\n\n## 总论\n...",
             "domain": "eia", "word_count": 500, "source_format": "markdown"},
            {"id": "seed_2", "title": "GB 3095-2012 环境空气质量标准",
             "content": "本标准规定了环境空气功能区分类...",
             "domain": "standards", "word_count": 3000, "source_format": "text"},
            {"id": "seed_3", "title": "水质监测规范", "content": "# 水质监测\n\n## 采样方法\n...",
             "domain": "water", "word_count": 800, "source_format": "markdown"},
        ]
        count = 0
        for doc in docs:
            doc["created_at"] = time.time()
            doc["updated_at"] = time.time()
            await db.insert("documents", doc)
            count += 1
        return count

    @staticmethod
    async def seed_audit_log(db) -> int:
        events = [
            ("report_generated", "eia_report", "user_001"),
            ("gap_resolved", "knowledge", "auto"),
            ("backup_created", "periodic", "auto"),
        ]
        count = 0
        for event, detail, user in events:
            await db.insert("audit_log", {
                "event": event, "details": json.dumps({"type": detail}),
                "timestamp": time.time(), "user_id": user,
            })
            count += 1
        return count


# ═══ 7. ETL Pipeline — cross-DB data migration ════════════════════

class ETLPipeline:
    """Extract-Transform-Load between different database backends."""

    @staticmethod
    async def sqlite_to_mongo(db_path: str, collection: str,
                              query: str = "", mongo_url: str = "") -> dict:
        """ETL: SQLite table → MongoDB collection."""
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute(query or f"SELECT * FROM {collection}")]
        conn.close()

        mongo = MongoBackend(mongo_url)
        if not await mongo.connect():
            return {"error": "MongoDB unavailable"}

        count = 0
        for row in rows:
            row["_source_db"] = db_path
            row["_etl_ts"] = time.time()
            await mongo.insert(collection, row)
            count += 1

        await mongo.close()
        return {"source": db_path, "target": f"mongodb:{collection}",
                "rows": count, "status": "ok"}

    @staticmethod
    async def sqlite_to_redis(db_path: str, key_prefix: str,
                              query: str = "", redis_url: str = "") -> dict:
        """ETL: SQLite query results → Redis as JSON cache."""
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = [dict(r) for r in conn.execute(query or "SELECT * FROM sqlite_master LIMIT 100")]
        conn.close()

        redis = RedisBackend(redis_url)
        if not await redis.connect():
            return {"error": "Redis unavailable"}

        for row in rows:
            key = f"{key_prefix}:{hashlib.md5(str(row).encode()).hexdigest()[:8]}"
            await redis.cache_set(key, row, ttl=3600)

        await redis.close()
        return {"source": db_path, "target": f"redis:{key_prefix}:*",
                "rows": len(rows), "status": "ok"}

    @staticmethod
    async def sqlite_to_neo4j(db_path: str, entity_query: str = "",
                              edge_query: str = "", neo4j_url: str = "") -> dict:
        """ETL: SQLite knowledge graph → Neo4j."""
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        entities = [dict(r) for r in conn.execute(
            entity_query or "SELECT * FROM entities")]
        edges = [dict(r) for r in conn.execute(
            edge_query or "SELECT * FROM edges")]

        conn.close()

        neo = Neo4jBackend(neo4j_url)
        if not await neo.connect():
            return {"error": "Neo4j unavailable"}

        e_count = 0
        for e in entities:
            if await neo.create_entity("Entity", e):
                e_count += 1

        r_count = 0
        for e in edges:
            if await neo.create_relation(
                hash(e.get("source_id","")), hash(e.get("target_id","")),
                e.get("predicate", "RELATED"), e,
            ):
                r_count += 1

        await neo.close()
        return {"entities": e_count, "relations": r_count, "status": "ok"}


# ═══ 8. PostgreSQL / MySQL Backends ═══════════════════════════════

class PGBackend:
    """Async PostgreSQL driver."""

    def __init__(self, dsn: str = ""):
        self._dsn = dsn or "postgresql://localhost/livingtree"
        self._pool: Any = None

    async def connect(self) -> bool:
        if not asyncpg is not None:
            return False
        try:
            self._pool = await asyncpg.create_pool(self._dsn, min_size=2, max_size=10)
            return True
        except Exception:
            return False

    async def fetch(self, sql: str, *params) -> list[dict]:
        if self._pool:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(sql, *params)
                return [dict(r) for r in rows]
        return []

    async def execute(self, sql: str, *params) -> str:
        if self._pool:
            async with self._pool.acquire() as conn:
                return await conn.execute(sql, *params)
        return ""

    async def close(self):
        if self._pool:
            await self._pool.close()

    @property
    def available(self) -> bool:
        return self._pool is not None


class MySQLBackend:
    """Async MySQL driver."""

    def __init__(self, host: str = "localhost", port: int = 3306,
                 user: str = "root", password: str = "",
                 db: str = "livingtree"):
        self._config = {"host": host, "port": port, "user": user,
                       "password": password, "db": db}
        self._pool: Any = None

    async def connect(self) -> bool:
        if not aiomysql is not None:
            return False
        try:
            self._pool = await aiomysql.create_pool(**self._config,
                                                     minsize=2, maxsize=10)
            return True
        except Exception:
            return False

    async def fetch(self, sql: str, params: tuple = ()) -> list[dict]:
        if self._pool:
            async with self._pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(sql, params)
                    return await cur.fetchall()
        return []

    async def execute(self, sql: str, params: tuple = ()) -> int:
        if self._pool:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    rows = await cur.execute(sql, params)
                    await conn.commit()
                    return rows
        return 0

    async def close(self):
        if self._pool:
            self._pool.close()
            await self._pool.wait_closed()

    @property
    def available(self) -> bool:
        return self._pool is not None


# ═══ 9. Unified DB Systems Hub ════════════════════════════════════

class DBSystemsHub:
    """Unified access to ALL database subsystems.

    One-liner to initialize everything:
        hub = DBSystemsHub()
        await hub.initialize()
        health = await hub.health()
    """

    def __init__(self):
        self.migrator: Optional[CoreMigrationManager] = None
        self.redis: Optional[RedisBackend] = None
        self.mongo: Optional[MongoBackend] = None
        self.neo4j: Optional[Neo4jBackend] = None
        self.pg: Optional[PGBackend] = None
        self.mysql: Optional[MySQLBackend] = None
        self.cache: Optional[DistributedCache] = None
        self.health_monitor = DBHealthMonitor()
        self._initialized = False

    async def initialize(self, db_paths: dict = None) -> dict:
        """Initialize all database subsystems. Gracefully degrades.

        db_paths: {"store": "path", "knowledge": "path", ...}
        """
        paths = db_paths or {}
        results = {}

        # Core migrations
        store_path = paths.get("store", ".livingtree/living_store.db")
        self.migrator = CoreMigrationManager(store_path)
        try:
            mg_result = await self.migrator.migrate()
            results["migrations"] = mg_result
        except Exception as e:
            results["migrations"] = {"error": str(e)}

        # Redis
        self.redis = RedisBackend()
        results["redis"] = "ok" if await self.redis.connect() else "unavailable"

        # MongoDB
        self.mongo = MongoBackend()
        results["mongo"] = "ok" if await self.mongo.connect() else "unavailable"

        # Neo4j
        self.neo4j = Neo4jBackend()
        results["neo4j"] = "ok" if await self.neo4j.connect() else "unavailable"

        # PostgreSQL
        self.pg = PGBackend()
        results["pg"] = "ok" if await self.pg.connect() else "unavailable"

        # MySQL
        self.mysql = MySQLBackend()
        results["mysql"] = "ok" if await self.mysql.connect() else "unavailable"

        # Distributed cache
        self.cache = DistributedCache()
        await self.cache.connect()
        results["cache"] = f"local:{self.cache.stats['local_entries']}"

        # Health monitor
        self.health_monitor.register("redis", lambda: self.redis.available if self.redis else False)
        self.health_monitor.register("mongo", lambda: self.mongo.available if self.mongo else False)
        self.health_monitor.register("neo4j", lambda: self.neo4j.available if self.neo4j else False)
        self.health_monitor.register("pg", lambda: self.pg.available if self.pg else False)
        self.health_monitor.register("mysql", lambda: self.mysql.available if self.mysql else False)

        self._initialized = True
        logger.info(f"DBSystemsHub initialized: {results}")
        return results

    async def health(self) -> dict:
        return await self.health_monitor.check_all()

    async def close(self):
        for backend in [self.redis, self.mongo, self.neo4j, self.pg, self.mysql]:
            if backend:
                await backend.close()


__all__ = [
    "CoreMigrationManager", "Migration",
    "RedisBackend", "MongoBackend", "Neo4jBackend",
    "AsyncConnectionPool", "DBHealthMonitor",
    "DistributedCache",
    "DataSeeder", "ETLPipeline",
    "PGBackend", "MySQLBackend",
    "DBSystemsHub",
]
