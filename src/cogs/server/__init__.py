from .server import Server
from vortex import vortex


async def setup(bot: vortex):
    await bot.add_cog(Server(bot))
