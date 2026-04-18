"""
智能创作与内容监控系统 - Web管理界面
"""

from pathlib import Path
from typing import Dict, Optional


def get_dashboard_html() -> str:
    """获取管理界面HTML"""
    return '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>内容监控中心</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        :root { --primary: #4F46E5; --success: #10B981; --warning: #F59E0B; --danger: #EF4444; --bg: #F9FAFB; --card-bg: #FFFFFF; --text: #1F2937; --text-muted: #6B7280; --border: #E5E7EB; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; }
        .navbar { background: var(--card-bg); border-bottom: 1px solid var(--border); padding: 0 24px; height: 64px; display: flex; align-items: center; justify-content: space-between; position: sticky; top: 0; z-index: 100; }
        .navbar-brand { font-size: 20px; font-weight: 600; color: var(--primary); }
        .navbar-nav { display: flex; gap: 8px; list-style: none; }
        .nav-item { padding: 8px 16px; border-radius: 8px; cursor: pointer; transition: all 0.2s; }
        .nav-item:hover, .nav-item.active { background: var(--primary); color: white; }
        .container { max-width: 1400px; margin: 0 auto; padding: 24px; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }
        .stat-card { background: var(--card-bg); border-radius: 12px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .stat-value { font-size: 32px; font-weight: 700; color: var(--primary); }
        .stat-label { color: var(--text-muted); font-size: 14px; }
        .stat-card.danger .stat-value { color: var(--danger); }
        .stat-card.warning .stat-value { color: var(--warning); }
        .stat-card.success .stat-value { color: var(--success); }
        .content-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
        @media (max-width: 900px) { .content-grid { grid-template-columns: 1fr; } }
        .card { background: var(--card-bg); border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); overflow: hidden; }
        .card-header { padding: 16px 20px; border-bottom: 1px solid var(--border); font-weight: 600; display: flex; justify-content: space-between; align-items: center; }
        .card-body { padding: 20px; }
        .form-group { margin-bottom: 16px; }
        .form-label { display: block; margin-bottom: 6px; font-weight: 500; font-size: 14px; }
        .form-textarea { width: 100%; min-height: 150px; padding: 12px; border: 1px solid var(--border); border-radius: 8px; font-family: inherit; font-size: 14px; resize: vertical; }
        .form-textarea:focus { outline: none; border-color: var(--primary); box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1); }
        .btn { padding: 10px 20px; border: none; border-radius: 8px; font-weight: 500; cursor: pointer; transition: all 0.2s; }
        .btn-primary { background: var(--primary); color: white; }
        .btn-primary:hover { background: #4338CA; }
        .alert-item { padding: 12px 16px; border-radius: 8px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; }
        .alert-level-1 { background: #FEF3C7; border-left: 4px solid var(--warning); }
        .alert-level-2 { background: #FED7AA; border-left: 4px solid #F97316; }
        .alert-level-3 { background: #FECACA; border-left: 4px solid var(--danger); }
        .alert-level-4 { background: #FEE2E2; border-left: 4px solid #DC2626; }
        .result-box { background: #F3F4F6; border-radius: 8px; padding: 16px; margin-top: 16px; font-family: monospace; font-size: 13px; white-space: pre-wrap; max-height: 300px; overflow-y: auto; }
        .tabs { display: flex; gap: 4px; margin-bottom: 16px; }
        .tab { padding: 8px 16px; border-radius: 8px 8px 0 0; cursor: pointer; background: var(--border); }
        .tab.active { background: var(--primary); color: white; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .toast { position: fixed; bottom: 24px; right: 24px; padding: 16px 24px; border-radius: 8px; background: var(--text); color: white; opacity: 0; transform: translateY(20px); transition: all 0.3s; z-index: 1000; }
        .toast.show { opacity: 1; transform: translateY(0); }
        .toast.success { background: var(--success); }
        .toast.error { background: var(--danger); }
    </style>
</head>
<body>
    <nav class="navbar">
        <div class="navbar-brand">🛡️ 内容监控中心</div>
        <ul class="navbar-nav">
            <li class="nav-item active" onclick="showTab('dashboard')">仪表板</li>
            <li class="nav-item" onclick="showTab('analyze')">内容分析</li>
            <li class="nav-item" onclick="showTab('alerts')">告警管理</li>
            <li class="nav-item" onclick="showTab('rules')">规则配置</li>
        </ul>
    </nav>
    
    <div class="container">
        <div id="dashboard" class="tab-content active">
            <div class="stats-grid">
                <div class="stat-card"><div class="stat-value" id="stat-total">0</div><div class="stat-label">总内容数</div></div>
                <div class="stat-card danger"><div class="stat-value" id="stat-alerts">0</div><div class="stat-label">总告警数</div></div>
                <div class="stat-card warning"><div class="stat-value" id="stat-pending">0</div><div class="stat-label">待审核</div></div>
                <div class="stat-card success"><div class="stat-value" id="stat-uptime">0s</div><div class="stat-label">运行时长</div></div>
            </div>
            <div class="content-grid">
                <div class="card"><div class="card-header">📊 告警分布</div><div class="card-body" id="alert-chart"></div></div>
                <div class="card"><div class="card-header">📝 最近告警</div><div class="card-body" id="recent-alerts"></div></div>
            </div>
        </div>
        
        <div id="analyze" class="tab-content">
            <div class="content-grid">
                <div class="card"><div class="card-header">📝 内容输入</div><div class="card-body">
                    <div class="form-group"><label class="form-label">待分析内容</label>
                    <textarea class="form-textarea" id="analyze-content" placeholder="输入要分析的内容..."></textarea></div>
                    <button class="btn btn-primary" onclick="analyzeContent()">分析内容</button>
                </div></div>
                <div class="card"><div class="card-header">📊 分析结果</div><div class="card-body">
                    <div id="analyze-result" class="result-box">等待分析...</div>
                </div></div>
            </div>
        </div>
        
        <div id="alerts" class="tab-content">
            <div class="card"><div class="card-header"><span>🚨 告警列表</span><button class="btn btn-primary" onclick="refreshAlerts()">刷新</button></div>
                <div class="card-body" id="alerts-list"></div>
            </div>
        </div>
        
        <div id="rules" class="tab-content">
            <div class="card"><div class="card-header">⚙️ 监控规则</div><div class="card-body" id="rules-list">
                <p>暂无规则数据</p>
            </div></div>
        </div>
    </div>
    
    <div class="toast" id="toast"></div>
    
    <script>
        const API_BASE = "http://localhost:8765/api";
        
        function showTab(tabId) {
            document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
            document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
            document.getElementById(tabId).classList.add("active");
            event.target.classList.add("active");
            if (tabId === "dashboard") refreshStats();
            if (tabId === "alerts") refreshAlerts();
        }
        
        function showToast(message, type = "info") {
            const toast = document.getElementById("toast");
            toast.textContent = message;
            toast.className = "toast show " + type;
            setTimeout(() => toast.classList.remove("show"), 3000);
        }
        
        async function refreshStats() {
            try {
                const res = await fetch(API_BASE + "/stats");
                const data = await res.json();
                if (data.success) {
                    document.getElementById("stat-total").textContent = data.data.total_content;
                    document.getElementById("stat-alerts").textContent = data.data.total_alerts;
                    document.getElementById("stat-pending").textContent = data.data.pending_review;
                    document.getElementById("stat-uptime").textContent = formatUptime(data.data.uptime_seconds);
                    const levels = data.data.alerts_by_level;
                    document.getElementById("alert-chart").innerHTML = Object.entries(levels).map(([k, v]) => 
                        `<div style="margin:8px 0"><span>${k}:</span> <strong>${v}</strong></div>`).join("");
                }
            } catch (e) { console.error(e); }
        }
        
        function formatUptime(s) {
            if (s < 60) return Math.round(s) + "s";
            if (s < 3600) return Math.round(s/60) + "m";
            return Math.round(s/3600) + "h";
        }
        
        async function analyzeContent() {
            const content = document.getElementById("analyze-content").value;
            if (!content.trim()) { showToast("请输入内容", "error"); return; }
            try {
                const res = await fetch(API_BASE + "/analyze", {
                    method: "POST", headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({ content })});
                const data = await res.json();
                const result = document.getElementById("analyze-result");
                if (data.success) {
                    const levelNames = ["正常", "低危", "中危", "高危", "紧急"];
                    result.textContent = JSON.stringify({
                        "内容类型": data.data.content_type, "告警级别": levelNames[data.data.alert_level],
                        "告警原因": data.data.alert_reasons, "状态": data.data.status}, null, 2);
                    showToast("分析完成", "success");
                } else {
                    result.textContent = "分析失败: " + data.error;
                    showToast("分析失败", "error");
                }
            } catch (e) { showToast("连接服务器失败", "error"); }
        }
        
        async function refreshAlerts() {
            try {
                const res = await fetch(API_BASE + "/alerts");
                const data = await res.json();
                if (data.success) {
                    const list = document.getElementById("alerts-list");
                    list.innerHTML = data.data.length === 0 ? "<p>暂无告警</p>" :
                        data.data.map(a => `<div class="alert-item alert-level-${a.alert_level}">
                            <div><strong>级别 ${a.alert_level}</strong><span style="margin-left:12px">${a.content_id}</span></div>
                            <div>${a.matched_keywords.slice(0,2).join(", ")}</div></div>`).join("");
                }
            } catch (e) { console.error(e); }
        }
        
        refreshStats();
        setInterval(refreshStats, 5000);
    </script>
</body>
</html>'''
