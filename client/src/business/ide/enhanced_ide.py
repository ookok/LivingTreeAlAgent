"""
增强版智能 IDE 模块
==================

集成 AI 代码生成、代码补全、测试生成功能。
使用 GlobalModelRouter 调用 LLM 生成高质量代码。

Author: LivingTreeAI
from __future__ import annotations
"""

import os
import re
import ast
import autopep8
import inspect
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

# GlobalModelRouter 导入
try:
    from business.global_model_router import (
        get_global_router, 
        ModelCapability,
        ModelRoute
    )
    GLOBAL_ROUTER_AVAILABLE = True
except ImportError:
    GLOBAL_ROUTER_AVAILABLE = False
    get_global_router = None
    ModelCapability = None
    ModelRoute = None

# 意图引擎导入（可选）
try:
    from business.intent_engine import IntentEngine
    from business.intent_engine.intent_types import Intent, IntentType
except ImportError:
    IntentEngine = None
    Intent = None
    IntentType = None


class CodeLanguage(Enum):
    """支持的编程语言"""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    GO = "go"
    RUST = "rust"
    CPP = "cpp"
    CSHARP = "csharp"
    PHP = "php"
    RUBY = "ruby"
    SWIFT = "swift"
    KOTLIN = "kotlin"


class CodeTemplate(Enum):
    """代码模板类型"""
    FUNCTION = "function"
    CLASS = "class"
    API_ENDPOINT = "api_endpoint"
    DATABASE_MODEL = "db_model"
    TEST = "test"
    CONFIG = "config"
    CLI_TOOL = "cli_tool"
    SCRIPT = "script"
    COMPONENT = "component"  # UI 组件
    MIDDLEWARE = "middleware"
    UTILITY = "utility"


@dataclass
class GeneratedCode:
    """生成的代码"""
    code: str
    language: str
    file_path: str
    description: str
    template_type: CodeTemplate
    confidence: float
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CodeCompletion:
    """代码补全结果"""
    completion: str
    explanation: str
    confidence: float
    alternatives: List[str] = field(default_factory=list)


@dataclass
class TestCase:
    """测试用例"""
    test_code: str
    test_description: str
    test_type: str  # unit, integration, e2e
    coverage: float = 0.0


@dataclass
class GenerationRequest:
    """生成请求"""
    intent: str  # 用户意图描述
    context: str = ""  # 上下文（现有代码）
    language: str = "python"
    framework: str = ""
    output_path: str = ""
    include_tests: bool = False
    include_comments: bool = True
    optimize: bool = True


@dataclass
class GenerationResult:
    """生成结果"""
    success: bool
    generated: Optional[GeneratedCode] = None
    error: str = ""
    alternatives: List[GeneratedCode] = field(default_factory=list)
    tests: List[TestCase] = field(default_factory=list)


class EnhancedIDEGenenerator:
    """
    增强版 IDE 代码生成器
    
    功能：
    1. AI 驱动的代码生成（通过 GlobalModelRouter）
    2. 代码补全
    3. 测试生成
    4. 代码优化
    5. 多语言支持
    
    使用方式：
        generator = EnhancedIDEGenenerator()
        
        # AI 生成代码
        result = generator.generate("写一个用户登录函数")
        
        # 代码补全
        completion = generator.complete("def login(user", language="python")
        
        # 生成测试
        tests = generator.generate_tests(code, language="python")
    """
    
    def __init__(self, intent_engine: Optional[IntentEngine] = None):
        """初始化"""
        self.intent_engine = intent_engine or (IntentEngine() if IntentEngine else None)
        self.generation_history: List[GenerationResult] = []
        
        # 初始化 GlobalModelRouter
        self._router = None
        if GLOBAL_ROUTER_AVAILABLE:
            try:
                self._router = get_global_router()
            except Exception:
                pass
    
    # ============ AI 代码生成 ============
    
    def generate(self, request: GenerationRequest) -> GenerationResult:
        """
        从自然语言意图生成代码（AI 驱动）
        
        Args:
            request: 生成请求
            
        Returns:
            GenerationResult: 生成结果
        """
        try:
            # 1. 解析意图（如果有意图引擎）
            intent_obj = None
            if self.intent_engine and Intent:
                intent_obj = self.intent_engine.parse(request.intent)
            
            # 2. 使用 AI 生成代码
            code = self._generate_with_ai(request, intent_obj)
            
            if not code:
                return GenerationResult(success=False, error="AI 生成失败")
                
            # 3. 后处理
            code = self._post_process(code, request.language)
            
            # 4. 生成测试（如果需要）
            tests = []
            if request.include_tests:
                tests = self._generate_tests_with_ai(code, request.language)
                
            # 5. 构建结果
            generated = GeneratedCode(
                code=code,
                language=request.language,
                file_path=self._suggest_file_path(request),
                description=request.intent,
                template_type=self._detect_template(request.intent, request.language),
                confidence=0.9,
                warnings=[],
                suggestions=self._generate_suggestions(request.language),
                metadata={
                    "has_tests": request.include_tests,
                    "has_comments": request.include_comments,
                    "optimized": request.optimize,
                }
            )
            
            result = GenerationResult(
                success=True,
                generated=generated,
                tests=tests,
            )
            
            self.generation_history.append(result)
            return result
            
        except Exception as e:
            return GenerationResult(success=False, error=str(e))
    
    def _generate_with_ai(self, request: GenerationRequest, intent: Optional[Intent]) -> str:
        """
        使用 AI 生成代码
        
        调用 GlobalModelRouter 生成代码
        """
        if not self._router or not ModelCapability:
            # 降级：使用模板生成
            return self._generate_with_template(request)
            
        # 构建 prompt
        prompt = self._build_code_generation_prompt(request, intent)
        
        # 调用 GlobalModelRouter
        try:
            result = self._router.call_model_sync(
                capability=ModelCapability.CODE_GENERATION,
                prompt=prompt,
                temperature=0.2,
                max_tokens=2048,
            )
            
            if result and "response" in result:
                code = result["response"]
                # 提取代码块
                code = self._extract_code_block(code, request.language)
                return code
                
        except Exception as e:
            print(f"AI 生成失败: {e}")
            
        # 降级：使用模板生成
        return self._generate_with_template(request)
    
    def _build_code_generation_prompt(self, request: GenerationRequest, intent: Optional[Intent]) -> str:
        """构建代码生成 prompt"""
        language = request.language
        framework = request.framework
        context = request.context
        include_comments = request.include_comments
        optimize = request.optimize
        
        prompt = f"""你是一个专业的 {language} 开发者。请根据以下需求生成高质量代码。

## 需求
{request.intent}

## 要求
- 语言: {language}
"""
        
        if framework:
            prompt += f"- 框架: {framework}\n"
            
        if include_comments:
            prompt += "- 添加清晰的注释和文档字符串\n"
            
        if optimize:
            prompt += "- 优化代码性能和可读性\n"
            
        prompt += "- 遵循最佳实践和编码规范\n"
        prompt += "- 只返回代码，不要额外解释\n"
        
        if context:
            prompt += f"\n## 上下文代码\n```context\n"
            
        prompt += "\n## 输出格式\n只返回代码块，使用 markdown 代码块格式。"
        
        return prompt
    
    def _extract_code_block(self, text: str, language: str) -> str:
        """从文本中提取代码块"""
        # 匹配 ```language ... ``` 或 ``` ... ```
        pattern = r"```(?:\w+\s+)?(.*?)```"
        matches = re.findall(pattern, text, re.DOTALL)
        
        if matches:
            return matches[0].strip()
            
        # 如果没有代码块，返回整个文本
        return text.strip()
    
    def _post_process(self, code: str, language: str) -> str:
        """后处理代码"""
        if language == "python":
            # 使用 autopep8 格式化 Python 代码
            try:
                code = autopep8.fix_code(code)
            except Exception:
                pass
                
        return code
    
    def _generate_with_template(self, request: GenerationRequest) -> str:
        """使用模板生成代码（降级方案）"""
        # 这里可以调用原有的 IntentCodeGenerator
        try:
            from business.ide.code_generator import IntentCodeGenerator
            generator = IntentCodeGenerator()
            result = generator.generate(request.intent, language=request.language)
            if result.success:
                return result.generated.code
        except Exception:
            pass
            
        # 如果都失败，返回简单模板
        return f"# TODO: 实现 {request.intent}\ndef generated_function():\n    pass\n"
    
    # ============ 代码补全 ============
    
    def complete(self, code_prefix: str, language: str = "python", 
                context: str = "", max_suggestions: int = 3) -> List[CodeCompletion]:
        """
        代码补全
        
        Args:
            code_prefix: 代码前缀（如 "def login(user"）
            language: 编程语言
            context: 上下文代码
            max_suggestions: 最大建议数
            
        Returns:
            List[CodeCompletion]: 补全建议列表
        """
        if not self._router or not ModelCapability:
            return [CodeCompletion(
                completion="",
                explanation="AI 补全不可用",
                confidence=0.0
            )]
            
        # 构建 prompt
        prompt = f"""你是一个专业的 {language} 开发者。请补全以下代码。

## 代码前缀
```{language}
{code_prefix}
```

## 上下文
```{language}
{context}
```

## 要求
- 补全代码，使其语法正确、逻辑完整
- 返回 JSON 格式，包含以下字段：
  - "completion": 补全的代码（只返回补全部分，不包含前缀）
  - "explanation": 补全的解释
  - "alternatives": 其他可能的补全（最多 3 个）
- 只返回 JSON，不要额外解释
"""
        
        # 调用 AI
        try:
            result = self._router.call_model_sync(
                capability=ModelCapability.CODE_COMPLETION,
                prompt=prompt,
                temperature=0.1,
                max_tokens=1024,
            )
            
            if result and "response" in result:
                import json
                response = result["response"]
                # 提取 JSON
                json_match = re.search(r"\{.*\}", response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(0))
                    completions = []
                    
                    # 主补全
                    completions.append(CodeCompletion(
                        completion=data.get("completion", ""),
                        explanation=data.get("explanation", ""),
                        confidence=0.9,
                        alternatives=data.get("alternatives", [])
                    ))
                    
                    return completions[:max_suggestions]
                    
        except Exception as e:
            print(f"代码补全失败: {e}")
            
        return [CodeCompletion(
            completion="",
            explanation=f"补全失败: {str(e)}",
            confidence=0.0
        )]
    
    # ============ 测试生成 ============
    
    def generate_tests(self, code: str, language: str = "python", 
                      test_type: str = "unit") -> List[TestCase]:
        """
        生成测试代码
        
        Args:
            code: 要测试的代码
            language: 编程语言
            test_type: 测试类型（unit/integration/e2e）
            
        Returns:
            List[TestCase]: 测试用例列表
        """
        if not self._router or not ModelCapability:
            return []
            
        # 构建 prompt
        prompt = f"""你是一个专业的测试工程师。请为以下代码生成 {test_type} 测试。

## 代码
```{language}
{code}
```

## 要求
- 测试类型: {test_type}
- 使用 {self._get_test_framework(language)} 测试框架
- 覆盖主要功能和边界情况
- 返回 JSON 格式，包含以下字段：
  - "test_code": 测试代码
  - "test_description": 测试描述
  - "test_type": 测试类型
  - "coverage": 估计的测试覆盖率（0-1 之间）
- 生成 3-5 个测试用例
- 只返回 JSON 数组，不要额外解释
"""
        
        # 调用 AI
        try:
            result = self._router.call_model_sync(
                capability=ModelCapability.CODE_GENERATION,
                prompt=prompt,
                temperature=0.3,
                max_tokens=2048,
            )
            
            if result and "response" in result:
                import json
                response = result["response"]
                # 提取 JSON 数组
                json_match = re.search(r"\[.*\]", response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(0))
                    tests = []
                    for item in data:
                        tests.append(TestCase(
                            test_code=item.get("test_code", ""),
                            test_description=item.get("test_description", ""),
                            test_type=item.get("test_type", test_type),
                            coverage=item.get("coverage", 0.0)
                        ))
                    return tests
                    
        except Exception as e:
            print(f"测试生成失败: {e}")
            
        return []
    
    def _generate_tests_with_ai(self, code: str, language: str) -> List[TestCase]:
        """使用 AI 生成测试（内部方法）"""
        return self.generate_tests(code, language, test_type="unit")
    
    # ============ 辅助方法 ============
    
    def _detect_template(self, intent: str, language: str) -> CodeTemplate:
        """检测模板类型"""
        intent_lower = intent.lower()
        
        if "test" in intent_lower or "测试" in intent_lower:
            return CodeTemplate.TEST
        if "api" in intent_lower or "接口" in intent_lower:
            return CodeTemplate.API_ENDPOINT
        if "class" in intent_lower or "类" in intent_lower:
            return CodeTemplate.CLASS
        if "function" in intent_lower or "函数" in intent_lower or "def " in intent_lower:
            return CodeTemplate.FUNCTION
            
        return CodeTemplate.FUNCTION
    
    def _suggest_file_path(self, request: GenerationRequest) -> str:
        """建议文件路径"""
        language = request.language
        intent = request.intent
        
        # 提取名称
        name = re.sub(r"[^a-zA-Z0-9_]", "_", intent[:20]).strip("_")
        
        # 语言特定后缀
        suffix_map = {
            "python": ".py",
            "javascript": ".js",
            "typescript": ".ts",
            "java": ".java",
            "go": ".go",
        }
        
        suffix = suffix_map.get(language, ".txt")
        
        # 模板特定前缀
        template_prefix = {
            CodeTemplate.TEST: "test_",
            CodeTemplate.API_ENDPOINT: "",
            CodeTemplate.CLASS: "",
        }
        
        prefix = template_prefix.get(self._detect_template(intent, language), "")
        
        return f"{prefix}{name}{suffix}"
    
    def _generate_suggestions(self, language: str) -> List[str]:
        """生成建议"""
        suggestions = []
        
        if language == "python":
            suggestions.append("可使用 type hints 增强类型安全")
            suggestions.append("可添加 docstring 说明函数用途")
        elif language in ["javascript", "typescript"]:
            suggestions.append("建议添加 JSDoc 注释")
            if language == "javascript":
                suggestions.append("考虑使用 TypeScript 增强类型安全")
                
        suggestions.append("生成后请检查代码逻辑是否满足需求")
        
        return suggestions
    
    def _get_test_framework(self, language: str) -> str:
        """获取测试框架"""
        framework_map = {
            "python": "pytest",
            "javascript": "jest",
            "typescript": "jest",
            "java": "junit",
            "go": "testing",
        }
        return framework_map.get(language, "unknown")
    
    # ============ 其他功能 ============
    
    def preview(self, generated: GeneratedCode) -> str:
        """预览生成的代码"""
        lines = [
            "=" * 60,
            f" 预览: {generated.file_path}",
            "=" * 60,
            "",
            f" 语言: {generated.language}",
            f" 模板: {generated.template_type.value}",
            f" 置信度: {generated.confidence:.0%}",
            "",
            "-" * 60,
            "",
            generated.code,
            "",
            "-" * 60,
        ]
        
        if generated.warnings:
            lines.extend(["", "⚠️  警告:"])
            for w in generated.warnings:
                lines.append(f"  • {w}")
            
        if generated.suggestions:
            lines.extend(["", "💡 建议:"])
            for s in generated.suggestions:
                lines.append(f"  • {s}")
            
        lines.extend(["", "=" * 60])
        
        return "\n".join(lines)
    
    def apply(self, generated: GeneratedCode, overwrite: bool = False) -> bool:
        """应用生成的代码到文件"""
        import os
        
        file_path = generated.file_path
        
        # 检查文件是否存在
        if os.path.exists(file_path) and not overwrite:
            # 追加模式
            with open(file_path, "a", encoding="utf-8") as f:
                f.write("\n\n")
                f.write(generated.code)
            return True
            
        # 创建目录
        dir_path = os.path.dirname(file_path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
            
        # 写入文件
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(generated.code)
            
        return True
    
    def get_history(self) -> List[GenerationResult]:
        """获取生成历史"""
        return self.generation_history
    
    def clear_history(self):
        """清空生成历史"""
        self.generation_history.clear()


# 快捷函数
def generate_code(intent: str, **kwargs) -> GenerationResult:
    """快捷生成代码"""
    generator = EnhancedIDEGenenerator()
    request = GenerationRequest(intent=intent, **kwargs)
    return generator.generate(request)

def complete_code(code_prefix: str, language: str = "python", **kwargs) -> List[CodeCompletion]:
    """快捷代码补全"""
    generator = EnhancedIDEGenenerator()
    return generator.complete(code_prefix, language, **kwargs)

def generate_tests(code: str, language: str = "python", **kwargs) -> List[TestCase]:
    """快捷生成测试"""
    generator = EnhancedIDEGenenerator()
    return generator.generate_tests(code, language, **kwargs)


# 测试
if __name__ == "__main__":
    # 测试代码生成
    generator = EnhancedIDEGenenerator()
    
    # 测试1: AI 生成代码
    print("\n[测试1] AI 生成代码...")
    request = GenerationRequest(
        intent="写一个用户登录函数，使用 JWT 认证",
        language="python",
        framework="FastAPI",
        include_tests=True,
    )
    result = generator.generate(request)
    if result.success:
        print(generator.preview(result.generated))
        if result.tests:
            print(f"\n生成了 {len(result.tests)} 个测试")
    
    # 测试2: 代码补全
    print("\n[测试2] 代码补全...")
    completions = generator.complete("def login(user", language="python")
    for i, comp in enumerate(completions):
        print(f"补全 {i+1}: {comp.completion}")
        print(f"  解释: {comp.explanation}")
    
    # 测试3: 生成测试
    print("\n[测试3] 生成测试...")
    code = """
def add(a, b):
    return a + b
"""
    tests = generator.generate_tests(code, language="python")
    for i, test in enumerate(tests):
        print(f"测试 {i+1}: {test.test_description}")
        print(f"  代码:\n{test.test_code}")
