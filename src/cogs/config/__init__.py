from .configuration import Config
from .modlogs import Modlogs
from .gate import Gate
from vortex import vortex


async def setup(bot: vortex):
    await bot.add_cog(Config(bot))
    await bot.add_cog(Modlogs(bot))
    await bot.add_cog(Gate(bot))
