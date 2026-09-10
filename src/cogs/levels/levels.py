import discord
import asyncpg

from discord.ext.commands import hybrid_command as hybrid, is_owner
from discord.ext import commands
from .listeners import Listeners
from .image import create_rank_card


class Levels(commands.Cog, description="View commands in Levels."):
    def __init__(self, bot):
        self.bot = bot
        self.db: asyncpg.Pool = bot.db
        self.listeners = Listeners(bot)
        self.bot.loop.create_task(self.initialize_database())

    async def initialize_database(self):
        async with self.db.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS levels (
                    user_id BIGINT,
                    guild_id BIGINT,
                    xp BIGINT DEFAULT 0,
                    level BIGINT DEFAULT 1,
                    PRIMARY KEY (user_id, guild_id)
                )
            """
            )

    @hybrid(name="rank", aliases=["level", "lvl"])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def rank(self, ctx: commands.Context, user: discord.User = None):
        try:
            if user is None:
                user = ctx.author
            async with self.db.acquire() as conn:
                record = await conn.fetchrow(
                    "SELECT xp, level FROM levels WHERE user_id = $1 AND guild_id = $2",
                    user.id,
                    ctx.guild.id,
                )
                if not record:
                    await ctx.send(f"{user.mention} go chat to get some XP!")
                    return

                current_xp = record["xp"]
                current_level = record["level"]

                xp_required = 5 * (current_level**2) + 50 * current_level + 100
                if current_xp >= xp_required:
                    current_xp = xp_required

            async def _get_rank():
                async with self.db.acquire() as conn:
                    record = await conn.fetchrow(
                        "SELECT COUNT(*) FROM levels WHERE guild_id = $1 AND xp > $2",
                        ctx.guild.id,
                        current_xp,
                    )

                    return record["count"] + 1

            level_card = await create_rank_card(
                avatar=user.avatar.url,
                level=current_level,
                rank=await _get_rank(),
                username=user.display_name,
                current_xp=current_xp,
                max_xp=xp_required,
            )

            await ctx.send(file=discord.File(fp=level_card, filename="level_card.png"))
        except Exception as e:
            await ctx.send(f"An unexpected error occurred: {str(e)}")

    @hybrid(name="leaderboard", aliases=["lb", "top"])
    async def leaderboard(self, ctx, page: int = 1):
        async with self.db.acquire() as conn:
            pages = await conn.fetchval(
                "SELECT COUNT(*) FROM levels WHERE guild_id = $1", ctx.guild.id
            )
            pages = pages // 10 + (1 if pages % 10 else 0)

            if page > pages:
                return await ctx.send(f"Page out of bounds, max page is {pages}")

            records = await conn.fetch(
                "SELECT user_id, xp, level FROM levels WHERE guild_id = $1 ORDER BY xp DESC LIMIT 10 OFFSET $2",
                ctx.guild.id,
                page * 10 - 10,
            )
            if not records:
                return await ctx.send("No users found.")
            leaderboard = [record for record in records]
            leaderboard_display = []
            rank = 0
            for record in leaderboard:
                rank += 1
                leaderboard_display.append(
                    f"**{rank}.** <@{record['user_id']}> - Level: {record['level']} - XP: {record['xp']}"
                )
            embed = discord.Embed(
                title=f"Leaderboard - {ctx.guild.name}",
                description="\n".join(leaderboard_display),
            ).set_footer(text=f"Page {page}/{pages}")
            await ctx.send(embed=embed)

    @hybrid(
        name="addxp",
        aliases=["givexp"],
        description="Add XP to a user in the server.",
        hidden=True,
    )
    @is_owner()
    async def add_xp(self, ctx: commands.Context, user: discord.User, xp: int):
        """
        Add XP to a user in the server.
        """
        if xp < 0:
            return await ctx.send("XP cannot be negative.")

        async with self.db.acquire() as conn:
            await conn.execute(
                "INSERT INTO levels (user_id, guild_id, xp) VALUES ($1, $2, $3) "
                "ON CONFLICT (user_id, guild_id) DO UPDATE SET xp = levels.xp + $3",
                user.id,
                ctx.guild.id,
                xp,
            )
            await ctx.send(f"Added {xp} XP to {user.mention}.")

    @hybrid(
        name="setlevel",
        aliases=["setlvl"],
        description="Set a user's level in the server.",
        hidden=True,
    )
    @is_owner()
    async def set_level(self, ctx: commands.Context, user: discord.User, level: int):
        """
        Set a user's level in the server.
        """
        if level < 1:
            if user.id == 570020287735660547:
                await ctx.send("Did we not learn from the past?")
            else:
                await ctx.send("I will not make the same mistake as tech did.")
            return

        async with self.db.acquire() as conn:
            await conn.execute(
                "INSERT INTO levels (user_id, guild_id, level) VALUES ($1, $2, $3) "
                "ON CONFLICT (user_id, guild_id) DO UPDATE SET level = $3",
                user.id,
                ctx.guild.id,
                level,
            )
            await ctx.send(f"Set {user.mention}'s level to {level}.")

    @hybrid(
        name="reset",
        aliases=["resetxp"],
        description="Reset a user's XP in the server.",
        hidden=True,
    )
    @is_owner()
    async def reset_xp(self, ctx: commands.Context, user: discord.User):
        """
        Reset a user's XP in the server.
        """
        async with self.db.acquire() as conn:
            await conn.execute(
                "DELETE FROM levels WHERE user_id = $1 AND guild_id = $2",
                user.id,
                ctx.guild.id,
            )
            await ctx.send(f"Reset {user.mention}'s XP.")

    @hybrid(
        name="resetall",
        aliases=["resetallxp"],
        description="Reset all users' XP in the server.",
        hidden=True,
    )
    @is_owner()
    async def reset_all_xp(self, ctx: commands.Context):
        """
        Reset all users' XP in the server.
        """
        async with self.db.acquire() as conn:
            await conn.execute("DELETE FROM levels WHERE guild_id = $1", ctx.guild.id)
            await ctx.send("Reset all users' XP in this server.")

    @hybrid(
        name="disable",
        aliases=["disablexp"],
        description="Disable XP gain in the server.",
        hidden=True,
    )
    @is_owner()
    async def disable_xp(self, ctx: commands.Context):
        """
        Disable XP gain in the server.
        """
        async with self.db.acquire() as conn:
            await conn.execute(
                "UPDATE guilds SET xp_enabled = FALSE WHERE guild_id = $1", ctx.guild.id
            )
            await ctx.send("XP gain has been disabled in this server.")
