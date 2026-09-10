from .reactions import Reactions
from vortex import vortex


async def setup(bot: vortex):
    await bot.add_cog(Reactions(bot))
