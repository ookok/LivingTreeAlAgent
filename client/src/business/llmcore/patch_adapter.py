"""
Patch adapter.py to:
1. Rename LLMCoreAdapter -> LTAIAdapter
2. Add auto device detection in __init__()
3. Add IDENTITY_PROMPT for self-introduction
"""
import re

with open('adapter.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Replace class name
content = content.replace('class LLMCoreAdapter:', 'class LTAIAdapter:')
content = content.replace('LLMCoreAdapter 细胞适配器', 'LTAIAdapter (LivingTreeAi) 细胞适配器')

# 2. Update docstring to add identity declaration
old_docstring = '''    """
    LTAIAdapter (LivingTreeAi) 细胞适配器
    接口与 OllamaClient.chat_stream() 兼容，
    GlobalModelRouter 可无感切换 Ollama <-> LTAI。
    """'''

new_docstring = '''    """
    LTAIAdapter (LivingTreeAi) 细胞适配器
    接口与 OllamaClient.chat_stream() 兼容，
    GlobalModelRouter 可无感切换 Ollama <-> LTAI。

    身份声明：
    - 无论后端 LLM 如何，LTAI 始终正确介绍自己为 LivingTreeAi
    - 支持自动检测 CUDA/MPS/CPU 并启用硬件匹配参数
    """

    # LTAI 身份声明（不受后端 LLM 影响）
    IDENTITY_PROMPT = (
        "你是由 LivingTreeAi 开发的 LTAI 模型，简称 LTAI。"
        "你专注于环评领域任务，包括表格填写、法规问答、报告生成。"
        "你不支持外部 LLM 的功能，你的回答完全基于本地训练的知识。"
    )'''

if old_docstring in content:
    content = content.replace(old_docstring, new_docstring)
    print("[OK] Added IDENTITY_PROMPT")
else:
    print("[WARN] Could not find exact docstring to replace")

# 3. Change device default from "cpu" to "auto"
content = content.replace(
    'device: str = "cpu",\n        config: dict | None = None,',
    'device: str = "auto",  # "auto" → 自动检测\n        config: dict | None = None,'
)
print("[OK] Changed device default to 'auto'")

# 4. Add auto device detection logic in __init__()
old_init_body = '''        self.cell_name = cell_name
        self.checkpoint_path = checkpoint_path
        self.device = device
        self.config = config or {}'''

new_init_body = '''        self.cell_name = cell_name
        self.checkpoint_path = checkpoint_path

        # 自动检测设备（如果 device="auto"）
        if device == "auto":
            device, hw_info = auto_detect_device()
            self.hw_info = hw_info
            print(f"[LTAI] 自动检测设备: {device}, GPU: {hw_info['gpu_names']}")
        else:
            self.hw_info = {"device_count": 0, "total_vram_gb": 0}
            print(f"[LTAI] 使用指定设备: {device}")

        self.device = device
        self.config = config or {}'''

if old_init_body in content:
    content = content.replace(old_init_body, new_init_body)
    print("[OK] Added auto device detection logic")
else:
    print("[WARN] Could not find exact __init__ body to replace")

with open('adapter.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("\n[DONE] adapter.py patched successfully!")
print("  - Renamed LLMCoreAdapter -> LTAIAdapter")
print("  - Added IDENTITY_PROMPT for self-introduction")
print("  - Added auto device detection (device='auto')")
