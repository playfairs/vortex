# System Imports
import os
import random
import sqlite3
import discord
import uwuipy
import asyncio
import pyfiglet
import aiohttp
import urllib.parse
import io
from PIL import Image, ImageDraw, ImageFont, ImageSequence
import textwrap
from typing import Union

# from - import Imports
from typing import Optional
from discord import app_commands, Embed
from discord.ext import commands
from discord.ext.commands import (
    Author,
    bot_has_permissions,
    Cog,
    cooldown,
    command,
    Context,
    group,
    has_permissions,
    hybrid_command as hybrid,
    hybrid_group,
    is_owner,
)
from discord.ui import Button, View
from discord import ButtonStyle, ui
from giphy_client import DefaultApi
from dotenv import load_dotenv
from uwuipy import uwuipy

# User Imports
from .blacktea import BlackTeaEmbeds
from managers.classes import Emojis
from vortex import vortex

load_dotenv()


class Fun(Cog, description="View commands in Fun."):
    def __init__(self, bot: vortex):
        self.bot = bot
        self.session = aiohttp.ClientSession()
        self.cat_api_key = os.getenv("CAT")
        self.cat_headers = (
            {"x-api-key": self.cat_api_key, "Content-Type": "application/json"}
            if self.cat_api_key
            else {}
        )
        self.db = self.bot.db
        self.db_path = os.path.join("db", "fucked_count.db")
        self.giphy = DefaultApi()
        self.water_reminders = {}  # Initialize water_reminders as an empty dict
        self.initialize_db()
        self.bot.loop.create_task(self.uwulock_tables())
        self.MatchStart = {}
        self.lifes = {}

    async def get_string(self):
        file_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "data",
            "words.txt",
        )
        with open(file_path, "r", encoding="utf-8") as f:
            words = [
                word.strip().lower() for word in f.readlines() if len(word.strip()) >= 3
            ]

        while True:
            word = random.choice(words)

            if len(word) == 3:
                return word

            max_start = len(word) - 3
            if max_start > 0:
                start = random.randint(0, max_start)
                return word[start : start + 3]

    async def get_words(self):
        async with aiohttp.ClientSession() as cs:
            async with cs.get("https://www.mit.edu/~ecprice/wordlist.100000") as r:
                byte = await r.read()
                data = str(byte, "utf-8")
                return data.splitlines()

    def initialize_db(self):
        """Initialize the database folder and file to store fuck counts."""
        try:
            if not os.path.exists("db"):
                os.makedirs("db")

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS fuck_count (
                user_id INTEGER PRIMARY KEY,
                count INTEGER DEFAULT 0
            )"""
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[FUCK] Error initializing database: {e}")

    async def uwulock_tables(self):
        """Create the uwulock tables if they don't exist."""
        async with self.bot.db.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS uwulock (
                    guild_id BIGINT,
                    user_id BIGINT,
                    PRIMARY KEY (guild_id, user_id)
                )
            """
            )

    async def cog_load(self):
        self.db = self.bot.db
        await self.create_tables()
        await self.create_selfreaction_tables()
        await self.create_water_tables()

    async def create_tables(self):
        await self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS nword (
                user_id BIGINT PRIMARY KEY,
                count BIGINT DEFAULT 0,
                count_hard BIGINT DEFAULT 0 
            );
            """
        )

    async def create_selfreaction_tables(self):
        await self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS selfreaction (
                user_id BIGINT,
                emoji TEXT,
                message_id BIGINT,
                count INTEGER DEFAULT 1,
                PRIMARY KEY (user_id, emoji, message_id)
            );
            """
        )

    async def create_water_tables(self):
        await self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS water (
                guild_id BIGINT,
                channel_id BIGINT,
                delay INT,
                PRIMARY KEY (guild_id)
            );
            """
        )

    async def cog_unload(self):
        """Clean up tasks when the cog is unloaded."""
        if hasattr(self, "water_reminders"):
            for reminder in self.water_reminders.values():
                if "task" in reminder:
                    reminder["task"].cancel()
            self.water_reminders.clear()

    @command(
        name="wolfram",
        aliases=["wolframalpha", "wr"],
        description="Ask Wolfram Alpha a question.",
    )
    async def wolfram(self, ctx, *, question: str):
        async with ctx.typing():
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://api.wolframalpha.com/v2/query?input={urllib.parse.quote(question)}&output=json&appid={os.getenv('WOLFRAM_ALPHA_API_KEY')}"
                ) as response:
                    if response.status != 200:
                        await ctx.send(
                            "Ion could not get a response from Wolfram Alpha."
                        )
                        return

                    response_json = await response.json()
                    if not response_json:
                        await ctx.send(
                            "Ion could not parse the response from Wolfram Alpha."
                        )
                        return

                    query_result = response_json.get("queryresult", {})
                    if not query_result:
                        await ctx.send(
                            "Ion could not parse the query result from Wolfram Alpha."
                        )
                        return

                    pods = query_result.get("pods", [])
                    if not pods:
                        error = query_result.get("error", False)
                        if error:
                            error_msg = "Unknown error"
                            if isinstance(error, dict):
                                error_msg = error.get("msg", "Unknown error")
                            await ctx.send(
                                f"Ion encountered an error with Wolfram Alpha's API: {error_msg}"
                            )
                        else:
                            await ctx.send(
                                "Ion could not find any answers from Wolfram Alpha. Try rephrasing your question."
                            )
                        return

                    def get_pod_text(pod):
                        try:
                            if pod.get("primary") == "true":
                                subpods = pod.get("subpods", [])
                                if subpods:
                                    return subpods[0].get("plaintext")
                        except (KeyError, IndexError, TypeError):
                            return None
                        return None

                    pod_texts = [get_pod_text(pod) for pod in pods if get_pod_text(pod)]
                    answer = "\n".join([t for t in pod_texts if t])

                    if not answer:
                        error_msg = "No answer found"
                        if "error" in query_result:
                            if isinstance(query_result["error"], dict):
                                error_msg = query_result["error"].get(
                                    "msg", "No answer found"
                                )
                        await ctx.send(f"Ion could not find an answer: {error_msg}")
                        return

                    embed = discord.Embed(
                        description=answer, color=discord.Color(0xFFFFFF)
                    )
                    embed.set_author(
                        name=ctx.author.display_name, icon_url=ctx.author.avatar.url
                    )
                    await ctx.send(embed=embed)

    @command(name="skibidi", aliases=["brainrot"], description="brainrot")
    async def skibidi(self, ctx):
        skibidi_gifs = [
            "https://tenor.com/view/bombardiro-crocodilo-gif-85634214384150846",
            "https://tenor.com/view/tung-tungtung-tungtungtung-sahur-tungtungtungsahur-tungtungsahur-gif-6699270143817937548",
        ]
        await ctx.send(random.choice(skibidi_gifs))

    @command(name="tableflip", description="flips a table")
    async def tableflip(self, ctx):
        await ctx.send("(╯°□°)╯︵ ┻━┻")

    @command(name="unflip", description="unflips a table")
    async def unflip(self, ctx):
        await ctx.send("┬─┬ノ( º _ ºノ)")

    # @hybrid(name="void", aliases=["ask"], description="asks void ai a question")
    # @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    # @app_commands.allowed_installs(guilds=True, users=True)
    # async def void(self, ctx, *, question: str):
    #     async with ctx.typing():
    #         async with aiohttp.ClientSession() as session:
    #             async with session.post(
    #                 "https://api.voidai.app/v1/chat/completions",
    #                 headers={
    #                     "Authorization": f"Bearer {os.getenv('VOID_AI_API_KEY')}",
    #                     "Content-Type": "application/json",
    #                 },
    #                 json={
    #                     "model": "gpt-4o",
    #                     "messages": [{"role": "user", "content": question}],
    #                     "max_tokens": 2048,
    #                     "temperature": 0.7,
    #                 },
    #             ) as response:
    #                 if response.status != 200:
    #                     await ctx.send("Ion wanna talk to u ")
    #                     return

    #                 response_json = await response.json()
    #                 if not response_json or not response_json.get("choices"):
    #                     await ctx.send("Ion wanna talk to u ")
    #                     return

    #                 answer = response_json["choices"][0]["message"]["content"].strip()
    #                 await ctx.send(answer)

    @command(name="touch", description="Touches a user.")
    async def touch(self, ctx, user: discord.User | discord.Member):
        if user.id == ctx.author.id:
            await ctx.send("In front of everyone??? You nasty little shit.")
            return
        if ctx.author.id == 1426711359059394662 and user.id != 570020287735660547:
            await ctx.send("Uhm, thats not tech silly goose!")
            return
        if ctx.author.id == 1426711359059394662 and user.id == self.bot.user.id:
            await ctx.send("Why are you trying to touch me? Im not tech.")
            return
        if ctx.author.id != 570020287735660547 and user.id == 1426711359059394662:
            await ctx.send("your not tech!")
            return
        if ctx.author.id != 1426711359059394662 and user.id == 570020287735660547:
            await ctx.send("no.")
            return
        outcomes = [
            f"{ctx.author.mention} gently touched {user.mention}'s shoulder.",
            f"{ctx.author.mention} gave {user.mention} a friendly tap on the back.",
            f"{ctx.author.mention} lovingly stroked {user.mention}'s hair.",
            f"{ctx.author.mention} gave {user.mention} a warm hug.",
            f"{ctx.author.mention} gave {user.mention} a playful pat on the head.",
            f"{ctx.author.mention} gave {user.mention} a high-five.",
            f"{ctx.author.mention} gave {user.mention} a *ding* on the nose.",
            f"{ctx.author.mention} gave {user.mention} a *poke* on the side.",
            f"{ctx.author.mention} gave {user.mention} a *tap tap* on the shoulder.",
            f"{ctx.author.mention} gave {user.mention} a *whap* on the back.",
            f"{ctx.author.mention} gave {user.mention} a *whap whap* on the head.",
            f"did {user.mention} even give consent???",
        ]
        random_outcome = random.choice(outcomes)
        await ctx.send(random_outcome)

    # @group(name="uwulock", description="Uwulock commands.", invoke_without_command=True)
    # @has_permissions(manage_webhooks=True)
    # @bot_has_permissions(manage_webhooks=True)
    # async def uwulock(self, ctx, user: discord.Member, *, flag: bool = False):
    #     """Toggle uwulock for a user."""

    #     if ctx.subcommand_passed is None:
    #         if flag:
    #             await self.bot.db.execute(
    #                 """
    #                 DELETE FROM uwulock
    #                 WHERE user_id = $1
    #                 """,
    #                 user.id,
    #             )
    #             await ctx.send(
    #                 f"{user.mention} is no longer uwulocked across all servers."
    #             )
    #             return

    #         is_uwulocked = await self.bot.db.fetchval(
    #             """
    #             SELECT 1 FROM uwulock 
    #             WHERE guild_id = $1 AND user_id = $2
    #             """,
    #             ctx.guild.id,
    #             user.id,
    #         )

    #         if is_uwulocked:
    #             await self.bot.db.execute(
    #                 """
    #                 DELETE FROM uwulock 
    #                 WHERE guild_id = $1 AND user_id = $2
    #                 """,
    #                 ctx.guild.id,
    #                 user.id,
    #             )
    #             await ctx.send(f"{user.mention} is no longer uwulocked.")
    #         else:
    #             await self.bot.db.execute(
    #                 """
    #                 INSERT INTO uwulock (guild_id, user_id)
    #                 VALUES ($1, $2)
    #                 ON CONFLICT (guild_id, user_id) DO NOTHING
    #                 """,
    #                 ctx.guild.id,
    #                 user.id,
    #             )
    #             await ctx.send(f"{user.mention} is now uwulocked.")

    # @uwulock.command(name="reset", description="Resets the uwulock table.")
    # @has_permissions(manage_webhooks=True)
    # @bot_has_permissions(manage_webhooks=True)
    # async def reset_uwulock(self, ctx):
    #     """Reset the uwulock table."""
    #     await self.bot.db.execute("TRUNCATE TABLE uwulock")
    #     await ctx.send("Successfully reset the uwulock table.")

    # @Cog.listener()
    # async def on_message(self, message: discord.Message):
    #     if message.author.bot:
    #         return

    #     if message.guild is None:
    #         return

    #     if not hasattr(message.channel, "webhooks"):
    #         return

    #     try:
    #         is_uwulocked = await self.bot.db.fetchval(
    #             """
    #             SELECT 1
    #             FROM uwulock
    #             WHERE guild_id = $1 AND user_id = $2
    #             """,
    #             message.guild.id,
    #             message.author.id,
    #         )

    #         if not is_uwulocked:
    #             return

    #         try:
    #             webhook = discord.utils.get(
    #                 await message.channel.webhooks(), name=message.author.display_name
    #             )
    #             if webhook is None:
    #                 webhook = await message.channel.create_webhook(
    #                     name=message.author.display_name
    #                 )
    #             uwu = uwuipy()
    #             uwuified_content = uwu.uwuify(message.clean_content)
    #             await message.delete()
    #             if "@everyone" in message.content or "@here" in message.content:
    #                 allowed_mentions = discord.AllowedMentions(
    #                     everyone=False, roles=False, users=True
    #                 )
    #             else:
    #                 allowed_mentions = discord.AllowedMentions.all()
    #             await webhook.send(
    #                 content=uwuified_content,
    #                 username=message.author.display_name,
    #                 avatar_url=message.author.display_avatar.url,
    #                 allowed_mentions=allowed_mentions,
    #             )
    #         except discord.HTTPException as e:
    #             print(f"Error in webhook handling: {e}")
    #     except discord.Forbidden as e:
    #         await message.channel.send("Missing Permissions: Manage Webhooks.")
    #     except Exception as e:
    #         print(f"Error in on_message: {e}")

    @command(name="button", description="Embeds as many buttons as possible.")
    async def button(self, ctx: Context):
        view = View()
        faces = [">_<", ">.<", "UwU", "nya~", "XD", ":P", ";-;"]
        for i in range(25):
            button = Button(label=random.choice(faces), style=ButtonStyle.gray)
            button.callback = self.send_random_emote
            view.add_item(button)
        await ctx.send(view=view)

    async def send_random_emote(self, interaction: discord.Interaction):
        messages = [
            "Ngh, don't touch my buttons >_<",
            "Stop pressing my buttons.. it feels so good >_<",
            "stop touching those.. >_<",
            "Leave my buttons alone.. i didnt consent to this >.<",
            "omggg~ >_< i love this",
            "oh yes keep touching me >_<",
            "ngh stop that feels so good >_<",
            "nghhh stoopp >_<",
            "nyah~ >_< keep going..",
            "im going to touch you next if you keep this up",
            "nghh~ keep doing that, it feels great",
            "button pressed.",
            "nya~ >_<",
            "stop touching me nyah~ >_<",
        ]
        await interaction.response.send_message(random.choice(messages), ephemeral=True)

    @command(
        name=",;",
        aliases=[".;", "-;"],
        description="Common emoticon, bots prefix is ; so whynot make a command for the emoticon :p",
        usage=",;",
    )
    async def comma(self, ctx: Context):
        await ctx.send(
            "https://tenor.com/view/happy-cat-silly-cat-happy-cat-smile-gif-11748501437476694103"
        )

    @command(name="playunfair")
    async def playunfair(self, ctx: Context):
        await ctx.send("<@1265662059056463976>")

    @command(
        name="l", description="L to you for thinking this was a command.. oh wait."
    )
    async def l(self, ctx: Context):
        await ctx.send("L to you for thinking this was a command.. oh wait..")

    @command(name="3", description=";3", usage=";3")
    async def three(self, ctx: Context):
        """
        ;3
        """
        if ctx.prefix != ";":
            return
        await ctx.send(f"{ctx.author.mention} ;3")

    @command(name="nothing", description="Literally does nothing.", usage=";nothing")
    async def nothing(self, ctx: Context):
        """
        Literally does nothing.
        """
        if ctx.prefix != ";":
            return

    @hybrid_group(
        name="nword",
        description="See how many times you have said the nword.",
        invoke_without_command=True,
    )
    @app_commands.allowed_contexts(dms=True, guilds=True, private_channels=True)
    @app_commands.allowed_installs(users=True, guilds=True)
    async def nword(self, ctx, *, user: discord.User = None):
        """See how many times you have said the nword."""
        if user is None:
            user = ctx.author

        data = await self.db.fetchrow(
            "SELECT count, count_hard FROM nword WHERE user_id = $1", user.id
        )

        if data is None:
            target = "you have" if user == ctx.author else f"{user.mention} has"
            await ctx.send(f"{target} not said the nword.")
        else:
            await ctx.send(
                f"You have said the nword {data['count']} times. \n-# {data['count_hard']} times hard."
            )

    @nword.command(
        name="scale",
        description="See how black you are based on how many times you have said the nword.",
    )
    @app_commands.allowed_contexts(dms=True, guilds=True, private_channels=True)
    @app_commands.allowed_installs(users=True, guilds=True)
    async def scale(self, ctx: Context, user: discord.User = None):
        """See how black you are based on how many times you have said the nword."""
        if user is None:
            user = ctx.author

        user_data = await self.db.fetchrow(
            "SELECT count, count_hard FROM nword WHERE user_id = $1", user.id
        )

        if user_data is None:
            target = "you have" if user == ctx.author else f"{user.mention} has"
            await ctx.send(f"{target} not said the nword.")
            return

        all_users = await self.db.fetch(
            "SELECT user_id, count + count_hard as total FROM nword ORDER BY total DESC"
        )

        if not all_users:
            await ctx.send("No data available.")
            return

        max_count = all_users[0]["total"]
        user_total = user_data["count"] + user_data["count_hard"]

        if max_count > 0:
            raw_percent = (user_total / max_count) * 100

            hard_penalty = (
                (user_data["count_hard"] / user_total) * 50 if user_total > 0 else 0
            )

            percentile = max(0, min(100, raw_percent - hard_penalty))
        else:
            percentile = 0

        rank = next(
            (i + 1 for i, u in enumerate(all_users) if u["user_id"] == user.id),
            len(all_users),
        )
        total_users = len(all_users)

        filled = "█" * (int(percentile) // 5)
        empty = "░" * (20 - len(filled))
        progress_bar = f"`{filled}{empty}` {int(percentile)}%"

        raw_racism = user_total / max(1, max_count)

        if raw_racism < 0.05:
            racism_msg = "Basically a saint"
        elif raw_racism < 0.15:
            racism_msg = "Mildly sus"
        elif raw_racism < 0.3:
            racism_msg = "Questionable at best"
        elif raw_racism < 0.5:
            racism_msg = "Yikes, that's pretty bad"
        elif raw_racism < 0.7:
            racism_msg = "You're pretty racist.."
        elif raw_racism < 0.9:
            racism_msg = "Certified Racist™"
        else:
            racism_msg = "Grand Wizard Man??"

        if user_data["count_hard"] > 0:
            if (user_data["count_hard"] / user_total) > 0.5:
                racism_msg = "Bro what the fuck is wrong with you"
            elif (user_data["count_hard"] / user_total) > 0.3:
                racism_msg = "You need to chill with the hard Rs"
            elif (user_data["count_hard"] / user_total) > 0.1:
                racism_msg = f"{racism_msg} (Hard R penalty applied)"

        response = (
            f"{progress_bar}\n"
            f"• Total n-words: `{user_total:,}`\n"
            f"• Rank: `{rank:,}` of `{total_users:,}`\n"
            f"• Hard R's: `{user_data['count_hard']:,}`\n"
            f"Racism estimation... **{racism_msg}**"
        )

        container = discord.ui.Container(
            discord.ui.TextDisplay(
                content=f"### {user.display_name}'s Blackness Scale"
            ),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            discord.ui.TextDisplay(content=response),
        )
        container.accent_colour = discord.Colour(0x000000)

        view = discord.ui.LayoutView()
        view.add_item(container)
        await ctx.send(view=view)

    @nword.command(name="apologize", description="Apologize for your racism.")
    @app_commands.allowed_contexts(dms=True, guilds=True, private_channels=True)
    @app_commands.allowed_installs(users=True, guilds=True)
    async def apologize(self, ctx: Context):
        """Reset your hard R count and apologize."""
        await self.bot.db.execute(
            """
            UPDATE nword 
            SET count_hard = 0 
            WHERE user_id = $1
            """,
            ctx.author.id,
        )

        data = await self.bot.db.fetchrow(
            "SELECT count_hard FROM nword WHERE user_id = $1", ctx.author.id
        )

        if data and data["count_hard"] == 0:
            await ctx.send("I forgive you.")
        else:
            await ctx.send("You don't have any hard Rs to apologize for.")

    @is_owner()
    @nword.command(name="forgive", description="Reset a user's n-word count entirely.")
    @app_commands.allowed_contexts(dms=True, guilds=True, private_channels=True)
    @app_commands.allowed_installs(users=True, guilds=True)
    async def forgive(self, ctx: Context, user: discord.User):
        """Reset a user's n-word count entirely."""
        await self.bot.db.execute(
            """
            UPDATE nword 
            SET count = 0,
                count_hard = 0
            WHERE user_id = $1
            """,
            user.id,
        )

        data = await self.bot.db.fetchrow(
            "SELECT count, count_hard FROM nword WHERE user_id = $1", user.id
        )

        if data and data["count"] == 0 and data["count_hard"] == 0:
            await ctx.send(f"{user.mention}'s n-word count has been reset to 0.")
        else:
            await ctx.send("No n-word count found for this user.")

    @Cog.listener("on_message")
    async def nigga_counter(self, message: discord.Message) -> discord.Message:
        if message.author.bot:
            return

        content = message.content.lower()
        soft_count = content.count("nigga") + content.count("nga")
        hard_count = content.count("nigger")

        if soft_count > 0:
            await self.bot.db.execute(
                """
                INSERT INTO nword (user_id, count)
                VALUES ($1, $2)
                ON CONFLICT (user_id)
                DO UPDATE SET count = nword.count + $2
                """,
                message.author.id,
                soft_count,
            )

        if hard_count > 0:
            await self.bot.db.execute(
                """
                INSERT INTO nword (user_id, count_hard)
                VALUES ($1, $2)
                ON CONFLICT (user_id)
                DO UPDATE SET count_hard = nword.count_hard + $2
                """,
                message.author.id,
                hard_count,
            )

    @command(name="pp", aliases=["dih", "dihsize"], description=",pp user")
    async def pp(self, ctx: Context, user: Optional[discord.Member] = Author):
        """See someones pp size"""
        size = random.randint(0, 15)
        pp_display = "8" + "=" * size + "D"

        if size < 6:
            comment = random.choice(
                [
                    "Damn, that's small.",
                    "Is that even measurable?",
                    "Sending thoughts and prayers.",
                    "Where’s the rest of it?",
                ]
            )
        elif 6 <= size <= 10:
            comment = random.choice(
                [
                    "That's pretty average.",
                    "Respectable size.",
                    "Not bad, not bad.",
                    "Right in the middle zone.",
                ]
            )
        else:
            comment = random.choice(
                [
                    "Dang. That’s BIG.",
                    "A true champion.",
                    "Calm down, bro.",
                    "Weapon of mass destruction!",
                    "Dihtacular",
                    "A weapon of mass dihstruction",
                ]
            )

        await ctx.send(
            embed=Embed(
                title=f"{user.name}'s pp size",
                description=f"{pp_display} \n-# {comment}",
            )
        )

    @command(
        name="pickupline",
        aliases=["pickup", "rizz"],
        description="Get a random pickup line.",
    )
    async def pickupline(self, ctx, *, user: Optional[discord.User] = None):
        """Get a random pickup line."""
        message = await ctx.send("Fetching a pickup line...")
        async with self.session.get("https://rizzapi.vercel.app/random") as response:
            if response.ok:
                data = await response.json()
                if user:
                    try:
                        if user == ctx.author:
                            await message.edit(content="Are you that lonely?")
                        elif user == ctx.bot.user:
                            await message.edit(content="Oh I see what you did there..")
                        else:
                            await user.send(f"{data['text']} - from {ctx.author.name}")
                            await message.edit(
                                content=f"Sent a pickup line to {user.name}!"
                            )
                    except discord.Forbidden:
                        await message.edit(content="I can't DM that user.")
                else:
                    await message.edit(content=data["text"])

    @command(name="blacktea", description="Play a game of blacktea.")
    @cooldown(1, 5, commands.BucketType.user)
    async def blacktea(self, ctx: Context):
        try:
            if self.MatchStart[ctx.guild.id] is True:
                return await ctx.reply(
                    "somebody in this server is already playing blacktea",
                    mention_author=False,
                )
        except KeyError:
            pass

        self.MatchStart[ctx.guild.id] = True
        used_words = set()
        try:
            mes = await ctx.send(embed=BlackTeaEmbeds.get_initial_embed(ctx))
            await mes.add_reaction(Emojis.blacktea)
            await asyncio.sleep(20)

            me = await ctx.channel.fetch_message(mes.id)
            players = [user.id async for user in me.reactions[0].users()]
            players.remove(self.bot.user.id)

            if len(players) < 2:
                return await ctx.reply(
                    f"{ctx.author.mention}, not enough players joined to start blacktea",
                    allowed_mentions=discord.AllowedMentions(users=True),
                )

            for player in players:
                self.lifes[player] = 0

            while len(players) > 1:
                for player in list(players):
                    strin = await self.get_string()
                    content, embed = BlackTeaEmbeds.get_game_embed(
                        player, strin, used_words
                    )
                    msg = await ctx.send(
                        content=content,
                        embed=embed,
                        allowed_mentions=discord.AllowedMentions(users=True),
                    )

                    def is_correct(m):
                        return m.author.id == player and m.channel.id == ctx.channel.id

                    try:
                        start_time = asyncio.get_event_loop().time()
                        countdown_shown = False
                        message = None

                        async def update_countdown():
                            nonlocal msg, countdown_shown
                            time_left = 10 - (
                                asyncio.get_event_loop().time() - start_time
                            )
                            if 0 < time_left <= 3 and not countdown_shown:
                                countdown_shown = True
                                for i in range(3, 0, -1):
                                    await msg.add_reaction(f"{i}️⃣")
                                    if i == 1:
                                        await asyncio.sleep(1)
                                        return
                                    await asyncio.sleep(1)

                        while True:
                            countdown_task = asyncio.create_task(update_countdown())
                            try:
                                message = await self.bot.wait_for(
                                    "message",
                                    timeout=10
                                    - (asyncio.get_event_loop().time() - start_time),
                                    check=is_correct,
                                )
                                countdown_task.cancel()
                            except asyncio.TimeoutError:
                                if countdown_shown:
                                    await asyncio.sleep(1)
                                raise

                            if countdown_shown:
                                try:
                                    await msg.clear_reactions()
                                except:
                                    pass

                            try:
                                is_valid, should_continue = (
                                    await BlackTeaEmbeds.handle_word_validation(
                                        message=message,
                                        used_words=used_words,
                                        target_string=strin,
                                        word_list=await self.get_words(),
                                        check_emoji=Emojis.check,
                                    )
                                )

                                if should_continue:
                                    continue
                                if is_valid:
                                    break
                            except Exception as e:
                                print(f"Error in word validation: {e}")
                                await message.add_reaction("❌")
                                await message.reply(
                                    "An error occurred while validating your word.",
                                    delete_after=2,
                                    mention_author=True,
                                    allowed_mentions=discord.AllowedMentions(
                                        users=True
                                    ),
                                )

                            if asyncio.get_event_loop().time() - start_time >= 10:
                                raise asyncio.TimeoutError()

                    except asyncio.TimeoutError:
                        self.lifes[player] = self.lifes.get(player, 0) + 1
                        remaining_lives = 3 - self.lifes[player]

                        embed = BlackTeaEmbeds.get_elimination_embed(
                            player, remaining_lives
                        )

                        if remaining_lives <= 0:
                            await ctx.send(
                                embed=embed,
                                delete_after=5,
                                allowed_mentions=discord.AllowedMentions(users=True),
                            )
                            players.remove(player)
                            if len(players) == 1:
                                break
                        else:
                            await ctx.send(
                                embed=embed,
                                delete_after=5,
                                allowed_mentions=discord.AllowedMentions(users=True),
                            )

            if players:
                winner_id = players[0]
                embed = BlackTeaEmbeds.get_victory_embed(
                    winner_id, 3 - self.lifes.get(winner_id, 0)
                )
                await ctx.send(
                    embed=embed,
                    mention_author=True,
                    allowed_mentions=discord.AllowedMentions(users=True),
                )
        finally:
            self.MatchStart[ctx.guild.id] = False
            for player in players:
                if player in self.lifes:
                    del self.lifes[player]

    @hybrid(name="ascii", description="Converts a given message into ASCII art.")
    async def ascii(self, ctx, *, message: str):
        """Converts a given message into ASCII art."""
        await ctx.message.delete()
        ascii_text = pyfiglet.figlet_format(message)
        await ctx.send(f"```\n{ascii_text}\n```")

    @hybrid(name="chipichipi", description="CHIPI CHIPI CHAPA CHA DUBI DUBI BADABA")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def chipichipichapachapadubidubidabadaba(self, ctx: Context):
        """CHIPI CHIPI CHAPA CHA DUBI DUBI BADABA"""
        container = discord.ui.Container(
            discord.ui.TextDisplay(
                content="# Chipichipi chapachapa dubidubi dabadaba magico mi dubidubi boom boom boom boom"
            ),
            discord.ui.MediaGallery(
                discord.MediaGalleryItem(
                    media="https://cdn.mtdv.me/video/chipi.mp4",
                ),
            ),
        )

        view = discord.ui.LayoutView()
        view.add_item(container)
        await ctx.send(view=view)

    @hybrid_group(
        name="selfreaction",
        aliases=["sr", "selfreactions"],
        description="Selfreaction commands",
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def selfreaction(self, ctx: Context):
        pass

    @selfreaction.command(name="count", description="Count your selfreactions")
    @app_commands.describe(user="The user to count selfreactions for")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def count(self, ctx: Context, user: discord.User = None):
        if user is None:
            user = ctx.author
        async with self.bot.db.acquire() as conn:
            count = await conn.fetchval(
                """
                SELECT COALESCE(SUM(count), 0) FROM selfreaction
                WHERE user_id = $1
                """,
                user.id,
            )
            message = f"{user.mention} has {count} selfreactions."
            if count > 10:
                message += ". what the fuck...."
            await ctx.send(message)

    @selfreaction.command(name="top", description="See the top selfreactions")
    @app_commands.describe(user="The user to check top selfreactions for")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def top(self, ctx: Context, user: discord.User = None):
        if user is None:
            user = ctx.author

        async with self.bot.db.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT emoji, SUM(count) as total
                FROM selfreaction
                WHERE user_id = $1
                GROUP BY emoji
                ORDER BY total DESC
                LIMIT 10
                """,
                user.id,
            )

            if not rows:
                await ctx.send(f"{user.mention} has no self-reactions yet!")
                return

            result = [f"{row['emoji']}: {row['total']}" for row in rows]

            container = discord.ui.Container(
                discord.ui.TextDisplay(
                    content="### Top Self Reactions for <@{}>".format(user.id)
                ),
                discord.ui.Separator(
                    visible=True, spacing=discord.SeparatorSpacing.large
                ),
                discord.ui.TextDisplay(content="\n".join(result)),
            )

            view = discord.ui.LayoutView()
            view.add_item(container)
            await ctx.send(view=view, allowed_mentions=discord.AllowedMentions.none())

    @selfreaction.command(
        name="leaderboard",
        aliases=["lb"],
        description="See the leaderboard of selfreactions",
    )
    @app_commands.describe(emoji="The emoji to filter by (optional)")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def leaderboard(self, ctx: Context, emoji: str = None):
        """Show the top 10 users with the most self-reactions, optionally filtered by emoji."""
        async with self.bot.db.acquire() as conn:
            query = """
                SELECT user_id, COALESCE(SUM(count), 0) AS total
                FROM selfreaction
                {}
                GROUP BY user_id
                ORDER BY total DESC
                LIMIT 10
                """.format(
                "WHERE emoji = $1" if emoji else ""
            )

            rows = await conn.fetch(query, *([emoji] if emoji else []))

            if not rows:
                message = (
                    f"No one has self reacted with {emoji} yet"
                    if emoji
                    else "No one has reacted to themself yet."
                )
                await ctx.send(message)
                return

            leaderboard = []
            for i, row in enumerate(rows, 1):
                user = self.bot.get_user(row["user_id"]) or f"<@{row['user_id']}>"
                leaderboard.append(f"**{i}.** {user}: `{row['total']}`")

            title = (
                f"### {'Emoji' if emoji else 'Global'} Leaderboard for Self Reactions"
            )
            if emoji:
                title = f"{title} - {emoji}"

            container = discord.ui.Container(
                discord.ui.TextDisplay(content=title),
                discord.ui.Separator(
                    visible=True, spacing=discord.SeparatorSpacing.large
                ),
                discord.ui.TextDisplay(content="\n".join(leaderboard)),
            )

            view = discord.ui.LayoutView()
            view.add_item(container)
            await ctx.send(view=view, allowed_mentions=discord.AllowedMentions.none())

    @is_owner()
    @selfreaction.command(name="reset", description="Reset your selfreactions")
    @app_commands.describe(
        user="The user to reset selfreactions for",
        table="Drop and recreate the selfreaction table",
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def reset(self, ctx: Context, user: discord.User = None, table: bool = False):
        if user is None:
            user = ctx.author

        async with self.bot.db.acquire() as conn:
            if table:
                await conn.execute("DROP TABLE IF EXISTS selfreaction")
                await self.create_selfreaction_tables()
                await ctx.send("Selfreaction table reset.")
            else:
                await conn.execute(
                    "DELETE FROM selfreaction WHERE user_id = $1", user.id
                )
                await ctx.send("Selfreactions reset for <@{}>".format(user.id))

    @Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        if user.bot or not reaction.message.guild:
            return

        if not isinstance(reaction.emoji, str) or hasattr(reaction.emoji, "id"):
            return

        if reaction.message.author.id == user.id:
            async with self.bot.db.acquire() as conn:
                exists = await conn.fetchval(
                    """
                    SELECT 1 FROM selfreaction 
                    WHERE user_id = $1 AND emoji = $2 AND message_id = $3
                    """,
                    user.id,
                    reaction.emoji,
                    reaction.message.id,
                )

                if not exists:
                    await conn.execute(
                        """
                        INSERT INTO selfreaction (user_id, emoji, message_id, count)
                        VALUES ($1, $2, $3, 1)
                        """,
                        user.id,
                        reaction.emoji,
                        reaction.message.id,
                    )

    @hybrid(
        name="cat",
        aliases=["kitty", "kitten", "cats", "kitties", "kittens"],
        description="Send a random image of a cat from the Cat API",
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def cat(self, ctx: Context):
        async with self.session.get(
            "https://api.thecatapi.com/v1/images/search", headers=self.cat_headers
        ) as response:
            if response.ok:
                data = await response.json()

                media_gallery = discord.ui.MediaGallery(
                    discord.MediaGalleryItem(media=data[0]["url"]),
                )

                container = discord.ui.Container(
                    discord.ui.TextDisplay(content="### Kitty!!"),
                    discord.ui.Separator(
                        visible=True, spacing=discord.SeparatorSpacing.large
                    ),
                    media_gallery,
                    discord.ui.Separator(
                        visible=True, spacing=discord.SeparatorSpacing.large
                    ),
                )

                action_row = discord.ui.ActionRow()
                action_row.add_item(
                    discord.ui.Button(
                        label="Get another Cat :3",
                        custom_id=f"cat_{ctx.message.id}",
                        style=discord.ButtonStyle.gray,
                    )
                )
                action_row.add_item(
                    discord.ui.Button(
                        label="Cat API",
                        url="https://thecatapi.com/",
                        style=discord.ButtonStyle.link,
                    )
                )

                container.add_item(action_row)

                view = discord.ui.LayoutView()
                view.media_gallery = media_gallery
                view.add_item(container)

                async def cat_callback(interaction: discord.Interaction):
                    async with self.session.get(
                        "https://api.thecatapi.com/v1/images/search",
                        headers=self.cat_headers,
                    ) as resp:
                        if resp.ok:
                            new_data = await resp.json()
                            view.media_gallery.items[0].media = new_data[0]["url"]
                            await interaction.response.edit_message(view=view)

                action_row.children[0].callback = cat_callback
                await ctx.send(
                    view=view, allowed_mentions=discord.AllowedMentions.none()
                )

    @hybrid(
        name="fox",
        aliases=["whatdoesthefoxsay"],
        description="Send a random image of a fox from the Fox API",
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def fox(self, ctx: Context):
        async with self.session.get("https://randomfox.ca/floof/") as response:
            if response.ok:
                data = await response.json()

            container = discord.ui.Container(
                discord.ui.TextDisplay(
                    content="# [What does the fox say?](https://open.spotify.com/track/5HOpkTTVcmZHnthgyxrIL8?si=1ab76af3b82f4935)"
                ),
                discord.ui.Separator(
                    visible=True, spacing=discord.SeparatorSpacing.large
                ),
                discord.ui.MediaGallery(
                    discord.MediaGalleryItem(media=data["image"]),
                ),
                discord.ui.Separator(
                    visible=True, spacing=discord.SeparatorSpacing.large
                ),
            )
            action_row = discord.ui.ActionRow()
            action_row.add_item(
                discord.ui.Button(
                    label="Get another Fox :3",
                    custom_id=f"fox_{ctx.message.id}",
                    style=discord.ButtonStyle.gray,
                )
            )
            action_row.add_item(
                discord.ui.Button(
                    label="Fox API",
                    url="https://randomfox.ca/",
                    style=discord.ButtonStyle.link,
                )
            )

            async def fox_callback(interaction: discord.Interaction):
                async with self.session.get("https://randomfox.ca/floof/") as response:
                    if response.ok:
                        data = await response.json()
                        for item in container.children:
                            if isinstance(item, discord.ui.MediaGallery):
                                item.items[0].media = data["image"]
                                break
                        await interaction.response.edit_message(view=view)

            action_row.children[0].callback = fox_callback
            container.add_item(action_row)
            view = discord.ui.LayoutView()
            view.add_item(container)
            await ctx.send(view=view, allowed_mentions=discord.AllowedMentions.none())

    @hybrid(
        name="duck",
        aliases=["quack", "duckling"],
        description="Send a random image of a duck from the Duck API",
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def duck(self, ctx: Context):
        async with self.session.get("https://random-d.uk/api/v2/random") as response:
            if response.ok:
                data = await response.json()

            container = discord.ui.Container(
                discord.ui.TextDisplay(content="### Duck :3"),
                discord.ui.Separator(
                    visible=True, spacing=discord.SeparatorSpacing.large
                ),
                discord.ui.MediaGallery(
                    discord.MediaGalleryItem(media=data["url"]),
                ),
                discord.ui.Separator(
                    visible=True, spacing=discord.SeparatorSpacing.large
                ),
            )

            action_row = discord.ui.ActionRow()
            action_row.add_item(
                discord.ui.Button(
                    label="Get another Duck :3",
                    custom_id=f"duck_{ctx.message.id}",
                    style=discord.ButtonStyle.gray,
                )
            )
            action_row.add_item(
                discord.ui.Button(
                    label="Duck API",
                    url="https://random-d.uk/",
                    style=discord.ButtonStyle.link,
                )
            )

            async def duck_callback(interaction: discord.Interaction):
                async with self.session.get(
                    "https://random-d.uk/api/v2/random"
                ) as response:
                    if response.ok:
                        data = await response.json()
                        for item in container.children:
                            if isinstance(item, discord.ui.MediaGallery):
                                item.items[0].media = data["url"]
                                break
                        await interaction.response.edit_message(view=view)

            action_row.children[0].callback = duck_callback

            container.add_item(action_row)
            view = discord.ui.LayoutView()
            view.add_item(container)
            await ctx.send(view=view, allowed_mentions=discord.AllowedMentions.none())

    @hybrid(
        name="dog",
        aliases=[
            "pupper",
            "pup",
            "puppies",
            "puppy",
            "pups",
            "doggo",
            "doggos",
            "doggie",
            "doggies",
        ],
        description="Send a random image of a dog from the Dog API",
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def dog(self, ctx: Context):
        async with self.session.get(
            "https://api.thedogapi.com/v1/images/search"
        ) as response:
            if response.ok:
                data = await response.json()

                media_gallery = discord.ui.MediaGallery(
                    discord.MediaGalleryItem(media=data[0]["url"]),
                )

                container = discord.ui.Container(
                    discord.ui.TextDisplay(content="### Doggo!!!"),
                    discord.ui.Separator(
                        visible=True, spacing=discord.SeparatorSpacing.large
                    ),
                    media_gallery,
                    discord.ui.Separator(
                        visible=True, spacing=discord.SeparatorSpacing.large
                    ),
                )

                action_row = discord.ui.ActionRow()
                action_row.add_item(
                    discord.ui.Button(
                        label="Get another Dog :3",
                        custom_id=f"dog_{ctx.message.id}",
                        style=discord.ButtonStyle.gray,
                    )
                )
                action_row.add_item(
                    discord.ui.Button(
                        label="Dog API",
                        url="https://thedogapi.com/",
                        style=discord.ButtonStyle.link,
                    )
                )

                container.add_item(action_row)

                view = discord.ui.LayoutView()
                view.media_gallery = media_gallery
                view.add_item(container)

                async def dog_callback(interaction: discord.Interaction):
                    async with self.session.get(
                        "https://api.thedogapi.com/v1/images/search"
                    ) as resp:
                        if resp.ok:
                            new_data = await resp.json()
                            view.media_gallery.items[0].media = new_data[0]["url"]
                            await interaction.response.edit_message(view=view)

                action_row.children[0].callback = dog_callback
                await ctx.send(
                    view=view, allowed_mentions=discord.AllowedMentions.none()
                )

    async def get_cat_breeds(self):
        """Fetch all available cat breeds from the API"""
        async with self.session.get(
            "https://api.thecatapi.com/v1/breeds", headers=self.cat_headers
        ) as response:
            if response.ok:
                return await response.json()
            return []

    @staticmethod
    def _truncate_text(text: str, max_length: int = 100) -> str:
        """Truncate text to a maximum length, adding ellipsis if needed."""
        if len(text) <= max_length:
            return text
        return text[: max_length - 3].strip() + "..."

    @hybrid(name="catfact", description="Get a random cat fact")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.describe(breed="The cat breed to get information about")
    async def catfact(self, ctx: Context, breed: str = None):
        """Get information about a cat breed"""
        breeds = await self.get_cat_breeds()

        selected_breed = None
        if breed:
            breed_lower = breed.lower()
            for b in breeds:
                if breed_lower in b["name"].lower() or (
                    b.get("id") and breed_lower == b["id"].lower()
                ):
                    selected_breed = b
                    break

            if not selected_breed:
                return await ctx.send(
                    f"Couldn't find a cat breed matching '{breed}'. Try without a breed for a random one!"
                )

        api_url = "https://api.thecatapi.com/v1/images/search?has_breeds=1"
        if selected_breed:
            api_url += f"&breed_ids={selected_breed['id']}"

        async with self.session.get(api_url, headers=self.cat_headers) as response:
            if response.ok:
                data = await response.json()

                if not data or not isinstance(data, list) or not data[0].get("breeds"):
                    return await ctx.send(
                        "Couldn't fetch cat breed information. Please try again!"
                    )

                breed_data = data[0]["breeds"][0]

                if "description" in breed_data:
                    breed_data["description"] = self._truncate_text(
                        breed_data["description"], 300
                    )
                if "temperament" in breed_data:
                    breed_data["temperament"] = self._truncate_text(
                        breed_data["temperament"], 200
                    )
                if "origin" in breed_data:
                    breed_data["origin"] = self._truncate_text(
                        breed_data["origin"], 100
                    )

                media_gallery = discord.ui.MediaGallery(
                    discord.MediaGalleryItem(media=data[0]["url"]),
                )

                container = discord.ui.Container()

                container.add_item(
                    discord.ui.TextDisplay(
                        content=f"### {breed_data.get('name', 'Unknown Cat')}",
                    )
                )
                container.add_item(
                    discord.ui.Separator(
                        visible=True, spacing=discord.SeparatorSpacing.small
                    )
                )

                if "url" in data[0]:
                    media_gallery = discord.ui.MediaGallery(
                        discord.MediaGalleryItem(media=data[0]["url"]),
                    )
                    container.add_item(media_gallery)
                    container.add_item(
                        discord.ui.Separator(
                            visible=True, spacing=discord.SeparatorSpacing.small
                        )
                    )
                if "origin" in breed_data:
                    container.add_item(
                        discord.ui.TextDisplay(
                            content=f"**Origin**\n{breed_data['origin']}"
                        )
                    )
                if "temperament" in breed_data:
                    container.add_item(
                        discord.ui.TextDisplay(
                            content=f"**Temperament**\n{breed_data['temperament']}"
                        )
                    )
                if "life_span" in breed_data:
                    container.add_item(
                        discord.ui.TextDisplay(
                            content=f"**Life Span**\n{breed_data['life_span']} years"
                        )
                    )
                if "weight" in breed_data and "metric" in breed_data["weight"]:
                    container.add_item(
                        discord.ui.TextDisplay(
                            content=f"**Weight**\n{breed_data['weight']['metric']} kg"
                        )
                    )
                if "description" in breed_data:
                    container.add_item(
                        discord.ui.Separator(
                            visible=True, spacing=discord.SeparatorSpacing.small
                        )
                    )
                    container.add_item(
                        discord.ui.TextDisplay(content=f"*{breed_data['description']}*")
                    )
                container.add_item(
                    discord.ui.Separator(
                        visible=True, spacing=discord.SeparatorSpacing.small
                    )
                )
                action_row1 = discord.ui.ActionRow()
                if len(breeds) > 1:
                    select = discord.ui.Select(
                        placeholder="Select a breed...",
                        custom_id=f"breed_select_{ctx.message.id}",
                        options=[
                            discord.SelectOption(
                                label=b["name"],
                                value=b["id"],
                                description=b.get("name", "")[:50],
                                default=b.get("id") == breed_data.get("id"),
                            )
                            for b in sorted(breeds[:25], key=lambda x: x["name"])
                        ],
                    )
                    action_row1.add_item(select)

                buttons = discord.ui.ActionRow()
                buttons.add_item(
                    discord.ui.Button(
                        label="Get Another Cat",
                        style=discord.ButtonStyle.gray,
                        custom_id=f"catfact_{ctx.message.id}",
                    )
                )
                if "wikipedia_url" in breed_data:
                    buttons.add_item(
                        discord.ui.Button(
                            label="Learn More",
                            url=breed_data["wikipedia_url"],
                            style=discord.ButtonStyle.link,
                        )
                    )

                container.add_item(action_row1)
                container.add_item(buttons)

                view = discord.ui.LayoutView()
                view.media_gallery = (
                    media_gallery if "media_gallery" in locals() else None
                )
                view.add_item(container)

                await ctx.send(view=view)

                field_order = []
                for i, child in enumerate(container.children):
                    if hasattr(child, "content"):
                        if child.content.startswith("###"):
                            field_order.append(("title", i))
                        elif "**Origin**" in child.content:
                            field_order.append(("origin", i))
                        elif "**Temperament**" in child.content:
                            field_order.append(("temperament", i))
                        elif "**Life Span**" in child.content:
                            field_order.append(("life_span", i))
                        elif "**Weight**" in child.content:
                            field_order.append(("weight", i))
                        elif child.content.startswith("*"):
                            field_order.append(("description", i))

                async def button_callback(interaction: discord.Interaction):
                    if interaction.user != ctx.author:
                        return await interaction.response.send_message(
                            "This is not your command!", ephemeral=True
                        )

                    if buttons.children and len(buttons.children) > 0:
                        buttons.children[0].disabled = True
                        buttons.children[0].label = "Loading..."

                    await interaction.response.edit_message(view=view)

                    try:
                        selected_breed_id = None
                        if hasattr(interaction, "data") and hasattr(
                            interaction.data, "get"
                        ):
                            if (
                                "values" in interaction.data
                                and interaction.data["values"]
                            ):
                                selected_breed_id = interaction.data["values"][0]

                        if (
                            selected_breed_id is None
                            and len(buttons.children) > 0
                            and hasattr(buttons.children[0], "values")
                            and buttons.children[0].values
                        ):
                            selected_breed_id = buttons.children[0].values[0]

                        api_url = (
                            "https://api.thecatapi.com/v1/images/search?has_breeds=1"
                        )
                        if selected_breed_id:
                            api_url += f"&breed_ids={selected_breed_id}"

                        async with self.session.get(
                            api_url, headers=self.cat_headers
                        ) as resp:
                            if resp.ok:
                                new_data = await resp.json()
                                if (
                                    new_data
                                    and "breeds" in new_data[0]
                                    and new_data[0]["breeds"]
                                ):
                                    new_breed = new_data[0]["breeds"][0]

                                    for field_name, idx in field_order:
                                        if (
                                            field_name == "title"
                                            and "name" in new_breed
                                        ):
                                            container.children[idx].content = (
                                                f"### {new_breed['name']}"
                                            )
                                        elif (
                                            field_name == "origin"
                                            and "origin" in new_breed
                                        ):
                                            container.children[idx].content = (
                                                f"**Origin**\n{new_breed['origin']}"
                                            )
                                        elif (
                                            field_name == "temperament"
                                            and "temperament" in new_breed
                                        ):
                                            container.children[idx].content = (
                                                f"**Temperament**\n{new_breed['temperament']}"
                                            )
                                        elif (
                                            field_name == "life_span"
                                            and "life_span" in new_breed
                                        ):
                                            container.children[idx].content = (
                                                f"**Life Span**\n{new_breed['life_span']} years"
                                            )
                                        elif (
                                            field_name == "weight"
                                            and "weight" in new_breed
                                            and "metric" in new_breed["weight"]
                                        ):
                                            container.children[idx].content = (
                                                f"**Weight**\n{new_breed['weight']['metric']} kg"
                                            )
                                        elif (
                                            field_name == "description"
                                            and "description" in new_breed
                                        ):
                                            container.children[idx].content = (
                                                f"*{new_breed['description']}*"
                                            )

                                    if (
                                        "url" in new_data[0]
                                        and hasattr(view, "media_gallery")
                                        and view.media_gallery is not None
                                    ):
                                        view.media_gallery.items = [
                                            discord.MediaGalleryItem(
                                                media=new_data[0]["url"]
                                            )
                                        ]

                                    if (
                                        "wikipedia_url" in new_breed
                                        and len(container.children) > 1
                                        and len(container.children[-1].children) > 1
                                    ):
                                        wiki_button = container.children[-1].children[1]
                                        if hasattr(wiki_button, "url"):
                                            wiki_button.url = new_breed["wikipedia_url"]

                    except Exception as e:
                        import traceback

                        error_msg = f"Error in catfact button callback: {str(e)}\ntraceback:\n{traceback.format_exc()}"
                        print(error_msg)
                        await interaction.response.send_message(
                            "An error occurred while fetching cat information. Please try again.",
                            ephemeral=True,
                        )

                    finally:
                        if buttons.children and len(buttons.children) > 0:
                            buttons.children[0].disabled = False
                            buttons.children[0].label = "Get Another Cat"

                        if len(action_row1.children) > 0:
                            action_row1.children[0].disabled = False

                        await interaction.edit_original_response(view=view)

                if buttons.children and len(buttons.children) > 0:
                    buttons.children[0].callback = button_callback

                if len(action_row1.children) > 0:
                    action_row1.children[0].callback = button_callback

    @app_commands.command(
        name="caption", description="Add a caption to an image or GIF"
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.describe(
        image="The image to add a caption to",
        caption="The caption text to add to the image",
    )
    async def caption(
        self,
        interaction: discord.Interaction,
        image: discord.Attachment,
        *,
        caption: str,
    ):
        if not image.content_type.startswith(("image/png", "image/jpeg", "image/gif")):
            await interaction.response.send_message(
                "Please provide a valid image file (PNG, JPG, or GIF).", ephemeral=True
            )
            return

        await interaction.response.defer()

        try:
            image_data = await image.read()
            img = Image.open(io.BytesIO(image_data))

            try:
                font = ImageFont.truetype("Arial-Bold.ttf", 60)
            except IOError:
                try:
                    font = ImageFont.truetype("ArialBold.ttf", 60)
                except IOError:
                    try:
                        font = ImageFont.truetype("arialbd.ttf", 60)
                    except IOError:
                        try:
                            font = ImageFont.truetype("DejaVuSans-Bold.ttf", 60)
                        except IOError:
                            font = ImageFont.load_default(60)
                            if hasattr(font, "font_variant"):
                                font = font.font_variant(weight="bold")
            except Exception as e:
                font = ImageFont.load_default(60)

            max_text_width = min(img.width * 0.8, 600)

            def wrap_text(text, font, max_width):
                lines = []

                words = text.split(" ")

                if not words:
                    return lines

                draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))

                current_line = []
                current_width = 0

                for word in words:
                    word_bbox = draw.textbbox((0, 0), word, font=font)
                    word_width = word_bbox[2] - word_bbox[0]

                    if word_width > max_width:
                        if current_line:
                            lines.append(" ".join(current_line))
                            current_line = []
                            current_width = 0

                        chunk = ""
                        for char in word:
                            test_chunk = chunk + char
                            chunk_bbox = draw.textbbox((0, 0), test_chunk, font=font)
                            chunk_width = chunk_bbox[2] - chunk_bbox[0]

                            if chunk_width <= max_width:
                                chunk = test_chunk
                            else:
                                if chunk:
                                    lines.append(chunk)
                                chunk = char

                        if chunk:
                            current_line = [chunk]
                            current_bbox = draw.textbbox((0, 0), chunk, font=font)
                            current_width = current_bbox[2] - current_bbox[0]
                        continue

                    test_line = (
                        " ".join(current_line + [word]) if current_line else word
                    )
                    test_bbox = draw.textbbox((0, 0), test_line, font=font)
                    test_width = test_bbox[2] - test_bbox[0]

                    if test_width <= max_width:
                        current_line.append(word)
                        current_width = test_width
                    else:
                        if current_line:
                            lines.append(" ".join(current_line))
                        current_line = [word]
                        current_bbox = draw.textbbox((0, 0), word, font=font)
                        current_width = current_bbox[2] - current_bbox[0]

                if current_line:
                    lines.append(" ".join(current_line))

                return lines

            wrapped_lines = wrap_text(caption, font, max_text_width)

            line_height = font.getbbox("A")[3] - font.getbbox("A")[1]
            padding = 30
            line_spacing = 5

            text_block_height = (line_height * len(wrapped_lines)) + (
                line_spacing * max(0, len(wrapped_lines) - 1)
            )

            bar_height = max(text_block_height + (padding * 2), line_height * 3)

            y_start = (bar_height - text_block_height) // 3

            frames = []
            duration = []

            if not getattr(img, "is_animated", False):
                frames_to_process = [img.convert("RGBA")]
                duration = [100]
            else:
                frames_to_process = [
                    frame.copy().convert("RGBA")
                    for frame in ImageSequence.Iterator(img)
                ]
                duration = [img.info.get("duration", 100) for _ in frames_to_process]

            for frame in frames_to_process:
                new_frame = Image.new(
                    "RGBA", (img.width, img.height + int(bar_height)), "white"
                )

                if frame.width > max_text_width * 1.25:
                    ratio = (max_text_width * 1.25) / frame.width
                    new_width = int(frame.width * ratio)
                    new_height = int(frame.height * ratio)
                    frame = frame.resize((new_width, new_height), Image.LANCZOS)

                x_offset = (new_frame.width - frame.width) // 2
                new_frame.paste(frame, (x_offset, int(bar_height)), frame)

                draw = ImageDraw.Draw(new_frame)
                y_text = y_start

                for line in wrapped_lines:
                    bbox = draw.textbbox((0, 0), line, font=font)
                    text_width = bbox[2] - bbox[0]
                    x_text = (new_frame.width - text_width) // 2

                    draw.text(
                        (x_text, y_text),
                        line,
                        fill="black",
                        font=font,
                        stroke_width=2,
                        stroke_fill="white",
                    )
                    y_text += line_height + line_spacing

                frames.append(new_frame)

            output = io.BytesIO()
            frames[0].save(
                output,
                format="GIF",
                save_all=True,
                append_images=frames[1:],
                duration=duration,
                loop=0,
                optimize=True,
                save_transparency=True,
                disposal=2,
            )
            output.seek(0)

            file = discord.File(output, filename="captioned.gif")
            await interaction.followup.send(file=file)

        except Exception as e:
            await interaction.followup.send(
                f"An error occurred while processing the image: {str(e)}",
                ephemeral=True,
            )
            import traceback

            traceback.print_exc()

    @hybrid_group(name="water", description="Base command for water related commands")
    @app_commands.default_permissions(manage_guild=True)
    async def water(self, interaction: discord.Interaction):
        if interaction.invoked_subcommand is None:
            await interaction.send_help(self)

    @water.command(name="remove", description="Remove a water reminder")
    @app_commands.default_permissions(manage_guild=True)
    async def remove(
        self, ctx_or_interaction: Union[discord.Interaction, commands.Context]
    ):
        """Remove the water reminder for this server."""
        is_interaction = isinstance(ctx_or_interaction, discord.Interaction)

        if is_interaction:
            await ctx_or_interaction.response.defer()
            guild_id = ctx_or_interaction.guild_id
            send = ctx_or_interaction.followup.send
        else:
            guild_id = ctx_or_interaction.guild.id
            send = ctx_or_interaction.send

        await self.bot.db.execute("DELETE FROM water WHERE guild_id = $1", guild_id)

        if guild_id in self.water_reminders:
            if "task" in self.water_reminders[guild_id]:
                self.water_reminders[guild_id]["task"].cancel()
            del self.water_reminders[guild_id]

        await send("Water reminder has been removed.")

    @commands.Cog.listener()
    async def on_ready(self):
        """Initialize the database when the bot is ready."""
        self.initialize_db()
        if not hasattr(self, "water_reminders"):
            self.water_reminders = {}

        rows = await self.bot.db.fetch("SELECT * FROM water")
        for row in rows:
            self.water_reminders[row["guild_id"]] = {
                "channel_id": row["channel_id"],
                "delay": row["delay"],
                "task": self.bot.loop.create_task(
                    self.water_reminder_loop(row["guild_id"])
                ),
            }

    async def water_reminder_loop(self, guild_id: int):
        """Background task that sends water reminders at the configured interval."""
        try:
            while True:
                reminder = self.water_reminders.get(guild_id)
                if not reminder:
                    break

                channel = self.bot.get_channel(reminder["channel_id"])
                if channel:
                    try:
                        if guild_id == 1271976967381712989:
                            await channel.send(
                                "💧 <@459493651530252288> **It's time to drink water!**"
                            )
                        else:
                            await channel.send("💧 **It's time to drink water!**")
                    except Exception as e:
                        print(f"Failed to send water reminder in {guild_id}: {e}")

                await asyncio.sleep(reminder["delay"] * 60)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Error in water reminder loop for guild {guild_id}: {e}")

    @water.command(name="add", description="Add a water reminder")
    @app_commands.describe(
        channel="The channel to send the reminder to",
        delay="The delay between reminders in minutes",
    )
    @app_commands.default_permissions(manage_guild=True)
    async def add(
        self,
        ctx_or_interaction: Union[discord.Interaction, commands.Context],
        channel: discord.TextChannel,
        delay: int,
    ):
        """Add a water reminder with the specified interval in minutes."""
        is_interaction = isinstance(ctx_or_interaction, discord.Interaction)

        if is_interaction:
            await ctx_or_interaction.response.defer()
            guild_id = ctx_or_interaction.guild_id
            send = ctx_or_interaction.followup.send
        else:
            guild_id = ctx_or_interaction.guild.id
            send = ctx_or_interaction.send

        if delay < 1:
            return await send(
                "Delay must be at least 1 minute.", ephemeral=is_interaction
            )

        delay_minutes = delay if delay >= 1 else 1

        await self.bot.db.execute(
            """
            INSERT INTO water (guild_id, channel_id, delay)
            VALUES ($1, $2, $3)
            ON CONFLICT (guild_id) 
            DO UPDATE SET channel_id = $2, delay = $3
            """,
            guild_id,
            channel.id,
            delay_minutes,
        )

        if guild_id in self.water_reminders:
            self.water_reminders[guild_id]["task"].cancel()

        self.water_reminders[guild_id] = {
            "channel_id": channel.id,
            "delay": delay_minutes,
            "task": self.bot.loop.create_task(self.water_reminder_loop(guild_id)),
        }

        time_unit = "minute" if delay_minutes == 1 else "minutes"
        message = f"Water reminder set in {channel.mention} every {delay_minutes} {time_unit}."
        await send(message)

    @command(name="roast", aliases=["insult"], description="Roast a user.")
    @app_commands.describe(
        user="The user to roast.",
    )
    async def roast(self, ctx: Context, user: Optional[discord.User] = None) -> None:
        """Roast a user."""
        if user is None:
            await ctx.send("You trying to roast the fucking air you moron?")
            return
        async with ctx.typing():

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://insult.mattbas.org/api/insult?who={user.name}"
                ) as response:
                    if response.status != 200:
                        await ctx.send(
                            "Ion could not get a response from the insult API."
                        )
                        return

                    insult = await response.text()
                    await ctx.send(insult)

    @hybrid(name="randomfact", aliases=["fact"], description="Get a random fact.")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def randomfact(self, ctx: Context):
        async with ctx.typing():
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://uselessfacts.jsph.pl/api/v2/facts/random?language=en"
                ) as response:
                    if response.status != 200:
                        await ctx.send(
                            "Ion could not get a response from the fact API."
                        )
                        return

                    data = await response.json()
                    fact = data.get("text", "Could not fetch a fact at this time.")
                    await ctx.send(fact)

    @hybrid(name="carrot", description="carrot ok...?")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def carrot(self, ctx: Context):
        async with ctx.typing():
            await ctx.send("i gonna get a carrot...ok?")

    @hybrid(name="bunni", description="bunni bunni bunni bunni")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def bunni(self, ctx: Context):
        container = discord.ui.Container(
            discord.ui.TextDisplay(content="# bunni bunni bunni bunni bunni"),
            discord.ui.MediaGallery(
                discord.MediaGalleryItem(
                    media="https://media.playfairs.cc/assets/bunni.png",
                ),
            ),
        )
        view = discord.ui.LayoutView()
        view.add_item(container)
        await ctx.send(view=view)

    @hybrid(name="dumbassdog", description=" LFMOAOOAOAOAOAOAOOAOA")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def dumbassdog(self, ctx: Context):
        container = discord.ui.Container(
            discord.ui.MediaGallery(
                discord.MediaGalleryItem(
                    media="https://dumbassdog.com/dog.mp4",
                ),
            ),
        )
        view = discord.ui.LayoutView()
        view.add_item(container)
        await ctx.send(view=view)

    @hybrid(name="fih", description="fih")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def fih(self, ctx: Context):
        container = discord.ui.Container(
            discord.ui.MediaGallery(
                discord.MediaGalleryItem(
                    media="https://static2.klipy.com/ii/4493325008d34b7bf8cd6813cd5c1619/a0/a7/IcNHnHM8KQ8HjsiMbbC.gif",
                ),
            ),
        )
        view = discord.ui.LayoutView()
        view.add_item(container)
        await ctx.send(view=view)
