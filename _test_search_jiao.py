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
print(f"backend: {agent._current_backend}")

print("\n发送搜索请求: 搜索 吉奥环朋")
print("=" * 60)

# send_message 返回生成器，需要迭代获取
response_chunks = []
for chunk in agent.send_message("搜索 吉奥环朋"):
    chunk_str = str(chunk)
    response_chunks.append(chunk_str)
    print(chunk_str, end="", flush=True)
    
print("\n" + "=" * 60)
print(f"总 chunk 数: {len(response_chunks)}")
