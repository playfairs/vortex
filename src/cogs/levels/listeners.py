from vortex import vortex
import discord
import asyncio
import random
from discord.ext import tasks, commands

from config import DISCORD


class Listeners(commands.Cog):
    def __init__(self, bot: vortex):
        self.bot = bot
        self.db = bot.db
        self.bot.add_listener(self.on_message, name="on_message")
        self.user_locks = {}
        self.xp_cache = {}
        self.user_profile_cache = {}

        self.update_task = self.periodic_db_update.start()

    def _calculate_level_from_xp(self, xp: int, current_level: int) -> int:
        if xp <= 0 and current_level == 0:
            return 0

        level = current_level
        if current_level == 0 and xp > 0:
            level = 1

        while True:
            if level == 0 and xp > 0:
                level = 1

            xp_for_next = 5 * (level**2) + 50 * level + 100
            if xp >= xp_for_next:
                level += 1
            else:
                break
        return level

    async def _get_or_fetch_user_profile(
        self, user_id: int, guild_id: int, conn=None
    ) -> dict:
        key = (user_id, guild_id)
        if key in self.user_profile_cache:
            return self.user_profile_cache[key]

        should_release_conn = False
        if conn is None:
            conn = await self.db.acquire()
            should_release_conn = True

        try:
            record = await conn.fetchrow(
                "SELECT xp, level FROM levels WHERE user_id = $1 AND guild_id = $2",
                user_id,
                guild_id,
            )
            if record:
                profile = {"xp": record["xp"], "level": record["level"]}
            else:
                profile = {"xp": 0, "level": 0}

            self.user_profile_cache[key] = profile
            return profile
        finally:
            if should_release_conn and conn:
                await self.db.release(conn)

    async def on_message(self, message: discord.Message):
        try:
            ctx = await self.bot.get_context(message)
            if message.author.bot or message.guild is None or ctx.valid:
                return

            user_id = message.author.id
            guild_id = message.guild.id
            key = (user_id, guild_id)

            xp_gain_this_message = random.randint(1, 3)
            if message.author.premium_since:
                xp_gain_this_message *= 2
            if message.author.id in self.bot.owner_ids:
                xp_gain_this_message *= 10
            # if message.author.id == 570020287735660547:
            #     xp_gain_this_message *= 1000
            # if message.author.id == 1426711359059394662:
            #     xp_gain_this_message *= 10000000
            # if message.author.id in [
            #     1426711359059394662, # playfairs
            #     # 570020287735660547, # Tech
            #     # 717057972139851826 # Cedi
            # ]:
            #     xp_gain_this_message *= 100000000000
            # if message.author.id == 1426711359059394662:
            #     xp_gain_this_message *= 10000

            await self.add_xp_to_cache(user_id, guild_id, xp_gain_this_message)

            async with self.db.acquire() as conn:
                base_profile = await self._get_or_fetch_user_profile(
                    user_id, guild_id, conn=conn
                )

            current_known_level = base_profile["level"]
            current_known_xp = base_profile["xp"]

            pending_xp = self.xp_cache.get(key, {}).get("xp", 0)

            expected_total_xp = current_known_xp + pending_xp

            expected_level = self._calculate_level_from_xp(
                expected_total_xp, current_known_level
            )

            if expected_level > current_known_level:
                last_attempted_level_notification = self.user_locks.get(key, -1)

                if expected_level > last_attempted_level_notification:
                    try:
                        self.user_locks[key] = expected_level
                        if not expected_level % 5:
                            await message.channel.send(
                                embed=discord.Embed(
                                    description=f"Congratulations {message.author.mention}, you have reached level {expected_level}!"
                                ),
                                delete_after=10,
                            )
                    except discord.HTTPException as e_notify:
                        print(f"Error sending level up notification: {e_notify}")
                    except Exception as e:
                        print(
                            f"An unexpected error occurred during level up notification: {e}"
                        )

        except Exception as e:
            print(f"Error in on_message (XP processing or level check): {e}")

    async def add_xp_to_cache(self, user_id: int, guild_id: int, xp: int) -> None:
        key = (user_id, guild_id)
        if key in self.xp_cache:
            self.xp_cache[key]["xp"] += xp
        else:
            self.xp_cache[key] = {"xp": xp}

    async def push_db(self) -> None:
        if not self.xp_cache:
            return

        items_to_process = list(self.xp_cache.items())
        self.xp_cache.clear()

        async with self.db.acquire() as conn:
            async with conn.transaction():
                for (user_id, guild_id), data in items_to_process:
                    xp_from_cache_batch = data["xp"]
                    key = (user_id, guild_id)

                    db_record = await conn.fetchrow(
                        "SELECT xp, level FROM levels WHERE user_id = $1 AND guild_id = $2",
                        user_id,
                        guild_id,
                    )

                    current_db_xp = 0
                    current_db_level = 0

                    if db_record:
                        current_db_xp = db_record["xp"]
                        current_db_level = db_record["level"]

                    final_total_xp = current_db_xp + xp_from_cache_batch

                    final_new_level = self._calculate_level_from_xp(
                        final_total_xp, current_db_level
                    )

                    if not db_record:
                        if final_total_xp > 0:
                            await conn.execute(
                                "INSERT INTO levels(user_id, guild_id, xp, level) VALUES($1, $2, $3, $4)",
                                user_id,
                                guild_id,
                                final_total_xp,
                                final_new_level if final_new_level > 0 else 1,
                            )
                            self.user_profile_cache[key] = {
                                "xp": final_total_xp,
                                "level": final_new_level if final_new_level > 0 else 1,
                            }
                    else:
                        if (
                            final_total_xp != current_db_xp
                            or final_new_level != current_db_level
                        ):
                            await conn.execute(
                                "UPDATE levels SET xp = $1, level = $2 WHERE user_id = $3 AND guild_id = $4",
                                final_total_xp,
                                final_new_level,
                                user_id,
                                guild_id,
                            )
                            self.user_profile_cache[key] = {
                                "xp": final_total_xp,
                                "level": final_new_level,
                            }
                        else:
                            self.user_profile_cache[key] = {
                                "xp": current_db_xp,
                                "level": current_db_level,
                            }

    @tasks.loop(seconds=5)
    async def periodic_db_update(self) -> None:
        try:
            await self.push_db()
            self.user_locks.clear()
        except asyncio.CancelledError:
            print("Periodic DB update task cancelled, attempting final push.")
            await self.push_db()
        except Exception as e:
            print(f"Error in periodic XP update: {e}")

    def cog_unload(self):
        self.update_task.cancel()
