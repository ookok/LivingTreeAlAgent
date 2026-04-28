"""
直接运行 train_cell.py 并捕获所有错误
"""
import sys
import os
import traceback

# 模拟命令行参数
sys.argv = ['train_cell.py', '--cell', 'table_cell_test', '--max-iters', '5', '--no-compress']

# 添加路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.dirname(__file__))

try:
    # 直接导入并运行 train() 函数
    from train_cell import train
    print("=" * 60)
    print("Starting training...")
    print("=" * 60 + "\n")
    train()
except Exception as e:
    print("\n" + "=" * 60)
    print("ERROR OCCURRED:")
    print("=" * 60)
    traceback.print_exc()
    sys.exit(1)
