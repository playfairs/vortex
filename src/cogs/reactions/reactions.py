import discord
from discord.ext import commands
from discord.ext.commands import (
    Cog,
    command,
    group,
    cooldown,
    BucketType,
)

from vortex import vortex
import random
import aiohttp
import os


class Reactions(Cog, description="View commands in Reactions."):
    def __init__(self, bot: vortex):
        self.bot = bot
        self.db = self.bot.db
        self.gif_api_key = os.getenv("GIPHY_API_KEY")
        self.session = aiohttp.ClientSession()

    async def cog_unload(self):
        await self.session.close()

    async def get_gif(self, query: str) -> str:
        """Fetch a random GIF from GIPHY based on the query"""
        if not self.gif_api_key:
            return None

        url = f"https://api.giphy.com/v1/gifs/random"
        params = {"api_key": self.gif_api_key, "tag": query, "rating": "pg-13"}

        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return (
                        data.get("data", {})
                        .get("images", {})
                        .get("original", {})
                        .get("url")
                    )
        except Exception as e:
            print(f"Error fetching GIF: {e}")
        return None

    async def cog_load(self):
        await self.create_tables()

    async def create_tables(self):
        await self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS skull_targets (
                user_id BIGINT PRIMARY KEY
            );
        """
        )
        await self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS auto_react_targets (
                user_id BIGINT,
                emoji TEXT,
                PRIMARY KEY (user_id, emoji)
            );
        """
        )
        await self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS custom_reactions (
                trigger TEXT PRIMARY KEY,
                reaction TEXT
            );
        """
        )

    @Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.content.lower() == "sob":
            await message.add_reaction("😭")

    @command(name="boop", description="Boops a user >_<")
    async def boop(self, ctx, user: discord.Member):
        """Boop someone with cuteness!"""
        if ctx.author.id != 7867491071323480074 and user.id == 570020287735660547:
            await ctx.send("No.")
            return
        if user.id == ctx.author.id:
            await ctx.send("Why are you trying to boop yourself?")
            return
        messages = [
            f"*gently boops {user.mention} on the nose* :3",
            f"Boop! {user.mention} has been officially booped! :point_right::point_left:",
            f"A wild boop for {user.mention}! :heart_eyes:",
            f"{ctx.author.mention} delivers a gentle boop to {user.mention}! :3",
            f"Boop! {user.mention} has been booped into next week! :zany_face:",
        ]
        gif_url = (
            await self.get_gif("anime boop nose cute")
            or "https://media.giphy.com/media/3o7TKtD0PA4GcWQJg4/giphy.gif"
        )

        embed = discord.Embed(description=random.choice(messages), color=0xFFFFFF)
        embed.set_image(url=gif_url)
        await ctx.send(embed=embed)

    @command(name="pat", description="Pats a user >_<")
    async def pat(self, ctx, user: discord.Member):
        """Give someone a nice headpat!"""
        if ctx.author.id != 7867491071323480074 and user.id == 570020287735660547:
            await ctx.send("Back up, he's not yours.")
            return
        if user.id == ctx.author.id:
            await ctx.send("What the hell")
            return
        messages = [
            f"*gives {user.mention} a gentle headpat* :3",
            f"{user.mention} has received a warm pat from {ctx.author.mention}! :heart:",
            f"Pat pat pat! {user.mention} looks so happy! :blush:",
            f"{ctx.author.mention} showers {user.mention} with headpats! :sparkling_heart:",
            f"The pats have been deployed to {user.mention}'s head! :wink:",
        ]
        gif_url = (
            await self.get_gif("anime headpat kawaii")
            or "https://media.giphy.com/media/5tmRHwTlHAA9WkVxTU/giphy.gif"
        )

        embed = discord.Embed(description=random.choice(messages), color=0xFFFFFF)
        embed.set_image(url=gif_url)
        await ctx.send(embed=embed)

    @command(name="hug", description="Hugs a user >_<")
    async def hug(self, ctx, user: discord.Member):
        """Give someone a warm hug!"""
        if ctx.author.id != 7867491071323480074 and user.id == 570020287735660547:
            await ctx.send("No.")
            return
        if user.id == ctx.author.id:
            await ctx.send("Awh do you need a hug? Here you go")
            return
        messages = [
            f"*gives {user.mention} a big warm hug* :hugging:",
            f"{ctx.author.mention} wraps their arms around {user.mention} in a cozy hug! :heart:",
            f"Hug attack! {user.mention} has been hugged by {ctx.author.mention}! :hugging:",
            f"A warm, fuzzy hug for {user.mention} from {ctx.author.mention}! :sparkling_heart:",
            f"Hugs make everything better! {user.mention} gets a hug from {ctx.author.mention}! :hugging:",
        ]
        gif_url = (
            await self.get_gif("anime hug tight warm")
            or "https://media.giphy.com/media/wnsgren9NtITS/giphy.gif"
        )

        embed = discord.Embed(description=random.choice(messages), color=0xFFFFFF)
        embed.set_image(url=gif_url)
        await ctx.send(embed=embed)

    @command(name="kiss", description="Kisses a user >_<")
    async def kiss(self, ctx, user: discord.Member):
        """Send a sweet kiss to someone special!"""
        if ctx.author.id != 7867491071323480074 and user.id == 570020287735660547:
            await ctx.send("Back up, he's not yours.")
            return
        if user.id == ctx.author.id:
            await ctx.send("Are you lonely?")
            return
        messages = [
            f"*gives {user.mention} a gentle kiss* :kissing_heart:",
            f"Mwah! {ctx.author.mention} plants a sweet kiss on {user.mention}'s cheek! :kissing_heart:",
            f"{user.mention} has been kissed by {ctx.author.mention}! How romantic! :heart_eyes:",
            f"A soft kiss from {ctx.author.mention} to {user.mention}! :sparkling_heart:",
            f"Smooch! {user.mention} has been kissed by {ctx.author.mention}! :kissing_closed_eyes:",
        ]
        gif_url = (
            await self.get_gif("anime kiss cheek romantic")
            or "https://media.giphy.com/media/bGm9FuBCGg4SY/giphy.gif"
        )

        embed = discord.Embed(description=random.choice(messages), color=0xFFFFFF)
        embed.set_image(url=gif_url)
        await ctx.send(embed=embed)

    @command(name="slap", description="Slaps a user >_<")
    async def slap(self, ctx, user: discord.Member):
        """Slap some sense into someone!"""
        if ctx.author.id != 7867491071323480074 and user.id == 570020287735660547:
            await ctx.send("No.")
            return
        if user.id == ctx.author.id:
            await ctx.send("Not if I can help it >:|")
            return
        if ctx.author.id == 338441186241019916:
            message = "BEAT EM UP BEAT EM UP BEAT EM UP"
        else:
            message = random.choice(
                [
                    f"*slaps {user.mention} with a large trout* :fish:",
                    f"{ctx.author.mention} delivers a stinging slap to {user.mention}! :raised_back_of_hand:",
                    f"SLAP! {user.mention} didn't see that coming from {ctx.author.mention}! :dizzy_face:",
                    f"The sound of a loud slap echoes as {user.mention} gets slapped by {ctx.author.mention}! :boom:",
                    f"Ouch! {user.mention} just got slapped into next week by {ctx.author.mention}! :exploding_head:",
                ]
            )
        gif_url = (
            await self.get_gif("anime slap face angry")
            or "https://media.giphy.com/media/Zau0yrl17uzdK/giphy.gif"
        )

        embed = discord.Embed(description=message, color=0xFFFFFF)
        embed.set_image(url=gif_url)
        await ctx.send(embed=embed)

    @command(name="punch", description="Punches a user >_<")
    async def punch(self, ctx, user: discord.Member):
        """Punch someone with your virtual fists!"""
        if ctx.author.id != 7867491071323480074 and user.id == 570020287735660547:
            await ctx.send("Nuh uh")
            return
        if user.id == ctx.author.id:
            await ctx.send("nuh uh")
            return
        messages = [
            f"*winds up and punches {user.mention}* :punch:",
            f"BAM! {ctx.author.mention} lands a solid punch on {user.mention}! :dizzy_face:",
            f"POW! Right in the kisser! {user.mention} gets punched by {ctx.author.mention}! :boom:",
            f"{user.mention} didn't stand a chance against {ctx.author.mention}'s powerful punch! :boxing_glove:",
            f"One punch from {ctx.author.mention} sends {user.mention} flying! :dizzy:",
        ]
        gif_url = (
            await self.get_gif("anime punch fight impact")
            or "https://media.giphy.com/media/13YrHUvPzUUmkM/giphy.gif"
        )

        embed = discord.Embed(description=random.choice(messages), color=0xFFFFFF)
        embed.set_image(url=gif_url)
        await ctx.send(embed=embed)

    # @command(name="kill", description="Kills a user >_<")
    # async def kill(self, ctx, user: discord.Member):
    #     """Eliminate someone from existence!"""
    #     if ctx.author.id != 7867491071323480074 and user.id == 570020287735660547:
    #         await ctx.send("Why would you do that?")
    #         return
    #     if user.id == ctx.author.id:
    #         await ctx.send("Nuuuu, don't kill yourself :(")
    #         return
    #     messages = [
    #         f"*pulls out a comically large mallet and bonks {user.mention}* :hammer:",
    #         f"{ctx.author.mention} has eliminated {user.mention} from existence! :skull_crossbones:",
    #         f"It was nice knowing you, {user.mention}. {ctx.author.mention} has ended you. :coffin:",
    #         f"F in the chat for {user.mention}, who was just killed by {ctx.author.mention}! :skull:",
    #         f"{user.mention} has been sent to the shadow realm by {ctx.author.mention}! :boom::skull_and_crossbones:",
    #     ]
    #     gif_url = (
    #         await self.get_gif("anime kill dramatic overkill")
    #         or "https://media.giphy.com/media/3o7TKsQf53w2dLmQy4/giphy.gif"
    #     )

    #     embed = discord.Embed(description=random.choice(messages), color=0xFFFFFF)
    #     embed.set_image(url=gif_url)
    #     await ctx.send(embed=embed)

    @command(name="bathe", description="You racist motherfucker")
    @cooldown(1, 10, BucketType.user)
    async def bathe(self, ctx, user: discord.Member):
        await ctx.send(f"scrub a dub dub {user.mention}")
