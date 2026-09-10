ERROR_WEBHOOK_URL = "https://discord.com/api/webhooks/1377575192670507050/KN7-C_YYudrBd_lCPoIAtOIS9KEGe5s_KeJ3CnrgVh6NeQVgu2PuDC5nelppO_PxgI5i"

import discord
import aiohttp
import random
from managers.classes import Emojis


class ErrorView(discord.ui.View):
    def __init__(self, db, id, ctx):
        super().__init__()
        self.db = db
        self.id = id
        self.ctx = ctx

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            ls = [
                "This ain't Build-A-Paginator.",
                "Hands off, gremlin.",
                "Bro this ain't even your function.",
                "You touching things you don't understand.",
                "Paginator said no 💅",
                "Go play in traffic (safely).",
                "You again? Sigh.",
                "404: Respect not found.",
                "Mind yo business.",
                "No thoughts, just vibes. And this ain't your vibe.",
                "You're not that guy, pal.",
                "Back away slowly.",
                "Unqualified and bold. I respect it, but stop.",
                "You edit this and the bot cries.",
                "Go outside. Touch grass. Leave this alone.",
                "Only I get to mess with this. You're not built like that.",
                "This was written in a state of rage. Don't ask questions.",
                "Bro this was duct taped together. Don't breathe near it.",
                "One wrong move and we all crash. Walk away.",
                "TS aint even yo paginator.",
                "You PMO sm rn.",
            ]

            await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"> ❌ {interaction.user.mention}: {random.choice(ls)}",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return False
        return True

    async def disable_all(self):
        for item in self.children:
            item.disabled = True
        self.stop()

    @discord.ui.button(
        label="Fixed", style=discord.ButtonStyle.green, emoji=Emojis.check
    )
    async def fixed_error(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        async with self.db.acquire() as conn:
            await conn.execute("DELETE FROM errors WHERE id = $1", self.id)

        await self.disable_all()
        await interaction.response.edit_message(
            embed=discord.Embed(
                description="✅   Error has been marked as resolved and removed from the datbase."
            ),
            view=self,
        )

    @discord.ui.button(label="Dismiss", style=discord.ButtonStyle.gray, emoji="🔇")
    async def ignore_error(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        async with self.db.acquire() as conn:
            await conn.execute("DELETE FROM errors WHERE id = $1", self.id)

        await self.disable_all()
        await interaction.response.edit_message(
            embed=discord.Embed(
                description="🔇   Error has been ignored and removed from the database."
            ),
            view=self,
        )

    @discord.ui.button(
        label="Report", style=discord.ButtonStyle.red, emoji=Emojis.error
    )
    async def report_error(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        async with self.db.acquire() as conn:
            res = await conn.fetchrow("SELECT * FROM errors WHERE id = $1", self.id)

        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url(ERROR_WEBHOOK_URL, session=session)
            embed = discord.Embed(
                title="Error Report",
                description=f"Command: {res['command']}\nError: {res['error']}\nType: {res['type']}",
                color=discord.Color.red(),
            )
            embed.set_footer(text=f"Error ID: {res['id']}")
            await webhook.send(embed=embed)

        await self.disable_all()
        await interaction.response.edit_message(
            embed=discord.Embed(
                description="❌   Error has been reported to current TODO errors."
            ),
            view=self,
        )
