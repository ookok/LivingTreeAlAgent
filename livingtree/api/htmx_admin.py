"""HTMX Admin routes — management panels & dashboards.

Extracted from htmx_web.py.
"""
from __future__ import annotations

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from loguru import logger

admin_router = APIRouter(prefix="/admin", tags=["admin"])

@admin_router.get("/admin/models")
async def tree_admin_models(request: Request):
    """Authoritative model election dashboard — LLMFit-style evaluation matrix."""
    from ..core.model_dashboard import get_model_dashboard
    dashboard = get_model_dashboard()
    task_type = request.query_params.get("task", "general")
    cards = dashboard.build_cards(task_type=task_type)
    return HTMLResponse(dashboard.render_html(cards, task_hint=task_type))

# ═══ QGIS-inspired Panels ═══

@admin_router.get("/admin/plugins")
async def tree_admin_plugins(request: Request):
    from ..core.skill_hub import get_skill_hub
    return HTMLResponse(get_skill_hub().render_html())

@admin_router.get("/admin/toolbox")
async def tree_admin_toolbox(request: Request):
    from ..core.processing_framework import get_processing
    return HTMLResponse(get_processing().render_toolbox_html())

@admin_router.get("/admin/organs")
async def tree_admin_organs(request: Request):
    from ..core.organ_dashboard import get_organ_dashboard
    return HTMLResponse(get_organ_dashboard().render_html())

# ═══ OpenMetadata-inspired Panels ═══

@admin_router.get("/admin/lineage")
async def tree_admin_lineage(request: Request):
    from ..knowledge.knowledge_lineage import get_lineage
    return HTMLResponse(get_lineage().render_html())

@admin_router.get("/admin/classifier")
async def tree_admin_classifier(request: Request):
    from ..core.auto_classifier import get_classifier
    sample = request.query_params.get("sample", "")
    return HTMLResponse(get_classifier().render_html(sample))

@admin_router.get("/admin/quality")
async def tree_admin_quality(request: Request):
    from ..knowledge.quality_guard import QUALITY_TEMPLATES
    rows = "".join(
        f'<tr><td style="padding:4px 8px;font-size:11px"><b>{t.name}</b></td>'
        f'<td style="padding:4px 8px;font-size:10px;color:var(--dim)">{t.description}</td>'
        f'<td style="padding:4px 8px;font-size:10px">{t.severity}</td>'
        f'<td style="padding:4px 8px;font-size:9px;color:var(--dim)">{t.domain}</td></tr>'
        for t in QUALITY_TEMPLATES
    )
    return HTMLResponse(f'''<div class="card">
<h2>✅ 质量测试库 <span style="font-size:10px;color:var(--dim)">— OpenMetadata DQ Test Library</span></h2>
<div style="font-size:9px;color:var(--dim);margin:4px 0">{len(QUALITY_TEMPLATES)}个参数化测试模板</div>
<table style="width:100%;border-collapse:collapse;font-size:11px">
<thead><tr style="border-bottom:2px solid var(--border);font-size:10px;color:var(--dim)">
  <th>测试</th><th>描述</th><th>级别</th><th>领域</th></tr></thead>
<tbody>{rows}</tbody></table>
<div style="font-size:9px;color:var(--dim);margin-top:8px">error=阻断 warning=提示 info=信息 · 支持参数化SQL式条件</div></div>''')

# ═══ AI Awareness Dashboard ═══

@admin_router.get("/admin/awareness")
async def tree_admin_awareness(request: Request):
    from ..core.awareness_engine import get_awareness
    return HTMLResponse(get_awareness().render_html())

@admin_router.get("/admin/vitals")
async def tree_admin_vitals(request: Request):
    from ..core.vitals import get_vitals
    v = get_vitals().measure()
    return HTMLResponse(f'''<div class="card">
<h2>💓 生命体征 <span style="font-size:10px;color:var(--dim)">— Living Pot 硬件遥测</span></h2>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:8px 0">
  <div style="text-align:center;padding:8px;background:var(--panel);border-radius:6px">
    <div style="font-size:24px">{'🔥' if v['cpu']['percent'] > 70 else '⚡' if v['cpu']['percent'] > 30 else '💤'}</div>
    <div style="font-size:18px;font-weight:700">{v['cpu']['percent']:.0f}%</div>
    <div style="font-size:10px;color:var(--dim)">CPU · {v['cpu']['level']}</div></div>
  <div style="text-align:center;padding:8px;background:var(--panel);border-radius:6px">
    <div style="font-size:24px">{'🧠' if v['memory']['percent'] > 70 else '💧'}</div>
    <div style="font-size:18px;font-weight:700">{v['memory']['percent']:.0f}%</div>
    <div style="font-size:10px;color:var(--dim)">RAM · {v['memory']['level']}</div></div>
  <div style="text-align:center;padding:8px;background:var(--panel);border-radius:6px">
    <div style="width:24px;height:24px;border-radius:50%;background:{v['led']['color_hex']};margin:0 auto"></div>
    <div style="font-size:11px;margin-top:4px">LED {v['led']['color_hex']}</div>
    <div style="font-size:9px;color:var(--dim)">亮度{v['led']['brightness']:.0%} · {v['led']['pulse_rate']}</div></div>
  <div style="text-align:center;padding:8px;background:var(--panel);border-radius:6px">
    <div style="font-size:24px">{v['leaf_display']['state']}</div>
    <div style="font-size:10px">{v['leaf_display']['message']}</div></div>
</div></div>''')

@admin_router.get("/admin/city")
async def tree_admin_city(request: Request):
    from ..core.city_mcp import get_city_mcp
    return HTMLResponse(get_city_mcp().render_html())

@admin_router.get("/admin/green")
async def tree_admin_green(request: Request):
    from ..core.green_scheduler import get_green_scheduler
    return HTMLResponse(get_green_scheduler().render_html())

@admin_router.get("/admin/shield")
async def tree_admin_shield(request: Request):
    from ..core.prompt_shield import get_shield
    return HTMLResponse(get_shield().render_html())

@admin_router.get("/admin/layers")
async def tree_admin_layers(request: Request):
    """3-layer provider configuration panel."""
    from ..treellm.sticky_election import get_layer_config, LayerConfigManager
    mgr = get_layer_config()
    configs = mgr.get_all()
    
    rows = ""
    for name in ["vector", "fast", "reasoning"]:
        c = configs[name]
        icon = {"vector": "🧮", "fast": "⚡", "reasoning": "🧠"}[name]
        desc = {"vector": "意图识别 & 嵌入", "fast": "日常快反 (80%请求)", "reasoning": "深度推理 & 创作"}[name]
        deg = "🔴" if c["degraded"] else "🟢"
        rows += f'''
        <div class="card" style="padding:12px;margin:8px 0">
          <div style="display:flex;justify-content:space-between;align-items:center">
            <div>
              <b>{icon} {name.upper()}</b>
              <span style="color:var(--dim);font-size:11px;margin-left:8px">{desc}</span>
              <span style="margin-left:8px">{deg}</span>
            </div>
            <div style="font-size:10px;color:var(--dim)">{c["successes"]} OK / {c["failures"]} fail</div>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr 2fr;gap:8px;margin-top:8px">
            <div>
              <label style="font-size:10px;color:var(--dim)">Provider</label>
              <input id="{name}-provider" value="{c["provider"]}" style="width:100%;padding:4px;border:1px solid var(--border);border-radius:4px;background:var(--panel);color:var(--text);font-size:11px">
            </div>
            <div>
              <label style="font-size:10px;color:var(--dim)">Model</label>
              <input id="{name}-model" value="{c["model"]}" style="width:100%;padding:4px;border:1px solid var(--border);border-radius:4px;background:var(--panel);color:var(--text);font-size:11px">
            </div>
            <div>
              <label style="font-size:10px;color:var(--dim)">API Key {"✅" if c["api_key_set"] else ""}</label>
              <input id="{name}-apikey" placeholder="(从vault自动加载)" style="width:100%;padding:4px;border:1px solid var(--border);border-radius:4px;background:var(--panel);color:var(--text);font-size:11px">
            </div>
          </div>
        </div>'''
    
    html = f'''<div class="card">
<h2>🔧 层配置 <span style="font-size:10px;color:var(--dim)">— 向量层 · 快反层 · 推理层</span></h2>
<p style="font-size:10px;color:var(--dim);margin:4px 0">配置自动保存到 .livingtree/layer_config.json。留空使用默认值。</p>
{rows}
<div style="margin-top:12px;display:flex;gap:6px">
  <button onclick="saveLayers()" style="font-size:11px;padding:6px 16px;background:var(--accent);color:var(--bg);border:none;border-radius:6px;cursor:pointer">💾 保存</button>
  <button onclick="resetLayers()" style="font-size:11px;padding:6px 16px;background:var(--panel);color:var(--dim);border:1px solid var(--border);border-radius:6px;cursor:pointer">↩ 重置默认</button>
</div>
<div id="layer-result" style="margin-top:8px;font-size:10px;color:var(--dim)"></div>
</div>
<script>
async function saveLayers(){{
  var data={{}};
  ["vector","fast","reasoning"].forEach(function(n){{
    var l={{"vector":0,"fast":1,"reasoning":2}}[n];
    data[n]={{provider:document.getElementById(n+"-provider").value,model:document.getElementById(n+"-model").value,api_key:document.getElementById(n+"-apikey").value}};
  }});
  var el=document.getElementById("layer-result");
  try{{
    var r=await fetch("/api/layers/save",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify(data)}});
    var j=await r.json();
    el.innerHTML="<span style=\\'color:var(--accent)\\'>✅ 已保存。重启或下次请求生效。</span>";
  }}catch(e){{el.innerHTML="<span style=\\'color:var(--err)\\'>❌ "+e.message+"</span>"}}
}}
async function resetLayers(){{
  var el=document.getElementById("layer-result");
  try{{
    var r=await fetch("/api/layers/reset",{{method:"POST"}});
    var j=await r.json();
    el.innerHTML="<span style=\\'color:var(--accent)\\'>✅ 已重置为默认值。刷新页面查看。</span>";
    setTimeout(function(){{location.reload()}},500);
  }}catch(e){{el.innerHTML="<span style=\\'color:var(--err)\\'>❌ "+e.message+"</span>"}}
}}
</script>'''
    return HTMLResponse(html)


@admin_router.get("/admin/telemetry")
async def tree_admin_telemetry(request: Request):
    from ..core.telemetry import get_telemetry
    return HTMLResponse(get_telemetry().render_html())

@admin_router.get("/reach/mobile")
async def tree_reach_mobile(request: Request):
    return _render_template("reach_mobile.html", request=request)

@admin_router.get("/admin/spider")
async def tree_admin_spider(request: Request):
    """Scrapling Spider framework — visual crawl dashboard."""
    from ..capability.browser_agent import BrowserAgent  # verify import works
    from scrapling.fetchers import StealthyFetcher
    stealth_ok = "✅ StealthyFetcher (patchright)"
    html = '''<div class="card">
<h2>🕷 爬虫框架 <span style="font-size:10px;color:var(--dim)">— Scrapling Spider + LLM</span></h2>
<div style="display:flex;gap:16px;margin:8px 0;font-size:11px">
  <span>✅ Scrapling + Playwright</span><span>''' + stealth_ok + '''</span>
</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
  <div class="card" style="padding:10px">
    <h3>🎯 已集成特性</h3>
    <table style="width:100%;font-size:11px;border-collapse:collapse">
      <tr><td style="padding:4px;border-bottom:1px solid var(--border)"><b>自适应选择器</b></td><td style="text-align:right">auto_save / adaptive</td></tr>
      <tr><td style="padding:4px;border-bottom:1px solid var(--border)"><b>文本搜索</b></td><td style="text-align:right">find_by_text / regex</td></tr>
      <tr><td style="padding:4px;border-bottom:1px solid var(--border)"><b>同类元素发现</b></td><td style="text-align:right">find_similar</td></tr>
      <tr><td style="padding:4px;border-bottom:1px solid var(--border)"><b>选择器自动生成</b></td><td style="text-align:right">generate_css_selector</td></tr>
      <tr><td style="padding:4px;border-bottom:1px solid var(--border)"><b>广告屏蔽</b></td><td style="text-align:right">block_ads (~3500域名)</td></tr>
      <tr><td style="padding:4px;border-bottom:1px solid var(--border)"><b>资源拦截</b></td><td style="text-align:right">disable_resources (+25%速度)</td></tr>
      <tr><td style="padding:4px;border-bottom:1px solid var(--border)"><b>自动重试</b></td><td style="text-align:right">retries=2</td></tr>
      <tr><td style="padding:4px;border-bottom:1px solid var(--border)"><b>元素等待</b></td><td style="text-align:right">wait_selector</td></tr>
      <tr><td style="padding:4px;border-bottom:1px solid var(--border)"><b>Canvas指纹</b></td><td style="text-align:right">hide_canvas (需patchright)</td></tr>
      <tr><td style="padding:4px"><b>Cloudflare绕过</b></td><td style="text-align:right">solve_cloudflare (需patchright)</td></tr>
    </table>
  </div>
  <div class="card" style="padding:10px">
    <h3>🔧 快速测试</h3>
    <div style="margin:8px 0">
      <input id="spider-url" placeholder="目标URL" style="width:100%;padding:6px;border:1px solid var(--border);border-radius:4px;background:var(--panel);color:var(--text);font-size:12px" value="http://esg.epmap.org/reports">
    </div>
    <div style="margin:8px 0">
      <input id="spider-task" placeholder="提取任务 (如: 搜索格林美ESG报告)" style="width:100%;padding:6px;border:1px solid var(--border);border-radius:4px;background:var(--panel);color:var(--text);font-size:12px" value="搜索ESG报告">
    </div>
    <button onclick="runSpider()" style="font-size:12px;padding:8px 20px;background:var(--accent);color:var(--bg);border:none;border-radius:6px;cursor:pointer">▶ 运行爬虫</button>
    <div id="spider-result" style="margin-top:12px;font-size:11px;color:var(--dim);max-height:400px;overflow:auto"></div>
  </div>
</div>
</div>
<script>
async function runSpider() {
  var url = document.getElementById("spider-url").value;
  var task = document.getElementById("spider-task").value;
  var el = document.getElementById("spider-result");
  el.innerHTML = '<div class="lc-loading">爬取中...</div>';
  try {
    var resp = await fetch("/tree/api/debug/chat", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({message: "/browse " + url + " task=" + task, stream: false})
    });
    var data = await resp.json();
    el.innerHTML = "<pre style='white-space:pre-wrap;font-size:10px'>" + JSON.stringify(data, null, 2).slice(0, 3000) + "</pre>";
  } catch(e) {
    el.innerHTML = "<span style='color:var(--err)'>Error: " + e.message + "</span>";
  }
}
</script>'''
    return HTMLResponse(html)

# ═══ Unified Admin Console ═══

@admin_router.get("/admin")
async def tree_admin_console(request: Request):
    """Unified admin console — aggregates all 7+ admin panels in one view."""
    return HTMLResponse('''<div style="padding:8px">
<h2 style="margin-bottom:8px">⚙ 管理员控制台 <span style="font-size:10px;color:var(--dim);font-weight:400">— 统一管理面板</span></h2>

<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:6px;margin-bottom:12px">
  <button onclick="loadAdminPanel('models')" class="admin-nav-btn active" id="admin-nav-models">📊 模型选举</button>
  <button onclick="loadAdminPanel('plugins')" class="admin-nav-btn" id="admin-nav-plugins">🧩 插件生态</button>
  <button onclick="loadAdminPanel('toolbox')" class="admin-nav-btn" id="admin-nav-toolbox">🔧 处理工具箱</button>
  <button onclick="loadAdminPanel('organs')" class="admin-nav-btn" id="admin-nav-organs">🫀 器官层面板</button>
  <button onclick="loadAdminPanel('lineage')" class="admin-nav-btn" id="admin-nav-lineage">🔗 知识血缘</button>
  <button onclick="loadAdminPanel('classifier')" class="admin-nav-btn" id="admin-nav-classifier">🏷 自动分类</button>
  <button onclick="loadAdminPanel('quality')" class="admin-nav-btn" id="admin-nav-quality">✅ 质量测试</button>
  <button onclick="loadAdminPanel('awareness')" class="admin-nav-btn" id="admin-nav-awareness">🧘 意识</button>
  <button onclick="loadAdminPanel('vitals')" class="admin-nav-btn" id="admin-nav-vitals">💓 体征</button>
  <button onclick="loadAdminPanel('city')" class="admin-nav-btn" id="admin-nav-city">🏯 城市</button>
  <button onclick="loadAdminPanel('green')" class="admin-nav-btn" id="admin-nav-green">🌿 绿色</button>
  <button onclick="loadAdminPanel('shield')" class="admin-nav-btn" id="admin-nav-shield">🛡️ 防护</button>
  <button onclick="loadAdminPanel('telemetry')" class="admin-nav-btn" id="admin-nav-telemetry">📊 遥测</button>
  <button onclick="loadAdminPanel('pipeline')" class="admin-nav-btn" id="admin-nav-pipeline">⚙ 管道</button>
  <button onclick="loadAdminPanel('layers')" class="admin-nav-btn" id="admin-nav-layers">🔧 层配置</button>
  <button onclick="loadAdminPanel('spider')" class="admin-nav-btn" id="admin-nav-spider">🕷 爬虫</button>
</div>

<div id="admin-panel-content" style="min-height:400px">
  <div class="lc-loading" style="min-height:200px">加载模型选举仪表盘...</div>
</div>

<style>
.admin-nav-btn{background:var(--panel);border:1px solid var(--border);color:var(--text);padding:6px 12px;border-radius:6px;font-size:11px;cursor:pointer;white-space:nowrap;transition:all .2s}
.admin-nav-btn:hover{border-color:var(--accent)}
.admin-nav-btn.active{background:var(--accent);color:var(--bg);border-color:var(--accent)}
</style>

<script>
var adminPanelMap = {
  models: "/tree/admin/models",
  plugins: "/tree/admin/plugins",
  toolbox: "/tree/admin/toolbox",
  organs: "/tree/admin/organs",
  lineage: "/tree/admin/lineage",
  classifier: "/tree/admin/classifier",
  quality: "/tree/admin/quality",
  awareness: "/tree/admin/awareness",
  vitals: "/tree/admin/vitals",
  city: "/tree/admin/city",
  green: "/tree/admin/green",
  shield: "/tree/admin/shield",
  telemetry: "/tree/admin/telemetry",
  pipeline: "/tree/admin/pipeline",
  layers: "/tree/admin/layers",
  spider: "/tree/admin/spider"
};

function loadAdminPanel(name) {
  document.querySelectorAll(".admin-nav-btn").forEach(function(b) { b.classList.remove("active"); });
  var btn = document.getElementById("admin-nav-" + name);
  if (btn) btn.classList.add("active");
  var el = document.getElementById("admin-panel-content");
  el.innerHTML = '<div class="lc-loading" style="min-height:200px">加载中...</div>';
  fetch(adminPanelMap[name]).then(function(r) { return r.text(); }).then(function(html) {
    el.innerHTML = html;
  });
}

// Load models panel by default
setTimeout(function() { loadAdminPanel("models"); }, 200);
</script>
</div>''')

@admin_router.get("/creative/twin")
async def tree_creative_twin(request: Request):
    from ..core.creative_viz import get_creative
    cv = get_creative()
    if cv is not None:
        cv._hub = _get_hub(request)
    return HTMLResponse(
        '<div class="card"><h2>🪞 数字孪生镜像</h2>'
        '<p style="font-size:11px;color:var(--dim);margin-bottom:8px">这是小树对你的认知。纠正它，帮助它更好地理解你。</p>'
        + cv.build_digital_twin() + '</div>')


@admin_router.get("/pair/all-methods")
async def tree_pair_all_methods(request: Request):
    """Show all available pairing methods: code, QR, LAN, audio."""
    from ..network.universal_pairing import get_pairing
    pairing = get_pairing()
    code = pairing.generate_code()
    server_host = request.headers.get("host", "localhost:8100")
    protocol = "https" if request.url.scheme == "https" else "http"
    server_url = f"{protocol}://{server_host}"
    qr_url = pairing.generate_qr_url(server_url)
    qr_img = f"https://api.qrserver.com/v1/create-qr-code/?size=180x180&data={qr_url}"

    lan_devices = pairing.detect_lan_devices()
    lan_html = ""
    for d in lan_devices[:5]:
        lan_html += f'<div style="padding:3px 0;font-size:11px">📡 {d["name"]} ({d.get("address","")[:20]}) <button onclick="pairLanDevice(\'{d["device_id"]}\')" style="font-size:9px;padding:2px 6px">配对</button></div>'
    if not lan_html:
        lan_html = '<div style="color:var(--dim);font-size:11px">未发现同网络设备</div>'

    return HTMLResponse(
        '<div class="card">'
        '<h2>🔗 万物互联 · 多模态配对</h2>'
        '<p style="font-size:11px;color:var(--dim);margin:4px 0">任选一种方式连接设备。配对后自动协商能力，渐进提升信任。</p>'

        '<div style="margin:8px 0;display:grid;grid-template-columns:1fr 1fr;gap:8px">'

        f'<div style="background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:12px;text-align:center">'
        f'<div style="font-size:20px;margin-bottom:4px">🔢</div>'
        f'<div style="font-size:11px;color:var(--dim);margin-bottom:4px">8位数字码</div>'
        f'<div style="font-size:22px;font-weight:700;font-family:monospace;letter-spacing:6px;color:var(--accent);margin:8px 0">{code}</div>'
        f'<div style="font-size:9px;color:var(--dim)">在手机上输入此码 · 5分钟有效</div></div>'

        f'<div style="background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:12px;text-align:center">'
        f'<div style="font-size:20px;margin-bottom:4px">📱</div>'
        f'<div style="font-size:11px;color:var(--dim);margin-bottom:4px">扫码配对</div>'
        f'<img src="{qr_img}" style="width:120px;height:120px;background:#fff;border-radius:6px;margin:4px 0">'
        f'<div style="font-size:9px;color:var(--dim)">扫描二维码自动连接</div></div>'

        f'<div style="background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:12px;text-align:center">'
        f'<div style="font-size:20px;margin-bottom:4px">📡</div>'
        f'<div style="font-size:11px;color:var(--dim);margin-bottom:4px">同WiFi自动发现</div>'
        f'{lan_html}'
        f'<div style="font-size:9px;color:var(--dim);margin-top:4px">零操作自动配对</div></div>'

        f'<div style="background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:12px;text-align:center">'
        f'<div style="font-size:20px;margin-bottom:4px">🔊</div>'
        f'<div style="font-size:11px;color:var(--dim);margin-bottom:4px">超声波配对</div>'
        f'<button onclick="startAudioPairing()" style="font-size:11px;padding:6px 14px;margin:4px 0">▶ 发射音频信号</button>'
        f'<div id="audio-pair-status" style="font-size:9px;color:var(--dim)">手机会听到超声波自动配对</div></div>'

        '</div>'

        '<div style="margin-top:8px"><h4 style="font-size:12px;margin-bottom:4px">已配对设备</h4>'
        + "".join(
            f'<div style="padding:3px 0;font-size:11px;display:flex;justify-content:space-between">'
            f'<span>{d["name"]} ({d["type"]}) — {d["pair_method"]}</span>'
            f'<span style="color:var(--accent)">信任 Lv.{d["trust"]}</span></div>'
            for d in pairing.get_paired_devices()
        )
        + '</div>'
        '</div>'
    )


@admin_router.get("/remote/panel")
async def tree_remote_panel(request: Request):
    """WebRTC remote ops panel — remote terminal, file browser, system monitor."""
    return HTMLResponse(
        '<div class="card">'
        '<h2>🖥 远程运维 · WebRTC P2P</h2>'
        '<div style="margin-bottom:8px">'
        '<span id="rtc-status" style="font-size:11px;color:var(--dim)">点击连接建立P2P通道</span>'
        '<button onclick="rtcConnect()" style="font-size:10px;padding:4px 10px;margin-left:8px">🔗 建立连接</button>'
        '</div>'

        '<div style="display:flex;gap:8px;margin-bottom:8px">'
        '<button onclick="showRtcTab(\'shell\')" class="tab-btn active" id="rtc-tab-shell">💻 终端</button>'
        '<button onclick="showRtcTab(\'files\')" class="tab-btn" id="rtc-tab-files">📂 文件</button>'
        '<button onclick="showRtcTab(\'monitor\')" class="tab-btn" id="rtc-tab-monitor">📊 监控</button>'
        '</div>'

        '<div id="rtc-tab-shell-content">'
        '<div style="display:flex;gap:4px;margin-bottom:4px">'
        '<input id="rtc-shell-cmd" placeholder="命令..." style="flex:1;font-size:12px;font-family:monospace;padding:6px 8px" onkeydown="if(event.key===\'Enter\')rtcShell()">'
        '<button onclick="rtcShell()" style="font-size:11px;padding:6px 12px">执行</button></div>'
        '<pre id="rtc-shell-out" style="background:rgba(0,0,0,.1);padding:8px;border-radius:4px;max-height:350px;overflow-y:auto;font-size:11px;min-height:80px;color:var(--text)">等待命令...</pre></div>'

        '<div id="rtc-tab-files-content" style="display:none">'
        '<div style="display:flex;gap:4px;margin-bottom:4px">'
        '<input id="rtc-file-path" placeholder="路径..." value="." style="flex:1;font-size:11px;padding:4px 8px">'
        '<button onclick="rtcFileBrowse()" style="font-size:10px;padding:4px 10px">浏览</button></div>'
        '<div style="display:flex;gap:8px"><div id="rtc-file-list" style="flex:1;max-height:250px;overflow-y:auto;font-size:11px;background:rgba(0,0,0,.05);padding:4px;border-radius:4px;min-height:100px"></div>'
        '<pre id="rtc-file-content" style="flex:2;max-height:250px;overflow-y:auto;font-size:10px;background:rgba(0,0,0,.05);padding:4px;border-radius:4px;min-height:100px;color:var(--dim)">点击文件查看</pre></div></div>'

        '<div id="rtc-tab-monitor-content" style="display:none">'
        '<button id="rtc-monitor-btn" onclick="rtcMonitor()" style="font-size:10px;padding:4px 10px;margin-bottom:8px">▶ 开始监控</button>'
        '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;text-align:center">'
        '<div style="background:rgba(100,150,100,.05);padding:8px;border-radius:6px"><div style="font-size:10px;color:var(--dim)">CPU</div><div style="font-size:20px;font-weight:600;color:var(--accent)" id="rtc-cpu">—</div></div>'
        '<div style="background:rgba(100,150,180,.05);padding:8px;border-radius:6px"><div style="font-size:10px;color:var(--dim)">Memory</div><div style="font-size:20px;font-weight:600;color:#6af" id="rtc-mem">—</div></div>'
        '<div style="background:rgba(150,150,100,.05);padding:8px;border-radius:6px"><div style="font-size:10px;color:var(--dim)">Disk</div><div style="font-size:20px;font-weight:600;color:#fa6" id="rtc-disk">—</div></div></div></div>'
        '</div>'
        '<script>'
        'var _rtcPc=null,_rtcDc=null,_rtcMonitorActive=false,_rtcReqId=0;'
        'function rtcConnect(){_rtcPc=new RTCPeerConnection({iceServers:[{urls:"stun:stun.l.google.com:19302"}]});_rtcDc=_rtcPc.createDataChannel("remote-ops");'
        '_rtcDc.onopen=function(){document.getElementById("rtc-status").innerHTML="<span style=color:var(--accent)>● P2P已连接</span>"};'
        '_rtcDc.onmessage=function(e){rtcOnMsg(JSON.parse(e.data))};'
        '_rtcDc.onclose=function(){document.getElementById("rtc-status").innerHTML="<span style=color:var(--err)>● 断开</span>"};'
        '_rtcPc.createOffer().then(function(o){_rtcPc.setLocalDescription(o);'
        'var ws=new WebSocket((location.protocol==="https:"?"wss:":"ws:")+location.host+"/ws/rtc-signal");'
        'ws.onopen=function(){ws.send(JSON.stringify({sdp:JSON.stringify(o)}))};'
        'ws.onmessage=function(e){var d=JSON.parse(e.data);if(d.sdp)_rtcPc.setRemoteDescription(new RTCSessionDescription(d.sdp));if(d.ice)_rtcPc.addIceCandidate(new RTCIceCandidate(d.ice))}})}}'
        'function rtcSend(op,data){if(_rtcDc&&_rtcDc.readyState==="open"){_rtcReqId++;data.request_id="r"+_rtcReqId;data.op=op;_rtcDc.send(JSON.stringify(data))}}'
        'function rtcOnMsg(d){if(d.op==="pong")return;'
        'if(d.op==="shell_result"){var o=document.getElementById("rtc-shell-out");o.textContent=(d.stdout||"")+(d.stderr||"")||"(无输出)";o.style.color=d.exit===0?"var(--text)":"var(--err)"}'
        'if(d.op==="monitor_data"){document.getElementById("rtc-cpu").textContent=d.cpu+"%";document.getElementById("rtc-mem").textContent=d.mem+"%";document.getElementById("rtc-disk").textContent=d.disk+"%"}'
        'if(d.op==="file_list_result"){var el=document.getElementById("rtc-file-list");el.innerHTML=d.files?d.files.map(function(f){return "<div onclick=rtcSend(\'file_read\',{path:\'"+d.path+"/"+f.name+"\'}) style=cursor:pointer;padding:2px_0;font-size:11px>"+(f.type==="dir"?"📁":"📄")+" "+f.name+"</div>"}).join(""):"error"}'
        'if(d.op==="file_read_result"){document.getElementById("rtc-file-content").textContent=d.content||d.error}}'
        'function rtcShell(){var c=document.getElementById("rtc-shell-cmd").value.trim();if(c&&_rtcDc)rtcSend("shell",{cmd:c})}'
        'function rtcMonitor(){_rtcMonitorActive=!_rtcMonitorActive;rtcSend(_rtcMonitorActive?"monitor_start":"monitor_stop",{interval:2});document.getElementById("rtc-monitor-btn").textContent=_rtcMonitorActive?"⏸ 停止":"▶ 开始监控"}'
        'function rtcFileBrowse(){rtcSend("file_list",{path:document.getElementById("rtc-file-path").value||"."})}'
        'function showRtcTab(t){["shell","files","monitor"].forEach(function(x){var e=document.getElementById("rtc-tab-"+x+"-content");var b=document.getElementById("rtc-tab-"+x);if(e)e.style.display=x===t?"block":"none";if(b)b.classList.toggle("active",x===t)})}'
        'setInterval(function(){if(_rtcDc&&_rtcDc.readyState==="open")rtcSend("ping",{})},15000);'
        '</script>'
    )


@admin_router.get("/p2p/status")
async def tree_p2p_status(request: Request):
    """P2P connectivity: NAT type, relay health, active peers."""
    hub = _get_hub(request)
    if not hub:
        return HTMLResponse('<div style="color:var(--dim)">系统未就绪</div>')

    from ..network.nat_traverse import NATType

    nat = getattr(getattr(hub, "world", None), "nat_traverser", None)
    st = nat.status() if nat else {"nat_type": "unknown", "public_endpoint": "", "active_peers": 0, "healthy_relays": 0, "relays": []}

    nat_descriptions = {
        "open": "🟢 公网IP — 最佳P2P,无需打洞",
        "full_cone": "🟢 Full Cone — 直接通信,成功率高",
        "restricted": "🟡 Restricted Cone — 需先发包,成功率90%+",
        "port_restricted": "🟠 Port-Restricted — 需端口匹配",
        "symmetric": "🔴 Symmetric — 需端口预测,中继兜底",
        "udp_blocked": "⚫ UDP被封锁 — 仅TCP/中继",
        "unknown": "⏳ 检测中...",
    }

    relays_html = ""
    for r in st.get("relays", []):
        icon = "🟢" if r.get("healthy") else "🔴"
        relays_html += f'<div style="font-size:11px;padding:2px 0">{icon} {r["host"]}:{r["port"]} (fail: {r.get("failures", 0)})</div>'

    return HTMLResponse(
        '<div class="card">'
        f'<h2>🔗 P2P 连接状态</h2>'
        f'<div style="padding:8px;background:rgba(100,150,180,.05);border-radius:6px;margin:8px 0">'
        f'<div style="font-size:14px;font-weight:600">{nat_descriptions.get(st.get("nat_type","unknown"), "⏳ 检测中")}</div>'
        f'<div style="font-size:10px;color:var(--dim);margin-top:4px">公网端点: {st.get("public_endpoint","检测中")}</div></div>'
        f'<div class="metric"><span>活跃P2P连接</span><span>{st.get("active_peers", 0)}</span></div>'
        f'<div class="metric"><span>健康中继</span><span>{st.get("healthy_relays", 0)}/{len(st.get("relays",[]))}</span></div>'
        f'<div style="margin-top:8px">{relays_html}</div>'
        f'<div style="margin-top:8px;font-size:10px;color:var(--dim)">'
        f'策略: 直连优先 → UDP打洞 → TCP直连 → TURN中继<br>'
        f'保活间隔: FullCone=20s Symmetric=10s</div>'
        '</div>'
    )


@admin_router.get("/tools/suggest")
async def tree_tools_suggest(request: Request, context: str = Query(default="")):
    """AI suggests interactive tools based on task context. Returns tool card HTML."""
    if not context.strip():
        return HTMLResponse('<div style="color:var(--dim);font-size:12px">没有上下文</div>')

    from ..core.interactive_tools import get_tool_registry
    registry = get_tool_registry()

    hub = _get_hub(request)
    available_tools = []
    if hub:
        try:
            tm = getattr(hub.world, "tool_market", None)
            if tm:
                found = tm.search(context)[:5]
                available_tools = [{"name": t.name, "description": getattr(t, "description", "")} for t in found]
        except Exception:
            pass

    offers = registry.suggest_tools(context, available_tools)
    if not offers:
        return HTMLResponse('<div style="color:var(--dim);font-size:12px">AI暂未建议交互工具</div>')

    html_parts = []
    for offer in offers:
        html_parts.append(offer.to_html())

    return HTMLResponse("\n".join(html_parts))


@admin_router.post("/tools/result")
async def tree_tools_result(request: Request):
    """User submits a tool result. Feeds back into AI context."""
    try:
        body = await request.json()
    except Exception:
        return HTMLResponse('<div style="color:var(--warn)">无效数据</div>')

    offer_id = body.get("offer_id", "")
    tool_type = body.get("tool_type", "custom")
    result = body.get("result", {})

    hub = _get_hub(request)
    if hub and hub.world and hub.world.consciousness:
        try:
            result_str = str(result)[:1000]
            resp = await hub.world.consciousness.chain_of_thought(
                f"用户使用工具 '{tool_type}' 产生以下结果:\n{result_str}\n\n"
                f"请基于此结果提供简短反馈或下一步建议 (1-2句)。", steps=1,
            )
            feedback = resp if isinstance(resp, str) else str(resp)
        except Exception:
            feedback = f"已收到 {tool_type} 工具结果，继续分析中..."

        return HTMLResponse(
            f'<div class="msg assistant" style="margin-top:8px">'
            f'<div class="who">小树 🌳 · 工具反馈</div>'
            f'<div class="text">{_html.escape(feedback[:500])}</div></div>'
        )

    return HTMLResponse('<div style="color:var(--dim);font-size:12px">AI已收到工具结果</div>')


@admin_router.get("/perf/stats")
async def tree_perf_stats(request: Request):
    """Performance stats: cache hit rate, stream render status."""
    from ..core.perf_accel import get_response_cache, get_stream_render
    from ..core.adaptive_folder import get_folder
    from ..core.final_polish import get_ladder, get_predictive
    cache = get_response_cache()
    sr = get_stream_render()
    folder = get_folder()
    fs = folder.stats()
    ladder = get_ladder()
    ls = ladder.status()
    pred = get_predictive()
    ps = pred.stats()
    return HTMLResponse(
        '<div class="card">'
        '<h2>⚡ 性能统计</h2>'
        f'<div class="metric"><span>缓存命中率</span><span>{cache.stats()["hit_rate"]}</span></div>'
        f'<div class="metric"><span>缓存条目</span><span>{cache.stats()["entries"]}/{cache.stats()["max_entries"]}</span></div>'
        f'<div class="metric"><span>预测命中率</span><span style="color:var(--accent)">{ps["hit_rate"]} ({ps["hits"]}/{ps["hits"]+ps["misses"]})</span></div>'
        f'<div class="metric"><span>节省Token</span><span>{cache.stats()["tokens_saved"]:,}</span></div>'
        f'<div class="metric"><span>成本层级</span><span style="color:{"var(--accent)" if ls["current_tier"]=="pro" else "var(--warn)"}">{ls["current_tier"]} → {ls["recommended_model"]}</span></div>'
        f'<div class="metric"><span>流渲染节流</span><span>{sr._throttle*1000:.0f}ms / {sr._chunk_chars}字符</span></div>'
        f'<div style="margin-top:8px;border-top:1px solid var(--border);padding-top:8px">'
        f'<h4 style="font-size:12px;margin-bottom:4px">🧠 自适应折叠</h4>'
        f'<div class="metric"><span>折叠次数 / 省字符</span><span>{fs["total_folds"]} / {fs["saved_chars"]:,}</span></div>'
        f'<div class="metric"><span>估算省费用</span><span>¥{fs["estimated_cost_saved_yuan"]:.6f}</span></div></div>'
        '</div>'
    )



__all__ = ["admin_router"]
