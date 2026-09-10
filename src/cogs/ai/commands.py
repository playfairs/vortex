# python
import os
import discord
from discord import app_commands
from discord.ext import commands
from discord.ext.commands import Cog, Context, hybrid_command as hybrid

from .utils import get_ai_response
from vortex import vortex


class AICommands(Cog, description="View commands in AICommands."):
    def __init__(self, bot: vortex):
        self.bot = bot
        self.api_url = "https://api.voidai.app/v1/chat/completions"
        self.api_key = os.getenv("VOID_AI_API_KEY")
        self.ai_cache = {"enabled_guilds": set(), "enabled_channels": set()}
        self.ctx_menu = app_commands.ContextMenu(
            name="Reply with AI",
            callback=self.reply_with_ai,
            allowed_contexts=app_commands.AppCommandContext(
                guild=True, dm_channel=True, private_channel=True
            ),
            allowed_installs=app_commands.AppInstallationType(guild=True, user=True),
        )
        self.bot.tree.add_command(self.ctx_menu)
        print("Loaded AI Context Menu Command: Reply with AI")

    async def cog_load(self):
        await self.create_tables()
        await self.load_ai_settings()

    async def create_tables(self):
        """Create the AI settings tables if they don't exist."""
        async with self.bot.db.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_guild_settings (
                    guild_id BIGINT PRIMARY KEY,
                    enabled BOOLEAN DEFAULT FALSE
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_channel_settings (
                    channel_id BIGINT PRIMARY KEY,
                    guild_id BIGINT NOT NULL,
                    enabled BOOLEAN DEFAULT FALSE
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_active_conversations (
                    channel_id BIGINT,
                    user_id BIGINT,
                    last_activity TIMESTAMP NOT NULL,
                    PRIMARY KEY (channel_id, user_id)
                )
                """
            )

    async def load_ai_settings(self):
        """Load AI settings from the database into cache."""
        async with self.bot.db.acquire() as conn:
            records = await conn.fetch(
                "SELECT guild_id FROM ai_guild_settings WHERE enabled = TRUE"
            )
            self.ai_cache["enabled_guilds"] = {r["guild_id"] for r in records}
            records = await conn.fetch(
                "SELECT channel_id FROM ai_channel_settings WHERE enabled = TRUE"
            )
            self.ai_cache["enabled_channels"] = {r["channel_id"] for r in records}

    async def is_ai_enabled(self, guild_id: int, channel_id: int = None) -> tuple:
        """Return (is_enabled, is_channel_specific) for guild and optional channel."""
        if not guild_id:
            return False, False
        if guild_id in self.ai_cache["enabled_guilds"]:
            return True, False
        if channel_id:
            return channel_id in self.ai_cache["enabled_channels"], True
        return False, False

    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def reply_with_ai(
        self, interaction: discord.Interaction, message: discord.Message
    ):
        """Context menu command to reply to a message with AI."""
        if interaction.user.id not in self.bot.owner_ids:
            return await interaction.response.send_message(
                "You do not have permission to use this command.", ephemeral=True
            )

        if message.author == self.bot.user:
            return await interaction.response.send_message(
                "I can't reply to my own messages!", ephemeral=True
            )

        is_enabled, is_channel_specific = await self.is_ai_enabled(
            interaction.guild.id if interaction.guild else None,
            interaction.channel.id if hasattr(interaction.channel, "id") else None,
        )

        if not is_enabled:
            return await interaction.response.send_message(
                "AI is not enabled in this channel or server.", ephemeral=True
            )

        if is_channel_specific and interaction.channel.id != message.channel.id:
            return await interaction.response.send_message(
                "AI is only enabled in specific channels. Please use the command in the correct channel.",
                ephemeral=True,
            )

        await interaction.response.defer(ephemeral=True)

        utility_cog = self.bot.get_cog("Utility")
        user_time = None
        if utility_cog and hasattr(utility_cog, "get_user_current_time"):
            user_time = await utility_cog.get_user_current_time(message.author.id)

        reply = await get_ai_response(
            message, self.bot.user, self.api_url, self.api_key, user_time
        )

        if reply and reply.get("text"):
            if (
                getattr(interaction.channel, "type", None)
                == discord.ChannelType.private
            ):
                await interaction.followup.send(reply["text"], ephemeral=False)
            else:
                await interaction.followup.send(
                    reply["text"],
                    allowed_mentions=discord.AllowedMentions.none(),
                    ephemeral=False,
                )
        else:
            await interaction.followup.send(
                "Failed to get a response from the AI.", ephemeral=True
            )

    @hybrid(name="ai", description="Toggles the AI Cog per server or channel")
    @app_commands.describe(
        enabled="Enable or Disable the AI in this server",
        channel="The channel to enable/disable the AI in (optional)",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def ai(
        self, ctx: Context, enabled: bool, channel: discord.TextChannel = None
    ):
        """Toggle AI functionality for the server or a specific channel."""
        if not ctx.guild:
            return await ctx.send("This command can only be used in a server.")

        async with self.bot.db.acquire() as conn:
            if channel:
                if enabled:
                    await conn.execute(
                        """
                        INSERT INTO ai_channel_settings (channel_id, guild_id, enabled)
                        VALUES ($1, $2, TRUE)
                        ON CONFLICT (channel_id) DO UPDATE SET enabled = TRUE
                        """,
                        channel.id,
                        ctx.guild.id,
                    )
                    self.ai_cache["enabled_channels"].add(channel.id)
                    await ctx.send(f"AI enabled in {channel.mention}")
                else:
                    await conn.execute(
                        "DELETE FROM ai_channel_settings WHERE channel_id = $1",
                        channel.id,
                    )
                    self.ai_cache["enabled_channels"].discard(channel.id)
                    await ctx.send(f"AI disabled in {channel.mention}")
            else:
                if enabled:
                    await conn.execute(
                        """
                        INSERT INTO ai_guild_settings (guild_id, enabled)
                        VALUES ($1, TRUE)
                        ON CONFLICT (guild_id) DO UPDATE SET enabled = TRUE
                        """,
                        ctx.guild.id,
                    )
                    self.ai_cache["enabled_guilds"].add(ctx.guild.id)
                    await ctx.send("AI enabled for this server")
                else:
                    await conn.execute(
                        "DELETE FROM ai_guild_settings WHERE guild_id = $1",
                        ctx.guild.id,
                    )
                    await conn.execute(
                        "DELETE FROM ai_channel_settings WHERE guild_id = $1",
                        ctx.guild.id,
                    )

                    self.ai_cache["enabled_guilds"].discard(ctx.guild.id)
                    self.ai_cache["enabled_channels"] = {
                        cid
                        for cid in self.ai_cache["enabled_channels"]
                        if cid not in {c.id for c in ctx.guild.channels}
                    }

                    await ctx.send("AI has been completely disabled for this server")
