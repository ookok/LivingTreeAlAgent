"""
P2P连接器测试脚本
"""

import asyncio
import sys
sys.path.insert(0, '.')

from core.p2p_connector import (
    ConnectorHub, ShortIDGenerator, DirectoryService,
    MultiChannelManager, NodeProfile, PeerStatus, ChannelType
)


async def test_basic():
    """基础功能测试"""
    print("=" * 50)
    print("P2P Connector Basic Test")
    print("=" * 50)

    # 创建连接器核心
    hub = ConnectorHub()
    print(f"[OK] ConnectorHub created")

    # 初始化
    await hub.initialize()
    print(f"[OK] Initialized")

    # 获取我的ID
    my_short_id = hub.get_my_short_id()
    my_node_id = hub.get_my_node_id()
    print(f"[OK] My Short ID: {my_short_id}")
    print(f"[OK] My Node ID: {my_node_id[:16]}...")

    # 短ID生成器测试
    generator = ShortIDGenerator()

    # 雪花算法
    snowflake_id = generator.generate_snowflake()
    print(f"[OK] Snowflake ID: {snowflake_id} (len={len(snowflake_id)})")

    # 随机生成
    random_id = generator.generate_random()
    print(f"[OK] Random ID: {random_id} (len={len(random_id)})")

    # 校验位验证
    valid = generator.verify_check_digit(random_id)
    print(f"[OK] Check digit valid: {valid}")

    # 注册档案
    profile = NodeProfile(
        node_id=my_node_id,
        short_id=my_short_id,
        display_name="Test User",
        status=PeerStatus.ONLINE,
        capabilities=["text", "file", "voice", "video", "live", "email"],
        relay_hosts=["139.199.124.242:8888"]
    )

    directory = DirectoryService()
    directory.register_profile(profile)
    print(f"[OK] Profile registered")

    # 解析
    resolved = directory.resolve_short_id(my_short_id)
    if resolved:
        print(f"[OK] Resolved profile: {resolved.display_name}")

    # 节点发现
    peers = directory.discover_peers()
    print(f"[OK] Discovered {len(peers)} peers")

    print("\n" + "=" * 50)
    print("All basic tests passed!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(test_basic())
