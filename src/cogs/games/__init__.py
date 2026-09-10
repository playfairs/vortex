from .games import Games
from vortex import vortex


async def setup(bot: vortex):
    await bot.add_cog(Games(bot))
