/**
 * TaskTreeRenderer — Three-zone task decomposition tree (vanilla JS).
 * Zones: minimap (80px) | main tree (scrollable) | detail panel (320px).
 * Driven by SSE events: task_init, node_update, task_done, task_error.
 *
 * Exports: window.TaskTreeRenderer
 */
(function () {
  'use strict';

  const STATUS_ICONS = {
    done: '\u2705',
    running: '\uD83D\uDD04',
    thinking: '\uD83D\uDCAD',
    pending: '\u23F3',
    failed: '\u274C',
    skipped: '\u23ED\uFE0F',
  };

  const STATUS_COLORS = {
    done: '#27ae60',
    running: '#4a90d9',
    thinking: '#f5a623',
    pending: '#888888',
    failed: '#e74c3c',
    skipped: '#999999',
  };

  function relativeTime(ts) {
    if (!ts) return '\u2014';
    const diff = Date.now() / 1000 - ts;
    if (diff < 5) return '\u521A\u521A';
    if (diff < 60) return `${Math.floor(diff)}\u79D2\u524D`;
    if (diff < 3600) return `${Math.floor(diff / 60)}\u5206\u949F\u524D`;
    return `${Math.floor(diff / 3600)}\u5C0F\u65F6\u524D`;
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  function numAnim(el, from, to, duration) {
    const start = performance.now();
    function tick(now) {
      const p = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      el.textContent = Math.round(from + (to - from) * eased);
      if (p < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }

  class TaskTreeRenderer {
    constructor() {
      this.container = document.getElementById('task-tree-root');
      this.treeData = null;
      this.nodes = {};
      this.selectedId = null;
      this.activeId = null;
      this.collapsed = new Set();
      this.stats = { total: 0, done: 0, running: 0, pending: 0, failed: 0 };
      this.eventSource = null;
      this._lastUserScroll = 0;
      this._timers = {};
      this._buildLayout();
    }

    init(taskDesc) {
      this.taskDesc = taskDesc;
      this._connectSSE();
    }

    /* ── SSE Handling ── */

    _connectSSE() {
      if (this.eventSource) this.eventSource.close();
      const taskId = this.taskDesc || '';
      const url = `/tree/task/tree${taskId ? '?task=' + encodeURIComponent(taskId) : ''}`;
      this.eventSource = new EventSource(url);

      const bind = (name) => {
        this.eventSource.addEventListener(name, (e) => {
          let data;
          try { data = JSON.parse(e.data); } catch (_) { data = {}; }
          this.handleSSEEvent({ type: name, data: data });
        });
      };
      bind('task_init');
      bind('node_update');
      bind('task_done');
      bind('task_error');

      this.eventSource.onerror = () => {
        setTimeout(() => {
          if (this.eventSource && this.eventSource.readyState === EventSource.CLOSED) {
            this._connectSSE();
          }
        }, 2000);
      };
    }

    handleSSEEvent(event) {
      switch (event.type) {
        case 'task_init':
          this.handleTaskInit(event.data);
          break;
        case 'node_update':
          this.handleNodeUpdate(event.data);
          break;
        case 'task_done':
          this.handleTaskDone(event.data);
          break;
        case 'task_error':
          this._showError(event.data.message || event.data.error || 'Unknown error');
          break;
      }
    }

    handleTaskInit(data) {
      this.treeData = data.tree || data;
      this.nodes = {};
      this._indexNodes(this.treeData);
      this._countStats();
      this.renderTree(this.treeData);
      this.renderMinimap();
      this.updateProgress(this.stats);
    }

    handleNodeUpdate(data) {
      const id = data.node_id || data.id;
      if (!id) return;
      const existing = this.nodes[id];
      if (existing) {
        Object.assign(existing, data);
      } else {
        this.nodes[id] = data;
        if (!this._findNodeById(this.treeData, id)) {
          if (data.parent_id && this._findNodeById(this.treeData, data.parent_id)) {
            const parent = this._findNodeById(this.treeData, data.parent_id);
            if (!parent.children) parent.children = [];
            parent.children.push(data);
          }
        }
      }
      this._countStats();

      if (data.status === 'running' || data.status === 'thinking') {
        this.activeId = id;
      }

      const domEl = this._mainEl.querySelector(`[data-id="${id}"]`);
      if (domEl) {
        this.updateNodeDOM(data);
      } else {
        this._insertNewNode(data);
      }
      this.renderMinimap();
      if (this.selectedId === id) {
        this.updateDetailPanel(data);
      }
      if (data.status === 'running') {
        const now = Date.now();
        if (now - this._lastUserScroll > 3000) {
          this.scrollToNode(id);
        }
      }
      this.updateProgress(this.stats);
    }

    handleTaskDone(data) {
      this._countStats();
      this.stats.done = this.stats.total;
      this.stats.running = 0;
      this.stats.pending = 0;
      this.stats.failed = this.stats.failed;
      this.updateProgress(this.stats);
      this.renderMinimap();
      if (data.tree) {
        this.treeData = data.tree;
        this.nodes = {};
        this._indexNodes(this.treeData);
        this.renderTree(this.treeData);
      }
    }

    /* ── Tree Rendering ── */

    renderTree(treeData) {
      this.treeData = treeData;
      this.nodes = {};
      this._indexNodes(this.treeData);
      this._mainEl.innerHTML = '';
      if (!treeData) {
        this._mainEl.innerHTML = '<div class="empty-state">No task tree yet.</div>';
        return;
      }
      const rootEl = this.buildNodeElement(treeData, 0);
      this._mainEl.appendChild(rootEl);
      this._staggerChildren(this._mainEl);
    }

    buildNodeElement(node, depth) {
      const status = node.status || 'pending';
      const priority = node.priority || 'P2';
      const label = node.label || node.node_id || node.id || 'untitled';
      const progress = node.progress || 0;
      const reasoning = node.reasoning || '';

      const wrapper = document.createElement('div');
      wrapper.className = `tree-node depth-${depth} status-${status} priority-${priority}`;
      wrapper.dataset.id = node.node_id || node.id;
      wrapper.dataset.status = status;
      wrapper.dataset.priority = priority;
      wrapper.dataset.depth = depth;

      const card = document.createElement('div');
      card.className = 'node-card';

      const hasChildren = node.children && node.children.length > 0;
      const collapsed = this.collapsed.has(node.node_id || node.id);
      const toggleIcon = collapsed ? '\u25B6' : '\u25BC';

      let html = '';
      if (hasChildren) {
        html += `<span class="node-toggle">${toggleIcon}</span>`;
      } else {
        html += '<span class="node-toggle node-toggle-empty"></span>';
      }
      html += `<span class="node-icon">${STATUS_ICONS[status] || STATUS_ICONS.pending}</span>`;
      html += `<span class="node-label">${escapeHtml(label)}</span>`;
      html += `<div class="node-progress"><div class="node-progress-fill" style="width:${progress}%"></div></div>`;
      if (reasoning) {
        html += `<div class="node-reasoning">${escapeHtml(reasoning.slice(0, 60))}${reasoning.length > 60 ? '\u2026' : ''}</div>`;
      }
      card.innerHTML = html;

      card.addEventListener('click', (e) => {
        if (e.target.classList.contains('node-toggle')) return;
        this.selectNode(node.node_id || node.id);
      });

      wrapper.appendChild(card);

      if (hasChildren) {
        card.querySelector('.node-toggle').addEventListener('click', (e) => {
          e.stopPropagation();
          this.toggleChildren(node.node_id || node.id);
        });

        const childrenDiv = document.createElement('div');
        childrenDiv.className = 'node-children';
        childrenDiv.style.display = collapsed ? 'none' : 'block';

        const childDepth = depth + 1;
        node.children.forEach((child, i) => {
          child._parentId = node.node_id || node.id;
          const childEl = this.buildNodeElement(child, childDepth);
          childEl.style.animationDelay = `${i * 0.05}s`;
          childrenDiv.appendChild(childEl);
        });
        wrapper.appendChild(childrenDiv);
      }

      return wrapper;
    }

    updateNodeDOM(nodeData) {
      const id = nodeData.node_id || nodeData.id;
      const el = this._mainEl.querySelector(`[data-id="${id}"]`);
      if (!el) return;
      const status = nodeData.status || 'pending';

      el.dataset.status = status;
      el.className = el.className.replace(/status-\w+/g, `status-${status}`);

      const iconEl = el.querySelector('.node-icon');
      if (iconEl) {
        iconEl.textContent = STATUS_ICONS[status] || STATUS_ICONS.pending;
      }

      if (nodeData.progress !== undefined) {
        const fillEl = el.querySelector('.node-progress-fill');
        if (fillEl) fillEl.style.width = `${nodeData.progress}%`;
      }

      if (nodeData.reasoning !== undefined) {
        let reasoningEl = el.querySelector('.node-reasoning');
        if (nodeData.reasoning) {
          const preview = nodeData.reasoning.slice(0, 60);
          if (!reasoningEl) {
            reasoningEl = document.createElement('div');
            reasoningEl.className = 'node-reasoning';
            el.querySelector('.node-card').appendChild(reasoningEl);
          }
          reasoningEl.textContent = preview + (nodeData.reasoning.length > 60 ? '\u2026' : '');
        } else if (reasoningEl) {
          reasoningEl.remove();
        }
      }

      if (status === 'done' || status === 'failed') {
        el.classList.add('node-completed');
        this._timers['complete_' + id] = setTimeout(() => el.classList.remove('node-completed'), 1200);
      }

      if (nodeData.children && nodeData.children.length > 0) {
        const existingChildren = el.querySelector('.node-children');
        const toggleEl = el.querySelector('.node-toggle');
        if (!existingChildren) {
          const childrenDiv = document.createElement('div');
          childrenDiv.className = 'node-children';
          childrenDiv.style.display = this.collapsed.has(id) ? 'none' : 'block';
          nodeData.children.forEach((child) => {
            childrenDiv.appendChild(this.buildNodeElement(child, (parseInt(el.dataset.depth) || 0) + 1));
          });
          el.appendChild(childrenDiv);
        }
        if (toggleEl) {
          toggleEl.classList.remove('node-toggle-empty');
          toggleEl.textContent = this.collapsed.has(id) ? '\u25B6' : '\u25BC';
        }
      }

      this.updateProgress(this.stats);
    }

    _insertNewNode(nodeData) {
      const parentId = nodeData.parent_id;
      if (!parentId) return;
      const parentEl = this._mainEl.querySelector(`[data-id="${parentId}"]`);
      if (!parentEl) return;
      const parentNode = this.nodes[parentId];
      const depth = parentNode ? (parentNode.depth || 0) + 1 : 1;
      const newEl = this.buildNodeElement(nodeData, depth);

      let childrenDiv = parentEl.querySelector('.node-children');
      if (!childrenDiv) {
        childrenDiv = document.createElement('div');
        childrenDiv.className = 'node-children';
        childrenDiv.style.display = this.collapsed.has(parentId) ? 'none' : 'block';
        parentEl.appendChild(childrenDiv);
        const toggleEl = parentEl.querySelector('.node-toggle');
        if (toggleEl) {
          toggleEl.classList.remove('node-toggle-empty');
          toggleEl.textContent = this.collapsed.has(parentId) ? '\u25B6' : '\u25BC';
          toggleEl.addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggleChildren(parentId);
          });
        }
      }
      childrenDiv.appendChild(newEl);
    }

    _staggerChildren(container) {
      const direct = container.querySelectorAll(':scope > .tree-node');
      direct.forEach((el, i) => {
        el.style.animationDelay = `${i * 0.05}s`;
      });
    }

    /* ── Minimap ── */

    renderMinimap() {
      const canvas = this._minimapCanvas;
      const ctx = canvas.getContext('2d');
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      canvas.width = w * (window.devicePixelRatio || 1);
      canvas.height = h * (window.devicePixelRatio || 1);
      ctx.scale(window.devicePixelRatio || 1, window.devicePixelRatio || 1);

      ctx.clearRect(0, 0, w, h);

      const allNodes = [];
      this._flattenTree(this.treeData, allNodes, 0);

      if (allNodes.length === 0) return;

      const spacingX = 8;
      const spacingY = 12;
      const maxDepth = Math.max(...allNodes.map(n => n.depth), 1);

      if (allNodes.length > 50) {
        allNodes.forEach((n, i) => {
          const x = 4 + (n.depth / Math.max(maxDepth, 1)) * (w - 8);
          const y = 4 + (i / allNodes.length) * (h - 8);
          ctx.fillStyle = STATUS_COLORS[n.status] || STATUS_COLORS.pending;
          ctx.beginPath();
          ctx.arc(x, y, 2, 0, Math.PI * 2);
          ctx.fill();
        });
      } else {
        const positions = [];
        allNodes.forEach((n, i) => {
          const x = 8 + n.depth * spacingX;
          const y = 8 + i * spacingY;
          positions.push({ id: n.id, x, y, status: n.status, depth: n.depth, parentId: n.parentId });
          ctx.fillStyle = STATUS_COLORS[n.status] || STATUS_COLORS.pending;
          ctx.beginPath();
          ctx.arc(x, y, 3, 0, Math.PI * 2);
          ctx.fill();
        });

        const posMap = {};
        positions.forEach(p => { posMap[p.id] = p; });
        positions.forEach(p => {
          if (p.parentId && posMap[p.parentId]) {
            const parent = posMap[p.parentId];
            ctx.strokeStyle = 'rgba(255,255,255,0.15)';
            ctx.lineWidth = 0.5;
            ctx.beginPath();
            ctx.moveTo(parent.x, parent.y);
            ctx.lineTo(parent.x, p.y);
            ctx.lineTo(p.x, p.y);
            ctx.stroke();
          }
        });
      }

      this._updateMinimapViewport();
    }

    updateMinimapViewport() { this._updateMinimapViewport(); }

    _updateMinimapViewport() {
      const canvas = this._minimapCanvas;
      const ctx = canvas.getContext('2d');
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      const main = this._mainEl;
      const scrollRatio = main.scrollTop / Math.max(main.scrollHeight - main.clientHeight, 1);
      const viewportH = (main.clientHeight / Math.max(main.scrollHeight, 1)) * h;

      ctx.clearRect(0, 0, w, h);
      this.renderMinimap();

      ctx.fillStyle = 'rgba(74, 144, 217, 0.2)';
      ctx.strokeStyle = 'rgba(74, 144, 217, 0.6)';
      ctx.lineWidth = 1;
      ctx.fillRect(0, scrollRatio * (h - viewportH), w, viewportH);
      ctx.strokeRect(0, scrollRatio * (h - viewportH), w, viewportH);
    }

    /* ── Scroll To Node ── */

    scrollToNode(nodeId) {
      const el = this._mainEl.querySelector(`[data-id="${nodeId}"]`);
      if (!el) return;
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      el.classList.add('node-flash');
      this._timers['flash_' + nodeId] = setTimeout(() => el.classList.remove('node-flash'), 600);
      this.updateBreadcrumb(nodeId);
      this._updateMinimapViewport();
    }

    /* ── Selection & Detail ── */

    selectNode(nodeId) {
      this.selectedId = nodeId;
      const prev = this._mainEl.querySelector('.tree-node.selected');
      if (prev) prev.classList.remove('selected');
      const el = this._mainEl.querySelector(`[data-id="${nodeId}"]`);
      if (el) el.classList.add('selected');
      const nodeData = this.nodes[nodeId];
      if (nodeData) this.updateDetailPanel(nodeData);
      this.updateBreadcrumb(nodeId);
    }

    updateDetailPanel(nodeData) {
      if (!this._detailEl) return;
      const status = nodeData.status || 'pending';
      const label = nodeData.label || nodeData.node_id || nodeData.id || 'untitled';

      let html = '';
      html += `<div class="detail-header">${escapeHtml(label)} <span class="status-badge status-${status}">${status}</span></div>`;

      html += '<div class="detail-section"><h4>\uD83D\uDCA1 \u63A8\u7406\u4F9D\u636E</h4>';
      html += `<blockquote>${escapeHtml(nodeData.reasoning || '\u6682\u65E0\u63A8\u7406')}</blockquote></div>`;

      html += '<div class="detail-section"><h4>\u23F1 \u65F6\u95F4\u7EBF</h4>';
      html += `<div>\u521B\u5EFA: ${relativeTime(nodeData.created_at || nodeData.created)}</div>`;
      html += `<div>\u5F00\u59CB: ${relativeTime(nodeData.started_at || nodeData.started)}</div>`;
      html += `<div>\u5B8C\u6210: ${relativeTime(nodeData.completed_at || nodeData.completed)}</div>`;
      html += '</div>';

      html += '<div class="detail-section"><h4>\uD83D\uDD17 \u4F9D\u8D56</h4>';
      if (nodeData.dependencies && nodeData.dependencies.length > 0) {
        html += nodeData.dependencies.map(dep => {
          const depId = dep.id || dep.node_id || dep;
          const depLabel = dep.label || depId;
          const depStatus = dep.status || (this.nodes[depId] ? this.nodes[depId].status : 'pending');
          const color = STATUS_COLORS[depStatus] || STATUS_COLORS.pending;
          return `<span class="dep-link" data-dep-id="${depId}" style="color:${color};cursor:pointer;text-decoration:underline;margin-right:10px">${escapeHtml(depLabel)}</span>`;
        }).join('');
      } else {
        html += '<span class="empty-state">\u65E0\u4F9D\u8D56</span>';
      }
      html += '</div>';

      html += '<div class="detail-section"><h4>\uD83D\uDCE4 \u7ED3\u679C</h4>';
      html += `<pre>${escapeHtml(nodeData.result || nodeData.output || '\u6682\u65E0\u7ED3\u679C')}</pre></div>`;

      html += '<div class="detail-section"><h4>\uD83D\uDCCA Token</h4>';
      const est = nodeData.tokens_estimated || '\u2014';
      const actual = nodeData.tokens_actual || '\u2014';
      const saved = nodeData.tokens_saved || '\u2014';
      html += `<div>\u9884\u4F30: ${est} \u2192 \u5B9E\u9645: ${actual} (\u8282\u7701: ${saved})</div></div>`;

      this._detailEl.innerHTML = html;

      this._detailEl.querySelectorAll('.dep-link').forEach(link => {
        link.addEventListener('click', () => {
          this.selectNode(link.dataset.depId);
          this.scrollToNode(link.dataset.depId);
        });
      });
    }

    updateBreadcrumb(nodeId) {
      if (!this._breadcrumbEl) return;
      const path = this.getBreadcrumbPath(nodeId, this.treeData);
      let html = '';
      path.forEach((n, i) => {
        const label = n.label || n.id || 'root';
        const isLast = i === path.length - 1;
        html += `<span class="crumb${isLast ? ' active' : ''}" data-crumb-id="${n.id}">${escapeHtml(label)}</span>`;
        if (!isLast) html += ' &gt; ';
      });
      this._breadcrumbEl.innerHTML = html;
      this._breadcrumbEl.querySelectorAll('.crumb').forEach(crumb => {
        crumb.addEventListener('click', () => {
          this.scrollToNode(crumb.dataset.crumbId);
        });
      });
    }

    /* ── Progress ── */

    updateProgress(stats) {
      if (!this._progressFillEl) return;
      const pct = stats.total > 0 ? Math.round((stats.done / stats.total) * 100) : 0;
      this._progressFillEl.style.width = `${pct}%`;

      if (this._statTotalEl) {
        const prev = parseInt(this._statTotalEl.textContent) || 0;
        numAnim(this._statTotalEl, prev, stats.total, 400);
        this._statTotalEl._val = stats.total;
      }
      if (this._statDoneEl) {
        const prev = parseInt(this._statDoneEl.textContent) || 0;
        numAnim(this._statDoneEl, prev, stats.done, 400);
        this._statDoneEl._val = stats.done;
      }
      if (this._statRunningEl) this._statRunningEl.textContent = stats.running;
      if (this._statPendingEl) this._statPendingEl.textContent = stats.pending;
      if (this._statFailedEl) this._statFailedEl.textContent = stats.failed;
    }

    /* ── Collapse / Expand ── */

    toggleChildren(nodeId) {
      const el = this._mainEl.querySelector(`[data-id="${nodeId}"]`);
      if (!el) return;
      const childrenDiv = el.querySelector('.node-children');
      if (!childrenDiv) return;
      const toggleEl = el.querySelector('.node-toggle');
      const wasHidden = childrenDiv.style.display === 'none';

      if (wasHidden) {
        childrenDiv.style.display = 'block';
        this.collapsed.delete(nodeId);
        if (toggleEl) toggleEl.textContent = '\u25BC';
      } else {
        childrenDiv.style.display = 'none';
        this.collapsed.add(nodeId);
        if (toggleEl) toggleEl.textContent = '\u25B6';
      }
      this.renderMinimap();
    }

    collapseAll() {
      this._mainEl.querySelectorAll('.node-children').forEach(el => {
        el.style.display = 'none';
      });
      this._mainEl.querySelectorAll('.node-toggle:not(.node-toggle-empty)').forEach(el => {
        el.textContent = '\u25B6';
      });
      this.flattenIds().forEach(id => {
        if (this._mainEl.querySelector(`[data-id="${id}"] > .node-children`)) {
          this.collapsed.add(id);
        }
      });
      this.renderMinimap();
    }

    expandAll() {
      this._mainEl.querySelectorAll('.node-children').forEach(el => {
        el.style.display = 'block';
      });
      this._mainEl.querySelectorAll('.node-toggle:not(.node-toggle-empty)').forEach(el => {
        el.textContent = '\u25BC';
      });
      this.collapsed.clear();
      this.renderMinimap();
    }

    /* ── Utility ── */

    findNodeById(id, root) {
      return this._findNodeById(root || this.treeData, id);
    }

    _findNodeById(node, id) {
      if (!node) return null;
      const nid = node.node_id || node.id;
      if (nid === id) return node;
      if (node.children) {
        for (const child of node.children) {
          const found = this._findNodeById(child, id);
          if (found) return found;
        }
      }
      return null;
    }

    getNodeDepth(nodeId, root) {
      return this._getNodeDepth(root || this.treeData, nodeId, 0);
    }

    _getNodeDepth(node, targetId, depth) {
      if (!node) return -1;
      const nid = node.node_id || node.id;
      if (nid === targetId) return depth;
      if (node.children) {
        for (const child of node.children) {
          const d = this._getNodeDepth(child, targetId, depth + 1);
          if (d >= 0) return d;
        }
      }
      return -1;
    }

    getBreadcrumbPath(nodeId, root) {
      const path = [];
      this._findPath(root || this.treeData, nodeId, path);
      return path;
    }

    _findPath(node, targetId, path) {
      if (!node) return false;
      const nid = node.node_id || node.id;
      path.push({ id: nid, label: node.label || nid });
      if (nid === targetId) return true;
      if (node.children) {
        for (const child of node.children) {
          if (this._findPath(child, targetId, path)) return true;
        }
      }
      path.pop();
      return false;
    }

    flattenIds() {
      const ids = [];
      if (this.treeData) this._collectIds(this.treeData, ids);
      return ids;
    }

    /* ── Private ── */

    _buildLayout() {
      this.container.innerHTML = '';
      this.container.classList.add('task-tree-root-container');

      const header = document.createElement('div');
      header.className = 'task-header-bar';
      header.innerHTML = `
        <div class="overall-progress"><div class="overall-progress-fill" style="width:0%"></div></div>
        <div class="stats">
          <span class="stat-done">0</span>/<span class="stat-total">0</span> done |
          <span class="stat-running">0</span> running |
          <span class="stat-pending">0</span> pending |
          <span class="stat-failed">0</span> failed
        </div>
        <div class="header-actions">
          <button class="btn-col-exp" title="Collapse all">\u2191</button>
          <button class="btn-col-exp" title="Expand all">\u2193</button>
        </div>
      `;
      this.container.appendChild(header);
      this._progressFillEl = header.querySelector('.overall-progress-fill');
      this._statTotalEl = header.querySelector('.stat-total');
      this._statDoneEl = header.querySelector('.stat-done');
      this._statRunningEl = header.querySelector('.stat-running');
      this._statPendingEl = header.querySelector('.stat-pending');
      this._statFailedEl = header.querySelector('.stat-failed');
      header.querySelectorAll('.btn-col-exp')[0].addEventListener('click', () => this.collapseAll());
      header.querySelectorAll('.btn-col-exp')[1].addEventListener('click', () => this.expandAll());

      const breadcrumb = document.createElement('div');
      breadcrumb.className = 'task-breadcrumb';
      breadcrumb.id = 'task-tree-breadcrumb';
      this.container.appendChild(breadcrumb);
      this._breadcrumbEl = breadcrumb;

      const toast = document.createElement('div');
      toast.className = 'task-error-toast';
      toast.id = 'task-tree-error';
      toast.style.display = 'none';
      this.container.appendChild(toast);
      this._toastEl = toast;

      const mainLayout = document.createElement('div');
      mainLayout.className = 'task-tree-container';

      const minimap = document.createElement('div');
      minimap.className = 'task-tree-minimap';
      minimap.id = 'task-tree-minimap';
      const canvas = document.createElement('canvas');
      canvas.width = 80;
      canvas.height = 400;
      minimap.appendChild(canvas);
      this._minimapCanvas = canvas;
      mainLayout.appendChild(minimap);

      const mainArea = document.createElement('div');
      mainArea.className = 'task-tree-main';
      mainArea.id = 'task-tree-main';
      mainLayout.appendChild(mainArea);
      this._mainEl = mainArea;

      const detail = document.createElement('div');
      detail.className = 'task-tree-detail';
      detail.id = 'task-tree-detail';
      detail.innerHTML = '<div class="empty-state">Select a node from the tree to view details.</div>';
      mainLayout.appendChild(detail);
      this._detailEl = detail;

      this.container.appendChild(mainLayout);

      mainArea.addEventListener('scroll', () => {
        this._lastUserScroll = Date.now();
        this._updateMinimapViewport();
      });

      canvas.addEventListener('click', (e) => {
        const rect = canvas.getBoundingClientRect();
        const y = e.clientY - rect.top;
        const h = canvas.clientHeight;
        const allNodes = [];
        this._flattenTree(this.treeData, allNodes, 0);
        if (allNodes.length === 0) return;
        const idx = Math.floor((y / h) * allNodes.length);
        if (idx >= 0 && idx < allNodes.length) {
          this.scrollToNode(allNodes[idx].id);
          this.selectNode(allNodes[idx].id);
        }
      });

      this._injectStyles();
    }

    _indexNodes(node, parentId) {
      if (!node) return;
      const id = node.node_id || node.id;
      if (!id) return;
      node._parentId = parentId;
      this.nodes[id] = node;
      if (parentId) {
        this.nodes[id].parent_id = parentId;
      }
      if (node.children) {
        node.children.forEach(child => this._indexNodes(child, id));
      }
    }

    _countStats() {
      const ids = Object.keys(this.nodes);
      this.stats.total = ids.length;
      this.stats.done = ids.filter(id => this.nodes[id].status === 'done').length;
      this.stats.running = ids.filter(id => this.nodes[id].status === 'running' || this.nodes[id].status === 'thinking').length;
      this.stats.failed = ids.filter(id => this.nodes[id].status === 'failed').length;
      this.stats.pending = this.stats.total - this.stats.done - this.stats.running - this.stats.failed;
    }

    _flattenTree(node, result, depth) {
      if (!node) return;
      const id = node.node_id || node.id;
      result.push({
        id,
        status: node.status || 'pending',
        depth: depth,
        label: node.label || id,
        parentId: node._parentId || null,
      });
      if (node.children) {
        node.children.forEach(child => {
          child._parentId = id;
          child.depth = depth + 1;
          this._flattenTree(child, result, depth + 1);
        });
      }
    }

    _collectIds(node, result) {
      if (!node) return;
      result.push(node.node_id || node.id);
      if (node.children) {
        node.children.forEach(child => this._collectIds(child, result));
      }
    }

    _showError(message) {
      if (!this._toastEl) return;
      this._toastEl.textContent = message;
      this._toastEl.style.display = 'block';
      clearTimeout(this._timers._toast);
      this._timers._toast = setTimeout(() => {
        this._toastEl.style.display = 'none';
      }, 4000);
    }

    _injectStyles() {
      if (document.getElementById('task-tree-runtime-styles')) return;
      const css = `
#task-tree-root { display:flex;flex-direction:column;height:100%;background:var(--bg, #08080f);color:var(--text, #c8c8d4);font-family:"Maple Mono","Cascadia Code",Consolas,monospace }
.task-header-bar { display:flex;align-items:center;padding:8px 16px;gap:12px;border-bottom:1px solid var(--border, #1a1a2e);flex-shrink:0 }
.task-header-bar .overall-progress { flex:1;height:8px;background:var(--border, #1a1a2e);border-radius:4px;overflow:hidden }
.task-header-bar .overall-progress-fill { height:100%;background:linear-gradient(90deg,#4a90d9,#27ae60);border-radius:4px;transition:width .5s }
.task-header-bar .stats { font-size:0.75rem;color:var(--muted, #6a6a7a);white-space:nowrap }
.task-header-bar .header-actions { display:flex;gap:4px }
.task-header-bar .btn-col-exp { background:var(--surface, #0f0f18);color:var(--muted, #6a6a7a);border:1px solid var(--border, #1a1a2e);border-radius:4px;padding:2px 8px;cursor:pointer;font-size:0.8rem }
.task-header-bar .btn-col-exp:hover { color:var(--text, #c8c8d4);border-color:var(--accent, #6c8) }
.task-breadcrumb { padding:4px 16px;font-size:0.72rem;color:var(--muted, #6a6a7a);flex-shrink:0;min-height:22px;border-bottom:1px solid rgba(26,26,46,0.5) }
.task-breadcrumb .crumb { cursor:pointer;color:var(--accent, #6c8) }
.task-breadcrumb .crumb:hover { text-decoration:underline }
.task-breadcrumb .crumb.active { color:var(--text, #c8c8d4);font-weight:600;cursor:default }
.task-error-toast { position:absolute;top:0;left:50%;transform:translateX(-50%);background:var(--red, #e05050);color:#fff;padding:8px 20px;border-radius:0 0 6px 6px;font-size:0.78rem;z-index:100;display:none }
.task-tree-container { display:flex;flex:1;overflow:hidden;position:relative }
.task-tree-minimap { width:80px;flex-shrink:0;border-right:1px solid var(--border, #1a1a2e);padding:4px;overflow:hidden }
.task-tree-minimap canvas { width:100%;height:100% }
.task-tree-main { flex:1;overflow-y:auto;overflow-x:auto;padding:12px 16px }
.task-tree-detail { width:320px;flex-shrink:0;border-left:1px solid var(--border, #1a1a2e);overflow-y:auto;padding:16px;background:var(--surface, #0f0f18) }
.tree-node { animation:node-fade-in .25s both }
@keyframes node-fade-in { from{opacity:0;transform:translateY(6px)} to{opacity:1;transform:translateY(0)} }
.node-card { display:flex;align-items:center;gap:6px;padding:6px 10px;margin:2px 0;border-left:3px solid transparent;border-radius:0 6px 6px 0;cursor:pointer;transition:background .15s;font-size:0.82rem;white-space:nowrap }
.node-card:hover { background:rgba(255,255,255,0.03) }
.tree-node.selected>.node-card { background:rgba(102,204,136,0.08) }
.tree-node.priority-P0>.node-card { border-left-color:var(--red, #e05050) }
.tree-node.priority-P1>.node-card { border-left-color:var(--orange, #e09030) }
.tree-node.priority-P2>.node-card { border-left-color:var(--blue, #4a8) }
.tree-node.priority-P3>.node-card { border-left-color:var(--border, #1a1a2e) }
.node-toggle { flex-shrink:0;width:18px;height:18px;display:inline-flex;align-items:center;justify-content:center;color:var(--muted);font-size:0.7rem;cursor:pointer;user-select:none;border-radius:3px }
.node-toggle:hover { color:var(--text);background:rgba(255,255,255,0.05) }
.node-toggle-empty { visibility:hidden }
.node-icon { flex-shrink:0;width:20px;text-align:center;font-size:0.85rem }
.node-label { flex:1;overflow:hidden;text-overflow:ellipsis }
.node-progress { width:60px;height:4px;background:var(--border);border-radius:2px;overflow:hidden;flex-shrink:0 }
.node-progress-fill { height:100%;background:var(--accent);border-radius:2px;transition:width .4s }
.node-reasoning { font-size:0.7rem;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin-left:44px }
.node-children { margin-left:24px }
.node-flash { animation:node-flash-anim .5s ease-out }
@keyframes node-flash-anim { 0%{box-shadow:0 0 12px rgba(74,144,217,0.6)} 100%{box-shadow:none} }
.node-completed>.node-card { animation:node-complete-flash .6s ease-out }
@keyframes node-complete-flash { 0%{background:rgba(39,174,96,0.25)} 100%{background:transparent} }
@keyframes pulse-icon { 0%,100%{opacity:.4;transform:scale(.9)} 50%{opacity:1;transform:scale(1.15)} }
@keyframes spin-icon { to{transform:rotate(360deg)} }
.status-thinking .node-icon { animation:pulse-icon 1s infinite }
.status-running .node-icon { animation:spin-icon 1.2s linear infinite }
.status-done .node-icon { animation:node-done-pop .35s ease-out }
@keyframes node-done-pop { 0%{transform:scale(0);opacity:0} 60%{transform:scale(1.3)} 100%{transform:scale(1);opacity:1} }
.detail-header { font-size:1rem;font-weight:600;margin-bottom:14px }
.detail-header .status-badge { display:inline-block;font-size:0.7rem;padding:2px 8px;border-radius:10px;margin-left:8px;text-transform:uppercase }
.status-badge.status-done { background:rgba(39,174,96,0.2);color:#27ae60 }
.status-badge.status-running { background:rgba(74,144,217,0.2);color:#4a90d9 }
.status-badge.status-thinking { background:rgba(245,166,35,0.2);color:#f5a623 }
.status-badge.status-pending { background:rgba(136,136,136,0.2);color:#888 }
.status-badge.status-failed { background:rgba(231,76,60,0.2);color:#e74c3c }
.detail-section { background:var(--bg, #08080f);border:1px solid var(--border, #1a1a2e);border-radius:6px;padding:14px;margin-bottom:12px }
.detail-section h4 { margin:0 0 8px;font-size:0.75rem;text-transform:uppercase;letter-spacing:.06em;color:var(--muted) }
.detail-section blockquote { font-size:0.8rem;line-height:1.55;margin:0;padding-left:10px;border-left:2px solid var(--accent) }
.detail-section pre { font-size:0.78rem;background:rgba(0,0,0,0.2);border:1px solid var(--border);border-radius:4px;padding:10px;max-height:200px;overflow-y:auto;white-space:pre-wrap;word-break:break-all;margin:0 }
.detail-section .dep-link { font-size:0.78rem;display:inline-block }
.empty-state { color:var(--muted);font-size:0.82rem;text-align:center;padding:30px 0 }
`;
      const style = document.createElement('style');
      style.id = 'task-tree-runtime-styles';
      style.textContent = css;
      document.head.appendChild(style);
    }

    destroy() {
      Object.values(this._timers).forEach(clearTimeout);
      this._timers = {};
      if (this.eventSource) {
        this.eventSource.close();
        this.eventSource = null;
      }
      if (this.container) {
        this.container.innerHTML = '';
      }
    }
  }

  window.TaskTreeRenderer = TaskTreeRenderer;

  document.addEventListener('DOMContentLoaded', () => {
    const root = document.getElementById('task-tree-root');
    if (root) {
      const taskDesc = root.dataset.task || '';
      window.taskTree = new TaskTreeRenderer();
      window.taskTree.init(taskDesc);
    }
  });
})();
