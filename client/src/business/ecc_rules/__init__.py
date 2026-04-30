"""
ECC Rule System - 事件驱动自动化规则
Inspired by Everything Claude Code (ECC)

Rule 是事件驱动的自动化规则
监听 IDE 事件，自动触发 Action

核心概念:
- Rule: 规则定义 (条件 + 动作)
- Event: IDE 事件 (file_saved, terminal_error, etc.)
- Action: 执行的动作 (run_skill, switch_agent, etc.)

内置事件:
- file_saved: 文件保存时
- file_created: 文件创建时
- file_deleted: 文件删除时
- terminal_error: 终端错误时
- build_failed: 构建失败时
- test_failed: 测试失败时
- session_start: 会话开始时
- session_end: 会话结束时
- agent_switch: Agent 切换时
- custom: 自定义事件
"""

import json
import uuid
import time
import asyncio
import threading
from pathlib import Path
from typing import Optional, Callable, Dict, List, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import yaml
import fnmatch


class EventType(Enum):
    """内置事件类型"""
    FILE_SAVED = "file_saved"
    FILE_CREATED = "file_created"
    FILE_DELETED = "file_deleted"
    FILE_MODIFIED = "file_modified"
    TERMINAL_ERROR = "terminal_error"
    BUILD_FAILED = "build_failed"
    TEST_FAILED = "test_failed"
    BUILD_SUCCESS = "build_success"
    TEST_SUCCESS = "test_success"
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    AGENT_SWITCH = "agent_switch"
    CUSTOM = "custom"


class ActionType(Enum):
    """动作类型"""
    RUN_SKILL = "run_skill"
    SWITCH_AGENT = "switch_agent"
    RUN_COMMAND = "run_command"
    SHOW_NOTIFICATION = "show_notification"
    PLAY_SOUND = "play_sound"
    LOG_MESSAGE = "log_message"
    CALLBACK = "callback"


@dataclass
class RuleCondition:
    """规则条件"""
    event_type: EventType
    file_pattern: str = ""
    agent_id: str = ""
    custom_filter: str = ""


@dataclass
class RuleAction:
    """规则动作"""
    action_type: ActionType
    config: Dict[str, Any] = field(default_factory=dict)
    skill_id: str = ""
    skill_parameters: Dict[str, Any] = field(default_factory=dict)
    target_agent_id: str = ""
    command: str = ""
    working_dir: str = ""
    notification_title: str = ""
    notification_message: str = ""
    notification_level: str = "info"
    sound_file: str = ""
    log_level: str = "info"
    log_message: str = ""
    callback_function: str = ""


@dataclass
class RuleConfig:
    """Rule 配置"""
    id: str
    name: str
    description: str = ""
    enabled: bool = True
    priority: int = 0
    conditions: List[RuleCondition] = field(default_factory=list)
    actions: List[RuleAction] = field(default_factory=list)
    max_executions_per_hour: int = 0
    cooldown_seconds: int = 0
    execution_count: int = 0
    last_executed_at: Optional[float] = None
    last_triggered_by: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "enabled": self.enabled,
            "priority": self.priority,
            "conditions": [
                {
                    "event_type": c.event_type.value,
                    "file_pattern": c.file_pattern,
                    "agent_id": c.agent_id,
                    "custom_filter": c.custom_filter,
                }
                for c in self.conditions
            ],
            "actions": self._serialize_actions(),
            "max_executions_per_hour": self.max_executions_per_hour,
            "cooldown_seconds": self.cooldown_seconds,
            "execution_count": self.execution_count,
            "last_executed_at": self.last_executed_at,
            "last_triggered_by": self.last_triggered_by,
        }

    def _serialize_actions(self) -> List[dict]:
        result = []
        for action in self.actions:
            a = {
                "action_type": action.action_type.value,
                "config": action.config,
            }
            for field_name in ["skill_id", "skill_parameters", "target_agent_id", "command",
                             "working_dir", "notification_title", "notification_message",
                             "notification_level", "sound_file", "log_level", 
                             "log_message", "callback_function"]:
                if hasattr(action, field_name):
                    a[field_name] = getattr(action, field_name)
            result.append(a)
        return result

    @classmethod
    def from_dict(cls, d: dict) -> "RuleConfig":
        conditions = []
        for c in d.get("conditions", []):
            conditions.append(RuleCondition(
                event_type=EventType(c.get("event_type", "custom")),
                file_pattern=c.get("file_pattern", ""),
                agent_id=c.get("agent_id", ""),
                custom_filter=c.get("custom_filter", ""),
            ))

        actions = []
        for a in d.get("actions", []):
            action = RuleAction(
                action_type=ActionType(a.get("action_type", "callback")),
                config=a.get("config", {}),
            )
            for field_name in ["skill_id", "skill_parameters", "target_agent_id", "command",
                             "working_dir", "notification_title", "notification_message",
                             "notification_level", "sound_file", "log_level",
                             "log_message", "callback_function"]:
                if field_name in a:
                    setattr(action, field_name, a[field_name])
            actions.append(action)

        return cls(
            id=d["id"],
            name=d["name"],
            description=d.get("description", ""),
            enabled=d.get("enabled", True),
            priority=d.get("priority", 0),
            conditions=conditions,
            actions=actions,
            max_executions_per_hour=d.get("max_executions_per_hour", 0),
            cooldown_seconds=d.get("cooldown_seconds", 0),
            execution_count=d.get("execution_count", 0),
            last_executed_at=d.get("last_executed_at"),
            last_triggered_by=d.get("last_triggered_by"),
            created_at=d.get("created_at", time.time()),
            updated_at=d.get("updated_at", time.time()),
        )

    @classmethod
    def from_yaml(cls, yaml_path: Path) -> "RuleConfig":
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data)


class RuleEngine:
    """Rule 引擎 - 管理规则注册、事件监听、规则匹配和执行"""

    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or (Path(__file__).parent.parent.parent / "config" / "ecc" / "rules")
        self.config_dir.mkdir(parents=True, exist_ok=True)

        self._rules: Dict[str, RuleConfig] = {}
        self._event_handlers: Dict[EventType, List[Callable]] = {}
        self._callbacks: Dict[str, Callable] = {}
        self._lock = threading.Lock()
        self._listeners: List[Callable] = []
        self._execution_history: List[Dict] = []
        self._max_history = 1000

        self._register_builtin_rules()
        self._scan_configs()

    def _register_builtin_rules(self):
        """注册内置规则"""
        builtin_rules = [
            self._create_py_save_rule(),
            self._create_error_diagnosis_rule(),
            self._create_test_failed_rule(),
        ]
        for rule in builtin_rules:
            self._rules[rule.id] = rule

    def _create_py_save_rule(self) -> RuleConfig:
        return RuleConfig(
            id="auto_format_py",
            name="Auto Format Python",
            description="保存 .py 文件时自动格式化",
            priority=10,
            conditions=[
                RuleCondition(event_type=EventType.FILE_SAVED, file_pattern="*.py"),
            ],
            actions=[
                RuleAction(
                    action_type=ActionType.RUN_SKILL,
                    skill_id="format_code",
                    skill_parameters={"file_path": "${file_path}"},
                ),
            ],
        )

    def _create_error_diagnosis_rule(self) -> RuleConfig:
        return RuleConfig(
            id="auto_diagnose_error",
            name="Auto Diagnose Errors",
            description="终端出现错误时自动调用 Debug Specialist",
            priority=50,
            conditions=[
                RuleCondition(event_type=EventType.TERMINAL_ERROR),
            ],
            actions=[
                RuleAction(
                    action_type=ActionType.SWITCH_AGENT,
                    target_agent_id="debug_specialist",
                ),
            ],
        )

    def _create_test_failed_rule(self) -> RuleConfig:
        return RuleConfig(
            id="test_failed_handler",
            name="Test Failure Handler",
            description="测试失败时自动调用 Debug Specialist",
            priority=40,
            conditions=[
                RuleCondition(event_type=EventType.TEST_FAILED),
            ],
            actions=[
                RuleAction(
                    action_type=ActionType.SWITCH_AGENT,
                    target_agent_id="debug_specialist",
                ),
            ],
        )

    def _scan_configs(self):
        if not self.config_dir.exists():
            return
        for yaml_file in self.config_dir.glob("*.yaml"):
            try:
                rule = RuleConfig.from_yaml(yaml_file)
                self._rules[rule.id] = rule
            except Exception as e:
                print(f"Failed to load Rule {yaml_file}: {e}")

    def register_rule(self, rule: RuleConfig) -> bool:
        with self._lock:
            self._rules[rule.id] = rule
            self._save_yaml(rule)
            return True

    def unregister_rule(self, rule_id: str) -> bool:
        with self._lock:
            if rule_id not in self._rules:
                return False
            del self._rules[rule_id]
            yaml_path = self.config_dir / f"{rule_id}.yaml"
            if yaml_path.exists():
                yaml_path.unlink()
            return True

    def get_rule(self, rule_id: str) -> Optional[RuleConfig]:
        return self._rules.get(rule_id)

    def list_rules(self, enabled_only: bool = True) -> List[RuleConfig]:
        rules = list(self._rules.values())
        if enabled_only:
            rules = [r for r in rules if r.enabled]
        return sorted(rules, key=lambda r: -r.priority)

    def register_callback(self, name: str, callback: Callable):
        self._callbacks[name] = callback

    def on_event(self, event_type: Union[EventType, str]):
        if isinstance(event_type, str):
            event_type = EventType(event_type)
        def decorator(func: Callable):
            self._event_handlers.setdefault(event_type, []).append(func)
            return func
        return decorator

    async def trigger(self, event_type: Union[EventType, str],
                    event_data: Dict[str, Any]) -> List[Dict]:
        if isinstance(event_type, str):
            event_type = EventType(event_type)

        results = []
        matching_rules = self._get_matching_rules(event_type, event_data)

        for rule in matching_rules:
            try:
                result = await self._execute_rule(rule, event_data)
                results.append({"rule_id": rule.id, "status": "success", "result": result})
                rule.execution_count += 1
                rule.last_executed_at = time.time()
                rule.last_triggered_by = event_type.value
                self._save_yaml(rule)
            except Exception as e:
                results.append({"rule_id": rule.id, "status": "error", "error": str(e)})

        # Trigger registered handlers
        for handler in self._event_handlers.get(event_type, []):
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event_data)
                else:
                    handler(event_data)
            except Exception as e:
                print(f"Event handler error: {e}")

        self._execution_history.append({
            "event_type": event_type.value,
            "event_data": event_data,
            "rules_triggered": len(results),
            "timestamp": time.time(),
        })
        if len(self._execution_history) > self._max_history:
            self._execution_history = self._execution_history[-self._max_history:]

        return results

    def _get_matching_rules(self, event_type: EventType,
                          event_data: Dict[str, Any]) -> List[RuleConfig]:
        matching = []
        for rule in self._rules.values():
            if not rule.enabled:
                continue
            if rule.last_executed_at:
                elapsed = time.time() - rule.last_executed_at
                if elapsed < rule.cooldown_seconds:
                    continue
            for condition in rule.conditions:
                if condition.event_type != event_type:
                    continue
                if condition.file_pattern:
                    file_path = event_data.get("file_path", "")
                    if not fnmatch.fnmatch(file_path, condition.file_pattern):
                        continue
                matching.append(rule)
                break
        return sorted(matching, key=lambda r: -r.priority)

    async def _execute_rule(self, rule: RuleConfig,
                          event_data: Dict[str, Any]) -> Dict[str, Any]:
        results = {}
        for action in rule.actions:
            try:
                result = await self._execute_action(action, event_data)
                results[action.action_type.value] = result
            except Exception as e:
                results[action.action_type.value] = {"error": str(e)}
        return results

    async def _execute_action(self, action: RuleAction,
                             event_data: Dict[str, Any]) -> Any:
        if action.action_type == ActionType.RUN_SKILL:
            from business.ecc_skills import get_skill_registry
            skill_registry = get_skill_registry()
            return await skill_registry.execute(action.skill_id, action.skill_parameters, event_data)

        elif action.action_type == ActionType.SWITCH_AGENT:
            from business.ecc_agents import get_agent_manager
            agent_manager = get_agent_manager()
            return agent_manager.switch_to(action.target_agent_id)

        elif action.action_type == ActionType.RUN_COMMAND:
            import subprocess
            result = subprocess.run(action.command, shell=True,
                                 cwd=action.working_dir or None,
                                 capture_output=True, text=True)
            return {"returncode": result.returncode, "output": result.stdout}

        elif action.action_type == ActionType.SHOW_NOTIFICATION:
            return {"title": action.notification_title,
                   "message": action.notification_message,
                   "level": action.notification_level}

        elif action.action_type == ActionType.LOG_MESSAGE:
            return {"level": action.log_level, "message": action.log_message}

        elif action.action_type == ActionType.CALLBACK:
            if action.callback_function in self._callbacks:
                callback = self._callbacks[action.callback_function]
                if asyncio.iscoroutinefunction(callback):
                    return await callback(event_data)
                return callback(event_data)

        return None

    def _save_yaml(self, rule: RuleConfig):
        yaml_path = self.config_dir / f"{rule.id}.yaml"
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(rule.to_dict(), f, allow_unicode=True,
                     default_flow_style=False, sort_keys=False)

    def on_change(self, callback: Callable):
        self._listeners.append(callback)

    def get_execution_history(self, limit: int = 100) -> List[Dict]:
        return self._execution_history[-limit:]

    def enable_rule(self, rule_id: str) -> bool:
        rule = self._rules.get(rule_id)
        if rule:
            rule.enabled = True
            self._save_yaml(rule)
            return True
        return False

    def disable_rule(self, rule_id: str) -> bool:
        rule = self._rules.get(rule_id)
        if rule:
            rule.enabled = False
            self._save_yaml(rule)
            return True
        return False


# Singleton
_rule_engine: Optional[RuleEngine] = None


def get_rule_engine() -> RuleEngine:
    global _rule_engine
    if _rule_engine is None:
        _rule_engine = RuleEngine()
    return _rule_engine


def on_rule_event(event_type: Union[EventType, str]):
    def decorator(func: Callable):
        engine = get_rule_engine()
        engine.on_event(event_type)(func)
        return func
    return decorator