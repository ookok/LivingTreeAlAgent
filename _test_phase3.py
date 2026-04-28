"""Phase 3 集成测试快速验证"""
import sys
sys.path.insert(0, '.')

from client.src.business.tools.register_all_tools import register_all_tools
register_all_tools()

from client.src.business.base_agents.base_agent import BaseToolAgent
agent = BaseToolAgent(enabled_toolsets=['core', 'geospatial'])

tools = agent.discover_tools('距离计算', max_results=5)
print(f'Discover: {[t.get("name") for t in tools]}')

r = agent.execute_tool('distance_tool', method='haversine',
                       from_lat=31.2304, from_lon=121.4737,
                       to_lat=39.9042, to_lon=116.4074)
print(f'Execute: name={r.name}, success={r.success}, data={r.data}')

# HermesAgent 测试
from client.src.business.agent import HermesAgent
from client.src.business.config import AppConfig
config = AppConfig()
hermes = HermesAgent(config=config)
print(f'HermesAgent._tool_agent: {hasattr(hermes, "_tool_agent")}')
