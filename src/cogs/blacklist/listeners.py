import discord
from discord.ext import commands
from discord.ext.commands import (
    Cog,
    Context,
    group,
    has_permissions,
    command,
    hybrid_command as hybrid,
)
from vortex import vortex
from managers.classes import Emojis


class Listeners(Cog, description="View commands in Listeners."):
    def __init__(self, bot: vortex):
        self.bot = bot

    async def _check_blacklist(self, **kwargs) -> bool:
        """Check if any record exists in the blacklist matching the given criteria"""
        conditions = []
        values = []
        for i, (key, value) in enumerate(kwargs.items(), 1):
            if value is not None:
                conditions.append(f"{key} = ${i}")
                values.append(value)

        if not conditions:
            return False

        query = f"SELECT 1 FROM blacklist WHERE {" OR ".join(conditions)} LIMIT 1"
        async with self.bot.db.acquire() as conn:
            return bool(await conn.fetchval(query, *values))

    async def is_blacklisted(
        self,
        user_id: int = None,
        guild_id: int = None,
        channel_id: int = None,
        command_name: str = None,
    ) -> bool:
        """Check if any blacklist conditions match the given criteria"""
        conditions = {}
        if user_id:
            conditions["user_id"] = user_id
        if guild_id:
            conditions["guild_id"] = guild_id
        if channel_id:
            conditions["channel_id"] = channel_id
        if command_name:
            conditions["command_name"] = command_name.lower()

        return await self._check_blacklist(**conditions)

    async def on_message(self, message):
        # Allows for running commands in DMs if not blacklisted.
        if message.author.bot or not message.guild:
            return

        # BLACKLIST CHECKS
        if await self.is_blacklisted(
            user_id=message.author.id,
            guild_id=message.guild.id,
            channel_id=message.channel.id,
        ):
            return

        # COMMAND BLACKLIST CHECK
        ctx = await self.bot.get_context(message)
        if ctx.command:
            if await self.is_blacklisted(
                command_name=ctx.command.qualified_name,
                guild_id=message.guild.id,
                user_id=message.author.id,
                channel_id=message.channel.id,
            ):
                await message.add_reaction(Emojis.no_entry)
                return

        await self.bot.process_commands(message)

    @Cog.listener()
    async def on_guild_join(self, guild):
        """Leave the guild if it's blacklisted"""
        if await self.is_blacklisted(guild_id=guild.id):
            try:
                await guild.leave()
                # Notify owner
                owner = self.bot.get_user(
                    self.bot.owner_id or (await self.bot.application_info()).owner.id
                )
                if owner:
                    await owner.send(
                        f"{Emojis.info} Left blacklisted guild: {guild.name} (ID: {guild.id})"
                    )
            except Exception as e:
                self.bot.logger.error(
                    f"Failed to leave blacklisted guild {guild.id}: {e}"
                )

    @Cog.listener()
    async def on_command_error(self, ctx, error):
        """Handle command errors, particularly for blacklisted commands"""
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                f"{Emojis.info} This command is on cooldown. Try again in {error.retry_after:.1f} seconds.",
                delete_after=5,
            )
        elif isinstance(error, commands.CommandNotFound):
            pass  # Ignore command not found errors
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send(
                f"{Emojis.no_entry} You don't have permission to use this command.",
                delete_after=5,
            )
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send(
                f"{Emojis.no_entry} I don't have the required permissions to execute this command.",
                delete_after=5,
            )
        else:
            self.bot.logger.error(
                f"Error in command '{ctx.command}': {error}", exc_info=error
            )
            await ctx.send(
                f"{Emojis.error} An error occurred while executing that command.",
                delete_after=10,
            )
