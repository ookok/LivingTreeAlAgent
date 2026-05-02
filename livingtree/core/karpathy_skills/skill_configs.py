"""
Karpathy 技能配置系统

实现预设技能：code-review, test-generator, refactor-advisor, doc-writer, performance-optimizer
"""

import asyncio
import time
import re
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass, field
import abc

from .models import (
    KarpathySkill,
    ReviewResult,
    TestResult,
    RefactorSuggestion,
    DocResult
)


class KarpathySkillRegistry:
    """
    Karpathy 技能注册表

    管理 Karpathy 技能
    """

    def __init__(self):
        self.skills: Dict[str, KarpathySkill] = {}
        self.skill_metadata: Dict[str, Dict[str, Any]] = {}

    async def register_skill(self, skill: KarpathySkill):
        """
        注册技能

        Args:
            skill: 技能实例
        """
        self.skills[skill.skill_id] = skill
        self.skill_metadata[skill.skill_id] = {
            "name": skill.name,
            "description": skill.description,
            "category": skill.category,
            "tags": skill.tags
        }

    async def execute_skill(
        self,
        skill_id: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行技能

        Args:
            skill_id: 技能 ID
            parameters: 技能参数

        Returns:
            Dict: 执行结果
        """
        skill = self.skills.get(skill_id)
        if not skill:
            return {
                "success": False,
                "error": f"Skill '{skill_id}' not found"
            }

        try:
            result = await skill.execute(parameters)
            return {
                "success": True,
                "result": result
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def get_skill(self, skill_id: str) -> Optional[KarpathySkill]:
        """
        获取技能

        Args:
            skill_id: 技能 ID

        Returns:
            Optional[KarpathySkill]: 技能实例
        """
        return self.skills.get(skill_id)

    def get_skills(self) -> List[str]:
        """
        获取所有技能 ID

        Returns:
            List[str]: 技能 ID 列表
        """
        return list(self.skills.keys())

    def get_skill_metadata(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """
        获取技能元数据

        Args:
            skill_id: 技能 ID

        Returns:
            Optional[Dict[str, Any]]: 技能元数据
        """
        return self.skill_metadata.get(skill_id)

    def search_skills(self, query: str) -> List[str]:
        """
        搜索技能

        Args:
            query: 搜索关键词

        Returns:
            List[str]: 匹配的技能 ID 列表
        """
        query_lower = query.lower()
        matches = []

        for skill_id, metadata in self.skill_metadata.items():
            if (
                query_lower in metadata["name"].lower() or
                query_lower in metadata["description"].lower() or
                query_lower in metadata["category"].lower() or
                any(query_lower in tag.lower() for tag in metadata["tags"])
            ):
                matches.append(skill_id)

        return matches


class CodeReviewSkill(KarpathySkill):
    """
    代码审查技能

    基于 Karpathy 的代码审查最佳实践
    """

    def __init__(self):
        super().__init__(
            skill_id="code_review",
            name="代码审查",
            description="深度代码审查，分析安全漏洞、性能问题、代码规范",
            category="code_quality",
            tags=["review", "security", "performance", "style"]
        )

    async def execute(
        self,
        parameters: Dict[str, Any]
    ) -> ReviewResult:
        """
        执行代码审查

        Args:
            parameters: 审查参数

        Returns:
            ReviewResult: 审查结果
        """
        code = parameters.get("code", "")
        language = parameters.get("language", "python")
        depth = parameters.get("depth", "deep")

        # 分析代码
        issues = await self._analyze_code(code, language, depth)

        return ReviewResult(
            code=code,
            language=language,
            depth=depth,
            issues=issues,
            suggestions=self._generate_suggestions(issues),
            overall_score=self._calculate_score(issues),
            timestamp=time.time()
        )

    async def _analyze_code(
        self,
        code: str,
        language: str,
        depth: str
    ) -> List[Dict[str, Any]]:
        """
        分析代码

        Args:
            code: 代码
            language: 语言
            depth: 审查深度

        Returns:
            List[Dict]: 问题列表
        """
        issues = []

        # 安全问题检查
        security_issues = self._check_security(code, language)
        issues.extend(security_issues)

        # 性能问题检查
        performance_issues = self._check_performance(code, language)
        issues.extend(performance_issues)

        # 代码规范检查
        style_issues = self._check_style(code, language)
        issues.extend(style_issues)

        # 逻辑问题检查
        logic_issues = self._check_logic(code, language)
        issues.extend(logic_issues)

        return issues[:10]  # 限制问题数量

    def _check_security(self, code: str, language: str) -> List[Dict[str, Any]]:
        """检查安全问题"""
        issues = []

        # 检查 SQL 注入
        if re.search(r'sql.*\%s|execute.*\%s' % ("\\'", "\\'"), code.lower()):
            issues.append({
                "type": "security",
                "severity": "high",
                "message": "可能存在 SQL 注入风险",
                "line": self._find_line(code, r'sql.*\%s|execute.*\%s' % ("\\'", "\\'"))
            })

        # 检查硬编码密码
        if re.search(r'password.*=.*["][^"]*["]', code):
            issues.append({
                "type": "security",
                "severity": "high",
                "message": "硬编码密码",
                "line": self._find_line(code, r'password.*=.*["][^"]*["]')
            })

        return issues

    def _check_performance(self, code: str, language: str) -> List[Dict[str, Any]]:
        """检查性能问题"""
        issues = []

        # 检查循环中的重复计算
        if re.search(r'for.*in.*range.*len\(', code):
            issues.append({
                "type": "performance",
                "severity": "medium",
                "message": "循环中重复计算 len()",
                "line": self._find_line(code, r'for.*in.*range.*len\(')
            })

        # 检查不必要的列表创建
        if re.search(r'list\(.*range\(', code):
            issues.append({
                "type": "performance",
                "severity": "low",
                "message": "不必要的列表创建",
                "line": self._find_line(code, r'list\(.*range\(')
            })

        return issues

    def _check_style(self, code: str, language: str) -> List[Dict[str, Any]]:
        """检查代码规范"""
        issues = []

        # 检查缩进
        lines = code.split('\n')
        for i, line in enumerate(lines):
            if line.startswith(' ' * 3) or line.startswith(' ' * 5):
                issues.append({
                    "type": "style",
                    "severity": "low",
                    "message": "缩进不一致",
                    "line": i + 1
                })

        # 检查变量命名
        if re.search(r'[A-Z][a-z]+', code):
            issues.append({
                "type": "style",
                "severity": "low",
                "message": "变量命名不符合规范",
                "line": self._find_line(code, r'[A-Z][a-z]+')
            })

        return issues

    def _check_logic(self, code: str, language: str) -> List[Dict[str, Any]]:
        """检查逻辑问题"""
        issues = []

        # 检查死代码
        if re.search(r'if.*False:|while.*False:', code):
            issues.append({
                "type": "logic",
                "severity": "medium",
                "message": "死代码",
                "line": self._find_line(code, r'if.*False:|while.*False:')
            })

        # 检查未使用的变量
        if re.search(r'\b\w+\s*=\s*[^=].*\b\w+\b(?!\s*=)', code):
            issues.append({
                "type": "logic",
                "severity": "low",
                "message": "可能存在未使用的变量",
                "line": self._find_line(code, r'\b\w+\s*=\s*[^=].*\b\w+\b(?!\s*=)')
            })

        return issues

    def _find_line(self, code: str, pattern: str) -> int:
        """查找模式所在行"""
        lines = code.split('\n')
        for i, line in enumerate(lines):
            if re.search(pattern, line):
                return i + 1
        return 1

    def _generate_suggestions(self, issues: List[Dict[str, Any]]) -> List[str]:
        """生成建议"""
        suggestions = []

        if any(issue["type"] == "security" for issue in issues):
            suggestions.append("使用参数化查询防止 SQL 注入")
            suggestions.append("避免硬编码敏感信息")

        if any(issue["type"] == "performance" for issue in issues):
            suggestions.append("在循环外计算不变值")
            suggestions.append("使用生成器代替列表以节省内存")

        if any(issue["type"] == "style" for issue in issues):
            suggestions.append("保持一致的缩进风格")
            suggestions.append("使用 snake_case 命名变量")

        if any(issue["type"] == "logic" for issue in issues):
            suggestions.append("移除死代码")
            suggestions.append("清理未使用的变量")

        return suggestions

    def _calculate_score(self, issues: List[Dict[str, Any]]) -> int:
        """计算代码评分"""
        score = 100

        for issue in issues:
            if issue["severity"] == "high":
                score -= 10
            elif issue["severity"] == "medium":
                score -= 5
            elif issue["severity"] == "low":
                score -= 2

        return max(0, score)


class TestGeneratorSkill(KarpathySkill):
    """
    测试生成技能

    基于函数签名自动生成边界测试用例
    """

    def __init__(self):
        super().__init__(
            skill_id="test_generator",
            name="测试生成",
            description="根据函数签名自动生成边界测试用例",
            category="testing",
            tags=["test", "unit_test", "boundary"]
        )

    async def execute(
        self,
        parameters: Dict[str, Any]
    ) -> TestResult:
        """
        执行测试生成

        Args:
            parameters: 测试参数

        Returns:
            TestResult: 测试结果
        """
        code = parameters.get("code", "")
        language = parameters.get("language", "python")
        coverage = parameters.get("coverage", "comprehensive")

        # 解析函数
        functions = self._parse_functions(code, language)

        # 生成测试用例
        test_cases = []
        for func in functions:
            cases = self._generate_test_cases(func, coverage)
            test_cases.extend(cases)

        return TestResult(
            code=code,
            language=language,
            coverage=coverage,
            functions=functions,
            test_cases=test_cases,
            test_code=self._generate_test_code(test_cases, language),
            timestamp=time.time()
        )

    def _parse_functions(self, code: str, language: str) -> List[Dict[str, Any]]:
        """解析函数"""
        functions = []

        if language == "python":
            # 简单的函数解析
            pattern = r'def\s+(\w+)\s*\(([^\)]*)\)\s*:'
            matches = re.findall(pattern, code)

            for name, params in matches:
                param_list = [p.strip() for p in params.split(',') if p.strip()]
                functions.append({
                    "name": name,
                    "parameters": param_list
                })

        return functions

    def _generate_test_cases(
        self,
        func: Dict[str, Any],
        coverage: str
    ) -> List[Dict[str, Any]]:
        """生成测试用例"""
        test_cases = []

        # 基本测试用例
        test_cases.append({
            "function": func["name"],
            "inputs": ["normal values"],
            "expected": "normal output",
            "description": "正常情况测试"
        })

        # 边界测试用例
        if coverage == "comprehensive":
            test_cases.append({
                "function": func["name"],
                "inputs": ["empty values"],
                "expected": "handles empty input",
                "description": "空值测试"
            })

            test_cases.append({
                "function": func["name"],
                "inputs": ["invalid values"],
                "expected": "handles invalid input",
                "description": "无效值测试"
            })

        return test_cases

    def _generate_test_code(
        self,
        test_cases: List[Dict[str, Any]],
        language: str
    ) -> str:
        """生成测试代码"""
        if language == "python":
            test_code = "import unittest\n\n"
            test_code += "class TestFunctions(unittest.TestCase):\n\n"

            for i, case in enumerate(test_cases):
                test_code += f"    def test_{case['function']}_{i+1}(self):\n"
                test_code += f"        # {case['description']}\n"
                test_code += f"        result = {case['function']}({case['inputs'][0]})\n"
                test_code += f"        self.assertIsNotNone(result)\n\n"

            test_code += "if __name__ == '__main__':\n    unittest.main()"
            return test_code

        return ""


class RefactorAdvisorSkill(KarpathySkill):
    """
    重构建议技能

    给出有据可查的重构建议，附带改动理由
    """

    def __init__(self):
        super().__init__(
            skill_id="refactor_advisor",
            name="重构建议",
            description="给出有据可查的重构建议，附带改动理由",
            category="refactoring",
            tags=["refactor", "optimization", "code_quality"]
        )

    async def execute(
        self,
        parameters: Dict[str, Any]
    ) -> RefactorSuggestion:
        """
        执行重构建议

        Args:
            parameters: 重构参数

        Returns:
            RefactorSuggestion: 重构建议
        """
        code = parameters.get("code", "")
        language = parameters.get("language", "python")
        level = parameters.get("level", "suggestive")

        # 分析代码
        suggestions = await self._analyze_for_refactoring(code, language, level)

        return RefactorSuggestion(
            code=code,
            language=language,
            level=level,
            suggestions=suggestions,
            improved_code=self._generate_improved_code(code, suggestions),
            timestamp=time.time()
        )

    async def _analyze_for_refactoring(
        self,
        code: str,
        language: str,
        level: str
    ) -> List[Dict[str, Any]]:
        """分析重构机会"""
        suggestions = []

        # 提取重复代码
        duplicate_code = self._find_duplicate_code(code)
        if duplicate_code:
            suggestions.append({
                "type": "duplication",
                "severity": "high",
                "message": "重复代码",
                "suggestion": "提取重复代码到函数",
                "reason": "减少代码重复，提高可维护性"
            })

        # 检查过长函数
        if self._is_function_too_long(code):
            suggestions.append({
                "type": "length",
                "severity": "medium",
                "message": "函数过长",
                "suggestion": "拆分长函数",
                "reason": "提高代码可读性和可测试性"
            })

        # 检查复杂条件
        if self._has_complex_conditions(code):
            suggestions.append({
                "type": "complexity",
                "severity": "medium",
                "message": "复杂条件",
                "suggestion": "简化条件表达式",
                "reason": "提高代码可读性"
            })

        # 检查魔术数字
        if self._has_magic_numbers(code):
            suggestions.append({
                "type": "magic_number",
                "severity": "low",
                "message": "魔术数字",
                "suggestion": "使用命名常量",
                "reason": "提高代码可读性和可维护性"
            })

        return suggestions

    def _find_duplicate_code(self, code: str) -> bool:
        """查找重复代码"""
        lines = code.split('\n')
        line_counts = {}

        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                line_counts[line] = line_counts.get(line, 0) + 1

        return any(count > 3 for count in line_counts.values())

    def _is_function_too_long(self, code: str) -> bool:
        """检查函数是否过长"""
        functions = re.findall(r'def\s+\w+\s*\([^\)]*\)\s*:(.*?)(?=def|$)', code, re.DOTALL)
        for func in functions:
            lines = func.split('\n')
            if len(lines) > 30:
                return True
        return False

    def _has_complex_conditions(self, code: str) -> bool:
        """检查复杂条件"""
        complex_patterns = [
            r'if.*and.*or',
            r'if.*\|\|.*&&',
            r'if.*\([^\)]*\)\s*and.*\([^\)]*\)'
        ]

        for pattern in complex_patterns:
            if re.search(pattern, code):
                return True
        return False

    def _has_magic_numbers(self, code: str) -> bool:
        """检查魔术数字"""
        # 排除行号、缩进等
        magic_pattern = r'\b\d+\b(?!\s*#|\s*=\s*["].*["])'  
        return bool(re.search(magic_pattern, code))

    def _generate_improved_code(
        self,
        code: str,
        suggestions: List[Dict[str, Any]]
    ) -> str:
        """生成改进后的代码"""
        # 简单的代码改进示例
        improved = code

        for suggestion in suggestions:
            if suggestion["type"] == "duplication":
                # 这里可以添加更复杂的代码重构逻辑
                pass

        return improved


class DocWriterSkill(KarpathySkill):
    """
    文档生成技能

    自动为代码生成符合项目风格的注释和文档
    """

    def __init__(self):
        super().__init__(
            skill_id="doc_writer",
            name="文档生成",
            description="自动为代码生成符合项目风格的注释和文档",
            category="documentation",
            tags=["doc", "comment", "documentation"]
        )

    async def execute(
        self,
        parameters: Dict[str, Any]
    ) -> DocResult:
        """
        执行文档生成

        Args:
            parameters: 文档参数

        Returns:
            DocResult: 文档结果
        """
        code = parameters.get("code", "")
        language = parameters.get("language", "python")
        style = parameters.get("style", "standard")

        # 生成文档
        docs = await self._generate_documentation(code, language, style)

        return DocResult(
            code=code,
            language=language,
            style=style,
            documentation=docs,
            documented_code=self._insert_documentation(code, docs, language),
            timestamp=time.time()
        )

    async def _generate_documentation(
        self,
        code: str,
        language: str,
        style: str
    ) -> Dict[str, Any]:
        """生成文档"""
        docs = {
            "functions": [],
            "classes": [],
            "modules": []
        }

        if language == "python":
            # 解析函数
            functions = re.findall(r'def\s+(\w+)\s*\(([^\)]*)\)\s*:', code)
            for name, params in functions:
                docs["functions"].append({
                    "name": name,
                    "parameters": params.strip(),
                    "docstring": self._generate_docstring(name, params, style)
                })

            # 解析类
            classes = re.findall(r'class\s+(\w+)\s*\([^\)]*\)\s*:', code)
            for name in classes:
                docs["classes"].append({
                    "name": name,
                    "docstring": f"""{name} 类"""
                })

        return docs

    def _generate_docstring(self, name: str, params: str, style: str) -> str:
        """生成 docstring"""
        if style == "standard":
            docstring = f"""{name} 函数

        Args:
        """

            param_list = [p.strip() for p in params.split(',') if p.strip()]
            for param in param_list:
                docstring += f"    {param}: 参数描述\n"

            docstring += "\nReturns:\n    返回值描述\n"""
            return docstring

        return f"""{name} 函数"""

    def _insert_documentation(
        self,
        code: str,
        docs: Dict[str, Any],
        language: str
    ) -> str:
        """插入文档"""
        if language == "python":
            # 简单的文档插入示例
            lines = code.split('\n')
            new_lines = []

            i = 0
            while i < len(lines):
                line = lines[i]
                new_lines.append(line)

                # 检查函数定义
                match = re.match(r'def\s+(\w+)\s*\(([^\)]*)\)\s*:', line)
                if match:
                    func_name = match.group(1)
                    # 查找对应的 docstring
                    for func_doc in docs["functions"]:
                        if func_doc["name"] == func_name:
                            new_lines.append(f"    {func_doc['docstring']}")
                            break

                i += 1

            return '\n'.join(new_lines)

        return code


class PerformanceOptimizerSkill(KarpathySkill):
    """
    性能优化技能

    提供具体的性能优化建议
    """

    def __init__(self):
        super().__init__(
            skill_id="performance_optimizer",
            name="性能优化",
            description="提供具体的性能优化建议",
            category="performance",
            tags=["optimization", "performance", "speed"]
        )

    async def execute(
        self,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行性能优化

        Args:
            parameters: 优化参数

        Returns:
            Dict: 优化建议
        """
        code = parameters.get("code", "")
        language = parameters.get("language", "python")
        target = parameters.get("target", "speed")

        # 分析性能问题
        issues = await self._analyze_performance(code, language, target)

        return {
            "code": code,
            "language": language,
            "target": target,
            "issues": issues,
            "suggestions": self._generate_optimization_suggestions(issues),
            "optimized_code": self._generate_optimized_code(code, issues),
            "timestamp": time.time()
        }

    async def _analyze_performance(
        self,
        code: str,
        language: str,
        target: str
    ) -> List[Dict[str, Any]]:
        """分析性能问题"""
        issues = []

        # 检查循环优化
        loop_issues = self._check_loop_optimization(code, language)
        issues.extend(loop_issues)

        # 检查内存使用
        memory_issues = self._check_memory_usage(code, language)
        issues.extend(memory_issues)

        # 检查 I/O 操作
        io_issues = self._check_io_operations(code, language)
        issues.extend(io_issues)

        return issues

    def _check_loop_optimization(self, code: str, language: str) -> List[Dict[str, Any]]:
        """检查循环优化"""
        issues = []

        # 检查循环中的昂贵操作
        if re.search(r'for.*in.*range.*len\(', code):
            issues.append({
                "type": "loop",
                "severity": "high",
                "message": "循环中重复计算 len()",
                "suggestion": "在循环外计算 len()"
            })

        # 检查嵌套循环
        if code.count('for ') > 1:
            issues.append({
                "type": "loop",
                "severity": "medium",
                "message": "嵌套循环",
                "suggestion": "考虑使用更高效的算法"
            })

        return issues

    def _check_memory_usage(self, code: str, language: str) -> List[Dict[str, Any]]:
        """检查内存使用"""
        issues = []

        # 检查不必要的列表创建
        if re.search(r'list\(.*range\(', code):
            issues.append({
                "type": "memory",
                "severity": "medium",
                "message": "不必要的列表创建",
                "suggestion": "使用生成器表达式"
            })

        # 检查大型列表操作
        if re.search(r'\.append\(.*\)\s*for', code):
            issues.append({
                "type": "memory",
                "severity": "medium",
                "message": "逐元素列表构建",
                "suggestion": "使用列表推导式"
            })

        return issues

    def _check_io_operations(self, code: str, language: str) -> List[Dict[str, Any]]:
        """检查 I/O 操作"""
        issues = []

        # 检查频繁的文件操作
        if code.count('open(') > 1:
            issues.append({
                "type": "io",
                "severity": "high",
                "message": "频繁的文件操作",
                "suggestion": "减少文件打开/关闭次数"
            })

        return issues

    def _generate_optimization_suggestions(self, issues: List[Dict[str, Any]]) -> List[str]:
        """生成优化建议"""
        suggestions = []

        if any(issue["type"] == "loop" for issue in issues):
            suggestions.append("在循环外计算不变值")
            suggestions.append("使用更高效的循环结构")

        if any(issue["type"] == "memory" for issue in issues):
            suggestions.append("使用生成器代替列表")
            suggestions.append("使用列表推导式提高效率")

        if any(issue["type"] == "io" for issue in issues):
            suggestions.append("批量处理 I/O 操作")
            suggestions.append("使用缓存减少 I/O 访问")

        return suggestions

    def _generate_optimized_code(self, code: str, issues: List[Dict[str, Any]]) -> str:
        """生成优化后的代码"""
        optimized = code

        # 优化循环中的 len() 计算
        if any(issue["message"] == "循环中重复计算 len()" for issue in issues):
            # 简单的替换示例
            optimized = re.sub(
                r'for\s+(\w+)\s+in\s+range\(len\((\w+)\)\)',
                r'n = len(\2)\n    for \1 in range(n)',
                optimized
            )

        return optimized


# 全局实例

_global_registry: Optional[KarpathySkillRegistry] = None


def get_karpathy_registry() -> KarpathySkillRegistry:
    """获取 Karpathy 技能注册表"""
    global _global_registry
    if _global_registry is None:
        _global_registry = KarpathySkillRegistry()
    return _global_registry