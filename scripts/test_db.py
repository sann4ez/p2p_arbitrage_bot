import asyncio
import sys

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from db.base import engine


async def test():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(lambda _: None)
        print("DB connected successfully")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(test())
