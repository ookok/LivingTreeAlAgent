"""
爬虫调度器 (Crawler Dispatcher)
===============================

浏览器即爬虫调度器：可视化配置爬虫规则

功能：
1. 可视化爬虫规则配置
2. 定时任务调度
3. 数据回流到邮件/SQLite
4. 节点集群分布式爬取
"""

import asyncio
import json
import re
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

import aiohttp


class CrawlStatus(Enum):
    """爬取状态"""
    PENDING = "pending"       # 待爬取
    RUNNING = "running"       # 爬取中
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"         # 失败


class DataSinkType(Enum):
    """数据sink类型"""
    EMAIL = "email"           # 邮件
    DATABASE = "database"     # SQLite
    FILE = "file"            # 文件
    API = "api"              # 外部API


@dataclass
class SelectorRule:
    """选择器规则"""
    name: str                # 规则名称
    selector: str            # CSS/XPath 选择器
    extract_type: str = "text"  # text/html/attr
    attribute: str = ""      # 属性名（如果 extract_type 是 attr）


@dataclass
class CrawlTask:
    """爬取任务"""
    task_id: str
    name: str
    url: str
    selectors: list[SelectorRule] = field(default_factory=list)
    interval_hours: int = 24
    status: CrawlStatus = CrawlStatus.PENDING
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    enabled: bool = True
    sink_type: DataSinkType = DataSinkType.EMAIL
    sink_config: dict[str, Any] = field(default_factory=dict)


@dataclass
class CrawlResult:
    """爬取结果"""
    task_id: str
    status: CrawlStatus
    data: dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    crawled_at: datetime = field(default_factory=datetime.now)


class CrawlerDispatcher:
    """
    爬虫调度器

    功能：
    1. 可视化配置爬虫规则
    2. 定时任务调度
    3. 数据回流到各种 sink
    4. 分布式节点爬取（通过 P2P 网络）
    """

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir / "crawler_dispatcher"
        self.db_path = self.data_dir / "crawlers.db"

        # 确保目录存在
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 初始化数据库
        self._init_database()

        # HTTP 会话
        self._session: Optional[aiohttp.ClientSession] = None

        # 运行中的任务
        self._running_tasks: dict[str, asyncio.Task] = {}

        # 调度器
        self._scheduler_task: Optional[asyncio.Task] = None

    def _init_database(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 爬取任务表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS crawl_tasks (
                task_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                selectors TEXT NOT NULL,
                interval_hours INTEGER DEFAULT 24,
                status TEXT DEFAULT 'pending',
                last_run TEXT,
                next_run TEXT,
                enabled INTEGER DEFAULT 1,
                sink_type TEXT DEFAULT 'email',
                sink_config TEXT
            )
        """)

        # 爬取结果表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS crawl_results (
                result_id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                status TEXT NOT NULL,
                data TEXT,
                error_message TEXT,
                crawled_at TEXT NOT NULL
            )
        """)

        conn.commit()
        conn.close()

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取 HTTP 会话"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    def create_task(
        self,
        name: str,
        url: str,
        selectors: list[SelectorRule],
        interval_hours: int = 24,
        sink_type: DataSinkType = DataSinkType.EMAIL,
        sink_config: Optional[dict[str, Any]] = None
    ) -> str:
        """创建爬取任务"""
        task_id = str(uuid.uuid4())[:12]

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO crawl_tasks
            (task_id, name, url, selectors, interval_hours, status, next_run,
             enabled, sink_type, sink_config)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
        """, (
            task_id,
            name,
            url,
            json.dumps([{"name": s.name, "selector": s.selector,
                        "extract_type": s.extract_type, "attribute": s.attribute}
                       for s in selectors]),
            interval_hours,
            CrawlStatus.PENDING.value,
            datetime.now().isoformat(),
            sink_type.value,
            json.dumps(sink_config or {})
        ))

        conn.commit()
        conn.close()

        return task_id

    async def execute_task(self, task_id: str) -> CrawlResult:
        """执行爬取任务"""
        # 获取任务配置
        task = self._get_task(task_id)
        if not task:
            return CrawlResult(
                task_id=task_id,
                status=CrawlStatus.FAILED,
                error_message="Task not found"
            )

        # 更新状态
        await self._update_task_status(task_id, CrawlStatus.RUNNING)

        try:
            # 爬取网页
            data = await self._fetch_and_extract(task)

            # 保存结果
            result = CrawlResult(
                task_id=task_id,
                status=CrawlStatus.COMPLETED,
                data=data
            )

            # 发送到 sink
            await self._send_to_sink(task, data)

            # 更新任务状态
            await self._update_task_status(task_id, CrawlStatus.COMPLETED)
            await self._update_task_next_run(task_id)

            return result

        except Exception as e:
            result = CrawlResult(
                task_id=task_id,
                status=CrawlStatus.FAILED,
                error_message=str(e)
            )
            await self._update_task_status(task_id, CrawlStatus.FAILED)
            return result

    async def _fetch_and_extract(self, task: CrawlTask) -> dict[str, Any]:
        """爬取并提取数据"""
        session = await self._get_session()

        async with session.get(task.url, timeout=aiohttp.ClientTimeout(total=30)) as response:
            if response.status != 200:
                raise Exception(f"HTTP {response.status}")

            html = await response.text()

            # 提取数据
            data = {"url": task.url, "crawled_at": datetime.now().isoformat(), "items": {}}

            for selector in task.selectors:
                items = self._extract_with_selector(html, selector)
                data["items"][selector.name] = items

            return data

    def _extract_with_selector(self, html: str, selector: SelectorRule) -> list[str]:
        """使用选择器提取数据"""
        results = []

        if selector.extract_type == "text":
            # 提取文本
            pattern = rf'<{selector.selector}[^>]*>([^<]+)</{selector.selector}>'
            matches = re.findall(pattern, html, re.IGNORECASE)
            results = [m.strip() for m in matches]

        elif selector.extract_type == "html":
            # 提取 HTML
            pattern = rf'<{selector.selector}[^>]*>(.*?)</{selector.selector}>'
            matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)
            results = matches

        elif selector.extract_type == "attr":
            # 提取属性
            pattern = rf'<{selector.selector}[^>]*>'
            matches = re.findall(pattern, html, re.IGNORECASE)
            for match in matches:
                attr_match = re.search(rf'{selector.attribute}="([^"]+)"', match)
                if attr_match:
                    results.append(attr_match.group(1))

        return results

    async def _send_to_sink(self, task: CrawlTask, data: dict[str, Any]):
        """发送数据到 sink"""
        if task.sink_type == DataSinkType.EMAIL:
            # 发送邮件
            from ..standalone import get_runtime
            runtime = get_runtime()
            if runtime:
                await runtime.send_mail(
                    to=task.sink_config.get("to", "local"),
                    subject=f"[爬取] {task.name}",
                    content=json.dumps(data, ensure_ascii=False, indent=2)
                )

        elif task.sink_type == DataSinkType.DATABASE:
            # 保存到 SQLite
            await self._save_to_database(task.task_id, data)

        elif task.sink_type == DataSinkType.FILE:
            # 保存到文件
            file_path = Path(task.sink_config.get("path", "crawl_result.json"))
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

    async def _save_to_database(self, task_id: str, data: dict[str, Any]):
        """保存到数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        result_id = str(uuid.uuid4())[:12]
        cursor.execute("""
            INSERT INTO crawl_results
            (result_id, task_id, status, data, crawled_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            result_id,
            task_id,
            CrawlStatus.COMPLETED.value,
            json.dumps(data),
            datetime.now().isoformat()
        ))

        conn.commit()
        conn.close()

    def _get_task(self, task_id: str) -> Optional[CrawlTask]:
        """获取任务"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM crawl_tasks WHERE task_id = ?", (task_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        selectors_data = json.loads(row[3])
        selectors = [SelectorRule(**s) for s in selectors_data]

        return CrawlTask(
            task_id=row[0],
            name=row[1],
            url=row[2],
            selectors=selectors,
            interval_hours=row[4],
            status=CrawlStatus(row[5]),
            last_run=datetime.fromisoformat(row[6]) if row[6] else None,
            next_run=datetime.fromisoformat(row[7]) if row[7] else None,
            enabled=bool(row[8]),
            sink_type=DataSinkType(row[9]),
            sink_config=json.loads(row[10]) if row[10] else {}
        )

    async def _update_task_status(self, task_id: str, status: CrawlStatus):
        """更新任务状态"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE crawl_tasks SET status = ?, last_run = ?
            WHERE task_id = ?
        """, (status.value, datetime.now().isoformat(), task_id))

        conn.commit()
        conn.close()

    async def _update_task_next_run(self, task_id: str):
        """更新下次运行时间"""
        task = self._get_task(task_id)
        if not task:
            return

        from datetime import timedelta
        next_run = datetime.now() + timedelta(hours=task.interval_hours)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE crawl_tasks SET next_run = ? WHERE task_id = ?
        """, (next_run.isoformat(), task_id))

        conn.commit()
        conn.close()

    def list_tasks(self, enabled_only: bool = False) -> list[dict[str, Any]]:
        """列出所有任务"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if enabled_only:
            cursor.execute("SELECT * FROM crawl_tasks WHERE enabled = 1 ORDER BY name")
        else:
            cursor.execute("SELECT * FROM crawl_tasks ORDER BY name")

        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "task_id": row[0],
                "name": row[1],
                "url": row[2],
                "interval_hours": row[4],
                "status": row[5],
                "last_run": row[6],
                "next_run": row[7],
                "enabled": bool(row[8]),
                "sink_type": row[9]
            }
            for row in rows
        ]

    def generate_selector_from_visual(
        self,
        html: str,
        selection: str
    ) -> SelectorRule:
        """
        从可视化选择生成选择器规则

        用户在浏览器中圈选区域后，调用此方法生成规则
        """
        # 简化实现：基于文本内容生成选择器
        # 实际实现中，应该使用 DOM 树分析

        clean_text = re.sub(r'\s+', ' ', selection).strip()

        return SelectorRule(
            name=f"rule_{uuid.uuid4().hex[:8]}",
            selector="p",  # 默认段落
            extract_type="text"
        )


def create_crawler_dispatcher(data_dir: Path) -> CrawlerDispatcher:
    """创建爬虫调度器"""
    return CrawlerDispatcher(data_dir=data_dir)