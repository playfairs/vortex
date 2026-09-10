import os
import time
import discord
import json
import pytz
import aiohttp
from typing import Optional, List
import yt_dlp
import aiohttp
import io
import datetime
from datetime import timezone
import os
import requests
import fuzzywuzzy
import base64
import re
from cogs.utility.timezone import TIMEZONE_ABBR
from discord.ext import commands
from discord import app_commands
from discord.ext.commands import (
    Cog,
    command,
    Context,
    hybrid_command as hybrid,
    hybrid_group,
    group,
    is_owner,
    has_permissions,
)
from discord import ui
from deep_translator import GoogleTranslator
from vortex import vortex
from managers import Emojis as e
import colorsys
import webcolors
import random
import subprocess

MERRIAM_WEBSTER_API_KEY = os.getenv("MERRIAM_WEBSTER_API_KEY")


class Emoji:
    def __init__(self, name: str, id: int, animated: bool):
        self.name = name
        self.id = id
        self.animated = animated

    @property
    def url(self) -> str:
        ext = "gif" if self.animated else "png"
        return f"https://cdn.discordapp.com/emojis/{self.id}.{ext}"

    @property
    def mention(self) -> str:
        return f"<{'a' if self.animated else ''}:{self.name}:{self.id}>"

    @property
    def extention(self) -> str:
        return "gif" if self.animated else "png"


class Utility(Cog, description="View commands in Utility."):
    def __init__(self, bot: vortex):
        self.bot = bot
        self._db_initialized = False
        self.sticky_counters = {}  # {channel_id: counter}
        self.last_sticky_messages = {}  # {channel_id: message_id}
        self.bot.loop.create_task(self.initialize_all())

    async def initialize_all(self):
        """Initialize all components in the correct order."""
        await self.initialize_db()
        await self.initialize_timezones_db()
        await self.initialize_sticky_db()
        await self.initialize_afk_db()
        self._db_initialized = True

    async def initialize_db(self):
        """Initialize the database tables."""
        async with self.bot.db.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sticky_notes (
                    guild_id BIGINT NOT NULL,
                    channel_id BIGINT NOT NULL,
                    rate INTEGER NOT NULL DEFAULT 5,
                    note TEXT NOT NULL,
                    PRIMARY KEY (guild_id, channel_id),
                    UNIQUE (guild_id, channel_id)
                )
                """
            )

    async def initialize_timezones_db(self):
        """Initialize the user_timezones table in the database."""
        await self.bot.db.execute(
            """
                CREATE TABLE IF NOT EXISTS user_timezones (
                    user_id BIGINT PRIMARY KEY,
                    timezone TEXT NOT NULL
                )
                """
        )

    async def initialize_sticky_db(self):
        """Initialize the sticky notes table in the database."""
        await self.bot.db.execute(
            """
                CREATE TABLE IF NOT EXISTS sticky_notes (
                    guild_id BIGINT PRIMARY KEY,
                    channel_id BIGINT NOT NULL,
                    rate BIGINT NOT NULL,
                    note TEXT NOT NULL
                )
                """
        )

    async def initialize_afk_db(self):
        """Initialize the PostgreSQL database for AFK users."""
        await self.bot.db.execute(
            """
                CREATE TABLE IF NOT EXISTS afk_users (
                    user_id BIGINT PRIMARY KEY,
                    reason TEXT,
                    afk_time BIGINT
                )
                """
        )

    async def timezone(self, user_id: int):
        """Fetches the timezone for a user from the database, matching the logic in time_set."""
        row = await self.bot.db.fetchrow(
            "SELECT timezone FROM user_timezones WHERE user_id = $1", user_id
        )
        if row and row["timezone"] in TIMEZONE_ABBR:
            return row["timezone"]
        return None

    async def get_user_current_time(self, user_id: int):
        tz_abbr = await self.timezone(user_id)
        if not tz_abbr:
            return None

        tz_name = TIMEZONE_ABBR.get(tz_abbr)
        if not tz_name:
            return None

        now = datetime.datetime.now(pytz.timezone(tz_name))
        return now.strftime("%m/%d/%Y %I:%M %p")

    async def set_afk(self, user_id, reason):
        """Sets the AFK status for a user with the current timestamp."""
        await self.bot.db.execute(
            """
                INSERT INTO afk_users (user_id, reason, afk_time)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id) 
                DO UPDATE SET reason = $2, afk_time = $3
                """,
            user_id,
            reason,
            int(time.time()),
        )

    async def get_afk_status(self, user_id):
        """Gets the AFK status and timestamp for a user."""
        return await self.bot.db.fetchrow(
            """SELECT reason, afk_time FROM afk_users WHERE user_id = $1""",
            user_id,
        )

    async def remove_afk(self, user_id):
        """Removes the AFK status for a user."""
        await self.bot.db.execute(
            """DELETE FROM afk_users WHERE user_id = $1""", user_id
        )

    def format_time_ago(self, afk_time):
        """Formats the time since the AFK status was set."""
        time_elapsed = int(time.time()) - afk_time
        if time_elapsed <= 1:
            return "What the fuck was the point of going afk if you're just coming back in less than a second??"
        if time_elapsed < 60:
            return f"{time_elapsed} seconds"
        elif time_elapsed < 3600:
            minutes = time_elapsed // 60
            return f"{minutes} minutes"
        elif time_elapsed < 86400:
            hours = time_elapsed // 3600
            return f"{hours} hours"
        else:
            days = time_elapsed // 86400
            return f"{days} days"

    @hybrid_group(
        name="afk",
        aliases=[
            "kms",
            "goodnight",
            "despawn",
            "idle",
            "akf",
            "dies",
            "oof",
            "bye",
            "a",
            "aficionado",
            "apt",
            "sleeping",
            "sleep",
            "tired",
        ],
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(reason="The reason for going AFK.")
    async def afk(self, ctx: Context, *, reason: str = None):
        """Set the AFK status with an optional reason."""
        if reason is None:
            reason = ""
        user_id = ctx.author.id

        aliases = [
            "kms",
            "despawn",
            "idle",
            "akf",
            "dies",
            "oof",
            "bye",
            "apt",
            "sleeping",
            "sleep",
            "tired",
        ]

        if ctx.invoked_with == "akf":
            reason = "away killing furries"
        if (
            ctx.invoked_with == "sleeping"
            or ctx.invoked_with == "sleep"
            or ctx.invoked_with == "tired"
            or ctx.invoked_with == "goodnight"
        ):
            reason = "sleeping"

        current_afk = await self.get_afk_status(user_id)
        is_updating = current_afk is not None

        if len(reason) >= 2000 and ctx.author.id == 1265662059056463976:
            container = ui.Container()
            container.add_item(
                ui.TextDisplay(
                    content="> FUCK YOU NOVA",
                )
            )
            container.accent_colour = discord.Colour(0xFFFFFF)
            view = ui.LayoutView()
            view.add_item(container)
            await ctx.send(view=view, ephemeral=True)
            return

        if len(reason) >= 2000:
            container = ui.Container()
            container.add_item(
                ui.TextDisplay(
                    content="> Your AFK reason is too long. Please keep it under 2000 characters.",
                )
            )
            container.accent_colour = discord.Colour(0xFFFFFF)
            view = ui.LayoutView()
            view.add_item(container)
            await ctx.send(view=view, ephemeral=True)
            return

        if is_updating:
            await self.bot.db.execute(
                """
                UPDATE afk_users 
                SET reason = $1 
                WHERE user_id = $2
                """,
                reason,
                user_id,
            )
        else:
            await self.bot.db.execute(
                """
                INSERT INTO afk_users (user_id, reason, afk_time)
                VALUES ($1, $2, $3)
                """,
                user_id,
                reason,
                int(time.time()),
            )
        if reason:
            container = ui.Container()
            if is_updating:
                container.add_item(
                    ui.TextDisplay(
                        content=f"> {ctx.author.mention}: Updated your AFK status: **{reason}**",
                    )
                )
            else:
                container.add_item(
                    ui.TextDisplay(
                        content=f"> {ctx.author.mention}: You're now AFK: **{reason}**",
                    )
                )
            container.accent_colour = discord.Colour(0xFFFFFF)
            view = ui.LayoutView()
            view.add_item(container)
            await ctx.reply(
                view=view,
                allowed_mentions=discord.AllowedMentions(
                    users=False, everyone=False, roles=False
                ),
                mention_author=True,
            )
        else:
            container = ui.Container()
            container.add_item(
                ui.TextDisplay(
                    content=f"> {ctx.author.mention}: You're now AFK.",
                )
            )
            container.accent_colour = discord.Colour(0xFFFFFF)
            view = ui.LayoutView()
            view.add_item(container)
            await ctx.reply(
                view=view,
                allowed_mentions=discord.AllowedMentions(
                    users=False, everyone=False, roles=False
                ),
                mention_author=True,
            )

    @afk.command(name="set", aliases=["update"])
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def afk_set(self, ctx, *, reason: str = None):
        await self.afk(ctx, reason=reason)

    @Cog.listener("on_message")
    async def afk_listener1(self, message):
        if message.author.bot or message.webhook_id is not None:
            return

        ctx = await self.bot.get_context(message)
        if ctx.valid:
            return

        afk_data = await self.get_afk_status(message.author.id)

        if afk_data:
            await self.remove_afk(message.author.id)

            container = ui.Container()
            container.add_item(
                ui.TextDisplay(
                    content=f"> {message.author.mention}: Welcome back, you went AFK: <t:{int(afk_data[1])}:R>.",
                )
            )
            container.accent_colour = discord.Colour(0xFFFFFF)
            view = ui.LayoutView()
            view.add_item(container)
            await ctx.reply(view=view, delete_after=60, mention_author=True)

        for mentioned_user in message.mentions:
            afk_data = await self.get_afk_status(mentioned_user.id)
            if afk_data:
                reason, afk_time = afk_data

                if reason:
                    container = ui.Container()
                    container.add_item(
                        ui.TextDisplay(
                            content=f"> {mentioned_user.mention} went AFK <t:{int(afk_time)}:R>: **{reason}**",
                        )
                    )
                else:
                    container = ui.Container()
                    container.add_item(
                        ui.TextDisplay(
                            content=f"> {mentioned_user.mention} went AFK <t:{int(afk_time)}:R>",
                        )
                    )

                container.accent_colour = discord.Colour(0xFFFFFF)
                view = ui.LayoutView()
                view.add_item(container)
                await ctx.reply(
                    view=view,
                    delete_after=20,
                    allowed_mentions=discord.AllowedMentions(
                        users=False, everyone=False, roles=False
                    ),
                    mention_author=True,
                )

    @afk.command(name="leaderboard", aliases=["lb"])
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def afk_leaderboard(self, ctx):
        """Shows the AFK leaderboard."""
        query = """
            SELECT user_id, afk_time
            FROM afk_users
            ORDER BY afk_time ASC
            LIMIT 10
        """
        afk_users = await self.bot.db.fetch(query)

        container = ui.Container()
        container.add_item(ui.TextDisplay(content="> ### AFK Leaderboard"))
        container.add_item(
            ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
        )

        if afk_users:
            lb = []
            for user_id, afk_time in afk_users:
                user = self.bot.get_user(user_id)
                if user is None:
                    lb.append(f"> Unknown User ({user_id}) <t:{int(afk_time)}:R>")
                else:
                    lb.append(f"> {user.mention} <t:{int(afk_time)}:R>")

            container.add_item(ui.TextDisplay(content="\n".join(lb)))
        else:
            container.add_item(
                ui.TextDisplay(content="> No one is currently AFK, how sad :(")
            )

        container.accent_colour = discord.Colour(0xFFFFFF)
        view = ui.LayoutView()
        view.add_item(container)
        await ctx.reply(view=view)

    @afk.command(name="remove", aliases=["uafk", "unafk", "forceremove"])
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def force_remove_afk(self, ctx, member: discord.Member):
        """Forcefully removes AFK status from a mentioned user if they are AFK."""
        if ctx.author.id != 1426711359059394662:
            await ctx.send("You do not have permission to use this command.")
            return

        afk_data = await self.get_afk_status(member.id)
        if afk_data:
            await self.remove_afk(member.id)
            container = ui.Container()
            container.add_item(
                ui.TextDisplay(
                    content=f"> {member.mention} is no longer AFK.",
                )
            )
            container.accent_colour = discord.Colour(0xFFFFFF)
            view = ui.LayoutView()
            view.add_item(container)
            await ctx.reply(view=view)
        else:
            container = ui.Container()
            container.add_item(
                ui.TextDisplay(
                    content=f"> {member.mention} is not AFK.",
                )
            )
            container.accent_colour = discord.Colour(0xFFFFFF)
            view = ui.LayoutView()
            view.add_item(container)
            await ctx.reply(view=view)

    @hybrid(
        name="urban",
        description="Searches for a word via the Urban Dictionary",
    )
    @app_commands.allowed_installs(
        guilds=True,
        users=True,
    )
    @app_commands.allowed_contexts(
        guilds=True,
        dms=True,
        private_channels=True,
    )
    @app_commands.describe(word="Defines a word via the Urban Dictionary.")
    async def urban(self, ctx: Context, *, word: str):
        if any(
            mention in ctx.message.content.lower() for mention in ["@here", "@everyone"]
        ):
            await ctx.send("Nice try, but no.")
            return

        url = f"https://api.urbandictionary.com/v0/define"
        params = {"term": word}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("list"):
                            definition_data = data["list"][0]
                            word = definition_data["word"]
                            definition = definition_data["definition"]
                            example = definition_data.get(
                                "example", "No example available"
                            )

                            if len(definition) > 1000:
                                definition = definition[:997] + "..."
                            if len(example) > 1000:
                                example = example[:997] + "..."

                            embed = discord.Embed(
                                title=f"Urban Dictionary: {word}",
                                color=discord.Color(0xFFFFFF),
                            )
                            embed.add_field(
                                name="Definition", value=definition, inline=False
                            )
                            if example.lower() != "no example available":
                                embed.add_field(
                                    name="Example", value=f"*{example}*", inline=False
                                )
                            embed.set_footer(text="Provided by the Urban Dictionary")

                            await ctx.send(embed=embed)
                        else:
                            await ctx.send(
                                f"No definition found for `{word}`, maybe you should make one."
                            )
                    else:
                        await ctx.send(
                            "Failed to fetch from Urban Dictionary. Please try again later."
                        )
        except Exception as e:
            print(f"Error in urban command: {e}")
            await ctx.send(
                "An error occurred while fetching from Urban Dictionary. Please try again later."
            )

    @hybrid(
        name="define",
        description="Searches for a word via the Merriam-Webster.",
    )
    @app_commands.allowed_installs(
        guilds=True,
        users=True,
    )
    @app_commands.allowed_contexts(
        guilds=True,
        dms=True,
        private_channels=True,
    )
    @app_commands.describe(word="Defines a word via the Merriam-Webster.")
    async def dictionary(self, ctx: Context, *, word: str):
        if any(
            mention in ctx.message.content.lower() for mention in ["@here", "@everyone"]
        ):
            await ctx.send("Nice try, but no.")
            return
        if not MERRIAM_WEBSTER_API_KEY:
            await ctx.send("The API key is not set.")
            return

        api_url = f"https://www.dictionaryapi.com/api/v3/references/collegiate/json/{word}?key={MERRIAM_WEBSTER_API_KEY}"
        response = requests.get(api_url)

        if response.status_code != 200:
            await ctx.send(
                "Sorry, I couldn't fetch the definition at the moment. Please try again later."
            )
            return

        data = response.json()

        if not data or isinstance(data[0], str):
            await ctx.send(f"No definition found for **{word}**.")
            return

        definition_data = data[0]
        word_definition = definition_data.get("shortdef", ["No definition available."])[
            0
        ]
        part_of_speech = definition_data.get("fl", "Unknown")

        embed = discord.Embed(
            title=f"Merriam Webster: {word}", color=discord.Color(0xFFFFFF)
        )
        embed.add_field(name="Word", value=word, inline=False)
        embed.add_field(name="Part of Speech", value=part_of_speech, inline=True)
        embed.add_field(name="Definition", value=word_definition, inline=False)
        embed.set_footer(text="Provided by the Merriam Webster.")

        await ctx.send(embed=embed)

    @group(
        name="time",
        aliases=["timezone", "tz"],
        invoke_without_command=True,
        description="Get the current time for yourself or set your timezone.",
    )
    async def time(self, ctx: Context, member: discord.Member = None):
        """Get the current time for yourself or another user based on their set timezone."""
        member = member or ctx.author

        async with self.bot.db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT timezone FROM user_timezones WHERE user_id = $1", member.id
            )
        if not row:
            embed = discord.Embed(
                title="Timezone Not Set",
                description=(
                    f"{'You have' if member == ctx.author else f'{member.mention} has'} not set a timezone yet. "
                    "Use `,time set <timezone>` to set it.\n\nAvailable timezones:\n"
                    + ", ".join(TIMEZONE_ABBR.keys())
                ),
                color=discord.Color(0xFFFFFF),
            )
            await ctx.send(embed=embed)
            return

        tz_abbr = row["timezone"]
        tz_name = TIMEZONE_ABBR.get(tz_abbr)
        if not tz_name:
            owner = "Your" if member == ctx.author else f"{member.mention}'s"
            await ctx.send(
                f"{owner} timezone is invalid or not supported. Please set it again with `/time set <timezone>`."
            )
            return

        now = datetime.datetime.now(pytz.timezone(tz_name))
        formatted_time = now.strftime("%m/%d/%Y %I:%M %p")
        if member == ctx.author:
            description = f"The current time for you is {formatted_time}."
            title = f"Current time for {ctx.author.display_name}"
        else:
            description = f"The current time for {member.mention} is {formatted_time}."
            title = f"Current time for {member.display_name}"

        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color(0xFFFFFF),
        )
        embed.set_footer(
            text=f"Requested by {ctx.author} • {tz_abbr}",
            icon_url=(
                ctx.author.avatar.url if ctx.author.avatar else self.bot.user.avatar.url
            ),
        )
        await ctx.send(embed=embed)

    @time.command(
        name="set", description="Set your timezone (see /time for available timezones)."
    )
    async def time_set(self, ctx: Context, timezone_abbr: str):
        """Set your timezone for time commands."""
        timezone_abbr = timezone_abbr.upper()
        if timezone_abbr not in TIMEZONE_ABBR:
            embed = discord.Embed(
                title="Invalid Timezone",
                description="That timezone abbreviation is not supported.\nAvailable timezones:\n"
                + ", ".join(TIMEZONE_ABBR.keys()),
                color=discord.Color(0xFFFFFF),
            )
            await ctx.send(embed=embed)
            return

        async with self.bot.db.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO user_timezones (user_id, timezone)
                VALUES ($1, $2)
                ON CONFLICT (user_id) DO UPDATE SET timezone = $2
                """,
                ctx.author.id,
                timezone_abbr,
            )
        embed = discord.Embed(
            title="Timezone Set",
            description=f"Your timezone has been set to **{timezone_abbr}**.",
            color=discord.Color(0xFFFFFF),
        )
        await ctx.send(embed=embed)

    @command(name="fetch")
    async def fetch_sticker(self, ctx):
        """Fetches the sticker from a reply and sends it as a downloadable file."""
        if ctx.message.reference is None:
            await ctx.send("Please reply to a sticker to fetch it.")
            return

        message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
        sticker = message.stickers[0] if message.stickers else None

        if sticker:
            async with aiohttp.ClientSession() as session:
                async with session.get(sticker.url) as resp:
                    if resp.status != 200:
                        await ctx.send("Failed to download the sticker.")
                        return
                    sticker_bytes = await resp.read()

            if len(sticker_bytes) > 256 * 1024:
                await ctx.send("Sticker is too large to fetch (max 256 KB).")
                return

            file_format = "gif" if sticker.url.endswith(".gif") else "png"
            await ctx.send(
                file=discord.File(
                    io.BytesIO(sticker_bytes), filename=f"sticker.{file_format}"
                )
            )
        else:
            await ctx.send("No sticker found in the replied message.")

    async def _download(self, url):
        """Download a file from a URL and return it as a BytesIO."""
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.read()
                    return data
                else:
                    return None

    @commands.group(name="steal", invoke_without_command=True)
    @has_permissions(manage_emojis_and_stickers=True)
    async def steal(self, ctx: commands.Context, emoji=None):
        """Steal first emoji, sticker from replied message, if not provided"""
        if not ctx.author.guild_permissions.manage_emojis_and_stickers:
            await ctx.send("You do not have permission to manage emojis and stickers.")
            return
        if not emoji:
            if ctx.message.reference:
                emoji = ctx.message.reference.resolved.content
            else:
                await ctx.send(
                    "Please provide an emoji or sticker to steal or reply to a message with an emoji or sticker."
                )
                return

        match = re.match(r"<(a?):(\w+):(\d+)>", emoji)
        if not match:
            await ctx.send("No valid emojis found to steal.")
            return
        if match:
            emoji = Emoji(match.group(2), match.group(3), match.group(1) == "a")
            try:
                created = await ctx.guild.create_custom_emoji(
                    name=emoji.name,
                    image=await self._download(emoji.url),
                    reason=f"Emoji stolen by {ctx.author}",
                )
                await ctx.send(
                    f"{e.check} Successfully stole emoji <{'a' if created.animated else ''}:{created.name}:{created.id}>!"
                )
            except discord.Forbidden or discord.HTTPException:
                await ctx.send(
                    f"{e.cancel} Failed to steal emoji. Please check the permissions and try again."
                )

    @steal.command(name="emojis")
    @has_permissions(manage_emojis_and_stickers=True)
    async def steal_emojis(self, ctx: commands.Context, *, emojis=None):
        """Steal multiple emojis from attached message, or replied message"""
        if not ctx.author.guild_permissions.manage_emojis_and_stickers:
            await ctx.send("You do not have permission to manage emojis and stickers.")
            return

        if not emojis and not ctx.message.reference:
            await ctx.send("Please provide emojis or reply to a message with emojis.")
            return

        if ctx.message.reference:
            message = ctx.message.reference.resolved
            if message and message.content:
                emojis = re.findall(r"<(a?):(\w+):(\d+)>", message.content)
            else:
                await ctx.send("No emojis found in the replied message.")
                return
        else:
            emojis = re.findall(r"<(a?):(\w+):(\d+)>", emojis)

        if not emojis:
            await ctx.send("No valid emojis found to steal.")
            return
        messages = []
        for match in emojis:
            emoji = Emoji(match[1], match[2], match[0] == "a")
            try:
                created = await ctx.guild.create_custom_emoji(
                    name=emoji.name,
                    image=await self._download(emoji.url),
                    reason=f"Emoji stolen by {ctx.author}",
                )
                messages.append(
                    f"{e.check} Successfully stole emoji <{'a' if created.animated else ''}:{created.name}:{created.id}>"
                )
            except discord.Forbidden or discord.HTTPException:
                messages.append(
                    f"{e.cancel} Failed to steal emoji {emoji.mention}. Please check the permissions and try again."
                )
        embed = discord.Embed(
            title="Stolen Emojis",
            description="\n".join(messages),
            color=discord.Color.green(),
        )
        await ctx.send(embed=embed)

    @steal.command(name="sticker")
    @has_permissions(manage_emojis_and_stickers=True)
    async def steal_sticker(self, ctx: commands.Context):
        """Steal a sticker by downloading from CDN and re-adding it to this guild preserving its values."""
        if not ctx.author.guild_permissions.manage_emojis_and_stickers:
            await ctx.send("You do not have permission to manage emojis and stickers.")
            return

        if not ctx.message.stickers:
            if ctx.message.reference:
                message = ctx.message.reference.resolved
                if message and message.stickers:
                    sticker = message.stickers[0]
                else:
                    await ctx.send("No stickers found in the replied message.")
                    return
        else:
            sticker = ctx.message.stickers[0]
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(sticker.url) as resp:
                    if resp.status != 200:
                        await ctx.send("Failed to download sticker from CDN.")
                        return
                    data = await resp.read()
                    content_type = resp.headers.get("Content-Type", "").lower()

            if len(data) > 512 * 1024:
                await ctx.send(
                    "Sticker is too large to upload as a guild sticker (max 512 KiB)."
                )
                return

            ext = "png"
            if "gif" in content_type or sticker.url.lower().endswith(".gif"):
                ext = "gif"
            elif "png" in content_type or sticker.url.lower().endswith(".png"):
                ext = "png"
            elif "webp" in content_type or sticker.url.lower().endswith(".webp"):
                ext = "webp"
            elif "json" in content_type or sticker.url.lower().endswith(".json"):
                ext = "json"

            filename = f"{sticker.name}.{ext}"

            current_stickers = await ctx.guild.fetch_stickers()
            max_stickers = 5
            if ctx.guild.premium_tier >= 1:
                max_stickers = 15
            if ctx.guild.premium_tier >= 2:
                max_stickers = 30
            if ctx.guild.premium_tier >= 3:
                max_stickers = 60

            if len(current_stickers) >= max_stickers:
                await ctx.send(
                    f"This server has reached its maximum number of stickers ({max_stickers}). "
                    "Upgrade the server's boost level to add more stickers!"
                )
                return

            desc = ""
            emoji_tag = "👍"
            try:
                full = await self.bot.fetch_sticker(sticker.id)
                if getattr(full, "description", None):
                    desc = full.description
                if getattr(full, "tags", None):
                    first_tag = str(full.tags).split(",")[0].strip()
                    if first_tag:
                        emoji_tag = first_tag
            except Exception:
                pass

            created = await ctx.guild.create_sticker(
                name=sticker.name,
                description=desc,
                emoji=emoji_tag,
                file=discord.File(io.BytesIO(data), filename=filename),
                reason=f"Sticker stolen by {ctx.author}",
            )

            await ctx.send(
                content=f"Successfully stole sticker `{created.name}`!",
                stickers=[created],
            )
        except discord.Forbidden:
            await ctx.send("I don't have permission to create stickers in this server.")
        except discord.HTTPException as ex:
            await ctx.send(f"Failed to create sticker: {ex}")

    @group(name="emoji", invoke_without_command=True)
    async def emoji(self, ctx: commands.Context):
        """Base command for emoji commands."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @emoji.command(name="escape", aliases=["esc"])
    async def escape(self, ctx: commands.Context, *, emojis: str):
        """Convert emojis to their string representation in a code block."""
        emoji_strings = []
        for char in emojis:
            if char in ("<", ">", ":", "a") and char in emojis:
                emoji_match = re.search(r"<a?:[a-zA-Z0-9_]+:(\d+)>", emojis)
                if emoji_match:
                    emoji_id = emoji_match.group(1)
                    emoji = self.bot.get_emoji(int(emoji_id))
                    if emoji:
                        animated = "a" if emoji.animated else ""
                        emoji_strings.append(f"<{animated}:{emoji.name}:{emoji.id}>")
                    emojis = emojis[emoji_match.end() :]
                    continue
            if ord(char) > 0x1F000:
                emoji_strings.append(char)

        if not emoji_strings:
            await ctx.send("No emojis found in the input.")
            return

        embed = discord.Embed(title="Emoji Escape", color=discord.Color.green())
        embed.description = "\n".join(
            [f"{i+1}. {emoji} = `{emoji}`" for i, emoji in enumerate(emoji_strings)]
        )
        await ctx.send(embed=embed)

    @hybrid(
        name="color",
        aliases=["hex", "colour"],
        description="Shows a color swatch and RGB, HEX, HSL info.",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(hexcode="The hex code to show.")
    async def color(self, ctx: Context, hexcode: str = None):
        """Shows a color swatch and RGB, HEX, HSL info."""
        if not hexcode:
            hexcode = f"{random.randint(0, 0xFFFFFF):06x}"
        else:
            hexcode = hexcode.lower().replace("#", "").strip()
            if not all(c in "0123456789abcdef" for c in hexcode) or len(
                hexcode
            ) not in (3, 6):
                return await ctx.send(
                    "Not a valid hex code, If you did a color name, searching colors is being worked on, please be patient :)",
                    ephemeral=True,
                )

        try:
            if len(hexcode) == 6:
                hex_val = hexcode
                rgb = tuple(int(hex_val[i : i + 2], 16) for i in (0, 2, 4))
            elif len(hexcode) == 3:
                hex_val = "".join([i * 2 for i in hexcode])
                rgb = tuple(int(hex_val[i : i + 2], 16) for i in (0, 2, 4))
            elif " " in hexcode:
                rgb = tuple(int(i) for i in hexcode.split())
                hex_val = "".join(f"{x:02x}" for x in rgb)
            else:
                raise ValueError("Invalid color format")

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://www.thecolorapi.com/id?hex={hex_val}&format=json"
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        color_name = data.get("name", {}).get("value", "")
                        if color_name:
                            color_display = (
                                f"{color_name.title()} (`#{hex_val.upper()}`)"
                            )
                        else:
                            color_display = f"`#{hex_val.upper()}`"

                        cmyk = (
                            data.get("cmyk", {})
                            .get("value", "")
                            .replace("cmyk(", "")
                            .rstrip(")")
                        )
                        hsv = (
                            data.get("hsv", {})
                            .get("value", "")
                            .replace("hsv(", "")
                            .rstrip(")")
                        )
                        xyz = (
                            data.get("XYZ", {})
                            .get("value", "")
                            .replace("XYZ(", "")
                            .rstrip(")")
                        )
                    else:
                        color_display = f"`#{hex_val.upper()}`"
                        cmyk = hsv = xyz = "N/A"

            h, l, s = colorsys.rgb_to_hls(*[v / 255 for v in rgb])
            hsl = (round(h * 360), round(s * 100), round(l * 100))
        except Exception as e:
            print(f"Error in color command: {e}")
            return await ctx.send(
                container=discord.ui.Container(
                    discord.ui.TextDisplay(content=f"Error in color command: {e}"),
                )
            )

        url = f"https://singlecolorimage.com/get/{hex_val}/600x100"

        container = discord.ui.Container(
            discord.ui.TextDisplay(
                content=f"### Color {hexcode.upper()}",
            ),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay(
                content=f"**Name:** {color_display}\n**RGB:** `{rgb}`\n**HSL:** `{hsl}`\n**CMYK:** `{cmyk}`\n**HSV:** `{hsv}`\n**XYZ:** `{xyz}`"
            ),
        )
        container.add_item(
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small)
        )
        container.add_item(discord.ui.MediaGallery(discord.MediaGalleryItem(media=url)))
        container.accent_colour = discord.Colour(int(f"0x{hexcode}", 16))

        view = discord.ui.LayoutView()
        view.add_item(container)
        await ctx.send(view=view)

    @hybrid_group(
        name="sticky", aliases=["stickynote", "note"], description="Sticky notes"
    )
    async def sticky(self, ctx: Context):
        """Sticky notes"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(self.sticky)

    @sticky.command(
        name="create", aliases=["add", "new"], description="Create a sticky note"
    )
    @app_commands.describe(
        note="The note to create",
        channel="The channel to create the sticky note in",
        rate="Number of messages between each sticky note",
    )
    @has_permissions(manage_guild=True, manage_webhooks=True)
    async def sticky_create(
        self,
        ctx: Context,
        *,
        note: str,
        channel: discord.TextChannel = None,
        rate: int = 5,
    ):
        """Create a sticky note"""
        target_channel = channel or ctx.channel

        clean_note = re.sub(r"<@[!&]?\d+>", "", note)
        clean_note = re.sub(r"@(everyone|here)", "", clean_note, flags=re.IGNORECASE)
        clean_note = clean_note.strip()

        if not clean_note:
            return await ctx.send("The note cannot be empty after removing mentions.")

        if target_channel.id not in self.sticky_counters:
            self.sticky_counters[target_channel.id] = 0

        async with self.bot.db.acquire() as conn:
            existing = await conn.fetchrow(
                """
                SELECT * FROM sticky_notes 
                WHERE guild_id = $1 AND channel_id = $2
                """,
                ctx.guild.id,
                target_channel.id,
            )

            if existing:
                await conn.execute(
                    """
                    UPDATE sticky_notes 
                    SET rate = $1, note = $2 
                    WHERE guild_id = $3 AND channel_id = $4
                    """,
                    rate,
                    clean_note,
                    ctx.guild.id,
                    target_channel.id,
                )
            else:
                await conn.execute(
                    """
                    INSERT INTO sticky_notes (guild_id, channel_id, rate, note)
                    VALUES ($1, $2, $3, $4)
                    """,
                    ctx.guild.id,
                    target_channel.id,
                    rate,
                    clean_note,
                )

        webhooks = await target_channel.webhooks()
        webhook = next((w for w in webhooks if w.name.startswith("sticky-")), None)
        if not webhook:
            short_id = str(target_channel.id)[-4:]
            webhook = await target_channel.create_webhook(name=f"sticky-{short_id}")

        sent_message = await webhook.send(
            clean_note,
            username="vortex Sticky Note",
            avatar_url=ctx.guild.icon.url if ctx.guild.icon else None,
            wait=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

        self.last_sticky_messages[target_channel.id] = sent_message.id

        container = ui.Container()
        container.add_item(ui.TextDisplay(content=f"Sticky note created."))
        container.add_item(
            ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small)
        )
        container.add_item(
            ui.TextDisplay(
                content=f"Channel: {target_channel.mention}\nRate: {rate} messages\nNote: {clean_note}"
            )
        )
        container.accent_colour = discord.Colour(0xFFFFFF)
        view = ui.LayoutView()
        view.add_item(container)
        await ctx.send(view=view)

    @sticky.command(
        name="delete",
        aliases=["remove", "del", "rm"],
        description="Delete a sticky note",
    )
    @has_permissions(manage_guild=True, manage_webhooks=True)
    async def sticky_delete(self, ctx: Context, channel: discord.TextChannel = None):
        """Delete a sticky note"""
        target_channel = channel or ctx.channel

        async with self.bot.db.acquire() as conn:
            await conn.execute(
                """
                DELETE FROM sticky_notes 
                WHERE guild_id = $1 AND channel_id = $2
                """,
                ctx.guild.id,
                target_channel.id,
            )

        if target_channel.id not in self.sticky_counters:
            return await ctx.send("No sticky note found for this channel.")

        webhooks = await target_channel.webhooks()
        webhook = next((w for w in webhooks if w.name.startswith("sticky-")), None)
        if webhook:
            await webhook.delete()

        self.sticky_counters.pop(target_channel.id, None)
        self.last_sticky_messages.pop(target_channel.id, None)

        container = ui.Container()
        container.add_item(ui.TextDisplay(content=f"Sticky note deleted."))
        container.accent_colour = discord.Colour(0xFFFFFF)
        view = ui.LayoutView()
        view.add_item(container)
        await ctx.send(view=view)

    @sticky.command(
        name="deleteall",
        aliases=["removeall", "delall", "reset"],
        description="Delete all sticky notes",
    )
    @has_permissions(manage_guild=True, manage_webhooks=True)
    async def sticky_deleteall(self, ctx: Context):
        """Delete all sticky notes"""
        async with self.bot.db.acquire() as conn:
            await conn.execute(
                """
                DELETE FROM sticky_notes 
                WHERE guild_id = $1
                """,
                ctx.guild.id,
            )

        deleted_webhooks = 0
        for channel in ctx.guild.text_channels:
            try:
                webhooks = await channel.webhooks()
                for webhook in webhooks:
                    if webhook.name.startswith("sticky-"):
                        await webhook.delete(reason="Deleting all sticky notes")
                        deleted_webhooks += 1
            except:
                continue

        self.sticky_counters.clear()
        self.last_sticky_messages.clear()

        container = ui.Container()
        container.add_item(
            ui.TextDisplay(
                content=f"Deleted all sticky notes and {deleted_webhooks} webhook(s)."
            )
        )
        container.accent_colour = discord.Colour(0xFFFFFF)
        view = ui.LayoutView()
        view.add_item(container)
        await ctx.send(view=view)

    # @sticky.command(name="list", aliases=["ls", "all"], description="List all sticky notes")
    # @has_permissions(manage_guild=True)
    # async def sticky_list(self, ctx: Context):
    #     """List all sticky notes"""
    #     async with self.bot.db.acquire() as conn:
    #         rows = await conn.fetch(
    #             """
    #             SELECT * FROM sticky_notes
    #             WHERE guild_id = $1
    #             """,
    #             ctx.guild.id
    #         )

    #     if not rows:
    #         return await ctx.send("No sticky notes found.")

    #     container = ui.Container()
    #     container.add_item(
    #         ui.TextDisplay(
    #             content="Sticky notes list"
    #         )
    #     )
    #     container.add_item(
    #         ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small)
    #     )
    #     for row in rows:
    #         container.add_item(
    #             ui.TextDisplay(
    #                 content=f"Channel: {row['channel_id']}\nRate: {row['rate']} messages\nNote: {row['note']}"
    #             )
    #         )

    #     button = ui.Button(
    #         style=discord.ButtonStyle.gray,
    #         label="Delete All",
    #         custom_id=f"delete_all_{ctx.message.id}"
    #     )

    #     async def button_callback(interaction: discord.Interaction):
    #         if interaction.user.id != ctx.author.id:
    #             return await interaction.response.send_message("You didn't create this message!", ephemeral=True)

    #         await interaction.response.defer()

    #         async with self.bot.db.acquire() as conn:
    #             await conn.execute(
    #                 """
    #                 DELETE FROM sticky_notes
    #                 WHERE guild_id = $1
    #                 """,
    #                 ctx.guild.id
    #             )

    #         self.sticky_counters.clear()
    #         self.last_sticky_messages.clear()

    #         container = ui.Container()
    #         container.add_item(
    #             ui.TextDisplay(
    #                 content="All sticky notes have been deleted."
    #             )
    #         )
    #         container.accent_colour = discord.Colour(0x2ecc71)
    #         view = ui.LayoutView()
    #         view.add_item(container)
    #         await interaction.followup.edit_message(interaction.message.id, view)

    #     button.callback = button_callback
    #     container.add_item(button)

    #     container.accent_colour = discord.Colour(0xFFFFFF)
    #     view = ui.LayoutView()
    #     view.add_item(container)

    #     await ctx.send(view=view)

    @Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        async with self.bot.db.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM sticky_notes 
                WHERE channel_id = $1
                """,
                message.channel.id,
            )

            for row in rows:
                if message.channel.id not in self.sticky_counters:
                    self.sticky_counters[message.channel.id] = 0

                self.sticky_counters[message.channel.id] += 1

                if self.sticky_counters[message.channel.id] >= row["rate"]:
                    self.sticky_counters[message.channel.id] = 0

                    webhooks = await message.channel.webhooks()
                    webhook = next(
                        (w for w in webhooks if w.name.startswith("sticky-")), None
                    )

                    if not webhook:
                        webhook = await message.channel.create_webhook(
                            name="sticky-note"
                        )

                    if message.channel.id in self.last_sticky_messages:
                        try:
                            last_message = await message.channel.fetch_message(
                                self.last_sticky_messages[message.channel.id]
                            )
                            if last_message:
                                await last_message.delete()
                        except:
                            pass

                    try:
                        sent_message = await webhook.send(
                            row["note"],
                            username="vortex Sticky Note",
                            avatar_url=(
                                message.guild.icon.url if message.guild.icon else None
                            ),
                            wait=True,
                        )
                        self.last_sticky_messages[message.channel.id] = sent_message.id
                    except Exception as e:
                        print(f"Error sending sticky note: {e}")

    @hybrid(name="gif", description="Convert image to Gif")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(image="The image to convert to GIF")
    async def gif(self, ctx, image: discord.Attachment):
        input_path = f"/tmp/{image.id}"
        output_path = f"/tmp/{image.id}.gif"

        await image.save(input_path)

        try:
            result = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    input_path,
                    "-vf",
                    "format=pal8,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse=dither=none",
                    output_path,
                ],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                await ctx.send(f"Error converting image: {result.stderr}")
                os.remove(input_path)
                return

            if not os.path.exists(output_path):
                await ctx.send("GIF creation failed, fix it peon.")
                os.remove(input_path)
                return

            await ctx.send(file=discord.File(output_path))

        except Exception as e:
            await ctx.send(f"Error: {str(e)}")
        finally:
            if os.path.exists(input_path):
                os.remove(input_path)
            if os.path.exists(output_path):
                os.remove(output_path)
