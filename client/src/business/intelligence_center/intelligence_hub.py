# -*- coding: utf-8 -*-
"""
Intelligence Hub 情报中心核心调度器
Intelligence Center - Central Orchestrator

整合所有情报模块，提供统一入口
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import (
    IntelligenceType, AlertLevel, RumorVerdict,
    IntelligenceSource, RawIntelligence, RumorCheckResult,
    CompetitorProfile, AlertRecord, IntelligenceReport, IntelligenceStats,
    IntelligenceCenterConfig, NotificationConfig
)
from .multi_search import MultiSourceSearcher, DeepSearchPipeline, SearchIntent
from .rumor_scanner import RumorDetector, SentimentAnalyzer, SentimentAggregator, RumorClaim, AlertLevel as RSAlertLevel
from .competitor_monitor import CompetitorMonitor, CompetitorProfile as CMPProfile, MonitoringScheduler, HealthStatus
from .alert_system import AlertManager, Alert, EmailConfig, WebhookConfig, AlertChannel
from .report_generator import ReportGenerator, CompetitorDailyReportGenerator, ReportType

logger = logging.getLogger(__name__)


class IntelligenceHub:
    """
    情报中心核心调度器

    整合 Multi-Search / Rumor-Scanner / Competitor-Monitor / Alert-System / Report-Generator
    提供从"搜索"到"决策"的闭环
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config: Optional[IntelligenceCenterConfig] = None):
        if self._initialized:
            return

        self.config = config or IntelligenceCenterConfig()

        # 初始化各组件
        cache_dir = str(Path.home() / ".hermes-desktop" / "intelligence_cache")
        self.searcher = MultiSourceSearcher(cache_dir=cache_dir, cache_ttl_hours=self.config.search_cache_hours)
        self.search_pipeline = DeepSearchPipeline(self.searcher)

        self.rumor_detector = RumorDetector(search_pipeline=self.search_pipeline)
        self.sentiment_aggregator = SentimentAggregator()

        self.competitor_monitor = CompetitorMonitor(
            search_pipeline=self.search_pipeline,
            rumor_detector=self.rumor_detector
        )
        self.monitoring_scheduler = MonitoringScheduler(self.competitor_monitor)

        self.alert_manager = AlertManager()
        self._configure_alerts()

        self.report_generator = ReportGenerator(self.config.report_output_dir)
        self.daily_report_gen = CompetitorDailyReportGenerator(self.config.report_output_dir)

        # 情报存储
        self.intelligence_cache: Dict[str, RawIntelligence] = {}
        self.stats = IntelligenceStats()

        self._initialized = True
        logger.info("情报中心初始化完成")

    def _configure_alerts(self):
        """配置预警"""
        # 邮件配置
        if self.config.notification.email_enabled:
            email_config = EmailConfig(
                enabled=True,
                smtp_host="smtp.gmail.com",
                smtp_port=587,
                username=self.config.notification.email_recipients[0] if self.config.notification.email_recipients else "",
                password="",
            )
            self.alert_manager.set_email_config(email_config)

        # Webhook配置
        if self.config.notification.webhook_enabled:
            webhook_config = WebhookConfig(
                enabled=True,
                url=self.config.notification.webhook_url,
            )
            self.alert_manager.set_webhook_config(webhook_config)

        # 默认规则
        from .alert_system import NotificationRule
        default_rule = NotificationRule(
            name="默认规则",
            min_level=AlertLevel.MEDIUM,
            channels=[AlertChannel.SYSTEM],
        )
        self.alert_manager.add_rule(default_rule)

    # ==================== 搜索接口 ====================

    async def search(
        self,
        query: str,
        sources: Optional[List[str]] = None,
        intent_hints: Optional[str] = None,
    ) -> Any:
        """
        多源搜索

        Args:
            query: 搜索关键词
            sources: 搜索源列表
            intent_hints: 意图提示 (competitor/product/news/rumor/review)

        Returns:
            SearchResponse
        """
        if intent_hints:
            intent_map = {
                "competitor": SearchIntent.COMPETITOR,
                "product": SearchIntent.PRODUCT,
                "news": SearchIntent.NEWS,
                "rumor": SearchIntent.RUMOR,
                "review": SearchIntent.REVIEW,
            }
            # 可以在此处理intent，但当前searcher会自己检测

        return await self.searcher.search(query, sources or ["baidu"])

    async def deep_search(
        self,
        query: str,
        search_type: str = "competitor",
    ) -> Any:
        """
        深度搜索

        Args:
            query: 搜索关键词
            search_type: 搜索类型 (competitor/releases/sentiment)

        Returns:
            SearchResponse
        """
        if search_type == "competitor":
            return await self.search_pipeline.search_competitor(query)
        elif search_type == "releases":
            return await self.search_pipeline.search_product_releases(query)
        elif search_type == "sentiment":
            return await self.search_pipeline.search_sentiment(query)
        else:
            return await self.searcher.search(query)

    # ==================== 谣言检测接口 ====================

    async def check_rumor(self, text: str, source_url: str = "") -> RumorCheckResult:
        """
        检测谣言

        Args:
            text: 待检测文本
            source_url: 来源URL

        Returns:
            RumorCheckResult
        """
        claim = RumorClaim(
            claim_id="",
            text=text,
            source_url=source_url,
        )

        result = await self.rumor_detector.check(claim)

        # 转换为标准结果
        return RumorCheckResult(
            rumor_id=result.claim_id,
            claim=text,
            source_url=source_url,
            verdict=result.verdict,
            confidence=result.confidence,
            truth_score=result.truth_score,
            evidence_for=result.evidence_for,
            evidence_against=result.evidence_against,
            analysis_summary=result.summary,
            risk_level=AlertLevel.HIGH if result.risk_level.value >= 3 else AlertLevel.MEDIUM,
        )

    async def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """
        分析情感

        Args:
            text: 待分析文本

        Returns:
            情感分析结果
        """
        result = SentimentAnalyzer.analyze(text)
        self.sentiment_aggregator.add(result)

        return {
            "text": result.text,
            "sentiment_score": result.sentiment_score,
            "sentiment_label": result.sentiment_label,
            "confidence": result.confidence,
            "positive_aspects": result.positive_aspects,
            "negative_aspects": result.negative_aspects,
        }

    def get_sentiment_trend(self) -> Dict[str, Any]:
        """获取舆情趋势"""
        return self.sentiment_aggregator.get_trend()

    # ==================== 竞品监控接口 ====================

    def add_competitor(
        self,
        name: str,
        keywords: Optional[List[str]] = None,
        website: str = "",
        social_media: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        添加竞品

        Args:
            name: 竞品名称
            keywords: 监控关键词
            website: 官网
            social_media: 社交媒体账号

        Returns:
            competitor_id
        """
        profile = CMPProfile(
            name=name,
            keywords=keywords or [name],
            website=website,
            social_media=social_media or {},
        )
        return self.competitor_monitor.add_competitor(profile)

    def remove_competitor(self, competitor_id: str) -> bool:
        """移除竞品"""
        return self.competitor_monitor.remove_competitor(competitor_id)

    def list_competitors(self) -> List[Dict[str, Any]]:
        """列出所有竞品"""
        return [
            {
                "id": p.competitor_id,
                "name": p.name,
                "keywords": p.keywords,
                "is_active": p.is_active,
            }
            for p in self.competitor_monitor.list_competitors()
        ]

    async def collect_competitor_intel(self, competitor_id: str) -> List[Dict[str, Any]]:
        """
        收集竞品情报

        Args:
            competitor_id: 竞品ID

        Returns:
            情报列表
        """
        intel_list = await self.competitor_monitor.collect_intel(competitor_id)

        return [
            {
                "id": i.intel_id,
                "type": i.intel_type,
                "title": i.title,
                "content": i.content,
                "url": i.url,
                "source": i.source,
                "sentiment": i.sentiment,
                "importance": i.importance,
                "collected_at": i.collected_at.isoformat(),
            }
            for i in intel_list
        ]

    async def evaluate_competitor_health(self, competitor_id: str) -> Optional[Dict[str, Any]]:
        """评估竞品健康度"""
        health = await self.competitor_monitor.evaluate_health(competitor_id)
        if not health:
            return None

        return {
            "competitor_id": health.competitor_id,
            "competitor_name": health.competitor_name,
            "health_score": health.health_score,
            "status": health.status.value,
            "trend": health.trend,
            "sentiment_score": health.sentiment_score,
            "negative_ratio": health.negative_ratio,
            "rumor_count": health.rumor_count,
            "complaint_count": health.complaint_count,
        }

    async def run_monitoring_cycle(self) -> Dict[str, List]:
        """运行监控周期"""
        return await self.competitor_monitor.run_monitoring_cycle()

    # ==================== 预警接口 ====================

    async def send_alert(
        self,
        level: AlertLevel,
        title: str,
        description: str = "",
        content: str = "",
        source_type: str = "",
        source_id: str = "",
    ) -> Alert:
        """
        发送预警

        Args:
            level: 预警级别
            title: 标题
            description: 描述
            content: 详细内容
            source_type: 来源类型
            source_id: 来源ID

        Returns:
            Alert
        """
        alert = await self.alert_manager.create_alert(
            level=level,
            title=title,
            description=description,
            content=content,
            source_type=source_type,
            source_id=source_id,
        )
        return alert

    def get_recent_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取最近预警"""
        alerts = self.alert_manager.get_recent_alerts(limit)
        return [
            {
                "id": a.alert_id,
                "level": a.level.name,
                "title": a.title,
                "description": a.description,
                "source_type": a.source_type,
                "status": a.status,
                "created_at": a.created_at.isoformat(),
            }
            for a in alerts
        ]

    def get_alert_stats(self) -> Dict[str, Any]:
        """获取预警统计"""
        return self.alert_manager.get_alert_stats()

    # ==================== 报告接口 ====================

    async def generate_daily_report(self) -> IntelligenceReport:
        """生成日报"""
        # 收集所有竞品情报
        all_intel = {}
        health_data = {}

        for comp in self.competitor_monitor.list_competitors():
            intel = await self.competitor_monitor.collect_intel(comp.competitor_id)
            all_intel[comp.competitor_id] = intel

            health = await self.competitor_monitor.evaluate_health(comp.competitor_id)
            if health:
                health_data[comp.competitor_id] = health

        # 生成报告
        report_data = {
            "competitors": [
                {"id": c.competitor_id, "name": c.name}
                for c in self.competitor_monitor.list_competitors()
            ]
        }

        # 转换为可序列化格式
        intel_list = []
        for intel in all_intel.values():
            intel_list.extend(intel)

        report = self.daily_report_gen.generate(report_data, intel_list, health_data)
        return report

    def generate_report(
        self,
        title: str,
        report_type: ReportType,
        sections: List[Dict],
        format: str = "markdown",
    ) -> IntelligenceReport:
        """
        生成自定义报告

        Args:
            title: 报告标题
            report_type: 报告类型
            sections: 章节列表
            format: 输出格式

        Returns:
            IntelligenceReport
        """
        from .report_generator import ReportSection

        report_sections = []
        for i, sec in enumerate(sections):
            section = ReportSection(
                title=sec.get("title", ""),
                content=sec.get("content", ""),
                order=i,
            )
            report_sections.append(section)

        report = self.report_generator.generate(
            title=title,
            report_type=report_type,
            sections=report_sections,
            format=ReportFormat[format.upper()] if format.upper() in ReportFormat.__members__ else ReportFormat.MARKDOWN,
        )

        output_path = self.report_generator.save(report)
        report.output_path = output_path

        return report

    # ==================== 竞品监控流 (MVP) ====================

    async def run_competitor_monitoring_flow(
        self,
        competitor_name: str,
        keywords: Optional[List[str]] = None,
        send_notification: bool = True,
    ) -> Dict[str, Any]:
        """
        运行竞品监控流 (MVP)

        完整流程：
        1. Multi-Search 抓取对手新品
        2. Rumor Scan 分析口碑风险
        3. Cloud-Writer 生成日报
        4. 邮件推送给运营

        Args:
            competitor_name: 竞品名称
            keywords: 监控关键词
            send_notification: 是否发送通知

        Returns:
            监控结果
        """
        result = {
            "competitor": competitor_name,
            "search_results": [],
            "rumor_results": [],
            "sentiment": {},
            "alerts": [],
            "report_path": "",
            "errors": [],
        }

        try:
            # 1. 多源搜索
            logger.info(f"[竞品监控流] 搜索竞品动态: {competitor_name}")
            search_results = await self.search_pipeline.search_competitor(
                competitor_name,
                keywords or ["新品", "评测", "价格"]
            )
            result["search_results"] = [
                {"title": r.title, "url": r.url, "snippet": r.snippet, "source": r.source}
                for r in search_results.results[:10]
            ]

            # 2. 谣言检测
            logger.info(f"[竞品监控流] 检测谣言风险: {competitor_name}")
            rumor_keywords = [f"{competitor_name} 假货", f"{competitor_name} 欺骗", f"{competitor_name} 投诉"]
            for kw in rumor_keywords[:2]:
                try:
                    rumor_result = await self.check_rumor(kw)
                    if rumor_result.verdict.value in ("false", "partly_false"):
                        result["rumor_results"].append({
                            "claim": kw,
                            "verdict": rumor_result.verdict.value,
                            "confidence": rumor_result.confidence,
                            "summary": rumor_result.analysis_summary,
                        })

                        # 发送预警
                        if send_notification:
                            await self.send_alert(
                                level=AlertLevel.HIGH if rumor_result.confidence > 0.7 else AlertLevel.MEDIUM,
                                title=f"[谣言风险] 关于{competitor_name}",
                                description=rumor_result.analysis_summary,
                                content=f"声明: {kw}\n判定: {rumor_result.verdict.value}\n置信度: {rumor_result.confidence:.2f}",
                                source_type="rumor",
                            )
                except Exception as e:
                    result["errors"].append(f"谣言检测失败: {str(e)}")

            # 3. 舆情分析
            logger.info(f"[竞品监控流] 分析舆情: {competitor_name}")
            if search_results.results:
                sample_text = " ".join([r.snippet for r in search_results.results[:3]])
                result["sentiment"] = await self.analyze_sentiment(sample_text)

            # 4. 生成简报
            logger.info(f"[竞品监控流] 生成报告: {competitor_name}")
            sections = [
                {"title": "竞品动态", "content": self._format_search_results(result["search_results"])},
                {"title": "风险检测", "content": self._format_rumor_results(result["rumor_results"])},
                {"title": "舆情分析", "content": f"情感得分: {result['sentiment'].get('sentiment_score', 0):.2f}"},
            ]

            report = self.generate_report(
                title=f"{competitor_name} 监控报告 {datetime.now().strftime('%Y-%m-%d')}",
                report_type=ReportType.SPECIAL,
                sections=sections,
            )
            result["report_path"] = report.output_path

        except Exception as e:
            logger.error(f"竞品监控流失败: {e}")
            result["errors"].append(str(e))

        return result

    def _format_search_results(self, results: List[Dict]) -> str:
        if not results:
            return "暂无数据"
        lines = []
        for r in results[:5]:
            lines.append(f"- [{r['title']}]({r['url']}) - {r['source']}")
        return "\n".join(lines)

    def _format_rumor_results(self, results: List[Dict]) -> str:
        if not results:
            return "未检测到谣言风险"
        lines = []
        for r in results:
            lines.append(f"- ⚠️ {r['claim']}: {r['verdict']} (置信度: {r['confidence']:.2f})")
        return "\n".join(lines)

    # ==================== 统计接口 ====================

    def get_stats(self) -> IntelligenceStats:
        """获取统计信息"""
        alert_stats = self.alert_manager.get_alert_stats()

        self.stats.total_collected = len(self.intelligence_cache)
        self.stats.alerts_triggered = alert_stats.get("total", 0)
        self.stats.by_level = alert_stats.get("by_level", {})

        return self.stats

    async def close(self):
        """关闭"""
        await self.searcher.close()


# ============ 单例访问函数 ============

_hub_instance: Optional[IntelligenceHub] = None


def get_intelligence_hub(config: Optional[IntelligenceCenterConfig] = None) -> IntelligenceHub:
    """获取情报中心单例"""
    global _hub_instance
    if _hub_instance is None:
        _hub_instance = IntelligenceHub(config)
    return _hub_instance


__all__ = [
    "IntelligenceHub",
    "get_intelligence_hub",
    "IntelligenceType",
    "AlertLevel",
    "RumorVerdict",
    "CompetitorProfile",
    "AlertRecord",
    "IntelligenceReport",
    "IntelligenceStats",
    "IntelligenceCenterConfig",
    "ReportType",
]