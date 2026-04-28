"""测试搜索引擎健康检测"""
import asyncio
import sys
sys.path.insert(0, 'd:/mhzyapp/LivingTreeAlAgent')

from core.search_engine_monitor import SearchEngineMonitor

async def test():
    monitor = SearchEngineMonitor(check_interval=0)
    print('开始健康检查...')
    print('-' * 60)
    await monitor.check_all_engines(force=True)
    print(monitor.get_status_report())

if __name__ == "__main__":
    asyncio.run(test())
