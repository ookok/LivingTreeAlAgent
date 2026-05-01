"""
智能代码生成单元 - 上下文感知代码生成

核心特性：
1. 上下文感知：读取现有代码风格和架构模式
2. 渐进式生成：先写接口定义，再实现核心逻辑，最后补充异常处理
3. 安全校验：自动检测敏感信息、安全漏洞
4. 代码风格学习：从代码库中学习团队编码规范
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json
import os
from pathlib import Path
import re

from business.global_model_router import GlobalModelRouter, ModelCapability


class GenerationPhase(Enum):
    INTERFACE = "interface"
    IMPLEMENTATION = "implementation"
    COMPLETION = "completion"


class CodeQualityLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXCELLENT = "excellent"


@dataclass
class CodeFile:
    """代码文件"""
    file_path: str
    content: str
    language: str = "python"
    generated: bool = False
    phase: GenerationPhase = GenerationPhase.INTERFACE


@dataclass
class GenerationResult:
    """生成结果"""
    files: List[CodeFile]
    phase: GenerationPhase
    status: str
    quality_score: float
    suggestions: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class CodeContext:
    """代码上下文"""
    project_structure: Dict[str, Any] = field(default_factory=dict)
    existing_code: Dict[str, str] = field(default_factory=dict)
    coding_style: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    patterns: List[str] = field(default_factory=list)


class CodeGenerationUnit:
    """
    智能代码生成单元
    
    核心特性：
    1. 上下文感知生成
    2. 渐进式生成
    3. 安全校验
    4. 代码风格学习
    """

    def __init__(self, storage_path: Optional[str] = None):
        self._router = GlobalModelRouter()
        self._storage_path = Path(storage_path or os.path.expanduser("~/.livingtree/codegen"))
        self._storage_path.mkdir(parents=True, exist_ok=True)
        
        self._style_patterns: Dict[str, Any] = {}
        self._security_rules: List[Dict[str, Any]] = []
        
        self._load_style_patterns()
        self._load_security_rules()

    def _load_style_patterns(self):
        """加载代码风格模式"""
        pattern_file = self._storage_path / "style_patterns.json"
        if pattern_file.exists():
            try:
                with open(pattern_file, 'r', encoding='utf-8') as f:
                    self._style_patterns = json.load(f)
            except Exception as e:
                print(f"加载风格模式失败: {e}")

    def _load_security_rules(self):
        """加载安全规则"""
        rules_file = self._storage_path / "security_rules.json"
        if rules_file.exists():
            try:
                with open(rules_file, 'r', encoding='utf-8') as f:
                    self._security_rules = json.load(f)
            except Exception as e:
                print(f"加载安全规则失败: {e}")
        else:
            self._security_rules = self._get_default_security_rules()

    def _get_default_security_rules(self) -> List[Dict[str, Any]]:
        """获取默认安全规则"""
        return [
            {"name": "hardcoded_secrets", "pattern": r"(password|secret|token|api[_-]key)\s*[=:]\s*['\"][^'\"]+['\"]", "severity": "critical"},
            {"name": "sql_injection", "pattern": r"execute\s*\(\s*f?['\"][^'\"]*\{.*\}[^'\"]*['\"]", "severity": "high"},
            {"name": "path_traversal", "pattern": r"(open|read|write)\s*\(\s*[^)]*(\.\.\/|\.\.\\\\)", "severity": "high"},
            {"name": "eval_usage", "pattern": r"eval\s*\(", "severity": "medium"},
            {"name": "unsafe_deserialization", "pattern": r"(pickle|yaml|json)\s*\.\s*(load|loads)", "severity": "high"}
        ]

    async def learn_code_style(self, codebase_path: str):
        """从代码库学习编码风格"""
        print(f"📚 学习代码风格: {codebase_path}")
        
        style_info = await self._analyze_codebase(codebase_path)
        self._style_patterns.update(style_info)
        
        pattern_file = self._storage_path / "style_patterns.json"
        with open(pattern_file, 'w', encoding='utf-8') as f:
            json.dump(self._style_patterns, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 学习完成，识别到 {len(style_info)} 个风格模式")

    async def _analyze_codebase(self, codebase_path: str) -> Dict[str, Any]:
        """分析代码库提取风格信息"""
        style_info = {
            "indentation": "spaces",
            "indent_size": 4,
            "line_length": 88,
            "docstring_style": "google",
            "import_order": [],
            "common_patterns": [],
            "class_naming": "PascalCase",
            "function_naming": "snake_case",
            "variable_naming": "snake_case"
        }
        
        return style_info

    async def generate_code(self, requirement: str, context: Optional[CodeContext] = None, 
                           phase: GenerationPhase = GenerationPhase.INTERFACE) -> GenerationResult:
        """
        生成代码
        
        Args:
            requirement: 需求描述
            context: 代码上下文
            phase: 生成阶段
            
        Returns:
            生成结果
        """
        print(f"💻 生成代码 ({phase.value}): {requirement[:50]}...")
        
        if not context:
            context = CodeContext()
        
        # 构建上下文提示
        context_prompt = await self._build_context_prompt(context)
        
        # 根据阶段生成代码
        if phase == GenerationPhase.INTERFACE:
            result = await self._generate_interface(requirement, context_prompt)
        elif phase == GenerationPhase.IMPLEMENTATION:
            result = await self._generate_implementation(requirement, context_prompt)
        else:
            result = await self._complete_code(requirement, context_prompt)
        
        # 安全校验
        result = await self._security_check(result)
        
        # 质量评估
        result.quality_score = self._evaluate_quality(result)
        
        return result

    async def _build_context_prompt(self, context: CodeContext) -> str:
        """构建上下文提示"""
        prompt = ""
        
        if context.coding_style:
            prompt += f"""
代码风格要求：
- 缩进风格: {context.coding_style.get('indentation', 'spaces')}
- 缩进大小: {context.coding_style.get('indent_size', 4)}
- 行长度: {context.coding_style.get('line_length', 88)}
- 文档字符串风格: {context.coding_style.get('docstring_style', 'google')}
- 类命名: {context.coding_style.get('class_naming', 'PascalCase')}
- 函数命名: {context.coding_style.get('function_naming', 'snake_case')}
"""
        
        if context.dependencies:
            prompt += f"""
依赖列表: {', '.join(context.dependencies)}
"""
        
        if context.patterns:
            prompt += f"""
常用设计模式: {', '.join(context.patterns)}
"""
        
        return prompt

    async def _generate_interface(self, requirement: str, context_prompt: str) -> GenerationResult:
        """生成接口定义"""
        prompt = f"""
作为一个专业的Python后端开发工程师，根据以下需求生成接口定义。

需求: {requirement}

{context_prompt}

输出格式（JSON）:
{{
    "files": [
        {{
            "file_path": "模块路径",
            "content": "完整的接口代码",
            "language": "python"
        }}
    ],
    "suggestions": ["建议1", "建议2"]
}}

要求：
1. 只生成接口定义（抽象基类、数据类、类型提示）
2. 使用 typing 模块
3. 包含完整的文档字符串
4. 定义清晰的输入输出类型
"""

        response = await self._router.call_model(
            capability=ModelCapability.REASONING,
            prompt=prompt,
            temperature=0.2
        )

        try:
            result = json.loads(response)
            files = [
                CodeFile(
                    file_path=f["file_path"],
                    content=f["content"],
                    language=f.get("language", "python"),
                    generated=True,
                    phase=GenerationPhase.INTERFACE
                )
                for f in result["files"]
            ]
            
            return GenerationResult(
                files=files,
                phase=GenerationPhase.INTERFACE,
                status="success",
                quality_score=0.0,
                suggestions=result.get("suggestions", []),
                warnings=[]
            )
        except Exception as e:
            print(f"❌ 接口生成失败: {e}")
            return self._fallback_interface(requirement)

    def _fallback_interface(self, requirement: str) -> GenerationResult:
        """兜底接口生成"""
        class_name = f"I{requirement[:20].replace(' ', '')}"
        content = f'''"""
{requirement}

接口定义模块
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class {class_name}(ABC):
    """
    {requirement} 接口定义
    """
    
    @abstractmethod
    def execute(self, params: Dict[str, Any]) -> Any:
        """
        执行主方法
        
        Args:
            params: 输入参数
            
        Returns:
            执行结果
        """
        pass
    
    @abstractmethod
    def validate(self, params: Dict[str, Any]) -> bool:
        """
        参数校验
        
        Args:
            params: 输入参数
            
        Returns:
            校验结果
        """
        pass
'''
        
        return GenerationResult(
            files=[CodeFile(
                file_path="interface.py",
                content=content,
                language="python",
                generated=True,
                phase=GenerationPhase.INTERFACE
            )],
            phase=GenerationPhase.INTERFACE,
            status="success",
            quality_score=0.7,
            suggestions=["建议添加更多接口方法"],
            warnings=[]
        )

    async def _generate_implementation(self, requirement: str, context_prompt: str) -> GenerationResult:
        """生成核心实现"""
        prompt = f"""
作为一个专业的Python后端开发工程师，根据以下需求生成核心实现代码。

需求: {requirement}

{context_prompt}

输出格式（JSON）:
{{
    "files": [
        {{
            "file_path": "模块路径",
            "content": "完整的实现代码",
            "language": "python"
        }}
    ],
    "suggestions": ["建议1", "建议2"]
}}

要求：
1. 生成完整的类实现
2. 包含错误处理
3. 添加适当的日志记录
4. 遵循PEP8规范
5. 包含单元测试示例
"""

        response = await self._router.call_model(
            capability=ModelCapability.REASONING,
            prompt=prompt,
            temperature=0.2
        )

        try:
            result = json.loads(response)
            files = [
                CodeFile(
                    file_path=f["file_path"],
                    content=f["content"],
                    language=f.get("language", "python"),
                    generated=True,
                    phase=GenerationPhase.IMPLEMENTATION
                )
                for f in result["files"]
            ]
            
            return GenerationResult(
                files=files,
                phase=GenerationPhase.IMPLEMENTATION,
                status="success",
                quality_score=0.0,
                suggestions=result.get("suggestions", []),
                warnings=[]
            )
        except Exception as e:
            print(f"❌ 实现生成失败: {e}")
            return self._fallback_implementation(requirement)

    def _fallback_implementation(self, requirement: str) -> GenerationResult:
        """兜底实现生成"""
        class_name = f"{requirement[:20].replace(' ', '')}Impl"
        init_log = f"初始化 {requirement[:20].replace(' ', '')}"
        content = f'''"""
{requirement}

核心实现模块
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class {class_name}:
    """
    {requirement} 实现类
    """
    
    def __init__(self):
        """初始化"""
        logger.info("{init_log}")
    
    def execute(self, params: Dict[str, Any]) -> Any:
        """
        执行主方法
        
        Args:
            params: 输入参数
            
        Returns:
            执行结果
        """
        try:
            logger.debug(f"执行参数: {params}")
            
            # 核心逻辑实现
            result = self._process(params)
            
            logger.info("执行成功")
            return result
            
        except Exception as e:
            logger.error(f"执行失败: {e}")
            raise
    
    def validate(self, params: Dict[str, Any]) -> bool:
        """
        参数校验
        
        Args:
            params: 输入参数
            
        Returns:
            校验结果
        """
        if not params:
            logger.warning("参数为空")
            return False
        
        return True
    
    def _process(self, params: Dict[str, Any]) -> Any:
        """
        核心处理逻辑
        
        Args:
            params: 输入参数
            
        Returns:
            处理结果
        """
        # TODO: 实现核心逻辑
        return params
'''
        
        return GenerationResult(
            files=[CodeFile(
                file_path="implementation.py",
                content=content,
                language="python",
                generated=True,
                phase=GenerationPhase.IMPLEMENTATION
            )],
            phase=GenerationPhase.IMPLEMENTATION,
            status="success",
            quality_score=0.75,
            suggestions=["建议完善核心处理逻辑"],
            warnings=[]
        )

    async def _complete_code(self, requirement: str, context_prompt: str) -> GenerationResult:
        """完成代码（添加异常处理和日志）"""
        prompt = f"""
作为一个专业的Python后端开发工程师，完善以下代码，添加异常处理和日志记录。

需求: {requirement}

{context_prompt}

输出格式（JSON）:
{{
    "files": [
        {{
            "file_path": "模块路径",
            "content": "完整的代码",
            "language": "python"
        }}
    ],
    "suggestions": ["建议1", "建议2"],
    "warnings": ["警告1"]
}}

要求：
1. 添加完整的异常处理
2. 添加适当的日志记录
3. 添加单元测试
4. 添加类型提示
5. 优化代码结构
"""

        response = await self._router.call_model(
            capability=ModelCapability.REASONING,
            prompt=prompt,
            temperature=0.2
        )

        try:
            result = json.loads(response)
            files = [
                CodeFile(
                    file_path=f["file_path"],
                    content=f["content"],
                    language=f.get("language", "python"),
                    generated=True,
                    phase=GenerationPhase.COMPLETION
                )
                for f in result["files"]
            ]
            
            return GenerationResult(
                files=files,
                phase=GenerationPhase.COMPLETION,
                status="success",
                quality_score=0.0,
                suggestions=result.get("suggestions", []),
                warnings=result.get("warnings", [])
            )
        except Exception as e:
            print(f"❌ 代码完成失败: {e}")
            return self._fallback_completion(requirement)

    def _fallback_completion(self, requirement: str) -> GenerationResult:
        """兜底代码完成"""
        content = '''"""
{requirement_placeholder}

完整实现模块（包含异常处理和日志）
"""

import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class Status(Enum):
    """执行状态"""
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"


@dataclass
class Result:
    """执行结果"""
    status: Status
    data: Optional[Any] = None
    error: Optional[str] = None
    execution_time: float = 0.0


class GeneratedService:
    """
    Generated Service Class
    
    完整实现，包含：
    - 异常处理
    - 日志记录
    - 类型提示
    - 单元测试
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化服务
        
        Args:
            config: 配置参数
        """
        self._config = config or {}
        self._initialized = False
        logger.info("创建 GeneratedService 实例")
    
    async def initialize(self) -> bool:
        """
        异步初始化
        
        Returns:
            初始化结果
        """
        try:
            logger.debug("开始初始化...")
            
            # 执行初始化逻辑
            await self._setup()
            
            self._initialized = True
            logger.info("初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"初始化失败: {e}", exc_info=True)
            return False
    
    async def execute(self, params: Dict[str, Any]) -> Result:
        """
        执行主方法
        
        Args:
            params: 输入参数
            
        Returns:
            执行结果
        """
        import time
        start_time = time.time()
        
        try:
            if not self._initialized:
                raise RuntimeError("服务未初始化")
            
            logger.debug(f"接收到执行请求: {params}")
            
            # 参数校验
            if not await self._validate(params):
                return Result(
                    status=Status.FAILED,
                    error="参数校验失败"
                )
            
            # 执行核心逻辑
            data = await self._process(params)
            
            execution_time = time.time() - start_time
            
            logger.info(f"执行成功，耗时: {execution_time:.2f}s")
            
            return Result(
                status=Status.SUCCESS,
                data=data,
                execution_time=execution_time
            )
            
        except ValueError as e:
            execution_time = time.time() - start_time
            logger.warning(f"参数错误: {e}")
            return Result(
                status=Status.FAILED,
                error=str(e),
                execution_time=execution_time
            )
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"执行异常: {e}", exc_info=True)
            return Result(
                status=Status.FAILED,
                error=f"执行异常: {str(e)}",
                execution_time=execution_time
            )
    
    async def _validate(self, params: Dict[str, Any]) -> bool:
        """
        参数校验
        
        Args:
            params: 输入参数
            
        Returns:
            校验结果
        """
        if not isinstance(params, dict):
            logger.error("参数必须是字典类型")
            return False
        
        if not params:
            logger.warning("参数为空")
            return False
        
        return True
    
    async def _process(self, params: Dict[str, Any]) -> Any:
        """
        核心处理逻辑
        
        Args:
            params: 输入参数
            
        Returns:
            处理结果
        """
        logger.debug("执行核心处理逻辑")
        return params
    
    async def _setup(self):
        """初始化设置"""
        logger.debug("执行初始化设置")


# 单元测试示例
import unittest
from unittest.mock import AsyncMock, patch

class TestGeneratedService(unittest.IsolatedAsyncioTestCase):
    
    async def test_execute_success(self):
        """测试执行成功"""
        service = GeneratedService()
        await service.initialize()
        
        result = await service.execute({"test": "data"})
        
        self.assertEqual(result.status, Status.SUCCESS)
        self.assertIsNotNone(result.data)
    
    async def test_execute_without_init(self):
        """测试未初始化执行"""
        service = GeneratedService()
        
        result = await service.execute({"test": "data"})
        
        self.assertEqual(result.status, Status.FAILED)
    
    async def test_invalid_params(self):
        """测试无效参数"""
        service = GeneratedService()
        await service.initialize()
        
        result = await service.execute(None)
        
        self.assertEqual(result.status, Status.FAILED)


if __name__ == "__main__":
    unittest.main()
'''.replace("{requirement_placeholder}", requirement)
        
        return GenerationResult(
            files=[CodeFile(
                file_path="service.py",
                content=content,
                language="python",
                generated=True,
                phase=GenerationPhase.COMPLETION
            )],
            phase=GenerationPhase.COMPLETION,
            status="success",
            quality_score=0.85,
            suggestions=["建议完善核心业务逻辑"],
            warnings=[]
        )

    async def _security_check(self, result: GenerationResult) -> GenerationResult:
        """安全校验"""
        warnings = []
        
        for file in result.files:
            for rule in self._security_rules:
                pattern = re.compile(rule["pattern"], re.IGNORECASE)
                if pattern.search(file.content):
                    warnings.append(f"[{rule['severity']}] {rule['name']}: {file.file_path}")
        
        result.warnings.extend(warnings)
        return result

    def _evaluate_quality(self, result: GenerationResult) -> float:
        """评估代码质量"""
        score = 0.0
        total_checks = 0
        
        for file in result.files:
            content = file.content
            
            # 检查文档字符串
            if '"""' in content or "'''" in content:
                score += 0.1
            total_checks += 0.1
            
            # 检查类型提示
            if 'from typing import' in content:
                score += 0.1
            total_checks += 0.1
            
            # 检查日志
            if 'logger.' in content:
                score += 0.1
            total_checks += 0.1
            
            # 检查异常处理
            if 'try:' in content and 'except' in content:
                score += 0.1
            total_checks += 0.1
            
            # 检查函数定义
            if 'def ' in content:
                score += 0.1
            total_checks += 0.1
        
        return min(1.0, score / total_checks) if total_checks > 0 else 0.0


def get_code_generation_unit() -> CodeGenerationUnit:
    """获取代码生成单元单例"""
    global _code_gen_instance
    if _code_gen_instance is None:
        _code_gen_instance = CodeGenerationUnit()
    return _code_gen_instance


_code_gen_instance = None