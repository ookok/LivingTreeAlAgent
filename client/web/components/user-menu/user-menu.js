class UserMenu extends Component {
  constructor() {
    super('user-dropdown');
    this._visible = false;
    this.on('user-menu:toggle', () => this._toggle());
    document.addEventListener('click', (e) => {
      if (this._visible && !this.el.contains(e.target)) {
        const su = LT.ge('sidebar-user');
        if (su && !su.contains(e.target)) this._hide();
      }
    });
  }

  _toggle() {
    this._visible ? this._hide() : this._show();
  }

  _show() {
    const su = LT.ge('sidebar-user');
    if (su) {
      const rect = su.getBoundingClientRect();
      this.el.style.left = rect.left + 'px';
      this.el.style.bottom = (window.innerHeight - rect.top + 8) + 'px';
      su.classList.add('open');
    }
    this.el.style.display = 'block';
    this._visible = true;
  }

  _hide() {
    this.el.style.display = 'none';
    const su = LT.ge('sidebar-user');
    if (su) su.classList.remove('open');
    this._visible = false;
  }

  template() {
    return `
<div class="user-dropdown-header">
  <div class="sidebar-user-avatar" style="width:36px;height:36px;font-size:14px">L</div>
  <div>
    <div style="font-weight:var(--font-weight-medium)">本地用户</div>
    <div style="font-size:var(--font-size-xs);color:var(--text-tertiary);margin-top:2px">Local Mode · Free</div>
  </div>
</div>
<div class="user-dropdown-divider"></div>
<div class="user-dropdown-item" data-action="theme">
  <svg width="14" height="14" viewBox="0 0 14 14"><circle cx="7" cy="7" r="3" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M7 1v1M7 12v1M1 7h1M12 7h1M2.5 2.5l.7.7M10.8 10.8l.7.7M2.5 11.5l.7-.7M10.8 3.2l.7-.7" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/></svg>
  <span>切换主题</span>
</div>
<div class="user-dropdown-item" data-action="settings">
  <svg width="14" height="14" viewBox="0 0 14 14"><circle cx="7" cy="7" r="2.5" fill="none" stroke="currentColor" stroke-width="1.2"/><path d="M7 1v1.5M7 11.5V13M1 7h1.5M11.5 7H13M2.5 2.5l1 1M10.5 10.5l1 1M2.5 11.5l1-1M10.5 3.5l1-1" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/></svg>
  <span>设置</span>
</div>
<div class="user-dropdown-item" data-action="shortcuts">
  <svg width="14" height="14" viewBox="0 0 14 14"><rect x="1" y="3" width="12" height="8" rx="1" fill="none" stroke="currentColor" stroke-width="1.3"/><line x1="4.5" y1="4" x2="4.5" y2="10" stroke="currentColor" stroke-width="0.8"/><line x1="6" y1="6" x2="8" y2="6" stroke="currentColor" stroke-width="0.8"/></svg>
  <span>快捷键</span>
  <span class="user-dropdown-shortcut">Ctrl+K</span>
</div>
<div class="user-dropdown-divider"></div>
<div class="user-dropdown-item" data-action="export">
  <svg width="14" height="14" viewBox="0 0 14 14"><path d="M6 1v7M3 5l3 3 3-3M1.5 9.5v1a1 1 0 001 1h7a1 1 0 001-1v-1" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/></svg>
  <span>导出全部会话</span>
</div>
<div class="user-dropdown-item danger" data-action="clear">
  <svg width="14" height="14" viewBox="0 0 14 14"><path d="M2.5 3.5h9M5.5 3V2a.5.5 0 01.5-.5h2a.5.5 0 01.5.5v1M4.5 5.5v6M9.5 5.5v6M2.5 3.5l.5 8.5h8l.5-8.5" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/></svg>
  <span>清除全部数据</span>
</div>`;
  }

  render() {
    super.render();
    const E = this.el;
    LT.qs('[data-action="theme"]', E).onclick = () => { S.toggleTheme(); this._hide(); };
    LT.qs('[data-action="settings"]', E).onclick = () => { this._hide(); LT.emit('settings:open'); };
    LT.qs('[data-action="shortcuts"]', E).onclick = () => {
      this._hide();
      LT.emit('notify', { msg: '快捷键: Ctrl+K 聚焦输入, Ctrl+B 切换侧栏', type: 'info' });
    };
    LT.qs('[data-action="export"]', E).onclick = () => {
      this._hide();
      S.sessions.forEach(s => S.export(s.id));
      LT.emit('notify', { msg: '全部会话已导出', type: 'success' });
    };
    LT.qs('[data-action="clear"]', E).onclick = () => {
      this._hide();
      if (!confirm('确定清除所有本地数据？此操作不可撤销。')) return;
      S.sessions = []; S.messages = {}; S.activeId = null; S.save();
      LT.emit('notify', { msg: '数据已清除', type: 'success' });
    };
  }
}
LT.register('user-menu', new UserMenu());
