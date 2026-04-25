# -*- coding: utf-8 -*-
"""
AI 意图解析器 - 使用真实 AI 服务
================================

调用 Ollama 服务来理解用户意图。

Author: LivingTreeAI Team
"""

from __future__ import annotations

import json
import httpx
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum


class IntentType(Enum):
    """意图类型"""
    CODE_GENERATION = "code_generation"
    CODE_COMPLETION = "code_completion"
    CODE_REVIEW = "code_review"
    BUG_FIX = "bug_fix"
    REFACTORING = "refactoring"
    QUERY = "query"
    EXECUTION = "execution"
    EXPLANATION = "explanation"
    CREATION = "creation"
    MODIFICATION = "modification"
    DELETION = "deletion"
    SEARCH = "search"
    ANALYSIS = "analysis"
    UNKNOWN = "unknown"


@dataclass
class Intent:
    """结构化意图"""
    raw_input: str
    intent_type: IntentType = IntentType.UNKNOWN
    action: str = ""
    target: str = ""
    confidence: float = 0.0
    tech_stack: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    constraints: List[str] = field(default_factory=list)
    reasoning: str = ""  # AI 推理过程
    
    def __str__(self) -> str:
        tech = ", ".join(self.tech_stack) if self.tech_stack else "无"
        return (
            f"Intent("
            f"类型={self.intent_type.value}, "
            f"动作={self.action or '无'}, "
            f"目标={self.target or '无'}, "
            f"技术栈=[{tech}], "
            f"置信度={self.confidence:.2f})"
        )


class AIIntentParser:
    """
    AI 意图解析器
    
    使用真实 AI 服务解析用户意图。
    
    使用示例:
        parser = AIIntentParser("http://www.mogoo.com.cn:8899/v1")
        intent = parser.parse("帮我写一个用户登录函数")
    """
    
    # 意图类型列表（用于 JSON 输出）
    INTENT_TYPES = [it.value for it in IntentType]
    
    def __init__(self, base_url: str = "http://www.mogoo.com.cn:8899/v1", model: str = "deepseek-r1:14b"):
        """
        初始化 AI 意图解析器
        
        Args:
            base_url: Ollama API 地址
            model: 使用的模型
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = httpx.Timeout(60.0, connect=10.0)
    
    def parse(self, text: str) -> Intent:
        """
        使用 AI 解析用户意图
        
        Args:
            text: 用户输入
            
        Returns:
            Intent: 结构化意图
        """
        # 构建提示词
        prompt = self._build_prompt(text)
        
        try:
            # 调用 AI 服务
            response = self._call_ai(prompt)
            
            # 解析响应
            intent = self._parse_response(text, response)
            return intent
            
        except Exception as e:
            print(f"[AIIntentParser] Error: {e}")
            # 降级到简单解析
            return self._fallback_parse(text)
    
    def _build_prompt(self, text: str) -> str:
        """构建提示词"""
        return f"""你是一个专业的代码助手。请分析用户的输入，识别其意图。

用户输入: {text}

请以 JSON 格式返回分析结果：
{{
    "intent_type": "意图类型，可选值：{', '.join(self.INTENT_TYPES)}",
    "action": "主要动作（如：写、修复、删除、查找等）",
    "target": "目标对象（如：用户登录函数、空指针错误等）",
    "tech_stack": ["检测到的技术栈列表，如 python, fastapi 等，空列表表示未检测到"],
    "constraints": ["约束条件，如 performance:high, security:required 等，空列表表示无"],
    "confidence": 0.0-1.0 的置信度,
    "reasoning": "你的分析推理过程"
}}

只返回 JSON，不要有其他内容。"""
    
    def _call_ai(self, prompt: str) -> str:
        """调用 AI 服务"""
        messages = [
            {"role": "user", "content": prompt}
        ]
        
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "temperature": 0.1,  # 低温度，更确定性的输出
        }
        
        with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
            response = client.post("/chat/completions", json=payload)
            response.raise_for_status()
            
            data = response.json()
            
            # 提取回复内容 (支持带 reasoning 的格式)
            if "choices" in data and len(data["choices"]) > 0:
                msg = data["choices"][0]["message"]
                # DeepSeek 格式可能包含 reasoning
                if "reasoning" in msg:
                    return msg["reasoning"] + "\n\n" + msg.get("content", "")
                return msg.get("content", "")
            
            raise ValueError(f"Invalid response: {data}")
    
    def _parse_response(self, text: str, response: str) -> Intent:
        """解析 AI 响应"""
        # 尝试提取 JSON
        try:
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]
            
            json_str = json_str.strip()
            data = json.loads(json_str)
            
            # 映射意图类型
            intent_type_str = data.get("intent_type", "unknown")
            intent_type = IntentType.UNKNOWN
            for it in IntentType:
                if it.value == intent_type_str.lower() or it.value == intent_type_str:
                    intent_type = it
                    break
            
            return Intent(
                raw_input=text,
                intent_type=intent_type,
                action=data.get("action", ""),
                target=data.get("target", ""),
                confidence=float(data.get("confidence", 0.5)),
                tech_stack=data.get("tech_stack", []),
                constraints=data.get("constraints", []),
                parameters={},
                reasoning=data.get("reasoning", ""),
            )
            
        except (json.JSONDecodeError, KeyError):
            # 无法解析 JSON，从自然语言中提取
            return self._parse_natural_language(text, response)
    
    def _parse_natural_language(self, text: str, response: str) -> Intent:
        """从自然语言响应中提取意图"""
        response_lower = response.lower()
        
        # 提取意图类型
        intent_type = IntentType.UNKNOWN
        for it in IntentType:
            if it.value in response_lower:
                intent_type = it
                break
        
        # 提取动作
        action = ""
        for kw in ['写', '生成', '创建', '修复', '删除', '查找', '搜索', '执行', '运行', '解释', '优化', '重构']:
            if kw in response:
                action = kw
                break
        
        # 提取目标
        target = ""
        for pattern in ['目标.*?["\'](.+?)["\']', 'target.*?["\'](.+?)["\']', 
                       '是(.+?)[，。]', '对象(.+?)[，.]']:
            import re
            match = re.search(pattern, response)
            if match:
                target = match.group(1)[:50]
                break
        if not target:
            target = text[:50]
        
        # 提取技术栈
        tech_stack = []
        techs = ['python', 'javascript', 'java', 'go', 'rust', 'c++', 'c#',
                 'fastapi', 'django', 'flask', 'react', 'vue', 'angular',
                 'mysql', 'postgresql', 'mongodb', 'redis', 'docker', 'git']
        for tech in techs:
            if tech in response_lower:
                tech_stack.append(tech)
        
        # 提取约束
        constraints = []
        if '性能' in response or 'performance' in response_lower:
            constraints.append('performance:high')
        if '安全' in response or 'security' in response_lower:
            constraints.append('security:required')
        if '异常' in response or '错误处理' in response:
            constraints.append('error_handling:required')
        
        return Intent(
            raw_input=text,
            intent_type=intent_type,
            action=action,
            target=target,
            confidence=0.7,  # 自然语言解析置信度稍低
            tech_stack=tech_stack,
            constraints=constraints,
            parameters={},
            reasoning=response[:200],
        )
    
    def _fallback_parse(self, text: str) -> Intent:
        """降级解析（规则匹配）"""
        text_lower = text.lower()
        
        # 简单规则匹配
        keywords_map = {
            'code_generation': ['写', '生成', '创建', '编写', '实现', 'build', 'create', 'generate'],
            'bug_fix': ['修复', 'fix', 'bug', '错误', 'error', '问题', '报错'],
            'code_review': ['审查', 'review', '检查', 'lint', 'check'],
            'refactoring': ['重构', 'refactor', '重写', '优化'],
            'query': ['查询', 'query', 'find', '找'],
            'execution': ['执行', 'run', '运行', 'execute', 'start'],
            'explanation': ['解释', 'explain', '说明', '什么是', 'why', 'how'],
            'creation': ['新建', 'new', '新增', 'add', '创建'],
            'modification': ['修改', 'edit', 'change', '更新', 'update'],
            'deletion': ['删除', 'delete', 'remove', '清除'],
            'search': ['搜索', 'search', '查找'],
            'analysis': ['分析', 'analyze', '评估', 'evaluate'],
        }
        
        for intent_type_str, keywords in keywords_map.items():
            for kw in keywords:
                if kw in text_lower:
                    intent_type = IntentType.UNKNOWN
                    for it in IntentType:
                        if it.value == intent_type_str:
                            intent_type = it
                            break
                    return Intent(
                        raw_input=text,
                        intent_type=intent_type,
                        confidence=0.3,
                        reasoning="降级解析",
                    )
        
        return Intent(
            raw_input=text,
            intent_type=IntentType.UNKNOWN,
            confidence=0.0,
            reasoning="无法识别",
        )


class AIIntentEngine:
    """
    AI 意图引擎
    
    使用 AI 服务解析用户意图。
    
    使用示例:
        engine = AIIntentEngine("http://www.mogoo.com.cn:8899/v1")
        intent = engine.parse("帮我写一个用户登录函数")
        print(intent)
    """
    
    def __init__(self, base_url: str = "http://www.mogoo.com.cn:8899/v1", model: str = "deepseek-r1:14b"):
        self.parser = AIIntentParser(base_url, model)
        print(f"[AIIntentEngine] Initialized with {base_url}, model={model}")
    
    def parse(self, query: str) -> Intent:
        """解析用户查询"""
        return self.parser.parse(query)
    
    def parse_batch(self, queries: List[str]) -> List[Intent]:
        """批量解析"""
        return [self.parse(q) for q in queries]


# 导出
__all__ = ['AIIntentEngine', 'AIIntentParser', 'Intent', 'IntentType']
