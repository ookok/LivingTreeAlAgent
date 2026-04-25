# -*- coding: utf-8 -*-
"""
Intent Code Generator - 意图驱动代码生成器
==========================================

核心理念：从"写代码"到"说意图"

传统编程：
    程序员 → 写代码 → 调试 → 修改 → ...
    
意图驱动编程：
    程序员 → 说意图 → AI 生成代码 → 预览 → 应用 → ...

功能：
1. 意图解析：利用 IntentEngine 理解用户想要什么
2. 代码生成：基于意图生成高质量代码
3. 模板系统：可扩展的代码模板
4. 预览+应用：安全的两阶段确认

Author: LivingTreeAI
"""

from __future__ import annotations

import os
import re
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

# 意图引擎导入
try:
    from core.intent_engine import IntentEngine
    from core.intent_engine.intent_types import Intent, IntentType
except ImportError:
    IntentEngine = None
    Intent = None
    IntentType = None


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


@dataclass
class GenerationRequest:
    """生成请求"""
    intent: str  # 用户意图描述
    context: str = ""  # 上下文（现有代码）
    language: str = "python"  # 目标语言
    framework: str = ""  # 框架
    output_path: str = ""  # 输出路径


@dataclass
class GenerationResult:
    """生成结果"""
    success: bool
    generated: Optional[GeneratedCode] = None
    error: str = ""
    alternatives: List[GeneratedCode] = field(default_factory=list)


class IntentCodeGenerator:
    """
    意图驱动代码生成器
    
    使用方式：
        generator = IntentCodeGenerator()
        
        # 方式1：直接生成
        result = generator.generate("写一个用户登录函数")
        
        # 方式2：使用 IntentEngine
        engine = IntentEngine()
        intent = engine.parse("用 FastAPI 写一个用户登录接口")
        result = generator.generate_from_intent(intent)
        
        # 预览和应用
        if result.success:
            preview = generator.preview(result.generated)
            generator.apply(result.generated)
    """

    # 内置模板
    TEMPLATES = {
        "python": {
            "function": '''def {name}({params}):
    """
    {description}
    
    Args:
{args_doc}
    
    Returns:
        {return_type}: {return_desc}
    """
    {body}
''',
            "class": '''class {name}:
    """
    {description}
    """
    
    def __init__(self{init_params}):
        """初始化"""
{init_body}
    
{Methods}
''',
            "api_endpoint": '''from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/{prefix}", tags=["{tag}"])


class {RequestModel}(BaseModel):
    """请求模型"""
{request_fields}


class {ResponseModel}(BaseModel):
    """响应模型"""
{response_fields}


@router.{method}("/{endpoint}", response_model={ResponseModel})
async def {endpoint}({request_param}):
    """
    {description}
    """
    try:
        # TODO: 实现业务逻辑
        pass
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
''',
            "test": '''import pytest
from {module} import {target}


class Test{TestClass}:
    """{test_description}"""
    
    def test_{test_name}(self):
        """测试 {test_name}"""
        # Given
        {given}
        
        # When
        result = {action}
        
        # Then
        {assertion}
''',
        },
        "javascript": {
            "function": '''/**
 * {description}
 * @param {param_types}
 * @returns {return_type}
 */
function {name}({params}) {{
    {body}
}}
''',
            "class": '''class {name} {{
    /**
     * {description}
     */
    constructor({constructor_params}) {{
{constructor_body}
    }}
    
{Methods}
}}
''',
            "api_endpoint": '''const express = require('express');
const router = express.Router();

// {description}
router.{method}('/{endpoint}', async (req, res) => {{
    try {{
        const {{ {request_params} }} = req.body;
        
        // TODO: 实现业务逻辑
        res.json({{ success: true }});
    }} catch (error) {{
        res.status(500).json({{ error: error.message }});
    }}
}});

module.exports = router;
''',
        },
    }

    # 意图 → 模板映射
    INTENT_TEMPLATE_MAP = {
        "登录": ("python", "api_endpoint"),
        "登录接口": ("python", "api_endpoint"),
        "登录函数": ("python", "function"),
        "用户": ("python", "class"),
        "用户管理": ("python", "class"),
        "接口": ("python", "api_endpoint"),
        "API": ("python", "api_endpoint"),
        "测试": ("python", "test"),
        "测试用例": ("python", "test"),
        "模型": ("python", "db_model"),
        "数据库": ("python", "db_model"),
    }

    def __init__(self, intent_engine: Optional[IntentEngine] = None):
        """
        初始化代码生成器
        
        Args:
            intent_engine: 可选的 IntentEngine 实例
        """
        self.intent_engine = intent_engine or IntentEngine()
        self.generation_history: List[GenerationResult] = []

    def generate(self, intent: str, **kwargs) -> GenerationResult:
        """
        从自然语言意图生成代码
        
        Args:
            intent: 自然语言描述
            **kwargs: 额外参数 (language, framework, context, output_path)
            
        Returns:
            GenerationResult: 生成结果
        """
        try:
            # 1. 解析意图
            parsed_intent = self.intent_engine.parse(intent)
            
            # 2. 确定语言和模板
            language = kwargs.get("language", self._detect_language(parsed_intent))
            template_type = self._detect_template(parsed_intent, language)
            
            # 3. 生成代码
            generated = self._generate_from_template(
                intent=parsed_intent,
                language=language,
                template_type=template_type,
                context=kwargs.get("context", ""),
                framework=kwargs.get("framework", ""),
            )
            
            # 4. 记录历史
            result = GenerationResult(success=True, generated=generated)
            self.generation_history.append(result)
            
            return result
            
        except Exception as e:
            return GenerationResult(success=False, error=str(e))

    def generate_from_intent(
        self,
        intent: Intent,
        language: str = "python",
        context: str = "",
    ) -> GenerationResult:
        """
        从已解析的 Intent 对象生成代码
        
        Args:
            intent: IntentEngine 解析的结果
            language: 目标语言
            context: 上下文代码
            
        Returns:
            GenerationResult: 生成结果
        """
        try:
            template_type = self._detect_template(intent, language)
            
            generated = self._generate_from_template(
                intent=intent,
                language=language,
                template_type=template_type,
                context=context,
                framework="",
            )
            
            result = GenerationResult(success=True, generated=generated)
            self.generation_history.append(result)
            
            return result
            
        except Exception as e:
            return GenerationResult(success=False, error=str(e))

    def _detect_language(self, intent: Intent) -> str:
        """检测目标语言"""
        if intent.tech_stack:
            tech = intent.tech_stack[0].lower()
            lang_map = {
                "python": "python",
                "javascript": "javascript",
                "js": "javascript",
                "typescript": "typescript",
                "ts": "typescript",
                "java": "java",
                "go": "go",
                "rust": "rust",
                "cpp": "cpp",
            }
            return lang_map.get(tech, "python")
        return "python"

    def _detect_template(self, intent: Intent, language: str) -> CodeTemplate:
        """检测模板类型"""
        target = intent.target.lower() if intent.target else ""
        action = intent.action.lower() if intent.action else ""
        
        # 基于关键词匹配
        for keyword, (lang, template) in self.INTENT_TEMPLATE_MAP.items():
            if lang == language and keyword in target:
                return CodeTemplate(template)
        
        # 基于意图类型
        if intent.intent_type == IntentType.CODE_GENERATION if IntentType else None:
            if "test" in target or "测试" in target:
                return CodeTemplate.TEST
            if "api" in target or "接口" in target:
                return CodeTemplate.API_ENDPOINT
            if "class" in target or "类" in target:
                return CodeTemplate.CLASS
        
        return CodeTemplate.FUNCTION

    def _generate_from_template(
        self,
        intent: Intent,
        language: str,
        template_type: CodeTemplate,
        context: str,
        framework: str,
    ) -> GeneratedCode:
        """从模板生成代码"""
        templates = self.TEMPLATES.get(language, self.TEMPLATES["python"])
        
        if template_type.value not in templates:
            template_type = CodeTemplate.FUNCTION
        
        template = templates[template_type.value]
        
        # 填充模板
        name = self._extract_name(intent.target)
        params = self._extract_params(intent)
        description = intent.description or f"{intent.action} {intent.target}"
        
        code = template.format(
            name=name,
            params=params,
            description=description,
            args_doc=self._generate_args_doc(intent),
            return_type="dict",
            return_desc="返回结果",
            body="    pass",
            prefix=name.replace("_", "-"),
            tag=name.replace("_", "-"),
            method="post",
            endpoint="endpoint",
            RequestModel=f"{name.title()}Request",
            ResponseModel=f"{name.title()}Response",
            request_param="request: RequestModel",
            request_fields="    pass",
            response_fields="    pass",
            module="module",
            target="target",
            TestClass=name.title(),
            test_description=description,
            test_name="basic",
            given="# given",
            action="# action",
            assertion="assert result is not None",
            init_params="",
            init_body="    pass",
            Methods="    pass",
            constructor_params="",
            constructor_body="",
            param_types="",
            return_type="*",
        )
        
        return GeneratedCode(
            code=code,
            language=language,
            file_path=self._suggest_file_path(name, template_type, language),
            description=description,
            template_type=template_type,
            confidence=0.85,
            warnings=self._generate_warnings(intent, language),
            suggestions=self._generate_suggestions(intent, language),
        )

    def _extract_name(self, target: str) -> str:
        """提取名称"""
        if not target:
            return "generated"
        
        # 移除常见前缀
        target = re.sub(r"^(写|创建|生成|一个|帮我)\s*", "", target)
        
        # 转驼峰
        words = re.findall(r"[\u4e00-\u9fa5a-zA-Z]+", target)
        if words:
            return words[0].lower()
        
        return "generated"

    def _extract_params(self, intent: Intent) -> str:
        """提取参数"""
        if intent.constraints:
            params = []
            for c in intent.constraints[:3]:
                param_name = re.sub(r"[^a-zA-Z]", "_", c.lower())
                params.append(param_name)
            return ", ".join(params) if params else ""
        
        # 默认参数
        return "self" if intent.target and "类" in intent.target else ""

    def _generate_args_doc(self, intent: Intent) -> str:
        """生成参数文档"""
        if not intent.constraints:
            return "        pass"
        
        doc_lines = []
        for c in intent.constraints[:5]:
            param_name = re.sub(r"[^a-zA-Z]", "_", c.lower())
            doc_lines.append(f"        {param_name}: Any")
        
        return "\n".join(doc_lines) if doc_lines else "        pass"

    def _suggest_file_path(self, name: str, template_type: CodeTemplate, language: str) -> str:
        """建议文件路径"""
        suffix_map = {
            CodeTemplate.FUNCTION: "_utils.py",
            CodeTemplate.CLASS: "_models.py",
            CodeTemplate.API_ENDPOINT: "_routes.py",
            CodeTemplate.TEST: "_test.py",
            CodeTemplate.DB_MODEL: "_models.py",
        }
        suffix = suffix_map.get(template_type, ".py")
        
        # 添加语言特定后缀
        if language == "javascript":
            suffix = suffix.replace(".py", ".js")
        elif language == "typescript":
            suffix = suffix.replace(".py", ".ts")
        
        return f"{name}{suffix}"

    def _generate_warnings(self, intent: Intent, language: str) -> List[str]:
        """生成警告"""
        warnings = []
        
        if not intent.tech_stack:
            warnings.append("未检测到技术栈，可能需要手动调整")
        
        if intent.intent_type and "modify" in str(intent.intent_type).lower():
            warnings.append("检测到修改意图，请确保有版本控制")
        
        return warnings

    def _generate_suggestions(self, intent: Intent, language: str) -> List[str]:
        """生成建议"""
        suggestions = []
        
        suggestions.append("生成后请检查代码逻辑是否满足需求")
        
        if language == "python":
            suggestions.append("可使用 type hints 增强类型安全")
            suggestions.append("可添加 docstring 说明函数用途")
        elif language == "javascript":
            suggestions.append("建议添加 JSDoc 注释")
            suggestions.append("考虑使用 TypeScript 增强类型安全")
        
        return suggestions

    def preview(self, generated: GeneratedCode) -> str:
        """
        预览生成的代码
        
        Args:
            generated: 生成的代码对象
            
        Returns:
            str: 格式化的预览
        """
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
        """
        应用生成的代码到文件
        
        Args:
            generated: 生成的代码对象
            overwrite: 是否覆盖已存在的文件
            
        Returns:
            bool: 是否成功
        """
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
    generator = IntentCodeGenerator()
    return generator.generate(intent, **kwargs)


# 测试
if __name__ == "__main__":
    # 测试代码生成
    generator = IntentCodeGenerator()
    
    # 测试1: 简单函数
    print("\n[Test 1] 生成简单函数...")
    result = generator.generate("写一个计算斐波那契的函数")
    if result.success:
        print(generator.preview(result.generated))
    
    # 测试2: API 接口
    print("\n[Test 2] 生成 API 接口...")
    result = generator.generate("帮我写一个用户登录接口，用 FastAPI")
    if result.success:
        print(generator.preview(result.generated))
    
    # 测试3: 测试用例
    print("\n[Test 3] 生成测试用例...")
    result = generator.generate("写一个登录函数的测试")
    if result.success:
        print(generator.preview(result.generated))
