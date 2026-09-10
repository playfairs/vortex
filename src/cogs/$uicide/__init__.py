from .suicide import Suicide
from vortex import vortex


async def setup(bot: vortex):
    await bot.add_cog(Suicide(bot))
