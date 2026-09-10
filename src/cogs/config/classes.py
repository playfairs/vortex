import discord
from discord.ui import View, Button
from managers.classes import Emojis


class ServersView(View):
    def __init__(self, servers, author, custom_emojis):
        super().__init__(timeout=60)
        self.servers = servers
        self.author = author
        self.current_page = 0
        self.items_per_page = 10
        self.custom_emojis = custom_emojis

    def get_embed(self):
        embed = discord.Embed(title="Server List", color=discord.Color(0xFFFFFF))
        start = self.current_page * self.items_per_page
        end = start + self.items_per_page
        servers_page = self.servers[start:end]

        server_lines = [f"{guild.name} `({guild.id})`" for guild in servers_page]
        embed.description = "\n".join(server_lines)

        embed.set_footer(
            text=f"Page {self.current_page + 1}/{(len(self.servers) - 1) // self.items_per_page + 1}"
        )
        return embed

    async def update_message(self, interaction):
        embed = self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(emoji=f"{Emojis.left}", style=discord.ButtonStyle.gray)
    async def left_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "You can't interact with this embed.", ephemeral=True
            )
            return
        if self.current_page > 0:
            self.current_page -= 1
            await self.update_message(interaction)

    @discord.ui.button(emoji=f"{Emojis.cancel}", style=discord.ButtonStyle.gray)
    async def close_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "You can't interact with this embed, womp womp", ephemeral=True
            )
            return
        await interaction.response.edit_message(
            content="Embed closed.", embed=None, view=None
        )

    @discord.ui.button(emoji=f"{Emojis.right}", style=discord.ButtonStyle.gray)
    async def right_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "You can't interact with this embed, womp womp", ephemeral=True
            )
            return
        if (self.current_page + 1) * self.items_per_page < len(self.servers):
            self.current_page += 1
            await self.update_message(interaction)
