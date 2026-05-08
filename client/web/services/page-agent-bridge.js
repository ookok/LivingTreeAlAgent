/* ═══════════════════════════════════
   LivingTree — Page Agent Bridge
   Inject into any third-party page to enable AI auto-fill.
   
   Usage (bookmarklet):
   javascript:(function(){var s=document.createElement('script');s.src='http://localhost:8100/services/page-agent-bridge.js';document.head.appendChild(s)})()
   ═══════════════════════════════════ */

(function() {
  'use strict';
  if (window.__LT_PAGE_AGENT_LOADED) return;
  window.__LT_PAGE_AGENT_LOADED = true;

  const LT_SERVER = 'http://localhost:8100';

  /* ── UI — floating control panel ── */
  const panel = document.createElement('div');
  panel.id = 'lt-auto-fill-panel';
  panel.innerHTML = `
<style>
#lt-auto-fill-panel{position:fixed;top:12px;right:12px;z-index:2147483647;background:#1a1b1d;border:1px solid rgba(255,255,255,0.12);border-radius:10px;padding:14px;font-family:"Microsoft YaHei",sans-serif;font-size:13px;color:#d1d3db;box-shadow:0 4px 20px rgba(0,0,0,0.4);width:300px;max-height:80vh;overflow-y:auto}
#lt-auto-fill-panel .lt-af-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}
#lt-auto-fill-panel .lt-af-title{font-weight:600;color:#0fdc78;display:flex;align-items:center;gap:6px}
#lt-auto-fill-panel .lt-af-close{cursor:pointer;color:#9599a6;font-size:16px;line-height:1}
#lt-auto-fill-panel .lt-af-close:hover{color:#f65a5a}
#lt-auto-fill-panel .lt-af-btn{display:block;width:100%;padding:8px 12px;border:none;border-radius:6px;font-size:12px;font-weight:500;cursor:pointer;margin:6px 0;transition:all .15s}
#lt-auto-fill-panel .lt-af-btn-primary{background:#0fdc78;color:#0c0c0d}
#lt-auto-fill-panel .lt-af-btn-primary:hover{background:#0ab861}
#lt-auto-fill-panel .lt-af-btn-secondary{background:rgba(255,255,255,0.08);color:#d1d3db}
#lt-auto-fill-panel .lt-af-btn-secondary:hover{background:rgba(255,255,255,0.14)}
#lt-auto-fill-panel .lt-af-field-list{margin:8px 0}
#lt-auto-fill-panel .lt-af-field{display:flex;justify-content:space-between;align-items:center;padding:6px 8px;border-radius:4px;background:rgba(255,255,255,0.04);margin:4px 0;font-size:11px}
#lt-auto-fill-panel .lt-af-field-label{color:#9599a6;flex:1;overflow:hidden;text-overflow:ellipsis}
#lt-auto-fill-panel .lt-af-field-value{color:#0fdc78;font-weight:500;margin-left:8px;max-width:120px;overflow:hidden;text-overflow:ellipsis}
#lt-auto-fill-panel .lt-af-field-conf{font-size:10px;margin-left:4px}
#lt-auto-fill-panel .lt-af-status{font-size:11px;color:#9599a6;text-align:center;padding:4px}
#lt-auto-fill-panel .lt-af-error{color:#f65a5a;font-size:11px;padding:4px}
</style>
<div class="lt-af-header">
  <span class="lt-af-title">🌳 LivingTree 自动填报</span>
  <span class="lt-af-close" onclick="document.getElementById('lt-auto-fill-panel').remove()">✕</span>
</div>
<div id="lt-af-status" class="lt-af-status">准备就绪</div>
<div id="lt-af-fields" class="lt-af-field-list"></div>
<div id="lt-af-actions">
  <button class="lt-af-btn lt-af-btn-primary" onclick="window.__LT_AF.scanAndFill()">🔍 扫描表单并智能填充</button>
  <button class="lt-af-btn lt-af-btn-secondary" onclick="window.__LT_AF.scanOnly()">📋 仅扫描表单</button>
</div>
<div id="lt-af-error"></div>
`;
  document.body.appendChild(panel);

  /* ── Core logic ── */
  window.__LT_AF = {
    _extractedFields: [],

    setStatus(msg, isError) {
      const el = document.getElementById('lt-af-status');
      if (el) { el.textContent = msg; el.style.color = isError ? '#f65a5a' : '#9599a6'; }
    },

    /* ── Scan all forms on the page ── */
    _scanForms() {
      const fields = [];
      const seen = new Set();
      const forms = document.querySelectorAll('form');
      const container = forms.length ? forms : [document.body];
      const selectors = 'input:not([type=hidden]):not([type=submit]):not([type=button]):not([type=image]), textarea, select, [contenteditable=true]';

      container.forEach(form => {
        form.querySelectorAll(selectors).forEach(el => {
          const tag = el.tagName.toLowerCase();
          const type = el.type || tag;
          if (type === 'submit' || type === 'button' || type === 'hidden' || type === 'image') return;

          // Get label
          let label = '';
          if (el.labels && el.labels[0]) {
            label = el.labels[0].textContent.trim();
          } else if (el.getAttribute('aria-label')) {
            label = el.getAttribute('aria-label').trim();
          } else if (el.getAttribute('placeholder')) {
            label = el.getAttribute('placeholder').trim();
          } else if (el.name) {
            label = el.name.replace(/[_-]/g, ' ');
          }
          // Try previous sibling / parent text
          if (!label && el.previousElementSibling) {
            label = el.previousElementSibling.textContent.trim().slice(0, 40);
          }
          if (!label) {
            const parent = el.closest('td, th, div, label, .form-group');
            if (parent) {
              const text = parent.textContent.replace(el.value || '', '').trim().slice(0, 40);
              if (text) label = text;
            }
          }

          label = label.replace(/\s+/g, ' ').replace(/[*：:]\s*$/, '').trim();
          if (!label) label = el.name || el.id || '未命名字段';

          const key = `${label}|${el.name || el.id}`;
          if (seen.has(key)) return; // skip duplicate
          seen.add(key);

          // Get options for selects
          let options = [];
          if (tag === 'select') {
            options = [...el.options].filter(o => o.value).map(o => o.textContent.trim());
          }

          fields.push({
            name: el.name || el.id || `field_${fields.length}`,
            label: label,
            type: type,
            tag: tag,
            placeholder: el.getAttribute('placeholder') || '',
            required: el.required || el.getAttribute('aria-required') === 'true',
            options: options,
            _el: el,
          });
        });
      });

      return fields;
    },

    /* ── Scan only — show extracted fields ── */
    scanOnly() {
      const fields = this._scanForms();
      this._extractedFields = fields;
      this._renderFieldList(fields);
      this.setStatus(`检测到 ${fields.length} 个表单字段`);
    },

    /* ── Scan + AI fill ── */
    async scanAndFill() {
      const fields = this._scanForms();
      this._extractedFields = fields;
      this._renderFieldList(fields);
      this.setStatus(`检测到 ${fields.length} 个字段，正在调用 AI 匹配...`);

      // Build request payload
      const fieldData = fields.map(f => ({
        name: f.name, label: f.label, type: f.type, placeholder: f.placeholder,
        options: f.options,
      }));

      try {
        const resp = await fetch(`${LT_SERVER}/api/auto-fill/match`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            fields: fieldData,
            context: { url: window.location.href, title: document.title },
          }),
        });

        if (!resp.ok) throw new Error(`API error ${resp.status}`);
        const data = await resp.json();

        if (data.values && Object.keys(data.values).length > 0) {
          this.setStatus(`AI 匹配了 ${data.matched}/${data.total} 个字段`);
          // Inject values
          this._injectValues(fields, data.values);
          // Refresh field list
          this._renderFieldList(fields, data.values, data.confidence);
        } else {
          this.setStatus('AI 未找到匹配值，已使用默认规则', true);
        }
      } catch (err) {
        this.setStatus(`连接失败: ${err.message}`, true);
      }
    },

    /* ── Inject values into form fields ── */
    _injectValues(fields, values) {
      fields.forEach(f => {
        const key = f.name;
        const val = values[key] || values[f.label];
        if (val && f._el) {
          try {
            if (f.tag === 'select') {
              // Try to select matching option
              const opts = [...f._el.options];
              const match = opts.find(o => o.textContent.includes(val) || o.value.includes(val));
              if (match) f._el.value = match.value;
            } else if (f.type === 'checkbox' || f.type === 'radio') {
              f._el.checked = val.toLowerCase() === 'true' || val === '1';
            } else {
              // Trigger input event for React/Vue frameworks
              const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                window.HTMLInputElement.prototype, 'value'
              ).set;
              nativeInputValueSetter.call(f._el, val);
              f._el.dispatchEvent(new Event('input', { bubbles: true }));
              f._el.dispatchEvent(new Event('change', { bubbles: true }));
            }
          } catch (e) {
            // Fallback for readonly/disabled fields
            try { f._el.value = val; } catch (_) {}
          }
        }
      });
    },

    /* ── Render field list in panel ── */
    _renderFieldList(fields, values, confidence) {
      const container = document.getElementById('lt-af-fields');
      if (!container) return;
      container.innerHTML = fields.map(f => {
        const val = (values && (values[f.name] || values[f.label])) || '';
        const conf = (confidence && (confidence[f.name] || confidence[f.label]));
        const confStr = conf ? ` ${Math.round(conf * 100)}%` : '';
        const color = conf && conf >= 0.8 ? '#0fdc78' : conf && conf >= 0.5 ? '#e28a00' : '#f65a5a';
        return `<div class="lt-af-field">
          <span class="lt-af-field-label">${f.label}${f.required ? ' *' : ''}</span>
          <span class="lt-af-field-value" style="color:${color}">${val || '(待填)'}</span>
          <span class="lt-af-field-conf" style="color:${color}">${confStr}</span>
        </div>`;
      }).join('');
    },
  };

  // Auto-scan on load
  setTimeout(() => window.__LT_AF.scanOnly(), 500);
  console.log('🌳 LivingTree Auto-Fill Bridge loaded — ready');
})();
