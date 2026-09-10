import discord
import time
import random
import psutil
import platform
import os
import asyncio
import io

from discord import ButtonStyle
from discord.ui import Button, View
from discord.ext import commands
from discord.ext.commands import (
    Cog,
    Context,
    hybrid_command as hybrid,
    command,
    BucketType,
    cooldown,
    has_permissions,
    is_owner,
)
from discord import app_commands, Color
from cogs.information.permissions import Permissions
from typing import Union, Optional
from datetime import datetime, timezone
from cogs.moderation.classes import RolesView

from .classes import MemberPages, PermissionPages
from vortex import vortex
from config import DISCORD, WHOAMI, BLACKLIST
from managers.classes import Emojis, Colors, Media, Servers, FallBackURLs
from managers.default_avatar import DefaultAvatarManager
from .views import (
    AvContainer,
    ServerAvatarView,
    BannerView,
    ServerBannerView,
    WhoisView,
    UserInfoView,
    NicknameHistoryView,
)


class Information(Cog, description="View commands in Information."):
    def __init__(self, bot: vortex):
        self.bot = bot
        self.db = bot.db
        self.developer_id = WHOAMI.OWNER_IDS
        self.heresy_id = DISCORD.HERESY_ID
        self.owners = WHOAMI.OWNER_IDS
        self.bot_id = DISCORD.BOT_ID
        self.jishaku_access = WHOAMI.JISHAKU_ACCESS
        self.start_time = datetime.now(timezone.utc)
        self.mutual_servers = 0
        self.default_avatar_manager = DefaultAvatarManager(self.bot)
        # Load offensive/banned display-name substrings from file
        self.filter_terms = self._load_name_filter_terms()

    async def create_nickname_history_table(self):
        """Create the nickname_history table if it doesn't exist."""
        await self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS nickname_history (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                nickname TEXT NOT NULL,
                changed_at TIMESTAMP DEFAULT (NOW() AT TIME ZONE 'utc')
            )
        """
        )

    @app_commands.command(name="about", description="About the bot or Developer.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(option="Select either Playfair, Heresy, or Vortex")
    @app_commands.choices(
        option=[
            app_commands.Choice(name="Playfair", value="playfair"),
            app_commands.Choice(name="Vortex", value="vortex"),
        ]
    )
    async def about(
        self, interaction: discord.Interaction, option: app_commands.Choice[str]
    ):
        """About the bot or Developer."""
        option_value = option.value.lower()
        if option_value == "playfair":
            owner = await self.bot.fetch_user(1426711359059394662)
            embed = discord.Embed(
                description=f"{owner.name} - Developer",
                color=discord.Color(0xFFFFFF),
            )
            embed.add_field(
                name="Description", value=f"{WHOAMI.BIOGRAPHY}", inline=False
            )
            owner = await self.bot.fetch_user(1426711359059394662)
            avatar = await self.default_avatar_manager.get_user_avatar_or_default(owner)
            embed.set_thumbnail(url=avatar)
            current_time = datetime.now().strftime("%I:%M %p")
            user_avatar = await self.default_avatar_manager.get_user_avatar_or_default(
                interaction.user
            )
            embed.set_footer(
                text=f"Requested by {interaction.user} • Today at {current_time}",
                icon_url=user_avatar,
            )

            view = View(timeout=180)

            async def on_timeout():
                for item in view.children:
                    item.disabled = True
                try:
                    await view.message.edit(view=view)
                except:
                    pass

            view.on_timeout = on_timeout

            github = Button(
                label="GitHub",
                url=WHOAMI.PERSONAL_LINKS["GitHub"],
                style=ButtonStyle.link,
            )
            view.add_item(github)

            biolink = Button(
                label="Biolink",
                url=WHOAMI.PERSONAL_LINKS["Biolink"],
                style=ButtonStyle.link,
            )
            view.add_item(biolink)

            await interaction.response.send_message(embed=embed, view=view)

        elif option_value == "vortex":
            bot = self.bot

            commands_list = []
            for cmd in sorted(bot.walk_commands(), key=lambda c: c.qualified_name):
                if isinstance(cmd, commands.Group):
                    commands_list.append(cmd.qualified_name)
                    for subcmd in cmd.walk_commands():
                        commands_list.append(subcmd.qualified_name)
                else:
                    commands_list.append(cmd.qualified_name)

            total_commands = len(commands_list)
            total_modules = len(list(bot.extensions.keys()))

            if platform.system() == "Darwin":
                host = "MacOS " + platform.mac_ver()[0]
            else:
                host = platform.system() + " " + platform.release()

            jishaku = self.bot.get_cog("Jishaku")
            if jishaku:
                uptime = datetime.now(timezone.utc) - jishaku.load_time
                days = uptime.days
                hours, remainder = divmod(uptime.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"
            else:
                uptime_str = "Unable to calculate"

            total_lines = 0
            total_files = 0
            total_imports = 0
            total_functions = 0

            project_root = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "../..")
            )
            search_dirs = [project_root]
            venv_path = os.path.join(project_root, "venv")
            if os.path.exists(venv_path):
                search_dirs.append(venv_path)

            for directory in search_dirs:
                for root, _, files in os.walk(directory):
                    for file in files:
                        if file.startswith("."):
                            continue

                        try:
                            file_path = os.path.join(root, file)
                            with open(
                                file_path, "r", encoding="utf-8", errors="ignore"
                            ) as f:
                                content = f.read()
                                total_files += 1
                                total_lines += len(content.splitlines())

                                if file.endswith(".py"):
                                    total_imports += len(
                                        [
                                            line
                                            for line in content.splitlines()
                                            if line.strip().startswith(
                                                ("import ", "from ")
                                            )
                                        ]
                                    )
                                    total_functions += len(
                                        [
                                            line
                                            for line in content.splitlines()
                                            if line.strip().startswith(
                                                ("def ", "async def ")
                                            )
                                        ]
                                    )
                        except Exception as e:
                            print(f"Error processing {file_path}: {e}")
                            continue

            embed = discord.Embed(
                description=f"Owned and Maintained by **[playfairs](https://playfairs.cc)**\n{total_commands} **commands** | {total_imports} **imports | {total_modules} **modules",
                color=discord.Color(0xFFFFFF),
            )

            embed.add_field(
                name="**Basic**",
                value=f"**Users**: {len(self.bot.users)}\n**Guilds**: {len(self.bot.guilds)}\n**Created**: <t:1741389840:d>\n**Members**: {self.bot.get_guild(1271976967381712989).member_count:,}",
                inline=True,
            )

            embed.add_field(
                name="**Runtime**",
                value=f"**OS**: {host}\n**CPU**: {psutil.cpu_percent()}%\n**Memory**: {psutil.Process().memory_info().rss / 1024 / 1024:.2f} MB\n**Uptime**: {uptime_str}",
                inline=True,
            )

            embed.add_field(
                name="**Code**",
                value=f"**Files**: {total_files}\n**Lines**: {total_lines:,}\n**Functions**: {total_functions}\n**Library**: dpy {discord.__version__}",
                inline=True,
            )

            embed.set_thumbnail(url=Media.vortex)
            current_time = datetime.now().strftime("%I:%M %p")
            embed.set_footer(
                text=f"Requested by {interaction.user} • Today at {current_time}",
                icon_url=(
                    interaction.user.display_avatar.url
                    if interaction.user.avatar
                    else await self.default_avatar_manager.get_user_avatar_or_default(
                        interaction.user
                    )
                ),
            )

            view = View(timeout=180)

            async def on_timeout():
                for item in view.children:
                    item.disabled = True
                try:
                    await view.message.edit(view=view)
                except:
                    pass

            view.on_timeout = on_timeout

            guild = self.bot.get_guild(1271976967381712989)
            if guild:
                try:
                    channel = next(
                        (
                            ch
                            for ch in guild.text_channels
                            if ch.permissions_for(guild.me).create_instant_invite
                        ),
                        None,
                    )
                    if channel:
                        invite = await channel.create_invite(
                            max_uses=1,
                            unique=True,
                            reason=f"One-time invite generated for {interaction.user}",
                            max_age=604800,
                        )
                        server_button = Button(
                            label="Support", url=str(invite), style=ButtonStyle.link
                        )
                    else:
                        raise Exception("No suitable channel found for invite")
                except Exception as e:
                    print(f"Error creating one-time invite: {e}")
                    server_button = Button(
                        label="Support", url=f"{Servers.vortex}", style=ButtonStyle.link
                    )
            else:
                server_button = Button(
                    label="Support", url=f"{Servers.vortex}", style=ButtonStyle.link
                )
            view.add_item(server_button)

            invite_button = Button(
                label="Invite",
                url="https://discord.com/oauth2/authorize?client_id=1347441071323480074&permissions=8&integration_type=0&scope=bot",
                style=ButtonStyle.link,
            )
            view.add_item(invite_button)

            website_button = Button(
                label="Website",
                url="https://vortex.playfairs.cc",
                style=ButtonStyle.link,
            )
            view.add_item(website_button)

            await interaction.response.send_message(embed=embed, view=view)

    @command(name="commands", description="Sends link to the bot's commands.")
    async def commands(self, ctx: Context):
        await ctx.send(
            "For the full list of commands, visit <https://vortex.playfairs.cc/commands> or use the help command for in-app help."
        )

    @command(name="privacy", description="Sends link to the bot's privacy policy.")
    async def privacy(self, ctx: Context):
        await ctx.send("<https://vortex.playfairs.cc/privacy>")

    @command(name="terms", description="Sends link to the bot's terms of service.")
    async def terms(self, ctx: Context):
        await ctx.send("<https://vortex.playfairs.cc/terms>")

    @command(
        name="docs",
        aliases=["documentation"],
        description="Sends link to the bot's documentation.",
    )
    async def docs(self, ctx: Context):
        await ctx.send("<https://vortex.playfairs.cc/docs>")

    @command(
        name="bi",
        aliases=["botinfo", "abt", "bitch"],
        help="Shows detailed information about the bot.",
    )
    async def show_bot_info(self, ctx: Context):
        """Displays detailed information about the bot including stats and system info."""
        bot = self.bot

        commands_list = []
        for cmd in sorted(bot.walk_commands(), key=lambda c: c.qualified_name):
            if isinstance(cmd, commands.Group):
                commands_list.append(cmd.qualified_name)
                for subcmd in cmd.walk_commands():
                    commands_list.append(subcmd.qualified_name)
            else:
                commands_list.append(cmd.qualified_name)

        total_commands = len(commands_list)
        total_modules = len(list(bot.extensions.keys()))

        if platform.system() == "Darwin":
            host = "MacOS " + platform.mac_ver()[0]
        else:
            host = platform.system() + " " + platform.release()

        jishaku = self.bot.get_cog("Jishaku")
        if jishaku:
            uptime = datetime.now(timezone.utc) - jishaku.load_time
            days = uptime.days
            hours, remainder = divmod(uptime.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"
        else:
            uptime_str = "Unable to calculate"

        total_lines = 0
        total_files = 0
        total_imports = 0
        total_functions = 0

        project_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../..")
        )  # heheh, bigger numbers = better code and funny :3
        search_dirs = [project_root]
        venv_path = os.path.join(
            project_root, "venv"
        )  # >_< is this a bad idea, nooooo its a wonderful idea >.<
        if os.path.exists(venv_path):
            search_dirs.append(venv_path)

        for directory in search_dirs:
            for root, _, files in os.walk(directory):
                for file in files:
                    if file.startswith("."):
                        continue

                    try:
                        file_path = os.path.join(root, file)
                        with open(
                            file_path, "r", encoding="utf-8", errors="ignore"
                        ) as f:
                            content = f.read()
                            total_files += 1
                            total_lines += len(content.splitlines())

                            if file.endswith(".py"):
                                total_imports += len(
                                    [
                                        line
                                        for line in content.splitlines()
                                        if line.strip().startswith(("import ", "from "))
                                    ]
                                )
                                total_functions += len(
                                    [
                                        line
                                        for line in content.splitlines()
                                        if line.strip().startswith(
                                            ("def ", "async def ")
                                        )
                                    ]
                                )
                    except Exception as e:
                        print(f"Error processing {file_path}: {e}")
                        continue

        embed = discord.Embed(
            description=f"Owned and Maintained by **[playfairs](https://playfairs.cc)**\n{total_commands} **commands** | {total_imports} **imports** | {total_modules} **modules**",
            color=discord.Color(0xFFFFFF),
        )

        embed.add_field(
            name="**Basic**",
            value=f"**Users**: {len(self.bot.users)}\n**Guilds**: {len(self.bot.guilds)}\n**Created**: <t:1741389840:d>\n**Members**: {self.bot.get_guild(1271976967381712989).member_count:,}",
            inline=True,
        )

        embed.add_field(
            name="**Runtime**",
            value=f"**OS**: {host}\n**CPU**: {psutil.cpu_percent()}%\n**Memory**: {psutil.Process().memory_info().rss / 1024 / 1024:.2f} MB\n**Uptime**: {uptime_str}",
            inline=True,
        )

        embed.add_field(
            name="**Code**",
            value=f"**Files**: {total_files}\n**Lines**: {total_lines:,}\n**Functions**: {total_functions}\n**Library**: dpy {discord.__version__}",
            inline=True,
        )

        embed.set_thumbnail(url=Media.vortex)
        current_time = datetime.now().strftime("%I:%M %p")
        embed.set_footer(
            text=f"Requested by {ctx.author}",
            icon_url=(
                ctx.author.display_avatar.url
                if ctx.author.avatar
                else await self.default_avatar_manager.get_user_avatar_or_default(
                    ctx.author
                )
            ),
        )

        view = View(timeout=180)

        async def on_timeout():
            for item in view.children:
                item.disabled = True
            try:
                await view.message.edit(view=view)
            except:
                pass

        view.on_timeout = on_timeout

        guild = self.bot.get_guild(1271976967381712989)
        if guild:
            try:
                channel = next(
                    (
                        ch
                        for ch in guild.text_channels
                        if ch.permissions_for(guild.me).create_instant_invite
                    ),
                    None,
                )
                if channel:
                    invite = await channel.create_invite(
                        max_uses=1,
                        unique=True,
                        reason=f"One-time invite generated for {ctx.author}",
                        max_age=604800,
                    )
                    server_button = Button(
                        label="Support", url=str(invite), style=ButtonStyle.link
                    )
                else:
                    raise Exception("No suitable channel found for invite")
            except Exception as e:
                print(f"Error creating one-time invite: {e}")
                server_button = Button(
                    label="Support", url=f"{Servers.vortex}", style=ButtonStyle.link
                )
        else:
            server_button = Button(
                label="Support", url=f"{Servers.vortex}", style=ButtonStyle.link
            )
        view.add_item(server_button)

        invite_button = Button(
            label="Invite",
            url="https://discord.com/oauth2/authorize?client_id=1347441071323480074&permissions=8&integration_type=0&scope=bot",
            style=ButtonStyle.link,
        )
        view.add_item(invite_button)

        website_button = Button(
            label="Website",
            url="https://vortex.playfairs.cc",
            style=ButtonStyle.link,
        )
        view.add_item(website_button)

        await ctx.send(embed=embed, view=view)

    @hybrid(
        name="whois",
        description="Show basic information about a user not in a server by ID.",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(user="The user you want to look up.")
    async def whois(self, ctx, user: discord.User = None):
        user = user or ctx.author
        user = await self.bot.fetch_user(user.id)

        view = await WhoisView.create(user, ctx, self.bot)
        await ctx.send(view=view)

    @hybrid(
        name="userinfo",
        aliases=["who", "ui", "info", "whoami", "profile"],
        description="Show detailed information about a user.",
    )
    @app_commands.describe(member="The user you want to look up.")
    async def userinfo(self, ctx: Context, member: discord.Member = None):
        """
        Displays detailed user information with badges, activity, and roles.
        """
        try:
            member = member or ctx.author

            if member.id == self.bot.user.id:
                return await self.bot.get_command("botinfo").invoke(ctx)

            if not isinstance(member, discord.Member):
                try:
                    member = await ctx.guild.fetch_member(member.id)
                except:
                    await ctx.send("This is a server only command.", ephemeral=True)
                    return

            if member.id in BLACKLIST.USER_ID:
                await ctx.send("This user is blacklisted from vortex.")
                return

            view = await UserInfoView.create(member, ctx, self.bot)
            await ctx.send(view=view)

        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}", ephemeral=True)
            raise e

    @hybrid(name="userid", aliases=["uid", "whoid", "id"])
    @app_commands.describe(
        user_id="The ID of the user you want to look up.",
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def userid(self, ctx: Context, user_id: str = None):
        """Shows the user ID of the specified user or yourself if no one is mentioned."""
        if user_id == None or user_id == "<@" + str(ctx.author.id) + ">":
            await ctx.send(f"Your user ID is `{ctx.author.id}`")
        elif user_id == "<@" + "1347441071323480074" + ">":
            await ctx.send("My user ID is `1347441071323480074`")

        # Mentioned User
        elif user_id.startswith("<@") and user_id.endswith(">"):
            user_id = user_id.replace("<@", "").replace("!", "").replace(">", "")
            member = ctx.guild.get_member(int(user_id))
            if member:
                await ctx.send(
                    f"`{member.id}`", allowed_mentions=discord.AllowedMentions.none()
                )
            else:
                await ctx.send("Member not found.")

        # Named User
        elif (
            user_name := ctx.guild.get_member_named(user_id) and user_name != ctx.author
        ):
            await ctx.send(f"`{user_name.id}`")
        elif (
            user_name := ctx.guild.get_member_named(user_id) and user_name == ctx.author
        ):
            await ctx.send(
                f"`Your user ID is {user_name.id}`",
                allowed_mentions=discord.AllowedMentions.none(),
            )

        # Raw ID
        elif user_id.isdigit() and user_id == "1347441071323480074":
            await ctx.send("Raw ID belongs to me!")
        elif user_id.isdigit() and user_id == str(ctx.author.id):
            await ctx.send("Raw ID belongs to you!")
        elif user_id.isdigit():
            try:
                return await ctx.send(
                    f"Raw ID belongs to <@{user_id}>",
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            except discord.HTTPException:
                return await ctx.send("User not found.")
        else:
            await ctx.send("Invalid User.")

    @hybrid(name="roleid", aliases=["rid"])
    @app_commands.describe(
        role="The role to show the ID for.",
    )
    async def roleid(self, ctx: Context, role: discord.Role = None):
        """Shows the role ID of the specified role or yourself if no one is mentioned."""
        role = role or ctx.author
        await ctx.send(f"`{role.id}`")

    @command(name="serverid", aliases=["sid"])
    async def serverid(self, ctx: Context):
        await ctx.send(f"`{ctx.guild.id}`")

    @command(
        name="si",
        aliases=["serverinfo"],
        help="Show the server info.",
    )
    @cooldown(1, 3, BucketType.user)
    async def server_info(self, ctx: Context, guild_id: int = None):
        """Shows the server information in an embed.

        In DMs, you must specify a guild ID.
        If you're a bot owner, you can specify any guild ID the bot is in.
        """
        if not ctx.guild and guild_id is None:
            return await ctx.send(
                "Please specify a server ID when using this command in DMs."
            )

        if guild_id is not None:
            if not await self.bot.is_owner(ctx.author):
                return await ctx.send("Only bot owners can specify a guild ID.")
            guild = self.bot.get_guild(guild_id)
            if not guild:
                return await ctx.send("I'm not in that server or the ID is invalid.")
        else:
            guild = ctx.guild

        if not guild.me.guild_permissions.embed_links:
            await ctx.send("I don't have permission to send embeds in that server.")
            return
        owner = guild.owner
        verification_level = guild.verification_level
        boosts = guild.premium_subscription_count
        booster_role = guild.premium_subscriber_role
        boosters = (
            [member for member in guild.members if booster_role in member.roles]
            if booster_role
            else []
        )

        total_boosters = len(boosters)

        total_members = guild.member_count
        bots = sum(1 for member in guild.members if member.bot)
        humans = total_members - bots
        admins = sum(
            1
            for member in guild.members
            if not member.bot and member.guild_permissions.administrator
        )

        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories = len(guild.categories)
        roles = len(guild.roles) - 1

        vanity_url_code = guild.vanity_url_code
        vanity_url = f"/{vanity_url_code}" if vanity_url_code else "None"

        server_description = guild.description or "No server description set"
        creation_time = guild.created_at.strftime("%B %d, %Y")
        now = datetime.now(timezone.utc)
        created_at = guild.created_at
        delta = now - created_at
        years = delta.days // 365
        time_since_creation = (
            f"{years} year{'s' if years != 1 else ''} ago"
            if years >= 1
            else f"{delta.days} day{'s' if delta.days > 1 else ''} ago"
        )

        server_icon_url = guild.icon.url if guild.icon else None

        embed = discord.Embed(
            title=f"`{guild.name}`",
            description=f"{server_description}\n\n",
            color=discord.Color(0xFFFFFF),
        )

        if server_icon_url:
            embed.set_thumbnail(url=server_icon_url)

        embed.add_field(
            name="**Server**",
            value=(
                f"> **Owner**: {owner.mention}\n"
                f"> **Verification**: {verification_level}\n"
                f"> **Boosts**: {boosts}\n"
                f"> **Level**: {guild.premium_tier}\n"
                f"> **Vanity**: {vanity_url}"
            ),
            inline=True,
        )

        embed.add_field(
            name="**Members**",
            value=(
                f"> **Total**: {total_members:,}\n"
                f"> **Humans**: {humans:,}\n"
                f"> **Boosters**: {total_boosters:,}\n"
                f"> **Bots**: {bots:,}\n"
                f"> **Admins**: {admins:,}"
            ),
            inline=True,
        )

        embed.add_field(
            name="**Structure**",
            value=(
                f"> **Channels**: {text_channels:,}\n"
                f"> **Voice**: {voice_channels:,}\n"
                f"> **Categories**: {categories:,}\n"
                f"> **Roles**: {roles:,}\n"
                f"> **Emotes**: {len(guild.emojis) + len(guild.stickers)}"
            ),
            inline=True,
        )

        view = discord.ui.View(timeout=180)

        async def on_timeout():
            for item in view.children:
                item.disabled = True
            try:
                await view.message.edit(view=view)
            except:
                pass

        view.on_timeout = on_timeout

        if guild.banner:
            banner_button = discord.ui.Button(
                label="Banner", style=discord.ButtonStyle.gray, custom_id="show_banner"
            )

            async def banner_callback(interaction):
                if guild.banner:
                    banner_embed = discord.Embed(color=discord.Color(0xFFFFFF))
                    banner_embed.set_author(
                        name=f"Banner for {guild.name}", icon_url=guild.icon.url
                    )
                    banner_embed.set_image(url=guild.banner.url)
                    banner_embed.set_footer(text=f"Guild ID: {guild.id}")

                    new_view = discord.ui.View(timeout=180)

                    async def banner_timeout():
                        for item in new_view.children:
                            item.disabled = True
                        try:
                            await new_view.message.edit(view=new_view)
                        except:
                            pass

                    new_view.on_timeout = banner_timeout

                    info_button = discord.ui.Button(
                        label="Server Info",
                        style=discord.ButtonStyle.gray,
                        custom_id="show_info",
                    )

                    async def info_callback(interaction):
                        await interaction.response.edit_message(embed=embed, view=view)

                    info_button.callback = info_callback
                    new_view.add_item(info_button)

                    await interaction.response.edit_message(
                        embed=banner_embed, view=new_view
                    )
                    new_view.message = await interaction.original_response()
                else:
                    await interaction.response.send_message(
                        "This server doesn't have a banner.", ephemeral=True
                    )

            banner_button.callback = banner_callback
            view.add_item(banner_button)

        roles_button = discord.ui.Button(
            label="Roles", style=discord.ButtonStyle.gray, custom_id="show_roles"
        )

        async def roles_callback(interaction):
            roles = sorted(
                [role for role in guild.roles if role.name != "@everyone"],
                key=lambda r: r.position,
                reverse=True,
            )
            roles.append(guild.default_role)

            class RolesViewWithBack(RolesView):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **kwargs)
                    back_button = discord.ui.Button(
                        label="Server Info", style=discord.ButtonStyle.gray, row=1
                    )

                    async def back_callback(interaction):
                        await interaction.response.edit_message(embed=embed, view=view)

                    back_button.callback = back_callback
                    self.add_item(back_button)

                async def on_timeout(self):
                    for item in self.children:
                        item.disabled = True
                    try:
                        await self.message.edit(view=self)
                    except:
                        pass

            roles_view = RolesViewWithBack(
                roles=roles, author=ctx.author, custom_emojis={}
            )
            await interaction.response.edit_message(
                embed=roles_view.get_embed(), view=roles_view
            )
            roles_view.message = await interaction.original_response()

        roles_button.callback = roles_callback
        view.add_item(roles_button)

        async def features_callback(interaction):
            features = sorted(guild.features)  # Sort features alphabetically hehehehehe

            features_embed = discord.Embed(
                title="Server Features",
                description=(
                    "\n".join(features)
                    if features
                    else "No special features enabled for this server."
                ),
                color=discord.Color(0xFFFFFF),
            )

            features_view = discord.ui.View(timeout=180)

            async def features_timeout():
                for item in features_view.children:
                    item.disabled = True
                try:
                    await features_view.message.edit(view=features_view)
                except:
                    pass

            features_view.on_timeout = features_timeout

            back_button = discord.ui.Button(
                label="Server Info",
                style=discord.ButtonStyle.gray,
                custom_id="back_to_server_info",
            )

            async def back_callback(interaction):
                await interaction.response.edit_message(embed=embed, view=view)

            back_button.callback = back_callback
            features_view.add_item(back_button)

            await interaction.response.edit_message(
                embed=features_embed, view=features_view
            )
            features_view.message = await interaction.original_response()

        features_button = discord.ui.Button(
            label="Features", style=discord.ButtonStyle.gray, custom_id="show_features"
        )
        features_button.callback = features_callback
        view.add_item(features_button)

        embed.set_footer(text=f"Guild ID: {guild.id} | Created: {creation_time}")

        await ctx.send(embed=embed, view=view)

    @command(
        name="serverfeatures",
        aliases=["sf", "features"],
        description="Display all features the server can access.",
    )
    async def server_features(self, ctx: Context):
        """Display all features the server can access."""
        guild = ctx.guild
        features = sorted(guild.features)  # Sort features alphabetically.. again

        embed = discord.Embed(
            title="Server Features",
            description=(
                "\n".join(features)
                if features
                else "No special features enabled for this server."
            ),
            color=discord.Color(0xFFFFFF),
        )
        await ctx.send(embed=embed)

    @command(
        name="ri",
        aliases=["roleinfo"],
        description="Display detailed information about a role.",
    )
    async def ri(self, ctx, *, role: discord.Role = None):
        await self.bot.get_cog("Moderation").role_info(ctx, role=role)

    @command(
        name="roles",
        alises=["rl", "rolelist"],
        description="Lists all roles in the server.",
    )
    @has_permissions(manage_roles=True)
    async def roles(self, ctx, user: discord.Member = None):
        await self.bot.get_cog("Moderation").roles(ctx, user=user)

    @command(
        name="mc",
        aliases=["membercount", "members"],
        description="Display the member count of the server.",
    )
    @cooldown(1, 3, BucketType.user)
    async def member_count(self, ctx: Context):
        guild = ctx.guild
        total_bots = sum(1 for member in guild.members if member.bot)
        total_humans = guild.member_count - total_bots
        boosters = [
            member for member in guild.members if member.premium_since is not None
        ]
        total_boosters = len(boosters)
        owner_ids = DISCORD.OWNER_IDS
        total_aliens = len([m for m in guild.members if m.id in owner_ids])

        embed = discord.Embed(
            title=f"Member Count for **{guild.name}**", color=discord.Color(0xFFFFFF)
        )

        embed.add_field(
            name="**Total**",
            value=f"> **Total**: {guild.member_count:,}\n"
            f"> **Humans**: {total_humans:,}\n"
            f"> **Boosters**: {total_boosters:,}\n"
            f"> **Bots**: {total_bots:,}\n"
            f"> **Aliens**: {total_aliens:,}",
            inline=True,
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        await ctx.send(embed=embed)

    @command(
        name="bots",
        aliases=["botcount"],
        description="Displays the number of bots in the server.",
    )
    async def bots(self, ctx: Context):
        """Displays the number of bots in the server."""
        bots = [member for member in ctx.guild.members if member.bot]
        pages = []
        for i in range(0, len(bots), 10):
            page = discord.Embed(
                title=f"Bots in {ctx.guild.name} ({len(bots)})",
                color=discord.Color(0xFFFFFF),
            )
            page.set_footer(text=f"Page {i//10+1}/{(len(bots)-1)//10+1}")
            page.add_field(
                name="",
                value="\n".join([f"{bot.mention}" for bot in bots[i : i + 10]]),
                inline=False,
            )
            pages.append(page)

        class PaginationView(discord.ui.View):
            def __init__(self, pages, timeout=180):
                super().__init__(timeout=timeout)
                self.pages = pages
                self.current_page = 0
                self.message = None
                self.update_buttons()

            def update_buttons(self):
                self.children[0].disabled = self.current_page == 0
                self.children[1].label = (
                    f"Page {self.current_page + 1}/{len(self.pages)}"
                )
                self.children[2].disabled = self.current_page >= len(self.pages) - 1

            async def update_message(self, interaction: discord.Interaction):
                self.update_buttons()
                await interaction.response.edit_message(
                    embed=self.pages[self.current_page], view=self
                )

            @discord.ui.button(emoji=Emojis.left, style=discord.ButtonStyle.gray)
            async def previous_button(
                self, interaction: discord.Interaction, button: discord.ui.Button
            ):
                if self.current_page > 0:
                    self.current_page -= 1
                    await self.update_message(interaction)

            @discord.ui.button(style=discord.ButtonStyle.gray, disabled=True)
            async def page_button(
                self, interaction: discord.Interaction, button: discord.ui.Button
            ):
                pass

            @discord.ui.button(emoji=Emojis.right, style=discord.ButtonStyle.gray)
            async def next_button(
                self, interaction: discord.Interaction, button: discord.ui.Button
            ):
                if self.current_page < len(self.pages) - 1:
                    self.current_page += 1
                    await self.update_message(interaction)

            async def on_timeout(self):
                if self.message:
                    await self.message.edit(view=None)
                    self.stop()

        view = PaginationView(pages)
        view.message = await ctx.send(embed=pages[0], view=view)

    @command(name="serverbanner", description="Shows the server banner in an embed.")
    @cooldown(1, 3, BucketType.user)
    async def server_banner(self, ctx):
        """Shows the server banner in an embed."""
        if ctx.guild.banner:
            embed = discord.Embed(
                title=f"{ctx.guild.name} Server Banner", color=discord.Color(0xFFFFFF)
            )
            embed.set_image(url=ctx.guild.banner.url)
            await ctx.send(embed=embed)
        else:
            await ctx.send("This server does not have a banner set.")

    @command(name="sicon", description="Shows the server icon in an embed.")
    @cooldown(1, 3, BucketType.user)
    async def server_icon(self, ctx):
        """Shows the server icon in an embed."""
        if not ctx.guild:
            await ctx.send("This command can only be used in a server.")
            return

        if ctx.guild.icon:
            embed = discord.Embed(
                title=f"{ctx.guild.name} Server Icon", color=discord.Color(0xFFFFFF)
            )
            embed.set_image(url=ctx.guild.icon.url)
            await ctx.send(embed=embed)
        else:
            await ctx.send("This server does not have an icon set.")

    @command(
        name="splash",
        description="Shows the server splash (invite banner) in an embed.",
    )
    @cooldown(1, 3, BucketType.user)
    async def server_splash(self, ctx):
        """Shows the server splash (invite banner) in an embed."""
        if ctx.guild.splash:
            embed = discord.Embed(
                title=f"{ctx.guild.name} Server Splash", color=discord.Color(0xFFFFFF)
            )
            embed.set_image(url=ctx.guild.splash.url)
            await ctx.send(embed=embed)
        else:
            await ctx.send("This server does not have a splash image set.")

    @hybrid(name="avatar", aliases=["pfp", "av"], description="Show your avatar.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(user="Select either a User or self to show your avatar.")
    @cooldown(1, 3, BucketType.user)
    async def avatar(self, ctx, user: Union[discord.User, discord.User] = None):
        user = user or ctx.author

        if not user.avatar:
            await ctx.send(
                f"{user.mention} doesn't have an avatar, man, who runs around discord without an avatar."
            )
            return

        view = AvContainer(user)
        await ctx.send(view=view)

    @command(
        name="serveravatar",
        aliases=["sav", "savatar"],
        description="Show your server avatar.",
    )  # Since this only matters for servers, no need to make it hybrid
    @cooldown(1, 3, BucketType.user)
    async def serveravatar(
        self, ctx, member: Union[discord.Member, discord.User] = None
    ):
        member = member or ctx.author
        if not member.guild_avatar:
            await ctx.send(f"{member.mention} does not have a server avatar.")
            return
        view = ServerAvatarView(member)
        await ctx.send(view=view)

    @hybrid(
        name="banner", description="Show your banner."
    )  # This however is global, this stays hybrid
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(
        member="Select either a User or if none is selected, the current user will be used."
    )
    async def banner(self, ctx, member: Union[discord.Member, discord.User] = None):
        user = member or ctx.author
        user = await self.bot.fetch_user(user.id)
        if not user.banner:
            await ctx.send(f"{user.mention} does not have a banner.")
            return
        view = BannerView(user)
        await ctx.send(view=view)

    @command(
        name="sbanner", description="Show your server banner."
    )  # This, does NOT stay hybrid
    async def serverbanner(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        if not member.guild_banner:
            await ctx.send(f"{member.mention} does not have a server banner.")
            return
        view = ServerBannerView(member)
        await ctx.send(view=view)

    @command(
        name="permissions",
        aliases=["perm", "perms"],
        description="Checks the permissions of a member or a role.",
    )
    async def _permissions(self, ctx: Context, *, target: str = None):
        """Checks the permissions of a member or a role."""
        if not target:
            role_or_user = ctx.author
        else:
            try:
                target_id = int(target)
                role = discord.utils.get(ctx.guild.roles, id=target_id)
                if role:
                    role_or_user = role
                else:
                    user = discord.utils.get(ctx.guild.members, id=target_id)
                    if user:
                        role_or_user = user
                    else:
                        embed = discord.Embed(
                            title="Error",
                            description="Could not find a role or user with that ID.",
                            color=discord.Color.red(),
                        )
                        return await ctx.send(embed=embed)
            except ValueError:
                if target.startswith("<@&"):
                    role_id = int(target.strip("<@&>"))
                    role = discord.utils.get(ctx.guild.roles, id=role_id)
                    if not role:
                        embed = discord.Embed(
                            title="Error",
                            description="Could not find the specified role.",
                            color=discord.Color.red(),
                        )
                        return await ctx.send(embed=embed)
                    role_or_user = role
                elif target.startswith("<@"):
                    user_id = int(target.strip("<@>"))
                    user = discord.utils.get(ctx.guild.members, id=user_id)
                    if not user:
                        embed = discord.Embed(
                            title="Error",
                            description="Could not find the specified user.",
                            color=discord.Color.red(),
                        )
                        return await ctx.send(embed=embed)
                    role_or_user = user
                else:
                    role = discord.utils.get(ctx.guild.roles, name=target)
                    if role:
                        role_or_user = role
                    else:
                        user = discord.utils.find(
                            lambda m: m.name.lower() == target.lower(),
                            ctx.guild.members,
                        )
                        if user:
                            role_or_user = user
                        else:
                            embed = discord.Embed(
                                title="Error",
                                description="Could not find a matching role or user.",
                                color=discord.Color.red(),
                            )
                            return await ctx.send(embed=embed)

        if isinstance(role_or_user, discord.Role):
            permissions = role_or_user.permissions
            title = f"Permissions for Role: `{role_or_user.name}`"
        else:
            permissions = role_or_user.guild_permissions
            title = f"Permissions for User: `{role_or_user.display_name}`"

        category_permissions = {}

        for category in dir(Permissions):
            if category.isupper():
                category_perms = getattr(Permissions, category)
                category_permissions[category] = {
                    perm: getattr(permissions, perm, False) for perm in category_perms
                }

        pages = [
            {category: category_permissions[category]}
            for category in category_permissions
        ]

        if not pages:
            embed = discord.Embed(
                title=title,
                description="No permissions found.",
                color=discord.Color(0xFFFFFF),
            )
            return await ctx.send(embed=embed)

        view = PermissionPages(pages=pages, title=title)
        message = await ctx.send(embed=await view.update_message(None), view=view)
        view.message = message

    @command(name="prefix", description="Fetches the current prefixes for the bot.")
    async def prefix(self, ctx: Context):
        try:
            server_prefix = await self.bot.db.fetchval(
                "SELECT prefix FROM config WHERE guild_id = $1", ctx.guild.id
            )
        except Exception:
            server_prefix = None

        global_prefixes = getattr(DISCORD, "PREFIXES", [])
        all_conflicting = getattr(DISCORD, "CONFLICTING_PREFIXES", [])

        guild_bot_ids = {member.id for member in ctx.guild.members if member.bot}

        conflicting_bots = []
        for i in range(0, len(all_conflicting), 2):
            if i + 1 < len(all_conflicting):
                bot_id = all_conflicting[i]
                if bot_id in guild_bot_ids:
                    prefix = all_conflicting[i + 1]
                    bot = self.bot.get_user(bot_id)
                    bot_name = getattr(bot, "name", f"Bot {bot_id}")
                    conflicting_bots.append((bot_name, prefix))

        container = discord.ui.Container()
        container.add_item(discord.ui.TextDisplay(content="### Prefix Information"))
        container.add_item(
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small)
        )

        if server_prefix:
            container.add_item(
                discord.ui.TextDisplay(
                    content=f"**Server Prefix:** \n> `{server_prefix}`"
                )
            )
            container.add_item(
                discord.ui.Separator(
                    visible=True, spacing=discord.SeparatorSpacing.small
                )
            )

        if global_prefixes:
            container.add_item(
                discord.ui.TextDisplay(
                    content="**Global Prefixes:** \n"
                    + "\n".join(f"> `{p}`" for p in global_prefixes)
                )
            )
            container.add_item(
                discord.ui.Separator(
                    visible=True, spacing=discord.SeparatorSpacing.small
                )
            )

        if conflicting_bots:
            conflict_text = []
            for bot_name, prefix in conflicting_bots:
                conflict_text.append(f"> `{prefix}`")

            container.add_item(
                discord.ui.TextDisplay(
                    content=f"**Conflicting Prefixes:** \n"
                    + "\n".join(conflict_text)
                    + "\n\n*These prefixes are ignored when the corresponding bot is present in the server.*\n"
                    + "-# If you find a bot with a prefix that conflicts with any of these, you can report it in the support server, or DM the owner (<@1426711359059394662>)."
                )
            )

        view = discord.ui.LayoutView()
        view.add_item(container)
        await ctx.send(view=view)

    @command(name="support", description="Sends a link to the bot's support server.")
    async def support(self, ctx: Context):
        support_server_id = 1271976967381712989
        support_channel_id = 1333059678137221210

        try:
            support_guild = self.bot.get_guild(support_server_id)
            if not support_guild:
                return await ctx.author.send(
                    "I couldn't access the support server. Please try again later."
                )

            channel = support_guild.get_channel(support_channel_id)
            if not channel or not isinstance(channel, discord.TextChannel):
                return await ctx.author.send(
                    "Couldn't find the support channel. Please contact the bot owner."
                )

            if not channel.permissions_for(support_guild.me).create_instant_invite:
                return await ctx.author.send(
                    "I don't have permission to create invites in the support channel."
                )

            invite = await channel.create_invite(
                max_uses=1,
                unique=True,
                reason=f"Support invite generated for {ctx.author}",
                max_age=604800,
            )

            await ctx.author.send(
                f"Here's your one-time invite to the support server: {invite}"
            )

        except discord.Forbidden:
            await ctx.send(
                "I can't DM you because of your privacy settings, please enable DMs for this server, then try again."
            )
        except Exception as e:
            await ctx.send(f"An error occurred while creating the invite: {e}")

    @hybrid(
        name="invite",
        aliases=["gbi"],
        description="Generates an invite link for the bot.",
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def invite(self, ctx: Context, user: Optional[discord.Member] = None):
        """Generates an invite link for the bot."""
        try:
            app_info = await self.bot.application_info()
            client_id = app_info.id
            permissions = discord.Permissions(8).value

            invite_url = (
                f"https://discord.com/oauth2/authorize?"
                f"client_id={client_id}&permissions={permissions}&integration_type=0&scope=bot+applications.commands"
            )

            container = discord.ui.Container(
                discord.ui.TextDisplay(content="### Guild Invite"),
                discord.ui.Separator(
                    visible=True, spacing=discord.SeparatorSpacing.small
                ),
                discord.ui.TextDisplay(
                    content=f"Inviting the bot to your server will allow you and others to use the bot's commands, and other features, additionally, the bot will request Admin on invite, this is just for the bot to function properly with some commands. If you plan on managing roles with the bot, you will need to ensure the bots role is above any relevant roles.\n\nFinally, if your guild has under 10 real members, the bot will leave automatically. This is to prevent abuse. **I'm sure you understand :)**"
                ),
                discord.ui.Separator(
                    visible=True, spacing=discord.SeparatorSpacing.small
                ),
                discord.ui.TextDisplay(
                    content="-# If you have any questions, or need support, please join our support server."
                ),
            )
            container.accent_colour = discord.Colour(0xFFFFFF)
            action_row = discord.ui.ActionRow()
            action_row.add_item(discord.ui.Button(label="Invite", url=invite_url))
            container.add_item(action_row)
            view = discord.ui.LayoutView()
            view.add_item(container)
            await ctx.send(view=view)
        except Exception as e:
            await ctx.send(f"```py\n{type(e).__name__}: {str(e)}```", ephemeral=True)

    @hybrid(
        name="install", description="Generates an OAuth2 User Install link for the bot."
    )
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def install(self, ctx: Context):
        """Generates an OAuth2 User Install link for the bot."""
        try:
            app_info = await self.bot.application_info()
            client_id = app_info.id
            install_url = (
                f"https://discord.com/oauth2/authorize?"
                f"client_id={client_id}&integration_type=1&scope=applications.commands"
            )

            container = discord.ui.Container(
                discord.ui.TextDisplay(content="### User Install"),
                discord.ui.Separator(
                    visible=True, spacing=discord.SeparatorSpacing.small
                ),
                discord.ui.TextDisplay(
                    content="Installing the bot will allow you to use the bot anywhere you have access to your apps, this only includes Application Commands, and message context menus."
                ),
                discord.ui.Separator(
                    visible=True, spacing=discord.SeparatorSpacing.small
                ),
            )
            container.accent_colour = discord.Colour(0xFFFFFF)
            action_row = discord.ui.ActionRow()
            action_row.add_item(discord.ui.Button(label="Install", url=install_url))
            container.add_item(action_row)

            view = discord.ui.LayoutView()
            view.add_item(container)
            await ctx.send(view=view)
        except Exception as e:
            await ctx.send(f"```py\n{type(e).__name__}: {str(e)}```", ephemeral=True)

    @command(
        name="vortex",
        description="Pointless command, shows the song in which the bots name was inspired by.",
    )
    async def vortex(self, ctx: Context):
        await ctx.send(
            "https://open.spotify.com/track/2L4ixu8XcjeKSm90C2ltGS?si=cde01410ee414c1d"
        )

    @command(name="rtt", aliases=["ping", "pong", "roundtrip", "latency"])
    @cooldown(1, 3, BucketType.user)
    async def rtt(self, ctx: Context):
        """Check the round-trip time (RTT) of the bot."""
        random_phrases = [
            "the White House",
            "Japan",
            "your mother's basement",
            "your WiFi router",
            "your television",
            "the terminal",
            "the toaster",
            "your mom",
            "Heresy",
        ]

        random_ping = random.choice(random_phrases)

        start_time = time.perf_counter()
        message = await ctx.send("Pinging...")
        ping_time = time.perf_counter()
        await message.edit(content="Calculating latency...")
        edit_time = time.perf_counter()

        rtt_ms = round((ping_time - start_time) * 1000, 2)
        rtt_s = round(ping_time - start_time, 2)
        edit_s = round(edit_time - ping_time, 2)
        websocket_latency = round(self.bot.latency * 1000, 2)

        embed = discord.Embed(
            title="RTT (Round-time Trip)",
            description=(
                f" **RTT**: `{rtt_ms}ms`\n"
                f" **Took `{rtt_s}s` to ping *{random_ping}* and `{edit_s}s` to edit the message.**\n"
                f" **Websocket Latency**: `{websocket_latency}ms`"
            ),
            color=discord.Color(0xFFFFFF),
        )
        await message.edit(content=None, embed=embed)

    @command(name="ltt", aliases=["oneway", "latencyoneway", "halfping"])
    @cooldown(1, 3, BucketType.user)
    async def ltt(self, ctx: Context):
        """Estimate the one-way latency (LTT) of the bot."""
        start_time = time.perf_counter()
        message = await ctx.send("Pinging one-way...")
        end_time = time.perf_counter()

        rtt = (end_time - start_time) * 1000
        estimated_ltt = round(rtt / 2, 2)
        websocket_latency = round(self.bot.latency * 1000, 2)
        estimated_ws_ltt = round(websocket_latency / 2, 2)

        embed = discord.Embed(
            title="LTT (One-Way Latency)",
            description=(
                f"**Estimated LTT (One-Way RTT)**: `{estimated_ltt}ms`\n"
                f"**Estimated WebSocket LTT**: `{estimated_ws_ltt}ms`\n"
            ),
            color=discord.Color(0xFFFFFF),
        )
        embed.set_footer(
            text="True one-way latency measurement requires time-synced systems, which this bot doesn’t have."
        )

        await message.edit(content=None, embed=embed)

    @command(
        name="shards",
        description="Shows information about the shards the bot is using.",
    )
    async def shards(self, ctx: Context):
        """Shows information about the shards the bot is using."""
        shard_count = self.bot.shard_count
        shard_info = []

        for shard_id in range(shard_count):
            guild_count = len(
                [guild for guild in self.bot.guilds if guild.shard_id == shard_id]
            )
            user_count = sum(
                guild.member_count
                for guild in self.bot.guilds
                if guild.shard_id == shard_id
            )
            shard_info.append((shard_id, guild_count, user_count))

        paginator = commands.Paginator(prefix="", suffix="", max_size=1000)
        for shard_id, guild_count, user_count in shard_info:
            paginator.add_line(
                f"Shard {shard_id}: {guild_count:>5} Guilds | {user_count:>5} Users"
            )

        for page in paginator.pages:
            await ctx.send(page)

    @hybrid(
        name="namehistory",
        aliases=["nickhistory", "nh", "ngh"],
        description="Shows the server nickname history of a user.",
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(users=True, guilds=True)
    @app_commands.describe(user="The user to show nickname history for.")
    async def namehistory(self, ctx: Context, user: Optional[discord.User] = None):
        """Shows the server nickname history of a user in an embed with pagination."""
        user = user or ctx.author

        nickname_history = await self.db.fetch(
            "SELECT nickname, changed_at FROM nickname_history WHERE user_id = $1 ORDER BY changed_at DESC",
            user.id,
        )

        if not nickname_history:
            embed = discord.Embed(
                description=f"No nickname history found for {user.mention}",
                color=0xFFFFFF,
            )
            await ctx.send(embed=embed)
            return

        view = NicknameHistoryView(user, nickname_history)
        message = await ctx.send(view=view)
        view.message = message

    @hybrid(
        name="avatarhistory",
        aliases=["avhistory", "ah", "avh"],
        description="View a user's avatar history.",
    )
    @app_commands.allowed_installs(guilds=True, users=False)
    @app_commands.allowed_contexts(guilds=True, dms=False, private_channels=False)
    @app_commands.describe(user="The user to view avatar history for.")
    async def avatarhistory(self, ctx: Context, user: Optional[discord.Member] = None):
        """View a user's avatar history from the database."""
        user = user or ctx.author

        records = await self.bot.db.fetch(
            """
            SELECT id, avatar_data, created_at 
            FROM avatar_history 
            WHERE user_id = $1 
            ORDER BY created_at DESC
            """,
            user.id,
        )

        if not records:
            return await ctx.send("No avatar history found for this user.")

        pages = []
        for record in records:
            pages.append(
                {
                    "data": record["avatar_data"],
                    "created_at": record["created_at"],
                    "id": record["id"],
                }
            )

        if not pages:
            return await ctx.send("No avatar history found for this user.")

        view = self.AvatarHistoryView(pages, user)

        await view.send_initial_message(ctx)

    class AvatarHistoryView(discord.ui.View):
        """View for paginating through avatar history."""

        def __init__(self, pages, user):
            super().__init__(timeout=180)
            self.pages = pages
            self.user = user
            self.current_page = 0
            self.message = None

            self.update_buttons()

        async def send_initial_message(self, ctx):
            """Send the initial message with the first page."""
            file, embed = self.create_page(0)
            self.message = await ctx.send(embed=embed, file=file, view=self)

        def create_page(self, page_num):
            """Create a file and embed for the given page number."""
            page = self.pages[page_num]

            file = discord.File(
                io.BytesIO(page["data"]), filename=f"avatar_{page['id']}.png"
            )

            embed = discord.Embed(
                title=f"Avatar history for {self.user}",
                color=Color(0xFFFFFF),
                timestamp=page["created_at"],
            )

            embed.set_image(url=f"attachment://avatar_{page['id']}.png")

            embed.set_footer(
                text=f"Changed on {page['created_at'].strftime('%Y-%m-%d %H:%M:%S')}"
            )

            return file, embed

        def update_buttons(self):
            """Update the state of pagination buttons."""
            self.clear_items()

            prev_button = discord.ui.Button(
                emoji=Emojis.left,
                style=discord.ButtonStyle.gray,
                disabled=self.current_page == 0,
            )

            page_button = discord.ui.Button(
                label=f"{self.current_page + 1}/{len(self.pages)}",
                style=discord.ButtonStyle.gray,
                disabled=True,
                custom_id="page_indicator",
            )

            next_button = discord.ui.Button(
                emoji=Emojis.right,
                style=discord.ButtonStyle.gray,
                disabled=self.current_page >= len(self.pages) - 1,
            )

            prev_button.callback = self.prev_callback
            next_button.callback = self.next_callback

            self.add_item(prev_button)
            self.add_item(page_button)
            self.add_item(next_button)

        async def update_message(self, interaction: discord.Interaction):
            """Update the message with the current page."""
            self.update_buttons()

            file, embed = self.create_page(self.current_page)

            await interaction.response.edit_message(
                embed=embed, attachments=[file], view=self
            )

        async def prev_callback(self, interaction: discord.Interaction):
            if self.current_page > 0:
                self.current_page -= 1
                await self.update_message(interaction)
            else:
                await interaction.response.defer()

        async def next_callback(self, interaction: discord.Interaction):
            if self.current_page < len(self.pages) - 1:
                self.current_page += 1
                await self.update_message(interaction)
            else:
                await interaction.response.defer()

        async def on_timeout(self):
            """Disable buttons when the view times out."""
            if hasattr(self, "message"):
                try:
                    self.clear_items()
                    await self.message.edit(view=self)
                except discord.NotFound:
                    pass

    @is_owner()
    @hybrid(
        name="clearnicknamehistory",
        aliases=["clearnickhistory", "cnh", "cngh"],
        description="Clears the nickname history of a user.",
    )
    @app_commands.describe(user="The user to clear nickname history for.")
    async def clearnicknamehistory(
        self, ctx: Context, user: Optional[discord.User] = None
    ):
        """Clears the nickname history of a user."""
        user = user or ctx.author
        history = await self.db.fetch(
            "SELECT * FROM nickname_history WHERE user_id = $1", user.id
        )
        if not history:
            await ctx.send(f"{user.mention} does not have any logged nickname history.")
            return
        await self.db.execute(
            "DELETE FROM nickname_history WHERE user_id = $1", user.id
        )
        await ctx.send(f"Nickname history for {user.mention} has been cleared.")

    @hybrid(
        name="clearavatarhistory",
        aliases=["clearavhistory", "cah", "cavh"],
        description="Clears the avatar history of a user.",
    )
    @app_commands.describe(user="The user to clear avatar history for.")
    @has_permissions(manage_guild=True)
    async def clearavatarhistory(
        self, ctx: Context, user: Optional[discord.Member] = None
    ):
        """Clears the avatar history of a user."""
        user = user or ctx.author
        history = await self.bot.db.fetch(
            "SELECT * FROM avatar_history WHERE user_id = $1", user.id
        )
        if not history:
            await ctx.send(f"{user.mention} does not have any logged avatar history.")
            return
        await self.bot.db.execute(
            "DELETE FROM avatar_history WHERE user_id = $1", user.id
        )
        await ctx.send(f"Avatar history for {user.mention} has been cleared.")

    def _load_name_filter_terms(self) -> set[str]:
        """Load banned/offensive substrings from src/data/filter.txt."""
        terms: set[str] = set()
        try:
            base_dir = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..")
            )
            path = os.path.join(base_dir, "data", "filter.txt")
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    w = line.strip()
                    if not w or w.startswith("#"):
                        continue
                    terms.add(w.casefold())
        except Exception as e:
            print(f"Failed to load name filter terms: {e}")
        return terms

    @Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.display_name != after.display_name:
            await self.create_nickname_history_table()
            try:
                new_name = (after.display_name or str(after)).strip()
                if not new_name:
                    return

                name_cf = new_name.casefold()
                if any(
                    term and term in name_cf
                    for term in getattr(self, "filter_terms", set())
                ):
                    return

                await self.db.execute(
                    """
                    INSERT INTO nickname_history (user_id, nickname) 
                    VALUES ($1, $2)
                    """,
                    after.id,
                    new_name,
                )
            except Exception as e:
                print(f"Error updating nickname history: {e}")

    @Cog.listener()
    async def on_user_update(self, before: discord.User, after: discord.User):
        """Log global profile name changes (username/global display name).
        This event fires for user-wide updates and complements on_member_update.
        """
        if (
            before.display_name == after.display_name
            and before.name == after.name
            and getattr(before, "global_name", None)
            == getattr(after, "global_name", None)
        ):
            return

        await self.create_nickname_history_table()
        try:
            new_name = (
                getattr(after, "display_name", None)
                or getattr(after, "global_name", None)
                or after.name
                or str(after)
            ).strip()
            if not new_name:
                return

            name_cf = new_name.casefold()
            if any(
                term and term in name_cf
                for term in getattr(self, "filter_terms", set())
            ):
                return

            await self.db.execute(
                """
                INSERT INTO nickname_history (user_id, nickname)
                VALUES ($1, $2)
                """,
                after.id,
                new_name,
            )
        except Exception as e:
            print(f"Error updating nickname history (user_update): {e}")

    @command(
        name="memberslist",
        aliases=["memberlist"],
        description="View the list of members in the server.",
    )
    async def members(self, ctx: Context):
        """Shows a list of all members in the server."""
        guild = ctx.guild
        members = guild.members
        members_sorted = [
            m for m in sorted(members, key=lambda m: m.joined_at, reverse=True)
        ]
        member_count = len(members_sorted)

        view = MemberPages(members_sorted, member_count, guild, ctx.author.id)
        await ctx.send(embed=await view.update_message(None), view=view)
        view.message = await ctx.channel.fetch_message(ctx.channel.last_message_id)

    @hybrid(name="ac", description="Air Conditioning")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def ac(self, ctx: Context):
        container = discord.ui.Container()
        container.add_item(discord.ui.TextDisplay(content="# Air Conditioning"))
        container.add_item(
            discord.ui.MediaGallery(
                discord.MediaGalleryItem(
                    media="https://media.playfairs.cc/assets/ac.png",
                ),
            ),
        )
        view = discord.ui.LayoutView()
        view.add_item(container)
        await ctx.send(view=view)

    @hybrid(name="heater", description="Heater")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def heater(self, ctx: Context):
        container = discord.ui.Container()
        container.add_item(discord.ui.TextDisplay(content="# Heater"))
        container.add_item(
            discord.ui.MediaGallery(
                discord.MediaGalleryItem(
                    media="https://media.playfairs.cc/assets/heater.png",
                ),
            ),
        )
        view = discord.ui.LayoutView()
        view.add_item(container)
        await ctx.send(view=view)

    @hybrid(name="uptime", description="Get the bot's uptime and system information.")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def uptime(self, ctx: Context):
        """Displays the bot's uptime and system information."""
        jishaku = self.bot.get_cog("Jishaku")
        if jishaku and hasattr(jishaku, "load_time"):
            load_time = jishaku.load_time

        boot_timestamp = int(psutil.boot_time())

        system_info = [
            f"### {self.bot.user.name} - Uptime Information",
            f"Running on `{platform.system()} {platform.release()}` with Python `{platform.python_version()}`",
            f"System Uptime: <t:{boot_timestamp}:R>",
        ]

        if psutil:
            try:
                proc = psutil.Process()
                with proc.oneshot():
                    try:
                        mem = proc.memory_full_info()
                        mem_info = [
                            "",
                            "**Memory Usage:**",
                            f"- Physical: {self._format_bytes(mem.rss)}",
                            f"- Virtual: {self._format_bytes(mem.vms)}",
                            f"- Unique: {self._format_bytes(mem.uss)}",
                        ]
                    except (psutil.AccessDenied, AttributeError):
                        pass

                    try:
                        proc_info = [
                            "",
                            "**Process Info:**",
                            f"- PID: {proc.pid}",
                            f"- Name: {proc.name()}",
                            f"- Threads: {proc.num_threads()}",
                            f"- CPU: {proc.cpu_percent()}%",
                        ]
                    except (psutil.AccessDenied, AttributeError):
                        pass
            except Exception as e:
                system_info.append(f"\n*Error getting process info: {str(e)}*")

        if psutil:
            try:
                system_stats = [
                    "",
                    "**System Stats:**",
                    f"- CPU Cores: {psutil.cpu_count(logical=True)} ({psutil.cpu_count(logical=False)} physical)",
                    f"- CPU Usage: {psutil.cpu_percent()}%",
                ]

                mem = psutil.virtual_memory()
                system_stats.extend(
                    [
                        f"- Total RAM: {self._format_bytes(mem.total)}",
                        f"- Used RAM: {self._format_bytes(mem.used)} ({mem.percent}%)",
                        f"- Available RAM: {self._format_bytes(mem.available)}",
                    ]
                )

                disk = psutil.disk_usage("/")
                system_stats.extend(
                    [
                        f"- Disk Usage: {self._format_bytes(disk.used)} / {self._format_bytes(disk.total)} ({disk.percent}%)"
                    ]
                )
                system_info.append(f"Bot Load Time: <t:{int(load_time.timestamp())}:R>")
            except Exception as e:
                system_info.append(f"\n*Error getting system stats: {str(e)}*")

        container = discord.ui.Container()
        container.add_item(
            discord.ui.Section(
                discord.ui.TextDisplay(content="\n".join(system_info)),
                accessory=discord.ui.Thumbnail(media=Media.vortex),
            )
        )
        container.add_item(
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small)
        )
        container.add_item(discord.ui.TextDisplay(content="\n".join(mem_info)))
        container.add_item(
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small)
        )
        container.add_item(discord.ui.TextDisplay(content="\n".join(proc_info)))
        container.add_item(
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small)
        )
        container.add_item(discord.ui.TextDisplay(content="\n".join(system_stats)))
        container.accent_colour = discord.Colour(0x000000)
        view = discord.ui.LayoutView()
        view.add_item(container)
        await ctx.send(view=view)

    @staticmethod
    def _format_bytes(bytes_val: int) -> str:
        """Format bytes to human-readable format."""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if bytes_val < 1024.0:
                return f"{bytes_val:.2f} {unit}"
            bytes_val /= 1024.0
        return f"{bytes_val:.2f} PB"

    @command(name="playfairs.cc", description="Get information about playfairs.cc.")
    async def playfairs_cc(self, ctx: Context):
        container = discord.ui.Container()
        container.add_item(
            discord.ui.TextDisplay(content="## Information about **playfairs.cc**")
        )
        container.add_item(
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small)
        )
        container.add_item(
            discord.ui.TextDisplay(
                content="root • [playfairs.cc](https://playfairs.cc)"
            )
        )
        container.add_item(
            discord.ui.TextDisplay(
                content="playlists • [playlists.playfairs.cc](https://playlists.playfairs.cc)"
            )
        )
        container.add_item(
            discord.ui.TextDisplay(
                content="bytelabs • [bytelabs.uk](https://bytelabs.uk) (Separate Domain)"
            )
        )

        view = discord.ui.LayoutView()
        view.add_item(container)
        await ctx.send(view=view)
