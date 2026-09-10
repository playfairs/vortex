from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Union
from discord.ext import commands
from discord.ext.commands import command, Cog
from discord import ui
import discord
import enum
from managers.classes import Media, Servers, Links, Emojis
from config import DISCORD
from managers.default_avatar import DefaultAvatarManager


class ImageButtons(discord.ui.ActionRow):

    def __init__(self, media: discord.Asset):
        super().__init__()
        self.add_item(
            discord.ui.Button(
                style=discord.ButtonStyle.link,
                label="PNG",
                url=media.with_format("png").url,
            )
        )
        self.add_item(
            discord.ui.Button(
                style=discord.ButtonStyle.link,
                label="JPG",
                url=media.with_format("jpg").url,
            )
        )
        self.add_item(
            discord.ui.Button(
                style=discord.ButtonStyle.link,
                label="WEBP",
                url=media.with_format("webp").url,
            )
        )
        if media.is_animated():
            self.add_item(
                discord.ui.Button(
                    style=discord.ButtonStyle.link,
                    label="GIF",
                    url=media.with_format("gif").url,
                )
            )


class AvContainer(discord.ui.LayoutView):
    def __init__(self, user: discord.User):
        super().__init__(timeout=None)

        avatar = user.display_avatar

        avatar_url = avatar.replace(
            format="webp",
            size=1024,
        ).url

        if avatar.is_animated():
            avatar_url += "&animated=true"

        container = discord.ui.Container()
        container.add_item(
            discord.ui.TextDisplay(
                content=f"### {user.name}'s Avatar"
            )
        )
        container.add_item(
            discord.ui.MediaGallery(
                discord.MediaGalleryItem(
                    media=avatar_url,
                ),
            ),
        )
        container.add_item(
            discord.ui.Separator(
                visible=True,
                spacing=discord.SeparatorSpacing.large,
            ),
        )

        container.accent_colour = discord.Colour(0xFFFFFF)
        container.add_item(ImageButtons(user.display_avatar))

        self.add_item(container)


class ServerAvatarView(discord.ui.LayoutView):
    def __init__(self, user: discord.User):
        super().__init__(timeout=None)

        container = discord.ui.Container()
        container.add_item(
            discord.ui.TextDisplay(content=f"### {user.name}'s Server Avatar")
        )
        container.add_item(
            discord.ui.MediaGallery(
                discord.MediaGalleryItem(
                    media=user.guild_avatar.url,
                ),
            ),
        )
        container.add_item(
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large),
        )
        container.accent_colour = discord.Colour(0xFFFFFF)
        container.add_item(ImageButtons(user.guild_avatar))
        self.add_item(container)


class BannerView(discord.ui.LayoutView):
    def __init__(self, user: discord.User):
        super().__init__(timeout=None)

        container = discord.ui.Container()
        container.add_item(discord.ui.TextDisplay(content=f"### {user.name}'s Banner"))
        container.add_item(
            discord.ui.MediaGallery(
                discord.MediaGalleryItem(
                    media=user.banner.url,
                ),
            ),
        )
        container.add_item(
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large),
        )
        container.accent_colour = discord.Colour(0xFFFFFF)
        container.add_item(ImageButtons(user.banner))
        self.add_item(container)


class ServerBannerView(discord.ui.LayoutView):
    def __init__(self, member: discord.Member):
        super().__init__(timeout=None)

        container = discord.ui.Container()
        container.add_item(
            discord.ui.TextDisplay(content=f"### {member.name}'s Server Banner")
        )
        container.add_item(
            discord.ui.MediaGallery(
                discord.MediaGalleryItem(
                    media=member.guild_banner.url,
                ),
            ),
        )
        container.add_item(
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.large),
        )
        container.accent_colour = discord.Colour(0xFFFFFF)
        container.add_item(ImageButtons(member.guild_banner))
        self.add_item(container)


class WhoisView(discord.ui.LayoutView):
    async def create_section(self):
        badges = []
        if hasattr(self.user, "public_flags") and self.user.public_flags:
            if self.user.public_flags.staff:
                badges.append(Emojis.staff)
            if self.user.public_flags.partner:
                badges.append(Emojis.partner)
            if self.user.public_flags.discord_certified_moderator:
                badges.append(Emojis.moderator_programs_alumni)
            if self.user.public_flags.hypesquad:
                badges.append(Emojis.hypesquad)
            if self.user.public_flags.hypesquad_bravery:
                badges.append(Emojis.bravery)
            if self.user.public_flags.hypesquad_brilliance:
                badges.append(Emojis.brilliance)
            if self.user.public_flags.hypesquad_balance:
                badges.append(Emojis.balance)
            if self.user.public_flags.bug_hunter:
                badges.append(Emojis.bug_hunter)
            if self.user.public_flags.bug_hunter_level_2:
                badges.append(Emojis.bug_hunter_level_2)
            if self.user.public_flags.active_developer:
                badges.append(Emojis.developer)
            if self.user.public_flags.verified_bot_developer:
                badges.append(Emojis.verified_developer)
            if self.user.public_flags.early_supporter:
                badges.append(Emojis.early_supporter)
            if (
                hasattr(self, "bot")
                and self.bot
                and hasattr(self.bot, "owner_ids")
                and self.user.id in self.bot.owner_ids
            ):
                badges.append(Emojis.developer3)
            if hasattr(self.user, "id") and self.user.id == DISCORD.HERESY_ID:
                badges.append(Emojis.heresy)
            if hasattr(self.user, "id") and self.user.id == DISCORD.BOT_ID:
                badges.append(Emojis.vortex)
            if hasattr(self.user, "bot") and self.user.bot:
                badges.append(Emojis.bot)
            if (
                hasattr(discord.ApplicationFlags, "auto_mod_badge")
                and discord.ApplicationFlags.auto_mod_badge in self.user.public_flags
            ):
                badges.append(Emojis.automod)

        mutual_servers = 0
        if hasattr(self.user, "mutual_guilds"):
            mutual_servers = len(
                [
                    guild
                    for guild in self.user.mutual_guilds
                    if hasattr(guild, "me") and guild.me
                ]
            )

        container = discord.ui.Container()

        section_items = [
            discord.ui.TextDisplay(
                content=f"### {self.user.name} ({self.user.display_name})\n**User ID:** {self.user.id}"
            )
        ]

        if mutual_servers > 0:
            section_items.append(
                discord.ui.TextDisplay(content=f"**Mutual Servers:** {mutual_servers}")
            )

        if badges:
            section_items.append(
                discord.ui.TextDisplay(content=f"**Badges:** {' '.join(badges)}")
            )

        avatar_url = (
            self.user.avatar.url
            if self.user.avatar
            else await self.default_avatar_manager.get_default_avatar(self.user.id)
        )

        section = discord.ui.Section(
            *section_items, accessory=discord.ui.Thumbnail(media=avatar_url)
        )
        container.add_item(section)
        container.add_item(
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small)
        )
        container.add_item(
            discord.ui.TextDisplay(
                content=f"**Created At:** <t:{int(self.user.created_at.timestamp())}:f>"
            )
        )
        container.add_item(
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small)
        )
        container.accent_colour = discord.Colour(0xFFFFFF)
        return container

    @classmethod
    async def create(cls, member: discord.User, ctx: discord.Context = None, bot=None):
        """Create a new instance of WhoisView with async initialization."""
        self = cls()
        self.ctx = ctx
        self.bot = bot or (ctx.bot if ctx else None)
        self.user = member or (ctx.user if ctx else None)
        self.default_avatar_manager = DefaultAvatarManager(self.bot)

        container = await self.create_section()

        action_row = discord.ui.ActionRow()
        is_guild_context = hasattr(self.ctx, "guild") and self.ctx.guild is not None
        member = None
        if is_guild_context and hasattr(self.ctx, "guild"):
            member = self.ctx.guild.get_member(self.user.id)

        has_server_avatar = (
            member
            and hasattr(member, "guild_avatar")
            and member.guild_avatar is not None
        )
        has_server_banner = (
            member
            and hasattr(member, "guild_banner")
            and member.guild_banner is not None
        )
        has_banner = (
            hasattr(self.user, "banner")
            and self.user.banner
            and hasattr(self.user.banner, "url")
            and self.user.banner.url
        )
        has_avatar = (
            hasattr(self.user, "avatar")
            and self.user.avatar
            and hasattr(self.user.avatar, "url")
            and self.user.avatar.url
        )

        action_row.add_item(
            discord.ui.Button(
                style=discord.ButtonStyle.link,
                label="Avatar",
                url=self.user.avatar.url if has_avatar else "https://discord.com",
                disabled=not has_avatar,
            )
        )
        action_row.add_item(
            discord.ui.Button(
                style=discord.ButtonStyle.link,
                label="Banner",
                url=(
                    self.user.banner.with_format("png").url
                    if has_banner
                    else "https://discord.com"
                ),
                disabled=not has_banner,
            )
        )
        action_row.add_item(
            discord.ui.Button(
                style=discord.ButtonStyle.link,
                label="Server Avatar",
                url=(
                    member.guild_avatar.url
                    if has_server_avatar
                    else "https://discord.com"
                ),
                disabled=not has_server_avatar,
            )
        )
        action_row.add_item(
            discord.ui.Button(
                style=discord.ButtonStyle.link,
                label="Server Banner",
                url=(
                    member.guild_banner.url
                    if has_server_banner
                    else "https://discord.com"
                ),
                disabled=not has_server_banner,
            )
        )
        if len(action_row.children) > 0:
            container.add_item(action_row)

        self.add_item(container)
        return self

    def __init__(self):
        super().__init__(timeout=None)


class UserInfoView(discord.ui.LayoutView):
    def __init__(self, member, ctx, bot):
        super().__init__(timeout=None)
        self.member = member
        self.ctx = ctx
        self.bot = bot
        self.user = member or (ctx.user if ctx else None)
        self.default_avatar_manager = DefaultAvatarManager(bot)
        self.developer_id = [1426711359059394662]
        self.jishaku_access = []

    @classmethod
    async def create(cls, member, ctx, bot):
        """Create a new instance of UserInfoView with async initialization."""
        self = cls(member, ctx, bot)

        try:
            if hasattr(member, "_user"):
                self.user = member._user
            else:
                self.user = member

            fetched_user = await bot.fetch_user(member.id)
            if (
                fetched_user
                and hasattr(fetched_user, "banner")
                and fetched_user.banner is not None
            ):
                self.user = fetched_user

            if not hasattr(self.user, "banner") or self.user.banner is None:
                if hasattr(member, "banner") and member.banner is not None:
                    self.user = member
        except Exception as e:
            print(f"Error fetching user banner: {e}")
            self.user = member

        await self.create_section()
        return self

    async def create_section(self):
        badges = []
        if self.member.public_flags.staff:
            badges.append(Emojis.staff)
        if self.member.public_flags.partner:
            badges.append(Emojis.partner)
        if self.member.public_flags.discord_certified_moderator:
            badges.append(Emojis.moderator_programs_alumni)
        if self.member.public_flags.hypesquad:
            badges.append(Emojis.hypesquad)
        if self.member.public_flags.hypesquad_bravery:
            badges.append(Emojis.bravery)
        if self.member.public_flags.hypesquad_brilliance:
            badges.append(Emojis.brilliance)
        if self.member.public_flags.hypesquad_balance:
            badges.append(Emojis.balance)
        if self.member.public_flags.bug_hunter:
            badges.append(Emojis.bug_hunter)
        if self.member.public_flags.bug_hunter_level_2:
            badges.append(Emojis.bug_hunter_level_2)
        if self.member.public_flags.active_developer:
            badges.append(Emojis.developer)
        if self.member.public_flags.verified_bot_developer:
            badges.append(Emojis.verified_developer)
        if self.member.public_flags.early_supporter:
            badges.append(Emojis.early_supporter)
        if self.member.premium_since:
            badges.append(Emojis.booster)
        if self.member == self.member.guild.owner:
            badges.append(Emojis.owner)
        if self.member.id in self.developer_id:
            badges.append(Emojis.developer3)
        if self.member.id == DISCORD.HERESY_ID:
            badges.append(Emojis.heresy)
        if self.member.id == DISCORD.BOT_ID:
            badges.append(Emojis.vortex)
        if self.member.bot:
            badges.append(Emojis.bot)
        if discord.ApplicationFlags.auto_mod_badge in self.member.public_flags:
            badges.append(Emojis.automod)

        titles = []
        if self.member.id == 1426711359059394662:
            titles.append("Lead Developer")
        if (
            self.member.id in self.bot.owner_ids
            and not self.member.id == 1426711359059394662
            and not self.member.id == 570020287735660547
        ):
            titles.append("Developer")
        if self.member.id in self.jishaku_access:
            titles.append("Privileged User")
        if self.member.id == 570020287735660547:
            titles.append("Cutie :3")
        if self.member.id == 1006623778085806161:
            titles.append("Bot Breaker")
        if self.member.id == 708096305477451846:
            titles.append("Cute Bot >_<")
        if self.member.id == 338441186241019916:
            titles.append("Member Purger")
        if self.member.id == 1119218378259845183:
            titles.append("The German Patriot")
        if self.member.id == 1267974559206735903:
            titles.append("The King Of All Strawberries")
        if self.member.id == 969914831194964028:
            titles.append("¡ǝɹǝɥʇ oʅʅǝH")
        if self.member.id == 1265662059056463976:
            titles.append("Jishaku Fein")
        if self.member.id == 757355424621133914:
            titles.append("Jay Roxxx")
        if self.member.id == 1395961548375068678:
            titles.append("Jailbreak Tester")

        roles = sorted(
            [role for role in self.member.roles[1:]],
            key=lambda x: x.position,
            reverse=True,
        )
        top_roles = roles[:5]
        roles_string = (
            " ".join(role.mention for role in top_roles) if top_roles else "No roles"
        )
        if len(roles) > 5:
            roles_string += f" (+{len(roles) - 5} more)"

        mutual_servers = 0
        if hasattr(self.member, "mutual_guilds"):
            mutual_servers = len(
                [
                    guild
                    for guild in self.member.mutual_guilds
                    if hasattr(guild, "me") and guild.me
                ]
            )

            created_days_ago = (
                datetime.now(timezone.utc) - self.member.created_at
            ).days
            joined_days_ago = (datetime.now(timezone.utc) - self.member.joined_at).days
            member_join_position = (
                sorted(self.member.guild.members, key=lambda m: m.joined_at).index(
                    self.member
                )
                + 1
            )

            created_ago = (
                f"{created_days_ago // 365} year{'s' if (created_days_ago // 365) > 1 else ''} ago"
                if created_days_ago >= 365
                else f"{created_days_ago} day{'s' if created_days_ago > 1 else ''} ago"
            )
            joined_ago = (
                f"{joined_days_ago // 365} year{'s' if (joined_days_ago // 365) > 1 else ''} ago"
                if joined_days_ago >= 365
                else f"{joined_days_ago} day{'s' if joined_days_ago > 1 else ''} ago"
            )

            if self.member.guild_avatar:
                avatar_url = self.member.guild_avatar.url
            elif self.member.avatar:
                avatar_url = self.member.avatar.url
            else:
                avatar_url = (
                    await self.default_avatar_manager.get_user_avatar_or_default(
                        self.member
                    )
                )

            if self.member.guild_banner:
                banner_url = self.member.guild_banner.url
            elif self.member.banner:
                banner_url = self.member.banner.with_format("png").url
            else:
                banner_url = None

        container = discord.ui.Container()

        container.add_item(
            discord.ui.Section(
                discord.ui.TextDisplay(
                    content=f"### {self.member.display_name}{' - ' + ' '.join(titles) if titles else ''}"
                ),
                discord.ui.TextDisplay(content=f"**Badges**\n{' '.join(badges)}"),
                accessory=discord.ui.Thumbnail(media=avatar_url),
            )
        )
        container.add_item(
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small)
        )
        container.add_item(
            discord.ui.TextDisplay(
                content=f"**Created:**\n<t:{int(self.member.created_at.timestamp())}:f>"
            )
        )
        container.add_item(
            discord.ui.TextDisplay(
                content=f"**Joined:**\n<t:{int(self.member.joined_at.timestamp())}:f>\nJoin Position: {member_join_position}"
            )
        )
        container.add_item(
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small)
        )
        container.add_item(
            discord.ui.TextDisplay(content=f"**Roles:**\n{roles_string}")
        )
        container.add_item(
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small)
        )
        container.add_item(
            discord.ui.TextDisplay(
                content=f"-# **User ID:** {self.member.id} • Mutual Servers: {mutual_servers} • Today at <t:{int(datetime.now(timezone.utc).timestamp())}:f>"
            )
        )
        container.add_item(
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small)
        )
        action_row = discord.ui.ActionRow()
        is_guild_context = hasattr(self.ctx, "guild") and self.ctx.guild is not None
        member = None
        if is_guild_context and hasattr(self.ctx, "guild"):
            member = self.ctx.guild.get_member(self.user.id)

        has_server_avatar = (
            member
            and hasattr(member, "guild_avatar")
            and member.guild_avatar is not None
        )
        has_server_banner = (
            member
            and hasattr(member, "guild_banner")
            and member.guild_banner is not None
        )
        has_banner = hasattr(self.user, "banner") and self.user.banner is not None
        has_avatar = (
            hasattr(self.user, "avatar")
            and self.user.avatar
            and hasattr(self.user.avatar, "url")
            and self.user.avatar.url
        )

        action_row.add_item(
            discord.ui.Button(
                style=discord.ButtonStyle.link,
                label="Avatar",
                url=self.user.avatar.url if has_avatar else "https://discord.com",
                disabled=not has_avatar,
            )
        )
        action_row.add_item(
            discord.ui.Button(
                style=discord.ButtonStyle.link,
                label="Banner",
                url=(
                    self.user.banner.with_format("png").url
                    if has_banner
                    else "https://discord.com"
                ),
                disabled=not has_banner,
            )
        )
        action_row.add_item(
            discord.ui.Button(
                style=discord.ButtonStyle.link,
                label="Server Avatar",
                url=(
                    member.guild_avatar.url
                    if has_server_avatar
                    else "https://discord.com"
                ),
                disabled=not has_server_avatar,
            )
        )
        action_row.add_item(
            discord.ui.Button(
                style=discord.ButtonStyle.link,
                label="Server Banner",
                url=(
                    member.guild_banner.url
                    if has_server_banner
                    else "https://discord.com"
                ),
                disabled=not has_server_banner,
            )
        )
        container.accent_colour = discord.Colour(0xFFFFFF)
        if len(action_row.children) > 0:
            container.add_item(action_row)
        self.add_item(container)


class NicknameHistoryView(discord.ui.LayoutView):
    def __init__(self, user: discord.User, nickname_history: list):
        super().__init__(timeout=180)
        self.user = user
        self.nickname_history = nickname_history or []
        self.chunk_size = 10
        self.nickname_chunks = [
            self.nickname_history[i : i + self.chunk_size]
            for i in range(0, len(self.nickname_history), self.chunk_size)
        ] or [[]]
        self.current_page = 0
        self.message: Optional[discord.Message] = None

        self._build_page()

    def _build_page(self):
        self.clear_items()

        total_pages = max(1, len(self.nickname_chunks))
        page_index = self.current_page + 1
        chunk = self.nickname_chunks[self.current_page] if self.nickname_chunks else []

        container = discord.ui.Container()
        container.add_item(
            discord.ui.TextDisplay(content=f"### {self.user.name}'s Name History")
        )
        container.add_item(
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
        )
        container.accent_colour = discord.Colour(0xFFFFFF)

        lines = []
        for idx, nick in enumerate(chunk, 1 + (self.current_page * self.chunk_size)):
            changed_at = nick["changed_at"]
            if getattr(changed_at, "tzinfo", None) is None:
                changed_at = changed_at.replace(tzinfo=timezone.utc)
            ts = int(changed_at.timestamp())
            raw_name = str(nick.get("nickname", ""))
            safe_name = discord.utils.escape_mentions(
                discord.utils.escape_markdown(raw_name)
            )
            lines.append(f"{idx}. **{safe_name}** <t:{ts}:D>")

        container.add_item(
            discord.ui.TextDisplay(content="\n".join(lines) if lines else "No entries.")
        )
        container.add_item(
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
        )
        container.add_item(
            discord.ui.TextDisplay(
                content=f"{len(self.nickname_history)} total nicknames."
            )
        )
        container.add_item(
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
        )
        action_row = discord.ui.ActionRow()
        start_btn = discord.ui.Button(
            style=discord.ButtonStyle.gray,
            emoji=Emojis.frontofpage,
            custom_id="nh_start",
            disabled=self.current_page == 0,
        )
        prev_btn = discord.ui.Button(
            style=discord.ButtonStyle.gray,
            emoji=Emojis.left,
            custom_id="nh_prev",
            disabled=self.current_page == 0,
        )
        page_lbl = discord.ui.Button(
            style=discord.ButtonStyle.gray,
            label=f"Page {page_index}/{total_pages}",
            disabled=True,
            custom_id="nh_page_label",
        )
        next_btn = discord.ui.Button(
            style=discord.ButtonStyle.gray,
            emoji=Emojis.right,
            custom_id="nh_next",
            disabled=self.current_page >= total_pages - 1,
        )
        end_btn = discord.ui.Button(
            style=discord.ButtonStyle.gray,
            emoji=Emojis.endofpage,
            custom_id="nh_end",
            disabled=self.current_page >= total_pages - 1,
        )
        action_row.add_item(start_btn)
        action_row.add_item(prev_btn)
        action_row.add_item(page_lbl)
        action_row.add_item(next_btn)
        action_row.add_item(end_btn)

        async def on_prev(interaction: discord.Interaction):
            if self.current_page > 0:
                self.current_page -= 1
                self._build_page()
                await interaction.response.edit_message(view=self)

        async def on_next(interaction: discord.Interaction):
            if self.current_page < len(self.nickname_chunks) - 1:
                self.current_page += 1
                self._build_page()
                await interaction.response.edit_message(view=self)

        async def on_start(interaction: discord.Interaction):
            if self.current_page != 0:
                self.current_page = 0
                self._build_page()
                await interaction.response.edit_message(view=self)

        async def on_end(interaction: discord.Interaction):
            last_index = max(0, len(self.nickname_chunks) - 1)
            if self.current_page != last_index:
                self.current_page = last_index
                self._build_page()
                await interaction.response.edit_message(view=self)

        prev_btn.callback = on_prev
        next_btn.callback = on_next
        start_btn.callback = on_start
        end_btn.callback = on_end
        container.add_item(action_row)
        self.add_item(container)

    async def on_timeout(self) -> None:
        try:
            for container in self.children:
                if hasattr(container, "children"):
                    for item in container.children:
                        if isinstance(item, discord.ui.ActionRow):
                            for btn in item.children:
                                if isinstance(
                                    btn, discord.ui.Button
                                ) and btn.custom_id in {
                                    "nh_prev",
                                    "nh_next",
                                    "nh_start",
                                    "nh_end",
                                }:
                                    btn.disabled = True
            if self.message:
                await self.message.edit(view=self)
        except Exception:
            pass
