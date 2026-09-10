from imports import *

from dotenv import load_dotenv
from os import getenv
from discord.ext.commands import (
    BotMissingPermissions,
    Context,
    CommandError,
    NotOwner,
    CheckFailure,
)
from config import DISCORD

os.environ["JISHAKU_NO_UNDERSCORE"] = "True"
os.environ["JISHAKU_NO_DM_TRACEBACK"] = "True"
postgress = os.getenv("POSTGRES")

load_dotenv(verbose=True)

intents = Intents.all()
intents.messages = True
intents.members = True
intents.presences = False

jishaku.Flags.HIDE = True
jishaku.Flags.RETAIN = True
jishaku.Flags.NO_DM_TRACEBACK = True
jishaku.Flags.NO_UNDERSCORE = True
jishaku.Flags.FORCE_PAGINATOR = True
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

log = logging.getLogger(__name__)


class vortex(commands.AutoShardedBot):

    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            **kwargs,
            command_prefix=DISCORD.PREFIXES,
            help_command=VortexHelp(),
            shard_count=None,
            case_insensitive=True,
            intents=Intents(
                guilds=True,
                members=True,
                messages=True,
                reactions=True,
                # presences=True,
                moderation=True,
                message_content=True,
                emojis_and_stickers=True,
                voice_states=True,
            ),
            allowed_mentions=AllowedMentions(
                everyone=False, users=True, roles=False, replied_user=True
            ),
        )
        self.owner_ids = DISCORD.OWNER_IDS
        self.db = None
        self.skip_cogs = [
            # "cogs.ai",
            "cogs.music",  # The cog works for some things, but it still needs alot more work + the fact it can't run on a server bc of cookies
            "cogs.spotify",
            # "cogs.blacklist",
            # "cogs.voicemaster",
            "cogs.git",
            "cogs.developer",
            "cogs.levels",  # this cog PISSES ME THE FUCK OFF
            "cogs.vanity",
            "cogs.server",
            "cogs.ai",
            "cogs.fakepermissions",  # Don't load this on production for now since im working on it
            # This MIGHT cause issues with other cogs which use fakepermissions, not sure
            # when this works, i plan on making all cogs use fakepermissions or at least commands which can be used with the bot
            # Stuff like ban, kick, moderation commands like such, role stuff is fine too, need to think about what makes sense
            # If your reading this, why are you snooping through the vortex.py?
            "cogs.scrapers",  # This needs some serious work, it is NOT at all ready to be used on production
            # I do plan on fixing it, but since I don't know much about web scraping, and don't know how the pinterest API works, its gonna be weird
            # I plan on using playwright to scrape pinterest, and then using the API to get the images
            # but atp, idk, I might just see if someone wants to work on it
        ]

    def run(self) -> None:
        log.info("Starting Vortex.")
        super().run(os.getenv("TOKEN"), reconnect=True)

    async def load_extensions(self) -> None:
        await self.load_extension("jishaku")
        for feature in Path("cogs").iterdir():
            if feature.is_dir() and (feature / "__init__.py").is_file():
                cog_name = ".".join(feature.parts)
                if cog_name in self.skip_cogs:
                    log.info(f"Skipping disabled cog: {cog_name}")
                    continue

                try:
                    print(f"Loading extension {cog_name}")
                    await self.load_extension(cog_name)
                    print(f"Loaded extension {cog_name}")
                except Exception as exc:
                    log.exception(
                        f"Failed to load extension {feature.name}.", exc_info=exc
                    )

    async def create_db_pool(self):
        self.db = await asyncpg.create_pool(
            host=os.getenv("POSTGRES_HOST"),
            port=int(os.getenv("POSTGRES_PORT") or 5432),
            database=os.getenv("POSTGRES_DB"),
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
            min_size=5,
            max_size=5,
        )

    async def setup_hook(self):
        await self.create_db_pool()
        await self.load_extensions()

    async def on_ready(self):
        print("Meow")

    async def get_prefix(self, message):
        prefixes = list(DISCORD.PREFIXES)
        content = message.content

        if message.guild is not None:
            guild_member_ids = {member.id for member in message.guild.members}
            conflicting_bots = {}
            for i in range(0, len(DISCORD.CONFLICTING_PREFIXES), 2):
                if i + 1 < len(DISCORD.CONFLICTING_PREFIXES):
                    bot_id = DISCORD.CONFLICTING_PREFIXES[i]
                    conflict_prefix = DISCORD.CONFLICTING_PREFIXES[i + 1]
                    conflicting_bots[bot_id] = conflict_prefix

            has_conflicting_bot = any(
                bot_id in guild_member_ids for bot_id in conflicting_bots
            )

            if has_conflicting_bot:
                for bot_id, conflict_prefix in conflicting_bots.items():
                    if bot_id in guild_member_ids and content.startswith(
                        conflict_prefix
                    ):
                        return

                try:
                    prefix = await self.db.fetchval(
                        "SELECT prefix FROM config WHERE guild_id = $1",
                        message.guild.id,
                    )
                    if prefix:
                        prefixes = [prefix]
                except asyncpg.exceptions.UndefinedTableError:
                    pass
            else:
                try:
                    prefix = await self.db.fetchval(
                        "SELECT prefix FROM config WHERE guild_id = $1",
                        message.guild.id,
                    )
                    if prefix:
                        prefixes = [prefix]
                except asyncpg.exceptions.UndefinedTableError:
                    pass

        return commands.when_mentioned_or(*prefixes)(self, message)

    async def process_commands(self, message):
        ctx = await self.get_context(message, cls=Context)
        await self.invoke(ctx)

    async def blacklist(self, user_id):
        """Check if a user is blacklisted by querying the database."""
        if not user_id:
            return False

        try:
            exists = await self.db.fetchval(
                "SELECT 1 FROM blacklisted_users WHERE user_id = $1", user_id
            )
            return exists is not None
        except Exception as e:
            self.logger.error(f"Error checking user blacklist for {user_id}: {e}")
            return False

    async def guild_blacklist(self, guild_id):
        """Check if a guild is blacklisted by querying the database."""
        if not guild_id:
            return False

        try:
            exists = await self.db.fetchval(
                "SELECT 1 FROM blacklisted_guilds WHERE guild_id = $1", guild_id
            )
            return exists is not None
        except Exception as e:
            self.logger.error(f"Error checking guild blacklist for {guild_id}: {e}")
            return False

    async def is_blacklisted(self, user_id, guild_id):
        """Check if either the user or guild is blacklisted."""
        if not user_id and not guild_id:
            return False

        if guild_id and await self.guild_blacklist(guild_id):
            return True

        return user_id is not None and await self.blacklist(user_id)

    async def on_message(self, message):
        if await self.is_blacklisted(
            message.author.id, message.guild.id if message.guild else None
        ):
            return

        await super().on_message(message)

    async def on_guild_join(self, guild):
        if await self.guild_blacklist(guild.id):
            await guild.leave()

    async def on_guild_blacklist(self, guild_id):
        """Handle guild blacklisting by leaving the guild if it's blacklisted."""
        if not guild_id:
            return

        try:
            is_blacklisted = await self.db.fetchval(
                "SELECT 1 FROM blacklisted_guilds WHERE guild_id = $1", guild_id
            )

            if is_blacklisted:
                guild = self.get_guild(guild_id)
                if guild:
                    try:
                        await guild.leave()
                        await self.owner.send(
                            f"Left blacklisted guild: {guild.name} (ID: {guild_id})"
                        )
                    except Exception as e:
                        self.logger.error(
                            f"Failed to leave blacklisted guild {guild_id}: {e}"
                        )

        except Exception as e:
            self.logger.error(f"Error in on_guild_blacklist for guild {guild_id}: {e}")

    member_cooldown = discord.ext.commands.CooldownMapping.from_cooldown(
        3, 5, discord.ext.commands.BucketType.user
    )

    def member_ratelimit(self, message: discord.Message) -> Optional[int]:
        bucket = self.member_cooldown.get_bucket(message)
        return bucket.update_rate_limit()  # type: ignore

    async def on_command(self, ctx) -> None:
        try:
            self.dispatch("usage", ctx)
        except Exception:
            import traceback

            traceback.print_exc()
        finally:
            location = f"{ctx.guild} ({ctx.guild.id})" if ctx.guild else "DMs"

            logger.info(
                f"{ctx.author} ({ctx.author.id}) executed {ctx.command} in {location}"
            )

    async def on_command_error(self, ctx: Context, exception: CommandError) -> None:
        if type(exception) in (NotOwner, CheckFailure):
            return

        elif isinstance(exception, BotMissingPermissions):
            return await ctx.send(
                embed=discord.Embed(
                    description=f"> I'm **missing** permission: `{', '.join(p for p in exception.missing_permissions)}`",  # type: ignore
                    color=discord.Color(0x333333),
                ),
                delete_after=5,
            )

        elif isinstance(exception, commands.CommandNotFound):
            return await ctx.send(
                embed=discord.Embed(
                    description=f"> {ctx.author.mention}, Command **{ctx.invoked_with}** does not exist, run `help` for a list of commands.",
                    color=discord.Color(0x333333),
                ),
                delete_after=5,
            )

        elif isinstance(exception, commands.CommandOnCooldown):
            return await ctx.send(
                embed=discord.Embed(
                    description=f"> {ctx.author.mention}, Command **{ctx.invoked_with}** is on cooldown, try again in {exception.retry_after:.2f} seconds.",
                    color=discord.Color(0x333333),
                ),
                delete_after=5,
            )

        elif isinstance(exception, commands.MissingRequiredArgument) and isinstance(
            exception.param, discord.app_commands.Group
        ):
            return await ctx.send_help(ctx.command)

        elif isinstance(exception, commands.MissingRequiredArgument):
            return await ctx.send(
                embed=discord.Embed(
                    description=f"> {ctx.author.mention}, Missing required argument for command **{ctx.invoked_with}**.",
                    color=discord.Color(0x333333),
                ),
                delete_after=5,
            )

        elif (
            isinstance(exception, NameError)
            and "bot" in str(exception)
            and "jishaku" in "".join(traceback.format_tb(exception.__traceback__))
        ):
            return await ctx.send(
                "Jishaku is being stupid again, just use `_bot` instead of `bot`",
                delete_after=10,
            )

        elif isinstance(exception, commands.MissingPermissions):
            return await ctx.send(
                embed=discord.Embed(
                    description=f"> {ctx.author.mention}, You are **missing** permission: `{', '.join(p for p in exception.missing_permissions)}`",  # type: ignore
                    color=discord.Color(0x333333),
                ),
                delete_after=5,
            )

    def format_number(self, number: int):
        """
        Convert larger numbers into a smaller condensed number.
        """
        if number >= 1000000000:
            return f"{number / 1000000000:.1f}B"
        elif number >= 1000000:
            return f"{number / 1000000:.1f}M"
        elif number >= 1000:
            return f"{number / 1000:.1f}K"
        return str(number)
