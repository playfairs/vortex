import discord
from discord import app_commands
from discord.ext import commands
from discord.ext.commands import (
    Cog,
    command,
    group,
    has_permissions,
    cooldown,
    BucketType,
    hybrid_group,
    Context,
)
import asyncpg
from datetime import datetime, timedelta
from config import DISCORD
import io

from vortex import vortex
import random
import aiohttp
import os


class Reposters(Cog, description="View commands in reposters."):
    def __init__(self, bot: vortex):
        self.bot = bot
        self.db = self.bot.db
        self.session = aiohttp.ClientSession()

    async def cog_load(self):
        self.db = self.bot.db
        await self.create_tables()

    async def create_tables(self):
        await self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS tiktok_reposter (
            guild_id BIGINT PRIMARY KEY,
            enabled BOOLEAN DEFAULT FALSE
            );
            """
        )

    @hybrid_group(name="tiktok", aliases=["tt"], invoke_without_command=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def tiktok(self, ctx):
        return await ctx.send_help(ctx.command)

    @tiktok.command(name="user", description="Get TikTok user info.")
    @app_commands.describe(username="The TikTok username.")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def tiktok_user(self, ctx: Context, username: str = None):
        """Get tiktok user information."""
        if username is None:
            return await ctx.send("Please provide a TikTok username.")

        try:
            async with self.session.get(
                f"https://socials.compile.best/api/tiktok/{username}"
            ) as res:
                if res.ok:
                    data = await res.json()

                    signature = data.get("signature")
                    if signature:
                        lines = signature.splitlines()
                        description = "\n".join(f"-# {line}" for line in lines if line)[
                            :250
                        ]
                    else:
                        description = None

                    fields = []
                    fields.append(
                        {
                            "name": "Followers",
                            "value": f"`{self.bot.format_number(data.get('followers'))}`",
                            "inline": True,
                        }
                    )
                    fields.append(
                        {
                            "name": "Following",
                            "value": f"`{self.bot.format_number(data.get('following'))}`",
                            "inline": True,
                        }
                    )

                    likes = data.get("likes")
                    fields.append(
                        {
                            "name": "Likes",
                            "value": f"`{self.bot.format_number(likes)}`",
                            "inline": True,
                        }
                    )

                    embed = discord.Embed(
                        title=f"{data.get('unique_id')} ({data.get('nickname')})",
                        url=f"https://www.tiktok.com/@{data.get('unique_id')}",
                        description=description,
                    )
                    embed.set_thumbnail(url=data.get("avatar_larger"))
                    embed.set_footer(text="tiktok.com")
                    for field in fields:
                        embed.add_field(
                            name=field["name"],
                            value=field["value"],
                            inline=field.get("inline", True),
                        )
                    return await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

    @tiktok.command(name="repost", description="Repost a TikTok video.")
    @app_commands.describe(url="The link to the TikTok video.")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def tiktok_repost(self, ctx: Context, url: str = None):
        """Repost a TikTok video."""
        if url is None:
            return await ctx.send(f"Please provide a link to a TikTok video.")

        try:
            async with self.session.get(
                f"https://tikwm.com/api/?url={url}"
            ) as response:
                if response.status != 200:
                    return await ctx.send(f"Failed to fetch the TikTok video UwU.")
                data = await response.json()

                video_url = data["data"]["play"]
                likes = data["data"]["digg_count"]
                comments = data["data"]["comment_count"]
                shares = data["data"]["share_count"]
                description = data["data"]["title"]
                username = data["data"]["author"]["unique_id"]
                avatar = data["data"]["author"]["avatar"]

                async with self.session.get(video_url) as r:
                    video_data = await r.read()

                    video = io.BytesIO(video_data)

                    if isinstance(ctx, commands.Context):
                        try:
                            await ctx.message.delete()
                        except discord.Forbidden:
                            pass

                    embed = discord.Embed(
                        description=description,
                        color=discord.Color.random(),
                    )
                    embed.set_author(
                        name=f"{username} on TikTok",
                        icon_url=avatar,
                    )
                    embed.set_footer(
                        text=f"❤️ {int(likes)} | 💬 {int(comments)} | 🔗 {int(shares)}",
                        icon_url="https://www.svgrepo.com/show/327400/logo-tiktok.svg",
                    )

                    await ctx.send(
                        embed=embed, file=discord.File(video, filename="tiktok.mp4")
                    )
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

    @tiktok.command(name="enable", description="Enable TikTok reposting in the server.")
    @has_permissions(manage_guild=True)
    @app_commands.describe()
    async def tiktok_enable(self, ctx: Context):
        await self.bot.db.execute(
            """
            INSERT INTO tiktok_reposter (guild_id, enabled) VALUES ($1, TRUE)
            ON CONFLICT (guild_id) DO UPDATE SET enabled = TRUE;
            """,
            ctx.guild.id,
        )
        await ctx.send("TikTok reposting has been enabled for this server.")

    @tiktok.command(
        name="disable", description="Disable TikTok reposting in the server."
    )
    @has_permissions(manage_guild=True)
    @app_commands.describe()
    async def tiktok_disable(self, ctx: Context):
        await self.bot.db.execute(
            """
            UPDATE tiktok_reposter SET enabled = FALSE WHERE guild_id = $1;
            """,
            ctx.guild.id,
        )
        await ctx.send("TikTok reposting has been disabled for this server.")

    @Cog.listener("on_message")
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if not message.guild:
            return

        if message.type == discord.MessageType.default:
            row = await self.bot.db.fetchrow(
                "SELECT enabled FROM tiktok_reposter WHERE guild_id = $1",
                message.guild.id,
            )

            if row and row["enabled"]:
                if "tiktok.com" in message.content:
                    async with self.session.get(
                        f"https://tikwm.com/api/?url={message.content}"
                    ) as response:
                        if response.status != 200:
                            return await message.channel.send(
                                f"Failed to fetch the TikTok video UwU."
                            )
                        data = await response.json()

                        video_url = data["data"]["play"]
                        likes = data["data"]["digg_count"]
                        comments = data["data"]["comment_count"]
                        shares = data["data"]["share_count"]
                        description = data["data"]["title"]
                        username = data["data"]["author"]["unique_id"]
                        avatar = data["data"]["author"]["avatar"]

                        async with self.session.get(video_url) as r:
                            video_data = await r.read()

                            video = io.BytesIO(video_data)

                            await message.delete()

                            embed = discord.Embed(
                                description=description,
                                color=discord.Color.random(),
                            )
                            embed.set_author(
                                name=f"{username} on TikTok",
                                icon_url=avatar,
                            )
                            embed.set_footer(
                                text=f"❤️ {int(likes)} | 💬 {int(comments)} | 🔗 {int(shares)}",
                                icon_url="https://www.svgrepo.com/show/327400/logo-tiktok.svg",
                            )

                            await message.channel.send(
                                embed=embed,
                                file=discord.File(video, filename="tiktok.mp4"),
                            )

    @hybrid_group(name="instagram", aliases=["ig"], invoke_without_command=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def instagram(self, ctx):
        return await ctx.send_help(ctx.command)

    @instagram.command(name="user", description="Get Instagram user info.")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def instagram_user(self, ctx: Context, *, username: str = None):
        """Get Instagram user information."""
        if username is None:
            return await ctx.send("Please provide an Instagram username.")

        try:
            async with self.session.get(
                f"https://socials.compile.best/api/instagram/{username}"
            ) as response:
                if not response.ok:
                    return await ctx.send(f"API timed out, user not found?")
                if response.ok:
                    data = await response.json()

                    username = data.get("username")

                    fields = []
                    fields.append(
                        {
                            "name": "Followers",
                            "value": f"`{self.bot.format_number(data.get('follower_count'))}`",
                            "inline": True,
                        }
                    )
                    fields.append(
                        {
                            "name": "Following",
                            "value": f"`{self.bot.format_number(data.get('following_count'))}`",
                            "inline": True,
                        }
                    )
                    biography = data.get("biography")
                    if biography:
                        lines = biography.splitlines()
                        description = "\n".join(f"-# {line}" for line in lines if line)[
                            :250
                        ]
                    else:
                        description = None
                    embed = discord.Embed(
                        title=username,
                        url=f"https://instagram.com/{username}",
                        description=description,
                    )
                    embed.set_thumbnail(url=data.get("profile_pic_url"))
                    embed.set_footer(
                        text="instagram.com",
                        icon_url="https://cdn.discordapp.com/emojis/1404538960042000414.png",
                    )
                    for field in fields:
                        embed.add_field(
                            name=field["name"],
                            value=field["value"],
                            inline=field.get("inline", True),
                        )
                    return await ctx.send(embed=embed)

        except Exception as e:
            return await ctx.send("An error occurred while fetching user information.")

    @instagram.command(name="trending", aliases=["fyp", "doomscroll"])
    async def instagram_trending(self, ctx: Context):
        """Get a trending instagram post"""
        async with ctx.typing():
            async with self.session.get(
                "http://socials.compile.best/api/instagram/trending"
            ) as response:
                if not response.ok:
                    return await ctx.send("API timed out.")
                data = await response.json()
                item = data[0] if isinstance(data, list) and data else data

                embed = discord.Embed(
                    description=(
                        item.get("caption").get("text")[:250]
                        if item.get("caption")
                        else None
                    ),
                )
                embed.set_author(
                    name=item.get("user").get("username"),
                    icon_url=item.get("user").get("profile_pic_url"),
                )
                embed.set_footer(text=f"❤️ {item.get('like_count'):,} | instagram.com")

                vv = item.get("video_versions")
                if vv:
                    try:
                        url_101 = next(v["url"] for v in vv if v.get("type") == 101)
                    except StopIteration:
                        url_101 = vv[0]["url"]

                    async with self.session.get(url_101) as vresp:
                        video_bytes = await vresp.read()

                    await ctx.reply(
                        embed=embed,
                        file=discord.File(
                            io.BytesIO(video_bytes), filename="trending.mp4"
                        ),
                    )
                else:
                    await ctx.reply(embed=embed)
