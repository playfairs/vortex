from .owner import Owner
from vortex import vortex


async def setup(bot: vortex):
    await bot.add_cog(Owner(bot))
