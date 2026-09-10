# can someone remove this cog, I don't even think I have it set to load but its just taking up space

import discord
from discord.ext import commands
import os
import jishaku
from platform import python_version
from managers.classes import Media


class Developer(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.version = "v1.1.1"
        self.discord_version = discord.__version__
        self.jishaku_version = jishaku.__version__
        self.python_version = python_version()

    @commands.command(name="patch")
    @commands.has_permissions(manage_guild=True)
    async def patch(self, ctx):
        """Sends the patch update from the patch.txt file with role mention."""
        patch_file_path = os.path.join("cogs", "developer", "patch", "patch.md")

        if not os.path.exists(patch_file_path):
            await ctx.send("No patch notes are available at the moment.")
            await ctx.message.delete()
            return

        with open(patch_file_path, "r") as file:
            patch_notes = file.read()

        role = discord.utils.get(ctx.guild.roles, name="Heresy Updates")
        if role is None:
            await ctx.send("Role not found.")
            await ctx.message.delete()
            return

        embed = discord.Embed(
            title=f"**{self.version} Release Update**",
            description=patch_notes,
            color=0xFFFFFF,
        )
        embed.set_footer(
            text=f"vortex {self.version} • discord.py {self.discord_version} • Jishaku {self.jishaku_version} • Python {self.python_version}"
        )
        embed.set_thumbnail(url=Media.vortex)

        await ctx.send(
            content=role.mention,
            embed=embed,
            allowed_mentions=discord.AllowedMentions(roles=True),
        )
        await ctx.message.delete()

    @commands.command(name="hotfix")
    @commands.has_permissions(manage_guild=True)
    async def hotfix(self, ctx):
        """Sends the hotfix update from the hotfix.txt file with role mention."""
        hotfix_file_path = os.path.join("cogs", "developer", "patch", "hotfix.md")

        if not os.path.exists(hotfix_file_path):
            await ctx.send("No hotfix notes are available at the moment.")
            await ctx.message.delete()
            return

        try:
            with open(hotfix_file_path, "r", encoding="utf-8") as file:
                patch_notes = file.read()
        except UnicodeDecodeError as e:
            await ctx.send(
                f"Failed to read the hotfix file due to encoding issues: {str(e)}"
            )
            await ctx.message.delete()
            return

        role = discord.utils.get(ctx.guild.roles, name="Heresy Updates")
        if role is None:
            await ctx.send("Role not found.")
            await ctx.message.delete()
            return

        embed = discord.Embed(
            title=f"**{self.version} Hotfix**", description=patch_notes, color=0x3498DB
        )
        embed.set_footer(
            text=f"vortex {self.version} • discord.py {self.discord_version} • Jishaku {self.jishaku_version}"
        )
        embed.set_thumbnail(url=Media.vortex)

        await ctx.send(
            content=role.mention,
            embed=embed,
            allowed_mentions=discord.AllowedMentions(roles=True),
        )
        await ctx.message.delete()
