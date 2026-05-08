/* ═══════════════════════════════════
   LivingTree — X6 Report Diagram Engine
   7 diagram types for industrial report generation
   ═══════════════════════════════════ */

const X6Diagram = {
  _graph: null,
  _type: null,
  _data: null,

  init(containerId) {
    if (!window.X6) return;
    this.destroy();
    this._graph = new X6.Graph({
      container: document.getElementById(containerId),
      width: 900, height: 600,
      grid: { size: 10, visible: true, type: 'dot', args: { color: 'rgba(255,255,255,0.03)' } },
      panning: { enabled: true, modifiers: 'shift' },
      mousewheel: { enabled: true, modifiers: 'ctrl', factor: 1.1 },
      snapline: true,
      background: { color: '#fafbfc' },
    });
    this._graph.centerContent();
  },

  destroy() {
    if (this._graph) { this._graph.dispose(); this._graph = null; }
  },

  _uid() { return 'd' + Math.random().toString(36).slice(2, 8); },

  /* ═══════════════════════════════════════
     1. CONTAMINANT PLUME CONTOUR MAP
     高斯烟羽污染扩散等值线图
     ═══════════════════════════════════════ */
  renderContourMap(data) {
    const g = this._graph;
    const d = data || {};
    const W = 800, H = 500, margin = 60;
    const sourceX = d.source_x || 200, sourceY = d.source_y || H / 2;
    const windDir = d.wind_dir || 0; // degrees, 0 = →

    // Background: coordinate grid
    for (let x = margin; x <= W - margin; x += 60) {
      g.addNode({
        shape: 'rect', x, y: margin, width: 1, height: H - 2 * margin,
        attrs: { body: { fill: 'none', stroke: '#e0e0e0', strokeWidth: 0.5 } },
      });
    }
    for (let y = margin; y <= H - margin; y += 60) {
      g.addNode({
        shape: 'rect', x: margin, y, width: W - 2 * margin, height: 1,
        attrs: { body: { fill: 'none', stroke: '#e0e0e0', strokeWidth: 0.5 } },
      });
    }

    // Pollution source
    g.addNode({
      shape: 'circle', x: sourceX - 12, y: sourceY - 12, width: 24, height: 24,
      attrs: {
        body: { fill: '#e8463a', stroke: '#fff', strokeWidth: 2 },
        label: { text: '源', fill: '#fff', fontSize: 10, fontWeight: 'bold', fontFamily: 'sans-serif' },
      },
    });

    // Plume contours (ellipses)
    const concentrations = d.concentrations || [0.8, 0.5, 0.2, 0.08, 0.02];
    const colors = ['rgba(232,70,58,0.35)', 'rgba(226,138,0,0.3)', 'rgba(250,173,20,0.2)', 'rgba(103,194,58,0.15)', 'rgba(63,133,255,0.08)'];
    concentrations.forEach((c, i) => {
      const rx = 30 + i * 50 + c * 40;
      const ry = 15 + i * 18 + c * 18;
      g.addNode({
        shape: 'ellipse',
        x: sourceX - rx + windDir * 0.1,
        y: sourceY - ry,
        width: rx * 2, height: ry * 2,
        attrs: {
          body: { fill: colors[i], stroke: colors[i].replace('0.3', '0.6').replace('0.2', '0.5').replace('0.15', '0.4').replace('0.08', '0.3').replace('0.35', '0.7'), strokeWidth: 1 },
          label: { text: `${Math.round(c * 100)}%`, fill: '#666', fontSize: 9, refY: ry + 8 },
        },
      });
    });

    // Wind arrow
    g.addEdge({
      source: { x: sourceX - 80, y: sourceY - 60 },
      target: { x: sourceX + 40, y: sourceY - 60 },
      attrs: {
        line: { stroke: '#3f85ff', strokeWidth: 2, targetMarker: { name: 'block', width: 8, height: 6 } },
      },
      labels: [{ attrs: { label: { text: `风向 ${windDir}° 风速 ${d.wind_speed || 3.5}m/s`, fill: '#3f85ff', fontSize: 10 } }, position: -20 }],
    });

    // Sensitive receptors
    (d.receptors || [{ x: 500, y: 200, name: '居民区A' }, { x: 550, y: 320, name: '学校B' }]).forEach(r => {
      g.addNode({
        shape: 'rect', x: r.x - 20, y: r.y - 14, width: 40, height: 28,
        attrs: {
          body: { fill: '#fff', stroke: '#f65a5a', strokeWidth: 1.5, rx: 4, ry: 4 },
          label: { text: r.name, fill: '#f65a5a', fontSize: 9, fontFamily: 'sans-serif' },
        },
      });
    });

    // Legend
    this._addMapLegend();
    g.centerContent();
  },

  _addMapLegend() {
    const g = this._graph;
    const items = [
      { color: '#e8463a', label: '高浓度区 (>50%)' },
      { color: '#e28a00', label: '中浓度区 (20-50%)' },
      { color: '#67c23a', label: '低浓度区 (5-20%)' },
      { color: '#3f85ff', label: '扩散边缘 (<5%)' },
    ];
    items.forEach((item, i) => {
      g.addNode({
        shape: 'rect', x: 630, y: 60 + i * 28, width: 14, height: 14,
        attrs: { body: { fill: item.color, stroke: 'none', rx: 2 } },
      });
      g.addNode({
        shape: 'rect', x: 650, y: 60 + i * 28 - 2, width: 120, height: 18,
        attrs: {
          body: { fill: 'none', stroke: 'none' },
          label: { text: item.label, fill: '#666', fontSize: 10, fontFamily: 'sans-serif', textAnchor: 'start' },
        },
      });
    });
  },

  /* ═══════════════════════════════════════
     2. PROCESS FLOW DIAGRAM
     工艺流程图 (PFD) with equipment symbols
     ═══════════════════════════════════════ */
  renderProcessFlow(data) {
    const g = this._graph;
    const nodes = data.nodes || [
      { id: 'raw', label: '原料罐', x: 80, y: 280, w: 80, h: 60, color: '#3f85ff', shape: 'cylinder' },
      { id: 'reactor', label: '反应釜\nR-101', x: 250, y: 260, w: 100, h: 80, color: '#e28a00', shape: 'vessel' },
      { id: 'heat', label: '换热器\nE-201', x: 440, y: 270, w: 70, h: 70, color: '#9570ff', shape: 'exchanger' },
      { id: 'separator', label: '分离塔\nT-301', x: 600, y: 240, w: 60, h: 120, color: '#0fdc78', shape: 'column' },
      { id: 'product', label: '产品罐', x: 760, y: 280, w: 80, h: 60, color: '#00b8f8', shape: 'cylinder' },
    ];
    const edges = data.edges || [
      { from: 'raw', to: 'reactor', label: '进料' },
      { from: 'reactor', to: 'heat', label: '反应物' },
      { from: 'heat', to: 'separator', label: '混合物' },
      { from: 'separator', to: 'product', label: '产品' },
    ];

    const nodeMap = {};
    nodes.forEach(n => {
      let node;
      if (n.shape === 'cylinder') {
        node = g.addNode({
          shape: 'rect', x: n.x, y: n.y, width: n.w, height: n.h,
          attrs: {
            body: { fill: n.color + '18', stroke: n.color, strokeWidth: 2, rx: n.w / 2, ry: 8 },
            label: { text: n.label, fill: '#333', fontSize: 11, fontFamily: 'sans-serif' },
          },
        });
      } else if (n.shape === 'vessel') {
        node = g.addNode({
          shape: 'rect', x: n.x, y: n.y, width: n.w, height: n.h,
          attrs: {
            body: { fill: n.color + '15', stroke: n.color, strokeWidth: 2, rx: 6, ry: 6 },
            label: { text: n.label, fill: '#333', fontSize: 11, fontFamily: 'sans-serif' },
          },
        });
      } else {
        node = g.addNode({
          shape: 'rect', x: n.x, y: n.y, width: n.w, height: n.h,
          attrs: {
            body: { fill: n.color + '12', stroke: n.color, strokeWidth: 2, rx: 4, ry: 4 },
            label: { text: n.label, fill: '#333', fontSize: 10, fontFamily: 'sans-serif' },
          },
        });
      }
      nodeMap[n.id] = node;

      // Ports for connections
      node.addPorts([
        { group: 'in', args: { x: 0, y: n.h / 2 } },
        { group: 'out', args: { x: n.w, y: n.h / 2 } },
      ]);
    });

    edges.forEach(e => {
      if (nodeMap[e.from] && nodeMap[e.to]) {
        g.addEdge({
          source: { cell: nodeMap[e.from].id },
          target: { cell: nodeMap[e.to].id },
          attrs: {
            line: { stroke: '#555', strokeWidth: 2, targetMarker: { name: 'block', width: 8, height: 6 } },
          },
          labels: e.label ? [{ attrs: { label: { text: e.label, fill: '#888', fontSize: 10 } }, position: 0.5 }] : [],
        });
      }
    });

    g.centerContent();
  },

  /* ═══════════════════════════════════════
     3. SITE LAYOUT PLAN
     平面布置图 — monitoring points, sources, receptors
     ═══════════════════════════════════════ */
  renderSitePlan(data) {
    const g = this._graph;
    const W = 800, H = 550;

    // Grid background
    for (let x = 0; x <= W; x += 50) {
      g.addEdge({
        source: { x, y: 0 }, target: { x, y: H },
        attrs: { line: { stroke: '#f0f0f0', strokeWidth: 0.5 } },
      });
    }
    for (let y = 0; y <= H; y += 50) {
      g.addEdge({
        source: { x: 0, y }, target: { x: W, y },
        attrs: { line: { stroke: '#f0f0f0', strokeWidth: 0.5 } },
      });
    }

    // Site boundary
    const bx = 60, by = 50, bw = 680, bh = 450;
    g.addNode({
      shape: 'rect', x: bx, y: by, width: bw, height: bh,
      attrs: { body: { fill: 'rgba(15,220,120,0.04)', stroke: '#0fdc78', strokeWidth: 2, strokeDasharray: '8 4', rx: 0 } },
    });
    this._addLabel(g, bx + bw / 2, by - 10, '厂区边界', '#0fdc78', 10);

    // Buildings
    (data.buildings || [
      { x: 100, y: 120, w: 80, h: 50, label: '车间A' },
      { x: 220, y: 120, w: 60, h: 50, label: '车间B' },
      { x: 100, y: 300, w: 70, h: 40, label: '仓库' },
      { x: 400, y: 150, w: 90, h: 60, label: '办公区' },
    ]).forEach(b => {
      g.addNode({
        shape: 'rect', x: b.x, y: b.y, width: b.w, height: b.h,
        attrs: {
          body: { fill: '#f5f5f5', stroke: '#bbb', strokeWidth: 1.5, rx: 2, ry: 2 },
          label: { text: b.label, fill: '#555', fontSize: 10, fontFamily: 'sans-serif' },
        },
      });
    });

    // Emission sources (smokestacks)
    (data.sources || [
      { x: 140, y: 100, label: '排气筒1\nH=30m' },
      { x: 250, y: 100, label: '排气筒2\nH=20m' },
    ]).forEach(s => {
      g.addNode({
        shape: 'rect', x: s.x - 22, y: s.y - 18, width: 44, height: 36,
        attrs: {
          body: { fill: '#e8463a', stroke: '#fff', strokeWidth: 1.5, rx: 4, ry: 4 },
          label: { text: s.label, fill: '#fff', fontSize: 9, fontFamily: 'sans-serif' },
        },
      });
    });

    // Monitoring points
    (data.monitors || [
      { x: 200, y: 250, label: 'A1' },
      { x: 350, y: 400, label: 'A2' },
      { x: 500, y: 300, label: 'A3' },
      { x: 600, y: 180, label: 'A4' },
    ]).forEach(m => {
      g.addNode({
        shape: 'circle', x: m.x - 10, y: m.y - 10, width: 20, height: 20,
        attrs: {
          body: { fill: '#3f85ff', stroke: '#fff', strokeWidth: 1.5 },
          label: { text: m.label, fill: '#fff', fontSize: 9, fontWeight: 'bold', fontFamily: 'sans-serif' },
        },
      });
    });

    // Scale bar
    g.addEdge({
      source: { x: bx + 10, y: bh + by - 22 },
      target: { x: bx + 110, y: bh + by - 22 },
      attrs: { line: { stroke: '#333', strokeWidth: 2 } },
    });
    this._addLabel(g, bx + 60, bh + by - 10, '100m', '#333', 9);

    g.centerContent();
  },

  _addLabel(g, x, y, text, color, size) {
    g.addNode({
      shape: 'rect', x: x - (text.length * size * 0.3), y: y - size / 2, width: text.length * size * 0.6, height: size * 1.5,
      attrs: {
        body: { fill: 'transparent', stroke: 'none' },
        label: { text, fill: color, fontSize: size, fontFamily: 'sans-serif' },
      },
    });
  },

  /* ═══════════════════════════════════════
     4. NOISE ATTENUATION PROFILE
     噪声衰减距离-分贝剖面图
     ═══════════════════════════════════════ */
  renderNoiseProfile(data) {
    const g = this._graph;
    const W = 800, H = 450, margin = 60;
    const benchmarks = data.benchmarks || [
      { dist: 0, db: 95 }, { dist: 50, db: 85 }, { dist: 100, db: 78 },
      { dist: 200, db: 70 }, { dist: 400, db: 62 }, { dist: 800, db: 54 },
    ];
    const limits = data.limits || [
      { label: '昼间标准 65dB', db: 65, color: '#e28a00' },
      { label: '夜间标准 55dB', db: 55, color: '#3f85ff' },
    ];

    const plotW = W - 2 * margin, plotH = H - 2 * margin;
    const maxDb = 100, maxDist = Math.max(...benchmarks.map(b => b.dist)) * 1.2;
    const toX = (d) => margin + (d / maxDist) * plotW;
    const toY = (db) => margin + plotH - (db / maxDb) * plotH;

    // Axes
    g.addEdge({ source: { x: margin, y: margin }, target: { x: margin, y: H - margin }, attrs: { line: { stroke: '#333', strokeWidth: 1.5 } } });
    g.addEdge({ source: { x: margin, y: H - margin }, target: { x: W - margin, y: H - margin }, attrs: { line: { stroke: '#333', strokeWidth: 1.5 } } });
    this._addLabel(g, W / 2, H - 18, '距离 (m)', '#555', 11);
    this._addLabel(g, 12, H / 2, '声压级 (dB)', '#555', 11);

    // Grid lines
    for (let db = 20; db <= 100; db += 20) {
      g.addEdge({
        source: { x: margin, y: toY(db) }, target: { x: W - margin, y: toY(db) },
        attrs: { line: { stroke: '#eee', strokeWidth: 0.5, strokeDasharray: '4 4' } },
      });
      this._addLabel(g, margin - 20, toY(db) + 2, String(db), '#999', 9);
    }
    for (let d = 200; d <= maxDist; d += 200) {
      g.addEdge({
        source: { x: toX(d), y: margin }, target: { x: toX(d), y: H - margin },
        attrs: { line: { stroke: '#eee', strokeWidth: 0.5, strokeDasharray: '4 4' } },
      });
      this._addLabel(g, toX(d), H - margin + 12, String(d), '#999', 9);
    }

    // Limit lines
    limits.forEach(l => {
      g.addEdge({
        source: { x: margin, y: toY(l.db) }, target: { x: W - margin, y: toY(l.db) },
        attrs: { line: { stroke: l.color, strokeWidth: 1, strokeDasharray: '6 3' } },
        labels: [{ attrs: { label: { text: l.label, fill: l.color, fontSize: 9 } }, position: 0.8 }],
      });
    });

    // Noise curve (polyline via edges)
    for (let i = 0; i < benchmarks.length - 1; i++) {
      g.addEdge({
        source: { x: toX(benchmarks[i].dist), y: toY(benchmarks[i].db) },
        target: { x: toX(benchmarks[i + 1].dist), y: toY(benchmarks[i + 1].db) },
        attrs: { line: { stroke: '#e8463a', strokeWidth: 2, targetMarker: null } },
      });
    }

    // Data points
    benchmarks.forEach((b, i) => {
      g.addNode({
        shape: 'circle', x: toX(b.dist) - 5, y: toY(b.db) - 5, width: 10, height: 10,
        attrs: { body: { fill: '#e8463a', stroke: '#fff', strokeWidth: 1.5 } },
      });
      this._addLabel(g, toX(b.dist), toY(b.db) - 12, `${b.db}dB`, '#e8463a', 9);
    });

    g.centerContent();
  },

  /* ═══════════════════════════════════════
     5. MONITORING NETWORK TOPOLOGY
     监测网络拓扑图
     ═══════════════════════════════════════ */
  renderMonitoringNet(data) {
    const g = this._graph;
    const W = 800, H = 500;

    const stations = data.stations || [
      { id: 'center', x: 400, y: 250, label: '监测中心', color: '#0fdc78', size: 20, type: 'center' },
      { id: 'aq1', x: 150, y: 120, label: '空气站 A1\nPM2.5/PM10/SO₂', color: '#3f85ff', size: 14, type: 'air' },
      { id: 'aq2', x: 650, y: 100, label: '空气站 A2\nPM2.5/O₃/NOx', color: '#3f85ff', size: 14, type: 'air' },
      { id: 'wq1', x: 200, y: 380, label: '水站 W1\nCOD/NH₃-N/pH', color: '#00b8f8', size: 14, type: 'water' },
      { id: 'wq2', x: 600, y: 380, label: '水站 W2\nDO/BOD/TP', color: '#00b8f8', size: 14, type: 'water' },
      { id: 'noise1', x: 400, y: 100, label: '噪声 N1\nLeq/L10/L90', color: '#e28a00', size: 12, type: 'noise' },
      { id: 'noise2', x: 400, y: 420, label: '噪声 N2\nLeq/Lmax', color: '#e28a00', size: 12, type: 'noise' },
    ];

    const connections = data.connections || [
      ['center', 'aq1'], ['center', 'aq2'], ['center', 'wq1'], ['center', 'wq2'],
      ['center', 'noise1'], ['center', 'noise2'],
      ['aq1', 'aq2'], ['wq1', 'wq2'],
    ];

    const nodeMap = {};
    stations.forEach(s => {
      const r = s.size;
      const node = g.addNode({
        shape: s.type === 'center' ? 'rect' : 'circle',
        x: s.x - (s.type === 'center' ? 40 : r),
        y: s.y - (s.type === 'center' ? 22 : r),
        width: s.type === 'center' ? 80 : r * 2,
        height: s.type === 'center' ? 44 : r * 2,
        attrs: {
          body: { fill: s.color + '20', stroke: s.color, strokeWidth: s.type === 'center' ? 2.5 : 1.5 },
          label: { text: s.label, fill: '#333', fontSize: s.type === 'center' ? 11 : 9, fontFamily: 'sans-serif' },
        },
      });
      nodeMap[s.id] = node;
    });

    connections.forEach(([a, b]) => {
      if (nodeMap[a] && nodeMap[b]) {
        const isMajor = a === 'center' || b === 'center';
        g.addEdge({
          source: { cell: nodeMap[a].id }, target: { cell: nodeMap[b].id },
          attrs: {
            line: { stroke: isMajor ? '#0fdc78' : 'rgba(15,220,120,0.3)',
              strokeWidth: isMajor ? 2 : 1, strokeDasharray: isMajor ? '' : '4 4',
              targetMarker: isMajor ? { name: 'block', width: 6, height: 5 } : null },
          },
        });
      }
    });

    g.centerContent();
  },

  /* ═══════════════════════════════════════
     6. EIA CAUSAL CHAIN
     环境影响因果链图
     ═══════════════════════════════════════ */
  renderCausalChain(data) {
    const g = this._graph;
    const W = 800;
    const chain = data.chain || [
      { layer: 0, items: [{ id: 'c1', label: '施工活动\n挖掘/打桩', color: '#e28a00' }] },
      { layer: 1, items: [
        { id: 'i1', label: '扬尘排放\nTSP/PM10', color: '#f65a5a' },
        { id: 'i2', label: '噪声影响\n施工机械', color: '#f65a5a' },
        { id: 'i3', label: '废水排放\n泥浆水', color: '#f65a5a' },
      ] },
      { layer: 2, items: [
        { id: 'r1', label: '居民区\n敏感目标', color: '#9570ff' },
        { id: 'r2', label: '地表水\n河流XX', color: '#3f85ff' },
        { id: 'r3', label: '大气环境', color: '#3f85ff' },
      ] },
      { layer: 3, items: [
        { id: 'm1', label: '洒水降尘\n围挡+覆盖', color: '#0fdc78' },
        { id: 'm2', label: '低噪设备\n隔声屏障', color: '#0fdc78' },
        { id: 'm3', label: '沉淀池\n循环利用', color: '#0fdc78' },
      ] },
    ];

    const layerLabels = ['活动', '影响', '受体', '措施'];
    const layerColors = ['#e28a00', '#f65a5a', '#9570ff', '#0fdc78'];
    const nodeMap = {};
    let maxItems = Math.max(...chain.map(l => l.items.length));
    const layerW = W / chain.length;

    chain.forEach((layer, li) => {
      const x = layerW * li + layerW / 2;
      const items = layer.items;
      const startY = 80 + (4 - items.length) * 30;

      // Layer header
      this._addLabel(g, x, 30, layerLabels[li], layerColors[li], 14);

      items.forEach((item, ii) => {
        const y = startY + ii * 90;
        const node = g.addNode({
          shape: 'rect', x: x - 60, y, width: 120, height: 50,
          attrs: {
            body: { fill: item.color + '15', stroke: item.color, strokeWidth: 1.5, rx: 6, ry: 6 },
            label: { text: item.label, fill: '#333', fontSize: 10, fontFamily: 'sans-serif' },
          },
        });
        nodeMap[item.id] = node;
      });
    });

    // Connect all possible causal links
    for (let i = 0; i < chain.length - 1; i++) {
      const fromLayer = chain[i];
      const toLayer = chain[i + 1];
      fromLayer.items.forEach(fi => {
        toLayer.items.forEach(ti => {
          if (nodeMap[fi.id] && nodeMap[ti.id]) {
            g.addEdge({
              source: { cell: nodeMap[fi.id].id },
              target: { cell: nodeMap[ti.id].id },
              attrs: {
                line: { stroke: 'rgba(0,0,0,0.15)', strokeWidth: 1,
                  strokeDasharray: Math.random() > 0.5 ? '' : '3 3',
                  targetMarker: { name: 'block', width: 5, height: 4 } },
              },
            });
          }
        });
      });
    }

    g.centerContent();
  },

  /* ═══════════════════════════════════════
     7. RISK ASSESSMENT MATRIX
     风险评价矩阵 — probability × consequence
     ═══════════════════════════════════════ */
  renderRiskMatrix(data) {
    const g = this._graph;
    const cell = 70, margin = 80;
    const probLabels = ['极低', '低', '中', '高', '极高'];
    const consLabels = ['轻微', '一般', '较大', '重大', '特别重大'];

    // Grid
    for (let p = 0; p < 5; p++) {
      for (let c = 0; c < 5; c++) {
        const score = (p + 1) * (c + 1);
        const fill = score <= 4 ? 'rgba(103,194,58,0.3)'
          : score <= 8 ? 'rgba(250,173,20,0.3)'
          : score <= 12 ? 'rgba(226,138,0,0.3)'
          : score <= 16 ? 'rgba(232,70,58,0.2)'
          : 'rgba(232,70,58,0.4)';

        g.addNode({
          shape: 'rect',
          x: margin + c * cell, y: margin + p * cell,
          width: cell, height: cell,
          attrs: {
            body: { fill, stroke: '#ddd', strokeWidth: 1 },
            label: { text: `P${p + 1}C${c + 1}`, fill: '#666', fontSize: 10, fontFamily: 'sans-serif' },
          },
        });
      }
    }

    // Axis labels
    probLabels.forEach((l, i) => this._addLabel(g, margin - 30, margin + i * cell + cell / 2, l, '#555', 10));
    consLabels.forEach((l, i) => this._addLabel(g, margin + i * cell + cell / 2, margin - 16, l, '#555', 9));
    this._addLabel(g, margin - 40, margin - 30, '概率↑', '#333', 12);
    this._addLabel(g, margin + 5 * cell / 2, margin - 40, '后果严重程度 →', '#333', 12);

    // Risk items
    (data.risks || [
      { id: 'r1', label: '化学品泄漏', prob: 2, cons: 3, color: '#e28a00' },
      { id: 'r2', label: '设备故障', prob: 3, cons: 2, color: '#e28a00' },
      { id: 'r3', label: '火灾爆炸', prob: 1, cons: 5, color: '#e8463a' },
      { id: 'r4', label: '噪声扰民', prob: 4, cons: 1, color: '#3f85ff' },
    ]).forEach(r => {
      const x = margin + (r.cons - 1) * cell + cell / 2;
      const y = margin + (r.prob - 1) * cell + cell / 2;
      g.addNode({
        shape: 'circle', x: x - 10, y: y - 10, width: 20, height: 20,
        attrs: {
          body: { fill: 'transparent', stroke: r.color, strokeWidth: 2.5 },
          label: { text: r.label, fill: r.color, fontSize: 9, fontFamily: 'sans-serif', refY: -14 },
        },
      });
    });

    // Legend
    const legend = [
      { color: 'rgba(103,194,58,0.6)', label: '可接受' },
      { color: 'rgba(250,173,20,0.6)', label: '需关注' },
      { color: 'rgba(226,138,0,0.6)', label: '需整改' },
      { color: 'rgba(232,70,58,0.5)', label: '不可接受' },
    ];
    legend.forEach((l, i) => {
      g.addNode({
        shape: 'rect', x: margin + 370, y: margin + i * 28, width: 16, height: 16,
        attrs: { body: { fill: l.color, stroke: 'none', rx: 2 } },
      });
      this._addLabel(g, margin + 410, margin + i * 28 + 8, l.label, '#555', 10);
    });

    g.centerContent();
  },

  /* ── Render by type ── */
  render(type, data) {
    if (!this._graph) return;
    this._type = type; this._data = data;
    this._graph.clearCells();
    switch (type) {
      case 'contour': this.renderContourMap(data); break;
      case 'process-flow': this.renderProcessFlow(data); break;
      case 'site-plan': this.renderSitePlan(data); break;
      case 'noise': this.renderNoiseProfile(data); break;
      case 'monitoring': this.renderMonitoringNet(data); break;
      case 'causal': this.renderCausalChain(data); break;
      case 'risk': this.renderRiskMatrix(data); break;
    }
  },

  /* ── Export diagram ── */
  exportSVG(callback) {
    if (!this._graph) return;
    this._graph.toSVG((svg) => callback(svg), { preserveDimensions: true });
  },

  exportPNG(callback) {
    if (!this._graph) return;
    this._graph.toPNG((dataUri) => callback(dataUri), { padding: 16, backgroundColor: '#ffffff' });
  },
};

window.X6Diagram = X6Diagram;
