from .developer import Developer
from vortex import vortex


async def setup(bot: vortex):
    await bot.add_cog(Developer(bot))
