import discord
import asyncio
import aiohttp
import traceback
import ast
import re
from datetime import timedelta
from discord.ext import commands, tasks
from discord.ext.commands import (
    command,
    group,
    has_permissions,
    Cog,
    Context,
    cooldown,
    BucketType,
    bot_has_permissions,
    hybrid_command as hybrid,
    hybrid_group,
    is_owner,
    guild_only,
)
from discord import app_commands, TextChannel, Member, Color
from typing import Optional
from datetime import datetime, timezone, timedelta
from fuzzywuzzy import process
from cogs.moderation.classes import (
    RolesView,
    BanListView,
    PaginationView,
    ConfirmView,
    SnipeView,
    NewUsersView,
)
from .snipe import Snipe
from vortex import vortex
from config import USERS
from managers.classes import Emojis, Colors
from managers.default_avatar import DefaultAvatarManager
from discord.embeds import Embed
from typing import Union
import time
from base.embeds import Builder

COOLDOWN = 1
CACHE = {}


class Moderation(Cog, description="View commands in Moderation."):
    async def parse_time_string(self, time_str: str) -> int:
        """
        Parse a time string into seconds.

        Examples:
        - "30s" -> 30
        - "1m" -> 60
        - "2m30s" -> 150
        - "1h" -> 3600
        """
        time_seconds = 0
        current_num = ""

        for char in time_str.lower():
            if char.isdigit():
                current_num += char
            elif char in ["s", "m", "h"]:
                if not current_num:
                    continue
                num = int(current_num)
                if char == "s":
                    time_seconds += num
                elif char == "m":
                    time_seconds += num * 60
                elif char == "h":
                    time_seconds += num * 3600
                current_num = ""
            elif char.isspace():
                continue
            else:
                raise ValueError(f"Invalid time format: {time_str}")

        # Handle case where there are just numbers without units (default to seconds)
        if current_num and not time_seconds:
            time_seconds = int(current_num)

        if time_seconds > 21600:  # 6 hours in seconds
            raise ValueError("Slowmode interval cannot be more than 6 hours")

        return time_seconds if time_seconds > 0 else 0

    def __init__(self, bot: vortex):
        self.bot = bot
        self.db = bot.db
        self.bot_session = aiohttp.ClientSession()
        self.start_time = datetime.now(timezone.utc)
        self.unmoderatable_user_ids = USERS.BAN_PROTECTED
        self.users_triggered_bot = []
        self.sniper = Snipe(self.bot)
        self.default_avatar_manager = DefaultAvatarManager(bot)
        self.bot.loop.create_task(self.check_autorole_tables())
        self.bot.loop.create_task(self.check_join_logs_table())
        self.hardbanned_user_ids = set()
        self.case_count = 0
        self.bot.loop.create_task(self.check_restore_table())
        self.bot.loop.create_task(self.create_nsr_table())

    async def cog_unload(self):
        if not self.bot_session.closed:
            await self.bot_session.close()

    async def create_autorole_tables(self):
        """Create the autorole tables if they don't exist."""
        async with self.bot.db.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS autorole_humans (
                    guild_id BIGINT PRIMARY KEY,
                    role_id BIGINT NOT NULL
                )
            """
            )

            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS autorole_bots (
                    guild_id BIGINT PRIMARY KEY,
                    role_id BIGINT NOT NULL
                )
            """
            )

    async def check_autorole_tables(self):
        """Check if autorole tables exist and create them if they don't."""
        async with self.bot.db.acquire() as conn:
            result = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'autorole_humans'
                )
            """
            )
            if not result:
                await self.create_autorole_tables()

    async def create_join_logs_table(self):
        """Create the join_logs table if it doesn't exist."""
        async with self.bot.db.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS join_logs (
                    server_id BIGINT PRIMARY KEY,
                    channel_id BIGINT,
                    welcome_message TEXT,
                    leave_message TEXT
                )
            """
            )

    async def check_join_logs_table(self):
        """Check if the join_logs table exists and create it if it doesn't."""
        async with self.bot.db.acquire() as conn:
            result = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'join_logs'
                )
            """
            )
            if not result:
                await self.create_join_logs_table()

    async def check_hardbanned_users_table(self):
        """Check if the hardbanned_users table exists and create it if it doesn't."""
        async with self.bot.db.acquire() as conn:
            table_exists = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'hardbanned_users'
                )
                """
            )
            if not table_exists:
                await self.create_hardbanned_users_table()

    async def create_hardbanned_users_table(self):
        """Create the hardbanned_users table if it doesn't exist."""
        async with self.bot.db.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS hardbanned_users (
                    user_id BIGINT PRIMARY KEY,
                    guild_id BIGINT
                )
                """
            )

    async def create_forced_nicks_table(self):
        """Create the forced_nicks table if it doesn't exist."""
        async with self.bot.db.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS forced_nicks (
                    guild_id BIGINT,
                    user_id BIGINT,
                    nick TEXT,
                    PRIMARY KEY (guild_id, user_id)
                )
            """
            )

    async def create_lockdown_roles_table(self):
        """Create the lockdown_roles table if it doesn't exist."""
        async with self.bot.db.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS lockdown_roles (
                    guild_id BIGINT UNIQUE,
                    role_id BIGINT,
                    PRIMARY KEY (guild_id, role_id)
                )
            """
            )

    async def create_restore_table(self):
        """Create or update the removed_roles table with all required columns."""
        async with self.bot.db.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS removed_roles (
                    user_id BIGINT,
                    guild_id BIGINT,
                    role_id BIGINT,
                    timestamp TIMESTAMP WITH TIME ZONE DEFAULT (now() AT TIME ZONE 'utc') NOT NULL,
                    PRIMARY KEY (user_id, guild_id, role_id)
                )
            """
            )

            await conn.execute(
                "CREATE INDEX idx_removed_roles_timestamp ON removed_roles(timestamp)"
            )
            table_info = await conn.fetch(
                """
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'removed_roles'
            """
            )

            columns = {row["column_name"] for row in table_info}
            required_columns = {"user_id", "guild_id", "role_id", "timestamp"}

            if not required_columns.issubset(columns):
                raise RuntimeError(
                    "Failed to create removed_roles table with required columns"
                )

            print("Successfully created removed_roles table with all required columns")

    async def check_restore_table(self):
        """Check if the restore table exists and has all required columns."""
        async with self.bot.db.acquire() as conn:
            table_exists = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_name = 'removed_roles'
                )
                """
            )

            if not table_exists:
                await self.create_restore_table()
            else:
                columns = await conn.fetch(
                    """
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'removed_roles'
                    """
                )

                existing_columns = {row["column_name"] for row in columns}
                required_columns = {"user_id", "guild_id", "role_id", "timestamp"}

                if not required_columns.issubset(existing_columns):
                    await conn.execute("DROP TABLE IF EXISTS removed_roles")
                    await self.create_restore_table()

    async def create_random_command_usage_table(self):
        """Create the random_command_usage table if it doesn't exist."""
        async with self.bot.db.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS random_command_usage (
                    user_id BIGINT,
                    command TEXT,
                    timestamp TIMESTAMP WITH TIME ZONE DEFAULT (now() AT TIME ZONE 'utc') NOT NULL,
                    PRIMARY KEY (user_id, command)
                )
                """
            )

    async def create_nsr_table(self):
        async with self.bot.db.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS nsr (
                    server_id BIGINT PRIMARY KEY,
                    enabled BOOLEAN NOT NULL DEFAULT false
                )
                """
            )

            try:
                await conn.execute(
                    """
                    ALTER TABLE nsr 
                    ADD COLUMN IF NOT EXISTS message TEXT
                    """
                )
            except Exception as e:
                print(f"[NSR] Error adding message column: {e}")
                if "duplicate column" not in str(e).lower():
                    raise

            records = await conn.fetch("SELECT server_id FROM nsr WHERE enabled = true")
            self.enabled_servers = {r["server_id"] for r in records}

    async def setup(self):
        """Initialize the cog by checking for the join_logs table."""
        await self.check_join_logs_table()
        await self.check_hardbanned_users_table()
        await self.create_forced_nicks_table()
        await self.create_lockdown_roles_table()
        await self.check_restore_table()
        await self.create_random_command_usage_table()
        await self.create_nsr_table()

    @tasks.loop(hours=1)
    async def restore_roles(self):
        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        async with self.bot.db.acquire() as conn:
            await conn.execute(
                "DELETE FROM removed_roles WHERE timestamp < $1",
                cutoff,
            )

    @Cog.listener()
    async def on_ready(self):
        """Initialize the cog when the bot is ready."""
        await self.setup()

    async def can_moderate(self, moderator, target) -> bool:

        if moderator.id == moderator.guild.owner_id:
            return True

        if moderator.id == target.id:
            return False

        if moderator.top_role == target.top_role:
            return False

        return moderator.top_role > target.top_role

    async def get_member(self, ctx, member: discord.Member = None, user_id: int = None):
        """
        Helper method to get a member either by direct mention or by user ID.

        Args:
            ctx (Context): The command context
            member (discord.Member, optional): The member mentioned directly
            user_id (int, optional): The user ID to fetch

        Returns:
            discord.Member or None: The resolved member, or None if not found
        """
        if member:
            return member

        if user_id:
            try:
                return await ctx.guild.fetch_member(user_id)
            except discord.NotFound:
                await ctx.send(
                    f"Could not find a member with ID {user_id} in this server."
                )
                return None
            except discord.HTTPException:
                await ctx.send("Failed to fetch the member.")
                return None

        return None

    async def give_role(self, ctx, member: discord.Member, role_input: str):
        roles = ctx.guild.roles
        closest_matches = process.extract(
            role_input, [role.name for role in roles], limit=1
        )
        if closest_matches:
            closest_match = closest_matches[0]
            if closest_match[1] > 60:
                role = discord.utils.get(roles, name=closest_match[0])
            else:
                role = None
        else:
            role = None

        if not role:
            try:
                role = await commands.RoleConverter().convert(ctx, role_input)
            except commands.RoleNotFound:
                embed = discord.Embed(
                    description=f"{Emojis.error} Role **{role_input}** not found; Maybe try the role ID, or run `roles` to see all roles.",
                    color=0xFFFFFF,
                )
                await ctx.send(embed=embed)
                return

        if role.position >= ctx.author.top_role.position:
            embed = discord.Embed(
                description=f"{Emojis.error} You cannot manage a role that is higher or equal to your highest role.",
                color=0xFFFFFF,
            )
            await ctx.send(embed=embed)
            return

        if role.position >= ctx.guild.me.top_role.position:
            embed = discord.Embed(
                description=f"{Emojis.error} I cannot manage a role that is higher or equal to my highest role.",
                color=0xFFFFFF,
            )
            await ctx.send(embed=embed)
            return

        try:
            if role in member.roles:
                await member.remove_roles(role, reason=f"Role removed by {ctx.author}")
                embed = discord.Embed(
                    description=f"{Emojis.check}  Removed {role.mention} from {member.mention}.",
                    color=0xFFFFFF,
                )
                await ctx.send(embed=embed)
            else:
                await member.add_roles(role, reason=f"Role added by {ctx.author}")
                embed = discord.Embed(
                    description=f"{Emojis.check}  Gave {role.mention} to {member.mention}.",
                    color=0xFFFFFF,
                )
                await ctx.send(embed=embed)
        except discord.Forbidden:
            embed = discord.Embed(
                description=f"{Emojis.error} I do not have permission to manage this role or member.",
                color=0xFFFFFF,
            )
            await ctx.send(embed=embed)
        except discord.HTTPException as e:
            embed = discord.Embed(
                description=f"{Emojis.error} A fucky wucky occurred while managing the role: {str(e)}",
                color=0xFFFFFF,
            )
            await ctx.send(embed=embed)

    async def send_embed(self, ctx, message: str):
        embed = discord.Embed(description=message, color=0xFFFFFF)
        await ctx.send(embed=embed)

    @command(
        name="ban",
        aliases=["execute"],
    )
    @has_permissions(ban_members=True)
    async def ban(
        self,
        ctx,
        member: Union[discord.Member, discord.User, int, str],
        *,
        reason: str = None,
    ):
        """Ban a user with an optional reason"""
        if not ctx.guild:
            return await ctx.send("This command can only be used in a server.")

        user_id = None
        is_member = True

        if isinstance(member, int):
            user_id = member
            is_member = False
        elif isinstance(member, (discord.Member, discord.User)):
            user_id = member.id
            is_member = isinstance(member, discord.Member)
        elif isinstance(member, str) and member.isdigit():
            user_id = int(member)
            is_member = False
        else:
            match = re.match(r"<@!?(\d+)>", member)
            if match:
                user_id = int(match.group(1))
                is_member = False
            else:
                return await ctx.send("Please provide a valid user mention or ID.")

        if not is_member and ctx.guild:
            try:
                member = await ctx.guild.fetch_member(user_id)
                is_member = True
            except discord.NotFound:
                pass

        try:
            user = await self.bot.fetch_user(user_id) if not is_member else member
        except discord.NotFound:
            return await ctx.send("Could not find that user.")

        if user_id == ctx.author.id:
            return await ctx.send("😭 just leave atp")

        if user_id == self.bot.user.id:
            return await ctx.send("jus say you hate me 😭✌️")

        if user_id in self.bot.owner_ids:
            return await ctx.send("no.")

        if is_member and isinstance(member, discord.Member):
            if (
                member.top_role >= ctx.author.top_role
                and ctx.author.id != ctx.guild.owner_id
            ):
                return await ctx.send(
                    "You can't ban someone with a role higher or equal to yours!"
                )

        reason = reason or f"Banned by {ctx.author}"

        try:
            await ctx.guild.ban(
                discord.Object(id=user_id), reason=reason, delete_message_days=1
            )
            await ctx.send("👍")
        except discord.Forbidden:
            await ctx.send("I don't have permission to ban that user.")
        except discord.HTTPException as e:
            await ctx.send(f"A fucky wucky occurred: {e}")

    @command(
        name="massban",
        aliases=["mban", "mb", "bulkban"],
        description="Mass bans users by User ID.",
    )
    @has_permissions(administrator=True)
    async def massban(self, ctx, *user_ids: int, reason: str = None):
        successful_bans = 0
        failed_bans = 0

        for user_id in user_ids:
            try:
                await ctx.guild.ban(
                    discord.Object(id=user_id),
                    reason=f"Mass banned by {ctx.author}"
                    + (f": {reason}" if reason else ""),
                )
                successful_bans += 1
            except discord.HTTPException:
                failed_bans += 1

        embed = discord.Embed(
            description=f"Successful Bans: {successful_bans}\n Failed Bans: {failed_bans}",
            color=0xFFFFFF,
        )
        await ctx.send(embed=embed)

    @command(
        name="hardban",
        aliases=["hb", "hban"],
        description="Bans a user by User ID and deletes their messages.",
    )
    @has_permissions(administrator=True)
    async def hardban(self, ctx, user_id: int, reason: str = None):
        try:
            await ctx.guild.ban(
                discord.Object(id=user_id),
                reason=f"Hard banned by {ctx.author}"
                + (f": {reason}" if reason else ""),
            )
            self.bot.db.execute(
                "INSERT INTO hardbanned_users (user_id, guild_id) VALUES (?, ?)",
                user_id,
                ctx.guild.id,
            )
            self.bot.db.commit()
            await ctx.send("👍")
        except discord.HTTPException as e:
            embed = discord.Embed(
                description=f"Uh oh, fucky wucky was made: {e}", color=0xFFFFFF
            )
            await ctx.send(embed=embed)

    @Cog.listener()
    async def on_member_unban(self, guild, user):
        if not guild.me.guild_permissions.ban_members:
            return

        async with self.bot.db.acquire() as conn:
            record = await conn.fetchrow(
                """
                SELECT * FROM hardbanned_users 
                WHERE user_id = $1 AND guild_id = $2
                """,
                user.id,
                guild.id,
            )

            if record:
                await guild.ban(
                    discord.Object(id=user.id),
                    reason=f"Automatically re-hardbanned by {self.bot.user}",
                )

    @command(
        name="banlist",
        aliases=["bans"],
        description="Shows list of users banned from the server.",
    )
    @has_permissions(administrator=True)
    async def ban_list(self, ctx):
        """Display the server's ban list in a paginated embed."""
        try:
            bans = [ban async for ban in ctx.guild.bans()]
            if not bans:
                await ctx.send("No one is currently banned in this server.")
                return

            view = BanListView(bans, ctx.author)
            embed = view.get_embed()
            await ctx.send(embed=embed, view=view)
        except Exception as e:
            await ctx.send(
                embed=discord.Embed(
                    title="Error",
                    description=f"An error occurred while fetching the ban list: {e}",
                    color=discord.Color(Colors.main),
                )
            )

    @command(
        name="unban",
        aliases=["befree"],
        description="Unbans a member by User ID or mention.",
    )
    @has_permissions(ban_members=True)
    async def unban(self, ctx, user: Union[discord.User, int, str]):
        """
        Unbans a user by their User ID or mention.
        Example: ,unban 1234567890 or ,unban @user
        """
        user_id = None

        if isinstance(user, int):
            user_id = user
        elif isinstance(user, discord.User):
            user_id = user.id
        elif isinstance(user, str):
            match = re.match(r"<@!?(\d+)>", user)
            if match:
                user_id = int(match.group(1))
            elif user.isdigit():
                user_id = int(user)
            else:
                return await ctx.send("Please provide a valid user mention or ID.")

        try:
            user_id = int(user_id)

            try:
                ban_entry = await ctx.guild.fetch_ban(discord.Object(user_id))
            except discord.NotFound:
                return await ctx.send("They're not even banned 😭")

            await ctx.guild.unban(ban_entry.user, reason=f"Unbanned by {ctx.author}")

            if (
                hasattr(self, "hardbanned_user_ids")
                and user_id in self.hardbanned_user_ids
            ):
                if ctx.author.guild_permissions.administrator:
                    self.bot.db.execute(
                        "DELETE FROM hardbanned_users WHERE user_id = ? AND guild_id = ?",
                        user_id,
                        ctx.guild.id,
                    )
                    self.bot.db.commit()

            await ctx.send("👍")

        except discord.Forbidden:
            await ctx.send("I don't have permissions to unban users :c")
        except discord.HTTPException as e:
            await ctx.send(f"Something went wrong 😭 {e}")
        except Exception as e:
            await ctx.send(f"Something went wrong 😭 {str(e)}")
            print(f"Unban error: {traceback.format_exc()}")

    @command(
        name="kick",
        aliases=["sock"],
        description="Kicks a member by mention or User ID.",
    )
    @has_permissions(kick_members=True)
    async def kick(
        self,
        ctx,
        member: discord.Member = None,
        user_id: int = None,
        *,
        reason: str = None,
    ):
        """
        Kicks a member from the server.
        """
        if user_id and not member:
            try:
                member = await ctx.guild.fetch_member(user_id)
            except discord.NotFound:
                await ctx.send("Bros tryna kick someone who's not even here 😭")
                return
            except discord.HTTPException:
                await ctx.send("An error occurred while fetching the user.")
                return
            if member.id in self.unmoderatable_user_ids:
                await ctx.send("no.")
                return

        if not member:
            await ctx.send(
                "What, are we kicking ghosts now? What in the ghostbusters are you trying to kick, specify a user.."
            )
            return

        if (
            member.top_role >= ctx.author.top_role
            and ctx.author.id != ctx.guild.owner_id
        ):
            embed = discord.Embed(
                description="You cannot kick this user due to role hierarchy.",
                color=0xFFFFFF,
            )
            await ctx.send(embed=embed)
            return

        try:
            await member.kick(reason=f"Kicked by {ctx.author}")
            await ctx.send(
                f"{member.mention} was kicked by {ctx.author.mention}"
                + (f" with reason: {reason}" if reason else "")
            )
        except discord.Forbidden:
            await ctx.send(
                "I am missing the required permissions to kick this user, please tick `Kick Members` for my role, then try again."
            )
        except discord.HTTPException:
            await ctx.send("Something went wrong, please try again.")
        except Exception as e:
            await ctx.send(
                "Something went wrong, <@1426711359059394662> check the terminal for more info."
            )
            print(
                f"Something went wrong when trying to kick {member.mention}: {str(e)}"
            )

    @command(
        name="timeout",
        aliases=["to", "bdsm", "ballgag", "stfu", "sybau", "smd"],
        description="Times out a member (e.g. ,to @user 7d, 24h, 60m)",
    )
    @has_permissions(moderate_members=True)
    async def timeout(self, ctx, member: discord.Member = None, duration: str = "5m"):
        if not member:
            await ctx.send("You must specify a user to timeout.")
            return

        if not self.can_moderate(ctx.author, member):
            return await ctx.send("no")

        if member.id in self.unmoderatable_user_ids:
            await ctx.send("no.")
            return

        try:
            amount = int(duration[:-1])
            unit = duration[-1].lower()

            if unit == "m":
                if not 1 <= amount <= 60:
                    return await ctx.send("Minutes must be between 1 and 60.")
                seconds = amount * 60
            elif unit == "h":
                if not 1 <= amount <= 24:
                    return await ctx.send("Hours must be between 1 and 24.")
                seconds = amount * 3600
            elif unit == "d":
                if not 1 <= amount <= 7:
                    return await ctx.send("Days must be between 1 and 7.")
                seconds = amount * 86400
            else:
                embed = discord.Embed(
                    description=f"Invalid time format; Max time is 7 days, minimum is 1 minute.",
                    color=discord.Color(0xFFFFFF),
                )
                return await ctx.send(embed=embed)

        except (ValueError, IndexError):
            embed = discord.Embed(
                description="Invalid duration format; Max time is 7 days, minimum is 1 minute.",
                color=discord.Color(0xFFFFFF),
            )
            return await ctx.send(embed=embed)

        try:
            await member.timeout(
                discord.utils.utcnow() + timedelta(seconds=seconds),
                reason=f"Timed out by {ctx.author}",
            )
            await ctx.send(
                f"Bad {member.mention}! Go sit in the naughty corner and think about what you did for {duration}! No cookies for you! 😠"
            )
        except discord.Forbidden:
            await ctx.send("I do not have permission to timeout this user.")
        except discord.HTTPException:
            await ctx.send("Failed to timeout the user.")

    @command(
        name="untimeout",
        aliases=["uto", "futo", "rto"],
        description="Removes the timeout from a member by mention or User ID.",
    )
    @has_permissions(moderate_members=True)
    async def remove_timeout(
        self, ctx, member: discord.Member = None, user_id: int = None
    ):
        target = await self.get_member(ctx, member, user_id)

        if not target:
            await ctx.send(
                "You must specify a user to remove timeout (mention or User ID)."
            )
            return

        try:
            await target.timeout(None, reason=f"Timeout removed by {ctx.author}")
            await ctx.send("👍")
        except discord.Forbidden:
            await ctx.send("I do not have permission to remove timeout from this user.")
        except discord.HTTPException:
            await ctx.send("Failed to remove timeout from the user.")

    @command(
        name="reactionmute",
        aliases=["rmute"],
        description="Revokes a users permissions to react in a channel.",
    )
    @has_permissions(moderate_members=True)
    async def reactionmute(self, ctx, member: discord.Member):
        """Revokes a users permissions to react in a channel."""
        channel = ctx.channel
        overwrite = channel.overwrites_for(member)
        overwrite.update(add_reactions=False)
        await channel.set_permissions(member, overwrite=overwrite)
        await ctx.send("👍")

    @command(
        name="reactionunmute",
        aliases=["rumute", "runmute"],
        description="Grants a users permissions to react in a channel.",
    )
    @has_permissions(moderate_members=True)
    async def reactionunmute(self, ctx, member: discord.Member):
        """Grants a users permissions to react in a channel."""
        channel = ctx.channel
        overwrite = channel.overwrites_for(member)
        overwrite.update(add_reactions=None)
        await channel.set_permissions(member, overwrite=overwrite)
        await ctx.send("👍")

    @group(
        name="nick",
        invoke_without_command=True,
        description="Base command for nickname management.",
    )
    @has_permissions(manage_nicknames=True)
    async def nick(self, ctx, member: discord.Member = None, *, new_nick: str = None):
        if ctx.invoked_subcommand is None:
            if member is None:
                member = ctx.author
            elif isinstance(member, str):
                member = discord.utils.get(ctx.guild.members, name=member)
            if member is None:
                await ctx.send(
                    "Member not found. Please mention a valid user or provide a correct name."
                )
                return
            if (
                member.id in self.unmoderatable_user_ids
                and ctx.author.id not in self.unmoderatable_user_ids
            ):
                await ctx.send("no.")
                return
            await self.set_nickname(ctx, member, new_nick=new_nick)

    @nick.command(
        name="set",
        aliases=["change"],
        description="Changes or resets the nickname of the mentioned user.",
    )
    async def set_nickname(
        self, ctx, member: discord.Member = None, *, new_nick: str = None
    ):
        if (
            new_nick in ["playfair", "playfairs"]
            and ctx.author.id != 1426711359059394662
        ):
            await ctx.send("No.")
            return

        if member is None:
            member = ctx.author

        if (
            member.id in self.unmoderatable_user_ids
            and ctx.author.id not in self.unmoderatable_user_ids
        ):
            return await ctx.send("no.")

        if member == ctx.guild.owner:
            return await ctx.send(
                "Even if I am above you, Discord has changed it so bots can no longer change the nickname of the owner."
            )

        if member.top_role >= ctx.author.top_role:
            return await ctx.send(
                "You cannot change the nickname of this user due to role hierarchy."
            )

        if member.top_role >= ctx.guild.me.top_role:
            return await ctx.send(
                "I cannot change the nickname of this user due to role hierarchy."
            )

        try:
            await member.edit(nick=new_nick)
            if new_nick:
                await ctx.send(
                    f"Nickname for {member.mention} changed to `{new_nick}`."
                )
            else:
                await ctx.send(f"Nickname for {member.mention} has been reset.")
        except discord.HTTPException as e:
            await ctx.send(f"Failed to change the nickname. Please try again. {e}")

    @nick.command(
        name="remove",
        aliases=["reset", "clear"],
        description="Removes the nickname of the mentioned user.",
    )
    async def remove_nickname(self, ctx, member: discord.Member = None):
        if not member:
            return await ctx.send(
                "You must specify a user to change the nickname (mention or User ID)."
            )

        if (
            member.id in self.unmoderatable_user_ids
            and ctx.author.id not in self.unmoderatable_user_ids
        ):
            return await ctx.send("no.")

        if member == ctx.guild.owner:
            return await ctx.send("Cannot change the nickname of the server owner.")

        if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            return await ctx.send(
                "You cannot change the nickname of this user due to role hierarchy."
            )

        if member.top_role >= ctx.guild.me.top_role:
            return await ctx.send(
                "I cannot change the nickname of this user due to role hierarchy."
            )

        try:
            await member.edit(nick=None)
            await ctx.send(f"Nickname for {member.mention} has been reset.")
        except discord.HTTPException as e:
            await ctx.send(f"Failed to reset the nickname. Please try again. {e}")

    @nick.command(
        name="force",
        description="Forces a nickname on a user that cannot be changed. If no nickname is provided, removes the forced nickname.",
    )
    @has_permissions(administrator=True)
    async def forcenick(
        self, ctx, member: discord.Member = None, *, forced_nick: Optional[str] = None
    ):
        if not member:
            return await ctx.send(
                "You must specify a user to change the nickname (mention or User ID)."
            )

        if (
            member.id in self.unmoderatable_user_ids
            and ctx.author.id not in self.unmoderatable_user_ids
        ):
            return await ctx.send("no.")

        if member == ctx.guild.owner:
            return await ctx.send("Cannot force nickname on the server owner.")

        if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            return await ctx.send(
                "You cannot force a nickname on this user due to role hierarchy."
            )

        if member.top_role >= ctx.guild.me.top_role:
            return await ctx.send(
                "I cannot force a nickname on this user due to role hierarchy."
            )

        try:
            if forced_nick:
                await self.bot.db.execute(
                    """
                    INSERT INTO forced_nicks (guild_id, user_id, nick)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (guild_id, user_id) DO UPDATE SET nick = $3
                    """,
                    ctx.guild.id,
                    member.id,
                    forced_nick,
                )
                await ctx.send(
                    f"Forced nickname for {member.mention} set to `{forced_nick}`."
                )
            else:
                await self.bot.db.execute(
                    """
                    DELETE FROM forced_nicks
                    WHERE guild_id = $1 AND user_id = $2
                    """,
                    ctx.guild.id,
                    member.id,
                )
                await ctx.send(
                    f"Forced nickname for {member.mention} has been removed."
                )
            await member.edit(nick=forced_nick)
        except discord.HTTPException as e:
            await ctx.send(f"Failed to change the nickname. Please try again. {e}")

    @Cog.listener()
    async def on_member_update(self, before, after):
        if before.nick != after.nick:
            async with self.bot.db.acquire() as conn:
                forced_nick = await conn.fetchval(
                    """
                    SELECT nick FROM forced_nicks
                    WHERE guild_id = $1 AND user_id = $2
                    """,
                    after.guild.id,
                    after.id,
                )
                if forced_nick and after.nick != forced_nick:
                    try:
                        await after.edit(nick=forced_nick)
                    except discord.HTTPException:
                        pass

    @Cog.listener()
    async def on_member_update(self, before, after):
        if before.nick != after.nick and after.nick is None:
            async with self.bot.db.acquire() as conn:
                forced_nick = await conn.fetchval(
                    """
                    SELECT nick FROM forced_nicks
                    WHERE guild_id = $1 AND user_id = $2
                    """,
                    after.guild.id,
                    after.id,
                )
                if forced_nick:
                    try:
                        await after.edit(nick=forced_nick)
                    except discord.HTTPException:
                        pass

    @hybrid_group(
        name="purge",
        aliases=["c", "clear"],
        invoke_without_command=True,
        description="Base command for purging messages.",
    )
    @cooldown(1, 5, BucketType.guild)
    @has_permissions(manage_messages=True)
    async def purge(self, ctx, amount: Union[int, discord.Member, discord.User] = None):
        if amount is None:
            await ctx.send_help(ctx.command)
            return
        
        if isinstance(amount, (discord.Member, discord.User)):
            target_user = amount
            messages_to_delete = []
            fourteen_days_ago = discord.utils.utcnow() - timedelta(days=14)
            
            async for message in ctx.channel.history(limit=50):
                if message.author == target_user and message.created_at > fourteen_days_ago:
                    messages_to_delete.append(message)
            
            if messages_to_delete:
                await ctx.channel.delete_messages(messages_to_delete)
                await ctx.send(
                    f"Purged {len(messages_to_delete)} messages from {target_user.mention} in {ctx.channel.mention}",
                    delete_after=5,
                )
            else:
                await ctx.send(
                    f"No messages found from {target_user.mention} in the last 50 messages (messages must be under 14 days old).",
                    delete_after=5,
                )
        elif isinstance(amount, int) and 1 <= amount <= 500:
            deleted = await ctx.channel.purge(limit=amount)
            await ctx.send(
                f"Purged {len(deleted)} messages in {ctx.channel.mention}",
                delete_after=5,
            )
        else:
            await ctx.send(
                "You must specify either a number of messages (1-500) or mention a user to purge their messages."
            )

    @purge.command(
        name="from",
        aliases=["user"],
        description="Purges messages from a specified user.",
    )
    @cooldown(1, 5, BucketType.guild)
    @app_commands.describe(
        user="The user to purge messages from.",
        amount="The amount of messages to purge.",
    )
    @has_permissions(manage_messages=True)
    async def purge_from(self, ctx, user: discord.User, amount: int = 20):
        if amount <= 0 or amount > 100:
            return await ctx.send("Amount must be between 1 and 100.", delete_after=5)

        if ctx.interaction:
            await ctx.interaction.response.defer()

        user_messages = []
        async for message in ctx.channel.history(limit=200):
            if message.author.id == user.id:
                user_messages.append(message)
                if len(user_messages) >= amount:
                    break

        if user_messages:
            await ctx.channel.delete_messages(user_messages)
            await ctx.send(
                f"Purged {len(user_messages)} messages from {user.mention}.",
                delete_after=5,
            )
        else:
            await ctx.send(
                f"No messages were found from {user.mention} in the recent messages.",
                delete_after=5,
            )

    @purge.command(
        name="before", description="Deletes all messages before a specified message ID."
    )
    @cooldown(1, 5, BucketType.guild)
    @app_commands.describe(
        message_id="The message ID to delete messages before.",
    )
    @has_permissions(manage_messages=True)
    async def purge_before(self, ctx, message_id: str):
        if ctx.interaction:
            await ctx.interaction.response.defer()

        message = await ctx.channel.fetch_message(int(message_id))
        deleted = await ctx.channel.purge(limit=100, before=message, oldest_first=True)
        await ctx.send(
            f"Purged {len(deleted)} messages before https://discord.com/channels/{ctx.guild.id}/{ctx.channel.id}/{message.id}",
            delete_after=5,
            ephemeral=True,
        )

    @purge.command(
        name="after", description="Deletes all messages after a specified message ID."
    )
    @cooldown(1, 5, BucketType.guild)
    @app_commands.describe(
        message_id="The message ID to delete messages after.",
    )
    @has_permissions(manage_messages=True)
    async def purge_after(self, ctx, message_id: str):
        if ctx.interaction:
            await ctx.interaction.response.defer()

        message = await ctx.channel.fetch_message(int(message_id))
        deleted = await ctx.channel.purge(limit=100, after=message, oldest_first=True)
        await ctx.send(
            f"Purged {len(deleted)} messages after https://discord.com/channels/{ctx.guild.id}/{ctx.channel.id}/{message.id}",
            delete_after=5,
            ephemeral=True,
        )

    @purge.command(
        name="bot",
        description="Deletes the last 100 bot related messages (Bot messages and commands).",
    )
    @cooldown(1, 5, BucketType.guild)
    @app_commands.describe(
        amount="The amount of messages to check (defaults to 50).",
        bot="The specific bot to purge messages from (optional).",
    )
    @has_permissions(manage_messages=True)
    async def purge_bot(
        self, ctx, bot: Optional[discord.Member] = None, amount: Optional[int] = 50
    ):
        if isinstance(bot, int) and amount == 50:
            amount = bot
            bot = None

        try:
            if ctx.interaction:
                await ctx.interaction.response.defer()

            messages_to_delete = []
            trigger_message = None
            
            async for message in ctx.channel.history(limit=amount):
                if hasattr(ctx, "message") and message.id == ctx.message.id:
                    trigger_message = message
                    continue

                if bot:
                    if message.author == bot:
                        messages_to_delete.append(message)
                elif (
                    message.author.bot
                    or message.author.id in self.users_triggered_bot
                    or message.content.startswith((";", ","))
                ):
                    messages_to_delete.append(message)

            if trigger_message:
                messages_to_delete.append(trigger_message)

            if messages_to_delete:
                await ctx.channel.delete_messages(messages_to_delete)

            response = (
                f"Purged {len(messages_to_delete)} bot messages in {ctx.channel.mention}"
                if messages_to_delete
                else f"No bot messages were found in the last {amount} messages."
            )

            if ctx.interaction:
                await ctx.interaction.followup.send(response, ephemeral=True)
                await asyncio.sleep(5)
                await ctx.interaction.delete_original_response()
            else:
                await ctx.send(response, delete_after=5)

        except Exception as e:
            error_msg = f"Failed to purge messages: {str(e)}"
            if ctx.interaction:
                await ctx.interaction.followup.send(error_msg, ephemeral=True)
            else:
                await ctx.send(error_msg)

    @purge.command(
        name="self", description="Deletes the last 100 messages from the author."
    )
    @cooldown(1, 5, BucketType.guild)
    @has_permissions(manage_messages=True)
    async def purge_self(self, ctx):
        try:
            if ctx.interaction:
                await ctx.interaction.response.defer()

            messages = [message async for message in ctx.channel.history(limit=100)]
            messages_to_delete = [
                message for message in messages if message.author == ctx.author
            ]

            if messages_to_delete:
                await ctx.channel.delete_messages(messages_to_delete)
                await ctx.send(
                    f"Purged {len(messages_to_delete)} messages from {ctx.author.mention}",
                    delete_after=5,
                )
            else:
                await ctx.send(
                    "No messages were found from you, weird isn't it?", delete_after=5
                )
        except discord.HTTPException:
            await ctx.send(
                "Failed to purge messages. Please try again.", delete_after=5
            )

    @purge.command(
        name="attachments",
        description="Deletes the last 100 messages with attachments.",
    )
    @cooldown(1, 5, BucketType.guild)
    @has_permissions(manage_messages=True)
    async def purge_attachments(self, ctx):
        try:
            if ctx.interaction:
                await ctx.interaction.response.defer()

            messages = [message async for message in ctx.channel.history(limit=100)]
            messages_to_delete = [
                message for message in messages if message.attachments
            ]

            if messages_to_delete:
                await ctx.channel.delete_messages(messages_to_delete)
                response = f"Purged {len(messages_to_delete)} attachments in {ctx.channel.mention}"
            else:
                response = f"No attachments were found in {ctx.channel.mention}"

            if ctx.interaction:
                await ctx.interaction.followup.send(response, ephemeral=False)
            else:
                await ctx.send(response, delete_after=5)

        except Exception as e:
            error_msg = f"Failed to purge messages: {str(e)}"
            if ctx.interaction:
                if ctx.interaction.response.is_done():
                    await ctx.interaction.followup.send(error_msg, ephemeral=True)
                else:
                    await ctx.interaction.response.send_message(
                        error_msg, ephemeral=True
                    )
            else:
                await ctx.send(error_msg, delete_after=5)

    @purge.command(
        name="links",
        aliases=["url"],
        description="Deletes the last 100 messages with links.",
    )
    @cooldown(1, 5, BucketType.guild)
    @has_permissions(manage_messages=True)
    async def purge_links(self, ctx):
        try:
            if ctx.interaction:
                await ctx.interaction.response.defer()

            messages = [message async for message in ctx.channel.history(limit=100)]
            messages_to_delete = [
                message
                for message in messages
                if (
                    message.content.startswith("https://")
                    or message.content.startswith("http://")
                )
                and not message.content.split(".")[-1].lower()
                in [
                    "png",
                    "gif",
                    "jpeg",
                    "jpg",
                    "webp",
                    "mp4",
                    "mov",
                    "avi",
                    "mkv",
                    "flv",
                ]
            ]

            if messages_to_delete:
                await ctx.channel.delete_messages(messages_to_delete)
                await ctx.send(
                    f"Purged {len(messages_to_delete)} links in {ctx.channel.mention}",
                    delete_after=5,
                )
            else:
                await ctx.send(
                    f"No links were found in {ctx.channel.mention}", delete_after=5
                )
        except discord.HTTPException:
            await ctx.send(
                "Failed to purge messages. Please try again.", delete_after=5
            )

    @purge.command(
        name="contains",
        description="Deletes the last 100 messages containing the specified text.",
    )
    @cooldown(1, 5, BucketType.guild)
    @has_permissions(manage_messages=True)
    async def purge_contains(self, ctx, *, text: str):
        try:
            if ctx.interaction:
                await ctx.interaction.response.defer()

            messages = [message async for message in ctx.channel.history(limit=100)]
            messages_to_delete = [
                message for message in messages if text in message.content
            ]

            if messages_to_delete:
                await ctx.channel.delete_messages(messages_to_delete)
                response = f"Purged {len(messages_to_delete)} messages containing '{text}' in {ctx.channel.mention}"
            else:
                response = f"No messages containing '{text}' were found in {ctx.channel.mention}"

            if ctx.interaction:
                await ctx.interaction.followup.send(response, ephemeral=False)
            else:
                await ctx.send(response, delete_after=5)

        except Exception as e:
            error_msg = f"Failed to purge messages: {str(e)}"
            if ctx.interaction:
                if ctx.interaction.response.is_done():
                    await ctx.interaction.followup.send(error_msg, ephemeral=True)
                else:
                    await ctx.interaction.response.send_message(
                        error_msg, ephemeral=True
                    )
            else:
                await ctx.send(error_msg, delete_after=5)

    @purge.command(
        name="endswith",
        description="Deletes the last 100 messages ending with the specified text.",
    )
    @cooldown(1, 5, BucketType.guild)
    @has_permissions(manage_messages=True)
    async def purge_endswith(self, ctx, *, text: str):
        try:
            if ctx.interaction:
                await ctx.interaction.response.defer()

            messages = [message async for message in ctx.channel.history(limit=100)]
            messages_to_delete = [
                message for message in messages if message.content.endswith(text)
            ]

            if messages_to_delete:
                await ctx.channel.delete_messages(messages_to_delete)
                await ctx.send(
                    f"Purged {len(messages_to_delete)} messages ending with '{text}' in {ctx.channel.mention}",
                    delete_after=5,
                )
            else:
                await ctx.send(
                    f"No messages ending with '{text}' were found in {ctx.channel.mention}",
                    delete_after=5,
                )
        except discord.HTTPException:
            await ctx.send(
                "Failed to purge messages. Please try again.", delete_after=5
            )

    @purge.command(
        name="startswith",
        description="Deletes the last 100 messages starting with the specified text.",
    )
    @cooldown(1, 5, BucketType.guild)
    @has_permissions(manage_messages=True)
    async def purge_startswith(self, ctx, *, text: str):
        try:
            if ctx.interaction:
                await ctx.interaction.response.defer()

            messages = [message async for message in ctx.channel.history(limit=100)]
            messages_to_delete = [
                message for message in messages if message.content.startswith(text)
            ]

            if messages_to_delete:
                await ctx.channel.delete_messages(messages_to_delete)
                await ctx.send(
                    f"Purged {len(messages_to_delete)} messages starting with '{text}' in {ctx.channel.mention}",
                    delete_after=5,
                )
            else:
                await ctx.send(
                    f"No messages starting with '{text}' were found in {ctx.channel.mention}",
                    delete_after=5,
                )
        except discord.HTTPException:
            await ctx.send(
                "Failed to purge messages. Please try again.", delete_after=5
            )

    @purge.command(
        name="invites",
        description="Deletes the last 100 messages containing an invite link.",
    )
    @cooldown(1, 5, BucketType.guild)
    @has_permissions(manage_messages=True)
    async def purge_invites(self, ctx):
        try:
            if ctx.interaction:
                await ctx.interaction.response.defer()

            messages = [message async for message in ctx.channel.history(limit=100)]
            messages_to_delete = [
                message for message in messages if "discord.gg/" in message.content
            ]

            if messages_to_delete:
                await ctx.channel.delete_messages(messages_to_delete)
                await ctx.send(
                    f"Purged {len(messages_to_delete)} invite links in {ctx.channel.mention}",
                    delete_after=5,
                )
            else:
                await ctx.send(
                    f"No invite links were found in {ctx.channel.mention}",
                    delete_after=5,
                )
        except discord.HTTPException:
            await ctx.send(
                "Failed to purge messages. Please try again.", delete_after=5
            )

    @purge.command(
        name="mentions",
        description="Deletes the last 100 messages containing a mention.",
    )
    @cooldown(1, 5, BucketType.guild)
    @has_permissions(manage_messages=True)
    async def purge_mentions(self, ctx, *, user: discord.Member = None):
        try:
            if ctx.interaction:
                await ctx.interaction.response.defer()

            messages = [message async for message in ctx.channel.history(limit=100)]
            if user:
                messages_to_delete = [
                    message for message in messages if user.mention in message.content
                ]
            else:
                messages_to_delete = [
                    message for message in messages if "@" in message.content
                ]
            if messages_to_delete:
                await ctx.channel.delete_messages(messages_to_delete)
                if user:
                    await ctx.send(
                        f"Purged {len(messages_to_delete)} messages mentioning {user.mention} in {ctx.channel.mention}",
                        delete_after=5,
                    )
                else:
                    await ctx.send(
                        f"Purged {len(messages_to_delete)} mentions in {ctx.channel.mention}",
                        delete_after=5,
                    )
            else:
                if user:
                    await ctx.send(
                        f"No messages mentioning {user.mention} were found in {ctx.channel.mention}",
                        delete_after=5,
                    )
                else:
                    await ctx.send(
                        f"No mentions were found in {ctx.channel.mention}",
                        delete_after=5,
                    )
        except discord.HTTPException:
            await ctx.send(
                "Failed to purge messages. Please try again.", delete_after=5
            )

    @purge.command(
        name="reactions", description="Deletes all reactions on the last 100 messages."
    )
    @cooldown(1, 5, BucketType.guild)
    @has_permissions(manage_messages=True)
    async def purge_reactions(self, ctx):
        try:
            if ctx.interaction:
                await ctx.interaction.response.defer()

            messages = [message async for message in ctx.channel.history(limit=100)]
            for message in messages:
                if message.reactions:
                    for reaction in message.reactions:
                        await reaction.clear()
            await ctx.send(f"Purged reactions in {ctx.channel.mention}", delete_after=5)
        except discord.HTTPException:
            await ctx.send(
                "Failed to purge reactions. Please try again.", delete_after=5
            )

    @purge.command(
        name="stickers", description="Deletes all stickers on the last 100 messages."
    )
    @cooldown(1, 5, BucketType.guild)
    @has_permissions(manage_messages=True)
    async def purge_stickers(self, ctx):
        await ctx.send("idk how to do that :c", delete_after=5)
        await ctx.send("Just kidding!")
        try:
            if ctx.interaction:
                await ctx.interaction.response.defer()

                messages = [message async for message in ctx.channel.history(limit=100)]
            messages_to_delete = [message for message in messages if message.stickers]
            if messages_to_delete:
                await ctx.channel.delete_messages(messages_to_delete)
                await ctx.send(
                    f"Purged {len(messages_to_delete)} stickers in {ctx.channel.mention}",
                    delete_after=5,
                )
            else:
                await ctx.send(
                    f"No stickers were found in {ctx.channel.mention}", delete_after=5
                )
        except discord.HTTPException:
            await ctx.send(
                "Failed to purge stickers. Please try again.", delete_after=5
            )

    @purge.command(name="all", description="Please don't use this command 😭..")
    @cooldown(1, 5, BucketType.guild)
    @has_permissions(administrator=True)
    async def purge_all(self, ctx):
        if ctx.interaction:
            await ctx.interaction.response.defer()

        await ctx.send(
            "bro, at that point just nuke the channel 😭, im not gonna rate limit myself bc you wanna purge every message in this channel"
        )
        button = discord.ui.Button(
            label="Nuke",
            style=discord.ButtonStyle.red,
            custom_id="nuke",
            disabled=False,
            url=None,
        )

        async def nuke_callback(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                await interaction.response.send_message(
                    "You can't use this button.", ephemeral=True
                )
                return
            await interaction.response.defer()
            await interaction.followup.send("Nuking channel...", ephemeral=True)
            await ctx.invoke(self.bot.get_command("nuke"))

        button.callback = nuke_callback

        view = discord.ui.View()
        view.add_item(button)
        await ctx.send(view=view)

    @command(name="bc", description="Invocation for purge bot.")
    @cooldown(1, 5, BucketType.guild)
    @has_permissions(manage_messages=True)
    async def botclear(self, ctx, amount: int = None):
        """Invocation for purge bot."""
        await self.bot.get_command("purge bot").invoke(ctx)

    @command(
        name="nuke",
        aliases=[
            "arab",
            "twintowers",
            "hiroshima",
            "nagasaki",
            "japan1945",
            "ww2",
            "boomboom",
            "no_witnesses",
            "allahuakbar",
            "tsarbomba",
            "saint",
        ],
        description="Nukes the current channel with confirmation.",
    )
    @cooldown(1, 10, BucketType.guild)
    @has_permissions(administrator=True)
    @bot_has_permissions(administrator=True)
    async def nuke(self, ctx):
        """Nukes the current channel with confirmation."""
        embed = discord.Embed(
            title="Nuke?",
            description="Are you sure you want to nuke this channel? This action cannot be undone.\n\n-# This will delete this channel and replace it with a new one.",
            color=discord.Color(0xFFFFFF),
        )

        view = ConfirmView(ctx, ctx.channel)
        await ctx.send(embed=embed, view=view)

    @hybrid_group(
        name="role",
        aliases=["r"],
        description="Base Command for managing roles.",
        invoke_without_command=True,
    )
    @has_permissions(manage_roles=True)
    @app_commands.describe(
        member="The member to assign the role to.",
        role_input="The role to assign to the member.",
    )
    async def role(self, ctx, member: discord.Member = None, *, role_input: str = None):
        if member and role_input:
            await self.give_role(ctx, member, role_input)
        else:
            await ctx.send_help(ctx.command)

    @role.command(
        name="human",
        aliases=["humans"],
        description="Assigns all non-bots in the server a specific role (Needs to be rewritten)",
    )
    @has_permissions(manage_roles=True)
    @app_commands.describe(
        role="The role to assign to all non-bots in the server.",
    )
    async def role_human(self, ctx, role: discord.Role):
        count = len(
            [member for member in ctx.guild.members if role not in member.roles]
        )
        await self.send_embed(
            ctx,
            f"Adding {role.mention} to {count} human members, this may take a moment...",
        )

        for member in ctx.guild.members:
            if role not in member.roles:
                await member.add_roles(role)

        await self.send_embed(
            ctx, f"Role {role.mention} has been given to {count} human members."
        )

    @role.command(
        name="bot",
        aliases=["bots"],
        description="Assigns all bots in the server a specific role (Needs to be rewritten)",
    )
    @has_permissions(manage_roles=True)
    @app_commands.describe(
        role="The role to assign to all bots in the server.",
    )
    async def role_bot(self, ctx, role: discord.Role):
        count = len([member for member in ctx.guild.members if member.bot])
        await self.send_embed(
            ctx,
            f"Adding {role.mention} to {count} bot members, this may take a moment...",
        )

        for member in ctx.guild.members:
            if member.bot:
                await member.add_roles(role)

        await self.send_embed(
            ctx, f"Role {role.mention} has been given to {count} bot members."
        )

    @role.command(
        name="has",
        description="Gives or removes a role to/from members who have a specific role.",
    )
    @has_permissions(manage_roles=True)
    @app_commands.describe(
        role="The role to check for.",
        action="The action to perform (give or remove).",
        new_role="The role to give or remove.",
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="Give", value="give"),
            app_commands.Choice(name="Remove", value="remove"),
        ]
    )
    async def role_has(
        self,
        ctx,
        role: discord.Role,
        action: app_commands.Choice[str],
        new_role: discord.Role,
    ):
        count = len([member for member in ctx.guild.members if role in member.roles])
        if action.value == "give":
            await self.send_embed(
                ctx,
                f"Adding {new_role.mention} to {count} members, this may take a moment...",
            )
        elif action.value == "remove":
            await self.send_embed(
                ctx,
                f"Removing {new_role.mention} from {count} members, this may take a moment...",
            )

        for member in ctx.guild.members:
            if role in member.roles:
                if action.value == "give":
                    await member.add_roles(new_role)
                elif action.value == "remove":
                    await member.remove_roles(new_role)

        embed = discord.Embed(
            description=f"{Emojis.check} Role {new_role.mention} has been {'added to' if action.value == 'give' else 'removed from'} {count} members.",
            color=0xFFFFFF,
        )
        await ctx.send(embed=embed)

    @role.command(name="create", description="Creates a role.")
    @has_permissions(manage_roles=True)
    @app_commands.describe(
        role_name="The name of the role to create.",
    )
    async def role_create(self, ctx, *, role_name: str):
        guild = ctx.guild
        await guild.create_role(name=role_name)
        await self.send_embed(ctx, f"Role {role_name} created successfully.")

    @role.command(name="delete", description="Deletes a role.")
    @has_permissions(manage_roles=True)
    @app_commands.describe(
        role="The role to delete.",
    )
    async def role_delete(self, ctx, role: discord.Role):
        await role.delete()
        await self.send_embed(ctx, f"Role {role.mention} has been deleted.")

    @role.command(
        name="give",
        description="Gives a role to a member. (Doing ,r {member} {role} also does this.)",
    )
    @has_permissions(manage_roles=True)
    @app_commands.describe(
        member="The member to give the role to.",
        role="The role to give to the member.",
    )
    async def role_give(self, ctx: Context, member: discord.Member, role: discord.Role):
        if role.position >= ctx.author.top_role.position:
            await ctx.send(
                "You cannot manage a role that is higher or equal to your highest role.",
                ephemeral=True,
            )
            return

        if role.position >= ctx.guild.me.top_role.position:
            await ctx.send(
                "I cannot manage a role that is higher or equal to my highest role.",
                ephemeral=True,
            )
            return

        try:
            if role in member.roles:
                await ctx.send(
                    f"{member.mention} already has the {role.name} role.",
                    ephemeral=True,
                )
                return

            await member.add_roles(role, reason=f"Role added by {ctx.author}")
            embed = discord.Embed(
                description=f"{Emojis.check} Role {role.mention} has been given to {member.mention}",
                color=0xFFFFFF,
            )
            await ctx.send(embed=embed)

        except discord.Forbidden:
            await ctx.send(
                "I do not have permission to manage this role.", ephemeral=True
            )
        except discord.HTTPException:
            await ctx.send("An error occurred while managing the role.", ephemeral=True)

    @role.command(
        name="remove",
        description="Removes a role from a member. (Doing ,r {member} {role} also does this.)",
    )
    @has_permissions(manage_roles=True)
    @app_commands.describe(
        member="The member to remove the role from.",
        role="The role to remove from the member.",
    )
    async def role_remove(
        self, ctx: Context, member: discord.Member, role: discord.Role
    ):
        try:
            if role not in member.roles:
                await ctx.send(
                    f"{member.mention} doesn't have the {role.mention} role.",
                    ephemeral=True,
                )
                return

            await member.remove_roles(role, reason=f"Role removed by {ctx.author}")
            embed = discord.Embed(
                description=f"{Emojis.check} Role {role.mention} has been removed from {member.mention}",
                color=0xFFFFFF,
            )
            await ctx.send(embed=embed)

        except discord.Forbidden:
            await ctx.send(
                "I do not have permission to manage this role.", ephemeral=True
            )
        except discord.HTTPException:
            await ctx.send("An error occurred while managing the role.", ephemeral=True)

    @role.command(
        name="rename", aliases=["name"], description="Changes the name of a role."
    )
    @has_permissions(manage_roles=True)
    @app_commands.describe(
        role="The role to rename.",
        new_name="The new name for the role.",
    )
    async def role_rename(self, ctx: Context, role: discord.Role, new_name: str):
        await role.edit(name=new_name)
        embed = discord.Embed(
            description=f"{Emojis.check} Role {role.mention} has been renamed to '{new_name}'.",
            color=0xFFFFFF,
        )
        await ctx.send(embed=embed)

    @role.command(name="hoist", description="Toggles whether a role is hoisted or not.")
    @has_permissions(manage_roles=True)
    @app_commands.describe(
        role="The role to toggle hoisting for.",
        hoist="The hoist value to set for the role.",
    )
    async def role_hoist(self, ctx: Context, role: discord.Role, hoist: str = None):
        if hoist is not None:
            if hoist.lower() in ("true", "yes", "on"):
                hoist_value = True
            elif hoist.lower() in ("false", "no", "off"):
                hoist_value = False
            else:
                await ctx.send(
                    "Please specify `true` or `false` for the hoist argument."
                )
                return
        else:
            hoist_value = not role.hoist

        try:
            await role.edit(hoist=hoist_value, reason=f"Hoist changed by {ctx.author}")
            state = "now displayed" if hoist_value else "no longer displayed"
            embed = discord.Embed(
                description=f"{Emojis.check} Role {role.mention} is {state} separately.",
                color=0xFFFFFF,
            )
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send("I don't have permission to edit this role.")
        except discord.HTTPException as e:
            await ctx.send(f"An error occurred while updating the role: {str(e)}")

    @role.command(name="color", description="Changes the color of a role.")
    @has_permissions(manage_roles=True)
    @app_commands.describe(
        role="The role to change the color of.",
        color_hex="The color hex code to set for the role.",
    )
    async def role_color(self, ctx: Context, role: discord.Role, color_hex: str):
        try:
            color = discord.Color(int(color_hex.lstrip("#"), 16))
            await role.edit(color=color)
            embed = discord.Embed(
                description=f"{Emojis.check} Role {role.mention}'s color has been changed to {color_hex}.",
                color=0xFFFFFF,
            )
            await ctx.send(embed=embed)
        except ValueError:
            await ctx.send(
                "Invalid color hex code. Please provide a valid hex color (e.g., #00ff00)."
            )

    @role.command(
        name="mentionable", description="Toggles whether a role is mentionable or not."
    )
    @has_permissions(manage_roles=True)
    @app_commands.describe(
        role="The role to toggle mentionability for.",
    )
    async def role_mentionable(self, ctx: Context, role: discord.Role):
        try:
            if ctx.guild.me.top_role <= role:
                return await ctx.send(
                    "I cannot manage a role that is higher or equal to my highest role."
                )

            if role.mentionable:
                await role.edit(mentionable=False)
                embed = discord.Embed(
                    description=f"{Emojis.check} Role {role.mention} is now no longer mentionable.",
                    color=0xFFFFFF,
                )
                await ctx.send(embed=embed)
            else:
                await role.edit(mentionable=True)
                embed = discord.Embed(
                    description=f"{Emojis.check} Role {role.mention} is now mentionable.",
                    color=0xFFFFFF,
                )
                await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send("I don't have permission to edit this role.")
        except discord.HTTPException as e:
            await ctx.send(f"An error occurred while updating the role: {str(e)}")

    @role.command(name="info", description="Gives information about a role.")
    @app_commands.describe(
        role="The role to get information about.",
    )
    async def role_info(self, ctx: Context, *, role: discord.Role = None):
        if not role:
            role = ctx.author.top_role

        if not isinstance(role, discord.Role):
            try:
                role = discord.utils.get(
                    ctx.guild.roles, name=role
                ) or discord.utils.get(ctx.guild.roles, mention=role)
                if not role:
                    embed = discord.Embed(
                        description=f"{Emojis.error} Role not found. Please specify a valid role.",
                        color=0xFFFFFF,
                    )
                    return await ctx.send(embed=embed)
            except:
                embed = discord.Embed(
                    description=f"{Emojis.error} Role not found. Please specify a valid role.",
                    color=0xFFFFFF,
                )
                return await ctx.send(embed=embed)

        members_with_role = len(
            [member for member in ctx.guild.members if role in member.roles]
        )

        role_type = "Member"
        permissions = role.permissions
        if permissions.administrator:
            role_type = "Admin"
        elif (
            permissions.manage_guild
            or permissions.manage_channels
            or permissions.manage_roles
            or permissions.manage_webhooks
        ):
            role_type = "Staff"
        elif (
            permissions.moderate_members
            or permissions.kick_members
            or permissions.ban_members
            or permissions.view_audit_log
            or permissions.change_nickname
            or permissions.manage_nicknames
            or permissions.manage_messages
        ):
            role_type = "Mod"

        embed = discord.Embed(title=role.name, color=role.color)

        if role.icon:
            embed.set_thumbnail(url=role.icon.url)

        display_info = f"> **Color:** {str(role.color)}\n> **Hoisted:** {'Yes' if role.hoist else 'No'}"
        role_info = f"> **Inrole:** {members_with_role}\n> **Permissions:** {role_type}\n> **Position:** {role.position}/{len(ctx.guild.roles)}"
        other_info = f"> **Mentionable:** {'Yes' if role.mentionable else 'No'}"
        embed.add_field(name="Display", value=display_info, inline=True)
        embed.add_field(name="Role Information", value=role_info, inline=True)
        embed.add_field(name="Other Information", value=other_info, inline=True)

        embed.set_footer(
            text=f"Role ID: {role.id} - Created at {role.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )

        await ctx.send(embed=embed)

    @role.command(name="list", description="Lists all roles in the server.")
    @has_permissions(manage_roles=True)
    @app_commands.describe(user="The user to list roles for.")
    async def roles(self, ctx, user: discord.Member = None):
        if user:
            roles = sorted(user.roles, key=lambda r: r.position, reverse=True)
            if len(roles) == 1 and roles[0] == ctx.guild.default_role:
                return await ctx.send(f"{user.mention} doesn't have any roles.")
        else:
            roles = sorted(ctx.guild.roles, key=lambda r: r.position, reverse=True)
        custom_emojis = {
            "left": Emojis.left,
            "right": Emojis.right,
        }
        view = RolesView(roles, ctx.author, custom_emojis, target_user=user)
        embed = view.get_embed()
        await ctx.send(embed=embed, view=view)

    @role.command(
        name="restore",
        description="Restores a user's recently removed roles (within the last hour).",
    )
    @has_permissions(administrator=True)
    @app_commands.describe(user="The user to restore roles for.")
    async def restore(self, ctx, user: discord.Member):
        now = datetime.now(timezone.utc)
        one_hour_ago = now - timedelta(hours=1)

        async with self.bot.db.acquire() as conn:
            result = await conn.fetch(
                """
                SELECT * FROM removed_roles 
                WHERE user_id = $1 AND guild_id = $2 AND timestamp > $3
                ORDER BY timestamp DESC
                """,
                user.id,
                ctx.guild.id,
                one_hour_ago,
            )

            if not result:
                embed = discord.Embed(
                    description=f"{Emojis.error} User {user.mention} has no roles to restore from the last hour.",
                    color=0xFF0000,
                )
                return await ctx.send(embed=embed)

            restored_roles = []
            failed_roles = []
            role_ids_to_remove = []

            for row in result:
                role = ctx.guild.get_role(row["role_id"])
                if role:
                    try:
                        await user.add_roles(role, reason="Role restoration")
                        restored_roles.append(role.mention)
                        role_ids_to_append = (user.id, ctx.guild.id, role.id)
                        role_ids_to_remove.append(role_ids_to_append)
                    except discord.Forbidden:
                        failed_roles.append(f"<@&{role.id}")

            if role_ids_to_remove:
                await conn.executemany(
                    """
                    DELETE FROM removed_roles 
                    WHERE user_id = $1 AND guild_id = $2 AND role_id = $3
                    """,
                    role_ids_to_remove,
                )

            description = []
            if restored_roles:
                description.append(
                    f"{Emojis.check} **Restored the following roles for {user.mention}:**\n"
                    + "\n".join(f"• {role}" for role in restored_roles)
                )

            if failed_roles:
                description.append(
                    f"\n{Emojis.error} **Failed to restore the following roles:**\n"
                    + "\n".join(f"• {role}" for role in failed_roles)
                )

            if not (restored_roles or failed_roles):
                description.append(
                    f"{Emojis.error} No roles could be restored for {user.mention}."
                )

            embed = discord.Embed(
                description="\n\n".join(description),
                color=0x00FF00 if restored_roles else 0xFF0000,
            )
            await ctx.send(embed=embed)

    @Cog.listener()
    async def on_member_update(self, before, after):
        removed_roles = [role for role in before.roles if role not in after.roles]
        if removed_roles:
            now = datetime.now(timezone.utc)
            async with self.bot.db.acquire() as conn:
                for role in removed_roles:
                    await conn.execute(
                        """
                        INSERT INTO removed_roles (user_id, guild_id, role_id, timestamp)
                        VALUES ($1, $2, $3, $4)
                        ON CONFLICT (user_id, guild_id, role_id) DO UPDATE
                        SET timestamp = EXCLUDED.timestamp
                        """,
                        after.id,
                        after.guild.id,
                        role.id,
                        now,
                    )

    @hybrid_group(name="inrole", aliases=["ir"], invoke_without_command=True)
    async def inrole(self, ctx, role: discord.Role):
        """Displays all members in a specific role with interactive buttons."""
        members = role.members
        if not members:
            await ctx.send(f"No members found in the role {role.mention}.")
            return

        member_chunks = [members[i : i + 10] for i in range(0, len(members), 10)]
        current_page = 0

        view = PaginationView(member_chunks, ctx, role)
        embed = view.create_embed(current_page)
        view.message = await ctx.send(embed=embed, view=view)

    @inrole.command(name="kick", description="kicks all users within a specific role")
    @has_permissions(manage_guild=True, kick_members=True)
    @bot_has_permissions(kick_members=True)
    async def inrole_kick(self, ctx, role: discord.Role, *, reason: str = "No reason provided"):
        members = [m for m in role.members if m != ctx.author and m != ctx.guild.owner]

        if not members:
            await ctx.send(f"No members found in {role.member}.")
            return

        kicked = []
        failed = []

        for member in members:
            try:
                await member.kick(reason=reason)
                kicked.append(str(member))
            except Exception:
                failed.append(str(member))

        embed = discord.Embed(
            title="inrole kick worked",
            color=discord.Color.orange()
        )

        embed.add_field(
            name=f"Kicked ({len(kicked)})",
            value="\n".join(kicked[:20]) or "None",
            inline=False
        )

        if failed:
            embed.add_field(
                name=f"Failed ({len(failed)})",
                value="\n".join(failed[:20]),
                inline=False
            )

        embed.set_footer(text=f"role: {role.name}")
        await ctx.send(embed=embed)

    @commands.group(name="jail", invoke_without_command=True)
    @has_permissions(moderate_members=True)
    async def jail(self, ctx, member: discord.Member, *, reason="No reason provided"):
        """Jails a user, applying the jailed role and logging the event."""
        if not self.can_moderate(ctx.author, member):
            return await ctx.send("You cannot jail this user due to role hierarchy!")

        guild = ctx.guild
        jailed_role = discord.utils.get(guild.roles, name="Jailed")
        jail_logs_channel = discord.utils.get(guild.text_channels, name="jail-logs")

        if not jailed_role:
            embed = discord.Embed(
                description="Jailed role does not exist. Run `;jail setup` first.",
                color=0xFFFFFF,
            )
            await ctx.send(embed=embed)
            return
        if not jail_logs_channel:
            embed = discord.Embed(
                description="Jail logs channel does not exist. Run `;jail setup` first.",
                color=0xFFFFFF,
            )
            await ctx.send(embed=embed)
            return

        await member.add_roles(jailed_role)

        self.case_count += 1

        embed = discord.Embed(title="Jail-Logs Entry", color=discord.Color.green())
        embed.add_field(
            name="Information",
            value=(
                f"**Case #{self.case_count} | Jail**\n"
                f"**User:** {member.mention} (`{member.id}`)\n"
                f"**Moderator:** {ctx.author.mention} (`{ctx.author.id}`)\n"
                f"**Reason:** {reason}\n"
                f"{datetime.utcnow().strftime('%m/%d/%y %I:%M %p')} UTC"
            ),
        )
        await jail_logs_channel.send(embed=embed)
        await ctx.send("👍")

    @jail.command(name="setup")
    @has_permissions(administrator=True)
    async def jail_setup(self, ctx):
        """Sets up the jail system with required roles and channels."""
        guild = ctx.guild

        jail_category = discord.utils.get(guild.categories, name="Jail")
        if not jail_category:
            jail_category = await guild.create_category("Jail")

        jail_channel = discord.utils.get(guild.text_channels, name="jail")
        if not jail_channel:
            jail_channel = await jail_category.create_text_channel("jail")

        jail_logs_channel = discord.utils.get(guild.text_channels, name="jail-logs")
        if not jail_logs_channel:
            jail_logs_channel = await jail_category.create_text_channel("jail-logs")

        jailed_role = discord.utils.get(guild.roles, name="Jailed")
        if not jailed_role:
            jailed_role = await guild.create_role(name="Jailed")

        for channel in guild.channels:
            await channel.set_permissions(
                jailed_role, read_messages=False, send_messages=False
            )

        await jail_channel.set_permissions(
            jailed_role, read_messages=True, send_messages=True
        )

        await ctx.send("Jail setup completed successfully.")

    @jail.command(name="channel")
    async def manual_set_channel(self, ctx, channel: discord.TextChannel):
        """Sets the jail channel for the jail system."""
        self.jail_channel_id = channel.id
        await ctx.send(f"Jail channel set to {channel.mention}.")

    @jail.command(name="role")
    async def manual_set_role(self, ctx, role: discord.Role):
        """Sets the jailed role for the jail system."""
        guild = ctx.guild
        jail_channel = guild.get_channel(self.jail_channel_id)
        if not jail_channel:
            await ctx.send("Jail channel is not set. Run `,jail set-channel` first.")
            return

        if role.id in self.unmoderatable_user_ids:
            await ctx.send("no.")
            return

        await jail_channel.set_permissions(role, read_messages=True, send_messages=True)

        for channel in guild.channels:
            await channel.set_permissions(
                role, read_messages=False, send_messages=False
            )

        await ctx.send("Jail setup completed successfully.")

    @command(
        name="unjail",
        aliases=["unj"],
        description="Removes the jailed role from a user and logs the event.",
    )
    @has_permissions(moderate_members=True)
    async def unjail(self, ctx, member: discord.Member, *, reason="No reason provided"):
        """Removes the jailed role from a user and logs the event."""
        guild = ctx.guild
        jailed_role = discord.utils.get(guild.roles, name="Jailed")
        jail_logs_channel = discord.utils.get(guild.text_channels, name="jail-logs")

        if not jailed_role:
            await ctx.send("Jailed role does not exist.")
            return
        if not jail_logs_channel:
            await ctx.send("Jail logs channel does not exist.")
            return

        await member.remove_roles(jailed_role)

        self.case_count += 1

        embed = discord.Embed(title="Jail-Logs Entry", color=discord.Color.green())
        embed.add_field(
            name="Information",
            value=(
                f"**Case #{self.case_count} | Remove Jail**\n"
                f"**User:** {member.mention} (`{member.id}`)\n"
                f"**Moderator:** {ctx.author.mention} (`{ctx.author.id}`)\n"
                f"**Reason:** {reason}\n"
                f"{datetime.utcnow().strftime('%m/%d/%y %I:%M %p')} UTC"
            ),
        )
        await jail_logs_channel.send(embed=embed)
        await ctx.send("👍")

    # @group(
    #     name="snipe",
    #     aliases=["s"],
    #     help="Snipes recently deleted messages",
    #     invoke_without_command=True,
    # )
    # @has_permissions(send_messages=True)
    # async def snipe(self, ctx):
    #     """Snipes the specified deleted message number."""
    #     sniped_messages = await self.sniper.snipe(ctx)
    #     if not sniped_messages:
    #         return await ctx.send(
    #             embed=discord.Embed(
    #                 description="No deleted messages found in the past 2 hours!",
    #                 color=discord.Color.red(),
    #             )
    #         )
    #     message = sniped_messages[0]
    #     user = await self.bot.fetch_user(message["user_id"])
    #     attachments_raw = message.get("attachments")
    #     attachments = []
    #     if attachments_raw:
    #         try:
    #             attachments = ast.literal_eval(attachments_raw)
    #         except Exception:
    #             attachments = [attachments_raw]
    #     embed = discord.Embed(
    #         title=f"Message Deleted by @{user.name}",
    #         description=message["message"] or "No message content",
    #         color=0xFFFFFF,
    #     )
    #     if attachments:
    #         embed.add_field(name="Attachments", value="\n".join(attachments))
    #     avatar = await self.default_avatar_manager.get_user_avatar_or_default(user)
    #     embed.set_thumbnail(url=avatar)
    #     reply = None
    #     if message.get("reply"):
    #         try:
    #             reply = await ctx.fetch_message(message["reply"])
    #         except:
    #             reply = None
    #     view = SnipeView(sniped_messages, ctx, self.bot, 0)

    #     m = await ctx.send(
    #         content=f"Replying to {reply.jump_url}" if reply else "",
    #         embed=embed,
    #         view=view,
    #     )
    #     view.message = m

    # @snipe.command(name="reaction")
    # async def snipe_reaction(self, ctx):
    #     """Snipes recently removed reactions."""
    #     sniped_reactions = await self.sniper.reactsnipe(ctx)
    #     if not sniped_reactions:
    #         return await ctx.send(
    #             embed=discord.Embed(
    #                 description="No reactions found in the past 2 hours!",
    #                 color=discord.Color.red(),
    #             )
    #         )
    #     sniped_reaction = sniped_reactions[0]
    #     user = await self.bot.fetch_user(sniped_reaction["user_id"])
    #     embed = discord.Embed(
    #         description=f"**{user.name}** reacted with {sniped_reaction['reaction']}",
    #         color=0xFFFFFF,
    #     )
    #     r = None
    #     try:
    #         r = await ctx.fetch_message(sniped_reaction["message"])
    #     except:
    #         r = None
    #     view = SnipeView(sniped_reactions, ctx, self.bot, 2)
    #     m = await ctx.send(
    #         content=(
    #             "" if not sniped_reaction.get("reply") else f"Reacted to {r.jump_url}"
    #         ),
    #         embed=embed,
    #         view=view,
    #     )
    #     view.message = m

    # @snipe.command(name="edit", aliases=["es"])
    # async def _es(self, ctx):
    #     await ctx.invoke(self.edit_snipe)

    # @command(name="editsnipe", aliases=["es"])
    # @has_permissions(send_messages=True)
    # async def edit_snipe(self, ctx):
    #     """Snipe the last edited message."""
    #     sniped_messages = await self.sniper.editsnipe(ctx)
    #     if not sniped_messages:
    #         return await ctx.send(
    #             embed=discord.Embed(
    #                 description="No edited messages found in the past 2 hours!",
    #                 color=discord.Color.red(),
    #             )
    #         )
    #     sniped_edit = sniped_messages[0]
    #     member: discord.User = await self.bot.fetch_user(sniped_edit["user_id"])
    #     embed = discord.Embed(title=f"Message edited by {member.name}", color=0xFFFFFF)
    #     embed.add_field(
    #         name="Before", value=sniped_edit["before"] or "No message content"
    #     )
    #     embed.add_field(
    #         name="After", value=sniped_edit["after"] or "No message content"
    #     )
    #     avatar = await self.default_avatar_manager.get_user_avatar_or_default(member)
    #     embed.set_thumbnail(url=avatar)
    #     reply = None
    #     if sniped_edit.get("reply"):
    #         try:
    #             reply = await ctx.fetch_message(sniped_edit["reply"])
    #         except:
    #             reply = None
    #     view = SnipeView(sniped_messages, ctx, self.bot, 1)
    #     m = await ctx.send(
    #         content=(
    #             "" if not sniped_edit.get("reply") else f"Replying to {reply.jump_url}"
    #         ),
    #         embed=embed,
    #         view=view,
    #     )
    #     view.message = m

    # @command(
    #     name="reactionsnipe",
    #     aliases=["rs"],
    #     help="Snipes the last removed reaction in the channel.",
    # )
    # @has_permissions(send_messages=True)
    # async def reaction_snipe(self, ctx):
    #     """Snipes the last removed reaction and sends it in an embed."""
    #     await ctx.invoke(self.snipe_reaction)

    # @command(
    #     name="clearsnipe",
    #     aliases=[
    #         "cs",
    #         "cs:go",
    #         "csharp",
    #         "counterstrike",
    #         "csgo",
    #         "computerscience",
    #         "cs:go:go",
    #         "csharp:sharp",
    #         "counterstrike:strike",
    #         "csgo:go",
    #         "clearsnipe:snipe",
    #         "computerscience:science",
    #     ],
    # )
    # @cooldown(1, 3, BucketType.guild)
    # @has_permissions(manage_messages=True)
    # async def clear_snipe(self, ctx):
    #     """Clear the snipe history."""
    #     if await self.sniper.clearsnipe(ctx):
    #         await ctx.message.add_reaction(Emojis.check)
    #     else:
    #         await ctx.message.add_reaction("‼️")

    @hybrid_group(name="lockdown", description="Lockdown commands")
    @has_permissions(manage_channels=True)
    async def lockdown(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @lockdown.command(name="staticrole")
    @app_commands.describe(role="Sets the static member role if a member role exists.")
    @has_permissions(manage_guild=True)
    async def set_static_role(self, ctx, role: discord.Role):
        """Sets the static member role if a member role exists."""
        if not self.db:
            return await ctx.send("This command requires a database to be enabled.")
        result = await self.db.execute(
            """
            UPDATE lockdown_roles 
            SET role_id = $1 
            WHERE guild_id = $2
            """,
            role.id,
            ctx.guild.id,
        )

        if result == "UPDATE 0":
            await self.db.execute(
                """
                INSERT INTO lockdown_roles (guild_id, role_id)
                VALUES ($1, $2)
                """,
                ctx.guild.id,
                role.id,
            )
        embed = discord.Embed(
            description=f"{Emojis.check} Set the static role to {role.mention}",
            color=0xFFFFFF,
        )
        await ctx.send(embed=embed)

    @lockdown.command(
        name="channel",
        description="Locks down a specific channel, or the current channel if none is specified.",
    )
    @app_commands.describe(
        channel="Locks down a specific channel, or the current channel if none is specified.",
        action="The action to perform on the channel.",
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="Lock", value="lock"),
            app_commands.Choice(name="Unlock", value="unlock"),
            app_commands.Choice(name="Hide", value="hide"),
            app_commands.Choice(name="Unhide", value="unhide"),
            app_commands.Choice(name="Hide & Lock", value="hide_lock"),
            app_commands.Choice(name="Unhide & Unlock", value="unhide_unlock"),
        ]
    )
    @has_permissions(manage_channels=True)
    async def channel(
        self, ctx, channel: Optional[discord.TextChannel] = None, action: str = "lock"
    ):
        """Locks down a specific channel, or the current channel if none is specified."""
        channel = channel or ctx.channel
        static_role_id = await self.db.fetchval(
            "SELECT role_id FROM lockdown_roles WHERE guild_id = $1", ctx.guild.id
        )
        static_role = ctx.guild.get_role(static_role_id) if static_role_id else None
        roles = (
            [ctx.guild.default_role, static_role]
            if static_role
            else [ctx.guild.default_role]
        )

        for role in roles:
            if not role:
                continue

            if action == "lock":
                await channel.set_permissions(
                    role,
                    send_messages=False,
                    create_public_threads=False,
                    add_reactions=False,
                )
            elif action == "unlock":
                await channel.set_permissions(
                    role,
                    send_messages=None,
                    create_public_threads=None,
                    add_reactions=None,
                )
            elif action == "hide":
                await channel.set_permissions(role, view_channel=False)
            elif action == "unhide":
                await channel.set_permissions(role, view_channel=None)
            elif action == "hide_lock":
                await channel.set_permissions(
                    role,
                    view_channel=False,
                    send_messages=False,
                    create_public_threads=False,
                    add_reactions=False,
                )
            elif action == "unhide_unlock":
                await channel.set_permissions(
                    role,
                    view_channel=None,
                    send_messages=None,
                    create_public_threads=None,
                    add_reactions=None,
                )

        action_responses = {
            "lock": f"Locked down {channel.mention}",
            "unlock": f"Unlocked {channel.mention}",
            "hide": f"Hidden {channel.mention}",
            "unhide": f"Unhidden {channel.mention}",
            "hide_lock": f"Hidden & Locked {channel.mention}",
            "unhide_unlock": f"Unhidden & Unlocked {channel.mention}",
        }

        if action in action_responses:
            await ctx.send(action_responses[action])
        else:
            await ctx.send(f"Performed {action} on {channel.mention}")

    @command(name="lock")
    @has_permissions(manage_channels=True)
    async def lock(self, ctx, channel: Optional[discord.TextChannel] = None):
        """
        Locks down the specified channel or the current channel if none is specified.

        This prevents @everyone from sending messages in the channel.
        """
        channel = channel or ctx.channel

        static_role_id = await self.db.fetchval(
            "SELECT role_id FROM lockdown_roles WHERE guild_id = $1", ctx.guild.id
        )
        static_role = ctx.guild.get_role(static_role_id) if static_role_id else None
        roles = (
            [ctx.guild.default_role, static_role]
            if static_role
            else [ctx.guild.default_role]
        )

        for role in roles:
            if role:
                await channel.set_permissions(
                    role,
                    send_messages=False,
                    create_public_threads=False,
                    add_reactions=False,
                )

        await ctx.send(f"👍")

    @command(name="unlock")
    @has_permissions(manage_channels=True)
    async def unlock(self, ctx, channel: Optional[discord.TextChannel] = None):
        """
        Unlocks the specified channel or the current channel if none is specified.

        This allows @everyone to send messages in the channel.
        """
        channel = channel or ctx.channel

        static_role_id = await self.db.fetchval(
            "SELECT role_id FROM lockdown_roles WHERE guild_id = $1", ctx.guild.id
        )
        static_role = ctx.guild.get_role(static_role_id) if static_role_id else None
        roles = (
            [ctx.guild.default_role, static_role]
            if static_role
            else [ctx.guild.default_role]
        )

        for role in roles:
            if role:
                await channel.set_permissions(
                    role,
                    send_messages=None,
                    create_public_threads=None,
                    add_reactions=None,
                )

        await ctx.send(f"👍")

    @command(name="hide")
    @has_permissions(manage_channels=True)
    async def hide(self, ctx, channel: Optional[discord.TextChannel] = None):
        """
        Hides the specified channel or the current channel if none is specified.

        This prevents @everyone from viewing the channel.
        """
        channel = channel or ctx.channel

        static_role_id = await self.db.fetchval(
            "SELECT role_id FROM lockdown_roles WHERE guild_id = $1", ctx.guild.id
        )
        static_role = ctx.guild.get_role(static_role_id) if static_role_id else None
        roles = (
            [ctx.guild.default_role, static_role]
            if static_role
            else [ctx.guild.default_role]
        )

        for role in roles:
            if role:
                await channel.set_permissions(role, view_channel=False)

        await ctx.send(f"👍")

    @command(name="unhide")
    @has_permissions(manage_channels=True)
    async def unhide(self, ctx, channel: Optional[discord.TextChannel] = None):
        """
        Unhides the specified channel or the current channel if none is specified.

        This allows @everyone to view the channel.
        """
        channel = channel or ctx.channel

        static_role_id = await self.db.fetchval(
            "SELECT role_id FROM lockdown_roles WHERE guild_id = $1", ctx.guild.id
        )
        static_role = ctx.guild.get_role(static_role_id) if static_role_id else None
        roles = (
            [ctx.guild.default_role, static_role]
            if static_role
            else [ctx.guild.default_role]
        )

        for role in roles:
            if role:
                await channel.set_permissions(role, view_channel=None)

        await ctx.send(f"👍")

    @hybrid_group(
        name="slowmode",
        description="Restricts members to sending one message per interval",
        invoke_without_command=True,
    )
    @has_permissions(manage_channels=True)
    async def slowmode(self, ctx: Context, time: Optional[str] = None):
        """
        Enable slowmode in the current channel.
        """
        pass

    @slowmode.command(
        name="on",
        aliases=["enable"],
        description="Enable slowmode in a channel",
    )
    @has_permissions(manage_channels=True)
    async def slowmode_on(
        self,
        ctx: Context,
        channel: Optional[TextChannel] = None,
        *,
        time: Optional[str] = None,
    ):
        """
        Enable slowmode in a channel.
        """
        if channel is None:
            channel = ctx.channel
        if not time:
            time_seconds = 5
        else:
            try:
                time_seconds = await self.parse_time_string(time)
                if time_seconds > 21600:
                    raise CommandError("Slowmode interval cannot be more than 6 hours")
            except (ValueError, TypeError):
                raise CommandError(
                    "Invalid time format. Use format like '5s', '1m', '30s', etc."
                )

        await channel.edit(
            slowmode_delay=time_seconds, reason=f"Slowmode enabled by {ctx.author}"
        )
        return await ctx.send(
            f"Set slowmode to {time_seconds} seconds in {channel.mention}"
        )

    @slowmode.command(
        name="off",
        aliases=["disable"],
        description="Disables slowmode in a channel",
    )
    @has_permissions(manage_channels=True)
    async def slowmode_off(self, ctx: Context, channel: Optional[TextChannel] = None):
        channel = channel or ctx.channel
        await channel.edit(
            slowmode_delay=0, reason=f"Slowmode disabled by {ctx.author}"
        )
        return await ctx.send(f"Disabled slowmode in {channel.mention}")

    @command(name="sdeafen", aliases=["sd", "deafen"])
    @has_permissions(moderate_members=True)
    async def voice_deafen(self, ctx, member: discord.Member = None):
        """Server deafens the mentioned member, or self if none mentioned."""
        target = member or ctx.author
        try:
            await target.edit(deafen=True)
            await ctx.send(f"👍")
        except discord.Forbidden:
            await ctx.send("I do not have permission to deafen members.")
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

    @command(name="smute", aliases=["sm", "mute"])
    @has_permissions(moderate_members=True)
    async def voice_mute(self, ctx, member: discord.Member = None):
        """Server mutes the mentioned member, or self if none mentioned."""
        target = member or ctx.author
        try:
            await target.edit(mute=True)
            await ctx.send(f"👍")
        except discord.Forbidden:
            await ctx.send("I do not have permission to mute members.")
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

    @command(name="sundeafen", aliases=["sund", "sunday", "undeafen"])
    @has_permissions(moderate_members=True)
    async def voice_undeafen(self, ctx, member: discord.Member = None):
        """Server undeafens the mentioned member, or self if none mentioned."""
        target = member or ctx.author
        try:
            await target.edit(deafen=False)
            await ctx.send(f"👍")
        except discord.Forbidden:
            await ctx.send("I do not have permission to undeafen members.")
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

    @command(name="sunmute", aliases=["sum", "unmute"])
    @has_permissions(moderate_members=True)
    async def voice_unmute(self, ctx, member: discord.Member = None):
        """Server unmutes the mentioned member, or self if none mentioned."""
        target = member or ctx.author
        try:
            await target.edit(mute=False)
            await ctx.send(f"👍")
        except discord.Forbidden:
            await ctx.send("I do not have permission to unmute members.")
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

    @command(name="disconnect", aliases=["dc"])
    @has_permissions(moderate_members=True)
    async def voice_disconnect(self, ctx, member: discord.Member = None):
        """Server disconnects the mentioned member, or self if none mentioned."""
        target = member or ctx.author
        try:
            await target.move_to(None)
            await ctx.send(f"👍")
        except discord.Forbidden:
            await ctx.send("I do not have permission to disconnect members.")
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

    @hybrid(
        name="createinvite",
        aliases=["createinv", "instantinvite"],
        description="Creates a unique invite for the server. (non-vanity).",
    )
    @app_commands.describe(
        channel="The channel to create an invite for.",
        age="The max age of the invite in seconds.",
        uses="The max uses of the invite.",
    )
    @app_commands.choices(
        age=[
            app_commands.Choice(name="30 minutes", value=1800),
            app_commands.Choice(name="1 hour", value=3600),
            app_commands.Choice(name="6 hours", value=21600),
            app_commands.Choice(name="12 hours", value=43200),
            app_commands.Choice(name="1 day", value=86400),
            app_commands.Choice(name="7 days", value=604800),
            app_commands.Choice(name="Never", value=0),
        ],
        uses=[
            app_commands.Choice(name="1 use", value=1),
            app_commands.Choice(name="5 uses", value=5),
            app_commands.Choice(name="10 uses", value=10),
            app_commands.Choice(name="25 uses", value=25),
            app_commands.Choice(name="50 uses", value=50),
            app_commands.Choice(name="100 uses", value=100),
            app_commands.Choice(name="No limit", value=0),
        ],
    )
    @has_permissions(create_instant_invite=True)
    async def create_invite(
        self,
        ctx,
        channel: discord.TextChannel = None,
        age: app_commands.Choice[int] = None,
        uses: app_commands.Choice[int] = None,
    ):
        """Creates a unique invite for the server. (non-vanity)."""
        channel = channel or ctx.channel
        try:
            invite = await channel.create_invite(
                max_age=age.value, max_uses=uses.value, unique=True
            )
            await ctx.send(invite.url, ephemeral=True)
        except discord.Forbidden:
            await ctx.send(
                "I do not have permission to create invites.", ephemeral=True
            )
        except Exception as e:
            await ctx.send(f"An error occurred: {e}", ephemeral=True)

    @command(name="sname", aliases=["servername"])
    @has_permissions(manage_guild=True)
    async def change_server_name(self, ctx, *, new_name: str = None):
        """Change the name of a server."""
        if not new_name:
            return await ctx.send("Please provide a new server name.")

        if not ctx.author.guild_permissions.manage_guild:
            return await ctx.send(
                "You don't have permission to change the server name."
            )

        try:
            await ctx.guild.edit(name=new_name)

            embed = discord.Embed(
                description=f"Server name has been changed to **{ctx.guild.name}**",
                color=discord.Color(0xFFFFFF),
            )
            await ctx.send(embed=embed)

        except discord.Forbidden:
            await ctx.send("I do not have permission to change the server name.")
        except discord.HTTPException as e:
            await ctx.send(f"Failed to change server name. Error: {e}")

    @Cog.listener()
    async def on_member_update(self, before, after):
        if before.nick != after.nick and after.nick is None:
            async with self.bot.db.acquire() as conn:
                forced_nick = await conn.fetchval(
                    """
                    SELECT nick FROM forced_nicks
                    WHERE guild_id = $1 AND user_id = $2
                    """,
                    after.guild.id,
                    after.id,
                )
                if forced_nick:
                    try:
                        await after.edit(nick=forced_nick)
                    except discord.HTTPException:
                        pass

    @hybrid_group(name="reaction", description="Base command for reaction management.")
    @guild_only()
    @has_permissions(moderate_members=True)
    async def reaction(self, ctx: Context):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @reaction.command(name="mute", description="Mute a user from reacting to messages.")
    @app_commands.describe(
        member="The member to mute from reacting to messages.",
        channel="The channel to mute the user from reacting in. Defaults to the current channel.",
    )
    @has_permissions(moderate_members=True)
    async def reactionmute(
        self,
        ctx: Context,
        member: discord.Member,
        channel: Optional[discord.TextChannel] = None,
    ):
        """Revokes a users permissions to react in a channel."""
        channel = channel or ctx.channel
        overwrite = channel.overwrites_for(member)
        overwrite.update(add_reactions=False)
        await channel.set_permissions(member, overwrite=overwrite)
        await ctx.send("👍")

    @reaction.command(
        name="unmute", description="Unmute a user from reacting to messages."
    )
    @app_commands.describe(
        member="The member to unmute from reacting to messages.",
    )
    @has_permissions(moderate_members=True)
    async def reactionunmute(
        self,
        ctx: Context,
        member: discord.Member,
    ):
        """Grants a users permissions to react in a channel."""
        for channel in ctx.guild.text_channels:
            overwrite = channel.overwrites_for(member)
            if overwrite.add_reactions is False:
                overwrite.add_reactions = None
                await channel.set_permissions(member, overwrite=overwrite)
        await ctx.send("👍")

    @hybrid_group(name="lockdown", description="Lockdown commands")
    @has_permissions(manage_channels=True)
    async def lockdown(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @lockdown.command(name="staticrole")
    @app_commands.describe(role="Sets the static member role if a member role exists.")
    @has_permissions(manage_guild=True)
    async def set_static_role(self, ctx, role: discord.Role):
        """Sets the static member role if a member role exists."""
        if not self.db:
            return await ctx.send("This command requires a database to be enabled.")
        result = await self.db.execute(
            """
            UPDATE lockdown_roles 
            SET role_id = $1 
            WHERE guild_id = $2
            """,
            role.id,
            ctx.guild.id,
        )

        if result == "UPDATE 0":
            await self.db.execute(
                """
                INSERT INTO lockdown_roles (guild_id, role_id)
                VALUES ($1, $2)
                """,
                ctx.guild.id,
                role.id,
            )
        embed = discord.Embed(
            description=f"{Emojis.check} Set the static role to {role.mention}",
            color=0xFFFFFF,
        )
        await ctx.send(embed=embed)

    @lockdown.command(
        name="channel",
        description="Locks down a specific channel, or the current channel if none is specified.",
    )
    @app_commands.describe(
        channel="Locks down a specific channel, or the current channel if none is specified.",
        action="The action to perform on the channel.",
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="Lock", value="lock"),
            app_commands.Choice(name="Unlock", value="unlock"),
            app_commands.Choice(name="Hide", value="hide"),
            app_commands.Choice(name="Unhide", value="unhide"),
            app_commands.Choice(name="Hide & Lock", value="hide_lock"),
            app_commands.Choice(name="Unhide & Unlock", value="unhide_unlock"),
        ]
    )
    @has_permissions(manage_channels=True)
    async def channel(
        self, ctx, channel: Optional[discord.TextChannel] = None, action: str = "lock"
    ):
        """Locks down a specific channel, or the current channel if none is specified."""
        channel = channel or ctx.channel
        static_role_id = await self.db.fetchval(
            "SELECT role_id FROM lockdown_roles WHERE guild_id = $1", ctx.guild.id
        )
        static_role = ctx.guild.get_role(static_role_id) if static_role_id else None
        roles = (
            [ctx.guild.default_role, static_role]
            if static_role
            else [ctx.guild.default_role]
        )

        for role in roles:
            if not role:
                continue

            if action == "lock":
                await channel.set_permissions(
                    role,
                    send_messages=False,
                    create_public_threads=False,
                    add_reactions=False,
                )
            elif action == "unlock":
                await channel.set_permissions(
                    role,
                    send_messages=None,
                    create_public_threads=None,
                    add_reactions=None,
                )
            elif action == "hide":
                await channel.set_permissions(role, view_channel=False)
            elif action == "unhide":
                await channel.set_permissions(role, view_channel=None)
            elif action == "hide_lock":
                await channel.set_permissions(
                    role,
                    view_channel=False,
                    send_messages=False,
                    create_public_threads=False,
                    add_reactions=False,
                )
            elif action == "unhide_unlock":
                await channel.set_permissions(
                    role,
                    view_channel=None,
                    send_messages=None,
                    create_public_threads=None,
                    add_reactions=None,
                )

        action_responses = {
            "lock": f"Locked down {channel.mention}",
            "unlock": f"Unlocked {channel.mention}",
            "hide": f"Hidden {channel.mention}",
            "unhide": f"Unhidden {channel.mention}",
            "hide_lock": f"Hidden & Locked {channel.mention}",
            "unhide_unlock": f"Unhidden & Unlocked {channel.mention}",
        }

        if action in action_responses:
            await ctx.send(action_responses[action])
        else:
            await ctx.send(f"Performed {action} on {channel.mention}")

    @command(name="sdeafen", aliases=["sd", "deafen"])
    @has_permissions(moderate_members=True)
    async def voice_deafen(self, ctx, member: discord.Member = None):
        """Server deafens the mentioned member, or self if none mentioned."""
        target = member or ctx.author
        try:
            await target.edit(deafen=True)
            await ctx.send(f"👍")
        except discord.Forbidden:
            await ctx.send("I do not have permission to deafen members.")
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

    @command(name="smute", aliases=["sm", "mute"])
    @has_permissions(moderate_members=True)
    async def voice_mute(self, ctx, member: discord.Member = None):
        """Server mutes the mentioned member, or self if none mentioned."""
        target = member or ctx.author
        try:
            await target.edit(mute=True)
            await ctx.send(f"👍")
        except discord.Forbidden:
            await ctx.send("I do not have permission to mute members.")
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

    @command(name="sundeafen", aliases=["sund", "sunday", "undeafen"])
    @has_permissions(moderate_members=True)
    async def voice_undeafen(self, ctx, member: discord.Member = None):
        """Server undeafens the mentioned member, or self if none mentioned."""
        target = member or ctx.author
        try:
            await target.edit(deafen=False)
            await ctx.send(f"👍")
        except discord.Forbidden:
            await ctx.send("I do not have permission to undeafen members.")
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

    @command(name="sunmute", aliases=["sum", "unmute"])
    @has_permissions(moderate_members=True)
    async def voice_unmute(self, ctx, member: discord.Member = None):
        """Server unmutes the mentioned member, or self if none mentioned."""
        target = member or ctx.author
        try:
            await target.edit(mute=False)
            await ctx.send(f"👍")
        except discord.Forbidden:
            await ctx.send("I do not have permission to unmute members.")
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

    @command(name="disconnect", aliases=["dc"])
    @has_permissions(moderate_members=True)
    async def voice_disconnect(self, ctx, member: discord.Member = None):
        """Server disconnects the mentioned member, or self if none mentioned."""
        target = member or ctx.author
        try:
            await target.move_to(None)
            await ctx.send(f"👍")
        except discord.Forbidden:
            await ctx.send("I do not have permission to disconnect members.")
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

    @hybrid(
        name="createinvite",
        aliases=["createinv", "instantinvite"],
        description="Creates a unique invite for the server. (non-vanity).",
    )
    @app_commands.describe(
        channel="The channel to create an invite for.",
        age="The max age of the invite in seconds.",
        uses="The max uses of the invite.",
    )
    @app_commands.choices(
        age=[
            app_commands.Choice(name="30 minutes", value=1800),
            app_commands.Choice(name="1 hour", value=3600),
            app_commands.Choice(name="6 hours", value=21600),
            app_commands.Choice(name="12 hours", value=43200),
            app_commands.Choice(name="1 day", value=86400),
            app_commands.Choice(name="7 days", value=604800),
            app_commands.Choice(name="Never", value=0),
        ],
        uses=[
            app_commands.Choice(name="1 use", value=1),
            app_commands.Choice(name="5 uses", value=5),
            app_commands.Choice(name="10 uses", value=10),
            app_commands.Choice(name="25 uses", value=25),
            app_commands.Choice(name="50 uses", value=50),
            app_commands.Choice(name="100 uses", value=100),
            app_commands.Choice(name="No limit", value=0),
        ],
    )
    @has_permissions(create_instant_invite=True)
    async def create_invite(
        self,
        ctx,
        channel: discord.TextChannel = None,
        age: app_commands.Choice[int] = None,
        uses: app_commands.Choice[int] = None,
    ):
        """Creates a unique invite for the server. (non-vanity)."""
        channel = channel or ctx.channel
        try:
            invite = await channel.create_invite(
                max_age=age.value, max_uses=uses.value, unique=True
            )
            await ctx.send(invite.url, ephemeral=True)
        except discord.Forbidden:
            await ctx.send(
                "I do not have permission to create invites.", ephemeral=True
            )
        except Exception as e:
            await ctx.send(f"An error occurred: {e}", ephemeral=True)

    @command(name="sname", aliases=["servername"])
    @has_permissions(manage_guild=True)
    async def change_server_name(self, ctx, *, new_name: str = None):
        """Change the name of a server."""
        if not new_name:
            return await ctx.send("Please provide a new server name.")

        if not ctx.author.guild_permissions.manage_guild:
            return await ctx.send(
                "You don't have permission to change the server name."
            )

        try:
            await ctx.guild.edit(name=new_name)

            embed = discord.Embed(
                description=f"Server name has been changed to **{ctx.guild.name}**",
                color=discord.Color(0xFFFFFF),
            )
            await ctx.send(embed=embed)

        except discord.Forbidden:
            await ctx.send("I do not have permission to change the server name.")
        except discord.HTTPException as e:
            await ctx.send(f"Failed to change server name. Error: {e}")

    @Cog.listener()
    async def on_member_update(self, before, after):
        if before.nick != after.nick and after.nick is None:
            async with self.bot.db.acquire() as conn:
                forced_nick = await conn.fetchval(
                    """
                    SELECT nick FROM forced_nicks
                    WHERE guild_id = $1 AND user_id = $2
                    """,
                    after.guild.id,
                    after.id,
                )
                if forced_nick:
                    try:
                        await after.edit(nick=forced_nick)
                    except discord.HTTPException:
                        pass

    @hybrid_group(
        name="staffstrip",
        aliases=["strip", "stripstaff"],
        description="Strips a user of all their moderation-related roles",
    )
    @has_permissions(administrator=True)
    async def staff_strip(self, ctx, member: discord.Member):
        if (
            member.top_role >= ctx.author.top_role
            and ctx.author.id != ctx.guild.owner_id
        ):
            return await ctx.message.add_reaction("‼️")

        mod_permissions = [
            "kick_members",
            "ban_members",
            "manage_channels",
            "manage_guild",
            "manage_messages",
            "manage_roles",
            "manage_webhooks",
            "moderate_members",
            "view_audit_log",
            "administrator",
        ]

        mod_roles = []
        removed_roles = []
        modified_roles = []

        for role in member.roles:
            if role == ctx.guild.default_role:
                continue

            role_perms = role.permissions
            for perm in mod_permissions:
                if getattr(role_perms, perm):
                    mod_roles.append(role)
                    break

        if not mod_roles:
            return await ctx.message.add_reaction("‼️")

        for role in mod_roles:
            try:
                if role.is_bot_managed():
                    perms = discord.Permissions()
                    await role.edit(
                        permissions=perms, reason=f"Staff strip by {ctx.author}"
                    )
                    modified_roles.append(role)
                else:
                    await member.remove_roles(
                        role, reason=f"Staff strip by {ctx.author}"
                    )
                    removed_roles.append(role)
            except (discord.Forbidden, discord.HTTPException):
                continue

        if not (removed_roles or modified_roles):
            return await ctx.message.add_reaction("‼️")

        await ctx.send("👍")

    @group(
        name="channel",
        description="Base command for channel management.",
        invoke_without_command=True,
    )
    @cooldown(3, 5, BucketType.guild)
    @has_permissions(manage_channels=True)
    async def channel(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @channel.command(name="create", description="Creates a new text channel.")
    @cooldown(3, 5, BucketType.guild)
    @has_permissions(manage_channels=True)
    async def channel_create(
        self, ctx, name: str, category: discord.CategoryChannel = None
    ):
        try:
            name = name.lower().replace(" ", "-")

            new_channel = await ctx.guild.create_text_channel(
                name=name, category=category
            )

            await ctx.send(f"Created text channel {new_channel.mention}")
        except discord.Forbidden:
            await ctx.send("I don't have permission to create channels.")
        except discord.HTTPException as e:
            await ctx.send(f"Failed to create channel: {str(e)}")

    @channel.command(name="delete", description="Deletes a channel.")
    @cooldown(3, 5, BucketType.guild)
    @has_permissions(manage_channels=True)
    async def channel_delete(self, ctx, channel: discord.TextChannel = None):
        channel = channel or ctx.channel

        try:
            await channel.delete()
            if channel != ctx.channel:
                await ctx.send(f"Deleted channel #{channel.name}")
        except discord.Forbidden:
            await ctx.send("I don't have permission to delete this channel.")
        except discord.HTTPException as e:
            await ctx.send(f"Failed to delete channel: {str(e)}")

    @channel.command(name="rename", description="Renames a channel.")
    @cooldown(1, 60, BucketType.guild)
    @has_permissions(manage_channels=True)
    async def channel_rename(self, ctx, *, new_name: str):
        try:
            new_name = new_name.lower().replace(" ", "-")

            await ctx.channel.edit(name=new_name)
            await ctx.send(f"Channel renamed to #{new_name}")
        except discord.Forbidden:
            await ctx.send("I don't have permission to rename this channel.")
        except discord.HTTPException as e:
            await ctx.send(f"Failed to rename channel: {str(e)}")

    @channel.command(name="private", description="Creates a private channel??")
    @cooldown(1, 5, BucketType.guild)
    @has_permissions(manage_channels=True)
    async def channel_private(self, ctx, name: str = None):
        try:
            name = name or f"{ctx.author.name}-private"

            name = name.lower().replace(" ", "-")

            new_channel = await ctx.guild.create_text_channel(
                name=name,
                overwrites={
                    ctx.guild.default_role: discord.PermissionOverwrite(
                        read_messages=False
                    ),
                    ctx.author: discord.PermissionOverwrite(
                        read_messages=True, manage_channels=True
                    ),
                },
            )

            await ctx.send(f"Created private channel {new_channel.mention}")
        except discord.Forbidden:
            await ctx.send("I don't have permission to create private channels.")
        except discord.HTTPException as e:
            await ctx.send(f"Failed to create private channel: {str(e)}")

    @channel.command(name="topic", description="Sets the topic for a channel.")
    @cooldown(3, 5, BucketType.guild)
    @has_permissions(manage_channels=True)
    async def channel_topic(self, ctx, *, new_topic: str):
        try:
            await ctx.channel.edit(topic=new_topic)
            embed = discord.Embed(
                description=f"Channel topic set to: {new_topic}",
                color=Color(0xFFFFFF),
            )
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send("I don't have permission to set the channel topic.")
        except discord.HTTPException as e:
            await ctx.send(f"Failed to set channel topic: {str(e)}")

    @channel.command(
        name="sync",
        description="Syncs channel permissions for a specific category, or all if specified as all.",
    )
    @cooldown(3, 5, BucketType.guild)
    @has_permissions(manage_channels=True)
    async def channel_sync(self, ctx, category: str = None):
        if category is None:
            await ctx.send("Please provide a category or 'all'.")
            return

        if category.lower() == "all":
            for channel in ctx.guild.channels:
                if isinstance(channel, discord.TextChannel) and channel.category:
                    await channel.edit(sync_permissions=True)
            await ctx.send("👍")
        else:
            category = discord.utils.get(ctx.guild.categories, name=category)
            if category:
                for channel in ctx.guild.channels:
                    if (
                        isinstance(channel, discord.TextChannel)
                        and channel.category == category
                    ):
                        await channel.edit(sync_permissions=True)
                await ctx.send("👍")
            else:
                await ctx.send("Category not found.")

    @hybrid_group(
        name="newusers",
        description="View list of all members that joined today",
        invoke_without_command=True,
    )
    @has_permissions(manage_guild=True)
    async def newusers(self, ctx: Context):
        def check(member: Member):
            return (
                True
                if member.joined_at > ctx.message.created_at - timedelta(days=1)
                else False
            )

        members = sorted(
            [m for m in ctx.guild.members if check(m)],
            key=lambda x: x.joined_at,
            reverse=True,
        )

        if not members:
            raise CommandError("No **members** joined today")  # type: ignore

        view = NewUsersView(ctx)
        view.set_data(members)
        view.current_page = 0
        view.total = len(members)
        embed = Embed(title="New users today").set_author(
            name=str(ctx.author), icon_url=ctx.author.display_avatar.url
        )
        return await ctx.send(embed=embed, view=view)

    _registart_runs = 0

    @command(
        name="registart",
        aliases=[
            "random-ass-command-that-does-nothing-useful-and-is-only-here-because-i-got-horribly-bored-and-decided-to-do-something-about-my-insufferable-boredom,why-are-you-even-reading-this"
        ],
        description="the fuck does this even do?",
    )
    async def registart(self, ctx: Context):
        self._registart_runs += 1
        await self.bot.db.execute(
            """
            INSERT INTO random_command_usage (user_id, command)
            VALUES ($1, $2)
            ON CONFLICT (user_id, command) 
            DO UPDATE SET timestamp = NOW()
            """,
            ctx.author.id,
            "registart",
        )
        await ctx.send("👍")

    @is_owner()
    @command(name="registarts", hidden=True)
    async def registarts(self, ctx: Context):
        result = await self.bot.db.fetchval(
            """
            SELECT COUNT(*) FROM random_command_usage
            WHERE command = 'registart'
            """,
        )
        await ctx.send(f"`registart` has been run a total of {result} times")

    @hybrid_group(name="noselfreact", aliases=["nsr"], invoke_without_command=True)
    @guild_only()
    @has_permissions(manage_guild=True)
    async def noselfreact(self, ctx: Context):
        """Prevents users from reacting to their own messages"""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @noselfreact.command(name="enable")
    @guild_only()
    @has_permissions(manage_guild=True)
    async def nsr_enable(self, ctx: Context):
        """Enable NoSelfReact for this server"""
        async with self.bot.db.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO nsr (server_id, enabled)
                VALUES ($1, true)
                ON CONFLICT (server_id) DO UPDATE
                SET enabled = true
                """,
                ctx.guild.id,
            )

        self.enabled_servers.add(ctx.guild.id)
        embed = discord.Embed(
            description="NoSelfReact has been enabled for this server.", color=0xFFFFFF
        )
        await ctx.send(embed=embed)

    @noselfreact.command(name="disable")
    @guild_only()
    @has_permissions(manage_guild=True)
    async def nsr_disable(self, ctx: Context):
        """Disable NoSelfReact for this server"""
        async with self.bot.db.acquire() as conn:
            await conn.execute(
                """
                UPDATE nsr
                SET enabled = false
                WHERE server_id = $1
                """,
                ctx.guild.id,
            )

        self.enabled_servers.discard(ctx.guild.id)
        embed = discord.Embed(
            description="NoSelfReact has been disabled for this server.", color=0xFFFFFF
        )
        await ctx.send(embed=embed)

    @noselfreact.group(name="message", invoke_without_command=True)
    @guild_only()
    @has_permissions(manage_guild=True)
    async def nsr_message(self, ctx: Context):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @nsr_message.command(name="set")
    @guild_only()
    @has_permissions(manage_guild=True)
    @app_commands.describe(message="The message the bot sends if nsr is enabled")
    async def nsr_message_set(self, ctx: Context, message: str):
        """Set NoSelfReact message for this server."""
        await self.bot.db.execute(
            """
            INSERT INTO nsr (server_id, message, enabled)
            VALUES ($1, $2, true)
            ON CONFLICT (server_id) 
            DO UPDATE SET message = $2
            """,
            ctx.guild.id,
            message,
        )

        preview = Builder.embed_replacement(ctx.author, message)
        embed = discord.Embed(
            description=f"NoSelfReact message has been updated.\n\n**Preview:**\n{preview}",
            color=0xFFFFFF,
        )
        await ctx.send(embed=embed)

    @nsr_message.command(name="reset")
    @guild_only()
    @has_permissions(manage_guild=True)
    async def nsr_message_reset(self, ctx: Context):
        """Reset NoSelfReact message for this server"""
        await self.bot.db.execute(
            """
            DELETE FROM nsr
            WHERE server_id = $1
            """,
            ctx.guild.id,
        )

        embed = discord.Embed(
            description="NoSelfReact message has been reset for this server.",
            color=0xFFFFFF,
        )
        await ctx.send(embed=embed)

    @Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        if user.bot or not reaction.message.guild:
            return

        if reaction.message.guild.id not in self.enabled_servers:
            return

        if reaction.message.author.id == user.id:
            now = time.time()
            message_id = reaction.message.id

            if message_id in CACHE and (now - CACHE[message_id]) < COOLDOWN:
                return

            try:
                await reaction.remove(user)

                message = await self.bot.db.fetchval(
                    """
                    SELECT message
                    FROM nsr
                    WHERE server_id = $1
                    """,
                    reaction.message.guild.id,
                )

                if message:
                    formatted_message = Builder.embed_replacement(user, message)
                    await reaction.message.channel.send(formatted_message)

            except discord.Forbidden:
                pass
            except Exception as e:
                print(f"Error in on_reaction_add: {e}")
                pass
            finally:
                CACHE[message_id] = now

    def _clean_cache(self):
        now = time.time()
        to_remove = [
            msg_id for msg_id, timestamp in CACHE.items() if (now - timestamp) > 300
        ]
        for msg_id in to_remove:
            CACHE.pop(msg_id, None)

    @hybrid_group(name="reaction", description="Base command for reaction management.")
    @guild_only()
    @has_permissions(manage_guild=True)
    async def reaction(self, ctx: Context):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @reaction.command(name="mute", description="Mute a user from reacting to messages.")
    @app_commands.describe(
        member="The member to mute from reacting to messages.",
        channel="The channel to mute the user from reacting in. Defaults to the current channel.",
    )
    @has_permissions(moderate_members=True)
    async def reactionmute(
        self,
        ctx: Context,
        member: discord.Member,
        channel: Optional[discord.TextChannel] = None,
    ):
        """Revokes a users permissions to react in a channel."""
        channel = channel or ctx.channel
        overwrite = channel.overwrites_for(member)
        overwrite.update(add_reactions=False)
        await channel.set_permissions(member, overwrite=overwrite)
        await ctx.send("👍")

    @reaction.command(
        name="unmute", description="Unmute a user from reacting to messages."
    )
    @app_commands.describe(
        member="The member to unmute from reacting to messages.",
    )
    @has_permissions(moderate_members=True)
    async def reactionunmute(
        self,
        ctx: Context,
        member: discord.Member,
    ):
        """Grants a users permissions to react in a channel."""
        for channel in ctx.guild.text_channels:
            overwrite = channel.overwrites_for(member)
            if overwrite.add_reactions is False:
                overwrite.add_reactions = None
                await channel.set_permissions(member, overwrite=overwrite)
        await ctx.send("👍")
