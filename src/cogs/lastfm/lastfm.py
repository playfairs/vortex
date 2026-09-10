# A femboy twink wrote this whole cog btw >_< im so kawaii :3

import discord
import pylast
import aiohttp
import os
import logging
import base64
import hashlib
import asyncio

from typing import Optional
from discord.ext import commands
from discord.ext.commands import group, Cog, Context, command, hybrid_group
from discord.ext.commands import hybrid_command as hybrid
from discord import app_commands, ui
from discord.ui import Button, View
from discord import ButtonStyle, Embed, Color
from urllib.parse import quote_plus, urlencode
from datetime import datetime
from config import BUTTONS
from vortex import vortex

from managers.classes import Media, Emojis, Colors
from .classes import ArtistPaginator, AlbumPaginator, TrackPaginator

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
        self.spotify_token = os.getenv("SPOTIFY_CLIENT_ID")
        self.spotify_secret = os.getenv("SPOTIFY_CLIENT_SECRET")

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

    async def fetch_lastfm_data(
        self, method: str, params: dict, use_post: bool = False
    ) -> Optional[dict]:
        """Generic method to fetch data from Last.fm API"""
        params.update({"method": method, "api_key": self.api_key, "format": "json"})

        if use_post:
            params["api_sig"] = self._generate_signature(params)
            params["sk"] = await self.get_session_key(params.get("username"))

        async with aiohttp.ClientSession() as session:
            try:
                if use_post:
                    async with session.post(self.base_url, data=params) as response:
                        if response.status == 200:
                            return await response.json()
                        else:
                            error_text = await response.text()
                            logger.error(
                                f"Last.fm API error {response.status}: {error_text}"
                            )
                            return None
                else:
                    async with session.get(self.base_url, params=params) as response:
                        if response.status == 200:
                            return await response.json()
                        else:
                            error_text = await response.text()
                            logger.error(
                                f"Last.fm API error {response.status}: {error_text}"
                            )
                            return None
            except Exception as e:
                logger.error(f"Error fetching Last.fm data: {e}")
                return None

    def _generate_signature(self, params: dict) -> str:
        """Generate API signature for authenticated requests"""
        params_copy = {
            k: v for k, v in params.items() if k not in ["format", "callback"]
        }

        signature_string = "".join(f"{k}{v}" for k, v in sorted(params_copy.items()))
        signature_string += os.getenv("LASTFM_SECRET")

        return hashlib.md5(signature_string.encode("utf-8")).hexdigest()

    async def get_session_key(self, username: str) -> Optional[str]:
        """Get the session key for a user"""
        if not username:
            return None

        record = await self.bot.db.fetchrow(
            "SELECT session_key FROM lastfm_sessions WHERE lastfm_name = $1 AND expires_at > NOW()",
            username,
        )

        if record and record["session_key"]:
            return record["session_key"]

        return None

    async def error_embed(self, ctx, message: str, ephemeral: bool = False):
        """Helper method to send error embeds"""
        embed = discord.Embed(description=message, color=discord.Color.red())
        if hasattr(ctx, "send"):
            return await ctx.send(embed=embed, ephemeral=ephemeral)
        return await ctx.send(embed=embed)

    async def get_spotify_cover(self, artist: str, track: str) -> Optional[str]:
        """Get cover art URL from Spotify's CDN"""
        if (
            not artist
            or not track
            or artist == "Unknown Artist"
            or track == "Unknown Track"
        ):
            logger.warning(f"Invalid artist or track: artist={artist}, track={track}")
            return None

        if not self.spotify_token or not self.spotify_secret:
            logger.warning("Spotify credentials not configured")
            return None

        try:
            auth_url = "https://accounts.spotify.com/api/token"
            auth_string = f"{self.spotify_token}:{self.spotify_secret}"
            auth_bytes = auth_string.encode("ascii")
            base64_auth = base64.b64encode(auth_bytes).decode("ascii")

            auth_header = {"Authorization": f"Basic {base64_auth}"}
            auth_data = {"grant_type": "client_credentials"}

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    auth_url, headers=auth_header, data=auth_data
                ) as auth_response:
                    if auth_response.status != 200:
                        error_text = await auth_response.text()
                        logger.error(
                            f"Spotify auth error {auth_response.status}: {error_text}"
                        )
                        return None

                    token_data = await auth_response.json()
                    access_token = token_data.get("access_token")

                    if not access_token:
                        logger.error("No access token received from Spotify")
                        return None

                search_url = "https://api.spotify.com/v1/search"
                headers = {"Authorization": f"Bearer {access_token}"}
                params = {
                    "q": f"artist:{artist} track:{track}",
                    "type": "track",
                    "limit": 1,
                    "market": "US",
                }

                async with session.get(
                    search_url, headers=headers, params=params
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(
                            f"Spotify API error {response.status}: {error_text}"
                        )
                        return None

                    data = await response.json()
                    tracks = data.get("tracks", {}).get("items", [])

                    if not tracks:
                        return None

                    track_data = tracks[0]

                    album_images = track_data.get("album", {}).get("images", [])

                    if album_images:
                        cover_url = album_images[0].get("url")
                        if cover_url:
                            return cover_url

                    return None

        except Exception as e:
            logger.error(f"Error in get_spotify_cover: {str(e)}", exc_info=True)
            return None

    async def get_artist_image(self, artist: str) -> Optional[str]:
        """Get artist image from Spotify"""
        if not artist or artist == "Unknown Artist":
            logger.warning(f"Invalid artist: {artist}")
            return None

        if not self.spotify_token or not self.spotify_secret:
            logger.warning("Spotify credentials not configured")
            return None

        try:
            auth_url = "https://accounts.spotify.com/api/token"
            auth_header = {
                "Authorization": f"Basic {base64.b64encode(f'{self.spotify_token}:{self.spotify_secret}'.encode()).decode()}"
            }
            auth_data = {"grant_type": "client_credentials"}

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    auth_url, headers=auth_header, data=auth_data
                ) as auth_response:
                    if auth_response.status != 200:
                        error_text = await auth_response.text()
                        logger.error(
                            f"Spotify auth error {auth_response.status}: {error_text}"
                        )
                        return None

                    token_data = await auth_response.json()
                    access_token = token_data.get("access_token")

                    if not access_token:
                        logger.error("No access token received from Spotify")
                        return None

                search_url = "https://api.spotify.com/v1/search"
                headers = {"Authorization": f"Bearer {access_token}"}
                params = {
                    "q": f"artist:{artist}",
                    "type": "artist",
                    "limit": 1,
                    "market": "US",
                }

                logger.debug(f"Searching Spotify for artist: {artist}")

                async with session.get(
                    search_url, headers=headers, params=params
                ) as response:
                    if response.status != 200:
                        return None

                    data = await response.json()
                    artists = data.get("artists", {}).get("items", [])

                    if not artists:
                        return None

                    artist_data = artists[0]

                    images = artist_data.get("images", [])
                    if images:
                        image_url = images[0].get("url")
                        if image_url:
                            return image_url

                    artist_id = artist_data.get("id")
                    if not artist_id:
                        return

                    top_tracks_url = (
                        f"https://api.spotify.com/v1/artists/{artist_id}/top-tracks"
                    )
                    async with session.get(
                        top_tracks_url, headers=headers, params={"market": "US"}
                    ) as tracks_response:
                        if tracks_response.status != 200:
                            error_text = await tracks_response.text()
                            logger.error(
                                f"Spotify API error {tracks_response.status} for top tracks: {error_text}"
                            )
                            return None

                        tracks_data = await tracks_response.json()
                        tracks = tracks_data.get("tracks", [])

                        if not tracks:
                            return None

                        album_images = tracks[0].get("album", {}).get("images", [])
                        if album_images:
                            image_url = album_images[0].get("url")
                            if image_url:
                                return image_url

                return None

        except Exception as e:
            return None

    async def format_time_ago(self, dt: datetime) -> str:
        """Format a datetime object into a human-readable relative time string."""
        now = datetime.now(dt.tzinfo)
        diff = now - dt

        if diff.days > 30:
            months = diff.days // 30
            return f"{months} month{'s' if months > 1 else ''} ago"
        elif diff.days > 0:
            return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
        elif diff.seconds >= 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif diff.seconds >= 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            return "just now"

    @hybrid_group(
        name="lastfm",
        aliases=["lf", "lfm"],
        description="Base command for LastFM related commands.",
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def lastfm(self, ctx: Context):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(self.lastfm)

    @lastfm.command(
        name="auth",
        description="Authenticate with Last.fm to link your account.",
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def auth(self, ctx: Context):
        """Start the Last.fm authentication process"""
        try:
            dm_channel = await ctx.author.create_dm()
            if ctx.guild is not None:
                try:
                    await ctx.send(
                        "Check your DMs for the authentication link.", ephemeral=True
                    )
                except discord.Forbidden:
                    pass
        except discord.Forbidden:
            try:
                await ctx.send(
                    "I couldn't send you a DM. Please enable DMs and try again.",
                    ephemeral=True,
                )
            except discord.Forbidden:
                pass
            return

        if ctx.guild is None:
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
                        color=discord.Color(0xFFFFFF),
                    )
                    embed.set_footer(text="This link will expire in 1 hour btw.")

                    await dm_channel.send(embed=embed, view=view)
        except Exception as e:
            if "Cannot send messages to this user" in str(e):
                await ctx.send(
                    "I couldn't send you a DM. Please enable DMs and try again.",
                    ephemeral=True,
                )
            else:
                raise

    @lastfm.command(
        name="logout",
        description="Logout of Last.fm.",
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def logout(self, ctx: Context):
        """Logout of Last.fm."""
        if ctx.guild:
            await ctx.typing()

        embed = discord.Embed(
            title="Log out of LastFM?",
            description="Are you sure you want to log out of LastFM? You will need to log back in to use the LastFM commands again.",
            color=discord.Color(0xFFFFFF),
        )

        view = discord.ui.View()
        view.add_item(
            discord.ui.Button(
                label="Logout", style=discord.ButtonStyle.red, custom_id="lastfm_logout"
            )
        )
        view.add_item(
            discord.ui.Button(
                label="Cancel",
                style=discord.ButtonStyle.green,
                custom_id="lastfm_cancel",
            )
        )

        message = await ctx.send(embed=embed, view=view)

        def check(interaction: discord.Interaction):
            return (
                interaction.user.id == ctx.author.id
                and interaction.message.id == message.id
            )

        try:
            interaction = await self.bot.wait_for(
                "interaction", check=check, timeout=30.0
            )
        except asyncio.TimeoutError:
            await message.edit(view=None)
            return

        if interaction.data["custom_id"] == "lastfm_logout":
            await self.bot.db.execute(
                "DELETE FROM lastfm_tokens WHERE discord_id = $1", ctx.author.id
            )
            await interaction.response.edit_message(
                content="Successfully logged out of LastFM.", embed=None, view=None
            )
        else:
            await interaction.response.edit_message(
                content="Logout cancelled.", embed=None, view=None
            )

    @hybrid(
        name="fm",
        aliases=["fuckme", "np", "nowplaying"],
        description="Shows currently playing track via the LastFM API.",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(user="The user to show the currently playing track for.")
    async def fm(self, ctx: Context, user: Optional[discord.User] = None):
        """Shows currently playing track via the LastFM API."""
        if ctx.interaction:
            await ctx.interaction.response.defer(thinking=True)
        elif ctx.guild:
            await ctx.typing()

        try:
            target = user or ctx.author
            lastfm_username = await self.get_lastfm_username(target.id)

            if not lastfm_username:
                return await self.error_embed(
                    ctx,
                    f"No Last.fm username found for {ctx.author.mention if user is None else user.mention}. Use `/lastfm auth` to set one up.",
                    ephemeral=True,
                )

            data = await self.fetch_lastfm_data(
                "user.getRecentTracks", {"user": lastfm_username, "limit": 1}
            )

            if (
                not data
                or "error" in data
                or not data.get("recenttracks", {}).get("track")
            ):
                error = data.get(
                    "error", "No recent tracks found or error fetching data"
                )
                return await self.error_embed(
                    ctx, f"Couldn't fetch recent tracks. Error: {error}", ephemeral=True
                )

            if not data["recenttracks"].get("track") or not isinstance(
                data["recenttracks"]["track"], list
            ):
                return await self.error_embed(
                    ctx,
                    "No recent tracks found or invalid track data received from Last.fm",
                    ephemeral=True,
                )

            track = data["recenttracks"]["track"][0]
            if not isinstance(track, dict):
                return await self.error_embed(
                    ctx,
                    "Invalid track data format received from Last.fm",
                    ephemeral=True,
                )

            is_now_playing = track.get("@attr", {}).get("nowplaying") == "true"
            artist = track.get("artist", {}).get("#text", "Unknown Artist")
            song = track.get("name", "Unknown Track")
            album = track.get("album", {}).get("#text", "Unknown Album")

            cover_url = await self.get_spotify_cover(artist, song)

            if not cover_url:
                lastfm_images = track.get("image", [])
                if lastfm_images and isinstance(lastfm_images, list):
                    lastfm_image = next(
                        (
                            img.get("#text")
                            for img in reversed(lastfm_images)
                            if img.get("#text")
                        ),
                        None,
                    )
                    if lastfm_image:
                        cover_url = lastfm_image

            if cover_url and cover_url.startswith("http:"):
                cover_url = cover_url.replace("http:", "https:", 1)

            artist_image_url = await self.get_artist_image(artist)
            if artist_image_url and artist_image_url.startswith("http:"):
                artist_image_url = artist_image_url.replace("http:", "https:", 1)

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
            artist_data = (
                await self.fetch_lastfm_data(
                    "artist.getInfo",
                    {"artist": main_artist, "username": lastfm_username},
                )
                or {}
            )
            track_data = (
                await self.fetch_lastfm_data(
                    "track.getInfo",
                    {
                        "artist": main_artist,
                        "track": song,
                        "username": lastfm_username,
                        "autocorrect": 1,
                    },
                )
                or {}
            )
            track_plays = 0
            if track_data.get("track"):
                track_plays = int(
                    track_data["track"].get("userplaycount")
                    or track_data["track"].get("playcount")
                    or track_data["track"].get("stats", {}).get("userplaycount")
                    or track_data["track"].get("stats", {}).get("playcount")
                    or 0
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

            avatar_url = (
                user_info.get("user", {}).get("image", [{}])[-1].get("#text") or None
            )

            author_args = {
                "name": f"{'Now playing' if is_now_playing else 'Last played'} - {target.display_name}",
                "url": lastfm_profile_url,
            }

            if "date" in track and "uts" in track["date"]:
                last_played = datetime.fromtimestamp(int(track["date"]["uts"]))
                time_ago = await self.format_time_ago(last_played)
                last_played_str = f"Last scrobbled: {time_ago}"
            else:
                last_played_str = ""

            footer_text = [
                f"-# {artist_plays:,} artist scrobbles • {track_plays:,} track scrobbles • {total_scrobbles:,} total scrobbles"
            ]
            if not is_now_playing and last_played_str:
                footer_text.append(
                    f"Songs not updating? Check '/outofsync' - {last_played_str}"
                )

            container = discord.ui.Container()
            section = discord.ui.Section(
                discord.ui.TextDisplay(
                    content=f"**Now Playing - {target.display_name}**"
                ),
                discord.ui.TextDisplay(content="\n".join(description)),
                accessory=discord.ui.Thumbnail(media=cover_url),
            )
            container.add_item(section)
            container.add_item(
                discord.ui.Separator(
                    visible=True, spacing=discord.SeparatorSpacing.small
                ),
            )
            container.add_item(
                discord.ui.TextDisplay(content="\n".join(footer_text)),
            )
            container.accent_colour = discord.Colour(0xFFFFFF)
            view = ui.LayoutView()
            view.add_item(container)
            await ctx.send(view=view)

        except Exception as e:
            error_msg = f"An error occurred while fetching track information: {str(e)}"
            if "404" in str(e) and "Unknown interaction" in str(e):
                error_msg = "The command took too long to respond. Please try again!"
            if "NoneType" in str(e):
                error_msg = (
                    "I genuinely have no clue what the fuck you're listening to, this cog was poorly coded and I can't read anything that isn't from spotify."
                )

            try:
                if ctx.interaction:
                    await ctx.interaction.followup.send(error_msg, ephemeral=True)
                else:
                    await ctx.send(error_msg)
            except:
                pass

    @hybrid(
        name="outofsync", description="Check if your LastFM scrobbles are out of sync."
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def outofsync(self, ctx: Context):
        if ctx.guild:
            await ctx.typing()  # I love when people think bots are human >_<

            container = ui.Container()
            container.add_item(ui.TextDisplay(content="## LastFM Sync Issues"))
            container.add_item(
                ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            )
            container.add_item(
                ui.TextDisplay(
                    content="Vortex uses your Last.fm account to track what you listen to. Sometimes, Last.fm and Spotify have issues staying in sync, which can cause commands to show outdated information about what you're currently playing. Sometimes it could also be due to Privacy settings on LastFM.",
                )
            )
            container.add_item(
                ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            )
            container.add_item(ui.TextDisplay(content="### Important Note"))
            container.add_item(
                ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            )
            container.add_item(
                ui.TextDisplay(
                    content="Vortex is not affiliated with LastFM. Your music is tracked by LastFM, not by Vortex. This means any sync issues are between LastFM and your music service. Not the bot.",
                )
            )
            container.add_item(
                ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            )
            container.add_item(
                ui.TextDisplay(
                    content="### How to fix it",
                )
            )
            container.add_item(
                ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            )
            container.add_item(
                ui.TextDisplay(
                    content="""
                > - Restart your Spotify/streaming app
                > - Disconnect and reconnect Spotify in your Last.fm settings
                > - Make sure you're scrobbling from only one device at a time
                > - Check if Last.fm is experiencing any service issues
                > - Try playing a different song to see if it updates
                > - Check your privacy settings on LastFM
                """,
                )
            )
            container.add_item(
                ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            )
            container.add_item(
                ui.TextDisplay(
                    content="**Need more help?** [Visit Last.fm's support page](https://support.last.fm/t/spotify-has-stopped-scrobbling-what-can-i-do/3184)",
                )
            )
            container.add_item(
                ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            )

            action_row = discord.ui.ActionRow()
            action_row.add_item(
                discord.ui.Button(
                    label="Last.FM Settings",
                    url="https://www.last.fm/settings/applications",
                    style=discord.ButtonStyle.link,
                )
            )
            action_row.add_item(
                discord.ui.Button(
                    label="Support Page",
                    url="https://support.last.fm/t/spotify-has-stopped-scrobbling-what-can-i-do/3184",
                    style=discord.ButtonStyle.link,
                )
            )

            container.add_item(action_row)
            view = ui.LayoutView()
            view.add_item(container)
            await ctx.reply(view=view)

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
                f"{user.mention} you have not authenticated with LastFM. Run `/lastfm auth` to authenticate.",
            )
            return

        try:
            data = await self.fetch_lastfm_data(
                "user.getRecentTracks", {"user": username, "limit": 1}
            )
            if not data or "error" in data:
                await self.error_embed(
                    ctx,
                    f"{user.mention} Failed to fetch cover art. Please try again later.",
                )
                return

            track = data.get("recenttracks", {}).get("track", [{}])[0]
            artist = track.get("artist", {}).get("#text")
            track_name = track.get("name")
            album = track.get("album", {}).get("#text")

            cover_url = await self.get_spotify_cover(artist, track_name)

            if not cover_url:
                cover_url = track.get("image", [{}])[-1].get("#text")

            if not cover_url or not album:
                await self.error_embed(
                    ctx,
                    f"{user.mention} Could not find cover art for this track.",
                )
                return

            embed = discord.Embed(description=f"{album}", color=0xFFFFFF)
            embed.set_image(url=cover_url)

            await ctx.send(embed=embed)

        except Exception as e:
            await self.error_embed(
                ctx,
                f"{user.mention} Failed to fetch cover art. Please try again later.",
            )
            logger.error(f"Error in cover command: {e}")

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

        if ctx.guild:
            await ctx.channel.typing()

        username = await self.get_lastfm_username(user.id)
        if not username:
            await self.error_embed(
                ctx,
                f"{user.mention} you have not authenticated with LastFM. Run `/lastfm auth` to authenticate.",
            )
            return

        data = await self.fetch_lastfm_data("user.getInfo", {"user": username})
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

        if ctx.guild:
            await ctx.channel.typing()

        username = await self.get_lastfm_username(user.id)
        if not username:
            await self.error_embed(
                ctx,
                f"{user.mention} you have not authenticated with LastFM. Run `/lastfm auth` to authenticate.",
            )
            return

        if track is None:
            data = await self.fetch_lastfm_data(
                "user.getRecentTracks", {"user": username, "limit": 1}
            )
            if not data or "error" in data:
                await self.error_embed(
                    ctx,
                    f"{user.mention} Failed to fetch current track. Please try again later.",
                )
                return

            track = data.get("recenttracks", {}).get("track", [{}])[0]
            track = track.get("name")
            if not track:
                await self.error_embed(
                    ctx,
                    f"{user.mention} Failed to fetch current track. Please try again later.",
                )
                return

        data = await self.fetch_lastfm_data(
            "user.getRecentTracks",
            {"user": username, "limit": 1, "track": track},
        )
        plays = int(
            data.get("recenttracks", {}).get("track", [{}])[0].get("playcount", 0)
        )
        await ctx.send(f"{user.mention} has `{plays}` total scrobbles for {track}.")

    @lastfm.group(
        name="whoknows",
        aliases=["wk", "whoknowsthis"],
        description="Shows who in the server listens to a specific artist the most.",
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def whoknows(self, ctx: Context, artist: str = None):
        """Shows who in the server listens to a specific artist the most."""
        if ctx.guild is None:
            await ctx.send("This command does not work in DMs.")
            return

        if ctx.guild:
            await ctx.channel.typing()

        if artist is None:
            username = await self.get_lastfm_username(ctx.author.id)

            if not username:
                await self.error_embed(
                    ctx,
                    f"{ctx.author.mention} you have not authenticated with LastFM. Run `/lastfm auth` to authenticate.",
                )
                return

            data = await self.fetch_lastfm_data(
                "user.getRecentTracks", {"user": username, "limit": 1}
            )

            if (
                not data
                or "error" in data
                or not data.get("recenttracks", {}).get("track")
            ):
                await self.error_embed(
                    ctx,
                    f"{ctx.author.mention} Couldn't fetch your currently playing track. Please specify an artist or try again later.",
                )
                return

            track = data["recenttracks"]["track"][0]
            artist = track["artist"]["#text"]

            if not artist:
                await self.error_embed(
                    ctx,
                    f"{ctx.author.mention} Couldn't determine the artist from your currently playing track. Please specify an artist manually.",
                )
                return

        artist_data = await self.fetch_lastfm_data("artist.getInfo", {"artist": artist})

        if not artist_data or "error" in artist_data or "artist" not in artist_data:
            await self.error_embed(
                ctx,
                f"{ctx.author.mention} Couldn't find artist '{artist}'. Please check the spelling and try again.",
            )
            return

        async with self.bot.db.acquire() as conn:
            records = await conn.fetch(
                "SELECT discord_id, lastfm_name FROM lastfm_tokens"
            )

        if not records:
            await self.error_embed(
                ctx,
                f"{ctx.author.mention} No users in this server have connected their Last.fm accounts yet.",
            )
            return

        user_plays = []
        artist_name = artist_data["artist"]["name"]
        artist_url = artist_data["artist"].get(
            "url", f"https://www.last.fm/music/{quote_plus(artist_name)}"
        )

        for record in records:
            try:
                user = ctx.guild.get_member(record["discord_id"])
                if not user:
                    continue

                artist_info = await self.fetch_lastfm_data(
                    "artist.getInfo",
                    {"artist": artist_name, "username": record["lastfm_name"]},
                )

                if (
                    artist_info
                    and "artist" in artist_info
                    and "stats" in artist_info["artist"]
                ):
                    playcount = int(
                        artist_info["artist"]["stats"].get("userplaycount", 0)
                    )
                    if playcount > 0:
                        user_plays.append((user, playcount))
            except Exception as e:
                logger.error(
                    f"Error fetching artist info for {record['lastfm_name']}: {e}"
                )
                continue

        user_plays.sort(key=lambda x: x[1], reverse=True)

        embed = discord.Embed(
            title=f"{artist_name} in {ctx.guild.name}",
            url=artist_url,
            color=discord.Color(0xFFFFFF),
        )

        if not user_plays:
            embed.description = (
                f"No one in this server has listened to {artist_name} yet."
            )
        else:
            top_users = user_plays[:10]

            leaderboard = []
            for i, (user, plays) in enumerate(top_users, 1):
                lastfm_username = await self.get_lastfm_username(user.id)
                lastfm_url = (
                    f"https://www.last.fm/user/{quote_plus(lastfm_username)}"
                    if lastfm_username
                    else "#"
                )
                formatted_plays = f"{plays:,} play{'s' if plays != 1 else ''}"
                leaderboard.append(
                    f"`{i}.` [{user.display_name}]({lastfm_url}) • **{formatted_plays}**"
                )

            embed.description = "\n".join(leaderboard)

            total_listeners = len(user_plays)
            total_plays = sum(plays for _, plays in user_plays)
            avg_plays = (
                round(total_plays / total_listeners, 1) if total_listeners > 0 else 0
            )

            stats = f"{artist_name} • {total_listeners} listener{'s' if total_listeners != 1 else ''} • {total_plays:,} plays • {avg_plays} avg"
            embed.set_footer(text=stats)

            artist_image = await self.get_artist_image(artist)
            if artist_image:
                embed.set_thumbnail(url=artist_image)

        await ctx.send(embed=embed)

    @whoknows.command(
        name="artist",
        description="Shows the top 10 users who listen to an artist server wide.",
    )
    @app_commands.describe(
        artist="The artist. Leave empty to use your currently playing track's artist.",
    )
    async def whoknowsartist(self, ctx: Context, artist: str = None):
        """Shows who in the server listens to a specific artist the most."""
        if ctx.guild:
            await ctx.channel.typing()

        if artist is None:
            username = await self.get_lastfm_username(ctx.author.id)

            if not username:
                await self.error_embed(
                    ctx,
                    f"{ctx.author.mention} you have not authenticated with LastFM. Run `/lastfm auth` to authenticate.",
                )
                return

            data = await self.fetch_lastfm_data(
                "user.getRecentTracks", {"user": username, "limit": 1}
            )

            if (
                not data
                or "error" in data
                or not data.get("recenttracks", {}).get("track")
            ):
                await self.error_embed(
                    ctx,
                    f"{ctx.author.mention} Couldn't fetch your currently playing track. Please specify an artist or try again later.",
                )
                return

            track = data["recenttracks"]["track"][0]
            artist = track["artist"]["#text"]

            if not artist:
                await self.error_embed(
                    ctx,
                    f"{ctx.author.mention} Couldn't determine the artist from your currently playing track. Please specify an artist manually.",
                )
                return

        artist_data = await self.fetch_lastfm_data("artist.getInfo", {"artist": artist})

        if not artist_data or "error" in artist_data or "artist" not in artist_data:
            await self.error_embed(
                ctx,
                f"{ctx.author.mention} Couldn't find artist '{artist}'. Please check the spelling and try again.",
            )
            return

        async with self.bot.db.acquire() as conn:
            records = await conn.fetch(
                "SELECT discord_id, lastfm_name FROM lastfm_tokens"
            )

        if not records:
            await self.error_embed(
                ctx,
                f"{ctx.author.mention} No users in this server have connected their Last.fm accounts yet.",
            )
            return

        user_plays = []
        artist_name = artist_data["artist"]["name"]
        artist_url = artist_data["artist"].get(
            "url", f"https://www.last.fm/music/{quote_plus(artist_name)}"
        )

        for record in records:
            try:
                user = ctx.guild.get_member(record["discord_id"])
                if not user:
                    continue

                artist_info = await self.fetch_lastfm_data(
                    "artist.getInfo",
                    {"artist": artist_name, "username": record["lastfm_name"]},
                )

                if (
                    artist_info
                    and "artist" in artist_info
                    and "stats" in artist_info["artist"]
                ):
                    playcount = int(
                        artist_info["artist"]["stats"].get("userplaycount", 0)
                    )
                    if playcount > 0:
                        user_plays.append((user, playcount))
            except Exception as e:
                continue

        user_plays.sort(key=lambda x: x[1], reverse=True)

        embed = discord.Embed(
            title=f"{artist_name} in {ctx.guild.name}",
            url=artist_url,
            color=discord.Color(0xFFFFFF),
        )

        if not user_plays:
            embed.description = f"{ctx.author.mention} No one in this server has listened to {artist_name} yet."
        else:
            top_users = user_plays[:10]

            leaderboard = []
            for i, (user, plays) in enumerate(top_users, 1):
                lastfm_username = await self.get_lastfm_username(user.id)
                lastfm_url = (
                    f"https://www.last.fm/user/{quote_plus(lastfm_username)}"
                    if lastfm_username
                    else "#"
                )
                formatted_plays = f"{plays:,} play{'s' if plays != 1 else ''}"
                leaderboard.append(
                    f"`{i}.` [{user.display_name}]({lastfm_url}) • **{formatted_plays}**"
                )

            embed.description = "\n".join(leaderboard)

            total_listeners = len(user_plays)
            total_plays = sum(plays for _, plays in user_plays)
            avg_plays = (
                round(total_plays / total_listeners, 1) if total_listeners > 0 else 0
            )

            stats = f"{artist_name} • {total_listeners} listener{'s' if total_listeners != 1 else ''} • {total_plays:,} plays • {avg_plays} avg"
            embed.set_footer(text=stats)

            artist_image = await self.get_artist_image(artist_name)
            if artist_image:
                embed.set_thumbnail(url=artist_image)

        await ctx.send(embed=embed)

    @whoknows.command(
        name="album",
        description="Shows the top 10 users who listen to an album server wide.",
    )
    @app_commands.describe(
        album="The album. Leave empty to use your currently playing track's album.",
        artist="The artist of the album. Only needed if not using currently playing track.",
    )
    async def whoknowsalbum(self, ctx: Context, album: str = None, artist: str = None):
        """Shows who in the server listens to a specific album the most."""
        if ctx.guild:
            await ctx.channel.typing()

        if album is None:
            username = await self.get_lastfm_username(ctx.author.id)

            if not username:
                await self.error_embed(
                    ctx,
                    "You need to authenticate with Last.fm first using `/lastfm auth`.",
                )
                return

            data = await self.fetch_lastfm_data(
                "user.getRecentTracks", {"user": username, "limit": 1}
            )

            if (
                not data
                or "error" in data
                or not data.get("recenttracks", {}).get("track")
            ):
                await self.error_embed(
                    ctx,
                    "Couldn't fetch your currently playing track. Please specify an album and artist or try again later.",
                )
                return

            track = data["recenttracks"]["track"][0]
            album = track.get("album", {}).get("#text")
            artist = track.get("artist", {}).get("#text")

            if not album or not artist:
                await self.error_embed(
                    ctx,
                    "Couldn't determine the album/artist from your currently playing track. Please specify them manually.",
                )
                return

        if not artist:
            await self.error_embed(
                ctx,
                "Please specify both artist and album, or use the command without parameters to use your currently playing track.",
            )
            return

        album_data = await self.fetch_lastfm_data(
            "album.getInfo", {"album": album, "artist": artist, "autocorrect": 1}
        )

        print(f"Album data: {album_data}")

        if not album_data or "error" in album_data or "album" not in album_data:
            await self.error_embed(
                ctx,
                f"Couldn't find album '{album}' by {artist}. Please check the spelling and try again.",
            )
            return

        records = await self.bot.db.fetch(
            "SELECT discord_id, lastfm_name FROM lastfm_tokens"
        )

        if not records:
            await self.error_embed(
                ctx,
                "No users have connected their Last.fm accounts yet.",
            )
            return

        user_plays = []
        album_name = album_data["album"].get("name", album)
        artist_name = album_data["album"].get("artist", artist)
        if isinstance(artist_name, dict):
            artist_name = artist_name.get("#text", artist)

        album_url = album_data["album"].get(
            "url",
            f"https://www.last.fm/music/{quote_plus(artist_name)}/{quote_plus(album_name)}",
        )

        for record in records:
            try:
                user = ctx.guild.get_member(record["discord_id"])
                if not user:
                    continue

                user_album_info = await self.fetch_lastfm_data(
                    "album.getInfo",
                    {
                        "album": album_name,
                        "artist": artist_name,
                        "username": record["lastfm_name"],
                    },
                )

                if (
                    user_album_info
                    and "album" in user_album_info
                    and "userplaycount" in user_album_info["album"]
                ):
                    playcount = int(user_album_info["album"].get("userplaycount", 0))
                    if playcount > 0:
                        user_plays.append((user, playcount))
            except Exception as e:
                continue

        user_plays.sort(key=lambda x: x[1], reverse=True)

        embed = discord.Embed(
            title=f"{album_name} in {ctx.guild.name}",
            url=album_url,
            color=discord.Color(0xFFFFFF),
        )

        if not user_plays:
            embed.description = (
                f"No one in this server has listened to {album_name} yet."
            )
        else:
            top_users = user_plays[:10]

            leaderboard = []
            for i, (user, plays) in enumerate(top_users, 1):
                lastfm_username = await self.get_lastfm_username(user.id)
                lastfm_url = (
                    f"https://www.last.fm/user/{quote_plus(lastfm_username)}"
                    if lastfm_username
                    else "#"
                )
                formatted_plays = f"{plays:,} play{'s' if plays != 1 else ''}"
                leaderboard.append(
                    f"`{i}.` [{user.display_name}]({lastfm_url}) • **{formatted_plays}**"
                )

            embed.description = "\n".join(leaderboard)

            total_listeners = len(user_plays)
            total_plays = sum(plays for _, plays in user_plays)
            avg_plays = (
                round(total_plays / total_listeners, 1) if total_listeners > 0 else 0
            )

            stats = f"{album_name} • {total_listeners} listener{'s' if total_listeners != 1 else ''} • {total_plays:,} plays • {avg_plays} avg"
            embed.set_footer(text=stats)

            album_image = None
            if "image" in album_data["album"]:
                album_image = next(
                    (
                        img["#text"]
                        for img in reversed(album_data["album"]["image"])
                        if img.get("#text")
                    ),
                    None,
                )

            if not album_image and "image" in album_data.get("album", {}):
                album_image = next(
                    (
                        img["#text"]
                        for img in reversed(album_data["album"]["image"])
                        if img.get("#text")
                    ),
                    None,
                )

            if not album_image:
                album_image = await self.get_spotify_cover(artist_name, album_name)

            if album_image:
                embed.set_thumbnail(url=album_image)

            embed.set_footer(text=stats)

        await ctx.send(embed=embed)

    @whoknows.command(
        name="track",
        description="Shows the top 10 users who listen to a track server wide.",
    )
    @app_commands.describe(
        track="The track.",
    )
    async def whoknowstrack(self, ctx: Context, track: str = None, artist: str = None):
        """Shows who in the server listens to a specific track the most."""
        if ctx.guild:
            await ctx.channel.typing()

        if track is None:
            username = await self.get_lastfm_username(ctx.author.id)

            if not username:
                await self.error_embed(
                    ctx,
                    f"{ctx.author.mention} you have not authenticated with LastFM. Run `/lastfm auth` to authenticate.",
                )
                return

            data = await self.fetch_lastfm_data(
                "user.getRecentTracks", {"user": username, "limit": 1}
            )

            if (
                not data
                or "error" in data
                or not data.get("recenttracks", {}).get("track")
            ):
                await self.error_embed(
                    ctx,
                    f"{ctx.author.mention} couldn't fetch your currently playing track. Please specify an album and artist or try again later.",
                )
                return

            track = data["recenttracks"]["track"][0]
            track_name = track["name"]
            artist = track["artist"]["#text"]

            if not track_name or not artist:
                await self.error_embed(
                    ctx,
                    f"{ctx.author.mention} couldn't determine the album/artist from your currently playing track. Please specify them manually.",
                )
                return

        if not artist:
            await self.error_embed(
                ctx,
                f"{ctx.author.mention} please specify both artist and album, or use the command without parameters to use your currently playing track.",
            )
            return

        track_info = await self.fetch_lastfm_data(
            "track.getInfo", {"track": track_name, "artist": artist}
        )

        if not track_info or "error" in track_info or "track" not in track_info:
            await self.error_embed(
                ctx,
                f"{ctx.author.mention} couldn't find track '{track_name}' by {artist}. Please check the spelling and try again.",
            )
            return

        track_name = track_info["track"].get("name", track_name)
        artist_name = track_info["track"].get("artist", {}).get("name", artist)
        track_url = track_info["track"].get("url")

        if not track_url and artist_name and track_name:
            track_url = f"https://www.last.fm/music/{quote_plus(artist_name)}/_/{quote_plus(track_name)}"

        async with self.bot.db.acquire() as conn:
            records = await conn.fetch(
                "SELECT discord_id, lastfm_name FROM lastfm_tokens"
            )

        if not records:
            await self.error_embed(
                ctx,
                f"{ctx.author.mention} no users in this server have connected their Last.fm accounts yet.",
            )
            return

        user_plays = []

        for record in records:
            try:
                user = ctx.guild.get_member(record["discord_id"])
                if not user:
                    logger.debug(f"User {record['discord_id']} not found in server")
                    continue

                user_track_info = await self.fetch_lastfm_data(
                    "track.getInfo",
                    {
                        "track": track_name,
                        "artist": artist_name,
                        "username": record["lastfm_name"],
                    },
                )

                if (
                    user_track_info
                    and "track" in user_track_info
                    and "userplaycount" in user_track_info["track"]
                ):
                    playcount = int(user_track_info["track"].get("userplaycount", 0))
                    if playcount > 0:
                        user_plays.append((user, playcount))
            except Exception as e:
                logger.error(
                    f"Error fetching track info for {record['lastfm_name']}: {e}"
                )
                continue

        user_plays.sort(key=lambda x: x[1], reverse=True)

        embed = discord.Embed(
            title=f"{track_name} by {artist_name} in {ctx.guild.name}",
            url=track_url,
            color=discord.Color(0xFFFFFF),
        )

        if not user_plays:
            embed.description = f"{ctx.author.mention} no one in this server has listened to {track_name} by {artist_name} yet."
        else:
            top_users = user_plays[:10]

            leaderboard = []
            for i, (user, plays) in enumerate(top_users, 1):
                lastfm_username = await self.get_lastfm_username(user.id)
                lastfm_url = (
                    f"https://www.last.fm/user/{quote_plus(lastfm_username)}"
                    if lastfm_username
                    else "#"
                )
                formatted_plays = f"{plays:,} play{'s' if plays != 1 else ''}"
                leaderboard.append(
                    f"`{i}.` [{user.display_name}]({lastfm_url}) • **{formatted_plays}**"
                )

            embed.description = "\n".join(leaderboard)

            total_listeners = len(user_plays)
            total_plays = sum(plays for _, plays in user_plays)
            avg_plays = (
                round(total_plays / total_listeners, 1) if total_listeners > 0 else 0
            )

            stats = [
                f"{track_name}",
                f"{total_listeners} listener{'s' if total_listeners != 1 else ''}",
                f"{total_plays:,} play{'s' if total_plays != 1 else ''}",
                f"{avg_plays} avg",
            ]

            embed.set_footer(text=f"{ctx.author.mention} • ".join(stats))

            track_image = await self.get_spotify_cover(artist_name, track_name)

            if (
                not track_image
                and "album" in track_data["track"]  # type: ignore
                and "image" in track_data["track"]["album"]  # type: ignore
            ):
                track_image = next(
                    (
                        img["#text"]
                        for img in reversed(track_data["track"]["album"]["image"])  # type: ignore
                        if img.get("#text")
                    ),
                    None,
                )

            if not track_image and "image" in track_data["track"]:  # type: ignore
                track_image = next(
                    (
                        img["#text"]
                        for img in reversed(track_data["track"]["image"])  # type: ignore
                        if img.get("#text")
                    ),
                    None,
                )

            if track_image:
                if track_image.startswith("http://"):
                    track_image = track_image.replace("http://", "https://", 1)
                embed.set_thumbnail(url=track_image)

        await ctx.send(embed=embed)

    @lastfm.group(
        name="top",
        description="Shows the top artists, albums, or tracks for a specific user.",
        invoke_without_command=True,
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.describe(
        user="The user.",
        period="Time period.",
    )
    @app_commands.choices(
        period=[
            app_commands.Choice(name="All Time", value="overall"),
            app_commands.Choice(name="Weekly", value="7day"),
            app_commands.Choice(name="Monthly", value="1month"),
            app_commands.Choice(name="3 Months", value="3month"),
            app_commands.Choice(name="6 Months", value="6month"),
            app_commands.Choice(name="Yearly", value="12month"),
        ]
    )
    async def top(
        self, ctx: Context, user: Optional[discord.Member] = None, period: str = "7day"
    ):
        """Show your top artists"""
        if ctx.invoked_subcommand is not None:
            return

        target_user = user or ctx.author
        username = await self.get_lastfm_username(target_user.id)

        if not username:
            await self.error_embed(
                ctx, f"{target_user.mention} hasn't set their Last.fm username."
            )
            return

        try:
            await ctx.typing()

            period_mapping = {
                "overall": ("overall", "All Time"),
                "7day": ("7day", "Weekly"),
                "1month": ("1month", "Monthly"),
                "3month": ("3month", "3 Months"),
                "6month": ("6month", "6 Months"),
                "12month": ("12month", "Yearly"),
                "at": ("overall", "All Time"),
                "7d": ("7day", "Weekly"),
                "1m": ("1month", "Monthly"),
                "3m": ("3month", "3 Months"),
                "6m": ("6month", "6 Months"),
                "12m": ("12month", "Yearly"),
            }

            api_period, display_period = period_mapping.get(period, ("7day", "Weekly"))

            data = await self.fetch_lastfm_data(
                "user.getTopArtists",
                {"user": username, "period": api_period, "limit": 50},
            )

            if (
                not data
                or "error" in data
                or not data.get("topartists", {}).get("artist")
            ):
                await self.error_embed(
                    ctx,
                    f"{ctx.author.mention} couldn't fetch top artists for {target_user.display_name}. Please try again later.",
                )
                return

            artists = data["topartists"]["artist"]

            paginator = ArtistPaginator(
                author_id=ctx.author.id,
                artists=artists,
                username=username,
                period=api_period,
            )

            message = await ctx.send(embed=paginator.get_page_content(), view=paginator)
            paginator.message = message

        except Exception as e:
            await self.error_embed(
                ctx,
                f"{ctx.author.mention} an error occurred while fetching top artists. Please try again later.",
            )

    @top.command(
        name="artist",
        description="Shows the top artists for a specific user.",
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.describe(
        user="The user.",
        period="Time period.",
    )
    @app_commands.choices(
        period=[
            app_commands.Choice(name="All Time", value="overall"),
            app_commands.Choice(name="Weekly", value="7day"),
            app_commands.Choice(name="Monthly", value="1month"),
            app_commands.Choice(name="3 Months", value="3month"),
            app_commands.Choice(name="6 Months", value="6month"),
            app_commands.Choice(name="Yearly", value="12month"),
        ]
    )
    async def artist(
        self, ctx: Context, user: Optional[discord.Member] = None, period: str = "7day"
    ):
        """Show your top artists"""
        if ctx.invoked_subcommand is not None:
            return

        target_user = user or ctx.author
        username = await self.get_lastfm_username(target_user.id)

        if not username:
            await self.error_embed(
                ctx, f"{target_user.mention} hasn't set their Last.fm username."
            )
            return

        try:
            await ctx.typing()

            period_mapping = {
                "overall": ("overall", "All Time"),
                "7day": ("7day", "Weekly"),
                "1month": ("1month", "Monthly"),
                "3month": ("3month", "3 Months"),
                "6month": ("6month", "6 Months"),
                "12month": ("12month", "Yearly"),
                "at": ("overall", "All Time"),
                "7d": ("7day", "Weekly"),
                "1m": ("1month", "Monthly"),
                "3m": ("3month", "3 Months"),
                "6m": ("6month", "6 Months"),
                "12m": ("12month", "Yearly"),
            }

            api_period, display_period = period_mapping.get(period, ("7day", "Weekly"))

            data = await self.fetch_lastfm_data(
                "user.getTopArtists",
                {"user": username, "period": api_period, "limit": 50},
            )

            if (
                not data
                or "error" in data
                or not data.get("topartists", {}).get("artist")
            ):
                await self.error_embed(
                    ctx,
                    f"{ctx.author.mention} couldn't fetch top artists for {target_user.display_name}. Please try again later.",
                )
                return

            artists = data["topartists"]["artist"]

            paginator = ArtistPaginator(
                author_id=ctx.author.id,
                artists=artists,
                username=username,
                period=api_period,
            )

            message = await ctx.send(embed=paginator.get_page_content(), view=paginator)
            paginator.message = message

        except Exception as e:
            await self.error_embed(
                ctx,
                f"{ctx.author.mention} an error occurred while fetching top artists. Please try again later.",
            )

    # @top.command(
    #     name="album",
    #     description="Shows the top albums for a specific user.",
    # )
    # @app_commands.describe(
    #     user="The user.",
    #     period="Time period.",
    # )
    # @app_commands.choices(
    #     period=[
    #         app_commands.Choice(name="All Time", value="overall"),
    #         app_commands.Choice(name="Weekly", value="7day"),
    #         app_commands.Choice(name="Monthly", value="1month"),
    #         app_commands.Choice(name="3 Months", value="3month"),
    #         app_commands.Choice(name="6 Months", value="6month"),
    #         app_commands.Choice(name="Yearly", value="12month"),
    #     ]
    # )
    # async def album(self, ctx: Context, user: Optional[discord.Member] = None, period: str = "7day"):
    #     """Show your top albums"""
    #     target_user = user or ctx.author
    #     username = await self.get_lastfm_username(target_user.id)

    #     if not username:
    #         await self.error_embed(
    #             ctx,
    #             f"{target_user.mention} hasn't set their Last.fm username."
    #         )
    #         return

    #     try:
    #         await ctx.typing()

    #         period_mapping = {
    #             "overall": ("overall", "All Time"),
    #             "7day": ("7day", "Weekly"),
    #             "1month": ("1month", "Monthly"),
    #             "3month": ("3month", "3 Months"),
    #             "6month": ("6month", "6 Months"),
    #             "12month": ("12month", "Yearly"),
    #             "at": ("overall", "All Time"),
    #             "7d": ("7day", "Weekly"),
    #             "1m": ("1month", "Monthly"),
    #             "3m": ("3month", "3 Months"),
    #             "6m": ("6month", "6 Months"),
    #             "12m": ("12month", "Yearly")
    #         }

    #         api_period, display_period = period_mapping.get(period, ("7day", "Weekly"))

    #         data = await self.fetch_lastfm_data(
    #             "user.getTopAlbums",
    #             {"user": username, "period": api_period, "limit": 50}
    #         )

    #         if not data or "error" in data or not data.get("topalbums", {}).get("album"):
    #             await self.error_embed(
    #                 ctx,
    #                 f"{ctx.author.mention} couldn't fetch top albums for {target_user.display_name}. Please try again later.",
    #             )
    #             return

    #         albums = data["topalbums"]["album"]

    #         paginator = AlbumPaginator(
    #             author_id=ctx.author.id,
    #             albums=albums,
    #             username=username,
    #             period=api_period
    #         )

    #         message = await ctx.send(embed=paginator.get_page_content(), view=paginator)
    #         paginator.message = message

    #     except Exception as e:
    #         await self.error_embed(
    #             ctx,
    #             f"{ctx.author.mention} an error occurred while fetching top albums. Please try again later.",
    #         )

    # @top.command(
    #     name="track",
    #     description="Shows the top 10 tracks for a specific user.",
    # )
    # @app_commands.describe(
    #     user="The user.",
    #     period="Time period.",
    # )
    # @app_commands.choices(
    #     period=[
    #         app_commands.Choice(name="All Time", value="overall"),
    #         app_commands.Choice(name="Weekly", value="7day"),
    #         app_commands.Choice(name="Monthly", value="1month"),
    #         app_commands.Choice(name="3 Months", value="3month"),
    #         app_commands.Choice(name="6 Months", value="6month"),
    #         app_commands.Choice(name="Yearly", value="12month"),
    #     ]
    # )
    # async def track(self, ctx: Context, user: Optional[discord.Member] = None, period: str = "7day"):
    #     pass # Will work on making the logic for this command in the morning.

    @command(
        name="topartist",
        aliases=["ta"],
        description="Shows the top 10 artists for a specific user.",
    )
    async def topartist_shortcut(
        self, ctx: Context, user: Optional[discord.Member] = None, period: str = "7day"
    ):
        await self.top(ctx, user, period)

    @lastfm.group(
        name="globalwhoknows",
        aliases=["gwk"],
        description="Shows what other users listen to globally.",
        invoke_without_command=True,
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def globalwhoknows(self, ctx: Context, artist: str = None):
        """Shows who listens to a specific artist the most across all servers."""
        if ctx.guild:
            await ctx.channel.typing()

        if not artist:
            username = await self.get_lastfm_username(ctx.author.id)
            if not username:
                await self.error_embed(
                    ctx,
                    "You need to authenticate with Last.fm first using `/lastfm auth`.",
                )
                return

            data = await self.fetch_lastfm_data(
                "user.getRecentTracks", {"user": username, "limit": 1}
            )

            if (
                not data
                or "error" in data
                or not data.get("recenttracks", {}).get("track")
            ):
                await self.error_embed(
                    ctx,
                    "Couldn't fetch your currently playing track. Please specify an artist.",
                )
                return

            current_track = data["recenttracks"]["track"][0]
            artist = current_track["artist"]["#text"]

            if not artist:
                await self.error_embed(
                    ctx,
                    "Couldn't determine the artist from your currently playing track. Please specify an artist.",
                )
                return

            return await self.artist(ctx, artist)

        await self.artist(ctx, artist)

    @globalwhoknows.command(
        name="artist",
        description="Shows the top 15 users who listen to an artist globally.",
    )
    @app_commands.describe(
        artist="The artist.",
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def artist(self, ctx: Context, artist: str = None):
        """Shows who listens to a specific artist the most across all servers."""
        if ctx.guild:
            await ctx.channel.typing()

        if not artist:
            username = await self.get_lastfm_username(ctx.author.id)
            if not username:
                await self.error_embed(
                    ctx,
                    "You need to authenticate with Last.fm first using `/lastfm auth`.",
                )
                return

            data = await self.fetch_lastfm_data(
                "user.getRecentTracks", {"user": username, "limit": 1}
            )

            if (
                not data
                or "error" in data
                or not data.get("recenttracks", {}).get("track")
            ):
                await self.error_embed(
                    ctx,
                    "Couldn't fetch your currently playing track. Please specify an artist.",
                )
                return

            current_track = data["recenttracks"]["track"][0]
            artist = current_track["artist"]["#text"]

            if not artist:
                await self.error_embed(
                    ctx,
                    "Couldn't determine the artist from your currently playing track. Please specify an artist.",
                )
                return

        artist_data = await self.fetch_lastfm_data("artist.getInfo", {"artist": artist})

        if not artist_data or "error" in artist_data or "artist" not in artist_data:
            await self.error_embed(
                ctx,
                f"Couldn't find artist '{artist}'. Please check the spelling and try again.",
            )
            return

        records = await self.bot.db.fetch(
            "SELECT discord_id, lastfm_name FROM lastfm_tokens"
        )

        if not records:
            await self.error_embed(
                ctx,
                "No users have connected their Last.fm accounts yet.",
            )
            return

        user_plays = []
        artist_name = artist_data["artist"]["name"]
        artist_url = artist_data["artist"].get(
            "url", f"https://www.last.fm/music/{quote_plus(artist_name)}"
        )

        for record in records:
            try:
                artist_info = await self.fetch_lastfm_data(
                    "artist.getInfo",
                    {"artist": artist_name, "username": record["lastfm_name"]},
                )

                if (
                    artist_info
                    and "artist" in artist_info
                    and "stats" in artist_info["artist"]
                ):
                    playcount = int(
                        artist_info["artist"]["stats"].get("userplaycount", 0)
                    )
                    if playcount > 0:
                        user_plays.append(
                            (record["discord_id"], record["lastfm_name"], playcount)
                        )
            except Exception as e:
                logger.error(
                    f"Error fetching artist info for {record['lastfm_name']}: {e}"
                )
                continue

        user_plays.sort(key=lambda x: x[2], reverse=True)

        embed = discord.Embed(
            title=f"{artist_name} globally",
            url=artist_url,
            color=discord.Color(0xFFFFFF),
        )

        if not user_plays:
            embed.description = f"No one has listened to {artist_name} yet."
        else:
            top_users = user_plays[:15]
            leaderboard = []

            for i, (user_id, lastfm_name, plays) in enumerate(top_users, 1):
                try:
                    user = await self.bot.fetch_user(user_id)
                    username = f"{user.name}"
                except:
                    username = f"{lastfm_name}"

                lastfm_profile = f"https://www.last.fm/user/{lastfm_name}"
                formatted_plays = f"{plays:,} play{'s' if plays != 1 else ''}"
                leaderboard.append(
                    f"`{i}.` [{username}]({lastfm_profile}) • **{formatted_plays}**"
                )

            embed.description = "\n".join(leaderboard)

            total_listeners = len(user_plays)
            total_plays = sum(plays for _, _, plays in user_plays)
            avg_plays = (
                round(total_plays / total_listeners, 1) if total_listeners > 0 else 0
            )

            stats = [
                f"{artist_name}",
                f"{total_listeners} listener{'s' if total_listeners != 1 else ''}",
                f"{total_plays:,} play{'s' if total_plays != 1 else ''}",
                f"{avg_plays} avg",
            ]

            embed.set_footer(text=" • ".join(stats))

            artist_image = await self.get_artist_image(artist_name)
            if artist_image:
                embed.set_thumbnail(url=artist_image)

        await ctx.send(embed=embed)

    @globalwhoknows.command(
        name="track",
        description="Shows the top 15 users who listen to a track globally.",
    )
    @app_commands.describe(
        track="The track to search for (optional, uses your currently playing track if not specified)",
        artist="The artist of the track (optional, only needed if track is specified and you want to override the artist)",
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def track(self, ctx: Context, track: str = None, artist: str = None):
        """Shows who listens to a specific track the most across all servers."""
        if ctx.guild:
            await ctx.channel.typing()

        if not track:
            username = await self.get_lastfm_username(ctx.author.id)
            if not username:
                await self.error_embed(
                    ctx,
                    "You need to authenticate with Last.fm first using `/lastfm auth`.",
                )
                return

            data = await self.fetch_lastfm_data(
                "user.getRecentTracks", {"user": username, "limit": 1}
            )

            if (
                not data
                or "error" in data
                or not data.get("recenttracks", {}).get("track")
            ):
                await self.error_embed(
                    ctx,
                    "Couldn't fetch your currently playing track. Please specify both track and artist.",
                )
                return

            current_track = data["recenttracks"]["track"][0]
            track = current_track["name"]
            artist = current_track["artist"]["#text"]

            if not track or not artist:
                await self.error_embed(
                    ctx,
                    "Couldn't determine the track/artist from your currently playing track. Please specify both track and artist.",
                )
                return

        track_data = await self.fetch_lastfm_data(
            "track.getInfo", {"track": track, "artist": artist}
        )

        if not track_data or "error" in track_data or "track" not in track_data:
            await self.error_embed(
                ctx,
                f"Couldn't find track '{track}' by {artist}. Please check the spelling and try again.",
            )
            return

        records = await self.bot.db.fetch(
            "SELECT discord_id, lastfm_name FROM lastfm_tokens"
        )

        if not records:
            await self.error_embed(
                ctx,
                "No users have connected their Last.fm accounts yet.",
            )
            return

        user_plays = []
        track_name = track_data["track"]["name"]
        artist_name = track_data["track"]["artist"]["name"]
        track_url = track_data["track"].get(
            "url",
            f"https://www.last.fm/music/{quote_plus(artist_name)}/_/{quote_plus(track_name)}",
        )

        for record in records:
            try:
                user_track_info = await self.fetch_lastfm_data(
                    "track.getInfo",
                    {
                        "track": track_name,
                        "artist": artist_name,
                        "username": record["lastfm_name"],
                    },
                )

                if (
                    user_track_info
                    and "track" in user_track_info
                    and "userplaycount" in user_track_info["track"]
                ):
                    playcount = int(user_track_info["track"].get("userplaycount", 0))
                    if playcount > 0:
                        user_plays.append(
                            (record["discord_id"], record["lastfm_name"], playcount)
                        )
            except Exception as e:
                logger.error(
                    f"Error fetching track info for {record['lastfm_name']}: {e}"
                )
                continue

        user_plays.sort(key=lambda x: x[2], reverse=True)

        embed = discord.Embed(
            title=f"{track_name} by {artist_name} globally",
            url=track_url,
            color=discord.Color(0xFFFFFF),
        )

        if not user_plays:
            embed.description = (
                f"No one has listened to {track_name} by {artist_name} yet."
            )
        else:
            top_users = user_plays[:15]
            leaderboard = []

            for i, (user_id, lastfm_name, plays) in enumerate(top_users, 1):
                try:
                    user = await self.bot.fetch_user(user_id)
                    username = f"{user.name}"
                except:
                    username = f"{lastfm_name}"

                lastfm_profile = f"https://www.last.fm/user/{lastfm_name}"
                formatted_plays = f"{plays:,} play{'s' if plays != 1 else ''}"
                leaderboard.append(
                    f"`{i}.` [{username}]({lastfm_profile}) • **{formatted_plays}**"
                )

            embed.description = "\n".join(leaderboard)

            total_listeners = len(user_plays)
            total_plays = sum(plays for _, _, plays in user_plays)
            avg_plays = (
                round(total_plays / total_listeners, 1) if total_listeners > 0 else 0
            )

            stats = [
                f"{track_name}",
                f"{total_listeners} listener{'s' if total_listeners != 1 else ''}",
                f"{total_plays:,} play{'s' if total_plays != 1 else ''}",
                f"{avg_plays} avg",
            ]

            embed.set_footer(text=" • ".join(stats))

            track_image = await self.get_spotify_cover(artist_name, track_name)

            if (
                not track_image
                and "album" in track_data["track"]
                and "image" in track_data["track"]["album"]
            ):
                track_image = next(
                    (
                        img["#text"]
                        for img in reversed(track_data["track"]["album"]["image"])
                        if img.get("#text")
                    ),
                    None,
                )

            if not track_image and "image" in track_data["track"]:
                track_image = next(
                    (
                        img["#text"]
                        for img in reversed(track_data["track"]["image"])
                        if img.get("#text")
                    ),
                    None,
                )

            if track_image:
                if track_image.startswith("http://"):
                    track_image = track_image.replace("http://", "https://", 1)
                embed.set_thumbnail(url=track_image)

        await ctx.send(embed=embed)

    @globalwhoknows.command(
        name="album",
        description="Shows the top 15 users who listen to an album globally.",
    )
    @app_commands.describe(
        album="The album (optional, uses your currently playing album if not specified)",
        artist="The artist (optional, only needed if album is specified and you want to override the artist)",
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def album(self, ctx: Context, album: str = None, artist: str = None):
        """Shows who listens to a specific album the most across all servers."""
        if ctx.guild:
            await ctx.channel.typing()

        if not album:
            username = await self.get_lastfm_username(ctx.author.id)
            if not username:
                await self.error_embed(
                    ctx,
                    "You need to authenticate with Last.fm first using `/lastfm auth`.",
                )
                return

            data = await self.fetch_lastfm_data(
                "user.getRecentTracks", {"user": username, "limit": 1}
            )

            if (
                not data
                or "error" in data
                or not data.get("recenttracks", {}).get("track")
            ):
                await self.error_embed(
                    ctx,
                    "Couldn't fetch your currently playing track. Please specify both album and artist.",
                )
                return

            current_track = data["recenttracks"]["track"][0]
            album = current_track.get("album", {}).get("#text")
            artist = current_track.get("artist", {}).get("#text")

            if not album or not artist:
                await self.error_embed(
                    ctx,
                    "Couldn't determine the album/artist from your currently playing track. Please specify them manually.",
                )
                return

        if not artist:
            await self.error_embed(
                ctx,
                "Please specify both artist and album, or use the command without parameters to use your currently playing track.",
            )
            return

        album_data = await self.fetch_lastfm_data(
            "album.getInfo", {"album": album, "artist": artist}
        )

        if not album_data or "error" in album_data or "album" not in album_data:
            await self.error_embed(
                ctx,
                f"Couldn't find album '{album}' by {artist}. Please check the spelling and try again.",
            )
            return

        records = await self.bot.db.fetch(
            "SELECT discord_id, lastfm_name FROM lastfm_tokens"
        )

        if not records:
            await self.error_embed(
                ctx,
                "No users have connected their Last.fm accounts yet.",
            )
            return

        user_plays = []
        album_name = album_data["album"]["name"]
        artist_name = album_data["album"]["artist"]["name"]
        track_url = album_data["album"].get(
            "url",
            f"https://www.last.fm/music/{quote_plus(artist_name)}/{quote_plus(album_name)}",
        )

        for record in records:
            try:
                user_track_info = await self.fetch_lastfm_data(
                    "album.getInfo",
                    {
                        "album": album_name,
                        "artist": artist_name,
                        "username": record["lastfm_name"],
                    },
                )

                if (
                    user_track_info
                    and "album" in user_track_info
                    and "userplaycount" in user_track_info["album"]
                ):
                    playcount = int(user_track_info["album"].get("userplaycount", 0))
                    if playcount > 0:
                        user_plays.append(
                            (record["discord_id"], record["lastfm_name"], playcount)
                        )
            except Exception as e:
                logger.error(
                    f"Error fetching album info for {record['lastfm_name']}: {e}"
                )
                continue

        user_plays.sort(key=lambda x: x[2], reverse=True)

        embed = discord.Embed(
            title=f"{album_name} by {artist_name} globally",
            url=track_url,
            color=discord.Color(0xFFFFFF),
        )

        if not user_plays:
            embed.description = (
                f"No one has listened to {album_name} by {artist_name} yet."
            )
        else:
            top_users = user_plays[:15]
            leaderboard = []

            for i, (user_id, lastfm_name, plays) in enumerate(top_users, 1):
                try:
                    user = await self.bot.fetch_user(user_id)
                    username = f"{user.name}"
                except:
                    username = f"{lastfm_name}"

                lastfm_profile = f"https://www.last.fm/user/{lastfm_name}"
                formatted_plays = f"{plays:,} play{'s' if plays != 1 else ''}"
                leaderboard.append(
                    f"`{i}.` [{username}]({lastfm_profile}) • **{formatted_plays}**"
                )

            embed.description = "\n".join(leaderboard)

            total_listeners = len(user_plays)
            total_plays = sum(plays for _, _, plays in user_plays)
            avg_plays = (
                round(total_plays / total_listeners, 1) if total_listeners > 0 else 0
            )

            stats = [
                f"{album_name}",
                f"{total_listeners} listener{'s' if total_listeners != 1 else ''}",
                f"{total_plays:,} play{'s' if total_plays != 1 else ''}",
                f"{avg_plays} avg",
            ]

            embed.set_footer(text=" • ".join(stats))

            track_image = None
            if "album" in album_data and "image" in album_data["album"]:
                track_image = next(
                    (
                        img["#text"]
                        for img in reversed(album_data["album"]["image"])
                        if img.get("#text")
                    ),
                    None,
                )

            if not track_image and "image" in album_data.get("album", {}):
                track_image = next(
                    (
                        img["#text"]
                        for img in reversed(album_data["album"]["image"])
                        if img.get("#text")
                    ),
                    None,
                )

            if not track_image:
                track_image = await self.get_spotify_cover(artist_name, album_name)

            if track_image:
                if track_image.startswith("http://"):
                    track_image = track_image.replace("http://", "https://", 1)
                embed.set_thumbnail(url=track_image)

        await ctx.send(embed=embed)

    @command(name="whoknows", aliases=["wk"])
    async def whoknows_shortcut(self, ctx: Context, *, artist: str = None):
        """Shortcut for lastfm whoknows command"""
        cmd = self.bot.get_command("lastfm whoknows")
        if cmd:
            await ctx.invoke(cmd, artist=artist)
        else:
            await ctx.send("Could not find the whoknows command.")

    @command(name="wktrack", aliases=["whoknowstrack", "wkt"])
    async def whoknowstrack_shortcut(self, ctx: Context, *, track: str = None):
        """Shortcut for lastfm whoknowstrack command"""
        cmd = self.bot.get_command("lastfm whoknows track")
        if cmd:
            await ctx.invoke(cmd, track=track)
        else:
            await ctx.send("Could not find the whoknowstrack command.")

    @command(name="wkalbum", aliases=["whoknowsalbum", "wka"])
    async def whoknowsalbum_shortcut(self, ctx: Context, *, album: str = None):
        """Shortcut for lastfm whoknowsalbum command"""
        cmd = self.bot.get_command("lastfm whoknows album")
        if cmd:
            await ctx.invoke(cmd, album=album)
        else:
            await ctx.send("Could not find the whoknowsalbum command.")

    @command(name="globalwhoknows", aliases=["gwk"])
    async def globalwhoknows_shortcut(self, ctx: Context, *, artist: str = None):
        """Shortcut for lastfm globalwhoknows command"""
        cmd = self.bot.get_command("lastfm globalwhoknows")
        if cmd:
            await ctx.invoke(cmd, artist=artist)
        else:
            await ctx.send("Could not find the globalwhoknows command.")

    @command(name="globalwhoknowstrack", aliases=["gwktrack", "gwkt"])
    async def globalwhoknowstrack_shortcut(self, ctx: Context, *, track: str = None):
        """Shortcut for lastfm globalwhoknowstrack command"""
        cmd = self.bot.get_command("lastfm globalwhoknows track")
        if cmd:
            await ctx.invoke(cmd, track=track)
        else:
            await ctx.send("Could not find the globalwhoknowstrack command.")

    @command(name="globalwhoknowsalbum", aliases=["gwkalbum", "gwka"])
    async def globalwhoknowsalbum_shortcut(self, ctx: Context, *, album: str = None):
        """Shortcut for lastfm globalwhoknowsalbum command"""
        cmd = self.bot.get_command("lastfm globalwhoknows album")
        if cmd:
            await ctx.invoke(cmd, album=album)
        else:
            await ctx.send("Could not find the globalwhoknowsalbum command.")

    @Cog.listener(name="on_message")
    async def on_message(self, message: discord.Message):
        if message.author.bot and message.author.id == self.bot.user.id:
            if message.content.lower().startswith((",fm", "-fm")):
                ctx = await self.bot.get_context(message)
                await self.fm(ctx)
