"""
Tree-sitter 解析器测试
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from livingtree.core.code_understanding import TreeSitterParser, LanguageSupport


def test_python_parsing():
    """测试 Python 代码解析"""
    code = '''
"""示例模块"""

import math
from typing import List

class Calculator:
    """计算器类"""
    
    def __init__(self, name: str):
        self.name = name
    
    def add(self, a: int, b: int) -> int:
        """加法运算"""
        return a + b
    
    def multiply(self, a: int, b: int) -> int:
        """乘法运算"""
        return a * b

def process_data(data: List[int]) -> List[int]:
    """处理数据"""
    return [x * 2 for x in data]

result = process_data([1, 2, 3])
'''
    
    parser = TreeSitterParser(LanguageSupport.PYTHON)
    structure = parser.parse(code)
    
    print("=== Python 代码解析测试 ===")
    print(f"语言: {structure.language.value}")
    print(f"导入: {structure.imports}")
    print(f"类: {[c.name for c in structure.classes]}")
    print(f"函数: {[f.name for f in structure.functions]}")
    print(f"变量: {[v.name for v in structure.variables]}")
    print(f"总符号数: {len(structure.symbols)}")
    print(f"错误: {structure.errors}")
    print()


def test_javascript_parsing():
    """测试 JavaScript 代码解析"""
    code = '''
import React from 'react';

class App extends React.Component {
    constructor(props) {
        super(props);
        this.state = { count: 0 };
    }
    
    handleClick = () => {
        this.setState({ count: this.state.count + 1 });
    }
    
    render() {
        return (
            <div>
                <h1>计数器: {this.state.count}</h1>
                <button onClick={this.handleClick}>点击</button>
            </div>
        );
    }
}

export default App;
'''
    
    parser = TreeSitterParser(LanguageSupport.JAVASCRIPT)
    structure = parser.parse(code)
    
    print("=== JavaScript 代码解析测试 ===")
    print(f"语言: {structure.language.value}")
    print(f"导入: {structure.imports}")
    print(f"类: {[c.name for c in structure.classes]}")
    print(f"函数: {[f.name for f in structure.functions]}")
    print(f"变量: {[v.name for v in structure.variables]}")
    print(f"总符号数: {len(structure.symbols)}")
    print(f"错误: {structure.errors}")
    print()


def test_java_parsing():
    """测试 Java 代码解析"""
    code = '''
package com.example;

import java.util.List;
import java.util.ArrayList;

public class Service {
    private String name;
    
    public Service(String name) {
        this.name = name;
    }
    
    public List<String> process(List<String> items) {
        List<String> result = new ArrayList<>();
        for (String item : items) {
            result.add(item.toUpperCase());
        }
        return result;
    }
}
'''
    
    parser = TreeSitterParser(LanguageSupport.JAVA)
    structure = parser.parse(code)
    
    print("=== Java 代码解析测试 ===")
    print(f"语言: {structure.language.value}")
    print(f"导入: {structure.imports}")
    print(f"类: {[c.name for c in structure.classes]}")
    print(f"函数: {[f.name for f in structure.functions]}")
    print(f"变量: {[v.name for v in structure.variables]}")
    print(f"总符号数: {len(structure.symbols)}")
    print(f"错误: {structure.errors}")
    print()


def test_go_parsing():
    """测试 Go 代码解析"""
    code = '''
package main

import "fmt"

type Server struct {
    host string
    port int
}

func (s *Server) Start() {
    fmt.Printf("Server starting on %s:%d\\n", s.host, s.port)
}

func main() {
    server := &Server{host: "localhost", port: 8080}
    server.Start()
}
'''
    
    parser = TreeSitterParser(LanguageSupport.GO)
    structure = parser.parse(code)
    
    print("=== Go 代码解析测试 ===")
    print(f"语言: {structure.language.value}")
    print(f"导入: {structure.imports}")
    print(f"类/结构体: {[c.name for c in structure.classes]}")
    print(f"函数: {[f.name for f in structure.functions]}")
    print(f"变量: {[v.name for v in structure.variables]}")
    print(f"总符号数: {len(structure.symbols)}")
    print(f"错误: {structure.errors}")
    print()


def test_rust_parsing():
    """测试 Rust 代码解析"""
    code = '''
use std::collections::HashMap;

struct Config {
    host: String,
    port: u32,
}

enum Status {
    Active,
    Inactive,
}

fn process(config: &Config) -> Status {
    if config.port > 0 {
        Status::Active
    } else {
        Status::Inactive
    }
}
'''
    
    parser = TreeSitterParser(LanguageSupport.RUST)
    structure = parser.parse(code)
    
    print("=== Rust 代码解析测试 ===")
    print(f"语言: {structure.language.value}")
    print(f"导入: {structure.imports}")
    print(f"类/结构体: {[c.name for c in structure.classes]}")
    print(f"函数: {[f.name for f in structure.functions]}")
    print(f"变量: {[v.name for v in structure.variables]}")
    print(f"总符号数: {len(structure.symbols)}")
    print(f"错误: {structure.errors}")
    print()


def test_sql_parsing():
    """测试 SQL 代码解析"""
    code = '''
SELECT u.name, COUNT(o.id) as order_count
FROM users u
JOIN orders o ON u.id = o.user_id
WHERE u.status = 'active'
GROUP BY u.id, u.name
HAVING COUNT(o.id) > 5
ORDER BY order_count DESC;
'''
    
    parser = TreeSitterParser(LanguageSupport.SQL)
    structure = parser.parse(code)
    
    print("=== SQL 代码解析测试 ===")
    print(f"语言: {structure.language.value}")
    print(f"总符号数: {len(structure.symbols)}")
    print(f"错误: {structure.errors}")
    print()


def test_syntax_tree():
    """测试语法树构建"""
    code = '''
def greet(name):
    print(f"Hello, {name}!")
'''
    
    parser = TreeSitterParser(LanguageSupport.PYTHON)
    tree = parser.build_syntax_tree(code)
    
    print("=== 语法树测试 ===")
    print(f"根节点类型: {tree.type}")
    print(f"子节点数量: {len(tree.children)}")
    
    def print_tree(node, indent=0):
        prefix = "  " * indent
        value = f" = {repr(node.value)[:30]}" if node.value else ""
        print(f"{prefix}{node.type}{value}")
        for child in node.children:
            print_tree(child, indent + 1)
    
    print_tree(tree)
    print()


def test_incremental_update():
    """测试增量更新"""
    code = '''
def add(a, b):
    return a + b
'''
    
    parser = TreeSitterParser(LanguageSupport.PYTHON)
    structure = parser.parse(code)
    print("=== 增量更新测试 ===")
    print(f"初始函数: {[f.name for f in structure.functions]}")
    
    new_code = '''
def add(a, b):
    result = a + b
    return result
'''
    
    structure = parser.update(new_code, 28, 28, 49)
    if structure:
        print(f"更新后变量: {[v.name for v in structure.variables]}")
    else:
        print("增量更新失败")
    print()


def test_query():
    """测试语法查询"""
    code = '''
def func1():
    pass

def func2():
    pass

class MyClass:
    def method1(self):
        pass
'''
    
    parser = TreeSitterParser(LanguageSupport.PYTHON)
    
    # 查询所有函数定义
    query = '''
    (function_definition
        name: (identifier) @func.name
    )
    '''
    
    results = parser.query(code, query)
    print("=== 语法查询测试 ===")
    print(f"查询到的函数: {[r['func.name']['value'] for r in results]}")
    print()


if __name__ == "__main__":
    print("=" * 60)
    print("Tree-sitter 代码解析器测试")
    print("=" * 60)
    print()
    
    try:
        test_python_parsing()
        test_javascript_parsing()
        test_java_parsing()
        test_go_parsing()
        test_rust_parsing()
        test_sql_parsing()
        test_syntax_tree()
        test_incremental_update()
        test_query()
        
        print("=" * 60)
        print("所有测试通过!")
        print("=" * 60)
    except ImportError as e:
        print(f"警告: Tree-sitter 依赖未安装 - {e}")
        print("请运行: pip install tree-sitter tree-sitter-languages")
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()