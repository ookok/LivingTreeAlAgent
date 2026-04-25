#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Evolution Engine 实际项目测试
测试 LivingTreeAI 项目的自我进化能力
"""

import sys
import os
import time

# 添加项目路径
sys.path.insert(0, r'f:\mhzyapp\LivingTreeAlAgent')

# 独立实现，不依赖项目的导入链
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum
import json
import re
from collections import defaultdict
from pathlib import Path

# ============================================================================
# Part 1: 代码质量扫描器 (模拟 sensors/quality_sensor.py)
# ============================================================================

class QualityIssue(Enum):
    LONG_FUNCTION = "long_function"
    DEAD_CODE = "dead_code"
    DUPLICATE_CODE = "duplicate_code"
    COMPLEX_METHOD = "complex_method"
    EMPTY_CATCH = "empty_catch"
    HARDCODED_CONFIG = "hardcoded_config"
    MISSING_ERROR_HANDLING = "missing_error_handling"
    INCOMPLETE_IMPL = "incomplete_impl"

@dataclass
class QualityFinding:
    file: str
    line: int
    issue_type: QualityIssue
    severity: str  # high, medium, low
    description: str
    suggestion: str

def scan_code_quality(project_root: str) -> List[QualityFinding]:
    """扫描项目代码质量问题"""
    findings = []
    patterns = [
        (r'def\s+\w+\([^)]*\):\s*\n(?:[^\n]*\n){50,}', QualityIssue.LONG_FUNCTION, "high",
         "函数超过50行", "考虑拆分为更小的函数"),
        (r'except[^:]*:\s*\n\s*pass', QualityIssue.EMPTY_CATCH, "medium",
         "空except块", "添加错误处理或日志"),
        (r'TODO|FIXME|HACK|XXX', QualityIssue.INCOMPLETE_IMPL, "low",
         "未完成的实现", "尽快完成或创建Issue追踪"),
        (r'time\.sleep\(\s*[\d.]+\s*\)', QualityIssue.HARDCODED_CONFIG, "medium",
         "硬编码sleep时间", "使用配置系统统一管理"),
    ]
    
    # 扫描关键目录
    scan_dirs = ['core', 'ui', 'services']
    
    for scan_dir in scan_dirs:
        full_path = os.path.join(project_root, scan_dir)
        if not os.path.exists(full_path):
            continue
            
        for root, dirs, files in os.walk(full_path):
            # 跳过测试和缓存目录
            dirs[:] = [d for d in dirs if d not in ['__pycache__', 'test', 'tests', '.git']]
            
            for file in files:
                if not file.endswith('.py'):
                    continue
                    
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        lines = content.split('\n')
                        
                    for pattern, issue_type, severity, desc, suggestion in patterns:
                        for i, line in enumerate(lines, 1):
                            if re.search(pattern, '\n'.join(lines[max(0,i-1):min(len(lines),i+10)])):
                                findings.append(QualityFinding(
                                    file=filepath,
                                    line=i,
                                    issue_type=issue_type,
                                    severity=severity,
                                    description=desc,
                                    suggestion=suggestion
                                ))
                except Exception as e:
                    pass  # 忽略编码错误
    
    return findings

# ============================================================================
# Part 2: 架构异味检测器 (模拟 sensors/architecture_smell_sensor.py)
# ============================================================================

@dataclass
class ArchitectureSmell:
    module: str
    smell_type: str
    severity: str
    description: str
    metrics: Dict[str, Any]

def detect_architecture_smells(project_root: str) -> List[ArchitectureSmell]:
    """检测架构异味"""
    smells = []
    
    # 检查循环依赖
    circular_imports = detect_circular_imports(project_root)
    if circular_imports:
        smells.append(ArchitectureSmell(
            module="core",
            smell_type="circular_dependency",
            severity="high",
            description=f"发现 {len(circular_imports)} 个循环依赖",
            metrics={"circular_pairs": circular_imports}
        ))
    
    # 检查模块间耦合度
    coupling = analyze_coupling(project_root)
    for module, metrics in coupling.items():
        if metrics['incoming'] > 10:
            smells.append(ArchitectureSmell(
                module=module,
                smell_type="high_coupling",
                severity="medium",
                description=f"{module} 被 {metrics['incoming']} 个模块依赖",
                metrics=metrics
            ))
    
    return smells

def detect_circular_imports(project_root: str) -> List[tuple]:
    """检测循环导入"""
    circular = []
    
    # 简化的循环导入检测
    core_path = os.path.join(project_root, 'core')
    if not os.path.exists(core_path):
        return circular
        
    # 检查 __init__.py 中的导入
    init_files = list(Path(core_path).rglob('__init__.py'))
    import_graph = defaultdict(set)
    
    for init_file in init_files:
        module = str(init_file.parent.relative_to(core_path))
        try:
            content = init_file.read_text(encoding='utf-8')
            imports = re.findall(r'from\s+\.(\w+)', content)
            for imp in imports:
                import_graph[module].add(imp)
        except:
            pass
    
    # 检测循环
    for module in import_graph:
        for dep in import_graph[module]:
            if dep in import_graph and module in import_graph[dep]:
                circular.append((module, dep))
    
    return circular

def analyze_coupling(project_root: str) -> Dict[str, Dict]:
    """分析模块耦合度"""
    coupling = defaultdict(lambda: {'incoming': 0, 'outgoing': 0})
    
    core_path = os.path.join(project_root, 'core')
    if not os.path.exists(core_path):
        return {}
    
    # 统计每个模块被其他模块导入的次数
    for py_file in Path(core_path).rglob('*.py'):
        if '__pycache__' in str(py_file):
            continue
            
        try:
            content = py_file.read_text(encoding='utf-8')
            imports = re.findall(r'from\s+core\.(\w+)', content)
            for imp in imports:
                if imp in ['core', 'utils', 'services']:
                    coupling[imp]['outgoing'] += 1
        except:
            pass
    
    return dict(coupling)

# ============================================================================
# Part 3: 配置问题检测器 (模拟 sensors/config_sensor.py)
# ============================================================================

@dataclass
class ConfigIssue:
    file: str
    issue_type: str
    description: str
    recommendation: str

def detect_config_issues(project_root: str) -> List[ConfigIssue]:
    """检测配置相关问题"""
    issues = []
    
    # 检测硬编码配置
    hardcoded = detect_hardcoded_configs(project_root)
    for item in hardcoded:
        issues.append(ConfigIssue(
            file=item['file'],
            issue_type='hardcoded_value',
            description=f"发现硬编码值: {item['value']}",
            recommendation='迁移到统一配置系统 (unified_config.py)'
        ))
    
    # 检测不一致的超时配置
    timeout_issues = detect_inconsistent_timeouts(project_root)
    if timeout_issues:
        issues.append(ConfigIssue(
            file='multiple',
            issue_type='inconsistent_timeout',
            description=f"发现 {len(timeout_issues)} 处不一致的超时配置",
            recommendation='使用 unified_config.py 的 get_timeout_config()'
        ))
    
    return issues

def detect_hardcoded_configs(project_root: str) -> List[Dict]:
    """检测硬编码配置值"""
    hardcoded = []
    patterns = [
        (r'timeout\s*=\s*(\d+)', 'timeout'),
        (r'sleep\(\s*([\d.]+)\s*\)', 'sleep'),
        (r'retry\s*=\s*(\d+)', 'retry'),
        (r'interval\s*=\s*([\d.]+)', 'interval'),
    ]
    
    for py_file in Path(project_root).rglob('*.py'):
        if '__pycache__' in str(py_file) or 'test' in str(py_file):
            continue
            
        try:
            content = py_file.read_text(encoding='utf-8')
            for pattern, config_type in patterns:
                matches = re.finditer(pattern, content)
                for match in matches:
                    hardcoded.append({
                        'file': str(py_file.relative_to(project_root)),
                        'type': config_type,
                        'value': match.group(0),
                        'line': content[:match.start()].count('\n') + 1
                    })
        except:
            pass
    
    return hardcoded[:20]  # 限制数量

def detect_inconsistent_timeouts(project_root: str) -> List[Dict]:
    """检测不一致的超时配置"""
    timeouts = []
    
    for py_file in Path(project_root).rglob('*.py'):
        if '__pycache__' in str(py_file):
            continue
        try:
            content = py_file.read_text(encoding='utf-8')
            matches = re.finditer(r'timeout\s*=\s*(\d+\.?\d*)', content)
            for match in matches:
                timeouts.append({
                    'file': str(py_file.relative_to(project_root)),
                    'value': float(match.group(1))
                })
        except:
            pass
    
    # 检测不一致
    unique_values = set(t['value'] for t in timeouts)
    if len(unique_values) > 5:  # 如果有超过5种不同的超时值
        return timeouts[:10]
    
    return []

# ============================================================================
# Part 4: 性能问题检测器 (模拟 sensors/performance_sensor.py)
# ============================================================================

@dataclass
class PerformanceIssue:
    file: str
    line: int
    issue_type: str
    description: str
    impact: str

def detect_performance_issues(project_root: str) -> List[PerformanceIssue]:
    """检测性能问题"""
    issues = []
    
    # 检测同步阻塞操作
    for py_file in Path(project_root).rglob('*.py'):
        if '__pycache__' in str(py_file) or 'test' in str(py_file):
            continue
        try:
            content = py_file.read_text(encoding='utf-8')
            lines = content.split('\n')
            
            for i, line in enumerate(lines):
                # 检测大文件同步读取
                if 'open(' in line and 'rb' in line:
                    issues.append(PerformanceIssue(
                        file=str(py_file.relative_to(project_root)),
                        line=i+1,
                        issue_type='sync_io',
                        description='同步文件读取',
                        impact='可能阻塞事件循环'
                    ))
                
                # 检测循环中的数据库操作
                if 'for ' in line and i+1 < len(lines):
                    next_lines = '\n'.join(lines[i:i+5])
                    if 'cursor.execute' in next_lines or 'session.query' in next_lines:
                        issues.append(PerformanceIssue(
                            file=str(py_file.relative_to(project_root)),
                            line=i+1,
                            issue_type='n+1_query',
                            description='循环中执行数据库查询',
                            impact='可能导致 N+1 查询问题'
                        ))
        except:
            pass
    
    return issues[:10]

# ============================================================================
# Part 5: 信号聚合器 (模拟 aggregator/rrf_aggregator.py)
# ============================================================================

@dataclass
class EvolutionSignal:
    signal_id: str
    source: str
    signal_type: str
    severity: float
    title: str
    description: str
    affected_files: List[str]
    metrics: Dict[str, Any]
    timestamp: str
    tags: List[str]

def aggregate_signals(
    quality_findings: List[QualityFinding],
    arch_smells: List[ArchitectureSmell],
    config_issues: List[ConfigIssue],
    perf_issues: List[PerformanceIssue]
) -> List[EvolutionSignal]:
    """聚合所有传感器信号"""
    signals = []
    signal_id = 1
    
    # 转换代码质量问题
    for f in quality_findings:
        signals.append(EvolutionSignal(
            signal_id=f"sig-{signal_id:03d}",
            source="quality_sensor",
            signal_type=f.issue_type.value,
            severity={"high": 0.9, "medium": 0.6, "low": 0.3}[f.severity],
            title=f"{f.issue_type.value}: {f.description}",
            description=f"{f.description} at {os.path.basename(f.file)}:{f.line}",
            affected_files=[f.file],
            metrics={"line": f.line, "suggestion": f.suggestion},
            timestamp=datetime.now().isoformat(),
            tags=["code-quality", f.severity]
        ))
        signal_id += 1
    
    # 转换架构异味
    for smell in arch_smells:
        signals.append(EvolutionSignal(
            signal_id=f"sig-{signal_id:03d}",
            source="architecture_smell_sensor",
            signal_type=smell.smell_type,
            severity={"high": 0.95, "medium": 0.65, "low": 0.35}[smell.severity],
            title=f"{smell.smell_type}: {smell.description}",
            description=smell.description,
            affected_files=[smell.module],
            metrics=smell.metrics,
            timestamp=datetime.now().isoformat(),
            tags=["architecture", smell.severity]
        ))
        signal_id += 1
    
    # 转换配置问题
    for issue in config_issues:
        signals.append(EvolutionSignal(
            signal_id=f"sig-{signal_id:03d}",
            source="config_sensor",
            signal_type=issue.issue_type,
            severity=0.7,
            title=f"config: {issue.description}",
            description=f"{issue.description}\n建议: {issue.recommendation}",
            affected_files=[issue.file] if issue.file != 'multiple' else [],
            metrics={"recommendation": issue.recommendation},
            timestamp=datetime.now().isoformat(),
            tags=["config", "technical-debt"]
        ))
        signal_id += 1
    
    # 转换性能问题
    for issue in perf_issues:
        signals.append(EvolutionSignal(
            signal_id=f"sig-{signal_id:03d}",
            source="performance_sensor",
            signal_type=issue.issue_type,
            severity=0.75,
            title=f"perf: {issue.description}",
            description=f"{issue.description} at {os.path.basename(issue.file)}:{issue.line}\nImpact: {issue.impact}",
            affected_files=[issue.file],
            metrics={"line": issue.line, "impact": issue.impact},
            timestamp=datetime.now().isoformat(),
            tags=["performance"]
        ))
        signal_id += 1
    
    # 按严重度排序
    signals.sort(key=lambda s: s.severity, reverse=True)
    
    return signals

# ============================================================================
# Part 6: 提案生成器 (模拟 proposal/proposal_generator.py)
# ============================================================================

@dataclass
class EvolutionProposal:
    proposal_id: str
    signals: List[str]
    title: str
    description: str
    benefits: List[str]
    risks: List[str]
    implementation_path: List[str]
    estimated_effort: str
    confidence: float
    priority: str
    timestamp: str

def generate_proposals(signals: List[EvolutionSignal]) -> List[EvolutionProposal]:
    """基于信号生成进化提案"""
    proposals = []
    
    # 按类型分组信号
    by_type = defaultdict(list)
    for s in signals:
        by_type[s.signal_type].append(s)
    
    # 提案1: 配置迁移
    config_signals = by_type.get('hardcoded_value', [])
    if len(config_signals) >= 3:
        files = list(set(s.affected_files[0] for s in config_signals if s.affected_files))[:5]
        proposals.append(EvolutionProposal(
            proposal_id="prop-001",
            signals=[s.signal_id for s in config_signals],
            title="统一配置系统迁移",
            description=f"将 {len(config_signals)} 处硬编码配置迁移到 unified_config.py",
            benefits=["集中管理配置", "便于维护", "支持热更新"],
            risks=["需要修改多个文件", "可能影响现有功能"],
            implementation_path=[
                "1. 识别所有硬编码配置",
                "2. 添加到 unified.yaml",
                "3. 创建配置获取方法",
                "4. 逐文件迁移",
                "5. 验证功能正常"
            ],
            estimated_effort="medium",
            confidence=0.85,
            priority="high",
            timestamp=datetime.now().isoformat()
        ))
    
    # 提案2: 代码质量改进
    long_func_signals = by_type.get('long_function', [])
    empty_catch_signals = by_type.get('empty_catch', [])
    if len(long_func_signals) >= 2 or len(empty_catch_signals) >= 2:
        files = list(set(s.affected_files[0] for s in long_func_signals + empty_catch_signals if s.affected_files))[:5]
        proposals.append(EvolutionProposal(
            proposal_id="prop-002",
            signals=[s.signal_id for s in long_func_signals + empty_catch_signals],
            title="代码质量提升",
            description=f"优化 {len(long_func_signals)} 个过长函数，处理 {len(empty_catch_signals)} 个空异常块",
            benefits=["提高代码可读性", "减少bug风险", "改善维护性"],
            risks=["重构可能引入bug", "需要充分测试"],
            implementation_path=[
                "1. 识别过长函数",
                "2. 分析函数职责",
                "3. 拆分为更小的函数",
                "4. 处理空catch块",
                "5. 添加适当日志"
            ],
            estimated_effort="high",
            confidence=0.75,
            priority="medium",
            timestamp=datetime.now().isoformat()
        ))
    
    # 提案3: 架构改进
    arch_signals = by_type.get('circular_dependency', []) + by_type.get('high_coupling', [])
    if arch_signals:
        proposals.append(EvolutionProposal(
            proposal_id="prop-003",
            signals=[s.signal_id for s in arch_signals],
            title="架构解耦优化",
            description=f"解决 {len(arch_signals)} 个架构问题",
            benefits=["降低耦合度", "提高模块独立性", "便于测试"],
            risks=["重构风险大", "需要仔细规划"],
            implementation_path=[
                "1. 分析依赖关系图",
                "2. 识别循环依赖",
                "3. 引入抽象接口",
                "4. 逐步解耦",
                "5. 验证功能"
            ],
            estimated_effort="high",
            confidence=0.65,
            priority="low",
            timestamp=datetime.now().isoformat()
        ))
    
    # 提案4: 性能优化
    perf_signals = by_type.get('sync_io', []) + by_type.get('n+1_query', [])
    if len(perf_signals) >= 2:
        proposals.append(EvolutionProposal(
            proposal_id="prop-004",
            signals=[s.signal_id for s in perf_signals],
            title="性能问题修复",
            description=f"修复 {len(perf_signals)} 个性能问题",
            benefits=["提升响应速度", "改善用户体验", "降低资源消耗"],
            risks=["异步改造复杂", "需要测试边界情况"],
            implementation_path=[
                "1. 识别性能瓶颈",
                "2. 优化同步IO为异步",
                "3. 解决N+1查询",
                "4. 添加缓存",
                "5. 性能测试验证"
            ],
            estimated_effort="medium",
            confidence=0.70,
            priority="medium",
            timestamp=datetime.now().isoformat()
        ))
    
    return proposals

# ============================================================================
# Part 7: 进化记忆存储 (模拟 memory/evolution_log.py)
# ============================================================================

def save_to_evolution_log(
    db_path: str,
    signals: List[EvolutionSignal],
    proposals: List[EvolutionProposal]
) -> bool:
    """保存到进化日志"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 创建表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evolution_signals (
                signal_id TEXT PRIMARY KEY,
                source TEXT,
                signal_type TEXT,
                severity REAL,
                title TEXT,
                description TEXT,
                affected_files TEXT,
                metrics TEXT,
                timestamp TEXT,
                tags TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evolution_proposals (
                proposal_id TEXT PRIMARY KEY,
                signals TEXT,
                title TEXT,
                description TEXT,
                benefits TEXT,
                risks TEXT,
                implementation_path TEXT,
                estimated_effort TEXT,
                confidence REAL,
                priority TEXT,
                timestamp TEXT
            )
        ''')
        
        # 插入信号
        for s in signals:
            cursor.execute('''
                INSERT OR REPLACE INTO evolution_signals 
                (signal_id, source, signal_type, severity, title, description, 
                 affected_files, metrics, timestamp, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                s.signal_id, s.source, s.signal_type, s.severity, s.title,
                s.description, json.dumps(s.affected_files), json.dumps(s.metrics),
                s.timestamp, json.dumps(s.tags)
            ))
        
        # 插入提案
        for p in proposals:
            cursor.execute('''
                INSERT OR REPLACE INTO evolution_proposals 
                (proposal_id, signals, title, description, benefits, risks,
                 implementation_path, estimated_effort, confidence, priority, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                p.proposal_id, json.dumps(p.signals), p.title, p.description,
                json.dumps(p.benefits), json.dumps(p.risks),
                json.dumps(p.implementation_path), p.estimated_effort,
                p.confidence, p.priority, p.timestamp
            ))
        
        conn.commit()
        return True
    finally:
        conn.close()

# ============================================================================
# Part 8: 主测试流程
# ============================================================================

def run_evolution_test():
    """运行完整的 Evolution Engine 测试"""
    print("=" * 70)
    print(" Evolution Engine - 实际项目测试 (LivingTreeAI)")
    print("=" * 70)
    
    project_root = r'f:\mhzyapp\LivingTreeAlAgent'
    db_path = os.path.join(project_root, '.evolution', 'test_evolution.db')
    
    # 确保目录存在
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    # Step 1: 代码质量扫描
    print("\n[1/6] 代码质量扫描...")
    quality_findings = scan_code_quality(project_root)
    print(f"      发现 {len(quality_findings)} 个代码质量问题")
    
    # Step 2: 架构异味检测
    print("\n[2/6] 架构异味检测...")
    arch_smells = detect_architecture_smells(project_root)
    print(f"      发现 {len(arch_smells)} 个架构异味")
    
    # Step 3: 配置问题检测
    print("\n[3/6] 配置问题检测...")
    config_issues = detect_config_issues(project_root)
    print(f"      发现 {len(config_issues)} 个配置问题")
    
    # Step 4: 性能问题检测
    print("\n[4/6] 性能问题检测...")
    perf_issues = detect_performance_issues(project_root)
    print(f"      发现 {len(perf_issues)} 个性能问题")
    
    # Step 5: 信号聚合
    print("\n[5/6] 信号聚合...")
    signals = aggregate_signals(quality_findings, arch_smells, config_issues, perf_issues)
    print(f"      生成 {len(signals)} 个进化信号")
    
    # Step 6: 提案生成
    print("\n[6/6] 提案生成...")
    proposals = generate_proposals(signals)
    print(f"      生成 {len(proposals)} 个进化提案")
    
    # Step 7: 保存到进化日志
    print("\n[7/7] 保存到进化日志...")
    save_to_evolution_log(db_path, signals, proposals)
    print(f"      已保存到 {db_path}")
    
    # 输出结果摘要
    print("\n" + "=" * 70)
    print(" TEST RESULTS SUMMARY")
    print("=" * 70)
    
    print(f"\n[Signal Stats]")
    print(f"   - Code Quality: {len(quality_findings)} issues")
    print(f"   - Architecture Smells: {len(arch_smells)} issues")
    print(f"   - Config Issues: {len(config_issues)} issues")
    print(f"   - Performance Issues: {len(perf_issues)} issues")
    print(f"   - Total Signals: {len(signals)}")
    
    print(f"\n[Evolution Proposals]")
    for p in proposals:
        print(f"\n   [{p.priority.upper()}] {p.title}")
        print(f"   - Signals: {len(p.signals)}")
        print(f"   - Confidence: {p.confidence:.0%}")
        print(f"   - Effort: {p.estimated_effort}")
        print(f"   - Benefits: {', '.join(p.benefits[:2])}")
    
    # Top 5 信号
    print(f"\n[Top 5 High Priority Signals]")
    for i, s in enumerate(signals[:5], 1):
        print(f"   {i}. [{s.source}] {s.title[:50]}")
    
    print("\n" + "=" * 70)
    print(" TEST COMPLETED!")
    print("=" * 70)
    
    return signals, proposals

if __name__ == '__main__':
    signals, proposals = run_evolution_test()
