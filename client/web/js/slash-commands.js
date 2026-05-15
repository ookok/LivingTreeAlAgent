/**
 * Slash Commands Registry — extensible command system for chat input.
 *
 * Usage:
 *   SlashCommands.register("/ask", "Ask AI", "Send a question to TreeLLM");
 *   SlashCommands.register("/do", "Execute task", "Run a multi-step task");
 *   const match = SlashCommands.match("/as");
 *   // → { cmd, name, desc, param: "/as" }
 *
 * Input.js uses this registry instead of an inline command list.
 * New skills/capabilities can add commands via SlashCommands.register().
 */
window.SlashCommands = (() => {
  const _commands = [];

  return {
    /** Register a slash command. Returns false if already exists. */
    register(cmd, name, desc, handler) {
      if (_commands.find(c => c.cmd === cmd)) return false;
      _commands.push({ cmd, name, desc, handler });
      return true;
    },

    /** Remove a command. */
    unregister(cmd) {
      const idx = _commands.findIndex(c => c.cmd === cmd);
      if (idx >= 0) { _commands.splice(idx, 1); return true; }
      return false;
    },

    /** Auto-complete: returns best-match command for a partial query. */
    match(partial) {
      if (!partial || partial === '/') return null;
      const query = partial.toLowerCase();
      for (const c of _commands) {
        if (c.cmd.startsWith(query)) return { ...c, param: query };
      }
      // Fuzzy: check if query appears anywhere in cmd
      for (const c of _commands) {
        if (c.cmd.includes(query)) return { ...c, param: query };
      }
      return null;
    },

    /** All commands for dropdown rendering. */
    list() { return _commands.slice(); },

    /** Filter commands by a partial query (for dropdown). */
    filter(partial) {
      if (!partial || partial === '/') return _commands.slice();
      const query = partial.toLowerCase();
      return _commands.filter(c => c.cmd.startsWith(query) || c.cmd.includes(query));
    },
  };
})();

// ── Built-in commands ──
SlashCommands.register("/ask", "AI 问答", "向 TreeLLM 提问", "ask");
SlashCommands.register("/do", "执行任务", "多步骤任务自动执行", "task");
SlashCommands.register("/files", "文件管理", "搜索 / 读取 / 编辑文件", "files");
SlashCommands.register("/learn", "学习知识", "学习新概念并存入知识库", "learn");
SlashCommands.register("/check", "代码检查", "代码审查 / 安全检查", "check");
SlashCommands.register("/docs", "文档生成", "生成报告、文档、图表", "docs");
SlashCommands.register("/team", "协作团队", "多 Agent 协作", "team");
SlashCommands.register("/help", "帮助", "显示所有可用命令", "help");
