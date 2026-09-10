import discord
from discord.ext import commands
from discord.ext.commands import Context, Cog, command
from discord import app_commands
from typing import Optional
from vortex import vortex
import functools


class Invocation:
    def __init__(self, restrict_to_owner: bool = False):
        self.restrict_to_owner = restrict_to_owner

    def __call__(self, func):
        @functools.wraps(func)
        async def wrapper(self_instance, ctx: Context, *args, **kwargs):
            if (
                self.restrict_to_owner
                and ctx.author.id != self_instance.bot.owner_ids[0]
            ):
                return await ctx.send("This command can only be used by the bot owner.")
            return await func(self_instance, ctx, *args, **kwargs)

        return wrapper


class Invocations(Cog, description="View commands in Invocations."):
    def __init__(self, bot: vortex):
        self.bot = bot
        self.sniped_messages = {}

    @property
    def restricted(self):
        return app_commands.checks.has_any_role(*self.bot.owner_ids)

    @command(
        name="invocations",
        help="Shows detailed information about all existing invocations.",
    )
    @Invocation(restrict_to_owner=True)
    async def show_invocations(self, ctx: Context):
        """Displays detailed information about all existing invocations."""
        await ctx.send_help(ctx.command)

    @command(name="loreadd", aliases=["addlore", "al", "clip"])
    async def add_lore(self, ctx: Context):
        """Adds a new lore entry."""
        # await ctx.send("Lore is currently disabled.")
        lore = self.bot.get_cog("Lore")
        if lore:
            try:
                await lore.add_lore(ctx)
            except Exception as e:
                await ctx.send(f"An error occurred: {e}")
        else:
            await ctx.send("cogs.lore is not loaded.")

    @command(name="asslore", description="Adds a new lore entry.")
    async def ass_lore(self, ctx: Context):
        """Adds a new lore entry."""
        await ctx.send("What the fuck..? You mean addlore..?? 😭")
