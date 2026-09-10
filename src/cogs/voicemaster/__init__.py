from .voicemaster import VoiceMaster
from .classes import Join2Create
from vortex import vortex


async def setup(bot: vortex):
    voice_master = VoiceMaster(bot)
    join2create = Join2Create(bot)
    await bot.add_cog(voice_master)
    await bot.add_cog(join2create)
    await voice_master.setup_tables()
