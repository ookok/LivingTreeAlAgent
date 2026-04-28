#!/usr/bin/env python3
"""
为 EIAgent 添加自我进化能力

修改 ei_agent_adapter.py，集成自我进化引擎
"""

import sys
import os

# 读取原文件
file_path = "client/src/business/ei_agent/ei_agent_adapter.py"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 在 __init__ 方法末尾添加自我进化引擎初始化
init_end = content.find('self.training_agent = None\n', content.find('def __init__(self):'))
if init_end > 0:
    init_end += len('self.training_agent = None\n')
    
    self_evolution_init = '''
        # 初始化自我进化引擎
        if 'SELF_EVOLUTION_AVAILABLE' in globals() and SELF_EVOLUTION_AVAILABLE:
            try:
                from client.src.business.self_evolution import SelfEvolutionEngine
                self.self_evolution_engine = SelfEvolutionEngine()
                self.self_evolution_enabled = True
                logger.info("[EIAgentExecutor] 自我进化引擎初始化成功")
            except Exception as e:
                logger.warning(f"[EIAgentExecutor] 自我进化引擎初始化失败: {e}")
                self.self_evolution_engine = None
                self.self_evolution_enabled = False
        else:
            self.self_evolution_engine = None
            self.self_evolution_enabled = False
'''
    
    content = content[:init_end] + self_evolution_init + content[init_end:]

# 2. 在 execute 方法中添加自我反思
# 找到 return result 之前的位置
return_result_pos = content.find('            return result\n', content.find('async def execute('))
if return_result_pos > 0:
    self_reflection_code = '''
            # 自我反思（如果启用了自我进化）
            if hasattr(self, 'self_evolution_enabled') and self.self_evolution_enabled:
                try:
                    reflection = await self.self_evolution_engine.reflect_on_task_execution(
                        task.description, result
                    )
                    logger.info(f"[EIAgent] 自我反思完成: success={reflection.get('success')}")
                    
                    # 如果发现能力缺失，尝试创建工具
                    if reflection.get("missing_capabilities"):
                        logger.info(f"[EIAgent] 发现能力缺失: {reflection['missing_capabilities']}")
                except Exception as e:
                    logger.error(f"[EIAgent] 自我反思失败: {e}")
            
'''
    
    content = content[:return_result_pos] + self_reflection_code + content[return_result_pos:]

# 3. 添加启用/禁用自我进化方法
enable_method = '''
    # ── 自我进化控制 ─────────────────────────────────────────────────────
    
    def enable_self_evolution(self, enabled: bool = True):
        """启用/禁用自我进化能力"""
        self.self_evolution_enabled = enabled
        if enabled and self.self_evolution_engine is None:
            try:
                from client.src.business.self_evolution import SelfEvolutionEngine
                self.self_evolution_engine = SelfEvolutionEngine()
                logger.info("[EIAgentExecutor] 自我进化引擎已启用")
            except Exception as e:
                logger.error(f"[EIAgent] 启用自我进化失败: {e}")
                self.self_evolution_enabled = False
        else:
            logger.info(f"[EIAgent] 自我进化: {'启用' if enabled else '禁用'}")
    
    async def start_active_learning(self, max_iterations: int = 10):
        """开始主动学习（如果启用了自我进化）"""
        if not hasattr(self, 'self_evolution_enabled') or not self.self_evolution_enabled:
            logger.warning("[EIAgent] 自我进化未启用，无法开始主动学习")
            return
        
        if self.self_evolution_engine is None:
            logger.warning("[EIAgent] 自我进化引擎未初始化")
            return
        
        try:
            await self.self_evolution_engine.start_active_learning(max_iterations)
            logger.info("[EIAgent] 主动学习完成")
        except Exception as e:
            logger.error(f"[EIAgent] 主动学习失败: {e}")
    
    def get_self_evolution_status(self) -> dict:
        """获取自我进化状态"""
        return {
            "enabled": getattr(self, 'self_evolution_enabled', False),
            "engine_initialized": self.self_evolution_engine is not None,
            "reflection_history_count": len(getattr(self.self_evolution_engine, '_reflection_history', []))
        }
'''

# 在 cancel 方法之前插入
cancel_pos = content.find('    async def cancel(self, task_id: str)')
if cancel_pos > 0:
    content = content[:cancel_pos] + enable_method + '\n' + content[cancel_pos:]

# 写入文件
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ EIAgent 自我进化能力集成完成")
print("  - 已添加自我进化引擎初始化")
print("  - 已添加任务执行后的自我反思")
print("  - 已添加 enable_self_evolution() 方法")
print("  - 已添加 start_active_learning() 方法")
print("  - 已添加 get_self_evolution_status() 方法")
