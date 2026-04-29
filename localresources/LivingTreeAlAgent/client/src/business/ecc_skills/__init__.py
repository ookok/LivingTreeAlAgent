"""
ECC Skill System - 可复用工作流系统
Inspired by Everything Claude Code (ECC)

Skill 是参数化、可组合的工作流单元
可以被 Agent 调用，也能被 Rules 自动触发

核心概念:
- Skill: 封装了工具链的工作流
- Trigger: 触发条件 (命令/事件)
- Context: 运行时上下文
"""

import json
import uuid
import time
import asyncio
import threading
import inspect
from pathlib import Path
from typing import Optional, Callable, Dict, List, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import yaml


class SkillCategory(Enum):
    """Skill 分类"""
    CODE_ANALYSIS = "code_analysis"       # 代码分析
    CODE_GENERATION = "code_generation"   # 代码生成
    REFACTORING = "refactoring"           # 重构
    TESTING = "testing"                   # 测试
    DOCUMENTATION = "documentation"       # 文档
    DEBUGGING = "debugging"               # 调试
    SECURITY = "security"                 # 安全
    PERFORMANCE = "performance"            # 性能
    DEPLOYMENT = "deployment"             # 部署
    INTEGRATION = "integration"           # 集成


@dataclass
class SkillParameter:
    """Skill 参数定义"""
    name: str
    type: str                    # string, integer, boolean, array, object
    description: str = ""
    default: Any = None
    required: bool = False
    enum_values: List[Any] = field(default_factory=list)


@dataclass
class SkillStep:
    """Skill 工作流步骤"""
    name: str
    description: str = ""
    action: str                  # 动作类型: tool, condition, loop, parallel
    config: Dict[str, Any] = field(default_factory=dict)  # 配置参数
    
    # Tool 动作
    tool_name: str = ""          # 工具名称
    parameters: Dict[str, Any] = field(default_factory=dict)  # 工具参数
    
    # Condition 动作
    condition: str = ""           # 条件表达式
    true_branch: List["SkillStep"] = field(default_factory=list)  # 条件为真时执行
    false_branch: List["SkillStep"] = field(default_factory=list)  # 条件为假时执行
    
    # Loop 动作
    items: str = ""              # 迭代项
    loop_body: List["SkillStep"] = field(default_factory=list)  # 循环体


@dataclass
class SkillConfig:
    """
    Skill 配置
    
    对应 ECC 的 skills/code_review.py
    """
    id: str
    name: str                           # Skill 名称
    description: str                    # 功能描述
    category: SkillCategory              # 分类
    version: str = "1.0.0"
    author: str = "Hermes"
    
    # 参数定义
    parameters: List[SkillParameter] = field(default_factory=list)
    
    # 工作流步骤
    steps: List[SkillStep] = field(default_factory=list)
    
    # 触发条件
    triggers: List[str] = field(default_factory=list)  # 触发词列表
    
    # 依赖
    dependencies: List[str] = field(default_factory=list)  # 依赖工具
    required_files: List[str] = field(default_factory=list)  # 必需文件
    
    # 元数据
    icon: str = "⚡"
    enabled: bool = True
    is_async: bool = False
    timeout: int = 300  # 超时秒数
    
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    
    # 执行统计
    use_count: int = 0
    success_count: int = 0
    avg_duration: float = 0.0  # 平均执行时长(秒)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "version": self.version,
            "author": self.author,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type,
                    "description": p.description,
                    "default": p.default,
                    "required": p.required,
                    "enum_values": p.enum_values,
                }
                for p in self.parameters
            ],
            "steps": self._serialize_steps(self.steps),
            "triggers": self.triggers,
            "dependencies": self.dependencies,
            "required_files": self.required_files,
            "icon": self.icon,
            "enabled": self.enabled,
            "is_async": self.is_async,
            "timeout": self.timeout,
            "use_count": self.use_count,
            "success_count": self.success_count,
            "avg_duration": self.avg_duration,
        }
    
    def _serialize_steps(self, steps: List[SkillStep]) -> List[dict]:
        """序列化步骤"""
        result = []
        for step in steps:
            s = {
                "name": step.name,
                "description": step.description,
                "action": step.action,
                "config": step.config,
            }
            if step.action == "tool":
                s["tool_name"] = step.tool_name
                s["parameters"] = step.parameters
            elif step.action == "condition":
                s["condition"] = step.condition
                s["true_branch"] = self._serialize_steps(step.true_branch)
                s["false_branch"] = self._serialize_steps(step.false_branch)
            elif step.action == "loop":
                s["items"] = step.items
                s["loop_body"] = self._serialize_steps(step.loop_body)
            result.append(s)
        return result
    
    @classmethod
    def from_dict(cls, d: dict) -> "SkillConfig":
        cat = SkillCategory(d.get("category", "code_analysis"))
        return cls(
            id=d["id"],
            name=d["name"],
            description=d["description"],
            category=cat,
            version=d.get("version", "1.0.0"),
            author=d.get("author", "Hermes"),
            parameters=[SkillParameter(**p) for p in d.get("parameters", [])],
            steps=cls._deserialize_steps(d.get("steps", [])),
            triggers=d.get("triggers", []),
            dependencies=d.get("dependencies", []),
            required_files=d.get("required_files", []),
            icon=d.get("icon", "⚡"),
            enabled=d.get("enabled", True),
            is_async=d.get("is_async", False),
            timeout=d.get("timeout", 300),
            use_count=d.get("use_count", 0),
            success_count=d.get("success_count", 0),
            avg_duration=d.get("avg_duration", 0.0),
            created_at=d.get("created_at", time.time()),
            updated_at=d.get("updated_at", time.time()),
        )
    
    @classmethod
    def _deserialize_steps(cls, steps_data: List[dict]) -> List[SkillStep]:
        """反序列化步骤"""
        steps = []
        for s in steps_data:
            step = SkillStep(
                name=s["name"],
                description=s.get("description", ""),
                action=s["action"],
                config=s.get("config", {}),
                tool_name=s.get("tool_name", ""),
                parameters=s.get("parameters", {}),
                condition=s.get("condition", ""),
                items=s.get("items", ""),
            )
            
            if step.action == "condition":
                step.true_branch = cls._deserialize_steps(s.get("true_branch", []))
                step.false_branch = cls._deserialize_steps(s.get("false_branch", []))
            elif step.action == "loop":
                step.loop_body = cls._deserialize_steps(s.get("loop_body", []))
            
            steps.append(step)
        return steps
    
    @classmethod
    def from_yaml(cls, yaml_path: Path) -> "SkillConfig":
        """从 YAML 文件加载"""
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)


@dataclass
class SkillExecution:
    """Skill 执行上下文"""
    skill_id: str
    parameters: Dict[str, Any]
    context: Dict[str, Any]  # 运行时上下文
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    status: str = "running"  # running, success, failed, cancelled
    result: Any = None
    error: str = ""
    steps_completed: int = 0
    total_steps: int = 0
    
    def mark_success(self, result: Any):
        self.status = "success"
        self.result = result
        self.completed_at = time.time()
    
    def mark_failed(self, error: str):
        self.status = "failed"
        self.error = error
        self.completed_at = time.time()
    
    def get_duration(self) -> float:
        if self.completed_at:
            return self.completed_at - self.started_at
        return time.time() - self.started_at


class SkillRegistry:
    """
    Skill 注册表
    
    管理所有 Skill 的注册、发现、执行
    """
    
    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or (Path(__file__).parent.parent.parent / "config" / "ecc" / "skills")
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self._skills: Dict[str, SkillConfig] = {}
        self._executors: Dict[str, Callable] = {}  # Python 函数执行器
        self._lock = threading.RLock()
        self._listeners: List[Callable] = []
        
        # 内置 Skill
        self._register_builtin_skills()
        
        # 扫描 YAML 配置
        self._scan_configs()
    
    def _register_builtin_skills(self):
        """注册内置 Skill"""
        builtin_skills = [
            self._create_code_review_skill(),
            self._create_format_code_skill(),
            self._create_lint_check_skill(),
            self._create_test_generation_skill(),
            self._create_doc_generation_skill(),
            self._create_security_scan_skill(),
            self._create_performance_analysis_skill(),
        ]
        
        for skill in builtin_skills:
            self._skills[skill.id] = skill
    
    def _create_code_review_skill(self) -> SkillConfig:
        """创建代码审查 Skill"""
        return SkillConfig(
            id="code_review",
            name="Code Review",
            description="代码审查工作流 - 分析代码质量、安全性、性能",
            category=SkillCategory.CODE_ANALYSIS,
            parameters=[
                SkillParameter("file_path", "string", "文件路径", required=True),
                SkillParameter("checklist", "string", "审查清单类型", default="default", 
                             enum_values=["default", "security", "performance", "style"]),
            ],
            steps=[
                SkillStep(
                    name="analyze_code",
                    description="分析代码结构",
                    action="tool",
                    tool_name="code_analyze",
                    parameters={"file_path": "${file_path}"},
                ),
                SkillStep(
                    name="run_linter",
                    description="运行代码检查",
                    action="tool",
                    tool_name="lint_check",
                    parameters={"file_path": "${file_path}"},
                ),
                SkillStep(
                    name="check_security",
                    description="安全扫描",
                    action="condition",
                    condition="${checklist} == 'security'",
                    true_branch=[
                        SkillStep(
                            name="security_scan",
                            description="执行安全扫描",
                            action="tool",
                            tool_name="security_scan",
                            parameters={"file_path": "${file_path}"},
                        )
                    ],
                ),
            ],
            triggers=["代码审查", "review", "审查", "检查代码"],
            dependencies=["code_analyze", "lint_check", "security_scan"],
            icon="👀",
        )
    
    def _create_format_code_skill(self) -> SkillConfig:
        """创建代码格式化 Skill"""
        return SkillConfig(
            id="format_code",
            name="Format Code",
            description="自动格式化代码",
            category=SkillCategory.REFACTORING,
            parameters=[
                SkillParameter("file_path", "string", "文件路径", required=True),
                SkillParameter("style", "string", "代码风格", default="default"),
            ],
            steps=[
                SkillStep(
                    name="format",
                    description="格式化代码",
                    action="tool",
                    tool_name="format_code",
                    parameters={"file_path": "${file_path}", "style": "${style}"},
                ),
            ],
            triggers=["格式化", "format", "整理代码"],
            dependencies=["format_code"],
            icon="✨",
        )
    
    def _create_lint_check_skill(self) -> SkillConfig:
        """创建代码检查 Skill"""
        return SkillConfig(
            id="lint_check",
            name="Lint Check",
            description="运行代码检查",
            category=SkillCategory.CODE_ANALYSIS,
            parameters=[
                SkillParameter("file_path", "string", "文件路径", required=True),
            ],
            steps=[
                SkillStep(
                    name="lint",
                    description="执行代码检查",
                    action="tool",
                    tool_name="lint_check",
                    parameters={"file_path": "${file_path}"},
                ),
            ],
            triggers=["lint", "检查", "代码检查"],
            dependencies=["lint_check"],
            icon="🔎",
        )
    
    def _create_test_generation_skill(self) -> SkillConfig:
        """创建测试生成 Skill"""
        return SkillConfig(
            id="generate_tests",
            name="Generate Tests",
            description="生成单元测试和集成测试",
            category=SkillCategory.TESTING,
            parameters=[
                SkillParameter("file_path", "string", "源文件路径", required=True),
                SkillParameter("test_type", "string", "测试类型", default="unit",
                             enum_values=["unit", "integration", "e2e"]),
            ],
            steps=[
                SkillStep(
                    name="analyze_code",
                    description="分析代码结构",
                    action="tool",
                    tool_name="code_analyze",
                    parameters={"file_path": "${file_path}"},
                ),
                SkillStep(
                    name="generate",
                    description="生成测试",
                    action="tool",
                    tool_name="generate_unit_tests" if "${test_type}" == "unit" else "generate_integration_tests",
                    parameters={"file_path": "${file_path}"},
                ),
            ],
            triggers=["测试", "test", "生成测试", "单元测试"],
            dependencies=["code_analyze", "generate_unit_tests", "generate_integration_tests"],
            icon="🧪",
        )
    
    def _create_doc_generation_skill(self) -> SkillConfig:
        """创建文档生成 Skill"""
        return SkillConfig(
            id="generate_docs",
            name="Generate Documentation",
            description="从代码生成文档",
            category=SkillCategory.DOCUMENTATION,
            parameters=[
                SkillParameter("file_path", "string", "文件路径", required=True),
                SkillParameter("format", "string", "文档格式", default="markdown",
                             enum_values=["markdown", "html", "pdf"]),
            ],
            steps=[
                SkillStep(
                    name="parse_code",
                    description="解析代码结构",
                    action="tool",
                    tool_name="parse_code_structure",
                    parameters={"file_path": "${file_path}"},
                ),
                SkillStep(
                    name="generate",
                    description="生成文档",
                    action="tool",
                    tool_name="generate_doc",
                    parameters={"file_path": "${file_path}", "format": "${format}"},
                ),
            ],
            triggers=["文档", "doc", "生成文档", "注释"],
            dependencies=["parse_code_structure", "generate_doc"],
            icon="📝",
        )
    
    def _create_security_scan_skill(self) -> SkillConfig:
        """创建安全扫描 Skill"""
        return SkillConfig(
            id="security_scan",
            name="Security Scan",
            description="扫描代码安全漏洞",
            category=SkillCategory.SECURITY,
            parameters=[
                SkillParameter("file_path", "string", "文件路径", required=True),
            ],
            steps=[
                SkillStep(
                    name="scan",
                    description="执行安全扫描",
                    action="tool",
                    tool_name="security_scan",
                    parameters={"file_path": "${file_path}"},
                ),
                SkillStep(
                    name="report",
                    description="生成安全报告",
                    action="tool",
                    tool_name="generate_security_report",
                    parameters={"file_path": "${file_path}"},
                ),
            ],
            triggers=["安全", "security", "漏洞", "扫描"],
            dependencies=["security_scan", "generate_security_report"],
            icon="🔒",
        )
    
    def _create_performance_analysis_skill(self) -> SkillConfig:
        """创建性能分析 Skill"""
        return SkillConfig(
            id="performance_analysis",
            name="Performance Analysis",
            description="分析代码性能瓶颈",
            category=SkillCategory.PERFORMANCE,
            parameters=[
                SkillParameter("file_path", "string", "文件路径", required=True),
            ],
            steps=[
                SkillStep(
                    name="analyze",
                    description="分析性能",
                    action="tool",
                    tool_name="analyze_performance",
                    parameters={"file_path": "${file_path}"},
                ),
                SkillStep(
                    name="suggest",
                    description="生成优化建议",
                    action="tool",
                    tool_name="suggest_optimizations",
                    parameters={"file_path": "${file_path}"},
                ),
            ],
            triggers=["性能", "performance", "优化", "瓶颈"],
            dependencies=["analyze_performance", "suggest_optimizations"],
            icon="⚡",
        )
    
    def _scan_configs(self):
        """扫描 YAML 配置"""
        if not self.config_dir.exists():
            return
        
        for yaml_file in self.config_dir.glob("*.yaml"):
            try:
                skill = SkillConfig.from_yaml(yaml_file)
                self._skills[skill.id] = skill
            except Exception as e:
                print(f"⚠️ 加载 Skill 配置失败 {yaml_file}: {e}")
    
    def register_skill(self, skill: SkillConfig) -> bool:
        """注册 Skill"""
        with self._lock:
            self._skills[skill.id] = skill
            
            # 保存为 YAML
            self._save_yaml(skill)
            
            # 通知
            self._notify("register", skill)
            
            return True
    
    def unregister_skill(self, skill_id: str) -> bool:
        """注销 Skill"""
        with self._lock:
            if skill_id not in self._skills:
                return False
            
            skill = self._skills[skill_id]
            del self._skills[skill_id]
            
            # 删除 YAML
            yaml_path = self.config_dir / f"{skill_id}.yaml"
            if yaml_path.exists():
                yaml_path.unlink()
            
            self._notify("unregister", skill)
            return True
    
    def get_skill(self, skill_id: str) -> Optional[SkillConfig]:
        """获取 Skill"""
        return self._skills.get(skill_id)
    
    def list_skills(self, category: Optional[SkillCategory] = None, 
                   enabled_only: bool = True) -> List[SkillConfig]:
        """列出 Skill"""
        skills = list(self._skills.values())
        
        if enabled_only:
            skills = [s for s in skills if s.enabled]
        
        if category:
            skills = [s for s in skills if s.category == category]
        
        return sorted(skills, key=lambda s: s.name)
    
    def match_skill(self, query: str) -> Optional[SkillConfig]:
        """根据查询匹配 Skill"""
        query_lower = query.lower()
        
        # 精确匹配
        if query_lower in self._skills:
            return self._skills[query_lower]
        
        # 匹配名称和描述
        for skill in self._skills.values():
            if not skill.enabled:
                continue
            if (query_lower in skill.name.lower() or 
                query_lower in skill.description.lower()):
                return skill
        
        # 匹配触发词
        for skill in self._skills.values():
            if not skill.enabled:
                continue
            for trigger in skill.triggers:
                if trigger.lower() in query_lower:
                    return skill
        
        return None
    
    def register_executor(self, skill_id: str, executor: Callable):
        """注册 Python 函数执行器"""
        self._executors[skill_id] = executor
    
    async def execute(self, skill_id: str, parameters: Dict[str, Any], 
                     context: Optional[Dict[str, Any]] = None) -> SkillExecution:
        """执行 Skill"""
        skill = self._skills.get(skill_id)
        if not skill:
            execution = SkillExecution(
                skill_id=skill_id,
                parameters=parameters,
                context=context or {},
                status="failed",
            )
            execution.mark_failed(f"Skill not found: {skill_id}")
            return execution
        
        execution = SkillExecution(
            skill_id=skill_id,
            parameters=parameters,
            context=context or {},
            total_steps=len(skill.steps),
        )
        
        # 如果有 Python 执行器，优先使用
        if skill_id in self._executors:
            try:
                executor = self._executors[skill_id]
                if asyncio.iscoroutinefunction(executor):
                    result = await executor(**parameters)
                else:
                    result = executor(**parameters)
                execution.mark_success(result)
            except Exception as e:
                execution.mark_failed(str(e))
        else:
            # 执行工作流步骤
            try:
                result = await self._execute_steps(skill.steps, parameters, execution)
                execution.mark_success(result)
            except Exception as e:
                execution.mark_failed(str(e))
        
        # 更新统计
        self._update_stats(skill, execution)
        
        return execution
    
    async def _execute_steps(self, steps: List[SkillStep], 
                           parameters: Dict[str, Any], 
                           execution: SkillExecution) -> Any:
        """执行工作流步骤"""
        results = []
        
        for step in steps:
            # 参数替换
            params = self._interpolate(step.parameters, parameters, results)
            
            if step.action == "tool":
                # 执行工具
                result = await self._execute_tool(step, params)
                results.append({"step": step.name, "result": result})
                execution.steps_completed += 1
                
            elif step.action == "condition":
                # 条件判断
                condition_value = self._eval_condition(step.condition, parameters, results)
                if condition_value:
                    sub_result = await self._execute_steps(step.true_branch, parameters, execution)
                    results.append({"step": step.name, "result": sub_result, "branch": "true"})
                else:
                    sub_result = await self._execute_steps(step.false_branch, parameters, execution)
                    results.append({"step": step.name, "result": sub_result, "branch": "false"})
                    
            elif step.action == "loop":
                # 循环
                items = self._get_loop_items(step.items, parameters, results)
                loop_results = []
                for item in items:
                    # 更新循环上下文
                    loop_params = parameters.copy()
                    loop_params[step.items] = item
                    sub_result = await self._execute_steps(step.loop_body, loop_params, execution)
                    loop_results.append(sub_result)
                results.append({"step": step.name, "result": loop_results})
        
        return results
    
    async def _execute_tool(self, step: SkillStep, parameters: Dict[str, Any]) -> Any:
        """执行工具"""
        # 获取工具执行器
        from core.tools_registry import ToolRegistry
        
        tool = ToolRegistry.get(step.tool_name)
        if not tool:
            # 尝试通过 ToolDispatcher
            from core.tools_registry import ToolDispatcher
            dispatcher = ToolDispatcher({})
            result = dispatcher.dispatch(step.tool_name, parameters)
            return result
        
        # 执行工具
        return tool.handler({}, **parameters)
    
    def _interpolate(self, template: Any, parameters: Dict[str, Any], 
                    results: List[Dict]) -> Dict[str, Any]:
        """参数插值 - 替换 ${xxx} 模板变量"""
        if isinstance(template, dict):
            return {k: self._interpolate(v, parameters, results) for k, v in template.items()}
        elif isinstance(template, list):
            return [self._interpolate(item, parameters, results) for item in template]
        elif isinstance(template, str):
            # 替换 ${xxx} 格式的变量
            import re
            def replace_var(match):
                var_name = match.group(1)
                if var_name in parameters:
                    return str(parameters[var_name])
                return match.group(0)
            return re.sub(r'\$\{([^}]+)\}', replace_var, template)
        return template
    
    def _eval_condition(self, condition: str, parameters: Dict[str, Any], 
                       results: List[Dict]) -> bool:
        """评估条件表达式"""
        # 简单实现 - 支持 ==, !=, in 等操作符
        import re
        
        # 替换变量
        def replace_var(match):
            var_name = match.group(1)
            value = parameters.get(var_name, "")
            if isinstance(value, str):
                return f'"{value}"'
            return str(value)
        
        expr = re.sub(r'\$\{([^}]+)\}', replace_var, condition)
        
        try:
            return eval(expr)
        except Exception:
            return False
    
    def _get_loop_items(self, items_expr: str, parameters: Dict[str, Any], 
                       results: List[Dict]) -> List[Any]:
        """获取循环项"""
        # 支持 ${items} 格式
        if items_expr.startswith("${") and items_expr.endswith("}"):
            var_name = items_expr[2:-1]
            value = parameters.get(var_name, [])
            if isinstance(value, list):
                return value
        return []
    
    def _update_stats(self, skill: SkillConfig, execution: SkillExecution):
        """更新执行统计"""
        skill.use_count += 1
        if execution.status == "success":
            skill.success_count += 1
        
        # 更新平均时长
        duration = execution.get_duration()
        if skill.avg_duration == 0:
            skill.avg_duration = duration
        else:
            skill.avg_duration = (skill.avg_duration * (skill.use_count - 1) + duration) / skill.use_count
        
        # 保存
        self._save_yaml(skill)
    
    def _save_yaml(self, skill: SkillConfig):
        """保存 Skill 为 YAML"""
        yaml_path = self.config_dir / f"{skill.id}.yaml"
        
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(skill.to_dict(), f, allow_unicode=True, 
                     default_flow_style=False, sort_keys=False)
    
    def on_change(self, callback: Callable):
        """注册变化监听器"""
        self._listeners.append(callback)
    
    def _notify(self, event: str, skill: SkillConfig):
        """通知变化"""
        for listener in self._listeners:
            try:
                listener(event, skill)
            except Exception as e:
                print(f"Skill listener error: {e}")


# 单例
_skill_registry: Optional[SkillRegistry] = None


def get_skill_registry() -> SkillRegistry:
    """获取 Skill 注册表单例"""
    global _skill_registry
    if _skill_registry is None:
        _skill_registry = SkillRegistry()
    return _skill_registry


# 便捷装饰器
def skill(name: str, description: str, category: SkillCategory = SkillCategory.CODE_ANALYSIS,
         triggers: List[str] = None):
    """Skill 注册装饰器"""
    def decorator(func: Callable):
        registry = get_skill_registry()
        
        # 构建 Skill 配置
        skill_config = SkillConfig(
            id=name,
            name=name.replace("_", " ").title(),
            description=description,
            category=category,
            triggers=triggers or [],
        )
        
        # 注册
        registry.register_skill(skill_config)
        registry.register_executor(name, func)
        
        return func
    return decorator