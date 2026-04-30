"""
技能发现引擎 (Skill Discovery Engine)
=====================================

参考: github.com/vercel/find-skills

实现技能发现和分析功能：
1. 代码库技能分析 - 自动发现代码中的技能和能力
2. 技能提取 - 从代码中提取技能信息
3. 技能分类 - 对发现的技能进行分类
4. 技能评分 - 评估技能熟练度

核心特性：
- 代码分析器 - 分析代码文件提取技能
- 技能识别器 - 识别技能类型和级别
- 技能分类器 - 对技能进行分类
- 技能评分器 - 评估技能熟练度

Author: LivingTreeAlAgent Team
Date: 2026-04-30
"""

import ast
import os
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = __import__('logging').getLogger(__name__)


class SkillCategory(Enum):
    """技能分类"""
    LANGUAGE = "language"          # 编程语言
    FRAMEWORK = "framework"        # 框架
    LIBRARY = "library"            # 库
    TOOL = "tool"                  # 工具
    DOMAIN = "domain"              # 领域知识
    METHODOLOGY = "methodology"    # 方法论


class SkillLevel(Enum):
    """技能级别"""
    BEGINNER = "beginner"          # 初学者
    INTERMEDIATE = "intermediate"  # 中级
    ADVANCED = "advanced"          # 高级
    EXPERT = "expert"              # 专家


@dataclass
class Skill:
    """技能"""
    name: str
    category: SkillCategory
    level: SkillLevel
    score: float = 0.0
    evidence: List[str] = field(default_factory=list)
    files: List[str] = field(default_factory=list)


@dataclass
class SkillAnalysisResult:
    """技能分析结果"""
    skills: List[Skill]
    total_files_analyzed: int = 0
    total_skills_found: int = 0
    analysis_time: float = 0.0


class SkillDiscovery:
    """
    技能发现引擎
    
    功能：
    1. 分析代码库发现技能
    2. 提取技能信息
    3. 分类和评分技能
    4. 生成技能报告
    """
    
    def __init__(self):
        # 技能关键词数据库
        self._skill_keywords = {
            # 编程语言
            "python": {"category": SkillCategory.LANGUAGE, "keywords": ["import ", "def ", "class ", "async def"]},
            "javascript": {"category": SkillCategory.LANGUAGE, "keywords": ["function ", "const ", "let ", "=>"]},
            "typescript": {"category": SkillCategory.LANGUAGE, "keywords": ["interface ", "type ", "extends ", "implements "]},
            "rust": {"category": SkillCategory.LANGUAGE, "keywords": ["fn ", "struct ", "impl ", "pub "]},
            "go": {"category": SkillCategory.LANGUAGE, "keywords": ["func ", "package ", "import ", "type "]},
            "cpp": {"category": SkillCategory.LANGUAGE, "keywords": ["#include", "class ", "public ", "private "]},
            "java": {"category": SkillCategory.LANGUAGE, "keywords": ["public class", "import ", "void ", "static "]},
            
            # 框架
            "pyqt": {"category": SkillCategory.FRAMEWORK, "keywords": ["QApplication", "QMainWindow", "QtWidgets"]},
            "qt": {"category": SkillCategory.FRAMEWORK, "keywords": ["QWidget", "QObject", "QtCore"]},
            "react": {"category": SkillCategory.FRAMEWORK, "keywords": ["React.", "useState", "useEffect", "JSX"]},
            "vue": {"category": SkillCategory.FRAMEWORK, "keywords": ["Vue.", "ref(", "reactive(", "template"]},
            "fastapi": {"category": SkillCategory.FRAMEWORK, "keywords": ["FastAPI()", "@app.get", "@app.post"]},
            "flask": {"category": SkillCategory.FRAMEWORK, "keywords": ["Flask(__name__)", "@app.route"]},
            "django": {"category": SkillCategory.FRAMEWORK, "keywords": ["django.", "from django", "Model", "View"]},
            
            # 库
            "asyncio": {"category": SkillCategory.LIBRARY, "keywords": ["asyncio.", "async ", "await "]},
            "pytest": {"category": SkillCategory.LIBRARY, "keywords": ["import pytest", "@pytest.", "def test_"]},
            "requests": {"category": SkillCategory.LIBRARY, "keywords": ["requests.", "import requests"]},
            "numpy": {"category": SkillCategory.LIBRARY, "keywords": ["import numpy", "np.", "numpy."]},
            "pandas": {"category": SkillCategory.LIBRARY, "keywords": ["import pandas", "pd.", "DataFrame"]},
            "transformers": {"category": SkillCategory.LIBRARY, "keywords": ["from transformers", "AutoModel", "Tokenizer"]},
            "langchain": {"category": SkillCategory.LIBRARY, "keywords": ["from langchain", "Chain", "Agent"]},
            "llama": {"category": SkillCategory.LIBRARY, "keywords": ["Llama", "llama."]},
            "ollama": {"category": SkillCategory.LIBRARY, "keywords": ["ollama.", "Ollama"]},
            
            # 工具
            "git": {"category": SkillCategory.TOOL, "keywords": ["git ", "commit", "push", "pull"]},
            "docker": {"category": SkillCategory.TOOL, "keywords": ["Dockerfile", "docker-compose", "FROM "]},
            "kubernetes": {"category": SkillCategory.TOOL, "keywords": ["kubernetes", "kubectl", "deployment"]},
            "terraform": {"category": SkillCategory.TOOL, "keywords": ["terraform", "resource ", "module "]},
            
            # 领域
            "llm": {"category": SkillCategory.DOMAIN, "keywords": ["LLM", "large language model", "GPT", "Claude"]},
            "rag": {"category": SkillCategory.DOMAIN, "keywords": ["RAG", "retrieval augmented generation"]},
            "ml": {"category": SkillCategory.DOMAIN, "keywords": ["machine learning", "ML", "model.fit"]},
            "nlp": {"category": SkillCategory.DOMAIN, "keywords": ["NLP", "natural language", "tokenize"]},
            "api": {"category": SkillCategory.DOMAIN, "keywords": ["API", "endpoint", "REST", "graphql"]},
            "websocket": {"category": SkillCategory.DOMAIN, "keywords": ["WebSocket", "websocket"]},
            "p2p": {"category": SkillCategory.DOMAIN, "keywords": ["P2P", "peer-to-peer", "peer"]},
            
            # 方法论
            "tdd": {"category": SkillCategory.METHODOLOGY, "keywords": ["TDD", "test-driven", "red-green-refactor"]},
            "ddd": {"category": SkillCategory.METHODOLOGY, "keywords": ["DDD", "domain-driven", "aggregate"]},
            "microservices": {"category": SkillCategory.METHODOLOGY, "keywords": ["microservice", "micro-service"]},
            "event-driven": {"category": SkillCategory.METHODOLOGY, "keywords": ["event-driven", "event sourcing"]},
        }
        
        # 文件类型映射
        self._file_types = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".jsx": "javascript",
            ".rs": "rust",
            ".go": "go",
            ".cpp": "cpp",
            ".h": "cpp",
            ".java": "java",
            ".md": "documentation",
            ".yaml": "configuration",
            ".yml": "configuration",
            ".json": "configuration",
            "Dockerfile": "docker",
            "docker-compose.yml": "docker",
        }
    
    def analyze_repo(self, repo_path: str) -> SkillAnalysisResult:
        """
        分析代码库发现技能
        
        Args:
            repo_path: 代码库路径
            
        Returns:
            技能分析结果
        """
        import time
        start_time = time.time()
        
        skills = []
        files_analyzed = 0
        
        # 遍历代码库
        for root, dirs, files in os.walk(repo_path):
            # 跳过隐藏目录和依赖目录
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'venv', 'node_modules']]
            
            for file in files:
                file_path = os.path.join(root, file)
                
                try:
                    file_skills = self._analyze_file(file_path)
                    skills.extend(file_skills)
                    files_analyzed += 1
                except Exception as e:
                    logger.debug(f"分析文件失败: {file_path}, 错误: {e}")
        
        # 合并重复技能
        skills = self._merge_skills(skills)
        
        # 计算技能级别
        for skill in skills:
            skill.level = self._calculate_level(skill)
        
        analysis_time = time.time() - start_time
        
        logger.info(f"[SkillDiscovery] 分析完成: {files_analyzed} 文件, {len(skills)} 技能, 耗时 {analysis_time:.2f}秒")
        
        return SkillAnalysisResult(
            skills=skills,
            total_files_analyzed=files_analyzed,
            total_skills_found=len(skills),
            analysis_time=analysis_time,
        )
    
    def _analyze_file(self, file_path: str) -> List[Skill]:
        """分析单个文件"""
        skills = []
        
        # 获取文件类型
        file_ext = os.path.splitext(file_path)[1].lower()
        file_name = os.path.basename(file_path)
        
        # 根据文件类型添加技能
        if file_ext in self._file_types:
            lang_skill = self._file_types[file_ext]
            if lang_skill in self._skill_keywords:
                skill_info = self._skill_keywords[lang_skill]
                skills.append(Skill(
                    name=lang_skill,
                    category=skill_info["category"],
                    level=SkillLevel.INTERMEDIATE,
                    evidence=[f"文件类型: {file_ext}"],
                    files=[file_path],
                ))
        
        # 读取文件内容分析
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # 检查技能关键词
            for skill_name, skill_info in self._skill_keywords.items():
                for keyword in skill_info["keywords"]:
                    if keyword.lower() in content.lower():
                        # 检查是否已存在
                        existing = next((s for s in skills if s.name == skill_name), None)
                        if existing:
                            existing.evidence.append(f"关键词: {keyword}")
                            existing.files.append(file_path)
                        else:
                            skills.append(Skill(
                                name=skill_name,
                                category=skill_info["category"],
                                level=SkillLevel.INTERMEDIATE,
                                evidence=[f"关键词: {keyword}"],
                                files=[file_path],
                            ))
                        break
            
            # Python 特定分析
            if file_ext == ".py":
                skills.extend(self._analyze_python_file(content, file_path))
            
        except Exception as e:
            pass
        
        return skills
    
    def _analyze_python_file(self, content: str, file_path: str) -> List[Skill]:
        """分析Python文件"""
        skills = []
        
        try:
            tree = ast.parse(content)
            
            # 分析导入
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name.split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module.split('.')[0])
            
            # 根据导入识别技能
            import_skill_map = {
                "PyQt6": "pyqt",
                "PyQt5": "pyqt",
                "qtpy": "pyqt",
                "asyncio": "asyncio",
                "pytest": "pytest",
                "requests": "requests",
                "numpy": "numpy",
                "pandas": "pandas",
                "transformers": "transformers",
                "langchain": "langchain",
                "ollama": "ollama",
                "fastapi": "fastapi",
                "flask": "flask",
                "django": "django",
            }
            
            for imp in imports:
                if imp in import_skill_map:
                    skill_name = import_skill_map[imp]
                    if skill_name in self._skill_keywords:
                        skill_info = self._skill_keywords[skill_name]
                        skills.append(Skill(
                            name=skill_name,
                            category=skill_info["category"],
                            level=SkillLevel.INTERMEDIATE,
                            evidence=[f"导入: {imp}"],
                            files=[file_path],
                        ))
            
            # 分析函数复杂度
            func_count = 0
            class_count = 0
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                    func_count += 1
                elif isinstance(node, ast.ClassDef):
                    class_count += 1
            
            # 根据代码复杂度调整级别
            if func_count > 10 or class_count > 5:
                for skill in skills:
                    if skill.name in ["python", "pyqt"]:
                        skill.level = SkillLevel.ADVANCED
        
        except SyntaxError:
            pass
        
        return skills
    
    def _merge_skills(self, skills: List[Skill]) -> List[Skill]:
        """合并重复技能"""
        merged = {}
        
        for skill in skills:
            if skill.name not in merged:
                merged[skill.name] = Skill(
                    name=skill.name,
                    category=skill.category,
                    level=skill.level,
                    score=0.0,
                    evidence=[],
                    files=[],
                )
            
            merged[skill.name].evidence.extend(skill.evidence)
            merged[skill.name].files.extend(skill.files)
            merged[skill.name].score += 1
        
        # 去重
        for skill in merged.values():
            skill.evidence = list(set(skill.evidence))
            skill.files = list(set(skill.files))
            skill.score = min(10.0, len(skill.files) * 2 + len(skill.evidence))
        
        return list(merged.values())
    
    def _calculate_level(self, skill: Skill) -> SkillLevel:
        """计算技能级别"""
        if skill.score >= 8:
            return SkillLevel.EXPERT
        elif skill.score >= 5:
            return SkillLevel.ADVANCED
        elif skill.score >= 3:
            return SkillLevel.INTERMEDIATE
        else:
            return SkillLevel.BEGINNER
    
    def get_skills_by_category(self, skills: List[Skill], category: SkillCategory) -> List[Skill]:
        """按分类获取技能"""
        return [s for s in skills if s.category == category]
    
    def get_top_skills(self, skills: List[Skill], count: int = 10) -> List[Skill]:
        """获取最核心的技能"""
        return sorted(skills, key=lambda s: s.score, reverse=True)[:count]
    
    def generate_report(self, result: SkillAnalysisResult) -> str:
        """生成技能报告"""
        report = ["技能分析报告"]
        report.append("=" * 40)
        report.append(f"分析文件数: {result.total_files_analyzed}")
        report.append(f"发现技能数: {result.total_skills_found}")
        report.append(f"分析耗时: {result.analysis_time:.2f}秒")
        report.append("")
        
        # 按分类分组
        categories = {}
        for skill in result.skills:
            if skill.category not in categories:
                categories[skill.category] = []
            categories[skill.category].append(skill)
        
        for category, skills in categories.items():
            report.append(f"【{category.value}】")
            for skill in sorted(skills, key=lambda s: s.score, reverse=True):
                report.append(f"  - {skill.name}: {skill.level.value} (得分: {skill.score:.1f})")
        
        return "\n".join(report)


# 便捷函数
def create_skill_discovery() -> SkillDiscovery:
    """创建技能发现引擎"""
    return SkillDiscovery()


__all__ = [
    "SkillCategory",
    "SkillLevel",
    "Skill",
    "SkillAnalysisResult",
    "SkillDiscovery",
    "create_skill_discovery",
]
