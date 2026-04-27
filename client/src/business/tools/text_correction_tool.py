"""
TextCorrectionTool - 错别字纠正工具（增强版）

功能：
1. 识别文本中的错别字（同音、形近、语法、多字、少字、乱序）
2. 从上下文推理正确用词
3. 给出纠正建议和理由
4. 支持批量处理

错别字类型说明：
- 同音错别字：发音相同，用字错误  例："我想吃平果" → "我想吃苹果"
- 形近错别字：字形相似，看错写错  例："她戴了一顶红色的冒子" → "帽子"
- 语法错别字：语法搭配错误          例："他学习很认直" → "认真"
- 多字错别字：多余字              例："我今天去去公园" → "我今天去公园"
- 少字错别字：缺少字              例："我今天公园" → "我今天去公园"
- 乱序错别字：字序颠倒            例："我天今去公园" → "我今天去公园"

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
Enhance: 2026-04-28 - 添加多字/少字/乱序错别字识别
"""

import json
import re
from typing import Any, Dict, List, Optional

from client.src.business.global_model_router import GlobalModelRouter, ModelCapability
from client.src.business.tools.base_tool import BaseTool
from client.src.business.tools.tool_result import ToolResult, SUCCESS, ERROR


# --------------------------------------------------------------------------- #
# 错别字类型常量
# --------------------------------------------------------------------------- #

ERROR_TYPE_TONE      = "同音错别字"
ERROR_TYPE_SHAPE     = "形近错别字"
ERROR_TYPE_GRAMMAR   = "语法错别字"
ERROR_TYPE_EXTRA     = "多字错别字"
ERROR_TYPE_MISSING   = "少字错别字"
ERROR_TYPE_SHUFFLE   = "乱序错别字"

ALL_ERROR_TYPES = [
    ERROR_TYPE_TONE,
    ERROR_TYPE_SHAPE,
    ERROR_TYPE_GRAMMAR,
    ERROR_TYPE_EXTRA,
    ERROR_TYPE_MISSING,
    ERROR_TYPE_SHUFFLE,
]


# --------------------------------------------------------------------------- #
# TextCorrectionTool
# --------------------------------------------------------------------------- #

class TextCorrectionTool(BaseTool):
    """
    错别字纠正工具

    功能：
    - 识别错别字（同音、形近、语法、多字、少字、乱序）
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
            description="识别并纠正文本中的错别字，支持上下文感知；支持同音/形近/语法/多字/少字/乱序六类错别字",
        )
        self._confidence_threshold = confidence_threshold
        self._router = GlobalModelRouter()

        # 缓存（避免重复纠正）
        self._cache: Dict[str, dict] = {}

    # ------------------------------------------------------------------ #
    # BaseTool 接口
    # ------------------------------------------------------------------ #

    def get_schema(self) -> dict:
        """返回工具的参数 schema"""
        return {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "要纠正的单个文本",
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
            text:         单个文本（与 texts 二选一）
            texts:        文本列表（与 text 二选一）
            context:      上下文（可选）
            auto_correct: 是否自动纠正（默认 False）

        Returns:
            ToolResult 包含纠正结果
        """
        text         = kwargs.get("text")
        texts        = kwargs.get("texts", [])
        context      = kwargs.get("context", "")
        auto_correct = kwargs.get("auto_correct", False)

        # 参数归一化
        if text:
            texts = [text]
        elif not texts:
            return ERROR("请提供 text 或 texts 参数")

        try:
            corrections_list:    List[List[Dict]] = []
            corrected_texts:     List[Optional[str]]  = []

            for t in texts:
                cache_key = f"{t}:{context}"
                if cache_key in self._cache:
                    cached = self._cache[cache_key]
                    corrections_list.append(cached["corrections"])
                    corrected_texts.append(cached["corrected_text"])
                    continue

                correction = self._correct_text_with_llm(t, context)
                corrections_list.append(correction["corrections"])
                corrected_texts.append(correction["corrected_text"])

                self._cache[cache_key] = correction

            # 构造返回数据
            result_data = {
                "original_texts":  texts,
                "corrections":     corrections_list,
                "corrected_texts": corrected_texts if auto_correct else None,
                "has_errors":     any(len(c) > 0 for c in corrections_list),
            }

            # 单文本时简化输出
            if len(texts) == 1:
                result_data["original_text"]  = texts[0]
                result_data["corrections"]    = corrections_list[0]
                result_data["corrected_text"] = corrected_texts[0] if auto_correct else None

            return SUCCESS(data=result_data)

        except Exception as e:
            return ERROR(f"错别字纠正失败: {str(e)}")

    # ------------------------------------------------------------------ #
    # 核心逻辑：调用 LLM
    # ------------------------------------------------------------------ #

    def _correct_text_with_llm(self, text: str, context: str) -> dict:
        """
        使用 LLM 纠正文本中的错别字

        Args:
            text:    要纠正的文本
            context: 上下文

        Returns:
            包含 corrections 和 corrected_text 的字典
        """
        prompt = self._build_correction_prompt(text, context)

        response = self._router.call_model_sync(
            capability=ModelCapability.REASONING,
            prompt=prompt,
            temperature=0.2,   # 低温度，提高准确性
        )

        # 解析响应
        try:
            # 优先尝试提取 JSON
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                result = self._parse_text_response(response, text)

            # 字段兜底
            if "corrections" not in result:
                result["corrections"] = []
            if "corrected_text" not in result:
                result["corrected_text"] = text
            if "has_error" not in result:
                result["has_error"] = len(result["corrections"]) > 0

            return result

        except json.JSONDecodeError:
            return {
                "corrections":    [],
                "corrected_text": text,
                "has_error":      False,
                "error":          "LLM 响应解析失败",
            }

    # ------------------------------------------------------------------ #
    # 提示词构建（核心优化点）
    # ------------------------------------------------------------------ #

    def _build_correction_prompt(self, text: str, context: str) -> str:
        """
        构造错别字纠正的 LLM 提示词（增强版）

        优化点：
        1. 明确列出六类错别字类型（含多字/少字/乱序）
        2. 给出每种类型的示例，帮助 LLM 准确分类
        3. 要求返回 error_type 字段
        4. 要求返回字符级起止位置（start_pos, end_pos）
        5. 降低误判概率的说明

        Args:
            text:    待检查文本
            context: 上下文

        Returns:
            提示词字符串
        """
        parts = [
            "你是一个专业的文字校对专家。请仔细检查以下文本是否有错别字。",
            "",
            "【错别字类型定义】",
            "",
            "1. 同音错别字：发音相同，但用字错误。",
            "   例：\"我想吃平果\" → \"苹果\"（píngguǒ，同音）",
            "",
            "2. 形近错别字：字形相似，看错写错。",
            "   例：\"她戴了一顶红色的冒子\" → \"帽子\"（冒/帽 形近）",
            "",
            "3. 语法错别字（搭配错误）：词语搭配不符合语言习惯。",
            "   例：\"他学习很认直\" → \"认真\"（固定搭配）",
            "",
            "4. 多字错别字：文本中多了多余的字。",
            "   例：\"我今天去去公园\" → 删除一个\"去\"",
            "   例：\"这个问题我我不太明白\" → 删除一个\"我\"",
            "",
            "5. 少字错别字：文本中缺少必要的字。",
            "   例：\"我今天公园\" → 缺少\"去\"，应为\"我今天去公园\"",
            "   例：\"他喜欢吃苹果香蕉\" → 缺少\"和\"，应为\"他喜欢吃苹果和香蕉\"",
            "",
            "6. 乱序错别字：字或词的顺序颠倒。",
            "   例：\"我天今去公园\" → \"今天\"颠倒，应为\"我今天去公园\"",
            "   例：\"这个非常问题复杂\" → \"非常\"和\"复杂\"重叠，应为\"这个问题非常复杂\"",
            "",
            "【重要规则】",
            "- 专业术语、人名、地名、网络用语、方言，除非明确错误，否则不要纠正。",
            "- \"的/地/得\" 搭配错误属于语法错别字，请指出。",
            "- 多字/少字/乱序类型，请在 corrected_text 中直接给出修正后的完整句子。",
            "",
        ]

        if context:
            parts.append(f"【上下文】\n{context}")
            parts.append("")

        parts.append(f"【待检查文本】\n{text}")
        parts.append("")

        # ---- 要求输出格式 ----
        example = {
            "has_error": True,
            "corrections": [
                {
                    "original":      "原始错误片段（多字/乱序时用这个字段表示错误位置）",
                    "corrected":    "纠正后的片段（少字时这里填应添加的内容）",
                    "error_type":   "同音错别字 / 形近错别字 / 语法错别字 / 多字错别字 / 少字错别字 / 乱序错别字",
                    "confidence":   0.95,
                    "start_pos":    3,   # 错误片段在原文中的起始字符位置（从 0 开始）
                    "end_pos":      5,   # 错误片段在原文中的结束字符位置（不含）
                    "description":  "对错误的简要说明（可选）",
                }
            ],
            "corrected_text": "纠正后的完整文本",
        }

        parts.append("【输出要求】")
        parts.append("请严格按照以下 JSON 格式输出，不要输出任何解释性文字。")
        parts.append("")
        parts.append(json.dumps(example, ensure_ascii=False, indent=2))
        parts.append("")
        parts.append("【注意事项】")
        parts.append("1. 如果没有错别字，has_error 设为 false，corrections 设为空数组 []。")
        parts.append("2. 置信度 confidence 低于 0.6 的纠正建议不要给出。")
        parts.append("3. 多字错别字：original 填多余的字，corrected 填空字符串。")
        parts.append("4. 少字错别字：original 填缺失位置前的文字，corrected 填应添加的字。")
        parts.append("5. 乱序错别字：original 填顺序错误的片段，corrected 填正确顺序。")
        parts.append("6. start_pos 和 end_pos 必须准确对应原文字符位置。")
        parts.append("7. 只输出 JSON，不要输出 ```json ``` 标记。")

        return "\n".join(parts)

    # ------------------------------------------------------------------ #
    # 文本响应解析（LLM 未返回 JSON 时的兜底）
    # ------------------------------------------------------------------ #

    def _parse_text_response(self, response: str, original_text: str) -> dict:
        """
        解析非 JSON 格式的 LLM 响应（兜底逻辑）

        Args:
            response:      LLM 原始响应
            original_text: 原始文本

        Returns:
            解析后的结果字典
        """
        corrections = []

        # 尝试匹配："原词" → "纠正词" (原因)
        pattern = r'["\'](.*?)["\']\s*[→\-→]\s*["\'](.*?)["\'](?:\s*[\(（](.*?)[\)）])?'
        matches = re.findall(pattern, response)

        for match in matches:
            original  = match[0]
            corrected = match[1]
            reason    = match[2] if match[2] else "未知"

            # 尝试推断错误类型
            error_type = self._infer_error_type(original, corrected, reason)

            corrections.append({
                "original":    original,
                "corrected":   corrected,
                "error_type":  error_type,
                "confidence":  0.75,
                "start_pos":   -1,   # 无法从文本响应中解析位置
                "end_pos":     -1,
                "description": reason,
            })

        # 构造纠正后的文本
        corrected_text = original_text
        for c in corrections:
            if c["original"] and c["corrected"]:
                corrected_text = corrected_text.replace(c["original"], c["corrected"])

        return {
            "has_error":     len(corrections) > 0,
            "corrections":   corrections,
            "corrected_text": corrected_text,
        }

    def _infer_error_type(self, original: str, corrected: str, reason: str) -> str:
        """
        根据 original / corrected / reason 推断错别字类型

        Args:
            original:  原始错误片段
            corrected: 纠正后的片段
            reason:    LLM 给出的原因字符串

        Returns:
            错误类型字符串（六种之一）
        """
        reason_lower = reason.lower()

        # 优先从 reason 中匹配
        if "同音" in reason_lower or "音" in reason_lower:
            return ERROR_TYPE_TONE
        if "形近" in reason_lower or "形" in reason_lower:
            return ERROR_TYPE_SHAPE
        if "语法" in reason_lower or "搭配" in reason_lower:
            return ERROR_TYPE_GRAMMAR
        if "多字" in reason_lower or "多余" in reason_lower:
            return ERROR_TYPE_EXTRA
        if "少字" in reason_lower or "缺少" in reason_lower or "缺失" in reason_lower:
            return ERROR_TYPE_MISSING
        if "乱序" in reason_lower or "颠倒" in reason_lower or "顺序" in reason_lower:
            return ERROR_TYPE_SHUFFLE

        # 根据 original / corrected 长度推断
        if len(original) > 0 and len(corrected) == 0:
            return ERROR_TYPE_EXTRA     # 有多余字
        if len(original) == 0 and len(corrected) > 0:
            return ERROR_TYPE_MISSING   # 缺少字
        if len(original) == len(corrected) and original != corrected:
            # 长度相同但内容不同 → 可能是乱序或同音/形近
            if sorted(original) == sorted(corrected):
                return ERROR_TYPE_SHUFFLE
            return ERROR_TYPE_TONE      # 默认归为同音（最常见）

        return ERROR_TYPE_GRAMMAR      # 兜底

    # ------------------------------------------------------------------ #
    # 便捷方法
    # ------------------------------------------------------------------ #

    def correct_text(self, text: str, context: str = "") -> dict:
        """
        纠正单个文本（便捷方法）

        Args:
            text:    要纠正的文本
            context: 上下文

        Returns:
            纠正结果字典
        """
        result = self.execute(text=text, context=context)

        if result.success:
            return result.data
        else:
            return {
                "has_error":     False,
                "corrections":   [],
                "corrected_text": text,
                "error":         result.error,
            }

    def correct_texts(self, texts: List[str], context: str = "") -> List[dict]:
        """
        纠正多个文本（便捷方法）

        Args:
            texts:   要纠正的文本列表
            context: 上下文

        Returns:
            纠正结果字典列表
        """
        result = self.execute(texts=texts, context=context)

        if result.success:
            data = result.data
            results = []
            for i, text in enumerate(texts):
                results.append({
                    "original_text":  text,
                    "corrections":    data["corrections"][i] if i < len(data["corrections"]) else [],
                    "corrected_text": data["corrected_texts"][i]
                                        if data["corrected_texts"] and i < len(data["corrected_texts"])
                                        else text,
                })
            return results
        else:
            return [{
                "original_text":  text,
                "corrections":   [],
                "corrected_text": text,
                "error":         result.error,
            } for text in texts]

    def clear_cache(self) -> None:
        """清空缓存"""
        self._cache.clear()


# --------------------------------------------------------------------------- #
# 便捷函数
# --------------------------------------------------------------------------- #

def correct_text(text: str, context: str = "") -> dict:
    """
    纠正文本中的错别字（便捷函数）

    Args:
        text:    要纠正的文本
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
        texts:   要纠正的文本列表
        context: 上下文

    Returns:
        纠正结果字典列表
    """
    tool = TextCorrectionTool()
    return tool.correct_texts(texts, context)


# --------------------------------------------------------------------------- #
# 测试入口
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    tool = TextCorrectionTool()

    test_cases = [
        ("同音错别字", "我想吃平果",            "讨论健康饮食"),
        ("形近错别字", "她戴了一顶红色的冒子", "讨论穿搭"),
        ("语法错别字",  "他学习很认直",          "老师评价学生"),
        ("多字错别字",  "我今天去去公园",         "周末计划"),
        ("少字错别字",  "我今天公园",            "周末计划"),
        ("乱序错别字",  "我天今去公园",          "周末计划"),
    ]

    for name, text, ctx in test_cases:
        print(f"测试：{name}")
        print(f"  原文：{text}")
        result = tool.correct_text(text, ctx)
        print(f"  纠正：{result['corrected_text']}")
        print(f"  建议：{result['corrections']}")
        print()

    # 批量处理测试
    batch = ["我想吃平果", "他学习很认直", "这是正确的句子"]
    results = tool.correct_texts(batch, context="学生生活")
    print("批量处理：")
    for i, r in enumerate(results):
        marker = "✅" if not r["corrections"] else "❌"
        print(f"  {marker} {r['original_text']} → {r['corrected_text']}")
        if r["corrections"]:
            for c in r["corrections"]:
                print(f"      纠错：{c['original']} → {c['corrected']}  ({c.get('error_type', '')})")


# --------------------------------------------------------------------------- #
# 自动注册
# --------------------------------------------------------------------------- #

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
