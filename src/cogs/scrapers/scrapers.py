import asyncio
import os
import logging
import sys
from pathlib import Path
from typing import Optional, Union
import discord
from discord.ext import tasks, commands
from discord import app_commands
from discord.ext.commands import (
    Cog,
    Context,
    has_permissions,
    hybrid_command as hybrid,
    hybrid_group,
    is_owner,
)
from .pinterest.pinterest import PinterestScraper
import io
import random
import time

logger = logging.getLogger(__name__)


class PinterestCog(Cog):
    def __init__(self, bot):
        self.bot = bot
        self.scraper = PinterestScraper()
        self.post_channel = None
        self.post_interval = 60

        try:
            self.post_pins = tasks.loop(seconds=self.post_interval, count=None)(
                self._post_pins
            )
        except Exception as e:
            logger.error(
                f"Failed to initialize Pinterest posting task: {e}", exc_info=True
            )
            raise

    async def cog_load(self):
        """Async initialization when the cog is loaded."""
        await self.create_tables()

    async def create_tables(self):
        """Create necessary database tables."""
        try:
            await self.bot.db.execute(
                """
                CREATE TABLE IF NOT EXISTS pinterest_queries (
                    id SERIAL PRIMARY KEY,
                    search_term TEXT NOT NULL,
                    added_by BIGINT NOT NULL,
                    guild_id BIGINT NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """
            )

            await self.bot.db.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS pinterest_queries_term_guild_idx 
                ON pinterest_queries (LOWER(search_term), guild_id)
            """
            )

            await self.bot.db.execute(
                """
                CREATE TABLE IF NOT EXISTS pinterest_config (
                    guild_id BIGINT PRIMARY KEY,
                    channel_id BIGINT,
                    is_active BOOLEAN DEFAULT false
                )
            """
            )
        except Exception as e:
            logger.error(f"Error creating Pinterest database tables: {e}")
            raise

    async def _post_pins(self):
        """Background task to post Pinterest images at regular intervals."""
        try:
            active_guilds = await self.bot.db.fetch(
                """
                SELECT * FROM pinterest_config 
                WHERE is_active = true 
                AND channel_id IS NOT NULL
                """
            )

            if not active_guilds:
                return

            print(f"post_pins: Found {len(active_guilds)} active guilds")

            for guild_config in active_guilds:
                try:
                    guild_id = guild_config["guild_id"]
                    print(f"post_pins: Processing guild {guild_id}")

                    query = await self.bot.db.fetchrow(
                        """
                        SELECT * FROM pinterest_queries 
                        WHERE guild_id = $1
                        ORDER BY RANDOM() 
                        LIMIT 1
                        """,
                        guild_id,
                    )

                    if not query:
                        print(f"No Pinterest queries found for guild {guild_id}")
                        continue

                    print(
                        f"post_pins: Found query '{query['search_term']}' for guild {guild_id}"
                    )

                    unique_query = (
                        f"{query['search_term']} {random.randint(1, 1000000)}"
                    )

                    downloaded_files = await self.scraper.scrape_pinterest(
                        unique_query, max_images=1
                    )

                    if not downloaded_files:
                        print(f"No images downloaded for query: {query['search_term']}")
                        continue

                    print(f"post_pins: Downloaded {len(downloaded_files)} files")

                    channel_id = guild_config.get("channel_id")
                    if not channel_id:
                        print(f"No channel set for guild {guild_id}")
                        continue

                    channel = self.bot.get_channel(channel_id)
                    if not channel:
                        print(
                            f"Could not find channel {channel_id} in guild {guild_id}"
                        )
                        continue

                    file_path = downloaded_files[0]
                    try:
                        with open(file_path, "rb") as f:
                            file_data = f.read()

                        unique_filename = f"{os.path.splitext(os.path.basename(file_path))[0]}_{int(time.time())}.jpg"

                        file_obj = discord.File(
                            io.BytesIO(file_data), filename=unique_filename
                        )

                        await channel.send(file=file_obj)
                        print(
                            f"Posted image to channel {channel_id} in guild {guild_id}"
                        )

                        try:
                            os.remove(file_path)
                            print(f"Cleaned up file: {file_path}")
                        except Exception as e:
                            print(f"Error cleaning up file {file_path}: {e}")

                    except Exception as e:
                        print(f"Error sending file {file_path} to channel: {e}")
                        try:
                            if os.path.exists(file_path):
                                os.remove(file_path)
                        except Exception as cleanup_error:
                            print(
                                f"Error during cleanup of failed send: {cleanup_error}"
                            )

                except Exception as e:
                    print(
                        f"Error processing guild {guild_config.get('guild_id', 'unknown')}: {e}"
                    )

        except Exception as e:
            print(f"Error in post_pins task: {e}")
        finally:
            print("post_pins: Task completed")

    @hybrid_group(
        name="pinterest",
        aliases=["pin"],
        description="Base command for Pinterest commands.",
        invoke_without_command=True,
    )
    async def pinterest(self, ctx: Context):
        """Base command for Pinterest commands."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @pinterest.group(
        name="query",
        aliases=["q"],
        description="Base command for Pinterest query commands.",
        invoke_without_command=True,
    )
    async def query(self, ctx: Context):
        """Base command for Pinterest query commands."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @query.command(name="add", description="Add a new Pinterest search query")
    @app_commands.describe(query="The search term to add")
    async def add_query(self, ctx: Union[Context, discord.Interaction], *, query: str):
        """Add a new Pinterest search query to the database"""
        is_interaction = isinstance(ctx, discord.Interaction)
        if is_interaction:
            await ctx.response.defer()
            author = ctx.user
            guild_id = ctx.guild_id
        else:
            author = ctx.author
            guild_id = ctx.guild.id
            await ctx.typing()

        try:
            await self.bot.db.execute(
                """
                INSERT INTO pinterest_queries (search_term, added_by, guild_id)
                VALUES ($1, $2, $3)
                ON CONFLICT (LOWER(search_term), guild_id) DO NOTHING
                RETURNING *
                """,
                query.strip(),
                author.id,
                guild_id,
            )

            response = f"Added search query: `{query}`"
            if is_interaction:
                await ctx.followup.send(response)
            else:
                await ctx.send(response)

        except Exception as e:
            print(f"Error adding query: {e}")
            error_msg = "An error occurred while adding the query."
            if is_interaction:
                await ctx.followup.send(error_msg, ephemeral=True)
            else:
                await ctx.send(error_msg)

    @query.command(
        name="remove", aliases=["rm"], description="Remove a Pinterest search query"
    )
    @app_commands.describe(query="The search term to remove")
    async def remove_query(
        self, ctx: Union[Context, discord.Interaction], *, query: str
    ):
        """Remove a Pinterest search query from the database"""
        is_interaction = isinstance(ctx, discord.Interaction)
        if is_interaction:
            await ctx.response.defer()
            guild_id = ctx.guild_id
        else:
            guild_id = ctx.guild.id
            await ctx.typing()

        try:
            await self.bot.db.execute(
                "DELETE FROM pinterest_queries WHERE LOWER(search_term) = LOWER($1) AND guild_id = $2",
                query.strip(),
                guild_id,
            )

            response = f"Removed search query: `{query}`"
            if is_interaction:
                await ctx.followup.send(response)
            else:
                await ctx.send(response)

        except Exception as e:
            print(f"Error removing query: {e}")
            error_msg = "An error occurred while removing the query."
            if is_interaction:
                await ctx.followup.send(error_msg, ephemeral=True)
            else:
                await ctx.send(error_msg)

    @query.command(
        name="list", aliases=["ls"], description="List all Pinterest search queries"
    )
    async def list_queries(self, ctx: Union[Context, discord.Interaction]):
        """List all Pinterest search queries"""
        is_interaction = isinstance(ctx, discord.Interaction)
        if is_interaction:
            await ctx.response.defer()
            guild_id = ctx.guild_id
        else:
            guild_id = ctx.guild.id
            await ctx.typing()

        try:
            queries = await self.bot.db.fetch(
                "SELECT * FROM pinterest_queries WHERE guild_id = $1", guild_id
            )

            if not queries:
                response = "No Pinterest search queries found for this guild."
            else:
                embed = discord.Embed(
                    title="Pinterest Queries",
                    description="\n".join(
                        [f"- {query['search_term']}" for query in queries]
                    ),
                    color=discord.Color(0xFFFFFF),
                )
                response = embed

            if is_interaction:
                await ctx.followup.send(embed=response)
            else:
                await ctx.send(embed=response)

        except Exception as e:
            print(f"Error listing queries: {e}")
            error_msg = "An error occurred while listing the queries."
            if is_interaction:
                await ctx.followup.send(error_msg, ephemeral=True)
            else:
                await ctx.send(error_msg)

    @pinterest.command(
        name="channel",
        aliases=["ch"],
        description="Set the channel for Pinterest posts",
    )
    @app_commands.describe(channel="The channel to post Pinterest images to")
    async def set_channel(
        self, ctx: Union[Context, discord.Interaction], channel: discord.TextChannel
    ):
        """Set the channel for Pinterest posts"""
        is_interaction = isinstance(ctx, discord.Interaction)
        if is_interaction:
            await ctx.response.defer()
            guild_id = ctx.guild_id
        else:
            guild_id = ctx.guild.id
            await ctx.typing()

        try:
            await self.bot.db.execute(
                """
                INSERT INTO pinterest_config (guild_id, channel_id, is_active)
                VALUES ($1, $2, true)
                ON CONFLICT (guild_id) 
                DO UPDATE SET channel_id = $2, is_active = true
                """,
                guild_id,
                channel.id,
            )

            self.post_channel = channel.id
            response = f"Set Pinterest posting channel to {channel.mention}"
            if is_interaction:
                await ctx.followup.send(response)
            else:
                await ctx.send(response)

        except Exception as e:
            print(f"Error setting channel: {e}")
            error_msg = "An error occurred while setting the channel."
            if is_interaction:
                await ctx.followup.send(error_msg, ephemeral=True)
            else:
                await ctx.send(error_msg)

    @pinterest.group(
        name="posting",
        aliases=["post"],
        description="Base command for Pinterest posting commands.",
        invoke_without_command=True,
    )
    async def posting(self, ctx: Context):
        """Base command for Pinterest posting commands."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @posting.command(name="start", description="Start auto-posting Pinterest images")
    async def start_posting(self, ctx: Union[Context, discord.Interaction]):
        """Start the auto-posting task"""
        is_interaction = isinstance(ctx, discord.Interaction)
        if is_interaction:
            await ctx.response.defer()
            guild_id = ctx.guild_id
        else:
            guild_id = ctx.guild.id
            await ctx.typing()

        try:
            print(f"Starting Pinterest posting for guild {guild_id}")

            await self.bot.db.execute(
                """
                INSERT INTO pinterest_config (guild_id, is_active)
                VALUES ($1, true)
                ON CONFLICT (guild_id) 
                DO UPDATE SET is_active = true
                """,
                guild_id,
            )

            if not hasattr(self, "post_pins") or not self.post_pins.is_running():
                print("Starting Pinterest posting task...")
                self.post_pins.start()
                print("Pinterest posting task started")
            else:
                print("Pinterest posting task is already running")

            print("Pinterest posting started successfully")

            response = "Started auto-posting Pinterest images!"
            if is_interaction:
                await ctx.followup.send(response)
            else:
                await ctx.send(response)

        except Exception as e:
            logger.error(f"Error starting Pinterest posting: {e}", exc_info=True)
            error_msg = f"An error occurred while starting Pinterest posting: {str(e)}"
            if is_interaction:
                await ctx.followup.send(error_msg, ephemeral=True)
            else:
                await ctx.send(error_msg)

    @posting.command(name="stop", description="Stop auto-posting Pinterest images")
    async def stop_posting(self, ctx: Union[Context, discord.Interaction]):
        """Stop the auto-posting task"""
        is_interaction = isinstance(ctx, discord.Interaction)
        if is_interaction:
            await ctx.response.defer()
            guild_id = ctx.guild_id
        else:
            guild_id = ctx.guild.id
            await ctx.typing()

        try:
            await self.bot.db.execute(
                "UPDATE pinterest_config SET is_active = false WHERE guild_id = $1",
                guild_id,
            )

            active_guilds = await self.bot.db.fetch(
                "SELECT COUNT(*) FROM pinterest_config WHERE is_active = true"
            )

            if active_guilds[0]["count"] == 0 and self.post_pins.is_running():
                self.post_pins.cancel()
                print("Stopped Pinterest posting task as no guilds are active")

            response = "Stopped auto-posting Pinterest images."
            if is_interaction:
                await ctx.followup.send(response)
            else:
                await ctx.send(response)

        except Exception as e:
            logger.error(f"Error stopping Pinterest posting: {e}")
            error_msg = f"An error occurred while stopping Pinterest posting: {str(e)}"
            if is_interaction:
                await ctx.followup.send(error_msg, ephemeral=True)
            else:
                await ctx.send(error_msg)

    @pinterest.command(
        name="debug",
        aliases=["dbg"],
        description="Debug information about the Pinterest posting",
    )
    @is_owner()
    async def debug_info(self, ctx: Union[Context, discord.Interaction]):
        """Show debug information about the Pinterest posting"""
        is_interaction = isinstance(ctx, discord.Interaction)
        if is_interaction:
            await ctx.response.defer()
            guild_id = ctx.guild_id
        else:
            guild_id = ctx.guild.id
            await ctx.typing()

        try:
            config = await self.bot.db.fetchrow(
                "SELECT * FROM pinterest_config WHERE guild_id = $1", guild_id
            )

            query_count = await self.bot.db.fetchval(
                "SELECT COUNT(*) FROM pinterest_queries WHERE guild_id = $1", guild_id
            )

            debug_info = [
                f"**Task Running:** {self.is_running}",
                f"**Task Active:** {self.post_pins.is_running() if hasattr(self, 'post_pins') else 'No task'}",
                f"**Next Run:** {self.post_pins.next_iteration if hasattr(self, 'post_pins') and self.post_pins.is_running() else 'N/A'}",
                f"**Guild ID:** {guild_id}",
                "\n**Database Config:**",
            ]

            if config:
                debug_info.extend(
                    [
                        f"- Channel ID: {config.get('channel_id')}",
                        f"- Is Active: {config.get('is_active', False)}",
                    ]
                )
            else:
                debug_info.append("- No config found for this guild")

            debug_info.append(f"\n**Saved Queries:** {query_count}")

            debug_info.extend(
                [
                    "\n**Environment Info:**",
                    f"- Python: {sys.version.split()[0]}",
                    f"- discord.py: {discord.__version__}",
                    f"- Temp Dir: {os.path.abspath('temp/pins') if os.path.exists('temp/pins') else 'Not found'}",
                ]
            )

            embed = discord.Embed(
                title="Pinterest Debug Info",
                description="\n".join(debug_info),
                color=discord.Color(0xFFFFFF),
            )

            if is_interaction:
                await ctx.followup.send(embed=embed)
            else:
                await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in debug command: {e}")
            error_msg = f"An error occurred while getting debug info: {str(e)}"
            if is_interaction:
                await ctx.followup.send(error_msg, ephemeral=True)
            else:
                await ctx.send(error_msg)

    @pinterest.command(name="enable")
    @commands.has_permissions(manage_guild=True)
    async def enable_posting(self, ctx: commands.Context):
        """Enable automatic Pinterest image posting in this server."""
        await self.bot.db.execute(
            """
            INSERT INTO pinterest_config (guild_id, channel_id, is_active)
            VALUES ($1, $2, true)
            ON CONFLICT (guild_id) 
            DO UPDATE SET is_active = true
            """,
            ctx.guild.id,
            ctx.channel.id,
        )
        await ctx.send("Pinterest image posting has been enabled in this channel.")

        if not self.post_pins.is_running():
            self.post_pins.start()

    @pinterest.command(name="disable")
    @has_permissions(manage_guild=True)
    async def disable_posting(self, ctx: commands.Context):
        """Disable automatic Pinterest image posting in this server."""
        await self.bot.db.execute(
            """
            UPDATE pinterest_config 
            SET is_active = false 
            WHERE guild_id = $1
            """,
            ctx.guild.id,
        )
        await ctx.send("Pinterest image posting has been disabled.")

    @pinterest.command(name="status")
    async def posting_status(self, ctx: commands.Context):
        """Show the current status of Pinterest image posting."""
        config = await self.bot.db.fetchrow(
            """
            SELECT channel_id, is_active 
            FROM pinterest_config 
            WHERE guild_id = $1
            """,
            ctx.guild.id,
        )

        if not config or not config["is_active"]:
            return await ctx.send(
                "Pinterest image posting is currently **disabled** in this server."
            )

        channel = self.bot.get_channel(config["channel_id"])
        channel_mention = f"<#{config['channel_id']}>" if channel else "unknown channel"

        query_count = await self.bot.db.fetchval(
            "SELECT COUNT(*) FROM pinterest_queries WHERE guild_id = $1", ctx.guild.id
        )

        status = (
            "Pinterest image posting is enabled\n"
            f"• **Channel:** {channel_mention}\n"
            f"• **Queries configured:** {query_count}\n"
            f"• **Next post:** In about 1 minute"
        )

        await ctx.send(status)
