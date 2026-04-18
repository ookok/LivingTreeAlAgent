# =================================================================
# 智能填表引擎 - Auto Fill Engine
# =================================================================
# 功能：
# 1. 从多个数据源获取建议值
# 2. 优先级排序和过滤
# 3. 生成填表建议
# =================================================================

import time
import re
from enum import Enum
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

from .form_parser import FormField, FormStructure, FieldSemanticType, FieldSource


class FillPriority(Enum):
    """填充优先级"""
    HIGH = 1      # 高优先级：直接填充
    MEDIUM = 2    # 中优先级：需要确认
    LOW = 3       # 低优先级：仅建议


class FillSource(Enum):
    """填充数据源"""
    KNOWLEDGE_BASE = "knowledge_base"      # 本地知识库
    BROWSER_AUTOFILL = "browser_autofill" # 浏览器自动填充
    CONTEXT = "context"                   # 上下文推测
    TEMPLATE = "template"                # 模板库
    AI_GENERATED = "ai_generated"         # AI生成
    HISTORY = "history"                   # 历史记录
    CLIPBOARD = "clipboard"              # 剪贴板


@dataclass
class FillSuggestion:
    """填表建议"""
    field_name: str
    field_semantic_type: FieldSemanticType

    # 建议值
    value: Any
    display_value: str = ""              # 显示用的值（如手机号显示为 138-****-5678）

    # 来源信息
    source: FillSource = FillSource.HISTORY
    source_detail: str = ""              # 如"知识库: 企业信息/营业执照"

    # 优先级
    priority: FillPriority = FillPriority.MEDIUM

    # 置信度
    confidence: float = 0.0              # 0-1

    # 关联信息
    related_suggestions: List['FillSuggestion'] = field(default_factory=list)

    # 额外信息
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.display_value:
            self.display_value = str(self.value)


@dataclass
class FillResult:
    """填充结果"""
    field_name: str
    success: bool
    value: Any = None
    error: str = ""
    suggestion_used: Optional[FillSuggestion] = None


class AutoFillEngine:
    """
    智能填表引擎

    数据源优先级：
    1. 本地知识库（高优先级，企业信息等）
    2. 浏览器自动填充（中等优先级，姓名电话等）
    3. 上下文推测（中等优先级）
    4. 历史记录（中等优先级）
    5. AI 生成（低优先级）
    """

    def __init__(self, knowledge_base=None, llm_client=None):
        self.knowledge_base = knowledge_base
        self.llm_client = llm_client

        # 缓存
        self._history_cache: Dict[str, List[Dict]] = defaultdict(list)
        self._context_cache: Dict[str, Any] = {}

        # 知识库接口（可选）
        self._kb = knowledge_base

    def get_suggestions(
        self,
        field: FormField,
        form: FormStructure,
        context: Dict[str, Any] = None
    ) -> List[FillSuggestion]:
        """
        获取字段填表建议

        Args:
            field: 表单字段
            form: 表单结构
            context: 上下文（当前页面/标签页信息）

        Returns:
            建议列表，按优先级排序
        """
        suggestions = []

        # 1. 知识库查询（高优先级）
        kb_suggestions = self._query_knowledge_base(field)
        suggestions.extend(kb_suggestions)

        # 2. 历史记录
        history_suggestions = self._query_history(field)
        suggestions.extend(history_suggestions)

        # 3. 上下文推测
        context_suggestions = self._query_context(field, form, context or {})
        suggestions.extend(context_suggestions)

        # 4. 浏览器自动填充（需要授权）
        browser_suggestions = self._query_browser_autofill(field)
        suggestions.extend(browser_suggestions)

        # 5. AI 生成（低优先级，用于复杂文本字段）
        if field.semantic_type in [FieldSemanticType.DESCRIPTION,
                                    FieldSemanticType.INTRODUCTION,
                                    FieldSemanticType.COMMENT]:
            ai_suggestions = self._generate_with_ai(field, form, context)
            suggestions.extend(ai_suggestions)

        # 去重和排序
        suggestions = self._deduplicate_and_rank(suggestions)

        return suggestions[:5]  # 最多返回5条建议

    def fill_field(
        self,
        field: FormField,
        suggestion: FillSuggestion
    ) -> FillResult:
        """
        填充单个字段

        Returns:
            FillResult: 填充结果
        """
        try:
            # 格式化值
            formatted_value = self._format_value(
                suggestion.value,
                field.field_type,
                field.semantic_type
            )

            # 更新历史缓存
            self._update_history(field, formatted_value, suggestion.source)

            return FillResult(
                field_name=field.name,
                success=True,
                value=formatted_value,
                suggestion_used=suggestion
            )
        except Exception as e:
            return FillResult(
                field_name=field.name,
                success=False,
                error=str(e)
            )

    def auto_fill_form(
        self,
        form: FormStructure,
        suggestions_map: Dict[str, FillSuggestion],
        auto_confirm_threshold: float = 0.9
    ) -> Dict[str, FillResult]:
        """
        自动填充整个表单

        Args:
            form: 表单结构
            suggestions_map: 字段名 -> 建议的映射
            auto_confirm_threshold: 自动确认置信度阈值

        Returns:
            填充结果映射
        """
        results = {}

        for field in form.fields:
            if field.readonly or field.disabled:
                continue

            if field.name in suggestions_map:
                suggestion = suggestions_map[field.name]

                # 高置信度自动填充
                if suggestion.confidence >= auto_confirm_threshold:
                    results[field.name] = self.fill_field(field, suggestion)
                else:
                    # 低置信度标记为待确认
                    results[field.name] = FillResult(
                        field_name=field.name,
                        success=False,
                        error="需要用户确认",
                        suggestion_used=suggestion
                    )

        return results

    # ========== 数据源查询 ==========

    def _query_knowledge_base(
        self,
        field: FormField
    ) -> List[FillSuggestion]:
        """从知识库查询"""
        if not self._kb:
            return []

        suggestions = []

        # 语义类型 -> 知识库路径映射
        semantic_to_kb = {
            FieldSemanticType.COMPANY_NAME: ["企业信息", "公司名称"],
            FieldSemanticType.COMPANY_CODE: ["企业信息", "统一社会信用代码"],
            FieldSemanticType.ADDRESS: ["企业信息", "注册地址"],
            FieldSemanticType.NAME: ["个人信息", "姓名"],
            FieldSemanticType.EMAIL: ["个人信息", "邮箱"],
            FieldSemanticType.PHONE_MOBILE: ["个人信息", "手机"],
            FieldSemanticType.ID_CARD: ["个人信息", "身份证号"],
        }

        if field.semantic_type in semantic_to_kb:
            kb_paths = semantic_to_kb[field.semantic_type]

            try:
                # 查询知识库
                value = self._kb.get_value(kb_paths)
                if value:
                    suggestions.append(FillSuggestion(
                        field_name=field.name,
                        field_semantic_type=field.semantic_type,
                        value=value,
                        source=FillSource.KNOWLEDGE_BASE,
                        source_detail=f"知识库: {'/'.join(kb_paths)}",
                        priority=FillPriority.HIGH,
                        confidence=0.85,
                        metadata={"kb_paths": kb_paths}
                    ))
            except Exception:
                pass

        return suggestions

    def _query_history(
        self,
        field: FormField
    ) -> List[FillSuggestion]:
        """从历史记录查询"""
        suggestions = []
        key = f"{field.semantic_type.value}:{field.name}"

        # 查找最近的历史值
        history = self._history_cache.get(key, [])
        history.extend(self._history_cache.get(field.semantic_type.value, []))

        # 去重并按时间排序
        seen = set()
        for record in reversed(history):
            value = record.get("value")
            if value and value not in seen:
                seen.add(value)

                # 计算频率权重
                frequency = record.get("frequency", 1)
                confidence = min(0.5 + frequency * 0.1, 0.85)

                suggestions.append(FillSuggestion(
                    field_name=field.name,
                    field_semantic_type=field.semantic_type,
                    value=value,
                    source=FillSource.HISTORY,
                    source_detail=f"历史记录 (使用{frequency}次)",
                    priority=FillPriority.MEDIUM,
                    confidence=confidence,
                    metadata={"frequency": frequency, "last_used": record.get("timestamp")}
                ))

        return suggestions

    def _query_context(
        self,
        field: FormField,
        form: FormStructure,
        context: Dict[str, Any]
    ) -> List[FillSuggestion]:
        """从上下文推测"""
        suggestions = []

        # 1. 从同页面其他字段值推断
        for other_field in form.fields:
            if other_field.is_filled and other_field.value:
                # 同一表单内的关联字段
                if self._are_related(field, other_field):
                    suggestions.append(FillSuggestion(
                        field_name=field.name,
                        field_semantic_type=field.semantic_type,
                        value=other_field.value,
                        source=FillSource.CONTEXT,
                        source_detail=f"来自同页面字段: {other_field.label}",
                        priority=FillPriority.MEDIUM,
                        confidence=0.6
                    ))

        # 2. 从打开的标签页提取信息
        tab_context = context.get("other_tabs", [])
        for tab in tab_context:
            tab_content = tab.get("content", "")
            if field.label and field.label in tab_content:
                # 从标签页内容中提取
                extracted = self._extract_from_text(tab_content, field.label)
                if extracted:
                    suggestions.append(FillSuggestion(
                        field_name=field.name,
                        field_semantic_type=field.semantic_type,
                        value=extracted,
                        source=FillSource.CONTEXT,
                        source_detail=f"来自标签页: {tab.get('title', '未知')}",
                        priority=FillPriority.LOW,
                        confidence=0.5
                    ))

        return suggestions

    def _query_browser_autofill(
        self,
        field: FormField
    ) -> List[FillSuggestion]:
        """浏览器自动填充（需要浏览器扩展支持）"""
        # 这需要与浏览器扩展通信
        # 简化实现：返回空列表
        return []

    def _generate_with_ai(
        self,
        field: FormField,
        form: FormStructure,
        context: Dict[str, Any]
    ) -> List[FillSuggestion]:
        """AI 生成内容"""
        if not self.llm_client:
            return []

        try:
            # 构建提示
            prompt = self._build_generation_prompt(field, form)

            # 调用 LLM
            result = self.llm_client.generate(prompt)

            if result:
                return [FillSuggestion(
                    field_name=field.name,
                    field_semantic_type=field.semantic_type,
                    value=result,
                    source=FillSource.AI_GENERATED,
                    source_detail="AI 生成",
                    priority=FillPriority.LOW,
                    confidence=0.5,
                    metadata={"prompt": prompt}
                )]
        except Exception:
            pass

        return []

    # ========== 辅助方法 ==========

    def _are_related(self, field1: FormField, field2: FormField) -> bool:
        """判断两个字段是否相关"""
        # 相同语义类型
        if field1.semantic_type == field2.semantic_type:
            return True

        # 地址相关
        addr_types = [
            FieldSemanticType.ADDRESS_PROVINCE,
            FieldSemanticType.ADDRESS_CITY,
            FieldSemanticType.ADDRESS_DISTRICT,
            FieldSemanticType.ADDRESS_STREET,
        ]
        if field1.semantic_type in addr_types and field2.semantic_type in addr_types:
            return True

        # 名称相关
        name_types = [FieldSemanticType.NAME_FAMILY, FieldSemanticType.NAME_GIVEN]
        if field1.semantic_type in name_types and field2.semantic_type in name_types:
            return True

        return False

    def _extract_from_text(self, text: str, label: str) -> Optional[str]:
        """从文本中提取 label 对应的值"""
        # 简单实现：查找 label: value 模式
        patterns = [
            rf"{label}[：:]\s*(.+?)(?:\n|$)",
            rf"{label}\s+is\s+(.+?)(?:\n|$)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return None

    def _deduplicate_and_rank(
        self,
        suggestions: List[FillSuggestion]
    ) -> List[FillSuggestion]:
        """去重和排序"""
        # 按值去重
        seen = {}
        unique = []
        for s in suggestions:
            key = str(s.value)
            if key not in seen or s.confidence > seen[key].confidence:
                seen[key] = s
                unique.append(s)

        # 按优先级和置信度排序
        unique.sort(key=lambda x: (x.priority.value, -x.confidence), reverse=False)

        return unique

    def _format_value(
        self,
        value: Any,
        field_type,  # FieldType enum
        semantic_type: FieldSemanticType
    ) -> str:
        """格式化值以匹配字段类型"""
        str_value = str(value)

        # 手机号格式化
        if semantic_type == FieldSemanticType.PHONE_MOBILE:
            digits = re.sub(r"\D", "", str_value)
            if len(digits) == 11:
                return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"

        # 金额格式化
        if semantic_type in [FieldSemanticType.AMOUNT, FieldSemanticType.PRICE]:
            try:
                amount = float(re.sub(r"[^\d.]", "", str_value))
                return f"{amount:.2f}"
            except ValueError:
                pass

        # 日期格式化
        if semantic_type == FieldSemanticType.DATE:
            # 标准化为 YYYY-MM-DD
            date_match = re.search(r"(\d{4})[年.\-](\d{1,2})[月.\-](\d{1,2})", str_value)
            if date_match:
                return f"{date_match.group(1)}-{int(date_match.group(2)):02d}-{int(date_match.group(3)):02d}"

        return str_value

    def _update_history(
        self,
        field: FormField,
        value: str,
        source: FillSource
    ):
        """更新历史记录"""
        key = f"{field.semantic_type.value}:{field.name}"

        # 查找现有记录
        found = False
        for record in self._history_cache[key]:
            if record.get("value") == value:
                record["frequency"] = record.get("frequency", 0) + 1
                record["timestamp"] = time.time()
                found = True
                break

        if not found:
            self._history_cache[key].append({
                "value": value,
                "frequency": 1,
                "timestamp": time.time(),
                "source": source.value
            })

        # 也按语义类型记录
        self._history_cache[field.semantic_type.value].append({
            "value": value,
            "frequency": 1,
            "timestamp": time.time(),
            "source": source.value
        })

    def _build_generation_prompt(
        self,
        field: FormField,
        form: FormStructure
    ) -> str:
        """构建 AI 生成提示"""
        # 获取表单上下文
        form_context = []
        for f in form.fields[:10]:  # 只取前10个字段
            if f.is_filled:
                form_context.append(f"{f.label}: {f.value}")

        prompt = f"""请为以下表单字段生成合适的内容：

字段：{field.label}
类型：{field.semantic_type.value}
{"可选上下文：" + " | ".join(form_context) if form_context else ""}

要求：
1. 内容要符合中国语境和常规格式
2. 如果是描述类字段，内容应简洁、专业
3. 不要编造具体的人名、公司名、金额等真实信息
4. 如果不确定，可以生成一个示例占位符

生成的内容："""

        return prompt

    def set_knowledge_base(self, kb):
        """设置知识库"""
        self._kb = kb

    def set_llm_client(self, llm):
        """设置 LLM 客户端"""
        self.llm_client = llm

    def load_history_from_disk(self, filepath: str):
        """从磁盘加载历史记录"""
        import json
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._history_cache = defaultdict(list, data)
        except Exception:
            pass

    def save_history_to_disk(self, filepath: str):
        """保存历史记录到磁盘"""
        import json
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(dict(self._history_cache), f, ensure_ascii=False, indent=2)
        except Exception:
            pass
