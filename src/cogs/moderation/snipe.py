import discord
from discord.ext import commands, tasks
from vortex import vortex

# this code was proudly created by a trans girly uwu


class Snipe:
    """
    Generate a db connection, called in moderation.py
    """

    def __init__(self, bot: vortex):
        self.database = bot.db
        self.bot = bot
        self.bot.loop.create_task(self.setup_tables())
        self.bot.add_listener(self.on_message_delete, "on_message_delete")
        self.bot.add_listener(self.on_message_edit, "on_message_edit")
        self.bot.add_listener(self.on_reaction_remove, "on_reaction_remove")
        self.clear.start()

    async def setup_tables(self):
        async with self.database.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS deleted (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT,
                user_id BIGINT,
                channel_id BIGINT,
                message TEXT,
                reply BIGINT DEFAULT NULL,
                attachments TEXT DEFAULT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS edited (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT,
                user_id BIGINT,
                channel_id BIGINT,
                before TEXT,
                after TEXT,
                reply BIGINT DEFAULT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS reactions (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT,
                user_id BIGINT,
                channel_id BIGINT,
                reaction TEXT,
                message BIGINT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
            )

    @tasks.loop(seconds=30)
    async def clear(self):
        async with self.database.acquire() as conn:
            await conn.execute(
                "DELETE FROM deleted WHERE timestamp < NOW() - INTERVAL '2 hours'"
            )
            await conn.execute(
                "DELETE FROM edited WHERE timestamp < NOW() - INTERVAL '2 hours'"
            )
            await conn.execute(
                "DELETE FROM reactions WHERE timestamp < NOW() - INTERVAL '2 hours'"
            )

    async def clearsnipe(self, ctx):
        try:
            async with self.database.acquire() as conn:
                await conn.execute(
                    "DELETE FROM deleted WHERE guild_id = $1", ctx.guild.id
                )
                await conn.execute(
                    "DELETE FROM edited WHERE guild_id = $1", ctx.guild.id
                )
                await conn.execute(
                    "DELETE FROM reactions WHERE guild_id = $1", ctx.guild.id
                )
            return True
        except:
            return False

    async def snipe(self, ctx):
        async with self.database.acquire() as conn:
            result = await conn.fetch(
                "SELECT * FROM deleted WHERE guild_id = $1 AND channel_id = $2 ORDER BY id DESC",
                ctx.guild.id,
                ctx.channel.id,
            )
            if not result:
                return None
            return result

    async def editsnipe(self, ctx, index=0):
        async with self.database.acquire() as conn:
            result = await conn.fetch(
                "SELECT * FROM edited WHERE guild_id = $1 AND channel_id = $2 ORDER BY id DESC",
                ctx.guild.id,
                ctx.channel.id,
            )
            if not result:
                return None
            return result

    async def reactsnipe(self, ctx, index=0):
        async with self.database.acquire() as conn:
            result = await conn.fetch(
                "SELECT * FROM reactions WHERE guild_id = $1 AND channel_id = $2 ORDER BY id DESC",
                ctx.guild.id,
                ctx.channel.id,
            )
            if not result:
                return None
            return result

    # listeners

    async def on_message_delete(self, message):
        if message.author.bot or not message.guild:
            return
        attachments = (
            None
            if not message.attachments
            else [attachment.url for attachment in message.attachments]
        )
        async with self.database.acquire() as conn:
            await conn.execute(
                "INSERT INTO deleted (guild_id, user_id, channel_id, message, reply, attachments) VALUES ($1, $2, $3, $4, $5, $6)",
                message.guild.id,
                message.author.id,
                message.channel.id,
                message.content,
                message.reference.message_id if message.reference else None,
                str(attachments),
            )
            # print(await conn.fetch("SELECT * FROM deleted WHERE guild_id = $1 AND channel_id = $2", message.guild.id, message.channel.id))

    async def on_message_edit(self, before, after):
        if before.author.bot or before.guild is None:
            return
        async with self.database.acquire() as conn:
            await conn.execute(
                "INSERT INTO edited (guild_id, user_id, channel_id, before, after, reply) VALUES ($1, $2, $3, $4, $5, $6)",
                before.guild.id,
                before.author.id,
                before.channel.id,
                before.content,
                after.content,
                before.reference.message_id if before.reference else None,
            )

    async def on_reaction_remove(self, reaction: discord.Reaction, user):
        if user.bot or reaction.message.guild is None:
            return

        emoji = reaction.emoji
        if isinstance(emoji, discord.Emoji):
            if not emoji.is_usable():
                return
            emoji_str = str(emoji)
        else:
            emoji_str = str(emoji)

        async with self.database.acquire() as conn:
            await conn.execute(
                "INSERT INTO reactions (guild_id, user_id, channel_id, reaction, message) VALUES ($1, $2, $3, $4, $5)",
                reaction.message.guild.id,
                user.id,
                reaction.message.channel.id,
                emoji_str,
                reaction.message.id,
            )
