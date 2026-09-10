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
        self.update_buttons()

    def get_embed(self):
        embed = discord.Embed(
            title=f"Servers ({len(self.servers)})", color=discord.Color(0xFFFFFF)
        )
        start = self.current_page * self.items_per_page
        end = start + self.items_per_page
        servers_page = self.servers[start:end]

        server_lines = [f"{guild.name} `({guild.id})`" for guild in servers_page]
        embed.description = "\n".join(server_lines)
        return embed

    def update_buttons(self):
        self.clear_items()

        total_pages = ((len(self.servers) - 1) // self.items_per_page) + 1

        left_disabled = self.current_page <= 0
        self.add_item(
            self.LeftButton(
                emoji=str(Emojis.left),
                style=discord.ButtonStyle.gray,
                disabled=left_disabled,
            )
        )

        self.add_item(
            self.PageButton(
                label=f"Page {self.current_page + 1}/{total_pages}", disabled=True
            )
        )

        right_disabled = (self.current_page + 1) * self.items_per_page >= len(
            self.servers
        )
        self.add_item(
            self.RightButton(
                emoji=str(Emojis.right),
                style=discord.ButtonStyle.gray,
                disabled=right_disabled,
            )
        )

    async def update_message(self, interaction):
        self.update_buttons()
        embed = self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    class LeftButton(Button):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

        async def callback(self, interaction: discord.Interaction):
            view = self.view
            if interaction.user.id != view.author.id:
                await interaction.response.send_message(
                    "You can't interact with this embed.", ephemeral=True
                )
                return
            if view.current_page > 0:
                view.current_page -= 1
                await view.update_message(interaction)

    class RightButton(Button):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

        async def callback(self, interaction: discord.Interaction):
            view = self.view
            if interaction.user.id != view.author.id:
                await interaction.response.send_message(
                    "You can't interact with this embed.", ephemeral=True
                )
                return
            if (view.current_page + 1) * view.items_per_page < len(view.servers):
                view.current_page += 1
                await view.update_message(interaction)

    class PageButton(Button):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

        async def callback(self, interaction: discord.Interaction):
            pass
