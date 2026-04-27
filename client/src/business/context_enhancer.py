"""
上下文管理增强模块
实现长期增强的上下文压缩策略
"""

import re
import time
import json
import hashlib
from typing import List, Dict, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum


class ContextLevel(Enum):
    """上下文级别"""
    L0 = "L0"  # 文件元信息
    L1 = "L1"  # 接口/类签名
    L2 = "L2"  # 关键函数逻辑
    L3 = "L3"  # 详细代码


class DegradationLevel(Enum):
    """降级级别"""
    NORMAL = "normal"      # 正常状态
    WARNING = "warning"    # 警告状态
    CRITICAL = "critical"  # 临界状态
    EMERGENCY = "emergency"  # 紧急状态


@dataclass
class ContextChunk:
    """上下文块"""
    id: str
    content: str
    level: ContextLevel
    tokens: int
    priority: float
    accessed_at: float
    scope: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IntentState:
    """意图状态"""
    raw_input: str
    task: str
    entities: List[Dict[str, Any]]
    constraints: List[str]
    clarified_details: List[str]
    assumptions: List[str]
    risks: List[str]
    updated_at: float = field(default_factory=time.time)


@dataclass
class MemoryManager:
    """记忆管理器"""
    short_term_memory: List[ContextChunk] = field(default_factory=list)
    long_term_memory: List[ContextChunk] = field(default_factory=list)
    max_short_term: int = 50
    max_long_term: int = 500


class ContextCompressionEnhancer:
    """
    上下文压缩增强器
    实现长期增强的上下文管理策略
    """
    
    def __init__(self):
        self.context_manager = None  # 现有的上下文管理器
        self.memory_manager = MemoryManager()
        self.intent_state: Optional[IntentState] = None
        self.degradation_level = DegradationLevel.NORMAL
        
        # 上下文窗口配置
        self.context_config = {
            "max_tokens": 128000,
            "warning_threshold": 100000,
            "critical_threshold": 115000,
            "emergency_threshold": 120000
        }
        
        # 分层摘要配置
        self.summary_config = {
            "L0_max_tokens": 100,
            "L1_max_tokens": 500,
            "L2_max_tokens": 2000,
            "L3_max_tokens": 5000
        }
    
    def set_context_manager(self, context_manager):
        """设置现有上下文管理器"""
        self.context_manager = context_manager
    
    def update_intent_state(self, intent_state: IntentState):
        """更新意图状态"""
        self.intent_state = intent_state
    
    def calculate_context_size(self, context: List[ContextChunk]) -> int:
        """计算上下文大小"""
        return sum(chunk.tokens for chunk in context)
    
    def check_degradation_level(self, current_tokens: int) -> DegradationLevel:
        """检查降级级别"""
        if current_tokens >= self.context_config["emergency_threshold"]:
            return DegradationLevel.EMERGENCY
        elif current_tokens >= self.context_config["critical_threshold"]:
            return DegradationLevel.CRITICAL
        elif current_tokens >= self.context_config["warning_threshold"]:
            return DegradationLevel.WARNING
        else:
            return DegradationLevel.NORMAL
    
    def apply_degradation_strategy(self, context: List[ContextChunk], target_tokens: int) -> List[ContextChunk]:
        """
        应用降级策略
        按照优先级降级：保意图 > 保结构 > 保关键 > 分治
        """
        current_tokens = self.calculate_context_size(context)
        if current_tokens <= target_tokens:
            return context
        
        # 1. 保意图：保留 CONSTITUTION 和 INTENT
        if self.intent_state:
            # 确保意图信息不被压缩
            pass
        
        # 2. 保结构：保留 L0+L1，丢弃 L3
        structured_context = []
        for chunk in context:
            if chunk.level in [ContextLevel.L0, ContextLevel.L1]:
                structured_context.append(chunk)
            elif chunk.level == ContextLevel.L2:
                # 保留部分 L2
                structured_context.append(chunk)
            # 丢弃 L3
        
        if self.calculate_context_size(structured_context) <= target_tokens:
            return structured_context
        
        # 3. 保关键：只保留被直接调用或继承的代码
        critical_context = self._filter_critical_context(structured_context)
        if self.calculate_context_size(critical_context) <= target_tokens:
            return critical_context
        
        # 4. 分治：任务拆分
        return self._divide_and_conquer(critical_context, target_tokens)
    
    def _filter_critical_context(self, context: List[ContextChunk]) -> List[ContextChunk]:
        """过滤关键上下文"""
        # 这里可以实现更复杂的关键代码分析
        # 暂时基于优先级过滤
        sorted_context = sorted(context, key=lambda x: x.priority, reverse=True)
        return sorted_context[:len(sorted_context) // 2]
    
    def _divide_and_conquer(self, context: List[ContextChunk], target_tokens: int) -> List[ContextChunk]:
        """分治策略"""
        # 按优先级分组
        high_priority = [c for c in context if c.priority >= 1.5]
        medium_priority = [c for c in context if 1.0 <= c.priority < 1.5]
        low_priority = [c for c in context if c.priority < 1.0]
        
        # 优先保留高优先级
        result = high_priority.copy()
        current_size = self.calculate_context_size(result)
        
        # 逐步添加中优先级
        for chunk in medium_priority:
            if current_size + chunk.tokens <= target_tokens:
                result.append(chunk)
                current_size += chunk.tokens
            else:
                break
        
        return result
    
    def generate_hierarchical_summary(self, content: str, level: ContextLevel) -> str:
        """生成分层摘要"""
        max_tokens = self.summary_config[f"{level.value}_max_tokens"]
        
        if level == ContextLevel.L0:
            # 文件元信息摘要
            return self._generate_l0_summary(content)
        elif level == ContextLevel.L1:
            # 接口/类签名摘要
            return self._generate_l1_summary(content)
        elif level == ContextLevel.L2:
            # 关键函数逻辑摘要
            return self._generate_l2_summary(content)
        elif level == ContextLevel.L3:
            # 详细代码摘要
            return self._generate_l3_summary(content)
        
        return content
    
    def _generate_l0_summary(self, content: str) -> str:
        """生成 L0 摘要"""
        # 提取文件元信息
        lines = content.split('\n')
        summary = []
        
        # 提取注释和导入
        for line in lines[:50]:  # 只处理前50行
            line = line.strip()
            if line.startswith('#') or line.startswith('//') or line.startswith('import') or line.startswith('from'):
                summary.append(line)
        
        return '\n'.join(summary[:10])  # 最多10行
    
    def _generate_l1_summary(self, content: str) -> str:
        """生成 L1 摘要"""
        # 提取接口和类签名
        patterns = [
            r'class\s+\w+\s*\([^\)]*\)',
            r'interface\s+\w+\s*{',
            r'type\s+\w+\s*=',
            r'def\s+\w+\s*\([^\)]*\)\s*(->\s*\w+)?',
            r'function\s+\w+\s*\([^\)]*\)',
            r'const\s+\w+\s*=\s*\(.*\)\s*=>'
        ]
        
        summary = []
        for pattern in patterns:
            matches = re.findall(pattern, content, re.MULTILINE)
            summary.extend(matches[:5])  # 每种类型最多5个
        
        return '\n'.join(summary[:15])  # 最多15个签名
    
    def _generate_l2_summary(self, content: str) -> str:
        """生成 L2 摘要"""
        # 提取函数逻辑摘要
        lines = content.split('\n')
        summary = []
        
        in_function = False
        function_lines = []
        
        for line in lines:
            if re.match(r'def\s+\w+\s*\(', line) or re.match(r'function\s+\w+\s*\(', line):
                if in_function and function_lines:
                    summary.append('\n'.join(function_lines[:10]))  # 每个函数最多10行
                in_function = True
                function_lines = [line.strip()]
            elif in_function:
                if line.strip().startswith('}') or (line.strip() and not line.startswith('    ') and not line.startswith('\t')):
                    summary.append('\n'.join(function_lines[:10]))
                    in_function = False
                    function_lines = []
                else:
                    function_lines.append(line.strip())
        
        return '\n\n'.join(summary[:3])  # 最多3个函数
    
    def _generate_l3_summary(self, content: str) -> str:
        """生成 L3 摘要"""
        # 详细代码摘要 - 保留关键部分
        lines = content.split('\n')
        total_lines = len(lines)
        
        # 保留开头、中间和结尾
        summary = []
        summary.extend(lines[:50])  # 前50行
        if total_lines > 100:
            summary.extend(lines[total_lines//2-25:total_lines//2+25])  # 中间50行
        summary.extend(lines[-50:])  # 后50行
        
        return '\n'.join(summary)
    
    def create_incremental_context(self, diff: str) -> List[ContextChunk]:
        """创建增量上下文"""
        chunks = []
        
        # 解析 git diff
        lines = diff.split('\n')
        current_file = ""
        content_lines = []
        
        for line in lines:
            if line.startswith('diff --git'):
                if current_file and content_lines:
                    chunk = ContextChunk(
                        id=hashlib.md5((current_file + ''.join(content_lines)).encode()).hexdigest(),
                        content='\n'.join(content_lines),
                        level=ContextLevel.L2,
                        tokens=len(''.join(content_lines)) // 4,
                        priority=1.5,
                        accessed_at=time.time(),
                        scope="diff"
                    )
                    chunks.append(chunk)
                current_file = line.split(' b/')[1] if ' b/' in line else ""
                content_lines = [line]
            else:
                content_lines.append(line)
        
        # 处理最后一个文件
        if current_file and content_lines:
            chunk = ContextChunk(
                id=hashlib.md5((current_file + ''.join(content_lines)).encode()).hexdigest(),
                content='\n'.join(content_lines),
                level=ContextLevel.L2,
                tokens=len(''.join(content_lines)) // 4,
                priority=1.5,
                accessed_at=time.time(),
                scope="diff"
            )
            chunks.append(chunk)
        
        return chunks
    
    def manage_memory(self):
        """管理记忆"""
        # 清理短期记忆
        if len(self.memory_manager.short_term_memory) > self.memory_manager.max_short_term:
            # 按访问时间排序，保留最近的
            self.memory_manager.short_term_memory.sort(key=lambda x: x.accessed_at, reverse=True)
            self.memory_manager.short_term_memory = self.memory_manager.short_term_memory[:self.memory_manager.max_short_term]
        
        # 清理长期记忆
        if len(self.memory_manager.long_term_memory) > self.memory_manager.max_long_term:
            # 按优先级和访问时间排序
            self.memory_manager.long_term_memory.sort(key=lambda x: (x.priority, x.accessed_at), reverse=True)
            self.memory_manager.long_term_memory = self.memory_manager.long_term_memory[:self.memory_manager.max_long_term]
    
    def get_context_for_task(self, task: str, max_tokens: int = 50000) -> List[ContextChunk]:
        """获取任务相关的上下文"""
        # 1. 先获取 L0+L1 摘要
        context = []
        
        # 2. 根据任务类型添加相关上下文
        if 'create' in task.lower() or 'generate' in task.lower():
            # 代码生成任务，需要更多结构信息
            context.extend([c for c in self.memory_manager.long_term_memory if c.level in [ContextLevel.L0, ContextLevel.L1]])
        elif 'fix' in task.lower() or 'debug' in task.lower():
            # 调试任务，需要错误相关信息
            context.extend([c for c in self.memory_manager.short_term_memory if 'error' in c.scope.lower()])
        elif 'refactor' in task.lower():
            # 重构任务，需要完整结构
            context.extend([c for c in self.memory_manager.long_term_memory if c.level in [ContextLevel.L0, ContextLevel.L1, ContextLevel.L2]])
        
        # 3. 应用降级策略
        return self.apply_degradation_strategy(context, max_tokens)
    
    def update_context_access(self, chunk_id: str):
        """更新上下文访问时间"""
        for chunk in self.memory_manager.short_term_memory:
            if chunk.id == chunk_id:
                chunk.accessed_at = time.time()
                break
        for chunk in self.memory_manager.long_term_memory:
            if chunk.id == chunk_id:
                chunk.accessed_at = time.time()
                break
    
    def add_context(self, content: str, level: ContextLevel, scope: str = "general"):
        """添加上下文"""
        chunk = ContextChunk(
            id=hashlib.md5((content + str(time.time())).encode()).hexdigest(),
            content=content,
            level=level,
            tokens=len(content) // 4,
            priority=self._calculate_priority(content, scope),
            accessed_at=time.time(),
            scope=scope
        )
        
        if level in [ContextLevel.L0, ContextLevel.L1]:
            # 长期记忆
            self.memory_manager.long_term_memory.append(chunk)
        else:
            # 短期记忆
            self.memory_manager.short_term_memory.append(chunk)
        
        # 管理记忆
        self.manage_memory()
        
        return chunk.id
    
    def _calculate_priority(self, content: str, scope: str) -> float:
        """计算优先级"""
        priority = 1.0
        
        # 基于范围的优先级
        if scope == "architecture":
            priority += 0.3
        elif scope == "requirements":
            priority += 0.2
        elif scope == "diff":
            priority += 0.5
        
        # 基于内容的优先级
        if any(kw in content.lower() for kw in ['important', '关键', '核心', 'critical']):
            priority += 0.2
        if any(kw in content.lower() for kw in ['TODO', 'FIXME', 'HACK']):
            priority += 0.1
        
        return min(priority, 2.0)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "short_term_memory": len(self.memory_manager.short_term_memory),
            "long_term_memory": len(self.memory_manager.long_term_memory),
            "short_term_tokens": sum(c.tokens for c in self.memory_manager.short_term_memory),
            "long_term_tokens": sum(c.tokens for c in self.memory_manager.long_term_memory),
            "degradation_level": self.degradation_level.value,
            "intent_state": self.intent_state is not None
        }


class IntentStateManager:
    """意图状态管理器"""
    
    def __init__(self):
        self.intent_states: Dict[str, IntentState] = {}
    
    def create_intent_state(self, session_id: str, raw_input: str) -> IntentState:
        """创建意图状态"""
        intent_state = IntentState(
            raw_input=raw_input,
            task="",
            entities=[],
            constraints=[],
            clarified_details=[],
            assumptions=[],
            risks=[]
        )
        self.intent_states[session_id] = intent_state
        return intent_state
    
    def get_intent_state(self, session_id: str) -> Optional[IntentState]:
        """获取意图状态"""
        return self.intent_states.get(session_id)
    
    def update_intent_state(self, session_id: str, **updates):
        """更新意图状态"""
        intent_state = self.intent_states.get(session_id)
        if intent_state:
            for key, value in updates.items():
                if hasattr(intent_state, key):
                    setattr(intent_state, key, value)
            intent_state.updated_at = time.time()
    
    def clear_intent_state(self, session_id: str):
        """清除意图状态"""
        if session_id in self.intent_states:
            del self.intent_states[session_id]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "active_intents": len(self.intent_states),
            "recent_intents": [
                {
                    "session_id": session_id,
                    "raw_input": state.raw_input[:50],
                    "updated_at": state.updated_at
                }
                for session_id, state in list(self.intent_states.items())[-5:]
            ]
        }


def create_context_enhancer() -> ContextCompressionEnhancer:
    """
    创建上下文增强器
    
    Returns:
        ContextCompressionEnhancer: 上下文增强器实例
    """
    return ContextCompressionEnhancer()


def create_intent_manager() -> IntentStateManager:
    """
    创建意图状态管理器
    
    Returns:
        IntentStateManager: 意图状态管理器实例
    """
    return IntentStateManager()