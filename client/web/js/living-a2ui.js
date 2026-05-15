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
        } else if (type === 'tailwind') {
          this.renderTailwind(el);
        }
      });
    },

    renderTailwind(el) {
      const comp = el.dataset.a2uiComponent;
      const props = JSON.parse(el.dataset.a2uiProps || '{}');
      let html = '';
      try {
        if (comp === 'Card') html = this._twCard(props);
        else if (comp === 'Table') html = this._twTable(props);
        else if (comp === 'Alert') html = this._twAlert(props);
        else if (comp === 'Badge') html = this._twBadge(props);
        else if (comp === 'Button') html = this._twButton(props);
        else if (comp === 'Form') html = this._twForm(props);
        else if (comp === 'Tabs') html = this._twTabs(props);
        else if (comp === 'Spinner') html = '<div class="w-8 h-8 animate-spin rounded-full border-2 border-gray-300 border-t-blue-600 mx-auto"></div>';
        else html = `<div class="text-gray-500 text-sm p-4">Unknown component: ${comp}</div>`;
      } catch(e) { html = `<div class="text-red-500 text-sm">Render error: ${e.message}</div>`; }
      el.innerHTML = html;
    },

    _twCard(p) {
      const accent = {blue:'border-l-4 border-blue-500',green:'border-l-4 border-green-500',red:'border-l-4 border-red-500'}[p.accent]||'';
      return `<div class="bg-white rounded-xl shadow-sm ${accent} p-5 mb-4">
        ${p.title?`<h3 class="text-lg font-semibold text-gray-800 mb-3">${this._esc(p.title)}</h3>`:''}
        <div class="text-gray-600">${Array.isArray(p.children)?p.children.join(''):p.children||''}</div>
        ${p.footer?`<div class="mt-4 pt-3 border-t border-gray-100 text-sm text-gray-500">${p.footer}</div>`:''}
      </div>`;
    },
    _twTable(p) {
      const cols = (p.columns||[]).map(c=>`<th class="px-4 py-2 text-left font-medium text-gray-600">${this._esc(c)}</th>`).join('');
      const rows = (p.rows||[]).map(r=>`<tr class="border-b">${r.map(c=>`<td class="px-4 py-2 text-gray-700">${this._esc(String(c))}</td>`).join('')}</tr>`).join('');
      return `<div class="overflow-x-auto"><table class="w-full text-sm"><thead><tr class="bg-gray-50 border-b">${cols}</tr></thead><tbody>${rows}</tbody></table></div>`;
    },
    _twAlert(p) {
      const levels={info:'bg-blue-50 border-blue-200 text-blue-800',success:'bg-green-50 border-green-200 text-green-800',warning:'bg-yellow-50 border-yellow-200 text-yellow-800',error:'bg-red-50 border-red-200 text-red-800'};
      return `<div class="border rounded-lg p-4 mb-3 ${levels[p.level]||levels.info}">${this._esc(p.message||'')}</div>`;
    },
    _twBadge(p) {
      const colors={gray:'bg-gray-100 text-gray-700',green:'bg-green-100 text-green-700',red:'bg-red-100 text-red-700',blue:'bg-blue-100 text-blue-700'};
      return `<span class="inline-flex px-2.5 py-0.5 rounded-full text-xs font-medium ${colors[p.color]||colors.gray}">${this._esc(p.label||'')}</span>`;
    },
    _twButton(p) {
      return `<button class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors">${this._esc(p.label||'')}</button>`;
    },
    _twForm(p) {
      const fields = (p.fields||[]).map(f=>`<div><label class="block text-sm font-medium text-gray-700 mb-1">${this._esc(f.label||f.name||'')}</label><input name="${this._esc(f.name||'')}" type="${f.type||'text'}" class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"></div>`).join('');
      return `<form class="space-y-4">${fields}<button type="submit" class="bg-blue-600 text-white px-6 py-2 rounded-lg text-sm mt-2">${this._esc(p.submit_label||'提交')}</button></form>`;
    },
    _twTabs(p) {
      const labels = Object.keys(p.tabs||{});
      const active = p.active || labels[0] || '';
      const nav = labels.map(l=>`<button class="px-3 py-2 text-sm font-medium ${l===active?'text-blue-600 border-b-2 border-blue-600':'text-gray-500'}">${this._esc(l)}</button>`).join('');
      const content = labels.map(l=>`<div class="tab-content${l!==active?' hidden':''}">${p.tabs[l]||''}</div>`).join('');
      return `<div><nav class="flex space-x-4 border-b border-gray-200 mb-3">${nav}</nav>${content}</div>`;
    },
    _esc(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); },

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
