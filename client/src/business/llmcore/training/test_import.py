"""
Test train_cell.py by importing it as a module
"""
import sys
import os

# Add parent directory to path (for adapter import)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.dirname(__file__))

try:
    print("Testing imports...")
    from adapter import auto_detect_device
    print(f"[OK] auto_detect_device imported")
    
    from _nanogpt_src.model import GPT, GPTConfig
    print(f"[OK] GPT, GPTConfig imported")
    
    print("\nAll imports successful!")
    print("Now testing argument parsing...")
    
    # Simulate command line args
    sys.argv = ['train_cell.py', '--cell', 'table_cell_test', '--max-iters', '10', '--no-compress']
    
    # Import the main function
    import importlib.util
    spec = importlib.util.spec_from_file_location("train_cell", "train_cell.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    print("[OK] Module loaded successfully")
    
except Exception as e:
    import traceback
    print(f"[ERROR] {e}")
    traceback.print_exc()
