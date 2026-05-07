let _abortController = null;

const DEMO_RESPONSES = [
  `你好！我是 LivingTree 智能助手 🌿

很高兴为你服务！我可以帮助你：

1. **信息查询** - 快速查找各类知识
2. **文本创作** - 撰写文章、代码、方案等
3. **数据分析** - 处理和解析数据
4. **日常对话** - 陪你聊天、解答疑问

有什么我可以帮你的吗？`,

  `感谢你的提问！让我来详细解答：

---

### 核心要点

这个问题可以从以下几个角度来理解：

1. **基础概念** - 首先要明确问题的背景和上下文
2. **关键因素** - 影响结果的主要变量有哪些
3. **实践建议** - 基于经验的最佳实践

> 小贴士：在实际应用中，建议根据具体情况灵活调整策略，没有放之四海而皆准的方案。

希望这些内容对你有所帮助！如果还有疑问，随时告诉我。`,

  `没问题，我来为你处理这个任务 🚀

让我分步骤来说明：

**第一步：分析需求**
理解你的目标和约束条件

**第二步：制定方案**
基于分析结果，规划执行路径

**第三步：执行验证**
实施方案并检查结果是否符合预期

\`\`\`
进度: [████████░░] 80%
状态: 进行中...
\`\`\`

如果需要调整方向或细化某个环节，请随时告诉我！我会持续优化方案直到满足你的需求。`
];

function _randomDemo() {
  return DEMO_RESPONSES[Math.floor(Math.random() * DEMO_RESPONSES.length)];
}

async function* _simulateStream(text, delayMin = 15, delayMax = 45) {
  for (let i = 0; i < text.length; i++) {
    const delay = delayMin + Math.random() * (delayMax - delayMin);
    await new Promise(r => setTimeout(r, delay));
    yield text[i];
  }
}

const api = {
  base: '/api/web',

  _abort() {
    if (_abortController) {
      _abortController.abort();
      _abortController = null;
    }
  },

  async streamChat(messages, onChunk, onDone, onError) {
    this._abort();
    _abortController = new AbortController();

    try {
      const response = await fetch(`${this.base}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages }),
        signal: _abortController.signal
      });

      if (!response.ok) {
        const text = await response.text().catch(() => '');
        const err = new Error(`API error ${response.status}: ${text}`);
        if (onError) onError(err);
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;
          if (trimmed.startsWith('data: ')) {
            const data = trimmed.slice(6);
            if (data === '[DONE]') {
              if (onDone) onDone();
              return;
            }
            try {
              const parsed = JSON.parse(data);
              const content = parsed.content || parsed.text || parsed.delta || '';
              if (content && onChunk) onChunk(content);
            } catch {
              if (onChunk) onChunk(data);
            }
          }
        }
      }

      if (buffer.trim() && onChunk) {
        onChunk(buffer.trim());
      }

      if (onDone) onDone();
    } catch (err) {
      if (err.name === 'AbortError') {
        if (onDone) onDone();
        return;
      }
      console.error('[api] streamChat error:', err);
      if (onError) onError(err);
    } finally {
      _abortController = null;
    }
  },

  send(input, onChunk, onDone, onError) {
    const store = window.LT && window.LT.store;
    if (!store) {
      console.error('[api] Store not available');
      if (onError) onError(new Error('Store not available'));
      return;
    }

    const sid = store.activeId;
    if (!sid) {
      console.error('[api] No active session');
      if (onError) onError(new Error('No active session'));
      return;
    }

    store.addMsg(sid, { role: 'user', content: input });

    const msgs = store.getMsgs(sid);

    store.generating = true;

    let fullContent = '';

    this.streamChat(
      msgs,
      (chunk) => {
        fullContent += chunk;
        if (onChunk) onChunk(chunk);
      },
      () => {
        if (fullContent) {
          store.addMsg(sid, { role: 'agent', content: fullContent });
        }
        store.generating = false;
        if (onDone) onDone(fullContent);
      },
      (err) => {
        store.generating = false;
        if (onError) onError(err);
      }
    );
  },

  stop() {
    this._abort();
    const store = window.LT && window.LT.store;
    if (store) {
      store.generating = false;
    }
  },

  async simulate(input, onChunk, onDone) {
    const store = window.LT && window.LT.store;
    const sid = store ? store.activeId : null;

    if (store && sid) {
      store.addMsg(sid, { role: 'user', content: input });
      store.generating = true;
    }

    const text = _randomDemo();
    let full = '';

    try {
      for await (const char of _simulateStream(text, 12, 35)) {
        full += char;
        if (onChunk) onChunk(char);
      }
    } finally {
      if (store && sid) {
        store.addMsg(sid, { role: 'agent', content: full });
        store.generating = false;
      }
      if (onDone) onDone(full);
    }
  }
};

window.LT = window.LT || {};
window.LT.api = api;

export default api;
