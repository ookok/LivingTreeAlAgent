import sys; sys.path.insert(0, "d:/mhzyapp/LivingTreeAlAgent")
from core.ollama_client import OllamaClient, ChatMessage
from core.config import AppConfig
import httpx

config = AppConfig()
config.ollama.default_model = "qwen2.5:1.5b"
client = OllamaClient(config.ollama)

# Test 1: 简单聊天（无 tools）
print("=== Test 1: 简单聊天 ===")
msgs = [ChatMessage(role="user", content="你好")]
chunks = list(client.chat(msgs, model="qwen2.5:1.5b", num_ctx=8192))
text1 = "".join(c.__dict__.get("delta", "") or "" for c in chunks if c.__dict__.get("delta"))
print(f"响应: {text1}")

# Test 2: 带 tools
print("\n=== Test 2: 带 tools ===")
msgs2 = [ChatMessage(role="user", content="5 + 3 等于多少")]
tools = [
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "简单的计算器",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "数学表达式"}
                },
                "required": ["expression"]
            }
        }
    }
]
chunks2 = list(client.chat(msgs2, model="qwen2.5:1.5b", num_ctx=8192, tools=tools))
text2 = "".join(c.__dict__.get("delta", "") or "" for c in chunks2 if c.__dict__.get("delta"))
print(f"响应: {text2}")
has_tool = any(c.__dict__.get("tool_calls") for c in chunks2)
print(f"工具调用: {has_tool}")

# Test 3: 带长系统消息
print("\n=== Test 3: 带长系统消息 ===")
system_long = "你是生命之树AI（LivingTreeAl），一款由 AI 驱动的桌面助手。你可以通过各种工具来帮助用户完成任务。"
msgs3 = [
    ChatMessage(role="system", content=system_long),
    ChatMessage(role="user", content="我是祖国的花朵")
]
chunks3 = list(client.chat(msgs3, model="qwen2.5:1.5b", num_ctx=8192))
text3 = "".join(c.__dict__.get("delta", "") or "" for c in chunks3 if c.__dict__.get("delta"))
print(f"响应: {text3}")
