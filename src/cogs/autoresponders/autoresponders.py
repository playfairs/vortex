import discord
from discord.ext import commands
from discord.ext.commands import (
    Cog,
    Context,
    command,
    BucketType,
    cooldown,
    has_permissions,
    hybrid_command as hybrid,
    hybrid_group,
)
from discord import app_commands, Guild, User
from typing import (
    Optional,
)
from vortex import vortex
import re
import time


class AutoResponders(Cog, description="View commands in AutoResponders."):
    def __init__(self, bot: vortex):
        self.bot = bot
        self.db = self.bot.db
        self.autoresponder_cooldowns = {}

    async def cog_load(self):
        await self.create_tables()

    async def create_tables(self):
        await self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS autoresponders (
                guild_id BIGINT,
                trigger TEXT,
                response TEXT,
                string BOOLEAN,
                enabled BOOLEAN,
                PRIMARY KEY (guild_id, trigger)
            );
            
            CREATE TABLE IF NOT EXISTS autoreactions (
                guild_id BIGINT,
                trigger TEXT,
                emoji TEXT,
                enabled BOOLEAN DEFAULT true,
                PRIMARY KEY (guild_id, trigger)
            );

            CREATE TABLE IF NOT EXISTS userreactions (
                guild_id BIGINT,
                user_id BIGINT,
                emoji TEXT,
                PRIMARY KEY (guild_id, user_id, emoji)
            );
        """
        )

    async def process_autoresponders(self, message: discord.Message) -> bool:
        """Process autoresponders for a message. Returns True if a response was sent."""
        try:
            # Check cooldown (3 seconds per guild)
            current_time = time.time()
            last_trigger = self.autoresponder_cooldowns.get(message.guild.id, 0)
            
            if current_time - last_trigger < 3:
                return False
            
            autoresponders = await self.db.fetch(
                """
                SELECT * FROM autoresponders
                WHERE guild_id = $1 AND enabled = $2
                """,
                message.guild.id,
                True,
            )

            for ar in autoresponders:
                try:
                    if ar["string"]:
                        try:
                            if re.search(ar["trigger"], message.content, re.IGNORECASE):
                                response = ar["response"].replace("{user.mention}", message.author.mention)
                                await message.channel.send(response)
                                self.autoresponder_cooldowns[message.guild.id] = current_time
                                return True
                        except re.error:
                            import traceback

                            traceback.print_exc()

                    elif ar["string"] is False:
                        if ar["trigger"].lower() in message.content.lower():
                            response = ar["response"].replace("{user.mention}", message.author.mention)
                            await message.channel.send(response)
                            self.autoresponder_cooldowns[message.guild.id] = current_time
                            return True

                    else:
                        if ar["trigger"].lower() == message.content.lower():
                            response = ar["response"].replace("{user.mention}", message.author.mention)
                            await message.channel.send(response)
                            self.autoresponder_cooldowns[message.guild.id] = current_time
                            return True

                except discord.HTTPException:
                    import traceback

                    traceback.print_exc()
                    continue

        except Exception:
            import traceback

            traceback.print_exc()

        return False

    async def process_autoreactions(self, message: discord.Message) -> bool:
        """Process autoreactions for a message. Returns True if a reaction was added."""
        try:
            enabled = await self.db.fetchval(
                "SELECT enabled FROM autoreactions WHERE guild_id = $1 LIMIT 1",
                message.guild.id,
            )

            if enabled is None or not enabled:
                return False

            autoreactions = await self.db.fetch(
                """
                SELECT trigger, emoji FROM autoreactions 
                WHERE guild_id = $1 AND enabled = $2
                """,
                message.guild.id,
                True,
            )

            for ar in autoreactions:
                trigger = ar["trigger"]
                emoji = ar["emoji"]

                if trigger.lower() in message.content.lower():
                    try:
                        await message.add_reaction(emoji)
                        return True
                    except discord.HTTPException as e:
                        print(f"Failed to add reaction {emoji}: {e}")
                        continue

        except Exception as e:
            print(f"Error in process_autoreactions: {e}")
            import traceback

            traceback.print_exc()

        return False

    async def process_userreactions(self, message: discord.Message) -> bool:
        """Process userreactions for a message. Returns True if a reaction was added."""
        try:
            userreactions = await self.db.fetch(
                """
                SELECT user_id, emoji FROM userreactions 
                WHERE guild_id = $1
                """,
                message.guild.id,
            )

            for ur in userreactions:
                user_id = ur["user_id"]
                emoji_str = ur["emoji"]

                if user_id == message.author.id:
                    emojis = [e.strip() for e in emoji_str.split(",") if e.strip()]

                    for emoji in emojis:
                        try:
                            await message.add_reaction(emoji)
                        except discord.HTTPException as e:
                            print(f"Failed to add reaction {emoji}: {e}")
                            continue

                    return bool(emojis)

        except Exception as e:
            print(f"Error in process_userreactions: {e}")
            import traceback

            traceback.print_exc()

        return False

    @Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        response_sent = await self.process_autoresponders(message)

        if not response_sent:
            await self.process_autoreactions(message)
            await self.process_userreactions(message)

    @hybrid_group(
        name="autoresponder", description="Setup autoresponders for your server."
    )
    @has_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def autoresponder(self, ctx: Context):
        """Setup autoresponders for your server."""
        if ctx.invoked_subcommand is None:
            return

    @autoresponder.command(name="create")
    @has_permissions(manage_guild=True)
    @app_commands.describe(
        trigger="The trigger for the autoresponder.",
        response="The response for the autoresponder.",
        string="Type of matching to use (exact, partial, or regex).",
    )
    @app_commands.choices(
        string=[
            app_commands.Choice(name="Exact", value="exact"),
            app_commands.Choice(name="Partial", value="partial"),
            app_commands.Choice(name="Regex", value="regex"),
        ]
    )
    async def create(
        self, ctx: Context, trigger: str, response: str, string: str = "exact"
    ):
        """Create an autoresponder."""

        existing = await self.db.fetchrow(
            """
            SELECT * FROM autoresponders
            WHERE guild_id = $1 AND trigger = $2
            """,
            ctx.guild.id,
            trigger,
        )

        if existing:
            await ctx.send("Autoresponder already exists.")
            return

        if string == "regex":
            string_value = True
        elif string == "partial":
            string_value = False
        else:
            string_value = None

        try:
            await self.db.execute(
                """
                INSERT INTO autoresponders (guild_id, trigger, response, string, enabled)
                VALUES ($1, $2, $3, $4, $5)
                """,
                ctx.guild.id,
                trigger,
                response,
                string_value,
                True,
            )

            # verify = await self.db.fetch(
            #     "SELECT * FROM autoresponders WHERE guild_id = $1",
            #     ctx.guild.id
            # )
            # print(f"Current autoresponders in DB: {verify}")

        except Exception as e:
            print(f"Error creating autoresponder: {e}")
            import traceback

            traceback.print_exc()
            await ctx.send(
                "An error occurred while creating the autoresponder.", ephemeral=True
            )
            return

        embed = discord.Embed(
            description=f"Autoresponder created.\n\n"
            f"**Trigger**: {trigger}\n"
            f"**Response**: {response}\n"
            f"**Match Type**: {string.title()}",
            color=discord.Color(0xFFFFFF),
        )
        await ctx.send(embed=embed)

    @autoresponder.command(name="delete")
    @has_permissions(manage_guild=True)
    @app_commands.describe(
        trigger="The trigger for the autoresponder.",
    )
    async def delete(self, ctx: Context, trigger: str):
        """Delete an autoresponder."""
        await self.db.execute(
            """
            DELETE FROM autoresponders
            WHERE guild_id = $1 AND trigger = $2
            """,
            ctx.guild.id,
            trigger,
        )

        embed = discord.Embed(
            description=f"Autoresponder deleted.\n\n" f"**Trigger**: {trigger}",
            color=discord.Color(0xFFFFFF),
        )
        await ctx.send(embed=embed)

    @autoresponder.command(name="list")
    @has_permissions(manage_guild=True)
    @app_commands.describe()
    async def list(self, ctx: Context):
        """List all autoresponders."""
        autoresponders = await self.db.fetch(
            """
            SELECT * FROM autoresponders
            WHERE guild_id = $1
            """,
            ctx.guild.id,
        )

        def get_match_type(string_value):
            if string_value is None:
                return "Exact"
            elif string_value is True:
                return "Regex"
            else:
                return "Partial"

        description = "\n\n".join(
            f"> **{ar['trigger']}**\n**Response**: {ar['response']}\n**Type**: {get_match_type(ar['string'])}"
            for ar in autoresponders
        )
        embed = discord.Embed(
            description=description,
            color=discord.Color(0xFFFFFF),
        )
        await ctx.send(embed=embed)

    @autoresponder.command(name="edit")
    @has_permissions(manage_guild=True)
    @app_commands.describe(
        trigger="The trigger for the autoresponder.",
        response="The response for the autoresponder.",
        string="Type of matching to use (exact, partial, or regex).",
    )
    @app_commands.choices(
        string=[
            app_commands.Choice(name="Exact", value="exact"),
            app_commands.Choice(name="Partial", value="partial"),
            app_commands.Choice(name="Regex", value="regex"),
        ]
    )
    async def edit(
        self, ctx: Context, trigger: str, response: str, string: str = "exact"
    ):
        """Edit an autoresponder."""
        if string == "regex":
            string_value = True
        elif string == "partial":
            string_value = False
        else:
            string_value = None

        await self.db.execute(
            """
            UPDATE autoresponders
            SET response = $3, string = $4
            WHERE guild_id = $1 AND trigger = $2
            """,
            ctx.guild.id,
            trigger,
            response,
            string_value,
        )

        embed = discord.Embed(
            description=f"Autoresponder edited.\n\n"
            f"**Trigger**: {trigger}\n"
            f"**Response**: {response}\n"
            f"**Match Type**: {string.title()}",
            color=discord.Color(0xFFFFFF),
        )
        await ctx.send(embed=embed)

    @autoresponder.command(name="toggle")
    @has_permissions(manage_guild=True)
    @app_commands.describe(action="Whether to enable or disable autoresponders")
    @app_commands.choices(
        action=[
            app_commands.Choice(name="Enable", value="enable"),
            app_commands.Choice(name="Disable", value="disable"),
        ]
    )
    async def toggle(self, ctx: Context, action: str):
        """Toggle autoresponders for this server."""
        status = action == "enable"

        await self.db.execute(
            """
            UPDATE autoresponders
            SET enabled = $2
            WHERE guild_id = $1
            """,
            ctx.guild.id,
            status,
        )

        embed = discord.Embed(
            description=f"Autoresponders have been {'enabled' if status else 'disabled'} for this server.",
            color=discord.Color(0xFFFFFF),
        )
        await ctx.send(embed=embed)

    @hybrid_group(
        name="autoreactions", aliases=["ar"], description="Setup autoreactions for your server."
    )
    @has_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def autoreactions(self, ctx: Context):
        """Setup autoreactions for your server."""
        if ctx.invoked_subcommand is None:
            return

    @autoreactions.command(name="create")
    @has_permissions(manage_guild=True)
    @app_commands.describe(
        trigger="The trigger for the autoreaction.",
        emoji="The emoji for the autoreaction.",
    )
    async def create(self, ctx: Context, trigger: str, emoji: str):
        """Create an autoreaction."""
        if await self.db.fetchrow(
            """
            SELECT * FROM autoreactions
            WHERE guild_id = $1 AND trigger = $2
            """,
            ctx.guild.id,
            trigger,
        ):
            await ctx.send("Autoreaction already exists.")
            return
        await self.db.execute(
            """
            INSERT INTO autoreactions (guild_id, trigger, emoji)
            VALUES ($1, $2, $3)
            """,
            ctx.guild.id,
            trigger,
            emoji,
        )

        embed = discord.Embed(
            description=f"Autoreaction created.\n\n"
            f"**Trigger**: {trigger}\n"
            f"**Emoji**: {emoji}",
            color=discord.Color(0xFFFFFF),
        )
        await ctx.send(embed=embed)

    @autoreactions.command(name="delete")
    @has_permissions(manage_guild=True)
    @app_commands.describe(
        trigger="The trigger for the autoreaction.",
    )
    async def delete(self, ctx: Context, trigger: str):
        """Delete an autoreaction."""
        await self.db.execute(
            """
            DELETE FROM autoreactions
            WHERE guild_id = $1 AND trigger = $2
            """,
            ctx.guild.id,
            trigger,
        )

        embed = discord.Embed(
            description=f"Autoreaction deleted.\n\n" f"**Trigger**: {trigger}",
            color=discord.Color(0xFFFFFF),
        )
        await ctx.send(embed=embed)

    @autoreactions.command(name="list")
    @app_commands.describe()
    async def list(self, ctx: Context):
        """List all autoreactions."""
        autoreactions = await self.db.fetch(
            """
            SELECT * FROM autoreactions
            WHERE guild_id = $1
            """,
            ctx.guild.id,
        )

        embed = discord.Embed(
            description="Autoreactions:\n\n"
            + "\n".join(
                [f'**{ar["trigger"]}**: {ar["emoji"]}' for ar in autoreactions]
            ),
            color=discord.Color(0xFFFFFF),
        )
        await ctx.send(embed=embed)

    @autoreactions.command(name="edit")
    @has_permissions(manage_guild=True)
    @app_commands.describe(
        trigger="The trigger for the autoreaction.",
        emoji="The emoji for the autoreaction.",
    )
    async def edit(self, ctx: Context, trigger: str, emoji: str):
        """Edit an autoreaction."""
        await self.db.execute(
            """
            UPDATE autoreactions
            SET emoji = $3
            WHERE guild_id = $1 AND trigger = $2
            """,
            ctx.guild.id,
            trigger,
            emoji,
        )

        embed = discord.Embed(
            description=f"Autoreaction edited.\n\n"
            f"**Trigger**: {trigger}\n"
            f"**Emoji**: {emoji}",
            color=discord.Color(0xFFFFFF),
        )
        await ctx.send(embed=embed)

    @autoreactions.command(name="toggle")
    @has_permissions(manage_guild=True)
    @app_commands.describe(
        trigger="The trigger to enable/disable",
        action="Whether to enable or disable the autoreaction",
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="Enable", value="enable"),
            app_commands.Choice(name="Disable", value="disable"),
        ]
    )
    async def toggle(self, ctx: Context, trigger: str, action: str):
        """Toggle a specific autoreaction. Whether to enable or disable the autoreaction"""
        status = action == "enable"

        exists = await self.db.fetchrow(
            "SELECT * FROM autoreactions WHERE guild_id = $1 AND trigger = $2",
            ctx.guild.id,
            trigger,
        )

        if not exists:
            await ctx.send(f"No autoreaction found for trigger: {trigger}")
            return

        await self.db.execute(
            """
            UPDATE autoreactions
            SET enabled = $3
            WHERE guild_id = $1 AND trigger = $2
            """,
            ctx.guild.id,
            trigger,
            status,
        )

        embed = discord.Embed(
            description=f"Autoreaction for `{trigger}` has been **{action}d**.",
            color=discord.Color(0xFFFFFF),
        )
        await ctx.send(embed=embed)

    @hybrid_group(
        name="userreactions", description="Setup userreactions for your server."
    )
    @has_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def userreactions(self, ctx: Context):
        """Setup userreactions for your server."""
        if ctx.invoked_subcommand is None:
            return

    @userreactions.command(name="create")
    @has_permissions(manage_guild=True)
    @app_commands.describe(
        emoji="The emoji for the userreaction. Separate multiple emojis with commas.",
        user="The user to add the userreaction to.",
    )
    async def create(self, ctx: Context, emoji: str, user: User):
        """Create a userreaction."""
        emojis = [e.strip() for e in emoji.split(",") if e.strip()]

        existing = await self.db.fetchrow(
            "SELECT * FROM userreactions WHERE guild_id = $1 AND user_id = $2",
            ctx.guild.id,
            user.id,
        )

        if existing:
            existing_emojis = [
                e.strip() for e in existing["emoji"].split(",") if e.strip()
            ]
            combined_emojis = list(dict.fromkeys(existing_emojis + emojis))
            emoji_str = ", ".join(combined_emojis)

            await self.db.execute(
                """
                UPDATE userreactions
                SET emoji = $3
                WHERE guild_id = $1 AND user_id = $2
                """,
                ctx.guild.id,
                user.id,
                emoji_str,
            )
        else:
            emoji_str = ", ".join(emojis)

            await self.db.execute(
                """
                INSERT INTO userreactions (guild_id, user_id, emoji)
                VALUES ($1, $2, $3)
                """,
                ctx.guild.id,
                user.id,
                emoji_str,
            )

        emoji_display = (
            f"\n\n**Emoji{'s' if len(emoji_str.split(',')) > 1 else ''}:** {emoji_str}"
            if emoji_str
            else ""
        )

        embed = discord.Embed(
            description=f"Userreaction created\n\n**User:** {user.mention}{emoji_display}",
            color=discord.Color(0xFFFFFF),
        )
        await ctx.send(embed=embed)

    @userreactions.command(name="delete")
    @has_permissions(manage_guild=True)
    @app_commands.describe(
        user="The user to remove the userreaction from.",
    )
    async def delete(self, ctx: Context, user: User):
        """Delete a userreaction."""
        userreaction = await self.db.fetchrow(
            """
            SELECT emoji FROM userreactions
            WHERE guild_id = $1 AND user_id = $2
            """,
            ctx.guild.id,
            user.id,
        )

        await self.db.execute(
            """
            DELETE FROM userreactions
            WHERE guild_id = $1 AND user_id = $2
            """,
            ctx.guild.id,
            user.id,
        )

        emoji_str = userreaction["emoji"] if userreaction else ""
        emoji_display = (
            f"\n\n**Emoji{'s' if len(emoji_str.split(',')) > 1 else ''}:** {emoji_str}"
            if emoji_str
            else ""
        )

        embed = discord.Embed(
            description=f"Userreaction deleted for {user.mention}\n\n{emoji_display}",
            color=discord.Color(0xFFFFFF),
        )
        await ctx.send(embed=embed)

    @userreactions.command(name="list")
    @has_permissions(manage_guild=True)
    async def list(self, ctx: Context):
        """List all userreactions for this guild."""
        guild_id = ctx.guild.id
        userreactions = await self.db.fetch(
            """
            SELECT * FROM userreactions
            WHERE guild_id = $1
            """,
            guild_id,
        )

        if not userreactions:
            await ctx.send("No userreactions found for this guild.")
        else:
            embed = discord.Embed(
                description=f"Userreactions for {ctx.guild}:\n\n"
                + "\n".join(
                    [f'<@{ur["user_id"]}>: {ur["emoji"]}' for ur in userreactions]
                ),
                color=discord.Color(0xFFFFFF),
            )
            await ctx.send(embed=embed)

    @userreactions.command(name="reset")
    @has_permissions(manage_guild=True)
    async def reset(self, ctx: Context):
        """Reset all userreactions for this guild."""
        await self.db.execute(
            """
            DELETE FROM userreactions
            WHERE guild_id = $1
            """,
            ctx.guild.id,
        )

        await ctx.send("Userreactions reset for this guild.")
