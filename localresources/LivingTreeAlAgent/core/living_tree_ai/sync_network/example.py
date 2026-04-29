"""
Sync Network Example - 三层同步体系使用示例
==========================================

Author: LivingTreeAI Community
"""

import asyncio
import time


async def example_event_sync():
    """
    事件同步示例

    演示Gossip协议的广播和订阅
    """
    from sync_network import GossipSync, EventType

    print("=== 事件同步示例 ===\n")

    # 创建Gossip同步实例
    gossip = GossipSync("node_a")

    # 添加一些节点
    gossip.add_peer("node_b")
    gossip.add_peer("node_c")
    gossip.add_peer("node_d")

    # 注册事件处理器
    async def handle_cache_index(event):
        print(f"  收到缓存索引事件: {event.data}")

    gossip.register_handler(EventType.CACHE_INDEX_NEW, handle_cache_index)

    # 订阅事件（node_b订阅缓存事件）
    gossip.subscriptions.subscribe("node_b", [EventType.CACHE_INDEX_NEW])

    # 广播事件
    print("广播缓存索引事件...")
    event = await gossip.broadcast_event(
        EventType.CACHE_INDEX_NEW,
        {"query": "测试查询", "result_hash": "abc123"},
    )
    print(f"  事件ID: {event.id}")
    print(f"  事件类型: {event.type.value}")
    print(f"  TTL: {event.ttl}")

    # 获取统计
    stats = gossip.get_stats()
    print(f"\n统计: {stats}")

    return gossip


async def example_incremental_sync():
    """
    增量同步示例

    演示Merkle树和版本向量的差异同步
    """
    from sync_network import IncrementalSync, DataType

    print("\n=== 增量同步示例 ===\n")

    # 创建两个节点
    node1 = IncrementalSync("node_1")
    node2 = IncrementalSync("node_2")

    # 节点1写入一些数据
    print("节点1写入数据...")
    node1.put(DataType.CACHE_INDEX, "key1", "value1")
    node1.put(DataType.CACHE_INDEX, "key2", "value2")
    node1.put(DataType.CACHE_INDEX, "key3", "value3")
    node1.put(DataType.SPECIALTY_INFO, "specialty1", "法律专长")

    # 节点2写入不同数据
    print("节点2写入数据...")
    node2.put(DataType.CACHE_INDEX, "key4", "value4")
    node2.put(DataType.CACHE_INDEX, "key5", "value5")
    node2.put(DataType.CREDIT_RECORD, "credit1", "100贡献点")

    # 模拟版本向量交换
    print("\n版本向量比较...")

    # 简化模拟：直接获取版本向量
    v1 = node1.version_vector.to_dict()
    v2 = node2.version_vector.to_dict()

    print(f"  节点1版本: {v1}")
    print(f"  节点2版本: {v2}")

    # 获取数据摘要
    print("\n数据摘要...")
    for dt in [DataType.CACHE_INDEX, DataType.SPECIALTY_INFO, DataType.CREDIT_RECORD]:
        digest = node1.generate_digest(dt)
        print(f"  {dt.value}: items={digest.item_count}, hash={digest.root_hash[:16]}...")

    return node1, node2


async def example_full_sync():
    """
    全量同步示例

    演示快照生成和分片下载
    """
    from sync_network import FullSync, DataType

    print("\n=== 全量同步示例 ===\n")

    # 创建全量同步实例
    sync = FullSync("node_source")

    # 创建快照
    print("创建数据快照...")

    # 模拟获取数据
    async def mock_get_data(types):
        return {
            "cache_index": {f"key_{i}": f"value_{i}" for i in range(100)},
            "specialty_info": {"legal": "法律专长", "tech": "技术专长"},
        }

    sync._get_data = mock_get_data

    snapshot = await sync.create_snapshot(["cache_index", "specialty_info"])

    print(f"  快照ID: {snapshot.snapshot_id}")
    print(f"  分片数: {snapshot.total_shards}")
    print(f"  总大小: {snapshot.total_size} bytes")
    print(f"  根哈希: {snapshot.root_hash[:32]}...")

    # 显示分片信息
    print(f"\n分片信息 ({len(snapshot.shards)} 个分片):")
    for shard in snapshot.shards[:3]:
        print(f"  分片{shard.index}: size={shard.size}, hash={shard.hash[:16]}...")

    return sync, snapshot


async def example_consistency():
    """
    一致性示例

    演示冲突解决策略
    """
    from sync_network import ConsistencyModel, ConsistencyLevel, ConflictResolver

    print("\n=== 一致性保证示例 ===\n")

    # 创建一致性模型
    consistency = ConsistencyModel("node_a")

    # 测试冲突解决
    resolver = consistency.conflict_resolver

    # 模拟多个版本
    versions = [
        {"value": "value_a", "timestamp": 1000, "node_id": "node_1"},
        {"value": "value_b", "timestamp": 1002, "node_id": "node_2"},
        {"value": "value_a", "timestamp": 1001, "node_id": "node_3"},
    ]

    print("冲突解决测试...")
    print(f"  输入版本数: {len(versions)}")

    # 最新时间戳策略
    resolver.set_policy("latest-wins")
    result = resolver.resolve(versions)
    print(f"  latest-wins: {result['value']} (来自 {result['node_id']})")

    # 声誉策略
    consistency._get_reputation = lambda n: 1.0 if n == "node_1" else 0.8
    resolver.set_policy("reputation-based")
    result = resolver.resolve(versions)
    print(f"  reputation-based: {result['value']} (来自 {result['node_id']})")

    # 多数策略
    resolver.set_policy("majority-wins")
    result = resolver.resolve(versions)
    print(f"  majority-wins: {result['value']}")

    return consistency


async def example_sync_manager():
    """
    同步管理器示例

    演示完整的三层同步流程
    """
    from sync_network import SyncManager, SyncConfig, EventType

    print("\n=== 同步管理器示例 ===\n")

    # 创建同步管理器
    config = SyncConfig()
    manager = SyncManager("node_master", config)

    # 添加同步伙伴
    manager.add_peer("peer_1")
    manager.add_peer("peer_2")
    manager.add_peer("peer_3")

    print(f"已添加 {len(manager.partners)} 个同步伙伴")

    # 选择同步伙伴
    partners = manager.select_sync_partners()
    print(f"选中的同步伙伴: {partners}")

    # 获取统计
    stats = manager.get_stats()
    print(f"\n初始统计: {stats['manager']}")

    # 模拟事件广播
    print("\n模拟事件广播...")
    await manager.broadcast_cache_index({"query": "测试", "results": []})

    # 模拟增量同步数据写入
    manager.incremental.put(DataType.CACHE_INDEX, "test_key", "test_value")

    return manager


async def example_full_workflow():
    """
    完整工作流示例

    模拟三层同步的完整流程
    """
    from sync_network import (
        SyncManager,
        SyncConfig,
        EventType,
        DataType,
    )

    print("\n" + "=" * 50)
    print("三层同步体系 - 完整工作流示例")
    print("=" * 50)

    # 创建两个节点
    node_a = SyncManager("node_a", SyncConfig())
    node_b = SyncManager("node_b", SyncConfig())

    # 建立连接
    node_a.add_peer("node_b")
    node_b.add_peer("node_a")

    print("\n【步骤1】事件同步 - 节点状态广播")
    await node_a.broadcast_node_status({
        "status": "online",
        "version": 1,
    })
    print("  → 节点A广播上线状态")

    print("\n【步骤2】增量同步 - 缓存索引同步")
    # 写入测试数据
    node_a.incremental.put(DataType.CACHE_INDEX, "query_1", {"results": ["a", "b"]})
    node_a.incremental.put(DataType.CACHE_INDEX, "query_2", {"results": ["c", "d"]})

    print(f"  节点A缓存: {node_a.incremental.get_all(DataType.CACHE_INDEX)}")
    print(f"  节点B缓存: {node_b.incremental.get_all(DataType.CACHE_INDEX)}")

    # 模拟增量同步（实际需要网络传输）
    # 这里演示数据结构
    digest_a = node_a.incremental.generate_digest(DataType.CACHE_INDEX)
    print(f"\n  节点A缓存摘要: items={digest_a.item_count}")

    print("\n【步骤3】全量同步 - 新节点加入")
    # 创建快照
    async def mock_get_data(types):
        return {"cache_index": {"new": "data"}}

    node_a.full_sync._get_data = mock_get_data
    snapshot = await node_a.full_sync.create_snapshot(["cache_index"])
    print(f"  生成快照: {snapshot.total_shards} 个分片, {snapshot.total_size} bytes")

    print("\n【步骤4】一致性保证 - 冲突解决")
    versions = [
        {"value": "v1", "timestamp": 100, "node_id": "node_a"},
        {"value": "v2", "timestamp": 101, "node_id": "node_b"},
    ]
    resolved = node_a.consistency.resolve_conflict(versions)
    print(f"  冲突解决: 采用 {resolved['value']} (timestamp={resolved['timestamp']})")

    print("\n【步骤5】同步统计")
    stats_a = node_a.get_stats()
    print(f"  事件广播: {stats_a['manager']['event_broadcasts']}")
    print(f"  增量同步: {stats_a['manager']['incremental_syncs']}")
    print(f"  全量同步: {stats_a['manager']['full_syncs']}")


async def main():
    """运行所有示例"""
    print("=" * 60)
    print("三层同步体系示例")
    print("=" * 60)

    await example_event_sync()
    await asyncio.sleep(0.2)

    await example_incremental_sync()
    await asyncio.sleep(0.2)

    await example_full_sync()
    await asyncio.sleep(0.2)

    await example_consistency()
    await asyncio.sleep(0.2)

    await example_sync_manager()
    await asyncio.sleep(0.2)

    await example_full_workflow()

    print("\n" + "=" * 60)
    print("示例完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())