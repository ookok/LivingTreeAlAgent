"""
Complete patch for global_model_router.py:
1. Rename methods: _call_llmcore() -> _call_ltai(), _call_llmcore_stream() -> _call_ltai_stream()
2. Update all call sites
3. Update comments
"""
import re

with open('global_model_router.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update comments
content = content.replace('LLMCORE 模型配置', 'LTAI 细胞模型配置')
content = content.replace('LLMCORE 后端调用（nanoGPT 细胞）', 'LTAI 后端调用（LTAI 细胞）')
content = content.replace('调用 LLMCORE 模型（同步）', '调用 LTAI 模型（同步）')
content = content.replace('通过 LLMCoreAdapter 加载本地 nanoGPT checkpoint 做推理。', 
                    '通过 LTAIAdapter 加载本地 LTAI 细胞 checkpoint 做推理。')
content = content.replace('调用 LLMCORE 模型（流式）', '调用 LTAI 模型（流式）')
content = content.replace('通过 LLMCoreAdapter.chat_stream() 流式 yield 文本片段。',
                    '通过 LTAIAdapter.chat_stream() 流式 yield 文本片段。')

# 2. Rename methods
content = content.replace('async def _call_llmcore(', 'async def _call_ltai(')
content = content.replace('async def _call_llmcore_stream(', 'async def _call_ltai_stream(')

# 3. Update call sites
content = content.replace('self._call_llmcore(', 'self._call_ltai(')
content = content.replace('self._call_llmcore_stream(', 'self._call_ltai_stream(')

# 4. Update any remaining LLMCORE references in comments
content = content.replace('LLMCORE', 'LTAI')

print("[OK] Method renaming and comment updates done!")
print("  - _call_llmcore() -> _call_ltai()")
print("  - _call_llmcore_stream() -> _call_ltai_stream()")
print("  - Comments updated")

with open('global_model_router.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("\n[DONE] global_model_router.py fully patched!")
