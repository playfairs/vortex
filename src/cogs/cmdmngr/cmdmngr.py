import asyncpg

from discord.ext import commands
from discord.ext.commands import Cog, Context, group, has_permissions

from vortex import vortex
from config import DISCORD
from managers.classes import Colors, Emojis


class CommandManager(Cog, description="View commands in Command Manager."):
    def __init__(self, bot: vortex):
        self.bot = bot
        self.pool = None

    async def command_tables(self):
        """Create the command tables if they don't exist."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS disabled_commands (
                guild_id BIGINT NOT NULL,
                command_name TEXT NOT NULL,
                PRIMARY KEY (guild_id, command_name)
                )
            """
            )

    @group(
        name="command",
        description="Base command for command management.",
        invoke_without_command=True,
    )
    @has_permissions(administrator=True)
    async def command(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @command.command(name="disable", description="Disables a command for the guild.")
    @has_permissions(administrator=True)
    async def disable_command(self, ctx, *, command_name: str):
        command_name = command_name.lower()
        guild_id = ctx.guild.id
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO disabled_commands (guild_id, command_name)
                VALUES ($1, $2) ON CONFLICT DO NOTHING
            """,
                guild_id,
                command_name,
            )

        await ctx.send(
            f"{Emojis.check} Disabled command {command_name} for {ctx.guild.name}",
            ephemeral=True,
        )

    @command.command(name="enable", description="Enables a command for the guild.")
    @has_permissions(administrator=True)
    async def enable_command(self, ctx, *, command_name: str):
        command_name = command_name.lower()
        guild_id = ctx.guild.id
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                DELETE FROM disabled_commands
                WHERE guild_id = $1 AND command_name = $2
            """,
                guild_id,
                command_name,
            )

        await ctx.send(
            f"{Emojis.check} Enabled command {command_name} for {ctx.guild.name}",
            ephemeral=True,
        )
