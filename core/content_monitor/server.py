"""
智能创作与内容监控系统 - 服务器主模块
独立运行的服务端
"""

import asyncio
import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from .monitor import ContentMonitor
from .summarizer import ContentSummarizer
from .models import AlertLevel, ContentType, SystemStats
from core.logger import get_logger
logger = get_logger('content_monitor.server')


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ContentMonitorServer")


class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, db_path: str = "data/content_monitor.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS content (
                id TEXT PRIMARY KEY, content TEXT, content_type TEXT,
                title TEXT, author TEXT, status TEXT, alert_level INTEGER,
                alert_reasons TEXT, created_at TEXT)
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id TEXT PRIMARY KEY, content_id TEXT, alert_level INTEGER,
                matched_keywords TEXT, action_taken TEXT, handled INTEGER, created_at TEXT)
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rules (
                id TEXT PRIMARY KEY, name TEXT, rule_type TEXT, pattern TEXT,
                alert_level INTEGER, enabled INTEGER)
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_content_status ON content(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_level ON alerts(alert_level)")
        
        conn.commit()
        conn.close()
    
    def save_content(self, content: Dict) -> bool:
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO content VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (content.get("id"), content.get("content"), content.get("content_type"),
                 content.get("title"), content.get("author"), content.get("status"),
                 content.get("alert_level"), content.get("alert_reasons"), content.get("created_at")))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Save content error: {e}")
            return False
    
    def get_content(self, content_id: str) -> Optional[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM content WHERE id = ?", (content_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def list_content(self, status: Optional[str] = None, limit: int = 100) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        if status:
            cursor.execute("SELECT * FROM content WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                          (status, limit))
        else:
            cursor.execute("SELECT * FROM content ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]


class APIServer:
    """API服务器"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        self.host = host
        self.port = port
        self.monitor = ContentMonitor()
        self.summarizer = ContentSummarizer()
        self.db = DatabaseManager()
        self.start_time = datetime.now()
        self._routes = {}
        self._register_routes()
    
    def _register_routes(self):
        self._routes = {
            "POST /api/analyze": self._handle_analyze,
            "POST /api/check": self._handle_check,
            "POST /api/summarize": self._handle_summarize,
            "POST /api/review": self._handle_review,
            "GET /api/alerts": self._handle_get_alerts,
            "GET /api/stats": self._handle_get_stats,
            "GET /api/content": self._handle_list_content,
            "GET /api/health": self._handle_health,
            "GET /api/rules": self._handle_get_rules,
            "POST /api/rules": self._handle_import_rules,
        }
    
    async def handle_request(self, method: str, path: str, data: Optional[Dict] = None) -> Dict:
        route_key = f"{method} {path.split('?')[0]}"
        for pattern, handler in self._routes.items():
            if self._match_route(method, path, pattern):
                try:
                    return await handler(data or {})
                except Exception as e:
                    logger.error(f"Handler error: {e}")
                    return {"error": str(e), "success": False}
        return {"error": "Not found", "success": False}
    
    def _match_route(self, method: str, path: str, pattern: str) -> bool:
        pattern_method, pattern_path = pattern.split(" ", 1)
        return pattern_method == method and pattern_path == path.split("?")[0]
    
    async def _handle_analyze(self, data: Dict) -> Dict:
        text = data.get("content", "")
        author = data.get("author", "")
        content = self.monitor.analyze_content(text, author)
        
        self.db.save_content({
            "id": content.content_id, "content": content.content,
            "content_type": content.content_type.value, "title": content.title,
            "author": content.author, "status": content.status.value,
            "alert_level": content.alert_level.value,
            "alert_reasons": json.dumps(content.alert_reasons),
            "created_at": content.created_at.isoformat()})
        
        return {"success": True, "data": {
            "content_id": content.content_id, "content_type": content.content_type.value,
            "alert_level": content.alert_level.value, "alert_reasons": content.alert_reasons,
            "status": content.status.value}}
    
    async def _handle_check(self, data: Dict) -> Dict:
        text = data.get("content", "")
        level, reasons, details = self.monitor.check_content(text)
        return {"success": True, "data": {
            "alert_level": level.value, "alert_level_name": level.name,
            "reasons": reasons, "details": details}}
    
    async def _handle_summarize(self, data: Dict) -> Dict:
        text = data.get("content", "")
        content_type = ContentType(data.get("content_type", "general"))
        options = data.get("options", {})
        result = self.summarizer.summarize(text, content_type, options)
        return {"success": True, "data": {
            "summary": result.summary, "key_points": result.key_points,
            "categories": result.categories, "statistics": result.statistics, "confidence": result.confidence}}
    
    async def _handle_review(self, data: Dict) -> Dict:
        content_id = data.get("content_id")
        action = data.get("action")
        if action == "approve":
            success = self.monitor.approve_content(content_id)
        else:
            success = self.monitor.reject_content(content_id, data.get("reason", ""))
        return {"success": success}
    
    async def _handle_get_alerts(self, data: Dict) -> Dict:
        min_level = AlertLevel(data.get("min_level", 1))
        alerts = self.monitor.get_alerts(min_level)
        return {"success": True, "data": [{
            "alert_id": a.alert_id, "content_id": a.content_id, "alert_level": a.alert_level.value,
            "matched_keywords": a.matched_keywords, "handled": a.handled, "created_at": a.created_at.isoformat()}
            for a in alerts]}
    
    async def _handle_get_stats(self, data: Dict) -> Dict:
        stats = self.monitor.get_stats()
        uptime = (datetime.now() - self.start_time).total_seconds()
        return {"success": True, "data": {
            "total_content": stats.total_content, "total_alerts": stats.total_alerts,
            "pending_review": stats.pending_review, "alerts_by_level": stats.alerts_by_level, "uptime_seconds": uptime}}
    
    async def _handle_list_content(self, data: Dict) -> Dict:
        status = data.get("status")
        limit = data.get("limit", 100)
        content_list = self.db.list_content(status, limit)
        return {"success": True, "data": content_list}
    
    async def _handle_health(self, data: Dict) -> Dict:
        return {"success": True, "status": "healthy", "timestamp": datetime.now().isoformat()}
    
    async def _handle_get_rules(self, data: Dict) -> Dict:
        rules = self.monitor.export_rules()
        return {"success": True, "data": rules}
    
    async def _handle_import_rules(self, data: Dict) -> Dict:
        rules = data.get("rules", [])
        count = self.monitor.import_rules(rules)
        return {"success": True, "imported": count}


class ContentMonitorServer:
    """内容监控服务器"""
    
    def __init__(self, config: Optional[Dict] = None):
        config = config or {}
        self.host = config.get("host", "0.0.0.0")
        self.port = config.get("port", 8765)
        self.api = APIServer(self.host, self.port)
        self.running = False
    
    async def start(self):
        self.running = True
        logger.info(f"Content Monitor Server starting on {self.host}:{self.port}")
        logger.info("Server started successfully")
        logger.info(f"API: POST /api/analyze, /api/check, /api/summarize, /api/review")
        logger.info(f"API: GET /api/alerts, /api/stats, /api/health, /api/rules")
    
    async def stop(self):
        self.running = False
        logger.info("Server stopped")
    
    def get_stats(self) -> Dict:
        return {"host": self.host, "port": self.port, "running": self.running}


async def create_server(config: Optional[Dict] = None) -> ContentMonitorServer:
    server = ContentMonitorServer(config)
    await server.start()
    return server


if __name__ == "__main__":
    async def test():
        server = await create_server({"port": 8765})
        logger.info("Server running, press Ctrl+C to stop")
        try:
            while server.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await server.stop()
    asyncio.run(test())
