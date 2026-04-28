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

# 保存完整结果到文件
full_text = []
for chunk in agent.send_message("搜索 吉奥环朋"):
    chunk_str = str(chunk)
    full_text.append(chunk_str)
    
result_text = "\n".join(full_text)

# 写入文件
with open("_search_result_jiao.txt", "w", encoding="utf-8") as f:
    f.write(result_text)

print("\n" + "=" * 60)
print(f"总 chunk 数: {len(full_text)}")
print(f"结果已保存到 _search_result_jiao.txt")
print(f"总字符数: {len(result_text)}")
