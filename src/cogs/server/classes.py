# from discord import app_commands
# from discord.ext import commands
# from discord.ext.commands import Context, Cog
# from discord.ui import View, Button

# from vortex import vortex
# from config import BUTTONS
# from typing import Optional, Union

# class ServerConfig(Cog, view=View):
#     def __init__(self, bot: vortex):
#         self.bot = bot
#         self.server_config = None

#     async def setup(self):
#         async with self.bot.db.acquire() as conn:
#             await conn.execute("""
#                 CREATE TABLE IF NOT EXISTS server_config (
#                     guild_id BIGINT PRIMARY KEY,
#                     prefix TEXT NOT NULL,
#                     language TEXT NOT NULL,
#                     modlog_channel_id BIGINT,
#                     joinlog_channel_id BIGINT,
#                     leave_channel_id BIGINT,
#                     welcome_message TEXT,
#                     leave_message TEXT
#                 )
#             """)

#     async def check_table(self):
#         async with self.bot.db.acquire() as conn:
#             result = await conn.fetchval("""
#                 SELECT EXISTS (
#                     SELECT 1 FROM information_schema.tables
#                     WHERE table_name = 'server_config'
#                 )
#             """)
#             if not result:
#                 await self.setup()

#     async def get_config(self, guild_id: int) -> Optional[dict]:
#         async with self.bot.db.acquire() as conn:
#             result = await conn.fetchrow("""
#                 SELECT * FROM server_config
#                 WHERE guild_id = $1
#             """, guild_id)
#             return result

#     async def update_config(self, guild_id: int, **kwargs):
#         async with self.bot.db.acquire() as conn:
#             await conn.execute("""
#                 UPDATE server_config
#                 SET $set
#                 WHERE guild_id = $1
#             """, **kwargs, guild_id=guild_id)

#     async def delete_config(self, guild_id: int):
#         async with self.bot.db.acquire() as conn:
#             await conn.execute("""
#                 DELETE FROM server_config
#                 WHERE guild_id = $1
#             """, guild_id)

#     async def add_config(self, guild_id: int, **kwargs):
#         async with self.bot.db.acquire() as conn:
#             await conn.execute("""
#                 INSERT INTO server_config (guild_id, $set)
#                 VALUES ($1, $2)
#             """, guild_id, **kwargs)

#     async def prefix(self, guild_id: int, prefix: str):
#         async with self.bot.db.acquire() as conn:
#             await conn.execute("""
#                 UPDATE server_config
#                 SET prefix = $2
#                 WHERE guild_id = $1
#             """, guild_id, prefix)

#     async def cog_load(self):
#         await self.check_table()

# class ModlogsEmbed(Cog, view=View):
#     def __init__(self, bot: vortex):
#         self.bot = bot
#         self.modlogs = None

#     @Cog.listener()
#     async def on_member_update(self, before, after):
#         if before.nick != after.nick:
#             embed = discord.Embed(title="**Member Update**", color=discord.Color(0xffffff))
#             embed.add_field(name="**Responsible:**", value=f"{after.guild.me.mention} ({after.guild.me.id})")
#             embed.add_field(name="**Target:**", value=f"{after.mention} ({after.id})")
#             embed.add_field(name="*Time:*", value="*{0}*".format(after.joined_at.strftime('%A, %b %d, %Y %I:%M %p')))
#             embed.add_field(name="**Changes**", value=f"> **Nick:** \n> {before.nick or 'None'} --> {after.nick or 'None'}", inline=False)
#             await self.send_log(after.guild.id, embed)

#         if before.roles != after.roles:
#             added_roles = [role for role in after.roles if role not in before.roles]
#             removed_roles = [role for role in before.roles if role not in after.roles]

#             if added_roles or removed_roles:
#                 entry = await after.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_role_update).find(lambda e: e.target.id == after.id)
#                 responsible_user = entry.user if entry else after.guild.me

#                 embed = discord.Embed(title="**Member Role Update**", color=discord.Color(0xffffff))
#                 embed.add_field(name="**Responsible:**", value=f"{responsible_user.mention} ({responsible_user.id})", inline=True)
#                 embed.add_field(name="**Target:**", value=f"{after.mention} ({after.id})", inline=True)
#                 embed.add_field(name="", value=f"*{discord.utils.utcnow().strftime('%A, %B %d, %Y at %I:%M %p')}*", inline=False)

#                 changes = ""
#                 if added_roles:
#                     changes += f"**{BUTTONS.CUSTOM_EMOJIS['right']} Additions:**\n" + "\n".join([f"{role.mention}" for role in added_roles])
#                 if removed_roles:
#                     if added_roles:
#                         changes += "\n\n"
#                     changes += f"**{BUTTONS.CUSTOM_EMOJIS['right']} Removals:**\n" + "\n".join([f"{role.mention}" for role in removed_roles])

#                 embed.add_field(name="Changes", value=changes, inline=False)
#                 await self.send_log(after.guild.id, embed)

#     @Cog.listener()
#     async def on_message_delete(self, message):
#         if message.author.bot:
#             return

#         embed = discord.Embed(title="**Message Deleted**", color=discord.Color(0xffffff))
#         embed.set_author(name=message.author.display_name, icon_url=message.author.avatar.url)
#         embed.add_field(name="Message sent by", value=message.author.mention)
#         embed.add_field(name="Deleted in", value=message.channel.mention)
#         embed.add_field(
#             name="Content",
#             value=f"```diff\n- {message.content}\n```" if message.content else "No content available",
#             inline=False
#         )
#         embed.add_field(name="Author ID", value=f"{message.author.id} | Message ID: {message.id}")
#         await self.send_log(message.guild.id, embed)

#     @Cog.listener()
#     async def on_bulk_message_delete(self, messages):
#         if len(messages) == 0:
#             return
#         channel = messages[0].channel
#         embed = discord.Embed(title="**Bulk Delete**", color=discord.Color(0xffffff))
#         embed.add_field(name="Bulk Delete in", value=f"{channel.mention}, {len(messages)} messages deleted")
#         embed.add_field(name="*Time:*", value="*{0}*".format(discord.utils.utcnow().strftime('%A, %b %d, %Y %I:%M %p')))
#         await self.send_log(channel.guild.id, embed)

#     @Cog.listener()
#     async def on_message_edit(self, before, after):
#         if before.content != after.content:
#             embed = discord.Embed(title="**Message Edited**", color=discord.Color(0xffffff))
#             embed.set_author(name=before.author.display_name, icon_url=before.author.avatar.url)
#             embed.add_field(name="Message Edited in", value=f"{before.channel.mention} [Jump to Message]({before.jump_url})")
#             embed.add_field(name="**Before:**", value=f"*{before.content}*", inline=False)
#             embed.add_field(name="**After:**", value=f"*{after.content}*", inline=False)
#             embed.add_field(name="User ID", value=f"{before.author.id}")
#             await self.send_log(before.guild.id, embed)

#     @Cog.listener()
#     async def on_member_ban(self, guild, user):
#         async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
#             if entry.target.id == user.id:
#                 responsible_user = entry.user
#                 reason = entry.reason or "No reason provided"
#                 break
#         else:
#             responsible_user = guild.me
#             reason = "No reason found"

#         embed = discord.Embed(title="**Member Ban Add**", color=discord.Color(0xffffff))
#         embed.add_field(name="**Responsible:**", value=f"{responsible_user.mention} ({responsible_user.id})")
#         embed.add_field(name="**Target:**", value=f"{user.mention} ({user.id})")
#         embed.add_field(name="*Time:*", value="*{0}*".format(discord.utils.utcnow().strftime('%A, %b %d, %Y %I:%M %p')))
#         embed.add_field(name="**Reason:**", value=reason, inline=False)
#         await self.send_log(guild.id, embed)

#     @Cog.listener()
#     async def on_guild_role_create(self, role):
#         async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_create):
#             if entry.target.id == role.id:
#                 responsible_user = entry.user
#                 break
#         else:
#             responsible_user = role.guild.me

#         embed = discord.Embed(title="**Role Created**", color=discord.Color(0xffffff))
#         embed.add_field(name="**Responsible:**", value=f"{responsible_user.mention} ({responsible_user.id})")
#         embed.add_field(name="**Role Name:**", value=role.mention)
#         embed.add_field(name="*Time:*", value="*{0}*".format(discord.utils.utcnow().strftime('%A, %b %d, %Y %I:%M %p')))

#         permissions = []
#         for perm, value in role.permissions:
#             if value:
#                 permissions.append(f"{perm.replace('_', ' ').title()}")

#         role_details = (
#             f"**Color:** {role.color}\n"
#             f"**Hoisted:** {'Yes' if role.hoist else 'No'}\n"
#             f"**Mentionable:** {'Yes' if role.mentionable else 'No'}\n"
#             f"**Position:** {role.position}\n"
#             f"**ID:** {role.id}"
#         )

#         embed.add_field(name="**Role Details**", value=role_details, inline=False)

#         if permissions:
#             perm_chunks = [permissions[i:i + 15] for i in range(0, len(permissions), 15)]
#             for i, chunk in enumerate(perm_chunks):
#                 embed.add_field(
#                     name=f"**Permissions {i+1}**" if i > 0 else "**Permissions**",
#                     value="\n".join(chunk),
#                     inline=False
#                 )

#         await self.send_log(role.guild.id, embed)

#     @Cog.listener()
#     async def on_guild_update(self, before, after):
#         async for entry in after.audit_logs(limit=1, action=discord.AuditLogAction.guild_update):
#             responsible_user = entry.user
#             break
#         else:
#             responsible_user = after.me

#         embed = discord.Embed(title="**Guild Update**", color=discord.Color(0xffffff))
#         embed.add_field(name="**Responsible:**", value=f"{responsible_user.mention} ({responsible_user.id})")
#         embed.add_field(name="*Time:*", value="*{0}*".format(discord.utils.utcnow().strftime('%A, %b %d, %Y %I:%M %p')))

#         changes = []

#         if before.name != after.name:
#             changes.append(f"**Name:** {before.name} → {after.name}")

#         if before.icon != after.icon:
#             if after.icon:
#                 icon_data = await after.icon.read()
#                 icon_b64 = base64.b64encode(icon_data).decode('utf-8')
#                 changes.append(f"**Server Icon:** ```bash\n[Prev → [{icon_b64[:32]}...]```")
#             else:
#                 changes.append(f"**Server Icon:** ```bash\n[Prev] → [Reset]```")

#         if before.banner != after.banner:
#             if after.banner:
#                 banner_data = await after.banner.read()
#                 banner_hash = hash(banner_data)
#                 changes.append(f"**Server Banner:** ```bash\n[Prev] → [{banner_hash}]```")
#             else:
#                 changes.append(f"**Server Banner:** ```bash\n[Prev] → [Reset]```")

#         if before.afk_channel != after.afk_channel:
#             changes.append(f"**AFK Channel:** {before.afk_channel} → {after.afk_channel}")

#         if before.afk_timeout != after.afk_timeout:
#             changes.append(f"**AFK Timeout:** {before.afk_timeout}s → {after.afk_timeout}s")

#         if before.verification_level != after.verification_level:
#             changes.append(f"**Verification Level:** {before.verification_level} → {after.verification_level}")

#         if before.explicit_content_filter != after.explicit_content_filter:
#             changes.append(f"**Content Filter:** {before.explicit_content_filter} → {after.explicit_content_filter}")

#         if before.system_channel != after.system_channel:
#             changes.append(f"**System Channel:** {before.system_channel} → {after.system_channel}")

#         if changes:
#             embed.add_field(name="**Changes**", value="\n".join(changes), inline=False)
#             await self.send_log(after.id, embed)
