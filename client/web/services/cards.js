/* ═══════════════════════════════════
   LivingTree — Interactive Message Cards
   Human-in-the-loop collaboration via rich card UI
   ═══════════════════════════════════ */

const Cards = {
  _cardId: 0,

  /* ── Card type registry ── */
  types: {
    location: { icon: '📍', label: '位置采集', color: '#3f85ff' },
    approval: { icon: '✅', label: '审批确认', color: '#0fdc78' },
    photo:    { icon: '📸', label: '现场拍照', color: '#e28a00' },
    form:     { icon: '📝', label: '信息采集', color: '#9570ff' },
    checklist:{ icon: '☑️', label: '检查清单', color: '#00b8f8' },
    signature:{ icon: '✍️', label: '电子签名', color: '#d1469e' },
    rating:   { icon: '⭐', label: '评价打分', color: '#e28a00' },
    qrscan:   { icon: '📱', label: '扫码确认', color: '#0fdc78' },
    timer:    { icon: '⏱️', label: '计时提醒', color: '#f65a5a' },
  },

  /* ── Generate card ID ── */
  uid() { return 'card_' + Date.now().toString(36) + '_' + (++this._cardId).toString(36); },

  /* ── Create a card data object ── */
  create(type, config) {
    return {
      id: this.uid(),
      type,
      title: config.title || this.types[type]?.label || 'Card',
      description: config.description || '',
      config: config.config || {},
      status: 'pending',  // pending | completed | expired
      response: null,
      createdAt: Date.now(),
      shared: false,
      shareUrl: '',
    };
  },

  /* ── Parse cards from message content ── */
  parseFromContent(content) {
    const cards = [];
    const re = /\[card:(\w+)\]([\s\S]*?)\[\/card\]/g;
    let m;
    while ((m = re.exec(content)) !== null) {
      const type = m[1];
      let inner = m[2].trim();
      const card = { id: this.uid(), type, title: '', description: '', config: {}, status: 'pending', response: null };

      // Parse inner YAML-like fields
      inner.split('\n').forEach(line => {
        const kv = line.match(/^(\w+):\s*(.+)/);
        if (kv) {
          const key = kv[1], val = kv[2].trim();
          if (key === 'title') card.title = val;
          else if (key === 'desc') card.description = val;
          else if (key === 'require_gps') card.config.requireGPS = val === 'true';
          else if (key === 'require_photo') card.config.requirePhoto = val === 'true';
          else if (key === 'items') card.config.items = val.split(',').map(s => s.trim());
          else if (key === 'fields') card.config.fields = val.split(',').map(s => s.trim());
          else if (key === 'deadline') card.config.deadline = val;
          else card.config[key] = val;
        }
      });

      cards.push(card);
    }
    return cards;
  },

  /* ── Render a single card as HTML ── */
  render(card) {
    const t = this.types[card.type] || { icon: '📋', label: card.type, color: '#888' };
    const statusBadge = card.status === 'completed'
      ? '<span class="card-badge done">✓ 已完成</span>'
      : card.status === 'expired'
        ? '<span class="card-badge expired">⏰ 已过期</span>'
        : '<span class="card-badge pending">待处理</span>';

    const body = this['_render_' + card.type] ? this['_render_' + card.type](card) : this._render_generic(card);

    return `
<div class="card ${card.type}" data-card-id="${card.id}" data-card-type="${card.type}" data-card-status="${card.status}">
  <div class="card-header">
    <span class="card-icon">${t.icon}</span>
    <span class="card-title">${LT.esc(card.title || t.label)}</span>
    ${statusBadge}
  </div>
  ${card.description ? `<div class="card-desc">${LT.esc(card.description)}</div>` : ''}
  <div class="card-body">${body}</div>
  ${card.response && card.status === 'completed' ? this._render_response(card) : ''}
  ${card.status === 'pending' ? this._render_share(card) : ''}
</div>`;
  },

  /* ── Card type renderers ── */

  _render_location(card) {
    return `
<div class="card-map-container">
  <div class="card-map" id="map-${card.id}" style="height:200px;background:var(--bg-overlay-l1);border-radius:var(--radius-6);display:flex;align-items:center;justify-content:center;color:var(--text-tertiary);font-size:var(--font-size-sm)">
    <div style="text-align:center">🗺️<br>点击获取位置</div>
  </div>
</div>
<div class="card-actions">
  <button class="card-btn card-btn-primary" data-action="get-location">
    <svg width="14" height="14" viewBox="0 0 14 14"><circle cx="7" cy="7" r="3" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M7 1v2M7 11v2M1 7h2M11 7h2" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/></svg>
    <span>获取当前定位</span>
  </button>
  <button class="card-btn" data-action="pick-location" style="flex:1">
    <svg width="14" height="14" viewBox="0 0 14 14"><circle cx="7" cy="5" r="3" fill="currentColor"/><path d="M7 8v6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
    <span>地图选点</span>
  </button>
</div>`;
  },

  _render_approval(card) {
    return `
<div class="card-approval-msg">${LT.esc(card.config.message || '请确认以上内容')}</div>
<div class="card-actions card-actions-dual">
  <button class="card-btn card-btn-approve" data-action="approve">
    <svg width="16" height="16" viewBox="0 0 16 16"><path d="M3 8l3 3 7-7" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/></svg>
    <span>同意</span>
  </button>
  <button class="card-btn card-btn-reject" data-action="reject">
    <svg width="16" height="16" viewBox="0 0 16 16"><path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/></svg>
    <span>驳回</span>
  </button>
</div>
<textarea class="card-comment" data-card-comment placeholder="审批意见（可选）..." rows="2" style="display:none"></textarea>`;
  },

  _render_photo(card) {
    return `
<div class="card-photo-area" id="photo-${card.id}">
  <button class="card-photo-btn" data-action="take-photo">
    <svg width="24" height="24" viewBox="0 0 24 24"><rect x="3" y="6" width="18" height="14" rx="3" fill="none" stroke="currentColor" stroke-width="1.5"/><circle cx="12" cy="13" r="3.5" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M8 4h8l2 2h3v2" stroke="currentColor" stroke-width="1.5" fill="none"/></svg>
    <span>拍照上传</span>
  </button>
  <input type="file" accept="image/*" capture="environment" data-action="photo-upload" style="display:none">
  <div class="card-photo-preview"></div>
</div>`;
  },

  _render_form(card) {
    const fields = card.config.fields || ['姓名', '电话', '备注'];
    return fields.map(f => `
<div class="form-group" style="margin-bottom:8px">
  <label class="form-label">${LT.esc(f)}</label>
  <input type="text" class="form-input" data-card-field="${f}" placeholder="请输入${f}">
</div>`).join('') + `
<button class="card-btn card-btn-primary" data-action="submit-form" style="width:100%;margin-top:8px">
  <span>提交</span>
</button>`;
  },

  _render_checklist(card) {
    const items = card.config.items || ['项目1', '项目2', '项目3'];
    return items.map((item, i) => `
<label class="card-check-item">
  <input type="checkbox" data-card-check="${i}" ${card.config.checked?.[i] ? 'checked' : ''}>
  <span>${LT.esc(item)}</span>
</label>`).join('') + `
<button class="card-btn card-btn-primary" data-action="submit-checklist" style="width:100%;margin-top:8px">
  <span>确认完成</span>
</button>`;
  },

  _render_signature(card) {
    return `
<div class="card-sig-area">
  <canvas class="card-sig-canvas" id="sig-${card.id}" width="280" height="120"></canvas>
</div>
<div class="card-actions">
  <button class="card-btn" data-action="clear-sig">清除</button>
  <button class="card-btn card-btn-primary" data-action="submit-sig">确认签名</button>
</div>`;
  },

  _render_rating(card) {
    const max = card.config.max || 5;
    let stars = '';
    for (let i = 1; i <= max; i++) stars += `<span class="card-star" data-star="${i}">☆</span>`;
    return `<div class="card-rating" data-card-rating>${stars}</div>
<button class="card-btn card-btn-primary" data-action="submit-rating" style="width:100%;margin-top:8px">提交评分</button>`;
  },

  _render_qrscan(card) {
    return `
<div class="card-qr-area" id="qr-${card.id}">
  <button class="card-photo-btn" data-action="scan-qr">
    <svg width="24" height="24" viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1" fill="none" stroke="currentColor" stroke-width="1.5"/><rect x="14" y="3" width="7" height="7" rx="1" fill="none" stroke="currentColor" stroke-width="1.5"/><rect x="3" y="14" width="7" height="7" rx="1" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M14 14h4v4M14 16v2h2" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round"/></svg>
    <span>扫码确认</span>
  </button>
</div>`;
  },

  _render_timer(card) {
    const mins = card.config.minutes || 5;
    return `
<div class="card-timer">
  <div class="card-timer-display" id="timer-${card.id}">${String(mins).padStart(2, '0')}:00</div>
  <div class="card-actions" style="margin-top:8px">
    <button class="card-btn card-btn-primary" data-action="start-timer" style="flex:1">开始计时</button>
    <button class="card-btn" data-action="stop-timer" style="flex:1">停止</button>
  </div>
</div>`;
  },

  _render_generic(card) {
    return `<p class="card-generic">${LT.esc(card.description || '待处理的任务卡片')}</p>
<button class="card-btn card-btn-primary" data-action="complete" style="width:100%">标记完成</button>`;
  },

  _render_response(card) {
    const r = card.response;
    if (r.type === 'location') return `<div class="card-result">📍 ${r.lat}, ${r.lng} — ${r.time}</div>`;
    if (r.type === 'approval') return `<div class="card-result ${r.decision}">${r.decision === 'approved' ? '✅ 已同意' : '❌ 已驳回'}${r.comment ? ': ' + r.comment : ''}</div>`;
    if (r.type === 'photo') return `<div class="card-result">📸 已拍照 — <a href="${r.url}" target="_blank">查看</a></div>`;
    if (r.type === 'form') return `<div class="card-result">📝 ${JSON.stringify(r.data)}</div>`;
    if (r.type === 'checklist') return `<div class="card-result">☑️ ${r.checked}/${r.total} 项完成</div>`;
    if (r.type === 'rating') return `<div class="card-result">⭐ ${r.score}/${r.max} 分</div>`;
    return `<div class="card-result">✓ 已完成</div>`;
  },

  _render_share(card) {
    return `
<div class="card-share">
  <button class="card-share-btn" data-action="share-card" data-card-id="${card.id}">
    <svg width="12" height="12" viewBox="0 0 12 12"><circle cx="8" cy="3" r="1.5" fill="none" stroke="currentColor" stroke-width="1.2"/><circle cx="8" cy="9" r="1.5" fill="none" stroke="currentColor" stroke-width="1.2"/><circle cx="4" cy="6" r="1.5" fill="none" stroke="currentColor" stroke-width="1.2"/><path d="M6.5 4L5.5 5.5M6.5 8L5.5 6.5" stroke="currentColor" stroke-width="1" stroke-linecap="round"/></svg>
    <span>分享给同事协助</span>
  </button>
</div>`;
  },

  /* ── Handle card action ── */
  handleAction(cardEl, action) {
    const cardId = cardEl.dataset.cardId;
    const cardType = cardEl.dataset.cardType;

    switch (action) {
      case 'get-location':
        this._doGetLocation(cardEl, cardId); break;
      case 'approve':
        this._doApprove(cardEl, cardId, true); break;
      case 'reject':
        this._doApprove(cardEl, cardId, false); break;
      case 'take-photo':
        this._doTakePhoto(cardEl); break;
      case 'submit-form':
        this._doSubmitForm(cardEl, cardId); break;
      case 'submit-checklist':
        this._doSubmitChecklist(cardEl, cardId); break;
      case 'submit-rating':
        this._doSubmitRating(cardEl, cardId); break;
      case 'complete':
        this._markComplete(cardEl, cardId); break;
      case 'share-card':
        this._shareCard(cardEl, cardId); break;
      case 'start-timer':
        this._startTimer(cardEl, cardId); break;
      case 'stop-timer':
        this._stopTimer(cardEl, cardId); break;
      case 'clear-sig':
        this._clearSignature(cardEl); break;
      case 'submit-sig':
        this._submitSignature(cardEl, cardId); break;
      case 'scan-qr':
        this._scanQR(cardEl); break;
    }
  },

  /* ── Location ── */
  _doGetLocation(cardEl, cardId) {
    if (!navigator.geolocation) {
      LT.emit('notify', { msg: '浏览器不支持定位', type: 'error' }); return;
    }
    navigator.geolocation.getCurrentPosition(pos => {
      const { latitude: lat, longitude: lng } = pos.coords;
      this._updateCard(cardEl, cardId, {
        status: 'completed',
        response: { type: 'location', lat: lat.toFixed(6), lng: lng.toFixed(6), time: new Date().toLocaleString('zh-CN') },
      });
      LT.emit('notify', { msg: `定位成功: ${lat.toFixed(4)}, ${lng.toFixed(4)}`, type: 'success' });
    }, () => {
      LT.emit('notify', { msg: '定位失败，请检查权限', type: 'error' });
    }, { enableHighAccuracy: true, timeout: 10000 });
  },

  /* ── Approval ── */
  _doApprove(cardEl, cardId, approved) {
    const commentEl = cardEl.querySelector('[data-card-comment]');
    const comment = commentEl ? commentEl.value : '';
    this._updateCard(cardEl, cardId, {
      status: 'completed',
      response: { type: 'approval', decision: approved ? 'approved' : 'rejected', comment },
    });
    LT.emit('notify', { msg: approved ? '已同意' : '已驳回', type: 'success' });
  },

  /* ── Photo ── */
  _doTakePhoto(cardEl) {
    const input = cardEl.querySelector('[data-action="photo-upload"]');
    if (input) input.click();
    if (input) {
      input.onchange = (e) => {
        const file = e.target.files[0];
        if (file) {
          const reader = new FileReader();
          reader.onload = (ev) => {
            const preview = cardEl.querySelector('.card-photo-preview');
            if (preview) preview.innerHTML = `<img src="${ev.target.result}" style="max-width:100%;border-radius:6px;margin-top:8px">`;
            this._updateCard(cardEl, cardEl.dataset.cardId, {
              status: 'completed', response: { type: 'photo', url: ev.target.result },
            });
          };
          reader.readAsDataURL(file);
        }
      };
    }
  },

  /* ── Form ── */
  _doSubmitForm(cardEl, cardId) {
    const data = {};
    cardEl.querySelectorAll('[data-card-field]').forEach(el => {
      data[el.dataset.cardField] = el.value;
    });
    this._updateCard(cardEl, cardId, {
      status: 'completed', response: { type: 'form', data },
    });
    LT.emit('notify', { msg: '表单已提交', type: 'success' });
  },

  /* ── Checklist ── */
  _doSubmitChecklist(cardEl, cardId) {
    const checks = cardEl.querySelectorAll('[data-card-check]');
    let checked = 0;
    const states = [];
    checks.forEach(cb => { states.push(cb.checked); if (cb.checked) checked++; });
    this._updateCard(cardEl, cardId, {
      config: { ...{}, checked: states },
      status: checked === checks.length ? 'completed' : 'pending',
      response: { type: 'checklist', checked, total: checks.length },
    });
  },

  /* ── Rating ── */
  _doSubmitRating(cardEl, cardId) {
    const active = cardEl.querySelector('.card-star.active');
    const score = active ? parseInt(active.dataset.star) : 0;
    const max = cardEl.querySelectorAll('.card-star').length;
    this._updateCard(cardEl, cardId, {
      status: 'completed', response: { type: 'rating', score, max },
    });
  },

  /* ── Signature ── */
  _clearSignature(cardEl) {
    const canvas = cardEl.querySelector('canvas');
    if (canvas) {
      const ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
  },
  _submitSignature(cardEl, cardId) {
    const canvas = cardEl.querySelector('canvas');
    const url = canvas ? canvas.toDataURL() : '';
    this._updateCard(cardEl, cardId, {
      status: 'completed', response: { type: 'signature', url },
    });
  },

  /* ── QR Scan ── */
  _scanQR(cardEl) {
    LT.emit('notify', { msg: '请用手机扫码（功能开发中）', type: 'info' });
  },

  /* ── Timer ── */
  _startTimer(cardEl, cardId) {
    const display = cardEl.querySelector('.card-timer-display');
    if (!display) return;
    let [m, s] = display.textContent.split(':').map(Number);
    let total = m * 60 + s;
    const interval = setInterval(() => {
      total--;
      if (total <= 0) { clearInterval(interval); this._updateCard(cardEl, cardId, { status: 'completed' }); return; }
      display.textContent = `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
    }, 1000);
    cardEl._timerInterval = interval;
  },
  _stopTimer(cardEl) {
    if (cardEl._timerInterval) { clearInterval(cardEl._timerInterval); cardEl._timerInterval = null; }
  },

  /* ── Generic complete ── */
  _markComplete(cardEl, cardId) {
    this._updateCard(cardEl, cardId, { status: 'completed', response: {} });
  },

  /* ── Update card DOM ── */
  _updateCard(cardEl, cardId, patch) {
    // Find card data in store and update it
    const store = LT.store;
    if (store && store.activeId) {
      const msgs = store.messages[store.activeId];
      if (msgs) {
        // Walk back to find the message containing this card
        for (let i = msgs.length - 1; i >= 0; i--) {
          if (msgs[i].cards) {
            const card = msgs[i].cards.find(c => c.id === cardId);
            if (card) {
              Object.assign(card, patch);
              store.save();
              break;
            }
          }
        }
      }
    }
    // Re-render the card
    if (cardEl) {
      const cardData = { ...Cards.types[cardEl.dataset.cardType], ...patch, id: cardId, type: cardEl.dataset.cardType };
      cardEl.outerHTML = Cards.render(cardData);
    }
  },

  /* ── Share card as standalone link ── */
  _shareCard(cardEl, cardId) {
    const shareUrl = `${window.location.origin}/card.html?id=${cardId}`;
    if (navigator.clipboard) {
      navigator.clipboard.writeText(shareUrl).then(() => {
        LT.emit('notify', { msg: '卡片链接已复制，发送给同事即可', type: 'success' });
      });
    }
    // Also open share modal
    if (window.Share) {
      Share.open(shareUrl, '协助请求');
    }
  },

  /* ── Wire up card interactions ── */
  wireCard(cardEl) {
    // Approval: show comment on reject
    cardEl.querySelectorAll('[data-action="reject"]').forEach(btn => {
      btn.addEventListener('click', () => {
        const comment = cardEl.querySelector('[data-card-comment]');
        if (comment) comment.style.display = 'block';
      });
    });

    // Rating stars
    cardEl.querySelectorAll('.card-star').forEach(star => {
      star.addEventListener('click', () => {
        const val = parseInt(star.dataset.star);
        cardEl.querySelectorAll('.card-star').forEach((s, i) => {
          s.textContent = i < val ? '★' : '☆';
          s.classList.toggle('active', i < val);
        });
      });
    });

    // Signature canvas
    const sigCanvas = cardEl.querySelector('.card-sig-canvas');
    if (sigCanvas) {
      const ctx = sigCanvas.getContext('2d');
      let drawing = false;
      sigCanvas.addEventListener('mousedown', e => { drawing = true; ctx.beginPath(); ctx.moveTo(e.offsetX, e.offsetY); });
      sigCanvas.addEventListener('mousemove', e => { if (!drawing) return; ctx.lineTo(e.offsetX, e.offsetY); ctx.stroke(); });
      sigCanvas.addEventListener('mouseup', () => { drawing = false; });
      sigCanvas.addEventListener('touchstart', e => {
        e.preventDefault(); drawing = true;
        const t = e.touches[0]; ctx.beginPath(); ctx.moveTo(t.clientX - sigCanvas.getBoundingClientRect().left, t.clientY - sigCanvas.getBoundingClientRect().top);
      });
      sigCanvas.addEventListener('touchmove', e => {
        e.preventDefault(); if (!drawing) return;
        const t = e.touches[0]; ctx.lineTo(t.clientX - sigCanvas.getBoundingClientRect().left, t.clientY - sigCanvas.getBoundingClientRect().top); ctx.stroke();
      });
      sigCanvas.addEventListener('touchend', () => { drawing = false; });
    }

    // Map initialization for location cards
    const mapContainer = cardEl.querySelector('.card-map');
    if (mapContainer && window.leaflet) {
      // Leaflet map would be initialized here if leaflet is loaded
    }
  },
};

window.Cards = Cards;
