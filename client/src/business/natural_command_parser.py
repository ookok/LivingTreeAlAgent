"""
自然语言命令解析器 (Natural Language Command Parser)

将自然语言请求转换为系统命令调用。

核心功能：
1. 使用统一意图定义中心进行意图识别
2. 实体提取：提取命令参数
3. 命令映射：映射到对应的系统命令
4. 智能推荐：当意图不明确时提供选项

设计原则：
- 所有意图定义都来自统一的意图定义中心 (intent_definitions.py)
- 避免硬编码意图，保持一致性
- 支持动态扩展意图定义
"""

import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

# 导入统一意图定义中心
from client.src.business.intent_definitions import (
    Intent,
    get_intent_by_keyword,
    get_intent_category
)


@dataclass
class ParsedCommand:
    """解析后的命令"""
    intent: Intent
    command: str
    args: str = ""
    confidence: float = 0.0
    alternatives: List[Tuple[str, float]] = field(default_factory=list)


class NaturalCommandParser:
    """
    自然语言命令解析器
    
    将自然语言请求转换为系统命令，使用统一的意图定义中心。
    """
    
    def __init__(self):
        # 命令到意图的映射（从意图定义中心获取）
        self.command_to_intent = self._build_command_mapping()
        
        # 意图到命令的反向映射
        self.intent_to_command = {v: k for k, v in self.command_to_intent.items()}
        
        print("[NaturalCommandParser] 初始化完成（使用统一意图定义中心）")
    
    def _build_command_mapping(self) -> Dict[str, Intent]:
        """
        构建命令到意图的映射
        
        从统一意图定义中心获取意图定义，避免硬编码。
        """
        return {
            "/model": Intent.MODEL_INFO,
            "/llmfit": Intent.MODEL_RECOMMEND,
            "/kb init": Intent.KB_INIT,
            "/kb status": Intent.KB_STATUS,
            "/ingest": Intent.KB_INGEST,
            "/query": Intent.KB_QUERY,
            "/lint": Intent.KB_LINT,
            "/record start": Intent.RECORD_START,
            "/record stop": Intent.RECORD_STOP,
            "/record summary": Intent.RECORD_SUMMARY,
            "/record status": Intent.RECORD_STATUS,
            "/video start": Intent.VIDEO_START,
            "/video stop": Intent.VIDEO_STOP,
            "/video status": Intent.VIDEO_STATUS,
            "/stats": Intent.SYSTEM_STATS,
            "/clear": Intent.CHAT_CLEAR,
            "/help": Intent.HELP
        }
    
    def parse(self, text: str) -> ParsedCommand:
        """
        解析自然语言，返回对应的命令
        
        Args:
            text: 用户输入的自然语言文本
            
        Returns:
            ParsedCommand: 解析后的命令
        """
        text = text.strip()
        
        # 首先检查是否是直接命令（以 / 开头）
        if text.startswith("/"):
            return self._parse_direct_command(text)
        
        # 使用统一意图定义中心进行意图识别
        return self._parse_natural_language(text)
    
    def _parse_direct_command(self, text: str) -> ParsedCommand:
        """解析直接命令"""
        # 简单处理：直接返回命令
        parts = text.split(None, 1)
        command = parts[0]
        args = parts[1] if len(parts) > 1 else ""
        
        # 查找对应的意图（从命令映射获取）
        intent = self.command_to_intent.get(command, Intent.NLU_FALLBACK)
        
        return ParsedCommand(
            intent=intent,
            command=command,
            args=args,
            confidence=1.0
        )
    
    def _parse_natural_language(self, text: str) -> ParsedCommand:
        """
        使用统一意图定义中心解析自然语言
        
        利用意图定义中心的关键词映射进行意图识别。
        """
        text_lower = text.lower().strip()
        
        # 获取所有意图关键词
        all_keywords = Intent.get_intent_keywords()
        
        matches = []
        
        for intent_value, keywords in all_keywords.items():
            # 检查文本中是否包含该意图的任何关键词
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    intent = Intent.from_value(intent_value)
                    if intent:
                        # 计算置信度（基于匹配的关键词数量）
                        match_count = sum(1 for kw in keywords if kw.lower() in text_lower)
                        confidence = min(0.7 + (match_count * 0.1), 0.95)
                        matches.append((intent, confidence))
                    break
        
        # 按置信度排序
        matches.sort(key=lambda x: -x[1])
        
        if matches:
            best_match = matches[0]
            intent = best_match[0]
            
            # 获取对应的命令
            command = self.intent_to_command.get(intent, "")
            
            # 提取参数（对于需要参数的命令）
            args = ""
            if intent == Intent.KB_QUERY:
                args = self._extract_query_argument(text)
            
            return ParsedCommand(
                intent=intent,
                command=command,
                args=args,
                confidence=best_match[1],
                alternatives=[(self.intent_to_command.get(i, ""), c) for i, c in matches[1:3]]
            )
        else:
            return ParsedCommand(
                intent=Intent.NLU_FALLBACK,
                command="",
                args="",
                confidence=0.0
            )
    
    def _extract_query_argument(self, text: str) -> str:
        """提取查询参数"""
        # 移除触发词，提取查询内容
        trigger_words = ["查询", "搜索", "查找", "帮我", "请", "查一下", "查"]
        
        result = text
        for word in trigger_words:
            result = result.replace(word, "", 1).strip()
        
        # 移除末尾的问号
        if result.endswith("？") or result.endswith("?"):
            result = result[:-1].strip()
        
        return result
    
    def is_command(self, text: str) -> bool:
        """判断是否是命令（直接命令或自然语言命令）"""
        parsed = self.parse(text)
        return parsed.intent != Intent.NLU_FALLBACK and parsed.confidence >= 0.7
    
    def suggest_commands(self, text: str) -> List[Tuple[str, float]]:
        """给出命令建议"""
        parsed = self.parse(text)
        
        # 返回最佳匹配和备选
        suggestions = []
        
        if parsed.command:
            suggestions.append((parsed.command, parsed.confidence))
        
        # 添加备选建议
        for cmd, conf in parsed.alternatives:
            if cmd and conf >= 0.5:
                suggestions.append((cmd, conf))
        
        return suggestions
    
    def get_intent_category(self, intent: Intent) -> str:
        """获取意图分类（从统一意图定义中心获取）"""
        return get_intent_category(intent)
    
    def is_command_intent(self, intent: Intent) -> bool:
        """判断是否为命令意图"""
        return get_intent_category(intent) == "command"


# 创建全局实例
_natural_parser = None


def get_natural_command_parser() -> NaturalCommandParser:
    """获取自然语言命令解析器实例"""
    global _natural_parser
    if _natural_parser is None:
        _natural_parser = NaturalCommandParser()
    return _natural_parser


__all__ = [
    "ParsedCommand",
    "NaturalCommandParser",
    "get_natural_command_parser"
]