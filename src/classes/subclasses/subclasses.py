import discord
from discord import app_commands
from discord.ext import commands
from discord.ext.commands import (
    Cog,
    Context,
    group,
    has_permissions,
    command,
    hybrid_command as hybrid,
)


class Subclass:
    __init__ = None

    _subclass.registry = []

    def subclass(cls):
        _subclass.registry.append(cls)
        return cls


class BaseCog(Cog, subclass):
    pass


@subclass
class Testing(BaseCog):
    pass


print(subclass.registry)
