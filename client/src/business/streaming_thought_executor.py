"""
流式思维执行器 - 共脑系统的基础

核心概念：
- 传统方式：思考完成 → 输出完整回答 → 执行动作
- 流式思维：思考开始 → 实时输出思考过程 → 同时执行已确定的动作

这是"共脑系统"的核心组件，让用户实时看到AI的思考过程，
并在思考过程中就开始执行已确定的动作。
"""

import asyncio
import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, AsyncIterator, Callable
from enum import Enum

logger = logging.getLogger(__name__)


# ============= 数据类型 =============

class ChunkType(Enum):
    """流式输出块类型"""
    THOUGHT = "thought"         # 思考片段
    ACTION = "action"           # 动作执行片段
    RESULT = "result"           # 结果片段
    FINAL = "final"             # 最终总结
    ERROR = "error"             # 错误


@dataclass
class ThoughtChunk:
    """思考片段"""
    content: str
    confidence: float = 1.0    # 置信度 (0-1)
    is_final: bool = False      # 是否是最终思考
    
    def to_dict(self) -> dict:
        return {
            "type": ChunkType.THOUGHT.value,
            "content": self.content,
            "confidence": self.confidence,
            "is_final": self.is_final,
        }


@dataclass
class ActionChunk:
    """动作执行片段"""
    action_type: str
    action_params: Dict[str, Any]
    status: str                # "pending", "running", "success", "failed"
    result: Optional[str] = None
    error: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "type": ChunkType.ACTION.value,
            "action_type": self.action_type,
            "action_params": self.action_params,
            "status": self.status,
            "result": self.result,
            "error": self.error,
        }


@dataclass
class ResultChunk:
    """结果片段"""
    content: str
    data: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> dict:
        return {
            "type": ChunkType.RESULT.value,
            "content": self.content,
            "data": self.data,
        }


@dataclass
class FinalChunk:
    """最终总结片段"""
    summary: str
    full_result: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> dict:
        return {
            "type": ChunkType.FINAL.value,
            "summary": self.summary,
            "full_result": self.full_result,
        }


@dataclass
class ErrorChunk:
    """错误片段"""
    error: str
    recoverable: bool = True
    
    def to_dict(self) -> dict:
        return {
            "type": ChunkType.ERROR.value,
            "error": self.error,
            "recoverable": self.recoverable,
        }



# ============= 置信度评估引擎 =============

class ConfidenceEngine:
    """
    置信度评估引擎
    对思考片段、动作、结果进行置信度评分（0-1）
    """
    
    def evaluate_thought(
        self,
        thought: str,
        context: Optional[Dict[str, Any]] = None,
        history: Optional[List[str]] = None,
    ) -> float:
        """
        评估思考片段的置信度（0-1）
        
        评分因素：
        - 长度（越长越自信）
        - 确定性关键词（"确定"/"一定" vs "可能"/"也许"）
        - 历史一致性（与历史对话的关键词重叠度）
        """
        score = 0.5  # 基础分
        
        # 长度加分
        if len(thought) > 200:
            score += 0.2
        elif len(thought) > 80:
            score += 0.1
        
        # 确定性关键词
        high_conf = ["确定", "一定", "必然", "毫无疑问", "显然"]
        mid_conf = ["应该", "可能", "也许", "大概", "估计"]
        low_conf = ["不确定", "不清楚", "不知道", "可能不对"]
        
        if any(k in thought for k in high_conf):
            score += 0.2
        elif any(k in thought for k in mid_conf):
            score += 0.05
        elif any(k in thought for k in low_conf):
            score -= 0.3
        
        # 历史一致性（简单重叠检查）
        if history and len(history) > 0:
            history_text = " ".join(history[-3:])  # 只看最近 3 轮
            tokens = set(thought.split())
            history_tokens = set(history_text.split())
            overlap = len(tokens & history_tokens)
            if overlap > 5:
                score += 0.1
            elif overlap == 0 and len(thought) > 50:
                score -= 0.1  # 与历史完全无关，稍微降分
        
        return min(max(score, 0.0), 1.0)
    
    def evaluate_action(
        self,
        action_type: str,
        params: Dict[str, Any],
    ) -> float:
        """
        评估动作的置信度（0-1）
        
        评分因素：
        - 参数完整性
        - 动作类型是否常见
        """
        score = 0.5
        
        if params and len(params) > 0:
            score += 0.3
        
        common_actions = ["search", "calculate", "read_file", "write_file", "translate", "summarize"]
        if action_type in common_actions:
            score += 0.2
        
        return min(max(score, 0.0), 1.0)
    

# ============= 思考解析器 =============

class ThoughtParser:
    """
    思考解析器
    
    从LLM的流式输出中解析出：
    1. 思考片段
    2. 已确定的动作
    3. 最终答案
    """
    
    # 动作标记模式（扩展版）
    ACTION_PATTERNS = [
        # 原有模式
        r"ACTION:\s*(\w+)\s*\((.*?)\)",          # ACTION: search(query="xxx")
        r"执行动作:\s*(\w+)\s*\((.*?)\)",      # 执行动作: search(query="xxx")
        r"```action\s*\n(.*?)\n```",               # ```action\nsearch(...)\n```
        # 新增模式（中文/简洁风格）
        r"执行[:：]\s*(\w+)\s*\((.*?)\)",        # 执行：search(query="xxx") / 执行:search(...)
        r"动作[:：]\s*(\w+)\s*\((.*?)\)",          # 动作：search(...) / 动作:search(...)
        r"调用[:：]\s*(\w+)\s*\((.*?)\)",          # 调用：search(...) / 调用:search(...)
        r"→\s*(\w+)\s*\((.*?)\)",                    # → search(query="xxx")
        r"➡️\s*(\w+)\s*\((.*?)\)",                  # ➡️ search(...)
        # 自然语言动作标记
        r"我需要(调用|执行|查询|计算|搜索|查看)\s*[:：]?\s*(.+)",  # 我需要调用: search ...
        r"应该(调用|执行|查询|计算|搜索)\s*[:：]?\s*(.+)", # 应该执行：search ...
    ]
    
    def __init__(self):
        self.buffer = ""
        self.actions_found = []
    
    def parse(self, text_chunk: str) -> Dict[str, Any]:
        """
        解析文本片段
        
        Returns:
            {
                "thought": "思考文本",
                "actions": [{"type": "search", "params": {...}}],
                "is_final": False,
            }
        """
        self.buffer += text_chunk
        
        result = {
            "thought": text_chunk,  # 默认：整个chunk都是思考
            "actions": [],
            "is_final": False,
        }
        
        # 检测动作标记
        for pattern in self.ACTION_PATTERNS:
            matches = re.finditer(pattern, self.buffer, re.DOTALL)
            for match in matches:
                action_type = match.group(1)
                action_params_str = match.group(2) if len(match.groups()) > 1 else ""
                
                # 解析参数（简单解析）
                params = self._parse_action_params(action_params_str)
                
                result["actions"].append({
                    "type": action_type,
                    "params": params,
                })
                
                # 从buffer中移除已解析的动作
                self.buffer = self.buffer.replace(match.group(0), "")
        
        # 检测最终答案标记
        if "FINAL:" in self.buffer or "最终答案:" in self.buffer:
            result["is_final"] = True
        
        return result
    
    def _parse_action_params(self, params_str: str) -> Dict[str, Any]:
        """解析动作参数（简化版）"""
        params = {}
        
        # 简单解析 key="value" 或 key=value
        kv_pattern = r'(\w+)\s*=\s*("([^"]*)"|(\d+)|([^,]+))'
        matches = re.finditer(kv_pattern, params_str)
        
        for match in matches:
            key = match.group(1)
            value = match.group(3) or match.group(4) or match.group(5)
            params[key] = value.strip()
        
        return params
    
    def reset(self):
        """重置解析器"""
        self.buffer = ""
        self.actions_found = []


# ============= 流式思维执行器 =============

class StreamingThoughtExecutor:
    """
    流式思维执行器 - 共脑系统基础
    
    工作流程：
    1. 接收用户意图
    2. 调用LLM流式API，获取思考过程
    3. 实时输出思考片段（ ThoughtChunk）
    4. 当解析出已确定的动作时，立即执行（ActionChunk）
    5. 思考完成后，输出最终总结（FinalChunk）
    """
    
    def __init__(self, model_router, action_executor: Optional[Callable] = None):
        """
        初始化执行器
        
        Args:
            model_router: 模型路由器（GlobalModelRouter实例）
            action_executor: 动作执行函数，签名为 async (action_type, params) -> result
        """
        self.model_router = model_router
        self.action_executor = action_executor
        self.thought_parser = ThoughtParser()
        self.confidence_engine = ConfidenceEngine()

        logger.info("StreamingThoughtExecutor 初始化完成")
    
    async def execute_stream(
        self,
        intent: str,
        context: Dict[str, Any] = None,
        history: Optional[List[str]] = None,
    ) -> AsyncIterator[Dict]:
        """
        流式执行：思考和执行并行
        
        Args:
            intent: 用户意图
            context: 上下文信息
            history: 历史对话列表（用于置信度评估）
        
        Yields:
            各种Chunk的字典表示
        """
        context = context or {}
        history = history or []
        self.thought_parser.reset()
        thought_history: List[str] = []  # 收集本次思考历史
        
        logger.info(f"开始流式执行: intent='{intent}'")
        
        # 构建提示词
        prompt = self._build_prompt(intent, context)
        system_prompt = self._build_system_prompt()
        
        # 用于跟踪已执行的动作（避免重复执行）
        executed_actions = set()
        
        try:
            # 调用LLM流式API
            async for text_chunk in self.model_router.call_model_stream(
                capability="reasoning",  # 使用推理能力
                prompt=prompt,
                system_prompt=system_prompt,
            ):
                if not text_chunk:
                    continue
                
                # 解析思考片段
                parsed = self.thought_parser.parse(text_chunk)
                
                # 1. 输出思考片段
                thought_content = parsed["thought"]
                thought_history.append(thought_content)
                
                # 评估置信度
                confidence = self.confidence_engine.evaluate_thought(
                    thought=thought_content,
                    context=context,
                    history=thought_history[:-1],  # 不含当前
                )
                
                yield ThoughtChunk(
                    content=thought_content,
                    confidence=confidence,
                    is_final=parsed["is_final"],
                ).to_dict()
                
                # 2. 执行已确定的动作
                for action in parsed["actions"]:
                    action_key = f"{action['type']}:{json.dumps(action['params'], sort_keys=True)}"
                    
                    if action_key not in executed_actions:
                        executed_actions.add(action_key)
                        
                        # 立即执行动作（不等思考完成）
                        yield ActionChunk(
                            action_type=action["type"],
                            action_params=action["params"],
                            status="running",
                        ).to_dict()
                        
                        try:
                            result = await self._execute_action(action["type"], action["params"])
                            
                            yield ActionChunk(
                                action_type=action["type"],
                                action_params=action["params"],
                                status="success",
                                result=result,
                            ).to_dict()
                        
                        except Exception as e:
                            logger.error(f"动作执行失败: {action['type']}, 错误: {e}")
                            
                            yield ActionChunk(
                                action_type=action["type"],
                                action_params=action["params"],
                                status="failed",
                                error=str(e),
                            ).to_dict()
                
                # 3. 如果思考已完成，输出最终总结
                if parsed["is_final"]:
                    yield FinalChunk(
                        summary="思考完成",
                        full_result={"executed_actions": list(executed_actions)},
                    ).to_dict()
                    break
        
        except Exception as e:
            logger.error(f"流式执行异常: {e}")
            yield ErrorChunk(error=str(e)).to_dict()
    
    async def execute_with_thought(self, intent: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        执行并收集完整结果（非流式）
        
        适用于不需要实时输出的场景
        """
        context = context or {}
        thoughts = []
        actions = []
        final_result = None
        errors = []
        
        async for chunk in self.execute_stream(intent, context):
            chunk_type = chunk.get("type")
            
            if chunk_type == ChunkType.THOUGHT.value:
                thoughts.append(chunk["content"])
            
            elif chunk_type == ChunkType.ACTION.value:
                actions.append(chunk)
            
            elif chunk_type == ChunkType.FINAL.value:
                final_result = chunk
            
            elif chunk_type == ChunkType.ERROR.value:
                errors.append(chunk["error"])
        
        return {
            "thoughts": thoughts,
            "actions": actions,
            "final_result": final_result,
            "errors": errors,
            "full_thought": "".join(thoughts),
        }
    
    def _build_prompt(self, intent: str, context: Dict[str, Any]) -> str:
        """构建提示词"""
        prompt_parts = []
        
        # 上下文
        if context:
            prompt_parts.append("上下文信息：")
            for key, value in context.items():
                prompt_parts.append(f"- {key}: {value}")
            prompt_parts.append("")
        
        # 用户意图
        prompt_parts.append(f"用户意图: {intent}")
        prompt_parts.append("")
        
        # 输出格式要求
        prompt_parts.append("请按以下格式输出：")
        prompt_parts.append("1. 先输出你的思考过程")
        prompt_parts.append("2. 当确定需要执行某个动作时，输出 ACTION: action_type(params)")
        prompt_parts.append("3. 思考完成后，输出 FINAL: 最终答案")
        prompt_parts.append("")
        prompt_parts.append("示例：")
        prompt_parts.append("思考：用户需要查询天气，我应该调用weather查询。")
        prompt_parts.append("ACTION: weather(city=\"北京\")")
        prompt_parts.append("思考：已获取天气信息，可以回答用户。")
        prompt_parts.append("FINAL: 北京今天晴天，温度20-25度。")
        
        return "\n".join(prompt_parts)
    
    def _build_system_prompt(self) -> str:
        """构建系统提示"""
        return """你是一个能够边思考边执行的AI助手。

规则：
1. 先输出思考过程，让用户看到你的思路
2. 当确定需要执行某个动作时，立即输出 ACTION: action_type(params)
3. 支持的动作用例：
   - ACTION: search(query="人工智能最新进展")
   - ACTION: calculate(expression="2+2")
   - ACTION: read_file(path="/path/to/file")
4. 思考完成后，输出 FINAL: 最终答案
5. 保持思考过程自然、连贯
"""
    
    async def _execute_action(self, action_type: str, params: Dict[str, Any]) -> str:
        """执行动作"""
        if self.action_executor and callable(self.action_executor):
            return await self.action_executor(action_type, params)
        else:
            # 默认：返回模拟结果
            logger.warning(f"未配置动作执行器，返回模拟结果: {action_type}")
            return f"[模拟结果] 执行动作 {action_type}, 参数: {params}"


# ============= 示例动作执行器 =============

class DefaultActionExecutor:
    """默认动作执行器（示例）"""
    
    async def execute(self, action_type: str, params: Dict[str, Any]) -> str:
        """执行动作"""
        if action_type == "search":
            query = params.get("query", "")
            return await self._search(query)
        
        elif action_type == "calculate":
            expression = params.get("expression", "")
            return self._calculate(expression)
        
        elif action_type == "read_file":
            path = params.get("path", "")
            return self._read_file(path)
        
        else:
            return f"未知动作类型: {action_type}"
    
    async def _search(self, query: str) -> str:
        """模拟搜索"""
        await asyncio.sleep(0.5)  # 模拟网络延迟
        return f"搜索结果：找到关于 '{query}' 的10条相关信息"
    
    def _calculate(self, expression: str) -> str:
        """计算表达式"""
        try:
            result = eval(expression)
            return f"计算结果: {expression} = {result}"
        except Exception as e:
            return f"计算失败: {e}"
    
    def _read_file(self, path: str) -> str:
        """读取文件（模拟）"""
        return f"文件内容：{path} 的前100个字符..."


# ============= 工厂函数 =============

def create_streaming_executor(model_router, action_executor: Optional[Callable] = None):
    """创建流式思维执行器"""
    if action_executor is None:
        action_executor = DefaultActionExecutor().execute
    
    return StreamingThoughtExecutor(model_router, action_executor)


# ============= 使用示例 =============

async def example_usage():
    """使用示例"""
    from business.global_model_router import get_global_router
    
    # 1. 获取全局路由器
    router = get_global_router()
    
    # 2. 创建流式执行器
    executor = create_streaming_executor(router)
    
    # 3. 流式执行
    intent = "帮我查一下今天的天气，然后计算2+2，最后总结"
    context = {"user_location": "北京"}
    
    print("开始流式执行...\n")
    
    async for chunk in executor.execute_stream(intent, context):
        chunk_type = chunk.get("type")
        
        if chunk_type == "thought":
            print(f"[思考] {chunk['content']}")
        
        elif chunk_type == "action":
            if chunk["status"] == "running":
                print(f"[动作] 执行 {chunk['action_type']}...")
            elif chunk["status"] == "success":
                print(f"[动作] 完成！结果: {chunk['result']}")
        
        elif chunk_type == "final":
            print(f"\n[完成] {chunk['summary']}")
    
    print("\n\n--- 非流式执行（收集完整结果）---\n")
    
    result = await executor.execute_with_thought(intent, context)
    print(f"完整思考过程:\n{result['full_thought']}")
    print(f"\n执行的动作: {len(result['actions'])} 个")
    print(f"错误数: {len(result['errors'])}")


if __name__ == "__main__":
    asyncio.run(example_usage())
