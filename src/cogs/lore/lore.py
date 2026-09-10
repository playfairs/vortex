import random
import discord
from discord.ext import commands
from discord.ext.commands import (
    Cog,
    Context,
    group,
    is_owner,
    hybrid_command as hybrid,
    hybrid_group,
)
from discord import (
    app_commands,
    Member,
    Message,
    Interaction,
    User,
)
from .views import SearchLoreView, LoreLeaderboardView, LoreLayoutView
from .filtered import FILTERED
from vortex import vortex
from typing import Union, Optional


class Lore(Cog, description="View commands in Lore."):
    def __init__(self, bot: vortex):
        self.bot = bot
        bot.loop.create_task(self.initialize_db())
        self.ctx_menu = app_commands.ContextMenu(
            name="Add to Lore",
            callback=self.add_lore_from_message,
            allowed_contexts=app_commands.AppCommandContext(
                guild=True, dm_channel=True, private_channel=True
            ),
            allowed_installs=app_commands.AppInstallationType(guild=True, user=True),
        )
        self.bot.tree.add_command(self.ctx_menu)
        print("Loaded Lore Context Menu Command: Add to Lore")

    async def initialize_db(self):
        async with self.bot.db.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS lore (
                    id BIGINT PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    content TEXT NOT NULL,
                    opted_out BOOLEAN NOT NULL DEFAULT FALSE
                )
            """
            )

            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS lore_opt_out (
                    user_id BIGINT PRIMARY KEY
                )
            """
            )

            await conn.execute(
                """
                ALTER TABLE lore 
                ADD COLUMN IF NOT EXISTS opted_out BOOLEAN DEFAULT FALSE
            """
            )

    async def save_lore(self, message: Message, content):
        """Save a lore entry to the database."""
        async with self.bot.db.acquire() as conn:
            if await conn.fetch("SELECT * FROM lore WHERE id = $1", message.id):
                return False
            await conn.execute(
                """
                INSERT INTO lore (id, user_id, content, opted_out)
                VALUES ($1, $2, $3, $4)
            """,
                message.id,
                message.author.id,
                content,
                False,
            )
            return True

    async def get_lore(self, user_id, include_id=False):
        """Retrieve lore entries for a user from the database."""
        async with self.bot.db.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT content, user_id{'' if not include_id else ", id"} FROM lore WHERE user_id = $1 ORDER BY id DESC
            """,
                user_id,
            )
            return [row for row in rows]

    @hybrid_group(name="lore", invoke_without_command=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.describe(user="The user to view lore for (mention or ID)")
    async def lore(self, ctx, user: Optional[Union[User, str]] = None):
        """
        Shows the lorebook for a user with pagination.
        If no user is mentioned, shows the invoking user's lorebook.
        """
        try:
            if user is None:
                user = ctx.author
            elif isinstance(user, str):
                user_id = user.strip("<@!>")
                if user_id.isdigit():
                    user = await self.bot.fetch_user(int(user_id))
                else:
                    user = await commands.UserConverter().convert(ctx, user)

            if hasattr(user, "guild"):
                user = await self.bot.fetch_user(user.id)

        except (ValueError, discord.NotFound, commands.BadArgument):
            return await ctx.send(
                "Couldn't find that user. Please use a valid user mention or ID.",
                ephemeral=True,
            )

        async with self.bot.db.acquire() as conn:
            opted_out = await conn.fetchval(
                "SELECT 1 FROM lore_opt_out WHERE user_id = $1", user.id
            )

            if opted_out:
                if user.id == ctx.author.id:
                    return await ctx.send(
                        "You have opted out of lore with the tradeoff of not being able to use the lore cog, If you would like to opt back in, please contact support."
                    )
                else:
                    return await ctx.send("This user has opted out of lore.")

        lorebook = await self.get_lore(user.id)

        if user.id == 570020287735660547 and ctx.author.id == 570020287735660547:
            await ctx.send("You don't have any lore, you're immune.")
            return
        else:
            if user.id == 570020287735660547:
                await ctx.send("This user doesn't have any lore, they're immune.")
                return
        if user.id == ctx.author.id:
            if not lorebook:
                await ctx.send(
                    f"You don't have any lore, add some by replying to a message with ,lore add or addlore."
                )
                return
        else:
            if not lorebook:
                await ctx.send(
                    f"{user.mention} doesn't have any lore, add some by replying to a message with ,lore add or addlore."
                )
                return

        view = LoreLayoutView(lorebook, user, ctx)
        await ctx.send(view=view, allowed_mentions=discord.AllowedMentions.none())

    @lore.command(
        name="view", description="Views a users lore, or your own if none mentioned."
    )
    @app_commands.describe(user="The user to view lore for.")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def view_lore(self, ctx: Context, user: Optional[User] = None):
        """
        Views a users lore, or your own if none mentioned.
        """
        await ctx.invoke(self.lore, user=user or ctx.author)

    @lore.command(
        name="add",
        description="Adds a message to the lorebook of the user who sent the referenced message.",
    )
    @app_commands.describe(
        message="The message to add to the lorebook (reply to a message or provide message ID)"
    )
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def add_lore(self, ctx: Context, message: Optional[str] = None):
        """
        Adds a message to the lorebook of the user who sent the referenced message.
        Must be used by replying to a message or providing a message ID.
        """
        if ctx.author.bot:
            return await ctx.send("Stop cheating your way with Jishaku exec.")

        if not message and not ctx.message.reference:
            return await ctx.send(
                "Please reply to a message or provide a message ID to add lore."
            )

        async with self.bot.db.acquire() as conn:
            command_user_opted_out = await conn.fetchval(
                "SELECT 1 FROM lore_opt_out WHERE user_id = $1", ctx.author.id
            )
            if command_user_opted_out:
                return await ctx.send(
                    "You have opted out of lore and cannot add new lore entries."
                )

        try:
            if ctx.message.reference:
                referenced_message = await ctx.channel.fetch_message(
                    ctx.message.reference.message_id
                )
            else:
                if not message.isdigit():
                    return await ctx.send(
                        "Please provide a valid message ID or reply to a message."
                    )
                referenced_message = await ctx.channel.fetch_message(int(message))

            target_user = referenced_message.author

            if ctx.author.id == target_user.id:
                return await ctx.send(
                    "You cannot add lore to your own messages. Please reply to someone else's message."
                )
            if target_user.bot:
                return await ctx.send("You cannot add lore to bot messages.")

            async with self.bot.db.acquire() as conn:
                target_opted_out = await conn.fetchval(
                    "SELECT 1 FROM lore_opt_out WHERE user_id = $1", target_user.id
                )
                if target_opted_out:
                    return await ctx.send(
                        f"{target_user.mention} has opted out of lore and cannot have new lore added about them."
                    )

            content = referenced_message.content

            if target_user.id == 570020287735660547:
                return await ctx.send("This user has lore immunity.")

            if target_user.id == 1347441071323480074:
                await ctx.message.reply("Added lore for.. m-m-myself..??")
                return await self.save_lore(referenced_message, content)

            content_lower = f" {content.lower()} "
            for word in FILTERED.Blacklisted_Words:
                word_lower = f" {word.lower()} "
                if word_lower in content_lower and word_lower not in [
                    f" {w.lower()} " for w in FILTERED.Whitelisted_Words
                ]:
                    return await ctx.send(
                        "This message contains flagged content and cannot be added to lore."
                    )

            lore_added = await self.save_lore(referenced_message, content)
            if not lore_added:
                return await ctx.send("Lore has already been added for this message.")

            await ctx.send(f"Added lore for {target_user.mention}.")

        except discord.NotFound:
            await ctx.send("Could not find the referenced message.")
        except discord.Forbidden:
            await ctx.send("I don't have permission to read that message.")
        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}")

    async def add_lore_from_message(self, interaction: Interaction, message: Message):
        """Add a message to your lorebook."""
        if message.author.id == 570020287735660547:
            await interaction.response.send_message(
                "This user has lore immunity.", ephemeral=False
            )
            return

        if message.author.bot:
            return await interaction.response.send_message(
                "You cannot add lore to bot messages.", ephemeral=False
            )

        async with self.bot.db.acquire() as conn:
            opted_out = await conn.fetchval(
                "SELECT 1 FROM lore_opt_out WHERE user_id = $1", interaction.user.id
            )
            if opted_out:
                return await interaction.response.send_message(
                    "You have opted out of lore.", ephemeral=True
                )

            opted_out = await conn.fetchval(
                "SELECT 1 FROM lore_opt_out WHERE user_id = $1", message.author.id
            )
            if opted_out:
                return await interaction.response.send_message(
                    "This user has opted out of lore.", ephemeral=True
                )

        for word in FILTERED.Blacklisted_Words:
            if f" {word.lower()} " in f" {message.content.lower()} ":
                if f" {word.lower()} " in [
                    f" {whitelist_word.lower()} "
                    for whitelist_word in FILTERED.Whitelisted_Words
                ]:
                    continue
                else:
                    await interaction.response.send_message(
                        "This message contains flagged content and cannot be added to lore.",
                        ephemeral=True,
                    )
                    return

        if not message.content and not message.attachments:
            await interaction.response.send_message(
                "This message has no content to add to lore.", ephemeral=True
            )
            return

        if interaction.user.id == message.author.id:
            await interaction.response.send_message(
                "😭 when no one else does it so they gotta do it themself",
                ephemeral=False,
            )
            return

        if interaction.guild is None:
            try:
                content = message.content
                if message.attachments:
                    attachments = "\n".join(
                        f"[Attachment: {a.filename}]" for a in message.attachments
                    )
                    content = f"{content}\n{attachments}" if content else attachments

                saved = await self.save_lore(message, content)
                if not saved:
                    await interaction.response.send_message(
                        "Lore has already been added for this message.", ephemeral=True
                    )
                    return

                await interaction.response.send_message(
                    f"Added lore for {message.author.mention} from DMs.",
                    ephemeral=False,
                )
                return
            except Exception:
                await interaction.response.send_message(
                    "An error occurred while processing this message.", ephemeral=True
                )
                return

        content = message.content
        if message.attachments:
            attachments = "\n".join(
                f"[Attachment: {a.filename}]" for a in message.attachments
            )
            content = f"{content}\n{attachments}" if content else attachments

        saved = await self.save_lore(message, content)
        if not saved:
            await interaction.response.send_message(
                "Lore has already been added for this message.", ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"Added lore for {message.author.mention}.", ephemeral=False
        )

    @lore.command(name="remove")
    @app_commands.describe(
        entry_number="The entry number to remove.",
        user="The user to remove the entry from. Optional.",
    )
    @is_owner()
    async def remove_lore(self, ctx: Context, entry_number: int, user: Member = None):
        """
        Removes a specific lore entry by its number.
        """
        if user is None:
            user = ctx.author

        lorebook = await self.get_lore(user.id, include_id=True)

        if entry_number < 1 or entry_number > len(lorebook):
            await ctx.send(
                f"Invalid entry number. Please choose a number between 1 and {len(lorebook)}."
            )
            return

        async with self.bot.db.acquire() as conn:
            await conn.execute(
                "DELETE FROM lore WHERE id = $1", lorebook[entry_number - 1]["id"]
            )

        await ctx.send(f"Removed entry {entry_number} from {user.mention}'s lorebook.")

    @lore.command(name="reset")
    @is_owner()
    async def reset_lore(self, ctx: Context, user: Member = None):
        """
        Resets a user's entire lorebook.
        """
        if user is None:
            user = ctx.author

        async with self.bot.db.acquire() as conn:
            await conn.execute("DELETE FROM lore WHERE user_id = $1", user.id)

        await ctx.send(f"Reset {user.mention}'s lorebook.")

    @lore.command(name="show")
    @app_commands.describe(
        entry_number="The entry number to show.",
        user="The user to show the entry from. Optional.",
    )
    async def show_lore(self, ctx: Context, entry_number: int, user: Member = None):
        """
        Shows a specific lore entry for a user.
        If no user is mentioned, uses the command invoker.
        If entry number is out of range, shows a random entry.
        """
        if user is None:
            user = ctx.author

        lorebook = await self.get_lore(user.id)

        if not lorebook:
            await ctx.send(f"Congrats {user.mention}, you haven't been clipped.. yet..")
            return

        if entry_number < 1 or entry_number > len(lorebook):
            entry_number = random.randint(1, len(lorebook))
            await ctx.send(f"Invalid entry number. Showing a random entry instead!")

        entry = lorebook[entry_number - 1]

        embed = discord.Embed(
            title=f"{user.display_name}'s Lore - Entry {entry_number}",
            description=entry.get("content", "No content"),
            color=0xFFFFFF,
        )

        await ctx.send(embed=embed)

    @lore.command(name="leaderboard", aliases=["lb", "top"])
    async def lore_leaderboard(self, ctx):
        """
        Shows the top 10 users with the most lore entries.
        """
        async with self.bot.db.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT user_id, COUNT(*) as lore_count
                FROM lore
                GROUP BY user_id
                ORDER BY lore_count DESC
            """
            )
        if not rows:
            return await ctx.send("No lore entries found.")

        view = LoreLeaderboardView(ctx, [dict(row) for row in rows], self.bot)
        await ctx.send(view=view)

    @lore.command(name="search", help="Search for lore entries containing a keyword")
    @app_commands.describe(
        query="The keyword to search for.",
        user="The user to search only their lorebook. Optional.",
    )
    async def search_lore(
        self, ctx: Context, *, query: str = None, user: Member = None
    ):
        """
        Search for lore entries containing a specific keyword.
        """
        if not query:
            await ctx.send("Please provide a keyword to search for.")
            return

        if user is None:
            user = ctx.author

        parts = query.split()

        if len(parts) > 1 and parts[-1].startswith("<@") and parts[-1].endswith(">"):
            try:
                query = " ".join(parts[:-1])
                user = await commands.MemberConverter().convert(ctx, parts[-1])
            except commands.MemberNotFound:
                query = " ".join(parts)

        lorebook = await self.get_lore(user.id)
        query = query.lower()

        matching_entries = [
            (index + 1, entry)
            for index, entry in enumerate(lorebook)
            if query in entry.get("content", "").lower()
        ]

        if not matching_entries:
            await ctx.send(
                f"No lore entries found containing '{query}' for {user.display_name}."
            )
            return

        view = SearchLoreView(ctx, matching_entries, user, query)
        await ctx.send(embed=view.get_embed(), view=view)

        if user is None:
            user = ctx.author

        parts = query.split()

        if len(parts) > 1 and parts[-1].startswith("<@") and parts[-1].endswith(">"):
            try:
                query = " ".join(parts[:-1])
                user = await commands.MemberConverter().convert(ctx, parts[-1])
            except commands.MemberNotFound:
                query = " ".join(parts)

        lorebook = await self.get_lore(user.id)
        query = query.lower()

        matching_entries = [
            (index + 1, entry)
            for index, entry in enumerate(lorebook)
            if query in entry.get("content", "").lower()
        ]

        if not matching_entries:
            await ctx.send(
                f"No lore entries found containing '{query}' for {user.display_name}."
            )
            return

        view = SearchLoreView(ctx, matching_entries, user, query)
        await ctx.send(embed=view.get_embed(), view=view)

    class ConfirmOptOutView(discord.ui.View):
        def __init__(self, ctx, message=None):
            super().__init__(timeout=60.0)
            self.ctx = ctx
            self.message = message
            self.value = None
            self.interaction = None

        async def interaction_check(self, interaction: discord.Interaction) -> bool:
            if interaction.user.id != self.ctx.author.id:
                await interaction.response.send_message(
                    "This confirmation dialog is not for you!", ephemeral=True
                )
                return False
            return True

        @discord.ui.button(label="Confirm", style=discord.ButtonStyle.red)
        async def confirm(
            self, interaction: discord.Interaction, button: discord.ui.Button
        ):
            self.value = True
            self.interaction = interaction
            self.stop()
            await self.disable_buttons()
            await interaction.response.edit_message(
                content="Processing your request...", embed=None, view=self
            )

        @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey)
        async def cancel(
            self, interaction: discord.Interaction, button: discord.ui.Button
        ):
            self.value = False
            self.interaction = interaction
            self.stop()
            await self.disable_buttons()
            await interaction.response.edit_message(
                content="Operation cancelled.", embed=None, view=self
            )

        async def disable_buttons(self):
            for item in self.children:
                if isinstance(item, discord.ui.Button):
                    item.disabled = True

        async def on_timeout(self):
            await self.disable_buttons()
            if self.message:
                try:
                    await self.message.edit(view=self)
                except:
                    pass

    @lore.command(name="opt-out", aliases=["optout"])
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def opt_out(self, ctx: Context):
        """Opt-out of having your lorebook visible to others."""
        user = ctx.author

        async with self.bot.db.acquire() as conn:
            already_opted_out = await conn.fetchval(
                "SELECT 1 FROM lore_opt_out WHERE user_id = $1", user.id
            )

            if already_opted_out:
                return await ctx.send("You're already opted out of lore tracking.")

            has_lore = await conn.fetchval(
                "SELECT 1 FROM lore WHERE user_id = $1 LIMIT 1", user.id
            )

            message = None

            if has_lore:
                confirm_view = self.ConfirmOptOutView(ctx)
                embed = discord.Embed(
                    title="Opt-out of Lore",
                    description=(
                        "**Warning: This action cannot be undone!**\n\n"
                        "Opting out will:\n"
                        "• Remove all your existing lore entries\n"
                        "• Prevent new lore from being added about you\n"
                        "• Revoke your access to adding lore to anyone.\n\n"
                        "Are you sure you want to proceed?"
                    ),
                    color=discord.Color(0xFFFFFF),
                )

                message = await ctx.send(embed=embed, view=confirm_view)
                confirm_view.message = message

                await confirm_view.wait()

                if confirm_view.value is None:
                    return await message.edit(
                        content="Timed out. Operation cancelled.", embed=None, view=None
                    )
                elif not confirm_view.value:
                    return await message.edit(
                        content="Operation cancelled.", embed=None, view=None
                    )

                await conn.execute("DELETE FROM lore WHERE user_id = $1", user.id)

            await conn.execute(
                """
                INSERT INTO lore_opt_out (user_id)
                VALUES ($1)
                ON CONFLICT (user_id) DO NOTHING
            """,
                user.id,
            )

            await conn.execute(
                "UPDATE lore SET opted_out = TRUE WHERE user_id = $1", user.id
            )

            if message:
                await message.edit(
                    content="You have been opted out of lore tracking. Your existing lore has been removed.",
                    embed=None,
                    view=None,
                )
            else:
                await ctx.send("You have been opted out of lore tracking.")

    @is_owner()
    @lore.command(name="opt-in", aliases=["optin"])
    @app_commands.describe(user="The user to opt-in to lore tracking.")
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.allowed_installs(guilds=True, users=True)
    async def opt_in(self, ctx: Context, user: Member = None):
        """Opt-in to having your lorebook visible to others."""
        user = user or ctx.author

        async with self.bot.db.acquire() as conn:
            already_opted_in = await conn.fetchval(
                "SELECT 1 FROM lore_opt_out WHERE user_id = $1", user.id
            )

            if not already_opted_in:
                return await ctx.send("You're already opted in to lore tracking.")

            await conn.execute("DELETE FROM lore_opt_out WHERE user_id = $1", user.id)
            await conn.execute(
                "UPDATE lore SET opted_out = FALSE WHERE user_id = $1", user.id
            )

            await ctx.send(f"{user.mention} has been opted in to lore tracking.")
