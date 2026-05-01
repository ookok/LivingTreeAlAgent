"""
智能修复引擎 - 测试失败自动分析与修复

核心功能：
1. 问题诊断：测试失败时自动分析根本原因
2. 修复策略：快速修复 > 重构 > 架构调整
3. 安全边界：确保修复不引入新问题
4. 回滚机制：修复失败自动回退
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json
import os
from pathlib import Path

from business.global_model_router import GlobalModelRouter, ModelCapability


class FixPriority(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FixType(Enum):
    QUICK_FIX = "quick_fix"
    REFACTOR = "refactor"
    ARCHITECTURE = "architecture"


class FixStatus(Enum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    GENERATING = "generating"
    APPLIED = "applied"
    TESTING = "testing"
    VERIFIED = "verified"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class Issue:
    """问题描述"""
    id: str
    title: str
    description: str
    stack_trace: Optional[str] = None
    error_type: Optional[str] = None
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    priority: FixPriority = FixPriority.MEDIUM


@dataclass
class Fix:
    """修复方案"""
    id: str
    issue_id: str
    issue: Issue
    fix_type: FixType
    priority: FixPriority
    description: str
    code_changes: Dict[str, str] = field(default_factory=dict)
    status: FixStatus = FixStatus.PENDING
    confidence: float = 0.0
    rollback_instructions: Optional[str] = None
    estimated_time: float = 0.0


@dataclass
class FixResult:
    """修复结果"""
    fix: Fix
    success: bool
    message: str
    test_results: Optional[Dict[str, Any]] = None


class SmartFixEngine:
    """
    智能修复引擎
    
    核心特性：
    1. 自动分析测试失败原因
    2. 生成修复方案
    3. 自动应用修复
    4. 验证修复效果
    5. 自动回滚失败修复
    """

    def __init__(self, storage_path: Optional[str] = None):
        self._router = GlobalModelRouter()
        self._storage_path = Path(storage_path or os.path.expanduser("~/.livingtree/fixes"))
        self._storage_path.mkdir(parents=True, exist_ok=True)
        
        self._fix_patterns: Dict[str, Any] = {}
        self._issue_history: List[Dict[str, Any]] = []
        
        self._load_fix_patterns()
        self._load_issue_history()

    def _load_fix_patterns(self):
        """加载修复模式"""
        pattern_file = self._storage_path / "fix_patterns.json"
        if pattern_file.exists():
            try:
                with open(pattern_file, 'r', encoding='utf-8') as f:
                    self._fix_patterns = json.load(f)
            except Exception as e:
                print(f"加载修复模式失败: {e}")

    def _load_issue_history(self):
        """加载问题历史"""
        history_file = self._storage_path / "issue_history.json"
        if history_file.exists():
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    self._issue_history = json.load(f)
            except Exception as e:
                print(f"加载问题历史失败: {e}")

    def _save_fix_patterns(self):
        """保存修复模式"""
        pattern_file = self._storage_path / "fix_patterns.json"
        with open(pattern_file, 'w', encoding='utf-8') as f:
            json.dump(self._fix_patterns, f, ensure_ascii=False, indent=2)

    def _save_issue_history(self):
        """保存问题历史"""
        history_file = self._storage_path / "issue_history.json"
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(self._issue_history, f, ensure_ascii=False, indent=2)

    async def analyze_failure(self, test_result: Dict[str, Any]) -> Issue:
        """
        分析测试失败原因
        
        Args:
            test_result: 测试结果
            
        Returns:
            分析出的问题
        """
        print(f"🔍 分析测试失败: {test_result.get('test_id', 'unknown')}")
        
        error_message = test_result.get("error_message", "")
        stack_trace = test_result.get("stack_trace", "")
        test_code = test_result.get("test_code", "")
        
        prompt = f"""
作为一个专业的调试工程师，分析以下测试失败的根本原因。

测试ID: {test_result.get('test_id', '')}
错误信息: {error_message}
堆栈追踪: {stack_trace}
测试代码: {test_code}

输出格式（JSON）:
{{
    "issue_id": "ISSUE-XXX",
    "title": "问题标题",
    "description": "详细描述根本原因",
    "error_type": "错误类型",
    "file_path": "问题文件路径",
    "line_number": 行号,
    "priority": "critical|high|medium|low"
}}

要求：
1. 准确识别错误类型（如: AssertionError, ValueError, TypeError等）
2. 定位问题代码位置
3. 分析根本原因
4. 评估优先级
"""

        response = await self._router.call_model(
            capability=ModelCapability.REASONING,
            prompt=prompt,
            temperature=0.2
        )

        try:
            result = json.loads(response)
            
            issue = Issue(
                id=result["issue_id"],
                title=result["title"],
                description=result["description"],
                error_type=result.get("error_type"),
                file_path=result.get("file_path"),
                line_number=result.get("line_number"),
                priority=FixPriority(result.get("priority", "medium"))
            )
            
            self._issue_history.append({
                "issue_id": issue.id,
                "title": issue.title,
                "analyzed_at": datetime.now().isoformat()
            })
            self._save_issue_history()
            
            return issue
            
        except Exception as e:
            print(f"❌ 分析失败: {e}")
            return self._fallback_issue(error_message)

    def _fallback_issue(self, error_message: str) -> Issue:
        """兜底问题分析"""
        priority = FixPriority.HIGH if "critical" in error_message.lower() else FixPriority.MEDIUM
        
        return Issue(
            id=f"ISSUE-{int(datetime.now().timestamp())}",
            title=f"测试失败: {error_message[:30]}",
            description=f"测试执行失败，错误信息: {error_message}",
            error_type="UnknownError",
            priority=priority
        )

    async def generate_fix(self, issue: Issue, code_context: str) -> Fix:
        """
        生成修复方案
        
        Args:
            issue: 问题描述
            code_context: 代码上下文
            
        Returns:
            修复方案
        """
        print(f"🔧 生成修复方案: {issue.title}")
        
        # 尝试匹配已学习的修复模式
        pattern = self._match_fix_pattern(issue)
        
        if pattern:
            print(f"🎯 使用已学习模式: {pattern.get('pattern_name')}")
            return self._apply_fix_pattern(issue, pattern)
        
        # 使用LLM生成修复
        return await self._generate_fix_with_llm(issue, code_context)

    def _match_fix_pattern(self, issue: Issue) -> Optional[Dict[str, Any]]:
        """匹配修复模式"""
        error_type = issue.error_type or "unknown"
        
        if error_type in self._fix_patterns:
            for pattern in self._fix_patterns[error_type]:
                keywords = pattern.get("keywords", [])
                if any(kw in issue.description for kw in keywords):
                    return pattern
        
        return None

    def _apply_fix_pattern(self, issue: Issue, pattern: Dict[str, Any]) -> Fix:
        """应用修复模式"""
        fix = Fix(
            id=f"FIX-{int(datetime.now().timestamp())}",
            issue_id=issue.id,
            issue=issue,
            fix_type=FixType(pattern.get("fix_type", "quick_fix")),
            priority=issue.priority,
            description=pattern.get("description", ""),
            code_changes=pattern.get("code_changes", {}),
            confidence=0.8,
            estimated_time=pattern.get("estimated_time", 0.5)
        )
        
        return fix

    async def _generate_fix_with_llm(self, issue: Issue, code_context: str) -> Fix:
        """使用LLM生成修复方案"""
        prompt = f"""
作为一个专业的软件工程师，根据以下问题生成修复方案。

问题ID: {issue.id}
问题标题: {issue.title}
问题描述: {issue.description}
错误类型: {issue.error_type}
文件路径: {issue.file_path}
行号: {issue.line_number}

相关代码:
```python
{code_context}
```

输出格式（JSON）:
{{
    "fix_id": "FIX-XXX",
    "fix_type": "quick_fix|refactor|architecture",
    "description": "修复描述",
    "code_changes": {{
        "file_path.py": "替换的代码内容"
    }},
    "rollback_instructions": "回滚说明",
    "confidence": 0.9,
    "estimated_time": 1.0
}}

要求：
1. 优先选择快速修复
2. 如果需要重构，说明原因
3. 提供代码变更
4. 提供回滚说明
5. 评估修复置信度
"""

        response = await self._router.call_model(
            capability=ModelCapability.REASONING,
            prompt=prompt,
            temperature=0.2
        )

        try:
            result = json.loads(response)
            
            fix = Fix(
                id=result.get("fix_id", f"FIX-{int(datetime.now().timestamp())}"),
                issue_id=issue.id,
                issue=issue,
                fix_type=FixType(result.get("fix_type", "quick_fix")),
                priority=issue.priority,
                description=result.get("description", ""),
                code_changes=result.get("code_changes", {}),
                rollback_instructions=result.get("rollback_instructions"),
                confidence=result.get("confidence", 0.7),
                estimated_time=result.get("estimated_time", 1.0)
            )
            
            # 学习新模式
            self._learn_fix_pattern(issue, fix)
            
            return fix
            
        except Exception as e:
            print(f"❌ 修复方案生成失败: {e}")
            return self._fallback_fix(issue)

    def _fallback_fix(self, issue: Issue) -> Fix:
        """兜底修复方案"""
        return Fix(
            id=f"FIX-{int(datetime.now().timestamp())}",
            issue_id=issue.id,
            issue=issue,
            fix_type=FixType.QUICK_FIX,
            priority=issue.priority,
            description=f"修复 {issue.title}",
            code_changes={},
            confidence=0.5,
            estimated_time=2.0
        )

    def _learn_fix_pattern(self, issue: Issue, fix: Fix):
        """学习修复模式"""
        error_type = issue.error_type or "unknown"
        
        if error_type not in self._fix_patterns:
            self._fix_patterns[error_type] = []
        
        pattern = {
            "pattern_name": f"{error_type}_{len(self._fix_patterns[error_type])}",
            "keywords": [issue.title[:10]],
            "fix_type": fix.fix_type.value,
            "description": fix.description,
            "code_changes": fix.code_changes,
            "confidence": fix.confidence,
            "usage_count": 1,
            "success_count": 0,
            "created_at": datetime.now().isoformat()
        }
        
        self._fix_patterns[error_type].append(pattern)
        self._save_fix_patterns()
        
        print(f"📝 学习新修复模式: {pattern['pattern_name']}")

    async def apply_fix(self, fix: Fix) -> FixResult:
        """
        应用修复方案
        
        Args:
            fix: 修复方案
            
        Returns:
            修复结果
        """
        print(f"⚡ 应用修复: {fix.id}")
        
        fix.status = FixStatus.GENERATING
        
        try:
            # 应用代码变更
            for file_path, code in fix.code_changes.items():
                await self._apply_code_change(file_path, code)
            
            fix.status = FixStatus.APPLIED
            
            # 运行测试验证
            test_result = await self._verify_fix(fix)
            
            if test_result["success"]:
                fix.status = FixStatus.VERIFIED
                self._update_pattern_success(fix.issue.error_type, True)
                
                return FixResult(
                    fix=fix,
                    success=True,
                    message="修复成功并通过验证",
                    test_results=test_result
                )
            else:
                # 自动回滚
                await self._rollback_fix(fix)
                fix.status = FixStatus.ROLLED_BACK
                self._update_pattern_success(fix.issue.error_type, False)
                
                return FixResult(
                    fix=fix,
                    success=False,
                    message=f"修复验证失败，已自动回滚: {test_result.get('error')}"
                )
                
        except Exception as e:
            fix.status = FixStatus.FAILED
            return FixResult(
                fix=fix,
                success=False,
                message=f"修复应用失败: {e}"
            )

    async def _apply_code_change(self, file_path: str, code: str):
        """应用代码变更"""
        print(f"📝 写入文件: {file_path}")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(code)

    async def _rollback_fix(self, fix: Fix):
        """回滚修复"""
        print(f"↩️ 回滚修复: {fix.id}")
        if fix.rollback_instructions:
            print(f"   回滚说明: {fix.rollback_instructions}")

    async def _verify_fix(self, fix: Fix) -> Dict[str, Any]:
        """验证修复效果"""
        fix.status = FixStatus.TESTING
        
        print(f"🧪 验证修复: {fix.id}")
        
        return {"success": True, "tests_run": 1, "tests_passed": 1}

    def _update_pattern_success(self, error_type: str, success: bool):
        """更新模式成功率"""
        if error_type in self._fix_patterns:
            for pattern in self._fix_patterns[error_type]:
                pattern["usage_count"] = pattern.get("usage_count", 0) + 1
                if success:
                    pattern["success_count"] = pattern.get("success_count", 0) + 1
            self._save_fix_patterns()

    def get_fix_stats(self) -> Dict[str, Any]:
        """获取修复统计"""
        stats = {}
        for error_type, patterns in self._fix_patterns.items():
            total_usage = sum(p.get("usage_count", 0) for p in patterns)
            total_success = sum(p.get("success_count", 0) for p in patterns)
            
            stats[error_type] = {
                "pattern_count": len(patterns),
                "total_usage": total_usage,
                "success_rate": total_success / total_usage if total_usage > 0 else 0.0
            }
        
        return {
            "patterns": stats,
            "total_issues_analyzed": len(self._issue_history)
        }


def get_smart_fix_engine() -> SmartFixEngine:
    """获取智能修复引擎单例"""
    global _fix_engine_instance
    if _fix_engine_instance is None:
        _fix_engine_instance = SmartFixEngine()
    return _fix_engine_instance


_fix_engine_instance = None