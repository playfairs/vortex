from .blacklist import Blacklist
from vortex import vortex


async def setup(bot: vortex):
    await bot.add_cog(Blacklist(bot))
