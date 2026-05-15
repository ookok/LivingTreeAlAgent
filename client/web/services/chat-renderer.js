/* LivingTree Chat Renderer — Rich segment-based message display
 * 
 * Handles: streaming thinking, tool calls, A2UI components, interactive asks, loading states
 * 
 * Message segment types:
 *   thinking   — collapsible reasoning stream (collapsed by default)
 *   text       — main content output
 *   tool_call  — expandable tool invocation with args + result
 *   a2ui       — auto-rendered Tailwind/Mermaid/Chart/Table
 *   ask        — interactive prompt requiring user response
 *   error      — error display
 *   loading    — typewriter animation
 */

(function() {
  'use strict';
  window.LT = window.LT || {};

  const ChatRenderer = {
    /** Add a new agent message container */
    addAgentMessage(containerId) {
      const area = document.getElementById(containerId || 'chat-area');
      const el = document.createElement('div');
      el.className = 'msg-enter flex gap-3 max-w-3xl mx-auto mb-4';
      el.innerHTML = `<div class="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-sm flex-shrink-0">🌳</div>
        <div class="flex-1 min-w-0 space-y-2" id="msg-${Date.now()}"></div>`;
      area.appendChild(el);
      area.scrollTop = area.scrollHeight;
      return el.querySelector('.space-y-2');
    },

    /** Add a user message */
    addUserMessage(text, containerId) {
      const area = document.getElementById(containerId || 'chat-area');
      const el = document.createElement('div');
      el.className = 'msg-enter flex gap-3 max-w-3xl mx-auto justify-end mb-4';
      el.innerHTML = `<div class="bg-blue-600 text-white rounded-2xl rounded-tr-none shadow-sm px-4 py-2.5 max-w-xl text-sm">${LT.esc(text)}</div>`;
      area.appendChild(el);
      area.scrollTop = area.scrollHeight;
    },

    /* ═══ Segment Renderers ═══ */

    /** Thinking block — collapsible, shows reasoning stream */
    thinking(container, text, isStreaming) {
      const cls = isStreaming ? 'thinking-streaming' : '';
      const existing = container.querySelector('.thinking-block:last-child.thinking-streaming');
      if (existing && isStreaming) {
        existing.querySelector('.thinking-content').textContent = text;
        return;
      }
      const div = document.createElement('div');
      div.className = `thinking-block bg-gray-50 border border-gray-200 rounded-xl overflow-hidden ${cls}`;
      div.innerHTML = `<div class="flex items-center justify-between px-3 py-2 cursor-pointer hover:bg-gray-100"
          onclick="this.nextElementSibling.classList.toggle('hidden');this.querySelector('.expand-icon').classList.toggle('rotate-90')">
          <span class="text-xs text-gray-500 flex items-center gap-1.5">
            <span class="w-1.5 h-1.5 rounded-full bg-purple-400 ${isStreaming?'animate-pulse':''}"></span>
            💭 思考中...
          </span>
          <svg class="expand-icon w-3 h-3 text-gray-400 transition-transform ${isStreaming?'':'rotate-90'}" viewBox="0 0 12 12"><path d="M4 2l4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>
        </div>
        <div class="thinking-content px-3 py-2 text-xs text-gray-500 leading-relaxed max-h-32 overflow-y-auto ${isStreaming?'':'hidden'}">${LT.esc(text)}</div>`;
      container.appendChild(div);
    },

    /** Main text block */
    text(container, text, isStreaming) {
      const existing = container.querySelector('.text-block:last-child.text-streaming');
      if (existing && isStreaming) {
        existing.innerHTML = this._md(text);
        return;
      }
      const div = document.createElement('div');
      div.className = `text-block bg-white rounded-2xl rounded-tl-none shadow-sm px-4 py-3 text-sm text-gray-700 leading-relaxed ${isStreaming?'text-streaming':''}`;
      div.innerHTML = this._md(text);
      container.appendChild(div);
    },

    /** Tool call block — expandable with live status */
    toolCall(container, name, args, status, result) {
      const icons = {pending:'⏳',running:'🔄',done:'✅',error:'❌'};
      const colors = {pending:'text-yellow-500',running:'text-blue-500',done:'text-green-500',error:'text-red-500'};
      const id = 'tc-'+Date.now()+'-'+Math.random().toString(36).slice(2,6);

      // Update existing if streaming
      if (status === 'running') {
        const existing = container.querySelector('.tool-block.tool-running');
        if (existing) {
          existing.querySelector('.tool-status').innerHTML = `${icons[status]} <span class="${colors[status]}">${LT.esc(name)}</span>`;
          return existing;
        }
      }

      const div = document.createElement('div');
      div.className = `tool-block bg-gray-50 border border-gray-200 rounded-xl overflow-hidden ${status==='running'?'tool-running':''}`;
      div.innerHTML = `<div class="flex items-center justify-between px-3 py-2 cursor-pointer hover:bg-gray-100"
          onclick="this.querySelector('.tool-detail').classList.toggle('hidden')">
          <span class="text-xs tool-status">${icons[status]} <span class="${colors[status]}">${LT.esc(name)}</span></span>
          <span class="text-xs text-gray-400">${status==='running'?'执行中...':status==='pending'?'等待中':''}</span>
        </div>
        <div class="tool-detail hidden px-3 py-2 text-xs border-t border-gray-200">
          ${args?`<div class="text-gray-400 mb-1">参数: ${LT.esc(args).slice(0,200)}</div>`:''}
          ${result?`<div class="text-gray-600 bg-white rounded-lg p-2 mt-1 max-h-24 overflow-y-auto">${LT.esc(String(result)).slice(0,500)}</div>`:''}
        </div>`;
      container.appendChild(div);
      return div;
    },

    /** A2UI component block */
    a2ui(container, type, data) {
      const div = document.createElement('div');
      if (type === 'tailwind') {
        div.className = 'living-a2ui';
        div.dataset.a2uiType = 'tailwind';
        div.dataset.a2uiComponent = data.component || 'Card';
        div.dataset.a2uiProps = JSON.stringify(data.props || {});
      } else if (type === 'chart') {
        div.className = 'living-a2ui';
        div.dataset.a2uiType = 'chart';
        div.dataset.a2uiChart = JSON.stringify(data);
        div.style.cssText = 'width:100%;min-height:300px;';
      } else if (type === 'diagram') {
        div.className = 'living-a2ui';
        div.dataset.a2uiType = 'diagram';
        div.textContent = data.code || '';
      }
      container.appendChild(div);
      if (window.LivingA2UI) setTimeout(() => LivingA2UI.scan(), 100);
      return div;
    },

    /** Interactive ask — requires user response */
    ask(container, question, options) {
      const div = document.createElement('div');
      div.className = 'bg-blue-50 border border-blue-200 rounded-xl p-3 text-sm';
      div.innerHTML = `<p class="text-blue-800 mb-2">🤔 ${LT.esc(question)}</p>
        <div class="flex flex-wrap gap-2">${(options||['是','否','跳过']).map(o =>
          `<button onclick="LT.chat.sendMsg('${LT.esc(o)}')" class="px-3 py-1 text-xs bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors">${LT.esc(o)}</button>`
        ).join('')}</div>`;
      container.appendChild(div);
    },

    /** Loading animation */
    loading(container) {
      const div = document.createElement('div');
      div.className = 'loading-block';
      div.innerHTML = `<div class="flex items-center gap-2 text-gray-400 text-xs px-1">
        <span class="typing-dot inline-block w-1.5 h-1.5 bg-gray-400 rounded-full" style="animation:blink 1.4s infinite both"></span>
        <span class="typing-dot inline-block w-1.5 h-1.5 bg-gray-400 rounded-full" style="animation:blink 1.4s infinite both;animation-delay:.2s"></span>
        <span class="typing-dot inline-block w-1.5 h-1.5 bg-gray-400 rounded-full" style="animation:blink 1.4s infinite both;animation-delay:.4s"></span>
        <span class="ml-1">思考中...</span>
      </div>`;
      container.appendChild(div);
      return div;
    },

    /** Error block */
    error(container, msg) {
      const div = document.createElement('div');
      div.className = 'bg-red-50 border border-red-200 rounded-xl p-3 text-xs text-red-700';
      div.textContent = '❌ ' + msg;
      container.appendChild(div);
    },

    /** Clear all children */
    clear(container) {
      while (container.firstChild) container.removeChild(container.firstChild);
    },

    /* ═══ Markdown ═══ */
    _md(text) {
      if (!text) return '';
      let out = LT.esc(text);
      // Bold
      out = out.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
      // Italic
      out = out.replace(/\*(.+?)\*/g, '<em>$1</em>');
      // Inline code
      out = out.replace(/`([^`]+)`/g, '<code class="bg-gray-100 text-red-600 px-1 py-0.5 rounded text-xs">$1</code>');
      // Code blocks
      out = out.replace(/```(\w*)\n([\s\S]*?)```/g, (m, lang, code) => {
        return `<pre class="bg-gray-900 text-gray-100 rounded-lg p-3 text-xs overflow-x-auto my-2"><code>${LT.esc(code)}</code></pre>`;
      });
      // Line breaks
      out = out.replace(/\n/g, '<br>');
      return out;
    },

    /** Parse streaming content for segments */
    parseSegments(text) {
      const segments = [];
      // Split by markers
      const parts = text.split(/(<thinking>|<\/thinking>|<tool_call|<result>|<\/result>|{"type":)/g);
      let currentType = 'text';
      let buffer = '';

      for (const part of parts) {
        if (part === '<thinking>') {
          if (buffer.trim()) { segments.push({type:currentType, content:buffer.trim()}); buffer=''; }
          currentType = 'thinking';
        } else if (part === '</thinking>') {
          if (buffer.trim()) { segments.push({type:'thinking', content:buffer.trim()}); buffer=''; }
          currentType = 'text';
        } else if (part.startsWith('<tool_call')) {
          if (buffer.trim()) { segments.push({type:currentType, content:buffer.trim()}); buffer=''; }
          currentType = 'tool_call';
          buffer = part;
        } else if (part === '<result>') {
          currentType = 'tool_result';
          buffer = '';
        } else if (part === '</result>') {
          segments.push({type:'tool_result', content:buffer.trim()}); buffer='';
          currentType = 'text';
        } else if (part === '{"type":') {
          if (buffer.trim()) { segments.push({type:currentType, content:buffer.trim()}); buffer=''; }
          currentType = 'a2ui';
          buffer = part;
        } else {
          buffer += (part || '');
        }
      }
      if (buffer.trim()) segments.push({type:currentType, content:buffer.trim()});
      return segments;
    },

    /** Render all segments into container */
    renderSegments(container, segments) {
      this.clear(container);
      for (const seg of segments) {
        if (!seg.content) continue;
        if (seg.type === 'thinking') {
          this.thinking(container, seg.content, false);
        } else if (seg.type === 'text') {
          this.text(container, seg.content, false);
        } else if (seg.type === 'tool_call') {
          const m = seg.content.match(/<tool_call\s+name="(\w+)"\s*>(.*?)<\/tool_call>/);
          if (m) this.toolCall(container, m[1], m[2], 'done');
        } else if (seg.type === 'tool_result') {
          this.toolCall(container, '', '', 'done', seg.content);
        } else if (seg.type === 'a2ui') {
          try {
            const data = JSON.parse(seg.content);
            if (data.type) this.a2ui(container, data.type, data[data.type] || data);
          } catch(e) {}
        }
      }
    }
  };

  LT.chat = LT.chat || {};
  LT.chat.renderer = ChatRenderer;

  /** Send a message with full rich rendering */
  LT.chat.sendMsg = async function(text) {
    if (!text) { const inp = document.getElementById('msg-input'); text = inp.value.trim(); if (!text) return; inp.value = ''; inp.style.height = 'auto'; }
    
    LT.chat.renderer.addUserMessage(text);
    const container = LT.chat.renderer.addAgentMessage();
    const loadingEl = LT.chat.renderer.loading(container);

    try {
      const resp = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({message:text, stream:true})
      });

      if (!resp.ok) throw new Error('HTTP '+resp.status);

      // Fallback: non-streaming response
      if (!resp.body || !resp.body.getReader) {
        const data = await resp.json();
        const content = data.reply || data.text || data.content || '';
        loadingEl?.remove();
        const segments = LT.chat.renderer.parseSegments(content);
        LT.chat.renderer.renderSegments(container, segments);
        if (window.LivingA2UI) setTimeout(() => LivingA2UI.scan(), 100);
        return;
      }

      let fullText = '';
      let thinkingText = '';
      let inThinking = false;
      let inToolCall = false;
      let toolBuffer = '';
      let toolName = '';
      let lastRender = Date.now();

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      loadingEl?.remove();

      while (true) {
        const {done, value} = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, {stream: true});
        const lines = chunk.split('\n').filter(l => l.startsWith('data: '));
        
        for (const line of lines) {
          const data = line.slice(6);
          if (data === '[DONE]') break;
          
          try {
            const parsed = JSON.parse(data);
            const token = parsed.choices?.[0]?.delta?.content || parsed.content || parsed.text || '';
            const reasoning = parsed.choices?.[0]?.delta?.reasoning_content || parsed.reasoning || '';
            const toolCalls = parsed.choices?.[0]?.delta?.tool_calls || parsed.tool_calls;

            // Handle reasoning/thinking stream
            if (reasoning) {
              if (!inThinking) {
                inThinking = true;
                LT.chat.renderer.thinking(container, reasoning, true);
              } else {
                LT.chat.renderer.thinking(container, (thinkingText + reasoning), true);
              }
              thinkingText += reasoning;
              continue;
            }
            if (inThinking && token) {
              inThinking = false;
              // Finalize thinking block
              LT.chat.renderer.thinking(container, thinkingText, false);
            }

            // Handle tool calls
            if (toolCalls) {
              if (!inToolCall) {
                inToolCall = true;
                toolName = toolCalls[0]?.function?.name || 'tool';
                LT.chat.renderer.toolCall(container, toolName, '', 'running');
              }
              const args = toolCalls[0]?.function?.arguments || '';
              toolBuffer += args;
              continue;
            }
            if (inToolCall && token) {
              inToolCall = false;
              LT.chat.renderer.toolCall(container, toolName, toolBuffer, 'done');
            }

            // Handle text output
            if (token) {
              fullText += token;
              // Throttle DOM updates to 60fps
              if (Date.now() - lastRender > 50) {
                const segments = LT.chat.renderer.parseSegments(fullText);
                LT.chat.renderer.renderSegments(container, segments);
                lastRender = Date.now();
              }
            }
          } catch(e) {}
        }
      }

      // Final render
      const segments = LT.chat.renderer.parseSegments(fullText);
      LT.chat.renderer.renderSegments(container, segments);
      
      // Trigger A2UI scan for any rendered components
      if (window.LivingA2UI) setTimeout(() => LivingA2UI.scan(), 100);

    } catch(e) {
      loadingEl?.remove();
      LT.chat.renderer.error(container, e.message || '请求失败');
    }

    document.getElementById('chat-area').scrollTop = document.getElementById('chat-area').scrollHeight;
  };

})();
