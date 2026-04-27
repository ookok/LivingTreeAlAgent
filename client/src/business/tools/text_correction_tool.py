"""
TextCorrectionTool - 错别字纠正工具

功能：
1. 识别文本中的错别字（同音、形近、语法别错）
2. 从上下文推理正确用词
3. 给出纠正建议和理由
4. 支持批量处理

使用方法：
    from client.src.business.tools.text_correction_tool import TextCorrectionTool
    
    tool = TextCorrectionTool()
    result = tool.execute(text="我想吃平果", context="讨论健康饮食")
    
    # 或者批量处理
    result = tool.execute(
        texts=["我想吃平果", "他学习很认直"],
        context="学生生活"
    )

Author: LivingTreeAI Agent
Date: 2026-04-28
"""

import json
import re
from typing import Any, Dict, List, Optional

from client.src.business.global_model_router import GlobalModelRouter, ModelCapability
from client.src.business.tools.base_tool import BaseTool
from client.src.business.tools.tool_result import ToolResult, SUCCESS, ERROR


class TextCorrectionTool(BaseTool):
    """
    错别字纠正工具
    
    功能：
    - 识别错别字（同音、形近、语法别错）
    - 从上下文推理正确用词
    - 给出纠正建议和理由
    - 支持批量处理
    
    用法：
        tool = TextCorrectionTool()
        result = tool.execute(text="我想吃平果", context="讨论健康饮食")
    """
    
    def __init__(self, confidence_threshold: float = 0.7):
        """
        初始化错别字纠正工具
        
        Args:
            confidence_threshold: 置信度阈值（低于此值不自动纠正）
        """
        super().__init__(
            name="text_correction",
            description="识别并纠正文本中的错别字，支持上下文感知",
        )
        self._confidence_threshold = confidence_threshold
        self._router = GlobalModelRouter()
        
        # 缓存（避免重复纠正）
        self._cache = {}
    
    def get_schema(self) -> dict:
        """返回工具的参数 schema"""
        return {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "要纠正的文本（单个字符串）",
                },
                "texts": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "要纠正的文本列表（批量处理）",
                },
                "context": {
                    "type": "string",
                    "description": "上下文（帮助理解语义，提高纠正准确率）",
                },
                "auto_correct": {
                    "type": "boolean",
                    "description": "是否自动纠正（false 则只返回建议）",
                    "default": False,
                },
            },
            "required": [],
        }
    
    def execute(self, **kwargs) -> ToolResult:
        """
        执行错别字纠正
        
        Args:
            text: 单个文本（与 texts 二选一）
            texts: 文本列表（与 text 二选一）
            context: 上下文（可选）
            auto_correct: 是否自动纠正（默认 False）
            
        Returns:
            ToolResult 包含纠正结果
        """
        text = kwargs.get("text")
        texts = kwargs.get("texts", [])
        context = kwargs.get("context", "")
        auto_correct = kwargs.get("auto_correct", False)
        
        # 参数处理
        if text:
            texts = [text]
        elif not texts:
            return ERROR("请提供 text 或 texts 参数")
        
        # 批量处理
        try:
            corrections = []
            corrected_texts = []
            
            for t in texts:
                # 检查缓存
                cache_key = f"{t}:{context}"
                if cache_key in self._cache:
                    cached = self._cache[cache_key]
                    corrections.append(cached["corrections"])
                    corrected_texts.append(cached["corrected_text"])
                    continue
                
                # 调用 LLM 进行纠正
                correction = self._correct_text_with_llm(t, context)
                corrections.append(correction["corrections"])
                corrected_texts.append(correction["corrected_text"])
                
                # 缓存结果
                self._cache[cache_key] = correction
            
            # 构造结果
            result_data = {
                "original_texts": texts,
                "corrections": corrections,
                "corrected_texts": corrected_texts if auto_correct else None,
                "has_errors": any(len(c) > 0 for c in corrections),
            }
            
            # 如果只有一个文本，简化输出
            if len(texts) == 1:
                result_data["original_text"] = texts[0]
                result_data["corrections"] = corrections[0]
                result_data["corrected_text"] = corrected_texts[0] if auto_correct else None
            
            return SUCCESS(data=result_data)
        
        except Exception as e:
            return ERROR(f"错别字纠正失败: {str(e)}")
    
    def _correct_text_with_llm(self, text: str, context: str) -> dict:
        """
        使用 LLM 纠正文本中的错别字
        
        Args:
            text: 要纠正的文本
            context: 上下文
            
        Returns:
            包含 corrections 和 corrected_text 的字典
        """
        # 构造提示词
        prompt = self._build_correction_prompt(text, context)
        
        # 调用 LLM（使用 GlobalModelRouter）
        response = self._router.call_model_sync(
            capability=ModelCapability.REASONING,  # 使用推理能力
            prompt=prompt,
            temperature=0.3,  # 低温度，提高准确性
        )
        
        # 解析响应
        try:
            # 尝试从响应中提取 JSON
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                # 如果不是 JSON，尝试解析文本响应
                result = self._parse_text_response(response, text)
            
            # 验证结果
            if "corrections" not in result:
                result["corrections"] = []
            if "corrected_text" not in result:
                result["corrected_text"] = text
            
            return result
        
        except json.JSONDecodeError:
            # JSON 解析失败，返回原始文本
            return {
                "corrections": [],
                "corrected_text": text,
                "error": "LLM 响应解析失败",
            }
    
    def _build_correction_prompt(self, text: str, context: str) -> str:
        """
        构造错别字纠正的提示词
        
        Args:
            text: 要纠正的文本
            context: 上下文
            
        Returns:
            提示词字符串
        """
        prompt_parts = [
            "你是一个专业的文字校对专家。请检查以下文本是否有错别字（包括同音错别字、形近错别字、语法错别字）。",
            "",
        ]
        
        if context:
            prompt_parts.append(f"上下文：{context}")
            prompt_parts.append("")
        
        prompt_parts.append(f"待检查文本：{text}")
        prompt_parts.append("")
        prompt_parts.append("请按以下 JSON 格式输出结果：")
        prompt_parts.append(json.dumps({
            "has_error": True,
            "corrections": [
                {
                    "original": "原始错误词",
                    "corrected": "纠正后的词",
                    "reason": "错误原因（同音错别字/形近错别字/语法错别字）",
                    "confidence": 0.95,  # 置信度 0-1
                }
            ],
            "corrected_text": "纠正后的完整文本",
        }, ensure_ascii=False, indent=2))
        prompt_parts.append("")
        prompt_parts.append("注意：")
        prompt_parts.append("1. 如果没有错别字，has_error 设为 false，corrections 设为空数组")
        prompt_parts.append("2. 置信度低于 0.7 的纠正建议请谨慎给出")
        prompt_parts.append("3. 专业术语、人名、地名不要随意纠正")
        prompt_parts.append("4. 只输出 JSON，不要输出其他内容")
        
        return "\n".join(prompt_parts)
    
    def _parse_text_response(self, response: str, original_text: str) -> dict:
        """
        解析非 JSON 格式的 LLM 响应
        
        Args:
            response: LLM 响应
            original_text: 原始文本
            
        Returns:
            解析后的结果字典
        """
        # 尝试从文本中提取纠正信息
        corrections = []
        
        # 匹配模式："原词" → "纠正词" (原因)
        pattern = r'["\'](.*?)["\']\s*[→\-→]\s*["\'](.*?)["\'](?:\s*[\(（](.*?)[\)）])?'
        matches = re.findall(pattern, response)
        
        for match in matches:
            original = match[0]
            corrected = match[1]
            reason = match[2] if match[2] else "未知"
            
            corrections.append({
                "original": original,
                "corrected": corrected,
                "reason": reason,
                "confidence": 0.8,  # 默认置信度
            })
        
        # 构造纠正后的文本
        corrected_text = original_text
        for c in corrections:
            corrected_text = corrected_text.replace(c["original"], c["corrected"])
        
        return {
            "has_error": len(corrections) > 0,
            "corrections": corrections,
            "corrected_text": corrected_text,
        }
    
    def correct_text(self, text: str, context: str = "") -> dict:
        """
        纠正单个文本（便捷方法）
        
        Args:
            text: 要纠正的文本
            context: 上下文
            
        Returns:
            纠正结果字典
        """
        result = self.execute(text=text, context=context)
        
        if result.success:
            return result.data
        else:
            return {
                "has_error": False,
                "corrections": [],
                "corrected_text": text,
                "error": result.error,
            }
    
    def correct_texts(self, texts: List[str], context: str = "") -> List[dict]:
        """
        纠正多个文本（便捷方法）
        
        Args:
            texts: 要纠正的文本列表
            context: 上下文
            
        Returns:
            纠正结果字典列表
        """
        result = self.execute(texts=texts, context=context)
        
        if result.success:
            data = result.data
            # 拆分结果
            results = []
            for i, text in enumerate(texts):
                results.append({
                    "original_text": text,
                    "corrections": data["corrections"][i] if i < len(data["corrections"]) else [],
                    "corrected_text": data["corrected_texts"][i] if data["corrected_texts"] and i < len(data["corrected_texts"]) else text,
                })
            return results
        else:
            return [{
                "original_text": text,
                "corrections": [],
                "corrected_text": text,
                "error": result.error,
            } for text in texts]
    
    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()


# 便捷函数
def correct_text(text: str, context: str = "") -> dict:
    """
    纠正文本中的错别字（便捷函数）
    
    Args:
        text: 要纠正的文本
        context: 上下文
        
    Returns:
        纠正结果字典
    """
    tool = TextCorrectionTool()
    return tool.correct_text(text, context)


def correct_texts(texts: List[str], context: str = "") -> List[dict]:
    """
    纠正多个文本中的错别字（便捷函数）
    
    Args:
        texts: 要纠正的文本列表
        context: 上下文
        
    Returns:
        纠正结果字典列表
    """
    tool = TextCorrectionTool()
    return tool.correct_texts(texts, context)


if __name__ == "__main__":
    # 测试
    tool = TextCorrectionTool()
    
    # 测试 1：同音错别字
    result = tool.correct_text("我想吃平果", context="讨论健康饮食")
    print("测试 1：同音错别字")
    print(f"原文：我想吃平果")
    print(f"纠正：{result['corrected_text']}")
    print(f"建议：{result['corrections']}")
    print()
    
    # 测试 2：形近错别字
    result = tool.correct_text("她戴了一顶红色的冒子", context="讨论穿搭")
    print("测试 2：形近错别字")
    print(f"原文：她戴了一顶红色的冒子")
    print(f"纠正：{result['corrected_text']}")
    print(f"建议：{result['corrections']}")
    print()
    
    # 测试 3：语法错别字
    result = tool.correct_text("他学习很认直", context="老师评价学生")
    print("测试 3：语法错别字")
    print(f"原文：他学习很认直")
    print(f"纠正：{result['corrected_text']}")
    print(f"建议：{result['corrections']}")
    print()
    
    # 测试 4：批量处理
    test_texts = ["我想吃平果", "他学习很认直", "这是正确的句子"]
    results = tool.correct_texts(test_texts, context="学生生活")
    print("测试 4：批量处理")
    for i, r in enumerate(results):
        print(f"{i+1}. {r['original_text']} → {r['corrected_text']}")
        if r['corrections']:
            print(f"   建议：{r['corrections']}")


def auto_register():
    """自动注册工具到 ToolRegistry"""
    from client.src.business.tools.tool_registry import ToolRegistry
    
    registry = ToolRegistry.get_instance()
    tool = TextCorrectionTool()
    success = registry.register_tool(tool)
    
    if success:
        print(f"[TextCorrectionTool] 已注册到 ToolRegistry")
    else:
        print(f"[TextCorrectionTool] 注册失败")
    
    return success


# 自动注册（导入时执行）
try:
    auto_register()
except Exception as e:
    print(f"[TextCorrectionTool] 自动注册失败: {e}")
