/* LivingTree Web — Chat Component */
class Chat extends Component {
  init() {
    this._unsubs.push(LT.on('session:switch', () => this._loadMessages()));
    this._unsubs.push(LT.on('msg:user', (d) => this._onUserMsg(d.content, d.raw)));
    this._unsubs.push(LT.on('msg:typing', () => this._onTyping()));
    this._unsubs.push(LT.on('msg:agent-stream', () => this._onAgentStream()));
    this._unsubs.push(LT.on('msg:chunk', (d) => this._onChunk(d.content)));
    this._unsubs.push(LT.on('msg:done', (d) => this._onDone(d.content)));
    this.render();
    this._loadInitial();
    this._setupMsgActions();
  }

  _setupMsgActions() {
    this.el.addEventListener('click', (e) => {
      const btn = e.target.closest('[data-action]');
      if (!btn || !btn.dataset.action) return;
      const msgEl = btn.closest('.message');
      if (!msgEl) return;

      const action = btn.dataset.action;
      if (action === 'copy-text') {
        LT.renderer.copyMsgText(msgEl);
      } else if (action === 'copy-md') {
        LT.renderer.copyMsgMarkdown(msgEl);
      } else if (action === 'share') {
        const raw = LT.renderer._getRaw(msgEl);
        Share.open(raw);
      } else if (action === 'open-in-oo') {
        const raw = LT.renderer._getRaw(msgEl);
        LT.emit('doc:create', { content: raw, title: this._getDocTitle(raw) });
      }
    });
  }

  _getDocTitle(content) {
    const firstLine = (content || '').split('\n')[0].replace(/^#+\s*/, '').trim().slice(0, 50);
    return firstLine || 'AI Generated Document';
  }

  template() {
    return `
      <div class="messages"></div>
      <div class="welcome">
        <div class="dashboard">
          <div class="dash-header"><h2>🌳 LivingTree</h2><span class="dash-sub">数字生命体 v2.1 · 本地模式</span></div>
          <div class="dash-cards">
            <div class="dash-card"><div class="dash-card-value dash-val-sessions">0</div><div class="dash-card-label">会话数</div></div>
            <div class="dash-card"><div class="dash-card-value dash-val-messages">0</div><div class="dash-card-label">总消息</div></div>
            <div class="dash-card"><div class="dash-card-value dash-val-tokens">0</div><div class="dash-card-label">Token 用量</div></div>
            <div class="dash-card"><div class="dash-card-value">4</div><div class="dash-card-label">可用工具</div></div>
          </div>
          <div class="dash-row">
            <div class="dash-panel">
              <div class="dash-panel-title">📊 Token 趋势</div>
              <canvas class="dash-chart" width="400" height="140"></canvas>
            </div>
            <div class="dash-panel">
              <div class="dash-panel-title">🕐 最近活动</div>
              <div class="dash-timeline dash-timeline-list"></div>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  get _msgsEl() { return this.el.querySelector('.messages'); }
  get _welcomeEl() { return this.el.querySelector('.welcome'); }

  _loadInitial() {
    const store = LT.store;
    if (store.activeId && store.getMsgs(store.activeId).length) {
      this._loadMessages();
    } else {
      this._showWelcome();
    }
  }

  _loadMessages() {
    const store = LT.store;
    const msgs = store.getMsgs(store.activeId);
    if (!msgs || !msgs.length) { this._showWelcome(); return; }
    this._showMessages();
    this._msgsEl.innerHTML = '';
    const renderer = LT.renderer;
    msgs.forEach((m) => {
      const role = m.role === 'assistant' ? 'agent' : m.role;
      renderer.append(this._msgsEl, m.role === 'user' ? renderer.userMsg(m.content) : renderer.agentMsg(m.content, false));
      if (role === 'agent') {
        const last = this._msgsEl.querySelector('.message-agent:last-of-type');
        if (last) {
          this._addThinking(last);
          this._addMsgActions(last);
          const blocks = this._detectDocCards(m.content);
          if (blocks.length) this._renderDocCards(last, blocks);
        }
      }
    });
    this._scrollBottom();
  }

  _showWelcome() {
    this._welcomeEl.style.display = 'flex';
    this._msgsEl.style.display = 'none';
    this._updateDashboard();
    this._drawChart();
  }

  _showMessages() {
    this._welcomeEl.style.display = 'none';
    this._msgsEl.style.display = 'flex';
  }

  _onUserMsg(content) {
    this._showMessages();
    LT.renderer.append(this._msgsEl, LT.renderer.userMsg(content));
    this._scrollBottom();
  }

  _onTyping() {
    this._showMessages();
    const div = document.createElement('div');
    div.innerHTML = LT.renderer.typing();
    this._msgsEl.appendChild(div.firstChild);
    this._scrollBottom();
  }

  _onAgentStream() {
    const typing = this._msgsEl.querySelector('.message-agent .typing-indicator');
    if (typing) {
      const msg = typing.closest('.message-agent');
      if (msg) msg.remove();
    }
    LT.renderer.append(this._msgsEl, LT.renderer.agentMsg('', true));
    this._scrollBottom();
  }

  _onChunk(content) {
    LT.renderer.updateStream(this._msgsEl, content);
    this._scrollBottom();
  }

  _onDone(content) {
    LT.renderer.finalize(this._msgsEl);
    // Update data-raw on the final agent message
    const last = this._msgsEl.querySelector('.message-agent:last-of-type');
    if (last) {
      last.setAttribute('data-raw', '`' + LT.renderer.esc(content).replace(/`/g, '\\`') + '`');
      this._addThinking(last);
      this._addMsgActions(last);
      const blocks = this._detectDocCards(content);
      if (blocks.length) this._renderDocCards(last, blocks);
    }
    this._scrollBottom();
  }

  _addMsgActions(msgEl) {
    const bubble = msgEl.querySelector('.agent-bubble');
    if (!bubble) return;
    const actions = LT.renderer.msgActions('agent');
    const el = document.createElement('div');
    el.innerHTML = actions;
    bubble.appendChild(el.firstChild);
  }

  _scrollBottom() {
    requestAnimationFrame(() => {
      this.el.scrollTop = this.el.scrollHeight;
    });
  }

  _addThinking(msgEl) {
    const steps = [
      { icon: '🔍', text: '分析用户意图...' },
      { icon: '📚', text: '检索知识库 (0 条匹配)' },
      { icon: '🧠', text: '生成回复策略' },
      { icon: '✍️', text: '组织回复内容' }
    ];
    const html = `<div class="think-toggle" onclick="this.classList.toggle('open');this.nextElementSibling.classList.toggle('open')"><svg width="10" height="10" viewBox="0 0 10 10"><path d="M3 1l5 4-5 4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>思考过程</div><div class="think-body">${steps.map(s => `<div class="think-step"><span class="think-step-icon">${s.icon}</span><span class="think-step-text">${s.text}</span></div>`).join('')}</div>`;
    const content = msgEl.querySelector('.content');
    if (content) {
      const t = document.createElement('div');
      t.innerHTML = html;
      content.appendChild(t.firstChild);
      content.appendChild(t.firstChild);
    }
  }

  _detectDocCards(content) {
    const blocks = [];
    const re = /```(\w+)\n([\s\S]*?)```/g;
    let m;
    while ((m = re.exec(content)) !== null) {
      const lang = m[1], code = m[2];
      if (code.length > 200 && ['python', 'javascript', 'markdown', 'json', 'yaml', 'html', 'css', 'sql', 'bash', 'text'].includes(lang)) {
        const title = code.split('\n')[0].replace(/^[#\s\/\-]+/, '').trim().slice(0, 50) || `${lang.toUpperCase()} 文档`;
        const preview = code.slice(0, 200).replace(/\n/g, ' ') + '...';
        blocks.push({ title, lang, code, preview, index: m.index });
      }
    }
    return blocks;
  }

  _renderDocCards(msgEl, blocks) {
    if (!blocks.length) return;
    const wrapper = document.createElement('div');
    blocks.forEach((b) => {
      const card = document.createElement('div');
      card.className = 'doc-card';
      card.innerHTML = `<div class="doc-card-header"><span class="doc-card-icon">📄</span><span class="doc-card-title">${LT.esc(b.title)}</span><span class="doc-card-meta"><span class="doc-card-badge">${b.lang}</span></span></div><div class="doc-card-body">${LT.esc(b.preview)}</div><div class="doc-card-actions"><button class="doc-card-btn"><svg width="12" height="12" viewBox="0 0 12 12"><circle cx="6" cy="6" r="1.5" fill="currentColor"/><path d="M1 6a5 5 0 0110 0" fill="none" stroke="currentColor" stroke-width="1.2"/></svg>查看</button><button class="doc-card-btn"><svg width="12" height="12" viewBox="0 0 12 12"><path d="M6 1v7M3 5l3 3 3-3M1.5 9.5v1a1 1 0 001 1h7a1 1 0 001-1v-1" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/></svg>下载</button></div>`;
      card._docData = b;
      wrapper.appendChild(card);
    });
    const content = msgEl.querySelector('.content');
    if (content) content.appendChild(wrapper);
  }

  _updateDashboard() {
    const store = LT.store;
    const st = store.stats();
    const sessionsEl = this._welcomeEl.querySelector('.dash-val-sessions');
    const messagesEl = this._welcomeEl.querySelector('.dash-val-messages');
    const tokensEl = this._welcomeEl.querySelector('.dash-val-tokens');
    if (sessionsEl) sessionsEl.textContent = st.sessions;
    if (messagesEl) messagesEl.textContent = st.messages;
    if (tokensEl) tokensEl.textContent = st.tokens.toLocaleString();

    const timeline = this._welcomeEl.querySelector('.dash-timeline-list');
    if (timeline) {
      timeline.innerHTML = store.sessions.slice(0, 5).map(s =>
        `<div class="dash-timeline-item"><span class="dash-timeline-time">${new Date(s.ut).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}</span><span>${LT.esc(s.title)}</span></div>`
      ).join('') || '<div class="dash-timeline-item"><span class="dash-timeline-time">--</span><span>尚无活动</span></div>';
    }

    this._drawChart(st.tokens);
  }

  _drawChart(tokens) {
    const c = this._welcomeEl.querySelector('.dash-chart');
    if (!c) return;
    const ctx = c.getContext('2d'), W = c.width, H = c.height;
    ctx.clearRect(0, 0, W, H);
    const pts = [tokens * 0.1, tokens * 0.2, tokens * 0.4, tokens * 0.6, tokens * 0.7, tokens * 0.85, tokens];
    const max = Math.max(...pts, 1);
    ctx.beginPath();
    ctx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue('--brand-default').trim();
    ctx.lineWidth = 1.5; ctx.lineJoin = 'round';
    pts.forEach((v, i) => {
      const x = 20 + i * (W - 40) / (pts.length - 1), y = H - 20 - (v / max) * (H - 40);
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.stroke();
    ctx.fillStyle = ctx.strokeStyle + '20';
    ctx.lineTo(W - 20, H - 20); ctx.lineTo(20, H - 20); ctx.closePath(); ctx.fill();
    ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--text-tertiary').trim();
    ctx.font = '9px sans-serif';
    ctx.fillText('0', 2, H - 4);
    ctx.fillText(max.toLocaleString(), 2, 12);
  }
}

LT.register('chat', Chat);
