# -*- coding: utf-8 -*-
"""
Constraint Extractor - 约束条件提取器
=====================================

从用户查询中提取约束条件。
from __future__ import annotations
"""


import re
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
from .intent_types import IntentConstraint


@dataclass
class ConstraintRule:
    """约束提取规则"""
    constraint_type: str
    name: str
    patterns: List[str]
    value_extractors: List[str]
    required_default: bool = False


class ConstraintExtractor:
    """约束条件提取器"""
    
    def __init__(self):
        self.rules = self._build_rules()
    
    def _build_rules(self) -> List[ConstraintRule]:
        return [
            # 性能约束
            ConstraintRule("performance", "响应时间", 
                [r"响应时间", r"延迟", r"ms", r"毫秒"],
                [r"(\d+)\s*ms", r"(\d+)\s*毫秒"]),
            ConstraintRule("performance", "吞吐量",
                [r"qps", r"tps", r"并发"],
                [r"(\d+)\s*qps", r"并发(\d+)"]),
            ConstraintRule("performance", "内存限制",
                [r"内存", r"memory"],
                [r"(\d+)\s*[mg]b"]),
            
            # 安全约束
            ConstraintRule("security", "认证方式",
                [r"认证", r"auth", r"token"],
                [r"(jwt|oauth|basic|bearer)"]),
            ConstraintRule("security", "加密要求",
                [r"加密", r"ssl", r"tls", r"https"],
                [r"(ssl|tls|https|aes)"]),
            ConstraintRule("security", "权限控制",
                [r"权限", r"rbac", r"角色"],
                [r"(rbac|acl)"]),
            
            # 格式约束
            ConstraintRule("format", "输出格式",
                [r"格式", r"json", r"xml", r"csv"],
                [r"(json|xml|csv|yaml|html)"]),
            ConstraintRule("format", "API风格",
                [r"api", r"rest", r"graphql"],
                [r"(rest|graphql|grpc)"]),
            
            # 质量约束
            ConstraintRule("quality", "测试要求",
                [r"测试", r"覆盖率", r"coverage"],
                [r"(\d+)%.*覆盖"]),
            ConstraintRule("quality", "文档要求",
                [r"文档", r"注释", r"doc"],
                [r"(docstring|javadoc)"]),
            
            # 部署约束
            ConstraintRule("deployment", "部署方式",
                [r"部署", r"docker", r"k8s"],
                [r"(docker|k8s|serverless)"]),
            ConstraintRule("deployment", "环境",
                [r"环境", r"production"],
                [r"(生产|测试|开发|staging)"]),
        ]
    
    def extract(self, query: str) -> Tuple[List[IntentConstraint], float]:
        constraints = []
        query_lower = query.lower()
        
        for rule in self.rules:
            matched = False
            for pattern in rule.patterns:
                if re.search(pattern, query_lower, re.IGNORECASE):
                    matched = True
                    break
            
            if matched:
                value = self._extract_value(query, rule)
                required = self._is_required(query, rule.name)
                
                constraints.append(IntentConstraint(
                    constraint_type=rule.constraint_type,
                    name=rule.name,
                    value=value,
                    required=required,
                    confidence=0.8 if value else 0.5
                ))
        
        confidence = self._calculate_confidence(constraints)
        return constraints, confidence
    
    def _extract_value(self, query: str, rule: ConstraintRule) -> Optional[Any]:
        for pattern in rule.value_extractors:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                if match.groups():
                    return match.group(1)
                return True
        return None
    
    def _is_required(self, query: str, constraint_name: str) -> bool:
        required_words = [r"必须", r"一定要", r"required", r"must"]
        optional_words = [r"建议", r"最好", r"should"]
        
        for word in required_words:
            if re.search(word, query, re.IGNORECASE):
                return True
        for word in optional_words:
            if re.search(word, query, re.IGNORECASE):
                return False
        return False
    
    def _calculate_confidence(self, constraints: List[IntentConstraint]) -> float:
        if not constraints:
            return 0.5
        total = sum(c.confidence for c in constraints)
        avg = total / len(constraints)
        if len(constraints) >= 3:
            avg = min(avg * 1.1, 0.95)
        return avg
