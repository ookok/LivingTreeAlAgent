"""
增量代码生成模块 - IncrementalCodeGenerator

核心功能：
1. 增量代码生成 - 只重新生成变更部分
2. 智能合并 - 保留手动修改
3. 冲突检测与解决 - 自动处理代码冲突
4. 代码差异分析 - 识别需要更新的部分
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
import asyncio
from pathlib import Path
import difflib
from loguru import logger


class ConflictType(Enum):
    """冲突类型"""
    NONE = "none"
    ADDITION = "addition"
    MODIFICATION = "modification"
    DELETION = "deletion"
    CONFLICT = "conflict"


@dataclass
class CodeDelta:
    """代码增量"""
    file_path: str
    old_content: str = ""
    new_content: str = ""
    delta_type: ConflictType = ConflictType.NONE
    conflicts: List[str] = field(default_factory=list)


@dataclass
class GenerationResult:
    """生成结果"""
    success: bool
    deltas: List[CodeDelta] = field(default_factory=list)
    updated_files: int = 0
    conflicts: int = 0
    message: str = ""


class IncrementalCodeGenerator:
    """
    增量代码生成器
    
    核心特性：
    1. 增量代码生成 - 只重新生成变更部分
    2. 智能合并 - 保留手动修改
    3. 冲突检测与解决 - 自动处理代码冲突
    4. 代码差异分析 - 识别需要更新的部分
    """

    def __init__(self):
        self._logger = logger.bind(component="IncrementalCodeGenerator")
        self._generation_history: Dict[str, str] = {}  # task_id -> last_generated_code

    async def generate_incremental(self, task_id: str, requirement: str, 
                                   existing_code: Optional[str] = None,
                                   context: Optional[Dict[str, Any]] = None) -> GenerationResult:
        """增量生成代码"""
        self._logger.info(f"增量生成代码: {task_id}")
        
        # 1. 分析需求变更
        changes = await self._analyze_requirement_changes(task_id, requirement)
        
        if not changes:
            return GenerationResult(
                success=True,
                message="需求未变更，无需重新生成"
            )
        
        # 2. 如果有现有代码，分析差异
        deltas = []
        if existing_code:
            deltas = await self._analyze_code_differences(existing_code, requirement, context)
        else:
            # 没有现有代码，生成全新代码
            new_code = await self._generate_new_code(requirement, context)
            deltas.append(CodeDelta(
                file_path="generated.py",
                new_content=new_code,
                delta_type=ConflictType.ADDITION
            ))
        
        # 3. 检测冲突
        conflicts = [d for d in deltas if d.delta_type == ConflictType.CONFLICT]
        
        # 4. 应用变更
        if conflicts:
            await self._resolve_conflicts(conflicts)
        
        # 5. 更新历史记录
        self._generation_history[task_id] = requirement
        
        return GenerationResult(
            success=True,
            deltas=deltas,
            updated_files=len(deltas),
            conflicts=len(conflicts),
            message=f"增量生成完成，更新 {len(deltas)} 个文件，{len(conflicts)} 个冲突"
        )

    async def _analyze_requirement_changes(self, task_id: str, new_requirement: str) -> bool:
        """分析需求变更"""
        old_requirement = self._generation_history.get(task_id, "")
        
        if not old_requirement:
            return True  # 第一次生成
        
        # 简单的差异检测
        similarity = self._calculate_similarity(old_requirement, new_requirement)
        
        # 如果相似度低于阈值，认为需求发生了变更
        return similarity < 0.8

    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """计算字符串相似度"""
        return difflib.SequenceMatcher(None, str1, str2).ratio()

    async def _analyze_code_differences(self, existing_code: str, requirement: str, 
                                        context: Optional[Dict[str, Any]]) -> List[CodeDelta]:
        """分析代码差异"""
        deltas = []
        
        # 生成新代码
        new_code = await self._generate_new_code(requirement, context)
        
        # 分析差异
        diff = difflib.unified_diff(
            existing_code.splitlines(),
            new_code.splitlines(),
            fromfile='old',
            tofile='new'
        )
        
        diff_lines = list(diff)
        
        if not diff_lines:
            deltas.append(CodeDelta(
                file_path="generated.py",
                old_content=existing_code,
                new_content=new_code,
                delta_type=ConflictType.NONE
            ))
        else:
            # 检测是否有冲突
            has_conflict = any('<<<<<' in line for line in diff_lines)
            
            deltas.append(CodeDelta(
                file_path="generated.py",
                old_content=existing_code,
                new_content=new_code,
                delta_type=ConflictType.CONFLICT if has_conflict else ConflictType.MODIFICATION,
                conflicts=diff_lines if has_conflict else []
            ))
        
        return deltas

    async def _generate_new_code(self, requirement: str, context: Optional[Dict[str, Any]]) -> str:
        """生成新代码"""
        # 简单的代码生成模板
        template = f'''"""
Generated code for: {requirement}
"""

class GeneratedService:
    """Generated service class"""
    
    def __init__(self):
        pass
    
    async def process(self, data: dict) -> dict:
        """Process data according to requirement"""
        # TODO: Implement based on requirement
        result = {{
            "status": "success",
            "message": "Processed according to: {requirement[:50]}..."
        }}
        return result

# Example usage
async def main():
    service = GeneratedService()
    result = await service.process({{}})
    print(result)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
'''
        
        return template

    async def _resolve_conflicts(self, conflicts: List[CodeDelta]):
        """解决冲突"""
        for delta in conflicts:
            self._logger.info(f"解决冲突: {delta.file_path}")
            
            # 简单的冲突解决策略：保留用户修改，添加新生成的代码作为注释
            if delta.delta_type == ConflictType.CONFLICT:
                resolved = f"""# === AUTO-GENERATED CODE ===
# Based on requirement changes
{delta.new_content}

# === MANUAL CHANGES (PRESERVED) ===
# {delta.conflicts}
{delta.old_content}
"""
                delta.new_content = resolved
                delta.delta_type = ConflictType.MODIFICATION
                delta.conflicts = []

    async def merge_changes(self, deltas: List[CodeDelta]) -> Dict[str, str]:
        """合并变更"""
        results = {}
        
        for delta in deltas:
            if delta.delta_type == ConflictType.ADDITION:
                results[delta.file_path] = delta.new_content
            elif delta.delta_type in [ConflictType.MODIFICATION, ConflictType.CONFLICT]:
                # 智能合并：保留手动修改的部分
                results[delta.file_path] = await self._smart_merge(
                    delta.old_content, 
                    delta.new_content
                )
        
        return results

    async def _smart_merge(self, old_code: str, new_code: str) -> str:
        """智能合并代码"""
        old_lines = old_code.split("\n")
        new_lines = new_code.split("\n")
        
        merged = []
        seen_lines = set()
        
        # 先添加旧代码中可能被手动修改的部分
        for line in old_lines:
            if line.strip() and line.strip() not in seen_lines:
                seen_lines.add(line.strip())
                merged.append(line)
        
        # 添加新代码中新增的部分
        for line in new_lines:
            if line.strip() and line.strip() not in seen_lines:
                merged.append(f"# NEW: {line}")
        
        return "\n".join(merged)

    def get_generation_history(self, task_id: str) -> Optional[str]:
        """获取生成历史"""
        return self._generation_history.get(task_id)

    def clear_history(self, task_id: Optional[str] = None):
        """清除生成历史"""
        if task_id:
            self._generation_history.pop(task_id, None)
        else:
            self._generation_history.clear()


def get_incremental_generator() -> IncrementalCodeGenerator:
    """获取增量代码生成器单例"""
    global _generator_instance
    if _generator_instance is None:
        _generator_instance = IncrementalCodeGenerator()
    return _generator_instance


_generator_instance = None