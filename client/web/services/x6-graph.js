/* ═══════════════════════════════════
   LivingTree Web — AntV X6 Graph Service
   All 6 visualization modes + shared utilities
   ═══════════════════════════════════ */

const X6Graph = {
  _graph: null,
  _container: null,
  _mode: null,
  _nodeId: 0,
  _colors: {
    brand: '#0fdc78', blue: '#3f85ff', violet: '#9570ff',
    cyan: '#00b8f8', amber: '#e28a00', coral: '#f65a5a',
    lime: '#a3d930', magenta: '#d1469e', teal: '#00bcd4',
  },

  /* ── Init / Destroy ── */
  init(containerId) {
    if (!window.X6) { console.warn('[X6Graph] X6 not loaded'); return; }
    this._container = document.getElementById(containerId);
    if (!this._container) return;
    this.destroy();
    this._graph = new X6.Graph({
      container: this._container,
      width: this._container.clientWidth,
      height: this._container.clientHeight,
      grid: { size: 10, visible: true, type: 'dot', args: { color: 'rgba(255,255,255,0.04)' } },
      panning: { enabled: true, modifiers: 'shift' },
      mousewheel: { enabled: true, modifiers: 'ctrl', factor: 1.1 },
      selecting: { enabled: true, multiple: true, rubberband: true },
      snapline: true,
      connecting: { snap: true, allowBlank: false, allowMulti: false, highlight: true },
      background: { color: 'transparent' },
    });
    this._graph.centerContent();
    window.addEventListener('resize', () => this._resize());
  },

  destroy() {
    if (this._graph) { this._graph.dispose(); this._graph = null; }
    this._nodeId = 0;
  },

  _resize() {
    if (!this._graph || !this._container) return;
    this._graph.resize(this._container.clientWidth, this._container.clientHeight);
  },

  _uid() { return 'n' + (++this._nodeId); },

  /* ── Shared node/edge builders ── */
  _rectNode(id, x, y, w, h, label, fill, textColor) {
    return this._graph.addNode({
      id, x, y, width: w, height: h, shape: 'rect',
      attrs: {
        body: { fill, stroke: 'rgba(255,255,255,0.12)', strokeWidth: 1, rx: 6, ry: 6 },
        label: { text: label, fill: textColor || '#d1d3db', fontSize: 11, fontFamily: '"Microsoft YaHei",sans-serif' },
      },
      ports: { groups: { top: { position: 'top' }, bottom: { position: 'bottom' }, left: { position: 'left' }, right: { position: 'right' } },
        items: [
          { group: 'top', id: id + '_t' }, { group: 'bottom', id: id + '_b' },
          { group: 'left', id: id + '_l' }, { group: 'right', id: id + '_r' },
        ] },
    });
  },

  _circleNode(id, x, y, r, label, fill) {
    return this._graph.addNode({
      id, x, y, width: r * 2, height: r * 2, shape: 'circle',
      attrs: {
        body: { fill, stroke: 'rgba(255,255,255,0.2)', strokeWidth: 2 },
        label: { text: label, fill: '#fff', fontSize: 10, fontFamily: '"Microsoft YaHei",sans-serif' },
      },
    });
  },

  _edge(source, target, label, dashed) {
    return this._graph.addEdge({
      source: { cell: source, port: source + '_b' },
      target: { cell: target, port: target + '_t' },
      attrs: {
        line: { stroke: 'rgba(255,255,255,0.2)', strokeWidth: 1.5, strokeDasharray: dashed ? '5 5' : '', targetMarker: { name: 'block', width: 8, height: 6 } },
      },
      labels: label ? [{ attrs: { label: { text: label, fill: '#9599a6', fontSize: 9 } } }] : [],
    });
  },

  /* ═══════════════════════════════════════
     1. AGENT PIPELINE DESIGNER
     ═══════════════════════════════════════ */
  _renderPipeline(data) {
    const g = this._graph;
    const cols = { input: 80, router: 280, models: 480, tools: 680, gate: 880, output: 1080 };
    const rowY = (i) => 60 + i * 90;

    // User Input
    this._rectNode(this._uid(), cols.input, 200, 120, 40, '👤 User Input', '#1a1b1d', '#3f85ff');
    // Router MoA
    const router = this._rectNode(this._uid(), cols.router, 200, 120, 40, '🧭 RouteMoA', '#1a1b1d', '#9570ff');
    this._edge(this._nodeId - 2, this._nodeId - 1, '', false);

    // Models
    const models = (data?.models || ['DeepSeek V4', 'LongCat', 'Qwen', 'SiliconFlow', 'Zhipu', 'Spark']).slice(0, 6);
    const modelIds = [];
    models.forEach((m, i) => {
      const id = this._uid();
      modelIds.push(id);
      this._rectNode(id, cols.models, rowY(i), 110, 36, `🤖 ${m}`, 'rgba(63,133,255,0.15)', '#d1d3db');
      this._edge(router, id, '', false);
    });

    // Knowledge / Tools
    const tools = (data?.tools || ['RAG 2.0', 'Gaussian Plume', 'Noise Model', 'Code Graph', 'Doc Engine', 'Visual Render']);
    let lastToolY = rowY(0);
    const toolIds = [];
    tools.forEach((t, i) => {
      const id = this._uid();
      toolIds.push(id);
      this._rectNode(id, cols.tools, rowY(i), 110, 36, `🔧 ${t}`, 'rgba(149,112,255,0.12)', '#d1d3db');
      // Connect from nearest model
      if (modelIds.length) this._edge(modelIds[i % modelIds.length], id, '', true);
    });

    // Economic Gate
    const gateId = this._uid();
    this._rectNode(gateId, cols.gate, 220, 120, 40, '💰 Economic Gate', '#1a1b1d', '#e28a00');
    toolIds.forEach(tid => this._edge(tid, gateId, '', false));
    toolIds.forEach(tid => this._edge(tid, gateId, '', false));

    // Output
    const outId = this._uid();
    this._rectNode(outId, cols.output, 220, 120, 40, '📄 Output DOCX/PDF', '#1a1b1d', '#0fdc78');
    this._edge(gateId, outId, '', false);

    // Add node tooltips
    g.on('node:mouseenter', ({ node }) => {
      const label = node.attr('label/text');
      if (label && label.includes('DeepSeek')) node.attr('body/stroke', '#3f85ff');
      if (label && label.includes('Economic')) node.attr('body/stroke', '#e28a00');
    });
    g.on('node:mouseleave', ({ node }) => {
      node.attr('body/stroke', 'rgba(255,255,255,0.12)');
    });

    g.centerContent();
  },

  /* ═══════════════════════════════════════
     2. KNOWLEDGE GRAPH EXPLORER
     ═══════════════════════════════════════ */
  _renderKnowledgeGraph(data) {
    const g = this._graph;
    const entities = data?.entities || [
      { name: '环评报告', category: 'doc', size: 24 },
      { name: '大气污染', category: 'concept', size: 18 },
      { name: 'PM2.5', category: 'metric', size: 14 },
      { name: '高斯烟羽', category: 'method', size: 14 },
      { name: '水环境', category: 'concept', size: 16 },
      { name: 'COD', category: 'metric', size: 12 },
      { name: '噪声衰减', category: 'method', size: 14 },
      { name: '法规 GB3095', category: 'law', size: 16 },
      { name: '排放标准', category: 'law', size: 14 },
      { name: '监测数据', category: 'data', size: 16 },
    ];
    const edges = data?.edges || [
      [0, 1], [0, 5], [0, 8], [1, 2], [1, 3],
      [4, 5], [5, 6], [7, 8], [0, 7], [3, 9], [6, 9],
    ];

    const catColors = {
      doc: '#0fdc78', concept: '#3f85ff', metric: '#e28a00',
      method: '#9570ff', law: '#f65a5a', data: '#00b8f8',
    };

    const W = g.options.width, H = g.options.height;
    const ids = [];

    entities.forEach((e, i) => {
      const angle = (i / entities.length) * Math.PI * 2 - Math.PI / 2;
      const cx = W / 2 + (W * 0.35) * Math.cos(angle);
      const cy = H / 2 + (H * 0.35) * Math.sin(angle);
      const r = e.size || 16;
      const fill = catColors[e.category] || '#888';
      const id = this._uid();
      ids.push(id);
      g.addNode({
        id, x: cx - r, y: cy - r, width: r * 2, height: r * 2, shape: 'circle',
        attrs: {
          body: { fill, stroke: 'rgba(255,255,255,0.2)', strokeWidth: 1.5, opacity: 0.85 },
          label: { text: e.name, fill: '#d1d3db', fontSize: 9,
            fontFamily: '"Microsoft YaHei",sans-serif', refY: r + 10 },
        },
      });
    });

    edges.forEach(([a, b]) => {
      if (ids[a] && ids[b]) {
        g.addEdge({
          source: { cell: ids[a] }, target: { cell: ids[b] },
          attrs: { line: { stroke: 'rgba(255,255,255,0.1)', strokeWidth: 1, targetMarker: null } },
        });
      }
    });

    // Legend
    this._renderLegend(catColors);
    g.centerContent();
  },

  _renderLegend(catColors) {
    const legend = document.getElementById('graph-legend');
    if (!legend) return;
    legend.innerHTML = Object.entries(catColors).map(([k, v]) =>
      `<span class="x6-legend-item"><span class="x6-legend-dot" style="background:${v}"></span>${k}</span>`
    ).join('');
  },

  /* ═══════════════════════════════════════
     3. LIFECYCLE OBSERVATORY
     ═══════════════════════════════════════ */
  _renderLifecycle(data) {
    const g = this._graph;
    const stages = [
      { name: 'SENSE', icon: '👁️', desc: '接收输入', color: '#3f85ff' },
      { name: 'THINK', icon: '🧠', desc: 'TreeLLM路由', color: '#9570ff' },
      { name: 'PLAN', icon: '📋', desc: '任务规划', color: '#e28a00' },
      { name: 'EXEC', icon: '⚡', desc: '执行中', color: '#0fdc78' },
      { name: 'REFLECT', icon: '🔍', desc: '反思评估', color: '#00b8f8' },
      { name: 'LEARN', icon: '📚', desc: 'DGM-H进化', color: '#d1469e' },
      { name: 'EVOLVE', icon: '🧬', desc: '新规则生成', color: '#f65a5a' },
    ];

    const W = g.options.width, H = g.options.height;
    const cx = W / 2, cy = H / 2, radius = Math.min(W, H) * 0.35;

    const ids = [];
    let activeIdx = data?.active_stage || 1; // default THINK active

    stages.forEach((s, i) => {
      const angle = (i / stages.length) * Math.PI * 2 - Math.PI / 2;
      const x = cx + radius * Math.cos(angle) - 40;
      const y = cy + radius * Math.sin(angle) - 22;
      const isActive = i === activeIdx;
      const fill = isActive ? s.color : 'rgba(255,255,255,0.06)';
      const stroke = isActive ? s.color : 'rgba(255,255,255,0.12)';
      const id = this._uid();
      ids.push(id);
      g.addNode({
        id, x, y, width: 80, height: 44, shape: 'rect',
        attrs: {
          body: { fill, stroke, strokeWidth: isActive ? 2 : 1, rx: 8, ry: 8 },
          label: { text: `${s.icon}\n${s.name}`, fill: isActive ? '#fff' : '#9599a6',
            fontSize: 10, fontFamily: '"Microsoft YaHei",sans-serif', textAnchor: 'middle', textVerticalAnchor: 'middle' },
        },
      });
      if (isActive) {
        // Pulse animation via CSS class
        const el = g.findViewByCell(id);
        if (el) el.container.classList.add('x6-pulse');
      }
    });

    // Connect stages in cycle
    for (let i = 0; i < ids.length; i++) {
      const next = (i + 1) % ids.length;
      const isActiveEdge = i === activeIdx || (i + 1) % ids.length === activeIdx;
      g.addEdge({
        source: { cell: ids[i] }, target: { cell: ids[next] },
        attrs: {
          line: { stroke: isActiveEdge ? stages[activeIdx].color : 'rgba(255,255,255,0.1)',
            strokeWidth: isActiveEdge ? 2 : 1, targetMarker: { name: 'block', width: 6, height: 4 } },
        },
        router: { name: 'manhattan' },
      });
    }

    // Center node: current status
    const center = this._uid();
    g.addNode({
      id: center, x: cx - 40, y: cy - 40, width: 80, height: 80, shape: 'circle',
      attrs: {
        body: { fill: stages[activeIdx].color, stroke: 'rgba(255,255,255,0.3)', strokeWidth: 2 },
        label: { text: `Gen ${data?.gen || 0}\n${stages[activeIdx].desc}`,
          fill: '#fff', fontSize: 10, fontFamily: '"Microsoft YaHei",sans-serif' },
      },
    });

    g.centerContent();
  },

  /* ═══════════════════════════════════════
     5. ECONOMIC DECISION TREE
     ═══════════════════════════════════════ */
  _renderEconomic(data) {
    const g = this._graph;
    const policy = data?.policy || { name: 'BALANCED', cost: 0.33, speed: 0.33, quality: 0.34 };
    const models = data?.models || [
      { name: 'DeepSeek V4', price: 0.002, latency: 300, quality: 92, roi: 2.1 },
      { name: 'LongCat', price: 0.001, latency: 500, quality: 85, roi: 1.8 },
      { name: 'Qwen', price: 0.003, latency: 200, quality: 90, roi: 2.0 },
      { name: 'SiliconFlow', price: 0.0015, latency: 400, quality: 82, roi: 1.5 },
      { name: 'Zhipu', price: 0.004, latency: 150, quality: 88, roi: 1.6 },
    ];

    // Root: Policy
    const rootId = this._uid();
    this._rectNode(rootId, 150, 40, 160, 50,
      `📊 Policy: ${policy.name}\nC:${policy.cost} S:${policy.speed} Q:${policy.quality}`,
      'rgba(226,138,0,0.15)', '#e28a00');

    // Models as child nodes
    const selected = data?.selected || 0;
    const ids = [];
    models.forEach((m, i) => {
      const x = 80 + i * 180;
      const y = 200;
      const roiColor = m.roi >= 2.0 ? '#0fdc78' : m.roi >= 1.6 ? '#e28a00' : '#f65a5a';
      const isBest = i === selected;
      const fill = isBest ? 'rgba(15,220,120,0.2)' : 'rgba(255,255,255,0.04)';
      const stroke = isBest ? '#0fdc78' : 'rgba(255,255,255,0.12)';

      const id = this._uid();
      ids.push(id);
      g.addNode({
        id, x, y, width: 150, height: 80, shape: 'rect',
        attrs: {
          body: { fill, stroke, strokeWidth: isBest ? 2 : 1, rx: 6, ry: 6 },
          label: { text: `🤖 ${m.name}\n¥${m.price}/1K  ${m.latency}ms\n质量:${m.quality}  ROI:${m.roi}`,
            fill: '#d1d3db', fontSize: 10, fontFamily: '"Microsoft YaHei",sans-serif' },
        },
      });

      // Small bar charts for cost/speed/quality
      const barW = 130;
      ['cost', 'speed', 'quality'].forEach((attr, bi) => {
        const val = attr === 'cost' ? 1 - m.price / 0.005 : attr === 'speed' ? 1 - m.latency / 600 : m.quality / 100;
        const barId = this._uid();
        g.addNode({
          id: barId, x: x + 10, y: y + 56 + bi * 8, width: barW * Math.max(val, 0.05), height: 5,
          shape: 'rect',
          attrs: { body: { fill: roiColor, stroke: 'none', rx: 2, ry: 2, opacity: 0.7 } },
        });
      });

      this._edge(rootId, id, `ROI: ${m.roi}`, false);
    });

    g.centerContent();
  },

  /* ═══════════════════════════════════════
     6. RULE EVOLUTION TREE
     ═══════════════════════════════════════ */
  _renderRuleTree(data) {
    const g = this._graph;
    const tree = data?.tree || {
      name: 'check_safety', success: 0.85, children: [
        { name: 'v1: basic_check', success: 0.78 },
        { name: 'v2: enhanced', success: 0.92, children: [
          { name: 'v2.1: +context', success: 0.95 },
          { name: 'v2.2: +citations', success: 0.88 },
        ] },
        { name: 'v3: strict', success: 0.45 },
      ],
    };

    this._renderTreeNode(tree, g.options.width / 2 - 60, 30, 300, null, 0);
    g.centerContent();
  },

  _renderTreeNode(node, x, y, width, parentId, depth) {
    const g = this._graph;
    const succColor = node.success >= 0.9 ? '#0fdc78' : node.success >= 0.7 ? '#e28a00' : '#f65a5a';
    const id = this._uid();
    const h = 36;
    g.addNode({
      id, x: x - width / 2, y, width, height: h, shape: 'rect',
      attrs: {
        body: { fill: succColor + '20', stroke: succColor, strokeWidth: 1, rx: 4, ry: 4 },
        label: { text: `📜 ${node.name}  ${Math.round(node.success * 100)}%`,
          fill: '#d1d3db', fontSize: 10, fontFamily: '"Microsoft YaHei",sans-serif' },
      },
    });

    if (parentId) {
      g.addEdge({
        source: { cell: parentId }, target: { cell: id },
        attrs: { line: { stroke: succColor, strokeWidth: 1, strokeDasharray: depth > 1 ? '3 3' : '',
          targetMarker: { name: 'block', width: 5, height: 4 } } },
        labels: [{ attrs: { label: { text: `mut:${depth}`, fill: '#9599a6', fontSize: 8 } } }],
      });
    }

    if (node.children) {
      const childW = width / node.children.length;
      node.children.forEach((c, i) => {
        this._renderTreeNode(c, x - width / 2 + childW * (i + 0.5), y + 80, childW * 0.85, id, depth + 1);
      });
    }
  },

  /* ═══════════════════════════════════════
     7. TASK DEPENDENCY GRAPH (DAG)
     ═══════════════════════════════════════ */
  _renderTaskGraph(data) {
    const g = this._graph;
    const tasks = data?.tasks || [
      { id: 't1', name: '数据收集', status: 'done', layer: 0 },
      { id: 't2', name: '模型计算', status: 'done', layer: 0 },
      { id: 't3', name: '法规检索', status: 'running', layer: 0 },
      { id: 't4', name: '结果分析', status: 'pending', layer: 1 },
      { id: 't5', name: '报告生成', status: 'pending', layer: 2 },
    ];
    const deps = data?.deps || [['t1', 't4'], ['t2', 't4'], ['t3', 't4'], ['t4', 't5']];

    const statusColors = { done: '#0fdc78', running: '#3f85ff', pending: 'rgba(255,255,255,0.06)', failed: '#f65a5a' };
    const statusIcons = { done: '✅', running: '🔄', pending: '⏳', failed: '❌' };

    // Layout: group by layer
    const layers = {};
    tasks.forEach(t => {
      if (!layers[t.layer]) layers[t.layer] = [];
      layers[t.layer].push(t);
    });

    const maxPerLayer = Math.max(...Object.values(layers).map(l => l.length));
    const W = g.options.width;
    const layerX = (l) => W / (Object.keys(layers).length + 1) * (l + 1);

    const nodeMap = {};
    Object.entries(layers).forEach(([layer, layerTasks]) => {
      layerTasks.forEach((t, i) => {
        const lx = layerX(parseInt(layer));
        const ly = 60 + i * 100 + (maxPerLayer - layerTasks.length) * 30;
        const color = statusColors[t.status] || '#888';
        const icon = statusIcons[t.status] || '?';
        const id = this._uid();
        nodeMap[t.id] = id;
        g.addNode({
          id, x: lx - 55, y: ly, width: 110, height: 44, shape: 'rect',
          attrs: {
            body: { fill: color, stroke: 'rgba(255,255,255,0.15)', strokeWidth: 1.5, rx: 6, ry: 6, opacity: 0.9 },
            label: { text: `${icon} ${t.name}`, fill: t.status === 'pending' ? '#9599a6' : '#fff',
              fontSize: 10, fontFamily: '"Microsoft YaHei",sans-serif' },
          },
        });
      });
    });

    deps.forEach(([from, to]) => {
      if (nodeMap[from] && nodeMap[to]) {
        g.addEdge({
          source: { cell: nodeMap[from] }, target: { cell: nodeMap[to] },
          attrs: { line: { stroke: 'rgba(255,255,255,0.2)', strokeWidth: 1.5,
            targetMarker: { name: 'block', width: 6, height: 5 } } },
          router: { name: 'manhattan' },
        });
      }
    });

    g.centerContent();
  },

  /* ── Switch mode ── */
  switchMode(mode, data) {
    if (!this._graph) return;
    this._mode = mode;
    this._graph.clearCells();
    this._graph.resetSelection();
    document.getElementById('graph-legend') && (document.getElementById('graph-legend').innerHTML = '');

    switch (mode) {
      case 'pipeline': this._renderPipeline(data); break;
      case 'knowledge': this._renderKnowledgeGraph(data); break;
      case 'lifecycle': this._renderLifecycle(data); break;
      case 'economic': this._renderEconomic(data); break;
      case 'ruletree': this._renderRuleTree(data); break;
      case 'taskgraph': this._renderTaskGraph(data); break;
    }
  },

  /* ── Fetch data from backend ── */
  async fetchData(mode) {
    const endpoints = {
      pipeline: '/api/graph/pipeline',
      knowledge: '/api/graph/knowledge',
      lifecycle: '/api/graph/lifecycle',
      economic: '/api/graph/economic',
      ruletree: '/api/graph/ruletree',
      taskgraph: '/api/graph/tasks',
    };
    const url = endpoints[mode];
    if (!url) return null;
    try {
      const r = await fetch(url);
      if (r.ok) return await r.json();
    } catch (e) {}
    return null;
  },
};

window.X6Graph = X6Graph;
