"""City Data MCP Connector — Nanjing "Jinling Memory" urban intelligence.

Maps the LivingTree organism to urban sensory inputs via MCP protocol:
  - Traffic data (Nanjing real-time congestion)
  - Cultural venue reservations (博物院, 夫子庙)
  - Government service APIs (苏服办, 营业执照)
  - Weather + Air quality (already via om_weather.py)

Designed as MCP tools — discoverable, self-describing, auto-registering.
Nanjing context: 长三角科教重镇 + 智慧城市试点.
"""

from __future__ import annotations

import json as _json
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx
from loguru import logger


CITY_MCP_TOOLS = [
    {
        "name": "nanjing_traffic",
        "description": "查询南京实时交通路况 — 拥堵指数/畅通路段/施工信息",
        "inputSchema": {
            "type": "object",
            "properties": {
                "district": {"type": "string", "description": "区名: 鼓楼区/玄武区/建邺区/秦淮区/江宁区"},
                "road": {"type": "string", "description": "路段名称, 如中山路"},
            },
        },
    },
    {
        "name": "nanjing_museum",
        "description": "查询南京博物院/夫子庙/中山陵预约情况 — 实时人流 + 可预约时段",
        "inputSchema": {
            "type": "object",
            "properties": {
                "venue": {"type": "string", "description": "场馆: nanjing_museum/fuzimiao/zhongshanling"},
                "date": {"type": "string", "description": "日期: YYYY-MM-DD, 默认今天"},
            },
        },
    },
    {
        "name": "nanjing_business",
        "description": "查询南京营业执照办理流程/租金行情/政策 — 玄武区/建邺区/江宁区分区数据",
        "inputSchema": {
            "type": "object",
            "properties": {
                "service": {"type": "string", "description": "服务: license/rental/policy"},
                "district": {"type": "string", "description": "区名: 玄武区/建邺区/江宁区"},
            },
        },
    },
    {
        "name": "nanjing_weather",
        "description": "南京实时天气+空气质量 (AQI/PM2.5) — 已接入 om_weather",
        "inputSchema": {"type": "object", "properties": {}},
    },
]

MOCK_DATA = {
    "traffic": {
        "鼓楼区": {"congestion_index": 6.2, "status": "轻度拥堵", "hotspots": ["中山北路", "中央路"]},
        "玄武区": {"congestion_index": 4.1, "status": "基本畅通", "hotspots": ["北京东路"]},
        "建邺区": {"congestion_index": 3.5, "status": "畅通", "hotspots": []},
        "秦淮区": {"congestion_index": 7.8, "status": "中度拥堵", "hotspots": ["夫子庙周边", "中华路"]},
        "江宁区": {"congestion_index": 2.9, "status": "畅通", "hotspots": []},
    },
    "museum": {
        "nanjing_museum": {"quota": 5000, "booked": 3200, "available": 1800, "status": "可预约"},
        "fuzimiao": {"quota": 8000, "booked": 7500, "available": 500, "status": "接近满员"},
        "zhongshanling": {"quota": 3000, "booked": 1200, "available": 1800, "status": "可预约"},
    },
    "business": {
        "license": {
            "玄武区": {"process": "线上苏服办→提交材料→5工作日", "fee": "免费"},
            "建邺区": {"process": "行政服务中心→窗口办理→7工作日", "fee": "免费"},
            "江宁区": {"process": "线上提交→3工作日快审", "fee": "免费"},
        },
        "rental": {
            "玄武区": {"avg_per_m2": 120, "trend": "平稳"},
            "建邺区": {"avg_per_m2": 150, "trend": "上涨"},
            "江宁区": {"avg_per_m2": 60, "trend": "下降"},
        },
        "policy": {
            "玄武区": ["大学生创业补贴 ¥5000-20000", "科技企业税收减免"],
            "建邺区": ["金融企业入驻补贴", "河西新城优惠政策"],
            "江宁区": ["制造业技改补贴", "高新技术企业认定奖励"],
        },
    },
}


class CityMCPConnector:
    """MCP-based urban data connector for Nanjing (金陵记忆).

    All tools are self-describing via the MCP tools/list protocol.
    Real API endpoints replace mock data when deployed in production.
    """

    def __init__(self):
        self._tools = {t["name"]: t for t in CITY_MCP_TOOLS}
        self._call_count: dict[str, int] = {}

    def list_tools(self) -> list[dict]:
        return CITY_MCP_TOOLS

    async def call_tool(self, tool_name: str, params: dict = None) -> dict:
        """Route to the appropriate city data handler."""
        params = params or {}
        self._call_count[tool_name] = self._call_count.get(tool_name, 0) + 1

        if tool_name == "nanjing_traffic":
            return self._traffic(params)
        elif tool_name == "nanjing_museum":
            return self._museum(params)
        elif tool_name == "nanjing_business":
            return self._business(params)
        elif tool_name == "nanjing_weather":
            return await self._weather()
        else:
            return {"error": f"unknown tool: {tool_name}"}

    def _traffic(self, params: dict) -> dict:
        district = params.get("district", "鼓楼区")
        data = MOCK_DATA["traffic"].get(district, {"congestion_index": 0, "status": "未知"})
        return {
            "tool": "nanjing_traffic",
            "district": district,
            "congestion_index": data["congestion_index"],
            "status": data["status"],
            "hotspots": data.get("hotspots", []),
            "recommendation": (
                "建议避开拥堵路段" if data["congestion_index"] > 5
                else "路况较好,可出行" if data["congestion_index"] > 3
                else "路况畅通,出行无忧"
            ),
            "source": "mock-nanjing-traffic-api",
            "note": "接入南京交通局实时API后可获得精确数据",
        }

    def _museum(self, params: dict) -> dict:
        venue = params.get("venue", "nanjing_museum")
        data = MOCK_DATA["museum"].get(venue, {"quota": 0, "booked": 0, "available": 0, "status": "未知"})
        return {
            "tool": "nanjing_museum",
            "venue": venue,
            "quota": data["quota"],
            "booked": data["booked"],
            "available": data["available"],
            "status": data["status"],
            "crowd_level": "拥挤" if data["booked"] / max(1, data["quota"]) > 0.8 else "适中",
            "recommendation": (
                "建议上午9点前到达" if data["booked"] / max(1, data["quota"]) > 0.7
                else "全天可预约,人流量适中"
            ),
            "source": "mock-nanjing-culture-api",
        }

    def _business(self, params: dict) -> dict:
        service = params.get("service", "license")
        district = params.get("district", "玄武区")
        data = MOCK_DATA["business"].get(service, {}).get(district, {})
        return {
            "tool": "nanjing_business",
            "service": service,
            "district": district,
            "data": data,
            "source": "mock-nanjing-gov-api",
            "note": "接入苏服办API后可获得实时政务数据",
        }

    async def _weather(self) -> dict:
        from ..knowledge.om_weather import get_weather_client
        try:
            client = get_weather_client()
            forecast = await client.get_forecast(32.06, 118.79)
            return {"tool": "nanjing_weather", "data": forecast, "source": "open-meteo"}
        except Exception:
            return {"tool": "nanjing_weather", "data": {"temperature": 22, "condition": "晴"},
                    "source": "fallback"}

    def stats(self) -> dict:
        return {
            "tools": len(CITY_MCP_TOOLS),
            "total_calls": sum(self._call_count.values()),
            "by_tool": dict(self._call_count),
            "city": "南京 (Nanjing)",
            "protocol": "MCP (Model Context Protocol)",
        }

    def render_html(self) -> str:
        st = self.stats()
        tool_rows = ""
        for tool in CITY_MCP_TOOLS:
            calls = self._call_count.get(tool["name"], 0)
            tool_rows += (
                f'<div style="padding:4px 8px;margin:2px 0;font-size:11px;border-left:3px solid var(--accent)">'
                f'<b>{tool["name"]}</b> <span style="color:var(--dim);font-size:9px">调用{calls}次</span>'
                f'<div style="font-size:9px;color:var(--dim)">{tool["description"]}</div></div>'
            )

        return f'''<div class="card">
<h2>🏯 金陵记忆 <span style="font-size:10px;color:var(--dim)">— City MCP Connector · 南京</span></h2>
<div style="font-size:9px;color:var(--dim);margin:4px 0">
  {st["total_calls"]}次调用 · {st["tools"]}个MCP工具 · 覆盖交通/文旅/政务/天气
</div>
{tool_rows}
<div style="font-size:9px;color:var(--dim);margin-top:8px;text-align:center">
  MCP协议接入 · mock数据演示 · 接入苏服办/南京地铁/文旅局API后实时更新</div>
</div>'''


_instance: Optional[CityMCPConnector] = None


def get_city_mcp() -> CityMCPConnector:
    global _instance
    if _instance is None:
        _instance = CityMCPConnector()
    return _instance
