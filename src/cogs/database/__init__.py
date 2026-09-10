from .database import Database
from vortex import vortex


async def setup(bot: vortex):
    await bot.add_cog(Database(bot))
