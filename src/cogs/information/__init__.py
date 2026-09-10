from .information import Information
from .avhistory import AvatarHistory
from vortex import vortex


async def setup(bot: vortex):
    await bot.add_cog(Information(bot))
    await bot.add_cog(AvatarHistory(bot))
