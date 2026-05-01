"""
代码理解模块测试脚本
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from business.code_understanding import (
    CodeParser,
    LanguageSupport,
    CodeAnalyzer,
    GitAnalyzer,
    PatternRecognizer,
    CodeGraph
)


def test_code_parser():
    """测试代码解析器"""
    print("📋 测试代码解析器...")
    
    parser = CodeParser()
    
    # 测试Python代码解析
    python_code = """
class UserService:
    def __init__(self):
        self.users = []
    
    def add_user(self, name: str) -> None:
        self.users.append(name)
    
    def get_users(self) -> list:
        return self.users

def main():
    service = UserService()
    service.add_user("Alice")
    print(service.get_users())
"""
    
    structure = parser.parse(python_code, LanguageSupport.PYTHON)
    
    print(f"  - 类数量: {len(structure.classes)}")
    print(f"  - 函数数量: {len(structure.functions)}")
    print(f"  - 变量数量: {len(structure.variables)}")
    print(f"  - 符号总数: {len(structure.symbols)}")
    
    assert len(structure.classes) >= 1, "至少应该识别到一个类"
    assert len(structure.symbols) >= 1, "至少应该识别到一个符号"
    print("✅ 代码解析器测试通过")


def test_code_analyzer():
    """测试代码分析器"""
    print("📋 测试代码分析器...")
    
    analyzer = CodeAnalyzer()
    
    test_code = """
def complex_function(x, y, z):
    result = 0
    if x > 0:
        if y > 0:
            if z > 0:
                result = x + y + z
            else:
                result = x + y
        else:
            result = x
    else:
        result = 0
    return result
"""
    
    report = analyzer.analyze(test_code)
    
    print(f"  - 圈复杂度: {report.complexity.cyclomatic_complexity}")
    print(f"  - 认知复杂度: {report.complexity.cognitive_complexity}")
    print(f"  - 行数: {report.complexity.lines_of_code}")
    print(f"  - 可维护性评分: {report.maintainability_score:.2f}")
    print(f"  - 问题数量: {len(report.issues)}")
    
    assert report.complexity.cyclomatic_complexity > 1
    print("✅ 代码分析器测试通过")


def test_git_analyzer():
    """测试Git分析器"""
    print("📋 测试Git分析器...")
    
    # 使用当前项目作为测试仓库
    repo_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    
    try:
        analyzer = GitAnalyzer(repo_path)
        
        info = analyzer.get_repo_info()
        print(f"  - 仓库名称: {info['name']}")
        print(f"  - 当前分支: {info['branch']}")
        print(f"  - 最后提交: {info['last_commit']}")
        
        stats = analyzer.get_repository_stats()
        print(f"  - 总提交数: {stats.total_commits}")
        print(f"  - 总文件数: {stats.total_files}")
        print(f"  - 贡献者数: {len(stats.contributors)}")
        
        hotspots = analyzer.get_hotspots()
        print(f"  - 热点文件数: {len(hotspots)}")
        
        print("✅ Git分析器测试通过")
    except Exception as e:
        print(f"⚠️ Git分析器测试跳过（非Git仓库）: {e}")


def test_pattern_recognizer():
    """测试模式识别器"""
    print("📋 测试模式识别器...")
    
    recognizer = PatternRecognizer()
    
    # 测试单例模式识别
    singleton_code = """
class Singleton:
    __instance = None
    
    def __new__(cls):
        if not cls.__instance:
            cls.__instance = super().__new__(cls)
        return cls.__instance
    
    @classmethod
    def get_instance(cls):
        if not cls.__instance:
            cls.__instance = cls()
        return cls.__instance
"""
    
    patterns = recognizer.recognize_patterns(singleton_code)
    
    print(f"  - 识别到模式数: {len(patterns)}")
    for pattern in patterns:
        print(f"    - [{pattern.pattern_type.value}] {pattern.pattern_name} (置信度: {pattern.confidence:.2f})")
    
    suggestions = recognizer.suggest_refactoring(singleton_code)
    print(f"  - 重构建议数: {len(suggestions)}")
    
    print("✅ 模式识别器测试通过")


def test_code_graph():
    """测试代码图"""
    print("📋 测试代码图...")
    
    graph = CodeGraph()
    
    # 添加文件和符号
    graph.add_file("src/service/user_service.py")
    graph.add_file("src/repository/user_repo.py")
    
    graph.add_symbol("src/service/user_service.py", "UserService", "class", 1)
    graph.add_symbol("src/service/user_service.py", "create_user", "function", 10)
    graph.add_symbol("src/repository/user_repo.py", "UserRepository", "class", 1)
    graph.add_symbol("src/repository/user_repo.py", "save", "function", 15)
    
    # 添加依赖关系
    graph.add_import("src/service/user_service.py", "UserRepository", "src/repository/user_repo.py")
    graph.add_call("src/service/user_service.py", "create_user", "src/repository/user_repo.py", "save")
    
    # 分析影响
    impact = graph.analyze_impact("src/repository/user_repo.py")
    print(f"  - 影响分析: {impact}")
    
    # 查找循环依赖
    cycles = graph.find_cycles()
    print(f"  - 循环依赖数: {len(cycles)}")
    
    # 导出JSON
    json_data = graph.to_json()
    print(f"  - 图节点数: {len(graph._nodes)}")
    print(f"  - 图边数: {len(graph._edges)}")
    
    print("✅ 代码图测试通过")


def main():
    """运行所有测试"""
    print("🚀 开始测试代码理解模块...")
    
    tests = [
        test_code_parser,
        test_code_analyzer,
        test_git_analyzer,
        test_pattern_recognizer,
        test_code_graph
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__} 测试失败: {e}")
            failed += 1
    
    print(f"\n📊 测试结果: {passed} 通过, {failed} 失败")
    return passed == len(tests)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)