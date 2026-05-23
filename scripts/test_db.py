import asyncio
import sys

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from db.base import engine

async def test():
    async with engine.begin() as conn:
        await conn.run_sync(lambda _: None)
    print("DB connected successfully")

asyncio.run(test())