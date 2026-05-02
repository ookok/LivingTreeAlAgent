"""
自动测试执行器
在镜像环境中执行测试
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import subprocess
import time
import json
from pathlib import Path


@dataclass
class TestCase:
    """测试用例"""
    name: str
    test_type: str  # 'unit' | 'integration' | 'ui' | 'performance'
    target: Optional[str] = None
    expected_result: Optional[str] = None
    timeout: int = 300
    
    
@dataclass
class TestResult:
    """测试结果"""
    test_case: TestCase
    success: bool
    output: str = ""
    error: Optional[str] = None
    duration: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)
    

class AutoTester:
    """
    自动测试执行器
    
    功能：
    1. 在镜像环境中执行测试
    2. 收集测试结果
    3. 生成测试报告
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or self._default_config()
        self.test_history: List[TestResult] = []
        
    def _default_config(self) -> Dict[str, Any]:
        return {
            'test_command': 'python -m pytest',
            'test_args': ['-v', '--tb=short'],
            'timeout': 300,
            'retry_count': 2,
        }
        
    def run_tests(self, 
                  mirror_path: str,
                  test_paths: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        在镜像中运行测试
        
        Args:
            mirror_path: 镜像路径
            test_paths: 测试文件路径列表
            
        Returns:
            测试结果汇总
        """
        if not test_paths:
            test_paths = ['tests/']
            
        cmd = self.config['test_command'].split()
        cmd.extend(self.config['test_args'])
        cmd.extend(test_paths)
        
        results = {
            'total': 0,
            'passed': 0,
            'failed': 0,
            'errors': 0,
            'details': [],
        }
        
        start_time = time.time()
        
        try:
            result = subprocess.run(
                cmd,
                cwd=mirror_path,
                capture_output=True,
                text=True,
                timeout=self.config['timeout']
            )
            
            output = result.stdout + '\n' + result.stderr
            
            # 解析pytest输出
            for line in output.split('\n'):
                if 'passed' in line or 'PASSED' in line:
                    results['passed'] += 1
                elif 'failed' in line or 'FAILED' in line:
                    results['failed'] += 1
                    
            results['total'] = results['passed'] + results['failed']
            results['output'] = output
            results['returncode'] = result.returncode
            results['duration'] = time.time() - start_time
            
        except subprocess.TimeoutExpired:
            results['error'] = f"测试超时（{self.config['timeout']}秒）"
            results['duration'] = self.config['timeout']
            
        except Exception as e:
            results['error'] = str(e)
            
        return results
        
    def run_ui_tests(self, mirror_instance: Any) -> Dict[str, Any]:
        """
        运行UI测试（需要镜像实例）
        
        简化实现：检查UI文件是否存在和语法正确
        """
        results = {
            'total': 0,
            'passed': 0,
            'failed': 0,
            'details': [],
        }
        
        # 扫描UI文件
        ui_files = list(Path(mirror_instance).rglob('*.py'))
        ui_files = [f for f in ui_files if 'ui/' in str(f) or 'panel' in f.name]
        
        results['total'] = len(ui_files)
        
        for ui_file in ui_files:
            try:
                with open(ui_file, 'r', encoding='utf-8') as f:
                    code = f.read()
                    
                # 编译检查
                compile(code, str(ui_file), 'exec')
                results['passed'] += 1
                
            except SyntaxError as e:
                results['failed'] += 1
                results['details'].append({
                    'file': str(ui_file),
                    'error': str(e),
                })
                
        return results
        
    def generate_report(self, results: Dict[str, Any]) -> str:
        """生成测试报告"""
        report = []
        report.append("=" * 60)
        report.append("测试报告")
        report.append("=" * 60)
        report.append(f"总计: {results['total']}")
        report.append(f"通过: {results['passed']}")
        report.append(f"失败: {results['failed']}")
        
        if results.get('error'):
            report.append(f"\n错误: {results['error']}")
            
        if results.get('output'):
            report.append(f"\n详细输出:\n{results['output'][:2000]}")
            
        return '\n'.join(report)
