#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Intent Code Generator 独立测试
不依赖项目的导入链
"""

import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum

# ============================================================
# 简化的 Intent 类型定义
# ============================================================

class IntentType(Enum):
    CODE_GENERATION = "code_generation"
    CODE_MODIFICATION = "code_modification"
    CODE_QUERY = "code_query"
    UNKNOWN = "unknown"

@dataclass
class Intent:
    intent_type: IntentType = IntentType.UNKNOWN
    action: str = ""
    target: str = ""
    description: str = ""
    tech_stack: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    confidence: float = 0.0

# ============================================================
# 简化的 Intent 解析
# ============================================================

class SimpleIntentParser:
    """简化意图解析"""
    
    ACTION_PATTERNS = [
        (r"(写|生成|创建|开发|实现)", "编写"),
        (r"(修改|更新|改)", "修改"),
        (r"(查|查询|获取)", "查询"),
        (r"(删|删除|移除)", "删除"),
        (r"(测|测试|校验)", "测试"),
    ]
    
    TARGET_PATTERNS = [
        (r"登录", "登录接口"),
        (r"用户", "用户"),
        (r"斐波那契", "斐波那契数列"),
        (r"函数", "函数"),
        (r"类", "类"),
        (r"接口", "接口"),
        (r"测试", "测试用例"),
    ]
    
    TECH_PATTERNS = [
        (r"fastapi", "fastapi"),
        (r"django", "django"),
        (r"flask", "flask"),
        (r"python", "python"),
        (r"javascript|js", "javascript"),
        (r"typescript|ts", "typescript"),
    ]
    
    def parse(self, query: str) -> Intent:
        intent = Intent()
        intent.description = query
        
        # 提取动作
        for pattern, action in self.ACTION_PATTERNS:
            if re.search(pattern, query):
                intent.action = action
                break
        
        # 提取目标
        for pattern, target in self.TARGET_PATTERNS:
            if re.search(pattern, query):
                intent.target = target
                break
        
        if not intent.target:
            intent.target = "代码"
        
        # 提取技术栈
        for pattern, tech in self.TECH_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                intent.tech_stack.append(tech)
        
        # 确定意图类型
        if intent.action in ["编写", "生成", "创建"]:
            intent.intent_type = IntentType.CODE_GENERATION
        elif intent.action in ["修改", "更新"]:
            intent.intent_type = IntentType.CODE_MODIFICATION
        
        intent.confidence = 0.8
        
        return intent

# ============================================================
# 代码生成器
# ============================================================

class GeneratedCode:
    def __init__(self, code: str, language: str, file_path: str, 
                 description: str, template_type: str, confidence: float):
        self.code = code
        self.language = language
        self.file_path = file_path
        self.description = description
        self.template_type = template_type
        self.confidence = confidence
        self.warnings = []
        self.suggestions = []

class GenerationResult:
    def __init__(self, success: bool, generated: Optional[GeneratedCode] = None, 
                 error: str = ""):
        self.success = success
        self.generated = generated
        self.error = error

class IntentCodeGenerator:
    """意图驱动代码生成器"""
    
    def __init__(self):
        self.parser = SimpleIntentParser()
    
    def generate(self, intent_str: str, **kwargs) -> GenerationResult:
        try:
            intent = self.parser.parse(intent_str)
            language = kwargs.get("language", "python")
            
            # 生成代码
            code = self._generate_code(intent, language)
            file_path = self._suggest_path(intent, language)
            
            generated = GeneratedCode(
                code=code,
                language=language,
                file_path=file_path,
                description=intent.description,
                template_type="function",
                confidence=0.85
            )
            
            generated.warnings = ["这是模板生成的代码，请检查逻辑"]
            generated.suggestions = ["可添加类型注解", "可添加错误处理"]
            
            return GenerationResult(success=True, generated=generated)
        except Exception as e:
            return GenerationResult(success=False, error=str(e))
    
    def _generate_code(self, intent: Intent, language: str) -> str:
        target = intent.target or "代码"
        
        templates = {
            "python": {
                "登录接口": '''from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["认证"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    用户登录接口
    
    Args:
        request: 登录请求 (username, password)
    
    Returns:
        LoginResponse: 包含 access_token 的响应
    """
    # TODO: 实现登录逻辑
    # 1. 验证用户凭证
    # 2. 生成 JWT token
    # 3. 返回 token
    pass
''',
                "斐波那契数列": '''def fibonacci(n: int) -> int:
    """
    计算斐波那契数列第 n 项
    
    Args:
        n: 第 n 项 (从 0 开始)
    
    Returns:
        int: 斐波那契数列第 n 项的值
    
    Example:
        >>> fibonacci(10)
        55
    """
    if n <= 0:
        return 0
    if n == 1:
        return 1
    
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b


def fibonacci_sequence(count: int) -> list:
    """
    生成斐波那契数列前 count 项
    
    Args:
        count: 需要生成的项数
    
    Returns:
        list: 斐波那契数列
    """
    return [fibonacci(i) for i in range(count)]
''',
                "函数": '''def {target}({params}):
    """
    {description}
    
    Args:
        {params}: TODO: 添加参数说明
    
    Returns:
        TODO: 添加返回值说明
    """
    # TODO: 实现函数逻辑
    pass
''',
                "类": '''class {target}:
    """
    {description}
    """
    
    def __init__(self):
        """初始化"""
        pass
    
    def create(self, data):
        """创建"""
        pass
    
    def read(self, id):
        """读取"""
        pass
    
    def update(self, id, data):
        """更新"""
        pass
    
    def delete(self, id):
        """删除"""
        pass
''',
                "测试用例": '''import pytest


def test_{target}():
    """
    测试 {description}
    """
    # Given
    pass
    
    # When
    pass
    
    # Then
    assert True
''',
            },
            "javascript": {
                "函数": '''/**
 * {description}
 * @param {params}
 * @returns
 */
function {target}({params}) {{
    // TODO: 实现函数逻辑
    return null;
}}
''',
            }
        }
        
        lang_templates = templates.get(language, templates["python"])
        
        # 查找匹配的模板
        for key, template in lang_templates.items():
            if key in target or key in intent.description:
                # 格式化模板
                params = "data" if "接口" not in target else "request"
                code = template.format(
                    target=target.replace("接口", "").replace("类", "").replace("函数", "Func") or "generated",
                    params=params,
                    description=intent.description,
                )
                return code
        
        # 默认模板
        return f"# TODO: Generate code for: {intent.description}"
    
    def _suggest_path(self, intent: Intent, language: str) -> str:
        target = intent.target.lower()
        
        if "登录" in target or "接口" in target:
            suffix = "_routes.js" if language == "javascript" else "_routes.py"
        elif "类" in target:
            suffix = "_models.js" if language == "javascript" else "_models.py"
        elif "测试" in target:
            suffix = "_test.js" if language == "javascript" else "_test.py"
        else:
            suffix = ".js" if language == "javascript" else ".py"
        
        name = intent.target.replace("接口", "").replace("类", "").replace("函数", "") or "generated"
        return f"{name}{suffix}"

# ============================================================
# 测试
# ============================================================

def run_tests():
    generator = IntentCodeGenerator()
    
    test_cases = [
        "写一个计算斐波那契的函数",
        "帮我写一个用户登录接口",
        "创建一个用户管理类",
        "写一个登录函数的测试用例",
    ]
    
    print("=" * 70)
    print(" Intent Code Generator - 独立测试")
    print("=" * 70)
    
    passed = 0
    total = len(test_cases)
    
    for i, intent_str in enumerate(test_cases, 1):
        print(f"\n[Test {i}/{total}] {intent_str}")
        print("-" * 50)
        
        result = generator.generate(intent_str, language="python")
        
        if result.success:
            g = result.generated
            print(f"  [PASS] Language: {g.language}")
            print(f"  [PASS] Confidence: {g.confidence:.0%}")
            print(f"  [PASS] File: {g.file_path}")
            print(f"\n  Code Preview:")
            for line in g.code.split('\n')[:15]:
                print(f"    {line}")
            if len(g.code.split('\n')) > 15:
                print("    ...")
            passed += 1
        else:
            print(f"  [FAIL] {result.error}")
    
    print("\n" + "=" * 70)
    print(f" RESULT: {passed}/{total} PASSED")
    print("=" * 70)
    
    return passed == total

if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
