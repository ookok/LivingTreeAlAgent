class Dashboard extends Component {
  constructor() { super('dashboard'); this._serverData = null }

  async init() {
    this.render();
    this.on('dashboard:update', () => this.render());
    this._serverData = await LT.api.status().catch(() => null);
    this.render();
  }

  template() {
    const st = LT.store.stats();
    const sd = this._serverData || {};
    const life = sd.life_engine || {};
    const orch = sd.orchestrator || {};
    const cells = sd.cells || {};
    const net = sd.network || {};
    const tools = sd.tools_count || (LT.api._toolsCache ? LT.api._toolsCache.length : 4);
    const recent = LT.store.sessions.slice(0, 5);

    return `
<div class="dash-header">
  <h2>🌳 LivingTree</h2>
  <span class="dash-sub">数字生命体 v2.1 · ${sd.version || '本地模式'} · Gen ${life.generation || 0}</span>
</div>
<div class="dash-cards">
  <div class="dash-card"><div class="dash-card-value">${st.sessions}</div><div class="dash-card-label">会话</div></div>
  <div class="dash-card"><div class="dash-card-value">${st.messages}</div><div class="dash-card-label">消息</div></div>
  <div class="dash-card"><div class="dash-card-value">${st.tokens.toLocaleString()}</div><div class="dash-card-label">Token</div></div>
  <div class="dash-card"><div class="dash-card-value">${tools}</div><div class="dash-card-label">工具</div></div>
</div>
<div class="dash-cards" style="margin-top:0">
  <div class="dash-card"><div class="dash-card-value">${cells.registered || 0}</div><div class="dash-card-label">AI 细胞</div></div>
  <div class="dash-card"><div class="dash-card-value">${orch.total_agents || 0}</div><div class="dash-card-label">智能体</div></div>
  <div class="dash-card"><div class="dash-card-value">${net.peers || 0}</div><div class="dash-card-label">P2P 节点</div></div>
  <div class="dash-card"><div class="dash-card-value">${life.mutations || 0}</div><div class="dash-card-label">进化代数</div></div>
</div>
<div class="dash-row">
  <div class="dash-panel">
    <div class="dash-panel-title">📊 Token 趋势</div>
    <canvas id="dash-chart" width="400" height="140"></canvas>
  </div>
  <div class="dash-panel">
    <div class="dash-panel-title">🕐 最近活动</div>
    <div class="dash-timeline" id="dash-timeline">
      ${recent.length
        ? recent.map(s => `<div class="dash-timeline-item"><span class="dash-timeline-time">${new Date(s.ut).toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit'})}</span><span>${LT.esc(s.title)}</span></div>`).join('')
        : '<div class="dash-timeline-item"><span class="dash-timeline-time">--</span><span>尚无活动</span></div>'}
    </div>
  </div>
</div>`;
  }

  render() {
    super.render();
    requestAnimationFrame(() => this._drawChart());
  }

  _drawChart() {
    const c = LT.ge('dash-chart'); if (!c) return;
    const ctx = c.getContext('2d'), W = c.width, H = c.height;
    const st = LT.store.stats();
    const pts = [st.tokens*.1,st.tokens*.2,st.tokens*.4,st.tokens*.6,st.tokens*.7,st.tokens*.85,st.tokens];
    const max = Math.max(...pts,1); ctx.clearRect(0,0,W,H); ctx.beginPath();
    ctx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue('--brand-default').trim();
    ctx.lineWidth=1.5; ctx.lineJoin='round';
    pts.forEach((v,i)=>{const x=20+i*(W-40)/(pts.length-1),y=H-20-(v/max)*(H-40);i===0?ctx.moveTo(x,y):ctx.lineTo(x,y)});
    ctx.stroke(); ctx.fillStyle=ctx.strokeStyle+'20'; ctx.lineTo(W-20,H-20);ctx.lineTo(20,H-20);ctx.closePath();ctx.fill();
    ctx.fillStyle=getComputedStyle(document.documentElement).getPropertyValue('--text-tertiary').trim();
    ctx.font='9px sans-serif';ctx.fillText('0',2,H-4);ctx.fillText(max.toLocaleString(),2,12);
  }
}
LT.register('dashboard', Dashboard);
