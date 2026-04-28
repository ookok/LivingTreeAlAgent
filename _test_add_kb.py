import sys; sys.path.insert(0, "d:/mhzyapp/LivingTreeAlAgent")
from core.config import AppConfig
config = AppConfig()

from core.agent import HermesAgent
import time

print("创建 HermesAgent...")
agent = HermesAgent(config=config, backend="ollama")
time.sleep(2)

# 手动存入"吉奥环朋"的企业信息
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
        "content": "注意：'吉奥环鹏' 是错别字，正确名称应为 '吉奥环朋'。两者在字形上相似（鹏/朋），容易混淆。",
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

print("\n知识库统计:", agent.knowledge_base.get_stats())

# 测试搜索
print("\n测试搜索: 搜索 吉奥环鹏")
results = agent.knowledge_base.search("吉奥环鹏", top_k=3)
print(f"找到 {len(results)} 条结果")
for i, r in enumerate(results):
    print(f"{i+1}. {r['content'][:80]}...")

print("\n测试搜索: 搜索 吉奥环朋")
results = agent.knowledge_base.search("吉奥环朋", top_k=3)
print(f"找到 {len(results)} 条结果")
for i, r in enumerate(results):
    print(f"{i+1}. {r['content'][:80]}...")
