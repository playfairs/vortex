# THIS IS A $UICIDEBOYS COG NOT A SUICIDE COG

import discord
from discord.ext import commands
from discord.ext.commands import (
    Cog,
    Context,
    group,
    command,
)
from typing import Optional
import base64
import os
import logging
import aiohttp
import re

logger = logging.getLogger(__name__)


class Suicide(Cog, description="View commands in Suicide"):
    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.spotify_token = os.getenv("SPOTIFY_CLIENT_ID")
        self.spotify_secret = os.getenv("SPOTIFY_CLIENT_SECRET")

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

    async def fetch_spotify_cover(self, artist: str, track: str) -> Optional[str]:
        """Compatibility wrapper requested by user; delegates to get_spotify_cover"""
        return await self.get_spotify_cover(artist, track)

    def _parse_spotify_track_id(self, url_or_id: str) -> Optional[str]:
        """Extract a Spotify track ID from a URL or return the input if it already looks like an ID."""
        if not url_or_id:
            return None
        url_or_id = url_or_id.strip()
        if "open.spotify.com/track/" in url_or_id:
            core = url_or_id.split("?")[0]
            try:
                return core.rstrip("/").split("/track/")[-1]
            except Exception:
                return None
        if re.fullmatch(r"[A-Za-z0-9]{22}", url_or_id):
            return url_or_id
        return None

    async def fetch_spotify_track_info(self, url_or_id: str) -> Optional[dict]:
        """Fetch track name, artists, album, cover URL from Spotify by track URL/ID."""
        track_id = self._parse_spotify_track_id(url_or_id)
        if not track_id:
            logger.warning(f"Invalid Spotify track identifier: {url_or_id}")
            return None
        if not getattr(self, "spotify_token", None) or not getattr(
            self, "spotify_secret", None
        ):
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
                        logger.error(
                            f"Spotify auth error {auth_response.status}: {await auth_response.text()}"
                        )
                        return None
                    token_data = await auth_response.json()
                    access_token = token_data.get("access_token")
                    if not access_token:
                        logger.error("No access token received from Spotify")
                        return None

                headers = {"Authorization": f"Bearer {access_token}"}
                track_url = f"https://api.spotify.com/v1/tracks/{track_id}"
                async with session.get(track_url, headers=headers) as resp:
                    if resp.status != 200:
                        logger.error(
                            f"Spotify track error {resp.status}: {await resp.text()}"
                        )
                        return None
                    data = await resp.json()
                    name = data.get("name") or "Unknown Track"
                    artists = (
                        ", ".join(
                            [
                                a.get("name", "Unknown Artist")
                                for a in data.get("artists", [])
                            ]
                        )
                        or "Unknown Artist"
                    )
                    album = (data.get("album") or {}).get("name") or "Unknown Album"
                    images = (data.get("album") or {}).get("images") or []
                    cover_url = images[0].get("url") if images else None
                    external_url = (data.get("external_urls") or {}).get("spotify")
                    return {
                        "name": name,
                        "artists": artists,
                        "album": album,
                        "cover_url": cover_url,
                        "url": external_url,
                    }
        except Exception as e:
            logger.error(f"Error in fetch_spotify_track_info: {e}", exc_info=True)
            return None

    async def _send_kys_embed(self, ctx: Context, part: Optional[str] = None):
        if part is None:
            alias = "I"
        else:
            alias = str(part).strip().upper()
        aliases = {
            "1": "I",
            "2": "II",
            "3": "III",
            "4": "IV",
            "5": "V",
            "I": "I",
            "II": "II",
            "III": "III",
            "IV": "IV",
            "V": "V",
        }
        key = aliases.get(alias, "I")

        mapping = {
            "I": {
                "url": "https://open.spotify.com/track/4Gy5kycvHxatuBiNQBCPA6?si=95565d9542514cce",
                "fallback_title": "KILL YOURSELF",
                "fallback_desc": "$uicideboys \nKILL YOURSELF Part I: The $uicide Saga",
                "fetch_artist": "$uicideboy$",
                "fetch_track": "Kill Yourself (Part I)",
            },
            "II": {
                "url": "https://open.spotify.com/track/1y8QivbbrlKYjjIgq7vwed?si=cc1098c93e974d12",
                "fallback_title": "Kill Yourself (Part II)",
                "fallback_desc": "$uicideboys \nGray/Grey",
                "fetch_artist": "$uicideboy$",
                "fetch_track": "Kill Yourself (Part II)",
            },
            "III": {
                "url": "https://open.spotify.com/track/0kEZlJh4mK1QRfb3CT5LPk?si=af519753d900472a",
                "fallback_title": "Kill Yourself (Part III)",
                "fallback_desc": "$uicideboys \nMy Liver Will Handle What My Heart Can't",
                "fetch_artist": "$uicideboy$",
                "fetch_track": "Kill Yourself (Part III)",
            },
            "IV": {
                "url": "https://open.spotify.com/track/3LLYTletE6uiRZ0hgMSrCN?si=03fc34d81bad443a",
                "fallback_title": "Kill Yourself (Part IV)",
                "fallback_desc": "$uicideboys\nKill Yourself (Part IV)",
                "fetch_artist": "$uicideboy$",
                "fetch_track": "Kill Yourself (Part IV)",
            },
            "V": {
                "url": "https://open.spotify.com/track/2oZNJdNHO4Kkw8Dh4Bwf5b?si=2bf3459f8c714194",
                "fallback_title": "Kill Yourself (Part V)",
                "fallback_desc": "$uicideboys\nNew World Depression",
                "fetch_artist": "$uicideboy$",
                "fetch_track": "Kill Yourself (Part V)",
            },
        }

        cfg = mapping[key]
        info = await self.fetch_spotify_track_info(cfg["url"])
        if info:
            embed = discord.Embed(
                title=info["name"],
                description=f"**{info['artists']}**\n> {info['album']}",
                color=discord.Color(0xFFFFFF),
            )
            if info.get("url"):
                embed.url = info["url"]
            if info.get("cover_url"):
                embed.set_thumbnail(url=info["cover_url"])
        else:
            embed = discord.Embed(
                title=cfg["fallback_title"],
                description=cfg["fallback_desc"],
                color=discord.Color(0xFFFFFF),
            )
            clean_url = cfg["url"].split("?")[0]
            embed.url = clean_url
            cover_url = await self.fetch_spotify_cover(
                cfg["fetch_artist"], cfg["fetch_track"]
            )
            if cover_url:
                embed.set_thumbnail(url=cover_url)
        await ctx.send(embed=embed)

    def _normalize_part_input(self, part_text: Optional[str]) -> Optional[str]:
        """Accepts inputs like "V", "5", or "part V" and returns a single token (e.g., "V" or "5").
        Returns None if no usable token is present.
        """
        if not part_text:
            return None
        txt = str(part_text).strip()
        if not txt:
            return None
        tokens = txt.split()
        if not tokens:
            return None
        if tokens[0].lower() == "part" and len(tokens) >= 2:
            return tokens[1]
        return tokens[0]

    @group(name="kill", description="Kill Yourself")
    async def kill(self, ctx: Context):
        pass

    @kill.command(name="yourself", description="Kill Yourself")
    async def kys(self, ctx: Context, *, part: Optional[str] = None):
        normalized = self._normalize_part_input(part)
        await self._send_kys_embed(ctx, normalized)

    @command(name="kys", description="Shortcut for 'kill yourself'")
    async def kys_cmd(self, ctx: Context, *, part: Optional[str] = None):
        normalized = self._normalize_part_input(part)
        await self._send_kys_embed(ctx, normalized)
