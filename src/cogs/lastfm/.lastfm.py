# Backup file since I can't test on the testing bot, since it doesn't have the Database

import discord
import pylast
import aiohttp
import os
import logging

from typing import Optional
from discord.ext import commands
from discord.ext.commands import group, Cog, Context, command, hybrid_group
from discord.ext.commands import hybrid_command as hybrid
from discord import app_commands, ui
from discord.ui import Button, View
from discord import ButtonStyle
from urllib.parse import quote_plus, urlencode
from datetime import datetime
from config import BUTTONS
from vortex import vortex

from managers.classes import Media, Emojis, Colors

logger = logging.getLogger(__name__)


class LastFM(Cog, description="View commands in LastFM."):
    def __init__(self, bot: vortex):
        self.bot = bot
        self.custom_commands = {}
        self.api_key = os.getenv("LASTFM_KEY")
        self.base_url = os.getenv("LASTFM_BASE_URL")
        self.network = pylast.LastFMNetwork(
            api_key=self.api_key, api_secret=os.getenv("LASTFM_SECRET")
        )
        self.db = None

    async def get_lastfm_username(self, user_id: int) -> Optional[str]:
        """Get Last.fm username for a Discord user"""
        record = await self.bot.db.fetchrow(
            "SELECT lastfm_name FROM lastfm_tokens WHERE discord_id = $1",
            user_id,
        )
        return record["lastfm_name"] if record else None

    async def create_tables(self):
        await self.bot.db.execute(
            """
            CREATE TABLE IF NOT EXISTS lastfm_tokens (
                discord_id BIGINT PRIMARY KEY,
                lastfm_name TEXT NOT NULL
            )
            """
        )

    async def fetch_lastfm_data(self, method: str, params: dict) -> Optional[dict]:
        """Generic method to fetch data from Last.fm API"""
        params.update({"method": method, "api_key": self.api_key, "format": "json"})

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(self.base_url, params=params) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        print(f"Error {response.status}: {await response.text()}")
                        return None
            except Exception as e:
                print(f"Error fetching Last.fm data: {e}")
                return None

    async def error_embed(self, ctx, message: str):
        """Helper method to send error embeds"""
        embed = discord.Embed(description=message, color=discord.Color.red())
        await ctx.send(embed=embed)

    @hybrid_group(
        name="lastfm",
        aliases=["lf", "lfm"],
        description="Base command for LastFM related commands.",
    )
    async def lastfm(self, ctx: Context):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(self.lastfm)

    @lastfm.command(
        name="auth",
        description="Authenticate with Last.fm to link your account.",
    )
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def auth(self, ctx: Context):
        """Start the Last.fm authentication process"""
        if ctx.guild is not None:
            try:
                dm_channel = await ctx.author.create_dm()
                await ctx.send(
                    "Check your DMs for the authentication link!", ephemeral=True
                )
            except discord.Forbidden:
                await ctx.send(
                    "I couldn't send you a DM. Please enable DMs and try again.",
                    ephemeral=True,
                )
                return
        else:
            dm_channel = ctx.channel

        auth_url = f"https://lf.playfairs.cc/lastfm/create"
        headers = {
            "Content-Type": "application/json",
            "authorization": "9203cc0f7ef47b2e1f35653f5428b12451bdfbcee5b10387332de16d571eefdd",
        }
        data = {"discord_id": str(ctx.author.id)}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    auth_url, headers=headers, json=data
                ) as response:
                    if response.status != 200:
                        await self.error_embed(
                            ctx,
                            "Failed to start authentication. Please try again later.",
                            ephemeral=True,
                        )
                        return

                    result = await response.json()
                    auth_url = result.get("url")

                    if not auth_url:
                        await self.error_embed(
                            ctx,
                            "Failed to get authentication URL. Please try again later.",
                            ephemeral=True,
                        )
                        return

                    view = discord.ui.View()
                    view.add_item(
                        discord.ui.Button(
                            label="Authorize with Last.fm",
                            url=auth_url,
                            style=discord.ButtonStyle.url,
                        )
                    )

                    embed = discord.Embed(
                        title="Last.fm Authentication",
                        description="Click the button below to authorize with Last.fm. This will allow the bot to access your recently played tracks.",
                        color=discord.Color.green(),
                    )
                    embed.set_footer(text="This link will expire in 1 hour.")

                    await dm_channel.send(embed=embed, view=view)

        except Exception as e:
            logger.error(f"Error during Last.fm auth: {e}")
            await self.error_embed(
                ctx,
                "An error occurred during authentication. Please try again later.",
                ephemeral=True,
            )

    @hybrid(name="fm", description="Shows currently playing track via the LastFM API.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(user="The user to show the currently playing track for.")
    async def fm(self, ctx: Context, user: Optional[discord.User] = None):
        """Shows currently playing track via the LastFM API."""
        if ctx.guild:
            await ctx.typing()
        target = user or ctx.author
        lastfm_username = await self.get_lastfm_username(target.id)

        if not lastfm_username:
            await self.error_embed(
                ctx,
                f"{target.mention} you have not authenticated with LastFM. Run `/lastfm auth` to authenticate.",
            )
            return

        try:
            data = await self.fetch_lastfm_data(
                "user.getrecenttracks", {"user": lastfm_username, "limit": 1}
            )

            if not data or "error" in data:
                error = data.get("error", "Unknown Error")
                await self.error_embed(
                    ctx,
                    f"Error fetching tracks: Check your privacy settings on LastFM.",
                )
                return

            track = (
                data["recenttracks"]["track"][0]
                if data["recenttracks"]["track"]
                else {}
            )
            is_now_playing = track.get("@attr", {}).get("nowplaying") == "true"

            artist = track.get("artist", {}).get("#text", "Unknown Artist")
            song = track.get("name", "Unknown Track")
            album = track.get("album", {}).get("#text", "Unknown Album")
            image_url = track.get("image", [{}])[-1].get("#text", None)

            all_artists = [artist]
            if "artist" in track and isinstance(track["artist"], list):
                all_artists.extend(
                    [
                        a.get("#text", "Unknown Artist")
                        for a in track["artist"]
                        if a.get("#text")
                    ]
                )

            all_artists = sorted(set(all_artists))

            main_artist = artist
            additional_artists = [a for a in all_artists if a != main_artist]

            artist_data = (
                await self.fetch_lastfm_data(
                    "artist.getInfo",
                    {"artist": main_artist, "username": lastfm_username},
                )
                or {}
            )

            user_info = (
                await self.fetch_lastfm_data("user.getInfo", {"user": lastfm_username})
                or {}
            )

            track_url = f"https://www.last.fm/music/{quote_plus(main_artist)}/_/{quote_plus(song)}"
            lastfm_profile_url = f"https://www.last.fm/user/{lastfm_username}"

            artist_plays = int(
                artist_data.get("artist", {}).get("stats", {}).get("userplaycount", 0)
            )
            total_scrobbles = int(user_info.get("user", {}).get("playcount", 0))

            description = [
                f"**[{song}]({track_url})**",
                f"> **{main_artist}** · *{album}*" if album else main_artist,
            ]

            embed = discord.Embed(description="\n".join(description), color=0xFFFFFF)

            if image_url:
                embed.set_thumbnail(url=image_url)

            avatar_url = (
                user_info.get("user", {}).get("image", [{}])[-1].get("#text") or None
            )

            author_args = {
                "name": f"{'Now playing' if is_now_playing else 'Last played'} - {target.display_name}",
                "url": lastfm_profile_url,
            }
            if avatar_url:
                author_args["icon_url"] = avatar_url
            embed.set_author(**author_args)

            footer_text = (
                f"{artist_plays} artist scrobbles · {total_scrobbles} total scrobbles"
            )
            embed.set_footer(text=footer_text)

            await ctx.send(embed=embed)

        except Exception as e:
            logging.error(f"Error fetching track information: {str(e)}")
            print(f"Error fetching track information: {str(e)}")
            return

    @lastfm.command(
        name="cover",
        aliases=["coverart", "c"],
        description="Get the cover art for the track you are currently listening to.",
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def cover(self, ctx: Context, user: Optional[discord.Member] = None):
        if user is None:
            user = ctx.author

        username = await self.get_lastfm_username(user.id)
        if not username:
            await self.error_embed(
                ctx,
                f"{BUTTONS.CUSTOM_EMOJIS['cancel']} {user.mention}: This user has not set their LastFM username. Run `;lf set <username>` to set it.",
            )
            return

        try:
            data = await self.fetch_lastfm_data(
                "user.getrecenttracks", {"user": username, "limit": 1}
            )
            if not data or "error" in data:
                await self.error_embed(
                    ctx,
                    f"{BUTTONS.CUSTOM_EMOJIS['cancel']} {user.mention}: Failed to fetch cover art. Please try again later.",
                )
                return

            track = data.get("recenttracks", {}).get("track", [{}])[0]
            image_url = track.get("image", [{}])[-1].get("#text")
            album = track.get("album", {}).get("#text")
            if not image_url or not album:
                await self.error_embed(
                    ctx,
                    f"{BUTTONS.CUSTOM_EMOJIS['cancel']} {user.mention}: Failed to fetch cover art. Please try again later.",
                )
                return

            embed = discord.Embed(description=f"{album}", color=0xFFFFFF)
            embed.set_image(url=image_url)

            base_url = image_url.rsplit(".", 1)[0]

            buttons = [
                Button(label="PNG", style=ButtonStyle.link, url=f"{base_url}.png"),
                Button(label="JPG", style=ButtonStyle.link, url=f"{base_url}.jpg"),
                Button(label="GIF", style=ButtonStyle.link, url=f"{base_url}.gif"),
            ]
            view = View()
            for button in buttons:
                view.add_item(button)
            await ctx.send(embed=embed, view=view)
        except Exception as e:
            await self.error_embed(
                ctx,
                f"{BUTTONS.CUSTOM_EMOJIS['cancel']} {user.mention}: Failed to fetch cover art. Please try again later.",
            )
            print(f"Error fetching cover art: {str(e)}")

    @lastfm.command(
        name="scrobbles",
        aliases=["sc", "plays"],
        description="Get the total scrobbles for a specific user.",
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.describe(user="The user to get the total scrobbles for.")
    async def scrobbles(self, ctx: Context, user: Optional[discord.Member] = None):
        if user is None:
            user = ctx.author

        username = await self.get_lastfm_username(user.id)
        if not username:
            await self.error_embed(
                ctx,
                f"{BUTTONS.CUSTOM_EMOJIS['cancel']} {user.mention}: This user has not set their LastFM username. Run `;lf set <username>` to set it.",
            )
            return

        data = await self.fetch_lastfm_data("user.getinfo", {"user": username})
        plays = int(data.get("user", {}).get("playcount", 0))
        await ctx.send(f"{user.mention} has `{plays}` total scrobbles.")

    @lastfm.command(
        name="trackplays",
        aliases=["tp"],
        description="Get the total scrobbles for a specific track.",
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.describe(
        user="The user to get the total scrobbles for.",
        track="The track.",
    )
    async def trackplays(
        self,
        ctx: Context,
        user: Optional[discord.Member] = None,
        track: str = None,
    ):
        if user is None:
            user = ctx.author

        username = await self.get_lastfm_username(user.id)
        if not username:
            await self.error_embed(
                ctx,
                f"{BUTTONS.CUSTOM_EMOJIS['cancel']} {user.mention}: This user has not set their LastFM username. Run `;lf set <username>` to set it.",
            )
            return

        if track is None:
            data = await self.fetch_lastfm_data(
                "user.getrecenttracks", {"user": username, "limit": 1}
            )
            if not data or "error" in data:
                await self.error_embed(
                    ctx,
                    f"{BUTTONS.CUSTOM_EMOJIS['cancel']} {user.mention}: Failed to fetch current track. Please try again later.",
                )
                return

            track = data.get("recenttracks", {}).get("track", [{}])[0]
            track = track.get("name")
            if not track:
                await self.error_embed(
                    ctx,
                    f"{BUTTONS.CUSTOM_EMOJIS['cancel']} {user.mention}: Failed to fetch current track. Please try again later.",
                )
                return

        data = await self.fetch_lastfm_data(
            "user.getrecenttracks",
            {"user": username, "limit": 1, "track": track},
        )
        plays = int(
            data.get("recenttracks", {}).get("track", [{}])[0].get("playcount", 0)
        )
        await ctx.send(f"{user.mention} has `{plays}` total scrobbles for {track}.")
