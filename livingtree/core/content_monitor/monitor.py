"""
智能创作与内容监控系统 - 内容监控模块
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any, Tuple
from collections import defaultdict

from .models import AlertLevel, AlertRecord, ContentItem, ContentStatus, SystemStats
from .rule_engine import RuleEngine
from .content_recognizer import ContentRecognizer


class AlertHandler:
    """告警处理器"""
    
    def __init__(self):
        self.handlers: Dict[AlertLevel, List[Callable]] = defaultdict(list)
        self.notification_queue: List[Dict] = []
    
    def register_handler(self, level: AlertLevel, handler: Callable):
        self.handlers[level].append(handler)
    
    async def handle(self, alert: AlertRecord) -> str:
        action_taken = "recorded"
        handlers = self.handlers.get(alert.alert_level, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(alert)
                else:
                    handler(alert)
            except Exception:
                continue
        
        if alert.alert_level == AlertLevel.CRITICAL:
            action_taken = "blocked_and_reported"
        elif alert.alert_level == AlertLevel.HIGH:
            action_taken = "blocked_pending_review"
        elif alert.alert_level == AlertLevel.MEDIUM:
            action_taken = "flagged_for_review"
        elif alert.alert_level == AlertLevel.LOW:
            action_taken = "flagged"
        
        return action_taken
    
    def get_pending_notifications(self) -> List[Dict]:
        return self.notification_queue


class ContentMonitor:
    """内容监控系统"""
    
    def __init__(self):
        self.rule_engine = RuleEngine()
        self.recognizer = ContentRecognizer()
        self.alert_handler = AlertHandler()
        self.content_history: Dict[str, ContentItem] = {}
        self.alert_history: Dict[str, AlertRecord] = {}
        self.stats = SystemStats()
        self._init_stats()
    
    def _init_stats(self):
        self.stats.alerts_by_level = {level.name: 0 for level in AlertLevel}
        self.stats.content_by_type = defaultdict(int)
    
    def analyze_content(self, text: str, author: str = "") -> ContentItem:
        content_id = f"content_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        analysis = self.recognizer.recognize(text)
        alert_level, reasons, keywords = self.rule_engine.analyze_content(text)
        
        content = ContentItem(
            content_id=content_id, content=text[:500], content_type=analysis.content_type,
            author=author, alert_level=alert_level, alert_reasons=reasons,
            status=ContentStatus.PENDING)
        
        if alert_level == AlertLevel.CRITICAL:
            content.status = ContentStatus.REJECTED
        elif alert_level == AlertLevel.HIGH:
            content.status = ContentStatus.REVIEWING
        
        self.content_history[content_id] = content
        self.stats.total_content += 1
        self.stats.content_by_type[analysis.content_type.value] += 1
        
        if alert_level.value > AlertLevel.NORMAL.value:
            alert = AlertRecord(content_id=content_id, content=text[:200],
                alert_level=alert_level, matched_keywords=keywords, trigger_rules=reasons)
            self.alert_history[alert.alert_id] = alert
            self.stats.total_alerts += 1
            self.stats.alerts_by_level[alert_level.name] += 1
        
        return content
    
    async def process_content_async(self, text: str, author: str = "") -> ContentItem:
        return self.analyze_content(text, author)
    
    def check_content(self, text: str) -> Tuple[AlertLevel, List[str], Dict[str, Any]]:
        alert_level, reasons, keywords = self.rule_engine.analyze_content(text)
        analysis = self.recognizer.recognize(text)
        details = {"content_type": analysis.content_type.value, "confidence": analysis.confidence,
                   "keywords": keywords, "requires_review": alert_level.value >= AlertLevel.MEDIUM.value}
        return alert_level, reasons, details
    
    def get_alerts(self, min_level: AlertLevel = AlertLevel.LOW, limit: int = 100) -> List[AlertRecord]:
        alerts = [a for a in self.alert_history.values() if a.alert_level.value >= min_level.value]
        alerts.sort(key=lambda x: x.created_at, reverse=True)
        return alerts[:limit]
    
    def get_pending_reviews(self) -> List[ContentItem]:
        return [c for c in self.content_history.values()
               if c.status in [ContentStatus.PENDING, ContentStatus.REVIEWING]]
    
    def approve_content(self, content_id: str) -> bool:
        if content_id in self.content_history:
            self.content_history[content_id].status = ContentStatus.APPROVED
            self.content_history[content_id].reviewed_at = datetime.now()
            return True
        return False
    
    def reject_content(self, content_id: str, reason: str = "") -> bool:
        if content_id in self.content_history:
            self.content_history[content_id].status = ContentStatus.REJECTED
            self.content_history[content_id].reviewed_at = datetime.now()
            self.content_history[content_id].alert_reasons.append(f"审核拒绝: {reason}")
            return True
        return False
    
    def get_stats(self) -> SystemStats:
        self.stats.pending_review = len(self.get_pending_reviews())
        return self.stats

    def get_sensitive_words(self) -> List:
        """获取所有敏感词列表"""
        return self.rule_engine.get_sensitive_words()

    def export_rules(self) -> List[Dict]:
        return self.rule_engine.export_rules()
    
    def import_rules(self, rules_data: List[Dict]) -> int:
        return self.rule_engine.import_rules(rules_data)
