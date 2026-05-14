"""react_executor.py — ReAct (Reasoning + Acting) interleaved execution loop.

Implements the Think-Act-Observe pattern from ReAct (Yao et al., 2022):
  Think: consciousness.chain_of_thought(task + history)
  Act:   execute one tool/action
  Observe: parse result, decide next step or FINAL_ANSWER

Complements DAGExecutor (parallel batch pipeline) with serial interleaving
for exploratory tasks where each action depends on the previous observation.

Routing: ForesightGate decides ReactExecutor vs DAGExecutor based on
task determinism (high certainty → DAG, exploratory → ReAct).

Reflexion (Shinn et al., 2023): After loop ends, reflect on full trajectory
and inject lessons into EvolutionStore for future improvement.

TACO Integration: Uses TerminalCompressor (TACO-inspired) for intelligent
terminal output compression instead of naive [observation[:500]] truncation.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

from loguru import logger


# ── ReAct Loop Types ──

class ReactAction(str, Enum):
    """Types of actions the ReAct agent can take."""
    THINK = "think"         # Internal reasoning / plan adjustment
    TOOL_CALL = "tool_call"  # Execute a tool (file read, web search, code exec, etc.)
    OBSERVE = "observe"     # Parse tool result, extract insights
    FINAL_ANSWER = "final_answer"  # Task complete, return result
    ASK_CLARIFY = "ask_clarify"    # Need human input before continuing


@dataclass
class ReactStep:
    """One complete Think-Act-Observe cycle."""
    iteration: int
    thought: str                    # What the agent reasoned
    action: str                     # The action performed (tool name or description)
    action_input: str               # Input to the action
    observation: str                # Result of the action
    confidence: float = 0.0         # Agent's confidence in this step
    latency_ms: float = 0.0
    tokens_used: int = 0
    error: str = ""


@dataclass
class ReactTrajectory:
    """Full ReAct execution trajectory for reflection."""
    task: str
    steps: list[ReactStep] = field(default_factory=list)
    final_answer: str = ""
    total_iterations: int = 0
    total_tokens: int = 0
    total_latency_ms: float = 0.0
    success: bool = False
    stopped_reason: str = ""        # "final_answer", "max_iterations", "error", "timeout"

    def to_reflection_text(self) -> str:
        if not self.steps:
            return f"Task '{self.task[:80]}': no steps executed."
        parts = [f"ReAct Trajectory for: {self.task[:120]}"]
        parts.append(f"Iterations: {len(self.steps)}, Success: {self.success}")
        for s in self.steps:
            status = "✓" if not s.error else "✗"
            parts.append(f"  {status} Step {s.iteration}: {s.action} → {s.observation[:80]}")
        if self.final_answer:
            parts.append(f"Answer: {self.final_answer[:200]}")
        return "\n".join(parts)

    def extract_lessons(self) -> list[str]:
        """Extract learnable lessons from this trajectory (Reflexion pattern)."""
        lessons = []
        for s in self.steps:
            if s.error:
                lessons.append(f"Avoid {s.action} on error: {s.error[:100]}")
            if s.confidence < 0.3 and s.iteration > 1:
                lessons.append(f"Low confidence at step {s.iteration}: {s.action}")
        if self.success and len(self.steps) == 1:
            lessons.append(f"Fast resolution: {self.steps[0].action}")
        if not self.success and self.stopped_reason == "max_iterations":
            lessons.append(f"Task '{self.task[:60]}' needs decomposition or human help")
        return lessons


# ── ReAct Prompt Template ──

REACT_SYSTEM_PROMPT = """You are a LivingTree ReAct agent with 45 tools across 13 categories. Solve tasks by interleaving thought, action, and observation.

You have MEMORY — you can remember results, recall past experiences, and build mental models. Use this to avoid repeating mistakes and to carry context across calls.

[Web] web_search(query) — Web search via Parallel MCP (free) → UnifiedSearch fallback
[Web] visit_page(url) — Fetch and extract web page content via Parallel MCP → WebReach fallback
[Web] url_fetch(url) — Raw URL fetch with auto proxy + mirror failover
[Web] api_call(url|method=GET|headers={}|body=) — Call external API

[Database] db_query(SQL) — Execute SQL query on SQLite database
[Database] db_schema(path|table) — Read database schema

[Git] git_diff(path|staged=true) — Show working tree changes
[Git] git_log(n|path) — Show commit history (n default 10)
[Git] git_blame(filepath|start|end) — Line-by-line authorship

[Shell] run_command(cmd) — Execute shell command (ToolExecutor async)
[Shell] execute(cmd) — Sandboxed shell execution with safety gates
[Shell] execute_python(code) — Execute Python code snippet
[Shell] execute_git(args) — Execute git command (e.g. 'status', 'branch -a')
[Shell] read_file(mount|path) — Read file from mounted filesystem
[Shell] list_files(mount|subpath) — List directory contents

[Search] find_files(query) — Unified search across 6 backends (files, code, docs, history, KB, graph)
[Search] kb_search(query) — Semantic vector search in knowledge base
[Search] kb_keyword(word1,word2) — Keyword-based knowledge base search
[Search] kb_retrieve(doc_id) — Retrieve KB document by ID
[Search] knowledge_forager(entity|type) — Entity-based knowledge lookup

[Data] csv_analyze(path) — Analyze CSV file (stats, columns, nulls)
[Data] json_transform(json|expression) — Transform/query JSON data

[Multimedia] pdf_parse(path|pages) — Extract text from PDF (pages optional, e.g. '1-5')
[Multimedia] ocr_extract(path|lang) — OCR image to text (lang default chi_sim)

[Visual] visual_render(data|type) — Render plot/map/diagram/table

[Memory] remember(text) — Store important information for future recall
[Memory] recall(query) — Retrieve relevant memories (AgentMemory + StructMemory)
[Memory] bind_event(role:content) — Bind a conversation turn to struct memory (role=user/assistant/system)
[Memory] mental_model(name) — Build a mental model from accumulated memory
[Memory] synthesize_opinions(limit) — Extract synthesized opinions from consolidated memory
[Memory] memory_stats — Get memory system statistics (entries, health, tiers)

[Storage] save_data(key:value) — Persist key-value data to disk
[Storage] load_data(key) — Load persisted data from disk
[Storage] list_saved — List all persisted data keys
[Storage] save_lesson(description) — Save a learned lesson to EvolutionStore
[Storage] list_lessons(limit) — List saved evolution lessons

[Skill] list_skills — List all installed LivingTree skills
[Skill] search_skills(keyword) — Search installed skills by name/description
[Skill] enable_skill(name) — Enable a disabled skill
[Skill] disable_skill(name) — Disable an installed skill

[Expert] find_experts(industry:profession) — Find domain experts (40+ industries)
[Expert] decompose_task(task) — Decompose complex task into parallel sub-tasks
[Expert] debate(topic) — Run multi-agent debate with 5 role perspectives

[Knowledge CRUD] kb_add(title:content) — Add document to knowledge base
[Knowledge CRUD] kb_update(id:title:content) — Update a knowledge base document
[Knowledge CRUD] kb_delete(doc_id) — Delete a document from knowledge base

[MCP] list_mcp — List MCP tools exposed to external clients (Chrome, City data)

Other actions:
- ask_clarify(question) — Ask the user for clarification before proceeding
- final_answer(response) — Task complete, return the answer

For each step, output exactly in this format:

Thought: <your reasoning about what to do next and why>
Action: tool_call(<tool_name>, <input>)  OR  Action: final_answer(<response>)  OR  Action: ask_clarify(<question>)

Rules:
1. Always think BEFORE acting — explain your reasoning in the "Thought" line
2. Use the most specific tool for each task (prefer find_files over kb_search for code)
3. After each action, consider the observation and think again
4. If observation reveals new information, adjust your plan
5. Use remember() after important discoveries — don't lose context
6. Use recall() when starting a new task — check what you already know
7. Use save_data() to persist results that may be needed later
8. If uncertain, say so — don't guess
9. Stop with final_answer when the task is complete, or max_iterations is reached

Task: {task}"""

OBSERVATION_PROMPT = """Observation: {result}

Based on this observation, what is your next thought and action?
Continue with the exact format: Thought: ... Action: ..."""


# ── ReactExecutor ──

@dataclass
class ReactConfig:
    """Configuration for ReactExecutor behavior."""
    max_iterations: int = 10         # Safety ceiling
    max_tokens_per_iteration: int = 4096
    timeout_seconds: float = 120.0
    confidence_threshold: float = 0.3  # Below this, reconsider step
    enable_reflexion: bool = True     # Extract lessons after completion
    temperature: float = 0.5


class ReactExecutor:
    """Serial Think-Act-Observe loop for exploratory tasks.

    Complements DAGExecutor (parallel batch). Use when the task
    requires step-by-step reasoning with feedback adaptation.

    45 built-in tools (zero new dependencies, all lazy-init):
      Web:     web_search, visit_page, url_fetch, api_call
      Database: db_query, db_schema
      Git:      git_diff, git_log, git_blame
      Shell:    run_command, execute, execute_python, execute_git, read_file, list_files
      Search:   find_files (6-backend), kb_search, kb_keyword, kb_retrieve, knowledge_forager
      Data:     csv_analyze, json_transform
      Media:    pdf_parse, ocr_extract
      Visual:   visual_render
      Memory:   remember, recall, bind_event, mental_model, synthesize_opinions, memory_stats
      Storage:  save_data, load_data, list_saved, save_lesson, list_lessons
      Skill:    list_skills, search_skills, enable_skill, disable_skill
      Expert:   find_experts, decompose_task, debate
      KB CRUD:  kb_add, kb_update, kb_delete
      MCP:      list_mcp

    Usage:
        executor = ReactExecutor(consciousness)
        result = await executor.run(
            task="Find all files related to auth and check recent git changes",
        )
    """

    def __init__(self, consciousness: Any = None):
        self._consciousness = consciousness
        self.config = ReactConfig()
        self._total_trajectories: list[ReactTrajectory] = []
        # TACO: terminal output compression middleware
        self._compressor = None
        self._evolving_rules = None
        # Lazy-init tool singletons — wired from existing system infrastructure
        self._unified_search = None   # web_search (fallback)
        self._web_reach = None         # visit_page (fallback)
        self._parallel_mcp = None      # MCP host client (primary web_search/web_fetch)
        self._tool_executor = None     # 14 tools (url_fetch, db_query, git_diff, ...)
        self._shell_executor = None    # 5 tools (execute, execute_python, execute_git, read_file, list_files)
        self._file_tool = None         # unified search (6 backends)
        self._kb = None                # knowledge_base (4 search methods)
        # P0: Memory & Storage singletons
        self._agent_memory = None      # AgentMemory (remember/recall/forget)
        self._struct_memory = None     # StructMemory (bind_events/retrieve/mental_model)
        self._async_disk = None        # AsyncDisk (save_json/load_json)
        self._evolution_store = None   # EvolutionStore (lessons persistence)
        # P1: Skill, Expert, MCP singletons
        self._skill_hub = None         # SkillHub (list/search/install/enable/disable)
        self._expert_roles = None      # ExpertRoleManager (filter by industry×profession)
        self._sub_agent_dispatch = None # SubAgentDispatch (decompose+execute)
        self._debate_engine = None     # MultiAgentDebate (deliberate with roles)

    @property
    def compressor(self):
        """Lazy-init TerminalCompressor for TACO-style output compression."""
        if self._compressor is None:
            from .terminal_compressor import get_terminal_compressor
            self._compressor = get_terminal_compressor()
        return self._compressor

    @property
    def evolving_rules(self):
        """Lazy-init SelfEvolvingRules for TACO-style rule discovery."""
        if self._evolving_rules is None:
            from ..dna.evolution import get_self_evolving_rules
            self._evolving_rules = get_self_evolving_rules(
                consciousness=self._consciousness)
        return self._evolving_rules

    # ── Lazy-init Helpers ──

    async def _ensure_search(self):
        if self._unified_search is None:
            from ..capability.unified_search import UnifiedSearch
            self._unified_search = UnifiedSearch()
        return self._unified_search

    async def _ensure_reach(self):
        if self._web_reach is None:
            from ..capability.web_reach import WebReach
            self._web_reach = WebReach(consciousness=self._consciousness)
        return self._web_reach

    def _ensure_executor(self):
        if self._tool_executor is None:
            from ..capability.tool_executor import get_executor
            self._tool_executor = get_executor()
        return self._tool_executor

    def _ensure_shell(self):
        if self._shell_executor is None:
            from ..core.shell_env import get_shell
            self._shell_executor = get_shell()
        return self._shell_executor

    async def _ensure_file_tool(self):
        if self._file_tool is None:
            from ..capability.unified_file_tool import UnifiedFileTool
            self._file_tool = UnifiedFileTool()
        return self._file_tool

    def _ensure_kb(self):
        if self._kb is None:
            from ..knowledge.knowledge_base import KnowledgeBase
            self._kb = KnowledgeBase()
        return self._kb

    # ── P0: Memory & Storage Lazy-init ──

    def _ensure_memory(self):
        if self._agent_memory is None:
            from ..core.session_memory import AgentMemory
            self._agent_memory = AgentMemory()
        return self._agent_memory

    def _ensure_struct_mem(self):
        if self._struct_memory is None:
            from ..knowledge.struct_mem import StructMemory
            self._struct_memory = StructMemory()
        return self._struct_memory

    def _ensure_disk(self):
        if self._async_disk is None:
            from ..core.async_disk import AsyncDisk
            self._async_disk = AsyncDisk()
        return self._async_disk

    def _ensure_evolution(self):
        if self._evolution_store is None:
            from ..dna.evolution_store import EvolutionStore
            self._evolution_store = EvolutionStore()
        return self._evolution_store

    # ── P1: Skill, Expert, Debate Lazy-init ──

    def _ensure_skill_hub(self):
        if self._skill_hub is None:
            from ..core.skill_hub import get_skill_hub
            self._skill_hub = get_skill_hub()
        return self._skill_hub

    def _ensure_expert_roles(self):
        if self._expert_roles is None:
            from ..dna.expert_role_manager import get_expert_role_manager
            self._expert_roles = get_expert_role_manager()
        return self._expert_roles

    def _ensure_sub_agent(self):
        if self._sub_agent_dispatch is None:
            from ..capability.sub_agent_dispatch import SubAgentDispatch
            self._sub_agent_dispatch = SubAgentDispatch()
        return self._sub_agent_dispatch

    def _ensure_debate(self):
        if self._debate_engine is None:
            from ..dna.multi_agent_debate import MultiAgentDebate
            self._debate_engine = MultiAgentDebate(consciousness=self._consciousness)
        return self._debate_engine

    async def _ensure_parallel_mcp(self):
        """Lazy-init Parallel Search MCP host client."""
        if self._parallel_mcp is None:
            try:
                from ..treellm.mcp_host_client import get_mcp_host
                self._parallel_mcp = await get_mcp_host("parallel-search")
            except Exception:
                self._parallel_mcp = False
        return self._parallel_mcp if self._parallel_mcp and self._parallel_mcp is not False else None

    # ── Web Tools ──

    async def _tool_web_search(self, query: str) -> str:
        if not query or not query.strip():
            return "[web_search] Error: empty query"
        # Try Parallel MCP first (free, professional search)
        mcp = await self._ensure_parallel_mcp()
        if mcp and mcp.is_ready:
            try:
                result = await mcp.call_tool("web_search", query=query.strip())
                if result.success and result.content:
                    return f"[web_search via Parallel MCP] {result.content[:3000]}"
            except Exception:
                pass
        # Fallback: existing UnifiedSearch (SparkSearch + DDG)
        search = await self._ensure_search()
        try:
            results = await search.query(query.strip(), limit=5)
            if not results:
                return f"[web_search] No results for: {query[:100]}"
            lines = [f"[web_search] {len(results)} results for: {query[:100]}"]
            for i, r in enumerate(results, 1):
                lines.append(f"  {i}. {r.title}")
                lines.append(f"     URL: {r.url}")
                if r.summary:
                    lines.append(f"     {r.summary[:200]}")
            return "\n".join(lines)
        except Exception as e:
            return f"[web_search] Error: {e}"

    async def _tool_visit_page(self, url: str) -> str:
        url = url.strip()
        if not url:
            return "[visit_page] Error: empty URL"
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        # Try Parallel MCP web_fetch first (handles JS rendering, CAPTCHA, PDF)
        mcp = await self._ensure_parallel_mcp()
        if mcp and mcp.is_ready:
            try:
                result = await mcp.call_tool("web_fetch", url=url)
                if result.success and result.content:
                    content = str(result.content)
                    return f"[visit_page via Parallel MCP] {content[:5000]}"
            except Exception:
                pass
        # Fallback: existing WebReach
        reach = await self._ensure_reach()
        try:
            page = await reach.fetch(url)
            status = "OK" if page.status_code == 200 else f"HTTP {page.status_code}"
            lines = [
                f"[visit_page] {status} | {page.title or '(no title)'}",
                f"  URL: {page.url}",
            ]
            if page.text:
                lines.append(f"  Content ({len(page.text)} chars): {page.text[:800]}")
            if page.links:
                lines.append(f"  Links: {len(page.links)} found")
            return "\n".join(lines)
        except Exception as e:
            return f"[visit_page] Error: {e}"

    async def _tool_url_fetch(self, input_str: str) -> str:
        """Fetch raw URL content with auto proxy + mirror failover."""
        if not input_str or not input_str.strip():
            return "[url_fetch] Error: empty URL"
        exe = self._ensure_executor()
        r = await exe.url_fetch(input_str.strip())
        return f"[url_fetch] {'OK' if r.success else 'FAIL'}: {r.output[:2000] or r.error}"

    async def _tool_api_call(self, input_str: str) -> str:
        """Call external API. Input: URL|method=GET|headers={}|body="""
        parts = input_str.split("|")
        url = parts[0].strip()
        method = "GET"; headers = "{}"; body = ""
        for p in parts[1:]:
            if "=" in p:
                k, v = p.split("=", 1)
                if k.strip() == "method": method = v.strip()
                elif k.strip() == "headers": headers = v.strip()
                elif k.strip() == "body": body = v.strip()
        exe = self._ensure_executor()
        r = await exe.api_call(url, method, headers, body)
        return f"[api_call] {'OK' if r.success else 'FAIL'}: {r.output[:2000] or r.error}"

    # ── Database Tools ──

    async def _tool_db_query(self, sql: str) -> str:
        """Execute SQL query. Input: SELECT ... FROM ..."""
        if not sql or not sql.strip():
            return "[db_query] Error: empty SQL"
        exe = self._ensure_executor()
        r = exe.db_query(sql.strip())
        return f"[db_query] {'OK' if r.success else 'FAIL'}:\n{r.output[:2000] or r.error}"

    async def _tool_db_schema(self, input_str: str) -> str:
        """Read DB schema. Input: db_path|optional_table"""
        parts = input_str.strip().split("|")
        db_path = parts[0].strip() or ":memory:"
        table = parts[1].strip() if len(parts) > 1 else ""
        exe = self._ensure_executor()
        r = exe.db_schema(db_path, table)
        return f"[db_schema] {'OK' if r.success else 'FAIL'}:\n{r.output[:2000] or r.error}"

    # ── Git Tools ──

    async def _tool_git_diff(self, input_str: str) -> str:
        """Show git diff. Input: path|staged=true/false (both optional)"""
        parts = input_str.strip().split("|")
        path = parts[0].strip() if parts[0].strip() else ""
        staged = False
        if len(parts) > 1 and "staged=true" in parts[1]:
            staged = True
        exe = self._ensure_executor()
        r = exe.git_diff(path, staged)
        return f"[git_diff] {'OK' if r.success else 'FAIL'}:\n{r.output[:3000] or r.error}"

    async def _tool_git_log(self, input_str: str) -> str:
        """Show git log. Input: n|path (both optional, default n=10)"""
        parts = input_str.strip().split("|")
        n = 10; path = ""
        try:
            n = int(parts[0].strip()) if parts[0].strip() else 10
        except ValueError:
            path = parts[0].strip()
        if len(parts) > 1:
            path = parts[1].strip()
        exe = self._ensure_executor()
        r = exe.git_log(n, path)
        return f"[git_log] {'OK' if r.success else 'FAIL'}:\n{r.output[:3000] or r.error}"

    async def _tool_git_blame(self, input_str: str) -> str:
        """Show git blame. Input: filepath|start_line|end_line"""
        parts = input_str.strip().split("|")
        path = parts[0].strip()
        if not path:
            return "[git_blame] Error: file path required"
        start = int(parts[1]) if len(parts) > 1 and parts[1].strip().isdigit() else 0
        end = int(parts[2]) if len(parts) > 2 and parts[2].strip().isdigit() else 0
        exe = self._ensure_executor()
        r = exe.git_blame(path, start, end)
        return f"[git_blame] {'OK' if r.success else 'FAIL'}:\n{r.output[:3000] or r.error}"

    # ── Shell Tools (ToolExecutor + ShellExecutor) ──

    async def _tool_run_command(self, command: str) -> str:
        """Execute shell command (ToolExecutor, async). Input: command string"""
        if not command or not command.strip():
            return "[run_command] Error: empty command"
        exe = self._ensure_executor()
        r = await exe.run_command(command.strip())
        return f"[run_command] exit={r.elapsed_ms}ms: {r.output[:3000] or r.error}"

    async def _tool_execute(self, command: str) -> str:
        """Execute shell command (ShellExecutor, sandboxed, safety gates). Input: command"""
        if not command or not command.strip():
            return "[execute] Error: empty command"
        shell = self._ensure_shell()
        r = await shell.execute(command.strip())
        out = r.stdout[:3000] or r.stderr[:2000] or "(no output)"
        return f"[execute] exit={r.exit_code}, {r.elapsed_ms:.0f}ms: {out}"

    async def _tool_execute_python(self, code: str) -> str:
        """Execute Python code. Input: Python code string"""
        if not code or not code.strip():
            return "[execute_python] Error: empty code"
        shell = self._ensure_shell()
        r = await shell.execute_python(code.strip())
        out = r.stdout[:3000] or r.stderr[:2000] or "(no output)"
        return f"[execute_python] exit={r.exit_code}: {out}"

    async def _tool_execute_git(self, args: str) -> str:
        """Execute git command. Input: git args (e.g. 'status', 'branch -a')"""
        if not args or not args.strip():
            return "[execute_git] Error: empty args"
        shell = self._ensure_shell()
        r = await shell.execute_git(args.strip())
        out = r.stdout[:3000] or r.stderr[:2000] or "(no output)"
        return f"[execute_git] exit={r.exit_code}: {out}"

    async def _tool_read_file(self, input_str: str) -> str:
        """Read file from mounted filesystem. Input: mount_name|file_path"""
        parts = input_str.strip().split("|")
        mount = parts[0].strip() if parts[0].strip() else "default"
        file_path = parts[1].strip() if len(parts) > 1 else parts[0].strip()
        shell = self._ensure_shell()
        content = shell.localfs.read_file(mount, file_path) if hasattr(shell, 'localfs') else None
        if content is None:
            return f"[read_file] File not found: {file_path}"
        return f"[read_file] {file_path} ({len(content)} chars):\n{content[:2000]}"

    async def _tool_list_files(self, input_str: str) -> str:
        """List files in mounted directory. Input: mount_name|subpath (both optional)"""
        parts = input_str.strip().split("|")
        mount = parts[0].strip() if parts[0].strip() else "default"
        subpath = parts[1].strip() if len(parts) > 1 else ""
        shell = self._ensure_shell()
        entries = shell.localfs.list_files(mount, subpath) if hasattr(shell, 'localfs') else []
        if not entries:
            return f"[list_files] No files found in {mount}/{subpath}"
        import json
        return f"[list_files] {mount}/{subpath}:\n" + json.dumps(entries, indent=2, ensure_ascii=False)[:3000]

    async def _tool_write_file(self, input_str: str) -> str:
        """Write text to file. Input: file_path|content. Overwrites existing file.
        Supports newline-separated multi-line content (\\n in input is real newlines)."""
        parts = input_str.strip().split("|", 1)
        file_path = parts[0].strip()
        content = parts[1] if len(parts) > 1 else ""
        content = content.replace("\\n", "\n") if "\\n" in content else content
        if not file_path:
            return "[write_file] Error: file path required"
        try:
            from ..infrastructure.fast_fs import get_fast_fs
            ffs = get_fast_fs()
            ffs.write_text(file_path, content, atomic=True)
            return f"[write_file] OK: {file_path} ({len(content)} chars)"
        except Exception as e:
            return f"[write_file] Error: {e}"

    async def _tool_append_file(self, input_str: str) -> str:
        """Append text to file end. Input: file_path|content. Creates file if not exists."""
        parts = input_str.strip().split("|", 1)
        file_path = parts[0].strip()
        content = parts[1] if len(parts) > 1 else ""
        content = content.replace("\\n", "\n") if "\\n" in content else content
        if not file_path:
            return "[append_file] Error: file path required"
        try:
            from ..infrastructure.fast_fs import get_fast_fs
            ffs = get_fast_fs()
            ffs.append_text(file_path, content)
            return f"[append_file] OK: {file_path} (+{len(content)} chars)"
        except Exception as e:
            return f"[append_file] Error: {e}"

    async def _tool_ripgrep_search(self, input_str: str) -> str:
        """Fast content search using ripgrep (rg). Input: directory|pattern|file_glob|max_results.
        Falls back to Python substring matching if rg not installed.
        Example: D:/project|class TreeLLM|*.py|50"""
        parts = input_str.strip().split("|")
        directory = parts[0].strip() if len(parts) > 0 else "."
        pattern = parts[1].strip() if len(parts) > 1 else ""
        file_glob = parts[2].strip() if len(parts) > 2 else "*"
        max_results = min(int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 100, 500)
        if not pattern:
            return "[ripgrep_search] Error: search pattern required"
        try:
            from ..infrastructure.fast_fs import get_fast_fs
            ffs = get_fast_fs()
            matches = ffs.grep(directory, pattern, file_glob=file_glob,
                               max_results=max_results)
            if not matches:
                return f"[ripgrep_search] No matches for '{pattern}' in {directory}"
            lines = [f"[ripgrep_search] {len(matches)} matches for '{pattern}' in {directory}"]
            for m in matches:
                lines.append(f"  {m.file_path}:{m.line_number}: {m.line_text[:200]}")
            return "\n".join(lines)[:5000]
        except Exception as e:
            return f"[ripgrep_search] Error: {e}"

    async def _tool_edit_file(self, input_str: str) -> str:
        """Atomic find-and-replace in a file. Input: path|old_str|new_str"""
        parts = input_str.strip().split("|", 2)
        if len(parts) < 3:
            return "[edit_file] Error: need path|old_str|new_str"
        path, old_str, new_str = parts[0].strip(), parts[1].strip(), parts[2].strip()
        te = await self._ensure_tool_executor()
        r = await te.edit_file(path, old_str, new_str)
        if r.success:
            return f"[edit_file] {r.output}"
        return f"[edit_file] Error: {r.error}"

    async def _tool_delete_file(self, path: str) -> str:
        """Delete a file or directory. Input: path"""
        path = path.strip()
        if not path:
            return "[delete_file] Error: empty path"
        te = await self._ensure_tool_executor()
        r = await te.delete_file(path)
        if r.success:
            return f"[delete_file] {r.output}"
        return f"[delete_file] Error: {r.error}"

    async def _tool_create_dir(self, path: str) -> str:
        """Create a directory (mkdir -p). Input: path"""
        path = path.strip()
        if not path:
            return "[create_dir] Error: empty path"
        te = await self._ensure_tool_executor()
        r = await te.create_dir(path)
        if r.success:
            return f"[create_dir] {r.output}"
        return f"[create_dir] Error: {r.error}"

    async def _tool_glob_files(self, input_str: str) -> str:
        """Glob pattern match for files. Input: pattern or directory|pattern"""
        parts = input_str.strip().split("|", 1)
        pattern = parts[-1].strip()
        directory = parts[0].strip() if len(parts) > 1 else "."
        if not pattern:
            return "[glob_files] Error: pattern required"
        te = await self._ensure_tool_executor()
        r = await te.glob_files(pattern, directory)
        if r.success:
            return f"[glob_files] {r.output}"[:5000]
        return f"[glob_files] Error: {r.error}"

    # ── File & Search Tools ──

    async def _tool_find_files(self, query: str) -> str:
        """Unified search across 6 backends (files, code, docs, history, KB, graph). Input: query"""
        if not query or not query.strip():
            return "[find_files] Error: empty query"
        ft = await self._ensure_file_tool()
        try:
            hits = await ft.search(query.strip(), max_results=10)
            if not hits:
                return f"[find_files] No results for: {query[:100]}"
            lines = [f"[find_files] {len(hits)} results for: {query[:100]}"]
            for h in hits:
                lines.append(f"  [{h.source}] {h.path or h.name} (score={h.score:.2f})")
                if h.content_preview:
                    lines.append(f"    {h.content_preview[:120]}")
            return "\n".join(lines)
        except Exception as e:
            return f"[find_files] Error: {e}"

    async def _tool_explore_domain(self, input_str: str) -> str:
        """Spontaneously explore a domain and build World Knowledge.
        Input: domain_or_url|optional_max_pages (default 15)
        LLM autonomously decides to explore unfamiliar domains before answering queries."""
        parts = input_str.strip().split("|")
        domain = parts[0].strip()
        if not domain:
            return "[explore_domain] Error: domain or URL required"
        max_pages = 15
        if len(parts) > 1 and parts[1].strip().isdigit():
            max_pages = min(int(parts[1].strip()), 50)
        try:
            from ..capability.world_explorer import get_world_explorer
            explorer = get_world_explorer()
            wk = await explorer.explore(domain, max_pages=max_pages)
            if wk and wk.page_count > 0:
                md = wk.to_markdown()
                return (
                    f"[explore_domain] Explored {domain}: {wk.page_count} pages, "
                    f"{len(wk.url_prefixes)} prefixes, {len(wk.actionable_items)} actionable items.\n"
                    f"World Knowledge (injected as context):\n{md[:4000]}"
                )
            return f"[explore_domain] No pages found for {domain}"
        except Exception as e:
            return f"[explore_domain] Error exploring {domain}: {e}"

    async def _tool_get_world_knowledge(self, domain: str) -> str:
        """Retrieve cached World Knowledge for a domain. Input: domain string"""
        if not domain or not domain.strip():
            return "[get_world_knowledge] Error: domain required"
        try:
            from ..knowledge.knowledge_base import get_knowledge_base
            kb = get_knowledge_base()
            wk_text = kb.get_world_knowledge(domain.strip())
            if wk_text:
                return f"[get_world_knowledge] Cached World Knowledge for {domain}:\n{wk_text[:5000]}"
            return f"[get_world_knowledge] No cached World Knowledge for {domain}. Use explore_domain to build it."
        except Exception as e:
            return f"[get_world_knowledge] Error: {e}"

    async def _tool_kb_search(self, query: str) -> str:
        """Semantic knowledge base search. Input: query string"""
        if not query or not query.strip():
            return "[kb_search] Error: empty query"
        kb = self._ensure_kb()
        try:
            docs = kb.search(query.strip(), top_k=5)
            if not docs:
                return f"[kb_search] No results for: {query[:100]}"
            lines = [f"[kb_search] {len(docs)} results for: {query[:100]}"]
            for d in docs:
                lines.append(f"  [{d.domain or 'general'}] {d.content[:200]}")
            return "\n".join(lines)
        except Exception as e:
            return f"[kb_search] Error: {e}"

    async def _tool_kb_keyword(self, input_str: str) -> str:
        """Keyword search in knowledge base. Input: keyword1,keyword2,..."""
        keywords = [k.strip() for k in input_str.split(",") if k.strip()]
        if not keywords:
            return "[kb_keyword] Error: no keywords"
        kb = self._ensure_kb()
        try:
            docs = kb.search_keyword(keywords)[:5]
            if not docs:
                return f"[kb_keyword] No results for: {keywords}"
            lines = [f"[kb_keyword] {len(docs)} results for: {keywords}"]
            for d in docs:
                lines.append(f"  [{d.domain or 'general'}] {d.content[:200]}")
            return "\n".join(lines)
        except Exception as e:
            return f"[kb_keyword] Error: {e}"

    async def _tool_kb_retrieve(self, doc_id: str) -> str:
        """Retrieve knowledge base document by ID. Input: document ID"""
        if not doc_id or not doc_id.strip():
            return "[kb_retrieve] Error: empty ID"
        kb = self._ensure_kb()
        try:
            doc = kb.retrieve(doc_id.strip())
            if not doc:
                return f"[kb_retrieve] Not found: {doc_id}"
            return f"[kb_retrieve] {doc.id} [{doc.domain or 'general'}]:\n{doc.content[:2000]}"
        except Exception as e:
            return f"[kb_retrieve] Error: {e}"

    async def _tool_knowledge_forager(self, input_str: str) -> str:
        """Entity-based knowledge lookup. Input: entity_name|entity_type (type optional)"""
        parts = input_str.strip().split("|")
        entity = parts[0].strip()
        etype = parts[1].strip() if len(parts) > 1 else ""
        if not entity:
            return "[knowledge_forager] Error: empty entity"
        try:
            from ..capability.knowledge_forager import KnowledgeForager
            kf = KnowledgeForager()
            result = kf.query(entity, etype)
            return f"[knowledge_forager] {entity}: {str(result)[:2000]}"
        except Exception as e:
            return f"[knowledge_forager] Error: {e}"

    # ── Data Tools ──

    async def _tool_csv_analyze(self, path: str) -> str:
        """Analyze CSV file. Input: file path"""
        if not path or not path.strip():
            return "[csv_analyze] Error: empty path"
        exe = self._ensure_executor()
        r = exe.csv_analyze(path.strip())
        return f"[csv_analyze] {'OK' if r.success else 'FAIL'}:\n{r.output[:2000] or r.error}"

    async def _tool_json_transform(self, input_str: str) -> str:
        """Transform JSON. Input: json_string|expression (expression optional)"""
        parts = input_str.split("|", 1)
        data = parts[0].strip()
        expr = parts[1].strip() if len(parts) > 1 else ""
        exe = self._ensure_executor()
        r = exe.json_transform(data, expr)
        return f"[json_transform] {'OK' if r.success else 'FAIL'}:\n{r.output[:2000] or r.error}"

    # ── Multimedia Tools ──

    async def _tool_pdf_parse(self, input_str: str) -> str:
        """Parse PDF content. Input: file_path|pages (pages optional, e.g. '1-5')"""
        parts = input_str.strip().split("|")
        path = parts[0].strip()
        pages = parts[1].strip() if len(parts) > 1 else ""
        if not path:
            return "[pdf_parse] Error: empty path"
        exe = self._ensure_executor()
        r = exe.pdf_parse(path, pages)
        return f"[pdf_parse] {'OK' if r.success else 'FAIL'}:\n{r.output[:3000] or r.error}"

    async def _tool_ocr_extract(self, input_str: str) -> str:
        """OCR image to text. Input: file_path|language (lang optional, default chi_sim)"""
        parts = input_str.strip().split("|")
        path = parts[0].strip()
        lang = parts[1].strip() if len(parts) > 1 else "chi_sim"
        if not path:
            return "[ocr_extract] Error: empty path"
        exe = self._ensure_executor()
        r = exe.ocr_extract(path, lang)
        return f"[ocr_extract] {'OK' if r.success else 'FAIL'}:\n{r.output[:3000] or r.error}"

    # ── Visual Tools ──

    async def _tool_visual_render(self, input_str: str) -> str:
        """Render visualization (plot, map, diagram, table). Input: data|type_hint (type optional)"""
        parts = input_str.split("|", 1)
        data = parts[0].strip()
        hint = parts[1].strip() if len(parts) > 1 else "auto"
        exe = self._ensure_executor()
        r = await exe.visual_render(data, hint)
        return f"[visual_render] {'OK' if r.success else 'FAIL'}: {r.output[:2000] or r.error}"

    # ── Utility: parse key=value pairs from input string ──

    @staticmethod
    def _parse_param(input_str: str, param_name: str, default: str = "") -> str:
        """Extract param_name=value from input string."""
        for part in input_str.split(","):
            if "=" in part:
                k, v = part.split("=", 1)
                if k.strip() == param_name:
                    return v.strip()
        return default

    # ── Tool Registry ──

    # ═══ P0: Memory Tools ═══

    async def _tool_remember(self, text: str) -> str:
        """Remember content for future recall. Usage: remember(<text to remember>)"""
        text = text.strip()
        if not text:
            return "[remember] Error: empty content"
        mem = self._ensure_memory()
        try:
            await mem.remember(content=text)
            return f"[remember] Stored: {text[:120]}..."
        except Exception as e:
            return f"[remember] Error: {e}"

    async def _tool_recall(self, query: str) -> str:
        """Recall relevant memories. Usage: recall(<what to find>)"""
        query = query.strip()
        if not query:
            return "[recall] Error: empty query"
        mem = self._ensure_memory()
        try:
            results = await mem.recall(query=query, top_k=5)
            if not results:
                return f"[recall] No memories found for: {query[:100]}"
            lines = [f"[recall] {len(results)} memories for: {query[:100]}"]
            for i, r in enumerate(results, 1):
                lines.append(f"  {i}. {str(r)[:200]}")
            return "\n".join(lines)
        except Exception as e:
            # Fallback: try struct memory
            try:
                sm = self._ensure_struct_mem()
                entries = await sm.retrieve_for_query(query, top_k=5)
                if not entries:
                    return f"[recall] No memories found for: {query[:100]}"
                lines = [f"[recall] {len(entries)} struct memories for: {query[:100]}"]
                for i, e in enumerate(entries, 1):
                    lines.append(f"  {i}. {e.content[:200] if hasattr(e,'content') else str(e)[:200]}")
                return "\n".join(lines)
            except Exception as e2:
                return f"[recall] Error: {e} | fallback: {e2}"

    async def _tool_bind_event(self, input_str: str) -> str:
        """Bind a conversation turn to struct memory. Usage: bind_event(role:content)
        e.g. bind_event(user:what is the weather) or bind_event(assistant:it is sunny)"""
        parts = input_str.split(":", 1)
        if len(parts) != 2:
            return "[bind_event] Error: format is 'role:content' (e.g. 'user:hello')"
        role, content = parts[0].strip(), parts[1].strip()
        if role not in ("user", "assistant", "system"):
            return f"[bind_event] Error: invalid role '{role}', use user/assistant/system"
        sm = self._ensure_struct_mem()
        try:
            import uuid
            sid = uuid.uuid4().hex[:12]
            entries = await sm.bind_events(sid, [{"role": role, "content": content}])
            return f"[bind_event] Bound {len(entries)} entries (session={sid})"
        except Exception as e:
            return f"[bind_event] Error: {e}"

    def _tool_mental_model(self, name: str = "") -> str:
        """Build a mental model from accumulated memory. Usage: mental_model or mental_model(my_model)"""
        name = name.strip() or "default"
        sm = self._ensure_struct_mem()
        try:
            model = sm.build_mental_model(name)
            return f"[mental_model] '{name}': opinions={len(getattr(model,'opinions',[]))}, {str(model)[:300]}"
        except Exception as e:
            return f"[mental_model] Error: {e}"

    def _tool_synthesize_opinions(self, limit: str = "") -> str:
        """Synthesize opinions from consolidated memory. Usage: synthesize_opinions or synthesize_opinions(5)"""
        n = 8
        if limit.strip():
            try:
                n = int(limit.strip())
            except ValueError:
                pass
        sm = self._ensure_struct_mem()
        try:
            opinions = sm.synthesize_opinions(limit=n)
            if not opinions:
                return "[synthesize_opinions] No opinions synthesized yet"
            lines = [f"[synthesize_opinions] {len(opinions)} opinions:"]
            for i, op in enumerate(opinions, 1):
                lines.append(f"  {i}. {str(op)[:200]}")
            return "\n".join(lines)
        except Exception as e:
            return f"[synthesize_opinions] Error: {e}"

    def _tool_memory_stats(self, _: str = "") -> str:
        """Get memory system statistics. Usage: memory_stats"""
        sm = self._ensure_struct_mem()
        try:
            stats = sm.get_stats() if hasattr(sm, 'get_stats') else {}
            health = sm.get_memory_health() if hasattr(sm, 'get_memory_health') else {}
            return f"[memory_stats] entries={stats.get('total_entries',0)}, health={health}"
        except Exception as e:
            return f"[memory_stats] Error: {e}"

    # ═══ P0: Storage Tools ═══

    def _tool_save_data(self, input_str: str) -> str:
        """Persist key-value data to disk. Usage: save_data(key:value)"""
        parts = input_str.split(":", 1)
        if len(parts) != 2:
            return "[save_data] Error: format is 'key:value'"
        key, value = parts[0].strip(), parts[1].strip()
        disk = self._ensure_disk()
        try:
            from pathlib import Path
            path = Path("data") / "react_storage" / f"{key}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            disk.write_json(path, {"key": key, "value": value, "timestamp": time.time()})
            return f"[save_data] Saved '{key}' → {len(value)} chars"
        except Exception as e:
            return f"[save_data] Error: {e}"

    def _tool_load_data(self, key: str) -> str:
        """Load persisted data from disk. Usage: load_data(<key>)"""
        key = key.strip()
        if not key:
            return "[load_data] Error: empty key"
        try:
            from pathlib import Path
            import json as _json
            path = Path("data") / "react_storage" / f"{key}.json"
            if not path.exists():
                return f"[load_data] No data found for key: {key}"
            data = _json.loads(path.read_text(encoding="utf-8"))
            return f"[load_data] {key}: {str(data.get('value',''))[:500]}"
        except Exception as e:
            return f"[load_data] Error: {e}"

    def _tool_list_saved(self, _: str = "") -> str:
        """List all persisted data keys. Usage: list_saved"""
        try:
            from pathlib import Path
            path = Path("data") / "react_storage"
            if not path.exists():
                return "[list_saved] No saved data yet"
            files = sorted(path.glob("*.json"))
            keys = [f.stem for f in files]
            return f"[list_saved] {len(keys)} keys: {', '.join(keys[:20])}"
        except Exception as e:
            return f"[list_saved] Error: {e}"

    def _tool_save_lesson(self, description: str) -> str:
        """Save a learned lesson to EvolutionStore. Usage: save_lesson(<lesson description>)"""
        description = description.strip()
        if not description:
            return "[save_lesson] Error: empty description"
        ev = self._ensure_evolution()
        try:
            lessons = ev.extract_lessons("react", [description])
            ev.save()
            return f"[save_lesson] Saved {len(lessons)} lesson(s)"
        except Exception as e:
            return f"[save_lesson] Error: {e}"

    def _tool_list_lessons(self, limit: str = "") -> str:
        """List saved evolution lessons. Usage: list_lessons or list_lessons(10)"""
        n = 10
        if limit.strip():
            try:
                n = int(limit.strip())
            except ValueError:
                pass
        ev = self._ensure_evolution()
        try:
            ev.load()
            lessons = ev.get_lessons_by_pattern("")
            if not lessons:
                return "[list_lessons] No lessons yet"
            lines = [f"[list_lessons] {min(n, len(lessons))} of {len(lessons)} lessons:"]
            for i, l in enumerate(lessons[:n], 1):
                lines.append(f"  {i}. {l.description[:200] if hasattr(l,'description') else str(l)[:200]}")
            return "\n".join(lines)
        except Exception as e:
            return f"[list_lessons] Error: {e}"

    # ═══ P1: Skill Tools ═══

    def _tool_list_skills(self, _: str = "") -> str:
        """List all installed skills. Usage: list_skills"""
        hub = self._ensure_skill_hub()
        try:
            skills = hub.list_installed()
            if not skills:
                return "[list_skills] No skills installed"
            lines = [f"[list_skills] {len(skills)} installed:"]
            for i, s in enumerate(skills[:30], 1):
                name = getattr(s, 'name', str(s))
                desc = getattr(s, 'description', '')[:80]
                lines.append(f"  {i}. {name} — {desc}")
            return "\n".join(lines)
        except Exception as e:
            return f"[list_skills] Error: {e}"

    def _tool_search_skills(self, query: str) -> str:
        """Search installed skills by name/description. Usage: search_skills(<keyword>)"""
        query = query.strip().lower()
        if not query:
            return "[search_skills] Error: empty query"
        hub = self._ensure_skill_hub()
        try:
            skills = hub.list_installed()
            matched = [
                s for s in skills
                if query in getattr(s, 'name', '').lower()
                or query in getattr(s, 'description', '').lower()
            ]
            if not matched:
                return f"[search_skills] No skills matching: {query}"
            lines = [f"[search_skills] {len(matched)} matching '{query}':"]
            for i, s in enumerate(matched[:15], 1):
                lines.append(f"  {i}. {getattr(s,'name',s)} — {getattr(s,'description','')[:100]}")
            return "\n".join(lines)
        except Exception as e:
            return f"[search_skills] Error: {e}"

    def _tool_enable_skill(self, name: str) -> str:
        """Enable a disabled skill. Usage: enable_skill(<skill_name>)"""
        name = name.strip()
        if not name:
            return "[enable_skill] Error: empty name"
        hub = self._ensure_skill_hub()
        try:
            if hasattr(hub, 'enable_skill'):
                hub.enable_skill(name)
                return f"[enable_skill] Enabled: {name}"
            return f"[enable_skill] Skill hub does not support enable (skill: {name})"
        except Exception as e:
            return f"[enable_skill] Error: {e}"

    def _tool_disable_skill(self, name: str) -> str:
        """Disable an installed skill. Usage: disable_skill(<skill_name>)"""
        name = name.strip()
        if not name:
            return "[disable_skill] Error: empty name"
        hub = self._ensure_skill_hub()
        try:
            if hasattr(hub, 'disable_skill'):
                hub.disable_skill(name)
                return f"[disable_skill] Disabled: {name}"
            return f"[disable_skill] Skill hub does not support disable (skill: {name})"
        except Exception as e:
            return f"[disable_skill] Error: {e}"

    # ═══ P1: Expert Tools ═══

    def _tool_find_experts(self, input_str: str) -> str:
        """Find domain experts by industry and profession. Usage: find_experts(industry:profession)
        e.g. find_experts(medical:surgeon) or find_experts(software:architect)"""
        parts = input_str.split(":", 1) if ":" in input_str else (input_str, "")
        industry = parts[0].strip()
        profession = parts[1].strip() if len(parts) > 1 else ""
        erm = self._ensure_expert_roles()
        try:
            roles = erm.filter(industry=industry, profession=profession)
            if not roles:
                return f"[find_experts] No experts for industry='{industry}' profession='{profession}'"
            lines = [f"[find_experts] {len(roles)} experts for {industry}/{profession}:"]
            for i, r in enumerate(roles[:10], 1):
                lines.append(f"  {i}. {getattr(r,'name','')} ({getattr(r,'profession','')}) — {getattr(r,'description','')[:80]}")
            return "\n".join(lines)
        except Exception as e:
            return f"[find_experts] Error: {e}"

    async def _tool_decompose_task(self, task: str) -> str:
        """Decompose a complex task into parallel sub-tasks. Usage: decompose_task(<task description>)"""
        task = task.strip()
        if not task:
            return "[decompose_task] Error: empty task"
        dispatch = self._ensure_sub_agent()
        try:
            sub_tasks = dispatch.decompose(task)
            if not sub_tasks:
                return f"[decompose_task] Could not decompose: {task[:100]}"
            lines = [f"[decompose_task] {len(sub_tasks)} sub-tasks for: {task[:100]}"]
            for i, st in enumerate(sub_tasks, 1):
                lines.append(f"  {i}. {getattr(st,'description',str(st))[:150]}")
            return "\n".join(lines)
        except Exception as e:
            return f"[decompose_task] Error: {e}"

    async def _tool_debate(self, topic: str) -> str:
        """Run multi-agent debate on a topic. Usage: debate(<topic>)
        Returns consensus from 5 role perspectives."""
        topic = topic.strip()
        if not topic:
            return "[debate] Error: empty topic"
        debate = self._ensure_debate()
        try:
            result = await debate.deliberate(topic)
            return f"[debate] Topic: {topic[:100]}\nResult: {str(result)[:500]}"
        except Exception as e:
            return f"[debate] Error: {e}"

    # ═══ P1: Knowledge CRUD Tools ═══

    def _tool_kb_add(self, input_str: str) -> str:
        """Add document to knowledge base. Usage: kb_add(title:content)"""
        parts = input_str.split(":", 1)
        if len(parts) != 2:
            return "[kb_add] Error: format is 'title:content'"
        title, content = parts[0].strip(), parts[1].strip()
        kb = self._ensure_kb()
        try:
            from ..knowledge.knowledge_base import Document
            import uuid
            doc_id = uuid.uuid4().hex[:12]
            doc = Document(id=doc_id, title=title, content=content)
            kb.add_document(doc)
            return f"[kb_add] Added document '{title}' (id={doc_id}, {len(content)} chars)"
        except Exception as e:
            return f"[kb_add] Error: {e}"

    def _tool_kb_update(self, input_str: str) -> str:
        """Update a knowledge base document. Usage: kb_update(id:title:content)"""
        parts = input_str.split(":", 2)
        if len(parts) != 3:
            return "[kb_update] Error: format is 'id:title:content'"
        doc_id, title, content = parts[0].strip(), parts[1].strip(), parts[2].strip()
        kb = self._ensure_kb()
        try:
            from ..knowledge.knowledge_base import Document
            doc = Document(id=doc_id, title=title, content=content)
            kb.update_document(doc)
            return f"[kb_update] Updated document '{title}' (id={doc_id})"
        except Exception as e:
            return f"[kb_update] Error: {e}"

    def _tool_kb_delete(self, doc_id: str) -> str:
        """Delete a document from knowledge base. Usage: kb_delete(<doc_id>)"""
        doc_id = doc_id.strip()
        if not doc_id:
            return "[kb_delete] Error: empty id"
        kb = self._ensure_kb()
        try:
            kb.delete_document(doc_id)
            return f"[kb_delete] Deleted document: {doc_id}"
        except Exception as e:
            return f"[kb_delete] Error: {e}"

    # ═══ P2: MCP Awareness ═══

    def _tool_list_mcp(self, _: str = "") -> str:
        """List available MCP (Model Context Protocol) tools. Usage: list_mcp"""
        lines = ["[list_mcp] MCP tools available to external clients:"]
        try:
            from ..core.chrome_mcp import ChromeMCPBridge
            lines.append("  Chrome MCP: browser automation (navigate, click, screenshot, eval)")
        except Exception:
            lines.append("  Chrome MCP: not available")
        try:
            from ..core.city_mcp import CityMCPConnector
            lines.append("  City MCP: urban data query (population, transport, weather)")
        except Exception:
            lines.append("  City MCP: not available")
        lines.append("  (MCP tools are exposed to external clients via stdio/SSE)")
        lines.append("  Use web_search or api_call for equivalent web operations")
        return "\n".join(lines)

    # ═══ Registry ═══

    def _default_tools(self) -> dict[str, Any]:
        """Build complete tool registry from LivingTree's existing infrastructure.

        All tools use pre-existing modules. Zero new dependencies. All lazy-initialized.

        Categories:
          Web (4), Database (2), Git (3), Shell (5), Search (5), Data (2),
          Multimedia (2), Visual (1), Memory (6), Storage (4), Skill (4),
          Expert (3), Knowledge CRUD (3), MCP (1) = 45 tools total
        """
        return {
            # Web (4)
            "web_search": self._tool_web_search,
            "visit_page": self._tool_visit_page,
            "url_fetch": self._tool_url_fetch,
            "api_call": self._tool_api_call,
            # Database (2)
            "db_query": self._tool_db_query,
            "db_schema": self._tool_db_schema,
            # Git (3)
            "git_diff": self._tool_git_diff,
            "git_log": self._tool_git_log,
            "git_blame": self._tool_git_blame,
            # Shell (5)
            "run_command": self._tool_run_command,
            "execute": self._tool_execute,
            "execute_python": self._tool_execute_python,
            "execute_git": self._tool_execute_git,
            # File tools (10)
            "read_file": self._tool_read_file,
            "write_file": self._tool_write_file,
            "append_file": self._tool_append_file,
            "edit_file": self._tool_edit_file,
            "delete_file": self._tool_delete_file,
            "create_dir": self._tool_create_dir,
            "glob_files": self._tool_glob_files,
            "list_files": self._tool_list_files,
            "find_files": self._tool_find_files,
            "ripgrep_search": self._tool_ripgrep_search,
            "kb_search": self._tool_kb_search,
            "kb_keyword": self._tool_kb_keyword,
            "kb_retrieve": self._tool_kb_retrieve,
            "knowledge_forager": self._tool_knowledge_forager,
            # Data (2)
            "csv_analyze": self._tool_csv_analyze,
            "json_transform": self._tool_json_transform,
            # Multimedia (2)
            "pdf_parse": self._tool_pdf_parse,
            "ocr_extract": self._tool_ocr_extract,
            # Visual (1)
            "visual_render": self._tool_visual_render,
            # ═══ P0: Memory (6) ═══
            "remember": self._tool_remember,
            "recall": self._tool_recall,
            "bind_event": self._tool_bind_event,
            "mental_model": self._tool_mental_model,
            "synthesize_opinions": self._tool_synthesize_opinions,
            "memory_stats": self._tool_memory_stats,
            # ═══ P0: Storage (4) ═══
            "save_data": self._tool_save_data,
            "load_data": self._tool_load_data,
            "list_saved": self._tool_list_saved,
            "save_lesson": self._tool_save_lesson,
            "list_lessons": self._tool_list_lessons,
            # ═══ P1: Skill (4) ═══
            "list_skills": self._tool_list_skills,
            "search_skills": self._tool_search_skills,
            "enable_skill": self._tool_enable_skill,
            "disable_skill": self._tool_disable_skill,
            # ═══ P1: Expert (3) ═══
            "find_experts": self._tool_find_experts,
            "decompose_task": self._tool_decompose_task,
            "debate": self._tool_debate,
            # ═══ P1: Knowledge CRUD (3) ═══
            "kb_add": self._tool_kb_add,
            "kb_update": self._tool_kb_update,
            "kb_delete": self._tool_kb_delete,
            # ═══ P2: MCP (1) ═══
            "list_mcp": self._tool_list_mcp,
            # ═══ P2: World Knowledge (2) ═══
            "explore_domain": self._tool_explore_domain,
            "get_world_knowledge": self._tool_get_world_knowledge,
        }

    async def run(
        self,
        task: str,
        tools: Optional[dict[str, Callable[..., Coroutine]]] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> ReactTrajectory:
        """Execute a task via interleaved Think-Act-Observe.

        Args:
            task: Natural language task description
            tools: Dict of tool_name → async callable
            context: Additional context (knowledge, memory, etc.)

        Returns:
            ReactTrajectory with full step history and result
        """
        tools = tools or {}
        context = context or {}

        # Merge built-in web tools (user tools override defaults)
        merged_tools = self._default_tools()
        merged_tools.update(tools)

        trajectory = ReactTrajectory(task=task)
        history: list[str] = []
        start_time = time.monotonic()

        # Build initial prompt with task + context
        knowledge = context.get("knowledge", "")
        kb_block = f"\nRelevant knowledge:\n{knowledge[:2000]}" if knowledge else ""
        current_prompt = REACT_SYSTEM_PROMPT.format(task=task) + kb_block

        for iteration in range(1, self.config.max_iterations + 1):
            if time.monotonic() - start_time > self.config.timeout_seconds:
                trajectory.stopped_reason = "timeout"
                break

            # ── THINK + ACT ──
            thought, action, action_input = await self._think_act(
                current_prompt, history, iteration)
            if not thought:
                trajectory.stopped_reason = "error"
                break

            # Check for final_answer
            if action == ReactAction.FINAL_ANSWER:
                trajectory.final_answer = action_input
                trajectory.success = True
                trajectory.stopped_reason = "final_answer"
                step = ReactStep(
                    iteration=iteration, thought=thought,
                    action="final_answer", action_input=action_input,
                    observation="Task complete.", confidence=1.0,
                )
                trajectory.steps.append(step)
                break

            # Check for clarification request
            if action == ReactAction.ASK_CLARIFY:
                step = ReactStep(
                    iteration=iteration, thought=thought,
                    action="ask_clarify", action_input=action_input,
                    observation=f"Clarification needed: {action_input}", confidence=0.5,
                )
                trajectory.steps.append(step)
                trajectory.stopped_reason = "ask_clarify"
                break

            # ── ACT: execute tool ──
            step_start = time.monotonic()
            observation, error = await self._execute_action(
                action, action_input, merged_tools)
            step_latency = (time.monotonic() - step_start) * 1000

            # ── OBSERVE: parse and update ──
            confidence = self._estimate_confidence(observation, error)
            step = ReactStep(
                iteration=iteration, thought=thought,
                action=f"tool_call({action})", action_input=action_input,
                observation=observation or error or "", confidence=confidence,
                latency_ms=step_latency, error=error,
            )
            trajectory.steps.append(step)

            if error and iteration >= 3:
                # Three consecutive failures → abort
                recent_errors = sum(1 for s in trajectory.steps[-3:] if s.error)
                if recent_errors >= 2:
                    trajectory.stopped_reason = "error"
                    break

            # Feed observation into next iteration
            history.append(f"Step {iteration}: {thought}")
            history.append(f"Action: {action}({action_input[:100]})")

            # TACO: compress terminal observation intelligently
            # instead of naive observation[:500]
            comp = self.compressor.compress(
                observation, command=str(action),
                context=task[:100])
            compressed_obs = comp.compressed
            history.append(f"Observation: {compressed_obs}")
            current_prompt = OBSERVATION_PROMPT.format(result=compressed_obs)

            # TACO: feed observation to self-evolving rules for pattern discovery
            try:
                self.evolving_rules.observe_output(
                    raw_output=observation,
                    compressed_output=compressed_obs,
                    namespace=self.compressor._detect_namespace(str(action), observation),
                    command=str(action),
                    saving_pct=comp.saving_pct,
                )
            except Exception:
                pass  # Rule observation should never crash the loop

        # Post-loop: compute trajectory stats
        trajectory.total_iterations = len(trajectory.steps)
        trajectory.total_tokens = sum(s.tokens_used for s in trajectory.steps)
        trajectory.total_latency_ms = sum(s.latency_ms for s in trajectory.steps)

        if not trajectory.stopped_reason:
            trajectory.stopped_reason = "max_iterations"

        self._total_trajectories.append(trajectory)

        # ── Reflexion: extract lessons ──
        if self.config.enable_reflexion and hasattr(self, 'on_trajectory_complete'):
            await self.on_trajectory_complete(trajectory)

        return trajectory

    async def _think_act(
        self, prompt: str, history: list[str], iteration: int,
    ) -> tuple[str, ReactAction, str]:
        """Think phase: call LLM to decide next action."""
        if self._consciousness is None:
            return "", ReactAction.FINAL_ANSWER, "No consciousness available"

        # TACO: compress history instead of raw history[-10:]
        if history:
            # Keep most recent entries raw, compress older ones
            recent = history[-6:] if len(history) > 6 else history
            older = history[:-6] if len(history) > 6 else []

            hist_lines = list(recent)
            if older:
                # Compress older history entries
                older_text = "\n".join(older)
                comp = self.compressor.compress(
                    older_text, command="history_compression",
                    context=prompt[:200])
                hist_lines.insert(0, f"[Compressed history: {comp.compressed[:500]}]")

            hist_block = "\n".join(hist_lines)
        else:
            hist_block = "(start)"
        full_prompt = f"{prompt}\n\nHistory:\n{hist_block}"

        try:
            response = await self._consciousness.chain_of_thought(
                full_prompt, temperature=self.config.temperature,
                max_tokens=self.config.max_tokens_per_iteration,
            )
        except Exception as e:
            logger.warning(f"ReAct think failed: {e}")
            return "Error in reasoning", ReactAction.FINAL_ANSWER, str(e)

        return self._parse_action(response)

    @staticmethod
    def _parse_action(response: str) -> tuple[str, ReactAction, str]:
        """Parse Thought and Action from LLM response."""
        # Extract Thought
        thought_match = re.search(
            r'Thought:\s*(.+?)(?=\n(?:Action|Observation):|\Z)',
            response, re.DOTALL | re.IGNORECASE)
        thought = thought_match.group(1).strip() if thought_match else response[:200]

        # Extract Action
        action_match = re.search(
            r'Action:\s*(\w+)\((.+?)\)',
            response, re.IGNORECASE)

        if not action_match:
            # Fallback: try to detect final answer pattern
            if any(kw in response.lower() for kw in
                   ['final answer', 'the answer is', 'in conclusion']):
                return thought, ReactAction.FINAL_ANSWER, response[:1000]
            # Fallback: treat as thought-only
            return thought, ReactAction.THINK, "re-evaluating"

        action_type = action_match.group(1).strip().lower()
        action_input = action_match.group(2).strip()

        # Map to ReactAction enum
        if action_type in ('final_answer', 'finalanswer', 'answer'):
            return thought, ReactAction.FINAL_ANSWER, action_input
        elif action_type in ('ask_clarify', 'askclarify', 'clarify', 'question'):
            return thought, ReactAction.ASK_CLARIFY, action_input
        else:
            return thought, ReactAction.TOOL_CALL, action_input

    @staticmethod
    async def _execute_action(
        self, action: str, action_input: str, tools: dict[str, Callable],
    ) -> tuple[str, str]:
        """Execute a tool action and return observation + error."""
        if action not in tools:
            return "", f"Unknown tool: {action}"

        # ── OrthogonalityGuard: diagnostic check for tool call redundancy ──
        if not hasattr(self, '_tool_call_history'):
            self._tool_call_history = {}
        try:
            from ..dna.orthogonality_guard import get_orthogonality_guard
            og = get_orthogonality_guard()
            tool_features = set(action.split('_') + [action])
            report = og.check_sparse(tool_features, self._tool_call_history, vector_id=action)
            if not report.is_orthogonal:
                logger.debug(f"Orthogonality: {action} overlaps with prior calls (cos={report.max_cosine_similarity:.2f})")
            self._tool_call_history[action] = tool_features
        except Exception:
            pass

        try:
            # Try calling the tool with input
            result = await tools[action](action_input)
            observation = str(result)[:2000]
            return observation, ""
        except Exception as e:
            return "", f"Tool {action} failed: {str(e)[:200]}"

    @staticmethod
    def _estimate_confidence(observation: str, error: str) -> float:
        """Lightweight confidence estimation from observation quality."""
        if error:
            return 0.1

        score = 0.5  # neutral baseline

        # Positive signals
        if len(observation) > 100:
            score += 0.2
        if any(kw in observation.lower() for kw in ['success', 'completed', 'found', 'result']):
            score += 0.15

        # Negative signals
        if any(kw in observation.lower() for kw in ['error', 'failed', 'not found', 'empty']):
            score -= 0.3
        if len(observation) < 10:
            score -= 0.2

        return max(0.0, min(1.0, score))

    async def on_trajectory_complete(self, trajectory: ReactTrajectory) -> None:
        """Hook for post-execution processing (Reflexion, evolution, etc.)."""
        lessons = trajectory.extract_lessons()
        if lessons:
            logger.info(f"ReAct Reflexion: {len(lessons)} lessons from '{trajectory.task[:60]}'")
            for lesson in lessons:
                logger.debug(f"  → {lesson}")

    def get_stats(self) -> dict[str, Any]:
        """Get aggregate statistics across all trajectories."""
        if not self._total_trajectories:
            return {"trajectories": 0}
        trajs = self._total_trajectories
        return {
            "trajectories": len(trajs),
            "success_rate": round(sum(1 for t in trajs if t.success) / len(trajs), 3),
            "avg_iterations": round(sum(t.total_iterations for t in trajs) / len(trajs), 1),
            "avg_tokens": round(sum(t.total_tokens for t in trajs) / len(trajs)),
            "avg_latency_ms": round(sum(t.total_latency_ms for t in trajs) / len(trajs)),
            "common_actions": self._common_actions(trajs),
        }

    @staticmethod
    def _common_actions(trajectories: list[ReactTrajectory]) -> list[str]:
        counts: dict[str, int] = {}
        for t in trajectories:
            for s in t.steps:
                key = s.action
                counts[key] = counts.get(key, 0) + 1
        return [a for a, _ in sorted(counts.items(), key=lambda x: x[1], reverse=True)[:5]]


# ── Dual-Mode Router ──

class ExecutionMode(str, Enum):
    DAG = "dag"       # Parallel batch pipeline (Plan-then-Execute)
    REACT = "react"   # Serial interleaved (Think-Act-Observe)
    HYBRID = "hybrid" # DAG for deterministic subtasks, ReAct for exploratory


async def route_execution(
    task: str,
    plan: list[dict],
    consciousness: Any,
    foresight_gate: Any = None,
) -> ExecutionMode:
    """Route task to appropriate execution mode based on determinism.

    Uses ForesightGate to assess task nature:
    - High confidence (>0.7) + simple plan → DAG (parallel batch)
    - Low confidence (<0.5) or exploratory → REACT (interleaved)
    - Everything else → HYBRID (DAG main + ReAct on ambiguous steps)

    Args:
        task: Natural language task
        plan: Decomposed task plan
        consciousness: LLM interface
        foresight_gate: Optional CoherenceGate for decision

    Returns:
        Recommended ExecutionMode
    """
    if not foresight_gate:
        # Simple heuristic: if plan has >3 independent steps, use DAG
        return ExecutionMode.DAG if len(plan) > 3 else ExecutionMode.REACT

    try:
        decision = foresight_gate.gate(
            task=task,
            context={"plan_length": len(plan), "has_subtasks": len(plan) > 1},
            history=[],
        )
    except Exception:
        # Fallback if gate doesn't have gate() method (legacy assess)
        try:
            decision = foresight_gate.assess(task, "general", [], "low")
        except Exception:
            return ExecutionMode.DAG if len(plan) > 3 else ExecutionMode.REACT

    confidence = getattr(decision, 'confidence', 0.5)
    state = getattr(decision, 'state', None)

    if state and hasattr(state, 'value'):
        state_val = state.value
    else:
        state_val = "accept"

    # Routing logic
    if state_val == "reject":
        return ExecutionMode.REACT  # Don't DAG on rejected — think step by step
    if state_val == "recalibrate":
        return ExecutionMode.REACT  # Need more info — ReAct observes and adapts
    if confidence > 0.7 and len(plan) > 2:
        return ExecutionMode.DAG   # High certainty, batchable
    if confidence < 0.5:
        return ExecutionMode.REACT  # Low confidence → observe after each step

    return ExecutionMode.HYBRID


# Singleton
_REACT_EXECUTOR: Optional[ReactExecutor] = None


def get_react_executor(consciousness: Any = None) -> ReactExecutor:
    global _REACT_EXECUTOR
    if _REACT_EXECUTOR is None:
        _REACT_EXECUTOR = ReactExecutor(consciousness)
    elif consciousness is not None and _REACT_EXECUTOR._consciousness is None:
        _REACT_EXECUTOR._consciousness = consciousness
    return _REACT_EXECUTOR
