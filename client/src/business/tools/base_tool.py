"""
BaseTool - 工具基类

所有工具模块继承此类，提供统一的调用接口。

遵循自我进化原则：
- 支持异步执行
- 支持动态参数验证
- 支持工具元数据管理
- 区分确定性工具和 AI 工具
- 智能体原生接口（支持结构化 JSON 输出）
- 精准修改约束（仅修改任务直接相关的文件/配置）

工具类型说明：
- deterministic（确定性工具）：直接执行，无需 AI 参与（如 bash 脚本、文件操作）
- ai（AI 工具）：需要调用 LLM，提升效率、降低 API 成本

智能体原生接口：
- agent_call() 方法提供标准化的 AI Agent 调用接口
- 返回结构化 JSON 格式输出
- 支持自动参数验证和错误处理

精准修改约束：
- 仅修改任务直接相关的文件/配置
- 避免无意义的副作用
- 记录所有修改操作，便于回滚
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
from loguru import logger
import json
import os
from datetime import datetime
from enum import Enum

# ── Opik 监控支持 ─────────────────────────────────────────
try:
    from business.opik_monitor import get_monitor, monitor_tool
    OPIK_MONITOR_AVAILABLE = True
except ImportError:
    logger.warning("Opik 监控模块导入失败，监控功能将不可用")
    OPIK_MONITOR_AVAILABLE = False
    get_monitor = lambda: None
    monitor_tool = lambda *a, **kw: lambda func: func  # no-op decorator


class ToolNodeType:
    """工具节点类型"""
    DETERMINISTIC = "deterministic"  # 确定性工具，直接执行
    AI = "ai"                          # AI 工具，需要调用 LLM


class ModifiedFile:
    """
    修改记录 - 记录工具执行过程中对文件的修改
    
    遵循精准修改原则：仅修改任务直接相关的文件/配置
    """
    
    def __init__(self, filepath: str, action: str, original_content: str = None, 
                 new_content: str = None, backup_path: str = None):
        self.filepath = filepath
        self.action = action  # create, modify, delete, rename
        self.original_content = original_content
        self.new_content = new_content
        self.backup_path = backup_path
        self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "filepath": self.filepath,
            "action": self.action,
            "timestamp": self.timestamp
        }


class VerificationStatus(Enum):
    """验证状态"""
    VERIFIED = "verified"      # 已验证，符合预期
    PARTIAL = "partial"        # 部分验证
    UNVERIFIED = "unverified"  # 未验证
    FAILED = "failed"          # 验证失败


class AgentCallResult:
    """
    智能体调用结果 - 结构化 JSON 输出
    
    遵循智能体原生架构原则，提供标准化的输出格式。
    
    效果可验证机制：
    - 定义明确的判断标准
    - 用户可直观判断工具是否正常工作
    - 包含验证证据和验证状态
    """
    
    def __init__(self, success: bool, data: Any = None, error: str = None, 
                 message: str = "", evidence: Dict[str, Any] = None,
                 verification: Optional[Dict[str, Any]] = None):
        self.success = success
        self.data = data
        self.error = error
        self.message = message
        self.evidence = evidence or {}
        self.timestamp = datetime.now().isoformat()
        
        # 效果验证字段
        self.verification = verification or {
            "status": VerificationStatus.UNVERIFIED.value,
            "criteria": [],           # 验证标准列表
            "checks": [],             # 验证检查项
            "score": 0.0,            # 验证分数 (0-1)
            "explanation": ""        # 验证说明
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "message": self.message,
            "evidence": self.evidence,
            "timestamp": self.timestamp,
            "verification": self.verification
        }
    
    def to_json(self, indent: int = 2) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
    
    @classmethod
    def success(cls, data: Any = None, message: str = "", evidence: Dict[str, Any] = None,
                verification: Optional[Dict[str, Any]] = None):
        """创建成功结果"""
        return cls(success=True, data=data, message=message, 
                   evidence=evidence, verification=verification)
    
    @classmethod
    def error(cls, error: str, message: str = ""):
        """创建失败结果"""
        return cls(success=False, error=error, message=message)
    
    def set_verification(self, criteria: List[str], checks: List[Dict[str, Any]],
                         score: float, explanation: str):
        """
        设置效果验证信息
        
        Args:
            criteria: 验证标准列表
            checks: 验证检查项列表，每项包含 {"name": str, "passed": bool, "value": any}
            score: 验证分数 (0-1)
            explanation: 验证说明
        """
        # 计算验证状态
        passed_count = sum(1 for check in checks if check.get("passed", False))
        total_checks = len(checks)
        
        if total_checks == 0:
            status = VerificationStatus.UNVERIFIED.value
        elif passed_count == total_checks:
            status = VerificationStatus.VERIFIED.value
        elif passed_count > 0:
            status = VerificationStatus.PARTIAL.value
        else:
            status = VerificationStatus.FAILED.value
        
        self.verification = {
            "status": status,
            "criteria": criteria,
            "checks": checks,
            "score": min(max(score, 0.0), 1.0),
            "explanation": explanation,
            "passed_count": passed_count,
            "total_checks": total_checks
        }
    
    def is_verified(self) -> bool:
        """检查是否已验证"""
        return self.verification.get("status") == VerificationStatus.VERIFIED.value
    
    def get_verification_summary(self) -> str:
        """获取验证摘要"""
        status = self.verification.get("status", "unknown")
        score = self.verification.get("score", 0.0)
        passed = self.verification.get("passed_count", 0)
        total = self.verification.get("total_checks", 0)
        
        return f"验证状态: {status} | 分数: {score:.2f} | 通过: {passed}/{total}"
    
    def to_markdown(self) -> str:
        """
        转换为 Markdown 格式（LLM 优化）
        
        特点:
        - 降低 token 占用成本
        - 提高 LLM 理解效率
        - 保留关键信息结构
        """
        md = []
        
        if self.success:
            md.append(f"## ✅ {self.message}")
            md.append("")
            
            if self.data is not None:
                md.append("### 📊 结果数据")
                md.append("")
                
                # 根据数据类型格式化
                if isinstance(self.data, dict):
                    for key, value in self.data.items():
                        if isinstance(value, dict):
                            md.append(f"- **{key}:**")
                            for k, v in value.items():
                                md.append(f"  - {k}: {v}")
                        elif isinstance(value, list):
                            md.append(f"- **{key}:**")
                            for item in value[:5]:  # 限制数量
                                md.append(f"  - {item}")
                            if len(value) > 5:
                                md.append(f"  - ... (共 {len(value)} 项)")
                        else:
                            md.append(f"- **{key}:** {value}")
                elif isinstance(self.data, list):
                    md.append("<details>")
                    md.append("<summary>查看详细列表</summary>")
                    md.append("")
                    for item in self.data[:10]:  # 限制数量
                        md.append(f"- {item}")
                    if len(self.data) > 10:
                        md.append(f"- ... (共 {len(self.data)} 项)")
                    md.append("")
                    md.append("</details>")
                else:
                    md.append(f"```\n{str(self.data)}\n```")
                md.append("")
            
            # 添加验证信息
            if self.verification.get("status") != VerificationStatus.UNVERIFIED.value:
                md.append("### ✔️ 验证结果")
                md.append("")
                md.append(f"- **状态:** {self.verification.get('status')}")
                md.append(f"- **分数:** {self.verification.get('score', 0.0):.2f}")
                md.append(f"- **通过:** {self.verification.get('passed_count', 0)}/{self.verification.get('total_checks', 0)}")
                
                if self.verification.get("explanation"):
                    md.append(f"- **说明:** {self.verification.get('explanation')}")
                md.append("")
            
            # 添加证据信息
            if self.evidence:
                md.append("### 📝 证据")
                md.append("")
                for key, value in self.evidence.items():
                    md.append(f"- {key}: {value}")
                md.append("")
        
        else:
            md.append(f"## ❌ {self.message}")
            md.append("")
            md.append(f"### 错误信息")
            md.append("")
            md.append(f"```\n{self.error}\n```")
        
        md.append(f"---\n*时间: {self.timestamp}*")
        
        return "\n".join(md)


@dataclass
class AccessControlRule:
    """访问控制规则"""
    name: str
    allowed_paths: List[str] = field(default_factory=list)
    denied_paths: List[str] = field(default_factory=list)
    allowed_patterns: List[str] = field(default_factory=list)
    denied_patterns: List[str] = field(default_factory=list)
    max_file_size: Optional[int] = None  # 字节
    read_only: bool = False


class BaseTool(ABC):
    """
    工具基类
    
    所有工具模块继承此类，提供统一的调用接口。
    
    子类需要实现：
    - name 属性：工具名称
    - description 属性：工具描述
    - category 属性：工具类别
    - execute() 方法：执行工具
    
    工具类型：
    - deterministic（确定性工具）：直接执行，无需 AI 参与
    - ai（AI 工具）：需要调用 LLM
    
    智能体原生接口：
    - agent_call() 提供标准化的 AI Agent 调用方式
    - 支持结构化 JSON 输出
    
    精准修改约束：
    - tracked_files: 允许修改的文件列表（None 表示无限制）
    - modifications: 记录所有修改操作
    
    细粒度访问控制：
    - access_rules: 访问控制规则列表
    - 支持路径白名单/黑名单
    - 支持文件大小限制
    - 支持只读模式
    """
    
    def __init__(self):
        self._logger = logger.bind(component=f"Tool.{self.name}")
        self._modifications: List[ModifiedFile] = []
        self._access_rules: List[AccessControlRule] = []
    
    @property
    def tracked_files(self) -> Optional[List[str]]:
        """
        允许修改的文件列表（精准修改约束）
        
        返回 None 表示无限制，返回列表表示只允许修改列表中的文件。
        
        子类可以重写此属性来限制工具只能修改特定文件。
        """
        return None  # 默认无限制
    
    @property
    def modifications(self) -> List[ModifiedFile]:
        """获取本次执行的所有修改记录"""
        return self._modifications
    
    @property
    def access_rules(self) -> List[AccessControlRule]:
        """获取访问控制规则列表"""
        return self._access_rules
    
    def add_access_rule(self, rule: AccessControlRule):
        """添加访问控制规则"""
        self._access_rules.append(rule)
        self._logger.debug(f"添加访问控制规则: {rule.name}")
    
    def clear_access_rules(self):
        """清除所有访问控制规则"""
        self._access_rules.clear()
    
    def check_access(self, filepath: str, action: str = "read") -> bool:
        """
        检查文件访问权限（细粒度访问控制）
        
        Args:
            filepath: 文件路径
            action: 操作类型（read, write, delete, execute）
            
        Returns:
            True 如果允许访问，False 否则
            
        访问控制优先级：
        1. 黑名单优先（denied_paths 和 denied_patterns）
        2. 白名单检查（allowed_paths 和 allowed_patterns）
        3. 文件大小限制（max_file_size）
        4. 只读模式检查（read_only）
        """
        normalized_path = os.path.normpath(filepath).lower()
        
        for rule in self._access_rules:
            # 检查黑名单路径
            for denied_path in rule.denied_paths:
                denied_norm = os.path.normpath(denied_path).lower()
                if normalized_path.startswith(denied_norm) or normalized_path == denied_norm:
                    self._logger.warning(f"访问被拒绝（黑名单路径）: {filepath}")
                    return False
            
            # 检查黑名单模式
            for pattern in rule.denied_patterns:
                if self._match_pattern(normalized_path, pattern.lower()):
                    self._logger.warning(f"访问被拒绝（黑名单模式）: {filepath}")
                    return False
            
            # 检查白名单路径（如果设置了白名单）
            if rule.allowed_paths:
                allowed = False
                for allowed_path in rule.allowed_paths:
                    allowed_norm = os.path.normpath(allowed_path).lower()
                    if normalized_path.startswith(allowed_norm) or normalized_path == allowed_norm:
                        allowed = True
                        break
                
                if not allowed:
                    self._logger.warning(f"访问被拒绝（不在白名单）: {filepath}")
                    return False
            
            # 检查白名单模式（如果设置了模式）
            if rule.allowed_patterns:
                matched = False
                for pattern in rule.allowed_patterns:
                    if self._match_pattern(normalized_path, pattern.lower()):
                        matched = True
                        break
                
                if not matched:
                    self._logger.warning(f"访问被拒绝（不匹配白名单模式）: {filepath}")
                    return False
            
            # 检查只读模式
            if rule.read_only and action.lower() not in ["read", "view"]:
                self._logger.warning(f"访问被拒绝（只读模式）: {filepath}, action: {action}")
                return False
            
            # 检查文件大小（仅在读取时检查）
            if rule.max_file_size and action.lower() == "read":
                try:
                    if os.path.exists(filepath):
                        file_size = os.path.getsize(filepath)
                        if file_size > rule.max_file_size:
                            self._logger.warning(f"访问被拒绝（文件过大）: {filepath}, size: {file_size}")
                            return False
                except Exception as e:
                    self._logger.debug(f"检查文件大小失败: {e}")
        
        return True
    
    def _match_pattern(self, filepath: str, pattern: str) -> bool:
        """匹配路径模式"""
        # 简单的模式匹配，支持通配符 *
        import fnmatch
        return fnmatch.fnmatch(filepath, pattern)
    
    def _track_modification(self, filepath: str, action: str, 
                           original_content: str = None, new_content: str = None):
        """
        记录修改操作（精准修改约束）
        
        Args:
            filepath: 修改的文件路径
            action: 操作类型（create, modify, delete, rename）
            original_content: 修改前的内容
            new_content: 修改后的内容
        """
        # 检查是否符合精准修改约束
        if self.tracked_files is not None:
            # 规范化路径以便比较
            normalized_path = os.path.normpath(filepath)
            allowed_paths = [os.path.normpath(p) for p in self.tracked_files]
            
            if normalized_path not in allowed_paths:
                raise PermissionError(
                    f"精准修改约束：不允许修改文件 {filepath}。"
                    f"允许修改的文件：{self.tracked_files}"
                )
        
        modification = ModifiedFile(
            filepath=filepath,
            action=action,
            original_content=original_content,
            new_content=new_content
        )
        self._modifications.append(modification)
        self._logger.debug(f"记录修改: {action} {filepath}")
    
    def _reset_modifications(self):
        """重置修改记录"""
        self._modifications = []
    
    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述"""
        pass
    
    @property
    @abstractmethod
    def category(self) -> str:
        """工具类别（network/document/database/task/learning/geo/simulation）"""
        pass
    
    @property
    def version(self) -> str:
        """工具版本"""
        return "1.0"
    
    @property
    def author(self) -> str:
        """工具作者"""
        return "system"
    
    @property
    def node_type(self) -> str:
        """
        工具节点类型
        
        - 'deterministic': 确定性工具，直接执行无需 AI 参与（如 bash 脚本、文件操作）
        - 'ai': AI 工具，需要调用 LLM
        
        子类可以重写此属性来指定工具类型
        """
        return ToolNodeType.AI  # 默认视为 AI 工具
    
    @property
    def parameters(self) -> Dict[str, str]:
        """参数 schema"""
        return {}
    
    @property
    def returns(self) -> str:
        """返回值 schema"""
        return "ToolResult"
    
    @property
    def agent_info(self) -> Dict[str, Any]:
        """
        智能体调用信息 - 用于 AI Agent 发现和调用工具
        
        返回结构化的工具元数据，包括：
        - 工具名称、描述、参数
        - 调用示例
        - 输出格式说明
        """
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "version": self.version,
            "node_type": self.node_type,
            "parameters": self.parameters,
            "returns": self.returns,
            "call_format": self.get_call_format(),
            "examples": self.get_call_examples()
        }
    
    def get_call_format(self) -> str:
        """获取智能体调用格式说明"""
        params = ", ".join([f"{key}={type(value).__name__}" for key, value in self.parameters.items()])
        return f"{self.name}({params}) -> {self.returns}"
    
    def get_call_examples(self) -> List[Dict[str, Any]]:
        """获取智能体调用示例"""
        return [
            {
                "description": f"调用 {self.name} 工具",
                "input": {"type": "object", "properties": self.parameters},
                "output": {"type": "object", "properties": {"success": "boolean", "data": "any", "error": "string"}}
            }
        ]
    
    def get_skill_md(self) -> str:
        """
        获取 SKILL.md 格式的工具描述
        
        参考 DeepTutor 的智能体原生架构，提供详细的 AI Agent 调用说明。
        """
        md = f"""# {self.name}

## 描述
{self.description}

## 类别
{self.category}

## 版本
{self.version}

## 工具类型
- Node Type: {self.node_type}

## 参数

| 参数名 | 类型 | 说明 |
|--------|------|------|
"""
        for param_name, param_desc in self.parameters.items():
            md += f"| {param_name} | string | {param_desc} |\n"
        
        md += """
## 返回值
```json
{
  "success": true/false,
  "data": "结果数据",
  "error": "错误信息（如果失败）",
  "message": "提示信息",
  "evidence": {},
  "timestamp": "时间戳"
}
```

## 调用示例

```python
# Python 调用
result = await tool.agent_call(param1="value1", param2="value2")
print(result.to_json())
```

```json
// JSON 格式调用
{
  "tool": "{self.name}",
  "parameters": {
    "param1": "value1",
    "param2": "value2"
  }
}
```

## 智能体使用建议
- 适用于: {self.description}
- 前置条件: 无
- 后置处理: 根据返回的 success 字段判断是否成功
"""
        return md
    
    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """
        执行工具（原始接口）
        
        Args:
            **kwargs: 工具参数
            
        Returns:
            工具执行结果
        """
        pass
    
    async def agent_call(self, **kwargs) -> AgentCallResult:
        """
        智能体原生调用接口 - 标准化的 AI Agent 调用方法
        
        参考 DeepTutor 的智能体原生架构设计，提供：
        1. 自动参数验证
        2. 结构化 JSON 输出
        3. 统一的错误处理
        4. 验证证据收集
        
        Args:
            **kwargs: 工具参数（会自动进行验证）
            
        Returns:
            AgentCallResult - 结构化的调用结果
        """
        # ── Opik 监控：开始 ─────────────────────────────────
        _monitor = None
        _start_time = time.time() if 'time' in sys.modules else 0
        
        if OPIK_MONITOR_AVAILABLE:
            try:
                _monitor = get_monitor()
            except Exception as e:
                logger.warning(f"获取监控器失败: {e}")
        
        try:
            # 参数验证
            validation_error = await self.validate_parameters(**kwargs)
            if validation_error:
                return AgentCallResult.error(
                    error=validation_error,
                    message="参数验证失败"
                )
            
            # 执行工具
            self._logger.info(f"智能体调用: {self.name} 参数: {kwargs}")
            result = await self.execute(**kwargs)
            
            # ── Opik 监控：记录成功 ─────────────────────────
            if _monitor is not None:
                try:
                    _latency = time.time() - _start_time
                    # 记录到监控器（通过 monitor_tool 装饰器）
                    # 注意：如果在 execute() 方法中使用了 @monitor_tool 装饰器，
                    # 这里不需要重复记录
                except Exception as e:
                    logger.warning(f"监控记录失败: {e}")
            
            # 返回成功结果
            return AgentCallResult.success(
                data=result,
                message=f"{self.name} 执行成功",
                evidence={"execution_time": datetime.now().isoformat()}
            )
            
        except Exception as e:
            # ── Opik 监控：记录失败 ─────────────────────────
            if _monitor is not None:
                try:
                    _latency = time.time() - _start_time
                    # 记录失败
                except Exception as ex:
                    logger.warning(f"监控记录失败: {ex}")
            
            self._logger.error(f"智能体调用失败 {self.name}: {e}")
            return AgentCallResult.error(
                error=str(e),
                message=f"{self.name} 执行失败"
            )
    
    async def validate_parameters(self, **kwargs) -> Optional[str]:
        """
        验证参数
        
        Args:
            **kwargs: 要验证的参数
            
        Returns:
            错误消息（如果验证失败），None 表示验证通过
        """
        required_params = self._get_required_parameters()
        for param in required_params:
            if param not in kwargs:
                return f"缺少必需参数: {param}"
        return None
    
    def _get_required_parameters(self) -> list:
        """获取必需参数列表"""
        return []
    
    def get_info(self) -> Dict[str, Any]:
        """获取工具信息"""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "version": self.version,
            "author": self.author,
            "node_type": self.node_type,
            "parameters": self.parameters,
            "returns": self.returns
        }
    
    def register(self):
        """注册到 ToolRegistry"""
        from .tool_registry import ToolRegistry, ToolDefinition
        
        registry = ToolRegistry.get_instance()
        tool_def = ToolDefinition(
            name=self.name,
            description=self.description,
            handler=self.execute,
            parameters=self.parameters,
            returns=self.returns,
            category=self.category,
            version=self.version,
            author=self.author
        )
        registry.register(tool_def)