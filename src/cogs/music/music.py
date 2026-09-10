import discord
import yt_dlp
from datetime import timedelta, datetime
import os
import asyncio
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

from discord import FFmpegPCMAudio, Color, app_commands, ui
from discord.ext.commands import (
    Cog,
    command,
    group,
    has_permissions,
    hybrid_command as hybrid,
    hybrid_group,
    Context,
)
from pathlib import Path
from discord.ext import commands, tasks
from discord.ext.commands import Cog, group, has_permissions
from discord.ui import View, Button
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import BatchHttpRequest

from vortex import vortex
from config import DISCORD, BUTTONS
from typing import Optional, Union
from discord.player import AudioSource
from data.cookies import Cookies


class Music(Cog, description="View commands in Music."):
    def __init__(self, bot: vortex):
        self.bot = bot
        self.queues = {}
        self.no_context = {}
        self.ydl_opts = {
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "m4a",
                    "preferredquality": "192",
                }
            ],
            "quiet": True,
            "no_warnings": True,
            "extract_flat": "in_playlist",
            "force_generic_extractor": True,
            "nocheckcertificate": True,
            "ignoreerrors": True,
            "no_playlist": True,
            "youtube_include_dash_manifest": False,
            "youtube_include_hls_manifest": False,
            "cookiefile": Cookies.cookies_path,
            "extractor_args": {
                "youtube": {"player_client": ["tvhtml5", "android", "web"]}
            },
            "retries": 3,
            "fragment_retries": 3,
            "socket_timeout": 30,
            "noprogress": True,
        }
        self.FFMPEG_OPTIONS = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "options": "-vn",
        }
        self.youtube = build("youtube", "v3", developerKey=os.getenv("YOUTUBE_KEY"))

    async def _on_batch_response(self, request_id, response, exception):
        if exception:
            print(f"Error fetching video details: {exception}")
        else:
            video = response["items"][0]
            self.no_context[video["id"]] = {
                "title": video["snippet"]["title"],
                "url": f"https://www.youtube.com/watch?v={video['id']}",
                "thumbnail": video["snippet"]["thumbnails"]["high"]["url"],
            }

    async def spotify_to_youtube(self, url: str) -> Optional[str]:
        """Convert a Spotify track URL to a YouTube URL using yt-dlp for searching."""
        try:
            if "open.spotify.com/track/" not in url:
                return None

            track_id = (
                url.split("open.spotify.com/track/")[1].split("?")[0].split("/")[0]
            )

            spotify = spotipy.Spotify(
                auth_manager=spotipy.oauth2.SpotifyClientCredentials(
                    client_id=os.getenv("SPOTIFY_CLIENT_ID"),
                    client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
                )
            )

            try:
                track = spotify.track(track_id)
                if not track:
                    return None

                track_name = track["name"]
                artist_name = track["artists"][0]["name"]

                search_queries = [
                    f"{track_name} {artist_name} official",
                    f"{track_name} {artist_name}",
                    f"{track_name} by {artist_name}",
                ]

                for query in search_queries:
                    try:
                        ydl_opts = {
                            "format": "bestaudio/best",
                            "quiet": True,
                            "extract_flat": True,
                            "skip_download": True,
                            "force_generic_extractor": True,
                        }

                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            search_results = await self.bot.loop.run_in_executor(
                                None,
                                lambda: ydl.extract_info(
                                    f"ytsearch:{query}", download=False
                                ),
                            )

                            if (
                                search_results
                                and "entries" in search_results
                                and search_results["entries"]
                            ):
                                video_url = search_results["entries"][0].get("url")
                                if video_url:
                                    return video_url

                    except Exception as e:
                        continue

                return None

            except Exception as e:
                return None

        except Exception as e:
            return None

    async def get_youtube_thumbnail(self, video_id: str) -> str:
        """Get the highest resolution thumbnail URL from a YouTube video ID."""
        return f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"

    async def get_spotify_track_info(self, track_url: str) -> tuple[str, str]:
        """Get track and artist information from Spotify."""
        try:
            if "open.spotify.com/track/" not in track_url:
                return None, None

            track_id = (
                track_url.split("open.spotify.com/track/")[1]
                .split("?")[0]
                .split("/")[0]
            )

            spotify = spotipy.Spotify(
                auth_manager=spotipy.oauth2.SpotifyClientCredentials(
                    client_id=os.getenv("SPOTIFY_CLIENT_ID"),
                    client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
                )
            )

            track = spotify.track(track_id)
            if track:
                artist = track.get("artists", [{}])[0].get("name", "Unknown Artist")
                title = track.get("name", "Unknown Title")
                return title, artist

        except Exception as e:
            print(f"Error getting Spotify track info: {e}")
        return None, None

    async def play_next(self, ctx: Context):
        """Play the next song in the queue."""
        if not hasattr(ctx.voice_client, "queue"):
            return

        if not ctx.voice_client.queue:
            return

        url = ctx.voice_client.queue.pop(0)
        await self.play_url(ctx, url, from_queue=True)

        if not ctx.voice_client.queue:
            await ctx.voice_client.disconnect()

    async def add_to_queue(self, ctx: Context, url: str, play_next: bool = False):
        """Add a song to the queue."""
        if not hasattr(ctx.voice_client, "queue"):
            ctx.voice_client.queue = []

        track_info = {"url": url, "title": "Loading..."}

        if play_next:
            ctx.voice_client.queue.insert(0, track_info)
        else:
            ctx.voice_client.queue.append(track_info)

        return len(ctx.voice_client.queue)

    async def play_url(
        self, ctx: Context, url: str, from_queue: bool = False, retry_count: int = 0
    ):
        """Plays a song from a URL with retry logic."""

        def after_playing(error):
            if error:
                print(f"Player error: {error}")

            if not hasattr(ctx.voice_client, "queue") or not ctx.voice_client.queue:
                asyncio.run_coroutine_threadsafe(
                    self.disconnect_after_delay(ctx), self.bot.loop
                )
                return

            next_track = ctx.voice_client.queue.pop(0)

            asyncio.run_coroutine_threadsafe(
                self.play_url(ctx, next_track["url"], from_queue=True), self.bot.loop
            )

        try:
            if not hasattr(ctx.voice_client, "queue"):
                ctx.voice_client.queue = []

            if (
                ctx.voice_client.is_playing() or ctx.voice_client.is_paused()
            ) and not from_queue:
                position = await self.add_to_queue(ctx, url)
                await ctx.send(f"Added to queue at position {position}")
                return

            try:
                with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                    info = await self.bot.loop.run_in_executor(
                        None, lambda: ydl.extract_info(url, download=False)
                    )
            except Exception as e:
                print(f"Error extracting info: {e}")
                if retry_count < 2:
                    await asyncio.sleep(1)
                    return await self.play_url(ctx, url, from_queue, retry_count + 1)
                raise

            if not info:
                if not from_queue:
                    await ctx.send(
                        "Could not get video information. The video might be unavailable."
                    )
                return

            if "entries" in info:
                info = info["entries"][0]

            if (
                from_queue
                and hasattr(ctx.voice_client, "queue")
                and ctx.voice_client.queue
            ):
                for track in ctx.voice_client.queue:
                    if track["url"] == url:
                        track["title"] = info.get("title", "Unknown Title")
                        break

            format_selector = yt_dlp.YoutubeDL(self.ydl_opts).build_format_selector(
                "bestaudio/best"
            )
            best_format = next(iter(format_selector(info)), None)
            if not best_format:
                raise Exception("No suitable format found")

            audio_url = best_format["url"]

            voice_client = ctx.voice_client or await ctx.author.voice.channel.connect()

            try:
                audio_source = FFmpegPCMAudio(audio_url, **self.FFMPEG_OPTIONS)

                if voice_client.is_playing() or voice_client.is_paused():
                    voice_client.stop()

                track_title = info.get("title", "Unknown Title")
                artist_name = "Unknown Artist"

                if "open.spotify.com/track/" in url:
                    spotify_title, spotify_artist = await self.get_spotify_track_info(
                        url
                    )
                    if spotify_title and spotify_artist:
                        track_title = spotify_title
                        artist_name = spotify_artist

                if not hasattr(voice_client, "current_song"):
                    voice_client.current_song = {}

                voice_client.current_song = {
                    "title": track_title,
                    "artist": artist_name,
                    "url": url,
                    "duration": info.get("duration", 0),
                }

                voice_client.play(audio_source, after=after_playing)

                if not from_queue:
                    duration = info.get("duration", 0)
                    end_time = int(
                        (datetime.now() + timedelta(seconds=duration)).timestamp()
                    )

                    video_id = None
                    if "youtube.com/watch?v=" in url:
                        video_id = url.split("youtube.com/watch?v=")[1].split("&")[0]
                    elif "youtu.be/" in url:
                        video_id = url.split("youtu.be/")[1].split("?")[0]

                    container = discord.ui.Container()

                    thumbnail = None
                    if video_id:
                        thumbnail = await self.get_youtube_thumbnail(video_id)

                    content = f"Track: {track_title}\n"
                    content += f"Artist: {artist_name}\n"
                    content += f"Ends: <t:{end_time}:R>"

                    container.add_item(
                        discord.ui.Section(
                            discord.ui.TextDisplay(
                                content=f"### Now Playing\n{content}"
                            ),
                            accessory=(
                                discord.ui.Thumbnail(media=thumbnail)
                                if thumbnail
                                else None
                            ),
                        )
                    )

                    view = discord.ui.LayoutView()
                    view.add_item(container)
                    await ctx.send(view=view)

            except Exception as e:
                print(f"Error creating audio source: {e}")
                if not from_queue:
                    await ctx.send(
                        f"An error occurred while trying to play the song: {str(e)}"
                    )
                if hasattr(ctx.voice_client, "queue") and ctx.voice_client.queue:
                    await self.play_next(ctx)

        except Exception as e:
            print(f"Error in play_url: {e}")
            if not from_queue:
                await ctx.send(
                    f"An error occurred while trying to play the song: {str(e)}"
                )

            if hasattr(ctx.voice_client, "queue") and ctx.voice_client.queue:
                await self.play_next(ctx)

    async def disconnect_after_delay(self, ctx: Context, delay: int = 10):
        """Disconnect from voice channel after a delay if queue is empty."""
        await asyncio.sleep(delay)
        if ctx.voice_client and not (
            ctx.voice_client.is_playing() or ctx.voice_client.is_paused()
        ):
            if not hasattr(ctx.voice_client, "queue") or not ctx.voice_client.queue:
                await ctx.voice_client.disconnect()
                await ctx.send("Queue is empty. Leaving voice channel.")

    async def queue(self, ctx: Context):
        """Shows the current queue."""
        if not ctx.voice_client:
            await ctx.send("I'm not connected to a voice channel.")
            return

        if not hasattr(ctx.voice_client, "queue") or not ctx.voice_client.queue:
            await ctx.send("The queue is empty.")
            return

        container = discord.ui.Container()

        if hasattr(ctx.voice_client, "current_song") and ctx.voice_client.current_song:
            current = ctx.voice_client.current_song
            container.add_item(
                discord.ui.TextDisplay(
                    content=f"**Now Playing:** {current.get('title', 'Unknown Title')} - {current.get('artist', 'Unknown Artist')}"
                )
            )

        for i, track in enumerate(ctx.voice_client.queue, 1):
            container.add_item(
                discord.ui.TextDisplay(
                    content=f"{i}. {track.get('title', 'Loading...')}"
                )
            )

        view = discord.ui.LayoutView()
        view.add_item(container)
        await ctx.send("**Queue:**", view=view)

    @hybrid(
        name="play",
        description="Plays a song from YouTube, Spotify, or searches YouTube.",
    )
    @app_commands.describe(
        query="The song name, YouTube URL, or Spotify track URL to play"
    )
    async def play(self, ctx: Context, *, query: str):
        """Plays a song from YouTube, Spotify, or searches YouTube."""
        if not query:
            await ctx.send("Please provide a song name or URL.")
            return

        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("You need to be in a voice channel to play music!")
            return

        voice_client = ctx.voice_client or await ctx.author.voice.channel.connect()

        if voice_client.channel != ctx.author.voice.channel:
            await voice_client.move_to(ctx.author.voice.channel)

        if query.startswith(("http://", "https://")):
            if any(domain in query for domain in ["youtube.com", "youtu.be"]):
                url = query
            elif "open.spotify.com/track/" in query:
                await ctx.send("Searching for the track on YouTube...")
                url = await self.spotify_to_youtube(query)
                if not url:
                    await ctx.send(
                        "Could not find a matching YouTube video for this Spotify track."
                    )
                    return
            else:
                await ctx.send(
                    "Unsupported URL. Please provide a valid YouTube or Spotify track URL."
                )
                return
        else:
            await ctx.send(f"Searching YouTube for: {query}")
            ydl_opts = {
                "format": "bestaudio/best",
                "quiet": True,
                "extract_flat": True,
                "skip_download": True,
            }

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    search_results = await self.bot.loop.run_in_executor(
                        None,
                        lambda: ydl.extract_info(f"ytsearch:{query}", download=False),
                    )

                    if (
                        search_results
                        and "entries" in search_results
                        and search_results["entries"]
                    ):
                        url = search_results["entries"][0].get("url")
                        if not url:
                            await ctx.send(
                                "Could not find any results for that search."
                            )
                            return
                    else:
                        await ctx.send("No results found for that search.")
                        return

            except Exception as e:
                print(f"Error searching YouTube: {e}")
                await ctx.send("An error occurred while searching for that song.")
                return

        if voice_client.is_playing() or voice_client.is_paused():
            position = await self.add_to_queue(ctx, url)
            await ctx.send(f"Added to queue at position {position}")
        else:
            await self.play_url(ctx, url)

    @hybrid(name="pause", description="Pauses the current song.")
    async def pause(self, ctx: Context):
        """Pauses the current song."""
        if not ctx.voice_client:
            await ctx.send("I'm not connected to a voice channel.")
            return

        if not ctx.voice_client.is_playing():
            await ctx.send("I'm not playing anything.")
            return

        ctx.voice_client.pause()
        await ctx.send("Paused the song.")

    @hybrid(name="resume", description="Resumes the current song.")
    async def resume(self, ctx: Context):
        """Resumes the current song."""
        if not ctx.voice_client:
            await ctx.send("I'm not connected to a voice channel.")
            return

        if not ctx.voice_client.is_paused():
            if ctx.voice_client.is_playing():
                await ctx.send("The song is already playing.")
            else:
                await ctx.send("There's nothing to resume.")
            return

        ctx.voice_client.resume()
        await ctx.send("Resumed the song.")

    @hybrid(name="stop", description="Stops the current song.")
    async def stop(self, ctx: Context):
        """Stops the current song."""
        if not ctx.voice_client:
            await ctx.send("I'm not connected to a voice channel.")
            return

        ctx.voice_client.stop()
        await ctx.voice_client.disconnect()
        await ctx.send("Stopped the song.")

    @hybrid(name="skip", description="Skips the current song.")
    async def skip(self, ctx: Context):
        """Skips the current song."""
        if not ctx.voice_client:
            await ctx.send("I'm not connected to a voice channel.")
            return

        if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
            await ctx.send("I'm not playing anything right now.")
            return

        ctx.voice_client.stop()
        await ctx.send("Skipped the current song.")
