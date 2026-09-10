import discord
import asyncpg
import time
import io
from discord.ext import commands
from discord.ext.commands import (
    Cog,
    Context,
    group,
    has_permissions,
    command,
    hybrid_command as hybrid,
    hybrid_group,
)
from discord import app_commands
from typing import Optional
from managers.classes import Media, Emojis, Colors
from vortex import vortex


class Blacklist(Cog, description="View commands in Blacklist."):
    def __init__(self, bot: vortex):
        self.bot = bot
        self.bot.loop.create_task(self.setup_blacklist())

    async def cog_check(self, ctx: Context) -> bool:
        if ctx.author.id not in self.bot.owner_ids:
            if isinstance(ctx, discord.Interaction):
                await ctx.response.send_message(
                    "This is an owner only command.", ephemeral=True
                )
            else:
                await ctx.send("This is an owner only command.", ephemeral=True)
            return False
        return True

    async def setup_blacklist(self):
        await self.bot.db.execute(
            """
            CREATE TABLE IF NOT EXISTS blacklisted_users (
                user_id BIGINT PRIMARY KEY,
                reason TEXT,
                blacklisted_time BIGINT,
                invoker_id BIGINT
            )
            """
        )
        await self.bot.db.execute(
            """
            CREATE TABLE IF NOT EXISTS blacklisted_guilds (
                guild_id BIGINT PRIMARY KEY,
                reason TEXT,
                blacklisted_time BIGINT,
                invoker_id BIGINT
            )
            """
        )
        try:
            await self.bot.db.execute(
                """
                ALTER TABLE blacklisted_users 
                ADD COLUMN IF NOT EXISTS invoker_id BIGINT
                """
            )
            await self.bot.db.execute(
                """
                ALTER TABLE blacklisted_guilds 
                ADD COLUMN IF NOT EXISTS invoker_id BIGINT
                """
            )
        except Exception as e:
            print(f"[Blacklist] Error adding invoker_id column: {e}")

    @hybrid_group(name="blacklist", aliases=["bl"])
    @app_commands.describe()
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def blacklist(self, ctx: Context):
        """View commands in Blacklist."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(self.blacklist)

    @blacklist.command(name="user")
    @app_commands.describe(
        user="The user to blacklist.", reason="The reason for blacklisting. Optional."
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def user(self, ctx: Context, user: str, *, reason: Optional[str] = None):
        """Blacklist a user."""
        if user.startswith("<@") and user.endswith(">"):
            user = user[2:-1]
        try:
            user_id = int(user)
        except ValueError:
            await ctx.send("Invalid user ID.", ephemeral=True)
            return

        existing = await self.bot.db.fetchval(
            "SELECT 1 FROM blacklisted_users WHERE user_id = $1", user_id
        )

        if existing:
            await ctx.send("That user is already blacklisted.", ephemeral=True)
            return

        try:
            await self.bot.db.execute(
                "INSERT INTO blacklisted_users (user_id, reason, blacklisted_time, invoker_id) VALUES ($1, $2, $3, $4)",
                user_id,
                reason or "Blacklisted by {}".format(ctx.author.id),
                int(time.time()),
                ctx.author.id,
            )
            user = ctx.bot.get_user(user_id)
            if user:
                msg = f"{user.mention} has been blacklisted"
            else:
                msg = f"User with ID `{user_id}` has been blacklisted"
            if reason:
                msg += f" with reason: {reason}"
            await ctx.send(msg)
        except asyncpg.UniqueViolationError:
            await ctx.send("That user is already blacklisted.", ephemeral=True)

    @blacklist.command(name="guild")
    @app_commands.describe(
        guild="The guild to blacklist (ID or mention).",
        reason="The reason for blacklisting. Optional.",
        leave="Whether the bot should leave the guild after blacklisting. Defaults to False.",
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def guild(
        self,
        ctx: Context,
        guild: str,
        *,
        reason: Optional[str] = None,
        leave: bool = False,
    ):
        """Blacklist a guild."""
        guild = guild.strip()
        if guild.startswith(("<", "@")) and guild.endswith(">"):
            guild = guild.strip("<@!>")

        try:
            guild_id = int(guild)
        except ValueError:
            await ctx.send("Invalid guild ID. Please provide a valid numeric guild ID.")
            return

        existing = await self.bot.db.fetchval(
            "SELECT 1 FROM blacklisted_guilds WHERE guild_id = $1", guild_id
        )

        if existing:
            await ctx.send("That guild is already blacklisted.", ephemeral=True)
            return

        try:
            discord_guild = self.bot.get_guild(guild_id)
            guild_name = (
                discord_guild.name if discord_guild else f"Guild ID: {guild_id}"
            )

            await self.bot.db.execute(
                """
                INSERT INTO blacklisted_guilds 
                (guild_id, reason, blacklisted_time, invoker_id) 
                VALUES ($1, $2, $3, $4)
                """,
                guild_id,
                reason or f"Blacklisted by {ctx.author} ({ctx.author.id})",
                int(time.time()),
                ctx.author.id,
            )

            msg = f"Successfully blacklisted `{guild_name}`"
            if reason:
                msg += f" with reason: {reason}"

            await ctx.send(msg)

            if leave and discord_guild:
                try:
                    await ctx.author.send(
                        f"Successfully blacklisted `{guild_name}` and left the guild."
                    )
                    await discord_guild.leave()
                except Exception as e:
                    try:
                        await ctx.author.send(
                            f"Failed to leave guild `{guild_name}`: {e}"
                        )
                    except:
                        pass
            elif leave and not discord_guild:
                try:
                    await ctx.author.send(
                        f"Cannot leave guild `{guild_name}`: Bot is not in this guild."
                    )
                except:
                    pass
        except asyncpg.UniqueViolationError:
            await ctx.send("That guild is already blacklisted.", ephemeral=True)

    @blacklist.command(
        name="extend",
        description="Blacklist more than one guild or user, or both, at once.",
    )
    @app_commands.describe(
        users="The users to blacklist. Optional. Separate multiple users with commas.",
        guilds="The guilds to blacklist. Optional. Separate multiple guilds with commas.",
        reason="The reason for blacklisting. Optional.",
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def extend(
        self,
        ctx: Context,
        users: Optional[str] = None,
        guilds: Optional[str] = None,
        *,
        reason: Optional[str] = None,
    ):
        """Blacklist more than one guild or user, or both, at once."""
        if not users and not guilds:
            return await ctx.send(
                "Please specify at least one user or guild to blacklist."
            )

        user_results = {"success": 0, "failed": 0}
        if users:
            user_ids = [user.strip("<@!>") for user in users.split(",") if user.strip()]
            if user_ids:
                try:
                    result = await self.bot.db.executemany(
                        """
                        INSERT INTO blacklisted_users (user_id, reason, blacklisted_time, invoker_id) 
                        VALUES ($1, $2, $3, $4) 
                        ON CONFLICT (user_id) DO NOTHING
                        RETURNING user_id
                        """,
                        [
                            (
                                int(user_id),
                                reason or f"Blacklisted by {ctx.author.id}",
                                int(time.time()),
                                ctx.author.id,
                            )
                            for user_id in user_ids
                        ],
                    )
                    user_results["failed"] = len(result or [])
                    user_results["success"] = len(user_ids) - user_results["failed"]
                except (ValueError, asyncpg.DataError):
                    user_results["failed"] = len(user_ids)

        guild_results = {"success": 0, "failed": 0}
        if guilds:
            guild_ids = [
                guild.strip("<@!>") for guild in guilds.split(",") if guild.strip()
            ]
            if guild_ids:
                try:
                    existing = await self.bot.db.fetch(
                        "SELECT guild_id FROM blacklisted_guilds WHERE guild_id = ANY($1::bigint[])",
                        [int(g_id) for g_id in guild_ids],
                    )
                    existing_ids = {r["guild_id"] for r in existing}

                    to_insert = []
                    for g_id in guild_ids:
                        try:
                            g_id_int = int(g_id)
                            if g_id_int not in existing_ids:
                                to_insert.append(
                                    (
                                        g_id_int,
                                        reason or f"Blacklisted by {ctx.author.id}",
                                        int(time.time()),
                                        ctx.author.id,
                                    )
                                )
                        except ValueError:
                            pass

                    if to_insert:
                        await self.bot.db.executemany(
                            """
                            INSERT INTO blacklisted_guilds (guild_id, reason, blacklisted_time, invoker_id) 
                            VALUES ($1, $2, $3, $4)
                            """,
                            to_insert,
                        )

                    guild_results["success"] = len(to_insert)
                    guild_results["failed"] = (
                        len(guild_ids) - guild_results["success"] - len(existing_ids)
                    )
                    if existing_ids:
                        await ctx.send(
                            f"Note: {len(existing_ids)} guilds were already blacklisted and were skipped."
                        )
                    guild_results["already_blacklisted"] = len(existing_ids)

                except (ValueError, asyncpg.DataError):
                    guild_results["failed"] = len(guild_ids)

        messages = []
        if users:
            msg = f"Users: {user_results['success']} blacklisted"
            if user_results["failed"]:
                msg += f", {user_results['failed']} failed"
            messages.append(msg)

        if guilds:
            msg = f"Guilds: {guild_results['success']} blacklisted"
            if guild_results.get("already_blacklisted", 0):
                msg += f", {guild_results['already_blacklisted']} already blacklisted"
            if guild_results["failed"]:
                msg += f", {guild_results['failed']} failed"
            messages.append(msg)

        await ctx.send(
            "\n".join(messages) if messages else "No valid users or guilds provided."
        )

    @blacklist.command(
        name="remove", description="Remove a user or guild from the blacklist."
    )
    @app_commands.describe(
        user="The user to remove from the blacklist.",
        guild="The guild to remove from the blacklist.",
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def remove(
        self, ctx: Context, user: Optional[str] = None, guild: Optional[str] = None
    ):
        """Remove a user or guild from the blacklist."""
        if user:
            try:
                user_ids = []
                for id_str in user.split(","):
                    id_str = id_str.strip()
                    if id_str.startswith(("<@", "<@!")) and id_str.endswith(">"):
                        id_str = id_str.strip("<@!>")
                    try:
                        user_ids.append(int(id_str))
                    except ValueError:
                        await ctx.send(f"Invalid user ID: {id_str}", ephemeral=True)
                        return

                if not user_ids:
                    await ctx.send("No valid user IDs provided.", ephemeral=True)
                    return

                result = await self.bot.db.execute(
                    "DELETE FROM blacklisted_users WHERE user_id = ANY($1::bigint[])",
                    user_ids,
                )

                removed_count = int(result.split()[1])
                if removed_count == 0:
                    await ctx.send("No users were removed from the blacklist.")
                elif removed_count == 1 and len(user_ids) == 1:
                    user = self.bot.get_user(user_ids[0]) or f"User {user_ids[0]}"
                    await ctx.send(f"Removed {user.mention} from the blacklist.")
                else:
                    await ctx.send(
                        f"Removed {removed_count} user(s) from the blacklist."
                    )

            except Exception as e:
                await ctx.send(f"An error occurred while removing users: {e}")

        elif guild:
            try:
                guild_ids = []
                for id_str in guild.split(","):
                    id_str = id_str.strip()
                    try:
                        guild_ids.append(int(id_str))
                    except ValueError:
                        await ctx.send(f"Invalid guild ID: {id_str}", ephemeral=True)
                        return

                if not guild_ids:
                    await ctx.send("No valid guild IDs provided.", ephemeral=True)
                    return

                result = await self.bot.db.execute(
                    "DELETE FROM blacklisted_guilds WHERE guild_id = ANY($1::bigint[])",
                    guild_ids,
                )

                removed_count = int(result.split()[1])
                if removed_count == 0:
                    await ctx.send("No guilds were removed from the blacklist.")
                elif removed_count == 1 and len(guild_ids) == 1:
                    guild = self.bot.get_guild(guild_ids[0]) or f"Guild {guild_ids[0]}"
                    await ctx.send(
                        f"Removed **Guild** *{guild.id}* from the blacklist."
                    )
                else:
                    await ctx.send(
                        f"Removed {removed_count} guild(s) from the blacklist."
                    )

            except Exception as e:
                await ctx.send(f"An error occurred while removing guilds: {e}")

        else:
            await ctx.send(
                "Please specify a user or guild to remove from the blacklist."
            )

    @blacklist.command(
        name="list",
        description="Generate a Python file with all blacklisted users and guilds.",
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def list(self, ctx: Context):
        """Generate a Python file with all blacklisted users and guilds in the specified format."""
        users = await self.bot.db.fetch(
            "SELECT user_id, reason, invoker_id FROM blacklisted_users ORDER BY user_id"
        )
        guilds = await self.bot.db.fetch(
            "SELECT guild_id, reason, invoker_id FROM blacklisted_guilds ORDER BY guild_id"
        )

        def format_comment(entry):
            parts = []
            if entry.get("reason"):
                parts.append(f"Reason: {entry['reason']}")
            if entry.get("invoker_id"):
                parts.append(f"Invoker: {entry['invoker_id']}")
            return f" # {' - '.join(parts)}" if parts else ""

        user_entries = []
        for user in users:
            comment = format_comment(user)
            user_entries.append(f"{user['user_id']}{comment}")

        guild_entries = [str(guild["guild_id"]) for guild in guilds]

        file_content = '''"""
Class to store blacklisted User ID's and Guild ID's.
"""

class BLACKLIST:
    """
    Class to store blacklisted User ID's and Guild ID's.
    """
    USER_ID: list[int] = [
'''

        for entry in user_entries:
            if "#" in entry:
                user_id, comment = entry.split("#", 1)
                file_content += f"        {user_id.strip()},    #{comment.strip()}\n"
            else:
                file_content += f"        {entry.strip()},\n"

        file_content += "    ]\n    GUILD_ID: list[int] = [\n"

        for i, guild_id in enumerate(guild_entries):
            if i < len(guild_entries) - 1:
                file_content += f"        {guild_id},\n"
            else:
                file_content += f"        {guild_id}\n"

        file_content += "    ]"

        file_bytes = file_content.encode("utf-8")
        file = discord.File(
            io.BytesIO(file_bytes),
            filename="blacklist.py",
            description="Blacklisted users and guilds",
        )
        await ctx.interaction.response.send_message(
            "Check your DMs for the Blacklist.", ephemeral=True
        )
        await ctx.author.send(file=file)

    @blacklist.command(
        name="view",
        description="Get information about a user or guild in the blacklist.",
    )
    @app_commands.describe(
        user="The user to get information about.",
        guild="The guild to get information about.",
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def info(
        self, ctx: Context, user: Optional[str] = None, guild: Optional[str] = None
    ):
        """Get information about a user or guild in the blacklist."""
        embed = discord.Embed(
            title="Blacklist Information", color=discord.Color(0xFFFFFF)
        )

        if not user and not guild:
            embed.description = "Lost? Maybe you meant to run `/blacklist list`?"
            await ctx.send(embed=embed, ephemeral=True)
            return

        if user:
            try:
                user_ids = [
                    int(id.strip("<@!>")) for id in user.split(",") if id.strip()
                ]
                if not user_ids:
                    raise ValueError("No valid user IDs provided")

                users = await self.bot.db.fetch(
                    "SELECT user_id, reason, blacklisted_time, invoker_id FROM blacklisted_users WHERE user_id = ANY($1::bigint[])",
                    user_ids,
                )

                if users:
                    for user in users:
                        timestamp = (
                            f"<t:{user['blacklisted_time']}:F>"
                            if user["blacklisted_time"]
                            else "Unknown"
                        )
                        embed.add_field(
                            name=f"User ID: {user['user_id']}",
                            value=f"**Reason:** {user['reason'] or 'No reason provided'}\n**Blacklisted:** {timestamp}\n**User:** <@!{user['user_id']}>\n**Invoker:** <@!{user['invoker_id']}>",
                            inline=False,
                        )
                else:
                    embed.description = (
                        "No users found in the blacklist with the provided IDs."
                    )

            except (ValueError, asyncpg.DataError) as e:
                embed.description = "Error: Please provide valid user IDs."

        elif guild:
            try:
                guild_ids = [
                    int(id.strip("<@!>")) for id in guild.split(",") if id.strip()
                ]
                if not guild_ids:
                    raise ValueError("No valid guild IDs provided")

                guilds = await self.bot.db.fetch(
                    "SELECT guild_id, reason, blacklisted_time, invoker_id FROM blacklisted_guilds WHERE guild_id = ANY($1::bigint[])",
                    guild_ids,
                )

                if guilds:
                    for guild in guilds:
                        timestamp = (
                            f"<t:{guild['blacklisted_time']}:F>"
                            if guild["blacklisted_time"]
                            else "Unknown"
                        )
                        embed.add_field(
                            name=f"Guild ID: {guild['guild_id']}",
                            value=f"**Reason:** {guild['reason'] or 'No reason provided'}\n**Blacklisted:** {timestamp}\n**Invoker:** <@{guild['invoker_id']}>",
                            inline=False,
                        )
                else:
                    embed.description = (
                        "No guilds found in the blacklist with the provided IDs."
                    )

            except (ValueError, asyncpg.DataError) as e:
                embed.description = "Error: Please provide valid guild IDs."
        await ctx.send(embed=embed)
