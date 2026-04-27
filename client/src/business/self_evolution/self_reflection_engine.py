"""
SelfReflectionEngine - 自我反思引擎

功能：智能体能够反思自己的表现，发现不足并改进。

工作流程：
1. 分析任务是否成功完成
2. 如果失败，分析失败原因
3. 如果发现能力缺失，触发工具创建流程
4. 如果发现性能问题，触发优化流程
5. 记录反思结果到日志
"""

import json
import asyncio
from typing import Any, Dict, List, Optional
from loguru import logger

from client.src.business.self_evolution.tool_missing_detector import ToolMissingDetector
from client.src.business.self_evolution.autonomous_tool_creator import AutonomousToolCreator


class SelfReflectionEngine:
    """
    自我反思引擎
    
    功能：智能体能够反思自己的表现，发现不足并改进。
    
    用法：
        engine = SelfReflectionEngine()
        await engine.reflect_on_task_execution(task, execution_result)
    """
    
    def __init__(self, llm_client=None):
        """
        初始化自我反思引擎
        
        Args:
            llm_client: LLM 客户端
        """
        self._llm = llm_client
        self._detector = ToolMissingDetector(llm_client)
        self._creator = AutonomousToolCreator(llm_client)
        self._logger = logger.bind(component="SelfReflectionEngine")
        self._reflection_history = []
    
    async def reflect_on_task_execution(
        self,
        task: str,
        execution_result: Any,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        反思任务执行情况
        
        执行流程：
        1. 分析任务是否成功完成
        2. 如果失败，分析失败原因
        3. 如果发现能力缺失，触发工具创建流程
        4. 如果发现性能问题，触发优化流程
        5. 记录反思结果到日志
        
        Args:
            task: 任务描述
            execution_result: 执行结果
            context: 上下文信息（可选）
            
        Returns:
            反思结果字典
        """
        self._logger.info(f"反思任务执行情况: {task[:50]}...")
        
        # 1. 让 LLM 进行反思
        reflection_prompt = self._build_reflection_prompt(task, execution_result, context)
        
        try:
            response = await self._call_llm(reflection_prompt)
            reflection_json = json.loads(response)
            
            self._logger.info(f"反思结果: success={reflection_json.get('success')}")
            
            # 2. 如果发现能力缺失，触发工具创建流程
            if reflection_json.get("missing_capabilities"):
                self._logger.info(f"发现能力缺失: {reflection_json['missing_capabilities']}")
                await self._handle_missing_capabilities(
                    task, reflection_json["missing_capabilities"]
                )
            
            # 3. 如果发现性能问题，触发优化流程
            if reflection_json.get("improvement_suggestions"):
                self._logger.info(f"发现改进建议: {reflection_json['improvement_suggestions']}")
                await self._handle_improvement_suggestions(
                    task, reflection_json["improvement_suggestions"]
                )
            
            # 4. 记录反思结果
            await self._log_reflection(task, execution_result, reflection_json)
            
            return reflection_json
            
        except Exception as e:
            self._logger.error(f"反思失败: {e}")
            import traceback
            self._logger.error(traceback.format_exc())
            return {}
    
    async def reflect_on_tool_execution(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_output: Any,
        error: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        反思工具执行情况
        
        Args:
            tool_name: 工具名称
            tool_input: 工具输入
            tool_output: 工具输出
            error: 错误信息（如果有）
            
        Returns:
            反思结果字典
        """
        self._logger.info(f"反思工具执行情况: {tool_name}")
        
        prompt = f"""
你是工具执行反思专家。

工具名称：{tool_name}
工具输入：{json.dumps(tool_input, ensure_ascii=False)}
工具输出：{tool_output}
错误信息：{error or "无"}

请反思：
1. 工具执行是否成功？
2. 如果失败，失败原因是什么？
3. 工具的设计是否合理？
4. 是否有改进空间？

请以 JSON 格式输出：
{{
    "success": true/false,
    "failure_reason": "...",
    "tool_design_issues": ["issue1", "issue2"],
    "improvement_suggestions": ["sug1", "sug2"]
}}
"""
        
        try:
            response = await self._call_llm(prompt)
            reflection = json.loads(response)
            
            # 如果有改进建议，触发工具优化流程
            if reflection.get("improvement_suggestions"):
                await self._improve_tool(tool_name, reflection)
            
            return reflection
            
        except Exception as e:
            self._logger.error(f"反思工具执行失败: {e}")
            return {}
    
    async def batch_reflect(self, task_execution_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        批量反思多个任务执行情况
        
        Args:
            task_execution_list: 任务执行列表，每个元素包含 task 和 execution_result
            
        Returns:
            反思结果列表
        """
        self._logger.info(f"批量反思 {len(task_execution_list)} 个任务")
        
        results = []
        
        for item in task_execution_list:
            task = item.get("task", "")
            execution_result = item.get("execution_result")
            context = item.get("context")
            
            reflection = await self.reflect_on_task_execution(task, execution_result, context)
            results.append(reflection)
        
        self._logger.info(f"批量反思完成，成功 {sum(1 for r in results if r.get('success'))} 个")
        
        return results
    
    def _build_reflection_prompt(
        self,
        task: str,
        execution_result: Any,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """构建反思提示词"""
        prompt = f"""
你是自我反思专家。

请反思以下任务执行情况：

任务：{task}
执行结果：{execution_result}
"""
        
        if context:
            prompt += f"\n上下文：{json.dumps(context, ensure_ascii=False)}\n"
        
        prompt += """
问题：
1. 任务是否成功完成？
2. 如果失败，失败原因是什么？
3. 是否缺少必要的工具或能力？
4. 是否有性能改进空间？
5. 下次如何做得更好？

请以 JSON 格式输出反思结果：
{{
    "success": true/false,
    "failure_reason": "...",
    "missing_capabilities": ["cap1", "cap2"],
    "improvement_suggestions": ["sug1", "sug2"],
    "next_time_how_to_do_better": "..."
}}
"""
        
        return prompt
    
    async def _handle_missing_capabilities(self, task: str, missing_caps: List[str]):
        """处理缺失的能力"""
        self._logger.info(f"处理缺失能力: {missing_caps}")
        
        for cap in missing_caps:
            try:
                self._logger.info(f"  创建工具: {cap}")
                success, file_path = await self._creator.create_tool(cap, f"自动创建的 {cap} 工具")
                
                if success:
                    self._logger.info(f"  工具创建成功: {file_path}")
                else:
                    self._logger.warning(f"  工具创建失败: {cap}")
                    
            except Exception as e:
                self._logger.error(f"  处理缺失能力失败: {e}")
    
    async def _handle_improvement_suggestions(self, task: str, suggestions: List[str]):
        """处理改进建议"""
        self._logger.info(f"处理改进建议: {suggestions}")
        
        # 这里可以实现具体的优化逻辑
        # 例如：优化工具代码、调整参数、改进算法等
        pass
    
    async def _improve_tool(self, tool_name: str, reflection: Dict[str, Any]):
        """改进工具"""
        self._logger.info(f"改进工具: {tool_name}")
        
        # 这里可以实现工具改进逻辑
        # 例如：重新生成工具代码、优化性能等
        pass
    
    async def _log_reflection(
        self,
        task: str,
        execution_result: Any,
        reflection: Dict[str, Any]
    ):
        """记录反思结果"""
        log_entry = {
            "task": task,
            "execution_result": str(execution_result)[:500],  # 限制长度
            "reflection": reflection,
            "timestamp": asyncio.get_event_loop().time()
        }
        
        self._reflection_history.append(log_entry)
        
        # 写入日志文件
        try:
            log_file = "reflection_log.json"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception as e:
            self._logger.error(f"写入反思日志失败: {e}")
    
    async def get_reflection_summary(self) -> Dict[str, Any]:
        """获取反思总结"""
        if not self._reflection_history:
            return {"message": "暂无反思记录"}
        
        total = len(self._reflection_history)
        success_count = sum(1 for h in self._reflection_history if h["reflection"].get("success"))
        
        return {
            "total_reflections": total,
            "success_count": success_count,
            "failure_count": total - success_count,
            "common_failure_reasons": self._analyze_common_failures(),
            "common_improvement_suggestions": self._analyze_common_improvements()
        }
    
    def _analyze_common_failures(self) -> List[str]:
        """分析常见失败原因"""
        failure_reasons = []
        for h in self._reflection_history:
            if not h["reflection"].get("success"):
                reason = h["reflection"].get("failure_reason")
                if reason:
                    failure_reasons.append(reason)
        
        # 返回最常见的 3 个失败原因
        from collections import Counter
        counter = Counter(failure_reasons)
        return [item[0] for item in counter.most_common(3)]
    
    def _analyze_common_improvements(self) -> List[str]:
        """分析常见改进建议"""
        improvements = []
        for h in self._reflection_history:
            suggestions = h["reflection"].get("improvement_suggestions", [])
            improvements.extend(suggestions)
        
        # 返回最常见的 3 个改进建议
        from collections import Counter
        counter = Counter(improvements)
        return [item[0] for item in counter.most_common(3)]
    
    async def _call_llm(self, prompt: str) -> str:
        """调用 LLM"""
        if self._llm is not None:
            return await self._llm.chat(prompt, model="qwen3.5:4b")
        else:
            try:
                from client.src.business.hermes_agent.llm_client import LLMClient
                llm = LLMClient()
                return await llm.chat(prompt, model="qwen3.5:4b")
            except Exception as e:
                self._logger.error(f"调用 LLM 失败: {e}")
                raise


async def test_self_reflection_engine():
    """测试自我反思引擎"""
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    
    # 配置 loguru
    logger.remove()
    logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)
    
    print("=" * 60)
    print("测试 SelfReflectionEngine")
    print("=" * 60)
    
    # 创建反思引擎
    engine = SelfReflectionEngine()
    
    # 测试反思任务执行
    print("\n测试反思任务执行...")
    task = "获取苹果公司的财报数据并分析"
    execution_result = "失败：缺少 financial_data_fetcher 工具"
    
    reflection = await engine.reflect_on_task_execution(task, execution_result)
    
    print(f"\n[结果] 反思完成:")
    print(f"  成功: {reflection.get('success')}")
    print(f"  失败原因: {reflection.get('failure_reason', '无')}")
    print(f"  缺失能力: {reflection.get('missing_capabilities', [])}")
    print(f"  改进建议: {reflection.get('improvement_suggestions', [])}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_self_reflection_engine())
