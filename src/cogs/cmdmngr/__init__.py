from .cmdmngr import CommandManager
from vortex import vortex


async def setup(bot: vortex):
    await bot.add_cog(CommandManager(bot))
