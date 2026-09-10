import discord
from typing import Set, List, Optional
from managers.classes import Media, Emojis


class BlackTeaEmbeds:
    @staticmethod
    def get_initial_embed(ctx) -> discord.Embed:
        """Create the initial game lobby embed."""
        embed = discord.Embed(
            color=discord.Color(0xFFFFFF),
            title="> BlackTea",
            description=f"⏰ Waiting for players to join. To join react with {Emojis.blacktea}.\nThe game will begin in **20 seconds**",
        )
        embed.add_field(
            name="> Goal",
            value="You have **10 seconds** to say a word containing the given group of **3 letters.**\nIf you don't answer in time, you will lose a life. Each player has **3 lives**",
        )
        embed.set_thumbnail(url=Media.blacktea)
        embed.set_author(name=ctx.author.name, icon_url=ctx.author.display_avatar.url)
        return embed

    @staticmethod
    def get_game_embed(
        player_id: int, strin: str, used_words: Set[str], remaining_lives: int = 3
    ) -> tuple[str, discord.Embed]:
        """Create the game round embed."""
        content = f"<@{player_id}>"
        embed = discord.Embed(
            title=f"Type a word containing **{strin.upper()}** IN THAT FUCKING ORDER, in **10 seconds**",
            description=f"**Used Words:** {', '.join(used_words)}",
            color=discord.Color(0xFFFFFF),
        )
        embed.set_thumbnail(url=Media.blacktea)
        return content, embed

    @staticmethod
    def get_elimination_embed(player_id: int, remaining_lives: int) -> discord.Embed:
        """Create an embed for player elimination or warning."""
        if remaining_lives > 0:
            return discord.Embed(
                description=f"<@{player_id}> didn't reply in time. **{remaining_lives}** lives remaining.",
                color=discord.Color(0xFFFFFF),
            )
        return discord.Embed(
            description=f"<@{player_id}> is out of lives and has been eliminated.",
            color=discord.Color(0xFFFFFF),
        )

    @staticmethod
    async def handle_word_validation(
        message: discord.Message,
        used_words: set,
        target_string: str,
        word_list: list,
        check_emoji: str = Emojis.check,
    ) -> tuple[bool, bool]:
        """
        Handle word validation logic.
        Returns a tuple of (is_valid, should_continue)
        """
        content_lower = message.content.lower()

        if content_lower in used_words:
            await message.reply(
                "That word was already used.",
                delete_after=2,
                mention_author=True,
                allowed_mentions=discord.AllowedMentions(users=True),
            )
            return False, True

        if len(content_lower) <= len(target_string):
            await message.reply(
                f"The word must be longer than {len(target_string)} characters, you pussy ass cheater.",
                delete_after=2,
                mention_author=True,
                allowed_mentions=discord.AllowedMentions(users=True),
            )
            return False, True

        if target_string.lower() in content_lower and content_lower in word_list:
            used_words.add(content_lower)
            await message.add_reaction(check_emoji)
            return True, False

        if target_string.lower() not in content_lower:
            await message.reply(
                f"<@{message.author.id}> That word doesn't contain '{target_string.upper()}', dumbass",
                delete_after=2,
                mention_author=True,
                allowed_mentions=discord.AllowedMentions(users=True),
            )
        return False, False

    @staticmethod
    def get_victory_embed(winner_id: int, remaining_lives: int) -> discord.Embed:
        """Create the victory embed."""
        return discord.Embed(
            description=f"<@{winner_id}> won the game with {remaining_lives} lives remaining!",
            color=discord.Color(0xFFFFFF),
        )
