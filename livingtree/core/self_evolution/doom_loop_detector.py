"""
DoomLoopDetector - 死循环检测器

参考 ml-intern 的 DoomLoopDetector

功能：
1. 检测重复工具调用模式（连续3次调用同一工具且参数相似）
2. 自动注入修正提示或切换策略
3. 支持循环检测阈值配置
4. 记录循环检测历史

遵循自我进化原则：
- 从检测历史中学习优化检测策略
- 动态调整检测阈值
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger
from datetime import datetime


@dataclass
class ToolCallRecord:
    """工具调用记录"""
    tool_name: str
    params: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    result: Optional[Dict[str, Any]] = None


@dataclass
class LoopDetectionResult:
    """循环检测结果"""
    is_loop: bool
    loop_type: Optional[str] = None
    tool_name: Optional[str] = None
    count: int = 0
    suggestion: Optional[str] = None


class DoomLoopDetector:
    """
    死循环检测器
    
    检测重复工具调用模式，防止无限循环。
    
    检测策略：
    1. 连续3次调用同一工具且参数相似（参数相似度 > 80%）
    2. 工具调用次数超过阈值
    3. 检测工具调用形成的循环依赖
    """

    def __init__(self):
        self._logger = logger.bind(component="DoomLoopDetector")
        self._call_history: List[ToolCallRecord] = []
        self._max_history_size = 50
        self._loop_threshold = 3  # 连续调用阈值
        self._param_similarity_threshold = 0.8  # 参数相似度阈值
        self._detection_history: List[Dict[str, Any]] = []

    async def detect_loop(self, tool_name: str, params: Dict[str, Any]) -> LoopDetectionResult:
        """
        检测是否存在死循环
        
        Args:
            tool_name: 工具名称
            params: 工具参数
            
        Returns:
            LoopDetectionResult
        """
        # 记录当前调用
        self._record_call(tool_name, params)

        # 检测连续调用模式
        consecutive_result = await self._detect_consecutive_calls(tool_name, params)
        if consecutive_result.is_loop:
            return consecutive_result

        # 检测参数变化模式
        param_result = await self._detect_param_pattern(tool_name, params)
        if param_result.is_loop:
            return param_result

        # 检测工具调用循环
        cycle_result = await self._detect_tool_cycle()
        if cycle_result.is_loop:
            return cycle_result

        return LoopDetectionResult(is_loop=False)

    def _record_call(self, tool_name: str, params: Dict[str, Any]):
        """记录工具调用"""
        record = ToolCallRecord(tool_name=tool_name, params=params.copy())
        self._call_history.append(record)

        # 限制历史大小
        if len(self._call_history) > self._max_history_size:
            self._call_history = self._call_history[-self._max_history_size:]

    async def _detect_consecutive_calls(self, tool_name: str, params: Dict[str, Any]) -> LoopDetectionResult:
        """
        检测连续调用模式
        
        检查最近 N 次调用是否都是同一工具且参数相似
        """
        # 获取最近 N 次调用
        recent_calls = self._call_history[-self._loop_threshold:]

        # 检查是否都是同一工具
        if len(recent_calls) >= self._loop_threshold:
            same_tool = all(call.tool_name == tool_name for call in recent_calls)
            
            if same_tool:
                # 检查参数相似度
                param_similarities = []
                for call in recent_calls[:-1]:
                    similarity = self._calculate_param_similarity(call.params, params)
                    param_similarities.append(similarity)

                avg_similarity = sum(param_similarities) / len(param_similarities)
                
                if avg_similarity >= self._param_similarity_threshold:
                    self._logger.warning(f"检测到死循环: 连续 {len(recent_calls)} 次调用 {tool_name}")
                    
                    # 记录检测结果
                    self._record_detection("consecutive", tool_name, len(recent_calls))

                    return LoopDetectionResult(
                        is_loop=True,
                        loop_type="consecutive",
                        tool_name=tool_name,
                        count=len(recent_calls),
                        suggestion=self._generate_suggestion(tool_name, params)
                    )

        return LoopDetectionResult(is_loop=False)

    async def _detect_param_pattern(self, tool_name: str, params: Dict[str, Any]) -> LoopDetectionResult:
        """
        检测参数变化模式
        
        检查参数是否在小范围内循环变化（如 offset: 0, 10, 20, 0, 10, 20...）
        """
        # 获取该工具的所有调用记录
        tool_calls = [c for c in self._call_history if c.tool_name == tool_name]
        
        if len(tool_calls) >= 6:
            # 检查参数循环模式
            if self._detect_cyclic_pattern(tool_calls):
                self._logger.warning(f"检测到参数循环模式: {tool_name}")
                
                self._record_detection("param_cycle", tool_name, len(tool_calls))
                
                return LoopDetectionResult(
                    is_loop=True,
                    loop_type="param_cycle",
                    tool_name=tool_name,
                    count=len(tool_calls),
                    suggestion="检测到参数循环模式，请检查参数生成逻辑"
                )

        return LoopDetectionResult(is_loop=False)

    def _detect_cyclic_pattern(self, calls: List[ToolCallRecord]) -> bool:
        """检测参数循环模式"""
        # 简单实现：检查数值型参数是否有规律变化
        params_list = [c.params for c in calls]
        
        # 找数值型参数
        numeric_keys = []
        for key in params_list[0].keys():
            if isinstance(params_list[0][key], (int, float)):
                numeric_keys.append(key)

        for key in numeric_keys:
            values = [p[key] for p in params_list]
            # 检查是否有周期性
            if self._has_periodicity(values):
                return True

        return False

    def _has_periodicity(self, values: List[float]) -> bool:
        """检查序列是否有周期性"""
        if len(values) < 4:
            return False

        # 简单周期检测：检查是否有重复模式
        for period in [2, 3, 4]:
            if len(values) >= period * 2:
                pattern = values[:period]
                matches = True
                for i in range(period, len(values), period):
                    if i + period > len(values):
                        break
                    if values[i:i+period] != pattern:
                        matches = False
                        break
                if matches:
                    return True

        return False

    async def _detect_tool_cycle(self) -> LoopDetectionResult:
        """
        检测工具调用循环
        
        检查工具调用序列是否形成循环（如 A→B→C→A→B→C...）
        """
        if len(self._call_history) < 6:
            return LoopDetectionResult(is_loop=False)

        # 获取最近的工具调用序列
        recent_tools = [c.tool_name for c in self._call_history[-6:]]

        # 检查是否有重复模式（如 A→B→A→B 或 A→B→C→A→B→C）
        patterns = [2, 3]
        for pattern_len in patterns:
            if len(recent_tools) >= pattern_len * 2:
                first_pattern = recent_tools[:pattern_len]
                second_pattern = recent_tools[pattern_len:pattern_len*2]
                if first_pattern == second_pattern:
                    self._logger.warning(f"检测到工具调用循环: {'→'.join(first_pattern)}")
                    
                    self._record_detection("tool_cycle", "/".join(first_pattern), pattern_len)
                    
                    return LoopDetectionResult(
                        is_loop=True,
                        loop_type="tool_cycle",
                        tool_name="/".join(first_pattern),
                        count=2,
                        suggestion=f"检测到工具调用循环: {'→'.join(first_pattern)}，建议切换策略"
                    )

        return LoopDetectionResult(is_loop=False)

    def _calculate_param_similarity(self, params1: Dict[str, Any], params2: Dict[str, Any]) -> float:
        """
        计算参数相似度
        
        Args:
            params1: 参数1
            params2: 参数2
            
        Returns:
            相似度（0-1）
        """
        if not params1 or not params2:
            return 0.0

        common_keys = set(params1.keys()) & set(params2.keys())
        if not common_keys:
            return 0.0

        match_count = 0
        for key in common_keys:
            if params1[key] == params2[key]:
                match_count += 1

        return match_count / len(common_keys)

    def _generate_suggestion(self, tool_name: str, params: Dict[str, Any]) -> str:
        """生成修正建议"""
        suggestions = [
            f"检测到连续调用 {tool_name}，建议检查工具配置参数",
            f"考虑使用不同的工具或调整参数: {params}",
            "建议增加人工干预或切换执行策略",
            "检查是否存在无限循环逻辑"
        ]
        return suggestions[0]

    def _record_detection(self, loop_type: str, tool_name: str, count: int):
        """记录检测结果"""
        self._detection_history.append({
            "timestamp": datetime.now().isoformat(),
            "loop_type": loop_type,
            "tool_name": tool_name,
            "count": count
        })

    def reset(self):
        """重置检测器"""
        self._call_history = []
        self._logger.info("死循环检测器已重置")

    def get_stats(self) -> Dict[str, Any]:
        """获取检测器统计信息"""
        return {
            "call_history_size": len(self._call_history),
            "detection_count": len(self._detection_history),
            "loop_threshold": self._loop_threshold,
            "param_similarity_threshold": self._param_similarity_threshold
        }