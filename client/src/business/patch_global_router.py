"""
Patch global_model_router.py to update LLMCORE -> LTAI
"""
import re

with open('global_model_router.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. ModelBackend enum: LLMCORE = "llmcore" -> LTAI = "ltai"
content = content.replace(
    'LLMCORE = "llmcore"   # 本地 nanoGPT 细胞模型',
    'LTAI = "ltai"   # LTAI (LivingTreeAi) 本地细胞模型'
)

# 2. Load config: llmcore_cfg -> ltai_cfg
content = content.replace('llmcore_cfg = load_model_config("llmcore")', 
                    'ltai_cfg = load_model_config("ltai")')
content = content.replace('cells = llmcore_cfg.get("cells", [])',
                    'cells = ltai_cfg.get("cells", [])')

# 3. model_id: llmcore_ -> ltai_
content = content.replace('"model_id": f"llmcore_{base_name}"',
                    '"model_id": f"ltai_{base_name}"')
content = content.replace('model_id = cell.get("model_id", f"llmcore_{cell_name}")',
                    'model_id = cell.get("model_id", f"ltai_{cell_name}")')

# 4. Backend: ModelBackend.LLMCORE -> ModelBackend.LTAI
content = content.replace('backend=ModelBackend.LLMCORE',
                    'backend=ModelBackend.LTAI')

# 5. Name: (LLMCORE) -> (LTAI)
content = content.replace('name=f"{cell_name} (LLMCORE)"',
                    'name=f"{cell_name} (LTAI)"')

# 6. Log: [加载] LLMCORE -> [加载] LTAI
content = content.replace('[加载] LLMCORE', '[加载] LTAI')

# 7. Condition: model.backend == ModelBackend.LLMCORE
content = content.replace('elif model.backend == ModelBackend.LLMCORE:',
                    'elif model.backend == ModelBackend.LTAI:')

# 8. Import: LLMCoreAdapter -> LTAIAdapter
content = content.replace(
    'from business.llmcore.adapter import LLMCoreAdapter',
    'from business.llmcore.adapter import LTAIAdapter'
)

# 9. Adapter instantiation: LLMCoreAdapter( -> LTAIAdapter(
content = content.replace('adapter = LLMCoreAdapter(',
                    'adapter = LTAIAdapter(')

# 10. Log: LLMCORE 调用异常 -> LTAI 调用异常
content = content.replace('LLMCORE 调用异常', 'LTAI 调用异常')
content = content.replace('LLMCORE 流式调用异常', 'LTAI 流式调用异常')

# 11. Docstring: LLMCORE 模型（同步/流式）-> LTAI 模型
content = content.replace('LLMCORE 模型（同步）', 'LTAI 模型（同步）')
content = content.replace('LLMCORE 模型（流式）', 'LTAI 模型（流式）')
content = content.replace('通过 LLMCoreAdapter', '通过 LTAIAdapter')
content = content.replace('LLMCoreAdapter.chat_stream()', 'LTAIAdapter.chat_stream()')

print("[OK] All replacements done!")
print("  - LLMCORE -> LTAI: ModelBackend enum")
print("  - llmcore_ -> ltai_: model_id prefix")
print("  - LLMCoreAdapter -> LTAIAdapter: adapter class")
print("  - Log messages updated")

with open('global_model_router.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("\n[DONE] global_model_router.py patched successfully!")
