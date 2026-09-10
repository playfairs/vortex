from .music import Music
from vortex import vortex


async def setup(bot: vortex):
    await bot.add_cog(Music(bot))
