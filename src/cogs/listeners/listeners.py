import discord
import asyncpg
from discord.ext import commands
from discord.ext.commands import Cog, Context, command
from discord import Message
import aiohttp
import os
from datetime import datetime, timezone, timedelta
from vortex import vortex
from managers.classes import Media, Servers

from config import WHOAMI
import json


class Listeners(Cog, description="View commands in Listeners."):
    def __init__(self, bot: vortex):
        self.bot = bot
        self.blacklisted_guilds = set()
        self.last_message_author = None
        self.consecutive_messages = 0
        self.owner_id = 1426711359059394662
        self.bot_id = 1284037026672279635
        self.last_help_message_id = None

    async def cog_load(self):
        """Initialize the cog and create necessary tables."""
        await self.create_tables()

    async def create_tables(self):
        """Create necessary tables if they don't exist."""
        async with self.bot.db.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tag_replies (
                    user_id BIGINT PRIMARY KEY,
                    message_id BIGINT,
                    message TEXT
                )
            """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tag_info_sent (
                    user_id BIGINT PRIMARY KEY,
                    guild_id BIGINT,
                    sent_at TIMESTAMP WITH TIME ZONE
                )
            """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS command_usage (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    guild_id BIGINT NOT NULL,
                    command_name TEXT NOT NULL,
                    timestamp TIMESTAMP WITH TIME ZONE DEFAULT (now() AT TIME ZONE 'utc'),
                    UNIQUE(user_id, guild_id, command_name, timestamp)
                )
            """
            )
            print("CREATE TABLE")

    async def check_user(self, user_id: int, guild_id: int) -> bool:
        """Check if the user has already received the tag info message"""
        async with self.bot.db.acquire() as conn:
            result = await conn.fetchrow(
                """
                SELECT 1 FROM tag_info_sent
                WHERE user_id = $1 AND guild_id = $2
            """,
                user_id,
                guild_id,
            )
            return bool(result)

    async def log_user(self, user_id: int, guild_id: int):
        """Log that we've sent the tag info message to this user"""
        async with self.bot.db.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO tag_info_sent (user_id, guild_id, sent_at)
                VALUES ($1, $2, NOW())
            """,
                user_id,
                guild_id,
            )

    @Cog.listener("on_guild_join")
    async def join_logger(self, guild):
        """
        Event triggered when the bot joins a new server (guild).
        """
        bot = self.bot

        blacklisted_guild = await self.bot.db.fetchval(
            "SELECT 1 FROM blacklisted_guilds WHERE guild_id = $1",
            guild.id,
        )
        if blacklisted_guild:
            embed = discord.Embed(
                title="Blacklisted Guild",
                description=f"Your guild `{guild.name}` (ID: {guild.id}) is blacklisted from using Vortex.\n\n"
                "If you believe this is a mistake, please contact the bot owner [@playfairs](https://discord.com/users/1426711359059394662)\n\n"
                f"For more info, join the [Discord Server]({Servers.vortex}) for more info on Vortex.",
                color=discord.Color(0xFFFFFF),
            )
            embed.set_thumbnail(url=Media.vortex)
            try:
                await guild.owner.send(embed=embed)
            except discord.Forbidden:
                pass
            await guild.leave()
            return

        inviter = None
        try:
            async for entry in guild.audit_logs(
                limit=1, action=discord.AuditLogAction.bot_add
            ):
                inviter = entry.user
                break
        except Exception as e:
            print(f"Could not retrieve inviter for {guild.name}: {e}")

        booster_pass = False
        if inviter is not None:
            try:
                source_guild = bot.get_guild(1271976967381712989)
                if source_guild is not None:
                    member = source_guild.get_member(inviter.id)
                    if member is None:
                        try:
                            member = await source_guild.fetch_member(inviter.id)
                        except Exception:
                            member = None
                    if member is not None and member.premium_since is not None:
                        booster_pass = True
            except Exception as e:
                print(f"Error checking booster exemption for inviter {inviter}: {e}")

        human_members = [m for m in guild.members if not m.bot]
        has_booster = any(m.premium_since is not None for m in guild.members)
        if (
            len(human_members) < 10
            and not has_booster
            and not booster_pass
            and guild.owner_id not in bot.owner_ids
        ):
            embed = discord.Embed(
                title="Guild too small",
                description=(
                    "Hello! Thank you for inviting Vortex to your server.\n"
                    "Unfortunately, Vortex requires a minimum of 10 human members in a guild to be allowed to join.\n"
                    "This is to ensure that Vortex can provide a more useful experience, if you still wish to add the bot without passing 10 members, you can DM @playfairs to have your guild whitelisted for this exception.\n\n"
                    f"If you have any questions, join the [Discord Server]({Servers.vortex}) for more info on Vortex."
                ),
                color=discord.Color(0xFFFFFF),
            )
            embed.set_thumbnail(url=Media.vortex)
            try:
                owner = guild.owner
                if owner is None or owner.bot:
                    owner = await self.bot.fetch_user(guild.owner_id)
                await owner.send(embed=embed)
            except Exception as e:
                print(f"Could not DM guild owner for {guild.name}: {e}")
            try:
                await guild.leave()
            except discord.Forbidden:
                print(f"Could not leave {guild.name} due to permissions.")
            except Exception as e:
                print(f"An error occurred while leaving {guild.name}: {e}")
            return

        if inviter:
            embed = discord.Embed(
                title="Thanks for inviting Vortex!",
                description=(
                    "Hello! Thank you for inviting Vortex to your server.\n"
                    "To see all available commands, use `;h`.\n\n"
                    f"If you have any questions, join the [Discord Server]({Servers.vortex}) for more info on Vortex."
                ),
                color=discord.Color(0xFFFFFF),
            )
            embed.set_thumbnail(url=Media.vortex)

            embed.add_field(
                name="Resources",
                value="**[invite](https://discordapp.com/oauth2/authorize?client_id=1284037026672279635&scope=bot+applications.commands&permissions=8)**  • "
                f"**[server]({Servers.vortex})**  • "
                "**[terms](https://vortex.playfairs.cc/terms)**  • "
                "**[privacy](https://vortex.playfairs.cc/privacy)**",
                inline=False,
            )
            embed.set_footer(
                text="Please note that Vortex is not perfect, and may have some minor issues, or lack commands."
            )
            try:
                await inviter.send(embed=embed)
            except Exception as e:
                print(f"Could not DM inviter {inviter}: {e}")

        invite_link = "Unable to generate invite"
        try:
            invite = await guild.text_channels[0].create_invite(
                max_age=604800, max_uses=1, unique=True
            )
            invite_link = invite.url
        except Exception as e:
            print(f"Could not create invite for {guild.name}: {e}")

        embed = discord.Embed(
            title="New Guild.",
            description=(
                f"I was added to `{guild.name}` by "
                f"{inviter.mention if inviter else 'an unauthorized user'}.\n\n"
                f"**Owner:** {guild.owner.mention if guild.owner else f'ID: {guild.owner_id}'}\n"
                f"**Created:** <t:{int(guild.created_at.replace(tzinfo=timezone.utc).timestamp())}:R>\n"
                f"**Members:** {guild.member_count}"
            ),
            color=discord.Color(0xFFFFFF),
        )
        embed.set_thumbnail(url=Media.vortex)
        embed.add_field(name="Invite Link", value=invite_link, inline=False)
        embed.set_footer(text=f"Guild ID: {guild.id}")
        try:
            owner_user = await self.bot.fetch_user(self.owner_id)
            await owner_user.send(embed=embed)
        except Exception as e:
            print(f"Could not DM owner: {e}")

        if guild.id in self.blacklisted_guilds:
            return
        else:
            await self.bot.get_channel(1374163885124485171).send(
                f"Added to `{guild.name}`, I am now in `{len(self.bot.guilds)}` guilds, serving `{sum(len(g.members) for g in self.bot.guilds)}` users."
            )

    #    @Cog.listener()
    #    async def on_user_update(self, before: discord.User, after: discord.User):
    #        if before.name != after.name:
    #            channel = self.bot.get_channel(1374163966678536363)
    #            if not channel:
    #                return
    #            if len(before.name) > 32:
    #                return
    #            embed = discord.Embed(
    #                description=f"Username **{before.name}** has been dropped.\n"
    #                f"> Username will become available on <t:{int((datetime.now(timezone.utc) + timedelta(days=14)).timestamp())}:f>",
    #                color=discord.Color.from_rgb(255, 255, 255),
    #            )
    #            embed.set_footer(text=f"User ID: {before.id} • New Name: {after.name}")
    #            embed.set_thumbnail(url=Media.vortex)
    #            await channel.send(embed=embed)

    @Cog.listener()
    async def on_user_update(self, before: discord.User, after: discord.User):
        if before.name == after.name:
            return

        if len(before.name) > 32:
            return

        channel_ids = [
            1374163966678536363,
            1453210973086289940,
        ]

        embed = discord.Embed(
            description=(
                f"Username **{before.name}** has been dropped.\n"
                f"> Username will become available on "
                f"<t:{int((datetime.now(timezone.utc) + timedelta(days=14)).timestamp())}:f>"
            ),
            color=discord.Color.from_rgb(255, 255, 255),
        )
        embed.set_footer(text=f"User ID: {before.id} • New Name: {after.name}")
        embed.set_thumbnail(url=Media.vortex)

        for channel_id in channel_ids:
            channel = self.bot.get_channel(channel_id)
            if channel:
                await channel.send(embed=embed)

    @Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if message.channel.type == discord.ChannelType.private:
            return

        content_lower = message.content.lower()
        tried_ping = "@everyone" in content_lower or "@here" in content_lower
        actually_pinged = message.mention_everyone
        if message.author == message.guild.owner and tried_ping and not actually_pinged:
            await message.reply(
                "How the fuck does the owner of a server fail a ping ", delete_after=5
            )
        else:
            if tried_ping and not actually_pinged:
                await message.reply("L ping fail", delete_after=5)

    @Cog.listener("afk_betrayal")
    async def afk_betrayal(self, ctx: Context):
        if ctx.author.id == 1426711359059394662:
            if ctx.message.content.startswith(
                "h;afk"
            ) or ctx.message.content.startswith(":afk "):
                await ctx.reply(
                    "bros not even using his own bot to go afk, how dare you :("
                )
                return

    @Cog.listener()
    async def on_message_edit(self, before: Message, after: Message):
        if (
            before.author
            and before.author.id == self.bot.user.id
            and not before.flags.suppress_embeds
            and after.flags.suppress_embeds
        ):
            await after.channel.send("hey where did my embed go :(")

    @Cog.listener(name="on_message")
    async def on_message2(self, message: Message):
        if (
            message.author.bot
            and message.author.id == 1184986039765450782
            and "<@1347441071323480074> you just advanced to level" in message.content
        ):
            await message.reply("Why thank you :3")

    @Cog.listener(name="on_message")
    async def on_message3(self, message: Message):
        if (
            message.author.bot
            and message.author.id == 1184986039765450782
            and "<@1426711359059394662> you just advanced to level" in message.content
        ):
            await message.reply("bro needs to touch grass")

    @Cog.listener(name="on_message")
    async def on_message4(self, message: Message):
        if not message.author.bot or not message.guild:
            return

        if message.reference is not None:
            return

        if message.author.id == 765883944770994176 and (
            message.content.startswith("<@1347441071323480074>")
            or "<@1347441071323480074>" in message.content
        ):
            if "is now having a fridge thrown at them" in message.content:
                await message.reply(
                    "Why is a bot throwing a fridge at me??", mention_author=False
                )
            elif "is now being run over by a truck" in message.content:
                await message.reply("ouch", mention_author=False)
            elif "is now being held at gunpoint" in message.content:
                await message.reply("get that gun out of my face", mention_author=False)

    @Cog.listener()
    async def on_usage(self, ctx):
        """Listener for command usage events."""

        if not hasattr(ctx, "command") or not ctx.command:
            return

        try:
            guild_id = ctx.guild.id if ctx.guild else 0
            command_name = ctx.command.qualified_name
            user_id = getattr(ctx.author, "id", 0)

            async with self.bot.db.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO command_usage (user_id, guild_id, command_name, timestamp)
                    VALUES ($1, $2, $3, NOW())
                    RETURNING id
                    """,
                    user_id,
                    guild_id,
                    command_name,
                )

        except Exception:
            import traceback

            traceback.print_exc()

    @command(name="imagine", hidden=True)
    async def imagine(self, ctx: Context):
        """A hidden command that only responds if run by a specific bot."""
        if ctx.author.id == 1184986039765450782:
            await ctx.send("and I'll do it again")

    @Cog.listener(name="on_message")
    async def on_jvc(self, message: Message):
        if message.author.bot:
            return

        if "jvc" in message.content.lower():
            if not message.author.voice or not message.author.voice.channel:
                return

            voice_channel = message.author.voice.channel
            try:
                channel_link = f"https://discord.com/channels/{message.guild.id}/{voice_channel.id}"

                if message.mentions:
                    for user in message.mentions:
                        await message.channel.send(
                            f"{user.mention}, {channel_link}", delete_after=30
                        )
                else:
                    await message.channel.send(channel_link, delete_after=30)

            except Exception as e:
                await message.channel.send(
                    f"Failed to create channel link: {e}", delete_after=30
                )
