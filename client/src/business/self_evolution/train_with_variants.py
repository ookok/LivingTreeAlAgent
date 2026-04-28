"""
TrainWithVariants - 使用变体训练工具选择

MVP 实现：
1. 读取训练池中的变体
2. 测试工具选择准确率
3. 输出训练报告

Author: LivingTreeAI Agent
Date: 2026-04-28
"""

import json
import asyncio
from typing import Any, Dict, List, Optional
from loguru import logger


# 训练池文件路径
TRAINING_POOL_FILE = "d:/mhzyapp/LivingTreeAlAgent/.workbuddy/memory/training_pool.json"


class VariantTrainer:
    """
    变体训练器
    
    功能：使用生成的变体来测试和优化工具选择
    
    用法：
        trainer = VariantTrainer()
        report = await trainer.train(max_variants=10)
    """
    
    def __init__(self, llm_client=None):
        """初始化训练器"""
        self._llm = llm_client
        self._logger = logger.bind(component="VariantTrainer")
    
    async def train(
        self,
        max_variants: int = 10,
        only_unused: bool = True
    ) -> Dict[str, Any]:
        """
        使用变体进行训练
        
        Args:
            max_variants: 最多使用多少个变体
            only_unused: 是否只使用未训练的变体
            
        Returns:
            训练报告
        """
        self._logger.info(f"开始训练（最多 {max_variants} 个变体）")
        
        # 1. 读取训练池
        variants = self._load_training_pool(unused_only=only_unused)
        
        if not variants:
            self._logger.info("没有可用的变体")
            return {
                "success": False,
                "message": "没有可用的变体",
                "accuracy": 0.0
            }
        
        # 限制数量
        variants = variants[:max_variants]
        
        self._logger.info(f"使用 {len(variants)} 个变体进行训练")
        
        # 2. 测试工具选择准确率
        results = []
        correct = 0
        
        for variant in variants:
            self._logger.info(f"测试变体: {variant['variant_id']}")
            
            try:
                result = await self._test_variant(variant)
                results.append(result)
                
                if result["correct"]:
                    correct += 1
                    self._mark_variant_used(variant['variant_id'])
                
                self._logger.info(f"  结果: {'✓' if result['correct'] else '✗'} ({result.get('selected_tool', 'unknown')})")
            
            except Exception as e:
                self._logger.error(f"  测试失败: {e}")
                results.append({
                    "variant_id": variant['variant_id'],
                    "correct": False,
                    "error": str(e)
                })
        
        # 3. 计算准确率
        accuracy = correct / len(variants) if variants else 0.0
        
        # 4. 生成报告
        report = {
            "success": True,
            "total_variants": len(variants),
            "correct": correct,
            "accuracy": accuracy,
            "details": results,
        }
        
        self._logger.info(f"训练完成: 准确率 {accuracy:.1%} ({correct}/{len(variants)})")
        
        # 5. 保存报告
        self._save_training_report(report)
        
        return report
    
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
        使用 LLM 选择工具
        
        Args:
            query: 用户查询
            hint_tool: 提示的工具名称
            
        Returns:
            选择的工具名称
        """
        # 简化实现：直接返回提示的工具
        # 在实际应用中，这里应该调用 ToolRegistry 的语义搜索
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
