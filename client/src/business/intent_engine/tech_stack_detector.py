# -*- coding: utf-8 -*-
"""
TechStack Detector - 技术栈检测器
=================================

从用户查询中推断和检测技术栈。

功能：
1. 编程语言检测
2. 框架检测
3. 数据库检测
4. 工具/中间件检测
5. 云服务检测
6. 技术栈组合推断
from __future__ import annotations
"""


import re
from typing import List, Dict, Tuple, Set, Optional
from dataclasses import dataclass


@dataclass
class TechStackMatch:
    """技术栈匹配结果"""
    name: str           # 技术栈名称
    category: str        # 类别（language/framework/db/tool/cloud）
    confidence: float    # 置信度
    aliases: List[str]  # 别名列表


class TechStackDetector:
    """
    技术栈检测器
    
    基于关键词匹配推断技术栈。
    """
    
    # 技术栈定义
    TECH_STACK_DB = {
        # 编程语言
        "python": {
            "category": "language",
            "aliases": ["python", "py", "python3"],
            "patterns": [r"python", r"django", r"flask", r"fastapi", r"pytorch"],
        },
        "javascript": {
            "category": "language",
            "aliases": ["js", "javascript", "node", "nodejs"],
            "patterns": [r"javascript", r"nodejs?", r"node\.js", r"express", r"npm"],
        },
        "typescript": {
            "category": "language",
            "aliases": ["ts", "typescript", "tsc"],
            "patterns": [r"typescript", r"ts"],
        },
        "java": {
            "category": "language",
            "aliases": ["java", "jdk"],
            "patterns": [r"\bjava\b", r"spring", r"maven", r"gradle"],
        },
        "go": {
            "category": "language",
            "aliases": ["go", "golang"],
            "patterns": [r"\bgo\b", r"golang"],
        },
        "rust": {
            "category": "language",
            "aliases": ["rust", "cargo"],
            "patterns": [r"rust", r"cargo"],
        },
        "c#": {
            "category": "language",
            "aliases": ["c#", "csharp", "dotnet", ".net"],
            "patterns": [r"c#", r"csharp", r"dotnet", r"\.net"],
        },
        "cpp": {
            "category": "language",
            "aliases": ["c++", "cpp"],
            "patterns": [r"c\+\+", r"cpp"],
        },
        "php": {
            "category": "language",
            "aliases": ["php", "laravel"],
            "patterns": [r"\bphp\b", r"laravel"],
        },
        
        # Web 框架
        "fastapi": {
            "category": "framework",
            "aliases": ["fastapi", "fast-api"],
            "patterns": [r"fastapi", r"fast-api"],
        },
        "django": {
            "category": "framework",
            "aliases": ["django", "django-rest-framework"],
            "patterns": [r"django", r"drf"],
        },
        "flask": {
            "category": "framework",
            "aliases": ["flask"],
            "patterns": [r"flask"],
        },
        "express": {
            "category": "framework",
            "aliases": ["express", "expressjs"],
            "patterns": [r"express", r"expressjs"],
        },
        "nestjs": {
            "category": "framework",
            "aliases": ["nestjs", "nest"],
            "patterns": [r"nestjs", r"nest\.js"],
        },
        "nextjs": {
            "category": "framework",
            "aliases": ["nextjs", "next.js", "next"],
            "patterns": [r"nextjs", r"next\.js"],
        },
        "react": {
            "category": "framework",
            "aliases": ["react", "reactjs"],
            "patterns": [r"react", r"reactjs", r"jsx", r"useeffect", r"usestate"],
        },
        "vue": {
            "category": "framework",
            "aliases": ["vue", "vuejs"],
            "patterns": [r"vue\.?(js|cli)?", r"nuxt"],
        },
        "spring": {
            "category": "framework",
            "aliases": ["spring", "springboot", "spring-boot"],
            "patterns": [r"spring", r"springboot", r"spring-boot"],
        },
        
        # 数据库
        "postgresql": {
            "category": "database",
            "aliases": ["postgresql", "postgres", "pg"],
            "patterns": [r"postgresql", r"postgres", r"\bpg\b"],
        },
        "mysql": {
            "category": "database",
            "aliases": ["mysql"],
            "patterns": [r"mysql"],
        },
        "mongodb": {
            "category": "database",
            "aliases": ["mongodb", "mongo"],
            "patterns": [r"mongodb", r"mongo"],
        },
        "redis": {
            "category": "database",
            "aliases": ["redis"],
            "patterns": [r"redis"],
        },
        "elasticsearch": {
            "category": "database",
            "aliases": ["elasticsearch", "es"],
            "patterns": [r"elasticsearch", r"\bes\b"],
        },
        "sqlite": {
            "category": "database",
            "aliases": ["sqlite", "sqlite3"],
            "patterns": [r"sqlite"],
        },
        
        # 工具/中间件
        "docker": {
            "category": "tool",
            "aliases": ["docker", "container"],
            "patterns": [r"docker", r"container", r"dockerfile"],
        },
        "kubernetes": {
            "category": "tool",
            "aliases": ["kubernetes", "k8s"],
            "patterns": [r"kubernetes", r"k8s"],
        },
        "git": {
            "category": "tool",
            "aliases": ["git", "github", "gitlab"],
            "patterns": [r"git", r"github", r"gitlab"],
        },
        "nginx": {
            "category": "tool",
            "aliases": ["nginx"],
            "patterns": [r"nginx"],
        },
        "kafka": {
            "category": "tool",
            "aliases": ["kafka", "kafkamq"],
            "patterns": [r"kafka"],
        },
        "rabbitmq": {
            "category": "tool",
            "aliases": ["rabbitmq", "rabbit"],
            "patterns": [r"rabbitmq", r"rabbit"],
        },
        
        # 云服务
        "aws": {
            "category": "cloud",
            "aliases": ["aws", "amazon", "s3", "ec2", "lambda"],
            "patterns": [r"aws", r"amazon\s*web", r"ec2", r"s3", r"lambda"],
        },
        "aliyun": {
            "category": "cloud",
            "aliases": ["aliyun", "阿里云"],
            "patterns": [r"aliyun", r"阿里云"],
        },
        "tencent": {
            "category": "cloud",
            "aliases": ["tencent", "腾讯云"],
            "patterns": [r"tencent", r"腾讯云"],
        },
        
        # AI/ML
        "pytorch": {
            "category": "ai",
            "aliases": ["pytorch", "torch"],
            "patterns": [r"pytorch", r"torch"],
        },
        "tensorflow": {
            "category": "ai",
            "aliases": ["tensorflow", "tf"],
            "patterns": [r"tensorflow", r"\btf\b"],
        },
        "langchain": {
            "category": "ai",
            "aliases": ["langchain", "lang-chain"],
            "patterns": [r"langchain", r"lang-chain"],
        },
        
        # 认证/安全
        "jwt": {
            "category": "auth",
            "aliases": ["jwt", "json web token"],
            "patterns": [r"jwt", r"token", r"token.*auth", r"auth.*token"],
        },
        "oauth": {
            "category": "auth",
            "aliases": ["oauth", "oauth2"],
            "patterns": [r"oauth"],
        },
        
        # API 相关
        "rest": {
            "category": "api",
            "aliases": ["rest", "restful", "rest api"],
            "patterns": [r"rest", r"restful", r"restful"],
        },
        "graphql": {
            "category": "api",
            "aliases": ["graphql", "gql"],
            "patterns": [r"graphql", r"gql"],
        },
        "grpc": {
            "category": "api",
            "aliases": ["grpc", "grpc"],
            "patterns": [r"grpc"],
        },
    }
    
    def __init__(self):
        # 编译所有模式
        self._compile_patterns()
        
        # 技术栈互斥关系（同一个位置不能同时出现）
        self.mutex_groups = [
            {"django", "flask", "fastapi"},  # Python Web 框架
            {"react", "vue", "angular"},      # 前端框架
            {"postgresql", "mysql", "mongodb", "sqlite"},  # 数据库
            {"python", "java", "javascript", "go", "rust"},  # 语言
        ]
    
    def _compile_patterns(self):
        """编译正则表达式"""
        for name, info in self.TECH_STACK_DB.items():
            info["compiled_patterns"] = [
                re.compile(p, re.IGNORECASE) for p in info["patterns"]
            ]
    
    def detect(self, query: str) -> Tuple[List[str], float]:
        """
        检测技术栈
        
        Args:
            query: 用户查询
            
        Returns:
            (检测到的技术栈列表, 置信度)
        """
        matches: List[TechStackMatch] = []
        query_lower = query.lower()
        
        for name, info in self.TECH_STACK_DB.items():
            confidence = 0.0
            
            # 检查别名
            for alias in info["aliases"]:
                if alias.lower() in query_lower:
                    confidence = max(confidence, 0.9)
                    break
            
            # 检查正则模式
            for pattern in info.get("compiled_patterns", []):
                if pattern.search(query):
                    confidence = max(confidence, 0.85)
                    break
            
            if confidence > 0:
                matches.append(TechStackMatch(
                    name=name,
                    category=info["category"],
                    confidence=confidence,
                    aliases=info["aliases"]
                ))
        
        # 处理互斥关系
        final_stacks = self._resolve_mutex(matches)
        
        # 计算整体置信度
        if final_stacks:
            avg_conf = sum(m.confidence for m in matches if m.name in final_stacks)
            avg_conf /= len(final_stacks)
        else:
            avg_conf = 0.0
        
        return list(final_stacks), avg_conf
    
    def _resolve_mutex(self, matches: List[TechStackMatch]) -> Set[str]:
        """
        处理互斥关系
        
        如果多个互斥的技术栈都匹配，选择置信度最高的。
        """
        selected: Set[str] = set()
        matched_names = [m.name for m in matches]
        
        for group in self.mutex_groups:
            matched_in_group = group & set(matched_names)
            if len(matched_in_group) > 1:
                # 多个匹配，选择置信度最高的
                best_match = max(
                    (m for m in matches if m.name in matched_in_group),
                    key=lambda m: m.confidence
                )
                selected.add(best_match.name)
            elif len(matched_in_group) == 1:
                selected.add(list(matched_in_group)[0])
        
        return selected
    
    def infer_from_context(self, query: str, project_context: Optional[str] = None) -> List[str]:
        """
        结合项目上下文推断技术栈
        
        Args:
            query: 用户查询
            project_context: 项目上下文（可选）
            
        Returns:
            推断的技术栈列表
        """
        stacks, _ = self.detect(query)
        
        # 如果查询中没有明确指定，尝试从上下文推断
        if not stacks and project_context:
            stacks_ctx, _ = self.detect(project_context)
            stacks = stacks_ctx
        
        return stacks
    
    def get_category(self, tech_stack: str) -> Optional[str]:
        """获取技术栈类别"""
        info = self.TECH_STACK_DB.get(tech_stack.lower())
        return info["category"] if info else None
