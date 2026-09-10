from .listeners import Listeners
from vortex import vortex


async def setup(bot: vortex):
    await bot.add_cog(Listeners(bot))
