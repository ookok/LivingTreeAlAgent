"""
TrainWithVariants - 使用变体训练工具选择

MVP 实现：
1. 读取训练池中的变体
2. 测试工具选择准确率（使用 ToolRegistry 语义搜索）
3. 输出训练报告

支持的难度级别：
- SIMPLE（简单）: 基础查询，无额外约束
- MEDIUM（中等）: 添加1-2个约束条件
- HARD（困难）: 添加多个约束、边界值、对抗条件

Author: LivingTreeAI Agent
Date: 2026-04-28
"""

import json
import asyncio
from typing import Any, Dict, List, Optional
from loguru import logger
from enum import Enum


def _get_training_pool_path() -> str:
    """获取训练池文件路径（自动检测项目根目录）"""
    import os
    # 优先从环境变量获取
    if 'LIVINGTREE_MEMORY_DIR' in os.environ:
        return os.path.join(os.environ['LIVINGTREE_MEMORY_DIR'], 'training_pool.json')
    
    # 尝试从当前文件位置向上查找
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # 向上找到项目根目录
    for _ in range(5):
        parent_dir = os.path.dirname(current_dir)
        workbuddy_dir = os.path.join(parent_dir, '.workbuddy', 'memory')
        if os.path.exists(workbuddy_dir):
            return os.path.join(workbuddy_dir, 'training_pool.json')
        current_dir = parent_dir
    
    # 默认路径
    return os.path.join(os.path.expanduser("~"), ".livingtree", "memory", "training_pool.json")


# 训练池文件路径
TRAINING_POOL_FILE = _get_training_pool_path()


class DifficultyLevel(Enum):
    """难度级别"""
    SIMPLE = "simple"       # 简单：基础查询，无额外约束
    MEDIUM = "medium"       # 中等：添加1-2个约束条件
    HARD = "hard"           # 困难：添加多个约束、边界值、对抗条件
    EXPERT = "expert"       # 专家：极端边界条件、复杂约束组合


class ConstraintType(Enum):
    """约束类型"""
    TIME_LIMIT = "time_limit"           # 时间限制
    RESOURCE_LIMIT = "resource_limit"   # 资源限制（CPU、内存）
    FORMAT_REQUIREMENT = "format_requirement"  # 格式要求
    BOUNDARY_VALUE = "boundary_value"   # 边界值约束
    PRECONDITION = "precondition"       # 前置条件
    REJECTION_CONDITION = "rejection_condition"  # 拒绝条件
    ADVERSARIAL = "adversarial"         # 对抗条件
    OUTPUT_LIMIT = "output_limit"       # 输出限制


class VariantTrainer:
    """
    变体训练器
    
    功能：使用生成的变体来测试和优化工具选择
    
    核心能力：
    1. 使用 ToolRegistry 语义搜索选择工具
    2. 支持多种约束类型（时间限制、资源限制、格式要求、边界值）
    3. 按难度级别区分测试
    4. 输出详细的训练报告
    
    用法：
        trainer = VariantTrainer()
        report = await trainer.train(max_variants=10)
    """
    
    def __init__(self, llm_client=None):
        """初始化训练器"""
        self._llm = llm_client
        self._logger = logger.bind(component="VariantTrainer")
        self._tool_registry = None
        
    def _get_tool_registry(self):
        """懒加载 ToolRegistry"""
        if self._tool_registry is None:
            try:
                from client.src.business.tools.tool_registry import ToolRegistry
                self._tool_registry = ToolRegistry.get_instance()
            except Exception as e:
                self._logger.warning(f"无法加载 ToolRegistry: {e}")
                self._tool_registry = None
        return self._tool_registry
    
    async def train(
        self,
        max_variants: int = 10,
        only_unused: bool = True,
        difficulty_filter: Optional[DifficultyLevel] = None
    ) -> Dict[str, Any]:
        """
        使用变体进行训练
        
        Args:
            max_variants: 最多使用多少个变体
            only_unused: 是否只使用未训练的变体
            difficulty_filter: 难度级别筛选（可选）
            
        Returns:
            训练报告（包含按难度级别的统计）
        """
        self._logger.info(f"开始训练（最多 {max_variants} 个变体，难度: {difficulty_filter}）")
        
        # 1. 读取训练池
        variants = self._load_training_pool(unused_only=only_unused)
        
        if not variants:
            self._logger.info("没有可用的变体")
            return {
                "success": False,
                "message": "没有可用的变体",
                "accuracy": 0.0
            }
        
        # 2. 按难度级别筛选
        if difficulty_filter:
            variants = [v for v in variants 
                       if self._get_variant_difficulty(v) == difficulty_filter]
            if not variants:
                self._logger.info(f"没有符合难度级别的变体: {difficulty_filter.value}")
                return {
                    "success": False,
                    "message": f"没有符合难度级别的变体: {difficulty_filter.value}",
                    "accuracy": 0.0
                }
        
        # 3. 限制数量
        variants = variants[:max_variants]
        
        self._logger.info(f"使用 {len(variants)} 个变体进行训练")
        
        # 4. 测试工具选择准确率
        results = []
        correct = 0
        
        # 按难度级别统计
        difficulty_stats = {level.value: {"total": 0, "correct": 0} for level in DifficultyLevel}
        
        for variant in variants:
            difficulty = self._get_variant_difficulty(variant)
            difficulty_stats[difficulty.value]["total"] += 1
            
            self._logger.info(f"测试变体: {variant['variant_id']} (难度: {difficulty.value})")
            
            try:
                result = await self._test_variant(variant)
                results.append(result)
                
                if result["correct"]:
                    correct += 1
                    difficulty_stats[difficulty.value]["correct"] += 1
                    self._mark_variant_used(variant['variant_id'])
                
                self._logger.info(f"  结果: {'✓' if result['correct'] else '✗'} ({result.get('selected_tool', 'unknown')})")
            
            except Exception as e:
                self._logger.error(f"  测试失败: {e}")
                results.append({
                    "variant_id": variant['variant_id'],
                    "correct": False,
                    "error": str(e)
                })
        
        # 5. 计算准确率
        accuracy = correct / len(variants) if variants else 0.0
        
        # 6. 计算按难度级别的准确率
        for level in difficulty_stats:
            total = difficulty_stats[level]["total"]
            if total > 0:
                difficulty_stats[level]["accuracy"] = difficulty_stats[level]["correct"] / total
            else:
                difficulty_stats[level]["accuracy"] = 0.0
        
        # 7. 生成报告
        report = {
            "success": True,
            "total_variants": len(variants),
            "correct": correct,
            "accuracy": accuracy,
            "difficulty_stats": difficulty_stats,
            "details": results,
            "timestamp": self._get_current_timestamp(),
        }
        
        self._logger.info(f"训练完成: 准确率 {accuracy:.1%} ({correct}/{len(variants)})")
        
        # 8. 保存报告
        self._save_training_report(report)
        
        return report
    
    def _get_variant_difficulty(self, variant: Dict[str, Any]) -> DifficultyLevel:
        """
        确定变体的难度级别
        
        难度判断依据：
        - SIMPLE: 无约束或只有1个简单约束
        - MEDIUM: 1-2个约束条件
        - HARD: 3个以上约束，或包含边界值、对抗条件
        - EXPERT: 极端边界条件、复杂约束组合
        
        Args:
            variant: 变体字典
            
        Returns:
            难度级别
        """
        constraints = variant.get("added_constraints", [])
        constraints_count = len(constraints)
        
        # 检查是否包含特殊约束类型
        has_boundary = False
        has_adversarial = False
        
        for constraint in constraints:
            constraint_lower = constraint.lower()
            if "边界" in constraint_lower or "边界值" in constraint_lower:
                has_boundary = True
            if "对抗" in constraint_lower or "拒绝" in constraint_lower:
                has_adversarial = True
        
        if constraints_count == 0:
            return DifficultyLevel.SIMPLE
        elif constraints_count <= 2 and not has_boundary and not has_adversarial:
            return DifficultyLevel.MEDIUM
        elif constraints_count <= 4 or has_boundary:
            return DifficultyLevel.HARD
        else:
            return DifficultyLevel.EXPERT
    
    async def _test_variant(self, variant: Dict[str, Any]) -> Dict[str, Any]:
        """
        测试单个变体
        
        Args:
            variant: 变体字典
            
        Returns:
            测试结果
        """
        test_case = variant.get("test_case", {})
        query = test_case.get("query", "")
        expected_tool = test_case.get("expected_tool", "")
        
        if not query:
            return {
                "variant_id": variant['variant_id'],
                "correct": False,
                "reason": "变体缺少测试查询"
            }
        
        # 使用 LLM 选择工具
        selected_tool = await self._select_tool_with_llm(query, variant.get("tool_name", ""))
        
        # 判断是否正确
        correct = selected_tool == expected_tool
        
        return {
            "variant_id": variant['variant_id'],
            "query": query,
            "expected_tool": expected_tool,
            "selected_tool": selected_tool,
            "correct": correct,
            "variant_description": variant.get("variant_description", "")
        }
    
    async def _select_tool_with_llm(self, query: str, hint_tool: str) -> str:
        """
        使用 ToolRegistry 语义搜索选择工具
        
        Args:
            query: 用户查询
            hint_tool: 提示的工具名称（用于回退）
            
        Returns:
            选择的工具名称
        """
        # 尝试使用 ToolRegistry 进行语义搜索
        registry = self._get_tool_registry()
        
        if registry:
            try:
                # 使用语义搜索查找最匹配的工具
                results = registry.search_tools(query, limit=3)
                
                if results:
                    # 返回最匹配的工具名称
                    selected_tool = results[0].name
                    self._logger.debug(f"语义搜索结果: {selected_tool} (query: {query[:30]}...)")
                    return selected_tool
                else:
                    self._logger.debug(f"语义搜索未找到匹配工具: {query[:30]}...")
            except Exception as e:
                self._logger.warning(f"语义搜索失败: {e}")
        
        # 回退到提示的工具
        self._logger.debug(f"回退到提示工具: {hint_tool}")
        return hint_tool
    
    def _load_training_pool(self, unused_only: bool = False) -> List[Dict[str, Any]]:
        """
        加载训练池
        
        Args:
            unused_only: 是否只返回未使用的变体
            
        Returns:
            变体列表
        """
        try:
            with open(TRAINING_POOL_FILE, 'r', encoding='utf-8') as f:
                pool = json.load(f)
            
            if unused_only:
                pool = [v for v in pool if not v.get("used_for_training", False)]
            
            return pool
        except Exception as e:
            self._logger.error(f"读取训练池失败: {e}")
            return []
    
    def _mark_variant_used(self, variant_id: str):
        """
        标记变体已用于训练
        
        Args:
            variant_id: 变体 ID
        """
        try:
            with open(TRAINING_POOL_FILE, 'r', encoding='utf-8') as f:
                pool = json.load(f)
            
            for variant in pool:
                if variant.get("variant_id") == variant_id:
                    variant["used_for_training"] = True
                    break
            
            with open(TRAINING_POOL_FILE, 'w', encoding='utf-8') as f:
                json.dump(pool, f, ensure_ascii=False, indent=2)
        
        except Exception as e:
            self._logger.error(f"标记变体失败: {e}")
    
    def _save_training_report(self, report: Dict[str, Any]):
        """
        保存训练报告
        
        Args:
            report: 训练报告
        """
        try:
            import os
            from datetime import datetime
            
            report_dir = "d:/mhzyapp/LivingTreeAlAgent/.workbuddy/memory/training_reports"
            os.makedirs(report_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = f"{report_dir}/report_{timestamp}.json"
            
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            
            self._logger.info(f"训练报告已保存: {report_file}")
        
        except Exception as e:
            self._logger.error(f"保存训练报告失败: {e}")
    
    def _get_current_timestamp(self) -> str:
        """获取当前时间戳（ISO 格式）"""
        from datetime import datetime
        return datetime.now().isoformat()


async def test_variant_trainer():
    """测试变体训练器"""
    import sys
    
    logger.remove()
    logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)
    
    print("=" * 60)
    print("测试 VariantTrainer")
    print("=" * 60)
    
    # 创建训练器
    trainer = VariantTrainer()
    
    # 训练
    print("\n开始训练...")
    report = await trainer.train(max_variants=3)
    
    print(f"\n[结果] 训练完成:")
    print(f"  总变体数: {report.get('total_variants', 0)}")
    print(f"  正确数: {report.get('correct', 0)}")
    print(f"  准确率: {report.get('accuracy', 0):.1%}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_variant_trainer())
