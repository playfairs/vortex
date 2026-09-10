from discord.ext import commands
from discord.ext.commands import Context
import json


class PermissionChecks:
    """Utility class for checking fake permissions."""

    @staticmethod
    async def has_fake_permission(ctx: Context, permission: str) -> bool:
        """Check if a user has a fake permission through any of their roles."""
        if not ctx.guild or not ctx.author or not hasattr(ctx.author, "roles"):
            return False

        if getattr(ctx.author.guild_permissions, permission, False):
            return True

        for role in ctx.author.roles:
            record = await ctx.bot.db.fetchrow(
                "SELECT permissions FROM fake_permissions WHERE role_id = $1", role.id
            )
            if record and permission in json.loads(record["permissions"]):
                return True

        return False


def has_fake_permission(permission: str):
    """Decorator to check for fake permissions."""

    async def predicate(ctx: Context) -> bool:
        return await PermissionChecks.has_fake_permission(ctx, permission)

    return commands.check(predicate)
