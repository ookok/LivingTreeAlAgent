/* ═══════════════════════════════════
   LivingTree Web — App Bootstrap
   Initializes all components and wires them together
   ═══════════════════════════════════ */

(function() {
  'use strict';

  /* ── Init Store & API ── */
  LT.store.init();
  LT.api.init();

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
  });

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
