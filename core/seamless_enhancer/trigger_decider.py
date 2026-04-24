"""
Trigger Decider - 智能触发决策器
分析任务特征，自动决定使用哪些增强能力
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


class EnhancementType(Enum):
    """增强类型"""
    REFLECTION = "reflection"           # 反思循环
    MULTI_PATH = "multi_path"           # 多路径探索
    WORLD_MODEL = "world_model"         # 世界模型模拟
    COLLECTIVE = "collective"           # 集体智能
    PROGRESSIVE = "progressive"        # 渐进式学习


@dataclass
class TaskAnalysis:
    """任务分析结果"""
    raw_query: str                     # 原始查询
    
    # 复杂度评估
    complexity: float = 0.5            # 复杂度 (0-1)
    steps_estimate: int = 1            # 预估步骤数
    
    # 风险评估
    risk_level: float = 0.5            # 风险等级 (0-1)
    is_destructive: bool = False       # 是否破坏性操作
    
    # 领域分析
    domains: List[str] = field(default_factory=list)  # 涉及领域
    requires_multi_domain: bool = False  # 是否需要多领域知识
    
    # 增强决策
    enabled_enhancements: List[EnhancementType] = field(default_factory=list)
    
    # 原因
    reasoning: str = ""


class TriggerDecider:
    """触发决策器
    
    分析用户任务，自动决定使用哪些增强能力
    用户无感知的自动化决策
    """
    
    # 复杂度关键词
    COMPLEXITY_KEYWORDS = {
        "high": [
            "架构", "设计", "系统", "优化", "重构", "迁移",
            "algorithm", "architecture", "optimize", "refactor",
            "implement", "build", "create system"
        ],
        "medium": [
            "功能", "模块", "组件", "接口", "开发",
            "function", "module", "component", "develop"
        ]
    }
    
    # 高风险关键词
    RISK_KEYWORDS = {
        "destructive": [
            "删除", "清空", "销毁", "drop", "delete", "remove",
            "格式化", "destroy", "truncate"
        ],
        "risky": [
            "修改", "更新", "批量", "替换", "修改",
            "update", "replace", "modify", "batch"
        ]
    }
    
    # 多领域关键词
    DOMAIN_KEYWORDS = {
        "code": ["代码", "编程", "函数", "class", "function", "code"],
        "database": ["数据库", "sql", "表", "db", "database"],
        "api": ["api", "接口", "请求", "http", "endpoint"],
        "file": ["文件", "读取", "写入", "file", "read", "write"],
        "network": ["网络", "请求", "下载", "http", "fetch"],
        "test": ["测试", "test", "单元测试", "测试用例"],
        "deploy": ["部署", "deploy", "上线", "发布"]
    }
    
    # 渐进式学习触发条件
    PROGRESSIVE_TRIGGERS = [
        "success", "completed", "成功", "完成",
        "work", "works", "有效", "搞定"
    ]
    
    def __init__(self, config: Dict[str, Any] = None):
        """初始化决策器
        
        Args:
            config: 配置参数
        """
        self.config = config or {}
        
        # 可配置的阈值
        self.complexity_threshold = self.config.get("complexity_threshold", 0.6)
        self.risk_threshold = self.config.get("risk_threshold", 0.5)
        self.auto_reflection = self.config.get("auto_reflection", True)
        self.auto_multi_path = self.config.get("auto_multi_path", True)
    
    def analyze(self, query: str, context: Dict[str, Any] = None) -> TaskAnalysis:
        """分析任务并决定增强策略
        
        Args:
            query: 用户查询
            context: 额外上下文 (如历史对话、用户偏好等)
            
        Returns:
            任务分析结果
        """
        context = context or {}
        
        analysis = TaskAnalysis(raw_query=query)
        
        # 1. 复杂度分析
        analysis.complexity = self._analyze_complexity(query)
        analysis.steps_estimate = self._estimate_steps(query, analysis.complexity)
        
        # 2. 风险评估
        analysis.risk_level, analysis.is_destructive = self._analyze_risk(query)
        
        # 3. 领域分析
        analysis.domains = self._analyze_domains(query)
        analysis.requires_multi_domain = len(analysis.domains) >= 2
        
        # 4. 决定启用哪些增强
        analysis.enabled_enhancements = self._decide_enhancements(analysis, context)
        
        # 5. 生成推理说明
        analysis.reasoning = self._generate_reasoning(analysis)
        
        return analysis
    
    def _analyze_complexity(self, query: str) -> float:
        """分析任务复杂度"""
        query_lower = query.lower()
        complexity = 0.5  # 默认中等复杂度
        
        # 检查高复杂度关键词
        for keyword in self.COMPLEXITY_KEYWORDS["high"]:
            if keyword.lower() in query_lower:
                complexity = max(complexity, 0.8)
                break
        
        # 检查中等复杂度关键词
        for keyword in self.COMPLEXITY_KEYWORDS["medium"]:
            if keyword.lower() in query_lower:
                complexity = max(complexity, 0.6)
                break
        
        # 检查多步骤指示
        step_keywords = ["多步", "几步", "多个", "几个", "several", "multiple"]
        for keyword in step_keywords:
            if keyword in query_lower:
                complexity = max(complexity, 0.7)
        
        # 检查项目符号/列表
        if "1." in query or "2." in query or "•" in query or "-" in query:
            complexity = max(complexity, 0.6)
        
        # 根据问题长度调整
        if len(query) > 200:
            complexity = max(complexity, 0.6)
        if len(query) > 500:
            complexity = max(complexity, 0.8)
        
        return min(complexity, 1.0)
    
    def _estimate_steps(self, query: str, complexity: float) -> int:
        """预估执行步骤数"""
        if complexity >= 0.8:
            return 5
        elif complexity >= 0.6:
            return 3
        else:
            return 1
    
    def _analyze_risk(self, query: str) -> tuple:
        """分析风险等级"""
        query_lower = query.lower()
        
        # 破坏性操作
        for keyword in self.RISK_KEYWORDS["destructive"]:
            if keyword.lower() in query_lower:
                return 0.9, True
        
        # 风险操作
        for keyword in self.RISK_KEYWORDS["risky"]:
            if keyword.lower() in query_lower:
                return 0.6, False
        
        return 0.3, False
    
    def _analyze_domains(self, query: str) -> List[str]:
        """分析涉及的领域"""
        query_lower = query.lower()
        domains = []
        
        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in query_lower:
                    if domain not in domains:
                        domains.append(domain)
                    break
        
        return domains if domains else ["general"]
    
    def _decide_enhancements(
        self,
        analysis: TaskAnalysis,
        context: Dict[str, Any]
    ) -> List[EnhancementType]:
        """决定启用哪些增强"""
        enabled = []
        
        # 1. 反思循环 - 几乎总是启用
        if self.auto_reflection:
            enabled.append(EnhancementType.REFLECTION)
        
        # 2. 多路径探索 - 复杂任务启用
        if self.auto_multi_path and analysis.complexity >= self.complexity_threshold:
            enabled.append(EnhancementType.MULTI_PATH)
        
        # 3. 世界模型 - 高风险或复杂任务
        if analysis.risk_level >= self.risk_threshold or analysis.complexity >= 0.8:
            enabled.append(EnhancementType.WORLD_MODEL)
        
        # 4. 集体智能 - 多领域任务
        if analysis.requires_multi_domain:
            enabled.append(EnhancementType.COLLECTIVE)
        
        # 5. 渐进式学习 - 始终在后台启用
        enabled.append(EnhancementType.PROGRESSIVE)
        
        return enabled
    
    def _generate_reasoning(self, analysis: TaskAnalysis) -> str:
        """生成决策推理"""
        parts = []
        
        if analysis.complexity >= 0.7:
            parts.append(f"复杂度较高({analysis.complexity:.1f})")
        
        if analysis.risk_level >= 0.6:
            parts.append(f"风险等级较高({analysis.risk_level:.1f})")
        
        if analysis.requires_multi_domain:
            parts.append(f"涉及多领域:{','.join(analysis.domains)}")
        
        enhancements = [e.value for e in analysis.enabled_enhancements]
        parts.append(f"启用:{','.join(enhancements)}")
        
        return "; ".join(parts)
    
    def should_enable(self, enhancement: EnhancementType, analysis: TaskAnalysis) -> bool:
        """检查是否应该启用某个增强"""
        return enhancement in analysis.enabled_enhancements


def create_decider(config: Dict[str, Any] = None) -> TriggerDecider:
    """创建决策器工厂"""
    return TriggerDecider(config)
