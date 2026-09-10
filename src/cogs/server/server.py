import discord

from discord import app_commands, Color
from discord.ui import Button, View
from discord.ext import commands, tasks
from discord.ext.commands import command, group, Context, Cog, has_permissions
from discord.ext.commands import hybrid_command as hybrid
from vortex import vortex
from config import BUTTONS
from typing import Optional, Union
from asyncpg import connection
from datetime import datetime, timezone
from config import DISCORD

# from .classes import ModlogsEmbed


class Server(Cog, description="Server Configuration commands."):
    def __init__(self, bot: vortex):
        self.bot = bot
        self.start_time = datetime.now(timezone.utc)
        self.server_config = None
        self.join_logs_table = None

    async def setup(self):
        async with self.bot.db.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS server_config (
                    guild_id BIGINT PRIMARY KEY,
                    prefix TEXT NOT NULL,
                    language TEXT NOT NULL,
                    modlog_channel_id BIGINT,
                    joinlog_channel_id BIGINT,
                    leave_channel_id BIGINT,
                    welcome_message TEXT,
                    leave_message TEXT
                )
            """
            )

    async def check_table(self):
        async with self.bot.db.acquire() as conn:
            result = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'server_config'
                )
            """
            )
            if not result:
                await self.setup()

    async def get_config(self, guild_id: int) -> Optional[dict]:
        async with self.bot.db.acquire() as conn:
            result = await conn.fetchrow(
                """
                SELECT * FROM server_config
                WHERE guild_id = $1
            """,
                guild_id,
            )
            return result

    async def update_config(self, guild_id: int, **kwargs):
        async with self.bot.db.acquire() as conn:
            await conn.execute(
                """
                UPDATE server_config
                SET $set
                WHERE guild_id = $1
            """,
                **kwargs,
                guild_id=guild_id,
            )

    async def delete_config(self, guild_id: int):
        async with self.bot.db.acquire() as conn:
            await conn.execute(
                """
                DELETE FROM server_config
                WHERE guild_id = $1
            """,
                guild_id,
            )

    async def add_config(self, guild_id: int, **kwargs):
        async with self.bot.db.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO server_config (guild_id, $set)
                VALUES ($1, $2)
            """,
                guild_id,
                **kwargs,
            )

    async def prefix(self, guild_id: int, prefix: str):
        async with self.bot.db.acquire() as conn:
            await conn.execute(
                """
                UPDATE server_config
                SET prefix = $2
                WHERE guild_id = $1
            """,
                guild_id,
                prefix,
            )

    @group(name="gate", invoke_without_command=True)
    async def gate(self, ctx: Context):
        if ctx.invoked_subcommand is None:
            return

    @gate.command(name="set", aliases=["logs"])
    @has_permissions(administrator=True)
    async def set_join_logs(self, ctx: Context, channel: discord.TextChannel = None):
        """Sets the join log channel for the current server."""
        server_id = int(ctx.guild.id)

        async with self.bot.db.acquire() as conn:
            current_channel_id = await conn.fetchval(
                """
                SELECT channel_id FROM join_logs WHERE server_id = $1
            """,
                server_id,
            )

            await conn.execute(
                """
                INSERT INTO join_logs (server_id, channel_id) VALUES ($1, $2)
                ON CONFLICT (server_id) DO UPDATE SET channel_id = $2
            """,
                server_id,
                channel.id if channel else None,
            )

        if channel is None:
            embed = discord.Embed(
                title="Join Logs",
                description=(
                    f"Current gate is set to {ctx.guild.get_channel(current_channel_id).mention}."
                    if current_channel_id
                    else "No gate set."
                ),
                color=Color(0xFFFFFF),
            )
            await ctx.send(embed=embed)
            return

        if channel.id == current_channel_id:
            embed = discord.Embed(
                title="Join Logs",
                description=f"Gate is already set to {channel.mention}.",
                color=Color(0xFFFFFF),
            )
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(
            title="Join Logs",
            description=f"Join logs have been set to {channel.mention} for this server.",
            color=Color(0xFFFFFF),
        )
        await ctx.send(embed=embed)

    @gate.command(
        name="join",
        aliases=[
            "joinmsg",
            "welcmsg",
            "joinmessage",
            "welcomemessage",
            "welcmessage",
            "welc",
        ],
    )
    @has_permissions(administrator=True)
    async def set_join_message(self, ctx: Context, *, message: str):
        """Sets a custom welcome message for the server and displays it in an embed."""
        server_id = int(ctx.guild.id)

        async with self.bot.db.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO join_logs (server_id, welcome_message) VALUES ($1, $2)
                ON CONFLICT (server_id) DO UPDATE SET welcome_message = $2
            """,
                server_id,
                message,
            )

        message = message.replace("{user.mention}", "")
        embed = discord.Embed(
            title="Welcome Message Set", description=message, color=Color(0xFFFFFF)
        )
        await ctx.send("Custom welcome message has been set.", embed=embed)

    @gate.command(name="leave", aliases=["leavemsg"])
    @has_permissions(administrator=True)
    async def set_leave_message(self, ctx: Context, *, message: str):
        """Sets a custom leave message for the server and displays it in an embed."""
        server_id = int(ctx.guild.id)

        async with self.bot.db.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO join_logs (server_id, leave_message) VALUES ($1, $2)
                ON CONFLICT (server_id) DO UPDATE SET leave_message = $2
            """,
                server_id,
                message,
            )

        message = message.replace("{user.mention}", "")
        embed = discord.Embed(
            title="Leave Message Set", description=message, color=Color(0xFFFFFF)
        )
        await ctx.send("Custom leave message has been set.", embed=embed)

    @gate.command(name="reset", aliases=["resetlogs"])
    @has_permissions(administrator=True)
    async def reset_join_logs(self, ctx: Context):
        """Resets the join logs for the current server."""
        server_id = int(ctx.guild.id)

        async with self.bot.db.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO join_logs (server_id, channel_id, welcome_message, leave_message)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (server_id) DO UPDATE SET channel_id = $2, welcome_message = $3, leave_message = $4
            """,
                server_id,
                None,
                None,
                None,
            )

        embed = discord.Embed(
            title="Join Logs Reset",
            description="Join logs have been reset for this server.",
            color=Color(0xFFFFFF),
        )
        await ctx.send(embed=embed)

    @gate.command(name="view", aliases=["viewlogs"])
    @has_permissions(administrator=True)
    async def view_join_logs(self, ctx: Context):
        """Views the current join logs for the current server."""
        server_id = int(ctx.guild.id)

        async with self.bot.db.acquire() as conn:
            channel_id = await conn.fetchval(
                """
                SELECT channel_id FROM join_logs WHERE server_id = $1
            """,
                server_id,
            )
            welcome_message = await conn.fetchval(
                """
                SELECT welcome_message FROM join_logs WHERE server_id = $1
            """,
                server_id,
            )
            leave_message = await conn.fetchval(
                """
                SELECT leave_message FROM join_logs WHERE server_id = $1
            """,
                server_id,
            )

        channel = ctx.guild.get_channel(channel_id) if channel_id else None
        embed = discord.Embed(
            title="Join Logs",
            description=f"Current gate is set to {channel.mention}.",
            color=Color(0xFFFFFF),
        )
        if welcome_message:
            embed.add_field(name="Welcome Message", value=welcome_message)
        if leave_message:
            embed.add_field(name="Leave Message", value=leave_message)
        await ctx.send(embed=embed)

    @command(name="autorole")
    @has_permissions(manage_guild=True)
    async def autorole(self, ctx, role: discord.Role):
        query = "SELECT role_id FROM autorole_humans WHERE guild_id = $1"
        async with self.bot.db.acquire() as conn:
            result = await conn.fetchrow(query, ctx.guild.id)
            if result and result["role_id"] == role.id:
                await conn.execute(
                    "DELETE FROM autorole_humans WHERE guild_id = $1", ctx.guild.id
                )
                embed = discord.Embed(
                    description=f"Autorole for new human members has been removed for this server.",
                    color=0xFFFFFF,
                )
                await ctx.send(embed=embed)
            else:
                await conn.execute(
                    """
                    INSERT INTO autorole_humans (guild_id, role_id) 
                    VALUES ($1, $2)
                    ON CONFLICT (guild_id) 
                    DO UPDATE SET role_id = EXCLUDED.role_id
                """,
                    ctx.guild.id,
                    role.id,
                )
                embed = discord.Embed(
                    description=f"Autorole for new human members set to {role.mention} for this server.",
                    color=0xFFFFFF,
                )
                await ctx.send(embed=embed)

    @command(name="autorolebots")
    @has_permissions(manage_guild=True)
    async def autorole_bots(self, ctx: Context, role: discord.Role):
        """Automatically assigns a role to new bot members for this server."""
        query = "SELECT role_id FROM autorole_bots WHERE guild_id = $1"
        async with self.bot.db.acquire() as conn:
            result = await conn.fetchrow(query, ctx.guild.id)
            if result and result["role_id"] == role.id:
                await conn.execute(
                    "DELETE FROM autorole_bots WHERE guild_id = $1", ctx.guild.id
                )
                embed = discord.Embed(
                    description=f"Autorole for new bot members has been removed for this server.",
                    color=0xFFFFFF,
                )
                await ctx.send(embed=embed)
            else:
                await conn.execute(
                    """
                    INSERT INTO autorole_bots (guild_id, role_id) 
                    VALUES ($1, $2)
                    ON CONFLICT (guild_id) 
                    DO UPDATE SET role_id = EXCLUDED.role_id
                """,
                    ctx.guild.id,
                    role.id,
                )
                embed = discord.Embed(
                    description=f"Autorole for new bot members set to {role.mention} for this server.",
                    color=0xFFFFFF,
                )
                await ctx.send(embed=embed)

    @Cog.listener()
    async def on_member_join(self, member):
        server_id = int(member.guild.id)

        async with self.bot.db.acquire() as conn:
            join_logs_result = await conn.fetchrow(
                """
                SELECT channel_id, welcome_message
                FROM join_logs
                WHERE server_id = $1
            """,
                server_id,
            )

            autorole_result = await conn.fetchrow(
                """
                SELECT role_id FROM autorole_humans WHERE guild_id = $1
            """,
                server_id,
            )

        if join_logs_result:
            channel_id, welcome_message = join_logs_result
            channel = self.bot.get_channel(channel_id)
            if channel:
                await channel.send(
                    (
                        welcome_message.replace("{user.mention}", f"{member.mention}")
                        if "{user.mention}" in welcome_message
                        else welcome_message
                    )
                )

        if autorole_result:
            role_id = autorole_result["role_id"]
            role = member.guild.get_role(role_id)
            if role:
                await member.add_roles(role)

    @Cog.listener()
    async def on_member_remove(self, member):
        server_id = int(member.guild.id)

        async with self.bot.db.acquire() as conn:
            result = await conn.fetchrow(
                """
                SELECT channel_id, leave_message
                FROM join_logs
                WHERE server_id = $1
            """,
                server_id,
            )

        if result is None:
            return

        channel_id, leave_message = result

        channel = self.bot.get_channel(channel_id)
        if channel:
            async for entry in member.guild.audit_logs(
                limit=1, action=discord.AuditLogAction.ban
            ):
                if entry.target.id == member.id:
                    await channel.send(
                        f"{member.mention} was banned by {entry.user.mention}"
                    )
                    return
            await channel.send(
                (
                    leave_message.replace("{user.mention}", f"{member.mention}")
                    if "{user.mention}" in leave_message
                    else leave_message
                )
            )
