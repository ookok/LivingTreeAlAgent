"""测试 llama-cpp-python 集成"""
import sys
sys.path.insert(0, "d:/mhzyapp/hermes-desktop")

print("=== Unified Model Client Test ===")
print()

# 1. 测试模块导入
print("[1/4] Module Imports...")
from core.llama_cpp_client import (
    LlamaCppClient,
    LlamaCppConfig,
    LLAMA_CPP_AVAILABLE,
    list_available_models,
)
from core.unified_model_client import (
    UnifiedModelClient,
    UnifiedModelManager,
    ModelSource,
    Message,
    GenerationConfig,
    create_local_client,
)
print("  All imports OK")

# 2. llama-cpp-python 可用性
print()
print("[2/4] llama-cpp-python Status...")
print(f"  Available: {LLAMA_CPP_AVAILABLE}")

# 3. 配置类测试
print()
print("[3/4] Config Classes...")
config = LlamaCppConfig(n_ctx=2048, n_threads=2)
print(f"  LlamaCppConfig: n_ctx={config.n_ctx}, n_threads={config.n_threads}")

gen_config = GenerationConfig(temperature=0.7, max_tokens=100)
print(f"  GenerationConfig: temp={gen_config.temperature}, max={gen_config.max_tokens}")

# 4. 列出可用模型
print()
print("[4/4] Available Models...")
models = list_available_models("d:/mhzyapp/hermes-desktop/models")
if models:
    for m in models:
        print(f"  - {m['name']} ({m['size_mb']:.1f} MB)")
else:
    print("  No GGUF models found in models/ directory")
    print("  Place a .gguf file to test")

print()
print("=== All Tests Passed ===")
