"""
ToolMonitor - 工具使用统计与监控

实现工具使用统计和监控功能。

功能：
1. 记录工具调用日志
2. 统计工具使用次数
3. 监控工具执行时间
4. 生成使用报告
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from loguru import logger
from datetime import datetime
import time


@dataclass
class ToolCallRecord:
    """工具调用记录"""
    record_id: str
    tool_name: str
    agent_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    success: bool = False
    error_message: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    result_size: int = 0


@dataclass
class ToolStatistics:
    """工具统计信息"""
    tool_name: str
    total_calls: int = 0
    success_calls: int = 0
    failed_calls: int = 0
    total_execution_time: float = 0.0
    avg_execution_time: float = 0.0
    min_execution_time: float = float('inf')
    max_execution_time: float = 0.0
    last_call_time: Optional[datetime] = None


class ToolMonitor:
    """
    工具监控器
    
    功能：
    1. 记录工具调用日志
    2. 统计工具使用次数
    3. 监控工具执行时间
    4. 生成使用报告
    """
    
    def __init__(self):
        self._logger = logger.bind(component="ToolMonitor")
        self._call_records: List[ToolCallRecord] = []
        self._statistics: Dict[str, ToolStatistics] = {}
        self._active_calls: Dict[str, ToolCallRecord] = {}
    
    def start_call(self, tool_name: str, agent_id: str, parameters: Dict[str, Any] = None) -> str:
        """
        开始工具调用
        
        Args:
            tool_name: 工具名称
            agent_id: 调用工具的智能体 ID
            parameters: 调用参数
            
        Returns:
            记录 ID
        """
        record_id = f"call_{int(time.time() * 1000)}"
        
        record = ToolCallRecord(
            record_id=record_id,
            tool_name=tool_name,
            agent_id=agent_id,
            start_time=datetime.now(),
            parameters=parameters or {}
        )
        
        self._active_calls[record_id] = record
        self._logger.debug(f"工具调用开始: {tool_name}, agent: {agent_id}")
        
        return record_id
    
    def end_call(self, record_id: str, success: bool = True, error_message: str = "", result_size: int = 0):
        """
        结束工具调用
        
        Args:
            record_id: 记录 ID
            success: 是否成功
            error_message: 错误消息（如果失败）
            result_size: 结果大小
        """
        record = self._active_calls.pop(record_id, None)
        if not record:
            return
        
        record.end_time = datetime.now()
        record.success = success
        record.error_message = error_message
        record.result_size = result_size
        
        self._call_records.append(record)
        
        # 更新统计信息
        self._update_statistics(record)
        
        if success:
            self._logger.debug(f"工具调用完成: {record.tool_name}")
        else:
            self._logger.error(f"工具调用失败: {record.tool_name}, 错误: {error_message}")
    
    def _update_statistics(self, record: ToolCallRecord):
        """更新统计信息"""
        if record.tool_name not in self._statistics:
            self._statistics[record.tool_name] = ToolStatistics(tool_name=record.tool_name)
        
        stats = self._statistics[record.tool_name]
        stats.total_calls += 1
        stats.last_call_time = record.end_time
        
        if record.success:
            stats.success_calls += 1
        else:
            stats.failed_calls += 1
        
        # 计算执行时间
        if record.start_time and record.end_time:
            execution_time = (record.end_time - record.start_time).total_seconds()
            stats.total_execution_time += execution_time
            stats.avg_execution_time = stats.total_execution_time / stats.total_calls
            stats.min_execution_time = min(stats.min_execution_time, execution_time)
            stats.max_execution_time = max(stats.max_execution_time, execution_time)
    
    def get_statistics(self, tool_name: Optional[str] = None) -> Dict[str, Any]:
        """
        获取统计信息
        
        Args:
            tool_name: 工具名称（可选，不指定则返回所有工具）
            
        Returns:
            统计信息
        """
        if tool_name:
            stats = self._statistics.get(tool_name)
            if stats:
                return {
                    "tool_name": stats.tool_name,
                    "total_calls": stats.total_calls,
                    "success_calls": stats.success_calls,
                    "failed_calls": stats.failed_calls,
                    "success_rate": stats.success_calls / max(stats.total_calls, 1),
                    "avg_execution_time": stats.avg_execution_time,
                    "min_execution_time": stats.min_execution_time,
                    "max_execution_time": stats.max_execution_time,
                    "last_call_time": stats.last_call_time.isoformat() if stats.last_call_time else None
                }
            return {}
        
        # 返回所有工具的统计信息
        all_stats = {}
        for tool_name, stats in self._statistics.items():
            all_stats[tool_name] = {
                "total_calls": stats.total_calls,
                "success_calls": stats.success_calls,
                "failed_calls": stats.failed_calls,
                "success_rate": stats.success_calls / max(stats.total_calls, 1),
                "avg_execution_time": stats.avg_execution_time
            }
        
        return all_stats
    
    def get_call_history(self, tool_name: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取调用历史
        
        Args:
            tool_name: 工具名称（可选）
            limit: 返回数量限制
            
        Returns:
            调用历史列表
        """
        records = self._call_records
        
        if tool_name:
            records = [r for r in records if r.tool_name == tool_name]
        
        # 按时间倒序排列
        records.sort(key=lambda x: x.start_time, reverse=True)
        
        result = []
        for record in records[:limit]:
            execution_time = None
            if record.start_time and record.end_time:
                execution_time = (record.end_time - record.start_time).total_seconds()
            
            result.append({
                "record_id": record.record_id,
                "tool_name": record.tool_name,
                "agent_id": record.agent_id,
                "start_time": record.start_time.isoformat(),
                "end_time": record.end_time.isoformat() if record.end_time else None,
                "execution_time": execution_time,
                "success": record.success,
                "error_message": record.error_message,
                "parameters": record.parameters,
                "result_size": record.result_size
            })
        
        return result
    
    def get_top_tools(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取使用最多的工具"""
        stats_list = []
        
        for tool_name, stats in self._statistics.items():
            stats_list.append({
                "tool_name": tool_name,
                "total_calls": stats.total_calls,
                "success_rate": stats.success_calls / max(stats.total_calls, 1),
                "avg_execution_time": stats.avg_execution_time
            })
        
        stats_list.sort(key=lambda x: x["total_calls"], reverse=True)
        return stats_list[:limit]
    
    def get_slow_tools(self, threshold: float = 5.0) -> List[Dict[str, Any]]:
        """获取执行慢的工具"""
        slow_tools = []
        
        for tool_name, stats in self._statistics.items():
            if stats.avg_execution_time > threshold:
                slow_tools.append({
                    "tool_name": tool_name,
                    "avg_execution_time": stats.avg_execution_time,
                    "max_execution_time": stats.max_execution_time,
                    "total_calls": stats.total_calls
                })
        
        slow_tools.sort(key=lambda x: x["avg_execution_time"], reverse=True)
        return slow_tools
    
    def get_failed_tools(self, min_failure_rate: float = 0.3) -> List[Dict[str, Any]]:
        """获取失败率高的工具"""
        failed_tools = []
        
        for tool_name, stats in self._statistics.items():
            failure_rate = stats.failed_calls / max(stats.total_calls, 1)
            if failure_rate > min_failure_rate:
                failed_tools.append({
                    "tool_name": tool_name,
                    "failure_rate": failure_rate,
                    "total_calls": stats.total_calls,
                    "failed_calls": stats.failed_calls
                })
        
        failed_tools.sort(key=lambda x: x["failure_rate"], reverse=True)
        return failed_tools
    
    def generate_report(self) -> Dict[str, Any]:
        """生成综合报告"""
        total_calls = sum(stats.total_calls for stats in self._statistics.values())
        total_success = sum(stats.success_calls for stats in self._statistics.values())
        total_failed = sum(stats.failed_calls for stats in self._statistics.values())
        
        return {
            "report_time": datetime.now().isoformat(),
            "total_tools": len(self._statistics),
            "total_calls": total_calls,
            "total_success": total_success,
            "total_failed": total_failed,
            "overall_success_rate": total_success / max(total_calls, 1),
            "top_tools": self.get_top_tools(5),
            "slow_tools": self.get_slow_tools(),
            "failed_tools": self.get_failed_tools()
        }
    
    def clear_history(self):
        """清空调用历史"""
        self._call_records = []
        self._statistics = {}
        self._active_calls = {}
        self._logger.info("工具监控历史已清空")