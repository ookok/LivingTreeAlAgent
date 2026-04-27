"""
搜索引擎健康检测与自动切换
============================

功能：
1. 自动检测搜索引擎可用性
2. 根据响应时间和成功率排序
3. 故障时自动切换备用引擎
4. 定期健康检查
"""

import asyncio
import time
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import httpx


class EngineStatus(Enum):
    """引擎状态"""
    HEALTHY = "healthy"      # 健康
    DEGRADED = "degraded"   # 降级（可用但慢）
    UNHEALTHY = "unhealthy"  # 不健康
    UNKNOWN = "unknown"      # 未知


@dataclass
class EngineHealth:
    """引擎健康状态"""
    name: str
    status: EngineStatus = EngineStatus.UNKNOWN
    avg_response_time: float = 0.0  # 平均响应时间（秒）
    success_count: int = 0
    fail_count: int = 0
    last_check: float = 0  # 上次检查时间
    last_error: str = ""
    
    @property
    def success_rate(self) -> float:
        total = self.success_count + self.fail_count
        return self.success_count / total if total > 0 else 0.0


class SearchEngineMonitor:
    """
    搜索引擎健康监控
    
    自动检测并维护可用搜索引擎列表
    """
    
        # 内置搜索引擎配置
    ENGINES = {
        # 国内搜索引擎
        "baidu": {
            "name": "百度",
            "url": "https://www.baidu.com/s",
            "params": {"wd": "{query}", "rn": "3"},
            "timeout": 10,
            "expected_keywords": ["百度", "search"],
        },
        "sogou": {
            "name": "搜狗",
            "url": "https://www.sogou.com/web",
            "params": {"query": "{query}"},
            "timeout": 10,
            "expected_keywords": ["搜狗", "sogou"],
        },
        "bing": {
            "name": "必应",
            "url": "https://cn.bing.com/search",
            "params": {"q": "{query}"},
            "timeout": 10,
            "expected_keywords": ["Bing", "微软"],
        },
        "360": {
            "name": "360搜索",
            "url": "https://www.so.com/s",
            "params": {"q": "{query}"},
            "timeout": 10,
            "expected_keywords": ["360", "so.com"],
        },
        
        # 国外搜索引擎
        "duckduckgo": {
            "name": "DuckDuckGo",
            "url": "https://api.duckduckgo.com/",
            "params": {"q": "{query}", "format": "json"},
            "timeout": 8,
            "expected_keywords": ["DuckDuckGo", "RelatedTopics"],
        },
        "serper": {
            "name": "Serper (Google)",
            "url": "https://google.serper.dev/search",
            "params": {"q": "{query}"},
            "timeout": 10,
            "requires_api_key": True,
            "expected_keywords": ["organic"],
        },
        
        # 备用方案
        "wikipedia": {
            "name": "Wikipedia",
            "url": "https://en.wikipedia.org/w/api.php",
            "params": {"action": "opensearch", "search": "{query}"},
            "timeout": 8,
            "expected_keywords": ["Wikipedia"],
        },
    }
    
    def __init__(self, check_interval: int = 300):  # 5分钟检查一次
        """
        初始化监控器
        
        Args:
            check_interval: 健康检查间隔（秒）
        """
        self.check_interval = check_interval
        self.engines_health: Dict[str, EngineHealth] = {}
        
        # 初始化健康状态
        for name in self.ENGINES:
            self.engines_health[name] = EngineHealth(name=name)
        
        # 加载保存的状态
        self._load_state()
        
        # 测试查询
        self.test_query = "test search"
    
    def _load_state(self):
        """加载保存的状态"""
        state_file = Path.home() / ".hermes-desktop" / "engine_health.json"
        if state_file.exists():
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for name, health_data in data.items():
                        if name in self.engines_health:
                            h = self.engines_health[name]
                            h.status = EngineStatus(health_data.get("status", "unknown"))
                            h.avg_response_time = health_data.get("avg_response_time", 0)
                            h.success_count = health_data.get("success_count", 0)
                            h.fail_count = health_data.get("fail_count", 0)
            except Exception as e:
                print(f"[EngineMonitor] 加载状态失败: {e}")
    
    def _save_state(self):
        """保存状态"""
        state_file = Path.home() / ".hermes-desktop" / "engine_health.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        
        data = {}
        for name, health in self.engines_health.items():
            data[name] = {
                "status": health.status.value,
                "avg_response_time": health.avg_response_time,
                "success_count": health.success_count,
                "fail_count": health.fail_count,
            }
        
        try:
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[EngineMonitor] 保存状态失败: {e}")
    
    async def check_engine(
        self, 
        name: str, 
        force: bool = False
    ) -> EngineHealth:
        """
        检查单个引擎健康状态
        
        Args:
            name: 引擎名称
            force: 强制检查（忽略时间间隔）
            
        Returns:
            EngineHealth: 健康状态
        """
        if name not in self.ENGINES:
            return self.engines_health.get(name, EngineHealth(name=name, status=EngineStatus.UNKNOWN))
        
        engine_config = self.ENGINES[name]
        health = self.engines_health[name]
        
        # 检查是否需要更新（避免频繁检查）
        if not force and time.time() - health.last_check < self.check_interval:
            return health
        
        # 跳过需要 API Key 的引擎
        if engine_config.get("requires_api_key"):
            health.status = EngineStatus.UNKNOWN
            health.last_check = time.time()
            return health
        
        # 执行检查
        start_time = time.time()
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            # 构建 URL
            url = engine_config["url"]
            params = {
                k: v.replace("{query}", self.test_query) 
                for k, v in engine_config.get("params", {}).items()
            }
            
            async with httpx.AsyncClient(timeout=engine_config.get("timeout", 10)) as client:
                response = await client.get(url, params=params, headers=headers)
                
                response_time = time.time() - start_time
                
                if response.status_code == 200:
                    content = response.text
                    
                    # 检查响应内容
                    if any(kw.lower() in content.lower() for kw in engine_config.get("expected_keywords", [])):
                        health.status = EngineStatus.HEALTHY
                        health.avg_response_time = (
                            health.avg_response_time * health.success_count + response_time
                        ) / (health.success_count + 1)
                        health.success_count += 1
                    else:
                        health.status = EngineStatus.DEGRADED
                        health.fail_count += 1
                else:
                    health.status = EngineStatus.UNHEALTHY
                    health.fail_count += 1
                    health.last_error = f"HTTP {response.status_code}"
                
        except asyncio.TimeoutError:
            health.status = EngineStatus.UNHEALTHY
            health.fail_count += 1
            health.last_error = "Timeout"
        except Exception as e:
            health.status = EngineStatus.UNHEALTHY
            health.fail_count += 1
            health.last_error = str(e)[:100]
        
        health.last_check = time.time()
        return health
    
    async def check_all_engines(self, force: bool = False) -> Dict[str, EngineHealth]:
        """
        检查所有引擎
        
        Args:
            force: 强制检查
            
        Returns:
            Dict[str, EngineHealth]: 所有引擎的健康状态
        """
        tasks = [
            self.check_engine(name, force=force)
            for name in self.ENGINES
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for name, result in zip(self.ENGINES.keys(), results):
            if isinstance(result, Exception):
                health = self.engines_health[name]
                health.status = EngineStatus.UNHEALTHY
                health.last_error = str(result)[:100]
        
        # 保存状态
        self._save_state()
        
        return self.engines_health
    
    def get_available_engines(
        self, 
        min_success_rate: float = 0.5,
        max_response_time: float = 30.0
    ) -> List[Tuple[str, EngineHealth]]:
        """
        获取可用引擎列表（按优先级排序）
        
        Args:
            min_success_rate: 最低成功率
            max_response_time: 最大响应时间（秒）
            
        Returns:
            List[Tuple[str, EngineHealth]]: 可用引擎列表（按优先级排序）
        """
        available = []
        
        for name, health in self.engines_health.items():
            if health.status == EngineStatus.UNKNOWN:
                continue
            
            if health.status != EngineStatus.UNHEALTHY:
                if health.success_rate >= min_success_rate:
                    if health.avg_response_time <= max_response_time or health.avg_response_time == 0:
                        available.append((name, health))
        
        # 按响应时间排序
        available.sort(key=lambda x: x[1].avg_response_time if x[1].avg_response_time > 0 else 999)
        
        return available
    
    def get_best_engine(self) -> Optional[str]:
        """获取最佳引擎"""
        available = self.get_available_engines()
        return available[0][0] if available else None
    
    def get_status_report(self) -> str:
        """生成状态报告"""
        lines = ["=== 搜索引擎健康状态 ===\n"]
        
        # 按状态分组
        by_status = {}
        for name, health in self.engines_health.items():
            if health.status not in by_status:
                by_status[health.status] = []
            by_status[health.status].append((name, health))
        
        # 输出
        for status in [EngineStatus.HEALTHY, EngineStatus.DEGRADED, EngineStatus.UNHEALTHY, EngineStatus.UNKNOWN]:
            if status in by_status:
                lines.append(f"\n【{status.value.upper()}】")
                for name, health in by_status[status]:
                    config = self.ENGINES.get(name, {})
                    display_name = config.get("name", name)
                    lines.append(f"  - {display_name} ({name})")
                    lines.append(f"    成功率: {health.success_rate:.1%}")
                    if health.avg_response_time > 0:
                        lines.append(f"    平均响应: {health.avg_response_time:.2f}s")
                    if health.last_error:
                        lines.append(f"    错误: {health.last_error[:50]}")
        
        # 可用引擎
        lines.append("\n【推荐引擎】")
        available = self.get_available_engines()
        if available:
            for name, health in available[:3]:
                config = self.ENGINES.get(name, {})
                lines.append(f"  [OK] {config.get('name', name)} ({name}) - {health.avg_response_time:.2f}s")
        else:
            lines.append("  [X] 无可用引擎")
        
        return "\n".join(lines)


async def quick_health_check():
    """快速健康检查（用于测试）"""
    monitor = SearchEngineMonitor(check_interval=0)  # 立即检查
    
    print("开始健康检查...")
    print("-" * 60)
    
    # 并行检查所有引擎
    await monitor.check_all_engines(force=True)
    
    # 输出报告
    print(monitor.get_status_report())
    
    return monitor


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--quick":
        asyncio.run(quick_health_check())
    else:
        print("使用: python search_engine_monitor.py --quick 进行快速健康检查")
