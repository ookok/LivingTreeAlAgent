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
          <svg width="18" height="18" viewBox="0 0 18 18">
            <path d="M9 2l6 4v8l-6 3-6-3V6l6-4z" fill="none" stroke="currentColor" stroke-width="1.3"/>
            <path d="M9 6v6M6 8v4M12 8v4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
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
          this.emit('user-menu:toggle');
          break;
        case 'new-session':
          this._newSession();
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
