/* LivingTree Web — Sidebar Component */

class Sidebar extends Component {
  constructor(el, props = {}) {
    super(el, props);
    this._searchTerm = '';
    this._bound = false;
  }

  get store() {
    return LT.store;
  }

  template() {
    const store = this.store;
    if (!store) {
      return `<div class="sidebar-body"><div class="empty-state"><div class="empty-state-icon">🌳</div><div class="empty-state-text">存储未就绪</div></div></div>`;
    }

    const sessions = store.search(this._searchTerm || '');
    const activeId = store.activeId;

    const sessionItems = sessions.length
      ? sessions.map(s => {
          const isActive = s.id === activeId;
          const id = LT.esc(s.id);
          const title = LT.esc(s.title);
          return `
            <div class="session-item${isActive ? ' active' : ''}" data-action="switch" data-id="${id}">
              <svg class="sess-icon" width="16" height="16" viewBox="0 0 16 16">
                <path d="M2 3h12a1 1 0 011 1v8a1 1 0 01-1 1H2a1 1 0 01-1-1V4a1 1 0 011-1z" fill="none" stroke="currentColor" stroke-width="1.3"/>
                <path d="M5 7h6M5 10h3" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
              </svg>
              <span class="sess-title">${title}</span>
              <span class="sess-actions">
                <button data-action="rename" data-id="${id}" title="重命名">
                  <svg width="12" height="12" viewBox="0 0 12 12"><path d="M8.5 1.5l2 2-7 7H1.5v-2l7-7z" fill="none" stroke="currentColor" stroke-width="1.2"/></svg>
                </button>
                <button data-action="export" data-id="${id}" title="导出">
                  <svg width="12" height="12" viewBox="0 0 12 12"><path d="M6 1v7M3 5l3 3 3-3M1.5 9.5v1a1 1 0 001 1h7a1 1 0 001-1v-1" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/></svg>
                </button>
                <button data-action="delete" data-id="${id}" title="删除">
                  <svg width="12" height="12" viewBox="0 0 12 12"><path d="M2.5 3.5h7M5 3.5V2.5a.5.5 0 01.5-.5h1a.5.5 0 01.5.5v1M4.5 5.5v4M7.5 5.5v4M3 3.5l.5 7h5l.5-7" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/></svg>
                </button>
              </span>
            </div>`;
        }).join('')
      : `<div class="empty-state"><div class="empty-state-icon">💬</div><div class="empty-state-text">${this._searchTerm ? '无匹配' : '暂无会话'}</div></div>`;

    return `
      <div class="sidebar-header">
        <div class="sidebar-logo">
          <svg width="20" height="20" viewBox="0 0 20 20" style="flex-shrink:0">
            <ellipse cx="10" cy="7" rx="7" ry="6.5" fill="none" stroke="currentColor" stroke-width="1.2"/>
            <ellipse cx="8" cy="10" rx="2.5" ry="3" fill="var(--brand-default)" opacity="0.3"/>
            <ellipse cx="12" cy="10" rx="2.5" ry="3" fill="var(--brand-default)" opacity="0.3"/>
            <circle cx="8.7" cy="10" r="1.3" fill="var(--bg-base)"/>
            <circle cx="12.7" cy="10" r="1.3" fill="var(--bg-base)"/>
            <path d="M9 17c0 1.5 2 2.5 2 0" fill="none" stroke="currentColor" stroke-width="1"/>
            <text x="10" y="9" text-anchor="middle" font-size="8" fill="var(--text)" font-weight="700">树</text>
          </svg>
          <span>LivingTree</span>
        </div>
        <button class="sidebar-collapse-btn" data-action="collapse" title="折叠侧栏">
          <svg width="16" height="16" viewBox="0 0 16 16">
            <path d="M10 3L5 8l5 5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M13 3v10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
        </button>
      </div>
      <div class="sidebar-search">
        <input type="text" id="session-search" placeholder="搜索会话..." value="${LT.esc(this._searchTerm)}" data-action="search">
      </div>
      <div class="sidebar-actions">
        <button class="btn-new-session" data-action="new-session">
          <svg width="14" height="14" viewBox="0 0 14 14">
            <path d="M7 2v10M2 7h10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
          <span>新建会话</span>
        </button>
      </div>
      <div class="sidebar-sessions">${sessionItems}</div>
      <div class="sidebar-footer-actions">
        <button class="btn-settings" data-action="open-models" title="模型选举">
          <svg width="14" height="14" viewBox="0 0 14 14"><rect x="1" y="3" width="5" height="8" rx="1" fill="none" stroke="currentColor" stroke-width="1.3"/><rect x="8" y="1" width="5" height="10" rx="1" fill="none" stroke="currentColor" stroke-width="1.3"/></svg>
          <span>模型选举</span>
        </button>
        <button class="btn-settings" data-action="open-creative" title="创意可视化">
          <svg width="14" height="14" viewBox="0 0 14 14"><circle cx="7" cy="7" r="5" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M7 2v3M7 9v3M2 7h3M9 7h3M3.5 3.5l2 2M8.5 8.5l2 2M3.5 10.5l2-2M8.5 5.5l2-2" stroke="currentColor" stroke-width="0.8" stroke-linecap="round"/></svg>
          <span>创意可视化</span>
        </button>
        <div style="display:flex;gap:4px">
          <button class="btn-settings" style="flex:1;justify-content:center" data-action="open-admin" title="管理员">
            <svg width="14" height="14" viewBox="0 0 14 14"><circle cx="7" cy="5" r="2" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M3 12c0-2.2 1.8-4 4-4s4 1.8 4 4" fill="none" stroke="currentColor" stroke-width="1.3"/></svg>
          </button>
          <button class="btn-settings" style="flex:1;justify-content:center" data-action="open-mobile" title="移动端">
            <svg width="14" height="14" viewBox="0 0 14 14"><rect x="3.5" y="1.5" width="7" height="11" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.3"/><line x1="6" y1="10.5" x2="8" y2="10.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/></svg>
          </button>
          <button class="btn-settings" style="flex:1;justify-content:center" data-action="toggle-theme" title="切换主题">
            <svg width="14" height="14" viewBox="0 0 14 14"><circle cx="7" cy="7" r="4" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M7 1v1.5M7 11.5v1.5M1 7h1.5M11.5 7H13M2.8 2.8l1 1M10.2 10.2l1 1M2.8 11.2l1-1M10.2 3.8l1-1" stroke="currentColor" stroke-width="1" stroke-linecap="round"/></svg>
          </button>
        </div>
        <div style="padding:4px 10px;font-size:10px;color:var(--text-secondary);display:flex;align-items:center;gap:6px" id="sidebar-nodes">
          <span style="width:6px;height:6px;border-radius:50%;background:var(--brand-default);display:inline-block"></span>
          <span>单机模式</span>
        </div>
      </div>
      <div class="sidebar-user" data-action="user-menu">
        <div class="sidebar-user-avatar">L</div>
        <div class="sidebar-user-info">
          <div class="sidebar-user-name">本地用户</div>
          <div class="sidebar-user-plan">Free</div>
        </div>
        <div class="sidebar-user-chevron">
          <svg width="12" height="12" viewBox="0 0 12 12"><path d="M3 4.5l3 3 3-3" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>
        </div>
      </div>
    `;
  }

  init() {
    super.init();
    this._bindEvents();
  }

  render() {
    if (this.el) {
      const wasFocused = document.activeElement && this.el.contains(document.activeElement);
      const activeData = wasFocused ? document.activeElement.dataset : null;
      this.el.innerHTML = this.template();
      if (wasFocused && activeData && activeData.action === 'search') {
        const input = this.el.querySelector('[data-action="search"]');
        if (input) input.focus();
      }
    }
  }

  _bindEvents() {
    if (this._bound) return;
    this._bound = true;

    this.el.addEventListener('click', (e) => {
      const target = e.target.closest('[data-action]');
      if (!target) return;
      const action = target.dataset.action;
      const id = target.dataset.id;

      switch (action) {
        case 'switch':
          if (id) this._switchSession(id);
          break;
        case 'rename':
          e.stopPropagation();
          if (id) this._renameSession(id);
          break;
        case 'export':
          e.stopPropagation();
          if (id) this._exportSession(id);
          break;
        case 'delete':
          e.stopPropagation();
          if (id) this._deleteSession(id);
          break;
        case 'collapse':
          this._toggleCollapse();
          break;
        case 'user-menu':
          LT.emit('settings:open');
          break;
        case 'new-session':
          this._newSession();
          break;
        case 'open-models':
          this.emit('models:open');
          break;
        case 'open-admin':
          window.open('/tree/admin', '_blank');
          break;
        case 'open-mobile':
          window.open('/tree/reach/mobile', '_blank');
          break;
        case 'toggle-theme':
          var html = document.documentElement;
          var cur = html.getAttribute('data-theme');
          var next = cur === 'dark' ? 'light' : 'dark';
          html.setAttribute('data-theme', next);
          if (LT.store) LT.store.theme = next;
          break;
        case 'open-creative':
          this.emit('creative:open');
          break;
      }
    });

    this.el.addEventListener('input', (e) => {
      const target = e.target.closest('[data-action]');
      if (!target || target.dataset.action !== 'search') return;
      this._searchTerm = target.value;
      this.render();
    });
  }

  _switchSession(id) {
    const store = this.store;
    if (!store) return;
    store.activeId = id;
    store.save();
    this.emit('session:switch', id);
    this.render();
  }

  _newSession() {
    const store = this.store;
    if (!store) return;
    store.create();
    this.render();
  }

  _deleteSession(id) {
    const store = this.store;
    if (!store || !confirm('确定删除此会话？')) return;
    store.remove(id);
    this.render();
  }

  _renameSession(id) {
    const store = this.store;
    if (!store) return;
    const session = store.sessions.find(s => s.id === id);
    if (!session) return;
    const title = prompt('重命名会话:', session.title);
    if (title && title.trim()) {
      store.rename(id, title.trim());
      this.render();
    }
  }

  _exportSession(id) {
    const store = this.store;
    if (!store) return;
    store.export(id);
  }

  _toggleCollapse() {
    this.el.classList.toggle('collapsed');
  }
}

if (!LT.store && typeof S !== 'undefined') {
  LT.store = S;
}

LT.register('sidebar', Sidebar);
