import aiohttp, asyncio, json

async def main():
    async with aiohttp.ClientSession() as s:
        r = await s.get('https://models.dev/api.json', timeout=aiohttp.ClientTimeout(total=15))
        data = await r.json()
        total = len(data)
        free_models = [x for x in data if isinstance(x, dict) and x.get('cost', {}).get('is_free')]
        open_models = [x for x in data if isinstance(x, dict) and x.get('open_weights')]
        print(f"models.dev total: {total}")
        print(f"  is_free=True: {len(free_models)}")
        print(f"  open_weights=True: {len(open_models)}")
        print()
        print("Top 20 free models:")
        for x in free_models[:20]:
            cost = x.get('cost', {})
            print(f"  {x.get('id', '?')[:55]}")
            print(f"    provider: {x.get('provider_name', '?')} | input: {cost.get('input', 0)} | output: {cost.get('output', 0)}")

asyncio.run(main())
