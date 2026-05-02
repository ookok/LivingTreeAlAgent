"""
自我反思引擎

实现SICA的自我反思能力，分析代码质量、识别改进机会。
"""
import json
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from ..global_model_router import GlobalModelRouter

logger = logging.getLogger(__name__)


@dataclass
class ReflectionResult:
    """反思结果"""
    code_quality: float = 0.0
    maintainability: float = 0.0
    performance: float = 0.0
    suggestions: List[str] = field(default_factory=list)
    refactoring_actions: List[Dict[str, Any]] = field(default_factory=list)
    knowledge_gaps: List[str] = field(default_factory=list)


class SelfReflectionEngine:
    """
    自我反思引擎
    
    核心能力：
    1. 代码质量评估
    2. 识别知识缺口
    3. 生成改进建议
    4. 自动重构
    """
    
    def __init__(self):
        self.model_router = GlobalModelRouter.get_instance()
    
    async def reflect_on_code(self, code: str, task_description: str) -> ReflectionResult:
        """
        对代码进行深度反思
        
        Args:
            code: 待分析的代码
            task_description: 原始任务描述
        
        Returns:
            ReflectionResult
        """
        logger.info("Performing self-reflection on generated code")
        
        # 构建反思提示词
        prompt = self._build_reflection_prompt(code, task_description)
        
        try:
            response = await self.model_router.generate(
                prompt=prompt,
                model_type="analysis",
                max_tokens=3000,
            )
            
            if not response or not response.content:
                return ReflectionResult(
                    suggestions=["反思生成失败"]
                )
            
            # 解析反思结果
            return self._parse_reflection(response.content)
        
        except Exception as e:
            logger.error(f"Self-reflection failed: {e}")
            return ReflectionResult(
                suggestions=[str(e)]
            )
    
    def _build_reflection_prompt(self, code: str, task_description: str) -> str:
        """构建反思提示词"""
        return f"""
你是一个专业的代码评审专家。请对以下代码进行深度分析和反思。

任务描述：
{task_description}

代码：
```python
{code}
```

请从以下维度进行分析：

1. **代码质量**：语法正确性、类型注解完整性、错误处理、注释质量
2. **可维护性**：代码结构、命名规范、模块化程度、可读性
3. **性能**：算法复杂度、潜在的性能瓶颈、优化机会
4. **业务逻辑**：是否正确实现了需求、是否有逻辑漏洞
5. **知识缺口**：代码中是否暴露了对业务领域知识的欠缺

请输出JSON格式的分析结果，包含：
- code_quality: 0-10的分数
- maintainability: 0-10的分数  
- performance: 0-10的分数
- suggestions: 改进建议列表
- knowledge_gaps: 识别到的知识缺口列表

输出格式：
```json
{{
  "code_quality": 8.5,
  "maintainability": 7.0,
  "performance": 6.5,
  "suggestions": [...],
  "knowledge_gaps": [...]
}}
```
"""
    
    def _parse_reflection(self, content: str) -> ReflectionResult:
        """解析反思结果"""
        import re
        
        # 提取JSON部分
        json_match = re.search(r"```json\s*(.*?)\s*```", content, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                return ReflectionResult(
                    code_quality=data.get("code_quality", 0.0),
                    maintainability=data.get("maintainability", 0.0),
                    performance=data.get("performance", 0.0),
                    suggestions=data.get("suggestions", []),
                    knowledge_gaps=data.get("knowledge_gaps", []),
                )
            except json.JSONDecodeError:
                pass
        
        # 如果JSON解析失败，尝试从文本中提取
        result = ReflectionResult()
        
        # 简单的分数提取
        quality_match = re.search(r"代码质量[：:]?\s*(\d+\.?\d*)", content)
        if quality_match:
            result.code_quality = float(quality_match.group(1))
        
        maintain_match = re.search(r"可维护性[：:]?\s*(\d+\.?\d*)", content)
        if maintain_match:
            result.maintainability = float(maintain_match.group(1))
        
        perf_match = re.search(r"性能[：:]?\s*(\d+\.?\d*)", content)
        if perf_match:
            result.performance = float(perf_match.group(1))
        
        # 提取建议
        suggestion_patterns = [
            r"改进建议[：:]?(.*?)(?=\n\n|$)",
            r"建议[：:]?(.*?)(?=\n\n|$)",
        ]
        for pattern in suggestion_patterns:
            match = re.search(pattern, content, re.DOTALL)
            if match:
                suggestions_text = match.group(1)
                result.suggestions = [
                    s.strip() for s in suggestions_text.split("\n") 
                    if s.strip() and not s.strip().startswith("-")
                ]
                if not result.suggestions:
                    result.suggestions = [suggestions_text.strip()]
                break
        
        return result
    
    async def identify_knowledge_gaps(self, code: str, domain: str) -> List[str]:
        """
        识别代码中的知识缺口
        
        Args:
            code: 代码
            domain: 业务领域（如环评、金融等）
        
        Returns:
            知识缺口列表
        """
        prompt = f"""
分析以下{domain}领域的代码，识别其中可能存在的知识缺口。

代码：
```python
{code}
```

请列出代码中可能反映出的对{domain}领域知识的欠缺，例如：
- 使用了错误的计算公式
- 遗漏了重要的业务规则
- 参数设置不合理
- 未考虑行业标准

请以列表形式输出。
"""
        
        try:
            response = await self.model_router.generate(
                prompt=prompt,
                model_type="analysis",
                max_tokens=1500,
            )
            
            if response and response.content:
                # 解析列表
                gaps = []
                for line in response.content.split("\n"):
                    line = line.strip()
                    if line and (line.startswith("-") or line.startswith("•") or line.startswith("*")):
                        gaps.append(line[1:].strip())
                return gaps
        
        except Exception as e:
            logger.error(f"Knowledge gap identification failed: {e}")
        
        return []
    
    async def suggest_refactoring(self, code: str) -> List[Dict[str, Any]]:
        """
        建议重构动作
        
        Args:
            code: 待重构的代码
        
        Returns:
            重构建议列表
        """
        prompt = f"""
请对以下代码进行重构分析，提供具体的重构建议。

代码：
```python
{code}
```

请输出每个重构建议，包含：
1. 重构类型（如：提取函数、合并重复代码、简化条件判断等）
2. 修改位置（行号或代码片段）
3. 修改方案

输出格式：
- 重构类型：XXX
  位置：第X行附近
  方案：具体修改建议
"""
        
        try:
            response = await self.model_router.generate(
                prompt=prompt,
                model_type="analysis",
                max_tokens=2000,
            )
            
            if response and response.content:
                return self._parse_refactoring_suggestions(response.content)
        
        except Exception as e:
            logger.error(f"Refactoring suggestion failed: {e}")
        
        return []
    
    def _parse_refactoring_suggestions(self, content: str) -> List[Dict[str, Any]]:
        """解析重构建议"""
        suggestions = []
        current_suggestion = {}
        
        for line in content.split("\n"):
            line = line.strip()
            
            if line.startswith("- 重构类型"):
                if current_suggestion:
                    suggestions.append(current_suggestion)
                current_suggestion = {"type": line.replace("- 重构类型：", "").strip()}
            
            elif line.startswith("位置："):
                current_suggestion["location"] = line.replace("位置：", "").strip()
            
            elif line.startswith("方案："):
                current_suggestion["solution"] = line.replace("方案：", "").strip()
        
        if current_suggestion:
            suggestions.append(current_suggestion)
        
        return suggestions