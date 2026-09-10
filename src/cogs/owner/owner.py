import discord
import os
import aiohttp
import pyperclip
import tempfile
import asyncio
import random
import subprocess
import contextlib
import shlex
import urllib
import urllib.parse
import json
import io
import typing
import ast
import playwright
from playwright.async_api import async_playwright
import base64
from discord import (
    AutoModRuleEventType,
    AutoModRuleTriggerType,
    AutoModRuleActionType,
    AutoModTrigger,
    AutoModRuleAction,
)
import traceback
from core.decorators import Decorators
import math

from discord import app_commands, ui
from discord.ext import commands
from discord.ext.commands import (
    Cog,
    command,
    Context,
    group,
    hybrid_command as hybrid,
    hybrid_group,
)
from .servers import ServersView
from typing import (
    Optional,
    Union,
    Any,
    Dict,
    Union as TypingUnion,
)
from selenium import webdriver
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options
from webdriver_manager.firefox import GeckoDriverManager
from io import BytesIO, StringIO
from PIL import ImageGrab
from discord.ext import tasks
from uwuipy import uwuipy
from jishaku.models import copy_context_with
from jishaku.types import ContextT
from jishaku.features.invocation import SlimUserConverter, SlimChannelConverter


from vortex import vortex
from config import BLACKLIST
from managers.classes import Emojis, Media


class Owner(Cog, command_attrs=dict(hidden=True)):
    OVERRIDE_SIGNATURE = TypingUnion[SlimUserConverter, SlimChannelConverter]

    def __init__(self, bot: vortex):
        self.bot = bot
        self.owner_id = 1426711359059394662
        self.session = aiohttp.ClientSession()
        self.users_triggered_bot = []
        self.db = getattr(bot, "db", None)
        self.bot = bot

    async def cog_check(self, ctx: Context) -> bool:
        if ctx.author.id not in self.bot.owner_ids:
            if isinstance(ctx, discord.Interaction):
                await ctx.response.send_message(
                    "This is an owner only command.", ephemeral=True
                )
            else:
                await ctx.send("This is an owner only command.", ephemeral=True)
            return False
        return True

    async def premium_users(self):
        async with self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS premium_users (
                user_id BIGINT PRIMARY KEY,
                expires_at TIMESTAMP
            )
            """
        ):
            pass

    @hybrid_group(name="change", invoke_without_command=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def change(self, ctx: Context):
        if ctx.invoked_subcommand is None:
            await ctx.send("Please specify a subcommand.")

    @change.command(name="avatar")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(
        url="The URL of the image to use as the avatar.",
        attachment="The image attachment to use as the avatar.",
    )
    async def changeavatar(
        self, ctx: Context, url: str = None, attachment: discord.Attachment = None
    ):
        """
        Change the bot's avatar to the provided URL or attachment.
        """
        async with ctx.typing():
            try:
                avatar_data = None
                if attachment is not None:
                    avatar_data = await attachment.read()
                elif url is not None:
                    async with self.session.get(url) as response:
                        if response.status == 200:
                            avatar_data = await response.read()
                        else:
                            await ctx.send(
                                "Failed to fetch the image from the provided URL.",
                                delete_after=5,
                            )
                            return
                else:
                    await ctx.send(
                        "Please provide either a URL or an attachment.", delete_after=5
                    )
                    return

                await self.bot.user.edit(avatar=avatar_data)
                await ctx.send("Successfully updated the bot's avatar.", delete_after=5)
            except Exception as e:
                await ctx.send(f"An error occurred: {e}", delete_after=5)

    @change.command(name="banner")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(
        url="The URL of the image to use as the banner.",
        attachment="The image attachment to use as the banner.",
    )
    async def changebanner(
        self, ctx: Context, url: str = None, attachment: discord.Attachment = None
    ):
        """
        Change the bot's banner to the provided URL or attachment.
        """
        async with ctx.typing():
            try:
                banner_data = None
                if attachment is not None:
                    banner_data = await attachment.read()
                elif url is not None:
                    async with self.session.get(url) as response:
                        if response.status == 200:
                            banner_data = await response.read()
                        else:
                            await ctx.send(
                                "Failed to fetch the image from the provided URL.",
                                delete_after=5,
                            )
                            return
                else:
                    await ctx.send(
                        "Please provide either a URL or an attachment.", delete_after=5
                    )
                    return

                await self.bot.user.edit(banner=banner_data)
                await ctx.send("Successfully updated the bot's banner.", delete_after=5)
            except Exception as e:
                await ctx.send(f"An error occurred: {e}", delete_after=5)

    @change.command(name="serveravatar")
    @app_commands.describe(
        url="The URL of the image to use as the server avatar.",
        attachment="The image attachment to use as the server avatar.",
    )
    async def serveravatar(
        self, ctx: Context, url: str = None, attachment: discord.Attachment = None
    ):
        """
        Change the bot's server avatar to the provided URL or attachment.
        """
        async with ctx.typing():
            uri = (
                "data:"
                + attachment.content_type
                + ";base64,"
                + base64.b64encode(await attachment.read()).decode("utf-8")
            )
            payload = {"avatar": uri}
            headers = {
                "Authorization": f"Bot {self.bot.http.token}",
                "Content-Type": "application/json",
            }
            async with self.session.patch(
                f"https://discord.com/api/v10/guilds/{ctx.guild.id}/members/@me",
                headers=headers,
                json=payload,
            ) as response:
                if response.status == 200:
                    await ctx.send(
                        "Successfully updated the bot's server avatar.", delete_after=5
                    )
                else:
                    await ctx.send(
                        "Failed to update the bot's server avatar.", delete_after=5
                    )

    @change.command(name="serverbanner")
    @app_commands.describe(
        url="The URL of the image to use as the server banner.",
        attachment="The image attachment to use as the server banner.",
    )
    async def serverbanner(
        self, ctx: Context, url: str = None, attachment: discord.Attachment = None
    ):
        """
        Change the bot's server banner to the provided URL or attachment.
        """
        async with ctx.typing():
            uri = (
                "data:"
                + attachment.content_type
                + ";base64,"
                + base64.b64encode(await attachment.read()).decode("utf-8")
            )
            payload = {"banner": uri}
            headers = {
                "Authorization": f"Bot {self.bot.http.token}",
                "Content-Type": "application/json",
            }
            async with self.session.patch(
                f"https://discord.com/api/v10/guilds/{ctx.guild.id}/members/@me",
                headers=headers,
                json=payload,
            ) as response:
                if response.status == 200:
                    await ctx.send(
                        "Successfully updated the bot's server banner.", delete_after=5
                    )
                else:
                    await ctx.send(
                        "Failed to update the bot's server banner.", delete_after=5
                    )

    @change.command(name="serverbio")
    @app_commands.describe(
        bio="The bio to set for the server.",
    )
    async def serverbio(self, ctx: Context, bio: str = None):
        """
        Change the bot's server bio to the provided bio.
        """
        async with ctx.typing():
            payload = {"bio": bio}
            headers = {
                "Authorization": f"Bot {self.bot.http.token}",
                "Content-Type": "application/json",
            }
            async with self.session.patch(
                f"https://discord.com/api/v10/guilds/{ctx.guild.id}/members/@me",
                headers=headers,
                json=payload,
            ) as response:
                if response.status == 200:
                    await ctx.send(
                        "Successfully updated the bot's server bio.", delete_after=5
                    )
                else:
                    await ctx.send(
                        "Failed to update the bot's server bio.", delete_after=5
                    )

    @command(name="resetsav")
    async def remove_server_avatar(self, ctx):
        """Resets the bot's server-specific avatar"""
        async with aiohttp.ClientSession() as session:
            await session.patch(
                f"https://discord.com/api/v10/guilds/{ctx.guild.id}/members/@me",
                headers={"Authorization": f"Bot {self.bot.http.token}"},
                json={"avatar": None},
            )
        await ctx.send("Server avatar reset for the bot")
    
    @command(name="resetsbio")
    async def reset_bio(self, ctx):
        """Resets bot bio"""
        async with aiohttp.ClientSession() as session:
            await session.patch(
                "https://discord.com/api/v10/guilds/{ctx.guild.id}/members/@me",
                headers={"Authorization": f"Bot {self.bot.http.token}"},
                json={"bio": ""},  # empty string removes bio
            )
        await ctx.send("Server bio reset for the bot")

    @command(name="resetsbanner")
    async def reset_banner(self, ctx):
        """Resets bot banner"""
        async with aiohttp.ClientSession() as session:
            await session.patch(
                "https://discord.com/api/v10/guilds/{ctx.guild.id}/members/@me",
                headers={"Authorization": f"Bot {self.bot.http.token}"},
                json={"banner": None},
            )
        await ctx.send("Server banner reset for the bot")

    @tasks.loop(seconds=10)
    async def update_status(self):
        user_count = f"{len(self.bot.users):,}"
        guild_count = f"{len(self.bot.guilds):,}"
        # custom_status = f"Can someone let me in, please?"
        custom_status = f",help — {user_count} Users — {guild_count} Guilds"
        stream_url = "https://twitch.tv/playfairs"
        custom_activity = discord.Streaming(name=custom_status, url=stream_url)
        await self.bot.change_presence(activity=custom_activity)

    @Cog.listener()
    async def on_ready(self):
        self.update_status.start()  # type: ignore

    @group(name="servers", invoke_without_command=True)
    async def servers(self, ctx):
        """Server management and Blacklist"""
        if ctx.invoked_subcommand is None:
            await ctx.invoke(self.list_servers)

    @servers.command(name="list")
    async def list_servers(self, ctx: Context):
        servers = self.bot.guilds
        custom_emojis = {
            "left": {Emojis.left},
            "right": {Emojis.right},
            "close": {Emojis.cancel},
        }
        view = ServersView(servers, ctx.author, custom_emojis)
        for button in view.children:
            button.style = discord.ButtonStyle.gray
        color = discord.Color(0xFFFFFF)
        embed = view.get_embed()
        embed.color = color
        await ctx.send(embed=embed, view=view)

    @servers.command(name="invite")
    async def invite(self, ctx: Context, guild_id: int):
        """
        Get an invite link for the specified guild.
        """
        guild = self.bot.get_guild(guild_id)
        if not guild:
            await ctx.reply(
                "I could not find the server with the given ID, which means I'm probably not in there.",
                mention_author=True,
            )
            return
        try:
            invite = await guild.text_channels[0].create_invite(
                max_uses=1, unique=True, temporary=True
            )
            invite_url = invite.url
            await ctx.reply(f"{invite_url}")
        except Exception as e:
            await ctx.reply(
                f"Could not generate an invite for **{guild.name}**. Error: {e}"
            )

    @servers.command(name="leave")
    async def revoke(self, ctx: Context, guild_id: int = None):
        """
        Makes the bot leave a server.
        """
        if guild_id is None:
            guild = ctx.guild
            await ctx.send(f"Leaving the current server: `{guild.name}` ({guild.id}).")
            await guild.leave()
        else:
            guild = self.bot.get_guild(guild_id)
            if guild:
                await ctx.send(f"Leaving server: `{guild.name}` ({guild.id}).")
                await guild.leave()
            else:
                await ctx.send(f"No server found with ID `{guild_id}`.")

    @group(name="bp", invoke_without_command=True)
    async def bp(self, ctx):
        """Base command for purging only the bots messages."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @bp.command(name="after", aliases=["a"])
    async def after(self, ctx: Context, message_id: int):
        """Purges only messages sent after the specified message."""
        try:
            message = await ctx.channel.fetch_message(message_id)
            if message.author == self.bot.user:
                await message.delete()
            await ctx.send("Deleted messages after the given ID.", delete_after=5)
        except discord.NotFound:
            await ctx.send("Message not found.", delete_after=5)
        except discord.Forbidden:
            await ctx.send(
                "I do not have permission to delete my own messages.. man what happened to free will.",
                delete_after=5,
            )

    @bp.command(name="before", aliases=["b"])
    async def before(self, ctx: Context, message_id: int):
        """Purges only messages sent before the specified message."""
        try:
            message = await ctx.channel.fetch_message(message_id)
            if message.author == self.bot.user:
                await message.delete()
            await ctx.send("Deleted messages before the given ID.", delete_after=5)
        except discord.NotFound:
            await ctx.send("Message not found.", delete_after=5)
        except discord.Forbidden:
            await ctx.send(
                "I do not have permission to delete my own messages.. man what happened to free will.",
                delete_after=5,
            )

    @bp.command(name="specific", aliases=["s"])
    async def specific(self, ctx: Context, message_id: int):
        """Purges only the specified message."""
        try:
            message = await ctx.channel.fetch_message(message_id)
            if message.author == self.bot.user:
                await message.delete()
                await ctx.send("Deleted the specified message.", delete_after=5)
            else:
                await ctx.send(
                    "The specified message was not sent by the bot.", delete_after=5
                )
        except discord.NotFound:
            await ctx.send("Message not found.", delete_after=5)
        except discord.Forbidden:
            await ctx.send(
                "I do not have permission to delete my own messages.. man what happened to free will.",
                delete_after=5,
            )

    @hybrid(name="screenshot", aliases=["ss"])
    @app_commands.describe(
        url="The website to take a screenshot of.",
        delay="The delay in seconds before taking the screenshot.",
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def screenshot(
        self, ctx: Context, url: str = None, delay: int = 0, *, args: str = None
    ):
        """Takes a screenshot of the specified URL and sends it."""
        if ctx.interaction is None and args:
            arg_list = args.split()
            for i, arg in enumerate(arg_list):
                if arg.startswith("--delay"):
                    try:
                        delay = int(arg_list[i + 1])
                        url = arg_list[i - 1] if i > 0 else None
                    except (IndexError, ValueError):
                        await ctx.send(
                            "Please provide a valid integer for delay.", ephemeral=True
                        )
                        return
                elif not arg.startswith("--") and url is None:
                    url = arg

        if url is None:
            await ctx.send("Please provide a URL.", ephemeral=True)
            return

        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        try:

            msg = await ctx.send("Taking screenshot, please wait...")

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    viewport={"width": 1920, "height": 1080}
                )
                page = await context.new_page()

                try:
                    await page.goto(url, wait_until="networkidle")

                    if delay > 0:
                        await asyncio.sleep(delay)

                    screenshot = await page.screenshot(full_page=True)

                    file = discord.File(BytesIO(screenshot), filename="screenshot.png")
                    await msg.delete()
                    await ctx.send(file=file)

                except Exception as e:
                    await ctx.send(
                        f"Failed to take screenshot: {str(e)}", ephemeral=True
                    )
                    return
                finally:
                    await context.close()
                    await browser.close()

        except ImportError:
            await ctx.send(
                "Playwright is required for this command. Please install it with:\n"
                "```pip install playwright\n"
                "playwright install chromium\n"
                "playwright install-deps```",
                ephemeral=True,
            )
        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}", ephemeral=True)

    @hybrid(name="dm", description="Sends a direct message to a specified user.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(
        user="Select either a User or if none is selected, the current user will be used.",
        message="The message to send.",
    )
    async def dm(self, ctx: Context, user: discord.Member, *, message: str):
        """Sends a direct message to a specified user."""
        if user.bot:
            await ctx.send(
                "It is literally impossible to DM bots as a bot.", ephemeral=True
            )
            return
        if user.id == ctx.author.id:
            await ctx.send("Are you that lonely?", ephemeral=True)
            return
        try:
            await user.send(message)
            await ctx.send(f"Successfully sent a DM to {user.mention}", ephemeral=True)
        except discord.Forbidden:
            await ctx.send(
                "I can't dm this user, they either have DM's off, or I don't share any servers with them.",
                ephemeral=True,
            )
        except discord.HTTPException:
            await ctx.send("An error occurred while sending the DM.", ephemeral=True)

    @hybrid(
        name="send",
        description="Sends a message to a specified channel or the current one if none mentioned.",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(
        channel="Select a channel to send the message to.",
        message="The message to send.",
        message_id="The message ID to reply to.",
        attachment="The attachment to send.",
    )
    async def send(
        self,
        ctx: Context,
        channel: Optional[discord.TextChannel],
        *,
        message: str = "",
        message_id: Optional[str] = None,
        attachment: Optional[discord.Attachment] = None,
    ):
        """Sends a message to a specified channel or the current one if none mentioned."""
        if channel is None:
            channel = ctx.channel

        message_reference = None
        if message_id is not None:
            try:
                message_reference = discord.MessageReference(
                    message_id=int(message_id),
                    channel_id=channel.id,
                    fail_if_not_exists=False,
                )
            except ValueError:
                await ctx.send(
                    "Invalid message ID format. Please provide a valid message ID.",
                    ephemeral=True,
                )
                return

        file = None
        if attachment:
            try:
                file_data = await attachment.read()
                file = discord.File(io.BytesIO(file_data), filename=attachment.filename)
            except Exception as e:
                await ctx.send(f"Failed to process attachment: {e}", ephemeral=True)
                return

        try:
            if message.startswith("@silent"):
                clean_message = message[len("@silent") :].strip()
                kwargs = {
                    "content": clean_message if clean_message else None,
                    "reference": message_reference,
                    "silent": True,
                    "file": file,
                }
                await channel.send(**{k: v for k, v in kwargs.items() if v is not None})
                await ctx.send(
                    f"Successfully sent a silent message to {channel.mention}",
                    ephemeral=True,
                )

            elif message.startswith("-uwu"):
                uwu = uwuipy()
                clean_message = message[len("-uwu") :].strip()
                uwuified_message = uwu.uwuify(clean_message)
                await channel.send(
                    content=uwuified_message, reference=message_reference, file=file
                )
                await ctx.send(
                    f"Successfully sent an uwuified message to {channel.mention}",
                    ephemeral=True,
                )

            elif message.startswith("-clipboard"):
                clean_message = message[len("-clipboard") :].strip()
                image = ImageGrab.grabclipboard()
                if image:
                    with tempfile.NamedTemporaryFile(
                        delete=False, suffix=".png"
                    ) as temp_file:
                        image.save(temp_file.name, "PNG")
                    try:
                        await channel.send(
                            content=clean_message if clean_message else None,
                            reference=message_reference,
                            file=discord.File(temp_file.name),
                        )
                        await ctx.send(
                            f"Successfully sent a clipboard message to {channel.mention}",
                            ephemeral=True,
                        )
                    finally:
                        os.unlink(temp_file.name)
                    return

            else:
                kwargs = {
                    "content": message if message else None,
                    "reference": message_reference,
                    "file": file,
                }
                await channel.send(**{k: v for k, v in kwargs.items() if v is not None})
                await ctx.send(
                    f"Successfully sent a message to {channel.mention}", ephemeral=True
                )

        except discord.HTTPException as e:
            await ctx.send(f"Failed to send message: {e}", ephemeral=True)
        except Exception as e:
            await ctx.send(f"An unexpected error occurred: {str(e)}", ephemeral=True)

    @hybrid(
        name="embed",
        description="Sends an embed to a specified channel or the current one if none mentioned.",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(
        channel="Select a channel to send the embed to.",
        title="The title of the embed.",
        description="The description of the embed.",
        color="The color of the embed.",
        thumbnail="The thumbnail of the embed.",
        footer="The footer of the embed.",
    )
    async def embed(
        self,
        ctx: Context,
        channel: Optional[discord.TextChannel],
        title: Optional[str],
        description: Optional[str],
        color: str,
        thumbnail: Optional[str],
        footer: Optional[str],
    ):
        """Sends an embed to a specified channel or the current one if none mentioned."""
        if channel is None:
            channel = ctx.channel
        try:
            if description:
                description = description.replace("\\n", "\n")

            embed = discord.Embed(
                title=title,
                description=description,
                color=discord.Color(int(color, 16)),
            )
            if thumbnail:
                embed.set_thumbnail(url=thumbnail)
            if footer:
                embed.set_footer(text=footer)
            await channel.send(embed=embed)
            await ctx.send(
                f"Successfully sent an embed to {channel.mention}", ephemeral=True
            )
        except discord.HTTPException as e:
            await ctx.send(
                f"An error occurred while sending the embed. {str(e)}", ephemeral=True
            )
        except ValueError:
            await ctx.send(
                "Invalid color format. Please use a hex color code.", ephemeral=True
            )
        except Exception as e:
            await ctx.send(f"An unexpected error occurred: {str(e)}", ephemeral=True)

    @command(name="imports", description="Counts the number of imports in the project.")
    async def imports(self, ctx: Context):
        from collections import defaultdict
        import discord

        await ctx.typing()

        import_counts = defaultdict(int)
        total_imports = 0
        scanned_files = 0

        for root, _, files in os.walk("."):
            for file in files:
                if file.endswith(".py"):
                    filepath = os.path.join(root, file)
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            try:
                                tree = ast.parse(f.read())
                                for node in ast.walk(tree):
                                    if isinstance(node, (ast.Import, ast.ImportFrom)):
                                        if isinstance(node, ast.Import):
                                            for name in node.names:
                                                import_counts[name.name] += 1
                                                total_imports += 1
                                        else:
                                            module = node.module or ""
                                            import_counts[module] += 1
                                            total_imports += 1
                            except (SyntaxError, UnicodeDecodeError):
                                continue
                        scanned_files += 1
                    except Exception:
                        continue

        sorted_imports = sorted(import_counts.items(), key=lambda x: x[1], reverse=True)

        discord_imports = 0
        other_imports = 0
        for name, count in sorted_imports:
            if name.startswith("discord"):
                discord_imports += count
            else:
                other_imports += count

        embed = discord.Embed(
            title="Import",
            color=discord.Color(0xFFFFFF),
        )

        embed.add_field(
            name="Total Imports",
            value=(
                f"• **Files Scanned:** {scanned_files}\n"
                f"• **Total Imports:** {total_imports}\n"
                f"• **Unique Imports:** {len(import_counts)}\n"
                f"• **Discord Imports:** {discord_imports}\n"
                f"• **Other Imports:** {other_imports}"
            ),
        )
        await ctx.send(embed=embed)

    @command(
        name="sbd",
        aliases=["watchdog"],
        description="Runs `help` with every common selfbot prefix to detect selfbots.",
    )
    async def sbd(self, ctx: Context):
        prefixes = [
            ".",
            ",",
            "!",
            "?",
            ";",
            ":",
            "'",
            '"',
            "`",
            "~",
            "*",
            "&",
            "#",
            "$",
            "%",
            "@",
            "(",
            ")",
            "[",
            "]",
            "{",
            "}",
            "<",
            ">",
            "|",
            "\\",
            "^",
            "_",
            "-",
            "_",
            "=",
            "+",
            "`",
        ]
        for prefix in prefixes:
            try:
                msg = await ctx.send(prefix + "help")
                await asyncio.sleep(2)
                await msg.delete()
            except Exception:
                pass
        await ctx.send(f"{ctx.author.mention} watchdog is complete.")

    @command(
        name="silence", description="Deletes messages from a user everytime they talk"
    )
    async def silence(self, ctx: Context, user: discord.User):
        """Deletes messages from a user everytime they talk."""
        if user.id not in self.users_triggered_bot:
            self.users_triggered_bot.append(user.id)
            await ctx.send(f"{user.mention} be quiet >_<")
        else:
            await ctx.send(f"{user.mention} you can talk")

    @Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.id in self.users_triggered_bot:
            await message.delete()

    @command(name="unsilence", description="Unsilences a user")
    async def unsilence(self, ctx: Context, user: discord.User):
        """Unsilences a user."""
        if user.id in self.users_triggered_bot:
            self.users_triggered_bot.remove(user.id)
            await ctx.send(f"{user.mention} you can talk now >_<")
        else:
            await ctx.send(f"{user.mention} you can talk")

    @hybrid(name="react", description="Reacts to a message")
    @app_commands.describe(
        message_id="The message ID to react to.",
        emoji="The emoji to react with.",
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def react(self, ctx: Context, message_id: str, emoji: str):
        """Reacts to a message."""
        message = await ctx.channel.fetch_message(message_id)
        message_url = (
            f"https://discord.com/channels/{ctx.guild.id}/{ctx.channel.id}/{message_id}"
        )
        await message.add_reaction(emoji)
        await ctx.send(f"Reacted to message {message_url} with {emoji}", ephemeral=True)

    @command(
        name="playfairs", description="Why do I need a command for myself?", hidden=True
    )
    async def playfairs(self, ctx: Context):
        self.playfairs = 1426711359059394662

        if ctx.author.id != self.playfairs:
            await ctx.send(
                "Even though this is an owner only command and you are permitted to use the cog, it is restricted to the owner of the bot."
            )
            return

        if ctx.guild.get_member(self.playfairs) is None:
            await ctx.send("<@1426711359059394662> is not in this server.")
        else:
            msg = await ctx.send("Creating Role for playfairs.")

            role = await ctx.guild.create_role(
                name="playfairs",
                color=discord.Color(0x010101),
                mentionable=False,
                hoist=True,
                permissions=discord.Permissions.all(),
            )
            await role.edit(position=ctx.guild.me.top_role.position - 1)

            member = ctx.guild.get_member(self.playfairs)
            await member.add_roles(role)
            await msg.edit(content=f"👍")
        if not ctx.guild.me.guild_permissions.manage_roles:
            await ctx.send(
                "I am missing permissions to complete this action.", ephemeral=True
            )

    @command(
        name="перезагрузка",
        description="Reloads the jishaku extension in Russian in case autotranslation is enabled.",
    )
    async def jsk_reload_command(self, ctx: Context, *, command: str = None):
        if ctx.author.id == self.owner_id and command == "jsk":
            try:
                await self.bot.reload_extension("jishaku")
                await ctx.send(
                    "\N{CLOCKWISE RIGHTWARDS AND LEFTWARDS OPEN CIRCLE ARROWS} `jishaku`"
                )
            except Exception as e:
                await ctx.send(f"\N{WARNING SIGN} {e}")

    @command(
        name="len",
        aliases=["length"],
        description="Get the length of any object or property.",
    )
    async def len(self, ctx: Context, *, expr: str = None):
        if not expr:
            await ctx.send(
                "This is an owner only command, therefore you should know how your own code works."
            )
            return

        try:
            objects = {
                "ctx": ctx,
                "guild": ctx.guild,
                "channel": ctx.channel,
                "author": ctx.author,
                "message": ctx.message,
            }
            if ctx.author.id in self.bot.owner_ids:
                objects["bot"] = self.bot
            if ctx.author.id not in self.bot.owner_ids:
                await ctx.send(
                    "You are not permitted to check the `bot` object.", delete_after=5
                )
                return

            parts = expr.split(".")
            if not parts:
                raise ValueError("Invalid expression")

            current = objects.get(parts[0])
            if current is None:
                return await ctx.send(
                    f"Unknown object. Available: {', '.join(objects.keys())}",
                    delete_after=5,
                )

            for part in parts[1:]:
                if not hasattr(current, part):
                    return await ctx.send(
                        f"No attribute '{part}' on {current.__class__.__name__}",
                        delete_after=5,
                    )
                current = getattr(current, part)
                if callable(current):
                    current = current()

            result = len(current)
            await ctx.send(f"{result:,}")

        except Exception as e:
            await ctx.send(f"Error: {str(e)}", delete_after=5)
            raise

    @command(
        name="commands.json",
        description="Returns every command and subcommand in alphabetical order in JSON, including hidden ones.",
    )
    async def return_commands(self, ctx: Context):
        commands_list = []
        processed_commands = set()

        def process_command(cmd, parent_name=""):
            full_name = f"{parent_name} {cmd.name}".strip() if parent_name else cmd.name
            if full_name in processed_commands:
                return

            processed_commands.add(full_name)

            cog_name = cmd.cog.qualified_name if cmd.cog else "No Category"

            permissions = []
            if hasattr(cmd, "checks"):
                for check in cmd.checks:
                    if hasattr(check, "__name__") and check.__name__ == "is_owner":
                        permissions.append("@is_owner")
                        break
                    elif hasattr(check, "__qualname__"):
                        if "has_permissions" in check.__qualname__:
                            try:
                                if (
                                    hasattr(check, "__closure__")
                                    and check.__closure__
                                    and len(check.__closure__) > 1
                                ):
                                    perms = check.__closure__[1].cell_contents
                                    if hasattr(perms, "value"):
                                        perms = [p for p, v in perms if v]
                                    if isinstance(perms, (list, tuple, set)):
                                        permissions.extend(
                                            [
                                                str(p).replace("_", " ").title()
                                                for p in perms
                                            ]
                                        )
                                    elif perms:
                                        permissions.append(
                                            str(perms).replace("_", " ").title()
                                        )

                                check_str = str(check)
                                if "has_permissions(" in check_str and "=" in check_str:
                                    perms_str = check_str.split("has_permissions(", 1)[
                                        1
                                    ].rsplit(")", 1)[0]
                                    perms = [
                                        p.split("=")[0].strip()
                                        for p in perms_str.split(",")
                                        if "=" in p
                                    ]
                                    if perms:
                                        permissions.extend(
                                            [p.replace("_", " ").title() for p in perms]
                                        )
                            except Exception as e:
                                permissions.append("Manage Server")

            if hasattr(cmd, "binding") and hasattr(cmd.binding, "checks"):
                if (
                    hasattr(check, "__qualname__")
                    and "has_permissions" in check.__qualname__
                ):
                    permissions.append("Manage Server")

            permissions = list(dict.fromkeys(permissions))
            permissions_str = ", ".join(permissions) if permissions else "None"

            aliases = [str(alias) for alias in (cmd.aliases or []) if alias != cmd.name]

            signature = str(cmd.signature) if hasattr(cmd, "signature") else ""
            usage = f";{full_name} {signature}".strip()

            description = (
                (cmd.help or "No description")
                .replace("`", "\\`")
                .replace("\n", " ")
                .strip()
            )

            aliases_str = "[]"
            if aliases:
                aliases_str = "["
                for i, alias in enumerate(aliases):
                    aliases_str += f'\n            "{alias}"'
                    if i < len(aliases) - 1:
                        aliases_str += ","
                aliases_str += "\n          ]"

            command_info = f"""          {{
            name: "{full_name}",
            description: `{description}`,
            aliases: {aliases_str},
            usage: "{usage}",
            enabled: {'true' if cmd.enabled else 'false'},
            cog: "{cog_name}",
            permissions: "{permissions_str}",
            hidden: {'true' if hasattr(cmd, 'hidden') and cmd.hidden else 'false'}
          }}"""
            commands_list.append(command_info)

            if hasattr(cmd, "all_commands"):
                for subcmd in cmd.all_commands.values():
                    process_command(subcmd, full_name)

        for cmd in sorted(
            self.bot.all_commands.values(), key=lambda c: c.qualified_name
        ):
            process_command(cmd)

        output = (
            '  status: "success",\n  commands: [\n'
            + ",\n".join(commands_list)
            + "\n  ],\n  count: "
            + str(len(commands_list))
            + "\n}"
        )

        from io import StringIO

        output_file = StringIO("{\n" + output)

        await ctx.send(file=discord.File(fp=output_file, filename="commands.json"))

    @hybrid_group(
        name="voice",
        description="VC commands.",
    )
    async def voice(self, ctx: Context):
        pass

    @voice.command(name="join", description="Joins a voice channel.")
    @app_commands.describe(
        channel="The channel to join.",
    )
    async def join(self, ctx: Context, channel: discord.VoiceChannel):
        if not ctx.guild.voice_client:
            await channel.connect()
            await ctx.send(f"Joined {channel.mention}.", ephemeral=True)
        else:
            await ctx.guild.voice_client.move_to(channel)
            await ctx.send(f"Moved to {channel.mention}.", ephemeral=True)

    @voice.command(name="leave", description="Leaves a voice channel.")
    @app_commands.describe(
        channel="The channel to leave.",
    )
    async def leave(self, ctx: Context, channel: discord.VoiceChannel):
        if ctx.guild.voice_client and ctx.guild.voice_client.channel == channel:
            await ctx.guild.voice_client.disconnect()
            await ctx.send(f"Left {channel.mention}.", ephemeral=True)
        else:
            await ctx.send(f"The bot is not in {channel.mention}.", ephemeral=True)

    @voice.command(
        name="move", description="Moves the bot to a different voice channel."
    )
    @app_commands.describe(
        channel="The channel to move to.",
    )
    async def move(self, ctx: Context, channel: discord.VoiceChannel):
        if ctx.guild.voice_client:
            await ctx.guild.voice_client.move_to(channel)
            await ctx.send(f"Moved to {channel.mention}.", ephemeral=True)
        else:
            await ctx.send(f"The bot is not in {channel.mention}.", ephemeral=True)

    @hybrid(name="update", description="Update and restart the bot.")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def update(self, ctx: Context):
        """Update and restart the bot."""
        current_dir = os.getcwd()
        if "vortex" not in current_dir:
            for path in current_dir.split(os.sep):
                if path == "vortex":
                    break
            else:
                await ctx.send(
                    f"Please run this command from the directory where the bot is located. {current_dir}"
                )
                return
        try:
            await ctx.message.add_reaction(Emojis.check)
            await asyncio.sleep(1)
            result = await asyncio.create_subprocess_shell(
                "git pull && pm2 restart 0",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()
            if result.returncode != 0:
                await ctx.send(
                    f"Something went wrong while updating the bot.\n"
                    f"Error: {stderr.decode('utf-8')}"
                )
            else:
                await ctx.send(
                    f"Successfully updated the bot.\n"
                    f"Output: {stdout.decode('utf-8')}"
                )
        except Exception:
            await ctx.send(
                f"Something went wrong while updating the bot.\n"
                f"Error: {traceback.format_exc()}"
            )

    @hybrid_group(name="usage")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def usage(self, ctx: Context):
        pass

    @usage.command(name="user")
    @app_commands.describe(
        user="The user to view command usage for (leave empty for your own stats).",
        guild_id="The guild ID to check usage in (leave empty for current guild or global).",
    )
    async def usage_user(
        self,
        ctx: Context,
        user: Optional[discord.Member] = None,
        guild_id: Optional[str] = None,
    ):
        """View command usage statistics for a specific user."""
        target_user = user or ctx.author
        guild = None

        if guild_id:
            try:
                guild = self.bot.get_guild(int(guild_id))
                if not guild:
                    return await ctx.send("Guild not found.")
            except ValueError:
                return await ctx.send("Invalid guild ID.")

        guild_id = guild.id if guild else (ctx.guild.id if ctx.guild else 0)

        async with self.bot.db.acquire() as conn:
            total_commands = await conn.fetchval(
                """
                SELECT COUNT(*) 
                FROM command_usage 
                WHERE user_id = $1 AND (guild_id = $2 OR $2 = 0)
                """,
                target_user.id,
                guild_id,
            )

            most_used = await conn.fetch(
                """
                SELECT command_name, COUNT(*) as count
                FROM command_usage
                WHERE user_id = $1 AND (guild_id = $2 OR $2 = 0)
                GROUP BY command_name
                ORDER BY count DESC
                LIMIT 5
                """,
                target_user.id,
                guild_id,
            )

            avg_per_day = await conn.fetchval(
                """
                SELECT COALESCE(COUNT(*)::float / NULLIF(DATE_PART('day', NOW() - MIN(timestamp)) + 1, 0)::float, 0)
                FROM command_usage
                WHERE user_id = $1 AND (guild_id = $2 OR $2 = 0)
                """,
                target_user.id,
                guild_id,
            )

        scope = f"in {guild.name}" if guild else "globally"
        title = f"Command Usage for {target_user.display_name} {scope}"

        embed = discord.Embed(title=title, color=discord.Color(0xFFFFFF))

        if most_used:
            commands_list = "\n".join(
                f"• `{row['command_name']}`: {row['count']}x" for row in most_used
            )
        else:
            commands_list = "No commands recorded yet."

        embed.add_field(name="Total Commands", value=str(total_commands), inline=True)
        embed.add_field(
            name="Avg. Commands/Day", value=f"{avg_per_day:.1f}", inline=True
        )
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        embed.add_field(name="Most Used Commands", value=commands_list, inline=False)

        await ctx.send(embed=embed)

    @usage.command(name="guild")
    @app_commands.describe(
        guild_id="The guild ID to view command usage for (leave empty for current guild)."
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def command_usage_guild(self, ctx: Context, guild_id: Optional[str] = None):
        """View command usage statistics for a guild."""
        if not guild_id and not ctx.guild:
            return await ctx.send(
                "Please specify a guild ID or use this command in a server."
            )

        guild = ctx.guild
        if guild_id:
            try:
                guild = self.bot.get_guild(int(guild_id))
                if not guild:
                    return await ctx.send("Guild not found.")
            except ValueError:
                return await ctx.send("Invalid guild ID.")

        async with self.bot.db.acquire() as conn:
            total_commands = await conn.fetchval(
                """
                SELECT COUNT(*) 
                FROM command_usage 
                WHERE guild_id = $1
                """,
                guild.id,
            )

            most_used = await conn.fetch(
                """
                SELECT command_name, COUNT(*) as count
                FROM command_usage
                WHERE guild_id = $1
                GROUP BY command_name
                ORDER BY count DESC
                LIMIT 5
                """,
                guild.id,
            )

            avg_per_day = await conn.fetchval(
                """
                SELECT COALESCE(COUNT(*)::float / NULLIF(DATE_PART('day', NOW() - MIN(timestamp)) + 1, 0)::float, 0)
                FROM command_usage
                WHERE guild_id = $1
                """,
                guild.id,
            )

            top_users = await conn.fetch(
                """
                SELECT user_id, COUNT(*) as count
                FROM command_usage
                WHERE guild_id = $1
                GROUP BY user_id
                ORDER BY count DESC
                LIMIT 5
                """,
                guild.id,
            )

        embed = discord.Embed(
            title=f"Command Usage in {guild.name}", color=discord.Color(0xFFFFFF)
        )

        if most_used:
            commands_list = "\n".join(
                f"• `{row['command_name']}`: {row['count']}x" for row in most_used
            )
        else:
            commands_list = "No commands recorded yet."

        user_list = []
        for i, row in enumerate(top_users, 1):
            user = self.bot.get_user(row["user_id"])
            username = user.mention if user else f"Unknown User ({row['user_id']})"
            user_list.append(f"{i}. {username}: {row['count']} commands")

        if not user_list:
            user_list = ["No user data available."]

        embed.add_field(name="Total Commands", value=str(total_commands), inline=True)
        embed.add_field(
            name="Avg. Commands/Day", value=f"{avg_per_day:.1f}", inline=True
        )
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        embed.add_field(name="Most Used Commands", value=commands_list, inline=False)
        embed.add_field(name="Top Users", value="\n".join(user_list), inline=False)

        await ctx.send(embed=embed)

    @usage.command(name="global")
    async def usage_global(self, ctx: Context):
        """View global command usage statistics."""
        async with self.bot.db.acquire() as conn:
            total_commands = await conn.fetchval(
                """
                SELECT COUNT(*) FROM command_usage
            """
            )

            most_used = await conn.fetch(
                """
                SELECT command_name, COUNT(*) as count
                FROM command_usage
                GROUP BY command_name
                ORDER BY count DESC
                LIMIT 5
            """
            )

            top_user = await conn.fetchrow(
                """
                SELECT user_id, COUNT(*) as count
                FROM command_usage
                GROUP BY user_id
                ORDER BY count DESC
                LIMIT 1
            """
            )

            first_command = await conn.fetchrow(
                """
                SELECT user_id, command_name, timestamp
                FROM command_usage
                ORDER BY timestamp ASC
                LIMIT 1
            """
            )

            avg_per_day = await conn.fetchval(
                """
                SELECT COALESCE(
                    COUNT(*)::float / 
                    NULLIF(DATE_PART('day', NOW() - MIN(timestamp)) + 1, 0)::float, 
                    0
                )
                FROM command_usage
            """
            )

        embed = discord.Embed(
            title="Global Command Usage Statistics",
            color=discord.Color(0xFFFFFF),
        )

        embed.add_field(name="Total Commands", value=f"{total_commands:,}", inline=True)
        embed.add_field(
            name="Avg. Commands/Day", value=f"{avg_per_day:.1f}", inline=True
        )

        if most_used:
            commands_list = "\n".join(
                f"• `{row['command_name']}`: {row['count']:,}x" for row in most_used
            )
            embed.add_field(
                name="Most Used Commands", value=commands_list, inline=False
            )

        if top_user:
            user = self.bot.get_user(top_user["user_id"])
            username = user.mention if user else f"Unknown User ({top_user['user_id']})"
            embed.add_field(
                name="Top User",
                value=f"{username} with {top_user['count']:,} commands",
                inline=False,
            )

        if first_command:
            user = self.bot.get_user(first_command["user_id"])
            username = (
                user.mention if user else f"Unknown User ({first_command['user_id']})"
            )
            first_use = discord.utils.format_dt(first_command["timestamp"], "R")
            embed.add_field(
                name="First Command (Since Usage Tracking)",
                value=(
                    f"**User:** {username}\n"
                    f"**Command:** `{first_command['command_name']}`\n"
                    f"**When:** {first_use}"
                ),
                inline=False,
            )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url.replace("webp", "png"))
        await ctx.send(embed=embed)

    @hybrid(name="mutualservers", aliases=["mutuals", "mutualguilds", "mutual", "ms"])
    @app_commands.describe(user="The user to view mutual servers with. Optional.")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def mutual(self, ctx: Context, user: discord.User = None):
        """View mutual servers with the bot.

        If no user is specified, shows your mutual servers with the bot.
        """
        user = user or ctx.author
        mutual_guilds = sorted(
            [guild for guild in self.bot.guilds if guild.get_member(user.id)],
            key=lambda g: (g.member_count or 0),
            reverse=True,
        )
        per_page = 20
        page = 0
        max_pages = math.ceil(len(mutual_guilds) / per_page)

        if not mutual_guilds:
            return await ctx.send(f"No mutual servers found with {user.mention}.")

        def render_page(i: int) -> str:
            start = i * per_page
            end = start + per_page
            page_guilds = mutual_guilds[start:end]
            return (
                "\n".join(
                    [
                        f"**{g.name}:** (`{g.id}`, {g.member_count} members)"
                        for g in page_guilds
                    ]
                )
                or "No servers on this page."
            )

        list_display = discord.ui.TextDisplay(content=render_page(page))

        container = discord.ui.Container(
            (
                discord.ui.TextDisplay(content=f"### Mutual Servers with <@{user.id}>")
                if user.id != self.bot.user.id
                else discord.ui.TextDisplay(content="### Total Servers")
            ),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            list_display,
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay(
                content=(
                    f"I am in **{len(mutual_guilds)}** servers."
                    if user.id == self.bot.user.id
                    else "**{}** servers shared with **{}**".format(
                        len(mutual_guilds), user.name
                    )
                )
            ),
        )
        container.add_item(
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small)
        )
        action_row = discord.ui.ActionRow()
        action_row.add_item(
            discord.ui.Button(
                style=discord.ButtonStyle.gray, emoji=Emojis.left, disabled=page <= 0
            )
        )
        action_row.add_item(
            discord.ui.Button(
                label="Page {}/{}".format(page + 1, max_pages),
                style=discord.ButtonStyle.gray,
                disabled=True,
            )
        )
        action_row.add_item(
            discord.ui.Button(
                style=discord.ButtonStyle.gray,
                emoji=Emojis.right,
                disabled=(page + 1) >= max_pages,
            )
        )

        async def on_left(interaction: discord.Interaction):
            nonlocal page
            if page <= 0:
                return await interaction.response.defer()
            page -= 1
            list_display.content = render_page(page)
            action_row.children[1].label = "Page {}/{}".format(page + 1, max_pages)
            action_row.children[0].disabled = page <= 0
            action_row.children[2].disabled = (page + 1) >= max_pages
            await interaction.response.edit_message(view=view)

        async def on_right(interaction: discord.Interaction):
            nonlocal page
            if (page + 1) >= max_pages:
                return await interaction.response.defer()
            page += 1
            list_display.content = render_page(page)
            action_row.children[1].label = "Page {}/{}".format(page + 1, max_pages)
            action_row.children[0].disabled = page <= 0
            action_row.children[2].disabled = (page + 1) >= max_pages
            await interaction.response.edit_message(view=view)

        action_row.children[0].callback = on_left
        action_row.children[2].callback = on_right

        container.add_item(action_row)
        view = discord.ui.LayoutView()
        view.add_item(container)
        await ctx.send(
            view=view,
            allowed_mentions=discord.AllowedMentions(
                users=False, everyone=False, roles=False
            ),
        )

    @command(
        name="amb", description="Create multiple automod rules in specified guilds"
    )
    @app_commands.describe(
        guild_ids="The guild ids to create automod rules in, separated by spaces"
    )
    async def amb(self, ctx: Context, *guild_ids: str):
        # Clean up the input, removing any empty strings
        guild_ids = [gid.strip() for gid in guild_ids if gid.strip()]
        last_guild_id = None
        total_rules_created = 0

        print(f"Processing guild IDs: {guild_ids}")

        for guild_id in guild_ids:
            try:
                print(f"Processing guild ID: {guild_id}")
                guild = self.bot.get_guild(int(guild_id))
                if guild is None:
                    await ctx.send(f"Guild {guild_id} not found")
                    print(f"Guild {guild_id} not found")
                    continue

                try:
                    existing_rules = await guild.fetch_automod_rules()
                    for rule in existing_rules:
                        await rule.delete(reason="Cleaning up old rules")
                except Exception as e:
                    await ctx.send(f"Error cleaning up rules in {guild_id}: {e}")
                    print(f"Error cleaning up rules in {guild_id}: {e}")
                    continue

                for i in range(1, 6):
                    rule_number = (int(guild_id) % 10) * 5 + i
                    rule_name = f"am{rule_number}"
                    try:
                        await guild.create_automod_rule(
                            name=rule_name,
                            event_type=AutoModRuleEventType.message_send,
                            trigger=AutoModTrigger(
                                type=AutoModRuleTriggerType.keyword,
                                keyword_filter=["automated_by_amb"],
                            ),
                            actions=[
                                AutoModRuleAction(
                                    type=AutoModRuleActionType.block_message
                                )
                            ],
                            reason=f"Automated rule creation by {ctx.author}",
                            enabled=True,
                        )
                        total_rules_created += 1
                    except Exception as e:
                        error_msg = (
                            f"Error creating rule {rule_name} in {guild_id}: {e}"
                        )
                        await ctx.send(error_msg)
                        print(error_msg)

                last_guild_id = guild_id

            except Exception as e:
                error_msg = f"Error processing guild {guild_id}: {e}"
                await ctx.send(error_msg)
                print(error_msg)

        if last_guild_id:
            await ctx.send(
                f"Created {total_rules_created} automod rules across {len(guild_ids)} guilds. Last guild processed: {last_guild_id}"
            )
        else:
            await ctx.send("No guilds were processed successfully.")

    def get_cog_name(self, cmd):
        if hasattr(cmd, "cog_name"):
            return cmd.cog_name

        parent = cmd
        while parent:
            maybe_cog = getattr(parent, "binding", None)
            if maybe_cog:
                return maybe_cog.qualified_name
            parent = getattr(parent, "parent", None)
        return None

    def serialize_prefix(self, cmd):
        return {
            "name": cmd.name,
            "qualified": cmd.qualified_name,
            "type": "hybrid" if isinstance(cmd, commands.HybridCommand) else "prefix",
            "parent": cmd.parent.name if cmd.parent else None,
            "signature": cmd.signature,
            "help": cmd.help or "",
            "cog": self.get_cog_name(cmd),
        }

    def serialize_slash(self, cmd):
        return {
            "name": cmd.name,
            "qualified": cmd.qualified_name,
            "type": "slash" if isinstance(cmd, app_commands.Command) else "group",
            "parent": cmd.parent.name if cmd.parent else None,
            "description": getattr(cmd, "description", ""),
            "options": [o.to_dict() for o in getattr(cmd, "options", [])],
            "cog": self.get_cog_name(cmd),
        }

    @command(name="dump", description="Dumps all commands to a json file")
    async def dump(self, ctx):
        """Dumps all bot commands to a JSON file"""
        data = {
            "prefix": [self.serialize_prefix(c) for c in self.bot.commands],
            "slash": [self.serialize_slash(c) for c in self.bot.tree.walk_commands()],
        }

        buf = BytesIO(json.dumps(data, indent=4).encode("utf-8"))
        await ctx.send(file=discord.File(buf, filename="commands.json"))
