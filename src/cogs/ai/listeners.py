import discord
from discord.ext import commands
from discord.ext.commands import Cog, Context
import aiohttp
import os
import re
import io
from vortex import vortex
from .utils import get_ai_response
import random
import time
from config import BLACKLIST
import json
import asyncio


class AIListeners(Cog, description="View commands in AIListeners."):
    def __init__(self, bot: vortex):
        self.bot = bot
        self.image_cache = {}

    async def cog_load(self):
        await self.create_tables()

    async def create_tables(self):
        async with self.bot.db.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_context (
                                                          id SERIAL PRIMARY KEY,
                                                          channel_id BIGINT NOT NULL,
                                                          user_id BIGINT NOT NULL,
                                                          role TEXT NOT NULL,
                                                          content TEXT NOT NULL,
                                                          timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_ai_context_channel_user_time
                    ON ai_context (channel_id, user_id, timestamp)
                """
            )

            await conn.execute(
                """
                DROP TABLE IF EXISTS ai_active_conversations
                """
            )

            await conn.execute(
                """
                CREATE TABLE ai_active_conversations (
                                                         channel_id BIGINT NOT NULL,
                                                         user_id BIGINT NOT NULL,
                                                         last_activity TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                                                         PRIMARY KEY (channel_id, user_id)
                )
                """
            )

            await conn.execute(
                """
                DELETE FROM ai_context
                WHERE timestamp < NOW() - INTERVAL '1 hour'
                """
            )

            await conn.execute(
                """
                DELETE FROM ai_active_conversations
                WHERE last_activity < NOW() - INTERVAL '30 minutes'
                """
            )

    async def replace_mentions_with_names(self, message: discord.Message) -> str:
        """Replace user mentions with their usernames in the message content."""
        content = message.content

        for mention in message.mentions:
            content = content.replace(f"<@{mention.id}>", f"@{mention.name}")
            content = content.replace(f"<@!{mention.id}>", f"@{mention.name}")

        return content

    async def get_conversation_context(self, channel_id: int, user_id: int) -> list:
        """Get recent conversation context for a user in a channel (within last hour)."""
        async with self.bot.db.acquire() as conn:
            await conn.execute(
                """
                DELETE FROM ai_context
                WHERE timestamp < NOW() - INTERVAL '1 hour'
                """
            )

            rows = await conn.fetch(
                """
                SELECT role, content FROM ai_context
                WHERE channel_id = $1 AND user_id = $2
                  AND timestamp >= NOW() - INTERVAL '1 hour'
                ORDER BY timestamp ASC
                    LIMIT 500
                """,
                channel_id,
                user_id,
            )

            context = []
            for row in rows:
                content = row["content"]

                context.append({"role": row["role"], "content": content})

            return context

    async def save_conversation_context(
        self, channel_id: int, user_id: int, role: str, content: str
    ):
        """Save a message to conversation context."""
        async with self.bot.db.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO ai_context (channel_id, user_id, role, content)
                VALUES ($1, $2, $3, $4)
                """,
                channel_id,
                user_id,
                role,
                content,
            )

    async def has_active_conversation(self, channel_id: int, user_id: int) -> bool:
        """Check if a specific user has an active conversation in this channel."""
        async with self.bot.db.acquire() as conn:

            await conn.execute(
                """
                DELETE FROM ai_active_conversations
                WHERE last_activity < NOW() - INTERVAL '30 minutes'
                """
            )

            row = await conn.fetchrow(
                """
                SELECT 1 FROM ai_active_conversations
                WHERE channel_id = $1 AND user_id = $2
                """,
                channel_id,
                user_id,
            )

            return row is not None

    async def start_conversation(self, channel_id: int, user_id: int):
        """Start a new conversation or update existing one."""
        async with self.bot.db.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO ai_active_conversations (channel_id, user_id, last_activity)
                VALUES ($1, $2, CURRENT_TIMESTAMP)
                    ON CONFLICT (channel_id, user_id)
                DO UPDATE SET last_activity = CURRENT_TIMESTAMP
                """,
                channel_id,
                user_id,
            )

    async def update_conversation_activity(self, channel_id: int, user_id: int):
        """Update the last activity timestamp for an active conversation."""
        async with self.bot.db.acquire() as conn:
            await conn.execute(
                """
                UPDATE ai_active_conversations
                SET last_activity = CURRENT_TIMESTAMP
                WHERE channel_id = $1 AND user_id = $2
                """,
                channel_id,
                user_id,
            )

    async def is_reply_in_user_context(
        self, channel_id: int, user_id: int, replied_message_id: int
    ) -> bool:
        """Check if the replied-to message is within the user's conversation context."""
        async with self.bot.db.acquire() as conn:
            conversation_row = await conn.fetchrow(
                """
                SELECT last_activity FROM ai_active_conversations
                WHERE channel_id = $1 AND user_id = $2
                """,
                channel_id,
                user_id,
            )

            if not conversation_row:
                return False

            try:
                discord_epoch = 1420070400000
                timestamp_ms = (replied_message_id >> 22) + discord_epoch
                replied_message_time = timestamp_ms / 1000

                conversation_start = conversation_row["last_activity"].timestamp()

                buffer_seconds = 300
                return replied_message_time >= (conversation_start - buffer_seconds)

            except Exception as e:
                print(f"Error parsing message timestamp: {e}")
                row = await conn.fetchrow(
                    """
                    SELECT COUNT(*) as count FROM ai_context
                    WHERE channel_id = $1 AND user_id = $2
                      AND role = 'assistant'
                      AND timestamp >= NOW() - INTERVAL '30 minutes'
                    """,
                    channel_id,
                    user_id,
                )

                return row["count"] > 0 if row else False

    def contains_url_or_encoding(self, text, is_enabled):
        if len(text) < 10:
            return False

        if (
            re.search(r"\.onion(?:/|\s|$)", text, re.IGNORECASE)
            or re.search(
                r"\b(?:send|give|find|get|share|provide|want|need|looking for|where can i find|how to access|how do i (?:get|find|access))\b.*\b(onion(?:\s+link)?|tor(?:\s+link)?|dark\s*web|hidden\s*service)",
                text,
                re.IGNORECASE,
            )
        ) and is_enabled:
            return True

        if (
            re.search(
                r"\b(?:decode|encode|decrypt|encrypt|base64|hex|binary|url[\s-]*(?:encode|decode)|convert (?:to|from) (?:base64|hex|binary))\s+(?:me|a|an|the|this|that|it|link|url)",
                text,
                re.IGNORECASE,
            )
            and is_enabled
        ):
            return True

        if (
            re.search(
                r'\b(?:https?:|www\.|ftp://|http://|https://|www\d*\.)[^\s\]\[\(\)\{\}<>"]+',
                text,
                re.IGNORECASE,
            )
            and is_enabled
        ):
            return True

        hex_url = re.sub(r"[^0-9a-fA-F]", "", text)
        if len(hex_url) >= 16 and is_enabled:
            try:
                decoded = bytes.fromhex(hex_url).decode("utf-8", errors="ignore")
                if (
                    re.search(r"(?:https?:|www\.|/|\.[a-z]{2,})", decoded)
                    and is_enabled
                ):
                    return True
            except:
                pass

        b64_match = re.search(r"[A-Za-z0-9+/=]{20,}", text)
        if b64_match and is_enabled:
            import base64

            try:
                decoded = base64.b64decode(b64_match.group(0) + "===").decode(
                    "utf-8", errors="ignore"
                )
                if (
                    re.search(r"(?:https?:|www\.|/|\.[a-z]{2,})", decoded)
                    and is_enabled
                ):
                    return True
            except:
                pass

        if (
            re.search(r"(?:^|\s)(?:[a-zA-Z0-9]\s*[\/\\]\s*){3,}[a-zA-Z0-9]", text)
            and is_enabled
        ):
            normalized = re.sub(r"[\s\\/]+", "", text)
            if re.search(r"\.[a-z]{2,}", normalized, re.IGNORECASE) and is_enabled:
                return True

        if (
            re.search(
                r"\b(?:[a-z0-9][^a-z0-9]*){2,}\.[a-z][^a-z]*[a-z](?:[^a-z]*[a-z][^a-z]*[a-z])?",
                text,
                re.IGNORECASE,
            )
            and is_enabled
        ):
            if (
                re.search(r"\.[a-z]{2,}[^a-z]*(?:/|$)", text, re.IGNORECASE)
                and is_enabled
            ):
                return True

        if re.search(r"\.onion(?:/|\s|$)", text, re.IGNORECASE) and is_enabled:
            return True

        return False

    @Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle incoming messages and check if they need an AI response."""
        if message.author.bot or not message.content or not message.guild:
            return

        ai_cog = self.bot.get_cog("AICommands")
        if not ai_cog:
            return

        is_enabled, is_channel_specific = await ai_cog.is_ai_enabled(
            message.guild.id, message.channel.id
        )

        if is_enabled and self.is_talking_to_vortex(message.content):
            content_lower = message.content.lower()
            if (
                ".onion" in content_lower
                or any(
                    phrase in content_lower
                    for phrase in [
                        "onion link",
                        "onion url",
                        "tor link",
                        "tor url",
                        "dark web",
                        "hidden service",
                        "onion address",
                        "tor network",
                        "darkweb",
                        "darknet",
                    ]
                )
                or re.search(
                    r"\b(?:send|give|find|get|share|provide|want|need|looking for|where can i find|how to access|how do i (?:get|find|access))\b.*\b(onion|tor|dark\s*web|hidden\s*service|darknet|dark\s*net|darkweb)",
                    content_lower,
                )
            ):
                await message.reply("I cannot access the Tor Network.")
                return
        elif not is_enabled:
            return

        if message.author == self.bot.user:
            return

        try:
            if message.guild:
                guild_blacklisted = await self.bot.db.fetchval(
                    """
                    SELECT 1 FROM blacklisted_guilds
                    WHERE guild_id = $1
                    """,
                    message.guild.id,
                )
                if guild_blacklisted:
                    return

            user_blacklisted = await self.bot.db.fetchval(
                """
                SELECT 1 FROM blacklisted_users
                WHERE user_id = $1
                """,
                message.author.id,
            )
            if user_blacklisted:
                return

        except Exception as e:
            print(f"[Blacklist Check Error] {e}")

        if any(message.content.startswith(prefix) for prefix in [",", ".", ";"]):
            return

        if (
            not "cogs." in message.content
            and self.contains_url_or_encoding(message.content, is_enabled)
            and is_enabled
        ):
            await message.reply("No.")
            return

        is_natural_address = self.is_talking_to_vortex(message.content)
        is_reply_to_vortex = (
            message.reference
            and message.reference.resolved
            and message.reference.resolved.author == self.bot.user
            and message.reference.resolved.author != message.author
        )

        user_has_conversation = await self.has_active_conversation(
            message.channel.id, message.author.id
        )

        if is_natural_address:
            await self.start_conversation(message.channel.id, message.author.id)
        elif is_reply_to_vortex:
            if not user_has_conversation:
                return

            replied_message_id = (
                message.reference.message_id if message.reference else None
            )
            if replied_message_id:
                is_valid_reply = await self.is_reply_in_user_context(
                    message.channel.id, message.author.id, replied_message_id
                )
                if not is_valid_reply:
                    return

            await self.update_conversation_activity(
                message.channel.id, message.author.id
            )
        else:
            return

        async with message.channel.typing():
            try:
                utility_cog = self.bot.get_cog("Utility")
                user_time = None
                if utility_cog:
                    user_time = await utility_cog.get_user_current_time(
                        message.author.id
                    )

                context = await self.get_conversation_context(
                    message.channel.id, message.author.id
                )

                heart_chance = random.randint(3, 5) == 1

                response = await get_ai_response(
                    message,
                    self.bot.user,
                    "https://api.voidai.app/v1/chat/completions",
                    os.getenv("VOID_AI_API_KEY"),
                    user_time,
                    context,
                    self,
                    heart_chance,
                )

                if response and (response.get("text") or response.get("images")):
                    reply_text = response.get("text", "")

                    if (
                        reply_text
                        and self.contains_url_or_encoding(reply_text, is_enabled)
                        and is_enabled
                    ):
                        await message.reply("No.")
                        return

                    images = response.get("images", [])

                    if reply_text:
                        reply_text = re.sub(r"https?://\S+", "No.", reply_text)
                        if reply_text.strip() == "No.":
                            await message.reply("No.")
                            return

                    if images and reply_text:
                        reply_text = re.sub(
                            r"!\[.*?\]\(attachment://.*?\)", "", reply_text
                        )
                        reply_text = re.sub(
                            r"attachment://\d+(?:\.\w+)?", "", reply_text
                        )
                        reply_text = re.sub(r"\s+", " ", reply_text).strip()

                    await self.save_conversation_context(
                        message.channel.id, message.author.id, "user", message.content
                    )

                    files = []
                    for i, image_data in enumerate(images):
                        file = discord.File(
                            io.BytesIO(image_data),
                            filename=f"generated_image_{i+1}.png",
                        )
                        files.append(file)

                    sent_message = None
                    if reply_text and files:
                        sent_message = await message.reply(
                            reply_text,
                            files=files,
                            allowed_mentions=discord.AllowedMentions.none(),
                        )
                    elif reply_text:
                        sent_message = await message.reply(
                            reply_text,
                            allowed_mentions=discord.AllowedMentions.none(),
                            suppress_embeds=True,
                        )
                    elif files:
                        sent_message = await message.reply(
                            files=files, allowed_mentions=discord.AllowedMentions.none()
                        )

                    if sent_message:
                        if images:
                            cache_key = f"{message.channel.id}_{message.author.id}_{int(time.time())}"
                            self.image_cache[cache_key] = images

                            user_keys = [
                                k
                                for k in self.image_cache.keys()
                                if k.startswith(
                                    f"{message.channel.id}_{message.author.id}_"
                                )
                            ]
                            if len(user_keys) > 10:
                                user_keys.sort()
                                for old_key in user_keys[:-10]:
                                    del self.image_cache[old_key]

                            if reply_text:
                                context_reply = (
                                    f"{reply_text} [Generated image:{cache_key}]"
                                )
                            else:
                                context_reply = f"[Generated image:{cache_key}]"
                        else:
                            context_reply = (
                                reply_text if reply_text else "[No text response]"
                            )

                        await self.save_conversation_context(
                            message.channel.id,
                            message.author.id,
                            "assistant",
                            context_reply,
                        )
                else:
                    await message.reply(
                        "I'm having trouble processing that right now >_< Please try again!"
                    )

            except Exception as e:
                print(f"Error in natural language processing: {e}")
                await message.reply("Something went wrong! Please try again later >.<")

    @Cog.listener()
    async def on_message2(self, message):
        """Test listener (disabled)."""
        if message.author == self.bot.user:
            return

        utility_cog = self.bot.get_cog("Utility")
        user_time = None
        if utility_cog:
            user_time = await utility_cog.get_user_current_time(message.author.id)

        response = await get_ai_response(
            message,
            self.bot.user,
            "https://api.voidai.app/v1/chat/completions",
            os.getenv("VOID_AI_API_KEY"),
            user_time,
        )
        if response and (response.get("text") or response.get("images")):
            reply_text = response.get("text", "")
            images = response.get("images", [])

            files = []
            for i, image_data in enumerate(images):
                file = discord.File(
                    io.BytesIO(image_data), filename=f"generated_image_{i+1}.png"
                )
                files.append(file)

            await message.reply(reply_text, files=files, mention_author=True)
        else:
            await message.channel.send(
                "Failed to get a response from the AI.", ephemeral=True
            )

    def is_talking_to_vortex(self, message_content: str) -> bool:
        """Check if the message is naturally addressing Vortex."""
        content = message_content.lower().strip()

        if "vortex" not in content:
            return False

        beginning_patterns = [
            r"^(hey|sup|yo|hi|hello)\s+vortex[,\s]",
            r"^vortex[,\s]",
            r"^(hey|sup|yo|hi|hello)\s+@?vortex[,\s]",
            r"^vortex\s+",
        ]

        for pattern in beginning_patterns:
            if re.match(pattern, content):
                return True

        anywhere_patterns = [
            r".*[,\s]+vortex[?!.\s]*$",  # "right, vortex?" or "isn't it, vortex!"
            r".*\s+vortex[,\s]+.*",  # "what do you think, vortex, about this?"
            r".*[,\s]+@?vortex[?!.\s]*$",  # "right, @vortex?"
            r".*\bvortex\b.*[?!].*$",  # any question/exclamation with vortex
            r".*\bvortex\b.*\b(right|correct|true|think|opinion|thoughts)\b.*[?]*$",  # seeking confirmation/opinion
        ]

        exclusion_patterns = [
            r".*\b(the|a|an)\s+vortex\b.*",  # "the vortex", "a vortex"
            r".*\bvortex\b.*\b(is|was|are|were|spinning|game|level|area)\b.*",  # contextual usage
            r".*\bvortexes?\b.*",  # plural form
            r".*\bvortex\d+.*",  # usernames like vortex123
        ]

        for pattern in exclusion_patterns:
            if re.search(pattern, content):
                return False

        for pattern in anywhere_patterns:
            if re.search(pattern, content):
                return True

        return False
