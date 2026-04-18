"""
上下文感知系统
Context Awareness System

感知维度：
- 项目上下文：咨询报告/小说/诗歌
- 进度上下文：开始/中间/结尾
- 情感上下文：紧张/舒缓/激昂
- 时间上下文：创作时段，持续时间
- 环境上下文：设备类型，网络状况

自适应策略：
- 进度感知：开头多建议，结尾少干扰
- 时间感知：深夜创作→温和建议
- 情感感知：激情写作→减少打断
- 疲劳感知：长时间写作→休息提醒
"""

import time
from typing import Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, time as dtime


class WritingPhase(Enum):
    """写作阶段"""
    START = "start"      # 开头
    MIDDLE = "middle"    # 中间
    END = "end"         # 结尾


class TimeOfDay(Enum):
    """时段"""
    EARLY_MORNING = "early_morning"  # 清晨 (5-7)
    MORNING = "morning"              # 上午 (7-12)
    AFTERNOON = "afternoon"          # 下午 (12-17)
    EVENING = "evening"              # 傍晚 (17-19)
    NIGHT = "night"                  # 夜晚 (19-23)
    LATE_NIGHT = "late_night"       # 深夜 (23-5)


class FatigueLevel(Enum):
    """疲劳程度"""
    FRESH = "fresh"           # 精神饱满
    NORMAL = "normal"         # 正常
    TIRED = "tired"           # 有些疲惫
    EXHAUSTED = "exhausted"   # 极度疲惫


class EmotionalState(Enum):
    """情感状态"""
    FOCUSED = "focused"       # 专注
    INSPIRED = "inspired"     # 灵感迸发
    BLOCKED = "blocked"       # 创作瓶颈
    RELAXED = "relaxed"       # 放松
    STRESSED = "stressed"     # 压力


@dataclass
class ContextSnapshot:
    """上下文快照"""
    # 基础信息
    mode: str = "creative"           # consulting/creative
    project_type: str = ""             # 项目类型
    
    # 进度
    phase: WritingPhase = WritingPhase.START
    progress_percent: float = 0.0
    word_count: int = 0
    target_word_count: int = 0
    
    # 时间
    time_of_day: TimeOfDay = TimeOfDay.MORNING
    session_duration_minutes: int = 0
    total_duration_minutes: int = 0
    
    # 状态
    emotional_state: EmotionalState = EmotionalState.FOCUSED
    fatigue_level: FatigueLevel = FatigueLevel.NORMAL
    
    # 环境
    device_type: str = "desktop"
    network_status: str = "good"
    
    # 行为模式
    typing_speed: float = 0.0          # 字/分钟
    pause_frequency: float = 0.0     # 暂停频率
    correction_rate: float = 0.0      # 修改率
    
    # 时间戳
    timestamp: float = field(default_factory=time.time)


@dataclass
class AdaptiveStrategy:
    """自适应策略"""
    # AI干预策略
    suggestion_frequency: float = 0.5   # 0-1
    intervention_level: str = "moderate"  # minimal/moderate/aggressive
    
    # 界面策略
    show_progress: bool = True
    show_timer: bool = True
    show_word_count: bool = True
    
    # 功能策略
    enable_auto_save: bool = True
    enable_auto_complete: bool = True
    enable_background_processing: bool = True
    
    # 提醒策略
    break_reminder: bool = True
    fatigue_warning: bool = True
    milestone_celebration: bool = True


class ContextAwareSystem:
    """
    上下文感知系统
    
    持续感知写作环境，动态调整AI策略
    """
    
    # 时段定义
    TIME_RANGES = {
        TimeOfDay.EARLY_MORNING: (5, 7),
        TimeOfDay.MORNING: (7, 12),
        TimeOfDay.AFTERNOON: (12, 17),
        TimeOfDay.EVENING: (17, 19),
        TimeOfDay.NIGHT: (19, 23),
        TimeOfDay.LATE_NIGHT: (23, 5),
    }
    
    def __init__(self):
        # 当前上下文
        self.current_context: ContextSnapshot = ContextSnapshot()
        
        # 历史上下文
        self.context_history: list[ContextSnapshot] = []
        self.max_history = 100
        
        # 回调
        self.on_context_change: Optional[Callable] = None
        self.on_strategy_change: Optional[Callable] = None
        
        # 统计
        self._session_start = time.time()
        self._typing_events: list[float] = []
        self._pause_events: list[float] = []
    
    # ==================== 上下文感知 ====================
    
    def update_context(self, **kwargs):
        """
        更新上下文
        
        可以在任何时候调用以更新上下文信息
        """
        old_context = self.current_context.copy() if hasattr(self.current_context, 'copy') else None
        
        for key, value in kwargs.items():
            if hasattr(self.current_context, key):
                setattr(self.current_context, key, value)
        
        # 自动计算派生属性
        self._update_derived_attributes()
        
        # 记录历史
        if old_context:
            self._record_history()
        
        # 触发回调
        if self.on_context_change and old_context:
            self.on_context_change(old_context, self.current_context)
    
    def _update_derived_attributes(self):
        """更新派生属性"""
        # 更新时段
        current_hour = datetime.now().hour
        self.current_context.time_of_day = self._get_time_of_day(current_hour)
        
        # 更新会话时长
        self.current_context.session_duration_minutes = int(
            (time.time() - self._session_start) / 60
        )
        
        # 更新阶段
        self._update_phase()
        
        # 更新疲劳度
        self._update_fatigue()
    
    def _get_time_of_day(self, hour: int) -> TimeOfDay:
        """根据小时获取时段"""
        for tod, (start, end) in self.TIME_RANGES.items():
            if start <= hour < end:
                return tod
        return TimeOfDay.LATE_NIGHT
    
    def _update_phase(self):
        """更新写作阶段"""
        progress = self.current_context.progress_percent
        
        if progress < 0.15:
            self.current_context.phase = WritingPhase.START
        elif progress > 0.85:
            self.current_context.phase = WritingPhase.END
        else:
            self.current_context.phase = WritingPhase.MIDDLE
    
    def _update_fatigue(self):
        """更新疲劳度"""
        session_mins = self.current_context.session_duration_minutes
        
        if session_mins < 30:
            self.current_context.fatigue_level = FatigueLevel.FRESH
        elif session_mins < 60:
            self.current_context.fatigue_level = FatigueLevel.NORMAL
        elif session_mins < 120:
            self.current_context.fatigue_level = FatigueLevel.TIRED
        else:
            self.current_context.fatigue_level = FatigueLevel.EXHAUSTED
        
        # 考虑时段
        if self.current_context.time_of_day == TimeOfDay.LATE_NIGHT:
            if self.current_context.fatigue_level.value in ["fresh", "normal"]:
                self.current_context.fatigue_level = FatigueLevel.TIRED
    
    def _record_history(self):
        """记录历史"""
        snapshot = ContextSnapshot(
            **{k: getattr(self.current_context, k) for k in self.current_context.__dataclass_fields__.keys()}
        )
        
        self.context_history.append(snapshot)
        
        if len(self.context_history) > self.max_history:
            self.context_history.pop(0)
    
    # ==================== 行为感知 ====================
    
    def record_typing_event(self):
        """记录打字事件"""
        self._typing_events.append(time.time())
        
        # 只保留最近1分钟的记录
        cutoff = time.time() - 60
        self._typing_events = [e for e in self._typing_events if e > cutoff]
        
        # 更新打字速度
        if len(self._typing_events) > 1:
            duration = self._typing_events[-1] - self._typing_events[0]
            if duration > 0:
                self.current_context.typing_speed = len(self._typing_events) / (duration / 60)
    
    def record_pause(self):
        """记录暂停"""
        self._pause_events.append(time.time())
        
        # 只保留最近1小时的记录
        cutoff = time.time() - 3600
        self._pause_events = [e for e in self._pause_events if e > cutoff]
        
        # 更新暂停频率
        hour_count = sum(1 for e in self._pause_events if e > time.time() - 3600)
        self.current_context.pause_frequency = hour_count / 60  # 每分钟暂停次数
    
    def update_word_count(self, word_count: int):
        """更新字数"""
        old_count = self.current_context.word_count
        self.current_context.word_count = word_count
        
        if old_count > 0 and word_count > old_count:
            # 计算修改率
            added = word_count - old_count
            # 简化：修改率 = 被删除的字 / 总字数变化
            self.current_context.correction_rate = 0.1  # 默认值
        
        # 更新目标进度
        if self.current_context.target_word_count > 0:
            self.current_context.progress_percent = min(
                word_count / self.current_context.target_word_count,
                1.0
            )
        
        self._update_phase()
    
    def detect_emotional_state(self, text: str) -> EmotionalState:
        """
        检测情感状态
        
        基于文本内容分析情感状态
        """
        # 简化实现
        positive_markers = ["开心", "兴奋", "灵感", "完美", "精彩"]
        negative_markers = ["困难", "痛苦", "瓶颈", "焦虑", "压力"]
        
        pos_count = sum(1 for m in positive_markers if m in text)
        neg_count = sum(1 for m in negative_markers if m in text)
        
        if pos_count > neg_count:
            return EmotionalState.INSPIRED
        elif neg_count > pos_count:
            return EmotionalState.STRESSED
        else:
            return EmotionalState.FOCUSED
    
    # ==================== 自适应策略 ====================
    
    def get_adaptive_strategy(self) -> AdaptiveStrategy:
        """
        获取自适应策略
        
        根据当前上下文返回最佳策略
        """
        strategy = AdaptiveStrategy()
        
        ctx = self.current_context
        
        # === AI干预策略 ===
        
        # 进度感知：开头多建议，结尾少打扰
        if ctx.phase == WritingPhase.START:
            strategy.suggestion_frequency = 0.7
            strategy.intervention_level = "aggressive"
        elif ctx.phase == WritingPhase.END:
            strategy.suggestion_frequency = 0.3
            strategy.intervention_level = "minimal"
        else:
            strategy.suggestion_frequency = 0.5
            strategy.intervention_level = "moderate"
        
        # 时间感知：深夜温和建议
        if ctx.time_of_day == TimeOfDay.LATE_NIGHT:
            strategy.suggestion_frequency *= 0.5
            strategy.intervention_level = "minimal"
        
        # 疲劳感知：疲惫时减少打扰
        if ctx.fatigue_level == FatigueLevel.EXHAUSTED:
            strategy.suggestion_frequency *= 0.3
            strategy.enable_background_processing = False
        elif ctx.fatigue_level == FatigueLevel.TIRED:
            strategy.suggestion_frequency *= 0.6
        
        # 情感感知：灵感迸发时减少打断
        if ctx.emotional_state == EmotionalState.INSPIRED:
            strategy.suggestion_frequency *= 0.2
            strategy.intervention_level = "minimal"
        elif ctx.emotional_state == EmotionalState.BLOCKED:
            strategy.suggestion_frequency *= 1.5
            strategy.enable_auto_complete = True
        
        # 环境感知：网络差时降低频率
        if ctx.network_status == "poor":
            strategy.suggestion_frequency *= 0.5
            strategy.enable_background_processing = False
        
        # === 界面策略 ===
        strategy.show_progress = ctx.phase != WritingPhase.MIDDLE or ctx.progress_percent > 0.1
        
        # === 提醒策略 ===
        strategy.break_reminder = (
            ctx.session_duration_minutes >= 45 and
            ctx.fatigue_level.value in ["tired", "exhausted"]
        )
        
        strategy.fatigue_warning = (
            ctx.fatigue_level == FatigueLevel.EXHAUSTED or
            (ctx.time_of_day == TimeOfDay.LATE_NIGHT and ctx.session_duration_minutes > 90)
        )
        
        return strategy
    
    def get_current_strategy_summary(self) -> dict:
        """获取策略摘要"""
        strategy = self.get_adaptive_strategy()
        
        return {
            "ai_intervention": {
                "suggestion_frequency": f"{strategy.suggestion_frequency:.0%}",
                "level": strategy.intervention_level,
            },
            "features": {
                "auto_save": strategy.enable_auto_save,
                "auto_complete": strategy.enable_auto_complete,
                "background_processing": strategy.enable_background_processing,
            },
            "reminders": {
                "break": strategy.break_reminder,
                "fatigue": strategy.fatigue_warning,
                "milestone": strategy.milestone_celebration,
            },
        }
    
    # ==================== 里程碑检测 ====================
    
    def check_milestones(self) -> list[dict]:
        """
        检查里程碑
        
        Returns:
            触发的里程碑列表
        """
        milestones = []
        progress = self.current_context.progress_percent
        word_count = self.current_context.word_count
        
        # 进度里程碑
        milestone_points = [
            (0.25, "25% 完成", "quarter"),
            (0.50, "50% 完成 - 已经走了一半！", "halfway"),
            (0.75, "75% 完成 - 胜利在望！", "three_quarter"),
            (0.90, "90% 完成 - 最后一搏！", "almost_done"),
            (1.00, "100% 完成 - 大功告成！", "complete"),
        ]
        
        for threshold, message, milestone_type in milestone_points:
            if progress >= threshold:
                # 检查是否已记录
                key = f"milestone_{milestone_type}"
                if not getattr(self.current_context, key, False):
                    milestones.append({
                        "type": milestone_type,
                        "message": message,
                        "progress": threshold,
                    })
                    setattr(self.current_context, key, True)
        
        # 字数里程碑
        word_milestones = [1000, 5000, 10000, 20000, 50000, 100000]
        for wm in word_milestones:
            if word_count >= wm:
                key = f"word_milestone_{wm}"
                if not getattr(self.current_context, key, False):
                    milestones.append({
                        "type": "word_count",
                        "message": f"达到 {wm:,} 字！",
                        "word_count": wm,
                    })
                    setattr(self.current_context, key, True)
        
        return milestones
    
    # ==================== 疲劳管理 ====================
    
    def should_take_break(self) -> tuple[bool, str]:
        """
        判断是否应该休息
        
        Returns:
            (是否休息, 建议)
        """
        strategy = self.get_adaptive_strategy()
        
        if not strategy.break_reminder:
            return False, ""
        
        if self.current_context.fatigue_level == FatigueLevel.EXHAUSTED:
            return True, "你已经连续创作超过2小时了，建议休息10-15分钟。"
        
        if self.current_context.session_duration_minutes >= 90:
            if self.current_context.time_of_day in [TimeOfDay.LATE_NIGHT, TimeOfDay.NIGHT]:
                return True, "夜深了，建议休息，明天再继续。"
        
        return False, ""
    
    def get_session_summary(self) -> dict:
        """获取会话摘要"""
        ctx = self.current_context
        
        return {
            "session_duration": f"{ctx.session_duration_minutes} 分钟",
            "words_written": ctx.word_count,
            "writing_speed": f"{ctx.typing_speed:.0f} 字/分钟" if ctx.typing_speed > 0 else "计算中...",
            "current_phase": ctx.phase.value,
            "fatigue_level": ctx.fatigue_level.value,
            "time_of_day": ctx.time_of_day.value,
            "emotional_state": ctx.emotional_state.value,
        }
    
    # ==================== 历史分析 ====================
    
    def analyze_productivity_pattern(self) -> dict:
        """
        分析生产力模式
        
        基于历史数据找出最佳写作时间和模式
        """
        if len(self.context_history) < 10:
            return {"message": "数据不足，需要更多写作历史"}
        
        # 分析最佳时段
        time_productivity = {}
        for snapshot in self.context_history:
            tod = snapshot.time_of_day.value
            if tod not in time_productivity:
                time_productivity[tod] = {"words": 0, "count": 0}
            time_productivity[tod]["words"] += snapshot.word_count
            time_productivity[tod]["count"] += 1
        
        best_time = max(
            time_productivity.items(),
            key=lambda x: x[1]["words"] / max(x[1]["count"], 1)
        )[0] if time_productivity else None
        
        return {
            "best_time_of_day": best_time,
            "time_productivity": time_productivity,
            "avg_session_length": sum(
                s.session_duration_minutes for s in self.context_history
            ) / len(self.context_history),
        }
    
    # ==================== 上下文导出 ====================
    
    def export_context(self) -> dict:
        """导出完整上下文"""
        return {
            "current": {
                k: getattr(self.current_context, k)
                for k in self.current_context.__dataclass_fields__.keys()
            },
            "strategy": self.get_current_strategy_summary(),
            "session": self.get_session_summary(),
            "history_length": len(self.context_history),
        }
