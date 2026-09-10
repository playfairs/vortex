import discord
import ast
from discord.ui import Button, View
from managers.classes import Emojis, Colors
from discord import Interaction
from discord.embeds import Embed
from discord.ext.commands import Context
from managers.default_avatar import DefaultAvatarManager


class BanListView(View):
    def __init__(self, bans, author):
        super().__init__(timeout=120)
        self.bans = bans
        self.author = author
        self.current_page = 0
        self.items_per_page = 10

    def get_embed(self):
        embed = discord.Embed(title="Ban List", color=Colors.main)
        start = self.current_page * self.items_per_page
        end = start + self.items_per_page
        bans_page = self.bans[start:end]

        ban_lines = [f"{ban.user} `(`{ban.user.id}`)`" for ban in bans_page]
        embed.description = (
            "\n".join(ban_lines) if ban_lines else "No banned users found."
        )

        total_bans = len(self.bans)
        embed.set_footer(
            text=f"Page: {self.current_page + 1}/{(total_bans - 1) // self.items_per_page + 1} | Showing {len(bans_page)}/{total_bans}"
        )
        return embed

    async def update_message(self, interaction):
        embed = self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(emoji=Emojis.left, style=discord.ButtonStyle.grey)
    async def left_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "Ngh~ >_< stop touching my buttons...", ephemeral=True
            )
            return
        if self.current_page > 0:
            self.current_page -= 1
            await self.update_message(interaction)

    @discord.ui.button(emoji=Emojis.cancel, style=discord.ButtonStyle.grey)
    async def close_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "Ngh~ >_< stop touching my buttons...", ephemeral=True
            )
            return
        await interaction.response.edit_message(
            content="Ban list closed.", embed=None, view=None
        )

    @discord.ui.button(emoji=Emojis.right, style=discord.ButtonStyle.grey)
    async def right_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "Ngh~ >_< stop touching my buttons...", ephemeral=True
            )
            return
        if (self.current_page + 1) * self.items_per_page < len(self.bans):
            self.current_page += 1
            await self.update_message(interaction)


class RolesView(View):
    def __init__(self, roles, author, custom_emojis, target_user=None):
        super().__init__(timeout=120)
        self.roles = roles
        self.author = author
        self.target_user = target_user
        self.current_page = 0
        self.items_per_page = 10
        self.custom_emojis = custom_emojis
        self.total_pages = max(
            1, (len(self.roles) + self.items_per_page - 1) // self.items_per_page
        )
        self.update_buttons()

    def update_buttons(self):
        self.left_button.disabled = self.current_page == 0
        self.right_button.disabled = self.current_page >= self.total_pages - 1
        self.page_button.label = f"Page {self.current_page + 1}/{self.total_pages}"

    def get_embed(self):
        if (
            self.target_user
            and len(self.roles) == 1
            and self.roles[0] == self.target_user.guild.default_role
        ):
            embed = discord.Embed(
                title=f"User Roles: {self.target_user.display_name}",
                description="This user doesn't have any roles.",
                color=Colors.main,
            )
            return embed

        if (
            len(self.roles) > 1
            and self.roles[-1].id == self.roles[-1].guild.id
            and self.target_user
        ):
            embed = discord.Embed(
                title=f"User Roles: {self.target_user.display_name}", color=Colors.main
            )
        else:
            embed = discord.Embed(title="Server Roles", color=Colors.main)

        start = self.current_page * self.items_per_page
        end = start + self.items_per_page
        roles_page = self.roles[start:end]

        role_lines = [
            f"{i+1}: <@&{role.id}> \u2022 `{role.id}`"
            for i, role in enumerate(roles_page)
        ]
        embed.description = "\n".join(role_lines) if role_lines else "No roles found."

        return embed

    async def update_message(self, interaction):
        embed = self.get_embed()
        self.update_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(emoji=Emojis.left, style=discord.ButtonStyle.gray)
    async def left_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "Ngh~ >_< stop touching my buttons...", ephemeral=True
            )
            return
        if self.current_page > 0:
            self.current_page -= 1
            await self.update_message(interaction)

    @discord.ui.button(style=discord.ButtonStyle.gray, disabled=True)
    async def page_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        pass

    @discord.ui.button(emoji=Emojis.right, style=discord.ButtonStyle.gray)
    async def right_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "Ngh~ >_< stop touching my buttons...", ephemeral=True
            )
            return
        if (self.current_page + 1) * self.items_per_page < len(self.roles):
            self.current_page += 1
            await self.update_message(interaction)


class PaginationView(discord.ui.View):
    def __init__(self, pages, author, role):
        super().__init__(timeout=120)
        self.pages = pages
        self.author = author  # This is the Context object
        self.role = role
        self.current_page = 0
        self.update_buttons()

    def update_buttons(self):
        self.prev_page.disabled = self.current_page == 0
        self.next_page.disabled = self.current_page >= len(self.pages) - 1
        self.page_button.label = f"Page {self.current_page + 1}/{len(self.pages)}"

    @discord.ui.button(emoji=Emojis.left, style=discord.ButtonStyle.gray, row=1)
    async def prev_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id != self.author.author.id:  # Access author from context
            return await interaction.response.send_message(
                "Ngh~ >_< stop touching my buttons...", ephemeral=True
            )

        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await self.update_message(interaction)

    @discord.ui.button(style=discord.ButtonStyle.gray, row=1, disabled=True)
    async def page_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        pass

    @discord.ui.button(emoji=Emojis.right, style=discord.ButtonStyle.gray, row=1)
    async def next_page(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id != self.author.author.id:
            return await interaction.response.send_message(
                "Ngh~ >_< stop touching my buttons...", ephemeral=True
            )

        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            self.update_buttons()
            await self.update_message(interaction)
        else:
            self.update_buttons()

    async def update_message(self, interaction: discord.Interaction):
        embed = self.create_embed(self.current_page)
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if hasattr(self, "message") and self.message:
            await self.message.edit(view=self)

    def create_embed(self, page):
        embed = discord.Embed(
            title=f"Inrole: {self.role.name} ({len(self.role.members)})",
            description="\n".join(
                [
                    f"- <@{member.id}> \u2022 `{member.id}`"
                    for member in self.pages[page]
                ]
            ),
            color=discord.Color(0xFFFFFF),
        )
        return embed


class ConfirmView(discord.ui.View):
    def __init__(self, ctx, original_channel):
        super().__init__()
        self.ctx = ctx
        self.original_channel = original_channel

    @discord.ui.button(label="", style=discord.ButtonStyle.grey, emoji=Emojis.check)
    async def confirm_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(
                "Ngh~ >_< stop touching my buttons...", ephemeral=True
            )
            return

        category = self.original_channel.category
        position = self.original_channel.position
        topic = self.original_channel.topic
        nsfw = self.original_channel.is_nsfw()
        overwrites = self.original_channel.overwrites

        await self.original_channel.delete()

        new_channel = await self.ctx.guild.create_text_channel(
            name=self.original_channel.name,
            category=category,
            position=position,
            topic=topic,
            nsfw=nsfw,
            overwrites=overwrites,
        )

        embed = discord.Embed(
            title="Channel Nuked",
            description=f"This channel was nuked by {self.ctx.author.mention}.",
            color=discord.Color(0xFFFFFF),
        )
        await new_channel.send(embed=embed)

    @discord.ui.button(label="", style=discord.ButtonStyle.grey, emoji=Emojis.cancel)
    async def cancel_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(
                "Ngh~ >_< stop touching my buttons...", ephemeral=True
            )
            return

        await interaction.response.send_message("Nuke cancelled.", ephemeral=False)
        if interaction.message:  # Check if message exists
            await interaction.message.delete()

    # @discord.ui.button(label="Archive", style=discord.ButtonStyle.grey)
    # async def archive_button(self, interaction: discord.Interaction, button: discord.ui.Button):
    #     if interaction.user != self.ctx.author:
    #         await interaction.response.send_message("Stop touching my buttons >_<", ephemeral=True)
    #         return

    #     category_name = "Archived"
    #     category = discord.utils.get(self.ctx.guild.categories, name=category_name)
    #     if not category:
    #         category = await self.ctx.guild.create_category(category_name, position=len(self.ctx.guild.categories))
    #         await category.set_permissions(self.ctx.guild.default_role, view_channel=False)

    #     await self.original_channel.edit(category=category, position=len(self.ctx.guild.channels))

    #     embed = discord.Embed(
    #         title="Channel Archived",
    #         description=f"This channel was archived by {self.ctx.author.mention}.",
    #         color=discord.Color(0xffffff)
    #     )
    #     await self.original_channel.send(embed=embed)
    #     await interaction.response.send_message("Channel archived.", ephemeral=False)


class SnipeView(discord.ui.View):
    def __init__(self, sniped_message, ctx, bot, stype):
        super().__init__(timeout=30)
        self.sniped_messages = sniped_message
        self.ctx = ctx
        self.bot = bot
        self.type = stype  # 0: deleted, 1: edited, 2: reaction
        self.total = len(sniped_message)
        self.current_page = 0
        self.message = None  # This will be set when the view is sent
        self.default_avatar_manager = DefaultAvatarManager(bot)
        # self.timeout_at = time.time() + self.timeout # timeout is handled by discord.py View

        self.update_buttons()

    @discord.ui.button(label="", style=discord.ButtonStyle.grey, emoji=Emojis.left)
    async def left_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                "Ngh~ >_< stop touching my buttons...", ephemeral=True
            )
            return

        if self.current_page > 0:
            self.current_page -= 1
        await self.update_message(interaction)

    @discord.ui.button(label="", style=discord.ButtonStyle.grey, emoji=Emojis.right)
    async def right_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                "Ngh~ >_< stop touching my buttons...", ephemeral=True
            )
            return

        if self.current_page < self.total - 1:
            self.current_page += 1
        await self.update_message(interaction)

    async def update_message(self, interaction: discord.Interaction):
        self.update_buttons()
        r = None
        match self.type:
            case 0:
                message_data = self.sniped_messages[self.current_page]
                user = await self.bot.fetch_user(message_data["user_id"])
                attachments_raw = message_data.get("attachments")
                attachments = []
                if attachments_raw:
                    try:
                        attachments = ast.literal_eval(attachments_raw)
                    except Exception:
                        attachments = [attachments_raw]
                if message_data.get("reply"):
                    try:
                        r = await self.ctx.fetch_message(message_data["reply"])
                    except discord.NotFound:
                        r = None
                embed = discord.Embed(
                    title=f"Message Deleted by @{user.name}",
                    description=message_data.get("message", "No message content"),
                    color=0xFFFFFF,
                )
                avatar = await self.default_avatar_manager.get_user_avatar_or_default(
                    user
                )
                embed.set_thumbnail(url=avatar)
                (
                    (
                        embed.add_field(
                            name="Attachments",
                            value="\n".join(attachments),
                            inline=False,
                        )
                    )
                    if attachments
                    else None
                )
                content = f"Replying to {r.jump_url}" if r else ""
                if interaction.response.is_done():
                    await interaction.edit_original_response(
                        content=content, embed=embed, view=self
                    )
                else:
                    await interaction.response.edit_message(
                        content=content, embed=embed, view=self
                    )

            case 1:
                message_data = self.sniped_messages[self.current_page]
                user = await self.bot.fetch_user(message_data["user_id"])
                embed = discord.Embed(
                    title=f"Message edited by {user.name}", color=0xFFFFFF
                )
                embed.add_field(
                    name="Before",
                    value=message_data.get("before") or "No message content",
                    inline=False,
                )
                embed.add_field(
                    name="After",
                    value=message_data.get("after") or "No message content",
                    inline=False,
                )
                avatar = await self.default_avatar_manager.get_user_avatar_or_default(
                    user
                )
                embed.set_thumbnail(url=avatar)
                if message_data.get("reply"):
                    try:
                        r = await self.ctx.fetch_message(message_data["reply"])
                    except discord.NotFound:
                        r = None
                content = f"Replying to {r.jump_url}" if r else ""
                if interaction.response.is_done():
                    await interaction.edit_original_response(
                        content=content, embed=embed, view=self
                    )
                else:
                    await interaction.response.edit_message(
                        content=content, embed=embed, view=self
                    )

            case 2:
                reaction_data = self.sniped_messages[self.current_page]
                user = await self.bot.fetch_user(reaction_data["user_id"])
                embed = discord.Embed(
                    description=f"**{user.name}** reacted with {reaction_data['reaction']}"
                )
                if reaction_data.get("message_id"):
                    try:
                        r = await self.ctx.fetch_message(reaction_data["message_id"])
                    except discord.NotFound:
                        r = None
                content = f"Reacted to {r.jump_url}" if r else ""
                if interaction.response.is_done():
                    await interaction.edit_original_response(
                        content=content, embed=embed, view=self
                    )
                else:
                    await interaction.response.edit_message(
                        content=content, embed=embed, view=self
                    )

    def update_buttons(self):
        if hasattr(self, "left_button") and hasattr(self, "right_button"):
            self.left_button.disabled = self.current_page == 0
            self.right_button.disabled = self.current_page >= self.total - 1

    async def on_timeout(self):
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=None)
            except discord.NotFound:
                pass


class NewUsersView(discord.ui.View):
    def __init__(self, ctx: Context):
        super().__init__(timeout=30)
        self.ctx = ctx
        self.per_page = 10
        self.current_page = 0
        self.total_pages = 0
        self.members = []

    def set_data(self, members):
        self.members = members
        self.total_pages = (len(members) + self.per_page - 1) // self.per_page
        self.update_buttons()

    def update_buttons(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button) and child.emoji == Emojis.left:
                child.disabled = self.current_page == 0
            elif isinstance(child, discord.ui.Button) and child.emoji == Emojis.right:
                child.disabled = self.current_page >= self.total_pages - 1

    @discord.ui.button(label="", style=discord.ButtonStyle.grey, emoji=Emojis.left)
    async def left_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(
                "Ngh~ >_< stop touching my buttons...", ephemeral=True
            )
            return

        if self.current_page > 0:
            self.current_page -= 1
            await self.update_message(interaction)

    @discord.ui.button(label="", style=discord.ButtonStyle.grey, emoji=Emojis.right)
    async def right_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(
                "Ngh~ >_< stop touching my buttons...", ephemeral=True
            )
            return

        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            await self.update_message(interaction)

    async def update_message(self, interaction: discord.Interaction):
        start = self.current_page * self.per_page
        end = start + self.per_page
        page_members = self.members[start:end]

        embed = discord.Embed(title="New users today")
        embed.set_author(
            name=str(self.ctx.author), icon_url=self.ctx.author.display_avatar.url
        )

        if not page_members:
            embed.description = "No members to display."
        else:
            members_list = []
            for i, member in enumerate(page_members, start=start + 1):
                members_list.append(
                    f"`{i}.` {member.mention} - {discord.utils.format_dt(member.joined_at, style='R')}"
                )
            embed.description = "\n".join(members_list)

        embed.set_footer(text=f"Page {self.current_page + 1}/{self.total_pages}")
        self.update_buttons()

        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        try:
            if hasattr(self, "message"):
                await self.message.edit(view=self)
        except discord.NotFound:
            pass
