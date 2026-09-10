# from discord.ext.commands import Cog
# from discord.ext import tasks
# from vortex import vortex
# import sqlite3
# import discord
# import os


# class UtilityListeners(Cog):
#     def __init__(self, bot: vortex):
#         self.bot = bot
#         self.initialize_db()

#     def initialize_db(self):
#         if not os.path.exists("db"):
#             os.makedirs("db")

#         conn = sqlite3.connect('db/afk_users.db')
#         cursor = conn.cursor()
#         cursor.execute('''CREATE TABLE IF NOT EXISTS afk_users (
#             user_id INTEGER PRIMARY KEY,
#             reason TEXT,
#             afk_time INTEGER
#         )''')
#         conn.commit()
#         conn.close()

#     @Cog.listener('on_message')
#     async def afk_listener1(self, message):
#         if message.author.bot or message.webhook_id is not None:
#             return

#         ctx = await self.bot.get_context(message)
#         if ctx.valid:
#             print(f"[AFK Debug] Ignoring AFK removal for command: {message.content}")
#             return

#         afk_data = self.get_afk_status(message.author.id)

#         if afk_data:
#             print(f"[AFK Debug] Removing AFK for user: {message.author.id} due to manual message.")
#             self.remove_afk(message.author.id)

#             embed = discord.Embed(
#                 description=f"<a:FlutterWave:1325184569447678049> {message.author.mention}: Welcome back, you were AFK for `{self.format_time_ago(afk_data[1])}`.",
#                 color=discord.Color(0xffffff)
#             )
#             await ctx.reply(embed=embed, delete_after=120)

#         for mentioned_user in message.mentions:
#             afk_data = self.get_afk_status(mentioned_user.id)
#             if afk_data:
#                 reason, afk_time = afk_data
#                 embed = discord.Embed(
#                     description=f"{mentioned_user.mention} went AFK `{self.format_time_ago(afk_time)}`: **{reason}**",
#                     color=discord.Color(0xffffff)
#                 )
#                 await ctx.reply(embed=embed)

#     @Cog.listener('on_message_edit')
#     async def afk_listener2(self, before, after):
#         afk_data = self.get_afk_status(before.author.id)
#         if afk_data:
#             embed = discord.Embed(
#                 description=f"{before.author.mention} edited a message, but is still AFK: **{afk_data[0]}**.",
#                 color=discord.Color(0xffffff)
#             )
#             await after.channel.send(embed=embed)

#     @Cog.listener('on_message_delete')
#     async def afk_listener3(self, message):
#         if message.author.bot:
#             return

#         afk_data = self.get_afk_status(message.author.id)
#         if afk_data:
#             embed = discord.Embed(
#                 description=f"{message.author.mention} deleted a message, but is still AFK: **{afk_data[0]}**.",
#                 color=discord.Color(0xffffff)
#             )
#             await message.channel.send(embed=embed)

#         if message.author.id == self.bot.user.id:
#             self.remove_afk(self.bot.user.id)
#             await message.channel.send(f"{self.bot.user.mention} was AFK, removing AFK as this shouldn't be possible.")
