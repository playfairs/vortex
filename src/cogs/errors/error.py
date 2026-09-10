from discord.ext import commands
import uuid
import discord
from .views import ErrorView


class ErrorHandler(commands.Cog, description="View commands in ErrorHandler."):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.bot.loop.create_task(self.create_database())

    async def create_database(self):
        async with self.bot.db.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS errors (
                    id TEXT PRIMARY KEY,
                    command TEXT NOT NULL,
                    error TEXT NOT NULL,
                    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    type TEXT NOT NULL
                )
            """
            )

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(
            error,
            (
                commands.CommandNotFound,
                commands.CommandOnCooldown,
                commands.MissingRequiredArgument,
                commands.TooManyArguments,
                commands.BadArgument,
                commands.NotOwner,
                commands.CheckFailure,
                discord.Forbidden,
            ),
        ):
            # Ignore common errors that don't need logging
            return
        if isinstance(error, commands.MissingPermissions):
            return await ctx.send(
                embed=discord.Embed(
                    description=f"aye man, you need `{', '.join(error.missing_permissions).capitalize()}` for this shi 😭✌️",
                    color=0xF8C9FF,
                )
            )
        if isinstance(error, commands.BotMissingPermissions):
            return await ctx.send(
                f":warning:  I am missing the following permissions to execute this command"
            )

        if hasattr(ctx, "interaction") and ctx.interaction is not None:
            invoked_with = "Slash"
        else:
            invoked_with = "Prefixed"

        error_id = str(uuid.uuid4())[:5]

        async def _is_existing_error(error_id):
            async with self.bot.db.acquire() as conn:
                result = await conn.fetchrow(
                    "SELECT id FROM errors WHERE id = $1", error_id
                )
                return result is not None

        error_string = (
            f"**Type:** {type(error).__module__}.{type(error).__name__}\n{error}"
        )
        command_name = f'{ctx.command.name}.{ctx.command.parent.name if ctx.command.parent else ""}'
        while await _is_existing_error(error_id):
            error_id = str(uuid.uuid4())[:5]

        async with self.bot.db.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO errors (id, command, error, type)
                VALUES ($1, $2, $3, $4)
            """,
                error_id,
                command_name,
                error_string,
                invoked_with,
            )

        embed = discord.Embed(
            description=f":warning:  An error occurred while executing the command `{command_name}`. \nPlease report this to the bot support server with the error ID: `{error_id}`.",
            color=discord.Color.red(),
        )
        try:
            if ctx.interaction and ctx.interaction.response.is_done():
                await ctx.send(embed=embed, ephemeral=True)
            else:
                await ctx.send(embed=embed, ephemeral=True)
        except (discord.NotFound, discord.HTTPException) as e:
            if isinstance(e, discord.NotFound) and e.code == 10062:
                try:
                    await ctx.channel.send(embed=embed)
                except:
                    pass

    @commands.is_owner()
    @commands.hybrid_command(name="errors", aliases=["errorsearch", "tb", "traceback"])
    async def error_search(self, ctx, id: str = None):
        """Search errors by ID. Requires bot owner permissions."""

        class ErrorLog:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

        async with self.bot.db.acquire() as conn:
            if id:
                result = await conn.fetchrow(
                    """
                    SELECT * FROM errors WHERE id = $1
                """,
                    id,
                )
                if result:
                    error_log = ErrorLog(**result)
                    embed = discord.Embed(
                        title=f"Error ID: {error_log.id}", color=discord.Color.red()
                    )
                    embed.add_field(
                        name="Command", value=f"Faulty command is `{error_log.command}`"
                    )
                    embed.add_field(
                        name="Type",
                        value=f"Command invoked via a {error_log.type} command.",
                    )
                    embed.add_field(
                        name="Error", value=f"{error_log.error}", inline=False
                    )
                    embed.add_field(
                        name="Timestamp",
                        value=error_log.timestamp.strftime("%Y-%m-%d %H:%M:%S%z"),
                    )
                    view = ErrorView(self.bot.db, id=error_log.id, ctx=ctx)
                    await ctx.send(embed=embed, view=view)
                else:
                    await ctx.send("No error found with that ID.")
            else:
                result = await conn.fetchrow(
                    """
                    SELECT * FROM errors ORDER BY timestamp DESC LIMIT 1
                """
                )
                if result:
                    error_log = ErrorLog(**result)
                    embed = discord.Embed(
                        title=f"Most recent error ID: {error_log.id}",
                        color=discord.Color.red(),
                    )
                    embed.add_field(
                        name="Command", value=f"Faulty command is `{error_log.command}`"
                    )
                    embed.add_field(
                        name="Type",
                        value=f"Command invoked via a {error_log.type} command.",
                    )
                    embed.add_field(
                        name="Error", value=f"{error_log.error}", inline=False
                    )
                    embed.add_field(
                        name="Timestamp",
                        value=error_log.timestamp.strftime("%Y-%m-%d %H:%M:%S%z"),
                    )
                    view = ErrorView(self.bot.db, id=error_log.id, ctx=ctx)
                    await ctx.send(embed=embed, view=view)
                else:
                    await ctx.send("No errors have been logged.")
