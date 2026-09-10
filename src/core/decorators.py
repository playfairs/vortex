from discord.ext import commands
from discord.ext.commands import Context
import functools
import logging


class Decorators:
    def __init__(self, bot=None):
        self.bot = bot
        self._logger = logging.getLogger(__name__)

    @property
    def restricted(self):
        """Property to check if the command is restricted to the bot owner."""
        if not self.bot:
            self._logger.warning("Bot instance not set in Decorators")
            return lambda func: func

        return commands.checks.has_any_role(*self.bot.owner_ids)

    def invocation(self, restrict_to_owner: bool = False):
        """Decorator to restrict command usage to the bot owner."""

        def decorator(func):
            @functools.wraps(func)
            async def wrapper(self_instance, ctx: Context, *args, **kwargs):
                if (
                    restrict_to_owner
                    and ctx.author.id != self_instance.bot.owner_ids[0]
                ):
                    return await ctx.send(
                        "This command can only be used by the bot owner."
                    )
                return await func(self_instance, ctx, *args, **kwargs)

            return wrapper

        return decorator
