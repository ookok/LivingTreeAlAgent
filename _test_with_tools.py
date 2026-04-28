import sys; sys.path.insert(0, "d:/mhzyapp/LivingTreeAlAgent")
from core.ollama_client import OllamaClient, ChatMessage
from core.config import AppConfig

config = AppConfig()
config.ollama.default_model = "qwen2.5:1.5b"
client = OllamaClient(config.ollama)

# 模拟 send_message 的消息构建
system_prompt = """你是生命之树AI（LivingTreeAl），一款由 AI 驱动的桌面助手，运行在本地 Windows 环境中。
请基于以上信息，提供详细、准确的回答。

## 用户问题
我是祖国的花朵"""

msgs = [
    ChatMessage(role="system", content=system_prompt),
    ChatMessage(role="user", content="我是祖国的花朵"),
]

# 测试 tools schema
tools = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取文件内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "文件路径"}
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "搜索知识库",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "top_k": {"type": "integer"}
                },
                "required": ["query"]
            }
        }
    }
]

print("=== 带 tools + reasoning_callback ===")
chunks = list(client.chat(msgs, model="qwen2.5:1.5b", num_ctx=8192, 
    tools=tools,
    reasoning_callback=lambda x: None))
text = "".join(c.__dict__.get("delta", "") or "" for c in chunks if c.__dict__.get("delta"))
has_tools = any(c.__dict__.get("tool_calls") for c in chunks)
print(f"响应: {text[:100]}")
print(f"工具调用: {has_tools}")
print(f"chunks: {len(chunks)}")

print("\n=== 不带 tools ===")
chunks2 = list(client.chat(msgs, model="qwen2.5:1.5b", num_ctx=8192,
    reasoning_callback=lambda x: None))
text2 = "".join(c.__dict__.get("delta", "") or "" for c in chunks2 if c.__dict__.get("delta"))
print(f"响应: {text2[:100]}")
print(f"chunks: {len(chunks2)}")
