"""
技能执行引擎
===========

执行已加载的 Agent Skills
"""

import logging
import time
from typing import Dict, List, Optional, Any, Callable
from core.agent_skills.skill_registry import SkillRegistry, SkillManifest, SkillCategory

logger = logging.getLogger(__name__)


class SkillExecutor:
    """
    技能执行引擎
    
    负责执行已注册的技能工作流
    """
    
    def __init__(self, registry: SkillRegistry):
        self.registry = registry
        self._execution_history: List[Dict] = []
        self._custom_handlers: Dict[str, Callable] = {}
        
    def register_handler(self, skill_id: str, handler: Callable):
        """注册自定义技能处理器"""
        self._custom_handlers[skill_id] = handler
        logger.info(f"[SkillExecutor] 注册处理器: {skill_id}")
        
    async def execute_skill(
        self, 
        skill_id: str, 
        context: Optional[Dict[str, Any]] = None,
        callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        执行指定技能
        
        Args:
            skill_id: 技能 ID
            context: 执行上下文
            callback: 执行回调
            
        Returns:
            执行结果
        """
        start_time = time.time()
        
        # 获取技能
        manifest = self.registry.get_skill(skill_id)
        if not manifest:
            return {"error": f"技能不存在: {skill_id}", "success": False}
            
        if not manifest.enabled:
            return {"error": f"技能已禁用: {skill_id}", "success": False}
            
        # 获取技能内容
        content = self.registry.get_skill_content(skill_id)
        
        try:
            # 优先使用自定义处理器
            if skill_id in self._custom_handlers:
                handler = self._custom_handlers[skill_id]
                # 检查是否是异步函数
                import asyncio
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(context, content) if callable(handler) else handler
                elif callable(handler):
                    result = handler(context, content)
                else:
                    result = handler
            else:
                # 默认处理：返回技能内容
                result = {
                    "skill_id": skill_id,
                    "content": content,
                    "instructions": self._parse_instructions(content),
                }
            
            # 记录执行历史
            execution_time = time.time() - start_time
            self._execution_history.append({
                "skill_id": skill_id,
                "timestamp": time.time(),
                "execution_time": execution_time,
                "success": True,
            })
            
            # 调用回调
            if callback:
                callback(result)
                
            return {**result, "success": True, "execution_time": execution_time}
            
        except Exception as e:
            logger.error(f"[SkillExecutor] 技能执行失败 {skill_id}: {e}")
            return {"error": str(e), "success": False}
    
    def _parse_instructions(self, content: str) -> List[str]:
        """从技能内容中解析指令步骤"""
        instructions = []
        lines = content.split('\n')
        
        current_step = ""
        for line in lines:
            line = line.strip()
            # 匹配步骤标题 (### 1. xxx, ## Step 1: xxx, etc.)
            if line.startswith(('###', '##', '#')) and any(kw in line.lower() for kw in ['step', 'phase', '阶段', '步骤']):
                if current_step:
                    instructions.append(current_step)
                current_step = line.lstrip('#').strip()
            # 匹配有序列表
            elif line and line[0].isdigit() and '. ' in line[:5]:
                if current_step:
                    current_step += "\n" + line
                else:
                    instructions.append(line)
                    
        if current_step:
            instructions.append(current_step)
            
        return instructions if instructions else [content[:500]]
    
    def get_execution_history(self, limit: int = 20) -> List[Dict]:
        """获取执行历史"""
        return self._execution_history[-limit:]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取执行统计"""
        return {
            "total_executions": len(self._execution_history),
            "successful_executions": sum(1 for e in self._execution_history if e.get("success")),
            "avg_execution_time": (
                sum(e.get("execution_time", 0) for e in self._execution_history) / 
                max(len(self._execution_history), 1)
            ),
        }
