import discord
import discord.utils

from discord.ui import View, Button
from managers.classes import Emojis


class PermissionPages(View):
    def __init__(self, pages, title, current_page=0):
        super().__init__()
        self.pages = pages
        self.title = title
        self.current_page = current_page
        self.message = None

        self.prev_button = Button(emoji=Emojis.left, style=discord.ButtonStyle.gray)
        self.prev_button.callback = self.prev_page
        self.add_item(self.prev_button)

        self.page_indicator = Button(
            label=f"Page 1/{len(pages)}",
            style=discord.ButtonStyle.gray,
            disabled=True,
            row=0,
        )
        self.add_item(self.page_indicator)

        self.next_button = Button(
            emoji=Emojis.right, style=discord.ButtonStyle.gray, row=0
        )
        self.next_button.callback = self.next_page
        self.add_item(self.next_button)

        self.update_buttons()

    def update_buttons(self):
        """Update button states and page indicator"""
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page >= len(self.pages) - 1
        self.page_indicator.label = f"Page {self.current_page + 1}/{len(self.pages)}"

    async def update_message(self, interaction: discord.Interaction):
        self.update_buttons()
        embed = discord.Embed(
            title=f"{self.title}",
            color=discord.Color(0xFFFFFF),
        )

        current_page = self.pages[self.current_page]
        for category, perms in current_page.items():
            if perms:
                category_perms = []
                for perm in perms:
                    if perms[perm]:
                        category_perms.append(
                            f"> [ {Emojis.check} ] {perm.replace('_', ' ').title()}"
                        )
                    else:
                        category_perms.append(
                            f"> [ {Emojis.cancel} ] {perm.replace('_', ' ').title()}"
                        )

                embed.add_field(
                    name=f"{category.replace('_', ' ').title()}",
                    value="\n".join(category_perms),
                    inline=False,
                )

        if interaction:
            await interaction.response.edit_message(embed=embed, view=self)
        return embed

    async def prev_page(self, interaction: discord.Interaction):
        if self.current_page > 0:
            self.current_page -= 1
            await self.update_message(interaction)

    async def next_page(self, interaction: discord.Interaction):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            await self.update_message(interaction)

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.message:
            await self.message.edit(view=self)


class MemberPages(View):
    def __init__(self, member_sorted, member_count, guild, user_id):
        super().__init__()

        self.member_sorted: list[discord.Member] = member_sorted
        self.member_count: int = member_count
        self.guild_name: str = guild.name

        self.current_page: int = 0
        self.message: discord.Message = None
        self.user_id: int = user_id

        self.PAGE_SIZE = 10
        self.PAGE_COUNT = (member_count + self.PAGE_SIZE - 1) // self.PAGE_SIZE

        self.update_buttons()

    def update_buttons(self):
        self.first_page.disabled = self.current_page == 0
        self.prev_page.disabled = self.current_page == 0
        self.next_page.disabled = self.current_page >= self.PAGE_COUNT - 1
        self.last_page.disabled = self.current_page >= self.PAGE_COUNT - 1
        self.page_button.label = f"Page {self.current_page + 1}/{self.PAGE_COUNT}"

    async def update_message(self, interaction: discord.Interaction = None):
        if interaction is not None and interaction.user.id != self.user_id:
            return await interaction.response.send_message(
                "You wittle femboy dwont hawve awcess two tweese bwuttons.",
                ephemeral=True,
            )

        self.update_buttons()
        embed = discord.Embed(
            title=f"Members in {self.guild_name} ({self.member_count})",
            description="",
            color=discord.Color(0xFFFFFF),
        )

        # Variables
        start_index = self.current_page * self.PAGE_SIZE
        end_index = start_index + self.PAGE_SIZE

        # Safety to not exceed the list length
        if end_index > len(self.member_sorted):
            end_index = len(self.member_sorted)

        # Add members to the embed
        for member in self.member_sorted[start_index:end_index]:
            join_timestamp = int(member.joined_at.timestamp())
            embed.description += f"{member.mention} • <t:{join_timestamp}:R>\n"

        try:
            if interaction is not None:
                if interaction.response.is_done():
                    await interaction.edit_original_response(embed=embed, view=self)
                else:
                    await interaction.response.edit_message(embed=embed, view=self)
            elif hasattr(self, "message") and self.message:
                await self.message.edit(embed=embed, view=self)
        except Exception as e:
            print(f"Error updating message: {e}")

        return embed

    @discord.ui.button(
        label="", style=discord.ButtonStyle.gray, emoji=Emojis.frontofpage, row=0
    )
    async def first_page(self, interaction: discord.Interaction, button: Button):
        if self.current_page > 0:
            self.current_page = 0
            await self.update_message(interaction)

    @discord.ui.button(
        label="", style=discord.ButtonStyle.gray, emoji=Emojis.left, row=0
    )
    async def prev_page(self, interaction: discord.Interaction, button: Button):
        if self.current_page > 0:
            self.current_page -= 1
            await self.update_message(interaction)

    @discord.ui.button(label="Page 1/1", style=discord.ButtonStyle.gray, row=0)
    async def page_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(
                "You wittle femboy dwont hawve awcess two tweese bwuttons.",
                ephemeral=True,
            )

        class PageSelectorModal(discord.ui.Modal, title="Select Page"):
            page_number: discord.ui.TextInput = discord.ui.TextInput(
                label="Page Number",
                placeholder="Enter a page number",
                required=True,
                min_length=1,
                max_length=6,
                default=self.current_page + 1,
            )

            async def on_submit(self, interaction: discord.Interaction):
                page = self.page_number.value
                if not page.isdigit():
                    return await interaction.response.send_message(
                        "Please enter a valid page **number**.", ephemeral=True
                    )

                page = int(page) - 1
                if page < 0 or page >= self.view.PAGE_COUNT:
                    return await interaction.response.send_message(
                        f"Page number must be between 1 and {self.view.PAGE_COUNT}.",
                        ephemeral=True,
                    )

                self.view.current_page = page
                await self.view.update_message(interaction)

        modal = PageSelectorModal()
        await interaction.response.send_modal(modal)
        modal.view = self

    @discord.ui.button(
        label="", style=discord.ButtonStyle.gray, emoji=Emojis.right, row=0
    )
    async def next_page(self, interaction: discord.Interaction, button: Button):
        if self.current_page < self.PAGE_COUNT - 1:
            self.current_page += 1
            await self.update_message(interaction)

    @discord.ui.button(
        label="", style=discord.ButtonStyle.gray, emoji=Emojis.endofpage, row=0
    )
    async def last_page(self, interaction: discord.Interaction, button: Button):
        if self.current_page < self.PAGE_COUNT - 1:
            self.current_page = self.PAGE_COUNT - 1
            await self.update_message(interaction)

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        await self.message.edit(view=self)
