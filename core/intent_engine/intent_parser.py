# -*- coding: utf-8 -*-
"""
Intent Parser - 意图解析器
=========================

基于规则的意图类型识别和解析。

功能：
1. 动作词提取（写/创建/修改/调试/分析...）
2. 目标提取（登录接口/用户模块/缓存层...）
3. 意图类型分类
4. 置信度计算

使用方式：
    parser = IntentParser()
    result = parser.parse("帮我写一个用户登录接口")
"""

from __future__ import annotations

import re
from typing import List, Dict, Tuple, Optional
from .intent_types import Intent, IntentType, IntentPriority


class IntentParser:
    """
    意图解析器
    
    基于关键词和模式匹配进行意图解析。
    无需 LLM 调用，快速响应。
    """
    
    def __init__(self):
        # 动作词 → 意图类型映射
        self.action_patterns = {
            # 代码生成类
            IntentType.CODE_GENERATION: [
                r"写", r"创建", r"生成", r"实现", r"编写", r"制作",
                r"write", r"create", r"generate", r"implement", r"build", r"make"
            ],
            IntentType.API_DESIGN: [
                r"接口", r"API", r"endpoint", r"路由", r"endpoint",
                r"写接口", r"定义接口", r"设计接口"
            ],
            IntentType.DATABASE_DESIGN: [
                r"表", r"数据库", r"schema", r"表结构", r"设计表",
                r"创建表", r"数据库设计"
            ],
            IntentType.UI_GENERATION: [
                r"界面", r"页面", r"UI", r"组件", r"前端", r"按钮",
                r"表单", r"弹窗", r"写页面", r"写界面"
            ],
            
            # 代码修改类
            IntentType.CODE_MODIFICATION: [
                r"修改", r"改动", r"调整", r"改一下", r"改动一下",
                r"modify", r"change", r"edit", r"update"
            ],
            IntentType.CODE_REFACTOR: [
                r"重构", r"优化代码", r"整理代码", r"规范化",
                r"refactor", r"restructure", r"reorganize"
            ],
            IntentType.CODE_OPTIMIZATION: [
                r"优化", r"提升性能", r"加速", r"减少.*延迟",
                r"optimize", r"improve.*performance", r"speed up"
            ],
            
            # 调试修复类
            IntentType.DEBUGGING: [
                r"调试", r"debug", r"排查", r"找出.*问题",
                r"为什么.*错", r"报错了", r"出问题了"
            ],
            IntentType.BUG_FIX: [
                r"修复.*bug", r"修.*bug", r"解决.*问题",
                r"fix.*bug", r"fix.*error", r"修复错误"
            ],
            IntentType.ERROR_RESOLUTION: [
                r"报错", r"错误", r"exception", r"Error",
                r"failed", r"失败", r"问题"
            ],
            
            # 代码理解类
            IntentType.CODE_UNDERSTANDING: [
                r"理解", r"看懂", r"解释.*代码", r"说明",
                r"understand", r"explain", r"what.*does"
            ],
            IntentType.CODE_EXPLANATION: [
                r"这是.*什么", r"代码.*解释", r"这段.*干.*什.*么",
                r"代码.*讲解"
            ],
            IntentType.CODE_REVIEW: [
                r"审查", r"review", r"检查.*代码", r"代码.*质量",
                r"评审"
            ],
            IntentType.DOCUMENTATION: [
                r"文档", r"注释", r"说明文档", r"api.*文档",
                r"doc", r"documentation", r"readme"
            ],
            
            # 测试验证类
            IntentType.TEST_GENERATION: [
                r"测试", r"用例", r"写.*测试", r"单元测试",
                r"test", r"unit test", r"test case"
            ],
            IntentType.SECURITY_CHECK: [
                r"安全", r"漏洞", r"security", r"sql.*注入",
                r"xss", r"csrf", r"权限"
            ],
            IntentType.PERFORMANCE_ANALYSIS: [
                r"性能", r"瓶颈", r"优化.*性能", r"performance",
                r"慢", r"卡顿"
            ],
            
            # 运维部署类
            IntentType.DEPLOYMENT: [
                r"部署", r"上线", r"发布", r"deploy", r"release",
                r"发布.*生产", r"发布.*环境"
            ],
            IntentType.CONFIGURATION: [
                r"配置", r"设置", r"config", r"配置.*文件",
                r"环境变量"
            ],
            IntentType.ENVIRONMENT_SETUP: [
                r"环境", r"搭建", r"安装.*依赖", r"setup",
                r"初始化", r"环境.*准备"
            ],
            
            # 文件操作类
            IntentType.FILE_OPERATION: [
                r"文件", r"读取", r"写入", r"删除.*文件",
                r"file", r"read", r"write", r"delete"
            ],
            IntentType.FOLDER_STRUCTURE: [
                r"目录", r"文件夹", r"结构", r"组织",
                r"folder", r"directory", r"structure"
            ],
            
            # 知识问答类
            IntentType.KNOWLEDGE_QUERY: [
                r"什么是", r".*的区别", r"如何", r"怎么实现",
                r"what.*is", r"how.*to", r"difference between"
            ],
            IntentType.BEST_PRACTICE: [
                r"最佳实践", r"推荐", r"建议.*做法",
                r"best practice", r"recommended"
            ],
        }
        
        # 动作词提取模式
        self.action_words = {
            # 动作词 → 标准动作
            "写": "编写代码",
            "创建": "创建",
            "生成": "生成",
            "实现": "实现",
            "编写": "编写",
            "制作": "制作",
            "修改": "修改",
            "改动": "修改",
            "调整": "调整",
            "重构": "重构",
            "优化": "优化",
            "调试": "调试",
            "修复": "修复",
            "解决": "解决",
            "排查": "排查",
            "理解": "理解",
            "解释": "解释",
            "审查": "审查",
            "检查": "检查",
            "测试": "测试",
            "部署": "部署",
            "上线": "上线",
            "发布": "发布",
            "配置": "配置",
            "设置": "设置",
            "搭建": "搭建",
            "安装": "安装",
            "读取": "读取",
            "写入": "写入",
            "删除": "删除",
            "查询": "查询",
            "设计": "设计",
            "分析": "分析",
            "查看": "查看",
            "生成": "生成",
            "导入": "导入",
            "导出": "导出",
            "迁移": "迁移",
            "转换": "转换",
        }
        
        # 意图优先级规则
        self.priority_rules = {
            IntentType.ERROR_RESOLUTION: IntentPriority.CRITICAL,
            IntentType.BUG_FIX: IntentPriority.CRITICAL,
            IntentType.DEBUGGING: IntentPriority.HIGH,
            IntentType.DEPLOYMENT: IntentPriority.HIGH,
            IntentType.CODE_GENERATION: IntentPriority.MEDIUM,
            IntentType.CODE_MODIFICATION: IntentPriority.MEDIUM,
            IntentType.CODE_REFACTOR: IntentPriority.MEDIUM,
            IntentType.CODE_OPTIMIZATION: IntentPriority.MEDIUM,
        }
        
        # 编译正则表达式
        self._compile_patterns()
    
    def _compile_patterns(self):
        """编译所有正则表达式"""
        self.compiled_patterns = {}
        for intent_type, patterns in self.action_patterns.items():
            self.compiled_patterns[intent_type] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]
    
    def parse(self, query: str) -> Intent:
        """
        解析用户查询
        
        Args:
            query: 用户输入的自然语言查询
            
        Returns:
            Intent: 结构化的意图对象
        """
        intent = Intent(raw_input=query)
        
        # 1. 检测意图类型
        intent_type, type_confidence = self._classify_intent(query)
        intent.intent_type = intent_type
        intent.confidence = type_confidence
        
        # 2. 提取动作词
        action = self._extract_action(query)
        intent.action = action
        
        # 3. 提取目标
        target, target_desc = self._extract_target(query, intent_type)
        intent.target = target
        intent.target_description = target_desc
        
        # 4. 设置优先级
        intent.priority = self._determine_priority(intent_type, query)
        
        # 5. 检测语言
        intent.language = self._detect_language(query)
        
        # 6. 计算完整性
        intent.completeness = self._calculate_completeness(intent)
        
        return intent
    
    def _classify_intent(self, query: str) -> Tuple[IntentType, float]:
        """
        意图分类
        
        返回:
            (意图类型, 置信度)
        """
        scores: Dict[IntentType, float] = {}
        
        for intent_type, patterns in self.compiled_patterns.items():
            score = 0.0
            for pattern in patterns:
                if pattern.search(query):
                    score += 1.0
            
            if score > 0:
                # 归一化：匹配越多，置信度越高
                confidence = min(score / len(patterns) * 0.7 + 0.3, 0.95)
                scores[intent_type] = confidence
        
        if not scores:
            return IntentType.UNKNOWN, 0.5
        
        # 返回得分最高的意图类型
        best_type = max(scores.items(), key=lambda x: x[1])
        return best_type[0], best_type[1]
    
    def _extract_action(self, query: str) -> str:
        """
        提取动作词
        
        例如：
            "帮我写一个登录接口" → "编写"
            "修复这个bug" → "修复"
        """
        for action_key, standard_action in self.action_words.items():
            if action_key in query:
                return standard_action
        
        return ""
    
    def _extract_target(self, query: str, intent_type: IntentType) -> Tuple[str, str]:
        """
        提取目标
        
        Args:
            query: 查询文本
            intent_type: 意图类型
            
        Returns:
            (目标, 目标描述)
        """
        target = ""
        target_desc = ""
        
        # 移除动作词后的文本
        clean_query = query
        for action_key in self.action_words:
            clean_query = clean_query.replace(action_key, "")
            clean_query = clean_query.replace(f"帮我{action_key}", "")
            clean_query = clean_query.replace(f"我要{action_key}", "")
            clean_query = clean_query.replace(f"帮我一下{action_key}", "")
        
        clean_query = clean_query.strip()
        
        # 提取名词短语
        # 简化版：提取连续的汉字/英文
        pattern = r'[\u4e00-\u9fa5a-zA-Z0-9]{2,30}'
        matches = re.findall(pattern, clean_query)
        
        if matches:
            # 取最长的作为目标
            target = max(matches, key=len)
            target_desc = " ".join(matches[:3])  # 前3个作为描述
        
        return target, target_desc
    
    def _determine_priority(self, intent_type: IntentType, query: str) -> IntentPriority:
        """
        确定意图优先级
        
        考虑意图类型 + 紧急程度词
        """
        # 基于类型确定基础优先级
        priority = self.priority_rules.get(intent_type, IntentPriority.MEDIUM)
        
        # 紧急程度词调整
        urgent_words = [r"紧急", r"马上", r"立即", r"尽快", r"critical", r"urgent"]
        for word in urgent_words:
            if re.search(word, query, re.IGNORECASE):
                if priority.value > IntentPriority.HIGH.value:
                    priority = IntentPriority.HIGH
                if priority.value > IntentPriority.CRITICAL.value:
                    priority = IntentPriority.CRITICAL
        
        # 紧急度降低
        low_priority_words = [r"以后", r"有空", r"不急", r"慢慢来"]
        for word in low_priority_words:
            if word in query:
                if priority.value < IntentPriority.MEDIUM.value:
                    priority = IntentPriority.LOW
        
        return priority
    
    def _detect_language(self, query: str) -> str:
        """
        检测查询语言
        
        Returns:
            "zh" / "en" / "mixed"
        """
        # 中文字符数量
        chinese_chars = len(re.findall(r'[\u4e00-\u9fa5]', query))
        # 英文字符数量
        english_chars = len(re.findall(r'[a-zA-Z]', query))
        
        total = chinese_chars + english_chars
        if total == 0:
            return "zh"
        
        chinese_ratio = chinese_chars / total
        
        if chinese_ratio > 0.7:
            return "zh"
        elif english_chars > 0.7:
            return "en"
        else:
            return "mixed"
    
    def _calculate_completeness(self, intent: Intent) -> float:
        """
        计算意图完整性
        
        完整性 = 意图描述是否足够清晰
        """
        score = 0.0
        
        # 意图类型明确 (+0.3)
        if intent.intent_type != IntentType.UNKNOWN:
            score += 0.3
        
        # 有动作词 (+0.2)
        if intent.action:
            score += 0.2
        
        # 有目标 (+0.3)
        if intent.target:
            score += 0.3
        
        # 技术栈明确 (+0.2)
        if intent.tech_stack:
            score += 0.2
        
        return min(score, 1.0)
    
    def batch_parse(self, queries: List[str]) -> List[Intent]:
        """批量解析"""
        return [self.parse(q) for q in queries]
