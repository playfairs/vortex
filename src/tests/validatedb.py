import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

print(os.getenv("DATABASE_URL"))
print(os.getenv("POSTGRES_USER"))
print(os.getenv("POSTGRES_DB"))
print(os.getenv("POSTGRES_HOST"))
print(os.getenv("POSTGRES_PORT"))


async def main():
    conn = await asyncpg.connect("postgresql://playfair@localhost/vortex")
    try:
        row = await conn.fetchrow("SELECT 1")
        assert row[0] == 1
    finally:
        await conn.close()
        print("Database connection was successful and now closed.")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
