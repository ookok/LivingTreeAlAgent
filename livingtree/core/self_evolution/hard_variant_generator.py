"""
HardVariantGenerator - 难题变体生成器

实现"双数据飞轮"中的"推理飞轮"：
从错题中自动生成更难的变体，用于训练模型/工具选择逻辑。

工作流程：
1. 读取失败案例（错题记录）
2. 使用 LLM 生成更难的变体（添加约束、边界条件、对抗元素）
3. 保存到训练池

Author: LivingTreeAI Agent
Date: 2026-04-28
"""

import json
import os
from typing import Any, Dict, List, Optional
from loguru import logger

from business.self_evolution.tool_self_repairer import (
    ToolSelfRepairer,
    RepairStrategy,
)
from business.global_model_router import GlobalModelRouter


# 训练池文件路径
TRAINING_POOL_FILE = "d:/mhzyapp/LivingTreeAlAgent/.workbuddy/memory/training_pool.json"


class HardVariantGenerator:
    """
    难题变体生成器
    
    功能：从错题中生成更难的变体
    
    用法：
        generator = HardVariantGenerator()
        variants = await generator.generate_variants(max_cases=5)
    """
    
    def __init__(self, llm_client=None):
        """
        初始化难题变体生成器
        
        Args:
            llm_client: LLM 客户端（可选）
        """
        self._llm = llm_client
        self._router = GlobalModelRouter.get_instance()
        self._repairer = ToolSelfRepairer()
        self._logger = logger.bind(component="HardVariantGenerator")
        self._ensure_training_pool()
    
    def _ensure_training_pool(self):
        """确保训练池文件存在"""
        os.makedirs(os.path.dirname(TRAINING_POOL_FILE), exist_ok=True)
        if not os.path.exists(TRAINING_POOL_FILE):
            with open(TRAINING_POOL_FILE, 'w', encoding='utf-8') as f:
                json.dump([], f, ensure_ascii=False, indent=2)
    
    async def generate_variants(
        self,
        max_cases: int = 5,
        only_unused: bool = True
    ) -> List[Dict[str, Any]]:
        """
        生成难题变体
        
        Args:
            max_cases: 最多处理多少个错题
            only_unused: 是否只处理未使用的错题
            
        Returns:
            生成的变体列表
        """
        self._logger.info(f"开始生成难题变体（最多 {max_cases} 个错题）")
        
        # 1. 读取失败案例
        failed_cases = self._repairer.get_failed_cases(unused_only=only_unused)
        
        if not failed_cases:
            self._logger.info("没有可用的失败案例")
            return []
        
        # 限制数量
        failed_cases = failed_cases[:max_cases]
        
        self._logger.info(f"处理了 {len(failed_cases)} 个失败案例")
        
        variants = []
        
        # 2. 为每个失败案例生成变体
        for case in failed_cases:
            self._logger.info(f"处理案例 {case['id']}: {case['tool_name']}")
            
            try:
                variant = await self._generate_variant_for_case(case)
                
                if variant:
                    variants.append(variant)
                    
                    # 标记案例已使用
                    self._repairer.mark_case_used(case['id'])
                    
                    # 保存到训练池
                    self._save_variant_to_pool(variant)
                    
                    self._logger.info(f"  变体生成成功: {variant['variant_id']}")
                else:
                    self._logger.warning(f"  变体生成失败")
            
            except Exception as e:
                self._logger.error(f"  处理案例时出错: {e}")
        
        self._logger.info(f"共生成 {len(variants)} 个难题变体")
        
        return variants
    
    async def _generate_variant_for_case(self, case: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        为单个失败案例生成变体
        
        Args:
            case: 失败案例
            
        Returns:
            变体字典，如果生成失败则返回 None
        """
        # 构造 Prompt
        prompt = self._build_variant_prompt(case)
        
        # 调用 LLM
        try:
            response = await self._router.call_model_sync(
                capability="reasoning",  # 使用推理能力
                prompt=prompt,
                temperature=0.7,  # 较高温度以增加多样性
            )
            
            # 解析响应
            if hasattr(response, 'thinking') and response.thinking:
                text = response.thinking
            elif hasattr(response, 'content') and response.content:
                text = response.content
            else:
                text = str(response)
            
            # 提取 JSON
            variant = self._extract_variant_from_response(text)
            
            if variant:
                # 添加元数据
                variant["variant_id"] = f"var_{case['id']}_{len(self._load_training_pool()) + 1}"
                variant["source_case_id"] = case['id']
                variant["tool_name"] = case['tool_name']
                variant["generated_at"] = self._get_current_timestamp()
                variant["used_for_training"] = False
                
                return variant
            
            return None
            
        except Exception as e:
            self._logger.error(f"调用 LLM 生成变体失败: {e}")
            return None
    
    def _build_variant_prompt(self, case: Dict[str, Any]) -> str:
        """
        构造生成变体的 Prompt
        
        Args:
            case: 失败案例
            
        Returns:
            Prompt 字符串
        """
        prompt = f"""你是难题变体生成专家（推理飞轮）。

## 任务
给定一个工具调用失败案例，生成一个**更难的变体**，用于训练 AI Agent 的工具调用能力。

## 原始失败案例
- 工具名称: {case['tool_name']}
- 错误信息: {case['error_message']}
- 工具输入: {json.dumps(case.get('tool_input', {}), ensure_ascii=False)}

## 生成要求
请生成一个更难的变体，可以通过以下方式：
1. **添加约束条件**: 增加 1-2 个限制条件（如：时间限制、资源限制、格式要求）
2. **修改输入参数**: 使用边界值、异常值、特殊字符
3. **添加干扰项**: 在问题描述中添加无关信息
4. **增加步骤复杂度**: 将单步任务改为多步任务
5. **对抗条件**: 添加需要满足的前置条件或拒绝条件

## 输出格式
请以 JSON 格式输出：
```json
{{
    "variant_description": "变体描述（中文）",
    "difficulty_increase": "难度提升说明",
    "new_input": {{
        // 新的输入参数（如果有）
    }},
    "added_constraints": [
        "约束1",
        "约束2"
    ],
    "test_case": {{
        "query": "测试查询（中文）",
        "expected_tool": "{case['tool_name']}",
        "expected_params": {{
            // 预期参数
        }}
    }}
}}
```

只输出 JSON，不要有其他内容。"""
        
        return prompt
    
    def _extract_variant_from_response(self, text: str) -> Optional[Dict[str, Any]]:
        """
        从 LLM 响应中提取变体
        
        Args:
            text: LLM 响应文本
            
        Returns:
            变体字典，如果提取失败则返回 None
        """
        import re
        
        # 方法1: 直接解析整个文本
        try:
            # 清理可能的 markdown 代码块
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*', '', text)
            
            result = json.loads(text)
            return result
        except Exception:
            pass
        
        # 方法2: 使用正则提取 JSON
        try:
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return result
        except Exception:
            pass
        
        self._logger.warning(f"无法从响应中提取 JSON: {text[:200]}")
        return None
    
    def _save_variant_to_pool(self, variant: Dict[str, Any]):
        """
        保存变体到训练池
        
        Args:
            variant: 变体字典
        """
        try:
            # 读取现有训练池
            pool = self._load_training_pool()
            
            # 添加新变体
            pool.append(variant)
            
            # 保存
            with open(TRAINING_POOL_FILE, 'w', encoding='utf-8') as f:
                json.dump(pool, f, ensure_ascii=False, indent=2)
            
            self._logger.info(f"变体已保存到训练池: {variant['variant_id']}")
            
        except Exception as e:
            self._logger.error(f"保存变体到训练池失败: {e}")
    
    def _load_training_pool(self) -> List[Dict[str, Any]]:
        """
        加载训练池
        
        Returns:
            训练池列表
        """
        try:
            with open(TRAINING_POOL_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    
    def _get_current_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def get_training_pool(self, unused_only: bool = False) -> List[Dict[str, Any]]:
        """
        获取训练池
        
        Args:
            unused_only: 是否只返回未使用的变体
            
        Returns:
            训练池列表
        """
        pool = self._load_training_pool()
        
        if unused_only:
            pool = [v for v in pool if not v.get("used_for_training", False)]
        
        return pool
    
    def mark_variant_used(self, variant_id: str):
        """
        标记变体已用于训练
        
        Args:
            variant_id: 变体 ID
        """
        try:
            pool = self._load_training_pool()
            
            for variant in pool:
                if variant.get("variant_id") == variant_id:
                    variant["used_for_training"] = True
                    break
            
            with open(TRAINING_POOL_FILE, 'w', encoding='utf-8') as f:
                json.dump(pool, f, ensure_ascii=False, indent=2)
            
            self._logger.info(f"已标记变体 {variant_id} 为已使用")
        except Exception as e:
            self._logger.error(f"标记变体失败: {e}")


async def test_hard_variant_generator():
    """测试难题变体生成器"""
    import sys
    
    logger.remove()
    logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)
    
    print("=" * 60)
    print("测试 HardVariantGenerator")
    print("=" * 60)
    
    # 创建生成器
    generator = HardVariantGenerator()
    
    # 生成变体
    print("\n生成难题变体...")
    variants = await generator.generate_variants(max_cases=2)
    
    print(f"\n[结果] 生成了 {len(variants)} 个变体:")
    for v in variants:
        print(f"  - {v['variant_id']}: {v['variant_description'][:50]}...")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_hard_variant_generator())
