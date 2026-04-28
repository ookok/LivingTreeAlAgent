import sys; sys.path.insert(0, "d:/mhzyapp/LivingTreeAlAgent")
from core.config import AppConfig
config = AppConfig()
config.ollama.default_model = "qwen2.5:1.5b"

from core.agent import HermesAgent
from core.ollama_client import ChatMessage
import time

print("创建 HermesAgent...")
agent = HermesAgent(config=config, backend="ollama")
time.sleep(3)

# 绕过 KB 和 deep search，直接测试 _llm_chat
print("\n直接调用 _llm_chat (绕过 send_message):")
system_prompt = "你是生命之树AI（LivingTreeAl），一款由 AI 驱动的桌面助手。"
msgs = [
    ChatMessage(role="system", content=system_prompt),
    ChatMessage(role="user", content="我是祖国的花朵")
]
chunks = list(agent._llm_chat(msgs))
print(f"chunks: {len(chunks)}")
for c in chunks:
    d = c.__dict__
    if d.get("error"):
        print(f"  ERROR: {d['error']}")
    if d.get("delta"):
        print(f"  delta: {d['delta'][:100]}")
    if d.get("done"):
        print(f"  done: {d['done']}")

# 测试 send_message
print("\n\n调用 send_message('我是祖国的花朵'):")
chunks2 = list(agent.send_message("我是祖国的花朵"))
print(f"chunks: {len(chunks2)}")
for c in chunks2:
    d = c.__dict__
    if d.get("error"):
        print(f"  ERROR: {d['error']}")
    if d.get("delta"):
        print(f"  delta: {d['delta'][:100]}")
    if d.get("done"):
        print(f"  done: {d['done']}")
