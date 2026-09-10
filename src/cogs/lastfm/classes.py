import discord
import pylast

from discord.ext import commands, tasks
from discord.ext.commands import Cog, command, group
from discord.ui import Button, View
from discord import app_commands
from config import BUTTONS
import os
import requests
from discord.ui import Modal, TextInput
from typing import List
from managers.classes import Emojis


class CREATEDB:
    def __init__(self, db, user_id: int, username: str, period: str):
        self.db = db
        self.user_id = user_id
        self.username = username
        self.period = period

    async def cog_load(self):
        """Create necessary database tables on cog load"""
        async with self.db.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS lastfm_tokens (
                    user_id BIGINT PRIMARY KEY,
                    lastfm_username TEXT NOT NULL
                )
            """
            )

            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS lastfm_custom_commands (
                    user_id BIGINT PRIMARY KEY,
                    emoji TEXT NOT NULL
                )
            """
            )

            records = await conn.fetch(
                "SELECT user_id, emoji FROM lastfm_custom_commands"
            )
            self.custom_commands = {
                record["user_id"]: record["emoji"] for record in records
            }

            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS lastfm_continuous_tracking (
                    user_id BIGINT PRIMARY KEY,
                    lastfm_username TEXT NOT NULL,
                    tracking_channel_id BIGINT NOT NULL
                )
            """
            )


class ArtistPaginator(View):
    def __init__(self, author_id: int, artists: List[dict], username: str, period: str):
        super().__init__(timeout=60)
        self.author_id = author_id
        self.artists = artists
        self.page = 1
        self.max_page = (len(artists) + 9) // 10
        self.username = username
        self.period = period

        self.prev_page.disabled = self.page == 1
        self.next_page.disabled = self.page >= self.max_page
        self.page_button.label = f"Page {self.page}/{self.max_page}"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "You can't use these buttons.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="", style=discord.ButtonStyle.gray, emoji=Emojis.left)
    async def prev_page(self, interaction: discord.Interaction, button: Button):
        self.page = max(1, self.page - 1)

        self.prev_page.disabled = self.page <= 1
        self.next_page.disabled = False
        self.page_button.label = f"Page {self.page}/{self.max_page}"

        await interaction.response.edit_message(
            embed=self.get_page_content(), view=self
        )

    @discord.ui.button(style=discord.ButtonStyle.gray, disabled=True)
    async def page_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        pass

    @discord.ui.button(
        label="",
        style=discord.ButtonStyle.gray,
        emoji=Emojis.right,
    )
    async def next_page(self, interaction: discord.Interaction, button: Button):
        self.page = min(self.max_page, self.page + 1)

        self.prev_page.disabled = False
        self.next_page.disabled = self.page >= self.max_page
        self.page_button.label = f"Page {self.page}/{self.max_page}"

        await interaction.response.edit_message(
            embed=self.get_page_content(), view=self
        )

    def get_page_content(self) -> discord.Embed:
        start_idx = (self.page - 1) * 10
        page_artists = self.artists[start_idx : start_idx + 10]

        description = []
        for idx, artist in enumerate(page_artists, start_idx + 1):
            name = artist["name"]
            plays = artist["playcount"]
            url = artist["url"]
            description.append(f"{idx}. [{name}]({url}) - {plays} plays")

        embed = discord.Embed(
            description="\n".join(description), color=discord.Color(0xFFFFFF)
        )

        period_display = {
            "overall": "All Time",
            "7day": "Weekly",
            "1month": "Monthly",
            "3month": "3 Months",
            "6month": "6 Months",
            "12month": "Yearly",
            "at": "All Time",
            "7d": "Weekly",
            "1m": "Monthly",
            "3m": "3 Months",
            "6m": "6 Months",
            "12m": "Yearly",
        }

        display_period = period_display.get(self.period, self.period)

        embed.set_author(name=f"{self.username}'s Top Artists ({display_period})")
        embed.set_footer(
            text=f"Page {self.page}/{self.max_page} - {len(self.artists)} different artists in this time period"
        )

        return embed

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)


class AlbumPaginator(View):
    def __init__(self, author_id: int, albums: List[dict], username: str, period: str):
        super().__init__(timeout=60)
        self.author_id = author_id
        self.albums = albums
        self.page = 1
        self.max_page = (len(albums) + 9) // 10
        self.username = username
        self.period = period

        self.prev_page.disabled = self.page == 1
        self.next_page.disabled = self.page >= self.max_page
        self.page_button.label = f"Page {self.page}/{self.max_page}"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "You can't use these buttons.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="", style=discord.ButtonStyle.gray, emoji=Emojis.left)
    async def prev_page(self, interaction: discord.Interaction, button: Button):
        self.page = max(1, self.page - 1)

        self.prev_page.disabled = self.page <= 1
        self.next_page.disabled = False
        self.page_button.label = f"Page {self.page}/{self.max_page}"

        await interaction.response.edit_message(
            embed=self.get_page_content(), view=self
        )

    @discord.ui.button(style=discord.ButtonStyle.gray, disabled=True)
    async def page_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        pass

    @discord.ui.button(
        label="",
        style=discord.ButtonStyle.gray,
        emoji=Emojis.right,
    )
    async def next_page(self, interaction: discord.Interaction, button: Button):
        self.page = min(self.max_page, self.page + 1)

        self.prev_page.disabled = False
        self.next_page.disabled = self.page >= self.max_page
        self.page_button.label = f"Page {self.page}/{self.max_page}"

        await interaction.response.edit_message(
            embed=self.get_page_content(), view=self
        )

    def get_page_content(self) -> discord.Embed:
        start_idx = (self.page - 1) * 10
        page_albums = self.albums[start_idx : start_idx + 10]

        description = []
        for idx, album in enumerate(page_albums, start_idx + 1):
            name = album["name"]
            plays = album["playcount"]
            url = album["url"]
            description.append(f"{idx}. [{name}]({url}) - {plays} plays")

        embed = discord.Embed(
            description="\n".join(description), color=discord.Color(0xFFFFFF)
        )

        period_display = {
            "overall": "All Time",
            "7day": "Weekly",
            "1month": "Monthly",
            "3month": "3 Months",
            "6month": "6 Months",
            "12month": "Yearly",
            "at": "All Time",
            "7d": "Weekly",
            "1m": "Monthly",
            "3m": "3 Months",
            "6m": "6 Months",
            "12m": "Yearly",
        }

        display_period = period_display.get(self.period, self.period)

        embed.set_author(name=f"{self.username}'s Top Albums ({display_period})")
        embed.set_footer(
            text=f"Page {self.page}/{self.max_page} - {len(self.albums)} different albums in this time period"
        )

        return embed

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)


class TrackPaginator(View):
    def __init__(self, author_id: int, tracks: List[dict], username: str, period: str):
        super().__init__(timeout=60)
        self.author_id = author_id
        self.tracks = tracks
        self.page = 1
        self.max_page = (len(tracks) + 9) // 10
        self.username = username
        self.period = period

        self.prev_page.disabled = self.page == 1
        self.next_page.disabled = self.page >= self.max_page
        self.page_button.label = f"Page {self.page}/{self.max_page}"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "You can't use these buttons.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="", style=discord.ButtonStyle.gray, emoji=Emojis.left)
    async def prev_page(self, interaction: discord.Interaction, button: Button):
        self.page = max(1, self.page - 1)

        self.prev_page.disabled = self.page <= 1
        self.next_page.disabled = False
        self.page_button.label = f"Page {self.page}/{self.max_page}"

        await interaction.response.edit_message(
            embed=self.get_page_content(), view=self
        )

    @discord.ui.button(style=discord.ButtonStyle.gray, disabled=True)
    async def page_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        pass

    @discord.ui.button(
        label="",
        style=discord.ButtonStyle.gray,
        emoji=Emojis.right,
    )
    async def next_page(self, interaction: discord.Interaction, button: Button):
        self.page = min(self.max_page, self.page + 1)

        self.prev_page.disabled = False
        self.next_page.disabled = self.page >= self.max_page
        self.page_button.label = f"Page {self.page}/{self.max_page}"

        await interaction.response.edit_message(
            embed=self.get_page_content(), view=self
        )

    def get_page_content(self) -> discord.Embed:
        start_idx = (self.page - 1) * 10
        page_tracks = self.tracks[start_idx : start_idx + 10]

        description = []
        for idx, track in enumerate(page_tracks, start_idx + 1):
            name = track["name"]
            plays = track["playcount"]
            url = track["url"]
            description.append(f"{idx}. [{name}]({url}) - {plays} plays")

        embed = discord.Embed(
            description="\n".join(description), color=discord.Color(0xFFFFFF)
        )

        period_display = {
            "overall": "All Time",
            "7day": "Weekly",
            "1month": "Monthly",
            "3month": "3 Months",
            "6month": "6 Months",
            "12month": "Yearly",
            "at": "All Time",
            "7d": "Weekly",
            "1m": "Monthly",
            "3m": "3 Months",
            "6m": "6 Months",
            "12m": "Yearly",
        }

        display_period = period_display.get(self.period, self.period)

        embed.set_author(name=f"{self.username}'s Top Tracks ({display_period})")
        embed.set_footer(
            text=f"Page {self.page}/{self.max_page} - {len(self.tracks)} different tracks in this time period"
        )

        return embed

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)
