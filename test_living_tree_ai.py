"""
LivingTreeAI - Test Script
=======================

Run all core module tests

Author: Hermes Desktop Team
"""

import asyncio
import sys
import os

# Add project path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def test_node():
    """Test node module"""
    print("\n" + "="*50)
    print("Test 1: LivingTreeNode")
    print("="*50)

    from core.living_tree_ai.node import LivingTreeNode, NodeType

    # Create node
    node = LivingTreeNode(
        node_type=NodeType.UNIVERSAL,
        specialization="test"
    )

    # Start node
    await node.start()

    # Get status
    status = node.get_status()
    print(f"\nNode Status:")
    print(f"  Node ID: {status['node_id']}")
    print(f"  Status: {status['status']}")
    print(f"  Type: {status['node_type']}")
    print(f"  Specialization: {status['specialization']}")

    # Submit task
    task_id = node.submit_task(
        task_type="inference",
        input_data={"prompt": "test"},
        priority=1
    )
    print(f"\nSubmitted task: {task_id}")

    # Wait for task execution
    await asyncio.sleep(2)

    # Stop node
    await node.stop()

    print("\n[PASS] LivingTreeNode Test")
    return True


async def test_network():
    """Test network module"""
    print("\n" + "="*50)
    print("Test 2: P2PNetwork")
    print("="*50)

    from core.living_tree_ai.network import P2PNetwork, NetworkConfig

    # Create network
    config = NetworkConfig()
    network = P2PNetwork("test_node_001", config)

    # Register handler
    async def handle_task(msg):
        return {"type": "response", "result": "ok"}

    network.register_handler(network.Protocol.TASK_REQUEST if hasattr(network, 'Protocol') else None, handle_task)

    # Start network
    await network.start()
    print(f"\nNetwork started")

    # Get stats
    stats = network.get_network_stats()
    print(f"Network stats: {stats}")

    # Stop network
    await network.stop()

    print("\n[PASS] P2PNetwork Test")
    return True


async def test_knowledge():
    """Test knowledge module"""
    print("\n" + "="*50)
    print("Test 3: KnowledgeBase")
    print("="*50)

    from core.living_tree_ai.knowledge import (
        KnowledgeBase, KnowledgeShare, KnowledgeEntry,
        KnowledgeType, KnowledgeLicense, KnowledgeQuery
    )

    # Create knowledge base
    kb = KnowledgeBase("test_node")

    # Add knowledge
    entry = KnowledgeEntry(
        knowledge_id="test_001",
        knowledge_type=KnowledgeType.FACT,
        title="Water Boiling Point",
        content="At standard atmospheric pressure, water boils at 100C",
        source_node="test_node",
        license=KnowledgeLicense.OPEN,
        domain="science",
        tags=["physics", "chemistry"],
        confidence=0.99,
    )
    kb.add(entry)
    print(f"\nAdded knowledge: {entry.knowledge_id}")

    # Query knowledge
    results = kb.query(KnowledgeQuery(domain="science"))
    print(f"Query results: {len(results)} items")

    # Stats
    stats = kb.get_stats()
    print(f"Stats: Total {stats.total_knowledge} items")

    # Knowledge sharing
    ks = KnowledgeShare(kb, "test_node")
    summary = ks.get_share_summary()
    print(f"Share summary: {summary}")

    print("\n[PASS] KnowledgeBase Test")
    return True


async def test_incentive():
    """Test incentive module"""
    print("\n" + "="*50)
    print("Test 4: IncentiveSystem")
    print("="*50)

    from core.living_tree_ai.incentive import IncentiveSystem, ContributionType

    # Create incentive system
    incentive = IncentiveSystem("coordinator_node")

    # Record contributions
    for i in range(3):
        incentive.record_contribution(
            node_id="node_001",
            contribution_type=ContributionType.TASK_COMPLETION,
            value=1.0,
            task_id=f"task_{i}",
        )

    incentive.record_contribution(
        node_id="node_001",
        contribution_type=ContributionType.ONLINE_TIME,
        value=5.0,  # 5 hours
    )

    incentive.record_contribution(
        node_id="node_001",
        contribution_type=ContributionType.KNOWLEDGE_SHARE,
        value=2.0,
    )

    print("\nRecorded contributions")

    # Get reputation
    rep = incentive.get_reputation("node_001")
    print(f"\nNode node_001 Reputation:")
    print(f"  Level: Lv.{rep.level} {rep.title}")
    print(f"  Points: {rep.total_points:.1f}")
    print(f"  Score: {rep.reputation_score:.1f}/100")
    print(f"  Tasks: {rep.tasks_completed}")
    print(f"  Badges: {', '.join(rep.badges) if rep.badges else 'None'}")

    # Leaderboard
    leaderboard = incentive.get_leaderboard()
    print(f"\nLeaderboard: {len(leaderboard)} nodes")

    # Reputation report
    report = incentive.get_reputation_report("node_001")
    print(report)

    print("\n[PASS] IncentiveSystem Test")
    return True


async def test_federation():
    """Test federated learning module"""
    print("\n" + "="*50)
    print("Test 5: FederatedLearning")
    print("="*50)

    from core.living_tree_ai.federation import FederatedLearning, FLConfig

    # Create config
    config = FLConfig(
        local_epochs=2,
        aggregation_strategy="fedavg",
        min_nodes=2,
        max_nodes=3,
    )

    # Mock network
    class MockNetwork:
        def __init__(self):
            self.peers = [{"node_id": f"node_{i}"} for i in range(3)]

        def get_peers(self):
            return self.peers

        async def broadcast(self, msg):
            print(f"  [Broadcast] {msg['type']}")

        def get_network_stats(self):
            return {"peer_count": 3}

    network = MockNetwork()

    # Create FL instance
    fl = FederatedLearning(config, "coordinator", network)

    # Callback
    def on_round_complete(round_obj):
        print(f"\n>>> Round {round_obj.round_number} complete!")
        print(f"    Participants: {len(round_obj.selected_nodes)}")
        print(f"    Avg Loss: {round_obj.avg_loss:.4f}")

    fl.on_round_complete = on_round_complete

    # Run 2 rounds
    print("\nStarting federated learning (2 rounds)...")
    await fl.start_fl(num_rounds=2)

    # Stats
    stats = fl.get_stats()
    print(f"\nFL Stats:")
    print(f"  Total rounds: {stats['total_rounds']}")
    print(f"  Current phase: {stats['current_phase']}")

    print("\n[PASS] FederatedLearning Test")
    return True


async def test_protocol():
    """Test protocol module"""
    print("\n" + "="*50)
    print("Test 6: Protocol")
    print("="*50)

    from core.living_tree_ai.protocol import ProtocolHandler, MessageType

    # Create handler
    handler = ProtocolHandler("test_node")

    # Register handler
    async def handle_task(msg):
        print(f"  Received task message: {msg.sender_id}")
        return None

    handler.register_handler(MessageType.TASK_REQUEST, handle_task)

    # Create message
    msg_data = handler.create_message(MessageType.TASK_REQUEST)
    print(f"\nCreated message: {len(msg_data)} bytes")

    # Handle message
    await handler.handle_message(msg_data)

    # Stats
    stats = handler.get_stats()
    print(f"\nHandler stats: {stats}")

    print("\n[PASS] Protocol Test")
    return True


async def run_all_tests():
    """Run all tests"""
    print("\n" + "="*60)
    print("[TEST] LivingTreeAI Core Modules Test")
    print("="*60)

    tests = [
        ("LivingTreeNode", test_node),
        ("P2PNetwork", test_network),
        ("KnowledgeBase", test_knowledge),
        ("IncentiveSystem", test_incentive),
        ("FederatedLearning", test_federation),
        ("Protocol", test_protocol),
    ]

    results = []

    for name, test_func in tests:
        try:
            await test_func()
            results.append((name, True, None))
        except Exception as e:
            results.append((name, False, str(e)))
            print(f"\n[FAIL] {name} Test: {e}")

    # Summary
    print("\n" + "="*60)
    print("[SUMMARY] Test Results")
    print("="*60)

    passed = sum(1 for _, success, _ in results if success)
    total = len(results)

    for name, success, error in results:
        status = "[PASS]" if success else f"[FAIL]: {error}"
        print(f"  {name}: {status}")

    print(f"\nTotal: {passed}/{total} tests passed")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
