import sys; sys.path.insert(0, "d:/mhzyapp/LivingTreeAlAgent")
from core.config import AppConfig
config = AppConfig()
config.ollama.default_model = "qwen2.5:1.5b"

from core.agent import HermesAgent
import time

print("创建 HermesAgent...")
agent = HermesAgent(config=config, backend="ollama")
time.sleep(3)

print(f"model: {agent.model}")
print(f"ollama: {agent.ollama}")
print(f"backend: {agent._current_backend}")

from core.ollama_client import ChatMessage
msgs = [ChatMessage(role="user", content="你好")]

print("调用 _llm_chat...")
chunks = list(agent._llm_chat(msgs))
print(f"chunks count: {len(chunks)}")
for c in chunks:
    d = c.__dict__
    if d.get("error"):
        print(f"  ERROR: {d['error']}")
    if d.get("delta"):
        print(f"  delta: {d['delta'][:80]}")
    if d.get("done"):
        print(f"  done: {d['done']}")
