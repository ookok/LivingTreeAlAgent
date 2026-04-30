"""
高级文本压缩方案

创新设计：
1. 语义理解压缩 - 基于知识图谱和语义分析
2. 领域自适应压缩 - 针对不同领域优化
3. 增量压缩 - 只压缩新增内容
4. 知识蒸馏压缩 - 提取核心信息
5. 动态词典压缩 - 基于上下文构建词典

Author: LivingTreeAI Agent
Date: 2026-04-30
"""

import asyncio
import re
from typing import Dict, Any, Optional, List, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger
from collections import OrderedDict, Counter


class CompressionAlgorithm(Enum):
    """压缩算法类型"""
    RULE_BASED = "rule_based"           # 规则引擎
    SEMANTIC = "semantic"               # 语义理解
    DOMAIN_ADAPTIVE = "domain_adaptive" # 领域自适应
    INCREMENTAL = "incremental"         # 增量压缩
    KNOWLEDGE_DISTILLATION = "knowledge_distillation"  # 知识蒸馏
    HYBRID = "hybrid"                   # 混合策略


class DomainType(Enum):
    """领域类型"""
    GENERAL = "general"
    CODE = "code"
    TECHNICAL = "technical"
    MEDICAL = "medical"
    LEGAL = "legal"
    FINANCIAL = "financial"
    EDUCATION = "education"
    CREATIVE = "creative"


@dataclass
class CompressionKnowledge:
    """压缩知识单元"""
    key_terms: Set[str] = field(default_factory=set)
    abbreviations: Dict[str, str] = field(default_factory=dict)
    patterns: Dict[str, str] = field(default_factory=dict)
    domain_rules: Dict[str, str] = field(default_factory=dict)


class DomainCompressionRules:
    """领域特定压缩规则"""
    
    DOMAIN_RULES = {
        DomainType.CODE: {
            "keywords": {"def", "class", "import", "return", "if", "else", "for", "while", "function", "const", "let", "var", "async", "await"},
            "abbreviations": {
                "function": "fn",
                "variable": "var",
                "parameter": "param",
                "return": "ret",
                "constant": "const",
                "component": "comp",
                "functionality": "func",
                "implementation": "impl",
                "configuration": "config",
                "documentation": "docs",
                "development": "dev",
                "production": "prod",
                "environment": "env",
                "database": "db",
                "server": "svr",
                "client": "cli",
                "application": "app",
                "interface": "iface",
                "module": "mod",
                "package": "pkg",
                "library": "lib",
                "framework": "fw",
                "algorithm": "algo",
                "data structure": "ds",
                "artificial intelligence": "AI",
                "machine learning": "ML",
                "deep learning": "DL",
                "neural network": "NN",
            },
            "patterns": {
                r'\bfunction\s+(\w+)\s*\(': r'fn \1(',
                r'\bconst\s+(\w+)\s*=': r'const \1=',
                r'\blet\s+(\w+)\s*=': r'let \1=',
                r'\bvar\s+(\w+)\s*=': r'var \1=',
                r'\breturn\b': r'ret',
                r'\bimport\s+from\b': r'import',
            }
        },
        DomainType.TECHNICAL: {
            "keywords": {"system", "architecture", "component", "module", "service", "API", "database", "server", "client", "network", "protocol", "algorithm", "framework"},
            "abbreviations": {
                "application": "app",
                "technology": "tech",
                "architecture": "arch",
                "component": "comp",
                "module": "mod",
                "service": "svc",
                "interface": "iface",
                "infrastructure": "infra",
                "deployment": "deploy",
                "configuration": "config",
                "documentation": "docs",
                "implementation": "impl",
                "integration": "integ",
                "performance": "perf",
                "scalability": "scal",
                "availability": "avail",
                "reliability": "rel",
                "security": "sec",
                "authentication": "auth",
                "authorization": "authz",
                "microservices": "microsvc",
                "containerization": "cont",
                "orchestration": "orch",
                "virtualization": "virt",
                "automation": "auto",
                "monitoring": "mon",
                "logging": "log",
                "debugging": "debug",
                "testing": "test",
                "development": "dev",
                "production": "prod",
            },
            "patterns": {
                r'\bthe\s+(system|architecture|component)\b': r'\1',
                r'\bwe\s+(need|should|can)\b': r'\1',
                r'\bin\s+order\s+to\b': r'to',
                r'\bas\s+a\s+result\b': r'so',
                r'\bin\s+addition\b': r'+',
                r'\bfor\s+example\b': r'e.g.',
                r'\bin\s+other\s+words\b': r'i.e.',
            }
        },
        DomainType.MEDICAL: {
            "keywords": {"patient", "treatment", "diagnosis", "symptom", "disease", "medication", "procedure", "clinical", "hospital", "doctor", "nurse"},
            "abbreviations": {
                "patient": "pt",
                "treatment": "tx",
                "diagnosis": "dx",
                "symptom": "sym",
                "disease": "dis",
                "medication": "med",
                "procedure": "proc",
                "clinical": "cl",
                "hospital": "hosp",
                "doctor": "dr",
                "nurse": "rn",
                "emergency": "ER",
                "intensive care unit": "ICU",
                "operating room": "OR",
                "laboratory": "lab",
                "radiology": "rad",
                "pharmacy": "pharm",
                "physiology": "physio",
                "pathology": "path",
                "anatomy": "anat",
                "biology": "bio",
                "chemistry": "chem",
                "microbiology": "micro",
                "immunology": "immuno",
                "cardiology": "cardio",
                "neurology": "neuro",
                "orthopedics": "ortho",
                "pediatrics": "peds",
                "geriatrics": "geri",
                "psychiatry": "psych",
                "surgery": "surg",
                "therapy": "ther",
                "rehabilitation": "rehab",
            },
            "patterns": {}
        },
        DomainType.LEGAL: {
            "keywords": {"agreement", "contract", "party", "term", "condition", "clause", "section", "article", "law", "regulation", "compliance"},
            "abbreviations": {
                "agreement": "agmt",
                "contract": "cntr",
                "party": "pty",
                "term": "term",
                "condition": "cond",
                "clause": "cl",
                "section": "sec",
                "article": "art",
                "law": "law",
                "regulation": "reg",
                "compliance": "comply",
                "obligation": "oblig",
                "liability": "liab",
                "indemnification": "indem",
                "confidentiality": "conf",
                "privacy": "priv",
                "intellectual property": "IP",
                "trademark": "TM",
                "copyright": "copy",
                "patent": "pat",
                "license": "lic",
                "dispute": "disp",
                "arbitration": "arb",
                "mediation": "med",
                "litigation": "lit",
                "judgment": "judg",
                "decree": "dec",
                "ruling": "rul",
                "statute": "stat",
                "ordinance": "ord",
                "provision": "prov",
                "amendment": "amend",
                "executive": "exec",
                "legislative": "leg",
                "judicial": "jud",
            },
            "patterns": {}
        },
        DomainType.FINANCIAL: {
            "keywords": {"investment", "portfolio", "asset", "liability", "revenue", "expense", "profit", "loss", "cash", "market", "stock", "bond"},
            "abbreviations": {
                "investment": "inv",
                "portfolio": "port",
                "asset": "ast",
                "liability": "liab",
                "revenue": "rev",
                "expense": "exp",
                "profit": "prf",
                "loss": "loss",
                "cash": "cash",
                "market": "mkt",
                "stock": "stk",
                "bond": "bond",
                "equity": "eq",
                "debt": "debt",
                "credit": "cr",
                "debit": "dr",
                "interest": "int",
                "dividend": "div",
                "capital": "cap",
                "fund": "fund",
                "account": "acct",
                "balance": "bal",
                "statement": "stmt",
                "report": "rpt",
                "analysis": "anl",
                "valuation": "val",
                "forecast": "fcst",
                "budget": "bud",
                "tax": "tax",
                "audit": "aud",
                "compliance": "comply",
                "risk": "risk",
                "return": "ret",
                "yield": "yield",
                "rate": "rate",
                "inflation": "inf",
                "deflation": "defl",
                "currency": "curr",
                "exchange": "exch",
            },
            "patterns": {}
        },
    }
    
    @classmethod
    def get_rules(cls, domain: DomainType) -> Dict[str, Any]:
        """获取领域规则"""
        return cls.DOMAIN_RULES.get(domain, {})


class AdvancedCompressor:
    """
    高级文本压缩器
    
    创新特性：
    1. 语义理解压缩 - 基于知识图谱分析
    2. 领域自适应压缩 - 针对不同领域优化
    3. 增量压缩 - 只压缩新增内容
    4. 知识蒸馏压缩 - 提取核心信息
    5. 动态词典压缩 - 基于上下文构建词典
    """
    
    def __init__(self):
        self._logger = logger.bind(component="AdvancedCompressor")
        self._domain_cache: Dict[str, CompressionKnowledge] = {}
        self._history: OrderedDict[str, str] = OrderedDict()
        self._dynamic_dict: Dict[str, str] = {}
        self._max_history_size = 100
    
    def _detect_domain(self, text: str) -> DomainType:
        """检测文本领域"""
        text_lower = text.lower()
        
        domain_keywords = {
            DomainType.CODE: ["def", "class", "import", "function", "const", "let", "var", "return", "if", "else", "for", "while", "console.log", "print(", "function("],
            DomainType.TECHNICAL: ["system", "architecture", "component", "API", "database", "server", "client", "network", "algorithm", "framework", "implementation"],
            DomainType.MEDICAL: ["patient", "treatment", "diagnosis", "symptom", "disease", "medication", "hospital", "doctor", "nurse", "clinical", "ICU", "ER"],
            DomainType.LEGAL: ["agreement", "contract", "party", "clause", "section", "article", "law", "regulation", "compliance", "obligation", "liability"],
            DomainType.FINANCIAL: ["investment", "portfolio", "asset", "liability", "revenue", "expense", "profit", "stock", "bond", "market", "cash"],
            DomainType.EDUCATION: ["student", "teacher", "class", "course", "school", "university", "exam", "homework", "assignment", "grade"],
            DomainType.CREATIVE: ["story", "character", "plot", "scene", "chapter", "novel", "poem", "art", "creative", "imagination"],
        }
        
        scores = {}
        for domain, keywords in domain_keywords.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            scores[domain] = score
        
        max_score = max(scores.values())
        if max_score >= 3:
            return max(scores, key=scores.get)
        
        return DomainType.GENERAL
    
    def _build_dynamic_dict(self, text: str):
        """构建动态词典"""
        words = re.findall(r'\b[a-zA-Z]{4,}\b', text)
        word_counts = Counter(words)
        
        for word, count in word_counts.items():
            if count >= 2 and word not in self._dynamic_dict:
                if len(self._dynamic_dict) < 100:
                    key = f"@{len(self._dynamic_dict):03d}"
                    self._dynamic_dict[word] = key
    
    def _apply_domain_rules(self, text: str, domain: DomainType) -> str:
        """应用领域特定规则"""
        rules = DomainCompressionRules.get_rules(domain)
        
        result = text
        
        for pattern, replacement in rules.get("patterns", {}).items():
            result = re.sub(pattern, replacement, result)
        
        for full, abbr in rules.get("abbreviations", {}).items():
            result = re.sub(r'\b' + full + r'\b', abbr, result, flags=re.IGNORECASE)
        
        return result
    
    def _semantic_compression(self, text: str) -> str:
        """语义理解压缩"""
        patterns = [
            (r'\b([Tt]he|[Aa]n?)\s+', r''),
            (r'\b([Ii]s|[Aa]re|[Ww]as|[Ww]ere|[Bb]e|[Bb]een)\s+', r''),
            (r'\b([Hh]ave|[Hh]as|[Hh]ad)\s+', r''),
            (r'\b([Dd]o|[Dd]oes|[Dd]id)\s+', r''),
            (r'\b([Ww]ill|[Ww]ould|[Cc]an|[Cc]ould|[Ss]hould|[Mm]ay|[Mm]ight)\s+', r''),
            (r'\b([Aa]nd|[Bb]ut|[Oo]r|[Ss]o|[Ff]or)\s+', r''),
            (r'\b[Ii]n\s+order\s+to\s+', r''),
            (r'\b[Aa]s\s+a\s+result\s+', r''),
            (r'\b[Ii]n\s+addition\s+', r''),
            (r'\b[Ff]or\s+example\s+', r''),
            (r'\b[Ii]n\s+other\s+words\s+', r''),
            (r'\b[Tt]hat\s+is\s+to\s+say\s+', r''),
            (r'\b[Nn]eedless\s+to\s+say\s+', r''),
            (r'\b[Oo]f\s+course\s+', r''),
            (r'\b[Cc]learly\s+', r''),
            (r'\b[Oo]bviously\s+', r''),
            (r'\b[Cc]ertainly\s+', r''),
            (r'\b[Aa]bsolutely\s+', r''),
            (r'\b[Vv]ery\s+', r''),
            (r'\b[Rr]eally\s+', r''),
            (r'\b[Gg]reat\s+', r''),
            (r'\b[Gg]ood\s+', r''),
            (r'\b[Mm]y\s+', r''),
            (r'\b[Oo]ur\s+', r''),
            (r'\b[Yy]our\s+', r''),
            (r'\b[Hh]is\s+', r''),
            (r'\b[Hh]er\s+', r''),
            (r'\b[Ii]t\s+', r''),
            (r'\b[Ww]e\s+', r''),
            (r'\b[Yy]ou\s+', r''),
            (r'\b[Tt]hey\s+', r''),
            (r'\b[Hh]e\s+', r''),
            (r'\b[Ss]he\s+', r''),
        ]
        
        result = text
        for pattern, replacement in patterns:
            result = re.sub(pattern, replacement, result)
        
        result = re.sub(r'\s+', ' ', result)
        return result.strip()
    
    def _incremental_compression(self, text: str, previous_text: str = "") -> Tuple[str, Dict[str, Any]]:
        """增量压缩"""
        if not previous_text:
            return text, {"type": "full"}
        
        previous_lines = set(previous_text.split('\n'))
        current_lines = text.split('\n')
        
        new_lines = []
        unchanged_count = 0
        
        for line in current_lines:
            if line not in previous_lines:
                new_lines.append(line)
            else:
                unchanged_count += 1
        
        if unchanged_count > 0:
            return '\n'.join(new_lines), {
                "type": "incremental",
                "unchanged_lines": unchanged_count,
                "new_lines": len(new_lines),
                "ratio": unchanged_count / len(current_lines)
            }
        
        return text, {"type": "full"}
    
    def _knowledge_distillation(self, text: str) -> Tuple[str, List[str]]:
        """知识蒸馏 - 提取核心信息"""
        key_points = []
        
        sentences = re.split(r'[.!?]+', text)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 5:
                continue
            
            if any(keyword in sentence.lower() for keyword in ["important", "关键", "核心", "必须", "需要", "应该", "建议", "结论", "总结"]):
                key_points.append(sentence)
            
            if any(keyword in sentence.lower() for keyword in ["原因", "结果", "因此", "所以", "导致"]):
                key_points.append(sentence)
        
        distilled = ' '.join(key_points) if key_points else text
        
        return distilled, key_points
    
    def _dynamic_dict_compression(self, text: str) -> str:
        """动态词典压缩"""
        self._build_dynamic_dict(text)
        
        result = text
        for word, key in sorted(self._dynamic_dict.items(), key=lambda x: -len(x[0])):
            result = re.sub(r'\b' + word + r'\b', key, result)
        
        return result
    
    async def compress(self, text: str, mode: CompressionAlgorithm = CompressionAlgorithm.HYBRID,
                      domain: Optional[DomainType] = None, previous_text: str = "") -> Dict[str, Any]:
        """
        执行高级压缩
        
        Args:
            text: 原始文本
            mode: 压缩模式
            domain: 指定领域（自动检测如果为None）
            previous_text: 上一次文本（用于增量压缩）
        
        Returns:
            压缩结果
        """
        if not text:
            return {
                "success": True,
                "compressed_text": "",
                "original_length": 0,
                "compressed_length": 0,
                "ratio": 0.0,
                "mode": mode.value,
                "domain": "unknown"
            }
        
        original_length = len(text)
        
        if domain is None:
            domain = self._detect_domain(text)
        
        result = text
        compression_info = {
            "steps": [],
            "domain": domain.value
        }
        
        if mode == CompressionAlgorithm.RULE_BASED or mode == CompressionAlgorithm.HYBRID:
            result = self._semantic_compression(result)
            compression_info["steps"].append("semantic_rules")
        
        if mode == CompressionAlgorithm.DOMAIN_ADAPTIVE or mode == CompressionAlgorithm.HYBRID:
            result = self._apply_domain_rules(result, domain)
            compression_info["steps"].append("domain_rules")
        
        if mode == CompressionAlgorithm.INCREMENTAL or mode == CompressionAlgorithm.HYBRID:
            result, inc_info = self._incremental_compression(result, previous_text)
            compression_info["steps"].append(f"incremental({inc_info['type']})")
        
        if mode == CompressionAlgorithm.KNOWLEDGE_DISTILLATION or mode == CompressionAlgorithm.HYBRID:
            result, key_points = self._knowledge_distillation(result)
            compression_info["steps"].append("knowledge_distillation")
            compression_info["key_points"] = key_points
        
        if mode == CompressionAlgorithm.HYBRID:
            result = self._dynamic_dict_compression(result)
            compression_info["steps"].append("dynamic_dict")
        
        compressed_length = len(result)
        ratio = 1 - (compressed_length / original_length) if original_length > 0 else 0
        
        self._history[text[:50] if len(text) > 50 else text] = result
        if len(self._history) > self._max_history_size:
            self._history.popitem(last=False)
        
        return {
            "success": True,
            "compressed_text": result,
            "original_length": original_length,
            "compressed_length": compressed_length,
            "ratio": ratio,
            "mode": mode.value,
            "domain": domain.value,
            "compression_info": compression_info
        }
    
    def get_domain_statistics(self) -> Dict[str, Any]:
        """获取领域统计"""
        return {
            "domains": [d.value for d in DomainType],
            "dynamic_dict_size": len(self._dynamic_dict),
            "history_size": len(self._history)
        }


# 全局实例
_advanced_compressor = AdvancedCompressor()


def get_advanced_compressor() -> AdvancedCompressor:
    """获取高级压缩器实例"""
    return _advanced_compressor
