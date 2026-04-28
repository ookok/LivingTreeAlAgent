"""
HarnessOptimization - 系统化优化模块

借鉴 ECC 的核心哲学：Memory Management + Security Checks + Verification Framework

核心组件：
1. MemoryManager - 内存管理
2. SecurityChecker - 安全检查
3. VerificationFramework - 验证框架

Author: LivingTreeAI Agent
Date: 2026-04-28
"""

import gc
import psutil
import os
import re
import hashlib
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger


class MemoryStatus(Enum):
    """内存状态"""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"


class SecurityLevel(Enum):
    """安全级别"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class VerificationStatus(Enum):
    """验证状态"""
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"


@dataclass
class MemoryInfo:
    """内存信息"""
    total: int = 0
    available: int = 0
    used: int = 0
    percent: float = 0.0
    status: MemoryStatus = MemoryStatus.NORMAL


@dataclass
class SecurityCheckResult:
    """安全检查结果"""
    check_name: str
    status: SecurityLevel
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VerificationResult:
    """验证结果"""
    verification_id: str
    status: VerificationStatus
    message: str = ""
    score: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)


class MemoryManager:
    """
    内存管理器
    
    功能：
    1. 监控内存使用
    2. 自动清理不再使用的对象
    3. 优化内存分配
    4. 防止内存泄漏
    """
    
    def __init__(self):
        self._logger = logger.bind(component="MemoryManager")
        self._tracked_objects: Set[int] = set()
        self._memory_threshold = 80  # 超过80%触发清理
        self._last_cleanup_time = 0
        
    def get_memory_info(self) -> MemoryInfo:
        """获取内存信息"""
        mem = psutil.virtual_memory()
        
        # 判断状态
        if mem.percent >= 90:
            status = MemoryStatus.CRITICAL
        elif mem.percent >= 80:
            status = MemoryStatus.WARNING
        else:
            status = MemoryStatus.NORMAL
        
        return MemoryInfo(
            total=mem.total,
            available=mem.available,
            used=mem.used,
            percent=mem.percent,
            status=status
        )
    
    def check_memory_status(self) -> MemoryStatus:
        """检查内存状态"""
        return self.get_memory_info().status
    
    def cleanup(self, force: bool = False):
        """
        清理内存
        
        Args:
            force: 是否强制清理
        """
        mem_info = self.get_memory_info()
        
        if force or mem_info.percent >= self._memory_threshold:
            self._logger.info(f"🧹 开始内存清理 (使用率: {mem_info.percent:.1%})")
            
            # 调用垃圾回收
            gc.collect()
            
            # 清理追踪的对象
            self._tracked_objects.clear()
            
            self._last_cleanup_time = 0
            self._logger.info(f"✅ 内存清理完成")
    
    def track_object(self, obj_id: int):
        """追踪对象"""
        self._tracked_objects.add(obj_id)
    
    def untrack_object(self, obj_id: int):
        """取消追踪对象"""
        self._tracked_objects.discard(obj_id)
    
    def get_tracked_count(self) -> int:
        """获取追踪对象数量"""
        return len(self._tracked_objects)
    
    def optimize(self):
        """执行优化"""
        # 优化内存分配
        self.cleanup()
        
        # 优化垃圾回收策略
        gc.set_threshold(700, 10, 10)


class SecurityChecker:
    """
    安全检查器
    
    功能：
    1. 输入验证
    2. 敏感信息检测
    3. 路径遍历防护
    4. 命令注入检测
    """
    
    def __init__(self):
        self._logger = logger.bind(component="SecurityChecker")
        
        # 敏感信息模式
        self._sensitive_patterns = {
            'api_key': re.compile(r'(?i)(api[_\\-]?key|api[_\\-]?token|secret[_\\-]?key)\\s*[=:]\\s*["\']?([a-zA-Z0-9]+)["\']?'),
            'password': re.compile(r'(?i)password\\s*[=:]\\s*["\']?([a-zA-Z0-9]+)["\']?'),
            'email': re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}'),
            'phone': re.compile(r'1[3-9]\\d{9}'),
            'ipv4': re.compile(r'\\b(?:\\d{1,3}\\.){3}\\d{1,3}\\b'),
        }
        
        # 危险命令模式
        self._dangerous_commands = {
            'rm': ['rm', 'rm -rf', 'rmdir'],
            'chmod': ['chmod', 'chown'],
            'curl': ['curl', 'wget'],
            'eval': ['eval', 'exec', 'bash -c'],
            'python': ['python', 'python3', 'pip'],
        }
    
    def check_input(self, input_text: str) -> List[SecurityCheckResult]:
        """
        检查输入安全性
        
        Args:
            input_text: 输入文本
        
        Returns:
            安全检查结果列表
        """
        results = []
        
        # 检查敏感信息
        results.extend(self._check_sensitive_info(input_text))
        
        # 检查危险命令
        results.extend(self._check_dangerous_commands(input_text))
        
        # 检查路径遍历
        results.extend(self._check_path_traversal(input_text))
        
        return results
    
    def _check_sensitive_info(self, text: str) -> List[SecurityCheckResult]:
        """检查敏感信息"""
        results = []
        
        for pattern_name, pattern in self._sensitive_patterns.items():
            matches = pattern.findall(text)
            if matches:
                results.append(SecurityCheckResult(
                    check_name=f"sensitive_{pattern_name}",
                    status=SecurityLevel.HIGH,
                    message=f"检测到敏感信息: {pattern_name}",
                    details={"matches": matches}
                ))
        
        return results
    
    def _check_dangerous_commands(self, text: str) -> List[SecurityCheckResult]:
        """检查危险命令"""
        results = []
        
        for cmd_category, commands in self._dangerous_commands.items():
            for cmd in commands:
                if cmd.lower() in text.lower():
                    results.append(SecurityCheckResult(
                        check_name=f"dangerous_command_{cmd_category}",
                        status=SecurityLevel.MEDIUM,
                        message=f"检测到潜在危险命令: {cmd}",
                        details={"command": cmd}
                    ))
        
        return results
    
    def _check_path_traversal(self, text: str) -> List[SecurityCheckResult]:
        """检查路径遍历攻击"""
        patterns = ['../', '..\\', '/etc/', '/var/', 'C:\\\\', 'D:\\\\']
        
        for pattern in patterns:
            if pattern in text:
                return [SecurityCheckResult(
                    check_name="path_traversal",
                    status=SecurityLevel.CRITICAL,
                    message=f"检测到路径遍历攻击: {pattern}",
                    details={"pattern": pattern}
                )]
        
        return []
    
    def sanitize_input(self, input_text: str) -> str:
        """清理输入（移除敏感信息）"""
        sanitized = input_text
        
        # 移除敏感信息
        for pattern_name, pattern in self._sensitive_patterns.items():
            sanitized = pattern.sub(f'{pattern_name}=***', sanitized)
        
        # 移除危险命令
        for cmd_category, commands in self._dangerous_commands.items():
            for cmd in commands:
                sanitized = sanitized.replace(cmd, f"[{cmd_category}]")
        
        return sanitized
    
    def is_safe(self, input_text: str) -> bool:
        """检查输入是否安全"""
        results = self.check_input(input_text)
        return not any(r.status in [SecurityLevel.HIGH, SecurityLevel.CRITICAL] for r in results)


class VerificationFramework:
    """
    验证框架
    
    功能：
    1. 结果验证
    2. 证据收集
    3. 置信度评估
    4. 可验证性检查
    """
    
    def __init__(self):
        self._logger = logger.bind(component="VerificationFramework")
        self._verification_cache: Dict[str, VerificationResult] = {}
    
    def verify(self, data: Any, criteria: Dict[str, Any]) -> VerificationResult:
        """
        执行验证
        
        Args:
            data: 待验证数据
            criteria: 验证标准
        
        Returns:
            验证结果
        """
        verification_id = self._generate_id(data)
        score = 0.0
        checks = []
        
        # 执行各项检查
        if 'type' in criteria:
            type_check = self._check_type(data, criteria['type'])
            checks.append(type_check)
            score += type_check.get('score', 0.0)
        
        if 'format' in criteria:
            format_check = self._check_format(data, criteria['format'])
            checks.append(format_check)
            score += format_check.get('score', 0.0)
        
        if 'range' in criteria:
            range_check = self._check_range(data, criteria['range'])
            checks.append(range_check)
            score += range_check.get('score', 0.0)
        
        if 'pattern' in criteria:
            pattern_check = self._check_pattern(data, criteria['pattern'])
            checks.append(pattern_check)
            score += pattern_check.get('score', 0.0)
        
        # 计算综合分数
        avg_score = score / len(checks) if checks else 0.0
        
        # 判断状态
        if avg_score >= 0.9:
            status = VerificationStatus.PASSED
            message = "验证通过"
        elif avg_score >= 0.6:
            status = VerificationStatus.WARNING
            message = "验证部分通过"
        else:
            status = VerificationStatus.FAILED
            message = "验证失败"
        
        result = VerificationResult(
            verification_id=verification_id,
            status=status,
            message=message,
            score=avg_score,
            details={"checks": checks}
        )
        
        # 缓存结果
        self._verification_cache[verification_id] = result
        
        return result
    
    def _check_type(self, data: Any, expected_type: type) -> Dict[str, Any]:
        """检查类型"""
        actual_type = type(data).__name__
        is_pass = isinstance(data, expected_type)
        
        return {
            "name": "type_check",
            "passed": is_pass,
            "score": 1.0 if is_pass else 0.0,
            "expected": expected_type.__name__,
            "actual": actual_type
        }
    
    def _check_format(self, data: Any, expected_format: str) -> Dict[str, Any]:
        """检查格式"""
        if expected_format == "json":
            try:
                import json
                json.dumps(data)
                return {"name": "format_check", "passed": True, "score": 1.0}
            except:
                return {"name": "format_check", "passed": False, "score": 0.0}
        
        if expected_format == "markdown":
            text = str(data)
            has_markdown = any(char in text for char in ['#', '*', '`', '[', '>'])
            return {"name": "format_check", "passed": has_markdown, "score": 1.0 if has_markdown else 0.5}
        
        return {"name": "format_check", "passed": True, "score": 1.0}
    
    def _check_range(self, data: Any, range_spec: Dict[str, Any]) -> Dict[str, Any]:
        """检查范围"""
        if isinstance(data, (int, float)):
            min_val = range_spec.get('min', float('-inf'))
            max_val = range_spec.get('max', float('inf'))
            
            is_in_range = min_val <= data <= max_val
            return {
                "name": "range_check",
                "passed": is_in_range,
                "score": 1.0 if is_in_range else 0.0,
                "min": min_val,
                "max": max_val,
                "actual": data
            }
        
        return {"name": "range_check", "passed": True, "score": 1.0}
    
    def _check_pattern(self, data: Any, pattern: str) -> Dict[str, Any]:
        """检查模式匹配"""
        text = str(data)
        matches = bool(re.match(pattern, text))
        
        return {
            "name": "pattern_check",
            "passed": matches,
            "score": 1.0 if matches else 0.0,
            "pattern": pattern
        }
    
    def _generate_id(self, data: Any) -> str:
        """生成验证ID"""
        return hashlib.md5(str(data).encode()).hexdigest()[:16]
    
    def get_verification_result(self, verification_id: str) -> Optional[VerificationResult]:
        """获取验证结果"""
        return self._verification_cache.get(verification_id)
    
    def clear_cache(self):
        """清除验证缓存"""
        self._verification_cache.clear()


class HarnessOptimization:
    """
    系统化优化主类
    
    整合三个核心组件：
    1. MemoryManager - 内存管理
    2. SecurityChecker - 安全检查
    3. VerificationFramework - 验证框架
    """
    
    def __init__(self):
        self._logger = logger.bind(component="HarnessOptimization")
        
        # 初始化组件
        self.memory_manager = MemoryManager()
        self.security_checker = SecurityChecker()
        self.verification_framework = VerificationFramework()
        
        self._logger.info("✅ HarnessOptimization 初始化完成")
    
    def run_optimization(self):
        """运行完整优化流程"""
        self._logger.info("🔄 开始执行系统化优化")
        
        # 内存优化
        self.memory_manager.optimize()
        
        # 安全检查（如果需要）
        # 验证框架检查（如果需要）
        
        self._logger.info("✅ 系统化优化完成")
    
    def get_status(self) -> Dict[str, Any]:
        """获取整体状态"""
        return {
            "memory": {
                "info": self.memory_manager.get_memory_info().__dict__,
                "tracked_objects": self.memory_manager.get_tracked_count()
            },
            "verification_cache_size": len(self.verification_framework._verification_cache)
        }


# 创建全局实例
harness_optimization = HarnessOptimization()


def get_harness_optimization() -> HarnessOptimization:
    """获取系统化优化实例"""
    return harness_optimization


# 测试函数
async def test_harness_optimization():
    """测试系统化优化模块"""
    import sys
    logger.remove()
    logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", colorize=False)
    
    print("=" * 60)
    print("测试 HarnessOptimization")
    print("=" * 60)
    
    harness = HarnessOptimization()
    
    # 1. 测试内存管理器
    print("\n[1] 测试 MemoryManager...")
    mem_info = harness.memory_manager.get_memory_info()
    print(f"    ✓ 内存状态: {mem_info.status.value}")
    print(f"    ✓ 内存使用率: {mem_info.percent:.1%}")
    print(f"    ✓ 已追踪对象: {harness.memory_manager.get_tracked_count()}")
    
    # 2. 测试安全检查器
    print("\n[2] 测试 SecurityChecker...")
    test_inputs = [
        "正常输入",
        "我的密码是 password=123456",
        "运行命令: rm -rf /",
        "路径: ../../etc/passwd"
    ]
    
    for i, input_text in enumerate(test_inputs):
        results = harness.security_checker.check_input(input_text)
        is_safe = harness.security_checker.is_safe(input_text)
        print(f"    ✓ 输入{i+1}: {'安全' if is_safe else '不安全'} ({len(results)} 个问题)")
    
    sanitized = harness.security_checker.sanitize_input("api_key=secret123")
    print(f"    ✓ 清理后: {sanitized}")
    
    # 3. 测试验证框架
    print("\n[3] 测试 VerificationFramework...")
    
    # 测试类型验证
    result = harness.verification_framework.verify(
        42,
        {"type": int, "range": {"min": 0, "max": 100}}
    )
    print(f"    ✓ 类型验证: {result.status.value} (分数: {result.score:.2f})")
    
    # 测试格式验证
    result = harness.verification_framework.verify(
        "# Hello",
        {"format": "markdown"}
    )
    print(f"    ✓ 格式验证: {result.status.value} (分数: {result.score:.2f})")
    
    # 4. 测试完整优化
    print("\n[4] 测试完整优化...")
    harness.run_optimization()
    status = harness.get_status()
    print(f"    ✓ 优化完成")
    print(f"    ✓ 状态: {status}")
    
    print("\n" + "=" * 60)
    print("🎉 所有测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_harness_optimization())