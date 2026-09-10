from .automod import Automod
from vortex import vortex


async def setup(bot: vortex):
    await bot.add_cog(Automod(bot))
