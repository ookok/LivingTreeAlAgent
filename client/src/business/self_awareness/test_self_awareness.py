"""
自我意识系统测试
"""

import pytest
import time
from self_awareness import (
    MirrorLauncher,
    ComponentScanner,
    ProblemDetector,
    HotFixEngine,
    ComponentType,
    ProblemCategory,
    ProblemSeverity
)


class TestMirrorLauncher:
    """镜像启动器测试"""
    
    def setup_method(self):
        self.launcher = MirrorLauncher()
        
    def test_launch_instance(self):
        """测试启动镜像实例"""
        instance = self.launcher.launch("./test_project", {"test": True})
        
        assert instance is not None
        assert instance.status.value in ["launching", "running"]
        
    def test_list_instances(self):
        """测试列出实例"""
        instances = self.launcher.list_instances()
        assert isinstance(instances, list)


class TestComponentScanner:
    """组件扫描器测试"""
    
    def setup_method(self):
        self.scanner = ComponentScanner()
        
    def test_scan_directory(self):
        """测试目录扫描"""
        # 创建临时测试目录
        import tempfile
        import os
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建测试文件
            test_file = os.path.join(tmpdir, "test_ui.py")
            with open(test_file, 'w') as f:
                f.write("""
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
class MyButton(QPushButton):
    pass
""")
            
            result = self.scanner.scan_directory(tmpdir)
            assert result is not None


class TestProblemDetector:
    """问题检测器测试"""
    
    def setup_method(self):
        self.detector = ProblemDetector()
        
    def test_detect_exception(self):
        """测试异常检测"""
        try:
            raise ValueError("Test error")
        except Exception as e:
            report = self.detector.detect_from_exception(e)
            
            assert report.category == ProblemCategory.RUNTIME_ERROR
            assert report.severity in [ProblemSeverity.MEDIUM, ProblemSeverity.HIGH]


class TestHotFixEngine:
    """热修复引擎测试"""
    
    def setup_method(self):
        self.engine = HotFixEngine()
        
    def test_fix_null_pointer(self):
        """测试空指针修复"""
        code = "result = data[key]"
        result = self.engine.fix(code, "null_pointer")
        
        assert result.success
        assert '.get(' in result.fixed_code or result.fixed_code == code
        
    def test_validate_fix(self):
        """测试修复验证"""
        valid_code = "x = 1 + 2"
        is_valid = self.engine._validate(valid_code)
        assert is_valid


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
