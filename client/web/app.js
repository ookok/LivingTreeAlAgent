/* ═══════════════════════════════════
   LivingTree Web — App Bootstrap
   Initializes all components and wires them together
   ═══════════════════════════════════ */

(function() {
  'use strict';

  /* ── Init Store & API ── */
  window.S = LT.store;   // global store reference (used by all component files)
  if (LT.store && LT.store.init) LT.store.init();
  if (LT.store && LT.store.initAutoTheme) LT.store.initAutoTheme();
  if (LT.store && LT.store.requestNotify) LT.store.requestNotify();
  // Fetch user role (for code mode admin check)
  if (LT.store && LT.store.fetchUserRole) LT.store.fetchUserRole();
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
    { name: 'code-editor', el: '#editor-panel-body', skip: true },
    { name: 'models', el: '#models-modal' },
  ];

  components.forEach(({ name, el, skip }) => {
    if (skip) return;
    const Cls = LT.get(name);
    if (!Cls) { console.warn(`Component "${name}" not registered`); return; }
    const root = typeof el === 'string' ? document.querySelector(el) : el;
    if (!root) { console.warn(`Mount point "${el}" not found for "${name}"`); return; }
    new Cls(root).init();
  });

  /* ── Periodic shield status + presence + scheduler color update ── */
  const _shieldTimer = setInterval(async function() {
    try { var r=await fetch('/api/shield/status');var d=await r.json();var el=document.getElementById('shield-indicator'); if(el) el.textContent = d.hitl_pending>0 ? '⚠️' : '🛡️'; } catch(e) {}
  }, 30000);

  const _vitalsTimer = setInterval(async function() {
    try { var r=await fetch('/api/status/vitals');var d=await r.json();var el=document.getElementById('presence-text'); if(el) el.textContent = (d.leaf_display||{}).message || '🌿'; } catch(e) {}
    try { var r=await fetch('/api/scheduler/status');var d=await r.json();var dm=document.documentElement;var colors={growth:'#0fdc78',active:'#67c23a',torpor:'#e28a00',hibernation:'#f65a5a'};var c=colors[d.mode]||'#0fdc78';dm.style.setProperty('--brand-default',c); } catch(e) {}
  }, 8000);

  // Cleanup on page unload
  window.addEventListener('beforeunload',function(){clearInterval(_shieldTimer);clearInterval(_vitalsTimer);});

  /* ── Open Admin link ── */
  window.openAdmin = function() { window.open('/tree/admin','_blank'); };

  /* ── Local folder picker (File System Access API) ── */
  var _dirHandle = null;
  window.pickFolder = async function() {
    try {
      _dirHandle = await window.showDirectoryPicker();
      document.getElementById('folder-path').textContent = _dirHandle.name;
      window.LT = window.LT || {};
      window.LT.dirHandle = _dirHandle;
      console.log('[localfs] Mounted:', _dirHandle.name);
    } catch(e) {
      if (e.name !== 'AbortError') console.warn('[localfs]', e);
    }
  };

  var _panelClearedAt = 0;
  window.clearPanel = function() {
    var el = document.getElementById('chat-area');
    if (el) { var msgs = el.querySelector('.messages'); if (msgs) msgs.innerHTML = ''; }
    if (window.S && window.S.activeId && window.S.messages) {
      var sid = window.S.activeId;
      _panelClearedAt = (window.S.messages[sid] || []).length;
    }
  };
  window.LT = window.LT || {};
  window.LT.getDirHandle = function() { return _dirHandle; };

  /* ── Cognition toggle ── */
  window.toggleCognition = function() {
    var p = document.getElementById('cognition-panel');
    if (!p) return;
    p.style.display = p.style.display === 'none' ? 'block' : 'none';
    if (p.style.display === 'block') {
      p.innerHTML = '<span style="color:var(--text-secondary)">🧠 认知流已开启 — 发送消息可见AI思考过程</span>';
      p.scrollIntoView({behavior:'smooth'});
    }
  };

  /* ── Creative panel ── */
  var _creativeTabs = ['timeline','dream','swarm','emotion','twin'];
  var _creativeIdx = 0;
  window.openCreative = function() {
    var existing = document.getElementById('creative-modal');
    if (existing) { existing.style.display = existing.style.display==='none'?'flex':'none'; return; }
    var el = document.createElement('div');
    el.id = 'creative-modal';
    el.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.9);z-index:999;display:flex;align-items:center;justify-content:center;flex-direction:column';
    el.onclick = function(e) { if (e.target===el) el.style.display='none'; };
    var inner = '<div style="background:var(--bg-secondary);border-radius:12px;width:700px;max-width:95vw;max-height:80vh;overflow:hidden;display:flex;flex-direction:column">' +
      '<div style="display:flex;gap:4px;padding:12px;border-bottom:1px solid var(--border-secondary)">' +
      _creativeTabs.map(function(t,i){ return '<button onclick="_switchCreative('+i+')" style="padding:4px 12px;border-radius:6px;font-size:11px;cursor:pointer;border:1px solid var(--border-secondary);background:none;color:var(--text-secondary)" id="crea-tab-'+i+'">'+{timeline:'⏳记忆',dream:'🌙梦境',swarm:'🗺️群体',emotion:'💭情绪',twin:'🪞孪生'}[t]+'</button>'; }).join('') +
      '<button style="margin-left:auto;padding:4px 12px;border-radius:6px;font-size:11px;cursor:pointer;border:none;background:none;color:var(--text-secondary)" onclick="document.getElementById(\'creative-modal\').remove()">✕</button></div>' +
      '<div id="creative-content" style="padding:16px;overflow-y:auto;flex:1;font-size:12px;color:var(--text-secondary)">加载中...</div></div>';
    el.innerHTML = inner;
    document.body.appendChild(el);
    _switchCreative(0);
  };
  window._switchCreative = function(idx) {
    _creativeIdx = idx;
    _creativeTabs.forEach(function(_,i) {
      var b = document.getElementById('crea-tab-'+i);
      if (b) b.style.background = i===idx ? 'var(--brand-default)' : 'none';
      if (b) b.style.color = i===idx ? 'var(--bg-base)' : 'var(--text-secondary)';
    });
    var el = document.getElementById('creative-content');
    if (el) {
      el.innerHTML = '<div style="text-align:center;padding:20px">加载中...</div>';
      fetch('/tree/creative/'+_creativeTabs[idx]).then(function(r){return r.text()}).then(function(h){ el.innerHTML = h; });
    }
  };
  LT.on('creative:open', function() { openCreative(); });
  LT.on('session:switch', id => {
    document.getElementById('topbar-title').textContent = LT.store.active()?.title || 'LivingTree AI Agent';
  });

  /* ── Code Mode button visibility (show only for admins) ── */
  LT.on('codemode:changed', (active) => {
    const btn = document.getElementById('btn-code-mode');
    if (btn) btn.classList.toggle('active', active);
  });
  LT.on('store:userRoleLoaded', () => {
    const btn = document.getElementById('btn-code-mode');
    if (btn) {
      btn.style.display = '';
    }
  });

  /* ── Sidebar toggle ── */
  window.toggleSidebar = () => document.getElementById('sidebar').classList.toggle('collapsed');

  /* ── Code Mode toggle ── */
  window.toggleCodeMode = () => {
    if (!LT.store.fetchUserRole) return;
    // If role not loaded yet, fetch first then toggle
    if (LT.store.userRole === null) {
      LT.store.fetchUserRole().then(() => LT.store.toggleCodeMode());
      return;
    }
    const active = LT.store.toggleCodeMode();
    if (active) {
      const overlay = document.getElementById('project-selector-overlay');
      if (overlay) overlay.style.display = 'flex';
    }
  };

  // Project selector open/close
  LT.on('project-selector:close', () => {
    const overlay = document.getElementById('project-selector-overlay');
    if (overlay) overlay.style.display = 'none';
  });

  // GitHub OAuth callback detection
  window.addEventListener('message', (e) => {
    if (e.data === 'github-auth-success') {
      LT.store.checkGitHubAuth();
    }
  });

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
    LT.emit('doc:insert-diagram', data);
  });

  /* ── Report workflow checkpoint check ── */
  if (typeof ReportWorkflow !== 'undefined') {
    const checkpoint = ReportWorkflow.resume();
    if (checkpoint && checkpoint.status !== 'done' && checkpoint.status !== 'idle') {
      LT.emit('notify', { msg: `检测到未完成的报告 "${checkpoint.title}"，点击继续`, type: 'info' });
    }
  }

  /* ── Service availability check ── */
  (async function checkServices() {
    try {
      const r = await fetch('http://localhost:9000/web-apps/apps/api/documents/api.js', { method: 'HEAD' });
      if (!r.ok) { var el = document.getElementById('btn-split'); if (el) el.style.opacity = '0.4'; }
    } catch(e) { var el = document.getElementById('btn-split'); if (el) el.style.opacity = '0.4'; }
  })();

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
    if (e.key === 'c' && (e.metaKey || e.ctrlKey) && e.shiftKey) {
      e.preventDefault();
      toggleCodeMode();
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
  LT.on('review:complete', () => { if (LT.store && LT.store.notify) LT.store.notify('LivingTree', '文档审阅完成'); });
  LT.on('msg:done', () => { if (LT.store && LT.store.notify) LT.store.notify('LivingTree', 'AI 回复已完成'); });

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

  /* ── Register Service Worker for caching ── */
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  }
})();
