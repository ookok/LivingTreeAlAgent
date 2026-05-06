"""Syllogism — 三段论推理验证。

实现亚里士多德三段论的核心模式：
  BARBARA:  所有A是B ∧ 所有B是C → 所有A是C
  CELARENT: 所有A是B ∧ 没有B是C → 没有A是C
  DARII:    所有A是B ∧ 有些A是C → 有些B是C
  FERIO:    没有A是B ∧ 有些A是C → 有些C不是B

每个 syllogism 返回 (结论, 置信度, 有效性标志)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from loguru import logger


class Quantifier(str, Enum):
    ALL = "all"        # 所有
    SOME = "some"      # 有些
    NONE = "none"      # 没有
    SOME_NOT = "some_not"  # 有些不


class SyllogismFigure(str, Enum):
    """三段论格 (4 figures of syllogism)."""
    FIGURE_1 = "1"  # M-P, S-M → S-P
    FIGURE_2 = "2"  # P-M, S-M → S-P
    FIGURE_3 = "3"  # M-P, M-S → S-P
    FIGURE_4 = "4"  # P-M, M-S → S-P


@dataclass
class CategoricalProposition:
    """直言命题 (A/E/I/O型)。"""
    subject: str        # 主项 S
    predicate: str      # 谓项 P
    quantifier: Quantifier
    confidence: float = 1.0


@dataclass
class SyllogismResult:
    conclusion: CategoricalProposition
    figure: SyllogismFigure
    mood: str = ""            # 三段论式名 (e.g. "BARBARA")
    valid: bool = True
    confidence: float = 1.0
    explanation: str = ""


class SyllogismVerifier:
    """三段论推理验证器。

    支持4格19个有效式（含5个弱式）的自动验证，
    以及自定义命题间的三段论推理。
    """

    # 24个有效式映射（key: (major_q, minor_q, conclusion_q, figure)）
    VALID_MOODS = {
        ("all", "all", "all", "1"): ("BARBARA", SyllogismFigure.FIGURE_1),
        ("none", "all", "none", "1"): ("CELARENT", SyllogismFigure.FIGURE_1),
        ("all", "some", "some", "1"): ("DARII", SyllogismFigure.FIGURE_1),
        ("none", "some", "some_not", "1"): ("FERIO", SyllogismFigure.FIGURE_1),
        ("all", "all", "some", "1"): ("BARBARI", SyllogismFigure.FIGURE_1),
        ("none", "all", "some_not", "1"): ("CELARONT", SyllogismFigure.FIGURE_1),
        ("none", "all", "none", "2"): ("CESARE", SyllogismFigure.FIGURE_2),
        ("all", "none", "none", "2"): ("CAMESTRES", SyllogismFigure.FIGURE_2),
        ("none", "some", "some_not", "2"): ("FESTINO", SyllogismFigure.FIGURE_2),
        ("all", "some_not", "some_not", "2"): ("BAROCO", SyllogismFigure.FIGURE_2),
        ("all", "all", "some", "3"): ("DARAPTI", SyllogismFigure.FIGURE_3),
        ("none", "all", "some_not", "3"): ("FELAPTON", SyllogismFigure.FIGURE_3),
        ("all", "some", "some", "3"): ("DATISI", SyllogismFigure.FIGURE_3),
        ("some", "all", "some", "3"): ("DISAMIS", SyllogismFigure.FIGURE_3),
        ("some_not", "all", "some_not", "3"): ("BOCARDO", SyllogismFigure.FIGURE_3),
        ("none", "some", "some_not", "3"): ("FERISON", SyllogismFigure.FIGURE_3),
        ("all", "all", "some", "4"): ("BRAMANTIP", SyllogismFigure.FIGURE_4),
        ("all", "none", "none", "4"): ("CAMENES", SyllogismFigure.FIGURE_4),
        ("some", "none", "some_not", "4"): ("DIMARIS", SyllogismFigure.FIGURE_4),
        ("none", "all", "some_not", "4"): ("FESAPO", SyllogismFigure.FIGURE_4),
        ("none", "some", "some_not", "4"): ("FRESISON", SyllogismFigure.FIGURE_4),
    }

    def verify(
        self,
        major: CategoricalProposition,   # 大前提
        minor: CategoricalProposition,   # 小前提
        figure: SyllogismFigure,
    ) -> SyllogismResult:
        """验证三段论是否有效。

        标准三段论形式：
          大前提: M-P (中项-大项)
          小前提: S-M (小项-中项) [图1]
          结论:   S-P (小项-大项)

        每一格有不同的项排列方式。
        """
        major_quant = major.quantifier.value
        minor_quant = minor.quantifier.value

        if figure == SyllogismFigure.FIGURE_1:
            conclusion_quant, valid = self._figure1(major_quant, minor_quant)
        elif figure == SyllogismFigure.FIGURE_2:
            conclusion_quant, valid = self._figure2(major_quant, minor_quant)
        elif figure == SyllogismFigure.FIGURE_3:
            conclusion_quant, valid = self._figure3(major_quant, minor_quant)
        elif figure == SyllogismFigure.FIGURE_4:
            conclusion_quant, valid = self._figure4(major_quant, minor_quant)
        else:
            return SyllogismResult(
                conclusion=CategoricalProposition(
                    subject=minor.subject, predicate=major.predicate,
                    quantifier=Quantifier.SOME,
                ),
                figure=figure,
                valid=False,
                explanation=f"Unknown figure: {figure}",
            )

        mood_key = (major_quant, minor_quant, conclusion_quant, figure.value)
        mood_info = self.VALID_MOODS.get(mood_key)

        if valid and mood_info:
            mood_name = mood_info[0]
            explanation = f"Valid syllogism: {mood_name} (Figure {figure.value})"
        elif valid:
            mood_name = "custom"
            explanation = f"Valid custom syllogism (Figure {figure.value})"
        else:
            mood_name = "invalid"
            explanation = f"Invalid syllogism: {major.subject}-{major.predicate} ∧ {minor.subject}-{minor.predicate}"

        confidence = min(major.confidence, minor.confidence) if valid else 0.0

        return SyllogismResult(
            conclusion=CategoricalProposition(
                subject=minor.subject,
                predicate=major.predicate,
                quantifier=Quantifier(conclusion_quant) if valid else Quantifier.SOME,
                confidence=confidence,
            ),
            figure=figure,
            mood=mood_name,
            valid=valid,
            confidence=confidence,
            explanation=explanation,
        )

    def verify_simple(
        self,
        major_all: bool, major_affirmative: bool,
        minor_all: bool, minor_affirmative: bool,
        figure: SyllogismFigure = SyllogismFigure.FIGURE_1,
    ) -> SyllogismResult:
        """简化接口：用布尔值表示量词（全称/特称）和肯定/否定。"""
        major_quant = Quantifier.ALL if major_all else Quantifier.SOME
        minor_quant = Quantifier.ALL if minor_all else Quantifier.SOME

        major_pred = "P_" + ("is" if major_affirmative else "is_not")
        minor_pred = "S_" + ("is" if minor_affirmative else "is_not")

        if not major_affirmative:
            major_quant = Quantifier.NONE if major_all else Quantifier.SOME_NOT
        if not minor_affirmative:
            minor_quant = Quantifier.NONE if minor_all else Quantifier.SOME_NOT

        major = CategoricalProposition(subject="M", predicate=major_pred, quantifier=major_quant)
        minor = CategoricalProposition(subject="S", predicate=minor_pred, quantifier=minor_quant)

        return self.verify(major, minor, figure)

    def explain(self, result: SyllogismResult) -> str:
        """生成三段论的自然语言解释。"""
        if not result.valid:
            return f"Invalid syllogism: {result.explanation}"

        c = result.conclusion
        quant_text = {
            Quantifier.ALL: "所有",
            Quantifier.SOME: "有些",
            Quantifier.NONE: "没有",
            Quantifier.SOME_NOT: "有些不",
        }

        return (
            f"{result.mood}三段论 (Figure {result.figure.value}): "
            f"前提 → {quant_text.get(c.quantifier, '')}{c.subject}是{c.predicate} "
            f"(置信度: {c.confidence:.0%}). {result.explanation}"
        )

    # ── Figure-specific logic ──

    def _figure1(self, major_q: str, minor_q: str) -> tuple[str, bool]:
        """图1: M-P, S-M → S-P"""
        if major_q == "all" and minor_q == "all":
            return "all", True  # BARBARA
        if major_q == "none" and minor_q == "all":
            return "none", True  # CELARENT
        if major_q == "all" and minor_q == "some":
            return "some", True  # DARII
        if major_q == "none" and minor_q == "some":
            return "some_not", True  # FERIO
        return "some", False

    def _figure2(self, major_q: str, minor_q: str) -> tuple[str, bool]:
        """图2: P-M, S-M → S-P"""
        if major_q == "none" and minor_q == "all":
            return "none", True  # CESARE
        if major_q == "all" and minor_q == "none":
            return "none", True  # CAMESTRES
        if major_q == "none" and minor_q == "some":
            return "some_not", True  # FESTINO
        if major_q == "all" and minor_q == "some_not":
            return "some_not", True  # BAROCO
        return "some", False

    def _figure3(self, major_q: str, minor_q: str) -> tuple[str, bool]:
        """图3: M-P, M-S → S-P"""
        if major_q == "all" and minor_q == "all":
            return "some", True  # DARAPTI
        if major_q == "none" and minor_q == "all":
            return "some_not", True  # FELAPTON
        if major_q == "all" and minor_q == "some":
            return "some", True  # DATISI
        if major_q == "some" and minor_q == "all":
            return "some", True  # DISAMIS
        if major_q == "some_not" and minor_q == "all":
            return "some_not", True  # BOCARDO
        if major_q == "none" and minor_q == "some":
            return "some_not", True  # FERISON
        return "some", False

    def _figure4(self, major_q: str, minor_q: str) -> tuple[str, bool]:
        """图4: P-M, M-S → S-P"""
        if major_q == "all" and minor_q == "all":
            return "some", True  # BRAMANTIP
        if major_q == "all" and minor_q == "none":
            return "none", True  # CAMENES
        if major_q == "some" and minor_q == "none":
            return "some_not", True  # DIMARIS
        if major_q == "none" and minor_q == "all":
            return "some_not", True  # FESAPO
        if major_q == "none" and minor_q == "some":
            return "some_not", True  # FRESISON
        return "some", False
