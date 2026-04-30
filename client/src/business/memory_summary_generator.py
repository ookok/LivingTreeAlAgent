"""
记忆摘要生成器 (Memory Summary Generator)
=========================================

借鉴 Claude Managed Agents 的摘要能力：
1. 自动摘要 - 对话结束自动生成摘要
2. 增量更新 - 新对话增量更新摘要
3. 语义压缩 - 保留核心信息，减少冗余
4. 多格式输出 - 支持多种摘要格式

核心特性：
- 支持多种摘要类型（简短、详细、结构化）
- 增量摘要更新（避免重复生成）
- 关键要点提取
- 实体识别和标注
- 多语言支持

Author: LivingTreeAlAgent Team
Date: 2026-04-30
"""

import json
import time
import asyncio
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4

logger = __import__('logging').getLogger(__name__)


class SummaryType(Enum):
    """摘要类型"""
    BRIEF = "brief"           # 简短摘要（1-2句话）
    DETAILED = "detailed"     # 详细摘要（段落）
    STRUCTURED = "structured" # 结构化摘要（要点列表）
    BULLET = "bullet"         # 项目符号摘要
    MARKDOWN = "markdown"     # Markdown格式摘要


class SummaryMode(Enum):
    """摘要模式"""
    FULL = "full"             # 完整重新生成
    INCREMENTAL = "incremental" # 增量更新


@dataclass
class SummaryResult:
    """摘要结果"""
    summary_id: str
    content: str
    summary_type: SummaryType
    mode: SummaryMode
    key_points: List[str]
    entities: List[str]
    confidence: float          # 置信度 0-1
    token_count: int           # 输出token数
    execution_time: float      # 执行时间（秒）


@dataclass
class ConversationContext:
    """对话上下文"""
    conversation_id: str
    messages: List[Dict[str, Any]]
    previous_summary: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class MemorySummaryGenerator:
    """
    记忆摘要生成器
    
    核心功能：
    1. 生成对话摘要（多种格式）
    2. 增量更新摘要
    3. 提取关键要点和实体
    4. 支持多语言摘要
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # LLM 调用函数
        self._llm_callable = None
        
        # 配置参数
        self._config = {
            "default_summary_type": "detailed",
            "max_tokens": 500,
            "min_confidence": 0.7,
            "incremental_threshold": 3,  # 新增消息数超过此值时增量更新
            "max_key_points": 5,
            "max_entities": 10,
        }
        
        # 提示词模板
        self._prompt_templates = {
            SummaryType.BRIEF: """请用1-2句话简要总结以下对话：

{conversation}

摘要：""",
            
            SummaryType.DETAILED: """请详细总结以下对话内容：

{conversation}

要求：
1. 概括对话的主要内容和目的
2. 列出关键决策和行动项
3. 保持自然流畅的语言

摘要：""",
            
            SummaryType.STRUCTURED: """请对以下对话进行结构化总结：

{conversation}

请按照以下格式输出：
## 对话主题
[主题描述]

## 关键要点
- [要点1]
- [要点2]
- [要点3]

## 核心实体
- [实体1]
- [实体2]

## 后续行动
- [行动1]
- [行动2]""",
            
            SummaryType.BULLET: """请用项目符号总结以下对话：

{conversation}

- 
- 
- """,
            
            SummaryType.MARKDOWN: """# 对话总结

## 概述
[对话概述]

## 关键要点
| 序号 | 内容 |
|------|------|
| 1 | [要点1] |
| 2 | [要点2] |

## 涉及实体
- [实体1]
- [实体2]

## 结论与行动
[结论和下一步行动]""",
        }
        
        # 增量更新提示词
        self._incremental_template = """以下是之前的对话摘要：

{previous_summary}

现在有新的对话内容：

{new_messages}

请根据新内容增量更新摘要，保留原有信息并添加新内容：

更新后的摘要："""
        
        self._initialized = True
        logger.info("[MemorySummaryGenerator] 记忆摘要生成器初始化完成")
    
    def set_llm_callable(self, llm_callable: Callable[[str], str]):
        """设置 LLM 调用函数"""
        self._llm_callable = llm_callable
    
    def configure(self, **kwargs):
        """配置摘要生成器"""
        self._config.update(kwargs)
        logger.info(f"[MemorySummaryGenerator] 配置更新: {kwargs}")
    
    def generate_summary(self, context: ConversationContext, 
                         summary_type: SummaryType = None) -> SummaryResult:
        """
        生成对话摘要
        
        Args:
            context: 对话上下文
            summary_type: 摘要类型（可选，默认使用配置的类型）
            
        Returns:
            SummaryResult: 摘要结果
        """
        start_time = time.time()
        
        # 确定摘要类型
        summary_type = summary_type or SummaryType(self._config["default_summary_type"])
        
        # 判断是否使用增量更新
        mode = SummaryMode.FULL
        if context.previous_summary and len(context.messages) > self._config["incremental_threshold"]:
            mode = SummaryMode.INCREMENTAL
        
        try:
            if mode == SummaryMode.INCREMENTAL:
                # 增量更新
                result = self._generate_incremental_summary(context, summary_type)
            else:
                # 完整生成
                result = self._generate_full_summary(context, summary_type)
            
            # 分析结果，提取要点和实体
            key_points, entities = self._analyze_summary(result["content"])
            
            # 计算置信度
            confidence = self._calculate_confidence(result["content"], context.messages)
            
            return SummaryResult(
                summary_id=f"sum_{uuid4().hex[:8]}",
                content=result["content"],
                summary_type=summary_type,
                mode=mode,
                key_points=key_points[:self._config["max_key_points"]],
                entities=entities[:self._config["max_entities"]],
                confidence=confidence,
                token_count=len(result["content"]),
                execution_time=time.time() - start_time
            )
            
        except Exception as e:
            logger.error(f"[MemorySummaryGenerator] 生成摘要失败: {e}")
            return SummaryResult(
                summary_id=f"sum_{uuid4().hex[:8]}",
                content="",
                summary_type=summary_type,
                mode=mode,
                key_points=[],
                entities=[],
                confidence=0.0,
                token_count=0,
                execution_time=time.time() - start_time
            )
    
    async def generate_summary_async(self, context: ConversationContext,
                                     summary_type: SummaryType = None) -> SummaryResult:
        """异步生成摘要"""
        return self.generate_summary(context, summary_type)
    
    def summarize_text(self, text: str, summary_type: SummaryType = None) -> str:
        """
        简单文本摘要（便捷方法）
        
        Args:
            text: 要摘要的文本
            summary_type: 摘要类型
            
        Returns:
            摘要文本
        """
        context = ConversationContext(
            conversation_id="temp",
            messages=[{"role": "user", "content": text}]
        )
        
        result = self.generate_summary(context, summary_type)
        return result.content
    
    async def summarize_text_async(self, text: str, summary_type: SummaryType = None) -> str:
        """异步文本摘要"""
        return self.summarize_text(text, summary_type)
    
    def extract_key_points(self, text: str) -> List[str]:
        """
        提取关键要点
        
        Args:
            text: 输入文本
            
        Returns:
            关键要点列表
        """
        prompt = f"""请从以下文本中提取关键要点：

{text}

请列出3-5个关键要点，每个要点不超过20字：
1. 
2. 
3. 
4. 
5. """
        
        response = self._call_llm(prompt)
        return self._parse_numbered_list(response)
    
    def extract_entities(self, text: str) -> List[str]:
        """
        提取实体
        
        Args:
            text: 输入文本
            
        Returns:
            实体列表
        """
        prompt = f"""请从以下文本中提取实体（人物、地点、组织、产品、概念等）：

{text}

请列出实体，用顿号分隔："""
        
        response = self._call_llm(prompt)
        return [e.strip() for e in response.strip().split("、") if e.strip()]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "config": self._config,
            "summary_types": [t.value for t in SummaryType],
            "modes": [m.value for m in SummaryMode],
        }
    
    # ========== 私有方法 ==========
    
    def _call_llm(self, prompt: str) -> str:
        """调用 LLM 生成响应"""
        if self._llm_callable:
            return self._llm_callable(prompt)
        
        # 尝试使用默认的模型路由
        try:
            from business.global_model_router import call_model_sync, ModelCapability
            return call_model_sync(ModelCapability.CHAT, prompt)
        except ImportError:
            logger.warning("[MemorySummaryGenerator] LLM 不可用")
            return ""
    
    def _generate_full_summary(self, context: ConversationContext, 
                               summary_type: SummaryType) -> Dict[str, Any]:
        """生成完整摘要"""
        # 构建对话文本
        conversation_text = self._format_conversation(context.messages)
        
        # 获取提示词模板
        template = self._prompt_templates.get(summary_type, self._prompt_templates[SummaryType.DETAILED])
        prompt = template.format(conversation=conversation_text)
        
        # 调用 LLM
        response = self._call_llm(prompt)
        
        return {"content": response.strip()}
    
    def _generate_incremental_summary(self, context: ConversationContext,
                                      summary_type: SummaryType) -> Dict[str, Any]:
        """增量更新摘要"""
        # 获取新消息
        new_messages = context.messages[-self._config["incremental_threshold"]:]
        new_messages_text = self._format_conversation(new_messages)
        
        # 构建增量更新提示
        prompt = self._incremental_template.format(
            previous_summary=context.previous_summary,
            new_messages=new_messages_text
        )
        
        # 调用 LLM
        response = self._call_llm(prompt)
        
        return {"content": response.strip()}
    
    def _format_conversation(self, messages: List[Dict[str, Any]]) -> str:
        """格式化对话为文本"""
        lines = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            
            # 标准化角色名称
            role_map = {
                "user": "用户",
                "assistant": "助手",
                "system": "系统",
                "unknown": "未知"
            }
            role_name = role_map.get(role, role)
            
            lines.append(f"{role_name}：{content}")
        
        return "\n".join(lines)
    
    def _analyze_summary(self, summary: str) -> Tuple[List[str], List[str]]:
        """分析摘要，提取要点和实体"""
        # 简单的启发式分析
        key_points = []
        entities = []
        
        # 尝试提取要点（以"- "或数字开头的行）
        import re
        lines = summary.split("\n")
        
        for line in lines:
            line = line.strip()
            
            # 匹配项目符号或编号
            bullet_match = re.match(r'^[-*•]+\s+(.+)', line)
            number_match = re.match(r'^\d+[\.\)]\s+(.+)', line)
            
            if bullet_match:
                key_points.append(bullet_match.group(1)[:50])
            elif number_match:
                key_points.append(number_match.group(1)[:50])
            
            # 提取实体（大写开头的单词或特定模式）
            entity_pattern = r'\b[A-Z][a-zA-Z]+\b'
            entities.extend(re.findall(entity_pattern, line))
            
            # 提取中文实体（包含关键词的短语）
            chinese_entity_keywords = ["公司", "产品", "项目", "系统", "功能", "模块", "方法"]
            for keyword in chinese_entity_keywords:
                if keyword in line:
                    parts = line.split(keyword)
                    if len(parts) > 1:
                        prefix = parts[0].strip()
                        if prefix:
                            words = prefix.split()
                            if words:
                                entities.append(words[-1] + keyword)
        
        # 去重
        key_points = list(set(key_points))
        entities = list(set(entities))
        
        return key_points, entities
    
    def _calculate_confidence(self, summary: str, messages: List[Dict[str, Any]]) -> float:
        """计算摘要置信度"""
        if not summary or not messages:
            return 0.0
        
        # 基于长度的置信度
        summary_length = len(summary)
        expected_length = sum(len(str(m.get("content", ""))) for m in messages) / 3
        
        length_score = min(summary_length / max(expected_length, 10), 1.0)
        
        # 基于内容覆盖的置信度（简单检查关键词）
        all_content = " ".join(str(m.get("content", "")) for m in messages).lower()
        summary_lower = summary.lower()
        
        # 检查摘要是否包含原对话的关键信息
        key_phrases = ["用户", "助手", "问题", "回答", "建议", "总结", "结论"]
        coverage_score = sum(1 for phrase in key_phrases if phrase in summary_lower) / len(key_phrases)
        
        # 综合评分
        return (length_score + coverage_score) / 2
    
    def _parse_numbered_list(self, text: str) -> List[str]:
        """解析编号列表"""
        lines = text.split("\n")
        result = []
        
        import re
        for line in lines:
            line = line.strip()
            match = re.match(r'^\d+[\.\)]\s+(.+)', line)
            if match:
                result.append(match.group(1).strip())
        
        return result


# 便捷函数
def get_summary_generator() -> MemorySummaryGenerator:
    """获取记忆摘要生成器单例"""
    return MemorySummaryGenerator()


__all__ = [
    "SummaryType",
    "SummaryMode",
    "SummaryResult",
    "ConversationContext",
    "MemorySummaryGenerator",
    "get_summary_generator",
]