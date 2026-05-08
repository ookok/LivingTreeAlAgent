/* LivingTree Web — Chat Component */
class Chat extends Component {
  init() {
    this._unsubs.push(LT.on('session:switch', () => this._loadMessages()));
    this._unsubs.push(LT.on('msg:user', (d) => this._onUserMsg(d.content, d.raw)));
    this._unsubs.push(LT.on('msg:typing', () => this._onTyping()));
    this._unsubs.push(LT.on('msg:agent-stream', () => this._onAgentStream()));
    this._unsubs.push(LT.on('msg:chunk', (d) => this._onChunk(d.content)));
    this._unsubs.push(LT.on('msg:done', (d) => this._onDone(d.content)));
    this._unsubs.push(LT.on('review:complete', (d) => this._onReviewComplete(d)));
    this._unsubs.push(LT.on('msg:pin', (d) => this._onPinMsg(d)));
    this.render();
    this._loadInitial();
    this._setupMsgActions();
    this._renderPinned();
  }

  _setupMsgActions() {
    this.el.addEventListener('click', (e) => {
      // Card action buttons
      const cardBtn = e.target.closest('[data-action]');
      if (cardBtn && cardBtn.closest('.card')) {
        const cardEl = cardBtn.closest('.card');
        const action = cardBtn.dataset.action;
        if (action === 'get-location' || action === 'approve' || action === 'reject' ||
            action === 'take-photo' || action === 'submit-form' || action === 'submit-checklist' ||
            action === 'submit-rating' || action === 'complete' || action === 'share-card' ||
            action === 'start-timer' || action === 'stop-timer' || action === 'clear-sig' ||
            action === 'submit-sig' || action === 'scan-qr' || action === 'pick-location') {
          e.preventDefault();
          Cards.handleAction(cardEl, action);
          return;
        }
      }

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

  /* ── Replay mode ── */
  startReplay() {
    if (this._replaying) return;
    this._replaying = true;
    const steps = [
      { icon: '👁️', label: 'SENSE — 接收输入', dur: 300 },
      { icon: '🧠', label: 'THINK — TreeLLM 路由分析', dur: 800 },
      { icon: '📚', label: 'RAG 2.0 — 检索知识库', dur: 600 },
      { icon: '📋', label: 'PLAN — 制定执行计划', dur: 500 },
      { icon: '⚡', label: 'EXEC — 执行中', dur: 1200 },
      { icon: '🔍', label: 'REFLECT — 反思评估', dur: 400 },
      { icon: '✨', label: 'OUTPUT — 输出结果', dur: 300 },
    ];
    const overlay = document.createElement('div');
    overlay.className = 'replay-overlay';
    overlay.innerHTML = `<div class="replay-panel"><div class="replay-header"><span>🔄 对话回放</span><button class="replay-close" onclick="this.closest('.replay-overlay').remove();LT.get('chat')._replaying=false">✕</button></div><div class="replay-timeline" id="replay-timeline"></div></div>`;
    document.body.appendChild(overlay);
    const tl = overlay.querySelector('#replay-timeline');
    let i = 0;
    const show = () => {
      if (i >= steps.length || !this._replaying) { this._replaying = false; setTimeout(() => overlay.remove(), 800); return; }
      const s = steps[i];
      const el = document.createElement('div');
      el.className = 'replay-step active';
      el.innerHTML = `<span class="replay-step-icon">${s.icon}</span><span>${s.label}</span><div class="replay-step-bar"><div class="replay-step-fill" style="animation: replayBar ${s.dur}ms linear"></div></div>`;
      tl.appendChild(el); tl.scrollTop = tl.scrollHeight;
      setTimeout(show, s.dur); i++;
    }; show();
  },

  _renderPinned() {
    const store = LT.store;
    const c = this.el.querySelector('#pinned-msgs');
    if (!c || !store) return;
    const pinned = store.getPinned(store.activeId);
    if (!pinned.length) { c.style.display = 'none'; return; }
    c.style.display = 'block';
    c.innerHTML = pinned.map((m, i) => `<div class="pinned-msg"><span class="pinned-icon">📌</span><span class="pinned-text">${LT.esc((m.content||'').slice(0,60))}</span><button class="pinned-close" onclick="LT.store.togglePin(LT.store.activeId,${i});LT.emit('session:switch')">✕</button></div>`).join('');
  },

  _audioCtx: null,
  _playClick() {
    if (!this._audioCtx) this._audioCtx = new (window.AudioContext||window.webkitAudioContext)();
    const o = this._audioCtx.createOscillator(), g = this._audioCtx.createGain();
    o.connect(g); g.connect(this._audioCtx.destination);
    o.frequency.value = 800; g.gain.value = 0.05;
    o.start(); o.stop(this._audioCtx.currentTime + 0.05);
  },

  _onReviewComplete(data) {
    this._showMessages();
    const review = data.review;
    const sum = review.summary;
    const topIssues = (review.annotations || []).slice(0, 5);
    const sevBadge = (s) => s === 'error' ? '🔴' : s === 'warning' ? '🟡' : '🔵';

    const html = `
<div class="message message-agent">
  <div class="message-bubble agent-bubble">
    <div class="review-summary">
      <div class="review-summary-header">
        <span class="review-summary-icon">📋</span>
        <span class="review-summary-title">AI 文档审阅 — ${LT.esc(data.docTitle || '文档')}</span>
      </div>
      <div class="review-summary-stats">
        <div class="review-stat">
          <div class="review-stat-value" style="color:#e8463a">${sum.by_severity.error || 0}</div>
          <div class="review-stat-label">错误</div>
        </div>
        <div class="review-stat">
          <div class="review-stat-value" style="color:#e28a00">${sum.by_severity.warning || 0}</div>
          <div class="review-stat-label">警告</div>
        </div>
        <div class="review-stat">
          <div class="review-stat-value" style="color:#3f85ff">${sum.by_severity.info || 0}</div>
          <div class="review-stat-label">建议</div>
        </div>
        <div class="review-stat">
          <div class="review-stat-value">${sum.total}</div>
          <div class="review-stat-label">合计</div>
        </div>
      </div>
      <div class="review-summary-list">
        ${topIssues.map(a => `
          <div class="review-summary-item re-sev-${a.severity}">
            ${sevBadge(a.severity)} <strong>${LT.esc(a.message)}</strong>
            ${a.suggestion ? `<div class="re-sug">💡 ${LT.esc(a.suggestion)}</div>` : ''}
          </div>`).join('')}
        ${review.annotations.length > 5 ? `<div class="review-summary-more">... 还有 ${review.annotations.length - 5} 条意见，请在文档编辑器中查看</div>` : ''}
      </div>
      <div class="review-summary-action">
        <button onclick="OnlyOffice.toggleSplit()" class="card-btn card-btn-primary" style="width:100%">
          在 OnlyOffice 中查看详情
        </button>
      </div>
    </div>
  </div>
</div>`;

    LT.renderer.append(this._msgsEl, html);
    this._scrollBottom();
  }

  template() {
    return `
      <div class="pinned-msgs" id="pinned-msgs" style="display:none"></div>
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
          // Render cards from stored card data or parse from content
          if (m.cards && m.cards.length) {
            const cardsHtml = m.cards.map(c => Cards.render(c)).join('');
            const wrapper = document.createElement('div');
            wrapper.className = 'msg-cards';
            wrapper.innerHTML = cardsHtml;
            last.appendChild(wrapper);
            m.cards.forEach((card, i) => {
              const cardEl = wrapper.querySelectorAll('.card')[i];
              if (cardEl) Cards.wireCard(cardEl);
            });
          } else {
            this._addCards(last, m.content);
          }
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
    // Initialize batched streaming
    const lastBubble = this._msgsEl.querySelector('.agent-bubble[data-stream]');
    if (lastBubble) Perf.initStream(lastBubble);
    this._scrollBottom();
  }

  _onChunk(content) {
    // Batched append via Perf — avoids innerHTML on every char
    Perf.appendChunk(content);
    this._scrollBottom();
  }

  _onDone(content) {
    LT.renderer.finalize(this._msgsEl);
    const last = this._msgsEl.querySelector('.message-agent:last-of-type');
    if (last) {
      last.setAttribute('data-raw', '`' + LT.renderer.esc(content).replace(/`/g, '\\`') + '`');
      this._addThinking(last);
      this._addMsgActions(last);
      this._addCards(last, content);
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

  _addCards(msgEl, content) {
    if (!window.Cards) return;
    const cards = Cards.parseFromContent(content);
    if (!cards.length) return;

    // Store cards on the message element
    const store = LT.store;
    if (store && store.activeId) {
      const msgs = store.messages[store.activeId];
      if (msgs && msgs.length) {
        const lastMsg = msgs[msgs.length - 1];
        if (lastMsg && lastMsg.role === 'agent') {
          lastMsg.cards = cards;
          store.save();
        }
      }
    }

    const cardsHtml = cards.map(c => Cards.render(c)).join('');
    const wrapper = document.createElement('div');
    wrapper.className = 'msg-cards';
    wrapper.innerHTML = cardsHtml;
    msgEl.appendChild(wrapper);

    // Wire up card interactions
    cards.forEach((card, i) => {
      const cardEl = wrapper.querySelectorAll('.card')[i];
      if (cardEl) Cards.wireCard(cardEl);
    });
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
