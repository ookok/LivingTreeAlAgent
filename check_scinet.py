import asyncio, aiohttp
async def test():
    async with aiohttp.ClientSession() as s:
        try:
            r = await s.get('http://127.0.0.1:7890/status', timeout=aiohttp.ClientTimeout(total=5))
            t = await r.text()
            print('scinet running:', r.status, t[:200])
        except Exception as e:
            print('scinet NOT running:', e)
asyncio.run(test())
