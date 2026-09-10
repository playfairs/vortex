from .error import ErrorHandler


async def setup(bot):
    await bot.add_cog(ErrorHandler(bot))
