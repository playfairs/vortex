from .commands import Math
from vortex import vortex


async def setup(bot: vortex):
    await bot.add_cog(Math(bot))
