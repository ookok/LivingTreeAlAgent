"""
自然语言命令解析器 (Natural Language Command Parser)

将自然语言请求转换为系统命令调用。

核心功能：
1. 意图识别：识别用户的命令意图
2. 实体提取：提取命令参数
3. 命令映射：映射到对应的系统命令
4. 智能推荐：当意图不明确时提供选项

支持的命令映射：
- 模型相关命令
- 知识库命令
- 操作记录命令
- 视频录制命令
- 系统命令
"""

import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod


class CommandIntent(Enum):
    """命令意图枚举"""
    # 模型相关
    MODEL_INFO = "model_info"
    MODEL_RECOMMEND = "model_recommend"
    
    # 知识库相关
    KB_INIT = "kb_init"
    KB_STATUS = "kb_status"
    KB_INGEST = "kb_ingest"
    KB_QUERY = "kb_query"
    KB_LINT = "kb_lint"
    
    # 操作记录相关
    RECORD_START = "record_start"
    RECORD_STOP = "record_stop"
    RECORD_SUMMARY = "record_summary"
    RECORD_STATUS = "record_status"
    
    # 视频录制相关
    VIDEO_START = "video_start"
    VIDEO_STOP = "video_stop"
    VIDEO_STATUS = "video_status"
    
    # 系统相关
    SYSTEM_STATS = "system_stats"
    CHAT_CLEAR = "chat_clear"
    HELP = "help"
    
    # 未知意图
    UNKNOWN = "unknown"


@dataclass
class ParsedCommand:
    """解析后的命令"""
    intent: CommandIntent
    command: str
    args: str = ""
    confidence: float = 0.0
    alternatives: List[Tuple[str, float]] = field(default_factory=list)


class IntentPattern:
    """意图模式"""
    
    def __init__(self, intent: CommandIntent, command: str, patterns: List[str], confidence: float = 0.8):
        self.intent = intent
        self.command = command
        self.patterns = patterns
        self.confidence = confidence
    
    def match(self, text: str) -> bool:
        """检查文本是否匹配任何模式"""
        text_lower = text.lower().strip()
        for pattern in self.patterns:
            pattern_lower = pattern.lower()
            
            # 精确匹配
            if text_lower == pattern_lower:
                return True
            
            # 包含匹配
            if pattern_lower in text_lower:
                return True
            
            # 关键词匹配（所有关键词都在文本中）
            keywords = pattern_lower.split()
            if all(keyword in text_lower for keyword in keywords):
                return True
        
        return False


class NaturalCommandParser:
    """
    自然语言命令解析器
    
    将自然语言请求转换为系统命令。
    """
    
    def __init__(self):
        # 意图模式定义
        self.intent_patterns = self._load_intent_patterns()
        
        # 命令到意图的映射
        self.command_to_intent = {
            "/model": CommandIntent.MODEL_INFO,
            "/llmfit": CommandIntent.MODEL_RECOMMEND,
            "/kb init": CommandIntent.KB_INIT,
            "/kb status": CommandIntent.KB_STATUS,
            "/ingest": CommandIntent.KB_INGEST,
            "/query": CommandIntent.KB_QUERY,
            "/lint": CommandIntent.KB_LINT,
            "/record start": CommandIntent.RECORD_START,
            "/record stop": CommandIntent.RECORD_STOP,
            "/record summary": CommandIntent.RECORD_SUMMARY,
            "/record status": CommandIntent.RECORD_STATUS,
            "/video start": CommandIntent.VIDEO_START,
            "/video stop": CommandIntent.VIDEO_STOP,
            "/video status": CommandIntent.VIDEO_STATUS,
            "/stats": CommandIntent.SYSTEM_STATS,
            "/clear": CommandIntent.CHAT_CLEAR,
            "/help": CommandIntent.HELP
        }
        
        print("[NaturalCommandParser] 初始化完成")
    
    def _load_intent_patterns(self) -> List[IntentPattern]:
        """加载意图模式"""
        return [
            # 模型相关
            IntentPattern(
                CommandIntent.MODEL_INFO,
                "/model",
                [
                    "查看模型",
                    "查看连接的模型",
                    "模型信息",
                    "当前模型",
                    "用的什么模型",
                    "model info",
                    "模型状态",
                    "模型配置"
                ],
                confidence=0.85
            ),
            IntentPattern(
                CommandIntent.MODEL_RECOMMEND,
                "/llmfit",
                [
                    "推荐模型",
                    "推荐本地模型",
                    "扫描硬件",
                    "硬件检测",
                    "选择模型",
                    "适合的模型",
                    "模型推荐",
                    "llmfit",
                    "量化版本"
                ],
                confidence=0.85
            ),
            
            # 知识库相关
            IntentPattern(
                CommandIntent.KB_INIT,
                "/kb init",
                [
                    "初始化知识库",
                    "创建知识库规则",
                    "kb init",
                    "新建知识库"
                ],
                confidence=0.8
            ),
            IntentPattern(
                CommandIntent.KB_STATUS,
                "/kb status",
                [
                    "知识库状态",
                    "kb status",
                    "查看知识库",
                    "知识库信息"
                ],
                confidence=0.8
            ),
            IntentPattern(
                CommandIntent.KB_INGEST,
                "/ingest",
                [
                    "摄入资料",
                    "处理资料",
                    "更新知识库",
                    "读取raw",
                    "导入资料",
                    "ingest"
                ],
                confidence=0.8
            ),
            IntentPattern(
                CommandIntent.KB_QUERY,
                "/query",
                [
                    "查询知识库",
                    "搜索知识",
                    "查找资料",
                    "知识库搜索",
                    "帮我查",
                    "请查一下"
                ],
                confidence=0.75
            ),
            IntentPattern(
                CommandIntent.KB_LINT,
                "/lint",
                [
                    "健康检查",
                    "知识库检查",
                    "检查知识库",
                    "找矛盾",
                    "清理知识库",
                    "lint"
                ],
                confidence=0.85
            ),
            
            # 操作记录相关
            IntentPattern(
                CommandIntent.RECORD_START,
                "/record start",
                [
                    "开始记录",
                    "记录操作",
                    "开启记录",
                    "record start",
                    "开始操作记录"
                ],
                confidence=0.85
            ),
            IntentPattern(
                CommandIntent.RECORD_STOP,
                "/record stop",
                [
                    "停止记录",
                    "结束记录",
                    "record stop",
                    "停止操作记录"
                ],
                confidence=0.85
            ),
            IntentPattern(
                CommandIntent.RECORD_SUMMARY,
                "/record summary",
                [
                    "记录总结",
                    "会话总结",
                    "record summary",
                    "操作总结"
                ],
                confidence=0.85
            ),
            IntentPattern(
                CommandIntent.RECORD_STATUS,
                "/record status",
                [
                    "记录状态",
                    "record status",
                    "操作记录状态"
                ],
                confidence=0.85
            ),
            
            # 视频录制相关
            IntentPattern(
                CommandIntent.VIDEO_START,
                "/video start",
                [
                    "开始录制",
                    "录制视频",
                    "开启录制",
                    "video start",
                    "录像"
                ],
                confidence=0.85
            ),
            IntentPattern(
                CommandIntent.VIDEO_STOP,
                "/video stop",
                [
                    "停止录制",
                    "结束录制",
                    "video stop",
                    "停止录像"
                ],
                confidence=0.85
            ),
            IntentPattern(
                CommandIntent.VIDEO_STATUS,
                "/video status",
                [
                    "录制状态",
                    "video status",
                    "录像状态"
                ],
                confidence=0.85
            ),
            
            # 系统相关
            IntentPattern(
                CommandIntent.SYSTEM_STATS,
                "/stats",
                [
                    "系统统计",
                    "统计信息",
                    "系统信息",
                    "查看统计",
                    "stats"
                ],
                confidence=0.85
            ),
            IntentPattern(
                CommandIntent.CHAT_CLEAR,
                "/clear",
                [
                    "清空聊天",
                    "清除记录",
                    "clear",
                    "重置聊天"
                ],
                confidence=0.85
            ),
            IntentPattern(
                CommandIntent.HELP,
                "/help",
                [
                    "帮助",
                    "帮助信息",
                    "命令列表",
                    "help",
                    "指令"
                ],
                confidence=0.9
            )
        ]
    
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
        
        # 尝试匹配意图模式
        return self._parse_natural_language(text)
    
    def _parse_direct_command(self, text: str) -> ParsedCommand:
        """解析直接命令"""
        # 简单处理：直接返回命令
        parts = text.split(None, 1)
        command = parts[0]
        args = parts[1] if len(parts) > 1 else ""
        
        # 查找对应的意图
        intent = self.command_to_intent.get(command, CommandIntent.UNKNOWN)
        
        return ParsedCommand(
            intent=intent,
            command=command,
            args=args,
            confidence=1.0
        )
    
    def _parse_natural_language(self, text: str) -> ParsedCommand:
        """解析自然语言"""
        matches = []
        
        for pattern in self.intent_patterns:
            if pattern.match(text):
                matches.append((pattern, pattern.confidence))
        
        # 按置信度排序
        matches.sort(key=lambda x: -x[1])
        
        if matches:
            best_match = matches[0]
            pattern = best_match[0]
            
            # 提取参数（对于需要参数的命令）
            args = ""
            if pattern.intent == CommandIntent.KB_QUERY:
                # 提取查询内容
                args = self._extract_query_argument(text)
            
            return ParsedCommand(
                intent=pattern.intent,
                command=pattern.command,
                args=args,
                confidence=best_match[1],
                alternatives=[(p.command, c) for p, c in matches[1:3]]  # 返回前2个备选
            )
        else:
            return ParsedCommand(
                intent=CommandIntent.UNKNOWN,
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
        return parsed.intent != CommandIntent.UNKNOWN and parsed.confidence >= 0.7
    
    def suggest_commands(self, text: str) -> List[Tuple[str, float]]:
        """给出命令建议"""
        matches = []
        
        for pattern in self.intent_patterns:
            if pattern.match(text):
                matches.append((pattern.command, pattern.confidence))
        
        # 按置信度排序，返回前3个
        matches.sort(key=lambda x: -x[1])
        return matches[:3]


# 创建全局实例
_natural_parser = None


def get_natural_command_parser() -> NaturalCommandParser:
    """获取自然语言命令解析器实例"""
    global _natural_parser
    if _natural_parser is None:
        _natural_parser = NaturalCommandParser()
    return _natural_parser


__all__ = [
    "CommandIntent",
    "ParsedCommand",
    "NaturalCommandParser",
    "get_natural_command_parser"
]