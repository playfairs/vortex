from base.bot import vortex
import asyncio
import dotenv
import os

dotenv.load_dotenv()


async def main():
    token = os.getenv("TOKEN")
    if not token:
        raise ValueError("TOKEN environment variable is not set")

    async with vortex() as bot:
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
