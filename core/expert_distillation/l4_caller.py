"""
L4 增强调用器 - L4EnhancedCaller

整合专家模板注入和蒸馏提示，提供增强的 L4 调用能力。
"""

from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime

from .template_library import ExpertTemplateLibrary
from .router import ExpertRouter, RoutingDecision, QueryDomain


@dataclass
class L4CallRequest:
    query: str
    domain: Optional[str] = None
    force_expert: bool = False
    include_reasoning: bool = True
    max_tokens: int = 2048
    temperature: float = 0.7


@dataclass
class L4CallResult:
    response: str
    reasoning: str
    expert_hint: str
    domain: str
    latency_ms: float
    tokens_used: int
    routing_decision: Optional[RoutingDecision] = None


class L4EnhancedCaller:
    """
    L4 增强调用器

    将专家模板和思维链注入到 L4 调用中，提升输出质量。

    Example:
        caller = L4EnhancedCaller(
            llm_call_fn=ollama_client.chat,
            router=router,
            template_library=library
        )

        result = caller.call("分析贵州茅台的估值")
        print(result.response)
        print(f"专家提示: {result.expert_hint}")
    """

    def __init__(
        self,
        llm_call_fn: Optional[Callable] = None,
        router: Optional[ExpertRouter] = None,
        template_library: Optional[ExpertTemplateLibrary] = None
    ):
        """
        Args:
            llm_call_fn: LLM 调用函数，签名: (prompt, system?) -> str
            router: 专家路由器
            template_library: 专家模板库
        """
        self.llm_call_fn = llm_call_fn or self._mock_llm_call
        self.router = router
        self.template_library = template_library or ExpertTemplateLibrary()
        self.call_history: List[L4CallResult] = []
        self.stats = {
            "total_calls": 0,
            "expert_hints_used": 0,
            "avg_latency_ms": 0
        }

    def _mock_llm_call(self, prompt: str, system: str = "") -> str:
        """模拟 LLM 调用"""
        return f"【模拟专家回答】\n\n基于以下推理过程得出结论：\n\n{prompt[-200:]}\n\n综合分析后提供专业回答。"

    def _build_enhanced_prompt(self, request: L4CallRequest, routing: Optional[RoutingDecision]) -> tuple[str, str]:
        """
        构建增强提示

        Returns:
            (system_prompt, user_prompt)
        """
        domain = request.domain or (routing.primary_domain.value if routing else "通用")

        # 1. 构建专家提示
        expert_hint = ""
        if routing and routing.expert_model:
            expert_hint = self.template_library.get_prompt_hint(request.query, domain)

        # 2. 构建系统提示
        system_parts = [
            "你是一位专业 AI 助手。",
        ]

        if expert_hint:
            system_parts.append(f"\n{expert_hint}")

        system_parts.extend([
            "\n请在回答中展示清晰的推理过程。",
            "格式：\n【推理过程】...\n【结论】...",
        ])

        system_prompt = "\n".join(system_parts)

        # 3. 构建用户提示
        user_prompt = f"\n【问题】\n{request.query}"

        return system_prompt, user_prompt

    def call(self, query: str, domain: Optional[str] = None, **kwargs) -> L4CallResult:
        """
        执行增强调用

        Args:
            query: 用户查询
            domain: 指定领域
            **kwargs: 其他参数传递给 LLM

        Returns:
            L4CallResult
        """
        start_time = datetime.now()

        # 1. 路由决策
        routing = self.router.decide(query, QueryDomain.from_name(domain)) if domain and self.router else None

        # 2. 构建请求
        request = L4CallRequest(
            query=query,
            domain=domain,
            force_expert=kwargs.get("force_expert", False)
        )

        # 3. 构建增强提示
        system_prompt, user_prompt = self._build_enhanced_prompt(request, routing)

        # 4. 调用 LLM
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        response = self.llm_call_fn(full_prompt)

        # 5. 解析响应
        latency_ms = (datetime.now() - start_time).total_seconds() * 1000
        reasoning, answer = self._parse_response(response)

        # 6. 构建结果
        result = L4CallResult(
            response=answer,
            reasoning=reasoning,
            expert_hint=self.template_library.get_prompt_hint(query, domain or "通用"),
            domain=domain or (routing.primary_domain.value if routing else "通用"),
            latency_ms=latency_ms,
            tokens_used=len(full_prompt) // 4,  # 粗略估算
            routing_decision=routing
        )

        # 7. 记录历史
        self.call_history.append(result)
        self._update_stats(result)

        return result

    def _parse_response(self, response: str) -> tuple[str, str]:
        """解析响应，分离推理和结论"""
        # 尝试识别推理标记
        reasoning_markers = ["【推理", "推理过程", "分析过程", "思考过程", "Reasoning"]
        conclusion_markers = ["【结论", "结论", "最终答案", "Answer"]

        reasoning = ""
        conclusion = response

        for marker in reasoning_markers:
            idx = response.find(marker)
            if idx >= 0:
                # 找到下一个结论标记或结尾
                end_idx = len(response)
                for end_marker in conclusion_markers:
                    next_idx = response.find(end_marker, idx + len(marker))
                    if next_idx > idx:
                        end_idx = min(end_idx, next_idx)

                reasoning = response[idx:end_idx].strip()
                conclusion = response[:idx].strip() + "\n\n" + response[end_idx:].strip()
                break

        if not reasoning:
            # 默认：前半是推理，后半是结论
            parts = response.split("\n\n")
            if len(parts) >= 2:
                reasoning = "\n\n".join(parts[:len(parts)//2])
                conclusion = "\n\n".join(parts[len(parts)//2:])

        return reasoning.strip(), conclusion.strip() or response.strip()

    def _update_stats(self, result: L4CallResult):
        """更新统计"""
        self.stats["total_calls"] += 1
        if result.expert_hint:
            self.stats["expert_hints_used"] += 1

        # 滑动平均延迟
        n = self.stats["total_calls"]
        avg = self.stats["avg_latency_ms"]
        self.stats["avg_latency_ms"] = (avg * (n - 1) + result.latency_ms) / n

    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        return {
            **self.stats,
            "total_history": len(self.call_history),
            "hint_usage_rate": self.stats["expert_hints_used"] / max(self.stats["total_calls"], 1)
        }

    def chat_stream(self, query: str, domain: Optional[str] = None):
        """
        流式调用（需要底层支持）

        Yields:
            str: 增量响应
        """
        # 简化实现：返回完整响应
        result = self.call(query, domain)
        yield result.response


# 便捷函数
def enhanced_call(query: str, domain: str = None, llm_fn=None) -> L4CallResult:
    """快速增强调用"""
    caller = L4EnhancedCaller(llm_call_fn=llm_fn)
    return caller.call(query, domain)
