# -*- coding: utf-8 -*-
"""
意图引擎核心 - 统一入口
=====================

简化版意图引擎，提供清晰的 API。

Author: LivingTreeAI Team
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional
import re


class IntentType(Enum):
    """意图类型"""
    CODE_GENERATION = "code_generation"        # 生成代码
    CODE_COMPLETION = "code_completion"        # 代码补全
    CODE_REVIEW = "code_review"                # 代码审查
    BUG_FIX = "bug_fix"                        # Bug修复
    REFACTORING = "refactoring"                # 重构
    QUERY = "query"                            # 查询
    EXECUTION = "execution"                    # 执行
    EXPLANATION = "explanation"                # 解释
    CREATION = "creation"                      # 创建
    MODIFICATION = "modification"              # 修改
    DELETION = "deletion"                      # 删除
    SEARCH = "search"                          # 搜索
    ANALYSIS = "analysis"                      # 分析
    UNKNOWN = "unknown"                        # 未知


class IntentPriority(Enum):
    """优先级"""
    P0_CRITICAL = 0  # 紧急
    P1_HIGH = 1      # 高
    P2_MEDIUM = 2    # 中
    P3_LOW = 3       # 低


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


class IntentParser:
    """意图解析器 - 将自然语言解析为结构化意图"""
    
    # 意图关键词映射
    INTENT_KEYWORDS = {
        IntentType.CODE_GENERATION: [
            '生成', '创建', '编写', '写', '实现', '写个',
            'build', 'create', 'generate', 'write', 'implement'
        ],
        IntentType.CODE_COMPLETION: [
            '补全', '完成', '填充', '完善',
            'complete', 'fill', 'autocomplete'
        ],
        IntentType.CODE_REVIEW: [
            '审查', 'review', '检查', 'lint', '质量',
            'check', '审计'
        ],
        IntentType.BUG_FIX: [
            '修复', 'fix', 'bug', '错误', 'error', '问题',
            '报错', '异常', '修复一下'
        ],
        IntentType.REFACTORING: [
            '重构', 'refactor', '重写', '优化', '优化一下',
            'optimize', '重构一下'
        ],
        IntentType.QUERY: [
            '查询', 'query', 'find', '找',
            'locate', 'grep'
        ],
        IntentType.EXECUTION: [
            '执行', 'run', '运行', 'execute', 'start', '启动',
            '跑一下', '运行一下'
        ],
        IntentType.EXPLANATION: [
            '解释', 'explain', '说明', '什么是', '为什么',
            'how', 'why', 'what'
        ],
        IntentType.CREATION: [
            '新建', 'new', '新增', 'add', '创建',
            '新建一个'
        ],
        IntentType.MODIFICATION: [
            '修改', 'edit', 'change', '更新', 'update',
            '改动', '调整'
        ],
        IntentType.DELETION: [
            '删除', 'delete', 'remove', '清除', '删掉'
        ],
        IntentType.SEARCH: [
            '搜索', 'search', '查找', '找',
            'locate'
        ],
        IntentType.ANALYSIS: [
            '分析', 'analyze', '分析一下', '评估',
            'evaluate', '看看'
        ],
    }
    
    # 动作词映射
    ACTION_PATTERNS = {
        '写': '编写',
        '生成': '生成',
        '创建': '创建',
        '实现': '实现',
        '修复': '修复',
        '检查': '检查',
        '优化': '优化',
        '删除': '删除',
        '查找': '查找',
        '运行': '运行',
        '打开': '打开',
        '关闭': '关闭',
        '帮我': '',
        '请': '',
        '能不能': '',
        '帮我': '',
    }
    
    # 技术栈关键词
    TECH_KEYWORDS = {
        'python': ['python', 'py', 'python3', 'django', 'flask', 'fastapi'],
        'javascript': ['javascript', 'js', 'nodejs', 'node'],
        'typescript': ['typescript', 'ts'],
        'java': ['java', 'spring', 'springboot'],
        'go': ['go', 'golang'],
        'rust': ['rust', 'rs'],
        'cpp': ['c++', 'cpp', 'c/c++'],
        'react': ['react'],
        'vue': ['vue', 'vuejs'],
        'fastapi': ['fastapi'],
        'django': ['django'],
        'flask': ['flask'],
        'mysql': ['mysql'],
        'postgresql': ['postgresql', 'postgres'],
        'mongodb': ['mongodb', 'mongo'],
        'redis': ['redis'],
        'docker': ['docker', 'container'],
        'git': ['git', 'github', 'gitlab'],
    }
    
    def parse(self, text: str) -> Intent:
        """
        解析自然语言为意图
        
        Args:
            text: 用户输入的自然语言
            
        Returns:
            Intent: 结构化意图对象
        """
        text_lower = text.lower().strip()
        
        # 1. 识别意图类型
        intent_type, confidence = self._classify_intent(text_lower)
        
        # 2. 提取动作
        action = self._extract_action(text)
        
        # 3. 提取目标
        target = self._extract_target(text)
        
        # 4. 检测技术栈
        tech_stack = self._detect_tech_stack(text_lower)
        
        # 5. 提取约束
        constraints = self._extract_constraints(text_lower)
        
        return Intent(
            raw_input=text,
            intent_type=intent_type,
            action=action,
            target=target,
            confidence=confidence,
            tech_stack=tech_stack,
            parameters={},
            constraints=constraints,
        )
    
    def _classify_intent(self, text: str) -> tuple[IntentType, float]:
        """识别意图类型"""
        scores = {}
        
        for intent_type, keywords in self.INTENT_KEYWORDS.items():
            score = sum(1 for keyword in keywords if keyword.lower() in text)
            if score > 0:
                scores[intent_type] = score / len(keywords)
        
        if not scores:
            return IntentType.UNKNOWN, 0.0
        
        # 返回最高分
        best = max(scores.items(), key=lambda x: x[1])
        return best[0], min(best[1], 1.0)
    
    def _extract_action(self, text: str) -> str:
        """提取动作"""
        for pattern, action in self.ACTION_PATTERNS.items():
            if pattern in text:
                return action
        return ""
    
    def _extract_target(self, text: str) -> str:
        """提取目标"""
        # 去掉动作词后的内容作为目标
        target = text
        for pattern in self.ACTION_PATTERNS.keys():
            if pattern in target:
                target = target.replace(pattern, '').strip()
        
        # 清理常见前缀
        prefixes = ['帮我', '请', '能不能', '麻烦', '一下', '一个']
        for prefix in prefixes:
            if target.startswith(prefix):
                target = target[len(prefix):].strip()
        
        # 提取文件名、函数名等
        patterns = [
            r'([\w./]+\.py)',     # Python文件
            r'([\w./]+\.js)',      # JS文件
            r'([\w./]+\.ts)',      # TS文件
            r'([\w./]+\.java)',    # Java文件
            r'def\s+(\w+)',        # 函数名
            r'class\s+(\w+)',      # 类名
            r'函数\s*(\w+)',       # 中文函数
            r'接口\s*(\w+)',       # 接口名
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        
        return target[:50] if target else "未知目标"
    
    def _detect_tech_stack(self, text: str) -> List[str]:
        """检测技术栈"""
        detected = []
        for tech, keywords in self.TECH_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                detected.append(tech)
        return detected
    
    def _extract_constraints(self, text: str) -> List[str]:
        """提取约束"""
        constraints = []
        
        if any(kw in text for kw in ['快', '快速', 'fast', 'quick', '高性能']):
            constraints.append('performance:high')
        if any(kw in text for kw in ['安全', 'secure', '安全地']):
            constraints.append('security:required')
        if any(kw in text for kw in ['异步', 'async', '并发']):
            constraints.append('async:required')
        if any(kw in text for kw in ['测试', 'test', '单元测试']):
            constraints.append('test:required')
            
        return constraints


class IntentEngine:
    """
    意图引擎 - 统一入口
    
    整合意图解析，提供简洁 API。
    
    使用示例:
        engine = IntentEngine()
        intent = engine.parse("帮我写一个用户登录函数，用Python")
        print(intent)
    """
    
    def __init__(self):
        self.parser = IntentParser()
    
    def parse(self, query: str) -> Intent:
        """解析用户查询"""
        return self.parser.parse(query)
    
    def parse_batch(self, queries: List[str]) -> List[Intent]:
        """批量解析"""
        return [self.parse(q) for q in queries]


# 导出
__all__ = ['IntentEngine', 'IntentParser', 'Intent', 'IntentType', 'IntentPriority']
