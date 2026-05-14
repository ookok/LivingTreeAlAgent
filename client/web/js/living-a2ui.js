/* LivingTree A2UI Renderer — Dynamic JSON-to-Visual rendering engine.
 * 
 * Inspired by A2UI (Agent-to-User Interface) and json-render.
 * Decouples backend data from frontend rendering.
 * 
 * Auto-renders any .living-a2ui element on page load and HTMX swaps.
 * Supports: chart (ECharts), diagram (Mermaid), svg (direct), map (Leaflet), tree, metric.
 * 
 * Dependencies (loaded async): ECharts, Mermaid, Leaflet
 */

(function() {
  'use strict';

  const A2UI = {
    loaded: { echarts: false, mermaid: false, leaflet: false },
    queue: [],

    init() {
      this.loadDependencies();
      this.observe();
      this.scan();

      // Listen for HTMX swaps
      document.addEventListener('htmx:afterSwap', () => this.scan());
      document.addEventListener('htmx:afterSettle', () => this.scan());
    },

    loadDependencies() {
      // ECharts
      if (typeof echarts === 'undefined') {
        const s = document.createElement('script');
        s.src = 'https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js';
        s.onload = () => { this.loaded.echarts = true; this.flush(); };
        document.head.appendChild(s);
      } else { this.loaded.echarts = true; }

      // Mermaid
      if (typeof mermaid === 'undefined') {
        const s = document.createElement('script');
        s.src = 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js';
        s.onload = () => { 
          mermaid.initialize({ startOnLoad: false, theme: 'default' });
          this.loaded.mermaid = true; 
          this.flush(); 
        };
        document.head.appendChild(s);
      } else { this.loaded.mermaid = true; }

      // Leaflet (for maps only)
      if (typeof L === 'undefined' && document.querySelector('[data-a2ui-type="map"]')) {
        const css = document.createElement('link');
        css.rel = 'stylesheet';
        css.href = 'https://cdn.jsdelivr.net/npm/leaflet@1.9/dist/leaflet.min.css';
        document.head.appendChild(css);
        const s = document.createElement('script');
        s.src = 'https://cdn.jsdelivr.net/npm/leaflet@1.9/dist/leaflet.min.js';
        s.onload = () => { this.loaded.leaflet = true; this.flush(); };
        document.head.appendChild(s);
      } else { this.loaded.leaflet = true; }
    },

    scan() {
      document.querySelectorAll('.living-a2ui:not([data-a2ui-rendered])').forEach(el => {
        const type = el.dataset.a2uiType;
        if (!type) return;
        el.dataset.a2uiRendered = '1';

        if (type === 'chart' || type === 'tree') {
          if (this.loaded.echarts) this.renderChart(el);
          else this.queue.push(() => this.renderChart(el));
        } else if (type === 'diagram') {
          if (this.loaded.mermaid) this.renderDiagram(el);
          else this.queue.push(() => this.renderDiagram(el));
        } else if (type === 'map') {
          if (this.loaded.leaflet) this.renderMap(el);
          else this.queue.push(() => this.renderMap(el));
        } else if (type === 'svg') {
          this.renderSVG(el);
        }
      });
    },

    flush() {
      while (this.queue.length > 0) {
        try { this.queue.shift()(); } catch(e) {}
      }
    },

    observe() {
      if (typeof MutationObserver === 'undefined') return;
      new MutationObserver(() => this.scan()).observe(document.body, {
        childList: true, subtree: true,
      });
    },

    // ── Renderers ──────────────────────────────────────────────

    renderChart(el) {
      try {
        const config = JSON.parse(el.dataset.a2uiChart || '{}');
        const chartId = el.querySelector('div[id]')?.id || ('chart_' + Math.random().toString(36).slice(2));
        const chartDom = el.querySelector('#' + chartId) || el;

        // Handle tree type
        if (config.type === 'tree') {
          this.renderTree(chartDom, config.data);
          return;
        }

        const myChart = echarts.init(chartDom);
        const type = config.type || 'bar';
        const data = config.data || {};
        const options = config.options || {};

        const echartsOption = {
          title: { text: options.title || '', left: 'center', textStyle: { fontSize: 14 } },
          tooltip: {},
          xAxis: type === 'bar' || type === 'line' ? { 
            type: 'category', data: data.labels || [], 
            axisLabel: { rotate: data.labels && data.labels.length > 6 ? 45 : 0 }
          } : (type === 'scatter' ? { type: 'value' } : undefined),
          yAxis: { type: 'value' },
          series: (data.datasets || [{ data: data.values || [] }]).map((ds, i) => ({
            name: ds.label || '',
            type: type,
            data: ds.data || [],
            smooth: type === 'line',
            ...(type === 'pie' ? {
              radius: '60%',
              center: ['50%', '55%'],
              data: (ds.data || []).map((v, j) => ({ 
                value: v, name: (data.labels || [])[j] || '' + j 
              })),
            } : {}),
            ...(type === 'scatter' ? {
              data: (ds.data || []).map((v, j) => [v, (ds.data || [])[j + 1] || v]),
            } : {}),
          })),
        };

        if (type === 'pie') {
          delete echartsOption.xAxis;
          delete echartsOption.yAxis;
        }

        myChart.setOption(echartsOption);
        window.addEventListener('resize', () => myChart.resize());
      } catch(e) {
        el.innerHTML = '<div style="color:#999;padding:8px;">图表渲染失败: ' + e.message + '</div>';
      }
    },

    renderTree(el, data) {
      const myChart = echarts.init(el);
      myChart.setOption({
        tooltip: { trigger: 'item' },
        series: [{
          type: 'tree',
          data: [data],
          top: '5%', left: '8%', bottom: '5%', right: '20%',
          symbolSize: 8,
          orient: 'LR',
          label: { fontSize: 11 },
          leaves: { label: { fontSize: 9 } },
        }]
      });
    },

    renderDiagram(el) {
      try {
        const code = el.querySelector('.mermaid')?.textContent || el.textContent || '';
        const id = 'mermaid_' + Math.random().toString(36).slice(2);
        el.innerHTML = '<div id="' + id + '">' + code + '</div>';
        mermaid.run({ nodes: [document.getElementById(id)] });
      } catch(e) {
        el.innerHTML = '<pre style="color:#999;padding:8px;">' + 
          (el.textContent || '') + '</pre>';
      }
    },

    renderSVG(el) {
      // SVG is already inline, just ensure proper sizing
      const svg = el.querySelector('svg');
      if (svg) {
        svg.style.maxWidth = '100%';
        svg.style.height = 'auto';
      }
    },

    renderMap(el) {
      try {
        const config = JSON.parse(el.dataset.a2uiMap || '{}');
        const map = L.map(el).setView([config.lat || 31.2, config.lon || 118.8], config.zoom || 12);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
          maxZoom: 18, attribution: 'OSM'
        }).addTo(map);
        (config.markers || []).forEach(m => {
          L.marker([m.lat, m.lon]).addTo(map).bindPopup(m.label || '');
        });
        if (config.polygons) {
          config.polygons.forEach(p => {
            L.polygon(p.coords, {color: p.color || '#3f85ff'}).addTo(map);
          });
        }
      } catch(e) {
        el.innerHTML = '<div style="color:#999;padding:8px;">地图渲染需 Leaflet</div>';
      }
    }
  };

  // Auto-init
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => A2UI.init());
  } else {
    A2UI.init();
  }

  window.LivingA2UI = A2UI;
})();
