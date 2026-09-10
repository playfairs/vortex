from discord.ext.commands import (
    Cog,
    command,
    has_permissions,
    Context,
    group,
    hybrid_group,
    hybrid_command as hybrid,
)
from discord import app_commands
from base.embeds import Builder
from vortex import vortex
import discord


class Config(Cog, description="View and manage server configuration."):
    def __init__(self, bot: vortex):
        self.bot = bot
        self.db = bot.db

    async def cog_load(self):
        """Called when the cog is loaded."""
        await self.create_config_tables()

    async def create_config_tables(self):
        """Create the necessary database tables if they don't exist."""
        try:
            await self.db.execute(
                """
                CREATE TABLE IF NOT EXISTS config (
                    guild_id BIGINT PRIMARY KEY,
                    prefix TEXT NOT NULL,
                    modlogs BIGINT
                );
                CREATE TABLE IF NOT EXISTS autorole (
                    guild_id BIGINT PRIMARY KEY,
                    role_id BIGINT,
                    bot_role_id BIGINT
                );
                CREATE TABLE IF NOT EXISTS gate (
                    guild_id BIGINT PRIMARY KEY,
                    role_id BIGINT,
                    channel_id BIGINT,
                    welcome_message TEXT,
                    goodbye_message TEXT,
                    dm_message TEXT
                );
                """
            )
        except Exception as e:
            print(f"Error creating config tables: {e}")
            raise

    @hybrid_group(name="server", invoke_without_command=True)
    @app_commands.guild_only()
    @has_permissions(manage_guild=True)
    async def server(self, ctx: Context):
        """Server configuration commands."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @server.group(name="prefix", invoke_without_command=True)
    @has_permissions(manage_guild=True)
    async def server_prefix(self, ctx: Context):
        """View or manage the server prefix."""
        prefix = await self.db.fetchval(
            "SELECT prefix FROM config WHERE guild_id = $1", ctx.guild.id
        )
        if prefix is None:
            prefix = (
                self.bot.command_prefix[0]
                if isinstance(self.bot.command_prefix, (list, tuple))
                else self.bot.command_prefix
            )

        embed = discord.Embed(
            description=f"This server's prefix is `{prefix}`",
            color=discord.Color(0xFFFFFF),
        )
        await ctx.send(embed=embed)

    @server_prefix.command(name="set")
    @app_commands.describe(prefix="The new prefix for the server")
    @has_permissions(manage_guild=True)
    async def server_prefix_set(self, ctx: Context, prefix: str):
        """Set the server prefix."""
        if len(prefix) > 10:
            await ctx.send("Prefix cannot be longer than 10 characters.")
            return

        await self.db.execute(
            """
            INSERT INTO config (guild_id, prefix) 
            VALUES ($1, $2) 
            ON CONFLICT (guild_id) DO UPDATE SET prefix = $2
            """,
            ctx.guild.id,
            prefix,
        )
        await ctx.send(f"Server prefix set to: `{prefix}`")

    @server_prefix.command(name="reset")
    @has_permissions(manage_guild=True)
    async def server_prefix_reset(self, ctx: Context):
        """Reset the server prefix to the default."""
        await self.db.execute("DELETE FROM config WHERE guild_id = $1", ctx.guild.id)
        default_prefix = (
            self.bot.command_prefix[0]
            if isinstance(self.bot.command_prefix, (list, tuple))
            else self.bot.command_prefix
        )
        await ctx.send(f"Server prefix reset to default: `{default_prefix}`")

    @hybrid_group(name="gate", invoke_without_command=True)
    @app_commands.guild_only()
    @has_permissions(manage_guild=True)
    async def gate(self, ctx: Context):
        """View or manage the server gate."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @gate.group(
        name="welcome",
        description="Manage the server gate welcome message.",
        invoke_without_command=True,
    )
    @has_permissions(manage_guild=True)
    async def gate_welcome(self, ctx: Context):
        """View or manage the server gate welcome message."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @gate_welcome.command(name="set")
    @app_commands.describe(
        message="The message to send when a user joins the server. Use {user.mention} for mentions, {user.name} for username, etc."
    )
    @has_permissions(manage_guild=True)
    async def gate_welcome_set(self, ctx: Context, *, message: str):
        """Set the server gate welcome message with embed replacements."""
        if not message.strip():
            return await ctx.send("Message cannot be empty.")

        current = await self.db.fetchrow(
            "SELECT channel_id FROM gate WHERE guild_id = $1", ctx.guild.id
        )
        channel_id = current["channel_id"] if current else ctx.channel.id

        await self.db.execute(
            """
            INSERT INTO gate (guild_id, channel_id, welcome_message) 
            VALUES ($1, $2, $3) 
            ON CONFLICT (guild_id) DO UPDATE SET 
                welcome_message = EXCLUDED.welcome_message,
                channel_id = EXCLUDED.channel_id
            """,
            ctx.guild.id,
            channel_id,
            message,
        )

        try:
            preview = Builder.embed_replacement(ctx.author, message)
            embed = discord.Embed(
                description=f"Server gate welcome message has been updated.\n\n**Preview:**\n{preview}",
                color=0x2B2D31,
            )
            await ctx.send(embed=embed)

        except Exception as e:
            embed = discord.Embed(
                description=f"Server gate welcome message has been updated.\n⚠️ There was an error generating the preview: {str(e)}",
                color=0x2B2D31,
            )
            await ctx.send(embed=embed)

    @gate.group(
        name="goodbye",
        description="Manage the server gate goodbye message.",
        invoke_without_command=True,
    )
    @has_permissions(manage_guild=True)
    async def gate_goodbye(self, ctx: Context):
        """Set the server gate goodbye message."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @gate_goodbye.command(name="set")
    @app_commands.describe(
        message="The message to send when a user leaves the server. Use {user.name} for username, etc."
    )
    @has_permissions(manage_guild=True)
    async def gate_goodbye_set(self, ctx: Context, *, message: str):
        """Set the server gate goodbye message with embed replacements."""
        if not message.strip():
            return await ctx.send("Message cannot be empty.")

        current = await self.db.fetchrow(
            "SELECT channel_id FROM gate WHERE guild_id = $1", ctx.guild.id
        )
        channel_id = current["channel_id"] if current else ctx.channel.id

        await self.db.execute(
            """
            INSERT INTO gate (guild_id, channel_id, goodbye_message) 
            VALUES ($1, $2, $3) 
            ON CONFLICT (guild_id) DO UPDATE SET 
                goodbye_message = EXCLUDED.goodbye_message,
                channel_id = EXCLUDED.channel_id
            """,
            ctx.guild.id,
            channel_id,
            message,
        )

        try:
            preview = Builder.embed_replacement(ctx.author, message)
            embed = discord.Embed(
                description=f"Server gate goodbye message has been updated.\n\n**Preview:**\n{preview}",
                color=0x2B2D31,
            )
            await ctx.send(embed=embed)

        except Exception as e:
            embed = discord.Embed(
                description=f"Server gate goodbye message has been updated.\n⚠️ There was an error generating the preview: {str(e)}",
                color=0x2B2D31,
            )
            await ctx.send(embed=embed)

    @gate.group(
        name="dm",
        description="Manage the server gate DM message.",
        invoke_without_command=True,
    )
    @has_permissions(manage_guild=True)
    async def gate_dm(self, ctx: Context):
        """View or manage the server gate DM message."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @gate_dm.command(name="set")
    @app_commands.describe(
        message="The message to DM when a user joins the server. Use {user.mention} for mentions, {user.name} for username, etc."
    )
    @has_permissions(manage_guild=True)
    async def gate_dm_set(self, ctx: Context, *, message: str):
        """Set the server gate DM message with embed replacements."""
        if not message.strip():
            return await ctx.send("Message cannot be empty.")

        current = await self.db.fetchrow(
            "SELECT channel_id FROM gate WHERE guild_id = $1", ctx.guild.id
        )
        channel_id = current["channel_id"] if current else ctx.channel.id

        await self.db.execute(
            """
            INSERT INTO gate (guild_id, channel_id, dm_message) 
            VALUES ($1, $2, $3) 
            ON CONFLICT (guild_id) DO UPDATE SET 
                dm_message = EXCLUDED.dm_message,
                channel_id = EXCLUDED.channel_id
            """,
            ctx.guild.id,
            channel_id,
            message,
        )

        try:
            preview = Builder.embed_replacement(ctx.author, message)
            embed = discord.Embed(
                description=f"Server gate DM message has been updated.\n\n**Preview:**\n{preview}",
                color=0x2B2D31,
            )
            await ctx.send(embed=embed)

        except Exception as e:
            embed = discord.Embed(
                description=f"Server gate DM message has been updated.\n⚠️ There was an error generating the preview: {str(e)}",
                color=0x2B2D31,
            )
            await ctx.send(embed=embed)

    @gate_dm.command(name="reset")
    @has_permissions(manage_guild=True)
    async def gate_dm_reset(self, ctx: Context):
        """Reset the server gate DM message."""
        await self.db.execute("DELETE FROM gate WHERE guild_id = $1", ctx.guild.id)
        embed = discord.Embed(
            description="Server gate DM message reset.", color=discord.Color(0xFFFFFF)
        )
        await ctx.send(embed=embed)

    @gate.command(
        name="channel",
        description="Manage the server gate channel.",
        invoke_without_command=True,
    )
    @has_permissions(manage_guild=True)
    @app_commands.describe(channel="The channel to send the server gate messages to")
    async def gate_channel(self, ctx: Context, channel: discord.TextChannel):
        """Set the server gate channel."""
        await self.db.execute(
            """
            INSERT INTO gate (guild_id, channel_id) 
            VALUES ($1, $2) 
            ON CONFLICT (guild_id) DO UPDATE SET channel_id = $2
            """,
            ctx.guild.id,
            channel.id,
        )
        await ctx.send(f"Server gate channel set to: {channel.mention}")

    @gate.command(
        name="view", description="View the server gate.", invoke_without_command=True
    )
    @has_permissions(manage_guild=True)
    async def gate_view(self, ctx: Context):
        """View the server gate."""
        async with self.db.acquire() as conn:
            gate = await conn.fetchrow(
                """
                SELECT * FROM gate WHERE guild_id = $1
                """,
                ctx.guild.id,
            )
            if gate is None:
                await ctx.send("No server gate set.")
                return

            channel = ctx.guild.get_channel(gate["channel_id"])
            embed = discord.Embed(
                title="Server Gate",
                description=(
                    f"**Channel:** {channel.mention if channel else 'Not Enabled'}\n"
                    + (
                        f"**Welcome Message:** {gate['welcome_message']}\n"
                        if gate["welcome_message"]
                        else ""
                    )
                    + (
                        f"**Goodbye Message:** {gate['goodbye_message']}\n"
                        if gate["goodbye_message"]
                        else ""
                    )
                    + (
                        f"**DM Message:** {gate['dm_message']}"
                        if gate["dm_message"]
                        else ""
                    )
                ),
                color=discord.Color(0xFFFFFF),
            )
            await ctx.send(embed=embed)

    @gate.command(
        name="reset", description="Reset the server gate.", invoke_without_command=True
    )
    @has_permissions(manage_guild=True)
    async def gate_reset(self, ctx: Context):
        """Reset the server gate."""
        await self.db.execute("DELETE FROM gate WHERE guild_id = $1", ctx.guild.id)
        await ctx.send("Server gate reset.")

    @gate.command(name="toggle", description="Toggle the server gate.")
    @has_permissions(manage_guild=True)
    @app_commands.describe(status="Enable or disable the server gate")
    @app_commands.choices(
        status=[
            app_commands.Choice(name="Enable", value="enable"),
            app_commands.Choice(name="Disable", value="disable"),
        ]
    )
    async def gate_toggle(self, ctx: Context, status: str):
        """Toggle the server gate."""
        async with self.db.acquire() as conn:
            gate = await conn.fetchrow(
                """
                SELECT * FROM gate WHERE guild_id = $1
                """,
                ctx.guild.id,
            )
            if gate is None and status == "disable":
                await ctx.send("Gate is not configured.")
                return

            if status == "enable":
                await self.db.execute(
                    """
                    INSERT INTO gate (guild_id, channel_id)
                    VALUES ($1, $2)
                    ON CONFLICT (guild_id) DO UPDATE SET channel_id = $2
                    """,
                    ctx.guild.id,
                    ctx.channel.id,
                )
                await ctx.send("Server gate enabled.")
            else:
                await self.db.execute(
                    "DELETE FROM gate WHERE guild_id = $1", ctx.guild.id
                )
                await ctx.send("Server gate disabled.")

    @hybrid_group(name="autorole", invoke_without_command=True)
    @app_commands.guild_only()
    @has_permissions(manage_guild=True)
    async def autorole(self, ctx: Context):
        """View or manage the server autorole."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @autorole.group(
        name="set", description="Set the server autorole.", invoke_without_command=True
    )
    @has_permissions(manage_guild=True)
    async def autorole_set(self, ctx: Context):
        """Set the server autorole."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @autorole_set.command(
        name="human",
        description="Set the server autorole for humans.",
        invoke_without_command=True,
    )
    @has_permissions(manage_guild=True)
    async def autorole_set_human(self, ctx: Context, role: discord.Role):
        """Set the server autorole for humans."""
        await self.db.execute(
            """
            INSERT INTO autorole (guild_id, role_id)
            VALUES ($1, $2)
            ON CONFLICT (guild_id) DO UPDATE SET role_id = $2
            """,
            ctx.guild.id,
            role.id,
        )
        await ctx.send(f"Server autorole for humans set to: {role.mention}")

    @autorole_set.command(
        name="bot",
        description="Set the server autorole for bots.",
        invoke_without_command=True,
    )
    @has_permissions(manage_guild=True)
    async def autorole_set_bot(self, ctx: Context, role: discord.Role):
        """Set the server autorole for bots."""
        await self.db.execute(
            """
            INSERT INTO autorole (guild_id, bot_role_id)
            VALUES ($1, $2)
            ON CONFLICT (guild_id) DO UPDATE SET bot_role_id = $2
            """,
            ctx.guild.id,
            role.id,
        )
        await ctx.send(f"Server autorole for bots set to: {role.mention}")

    @autorole.command(
        name="view",
        description="View the server autorole.",
        invoke_without_command=True,
    )
    @has_permissions(manage_guild=True)
    async def autorole_view(self, ctx: Context):
        """View the server autorole."""
        autorole = await self.db.fetchrow(
            """
            SELECT * FROM autorole WHERE guild_id = $1
            """,
            ctx.guild.id,
        )

        if not autorole or (
            not autorole.get("role_id") and not autorole.get("bot_role_id")
        ):
            await ctx.send("No autoroles have been set up yet.")
            return

        human_role = (
            ctx.guild.get_role(autorole.get("role_id"))
            if autorole.get("role_id")
            else None
        )
        bot_role = (
            ctx.guild.get_role(autorole.get("bot_role_id"))
            if autorole.get("bot_role_id")
            else None
        )

        embed = discord.Embed(title="Server Autoroles", color=discord.Color.blue())

        if human_role:
            embed.add_field(name="Human Role", value=human_role.mention, inline=False)
        if bot_role:
            embed.add_field(name="Bot Role", value=bot_role.mention, inline=False)

        await ctx.send(embed=embed)

    @autorole.command(
        name="reset",
        description="Reset the server autorole.",
        invoke_without_command=True,
    )
    @has_permissions(manage_guild=True)
    async def autorole_reset(self, ctx: Context):
        """Reset the server autorole."""
        await self.db.execute("DELETE FROM autorole WHERE guild_id = $1", ctx.guild.id)
        await ctx.send("Server autorole reset.")

    @autorole.command(name="toggle", description="Toggle the server autorole.")
    @has_permissions(manage_guild=True)
    @app_commands.describe(status="Enable or disable the server autorole")
    @app_commands.choices(
        status=[
            app_commands.Choice(name="Enable", value="enable"),
            app_commands.Choice(name="Disable", value="disable"),
        ]
    )
    async def autorole_toggle(self, ctx: Context, status: str):
        """Toggle the server autorole."""
        async with self.db.acquire() as conn:
            autorole = await conn.fetchrow(
                """
                SELECT * FROM autorole WHERE guild_id = $1
                """,
                ctx.guild.id,
            )
            if autorole is None and status == "disable":
                await ctx.send("Autorole is not configured.")
                return

            if status == "enable":
                await self.db.execute(
                    """
                    INSERT INTO autorole (guild_id, role_id) 
                    VALUES ($1, $2) 
                    ON CONFLICT (guild_id) DO UPDATE SET role_id = $2
                    """,
                    ctx.guild.id,
                    ctx.channel.id,
                )
                await ctx.send("Server autorole enabled.")
            else:
                await self.db.execute(
                    "DELETE FROM autorole WHERE guild_id = $1", ctx.guild.id
                )
                await ctx.send("Server autorole disabled.")
