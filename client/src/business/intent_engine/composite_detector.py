# -*- coding: utf-8 -*-
"""
Composite Detector - 复合意图检测器
===================================

检测用户查询中的复合意图，并分解为多个子意图。
from __future__ import annotations
"""


import re
from typing import List, Tuple, Optional
from .intent_types import Intent, IntentType
from .intent_parser import IntentParser
from .tech_stack_detector import TechStackDetector
from .constraint_extractor import ConstraintExtractor


class CompositeDetector:
    """
    复合意图检测器
    
    检测复合查询（如"帮我写一个登录接口并写测试"）
    并分解为多个独立子意图。
    """
    
    # 复合模式：连接词
    CONNECTORS = [
        r"和", r"并且", r"而且", r"同时",
        r"and", r"&&", r"&", r"同时",
        r"然后", r"接着", r"再",
        r"以及", r"加", r"还要",
        r"或者", r"或", r"或则",  # 或关系
    ]
    
    # 并列关系模式
    PARALLEL_PATTERNS = [
        # "写...并写..."
        r"(.+?)\s*(和|并且|而且|and|&|以及)\s*(.+?)\s*(和|并且|而且|and|&|以及)\s*(.+)",
        # "写...和写..."
        r"(.+?)\s*(和|并且|and|&|以及)\s*(.+)",
    ]
    
    # 顺序关系模式
    SEQUENCE_PATTERNS = [
        r"(.+?)\s*(然后|接着|之后|再|after)\s*(.+)",
        r"(.+?)\s*(先|首先|第一步)\s*(.+)",
    ]
    
    # 已知的复合任务组合
    KNOWN_COMPOSITES = {
        # 代码 + 测试
        frozenset(["写", "测试"]): ("代码生成", "测试生成"),
        frozenset(["实现", "测试"]): ("代码实现", "测试生成"),
        frozenset(["写接口", "写文档"]): ("API设计", "文档生成"),
        
        # 代码 + 部署
        frozenset(["写", "部署"]): ("代码生成", "部署配置"),
        frozenset(["实现", "上线"]): ("代码实现", "部署上线"),
        
        # 分析 + 修复
        frozenset(["分析", "修复"]): ("问题分析", "问题修复"),
        frozenset(["排查", "解决"]): ("问题排查", "问题解决"),
        
        # 理解 + 优化
        frozenset(["理解", "优化"]): ("代码理解", "代码优化"),
        frozenset(["分析", "改进"]): ("代码分析", "代码改进"),
    }
    
    def __init__(self):
        self.parser = IntentParser()
        self.tech_detector = TechStackDetector()
        self.constraint_extractor = ConstraintExtractor()
    
    def detect(self, query: str) -> Tuple[bool, List[Intent]]:
        """
        检测是否为复合意图
        
        Args:
            query: 用户查询
            
        Returns:
            (是否复合意图, 子意图列表)
        """
        # 简单检查：是否包含连接词
        has_connector = any(re.search(conn, query) for conn in self.CONNECTORS)
        
        if not has_connector:
            return False, []
        
        # 尝试分解
        sub_queries = self._split_query(query)
        
        if len(sub_queries) < 2:
            return False, []
        
        # 解析每个子查询
        sub_intents = []
        for sq in sub_queries:
            intent = self.parser.parse(sq)
            # 继承父意图的技术栈和约束
            tech_stack, _ = self.tech_detector.detect(query)
            intent.tech_stack = tech_stack
            constraints, _ = self.constraint_extractor.extract(query)
            intent.constraints = constraints
            sub_intents.append(intent)
        
        # 标记为复合意图
        is_composite = len(sub_intents) >= 2
        
        return is_composite, sub_intents
    
    def _split_query(self, query: str) -> List[str]:
        """分解查询"""
        parts = []
        
        # 按连接词分割
        split_pattern = r'[和并且而且以及&以及,，、]'
        parts = re.split(split_pattern, query)
        
        # 清理每个部分
        cleaned = []
        for p in parts:
            p = p.strip()
            if p and len(p) > 2:
                cleaned.append(p)
        
        return cleaned
    
    def detect_sequential(self, query: str) -> Tuple[bool, List[str]]:
        """
        检测顺序意图
        
        例如："先写登录接口，然后写测试"
        """
        for pattern in self.SEQUENCE_PATTERNS:
            match = re.search(pattern, query)
            if match:
                groups = match.groups()
                steps = []
                for g in groups:
                    if g and len(g.strip()) > 2:
                        steps.append(g.strip())
                if len(steps) >= 2:
                    return True, steps
        
        return False, []
    
    def is_sequential(self, query: str) -> bool:
        """判断是否为顺序任务"""
        sequential_markers = [
            r"先", r"首先", r"第一步",
            r"然后", r"接着", r"之后",
            r"再", r"最后",
            r"before", r"after", r"then",
        ]
        return any(re.search(m, query) for m in sequential_markers)
    
    def get_sequence_order(self, query: str) -> List[dict]:
        """
        获取顺序任务的执行顺序
        
        Returns:
            [{"step": 1, "action": "写登录接口"}, ...]
        """
        if not self.is_sequential(query):
            return []
        
        # 提取顺序词
        order_markers = {
            "先": 0, "首先": 0, "第一步": 0,
            "然后": 1, "接着": 1,
            "再": 2, "最后": 3,
        }
        
        sequence = []
        for marker, order in order_markers.items():
            if marker in query:
                # 提取标记后的内容
                idx = query.index(marker)
                remaining = query[idx + len(marker):].strip()
                # 找到下一个标记或句号
                next_marker_idx = len(remaining)
                for next_m in ["然后", "接着", "最后", "再", "。", "，"]:
                    if next_m in remaining:
                        next_marker_idx = min(next_marker_idx, remaining.index(next_m))
                action = remaining[:next_marker_idx].strip()
                if action:
                    sequence.append({"step": order, "action": action, "marker": marker})
        
        # 按顺序排序
        sequence.sort(key=lambda x: x["step"])
        return sequence
