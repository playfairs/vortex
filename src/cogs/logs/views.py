from discord.ui import View, Button
from discord import Interaction, Embed, ButtonStyle
from discord.ext import commands
from discord.ext.commands import (
    Context,
    Cog,
    group,
    hybrid_command as hyrbid,
    command,
    has_permissions,
)

from .actionmap import ActionMap


class ModLogsView(View, ActionMap):
    def __init__(self, ctx: Context):
        super().__init__(timeout=None)
        self.ctx = ctx
