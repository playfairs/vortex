import discord
from managers.classes import Emojis
from discord.ui import View, Button, LayoutView
from discord import ui


class SearchLoreView(View):
    def __init__(self, ctx, matching_entries, user, query):
        super().__init__()
        self.ctx = ctx
        self.matching_entries = matching_entries
        self.user = user
        self.query = query
        self.current_page = 0
        self.update_buttons()

    def get_embed(self):
        entry_number, entry = self.matching_entries[self.current_page]

        embed = discord.Embed(
            title=f"{self.user.display_name}'s Lore - Search Results",
            description=f"Searching for '{self.query}'\nShowing result {self.current_page + 1} of {len(self.matching_entries)}",
            color=0xFFFFFF,
        )

        embed.add_field(
            name=f"Entry {entry_number}",
            value=entry.get("content", "No content"),
            inline=False,
        )

        return embed

    def update_buttons(self):
        self.previous.disabled = self.current_page == 0
        self.next.disabled = self.current_page == len(self.matching_entries) - 1

    @discord.ui.button(
        label="Previous", style=discord.ButtonStyle.gray, emoji=Emojis.left
    )
    async def previous(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(
                "You cannot use these buttons.", ephemeral=True
            )
            return

        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.gray, emoji=Emojis.right)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(
                "You cannot use these buttons.", ephemeral=True
            )
            return

        if self.current_page < len(self.matching_entries) - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_embed(), view=self)


class LoreLeaderboard(View):
    def __init__(self, lorecount, bot, ctx):
        super().__init__()
        self.current_page = 0
        self.lore_counts = lorecount
        self.update_buttons()
        self.bot = bot
        self.ctx = ctx

    def get_embed(self):
        embed = discord.Embed(title="Lore Leaderboard", color=0xFFFF)
        start_idx = self.current_page * 10
        end_idx = start_idx + 10
        entries = self.lore_counts[start_idx:end_idx]

        col1 = entries[:5]
        col2 = entries[5:10]

        def format_column(col_entries, offset):
            lines = []
            for i, entry in enumerate(col_entries, start=offset):
                try:
                    user_obj = self.bot.get_user(entry["user_id"])
                    user_display = (
                        user_obj.display_name
                        if user_obj
                        else f'User {entry["user_id"]}'
                    )
                    user_id = entry["user_id"]
                except Exception:
                    user_display = f'User {entry["user_id"]}'
                    user_id = entry["user_id"]
                lines.append(
                    f"**{i}.** <@{user_id}>\n> __{entry['lore_count']}__ Lore Entries"
                )
            return "\n".join(lines) if lines else "No entries beyond this point."

        embed.add_field(name="", value=format_column(col1, start_idx + 1), inline=True)
        embed.add_field(name="", value=format_column(col2, start_idx + 6), inline=True)

        total_pages = max(1, (len(self.lore_counts) + 9) // 10)
        embed.set_footer(text=f"Page {self.current_page + 1}/{total_pages}")
        return embed

    @discord.ui.button(
        label="", style=discord.ButtonStyle.gray, emoji=Emojis.left, row=0
    )
    async def previous_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(
                "You cannot use these buttons.", ephemeral=True
            )
            return
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(
        label="", style=discord.ButtonStyle.gray, emoji=Emojis.right, row=0
    )
    async def next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(
                "You cannot use these buttons.", ephemeral=True
            )
            return
        total_pages = max(1, (len(self.lore_counts) + 9) // 10)
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_embed(), view=self)

    def update_buttons(self):
        if hasattr(self, "previous_button") and hasattr(self, "next_button"):
            total_pages = max(1, (len(self.lore_counts) + 9) // 10)
            self.previous_button.disabled = self.current_page == 0
            self.next_button.disabled = self.current_page >= total_pages - 1


class LoreView(View):
    def __init__(self, lorebook, user, ctx):
        super().__init__()
        self.lorebook = lorebook
        self.user = user
        self.ctx = ctx
        self.current_page = 0
        self.update_buttons()

    def get_embed(self):
        if not self.lorebook:
            return discord.Embed(description="No lore entries found.")

        entry = self.lorebook[self.current_page]
        embed = discord.Embed(
            title=f"{self.user.display_name}'s Lore",
            description=entry.get("content", "No content"),
            color=0xFFFFFF,
        )

        embed.set_footer(text=f"Entry {self.current_page + 1}/{len(self.lorebook)}")
        return embed

    @discord.ui.button(label="", style=discord.ButtonStyle.gray, emoji=Emojis.left)
    async def previous_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(
                "You cannot use these buttons.", ephemeral=True
            )
            return
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="", style=discord.ButtonStyle.gray, emoji=Emojis.right)
    async def next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(
                "You cannot use these buttons.", ephemeral=True
            )
            return
        if self.current_page < len(self.lorebook) - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.get_embed(), view=self)

    def update_buttons(self):
        if hasattr(self, "previous_button") and hasattr(self, "next_button"):
            total_pages = max(1, len(self.lorebook))
            self.previous_button.disabled = self.current_page == 0
            self.next_button.disabled = self.current_page >= total_pages - 1
            self.next_button.disabled = self.current_page >= len(self.lorebook) - 1


class SearchModal(discord.ui.Modal, title="Search Lore"):
    def __init__(self, view):
        super().__init__()
        self.view = view

        self.query = discord.ui.TextInput(
            label="Search Query",
            placeholder="Enter search terms...",
            min_length=1,
            max_length=100,
            required=True,
        )
        self.add_item(self.query)

    async def on_submit(self, interaction: discord.Interaction):
        query = self.query.value.lower()
        self.view.search_query = query
        self.view.current_page = 0
        self.view.filtered_entries = [
            entry
            for entry in self.view.lorebook
            if query in entry.get("content", "").lower()
        ]

        if not self.view.filtered_entries:
            await interaction.response.send_message(
                f"No lore entries found matching '{self.query.value}'", ephemeral=True
            )
            return

        self.view.update_content()
        await interaction.response.edit_message(view=self.view)


class PageJumpModal(discord.ui.Modal, title="Jump to Page"):
    def __init__(self, total_pages):
        super().__init__()
        self.total_pages = total_pages

        self.page_number = discord.ui.TextInput(
            label=f"Enter page number (1-{total_pages})",
            placeholder=f"1-{total_pages}",
            min_length=1,
            max_length=len(str(total_pages)) + 1,
            required=True,
        )
        self.add_item(self.page_number)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            page = int(self.page_number.value)
            if 1 <= page <= self.total_pages:
                interaction.client.page_to_jump = page - 1
                await interaction.response.defer()
            else:
                await interaction.response.send_message(
                    f"Please enter a number between 1 and {self.total_pages}.",
                    ephemeral=True,
                )
        except ValueError:
            await interaction.response.send_message(
                "Please enter a valid number.", ephemeral=True
            )


class LoreLayoutView(LayoutView):
    def __init__(self, lorebook, user, ctx):
        super().__init__(timeout=None)
        self.lorebook = lorebook
        self.user = user
        self.ctx = ctx
        self.current_page = 0
        self.search_query = None
        self.filtered_entries = None
        self.prev_button = None
        self.next_button = None
        self.original_message = None
        self.update_content()

    def get_current_entries(self):
        """Get the current set of entries (filtered if searching)."""
        if self.search_query and hasattr(self, "filtered_entries"):
            return self.filtered_entries
        return self.lorebook

    def get_current_entry(self):
        """Get the current entry based on page and search state."""
        entries = self.get_current_entries()
        if not entries or self.current_page >= len(entries):
            return None
        return entries[self.current_page]

    def update_content(self):
        """Update the message content and button states."""
        entries = self.get_current_entries()
        entry = self.get_current_entry()
        total_pages = len(entries) if entries else 1

        if not entry:
            content = "No matching entries found."
        else:
            content = entry.get("content", "No content")

        container = discord.ui.Container()

        header = f"## {self.user.display_name}'s Lore"
        if self.search_query:
            header += f"\n*Showing results for: {self.search_query}*"

        container.add_item(discord.ui.TextDisplay(content=f"{header}"))
        container.add_item(
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small)
        )
        container.add_item(discord.ui.TextDisplay(content=f"> {content}"))
        container.add_item(
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small)
        )

        button_row = discord.ui.ActionRow()

        self.prev_button = discord.ui.Button(
            style=discord.ButtonStyle.gray,
            emoji=Emojis.left,
            custom_id=f"lore_prev_{self.ctx.message.id}",
            disabled=self.current_page == 0,
        )
        self.prev_button.callback = self.prev_callback

        self.page_button = discord.ui.Button(
            style=discord.ButtonStyle.blurple,
            label=f"Page {self.current_page + 1}/{total_pages}",
            custom_id=f"lore_page_{self.ctx.message.id}",
            disabled=not entries or total_pages <= 1,
        )
        self.page_button.callback = self.page_jump_callback

        self.next_button = discord.ui.Button(
            style=discord.ButtonStyle.gray,
            emoji=Emojis.right,
            custom_id=f"lore_next_{self.ctx.message.id}",
            disabled=not entries or self.current_page >= total_pages - 1,
        )
        self.next_button.callback = self.next_callback

        button_row.add_item(self.prev_button)
        button_row.add_item(self.page_button)
        button_row.add_item(self.next_button)

        self.search_button = discord.ui.Button(
            style=discord.ButtonStyle.gray,
            emoji=Emojis.search,
            custom_id=f"lore_search_{self.ctx.message.id}",
            disabled=not self.lorebook,
        )
        self.search_button.callback = self.search_callback
        button_row.add_item(self.search_button)

        if self.search_query:
            clear_button = discord.ui.Button(
                style=discord.ButtonStyle.red,
                emoji=Emojis.cancel,
                custom_id=f"lore_clear_{self.ctx.message.id}",
                label="Clear Search",
            )
            clear_button.callback = self.clear_search_callback
            button_row.add_item(clear_button)

        self.delete_button = discord.ui.Button(
            style=discord.ButtonStyle.gray,
            emoji=Emojis.delete,
            custom_id=f"lore_delete_{self.ctx.message.id}",
            disabled=not entry,
        )
        self.delete_button.callback = self.delete_callback
        button_row.add_item(self.delete_button)

        container.add_item(button_row)
        self.clear_items()
        self.add_item(container)

    async def delete_callback(self, interaction: discord.Interaction):
        """Handle delete button click."""
        entry = self.get_current_entry()
        if not entry:
            await interaction.response.send_message(
                "No entry found to delete.", ephemeral=True
            )
            return

        message_to_edit = interaction.message

        self.delete_button.disabled = True
        await interaction.response.edit_message(view=self)

        entry_content = None
        if hasattr(entry, "content"):
            entry_content = entry.content
        elif isinstance(entry, dict) and "content" in entry:
            entry_content = entry["content"]
        elif hasattr(entry, "get"):
            entry_content = entry.get("content")
        else:
            entry_content = str(entry)

        entry_id = None
        entry_owner_id = None
        try:
            async with self.ctx.bot.db.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id, user_id FROM lore 
                    WHERE (user_id = $1 OR user_id = $2) AND content = $3 
                    ORDER BY id DESC LIMIT 1
                    """,
                    interaction.user.id,
                    self.user.id,
                    entry_content,
                )

                if not row and len(entry_content) > 20:
                    row = await conn.fetchrow(
                        """
                        SELECT id, user_id FROM lore 
                        WHERE (user_id = $1 OR user_id = $2) AND content LIKE $3 || '%'
                        ORDER BY id DESC LIMIT 1
                        """,
                        interaction.user.id,
                        self.user.id,
                        entry_content[:20],
                    )

                if row:
                    entry_id = row["id"]
                    entry_owner_id = row["user_id"]
                else:
                    row = await conn.fetchrow(
                        """
                        SELECT id, user_id FROM lore 
                        WHERE (user_id = $1 OR user_id = $2) AND content LIKE '%' || $3 || '%'
                        ORDER BY id DESC LIMIT 1
                        """,
                        interaction.user.id,
                        self.user.id,
                        entry_content[:50],
                    )
                    if row:
                        entry_id = row["id"]
                        entry_owner_id = row["user_id"]

        except Exception as e:
            print(f"Error fetching entry ID: {e}")

        if not entry_id:
            print(f"Could not determine entry ID. Entry content: {entry_content}")
            self.delete_button.disabled = False
            await message_to_edit.edit(view=self)
            await interaction.followup.send(
                "You don't have permission to delete this lore entry or it doesn't exist.",
                ephemeral=True,
            )
            return

        if (
            interaction.user.id != entry_owner_id
            and interaction.user.id != self.user.id
        ):
            self.delete_button.disabled = False
            await message_to_edit.edit(view=self)
            await interaction.followup.send(
                "Only the lore entry owner or the user associated with this lore can delete entries.",
                ephemeral=True,
            )
            return

        owner = self.ctx.bot.get_user(1426711359059394662)
        if not owner:
            await interaction.followup.send(
                "Could not contact bot owner. Please try again later.", ephemeral=True
            )
            return

        container = discord.ui.Container()

        original_content = f"**User:** {interaction.user.mention} (`{interaction.user.id}`)\n**Entry ID:** `{entry_id}`\n**Content:** {entry_content[:100]}{'...' if len(entry_content) > 100 else ''}"

        container.add_item(discord.ui.TextDisplay(content=f"### Lore Delete Request:"))
        container.add_item(
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small)
        )
        container.add_item(
            discord.ui.TextDisplay(
                content=f"{original_content}\n\n**Approve or deny this deletion request:**"
            )
        )

        async def approve_callback(button_interaction: discord.Interaction):
            if button_interaction.user.id != owner.id:
                await button_interaction.response.send_message(
                    "Only the bot owner can approve this request.", ephemeral=True
                )
                return

            try:
                entry_owner = await self.ctx.bot.fetch_user(entry_owner_id)

                async with self.ctx.bot.db.acquire() as conn:
                    await conn.execute("DELETE FROM lore WHERE id = $1", entry_id)

                dm_container = discord.ui.Container()
                dm_container.add_item(
                    discord.ui.TextDisplay(
                        content=f"### Lore Deletion Request Approved"
                    )
                )
                dm_container.add_item(
                    discord.ui.Separator(
                        visible=True, spacing=discord.SeparatorSpacing.small
                    )
                )
                dm_container.add_item(
                    discord.ui.TextDisplay(
                        content=(
                            f"Your lore entry deletion request has been approved by {button_interaction.user.mention}.\n\n"
                            f"**Entry ID:** {entry_id}\n"
                            f"**Content:** {entry_content[:1900]}"
                        )
                    )
                )
                dm_view = discord.ui.LayoutView()
                dm_view.add_item(dm_container)
                await entry_owner.send(view=dm_view)

                container.clear_items()
                container.add_item(
                    discord.ui.TextDisplay(
                        content=f"### Lore Delete Request: (Approved)"
                    )
                )
                container.add_item(
                    discord.ui.Separator(
                        visible=True, spacing=discord.SeparatorSpacing.small
                    )
                )
                container.add_item(discord.ui.TextDisplay(content=original_content))

                for item in view.children:
                    if hasattr(item, "disabled"):
                        item.disabled = True

                await button_interaction.response.edit_message(view=view)

            except Exception as e:
                await button_interaction.response.send_message(
                    f"An error occurred while deleting the lore entry: {str(e)}",
                    ephemeral=True,
                )

        async def deny_callback(button_interaction: discord.Interaction):
            if button_interaction.user.id != owner.id:
                await button_interaction.response.send_message(
                    "Only the bot owner can deny this request.", ephemeral=True
                )
                return

            try:
                entry_owner = await self.ctx.bot.fetch_user(entry_owner_id)

                dm_container = discord.ui.Container()
                dm_container.add_item(
                    discord.ui.TextDisplay(content=f"### Lore Deletion Request Denied")
                )
                dm_container.add_item(
                    discord.ui.Separator(
                        visible=True, spacing=discord.SeparatorSpacing.small
                    )
                )
                dm_container.add_item(
                    discord.ui.TextDisplay(
                        content=(
                            f"Your lore entry deletion request has been denied by {button_interaction.user.mention}.\n\n"
                            f"**Entry ID:** {entry_id}\n"
                            f"**Content:** {entry_content[:1900]}"
                        )
                    )
                )
                dm_view = discord.ui.LayoutView()
                dm_view.add_item(dm_container)
                await entry_owner.send(view=dm_view)

                container.clear_items()
                container.add_item(
                    discord.ui.TextDisplay(content=f"### Lore Delete Request: (Denied)")
                )
                container.add_item(
                    discord.ui.Separator(
                        visible=True, spacing=discord.SeparatorSpacing.small
                    )
                )
                container.add_item(discord.ui.TextDisplay(content=original_content))

                for item in view.children:
                    if hasattr(item, "disabled"):
                        item.disabled = True

                await button_interaction.response.edit_message(view=view)

            except Exception as e:
                await button_interaction.response.send_message(
                    f"An error occurred while processing the request: {str(e)}",
                    ephemeral=True,
                )

        container.add_item(
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small)
        )

        approve_button = ui.Button(
            label="Approve",
            style=discord.ButtonStyle.gray,
            custom_id=f"approve_{entry_id}",
        )
        approve_button.callback = approve_callback

        deny_button = ui.Button(
            label="Deny", style=discord.ButtonStyle.gray, custom_id=f"deny_{entry_id}"
        )
        deny_button.callback = deny_callback

        action_row = discord.ui.ActionRow(approve_button, deny_button)
        container.add_item(action_row)
        container.accent_colour = discord.Colour(0xFFFFFF)
        view = discord.ui.LayoutView()
        view.add_item(container)

        try:
            await owner.send(view=view)

            await interaction.followup.send(
                "Your request to delete this lore entry has been sent for approval.",
                ephemeral=True,
            )

        except Exception as e:
            print(f"Error sending approval request: {e}")
            self.delete_button.disabled = False
            await message_to_edit.edit(view=self)
            await interaction.followup.send(
                "An error occurred while sending the deletion request. Please try again.",
                ephemeral=True,
            )

    async def search_callback(self, interaction: discord.Interaction):
        """Handle search button click by showing a search modal."""
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(
                "You can't use these buttons.", ephemeral=True
            )

        modal = SearchModal(self)
        await interaction.response.send_modal(modal)

        try:
            await interaction.client.wait_for("interaction", timeout=60.0)
            if hasattr(interaction.client, "page_to_jump"):
                self.current_page = interaction.client.page_to_jump
                delattr(interaction.client, "page_to_jump")
                self.update_content()
                await interaction.followup.edit_message(
                    message_id=interaction.message.id, view=self
                )
        except asyncio.TimeoutError:
            pass

    async def clear_search_callback(self, interaction: discord.Interaction):
        """Handle clear search button click."""
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(
                "You can't use these buttons.", ephemeral=True
            )

        self.search_query = None
        self.filtered_entries = None
        self.current_page = 0
        self.update_content()
        await interaction.response.edit_message(view=self)

    async def prev_callback(self, interaction: discord.Interaction):
        """Handle previous button click."""
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(
                "You can't use these buttons.", ephemeral=True
            )

        if self.current_page > 0:
            self.current_page -= 1
            self.update_content()
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.defer()

    async def next_callback(self, interaction: discord.Interaction):
        """Handle next button click."""
        entries = self.get_current_entries()
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(
                "You can't use these buttons.", ephemeral=True
            )

        if entries and self.current_page < len(entries) - 1:
            self.current_page += 1
            self.update_content()
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.defer()

    async def page_jump_callback(self, interaction: discord.Interaction):
        """Handle page jump button click."""
        if interaction.user.id != self.ctx.author.id:
            return await interaction.response.send_message(
                "You can't use these buttons.", ephemeral=True
            )

        entries = self.get_current_entries()
        if not entries:
            return await interaction.response.send_message(
                "No entries available to navigate.", ephemeral=True
            )

        modal = PageJumpModal(len(entries))
        await interaction.response.send_modal(modal)

        try:
            await interaction.client.wait_for("interaction", timeout=60.0)
            if hasattr(interaction.client, "page_to_jump"):
                self.current_page = interaction.client.page_to_jump
                delattr(interaction.client, "page_to_jump")
                self.update_content()
                await interaction.followup.edit_message(
                    message_id=interaction.message.id, view=self
                )
        except asyncio.TimeoutError:
            pass


class LoreLeaderboardView(ui.LayoutView):
    def __init__(self, ctx, lorecount, bot):
        super().__init__()
        self.ctx = ctx
        self.lore_count = lorecount
        self.bot = bot
        self.current_page = 0
        self.users_per_page = 10
        self.total_pages = max(
            1, (len(self.lore_count) + self.users_per_page - 1) // self.users_per_page
        )

        self.create_view()

    def create_view(self):
        self.clear_items()

        start_idx = self.current_page * self.users_per_page
        end_idx = start_idx + self.users_per_page
        entries = self.lore_count[start_idx:end_idx]

        leaderboard_lines = []
        for i, entry in enumerate(entries, start=1):
            user_id = entry["user_id"]
            count = entry["lore_count"]
            pos = (self.current_page * self.users_per_page) + i
            leaderboard_lines.append(f"**#{pos}** <@{user_id}> - {count} entries")

        container = discord.ui.Container()
        container.add_item(discord.ui.TextDisplay(content=f"### Lore Leaderboard"))
        container.add_item(
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small)
        )
        container.add_item(
            discord.ui.TextDisplay(
                content=(
                    "\n".join(leaderboard_lines)
                    if leaderboard_lines
                    else "No entries yet!"
                )
            )
        )
        container.add_item(
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small)
        )

        action_row = discord.ui.ActionRow()

        prev_button = discord.ui.Button(
            style=discord.ButtonStyle.gray,
            emoji=Emojis.left,
            custom_id=f"lore_prev_{self.ctx.message.id}",
            disabled=self.current_page == 0,
        )
        prev_button.callback = self.on_prev_page
        action_row.add_item(prev_button)

        jump_button = discord.ui.Button(
            style=discord.ButtonStyle.gray,
            label=f"Page {self.current_page + 1}/{self.total_pages}",
            custom_id=f"lore_jump_{self.ctx.message.id}",
        )
        jump_button.callback = self.on_jump_page
        action_row.add_item(jump_button)

        next_button = discord.ui.Button(
            style=discord.ButtonStyle.gray,
            emoji=Emojis.right,
            custom_id=f"lore_next_{self.ctx.message.id}",
            disabled=len(self.lore_count)
            <= (self.current_page + 1) * self.users_per_page,
        )
        next_button.callback = self.on_next_page
        action_row.add_item(next_button)

        container.add_item(action_row)

        self.add_item(container)

    async def on_prev_page(self, interaction: discord.Interaction):
        if self.current_page > 0:
            self.current_page -= 1
            self.create_view()
            await interaction.response.edit_message(view=self)

    async def on_next_page(self, interaction: discord.Interaction):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.create_view()
            await interaction.response.edit_message(view=self)

    async def on_jump_page(self, interaction: discord.Interaction):
        """Handle jump to page button click."""
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message(
                "You can't use these buttons.", ephemeral=True
            )

        modal = PageJumpModal(self.total_pages)
        await interaction.response.send_modal(modal)

        try:
            await interaction.client.wait_for("interaction", timeout=60.0)
            if hasattr(interaction.client, "page_to_jump"):
                self.current_page = interaction.client.page_to_jump
                delattr(interaction.client, "page_to_jump")
                self.create_view()
                await interaction.followup.edit_message(
                    message_id=interaction.message.id, view=self
                )
        except asyncio.TimeoutError:
            pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.ctx.author
