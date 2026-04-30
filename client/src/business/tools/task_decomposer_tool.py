"""
TaskDecomposerTool - 任务分解工具（BaseTool 包装器）

将现有的 task_decomposer 功能包装为标准的 BaseTool 子类
"""

from typing import Any, Dict, Optional
from loguru import logger

from business.tools.base_tool import BaseTool
from business.tools.tool_result import ToolResult
from business.task_decomposer import TaskDecomposer, DecomposedTask


class TaskDecomposerTool(BaseTool):
    """
    任务分解工具
    
    将复杂任务分解为多个子步骤，支持链式思考。
    
    示例：
        tool = TaskDecomposerTool()
        result = tool.execute(question="如何实现一个 Web 应用？")
    """
    
    def __init__(self):
        super().__init__(
            name="task_decomposer",
            description="将复杂任务分解为多个子步骤，支持链式思考和小模型推理",
            category="task_management",
            tags=["task", "decompose", "chain_of_thought", "planning"],
            version="1.0.0"
        )
        self._decomposer = TaskDecomposer()
        self._logger = logger.bind(tool="TaskDecomposerTool")
    
    def execute(
        self,
        question: str,
        context: Optional[Dict[str, Any]] = None,
        max_steps: int = 10
    ) -> ToolResult:
        """
        分解任务
        
        Args:
            question: 要分解的问题/任务
            context: 可选，任务上下文
            max_steps: 最大步骤数
            
        Returns:
            ToolResult 包含分解后的任务（DecomposedTask）
        """
        try:
            self._logger.info(f"分解任务: {question[:50]}...")
            
            # 调用现有的 TaskDecomposer
            decomposed = self._decomposer.decompose(
                question=question,
                context=context,
                max_steps=max_steps
            )
            
            # 转换为可序列化的字典
            result_data = {
                "task_id": decomposed.task_id,
                "original_question": decomposed.original_question,
                "total_steps": decomposed.total_steps,
                "completed_steps": decomposed.completed_steps,
                "progress": decomposed.progress,
                "steps": [step.to_dict() for step in decomposed.steps]
            }
            
            self._logger.info(f"任务分解完成: {decomposed.total_steps} 个步骤")
            
            return ToolResult.ok(
                data=result_data,
                message=f"成功分解任务为 {decomposed.total_steps} 个步骤"
            )
        
        except Exception as e:
            self._logger.exception(f"任务分解失败: {e}")
            return ToolResult.fail(error=str(e))
    
    def get_tool_definition(self) -> Dict[str, Any]:
        """获取工具定义（用于 LLM 调用）"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "要分解的复杂问题或任务"
                    },
                    "context": {
                        "type": "object",
                        "description": "可选的任务上下文"
                    },
                    "max_steps": {
                        "type": "integer",
                        "description": "最大步骤数，默认 10",
                        "default": 10
                    }
                },
                "required": ["question"]
            }
        }


# 便捷函数：直接执行任务分解（无需实例化工具）
def decompose_task(
    question: str,
    context: Optional[Dict[str, Any]] = None,
    max_steps: int = 10
) -> ToolResult:
    """
    便捷函数：分解任务
    
    Args:
        question: 要分解的问题/任务
        context: 可选，任务上下文
        max_steps: 最大步骤数
        
    Returns:
        ToolResult 包含分解后的任务
    """
    tool = TaskDecomposerTool()
    return tool.execute(question=question, context=context, max_steps=max_steps)


if __name__ == "__main__":
    # 简单测试
    tool = TaskDecomposerTool()
    result = tool.execute(question="如何实现登录功能？")
    
    if result.success:
        print(f"[PASS] 任务分解成功: {result.message}")
        print(f"  步骤数: {result.data['total_steps']}")
    else:
        print(f"[FAIL] 任务分解失败: {result.error}")


# =============================================================================
# Auto-Registration
# =============================================================================

_registration_done = False

def _auto_register():
    """自动注册工具到 ToolRegistry"""
    global _registration_done
    
    if _registration_done:
        return
    
    try:
        # 创建工具实例
        _tool_instance = TaskDecomposerTool()
        
        # 获取 ToolRegistry 单例
        from business.tools.tool_registry import ToolRegistry
        _registry = ToolRegistry.get_instance()
        
        # 注册工具
        success = _registry.register_tool(_tool_instance)
        
        if success:
            import loguru
            loguru.logger.info(f"Auto-registered: {_tool_instance.name}")
        else:
            import loguru
            loguru.logger.warning(f"Auto-registration failed (tool already exists): {_tool_instance.name}")
        
        _registration_done = True
        
    except Exception as e:
        import loguru
        loguru.logger.error(f"Auto-registration error: {e}")


# 执行自动注册
_auto_register()
