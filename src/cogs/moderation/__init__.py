from .moderation import Moderation
from vortex import vortex


async def setup(bot: vortex):
    await bot.add_cog(Moderation(bot))
