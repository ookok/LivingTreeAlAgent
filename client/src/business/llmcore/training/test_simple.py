"""
最简单的测试：直接调用 train_cell.py 的 train() 函数
"""
import sys
import os

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.dirname(__file__))

# 模拟命令行参数
sys.argv = ['train_cell.py', '--cell', 'table_cell_test', '--max-iters', '5', '--no-compress']

try:
    print("=" * 60)
    print("开始导入 train_cell 模块...")
    print("=" * 60)
    
    # 方法1：直接 exec（避免 import 问题）
    with open('train_cell.py', 'r', encoding='utf-8') as f:
        code = f.read()
    
    # 创建模块字典
    module_dict = {
        '__name__': '__main__',
        '__file__': 'train_cell.py',
        'sys': sys,
        'os': os,
        'torch': __import__('torch'),
        'math': __import__('math'),
        'pickle': __import__('pickle'),
        'zipfile': __import__('zipfile'),
        'time': __import__('time'),
        'Path': __import__('pathlib').Path,
        'nullcontext': __import__('contextlib').nullcontext,
        'F': __import__('torch.nn.functional', fromlist=['F']).F,
        'clip_grad_norm_': __import__('torch.nn.utils', fromlist=['clip_grad_norm_']).clip_grad_norm_,
    }
    
    print("[1/2] 执行 train_cell.py 代码...")
    exec(code, module_dict)
    
    print("\n[2/2] 调用 train() 函数...")
    train_func = module_dict.get('train')
    if train_func:
        train_func()
    else:
        print("[ERROR] 找不到 train() 函数")
        
except Exception as e:
    import traceback
    print("\n" + "=" * 60)
    print("错误发生在：")
    traceback.print_exc()
    print("=" * 60)
    sys.exit(1)
