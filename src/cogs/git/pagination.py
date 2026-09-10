import discord
from discord.ext import commands
from typing import List, Optional
from discord.ui import View, Button

from vortex import vortex
from managers.classes import Emojis


class PaginatorView(View):
    def __init__(self, pages: List[str], title: str, timeout: float = 60.0):
        super().__init__(timeout=timeout)
        self.pages = pages
        self.title = title
        self.current_page = 0
        self.message: Optional[discord.Message] = None

        self.first_page = Button(
            emoji="⏮", style=discord.ButtonStyle.gray, disabled=True
        )
        self.prev_page = Button(
            emoji="◀", style=discord.ButtonStyle.gray, disabled=True
        )
        self.page_counter = Button(
            label="Page 1/1", style=discord.ButtonStyle.gray, disabled=True
        )
        self.next_page = Button(
            emoji="▶", style=discord.ButtonStyle.gray, disabled=len(pages) <= 1
        )
        self.last_page = Button(
            emoji="⏭", style=discord.ButtonStyle.gray, disabled=len(pages) <= 1
        )
        self.stop_button = Button(emoji=Emojis.cancel, style=discord.ButtonStyle.danger)

        self.first_page.callback = self.first_page_callback
        self.prev_page.callback = self.prev_page_callback
        self.next_page.callback = self.next_page_callback
        self.last_page.callback = self.last_page_callback
        self.stop_button.callback = self.stop_button_callback

        self.add_item(self.first_page)
        self.add_item(self.prev_page)
        self.add_item(self.page_counter)
        self.add_item(self.next_page)
        self.add_item(self.last_page)
        self.add_item(self.stop_button)

    def _update_buttons(self):
        """Update button states based on current page."""
        self.first_page.disabled = self.current_page == 0
        self.prev_page.disabled = self.current_page == 0
        self.next_page.disabled = self.current_page == len(self.pages) - 1
        self.last_page.disabled = self.current_page == len(self.pages) - 1
        self.page_counter.label = f"Page {self.current_page + 1}/{len(self.pages)}"

    def get_embed(self) -> discord.Embed:
        """Create an embed with the current page content."""
        embed = discord.Embed(
            title=self.title,
            description=f"```\n{self.pages[self.current_page]}\n```",
            color=discord.Color(0xFFFFFF),
        )
        embed.set_footer(text=f"Page {self.current_page + 1}/{len(self.pages)}")
        return embed

    async def first_page_callback(self, interaction: discord.Interaction):
        self.current_page = 0
        self._update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    async def prev_page_callback(self, interaction: discord.Interaction):
        self.current_page = max(0, self.current_page - 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    async def next_page_callback(self, interaction: discord.Interaction):
        self.current_page = min(len(self.pages) - 1, self.current_page + 1)
        self._update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    async def last_page_callback(self, interaction: discord.Interaction):
        self.current_page = len(self.pages) - 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    async def stop_button_callback(self, interaction: discord.Interaction):
        """Stop the pagination and remove all buttons."""
        await interaction.response.defer()
        if self.message:
            try:
                await self.message.delete()
            except discord.NotFound:
                pass
        self.stop()

    async def on_timeout(self):
        """Disable all buttons when the view times out."""
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass


def paginate_text(text: str, max_length: int = 1900) -> List[str]:
    """Split text into chunks that fit within Discord's message length limit."""
    if len(text) <= max_length:
        return [text]

    chunks = []
    current_chunk = []
    current_length = 0

    # Split by lines to avoid breaking in the middle of a line
    lines = text.split("\n")

    for line in lines:
        # If adding this line would exceed the limit, start a new chunk
        if current_length + len(line) + 1 > max_length and current_chunk:
            chunks.append("\n".join(current_chunk))
            current_chunk = []
            current_length = 0

        current_chunk.append(line)
        current_length += len(line) + 1  # +1 for the newline

    # Add the last chunk if not empty
    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks
