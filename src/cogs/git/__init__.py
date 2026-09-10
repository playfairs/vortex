from .git import Git
from vortex import vortex


async def setup(bot):
    await bot.add_cog(Git(vortex))
