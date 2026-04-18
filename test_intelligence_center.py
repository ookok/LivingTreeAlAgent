# -*- coding: utf-8 -*-
"""
Intelligence Center Test Script
"""

import asyncio
import sys
sys.path.insert(0, "d:/mhzyapp/hermes-desktop")

from core.intelligence_center import (
    get_intelligence_hub,
    AlertLevel,
    ReportType,
)


async def test_basic():
    """基础功能测试"""
    print("=" * 50)
    print("Intelligence Center Basic Test")
    print("=" * 50)

    # 获取单例
    hub = get_intelligence_hub()
    print(f"[OK] IntelligenceHub singleton")

    # 测试谣言检测
    print("\n--- Test Rumor Detection ---")
    rumor_text = "A brand product was exposed to contain harmful substances"
    result = await hub.check_rumor(rumor_text)
    print(f"[OK] Rumor verdict: {result.verdict.value}")
    print(f"     Confidence: {result.confidence:.2f}")

    # 测试情感分析
    print("\n--- Test Sentiment Analysis ---")
    sentiment_text = "This product is very good, high cost performance, recommended"
    sentiment = await hub.analyze_sentiment(sentiment_text)
    print(f"[OK] Sentiment: {sentiment['sentiment_label']}")
    print(f"     Score: {sentiment['sentiment_score']:.2f}")

    # 测试舆情趋势
    trend = hub.get_sentiment_trend()
    print(f"[OK] Sentiment trend: {trend}")

    # 测试竞品管理
    print("\n--- Test Competitor Management ---")
    comp_id = hub.add_competitor(
        name="TestCompetitor",
        keywords=["keyword1", "keyword2"],
        website="https://example.com"
    )
    print(f"[OK] Added competitor: {comp_id}")

    competitors = hub.list_competitors()
    print(f"[OK] Competitor list: {len(competitors)} items")

    # 测试健康度评估
    health = await hub.evaluate_competitor_health(comp_id)
    if health:
        print(f"[OK] Health score: {health['health_score']:.0f}/100 ({health['status']})")

    # 测试预警
    print("\n--- Test Alert ---")
    alert = await hub.send_alert(
        level=AlertLevel.HIGH,
        title="Test Alert",
        description="This is a test alert",
        content="Details...",
        source_type="test"
    )
    print(f"[OK] Alert created: {alert.alert_id}")

    recent_alerts = hub.get_recent_alerts(limit=5)
    print(f"[OK] Recent alerts: {len(recent_alerts)} items")

    # 测试统计
    stats = hub.get_stats()
    print(f"[OK] Total intelligence: {stats.total_collected} items")

    print("\n" + "=" * 50)
    print("Basic test completed!")
    print("=" * 50)


if __name__ == "__main__":
    try:
        asyncio.run(test_basic())
    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()