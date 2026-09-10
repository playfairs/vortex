from .lastfm import LastFM
from vortex import vortex


async def setup(bot: vortex):
    await bot.add_cog(LastFM(bot))
