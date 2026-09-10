import discord
import aiohttp

from discord.ext import commands, tasks
from discord.ext.commands import command, has_permissions, Context, Cog
from discord.ext.commands import group
from discord.ext.commands import hybrid_command as hybrid
from discord import Member, app_commands

from vortex import vortex
from managers.classes import Emojis, Colors, Media, Assets


class Vanity(Cog, description="View commands in Vanity."):
    def __init__(self, bot: vortex):
        self.bot = bot
        self.db = self.bot.db

    async def cog_load(self):
        await self.create_tables()

    async def create_tables(self):
        await self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS vanity (
                guild_id BIGINT PRIMARY KEY, 
                vanity VARCHAR(32),
                pic_role_id BIGINT,
                log_channel_id BIGINT
            );
        """
        )
        await self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS user_activity (
                user_id BIGINT,
                guild_id BIGINT,
                has_vanity BOOLEAN,
                PRIMARY KEY (user_id, guild_id),
                FOREIGN KEY (guild_id) REFERENCES vanity(guild_id) ON DELETE CASCADE
            );
        """
        )
        await self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS role_assignments (
                user_id BIGINT,
                guild_id BIGINT,
                role_assigned BOOLEAN,
                PRIMARY KEY (user_id, guild_id),
                FOREIGN KEY (guild_id) REFERENCES vanity(guild_id) ON DELETE CASCADE
            );
        """
        )

    @group(name="vanity", invoke_without_command=True)
    @has_permissions(administrator=True)
    async def vanity(self, ctx: Context):
        """Group of commands to manage vanity settings."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @vanity.command(name="set")
    @has_permissions(administrator=True)
    async def set_vanity(self, ctx: Context, *, vanity: str):
        """Set the vanity keyword for the server."""
        guild_id = ctx.guild.id
        await self.db.execute(
            """
            INSERT INTO vanity (guild_id, vanity)
            VALUES ($1, $2)
            ON CONFLICT (guild_id) DO UPDATE SET vanity = $2;
        """,
            guild_id,
            vanity,
        )
        await ctx.send(f"Vanity keyword set to `{vanity}` for this server.")

    @vanity.command(name="role")
    @has_permissions(administrator=True)
    async def set_pic_role(self, ctx: Context, role: discord.Role):
        """Set the pic permissions role for the server."""
        guild_id = ctx.guild.id
        await self.db.execute(
            """
            INSERT INTO vanity (guild_id, pic_role_id)
            VALUES ($1, $2)
            ON CONFLICT (guild_id) DO UPDATE SET pic_role_id = $2;
        """,
            guild_id,
            role.id,
        )
        await ctx

    @vanity.command(name="logs")
    @has_permissions(administrator=True)
    async def set_log_channel(self, ctx: Context, channel: discord.TextChannel):
        """Set the log channel for vanity updates."""
        guild_id = ctx.guild.id
        await self.db.execute(
            """
            INSERT INTO vanity (guild_id, log_channel_id)
            VALUES ($1, $2)
            ON CONFLICT (guild_id) DO UPDATE SET log_channel_id = $2;
        """,
            guild_id,
            channel.id,
        )
        await ctx.send(f"Log channel set to `{channel.name}`.")

    @tasks.loop(seconds=2)
    async def check_vanity_statuses(self):
        """Check all members' custom statuses every 2 seconds."""
        async with self.db.acquire() as conn:
            result = await conn.fetch(
                "SELECT guild_id, vanity, pic_role_id, log_channel_id FROM vanity"
            )

        for guild_id, vanity, pic_role_id, log_channel_id in result:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue

            role = guild.get_role(pic_role_id)
            log_channel = guild.get_channel(log_channel_id)

            if not role or not log_channel:
                continue

            for member in guild.members:
                if member.bot:
                    continue

                has_vanity = any(
                    (
                        isinstance(activity, discord.CustomActivity)
                        and vanity in str(activity.name or "")
                    )
                    or (
                        hasattr(activity, "name")
                        and activity.name
                        and vanity in str(activity.name)
                    )
                    for activity in member.activities
                )

                if has_vanity and role not in member.roles:
                    try:
                        await member.add_roles(role)
                        embed = discord.Embed(
                            description=f"Gave pic perms to {member.mention}, user has `{vanity}` in status.",
                            color=discord.Color(0xFFFFFF),
                        )
                        await log_channel.send(embed=embed)
                    except Exception as e:
                        print(f"Error adding role for {member.name}: {e}")

                elif not has_vanity and role in member.roles:
                    try:
                        await member.remove_roles(role)
                        embed = discord.Embed(
                            description=f"Removed pic perms from {member.mention}, user no longer has `{vanity}` in status.",
                            color=discord.Color(0xFFFFFF),
                        )
                        await log_channel.send(embed=embed)
                    except Exception as e:
                        print(f"Error removing role for {member.name}: {e}")

    @Cog.listener()
    async def on_ready(self):
        """Start the vanity status checking loop when the bot is ready."""
        if not self.check_vanity_statuses.is_running():
            self.check_vanity_statuses.start()

    @Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listen for 'pic' messages and respond with vanity instructions."""
        if message.author.bot or message.content.startswith(
            tuple(self.bot.command_prefix)
        ):
            return

        if (
            "pic perms" in message.content.lower()
            or "give pic" in message.content.lower()
            or "perms" in message.content.lower()
        ):
            guild_id = message.guild.id

            async with self.db.acquire() as conn:
                result = await conn.fetchrow(
                    "SELECT vanity FROM vanity WHERE guild_id = $1", guild_id
                )

                if result is not None:
                    vanity = result.get("vanity", "/vanity")
                else:
                    vanity = "/vanity"

                await message.channel.send(
                    f"rep `{vanity}` 4 pic perms.", delete_after=5
                )

    @vanity.command(name="check")
    @has_permissions(administrator=True)
    async def check_all_members(self, ctx):
        """Manually check all members' statuses and update roles."""
        guild_id = ctx.guild.id

        result = await self.db.fetchrow(
            "SELECT * FROM vanity WHERE guild_id = $1", guild_id
        )

        # if not result:
        #     await ctx.send("Vanity not configured for this server.", delete_after=5)
        #     return

        settings = result
        vanity = settings.get("vanity", "/vanity")
        pic_role_id = settings.get("pic_role_id")
        log_channel_id = settings.get("log_channel_id")

        # if not pic_role_id or not log_channel_id:
        #     await ctx.send("Pic role or log channel not configured.", delete_after=5)
        #     return

        role = ctx.guild.get_role(pic_role_id)
        if not role:
            await ctx.send("Configured pic role not found.", delete_after=5)
            return

        log_channel = ctx.guild.get_channel(log_channel_id)
        if not log_channel:
            await ctx.send("Configured log channel not found.", delete_after=5)
            return

        count = 0
        async with ctx.typing():
            for member in ctx.guild.members:
                if member.bot:
                    continue

                has_vanity = any(
                    (
                        isinstance(activity, discord.CustomActivity)
                        and vanity in str(activity.name or "")
                    )
                    or (
                        hasattr(activity, "name")
                        and activity.name
                        and vanity in str(activity.name)
                    )
                    for activity in member.activities
                )

                if has_vanity and role not in member.roles:
                    await member.add_roles(role)
                    count += 1
                elif not has_vanity and role in member.roles:
                    await member.remove_roles(role)
                    count += 1

        await ctx.send(f"Updated roles for `{count}` members.")

    @vanity.command(name="reset")
    @has_permissions(administrator=True)
    async def reset(self, ctx):
        """Reset the vanity settings."""
        guild_id = ctx.guild.id
        await self.db.execute("DELETE FROM vanity WHERE guild_id = $1", guild_id)
        await self.db.execute("DELETE FROM user_activity WHERE guild_id = $1", guild_id)
        await self.db.execute(
            "DELETE FROM role_assignments WHERE guild_id = $1", guild_id
        )
        await ctx.send("Vanity settings reset.")
