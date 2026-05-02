"""
Karpathy Skills 核心规则定义
工程师行为准则（源于 Andrej Karpathy）
"""

# 工程师行为准则文本（可注入到 System Prompt）
KARPATHY_RULES_TEXT = """
## 工程师行为准则（源于 Andrej Karpathy）

### 1. 不隐藏困惑（No Hiding Confusion）
- 若需求/代码有歧义，必须列出所有可能解读并追问确认
- 禁止自行选择一种解读后沉默执行
- 检测到不确定信息时，立即暂停并请求澄清

### 2. 极简实现（Minimal Implementation）
- 写完代码后自问："资深工程师会觉得这过度设计吗？"
- 若是，删减至仅满足需求的最少代码
- 优先选择更简单、更直接的实现，除非有明确理由

### 3. 最小接触（Minimal Touch）
- 编辑旧代码时，只修改与任务直接相关的部分
- 不顺手"清理"无关注释、格式、变量命名
- 清理范围仅限于：本次引入的残留（临时变量/函数/导入）

### 4. 目标驱动（Goal-Driven）
- 多步任务先输出≤3步的计划，并定义可验证的成功标准
- 成功标准示例："测试通过 + 无性能衰退" 或 "输出格式正确"
- 循环执行直到所有成功标准满足

### 5. 主动权衡（Explicit Trade-offs）
- 在关键决策点展示权衡："方案A快但耦合，方案B慢但解耦"
- 让用户了解决策利弊后再执行
- 不替用户做隐性选择
"""


class AmbiguitySignal:
    """歧义信号数据结构"""

    def __init__(
        self,
        ambiguity_type: str,
        possible_interpretations: list[str],
        original_text: str,
        confidence: float = 0.5,
    ):
        """
        Args:
            ambiguity_type: 歧义类型 (requirement/interface/behavior/data)
            possible_interpretations: 可能的解读列表
            original_text: 原始文本片段
            confidence: 歧义置信度 0.0-1.0
        """
        self.ambiguity_type = ambiguity_type
        self.possible_interpretations = possible_interpretations
        self.original_text = original_text
        self.confidence = confidence
        self.resolved = False
        self.selected_interpretation = None

    def to_prompt(self) -> str:
        """转换为提示文本"""
        options = "\n".join(
            f"  选项{i+1}: {opt}"
            for i, opt in enumerate(self.possible_interpretations)
        )
        return f"""
【检测到需求歧义】
类型: {self.ambiguity_type}
原文: {self.original_text[:100]}...

{options}

请确认你的意图：直接回复选项编号（1/2/3...）或补充细节
"""


class AmbiguityDetector:
    """歧义检测器 - 分析用户需求中的潜在歧义"""

    # 歧义触发关键词
    AMBIGUITY_KEYWORDS = {
        "requirement": ["可能", "大概", "差不多", "类似", "参考", "参照"],
        "interface": ["接口", "参数", "返回", "格式", "结构", "字段"],
        "behavior": ["自动", "智能", "处理", "判断", "逻辑", "规则"],
        "data": ["数据", "存储", "保存", "读取", "加载", "输入", "输出"],
    }

    # 低置信度指示词
    UNCERTAINTY_MARKERS = [
        "我理解",
        "可能需要",
        "也许",
        "应该可以",
        "不确定",
        "我猜",
        "大概",
        "看起来像",
        "初步",
        "暂定",
    ]

    # 过度设计风险模式
    OVER_ENGINEERING_PATTERNS = [
        "factory",
        "abstract",
        "baseclass",
        "interface",
        "polymorphism",
        "decorator",
        "observer",
        "strategy",
        "builder",
        "singleton",
        "facade",
    ]

    def __init__(self):
        self._history: list[AmbiguitySignal] = []

    def detect(self, text: str) -> list[AmbiguitySignal]:
        """
        检测文本中的潜在歧义

        Args:
            text: 用户输入的原始文本

        Returns:
            检测到的歧义信号列表
        """
        signals = []
        text_lower = text.lower()

        # 1. 检测不确定性标记
        for marker in self.UNCERTAINTY_MARKERS:
            if marker in text_lower:
                signals.append(
                    AmbiguitySignal(
                        ambiguity_type="requirement",
                        possible_interpretations=[
                            f"按'{marker}'的倾向理解",
                            "忽略该倾向，按更通用的方式理解",
                        ],
                        original_text=text,
                        confidence=0.6,
                    )
                )
                break

        # 2. 检测模糊需求词
        for category, keywords in self.AMBIGUITY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text and len(text) > 20:
                    # 发现关键词但上下文不明确
                    if not self._has_specific_context(text, keyword):
                        signals.append(
                            AmbiguitySignal(
                                ambiguity_type=category,
                                possible_interpretations=self._generate_interpretations(
                                    keyword, category
                                ),
                                original_text=text,
                                confidence=0.5,
                            )
                        )
                        break

        # 3. 检测语言混合导致的歧义
        if self._is_mixed_language(text):
            signals.append(
                AmbiguitySignal(
                    ambiguity_type="requirement",
                    possible_interpretations=[
                        "按中文语义理解",
                        "按英文语义理解",
                        "中英混合，按最常用方式理解",
                    ],
                    original_text=text,
                    confidence=0.4,
                )
            )

        self._history.extend(signals)
        return signals

    def _has_specific_context(self, text: str, keyword: str) -> bool:
        """检查关键词是否有具体上下文"""
        return '"' in text or "'" in text or "(" in text

    def _generate_interpretations(self, keyword: str, category: str) -> list[str]:
        """为关键词生成可能的解读"""
        templates = {
            "requirement": ["精确实现字面含义", "按常规惯例理解"],
            "interface": ["按最简单方式实现", "按行业标准接口设计"],
            "behavior": ["默认行为：静默处理", "默认行为：抛出异常"],
            "data": ["持久化存储", "仅内存临时存储"],
        }
        return templates.get(category, ["精确理解", "按惯例理解"])

    def _is_mixed_language(self, text: str) -> bool:
        """检测是否中英混合"""
        has_cn = any("\u4e00" <= c <= "\u9fff" for c in text)
        en_chars = [c for c in text if c.isalpha() and ord(c) > 127]
        return has_cn and len(en_chars) > 5

    def check_code_complexity(self, code: str) -> dict:
        """
        检查代码复杂度，检测过度设计风险

        Returns:
            dict with keys: is_over_engineered, patterns_found, suggestion
        """
        code_lower = code.lower()
        patterns_found = [
            p for p in self.OVER_ENGINEERING_PATTERNS if p in code_lower
        ]

        lines = [l for l in code.split("\n") if l.strip()]
        functions = code.count("def ") + code.count("async def ")

        is_over_engineered = len(lines) > 50 and functions > 5

        return {
            "is_over_engineered": is_over_engineered,
            "patterns_found": patterns_found,
            "suggestion": "考虑使用更简单的函数式实现" if is_over_engineered else "代码复杂度正常",
        }

    def get_history(self) -> list[AmbiguitySignal]:
        """获取检测历史"""
        return self._history.copy()


# 全局单例
_detector = None


def get_detector() -> AmbiguityDetector:
    """获取全局歧义检测器单例"""
    global _detector
    if _detector is None:
        _detector = AmbiguityDetector()
    return _detector