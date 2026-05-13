"""Real-world conversation test — full pipeline with shared context."""
import asyncio
from livingtree.treellm.core import TreeLLM
from livingtree.treellm.fluid_collective import get_fluid_collective


async def test_conversation():
    llm = TreeLLM.from_config()

    if not llm._providers:
        print("SKIP: No providers configured.")
        return

    fc = get_fluid_collective()
    print(f"Bootstrapped: {list(llm._providers.keys())}")
    print(f"Memory traces: {len(fc._traces)}")
    print()

    queries = [
        ("Q1", "国庆去哪玩？", True),
        ("Q2", "南京有什么好玩的？", False),
        ("Q3", "预算2000元左右，两个人能玩几天？", True),
    ]

    for label, query, deep_probe in queries:
        print(f"--- {label}: {query} ---")

        result = await llm.route_layered(
            query=query, task_type="chat",
            deep_probe=deep_probe, aggregate=False,
        )

        provider = result.get("provider", "NONE")
        layers = result.get("layers_used", 0)
        scores = result.get("scores", {})
        dp = result.get("deep_probe", {})
        ms = result.get("stigmergy", False)

        res = result.get("result")
        text = getattr(res, "text", "") or "" if res else ""
        tokens = getattr(res, "tokens", 0) if res else 0

        print(f"  {provider} | L{layers} | {tokens}t | stigmergy={ms}")
        if dp:
            s = dp.get("strategies", [])
            print(f"  DeepProbe: d={dp.get('probe_depth')} {s[:3]}")
        print(f"  Self-assess: {scores.get('self_assessment', 0):.2f}")
        if text:
            print(f"  {text[:150]}...")
        else:
            print(f"  EMPTY")
        print(f"  Memory: {len(fc._traces)} traces")
        print()

    from livingtree.treellm.joint_evolution import get_joint_evolution
    health = get_joint_evolution().joint_health()
    print(f"JointEvolution: score={health.score:.3f} ({health.total_trajectories} trajectories)")


if __name__ == "__main__":
    asyncio.run(test_conversation())
