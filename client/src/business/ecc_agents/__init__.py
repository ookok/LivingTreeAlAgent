"""
ECC Agent System - 专业角色分工系统
Inspired by Everything Claude Code (ECC)

将 Hermes 从"编辑器"升级为"Agent 宿主平台"

核心概念:
- Agent: 专业角色 (Code Architect, Debug Specialist, etc.)
- 每个 Agent 有独立的 System Prompt 和工具集绑定
- 用户切换 Agent 即切换行为模式
"""

import json
import uuid
import time
import threading
from pathlib import Path
from typing import Optional, Callable, Dict, List, Any
from dataclasses import dataclass, field
from enum import Enum
import yaml


class AgentCapability(Enum):
    """Agent 能力枚举"""
    CODE_ARCHITECT = "code_architect"      # 代码架构设计
    DEBUG_SPECIALIST = "debug_specialist"  # Bug追踪诊断
    CODE_REVIEW = "code_review"           # 代码审查
    REFACTORING = "refactoring"            # 重构优化
    TEST_GENERATOR = "test_generator"      # 测试生成
    DOC_GENERATOR = "doc_generator"        # 文档生成
    PERFORMANCE = "performance"            # 性能优化
    SECURITY = "security"                  # 安全审计
    DATABASE = "database"                   # 数据库设计
    API_DESIGN = "api_design"              # API设计


@dataclass
class AgentTool:
    """Agent 绑定的工具"""
    name: str
    description: str = ""
    parameters: dict = field(default_factory=dict)


@dataclass
class AgentConfig:
    """
    Agent 角色配置
    
    对应 ECC 的 agents/code_architect.yaml
    """
    id: str
    name: str                           # 显示名称
    description: str                    # 角色描述
    system_prompt: str                  # 系统提示词
    capabilities: List[AgentCapability] # 能力列表
    tools: List[AgentTool]              # 绑定工具
    keywords: List[str]                # 触发关键词
    icon: str = "🤖"                    # 图标
    enabled: bool = True
    is_default: bool = False
    version: str = "1.0.0"
    author: str = "Hermes"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "system_prompt": self.system_prompt,
            "capabilities": [c.value for c in self.capabilities],
            "tools": [{"name": t.name, "description": t.description} for t in self.tools],
            "keywords": self.keywords,
            "icon": self.icon,
            "enabled": self.enabled,
            "is_default": self.is_default,
            "version": self.version,
            "author": self.author,
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> "AgentConfig":
        return cls(
            id=d["id"],
            name=d["name"],
            description=d["description"],
            system_prompt=d["system_prompt"],
            capabilities=[AgentCapability(c) for c in d.get("capabilities", [])],
            tools=[AgentTool(**t) for t in d.get("tools", [])],
            keywords=d.get("keywords", []),
            icon=d.get("icon", "🤖"),
            enabled=d.get("enabled", True),
            is_default=d.get("is_default", False),
            version=d.get("version", "1.0.0"),
            author=d.get("author", "Hermes"),
            created_at=d.get("created_at", time.time()),
            updated_at=d.get("updated_at", time.time()),
        )
    
    @classmethod
    def from_yaml(cls, yaml_path: Path) -> "AgentConfig":
        """从 YAML 文件加载"""
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)


class AgentManager:
    """
    Agent 管理器
    
    负责:
    - 加载/保存 Agent 配置
    - Agent 切换
    - 工具集绑定
    """
    
    DEFAULT_AGENTS = {
        "code_architect": AgentConfig(
            id="code_architect",
            name="Code Architect",
            description="代码架构师 - 专注架构设计、模式选择、可扩展性",
            system_prompt="""You are a Solution Designer focused on architecture, patterns, and scalability.

Your expertise:
- System design and architecture patterns
- Choosing the right tools and frameworks
- Code organization and module boundaries
- Scalability considerations
- Performance trade-offs

Rules:
1. Always ask clarifying questions before designing
2. Consider multiple设计方案 and trade-offs
3. Provide Mermaid diagrams for architecture
4. Never write uncommented code
5. Prefer composition over inheritance

Tools you use: code_analyze, gen_design_doc, mermaid_gen, doc_generator
When analyzing: identify patterns, suggest improvements, create architecture diagrams""",
            capabilities=[AgentCapability.CODE_ARCHITECT, AgentCapability.REFACTORING],
            tools=[
                AgentTool("code_analyze", "分析代码结构和模式"),
                AgentTool("gen_design_doc", "生成设计文档"),
                AgentTool("mermaid_gen", "生成Mermaid图表"),
            ],
            keywords=["架构", "设计", "模式", "结构", "architecture", "design", "pattern"],
            icon="🏗️",
            is_default=True,
        ),
        
        "debug_specialist": AgentConfig(
            id="debug_specialist",
            name="Debug Specialist",
            description="Bug猎人 - 分析日志、运行测试、追踪根因",
            system_prompt="""You are a Bug Hunter specializing in error diagnosis and root cause analysis.

Your expertise:
- Log analysis and pattern recognition
- Test-driven debugging
- Stack trace interpretation
- Memory leak detection
- Race condition identification

Debug workflow:
1. Gather evidence (logs, stack traces, error messages)
2. Form hypothesis
3. Create minimal reproduction case
4. Apply fix
5. Verify with tests

Tools you use: query_logs, run_test, explain_error, lnav, grex, dasel
When diagnosing: be systematic, test each hypothesis, document findings""",
            capabilities=[AgentCapability.DEBUG_SPECIALIST],
            tools=[
                AgentTool("query_logs", "查询和分析日志"),
                AgentTool("run_test", "运行测试验证"),
                AgentTool("explain_error", "解释错误信息"),
            ],
            keywords=["bug", "错误", "异常", "崩溃", "debug", "error", "crash", "fix"],
            icon="🔍",
        ),
        
        "code_review": AgentConfig(
            id="code_review",
            name="Code Reviewer",
            description="代码审查员 - 审查代码质量、安全性、性能",
            system_prompt="""You are a Senior Code Reviewer focused on quality, security, and best practices.

Your expertise:
- Code quality and readability
- Security vulnerabilities
- Performance issues
- Best practices and coding standards
- Test coverage

Review checklist:
1. Correctness - does it do what it claims?
2. Security - any vulnerabilities?
3. Performance - any bottlenecks?
4. Maintainability - is it readable and extensible?
5. Test coverage - are edge cases covered?

Provide actionable feedback with severity levels:
- 🔴 Critical: Must fix before merge
- 🟡 Warning: Should address
- 🟢 Suggestion: Consider improving

Tools you use: code_analyze, lint_check, security_scan, test_coverage""",
            capabilities=[AgentCapability.CODE_REVIEW, AgentCapability.SECURITY],
            tools=[
                AgentTool("code_analyze", "分析代码质量"),
                AgentTool("lint_check", "代码检查"),
                AgentTool("security_scan", "安全扫描"),
            ],
            keywords=["review", "审查", "检查", "质量", "安全"],
            icon="👀",
        ),
        
        "refactoring_expert": AgentConfig(
            id="refactoring_expert",
            name="Refactoring Expert",
            description="重构专家 - 代码优化、模式转换、技术债务清理",
            system_prompt="""You are a Refactoring Expert specialized in improving code structure without changing behavior.

Your expertise:
- Identifying code smells
- Applying refactoring patterns
- Improving code metrics
- Technical debt management
- Incremental refactoring

Refactoring principles:
1. Boy Scout Rule: leave code cleaner than you found it
2. Make changes in small, testable increments
3. Never refactor without tests
4. Document why, not just what

Common refactorings:
- Extract Method/Function
- Rename variables for clarity
- Replace conditional with polymorphism
- Merge duplicate code
- Split large functions

Tools you use: code_analyze, refactor_preview, apply_refactor, undo_refactor""",
            capabilities=[AgentCapability.REFACTORING, AgentCapability.CODE_ARCHITECT],
            tools=[
                AgentTool("code_analyze", "分析代码结构"),
                AgentTool("refactor_preview", "预览重构效果"),
                AgentTool("apply_refactor", "应用重构"),
            ],
            keywords=["refactor", "重构", "优化", "clean", "technical debt"],
            icon="🔧",
        ),
        
        "test_generator": AgentConfig(
            id="test_generator",
            name="Test Engineer",
            description="测试工程师 - 生成单元测试、集成测试、端到端测试",
            system_prompt="""You are a Test Engineer focused on comprehensive test coverage.

Your expertise:
- Unit testing best practices
- Test-driven development (TDD)
- Mocking and stubbing
- Edge case identification
- Property-based testing

Testing pyramid:
1. Many unit tests (fast, isolated)
2. Some integration tests
3. Few end-to-end tests (slow, brittle)

Test naming convention: method_expectedBehavior
Example: test_user_login_success, test_user_login_invalid_password

Test structure (Arrange-Act-Assert):
1. Set up test data
2. Execute the action
3. Assert expected results

Tools you use: generate_unit_tests, generate_integration_tests, run_coverage, test_template""",
            capabilities=[AgentCapability.TEST_GENERATOR],
            tools=[
                AgentTool("generate_unit_tests", "生成单元测试"),
                AgentTool("generate_integration_tests", "生成集成测试"),
                AgentTool("run_coverage", "运行覆盖率"),
            ],
            keywords=["test", "测试", "coverage", "单元测试", "集成测试"],
            icon="🧪",
        ),
    }
    
    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or (Path(__file__).parent.parent.parent / "config" / "ecc" / "agents")
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self._agents: Dict[str, AgentConfig] = {}
        self._current_agent_id: Optional[str] = None
        self._lock = threading.RLock()
        self._change_listeners: List[Callable] = []
        
        # 加载默认 Agent
        self._load_defaults()
        
        # 扫描 YAML 配置
        self._scan_configs()
    
    def _load_defaults(self):
        """加载默认 Agent"""
        for agent_id, agent in self.DEFAULT_AGENTS.items():
            self._agents[agent_id] = agent
    
    def _scan_configs(self):
        """扫描 YAML 配置文件"""
        if not self.config_dir.exists():
            return
        
        for yaml_file in self.config_dir.glob("*.yaml"):
            try:
                agent = AgentConfig.from_yaml(yaml_file)
                self._agents[agent.id] = agent
            except Exception as e:
                print(f"⚠️ 加载 Agent 配置失败 {yaml_file}: {e}")
    
    def register_agent(self, agent: AgentConfig) -> bool:
        """注册新 Agent"""
        with self._lock:
            self._agents[agent.id] = agent
            
            # 保存为 YAML
            self._save_yaml(agent)
            
            # 通知变化
            self._notify_change("register", agent)
            
            return True
    
    def unregister_agent(self, agent_id: str) -> bool:
        """注销 Agent"""
        with self._lock:
            if agent_id not in self._agents:
                return False
            
            agent = self._agents[agent_id]
            del self._agents[agent_id]
            
            # 删除 YAML
            yaml_path = self.config_dir / f"{agent_id}.yaml"
            if yaml_path.exists():
                yaml_path.unlink()
            
            # 如果是当前 Agent，切换到默认
            if self._current_agent_id == agent_id:
                self.switch_to("code_architect")
            
            self._notify_change("unregister", agent)
            return True
    
    def switch_to(self, agent_id: str) -> bool:
        """切换当前 Agent"""
        if agent_id not in self._agents:
            return False
        
        agent = self._agents[agent_id]
        if not agent.enabled:
            return False
        
        with self._lock:
            self._current_agent_id = agent_id
            self._notify_change("switch", agent)
        
        return True
    
    def get_current_agent(self) -> Optional[AgentConfig]:
        """获取当前 Agent"""
        if not self._current_agent_id:
            # 返回默认 Agent
            for agent in self._agents.values():
                if agent.is_default:
                    self._current_agent_id = agent.id
                    return agent
            # 如果没有默认，返回第一个
            if self._agents:
                self._current_agent_id = next(iter(self._agents.keys()))
                return self._agents[self._current_agent_id]
            return None
        
        return self._agents.get(self._current_agent_id)
    
    def get_agent(self, agent_id: str) -> Optional[AgentConfig]:
        """获取指定 Agent"""
        return self._agents.get(agent_id)
    
    def list_agents(self, enabled_only: bool = True) -> List[AgentConfig]:
        """列出所有 Agent"""
        agents = list(self._agents.values())
        if enabled_only:
            agents = [a for a in agents if a.enabled]
        return sorted(agents, key=lambda a: (not a.is_default, a.name))
    
    def match_agent(self, query: str) -> Optional[AgentConfig]:
        """
        根据查询字符串匹配 Agent
        
        匹配逻辑:
        1. 精确匹配 ID
        2. 匹配名称/描述
        3. 匹配关键词
        """
        query_lower = query.lower()
        
        # 1. 精确匹配
        if query_lower in self._agents:
            return self._agents[query_lower]
        
        # 2. 匹配名称和描述
        for agent in self._agents.values():
            if not agent.enabled:
                continue
            if (query_lower in agent.name.lower() or 
                query_lower in agent.description.lower()):
                return agent
        
        # 3. 匹配关键词
        for agent in self._agents.values():
            if not agent.enabled:
                continue
            for keyword in agent.keywords:
                if keyword.lower() in query_lower:
                    return agent
        
        return None
    
    def update_agent(self, agent_id: str, updates: dict) -> bool:
        """更新 Agent 配置"""
        if agent_id not in self._agents:
            return False
        
        agent = self._agents[agent_id]
        
        # 应用更新
        for key, value in updates.items():
            if hasattr(agent, key) and key not in ("id", "created_at"):
                setattr(agent, key, value)
        
        agent.updated_at = time.time()
        
        # 保存
        self._save_yaml(agent)
        self._notify_change("update", agent)
        
        return True
    
    def _save_yaml(self, agent: AgentConfig):
        """保存 Agent 为 YAML"""
        yaml_path = self.config_dir / f"{agent.id}.yaml"
        
        # 转换为 YAML 格式
        data = agent.to_dict()
        
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    
    def on_change(self, callback: Callable):
        """注册变化监听器"""
        self._change_listeners.append(callback)
    
    def _notify_change(self, event: str, agent: AgentConfig):
        """通知变化"""
        for listener in self._change_listeners:
            try:
                listener(event, agent)
            except Exception as e:
                print(f"Agent change listener error: {e}")
    
    def get_system_prompt(self, agent_id: Optional[str] = None) -> str:
        """获取 Agent 的系统提示词"""
        agent = self._agents.get(agent_id) if agent_id else self.get_current_agent()
        if not agent:
            return ""
        return agent.system_prompt
    
    def get_tools_for_agent(self, agent_id: Optional[str] = None) -> List[str]:
        """获取 Agent 绑定的工具列表"""
        agent = self._agents.get(agent_id) if agent_id else self.get_current_agent()
        if not agent:
            return []
        return [t.name for t in agent.tools]


# 单例
_agent_manager: Optional[AgentManager] = None


def get_agent_manager() -> AgentManager:
    """获取 Agent 管理器单例"""
    global _agent_manager
    if _agent_manager is None:
        _agent_manager = AgentManager()
    return _agent_manager