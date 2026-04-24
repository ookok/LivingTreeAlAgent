# -*- coding: utf-8 -*-
"""
三级验证流水线 - AI原生OS愿景 Phase 1-2

验证压缩后的上下文是否仍然有效且可用：
- L1: 语法验证 - 检查代码语法、Markdown格式、JSON结构
- L2: 语义验证 - 检查意图保留度、语义完整性、约束条件
- L3: 集成验证 - 检查模块引用、API兼容性、依赖关系

Author: AI Native OS Team
Date: 2026-04-24
"""

import re
import json
import ast
import time
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed


class VerificationLevel(Enum):
    """验证级别"""
    L1_SYNTAX = "L1_SYNTAX"      # 语法验证
    L2_SEMANTIC = "L2_SEMANTIC"  # 语义验证
    L3_INTEGRATION = "L3_INTEGRATION"  # 集成验证


class VerificationStatus(Enum):
    """验证状态"""
    PASSED = "PASSED"
    FAILED = "FAILED"
    WARNING = "WARNING"
    SKIPPED = "SKIPPED"


@dataclass
class VerificationResult:
    """单次验证结果"""
    level: VerificationLevel
    name: str
    status: VerificationStatus
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    
    def __str__(self):
        icon = {
            VerificationStatus.PASSED: "✅",
            VerificationStatus.FAILED: "❌",
            VerificationStatus.WARNING: "⚠️",
            VerificationStatus.SKIPPED: "⏭️"
        }.get(self.status, "❓")
        return f"{icon} [{self.level.value}] {self.name}: {self.message}"


@dataclass
class VerificationReport:
    """完整验证报告"""
    overall_status: VerificationStatus
    level_results: Dict[VerificationLevel, List[VerificationResult]] = field(default_factory=dict)
    total_duration_ms: float = 0.0
    recommendations: List[str] = field(default_factory=list)
    compressed_context: Optional[str] = None
    validation_signature: Optional[Dict[str, Any]] = None
    
    def get_summary(self) -> str:
        """获取摘要"""
        passed = sum(1 for results in self.level_results.values() 
                     for r in results if r.status == VerificationStatus.PASSED)
        failed = sum(1 for results in self.level_results.values() 
                     for r in results if r.status == VerificationStatus.FAILED)
        warnings = sum(1 for results in self.level_results.values() 
                       for r in results if r.status == VerificationStatus.WARNING)
        total = passed + failed + warnings
        return f"验证结果: {passed}/{total} 通过, {warnings} 警告, {failed} 失败"


# ============================================================================
# L1: 语法验证层
# ============================================================================

class L1SyntaxValidator:
    """
    L1 语法验证器
    
    验证内容:
    - 代码语法正确性 (Python/JavaScript)
    - Markdown 格式完整性
    - JSON/YAML 结构有效性
    - 文件路径格式正确性
    """
    
    def __init__(self, max_errors: int = 5):
        self.max_errors = max_errors
        self.errors: List[str] = []
    
    def validate(self, context: str, intent_signature: Dict[str, Any]) -> VerificationResult:
        """执行语法验证"""
        start_time = time.time()
        self.errors = []
        
        # 1. 检查是否为空
        if not context or not context.strip():
            self.errors.append("上下文为空")
        
        # 2. 检查代码块语法
        self._validate_code_blocks(context)
        
        # 3. 检查 Markdown 格式
        self._validate_markdown(context)
        
        # 4. 检查 JSON 语法
        self._validate_json(context)
        
        # 5. 检查文件路径
        self._validate_paths(context)
        
        # 6. 检查括号匹配
        self._validate_brackets(context)
        
        duration_ms = (time.time() - start_time) * 1000
        
        if not self.errors:
            return VerificationResult(
                level=VerificationLevel.L1_SYNTAX,
                name="语法验证",
                status=VerificationStatus.PASSED,
                message="所有语法检查通过",
                details={"error_count": 0, "checks_performed": 6},
                duration_ms=duration_ms
            )
        elif len(self.errors) <= self.max_errors:
            return VerificationResult(
                level=VerificationLevel.L1_SYNTAX,
                name="语法验证",
                status=VerificationStatus.WARNING,
                message=f"发现 {len(self.errors)} 个语法问题",
                details={"errors": self.errors[:self.max_errors], "error_count": len(self.errors)},
                duration_ms=duration_ms
            )
        else:
            return VerificationResult(
                level=VerificationLevel.L1_SYNTAX,
                name="语法验证",
                status=VerificationStatus.FAILED,
                message=f"发现 {len(self.errors)} 个严重语法错误",
                details={"errors": self.errors[:self.max_errors], "error_count": len(self.errors)},
                duration_ms=duration_ms
            )
    
    def _validate_code_blocks(self, context: str) -> None:
        """验证代码块语法"""
        code_block_pattern = r'```(\w+)?\n(.*?)```'
        code_blocks = re.findall(code_block_pattern, context, re.DOTALL)
        
        for lang, code in code_blocks:
            if not code.strip():
                self.errors.append(f"代码块为空 (语言: {lang or 'unknown'})")
                continue
            
            # Python 语法检查
            if lang in ('python', 'py', ''):
                self._validate_python_syntax(code, lang)
            
            # JavaScript 语法检查
            elif lang in ('javascript', 'js', 'typescript', 'ts'):
                self._validate_js_syntax(code, lang)
    
    def _validate_python_syntax(self, code: str, lang: str) -> None:
        """验证 Python 代码语法"""
        try:
            ast.parse(code)
        except SyntaxError as e:
            self.errors.append(f"Python 语法错误: {e.msg} (行 {e.lineno})")
    
    def _validate_js_syntax(self, code: str, lang: str) -> None:
        """验证 JavaScript 代码语法（简单检查）"""
        # 简单括号匹配检查
        if code.count('{') != code.count('}'):
            self.errors.append(f"{lang} 代码: 花括号不匹配")
        if code.count('(') != code.count(')'):
            self.errors.append(f"{lang} 代码: 圆括号不匹配")
        if code.count('[') != code.count(']'):
            self.errors.append(f"{lang} 代码: 方括号不匹配")
    
    def _validate_markdown(self, context: str) -> None:
        """验证 Markdown 格式"""
        lines = context.split('\n')
        
        # 检查标题层级是否连续
        heading_levels = []
        for i, line in enumerate(lines):
            match = re.match(r'^(#{1,6})\s+(.+)', line)
            if match:
                level = len(match.group(1))
                heading_levels.append((level, i + 1))
        
        # 检查是否有悬空的代码块
        code_block_count = context.count('```')
        if code_block_count % 2 != 0:
            self.errors.append("Markdown: 代码块未正确关闭")
        
        # 检查链接格式
        bad_links = re.findall(r'\[([^\]]+)\]\(([^)]*)\)', context)
        for text, url in bad_links:
            if not url.strip():
                self.errors.append(f"Markdown: 空链接 [{text}]()")
    
    def _validate_json(self, context: str) -> None:
        """验证 JSON 语法"""
        # 查找 JSON 块
        json_pattern = r'```json\n(.*?)```'
        json_blocks = re.findall(json_pattern, context, re.DOTALL)
        
        for json_str in json_blocks:
            try:
                json.loads(json_str)
            except json.JSONDecodeError as e:
                self.errors.append(f"JSON 语法错误: {e.msg} (位置 {e.pos})")
    
    def _validate_paths(self, context: str) -> None:
        """验证文件路径格式"""
        # Windows 路径
        win_paths = re.findall(r'[A-Za-z]:\\[^\s<>"|?*]+', context)
        for path in win_paths:
            if path.endswith('\\') and len(path) > 4:
                self.errors.append(f"路径以反斜杠结尾: {path}")
        
        # Unix 路径
        unix_paths = re.findall(r'(?:^|/)\/(?:[^\s<>"|?*]+)', context)
        for path in unix_paths:
            if path.endswith('/') and len(path) > 2:
                self.errors.append(f"路径以正斜杠结尾: {path}")
    
    def _validate_brackets(self, context: str) -> None:
        """验证括号匹配（通用）"""
        brackets = {'(': ')', '[': ']', '{': '}'}
        
        # 移除代码块内容（避免字符串内的括号干扰）
        clean_context = re.sub(r'```.*?```', '', context, flags=re.DOTALL)
        clean_context = re.sub(r'"[^"]*"', '', clean_context)
        clean_context = re.sub(r"'[^']*'", '', clean_context)
        
        stack = []
        for char in clean_context:
            if char in brackets:
                stack.append(char)
            elif char in brackets.values():
                if not stack:
                    self.errors.append(f"多余的闭合括号: {char}")
                else:
                    opening = stack.pop()
                    if brackets[opening] != char:
                        self.errors.append(f"括号不匹配: {opening} 与 {char}")


# ============================================================================
# L2: 语义验证层
# ============================================================================

class L2SemanticValidator:
    """
    L2 语义验证器
    
    验证内容:
    - 意图保留度检查（核心意图是否在压缩后仍存在）
    - 语义完整性检查（关键信息是否丢失）
    - 约束条件检查（用户指定的约束是否满足）
    - 上下文一致性检查（前后文是否矛盾）
    """
    
    def __init__(self, min_intent_preservation: float = 0.8):
        self.min_intent_preservation = min_intent_preservation
    
    def validate(self, context: str, intent_signature: Dict[str, Any], 
                 original_query: str = "") -> VerificationResult:
        """执行语义验证"""
        start_time = time.time()
        issues = []
        
        # 1. 意图保留度检查
        intent_score = self._check_intent_preservation(context, intent_signature)
        if intent_score < self.min_intent_preservation:
            issues.append(f"意图保留度过低: {intent_score:.1%} < {self.min_intent_preservation:.1%}")
        
        # 2. 关键词完整性检查
        self._check_keyword_completeness(context, original_query, issues)
        
        # 3. 代码签名完整性检查
        self._check_code_signature_completeness(context, intent_signature, issues)
        
        # 4. 约束条件满足度检查
        self._check_constraint_satisfaction(context, intent_signature, issues)
        
        # 5. 上下文一致性检查
        self._check_context_consistency(context, issues)
        
        duration_ms = (time.time() - start_time) * 1000
        
        if not issues:
            return VerificationResult(
                level=VerificationLevel.L2_SEMANTIC,
                name="语义验证",
                status=VerificationStatus.PASSED,
                message=f"语义完整性检查通过 (意图保留度: {intent_score:.1%})",
                details={
                    "intent_preservation": intent_score,
                    "checks_passed": 5
                },
                duration_ms=duration_ms
            )
        else:
            return VerificationResult(
                level=VerificationLevel.L2_SEMANTIC,
                name="语义验证",
                status=VerificationStatus.WARNING,
                message=f"发现 {len(issues)} 个语义问题",
                details={
                    "intent_preservation": intent_score,
                    "issues": issues,
                    "checks_passed": 5 - len(issues)
                },
                duration_ms=duration_ms
            )
    
    def _check_intent_preservation(self, context: str, intent_signature: Dict) -> float:
        """检查意图保留度"""
        score = 1.0
        
        # 检查意图类型是否在上下文中体现
        intent_type = intent_signature.get('type', '')
        type_indicators = {
            'create': ['创建', '生成', '新建', 'add', 'create', 'new'],
            'modify': ['修改', '更新', '编辑', 'change', 'update', 'edit'],
            'analyze': ['分析', '解析', '检查', 'analyze', 'check', 'review'],
            'debug': ['修复', '错误', 'bug', 'fix', 'error', 'debug'],
            'optimize': ['优化', '性能', '改进', 'optimize', 'performance', 'improve'],
        }
        
        indicators = type_indicators.get(intent_type.lower(), [])
        if indicators:
            found = any(ind in context.lower() for ind in indicators)
            if not found:
                score -= 0.2
        
        # 检查目标是否在上下文中
        target = intent_signature.get('target', '')
        if target and target.lower() not in context.lower():
            score -= 0.2
        
        # 检查约束是否在上下文中
        constraints = intent_signature.get('constraints', [])
        if constraints:
            satisfied = sum(1 for c in constraints if c.lower() in context.lower())
            score -= 0.1 * (1 - satisfied / len(constraints))
        
        return max(0.0, score)
    
    def _check_keyword_completeness(self, context: str, original_query: str, issues: List) -> None:
        """检查关键词完整性"""
        if not original_query:
            return
        
        # 提取关键实体（简单实现）
        important_words = re.findall(r'[\u4e00-\u9fa5]{2,}', original_query)
        important_words += re.findall(r'\b[A-Za-z]{3,}\b', original_query)
        
        # 过滤停用词
        stop_words = {'这个', '那个', '什么', '怎么', '如何', '一个', '帮我', '请', 'the', 'and', 'for', 'with'}
        important_words = [w for w in important_words if w not in stop_words]
        
        # 检查关键词保留率
        preserved = sum(1 for w in important_words if w in context)
        preservation_rate = preserved / len(important_words) if important_words else 1.0
        
        if preservation_rate < 0.7:
            missing = [w for w in important_words if w not in context]
            issues.append(f"关键词丢失: {missing[:3]}")
    
    def _check_code_signature_completeness(self, context: str, intent_signature: Dict, issues: List) -> None:
        """检查代码签名完整性"""
        code_signatures = intent_signature.get('code_signatures', [])
        if not code_signatures:
            return
        
        # 检查代码块中的签名是否完整
        code_blocks = re.findall(r'```\w+\n(.*?)```', context, re.DOTALL)
        total_lines = sum(len(block.split('\n')) for block in code_blocks)
        
        # 如果代码太长，可能签名化不彻底
        if total_lines > 100:
            issues.append(f"代码块过长 ({total_lines} 行)，可能未充分签名化")
    
    def _check_constraint_satisfaction(self, context: str, intent_signature: Dict, issues: List) -> None:
        """检查约束条件满足度"""
        constraints = intent_signature.get('constraints', [])
        
        for constraint in constraints:
            constraint_lower = constraint.lower()
            
            # 性能相关约束
            if any(word in constraint_lower for word in ['性能', '高效', 'performance', 'fast']):
                if 'O(' not in context and '复杂度' not in context:
                    issues.append("约束 '性能' 未在上下文中体现")
            
            # 安全性相关约束
            if any(word in constraint_lower for word in ['安全', 'security', '加密']):
                if 'security' not in context.lower() and '安全' not in context:
                    issues.append("约束 '安全' 未在上下文中体现")
            
            # 兼容性相关约束
            if any(word in constraint_lower for word in ['兼容', 'compatible', '适配']):
                if 'compat' not in context.lower():
                    issues.append("约束 '兼容性' 未在上下文中体现")
    
    def _check_context_consistency(self, context: str, issues: List) -> None:
        """检查上下文一致性"""
        # 检查是否有矛盾的信息
        contradictions = [
            ('import', 'export'),  # 导入 vs 导出
            ('async', 'sync'),     # 异步 vs 同步
            ('class', 'function'), # 类 vs 函数（取决于语言）
        ]
        
        for pos, neg in contradictions:
            pos_count = context.lower().count(pos.lower())
            neg_count = context.lower().count(neg.lower())
            if pos_count > 0 and neg_count > 0:
                # 可能是合理的（如既有导入也有导出），只警告
                if abs(pos_count - neg_count) > 5:
                    issues.append(f"上下文可能存在矛盾: {pos} vs {neg}")


# ============================================================================
# L3: 集成验证层
# ============================================================================

class L3IntegrationValidator:
    """
    L3 集成验证器
    
    验证内容:
    - 模块引用完整性（引用的模块是否存在）
    - API 兼容性检查（使用的 API 是否存在）
    - 依赖关系检查（依赖的包是否在上下文中说明）
    - 执行路径检查（代码是否可以正常执行）
    """
    
    def __init__(self):
        self.issues = []
    
    def validate(self, context: str, intent_signature: Dict[str, Any],
                 project_context: Optional[Dict[str, Any]] = None) -> VerificationResult:
        """执行集成验证"""
        start_time = time.time()
        self.issues = []
        project_context = project_context or {}
        
        # 1. 检查导入语句
        self._validate_imports(context)
        
        # 2. 检查依赖声明
        self._validate_dependencies(context)
        
        # 3. 检查函数调用
        self._validate_function_calls(context)
        
        # 4. 检查类型引用
        self._validate_type_references(context, project_context)
        
        # 5. 检查配置文件引用
        self._validate_config_references(context)
        
        duration_ms = (time.time() - start_time) * 1000
        
        if not self.issues:
            return VerificationResult(
                level=VerificationLevel.L3_INTEGRATION,
                name="集成验证",
                status=VerificationStatus.PASSED,
                message="模块引用和依赖关系检查通过",
                details={"issues_count": 0, "checks_performed": 5},
                duration_ms=duration_ms
            )
        else:
            return VerificationResult(
                level=VerificationLevel.L3_INTEGRATION,
                name="集成验证",
                status=VerificationStatus.WARNING,
                message=f"发现 {len(self.issues)} 个集成问题",
                details={"issues": self.issues, "issues_count": len(self.issues)},
                duration_ms=duration_ms
            )
    
    def _validate_imports(self, context: str) -> None:
        """验证导入语句"""
        # Python 导入
        py_imports = re.findall(r'^(?:from\s+([\w.]+)\s+)?import\s+(.+)', context, re.MULTILINE)
        for module, items in py_imports:
            if module:
                if module.startswith('.'):
                    self.issues.append(f"相对导入可能无法解析: {module}")
                # 检查常见标准库
                std_libs = ['os', 'sys', 'json', 're', 'time', 'datetime', 'collections']
                if module.split('.')[0] not in std_libs:
                    self.issues.append(f"第三方模块未在依赖中声明: {module}")
        
        # JavaScript 导入
        js_imports = re.findall(r'(?:import|require)\s*(?:\{[^}]*\}|\*\s*as\s+\w+|\w+)?\s*from\s*[\'"]([^\'"]+)[\'"]', context)
        for module in js_imports:
            if module.startswith('.'):
                continue  # 相对导入跳过
            if not any(std in module for std in ['@/', '@/']):
                self.issues.append(f"JavaScript 模块可能缺少依赖: {module}")
    
    def _validate_dependencies(self, context: str) -> None:
        """验证依赖声明"""
        # 检查 requirements.txt / package.json 引用
        has_requirements = 'requirements.txt' in context
        has_package_json = 'package.json' in context
        
        # 统计外部依赖
        py_deps = re.findall(r'(?:from\s+([\w]+)\s+import|import\s+([\w]+))', context)
        # 修复正则表达式 - 移除错误的语法
        js_pattern = r'import\s+.*?from\s+[\'"]([^\'".@]+)'
        js_deps = re.findall(js_pattern, context)
        
        # 如果有依赖但没有依赖文件引用
        if (py_deps or js_deps) and not (has_requirements or has_package_json):
            dep_count = len(set(py_deps)) + len(set(js_deps))
            if dep_count > 3:
                self.issues.append(f"发现 {dep_count} 个外部依赖，但未引用依赖配置文件")
    
    def _validate_function_calls(self, context: str) -> None:
        """验证函数调用"""
        # 检查函数定义与调用是否匹配
        function_defs = re.findall(r'def\s+(\w+)\s*\(', context)
        function_calls = re.findall(r'(\w+)\s*\(', context)
        
        # 过滤内置函数
        builtins = {'print', 'len', 'str', 'int', 'float', 'list', 'dict', 'set', 'tuple',
                   'range', 'enumerate', 'zip', 'map', 'filter', 'sum', 'min', 'max',
                   'open', 'input', 'isinstance', 'type', 'hasattr', 'getattr', 'setattr'}
        
        defined_funcs = set(function_defs)
        called_funcs = set(function_calls) - builtins
        
        # 检查未定义但调用的函数
        undefined = called_funcs - defined_funcs
        if undefined:
            # 只报告可能的问题（排除常见库函数）
            likely_undefined = undefined - {
                'self', 'cls', 'super', 'log', 'error', 'warn', 'info',
                'pd', 'np', 'plt', 'tf', 'torch', 'db', 'api', 'app'
            }
            if likely_undefined:
                self.issues.append(f"可能未定义的函数调用: {list(likely_undefined)[:3]}")
    
    def _validate_type_references(self, context: str, project_context: Dict) -> None:
        """验证类型引用"""
        # 提取类型注解
        type_annotations = re.findall(r':\s*([A-Z]\w*)\s*[=,\)]', context)
        type_annotations += re.findall(r'->\s*([A-Z]\w*)', context)
        
        # 提取类定义
        class_defs = re.findall(r'class\s+(\w+)', context)
        defined_types = set(class_defs)
        
        # 检查未定义类型
        for type_name in type_annotations:
            if type_name not in defined_types and type_name not in project_context.get('types', []):
                # 可能是标准库类型，检查
                std_types = {'str', 'int', 'float', 'bool', 'list', 'dict', 'tuple', 
                           'set', 'Optional', 'List', 'Dict', 'Any', 'Union', 'Callable'}
                if type_name not in std_types:
                    self.issues.append(f"可能未定义的类型: {type_name}")
    
    def _validate_config_references(self, context: str) -> None:
        """验证配置文件引用"""
        # 检查引用的配置文件是否存在
        config_files = re.findall(r'[\'"]([\w.-]+\.(?:json|yaml|yml|ini|toml|env))[\'"]', context)
        
        # 检查环境变量引用
        env_vars = re.findall(r'(?:os\.environ|process\.env)\s*\[[\'"]([^\'"]+)[\'"]\]', context)
        
        # 如果有配置引用但没有说明
        if (config_files or env_vars) and '# config' not in context.lower() and '# env' not in context.lower():
            self.issues.append(f"引用了 {len(config_files)} 个配置文件和 {len(env_vars)} 个环境变量")


# ============================================================================
# 三级验证流水线
# ============================================================================

class ThreeLevelVerificationPipeline:
    """
    三级验证流水线
    
    整合 L1/L2/L3 三层验证，确保压缩后的上下文质量。
    
    流程:
    1. L1 语法验证 → 代码语法、Markdown、JSON
    2. L2 语义验证 → 意图保留度、语义完整性
    3. L3 集成验证 → 模块引用、依赖关系
    """
    
    def __init__(self, 
                 l1_max_errors: int = 5,
                 l2_min_preservation: float = 0.8,
                 parallel_execution: bool = True):
        """
        初始化验证流水线
        
        Args:
            l1_max_errors: L1 最大允许错误数
            l2_min_preservation: L2 最小意图保留度
            parallel_execution: 是否并行执行验证
        """
        self.l1_validator = L1SyntaxValidator(max_errors=l1_max_errors)
        self.l2_validator = L2SemanticValidator(min_intent_preservation=l2_min_preservation)
        self.l3_validator = L3IntegrationValidator()
        self.parallel_execution = parallel_execution
        
        # 验证级别定义
        self.levels = [
            VerificationLevel.L1_SYNTAX,
            VerificationLevel.L2_SEMANTIC,
            VerificationLevel.L3_INTEGRATION
        ]
    
    def verify(self, context: str, intent_signature: Dict[str, Any],
               original_query: str = "",
               project_context: Optional[Dict[str, Any]] = None) -> VerificationReport:
        """
        执行完整验证流程
        
        Args:
            context: 待验证的压缩上下文
            intent_signature: 意图签名
            original_query: 原始查询（用于对比）
            project_context: 项目上下文（可选）
        
        Returns:
            VerificationReport: 完整验证报告
        """
        start_time = time.time()
        level_results: Dict[VerificationLevel, List[VerificationResult]] = {
            level: [] for level in self.levels
        }
        
        if self.parallel_execution:
            # 并行执行
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {
                    executor.submit(self._run_l1, context, intent_signature): VerificationLevel.L1_SYNTAX,
                    executor.submit(self._run_l2, context, intent_signature, original_query): VerificationLevel.L2_SEMANTIC,
                    executor.submit(self._run_l3, context, intent_signature, project_context): VerificationLevel.L3_INTEGRATION,
                }
                
                for future in as_completed(futures):
                    level = futures[future]
                    try:
                        result = future.result()
                        level_results[level].append(result)
                    except Exception as e:
                        level_results[level].append(VerificationResult(
                            level=level,
                            name="验证执行",
                            status=VerificationStatus.FAILED,
                            message=f"验证执行失败: {str(e)}",
                            duration_ms=0
                        ))
        else:
            # 串行执行
            level_results[VerificationLevel.L1_SYNTAX].append(
                self._run_l1(context, intent_signature))
            level_results[VerificationLevel.L2_SEMANTIC].append(
                self._run_l2(context, intent_signature, original_query))
            level_results[VerificationLevel.L3_INTEGRATION].append(
                self._run_l3(context, intent_signature, project_context))
        
        # 计算整体状态
        overall_status = self._compute_overall_status(level_results)
        
        # 生成建议
        recommendations = self._generate_recommendations(level_results)
        
        # 生成验证签名
        validation_signature = self._generate_validation_signature(level_results)
        
        total_duration_ms = (time.time() - start_time) * 1000
        
        return VerificationReport(
            overall_status=overall_status,
            level_results=level_results,
            total_duration_ms=total_duration_ms,
            recommendations=recommendations,
            compressed_context=context if overall_status != VerificationStatus.FAILED else None,
            validation_signature=validation_signature
        )
    
    def _run_l1(self, context: str, intent_signature: Dict) -> VerificationResult:
        """执行 L1 语法验证"""
        return self.l1_validator.validate(context, intent_signature)
    
    def _run_l2(self, context: str, intent_signature: Dict, original_query: str) -> VerificationResult:
        """执行 L2 语义验证"""
        return self.l2_validator.validate(context, intent_signature, original_query)
    
    def _run_l3(self, context: str, intent_signature: Dict, project_context: Optional[Dict]) -> VerificationResult:
        """执行 L3 集成验证"""
        return self.l3_validator.validate(context, intent_signature, project_context)
    
    def _compute_overall_status(self, level_results: Dict) -> VerificationStatus:
        """计算整体验证状态"""
        all_results = [r for results in level_results.values() for r in results]
        
        if any(r.status == VerificationStatus.FAILED for r in all_results):
            return VerificationStatus.FAILED
        elif any(r.status == VerificationStatus.WARNING for r in all_results):
            return VerificationStatus.WARNING
        elif all(r.status == VerificationStatus.PASSED for r in all_results):
            return VerificationStatus.PASSED
        else:
            return VerificationStatus.SKIPPED
    
    def _generate_recommendations(self, level_results: Dict) -> List[str]:
        """生成改进建议"""
        recommendations = []
        
        for level, results in level_results.items():
            for result in results:
                if result.status in (VerificationStatus.FAILED, VerificationStatus.WARNING):
                    if result.details.get('errors'):
                        recommendations.append(f"{level.value}: 修复语法错误")
                    if result.details.get('intent_preservation', 1.0) < 0.8:
                        recommendations.append(f"{level.value}: 提高意图保留度")
                    if result.details.get('issues'):
                        for issue in result.details['issues'][:2]:
                            recommendations.append(f"{level.value}: {issue}")
        
        return list(set(recommendations))[:5]  # 最多5条建议
    
    def _generate_validation_signature(self, level_results: Dict) -> Dict[str, Any]:
        """生成验证签名"""
        signature = {
            "validated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "levels_passed": [],
            "levels_warning": [],
            "levels_failed": [],
            "intent_preservation": None,
            "syntax_errors": 0,
        }
        
        for level, results in level_results.items():
            for result in results:
                if result.status == VerificationStatus.PASSED:
                    signature["levels_passed"].append(level.value)
                elif result.status == VerificationStatus.WARNING:
                    signature["levels_warning"].append(level.value)
                elif result.status == VerificationStatus.FAILED:
                    signature["levels_failed"].append(level.value)
                
                if result.details.get('intent_preservation'):
                    signature['intent_preservation'] = result.details['intent_preservation']
                if result.details.get('error_count'):
                    signature['syntax_errors'] += result.details['error_count']
        
        return signature
    
    def quick_verify(self, context: str) -> Tuple[bool, str]:
        """
        快速验证（仅 L1）
        
        用于实时反馈场景
        
        Returns:
            (是否通过, 消息)
        """
        result = self.l1_validator.validate(context, {})
        passed = result.status in (VerificationStatus.PASSED, VerificationStatus.WARNING)
        return passed, result.message


# ============================================================================
# 与压缩器的集成
# ============================================================================

class VerifiedCompressionPipeline:
    """
    带验证的压缩流水线
    
    将意图保持型压缩器与三级验证流水线整合，
    确保输出的上下文经过质量验证。
    """
    
    def __init__(self, compressor: Any = None, verifier: ThreeLevelVerificationPipeline = None):
        """
        初始化
        
        Args:
            compressor: 意图保持型压缩器（可选，默认使用内置）
            verifier: 验证器（可选，默认新建）
        """
        self.compressor = compressor
        self.verifier = verifier or ThreeLevelVerificationPipeline()
    
    def compress_and_verify(self, query: str, context: str, code: str = "",
                           project_context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        压缩并验证
        
        Args:
            query: 用户查询
            context: 原始上下文
            code: 代码内容（可选）
            project_context: 项目上下文（可选）
        
        Returns:
            {
                "compressed": str,           # 压缩后的上下文
                "verification_report": dict, # 验证报告
                "intent_signature": dict,    # 意图签名
                "success": bool              # 是否通过验证
            }
        """
        # 1. 压缩
        if self.compressor:
            compression_result = self.compressor.compress(query, context, code)
            compressed_context = compression_result.get('compressed', context)
            intent_signature = compression_result.get('intent_signature', {})
        else:
            # 如果没有压缩器，直接使用原始上下文
            compressed_context = context
            intent_signature = {}
        
        # 2. 验证
        report = self.verifier.verify(
            context=compressed_context,
            intent_signature=intent_signature,
            original_query=query,
            project_context=project_context
        )
        
        # 3. 决定输出
        success = report.overall_status != VerificationStatus.FAILED
        
        return {
            "compressed": compressed_context if success else context,
            "verification_report": {
                "overall_status": report.overall_status.value,
                "summary": report.get_summary(),
                "duration_ms": report.total_duration_ms,
                "recommendations": report.recommendations,
                "validation_signature": report.validation_signature,
                "level_details": {
                    level.value: [
                        {"name": r.name, "status": r.status.value, "message": r.message}
                        for r in results
                    ]
                    for level, results in report.level_results.items()
                }
            },
            "intent_signature": intent_signature,
            "success": success
        }


# ============================================================================
# 便捷函数
# ============================================================================

def quick_verify(context: str) -> Tuple[bool, str]:
    """
    快速验证上下文语法
    
    用法:
        is_valid, message = quick_verify("你的上下文...")
    """
    pipeline = ThreeLevelVerificationPipeline()
    return pipeline.quick_verify(context)


def verify_and_fix(context: str, intent_signature: Dict) -> Tuple[str, List[str]]:
    """
    验证并尝试修复问题
    
    Args:
        context: 待验证上下文
        intent_signature: 意图签名
    
    Returns:
        (修复后的上下文, 问题列表)
    """
    verifier = ThreeLevelVerificationPipeline()
    issues = []
    
    # L1: 修复语法问题
    l1 = L1SyntaxValidator()
    result = l1.validate(context, intent_signature)
    
    if result.status == VerificationStatus.FAILED:
        issues.extend(result.details.get('errors', []))
        
        # 尝试修复
        fixed = context
        # 移除空代码块
        fixed = re.sub(r'```\w*\n```', '', fixed)
        # 修复未闭合的代码块
        code_block_count = fixed.count('```')
        if code_block_count % 2 != 0:
            fixed += '\n```'
        
        context = fixed
    
    # L2: 检查语义
    l2 = L2SemanticValidator()
    result = l2.validate(context, intent_signature)
    if result.status != VerificationStatus.PASSED:
        issues.extend(result.details.get('issues', []))
    
    return context, issues
