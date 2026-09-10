# import discord
# from discord.ext import commands
# from discord.ext.commands import Cog, command, group, has_permissions
# import random
# import sqlite3  # Leave this here until all sqlite3 is converted to asyncpg
# import asyncpg
# import os
# import asyncio
# import json
# import re
# import aiohttp
# from datetime import datetime, timedelta
# from config import DISCORD

# from vortex import vortex


# class Reactions(Cog, description="View commands in Reactions."):
#     def __init__(self, bot: vortex):
#         self.bot = bot
#         self.custom_reactions = {}
#         self.skull_targets = set()
#         self.auto_react_targets = {}
#         self.responses = {}
#         self.secondary_responses = {}

#         self.db_path = "reactions.db"
#         self.postgres_uri = os.getenv("POSTGRES_URI")
#         self.developer_id = DISCORD.DEVELOPER_ID

#     async def setup_database(self):
#         """Initialize the PostgreSQL database for reactions"""
#         try:
#             conn = await asyncpg.connect(self.postgres_uri)
#             await conn.execute('''
#                 CREATE TABLE IF NOT EXISTS skull_targets (
#                     user_id BIGINT PRIMARY KEY
#                 );
#             ''')
#             await conn.execute('''
#                 CREATE TABLE IF NOT EXISTS auto_react_targets (
#                     user_id BIGINT,
#                     emoji TEXT,
#                     PRIMARY KEY (user_id, emoji)
#                 );
#             ''')
#             await conn.execute('''
#                 CREATE TABLE IF NOT EXISTS custom_reactions (
#                     trigger TEXT PRIMARY KEY,
#                     reaction TEXT
#                 );
#             ''')
#             await conn.close()
#         except asyncpg.PostgresError as e:
#             print(f"Database setup error: {e}")

#     async def load_data(self):
#         """Load reaction data from the database"""
#         try:
#             conn = await asyncpg.connect(self.postgres_uri)

#             skull_target = await conn.fetchval("SELECT user_id FROM skull_targets")
#             self.skull_targets = set([skull_target]) if skull_target else set()

#             self.auto_react_targets = {}
#             rows = await conn.fetch("SELECT user_id, emoji FROM auto_react_targets")
#             for user_id, emoji in rows:
#                 if user_id not in self.auto_react_targets:
#                     self.auto_react_targets[user_id] = []
#                 self.auto_react_targets[user_id].append(emoji)

#             custom_reactions = await conn.fetch("SELECT trigger, reaction FROM custom_reactions")
#             self.custom_reactions = dict(custom_reactions) if custom_reactions else {}

#             await conn.close()
#         except asyncpg.PostgresError as e:
#             print(f"Data loading error: {e}")
#             self.skull_targets = set()
#             self.auto_react_targets = {}
#             self.custom_reactions = {}

#     async def cog_load(self):
#         """Called when the cog is loaded"""
#         await self.setup_database()
#         await self.load_data()

#     @Cog.listener()
#     async def on_message(self, message):
#         if message.author.id != self.developer_id:
#             if message.content.lower() in [
#                 "im playfairs",
#                 "im playfair",
#                 "i am playfair",
#                 "i am playfairs",
#             ]:
#                 await message.channel.send("no you're not")

#         self.conversation_context = {}

#         self.bot_responders = {}

#         print("Responses Initialized:", self.bot_responders)

#     async def add_response(self, ctx, args):
#         """Add a new autoresponse."""
#         if "," in args:
#             keyword, response = map(str.strip, args.split(",", 1))
#             if keyword and response:
#                 guild_id = ctx.guild.id
#                 if guild_id not in self.responses:
#                     self.responses[guild_id] = {}
#                 self.responses[guild_id][keyword.lower()] = response

#                 embed = discord.Embed(
#                     title="Autoresponse Added",
#                     description=f"Keyword: `{keyword}`\nResponse: `{response}`",
#                     color=discord.Color(0xFFFFFF),
#                 )
#                 await ctx.send(embed=embed)
#             else:
#                 await self.send_error(ctx, "Keyword and response cannot be empty.")
#         else:
#             await self.send_error(
#                 ctx, "Invalid syntax. Usage: `,autoresponder add <keyword> <response>`."
#             )

#     async def remove_response(self, ctx, args):
#         """Remove an autoresponse."""
#         keyword = args.strip()
#         guild_id = ctx.guild.id

#         if guild_id in self.responses and keyword in self.responses[guild_id]:
#             del self.responses[guild_id][keyword]
#             embed = discord.Embed(
#                 title="Autoresponse Removed",
#                 description=f"Keyword: `{keyword}` has been removed.",
#                 color=discord.Color(0xFFFFFF),
#             )
#             await ctx.send(embed=embed)
#         else:
#             await self.send_error(
#                 ctx, f"No autoresponse found for keyword: `{keyword}`."
#             )

#     async def send_error(self, ctx, message):
#         """Send an error message in an embed."""
#         embed = discord.Embed(
#             title="Error", description=message, color=discord.Color(0xFFFFFF)
#         )
#         await ctx.send(embed=embed)

#     async def send_help(self, ctx):
#         """Send help information for the autoresponder command."""
#         embed = discord.Embed(
#             title="Autoresponder Help",
#             description="Manage autoresponses for your server.",
#             color=discord.Color(0xFFFFFF),
#         )
#         embed.add_field(
#             name="Add Response",
#             value="Usage: `,autoresponder add <keyword> <response>`",
#             inline=False,
#         )
#         embed.add_field(
#             name="Remove Response",
#             value="Usage: `,autoresponder remove <keyword>`",
#             inline=False,
#         )
#         embed.add_field(name="Permissions", value="Administrator", inline=False)
#         await ctx.send(embed=embed)

#     @command()
#     async def skull(self, ctx: commands.Context, user: discord.Member):
#         """Toggles the skull reaction targeting for a user."""
#         if user.id in self.skull_targets:
#             self.skull_targets.remove(user.id)
#             embed = discord.Embed(
#                 title="Skull Reaction Target Removed",
#                 description=f"{user.mention} will no longer receive a 💀 reaction.",
#                 color=discord.Color(0xFFFFFF),
#             )
#             await ctx.send(embed=embed)

#             conn = await asyncpg.connect(self.postgres_uri)
#             await conn.execute(
#                 "DELETE FROM skull_targets WHERE user_id = ?", (user.id,)
#             )
#             await conn.close()
#         else:
#             self.skull_targets.add(user.id)
#             embed = discord.Embed(
#                 title="Skull Reaction Targeted",
#                 description=f"{user.mention} will receive a 💀 reaction whenever they send a message.",
#                 color=discord.Color(0xFFFFFF),
#             )
#             await ctx.send(embed=embed)

#             conn = await asyncpg.connect(self.postgres_uri)
#             await conn.execute(
#                 "INSERT OR IGNORE INTO skull_targets (user_id) VALUES (?)", (user.id,)
#             )
#             await conn.close()

#     @command()
#     async def skullreset(self, ctx: commands.Context):
#         """Resets all users targeted by the skull command."""
#         self.skull_targets.clear()

#         embed = discord.Embed(
#             title="Skull Targets Reset",
#             description="All skull targets have been reset.",
#             color=discord.Color(0xFFFFFF),
#         )
#         await ctx.send(embed=embed)

#         conn = await asyncpg.connect(self.postgres_uri)
#         await conn.execute("DELETE FROM skull_targets")
#         await conn.close()

#     @command(name="ar", aliases=["autoreactor, autoreaction, reactions"])
#     async def autoreact(self, ctx: commands.Context, user: discord.Member, *emojis):
#         """Sets up auto-react for a specified user with given emojis."""
#         if user.id not in self.auto_react_targets:
#             self.auto_react_targets[user.id] = []

#         self.auto_react_targets[user.id].extend(emojis)

#         embed = discord.Embed(
#             title="Auto-Reaction Set",
#             description=f"{user.mention} will receive reactions: {', '.join(emojis)}",
#             color=discord.Color(0xFFFFFF),
#         )
#         await ctx.send(embed=embed)

#         conn = await asyncpg.connect(self.postgres_uri)
#         await conn.execute(
#             "INSERT OR REPLACE INTO auto_react_targets (user_id, emoji) VALUES (?, ?)",
#             (user.id, ",".join(self.auto_react_targets[user.id])),
#         )
#         await conn.close()

#     @command(
#         name="arreset", aliases=["reactionsreset, removereactions, reactionsremove"]
#     )
#     async def auto_react_reset(self, ctx: commands.Context):
#         """Resets all auto-react settings."""
#         self.auto_react_targets.clear()

#         embed = discord.Embed(
#             title="Auto-Reactions Reset",
#             description="All auto-reaction settings have been reset.",
#             color=discord.Color(0xFFFFFF),
#         )
#         await ctx.send(embed=embed)

#         conn = await asyncpg.connect(self.postgres_uri)
#         await conn.execute("DELETE FROM auto_react_targets")
#         await conn.close()

#     @group(name="reaction", invoke_without_command=True)
#     async def reaction(self, ctx: commands.Context):
#         """Base command for custom reactions."""
#         await ctx.send("Available subcommands: `add`, `remove`, `reset`")

#     @reaction.command(name="add")
#     async def custom_word_add(self, ctx: commands.Context, word: str, emoji: str):
#         """Adds a custom word for auto-reaction."""
#         word_lower = word.lower()
#         self.custom_reactions[word_lower] = emoji

#         embed = discord.Embed(
#             title="Custom Reaction Added",
#             description=f"Now reacting to '{word}' with {emoji}",
#             color=discord.Color(0xFFFFFF),
#         )
#         await ctx.send(embed=embed)

#         conn = await asyncpg.connect(self.postgres_uri)
#         await conn.execute(
#             "INSERT OR REPLACE INTO custom_reactions (trigger, reaction) VALUES (?, ?)",
#             (word_lower, emoji),
#         )
#         await conn.close()

#     @reaction.command(name="remove")
#     async def custom_word_remove(self, ctx: commands.Context, word: str):
#         """Removes a custom word for auto-reaction."""
#         word_lower = word.lower()
#         if word_lower in self.custom_reactions:
#             del self.custom_reactions[word_lower]
#             embed = discord.Embed(
#                 title="Custom Reaction Removed",
#                 description=f"Removed reaction for the word '{word}'.",
#                 color=discord.Color(0xFFFFFF),
#             )
#             await ctx.send(embed=embed)

#             conn = await asyncpg.connect(self.postgres_uri)
#             await conn.execute("DELETE FROM custom_reactions WHERE trigger = ?", (word_lower,))
#             await conn.close()
#         else:
#             embed = discord.Embed(
#                 title="Word Not Found",
#                 description=f"There is no custom reaction for '{word}'.",
#                 color=discord.Color(0xFFFFFF),
#             )
#             await ctx.send(embed=embed)

#     @reaction.command(name="reset")
#     async def custom_word_reset(self, ctx: commands.Context):
#         """Resets all custom keyword reactions."""
#         self.custom_reactions.clear()

#         embed = discord.Embed(
#             title="Custom Reactions Reset",
#             description="All custom keyword reactions have been reset.",
#             color=discord.Color.green(),
#         )
#         await ctx.send(embed=embed)

#         conn = await asyncpg.connect(self.postgres_uri)
#         await conn.execute("DELETE FROM custom_reactions")
#         await conn.close()

#     @command(name="autoresponder")
#     @has_permissions(administrator=True)
#     async def autoresponder(self, ctx: commands.Context, action: str, *, args: str):
#         """Main command for managing autoresponses."""
#         if action.lower() == "add":
#             await self.add_response(ctx, args)
#         elif action.lower() == "remove":
#             await self.remove_response(ctx, args)
#         else:
#             await self.send_help(ctx)

#     @Cog.listener()
#     async def on_message(self, message):
#         """Handle automatic reactions and responses"""
#         if message.author.bot or not message.guild:
#             return

#         content = message.content.lower()

#         try:
#             if message.author.id in self.skull_targets:
#                 await message.add_reaction("💀")

#             if "sob" in content or "😭" in content:
#                 await message.add_reaction("😭")

#             if "heresy" in content or "1291967026788831232" in content:
#                 await message.add_reaction("<:heresyicon:1338845590033006744>")

#             if "nova" in content or "1320964930387709973" in content:
#                 await message.add_reaction("<:nova:1320964930387709973>")

#             if "playfair" in content or "1276099010779942954" in content:
#                 await message.add_reaction("<:playfair:1276099010779942954>")

#             if "nigger" in content:
#                 await message.add_reaction("💀")

#             if "kys" in content or "kill yourself" in content:
#                 await message.add_reaction("💀")

#             for trigger, reaction in self.custom_reactions.items():
#                 if trigger.lower() in content:
#                     await message.add_reaction(reaction)

#             if message.author.id in self.auto_react_targets:
#                 for emoji in self.auto_react_targets[message.author.id]:
#                     await message.add_reaction(emoji)
#         except discord.HTTPException:
#             pass

#         for trigger, responses in self.responses.items():
#             trigger_lower = trigger.lower()

#             if trigger_lower in content:
#                 try:

#                     response = random.choice(responses)

#                     await message.reply(response)
#                 except Exception as e:
#                     print(f"Error sending response for trigger {trigger}: {e}")
#                 break

#         for trigger, secondary_responses in getattr(
#             self, "secondary_responses", {}
#         ).items():
#             trigger_lower = trigger.lower()

#             if trigger_lower in content:
#                 try:
#                     secondary_response = random.choice(secondary_responses)

#                     await message.reply(secondary_response)
#                 except Exception as e:
#                     print(
#                         f"Error sending secondary response for trigger {trigger}: {e}"
#                     )
#                 break

#         if (
#             message.author.id == 1252011606687350805
#             or message.author.id == 1265662059056463976
#             and message.content == "hwlp"
#         ):
#             await message.reply("<@1252011606687350805> https://www.grammarly.com")
#             print(f"Response sent for hwlp from user {message.author.id}")

#         if message.author.id == 757355424621133914 and message.content == "guess what":
#             await message.channel.send("chicken butt")
#             print(f"Response sent for guess what from user {message.author.id}")

#         if (
#             message.author.id == 757355424621133914
#             and message.content == "pocket pussy"
#         ):
#             await message.channel.send("stfu lina")
#             print(f"Response sent for pocket pussy from user {message.author.id}")

#         if (
#             message.author.id == self.bot.user.id
#             and message.content == "failed to fetch that post!"
#         ):
#             await message.channel.send("this is why I'm better <@1203514684326805524>")
#             print(
#                 f"Response sent for failed to fetch that post! from user {message.author.id}"
#             )

#     @Cog.listener()
#     async def on_message_skull_react(self, message):
#         """Listens for users that should receive a skull reaction."""
#         if message.author.id in self.skull_targets:
#             await message.add_reaction("💀")

#     @Cog.listener()
#     async def on_message_sob_react(self, message):
#         """Listens for messages that contain the word "sob" and reacts with a crying face."""
#         if message.content.lower() == "sob":
#             await message.add_reaction("😭")

#     @Cog.listener()
#     async def on_message_custom_react(self, message):
#         """Listens for messages that contain custom reaction keywords and reacts accordingly."""
#         if message.author == self.bot.user:
#             return

#         if any(keyword in message.content.lower() for keyword in self.custom_reactions):
#             await message.add_reaction(self.custom_reactions[next((keyword for keyword in self.custom_reactions if keyword in message.content.lower()), None)])

#     @Cog.listener()
#     async def on_message_auto_react(self, message):
#         """Listens for messages from users that have auto-reacts enabled and reacts with the specified emoji."""
#         if message.author == self.bot.user:
#             return

#         if message.author.id in self.auto_react_targets:
#             for emoji in self.auto_react_targets[message.author.id]:
#                 await message.add_reaction(emoji)

#     @Cog.listener()
#     async def on_message(self, message):
#         if message.author.id == 1265662059056463976 and message.content == "silencio":
#             await message.reply("los jalapeños están durmiendo")
