"""HTMX Reach routes — mobile device pairing & remote sensor bridge.

Extracted from htmx_web.py to keep file sizes manageable.
Routes: /reach/pair/{code}, /reach/qr, /reach/status, /reach/request, /reach/demo
"""

from __future__ import annotations

import asyncio
import html as _html
import re

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from loguru import logger

reach_router = APIRouter(prefix="/reach", tags=["reach"])


def _get_hub(request: Request):
    return getattr(request.app.state, "hub", None)


def _sanitize_html(text: str) -> str:
    if not text:
        return ""
    clean = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r'<iframe[^>]*>.*?</iframe>', '', clean, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r'<object[^>]*>.*?</object>', '', clean, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r'<embed[^>]*>', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'<style[^>]*>.*?</style>', '', clean, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r'<meta[^>]*>', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'<svg[^>]*on\w+\s*=[^>]*>', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'\bon\w+\s*=\s*["\'][^"\']*["\']', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'\bon\w+\s*=\s*\S+', '', clean, flags=re.IGNORECASE)
    if not re.search(r'<[a-zA-Z/][^>]*>', clean):
        clean = _html.escape(clean)
    return clean


def _render_html(template_name: str, request: Request):
    from pathlib import Path
    from jinja2 import Environment, FileSystemLoader
    from fastapi.responses import HTMLResponse as _HTMLResponse
    TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
    _jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    try:
        tpl = _jinja_env.get_template(template_name)
        return _HTMLResponse(tpl.render(request=request))
    except Exception:
        return _HTMLResponse(f"<p>Template error: {template_name}</p>", status_code=500)


@reach_router.get("/pair/{code}")
async def reach_pair(request: Request, code: str):
    from ..network.reach_gateway import get_reach_gateway
    reach = get_reach_gateway()
    hub = _get_hub(request)
    if hub:
        reach.set_hub(hub)
    return _render_html("reach_mobile.html", request)


@reach_router.get("/qr")
async def reach_qr(request: Request):
    from ..network.reach_gateway import get_reach_gateway
    reach = get_reach_gateway()
    hub = _get_hub(request)
    if hub:
        reach.set_hub(hub)
    server_host = request.headers.get("host", "localhost:8100")
    protocol = "https" if request.url.scheme == "https" else "http"
    server_url = f"{protocol}://{server_host}"
    pairing_url = reach.generate_pairing_qr(server_url)
    qr_api = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={pairing_url}"
    return HTMLResponse(
        f'<div class="card"><h2>📱 连接移动设备</h2>'
        f'<p style="font-size:12px;color:var(--dim);margin:8px 0">扫描二维码，让手机成为 AI 的眼睛和手</p>'
        f'<div style="text-align:center;margin:12px 0">'
        f'<img src="{qr_api}" alt="Pairing QR" style="width:200px;height:200px;background:#fff;border-radius:8px">'
        f'</div><p style="font-size:11px;color:var(--dim);text-align:center">'
        f'或访问: <code style="color:var(--accent)">{pairing_url}</code></p>'
        f'<div id="reach-status" style="margin-top:8px;text-align:center;font-size:12px;color:var(--accent)" '
        f'hx-get="/tree/reach/status" hx-trigger="load, every 5s" hx-swap="innerHTML">等待设备连接...</div></div>')


@reach_router.get("/status")
async def reach_status(request: Request):
    from ..network.reach_gateway import get_reach_gateway
    reach = get_reach_gateway()
    st = reach.status()
    mobiles = st["mobile_devices"]
    total = st["total_devices"]
    if mobiles > 0:
        names = [d["device_name"] for d in st["devices"] if d["device_type"] == "mobile"]
        return HTMLResponse(
            f'<span style="color:var(--accent)">📱 {", ".join(names[:3])} 已连接 ({mobiles}台移动设备)</span>')
    return HTMLResponse(f'<span style="color:var(--dim)">📱 等待设备连接... ({total}台设备在线)</span>')


@reach_router.post("/request")
async def reach_request_sensor(request: Request):
    try:
        body = await request.json()
    except Exception:
        form = await request.form()
        body = {k: v for k, v in form.items()}
    sensor_type_str = body.get("sensor_type", "camera_photo")
    title = body.get("title", "需要你的帮助")
    instruction = body.get("instruction", "")
    context = body.get("context", "")
    from ..network.reach_gateway import get_reach_gateway, SensorType
    reach = get_reach_gateway()
    hub = _get_hub(request)
    if hub:
        reach.set_hub(hub)
    try:
        st = SensorType(sensor_type_str)
    except ValueError:
        st = SensorType.CAMERA_PHOTO
    if not reach.has_mobile():
        return HTMLResponse(
            '<div class="card" style="border-color:var(--warn)">'
            '<h2>📱 无移动设备在线</h2>'
            '<p style="font-size:12px;color:var(--dim)">请先扫描二维码连接手机</p>'
            '<button hx-get="/tree/reach/qr" hx-target="closest .card" hx-swap="outerHTML" '
            'style="font-size:11px;padding:6px 12px">📱 显示配对码</button></div>')
    sensor_icons = {
        SensorType.CAMERA_PHOTO: "📸", SensorType.CAMERA_SCAN: "📷",
        SensorType.QR_CODE: "📱", SensorType.GPS_LOCATION: "📍",
        SensorType.MICROPHONE: "🎤", SensorType.NFC_TAG: "📡",
    }
    icon = sensor_icons.get(st, "📱")
    push_card = HTMLResponse(
        f'<div class="card" style="border-left:3px solid var(--accent)">'
        f'<h2>{icon} 已发送: {title}</h2>'
        f'<p style="font-size:12px;margin:4px 0">{instruction[:200]}</p>'
        f'<p style="font-size:10px;color:var(--dim)">请在手机上完成操作，结果将自动返回</p>'
        f'<div hx-get="/tree/reach/status" hx-trigger="every 3s" hx-swap="innerHTML" '
        f'style="font-size:11px;margin-top:4px"></div></div>')
    asyncio.create_task(_dispatch_reach_request(reach, st, title, instruction, context))
    return push_card


async def _dispatch_reach_request(reach, sensor_type, title, instruction, context):
    try:
        result = await reach.request_sensor(
            sensor_type=sensor_type, title=title,
            instruction=instruction, context=context, timeout=120.0, required=False)
        if result:
            logger.info(f"Reach: sensor response received — {sensor_type.value}")
    except Exception as e:
        logger.debug(f"Reach dispatch: {e}")


@reach_router.get("/demo")
async def reach_demo_actions(request: Request):
    return HTMLResponse(
        '<div class="card"><h2>📱 AI 感官扩展 — 需要手机帮忙的事</h2>'
        '<p style="font-size:11px;color:var(--dim);margin-bottom:8px">点击下方按钮，AI 会向你的手机发送任务</p>'
        '<div style="display:flex;flex-wrap:wrap;gap:4px">'
        '<button hx-post="/tree/reach/request" hx-target="#reach-demo-result" hx-swap="innerHTML" '
        'hx-vals=\'{"sensor_type":"camera_photo","title":"拍摄现场照片",'
        '"instruction":"请拍摄项目现场的照片","context":"环评报告 — 环境现状调查章节需要现场照片"}\''
        'class="lc-tool-btn">📸 拍现场照</button>'
        '<button hx-post="/tree/reach/request" hx-target="#reach-demo-result" hx-swap="innerHTML" '
        'hx-vals=\'{"sensor_type":"gps_location","title":"获取当前位置","instruction":"请获取当前位置的精确坐标",'
        '"context":"项目选址 — 需要确认坐标在允许范围内"}\''
        'class="lc-tool-btn">📍 获取位置</button>'
        '<button hx-post="/tree/reach/request" hx-target="#reach-demo-result" hx-swap="innerHTML" '
        'hx-vals=\'{"sensor_type":"microphone","title":"录制环境声音","instruction":"请录制10秒环境声音",'
        '"context":"噪声监测 — 现场噪声水平评估"}\''
        'class="lc-tool-btn">🎤 录环境音</button>'
        '<button hx-post="/tree/reach/request" hx-target="#reach-demo-result" hx-swap="innerHTML" '
        'hx-vals=\'{"sensor_type":"nfc_tag","title":"扫描NFC标签","instruction":"请扫描现场的NFC设备标签",'
        '"context":"设备巡检 — 记录设备运行状态"}\''
        'class="lc-tool-btn">📡 扫描设备</button>'
        '</div><div id="reach-demo-result" style="margin-top:8px;font-size:12px;color:var(--dim)"></div></div>')


__all__ = ["reach_router"]
