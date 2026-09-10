import discord
from discord import utils
from discord.ext import commands
from vortex import vortex
import aiohttp


class DefaultAvatarManager:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()

    @staticmethod
    def default_avatar(user_id: int) -> str:
        return f"https://cdn.discordapp.com/embed/avatars/{(user_id >> 22) % 6}.png"

    async def get_default_avatar(self, user_id: int) -> str:
        """Get the default Discord avatar URL for a user based on their ID."""
        return self.default_avatar(user_id)

    async def get_user_avatar_or_default(
        self, user: discord.User | discord.Member
    ) -> str:
        """Get user's avatar URL or fallback to default avatar URL if they don't have one."""
        if user.avatar:
            return user.avatar.url
        return await self.get_default_avatar(user.id)

    async def close(self):
        """Close the aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()
