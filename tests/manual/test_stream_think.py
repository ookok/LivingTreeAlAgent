import asyncio
import sys
sys.path.insert(0, ".")
from livingtree.dna.stream_think import get_stream_think

async def main():
    st = get_stream_think()
    stages = await st.simulate_thinking(0.5)
    for s in stages:
        print(f"  [{s['stage']:15s}] {s['message'][:60]}")

asyncio.run(main())
