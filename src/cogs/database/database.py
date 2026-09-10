import asyncpg
import discord
import os
from discord.ext import commands


class Database(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pool = None

    async def connect(self):
        """
        Establish a connection to the database.
        """
        self.pool = await asyncpg.create_pool(dsn=os.getenv("DATABASE_URL"))

    async def fetch_guild_config(self, guild_id: int):
        """
        Fetch guild configuration from the database.
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT * FROM guild_config WHERE guild_id = $1", guild_id
            )

    async def set_guild_config(self, guild_id: int, log_channel: int):
        """Sets log channel for a guild."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO guild_config (guild_id, log_channel) VALUES ($1, $2) ON CONFLICT (guild_id) DO UPDATE SET log_channel = $2",
                guild_id,
                log_channel,
            )

    async def close(self):
        """Closes the database connection."""
        if self.pool:
            await self.pool.close()


async def setup(bot):
    db = Database(bot)
    bot.add_cog(db)
    await db.connect()
