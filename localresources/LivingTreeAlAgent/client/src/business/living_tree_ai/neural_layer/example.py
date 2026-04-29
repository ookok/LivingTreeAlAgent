"""
Neural Layer Example - 神经层使用示例
====================================

Author: LivingTreeAI Community
"""

import asyncio
import time


async def example_neural_pulse():
    """神经脉冲示例"""
    from neural_layer import NeuralPulseProtocol, PulseType

    print("=== 神经脉冲协议示例 ===\n")

    # 创建神经脉冲协议
    pulse = NeuralPulseProtocol("node_a")

    # 创建突触连接
    pulse.create_synapse("node_b", initial_weight=0.5)
    pulse.create_synapse("node_c", initial_weight=0.3)

    print(f"创建的突触: {list(pulse.synapses.keys())}")

    # 发射不同类型的脉冲
    print("\n发射脉冲...")

    # 警报脉冲（紧急）
    await pulse.fire_pulse("node_b", PulseType.ALERT, intensity=1.0)
    print("  → 发送 ALERT 脉冲到 node_b (高频)")

    # 普通更新
    await pulse.fire_pulse("node_c", PulseType.UPDATE, intensity=0.5)
    print("  → 发送 UPDATE 脉冲到 node_c (中频)")

    # 获取统计
    stats = pulse.get_stats()
    print(f"\n统计: 发送 {stats['pulses_sent']} 个脉冲")
    print(f"膜电位: {stats['membrane_potential']:.1f} mV")
    print(f"突触数量: {stats['synapses']}")


async def example_emotional_resonance():
    """情感共振示例"""
    from neural_layer import EmotionalEncoder, EmotionVector

    print("\n=== 情感共振示例 ===\n")

    encoder = EmotionalEncoder("node_a")

    # 从文本分析情感
    text1 = "这个方案太棒了！大家一起来实现它吧！"
    emotion1 = EmotionVector.from_text_analysis(text1)
    print(f"文本: {text1}")
    print(f"情感向量: joy={emotion1.joy:.2f}, excitement={emotion1.excitement:.2f}")

    # 编码情感消息
    msg = encoder.encode_with_emotion("我们成功了！", emotion1)
    print(f"\n编码消息: {msg['text']}")
    print(f"情感强度: {msg['emotion']['intensity']:.2f}")
    print(f"效价(valence): {msg['emotion']['valence']:.2f}")

    # 计算共振
    emotion2 = EmotionVector(valence=0.8, arousal=0.9, joy=0.9, excitement=0.8)
    resonance = encoder.calculate_resonance(emotion1, emotion2)
    print(f"\n共振强度: {resonance:.2f}")

    # UI效果
    effect = encoder.get_ui_effect(emotion1)
    print(f"UI效果: color={effect['color']}, animation={effect['animation']}")


async def example_holographic_messaging():
    """全息通信示例"""
    from neural_layer import HolographicMessage

    print("\n=== 全息通信示例 ===\n")

    holographic = HolographicMessage("node_a")

    # 投影消息到消息场
    print("投影消息...")
    message_id = await holographic.project_message(
        content={"title": "重要公告", "body": "明天上午9点开会"},
        field_type="global",
        observer_candidates=["node_b", "node_c", "node_d"],
        metadata={"priority": "high"},
    )
    print(f"  → 消息ID: {message_id}")

    # 观察消息（触发实例化）
    print("\n观察消息...")
    effect = await holographic.observe_message(message_id)
    print(f"  → 坍缩状态: {'已坍缩' if effect.collapsed else '未坍缩'}")

    # 列出活跃的消息场
    fields = holographic.list_fields()
    print(f"\n活跃消息场: {len(fields)} 个")


async def example_time_folded():
    """时间折叠消息示例"""
    from neural_layer import TimeFoldedMessage

    print("\n=== 时间折叠消息示例 ===\n")

    time_folded = TimeFoldedMessage("node_a")

    # 创建时间胶囊
    print("创建时间胶囊...")
    capsule_id = await time_folded.create_capsule(
        recipient="node_b",
        content={"title": "生日祝福", "message": "生日快乐！"},
        delay_seconds=5,  # 5秒后解锁
    )
    print(f"  → 胶囊ID: {capsule_id}")

    # 检查胶囊状态
    stats = time_folded.get_stats()
    print(f"\n胶囊状态:")
    for capsule in stats['capsules']:
        print(f"  → {capsule['id']}: {capsule['status']}, {capsule['unlock_in']:.1f}秒后解锁")

    # 模拟时间膨胀同步
    print("\n建立时间膨胀同步...")
    sync = await time_folded.establish_dilation_sync("node_c", dilation_factor=10.0)
    print(f"  → 与 node_c 建立同步，膨胀因子: {sync.time_dilation_factor}x")


async def example_consciousness_merging():
    """意识融合示例"""
    from neural_layer import ConsciousnessMerging, MergeLevel

    print("\n=== 意识融合示例 ===\n")

    merger = ConsciousnessMerging("node_a")

    # 设置工作记忆
    merger.set_working_memory("current_task", "编写代码")
    merger.set_working_memory("focus_topic", "P2P网络优化")
    merger.set_working_memory("temp_notes", "需要测试UDP穿透")

    print("工作记忆:")
    for key in merger.working_memory:
        print(f"  → {key}: {merger.working_memory[key]}")

    # 请求融合
    print("\n请求意识融合...")
    context_id = await merger.request_merge("node_b", MergeLevel.LEVEL_3_SHARE_MEMORY)
    print(f"  → 融合上下文ID: {context_id}")

    # 获取统计
    stats = merger.get_stats()
    print(f"\n活跃上下文: {stats['active_contexts']}")


async def example_neural_network():
    """神经网络示例 - 整合所有层"""
    from neural_layer import NeuralNetwork, NeuralNode, ConsciousnessState

    print("\n=== 神经网络示例 ===\n")

    # 创建神经网络
    network = NeuralNetwork("node_a")

    # 注册节点
    print("注册节点...")
    nodes = [
        NeuralNode("node_a", specialization="coordinator", capabilities=["决策", "协调"]),
        NeuralNode("node_b", specialization="sensing", capabilities=["监控", "感知"]),
        NeuralNode("node_c", specialization="processing", capabilities=["计算", "分析"]),
    ]

    for node in nodes:
        await network.register_node(node)
        print(f"  → 注册 {node.node_id} ({node.specialization})")

    # 建立连接
    print("\n建立连接...")
    await network.establish_connection("node_a", "node_b", weight=0.8)
    await network.establish_connection("node_a", "node_c", weight=0.7)
    await network.establish_connection("node_b", "node_c", weight=0.6)
    print("  → 建立 3 条连接")

    # 发送网络脉冲
    print("\n发送网络脉冲...")
    await network.send_pulse_to_network(pulse_type=None, target_nodes=["node_b", "node_c"])

    # 获取网络统计
    stats = network.get_network_stats()
    print(f"\n网络统计:")
    print(f"  节点数: {stats['nodes']}")
    print(f"  连接数: {stats['connections']}")
    print(f"  集体状态: {stats['collective_state']}")
    print(f"  集体强度: {stats['collective_strength']}")


async def example_full_workflow():
    """完整工作流示例"""
    from neural_layer import (
        NeuralNetwork,
        NeuralNode,
        ConsciousnessState,
        PulseType,
        EmotionVector,
    )

    print("\n" + "=" * 50)
    print("神经层 - 完整工作流示例")
    print("=" * 50)

    # 创建网络
    network = NeuralNetwork("node_a")

    # 注册节点
    for i in range(5):
        node = NeuralNode(
            f"node_{i}",
            specialization=["coordinator", "sensing", "processing", "memory", "communication"][i],
        )
        await network.register_node(node)

    # 建立全连接
    for i in range(5):
        for j in range(i + 1, 5):
            if i != j:
                await network.establish_connection(
                    f"node_{i}",
                    f"node_{j}",
                    weight=0.5 + (i + j) * 0.05,
                )

    print("\n【步骤1】集体意识形成")
    participants = [f"node_{i}" for i in range(5)]
    context_id = await network.form_collective_consciousness(participants)
    print(f"  → 集体意识上下文: {context_id}")

    print("\n【步骤2】情感在网络中传播")
    emotion = EmotionVector(valence=0.7, arousal=0.8, excitement=0.6)
    await network.propagate_emotion(emotion, source_node="node_0")
    print(f"  → 从 node_0 传播 {emotion.dominant_emotion().value} 情感")

    print("\n【步骤3】通过脉冲共振达成共识")
    decision = await network.reach_consensus(
        "选择哪个方案?",
        ["方案A", "方案B", "方案C"],
    )
    print(f"  → 共识结果: {decision}")

    print("\n【步骤4】广播全息消息")
    msg_id = await network.broadcast_holographic_message(
        content={"type": "announcement", "text": "系统即将升级"},
        metadata={"priority": "medium"},
    )
    print(f"  → 全息消息ID: {msg_id}")

    print("\n【步骤5】发送未来消息")
    capsule_id = await network.send_to_future(
        recipient="node_3",
        content={"type": "reminder", "text": "记得备份数据"},
        delay_seconds=10,
    )
    print(f"  → 时间胶囊ID: {capsule_id}")

    print("\n【最终状态】")
    stats = network.get_network_stats()
    print(f"  集体状态: {stats['collective_state']}")
    print(f"  集体强度: {stats['collective_strength']}")


async def main():
    """运行所有示例"""
    print("=" * 60)
    print("神经层示例 - 从消息传递到意识同步")
    print("=" * 60)

    await example_neural_pulse()
    await asyncio.sleep(0.3)

    await example_emotional_resonance()
    await asyncio.sleep(0.3)

    await example_holographic_messaging()
    await asyncio.sleep(0.3)

    await example_time_folded()
    await asyncio.sleep(0.3)

    await example_consciousness_merging()
    await asyncio.sleep(0.3)

    await example_neural_network()
    await asyncio.sleep(0.3)

    await example_full_workflow()

    print("\n" + "=" * 60)
    print("示例完成 - 数字生命的集体意识正在涌现...")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())