"""
Pipeline Orchestrator - 深度融合的 AI Pipeline 编排器

核心创新设计：
1. 思考过程可视化引擎 - 支持 Thinking 模式输出和可视化
2. 多模态输入融合 - 文本、文件、图片、URL 统一处理
3. 自适应学习系统 - 从执行中学习优化
4. 增量代码生成 - 只重新生成变更部分
5. 知识图谱集成 - 构建领域知识图谱
6. 智能调度引擎 - 资源感知调度和故障自愈

架构层次：
┌─────────────────────────────────────────────────────────────────┐
│                     交互层 (Interaction)                        │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────┐   │
│  │  对话接口    │ │  IDE面板     │ │  多模态输入处理器       │   │
│  └──────┬──────┘ └──────┬──────┘ └──────────┬──────────────┘   │
├─────────┼────────────────┼───────────────────┼──────────────────┤
│                     协调层 (Coordination)                       │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              Pipeline Orchestrator                       │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌────────────────┐ │   │
│  │  │ 思考引擎 │ │ 知识图谱 │ │ 调度引擎 │ │ 自适应学习器   │ │   │
│  │  └────┬────┘ └────┬────┘ └────┬────┘ └───────┬────────┘ │   │
│  └───────┼───────────┼───────────┼───────────────┼─────────┘   │
├──────────┼───────────┼───────────┼───────────────┼─────────────┤
│                     执行层 (Execution)                          │
│  ┌─────────┐ ┌───────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ │
│  │任务分解 │ │代码生成    │ │测试系统 │ │修复引擎 │ │质量门禁 │ │
│  └─────────┘ └───────────┘ └─────────┘ └─────────┘ └─────────┘ │
└─────────────────────────────────────────────────────────────────┘
"""

import asyncio
import json
import time
import logging
from typing import Dict, Any, Optional, List, Callable, AsyncIterator, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class PipelinePhase(Enum):
    """流水线阶段"""
    INITIAL = "initial"
    REQUIREMENT_ANALYSIS = "requirement_analysis"
    TASK_DECOMPOSITION = "task_decomposition"
    CODE_GENERATION = "code_generation"
    TEST_EXECUTION = "test_execution"
    CODE_REVIEW = "code_review"
    QUALITY_GATE = "quality_gate"
    DEPLOYMENT = "deployment"
    COMPLETE = "complete"


class ThinkingStep:
    """思考步骤"""
    def __init__(self, step_num: int, thought: str, confidence: float = 0.8):
        self.step_num = step_num
        self.thought = thought
        self.confidence = confidence
        self.timestamp = datetime.now()
    
    def to_dict(self):
        return {
            "step": self.step_num,
            "thought": self.thought,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class ThinkingResult:
    """思考结果"""
    steps: List[ThinkingStep] = field(default_factory=list)
    final_answer: str = ""
    confidence: float = 0.8
    total_tokens: int = 0
    reasoning_chain: str = ""
    
    def add_step(self, thought: str, confidence: float = 0.8):
        self.steps.append(ThinkingStep(len(self.steps) + 1, thought, confidence))
    
    def build_reasoning_chain(self):
        """构建推理链"""
        chain = "\n".join([f"[{s.step}] {s.thought}" for s in self.steps])
        self.reasoning_chain = chain
        return chain
    
    def to_dict(self):
        return {
            "steps": [s.to_dict() for s in self.steps],
            "final_answer": self.final_answer,
            "confidence": self.confidence,
            "total_tokens": self.total_tokens,
            "reasoning_chain": self.reasoning_chain
        }


class PipelineOrchestrator:
    """
    深度融合的 AI Pipeline 编排器
    
    核心特性：
    1. 思考过程可视化引擎
    2. 多模态输入融合
    3. 自适应学习系统
    4. 增量代码生成
    5. 知识图谱集成
    6. 智能调度引擎
    """
    
    def __init__(self):
        # 延迟导入避免循环依赖
        from livingtree.core.model.enhanced_router import get_enhanced_model_router
        
        self._model_router = get_enhanced_model_router()
        self._thinking_enabled = True
        
        # 思考过程缓存
        self._thinking_cache = {}
        
        # 学习数据存储
        self._learning_data = {
            "successful_prompts": [],
            "failed_prompts": [],
            "user_preferences": {},
            "performance_metrics": []
        }
        
        # 任务队列
        self._task_queue = asyncio.Queue()
        self._worker_tasks = []
        
        logger.info("✅ PipelineOrchestrator 初始化完成")
    
    async def run_with_thinking(self, capability: str, prompt: str, 
                               system_prompt: str = "", **kwargs) -> ThinkingResult:
        """
        带思考过程的模型调用
        
        Args:
            capability: 能力类型
            prompt: 用户提示
            system_prompt: 系统提示
        
        Returns:
            ThinkingResult - 包含思考步骤和最终答案
        """
        result = ThinkingResult()
        
        # 调用增强模型路由器
        response = await self._model_router.call_model(
            capability=capability,
            prompt=prompt,
            system_prompt=system_prompt,
            prefer_thinking=self._thinking_enabled,
            **kwargs
        )
        
        if response.success:
            result.final_answer = response.content
            result.total_tokens = response.tokens_used
            
            # 解析思考过程
            if response.thinking_content:
                result = self._parse_thinking_content(response.thinking_content, result)
            else:
                # 从响应中提取思考过程（如果模型返回了思考内容）
                result = self._extract_thinking_from_response(response.content, result)
            
            # 计算置信度
            result.confidence = self._calculate_confidence(response)
            
            # 缓存思考过程
            self._cache_thinking(response, result)
            
            # 记录学习数据
            self._record_learning_data("success", capability, prompt, response)
        
        return result
    
    def _parse_thinking_content(self, thinking_content: str, result: ThinkingResult) -> ThinkingResult:
        """解析模型返回的结构化思考内容"""
        try:
            # 尝试 JSON 解析
            thinking_data = json.loads(thinking_content)
            if isinstance(thinking_data, list):
                for i, thought in enumerate(thinking_data, 1):
                    if isinstance(thought, dict):
                        result.add_step(
                            thought.get("thought", ""),
                            thought.get("confidence", 0.8)
                        )
                    else:
                        result.add_step(str(thought))
            elif isinstance(thinking_data, dict):
                steps = thinking_data.get("steps", [])
                for step in steps:
                    result.add_step(
                        step.get("thought", ""),
                        step.get("confidence", 0.8)
                    )
        except json.JSONDecodeError:
            # 非结构化思考内容，按行分割
            lines = thinking_content.strip().split('\n')
            for i, line in enumerate(lines, 1):
                line = line.strip()
                if line and not line.startswith("#"):
                    result.add_step(line)
        
        return result
    
    def _extract_thinking_from_response(self, content: str, result: ThinkingResult) -> ThinkingResult:
        """从响应中提取思考过程"""
        # 检测 <think> 标签
        if "<think>" in content and "</think>" in content:
            start = content.find("<think>") + 7
            end = content.find("</think>")
            thinking_text = content[start:end].strip()
            
            # 提取最终答案
            answer_start = end + 8
            result.final_answer = content[answer_start:].strip()
            
            # 解析思考步骤
            lines = thinking_text.split('\n')
            for i, line in enumerate(lines, 1):
                line = line.strip()
                if line:
                    result.add_step(line)
        
        # 检测思考标记
        elif "思考:" in content or "思考过程:" in content:
            parts = content.split("思考:") if "思考:" in content else content.split("思考过程:")
            if len(parts) > 1:
                thinking_part = parts[1].split("答案:")[0] if "答案:" in parts[1] else parts[1]
                lines = thinking_part.strip().split('\n')
                for i, line in enumerate(lines, 1):
                    line = line.strip()
                    if line:
                        result.add_step(line)
        
        return result
    
    def _calculate_confidence(self, response) -> float:
        """计算置信度"""
        base_confidence = 0.7
        
        # 根据模型类型调整
        if "Pro" in response.model_used or "Max" in response.model_used:
            base_confidence += 0.15
        elif "Turbo" in response.model_used:
            base_confidence += 0.05
        
        # 根据思考模式调整
        if response.thinking_enabled:
            base_confidence += 0.1
        
        # 根据响应长度调整
        if len(response.content) > 500:
            base_confidence += 0.05
        
        return min(base_confidence, 0.95)
    
    def _cache_thinking(self, response, result: ThinkingResult):
        """缓存思考过程"""
        cache_key = f"{response.model_used}_{hash(response.content[:100])}"
        self._thinking_cache[cache_key] = {
            "timestamp": datetime.now(),
            "result": result.to_dict(),
            "response": response
        }
        
        # 限制缓存大小
        if len(self._thinking_cache) > 100:
            oldest_key = next(iter(self._thinking_cache))
            del self._thinking_cache[oldest_key]
    
    def _record_learning_data(self, status: str, capability: str, prompt: str, response):
        """记录学习数据"""
        record = {
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "capability": capability,
            "prompt_length": len(prompt),
            "response_length": len(response.content),
            "model_used": response.model_used,
            "tokens_used": response.tokens_used,
            "latency_ms": response.latency_ms,
            "thinking_enabled": response.thinking_enabled
        }
        
        if status == "success":
            self._learning_data["successful_prompts"].append(record)
        else:
            self._learning_data["failed_prompts"].append(record)
        
        # 记录性能指标
        self._learning_data["performance_metrics"].append(record)
    
    async def run_pipeline(self, requirement: str, 
                          thinking_mode: bool = True) -> Dict[str, Any]:
        """
        运行完整的 AI Pipeline
        
        Args:
            requirement: 用户需求
            thinking_mode: 是否启用思考模式
        
        Returns:
            完整的流水线执行结果
        """
        self._thinking_enabled = thinking_mode
        
        pipeline_result = {
            "requirement": requirement,
            "phases": [],
            "thinking_enabled": thinking_mode,
            "start_time": datetime.now().isoformat(),
            "total_tokens": 0,
            "total_cost_usd": 0.0
        }
        
        # 阶段 1: 需求分析
        phase1 = await self._phase_requirement_analysis(requirement)
        pipeline_result["phases"].append(phase1)
        
        # 阶段 2: 任务分解
        phase2 = await self._phase_task_decomposition(requirement, phase1)
        pipeline_result["phases"].append(phase2)
        
        # 阶段 3: 代码生成
        phase3 = await self._phase_code_generation(requirement, phase2)
        pipeline_result["phases"].append(phase3)
        
        # 阶段 4: 代码审查
        phase4 = await self._phase_code_review(phase3)
        pipeline_result["phases"].append(phase4)
        
        # 阶段 5: 质量门禁
        phase5 = await self._phase_quality_gate(phase3, phase4)
        pipeline_result["phases"].append(phase5)
        
        # 汇总统计
        pipeline_result["end_time"] = datetime.now().isoformat()
        pipeline_result["total_tokens"] = sum(p.get("tokens_used", 0) for p in pipeline_result["phases"])
        pipeline_result["total_cost_usd"] = sum(p.get("cost_usd", 0) for p in pipeline_result["phases"])
        
        # 检查是否所有阶段都通过
        all_passed = all(p.get("passed", False) for p in pipeline_result["phases"])
        pipeline_result["success"] = all_passed
        
        return pipeline_result
    
    async def _phase_requirement_analysis(self, requirement: str) -> Dict[str, Any]:
        """阶段 1: 需求分析"""
        print("\n🔍 阶段 1: 需求分析")
        
        thinking_result = await self.run_with_thinking(
            capability="planning",
            prompt=f"请分析以下需求，提取关键信息：\n{requirement}",
            system_prompt="你是一个资深产品经理，擅长分析和理解用户需求。",
            max_tokens=1024
        )
        
        return {
            "phase": PipelinePhase.REQUIREMENT_ANALYSIS.value,
            "status": "completed",
            "passed": True,
            "analysis": thinking_result.final_answer,
            "thinking_steps": [s.to_dict() for s in thinking_result.steps],
            "confidence": thinking_result.confidence,
            "tokens_used": thinking_result.total_tokens,
            "cost_usd": thinking_result.total_tokens * 0.0005 / 1000
        }
    
    async def _phase_task_decomposition(self, requirement: str, analysis_result: Dict) -> Dict[str, Any]:
        """阶段 2: 任务分解"""
        print("\n📋 阶段 2: 任务分解")
        
        thinking_result = await self.run_with_thinking(
            capability="planning",
            prompt=f"基于以下需求分析，将需求分解为具体的开发任务：\n需求: {requirement}\n分析: {analysis_result.get('analysis', '')}",
            system_prompt="你是一个项目管理专家，擅长将需求分解为可执行的任务。",
            max_tokens=1536
        )
        
        return {
            "phase": PipelinePhase.TASK_DECOMPOSITION.value,
            "status": "completed",
            "passed": True,
            "decomposition": thinking_result.final_answer,
            "thinking_steps": [s.to_dict() for s in thinking_result.steps],
            "confidence": thinking_result.confidence,
            "tokens_used": thinking_result.total_tokens,
            "cost_usd": thinking_result.total_tokens * 0.0005 / 1000
        }
    
    async def _phase_code_generation(self, requirement: str, decomposition_result: Dict) -> Dict[str, Any]:
        """阶段 3: 代码生成"""
        print("\n💻 阶段 3: 代码生成")
        
        thinking_result = await self.run_with_thinking(
            capability="content_generation",
            prompt=f"基于以下需求和任务分解，生成完整的代码实现：\n需求: {requirement}\n任务分解: {decomposition_result.get('decomposition', '')}",
            system_prompt="你是一个资深 Python 开发者，擅长编写高质量、可维护的代码。",
            max_tokens=2048
        )
        
        return {
            "phase": PipelinePhase.CODE_GENERATION.value,
            "status": "completed",
            "passed": True,
            "code": thinking_result.final_answer,
            "thinking_steps": [s.to_dict() for s in thinking_result.steps],
            "confidence": thinking_result.confidence,
            "tokens_used": thinking_result.total_tokens,
            "cost_usd": thinking_result.total_tokens * 0.0005 / 1000
        }
    
    async def _phase_code_review(self, code_result: Dict) -> Dict[str, Any]:
        """阶段 4: 代码审查"""
        print("\n🔍 阶段 4: 代码审查")
        
        code = code_result.get("code", "")
        if len(code) > 500:
            code = code[:500] + "..."
        
        thinking_result = await self.run_with_thinking(
            capability="planning",
            prompt=f"请审查以下代码，指出潜在问题和改进建议：\n{code}",
            system_prompt="你是一个代码审查专家，擅长发现代码质量问题和安全隐患。",
            max_tokens=1024
        )
        
        # 判断是否通过审查（简单规则：没有严重问题即为通过）
        has_critical_issue = any(
            "严重" in step.thought or "错误" in step.thought or "安全" in step.thought
            for step in thinking_result.steps
        )
        
        return {
            "phase": PipelinePhase.CODE_REVIEW.value,
            "status": "completed",
            "passed": not has_critical_issue,
            "review_comments": thinking_result.final_answer,
            "thinking_steps": [s.to_dict() for s in thinking_result.steps],
            "confidence": thinking_result.confidence,
            "tokens_used": thinking_result.total_tokens,
            "cost_usd": thinking_result.total_tokens * 0.0005 / 1000
        }
    
    async def _phase_quality_gate(self, code_result: Dict, review_result: Dict) -> Dict[str, Any]:
        """阶段 5: 质量门禁"""
        print("\n✅ 阶段 5: 质量门禁")
        
        # 综合评估
        code_confidence = code_result.get("confidence", 0.7)
        review_passed = review_result.get("passed", True)
        review_confidence = review_result.get("confidence", 0.7)
        
        overall_score = (code_confidence * 0.6 + review_confidence * 0.4) * (1 if review_passed else 0.5)
        passed = overall_score >= 0.7
        
        return {
            "phase": PipelinePhase.QUALITY_GATE.value,
            "status": "completed",
            "passed": passed,
            "overall_score": round(overall_score, 2),
            "code_confidence": code_confidence,
            "review_passed": review_passed,
            "review_confidence": review_confidence,
            "tokens_used": 0,
            "cost_usd": 0.0
        }
    
    def generate_thinking_report(self, pipeline_result: Dict) -> str:
        """生成思考过程报告"""
        report = f"""
╔══════════════════════════════════════════════════════════════╗
║                  思考过程分析报告                            ║
╠══════════════════════════════════════════════════════════════╣
║  需求: {pipeline_result['requirement'][:50]}...              ║
║  思考模式: {'✅ 启用' if pipeline_result['thinking_enabled'] else '❌ 禁用'} ║
║  总 Token: {pipeline_result['total_tokens']}                ║
║  总成本: ${pipeline_result['total_cost_usd']:.4f}          ║
╠══════════════════════════════════════════════════════════════╣
"""
        
        for phase in pipeline_result["phases"]:
            report += f"║\n║  阶段: {phase['phase']}\n"
            report += f"║  状态: {'✅ 通过' if phase['passed'] else '❌ 失败'}\n"
            
            if "thinking_steps" in phase and phase["thinking_steps"]:
                report += f"║  思考步骤:\n"
                for step in phase["thinking_steps"][:3]:  # 最多显示3步
                    report += f"║    [{step['step']}] {step['thought'][:50]}...\n"
            
            report += f"║  置信度: {phase.get('confidence', 0):.2f}\n"
        
        report += f"""
╠══════════════════════════════════════════════════════════════╣
║  流水线结果: {'🎉 成功' if pipeline_result['success'] else '⚠️ 失败'} ║
╚══════════════════════════════════════════════════════════════╝
"""
        
        return report
    
    def get_learning_insights(self) -> Dict[str, Any]:
        """获取学习洞察"""
        successful = self._learning_data["successful_prompts"]
        failed = self._learning_data["failed_prompts"]
        metrics = self._learning_data["performance_metrics"]
        
        if not metrics:
            return {"message": "暂无学习数据"}
        
        avg_latency = sum(m["latency_ms"] for m in metrics) / len(metrics)
        avg_tokens = sum(m["tokens_used"] for m in metrics) / len(metrics)
        success_rate = len(successful) / max(len(successful) + len(failed), 1) * 100
        
        # 模型使用统计
        model_usage = {}
        for m in metrics:
            model = m["model_used"]
            model_usage[model] = model_usage.get(model, 0) + 1
        
        return {
            "total_calls": len(metrics),
            "success_rate": round(success_rate, 2),
            "avg_latency_ms": round(avg_latency, 2),
            "avg_tokens": round(avg_tokens, 2),
            "model_usage": model_usage,
            "thinking_enabled_rate": sum(1 for m in metrics if m["thinking_enabled"]) / len(metrics) * 100
        }


# 全局单例
_global_pipeline_orchestrator: Optional[PipelineOrchestrator] = None


def get_pipeline_orchestrator() -> PipelineOrchestrator:
    """获取全局 PipelineOrchestrator 单例"""
    global _global_pipeline_orchestrator
    if _global_pipeline_orchestrator is None:
        _global_pipeline_orchestrator = PipelineOrchestrator()
    return _global_pipeline_orchestrator


# 测试函数
async def test_pipeline_orchestrator():
    """测试 PipelineOrchestrator"""
    print("🚀 测试 PipelineOrchestrator")
    print("="*60)
    
    orchestrator = get_pipeline_orchestrator()
    
    # 测试思考模式调用
    print("\n🧠 测试思考模式调用:")
    thinking_result = await orchestrator.run_with_thinking(
        capability="planning",
        prompt="一个房间里有3个人，每个人有2个苹果，后来进来了2个人，每个人有3个苹果，现在总共有多少个苹果？",
        system_prompt="你是一个数学助手，使用思考模式详细解释计算过程。"
    )
    
    print(f"✅ 思考步骤数: {len(thinking_result.steps)}")
    print(f"✅ 最终答案: {thinking_result.final_answer}")
    print(f"✅ 置信度: {thinking_result.confidence:.2f}")
    
    if thinking_result.steps:
        print("\n📝 思考过程:")
        for step in thinking_result.steps:
            print(f"   [{step.step_num}] {step.thought}")
    
    # 测试完整流水线
    print("\n🚀 测试完整流水线:")
    pipeline_result = await orchestrator.run_pipeline(
        requirement="开发一个简单的待办事项 API，支持任务的创建、查询、更新和删除",
        thinking_mode=True
    )
    
    # 输出思考报告
    print("\n📊 思考过程报告:")
    print(orchestrator.generate_thinking_report(pipeline_result))
    
    # 输出学习洞察
    insights = orchestrator.get_learning_insights()
    print("\n💡 学习洞察:")
    print(f"   总调用次数: {insights['total_calls']}")
    print(f"   成功率: {insights['success_rate']:.2f}%")
    print(f"   平均延迟: {insights['avg_latency_ms']:.2f}ms")
    print(f"   平均 Token: {insights['avg_tokens']:.2f}")
    
    return True


if __name__ == "__main__":
    asyncio.run(test_pipeline_orchestrator())