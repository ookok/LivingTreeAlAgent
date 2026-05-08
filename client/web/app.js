/* ═══════════════════════════════════
   LivingTree Web — App Bootstrap
   Initializes all components and wires them together
   ═══════════════════════════════════ */

(function() {
  'use strict';

  /* ── Init Store & API ── */
  if (LT.store && LT.store.init) LT.store.init();
  if (LT.store && LT.store.initAutoTheme) LT.store.initAutoTheme();
  if (LT.store && LT.store.requestNotify) LT.store.requestNotify();
  if (!LT.store) console.error('LT.store not available');
  if (!LT.store || !LT.store.stats) {
    LT.store = LT.store || { sessions: [], activeId: null, messages: {}, stats: () => ({ sessions: 0, messages: 0, tokens: 0 }) };
  }

  /* ── Create all components ── */
  const components = [
    { name: 'boot-overlay', el: '#boot-overlay' },
    { name: 'sidebar', el: '#sidebar' },
    { name: 'dashboard', el: '#dashboard' },
    { name: 'chat', el: '#chat-area' },
    { name: 'input', el: '.input-area' },
    { name: 'context-panel', el: '#context-panel' },
    { name: 'settings', el: '#settings-modal' },
    { name: 'doc-reader', el: '#doc-reader-modal' },
    { name: 'notifications', el: '#notifications' },
    { name: 'user-menu', el: '#user-dropdown' },
    { name: 'code-editor', el: '#editor-panel-body' },
    { name: 'doc-studio', el: '#doc-studio' },
    { name: 'graph-studio', el: '#graph-studio' },
    { name: 'diagram-studio', el: '#diagram-studio' },
  ];

  components.forEach(({ name, el }) => {
    const Cls = LT.get(name);
    if (!Cls) { console.warn(`Component "${name}" not registered`); return; }
    const root = typeof el === 'string' ? document.querySelector(el) : el;
    if (!root) { console.warn(`Mount point "${el}" not found for "${name}"`); return; }
    new Cls(root).init();
  });

  /* ── Top-level event wiring ── */
  LT.on('session:switch', id => {
    document.getElementById('topbar-title').textContent = LT.store.active()?.title || 'LivingTree AI Agent';
  });

  /* ── Sidebar toggle ── */
  window.toggleSidebar = () => document.getElementById('sidebar').classList.toggle('collapsed');

  /* ── Right panel toggle ── */
  window.toggleRightPanel = () => {
    const p = document.getElementById('context-panel');
    if (p) p.classList.toggle('open');
  };

  /* ── Code editor panel toggle ── */
  LT.on('code-editor:toggle', () => {
    const panel = document.getElementById('editor-panel');
    if (panel) panel.style.display = panel.style.display === 'flex' ? 'none' : 'flex';
  });

  /* ── Graph studio toggle ── */
  window.toggleGraphStudio = () => {
    const panel = document.getElementById('graph-studio-panel');
    if (panel) panel.style.display = panel.style.display === 'flex' ? 'none' : 'flex';
  };

  /* ── Diagram studio toggle (for report generation) ── */
  window.toggleDiagramStudio = () => {
    const panel = document.getElementById('diagram-studio-panel');
    if (panel) panel.style.display = panel.style.display === 'flex' ? 'none' : 'flex';
  };

  /* ── Listen for diagram insert into OnlyOffice ── */
  LT.on('diagram:insert', (data) => {
    // Forward to doc-studio for insertion into OnlyOffice document
    LT.emit('doc:insert-diagram', data);
  });

  /* ── Theme toggle ── */
  window.toggleTheme = () => LT.store.toggleTheme();

  /* ── Resizer ── */
  (function() {
    const resizer = document.getElementById('resizer');
    const sidebar = document.getElementById('sidebar');
    if (!resizer || !sidebar) return;
    let sx, sw;
    resizer.addEventListener('mousedown', e => {
      sx = e.clientX; sw = sidebar.offsetWidth;
      document.addEventListener('mousemove', mm);
      document.addEventListener('mouseup', mu);
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
    });
    function mm(e) {
      const w = Math.max(200, Math.min(500, sw + e.clientX - sx));
      sidebar.style.minWidth = w + 'px';
      sidebar.style.width = w + 'px';
      document.documentElement.style.setProperty('--sidebar-width', w + 'px');
    }
    function mu() {
      document.removeEventListener('mousemove', mm);
      document.removeEventListener('mouseup', mu);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    }
  })();

  /* ── Keyboard shortcuts ── */
  document.addEventListener('keydown', e => {
    if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      const input = document.getElementById('chat-input');
      if (input) input.focus();
    }
    if (e.key === 'b' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      toggleSidebar();
    }
    if (e.key === '?' && !e.target.closest('input,textarea,[contenteditable]')) {
      e.preventDefault();
      toggleShortcuts();
    }
    if (e.key === 'Escape') {
      const sc = document.getElementById('shortcuts-overlay');
      if (sc && sc.style.display === 'flex') sc.style.display = 'none';
    }
  });

  /* ── Shortcuts panel ── */
  window.toggleShortcuts = () => {
    let sc = document.getElementById('shortcuts-overlay');
    if (!sc) {
      sc = document.createElement('div');
      sc.id = 'shortcuts-overlay';
      sc.className = 'shortcuts-overlay';
      sc.onclick = e => { if (e.target === sc) sc.style.display = 'none'; };
      const shortcuts = [
        ['Ctrl+K','聚焦输入框'],['Ctrl+B','切换侧栏'],['?','显示快捷键'],
        ['Ctrl+滚轮','缩放图表'],['Shift+拖拽','平移画布'],['右键消息','上下文菜单'],
        ['/','命令菜单'],['Enter','发送消息'],['Shift+Enter','换行'],
        ['Ctrl+N','新建会话'],['Ctrl+S','保存文档'],['Esc','关闭面板'],
      ];
      sc.innerHTML = `<div class="shortcuts-panel">
        <div class="shortcuts-header"><span>⌨️ 快捷键</span><button onclick="this.closest('.shortcuts-overlay').style.display='none'">✕</button></div>
        <div class="shortcuts-grid">${shortcuts.map(s => `<div class="shortcuts-row"><kbd>${s[0]}</kbd><span>${s[1]}</span></div>`).join('')}</div>
        <div class="shortcuts-footer">提示: 右键消息可置顶 / 分叉 / 复制</div>
      </div>`;
      document.body.appendChild(sc);
    }
    sc.style.display = sc.style.display === 'flex' ? 'none' : 'flex';
  };

  /* ── Notifications for task completion ── */
  LT.on('review:complete', () => { if (LT.store) LT.store.notify('LivingTree', '文档审阅完成'); });
  LT.on('msg:done', () => { if (LT.store) LT.store.notify('LivingTree', 'AI 回复已完成'); });

  /* ── Context menu (right click on messages) ── */
  let ctxTarget = null, ctxIndex = -1;
  document.addEventListener('contextmenu', e => {
    const msg = e.target.closest('.user-message,.agent-message');
    if (!msg) return;
    e.preventDefault();
    ctxTarget = msg;
    const all = [...msg.parentElement.children];
    ctxIndex = all.indexOf(msg);
    const menu = document.getElementById('ctx-menu');
    if (menu) {
      menu.innerHTML = `
        <div class="ctx-menu-item" onclick="copyMessageText()">📋 复制文本</div>
        <div class="ctx-menu-item" onclick="pinMessageHere()">📌 ${LT.store.pinned[LT.store.activeId]?.has(ctxIndex) ? '取消置顶' : '置顶消息'}</div>
        <div class="ctx-menu-divider"></div>
        <div class="ctx-menu-item" onclick="forkFromHere()">🔀 从此处分叉</div>
        <div class="ctx-menu-item" onclick="replayConversation()">🔄 回放对话</div>
        <div class="ctx-menu-divider"></div>
        <div class="ctx-menu-item danger" onclick="deleteMessageHere()">🗑️ 删除后续</div>
      `;
      menu.style.display = 'block';
      menu.style.left = e.clientX + 'px';
      menu.style.top = e.clientY + 'px';
    }
  });
  document.addEventListener('click', () => {
    const menu = document.getElementById('ctx-menu');
    if (menu) menu.style.display = 'none';
  });

  window.forkFromHere = () => {
    if (ctxIndex < 0 || !LT.store.activeId) return;
    LT.store.fork(LT.store.activeId, ctxIndex);
    LT.emit('session:switch', LT.store.activeId);
    LT.emit('notify', { msg: '会话已分叉', type: 'success' });
  };

  window.copyMessageText = () => {
    if (ctxTarget) {
      const t = ctxTarget.querySelector('.bubble,.content');
      if (t) navigator.clipboard.writeText(t.textContent).then(() =>
        LT.emit('notify', { msg: '已复制', type: 'success' }));
    }
  };

  window.deleteMessageHere = () => {
    if (ctxIndex < 0 || !LT.store.activeId) return;
    LT.store.removeMsgFrom(LT.store.activeId, ctxIndex);
    LT.emit('session:switch', LT.store.activeId);
  };

  window.pinMessageHere = () => {
    if (ctxIndex < 0 || !LT.store.activeId) return;
    LT.emit('msg:pin', { index: ctxIndex });
  };

  window.replayConversation = () => {
    const chat = LT.get('chat');
    if (chat) chat.startReplay();
  };

  /* ── Start polling boot progress ── */
  (function pollBoot() {
    const overlay = document.getElementById('boot-overlay');
    if (!overlay) return;
    const fill = document.getElementById('boot-fill');
    const text = document.getElementById('boot-text');
    (async function loop() {
      for (let i = 0; i < 200; i++) {
        try {
          const r = await fetch('/api/boot/progress');
          const d = await r.json();
          if (fill) fill.style.width = d.pct + '%';
          if (text) text.textContent = d.detail || '';
          if (d.stage === 'ready') {
            await new Promise(r => setTimeout(r, 500));
            overlay.classList.add('hidden');
            setTimeout(() => overlay.remove(), 500);
            LT.emit('dashboard:update');
            LT.emit('ctx:update');
            return;
          }
        } catch (e) {}
        await new Promise(r => setTimeout(r, 500));
      }
      if (overlay.parentNode) overlay.remove();
    })();
  })();

  console.log('🌳 LivingTree Web v2.1 — All components initialized');
})();
