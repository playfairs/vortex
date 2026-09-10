import discord
from discord.ext import commands, tasks
from discord.ext.commands import (
    Cog,
    Context,
    hybrid_group,
    hybrid_command as hybrid,
    has_permissions,
)
from vortex import vortex
from config import DISCORD, WHOAMI, BLACKLIST
from managers.classes import Emojis, Colors, Media, Servers, FallBackURLs
import aiohttp
import datetime
import asyncio
import io
from typing import Optional, List, Dict, Any


class AvatarHistory(Cog):
    """Class for handling server avatar history tracking."""

    def __init__(self, bot: vortex):
        self.bot = bot
        self.db = bot.db
        self.bot.loop.create_task(self.setup_tables())
        self.session = aiohttp.ClientSession()
        self.cleanup_old_avatars.start()

    async def cog_unload(self):
        self.cleanup_old_avatars.cancel()
        await self.session.close()

    @tasks.loop(hours=24)
    async def cleanup_old_avatars(self):
        try:
            five_days_ago = datetime.datetime.now(
                datetime.timezone.utc
            ) - datetime.timedelta(days=5)

            five_days_ago_utc = five_days_ago.timestamp()

            deleted = await self.db.fetch(
                """
                DELETE FROM avatar_history 
                WHERE EXTRACT(EPOCH FROM created_at) < $1
                RETURNING id
                """,
                five_days_ago_utc,
            )

            if deleted:
                print(
                    f"[Avatar Cleanup] Cleaned up {len(deleted)} old server avatars from the database."
                )
        except Exception as e:
            print(f"[Avatar Cleanup] Error cleaning up old server avatars: {e}")

    @cleanup_old_avatars.before_loop
    async def before_cleanup(self):
        await self.bot.wait_until_ready()
        print("[Avatar Cleanup] Starting server avatar cleanup task")

    async def setup_tables(self):
        await self.bot.db.execute(
            """
            CREATE TABLE IF NOT EXISTS avatar_history (
                id SERIAL PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                avatar_hash TEXT NOT NULL,
                avatar_data BYTEA NOT NULL,
                avatar_url TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT (NOW() AT TIME ZONE 'utc'),
                UNIQUE(guild_id, user_id, avatar_hash)
            )
            """
        )

        await self.bot.db.execute(
            "CREATE INDEX IF NOT EXISTS idx_avatar_history_guild_user ON avatar_history(guild_id, user_id)"
        )
        await self.bot.db.execute(
            "CREATE INDEX IF NOT EXISTS idx_avatar_history_created_at ON avatar_history(created_at)"
        )

    async def download_avatar(self, url: str) -> Optional[bytes]:
        try:
            async with self.session.get(url) as resp:
                if resp.status == 200:
                    content_type = resp.headers.get("Content-Type", "").lower()
                    image_data = await resp.read()

                    if (
                        "webp" in content_type
                        or image_data.startswith(b"\x52\x49\x46\x46")
                        and b"WEBP" in image_data[:20]
                    ):
                        return image_data

                    try:
                        from PIL import Image
                        from io import BytesIO

                        img = Image.open(BytesIO(image_data))

                        if img.mode in ("RGBA", "LA"):
                            background = Image.new("RGB", img.size, (255, 255, 255))
                            background.paste(img, mask=img.split()[-1])
                            img = background

                        output = BytesIO()
                        img.save(output, format="WEBP", quality=95)
                        return output.getvalue()

                    except ImportError:
                        print(
                            "[Avatar Download] Pillow not installed, cannot convert to WebP"
                        )
                        return None
                    except Exception as e:
                        print(f"[Avatar Download] Error converting to WebP: {e}")
                        return None
                return None
        except Exception as e:
            print(f"[Avatar Download] Error downloading avatar: {e}")
            return None

    async def store_avatar(self, member: discord.Member) -> bool:
        if not member.guild_avatar:
            return False

        avatar_url = str(member.guild_avatar.with_format("webp").with_size(1024))
        avatar_hash = (
            str(member.guild_avatar.key)
            if member.guild_avatar.key
            else str(member.guild_avatar)
        )

        exists = await self.db.fetchval(
            """
            SELECT 1 FROM avatar_history 
            WHERE guild_id = $1 AND user_id = $2 AND avatar_hash = $3
            """,
            member.guild.id,
            member.id,
            avatar_hash,
        )

        if exists:
            return False

        avatar_data = await self.download_avatar(avatar_url)
        if not avatar_data:
            return False

        try:
            async with self.db.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(
                        """
                        INSERT INTO avatar_history (guild_id, user_id, avatar_hash, avatar_data, avatar_url)
                        VALUES ($1, $2, $3, $4, $5)
                        """,
                        member.guild.id,
                        member.id,
                        avatar_hash,
                        avatar_data,
                        avatar_url,
                    )

                    count = await conn.fetchval(
                        """
                        SELECT COUNT(*) FROM avatar_history 
                        WHERE guild_id = $1 AND user_id = $2
                        """,
                        member.guild.id,
                        member.id,
                    )

                    if count > 10:
                        await conn.execute(
                            """
                            DELETE FROM avatar_history
                            WHERE id IN (
                                SELECT id FROM avatar_history
                                WHERE guild_id = $1 AND user_id = $2
                                ORDER BY created_at ASC
                                LIMIT $3
                            )
                            """,
                            member.guild.id,
                            member.id,
                            count - 10,
                        )
                        print(
                            f"[Avatar Storage] Removed {count - 10} old server avatars for user {member.id} in guild {member.guild.id}"
                        )

                    return True

        except Exception as e:
            print(f"[Avatar Storage] Error storing server avatar: {e}")
            return False

    @Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.guild_avatar == after.guild_avatar:
            return

        await self.store_avatar(after)


async def setup(bot: vortex):
    await bot.add_cog(AvatarHistory(bot))
