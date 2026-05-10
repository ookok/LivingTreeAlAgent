class Dashboard extends Component {
  constructor() {
    super('dashboard');
    this._live = {};
    this.on('dashboard:update', () => { this._fetchLive(); this.render(); });
  }

  async _fetchLive() {
    try {
      var r = await fetch('/api/telemetry/stats'); if (r.ok) this._live.telemetry = await r.json();
    } catch(e) {}
    try {
      var r = await fetch('/api/status/vitals'); if (r.ok) this._live.vitals = await r.json();
    } catch(e) {}
    this.render();
  }

  template() {
    var S = LT.store;
    var st = S.stats();
    var recent = (S.sessions || []).slice(0, 5);
    var vitals = this._live.vitals || {};
    var tele = this._live.telemetry || {};
    var cpu = vitals.cpu || {};
    var mem = vitals.memory || {};
    var llm = tele.llm || {};

    return `
<div class="dash-header">
  <h2>🌳 LivingTree</h2>
  <span class="dash-sub">v2.3 · ${tele.uptime_seconds ? Math.floor(tele.uptime_seconds/3600)+'h'+(Math.floor(tele.uptime_seconds/60)%60)+'m' : '本地模式'}</span>
</div>
<div class="dash-cards">
  <div class="dash-card"><div class="dash-card-value">${st.totalSessions||0}</div><div class="dash-card-label">会话数</div></div>
  <div class="dash-card"><div class="dash-card-value">${st.totalMessages||0}</div><div class="dash-card-label">总消息</div></div>
  <div class="dash-card"><div class="dash-card-value">${llm.total_calls||0}</div><div class="dash-card-label">LLM 调用</div></div>
  <div class="dash-card"><div class="dash-card-value" style="color:${cpu.percent>80?'var(--accent-coral)':'var(--brand-default)'}">${cpu.percent||'--'}%</div><div class="dash-card-label">CPU</div></div>
</div>
<div class="dash-row">
  <div class="dash-panel">
    <div class="dash-panel-title">📊 系统资源</div>
    <div style="padding:8px;font-size:11px">
      <div style="display:flex;justify-content:space-between;margin:4px 0"><span>CPU</span><span style="color:var(--brand-default)">${cpu.percent||'--'}% · ${cpu.level||''}</span></div>
      <div style="display:flex;justify-content:space-between;margin:4px 0"><span>内存</span><span>${mem.used_gb||'--'}/${mem.total_gb||'--'} GB · ${mem.level||''}</span></div>
      <div style="display:flex;justify-content:space-between;margin:4px 0"><span>磁盘</span><span>${vitals.disk? vitals.disk.free_gb+'GB free' : '--'}</span></div>
      <div style="display:flex;justify-content:space-between;margin:4px 0"><span>LLM 延迟</span><span>${llm.avg_latency_ms? Math.round(llm.avg_latency_ms)+'ms' : '--'}</span></div>
      <div style="display:flex;justify-content:space-between;margin:4px 0"><span>LLM 成本</span><span>¥${llm.total_cost_yuan||'0'}</span></div>
    </div>
  </div>
  <div class="dash-panel">
    <div class="dash-panel-title">🕐 最近活动</div>
    <div class="dash-timeline">
      ${recent.length
        ? recent.map(function(s) { return '<div class="dash-timeline-item"><span class="dash-timeline-time">' + new Date(s.ut).toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit'}) + '</span><span>' + LT.esc(s.title) + '</span></div>'; }).join('')
        : '<div class="dash-timeline-item"><span class="dash-timeline-time">--</span><span>尚无活动记录</span></div>'}
    </div>
  </div>
</div>
<div class="dash-row">
  <div class="dash-panel">
    <div class="dash-panel-title">🧘 AI 意识</div>
    <div style="padding:8px;font-size:11px" id="dash-awareness">加载中...</div>
  </div>
  <div class="dash-panel">
    <div class="dash-panel-title">🌿 绿能调度</div>
    <div style="padding:8px;font-size:11px" id="dash-scheduler">加载中...</div>
  </div>
</div>`;
  }

  render() {
    super.render();
    this._fetchAwareness();
    this._fetchScheduler();
  }

  async _fetchAwareness() {
    var el = document.getElementById('dash-awareness'); if (!el) return;
    try {
      var r = await fetch('/tree/admin/awareness'); if (r.ok) el.innerHTML = await r.text();
    } catch(e) { el.textContent = '不可用'; }
  }

  async _fetchScheduler() {
    var el = document.getElementById('dash-scheduler'); if (!el) return;
    try {
      var r = await fetch('/api/scheduler/status'); if (!r.ok) { el.textContent = '不可用'; return; }
      var d = await r.json();
      el.innerHTML = '<div>模式: <b style="color:var(--brand-default)">' + d.mode.toUpperCase() + '</b></div>' +
        '<div>待处理: <b>' + d.deferred_count + '</b></div>' +
        '<div style="font-size:10px;color:var(--text-secondary)">' + d.metaphor + '</div>';
    } catch(e) { el.textContent = '不可用'; }
  }
}
LT.register('dashboard', Dashboard);
