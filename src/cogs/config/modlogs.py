from .configuration import Config
from discord import app_commands
from discord.ext import commands
from discord.ext.commands import (
    Cog,
    Context,
    has_permissions,
    hybrid_group,
    hybrid_command as hybrid,
)
from vortex import vortex
import discord


class Modlogs(Cog):
    def __init__(self, bot: vortex):
        self.bot = bot
        self.db = bot.db

    async def actionmap(self, action: str):
        return {
            "ban": "Banned",
            "kick": "Kicked",
            "mute": "Muted",
            "unmute": "Unmuted",
            "softban": "Softbanned",
            "unban": "Unbanned",
            "prune": "Pruned",
            "warn": "Warned",
        }[action]
