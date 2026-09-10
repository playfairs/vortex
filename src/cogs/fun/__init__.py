from .fun import Fun
from vortex import vortex


async def setup(bot: vortex):
    await bot.add_cog(Fun(bot))
