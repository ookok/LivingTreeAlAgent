import sys; sys.path.insert(0, "d:/mhzyapp/LivingTreeAlAgent")
from core.config import AppConfig
config = AppConfig()
config.ollama.default_model = "qwen2.5:1.5b"

from core.agent import HermesAgent
import time

print("创建 HermesAgent...")
agent = HermesAgent(config=config, backend="ollama")
time.sleep(3)

print("\n调用 send_message('我是祖国的花朵')...")
chunks = list(agent.send_message("我是祖国的花朵"))
print(f"chunks count: {len(chunks)}")
for c in chunks:
    d = c.__dict__
    if d.get("error"):
        print(f"  ERROR: {d['error']}")
    if d.get("delta"):
        print(f"  delta: {d['delta']}")
    if d.get("done"):
        print(f"  done: {d['done']}")
