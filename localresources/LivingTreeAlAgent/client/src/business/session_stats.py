"""
会话统计追踪器
用于追踪 Agent 会话过程中的各类指标：
- 工具调用数量
- 过程消息数量
- 调用技能数量
- 访问URL数量
- 消耗Token数量
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
import threading


@dataclass
class SessionStats:
    """会话统计数据"""
    # 计数类
    tool_call_count: int = 0           # 工具调用总次数
    message_count: int = 0             # 过程消息数量
    skill_call_count: int = 0          # 调用技能数量
    url_visit_count: int = 0           # 访问URL数量
    
    # Token消耗
    prompt_tokens: int = 0            # 提示词Token
    completion_tokens: int = 0        # 生成Token
    total_tokens: int = 0             # 总Token
    
    # 时间
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    # 详情记录
    tool_calls: List[Dict] = field(default_factory=list)  # 工具调用详情
    skills_used: List[str] = field(default_factory=list)  # 使用过的技能
    urls_visited: List[str] = field(default_factory=list) # 访问过的URL
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        duration = None
        if self.start_time and self.end_time:
            duration = (self.end_time - self.start_time).total_seconds()
        
        return {
            "tool_call_count": self.tool_call_count,
            "message_count": self.message_count,
            "skill_call_count": self.skill_call_count,
            "url_visit_count": self.url_visit_count,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "duration_seconds": duration,
            "tools_used": list(set(self.tools_used)) if hasattr(self, 'tools_used') else [],
            "urls_visited": list(set(self.urls_visited)) if hasattr(self, 'urls_visited') else [],
        }
    
    def get_summary(self) -> str:
        """获取统计摘要"""
        parts = []
        parts.append(f"🔧 工具调用: {self.tool_call_count}次")
        parts.append(f"💬 过程消息: {self.message_count}条")
        parts.append(f"🎯 调用技能: {self.skill_call_count}个")
        parts.append(f"🔗 访问URL: {self.url_visit_count}个")
        
        if self.total_tokens > 0:
            parts.append(f"📊 Token消耗: {self.total_tokens:,} (提示:{self.prompt_tokens:,} 生成:{self.completion_tokens:,})")
        
        if self.start_time and self.end_time:
            duration = (self.end_time - self.start_time).total_seconds()
            parts.append(f"⏱️ 耗时: {duration:.2f}秒")
        
        return " | ".join(parts)


class SessionStatsTracker:
    """
    会话统计追踪器
    线程安全，支持实时更新
    """
    
    def __init__(self):
        self._stats: Dict[str, SessionStats] = {}
        self._current_session_id: Optional[str] = None
        self._lock = threading.RLock()
    
    def start_session(self, session_id: str) -> SessionStats:
        """开始新的会话追踪"""
        with self._lock:
            stats = SessionStats(start_time=datetime.now())
            self._stats[session_id] = stats
            self._current_session_id = session_id
            return stats
    
    def end_session(self, session_id: str) -> Optional[SessionStats]:
        """结束会话追踪"""
        with self._lock:
            if session_id in self._stats:
                self._stats[session_id].end_time = datetime.now()
                return self._stats[session_id]
            return None
    
    def get_current_session(self) -> Optional[str]:
        """获取当前会话ID"""
        return self._current_session_id
    
    def get_stats(self, session_id: str) -> Optional[SessionStats]:
        """获取指定会话的统计"""
        with self._lock:
            return self._stats.get(session_id)
    
    def record_tool_call(self, session_id: str, tool_name: str, args: str = ""):
        """记录工具调用"""
        with self._lock:
            if session_id in self._stats:
                stats = self._stats[session_id]
                stats.tool_call_count += 1
                stats.tool_calls.append({
                    "tool": tool_name,
                    "args": args,
                    "time": datetime.now().isoformat()
                })
                # 判断是否为技能调用
                if tool_name.startswith("skill_") or "skill" in tool_name.lower():
                    stats.skill_call_count += 1
                    if tool_name not in stats.skills_used:
                        stats.skills_used.append(tool_name)
    
    def record_message(self, session_id: str, role: str = "user"):
        """记录过程消息"""
        with self._lock:
            if session_id in self._stats:
                self._stats[session_id].message_count += 1
    
    def record_url_visit(self, session_id: str, url: str):
        """记录URL访问"""
        with self._lock:
            if session_id in self._stats:
                stats = self._stats[session_id]
                stats.url_visit_count += 1
                if url not in stats.urls_visited:
                    stats.urls_visited.append(url)
    
    def record_tokens(self, session_id: str, prompt_tokens: int = 0, completion_tokens: int = 0):
        """记录Token消耗"""
        with self._lock:
            if session_id in self._stats:
                stats = self._stats[session_id]
                stats.prompt_tokens += prompt_tokens
                stats.completion_tokens += completion_tokens
                stats.total_tokens = stats.prompt_tokens + stats.completion_tokens
    
    def get_all_stats(self) -> Dict[str, SessionStats]:
        """获取所有会话统计"""
        with self._lock:
            return dict(self._stats)
    
    def clear_session(self, session_id: str):
        """清除指定会话统计"""
        with self._lock:
            if session_id in self._stats:
                del self._stats[session_id]


# 全局单例
_stats_tracker: Optional[SessionStatsTracker] = None


def get_stats_tracker() -> SessionStatsTracker:
    """获取统计追踪器单例"""
    global _stats_tracker
    if _stats_tracker is None:
        _stats_tracker = SessionStatsTracker()
    return _stats_tracker


def start_session_tracking(session_id: str) -> SessionStats:
    """快捷函数：开始会话追踪"""
    return get_stats_tracker().start_session(session_id)


def end_session_tracking(session_id: str) -> Optional[SessionStats]:
    """快捷函数：结束会话追踪"""
    return get_stats_tracker().end_session(session_id)


def get_session_stats(session_id: str) -> Optional[SessionStats]:
    """快捷函数：获取会话统计"""
    return get_stats_tracker().get_stats(session_id)
