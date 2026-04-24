"""
动态指引系统

提供多级指引系统：
1. 简单高亮
2. 分步指引
3. 交互式引导
"""

import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum
from .models import Guide, GuideStep, GuideLevel, OperationPath
from core.logger import get_logger
logger = get_logger('smart_assistant.guide_system')



class GuideState(Enum):
    """指引状态"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABORTED = "aborted"


class GuideStepResult(Enum):
    """步骤执行结果"""
    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class GuideStepExecution:
    """指引步骤执行记录"""
    step_number: int
    start_time: float
    end_time: Optional[float] = None
    result: GuideStepResult = GuideStepResult.SUCCESS
    error_message: str = ""


@dataclass
class GuideExecution:
    """指引执行记录"""
    guide_id: str
    guide_name: str
    start_time: float
    end_time: Optional[float] = None
    current_step: int = 0
    state: GuideState = GuideState.IDLE
    step_executions: List[GuideStepExecution] = None
    completion_rate: float = 0.0
    
    def __post_init__(self):
        if self.step_executions is None:
            self.step_executions = []


class GuideSystem:
    """
    动态指引系统
    
    提供多级指引功能：
    - 简单高亮
    - 分步指引
    - 交互式引导
    """
    
    def __init__(self):
        self.current_guide: Optional[Guide] = None
        self.current_execution: Optional[GuideExecution] = None
        self.callbacks: Dict[str, List[Callable]] = {
            "on_step_start": [],
            "on_step_complete": [],
            "on_step_error": [],
            "on_guide_complete": [],
            "on_guide_abort": [],
            "on_highlight": [],
            "on_navigate": []
        }
        
        # 指引历史
        self.execution_history: List[GuideExecution] = []
    
    # ==================== 回调管理 ====================
    
    def register_callback(self, event: str, callback: Callable):
        """注册事件回调"""
        if event in self.callbacks:
            self.callbacks[event].append(callback)
    
    def _trigger_callback(self, event: str, **kwargs):
        """触发回调"""
        for callback in self.callbacks.get(event, []):
            try:
                callback(**kwargs)
            except Exception as e:
                logger.info(f"回调执行失败: {e}")
    
    # ==================== 指引执行 ====================
    
    def start_guide(self, guide: Guide) -> bool:
        """
        开始指引
        
        Args:
            guide: Guide对象
            
        Returns:
            是否成功开始
        """
        if self.current_guide and self.current_execution:
            if self.current_execution.state == GuideState.RUNNING:
                logger.info("已有指引正在运行，请先结束")
                return False
        
        self.current_guide = guide
        self.current_execution = GuideExecution(
            guide_id=guide.guide_id,
            guide_name=guide.name,
            start_time=time.time(),
            state=GuideState.RUNNING
        )
        
        # 触发回调
        self._trigger_callback("on_step_start", 
                               guide=guide, 
                               step=guide.steps[0] if guide.steps else None,
                               step_number=1)
        
        return True
    
    def pause_guide(self):
        """暂停指引"""
        if self.current_execution:
            self.current_execution.state = GuideState.PAUSED
    
    def resume_guide(self):
        """恢复指引"""
        if self.current_execution:
            self.current_execution.state = GuideState.RUNNING
            self._trigger_callback("on_step_start",
                                  guide=self.current_guide,
                                  step=self.current_guide.steps[self.current_execution.current_step],
                                  step_number=self.current_execution.current_step + 1)
    
    def abort_guide(self, reason: str = ""):
        """中止指引"""
        if self.current_execution:
            self.current_execution.state = GuideState.ABORTED
            self.current_execution.end_time = time.time()
            self.execution_history.append(self.current_execution)
            
            self._trigger_callback("on_guide_abort",
                                 guide=self.current_guide,
                                 execution=self.current_execution,
                                 reason=reason)
            
            self.current_guide = None
            self.current_execution = None
    
    def complete_guide(self):
        """完成指引"""
        if self.current_execution:
            self.current_execution.state = GuideState.COMPLETED
            self.current_execution.end_time = time.time()
            self.current_execution.completion_rate = 1.0
            
            # 执行完成动作
            if self.current_guide:
                for action in self.current_guide.completion_actions:
                    self._execute_action(action)
            
            self._trigger_callback("on_guide_complete",
                                 guide=self.current_guide,
                                 execution=self.current_execution)
            
            self.execution_history.append(self.current_execution)
            self.current_guide = None
            self.current_execution = None
    
    # ==================== 步骤控制 ====================
    
    def next_step(self, success: bool = True, error: str = "") -> Optional[GuideStep]:
        """
        进入下一步
        
        Args:
            success: 当前步骤是否成功
            error: 错误信息（如果失败）
            
        Returns:
            下一个步骤或None
        """
        if not self.current_guide or not self.current_execution:
            return None
        
        # 记录当前步骤结果
        current_step_num = self.current_execution.current_step
        execution = GuideStepExecution(
            step_number=current_step_num + 1,
            start_time=time.time() - 60 if self.current_execution.step_executions else time.time(),
            end_time=time.time(),
            result=GuideStepResult.SUCCESS if success else GuideStepResult.FAILED,
            error_message=error
        )
        self.current_execution.step_executions.append(execution)
        
        # 触发步骤完成回调
        self._trigger_callback("on_step_complete",
                             guide=self.current_guide,
                             step=self.current_guide.steps[current_step_num],
                             step_number=current_step_num + 1,
                             success=success)
        
        if not success:
            self._trigger_callback("on_step_error",
                                 guide=self.current_guide,
                                 step=self.current_guide.steps[current_step_num],
                                 step_number=current_step_num + 1,
                                 error=error)
        
        # 更新进度
        self.current_execution.current_step += 1
        self.current_execution.completion_rate = self.current_execution.current_step / len(self.current_guide.steps)
        
        # 检查是否完成
        if self.current_execution.current_step >= len(self.current_guide.steps):
            self.complete_guide()
            return None
        
        # 返回下一步
        next_step = self.current_guide.steps[self.current_execution.current_step]
        self._trigger_callback("on_step_start",
                             guide=self.current_guide,
                             step=next_step,
                             step_number=self.current_execution.current_step + 1)
        
        return next_step
    
    def skip_step(self) -> Optional[GuideStep]:
        """跳过当前步骤"""
        if not self.current_guide or not self.current_execution:
            return None
        
        # 记录跳过
        execution = GuideStepExecution(
            step_number=self.current_execution.current_step + 1,
            start_time=time.time(),
            end_time=time.time(),
            result=GuideStepResult.SKIPPED
        )
        self.current_execution.step_executions.append(execution)
        
        return self.next_step(success=True)
    
    def go_to_step(self, step_number: int) -> Optional[GuideStep]:
        """跳转到指定步骤"""
        if not self.current_guide or not self.current_execution:
            return None
        
        if step_number < 0 or step_number >= len(self.current_guide.steps):
            return None
        
        self.current_execution.current_step = step_number
        self.current_execution.completion_rate = step_number / len(self.current_guide.steps)
        
        step = self.current_guide.steps[step_number]
        self._trigger_callback("on_step_start",
                             guide=self.current_guide,
                             step=step,
                             step_number=step_number + 1)
        
        return step
    
    # ==================== 状态查询 ====================
    
    def get_current_step(self) -> Optional[GuideStep]:
        """获取当前步骤"""
        if not self.current_guide or not self.current_execution:
            return None
        
        if self.current_execution.current_step >= len(self.current_guide.steps):
            return None
        
        return self.current_guide.steps[self.current_execution.current_step]
    
    def get_progress(self) -> Dict[str, Any]:
        """获取进度信息"""
        if not self.current_guide or not self.current_execution:
            return {
                "running": False,
                "guide_id": "",
                "guide_name": "",
                "current_step": 0,
                "total_steps": 0,
                "completion_rate": 0.0
            }
        
        return {
            "running": self.current_execution.state == GuideState.RUNNING,
            "guide_id": self.current_guide.guide_id,
            "guide_name": self.current_guide.name,
            "current_step": self.current_execution.current_step + 1,
            "total_steps": len(self.current_guide.steps),
            "completion_rate": self.current_execution.completion_rate,
            "state": self.current_execution.state.value
        }
    
    def is_running(self) -> bool:
        """检查是否有指引正在运行"""
        return (self.current_guide is not None and 
                self.current_execution is not None and
                self.current_execution.state == GuideState.RUNNING)
    
    # ==================== 动作执行 ====================
    
    def _execute_action(self, action: str):
        """执行动作"""
        # 解析动作类型
        if action.startswith("highlight:"):
            component_id = action.split(":", 1)[1]
            self._trigger_callback("on_highlight", component_id=component_id)
        
        elif action.startswith("navigate:"):
            page_id = action.split(":", 1)[1]
            self._trigger_callback("on_navigate", page_id=page_id)
        
        elif action.startswith("message:"):
            message = action.split(":", 1)[1]
            logger.info(f"指引消息: {message}")
    
    # ==================== 指引渲染 ====================
    
    def render_step_card(self, step: GuideStep) -> str:
        """
        渲染步骤卡片
        
        Returns:
            Markdown格式的步骤卡片
        """
        card = f"""
## 步骤 {step.step_number}

{step.instruction}

"""
        if step.tips:
            card += f"> 💡 **提示**: {step.tips}\n"
        
        if step.warning:
            card += f"> ⚠️ **注意**: {step.warning}\n"
        
        return card
    
    def render_guide_progress(self) -> str:
        """渲染指引进度"""
        if not self.current_guide or not self.current_execution:
            return ""
        
        progress = self.current_execution.completion_rate
        current = self.current_execution.current_step + 1
        total = len(self.current_guide.steps)
        
        # 进度条
        bar_length = 30
        filled = int(bar_length * progress)
        bar = "█" * filled + "░" * (bar_length - filled)
        
        text = f"""
### 🎯 {self.current_guide.name}

**进度**: [{bar}] {int(progress * 100)}%

**当前**: 步骤 {current}/{total}

"""
        return text
    
    def render_full_guide(self, guide: Guide) -> str:
        """渲染完整指引"""
        text = f"""
# 📖 {guide.name}

{guide.description}

**指引级别**: {'🟢 简单' if guide.level == GuideLevel.SIMPLE else '🟡 分步' if guide.level == GuideLevel.STEP else '🔵 交互式'}

---
"""
        
        for i, step in enumerate(guide.steps, 1):
            text += f"\n### 步骤 {i}\n\n"
            text += f"{step.instruction}\n\n"
            
            if step.tips:
                text += f"> 💡 {step.tips}\n"
            
            if step.warning:
                text += f"> ⚠️ {step.warning}\n"
        
        text += "\n---\n"
        text += f"**前置条件**: {', '.join(guide.prerequisites) if guide.prerequisites else '无'}\n"
        text += f"**相关标签**: {', '.join(guide.tags) if guide.tags else '无'}\n"
        
        return text
    
    # ==================== 操作路径转指引 ====================
    
    def create_guide_from_path(self, path: OperationPath) -> Guide:
        """从操作路径创建指引"""
        guide_id = f"guide_{path.path_id}"
        
        steps = []
        for i, operation in enumerate(path.steps, 1):
            step = GuideStep(
                step_number=i,
                page_id=operation.page_id,
                component_id=operation.component_id,
                instruction=operation.description,
                highlight=True,
                animation="pulse",
                expected_result=operation.expected_result,
                tips=operation.warning if operation.warning else ""
            )
            steps.append(step)
        
        guide = Guide(
            guide_id=guide_id,
            name=f"指引: {path.name}",
            description=path.description,
            level=GuideLevel.INTERACTIVE,
            target_page=path.to_page,
            steps=steps,
            prerequisites=path.prerequisites,
            tags=path.tags
        )
        
        return guide
    
    # ==================== 历史统计 ====================
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """获取执行统计"""
        if not self.execution_history:
            return {
                "total_guides": 0,
                "completed": 0,
                "aborted": 0,
                "avg_completion_rate": 0.0,
                "avg_time": 0.0
            }
        
        total = len(self.execution_history)
        completed = sum(1 for e in self.execution_history if e.state == GuideState.COMPLETED)
        aborted = sum(1 for e in self.execution_history if e.state == GuideState.ABORTED)
        
        completion_rates = [e.completion_rate for e in self.execution_history]
        times = [e.end_time - e.start_time for e in self.execution_history if e.end_time]
        
        return {
            "total_guides": total,
            "completed": completed,
            "aborted": aborted,
            "avg_completion_rate": sum(completion_rates) / len(completion_rates) if completion_rates else 0,
            "avg_time": sum(times) / len(times) if times else 0
        }


# 单例
_guide_system_instance = None

def get_guide_system() -> GuideSystem:
    """获取指引系统单例"""
    global _guide_system_instance
    if _guide_system_instance is None:
        _guide_system_instance = GuideSystem()
    return _guide_system_instance
