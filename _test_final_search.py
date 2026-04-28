import sys; sys.path.insert(0, "d:/mhzyapp/LivingTreeAlAgent")
from core.config import AppConfig
config = AppConfig()

from core.agent import HermesAgent
import time

print("创建 HermesAgent...")
agent = HermesAgent(config=config, backend="ollama")
time.sleep(2)

# 先存入知识库
kb_info = [
    {
        "content": "吉奥环朋科技（江苏）有限公司成立于2021年6月4日，注册资本5000万人民币，法定代表人代新凯，位于南京市雨花台区。主营业务包括新兴能源技术研发、锂电池回收利用等。",
        "source": "web_search",
        "query": "吉奥环朋",
        "url": "https://baike.baidu.com/item/吉奥环朋科技"
    },
    {
        "content": "吉奥环朋科技（扬州）有限公司成立于2021年7月15日，注册资本12250万人民币，位于扬州市仪征市，属于枫创环保旗下企业。主营危废品处理和新能源动力锂电池回收（年回收3万吨）。",
        "source": "web_search",
        "query": "吉奥环朋",
        "url": "https://aiqicha.baidu.com/company_detail_94239359999962"
    },
    {
        "content": "吉奥环朋科技（江苏）有限公司拥有多项知识产权，包括1个企业品牌项目和14个专利信息。",
        "source": "web_search",
        "query": "吉奥环朋",
        "url": "https://www.tianyancha.com/company/5043196780/zhishi"
    },
    {
        "content": "注意：'吉奥环鹏' 是错别字，正确名称应为 '吉奥环朋'。",
        "source": "typo_fix",
        "query": "吉奥环鹏",
        "url": ""
    }
]

print("\n存入知识库...")
for info in kb_info:
    agent.knowledge_base.add_knowledge(
        content=info["content"],
        source=info["source"],
        query=info["query"],
        url=info["url"]
    )

print("\n" + "=" * 60)
print("测试: 搜索 吉奥环鹏")
print("=" * 60)

# 保存完整结果
full_text = []
for chunk in agent.send_message("搜索 吉奥环鹏"):
    chunk_str = str(chunk)
    full_text.append(chunk_str)
    
result_text = "\n".join(full_text)

with open("_search_result_final.txt", "w", encoding="utf-8") as f:
    f.write(result_text)

print("\n" + "=" * 60)
print(f"总 chunk 数: {len(full_text)}")
print(f"总字符数: {len(result_text)}")
print("结果已保存到 _search_result_final.txt")
