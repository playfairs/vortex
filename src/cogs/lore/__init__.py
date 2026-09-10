from .lore import Lore


async def setup(bot):
    await bot.add_cog(Lore(bot))
