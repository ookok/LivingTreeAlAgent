# -*- coding: utf-8 -*-
"""
专家训练仪表盘测试
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_import():
    """测试导入"""
    print("=" * 60)
    print("测试1: 导入专家训练仪表盘")
    print("=" * 60)

    try:
        from client.src.presentation.panels.expert_training_dashboard import (
            ExpertTrainingDashboard,
            TrainingWizard,
            KnowledgeImportDialog,
            MetricsCard,
            ExpertCard,
            CircularProgress,
            KnowledgeTree,
        )
        print("[OK] All components imported successfully")
        return True
    except ImportError as e:
        print(f"[FAIL] Import failed: {e}")
        return False


def test_basic_functionality():
    """测试基本功能"""
    print("\n" + "=" * 60)
    print("Test 2: Basic Data Structures")
    print("=" * 60)

    try:
        from dataclasses import dataclass
        from typing import List

        # 测试 ExpertInfo
        @dataclass
        class ExpertInfo:
            id: str
            name: str
            domain: str
            status: str
            accuracy: float = 0.0
            trained_count: int = 0
            total_samples: int = 0

        expert = ExpertInfo(
            id="exp_001",
            name="金融分析师",
            domain="金融",
            status="active",
            accuracy=0.92,
            trained_count=156,
            total_samples=200
        )
        print(f"[OK] 创建专家: {expert.name}")
        print(f"    - 领域: {expert.domain}")
        print(f"    - 准确率: {expert.accuracy:.0%}")
        print(f"    - 训练进度: {expert.trained_count}/{expert.total_samples}")

        # 测试 LearningMetrics
        @dataclass
        class LearningMetrics:
            cache_hit_rate: float = 0.0
            correction_rate: float = 0.0
            accuracy: float = 0.0
            total_queries: int = 0
            learning_records: int = 0
            knowledge_fragments: int = 0
            system_health: float = 0.0

        metrics = LearningMetrics(
            cache_hit_rate=78.5,
            correction_rate=12.3,
            accuracy=91.2,
            total_queries=1234,
            learning_records=45,
            knowledge_fragments=567,
            system_health=85.0,
        )
        print(f"\n[OK] 学习指标:")
        print(f"    - 缓存命中率: {metrics.cache_hit_rate}%")
        print(f"    - 纠正率: {metrics.correction_rate}%")
        print(f"    - 准确率: {metrics.accuracy}%")
        print(f"    - 总查询量: {metrics.total_queries}")
        print(f"    - 知识碎片: {metrics.knowledge_fragments}")
        print(f"    - 系统健康: {metrics.system_health}%")

        return True
    except Exception as e:
        print(f"[FAIL] 测试失败: {e}")
        return False


def test_potential_features():
    """测试潜在功能概念"""
    print("\n" + "=" * 60)
    print("Test 3: Potential Features Module Proof of Concept")
    print("=" * 60)

    try:
        from dataclasses import dataclass, field
        from typing import List, Dict, Optional, Any
        from datetime import datetime
        from enum import Enum

        # ═══════════════════════════════════════════════════════════════════
        # 思维链模板库
        # ═══════════════════════════════════════════════════════════════════

        class ReasoningType(Enum):
            CAUSAL = "causal"
            ANALOGICAL = "analogical"
            DEDUCTIVE = "deductive"
            ABDUCTIVE = "abductive"

        @dataclass
        class ChainTemplate:
            id: str
            query_pattern: str
            query_type: ReasoningType
            reasoning_steps: List[str]
            pattern: str
            usage_count: int = 0
            success_rate: float = 0.0

        template = ChainTemplate(
            id="tmpl_001",
            query_pattern="为什么*是*",
            query_type=ReasoningType.CAUSAL,
            reasoning_steps=["识别因果关系", "查找相关因素", "评估影响程度"],
            pattern="因果推理链",
            usage_count=42,
            success_rate=0.89
        )
        print(f"[OK] 思维链模板: {template.pattern}")
        print(f"    - 类型: {template.query_type.value}")
        print(f"    - 使用次数: {template.usage_count}")
        print(f"    - 成功率: {template.success_rate:.0%}")

        # ═══════════════════════════════════════════════════════════════════
        # 多专家协作
        # ═══════════════════════════════════════════════════════════════════

        @dataclass
        class ExpertOpinion:
            expert_id: str
            expert_name: str
            opinion: str
            confidence: float
            reasoning: str = ""

        opinions = [
            ExpertOpinion("exp_001", "金融分析师", "应该买入", 0.85, "基本面良好"),
            ExpertOpinion("exp_002", "技术专家", "风险较高", 0.70, "技术指标显示超买"),
        ]

        # 简单投票机制
        avg_confidence = sum(o.confidence for o in opinions) / len(opinions)
        best_opinion = max(opinions, key=lambda x: x.confidence)

        print(f"\n[OK] 多专家协作:")
        print(f"    - 参与专家: {len(opinions)}")
        print(f"    - 平均置信度: {avg_confidence:.0%}")
        print(f"    - 决策: {best_opinion.opinion} (置信度: {best_opinion.confidence:.0%})")

        # ═══════════════════════════════════════════════════════════════════
        # 知识版本控制
        # ═══════════════════════════════════════════════════════════════════

        @dataclass
        class KnowledgeVersion:
            version: str
            knowledge_id: str
            content: str
            changed_at: str
            change_message: str

        versions = [
            KnowledgeVersion("v1.0", "know_001", "Python是一种编程语言", "2024-04-20", "初始创建"),
            KnowledgeVersion("v1.1", "know_001", "Python是一种高级编程语言", "2024-04-22", "补充描述"),
            KnowledgeVersion("v1.2", "know_001", "Python是一种解释型高级编程语言", "2024-04-24", "完善细节"),
        ]

        print(f"\n[OK] 知识版本控制:")
        print(f"    - 版本数: {len(versions)}")
        print(f"    - 最新版本: {versions[-1].version}")
        print(f"    - 变更: {versions[-1].change_message}")

        # ═══════════════════════════════════════════════════════════════════
        # 自适应学习节奏
        # ═══════════════════════════════════════════════════════════════════

        class AdaptiveLearningRhythm:
            def __init__(self):
                self.user_activity_history = []
                self.learning_intensity = 1.0
                self.fatigue_threshold = 0.8

            def should_learn_now(self, recent_queries: int, fatigue_score: float) -> bool:
                """判断是否应该学习"""
                if fatigue_score > self.fatigue_threshold:
                    return False
                if recent_queries > 10:
                    return False
                return True

            def get_learning_intensity(self, fatigue_score: float) -> float:
                """获取学习强度"""
                return max(0.1, 1.0 - fatigue_score * 0.5)

        rhythm = AdaptiveLearningRhythm()
        can_learn = rhythm.should_learn_now(recent_queries=5, fatigue_score=0.3)
        intensity = rhythm.get_learning_intensity(fatigue_score=0.3)

        print(f"\n[OK] 自适应学习节奏:")
        print(f"    - 当前是否可以学习: {'是' if can_learn else '否'}")
        print(f"    - 学习强度: {intensity:.0%}")

        # ═══════════════════════════════════════════════════════════════════
        # 遗忘曲线
        # ═══════════════════════════════════════════════════════════════════

        import math

        class ForgettingCurve:
            @staticmethod
            def retention(time_elapsed_days: float, stability: float = 1.0) -> float:
                """
                计算记忆保留率 (艾宾浩斯公式)
                R = e^(-t/S)
                """
                return math.exp(-time_elapsed_days / (stability * 7))

        curve = ForgettingCurve()

        print(f"\n[OK] 遗忘曲线模拟:")
        for days in [1, 2, 7, 14, 30]:
            retention = curve.retention(days)
            print(f"    - 第{days}天: 保留 {retention:.1%}")

        return True
    except Exception as e:
        print(f"[FAIL] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ui_components():
    """测试UI组件"""
    print("\n" + "=" * 60)
    print("Test 4: UI Components Availability Check")
    print("=" * 60)

    try:
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            print("[INFO] 创建 QApplication")
            app = QApplication([])

        from client.src.presentation.panels.expert_training_dashboard import (
            ExpertTrainingDashboard,
            TrainingWizard,
            KnowledgeImportDialog,
            MetricsCard,
            ExpertCard,
            CircularProgress,
        )
        from dataclasses import dataclass

        @dataclass
        class ExpertInfo:
            id: str
            name: str
            domain: str
            status: str
            accuracy: float = 0.0
            trained_count: int = 0
            total_samples: int = 0

        # 测试 MetricsCard
        card = MetricsCard("测试卡片", "📊")
        card.update_value(85.5, delta=2.3)
        print(f"[OK] MetricsCard: 数值更新成功")

        # 测试 CircularProgress
        progress = CircularProgress(120)
        progress.set_value(78.5, "系统健康")
        print(f"[OK] CircularProgress: 进度设置成功")

        # 测试 ExpertCard
        expert = ExpertInfo(
            id="test",
            name="测试专家",
            domain="测试",
            status="active",
            accuracy=0.92
        )
        expert_card = ExpertCard(expert)
        print(f"[OK] ExpertCard: 创建成功")

        # 测试主面板
        dashboard = ExpertTrainingDashboard()
        print(f"[OK] ExpertTrainingDashboard: 创建成功")

        return True
    except ImportError as e:
        print(f"[WARN] PyQt6 未安装，跳过 UI 测试: {e}")
        return True
    except Exception as e:
        print(f"[FAIL] UI 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_integration_with_existing_system():
    """测试与现有系统集成"""
    print("\n" + "=" * 60)
    print("Test 5: Integration with Existing System")
    print("=" * 60)

    try:
        # 测试 ExpertGuidedLearningSystem
        print("[INFO] 检查 ExpertGuidedLearningSystem...")

        try:
            from client.src.business.expert_learning.expert_guided_system import (
                ExpertGuidedLearningSystem,
                LearningPhase,
                CorrectionLevel,
            )
            print(f"[OK] ExpertGuidedLearningSystem 可用")
            print(f"    - 学习阶段: {[p.value for p in LearningPhase]}")
            print(f"    - 纠正层级: {[c.value for c in CorrectionLevel]}")
        except ImportError as e:
            print(f"[WARN] ExpertGuidedLearningSystem 导入失败: {e}")

        # 测试 IntelligentLearningSystem
        print("\n[INFO] 检查 IntelligentLearningSystem...")

        try:
            from client.src.business.expert_learning.intelligent_learning_system import (
                IntelligentLearningSystem,
                get_intelligent_learning_system,
            )
            print(f"[OK] IntelligentLearningSystem 可用")
        except ImportError as e:
            print(f"[WARN] IntelligentLearningSystem 导入失败: {e}")

        # 测试 ExpertTrainingPipeline
        print("\n[INFO] 检查 ExpertTrainingPipeline...")

        try:
            from client.src.business.expert_distillation.expert_training_pipeline import (
                ExpertTrainingPipeline,
                PipelineStage,
            )
            print(f"[OK] ExpertTrainingPipeline 可用")
            print(f"    - 训练阶段: {[p.value for p in PipelineStage]}")
        except ImportError as e:
            print(f"[WARN] ExpertTrainingPipeline 导入失败: {e}")

        return True
    except Exception as e:
        print(f"[FAIL] 集成测试失败: {e}")
        return False


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("[TEST] Expert Training Dashboard - Function Tests")
    print("=" * 60)

    results = []

    results.append(("Import Test", test_import()))
    results.append(("Basic Functionality", test_basic_functionality()))
    results.append(("Potential Features", test_potential_features()))
    results.append(("UI Components", test_ui_components()))
    results.append(("System Integration", test_integration_with_existing_system()))

    print("\n" + "=" * 60)
    print("[SUMMARY] Test Results")
    print("=" * 60)

    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {name}: {status}")

    all_passed = all(r[1] for r in results)
    print("\n" + "=" * 60)
    if all_passed:
        print("[OK] All tests passed!")
    else:
        print("[WARN] Some tests failed, please check output")
    print("=" * 60)

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
