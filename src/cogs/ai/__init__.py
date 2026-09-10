from .listeners import AIListeners
from .commands import AICommands
from vortex import vortex


async def setup(bot: vortex):
    # print(f"Cog {AIListeners.__name__} disabled. (Not Loaded).")
    await bot.add_cog(AIListeners(bot))
    await bot.add_cog(AICommands(bot))
