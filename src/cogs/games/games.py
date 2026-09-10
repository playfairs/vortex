import discord
import random
from discord import ui
from discord.ext import commands
from typing import Optional

from managers.classes import Emojis
import os


class HangmanLetterSelect(ui.Select):
    def __init__(self, guessed, word):
        self.guessed = guessed
        self.word = word

        options = [
            discord.SelectOption(
                label=chr(i),
                value=chr(i),
                emoji=(
                    Emojis.check
                    if chr(i) in word and chr(i) in guessed
                    else (Emojis.cancel if chr(i) in guessed else None)
                ),
            )
            for i in range(65, 91)
            if chr(i) not in guessed
        ]

        super().__init__(
            placeholder="Select a letter...",
            min_values=1,
            max_values=1,
            options=options[:25],
        )

    async def callback(self, interaction: discord.Interaction):
        await self.view.process_guess(interaction, self.values[0])


class HangmanView(ui.View):
    def __init__(self, word, lives=6):
        super().__init__(timeout=300)
        self.word = word.upper()
        self.guessed = set()
        self.lives = lives
        self.game_over = False
        self.update_letter_select()

    def display_word(self):
        return " ".join(
            [letter if letter in self.guessed else "⬜" for letter in self.word]
        )

    def update_letter_select(self):
        self.clear_items()
        if not self.game_over and any(
            letter not in self.guessed for letter in self.word
        ):
            self.add_item(HangmanLetterSelect(self.guessed, self.word))

    async def process_guess(self, interaction: discord.Interaction, letter: str):
        """Process a letter guess from the select menu."""
        if self.game_over:
            return await interaction.response.defer()

        letter = letter.upper()
        self.guessed.add(letter)

        if letter not in self.word:
            self.lives -= 1

        if all(l in self.guessed for l in self.word):
            self.game_over = True
            await self.update_game_state(interaction, self.get_win_message())
        elif self.lives <= 0:
            self.game_over = True
            await self.update_game_state(interaction, self.get_lose_message())
        else:
            await self.update_game_state(interaction, self.get_status())

    async def update_game_state(self, interaction: discord.Interaction, content: str):
        """Update the game message with the current state."""
        self.update_letter_select()
        embed = discord.Embed(
            title="Hangman Game", description=content, color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=self)

    def get_status(self):
        return (
            f"{self.get_hangman_art()}\n"
            f"🔠 **{self.display_word()}**\n"
            f"❤️ **Lives:** {self.lives}\n"
            f"🚫 **Missed:** {', '.join(sorted(self.guessed - set(self.word))) or 'None'}"
        )

    def get_hangman_art(self):
        stages = [
            """
              +---+
              |   |
                  |
                  |
                  |
                  |
            =========
        """,
            """
              +---+
              |   |
              O   |
                  |
                  |
                  |
            =========
        """,
            """
              +---+
              |   |
              O   |
              |   |
                  |
                  |
            =========
        """,
            """
              +---+
              |   |
              O   |
             /|   |
                  |
                  |
            =========
        """,
            """
              +---+
              |   |
              O   |
             /|\  |
                  |
                  |
            =========
        """,
            """
              +---+
              |   |
              O   |
             /|\  |
             /    |
                  |
            =========
        """,
            """
              +---+
              |   |
              O   |
             /|\  |
             / \  |
                  |
            =========
        """,
        ]
        return f"```{stages[6 - self.lives]}```"

    def get_win_message(self):
        return (
            f"**VICTORY!**\n"
            f"Word: ||{self.word}||\n"
            f"Lives left: {self.lives}\n"
            f"{self.get_hangman_art()}"
        )

    def get_lose_message(self):
        return (
            f"**GAME OVER**\n"
            f"Word: ||{self.word}||\n"
            f"Missed letters: {', '.join(sorted(self.guessed - set(self.word)))}\n"
            f"{self.get_hangman_art()}"
        )


class ConfirmView(ui.View):
    def __init__(self, challenger: discord.Member, opponent: discord.Member):
        super().__init__(timeout=30)
        self.challenger = challenger
        self.opponent = opponent
        self.confirmed = False

    @ui.button(label="", style=discord.ButtonStyle.green, emoji=Emojis.check)
    async def accept(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.opponent.id:
            return await interaction.response.send_message(
                "Only the challenged player can accept!", ephemeral=True
            )
        self.confirmed = True
        self.stop()
        await interaction.response.edit_message(
            content=f"{self.opponent.mention} accepted the challenge!", view=None
        )

    @ui.button(label="", style=discord.ButtonStyle.red, emoji=Emojis.cancel)
    async def decline(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.opponent.id:
            return await interaction.response.send_message(
                "Only the challenged player can decline!", ephemeral=True
            )
        self.stop()
        await interaction.response.edit_message(
            content=f"{self.opponent.mention} declined the challenge.", view=None
        )

    async def on_timeout(self):
        if not self.confirmed:
            await self.message.edit(content="Challenge timed out.", view=None)


class TicTacToeButton(ui.Button):
    def __init__(self, x: int, y: int):
        super().__init__(style=discord.ButtonStyle.secondary, label="\u200b", row=y)
        self.x = x
        self.y = y

    async def callback(self, interaction: discord.Interaction):
        view: TicTacToeView = self.view
        if interaction.user.id != view.current_player.id:
            return await interaction.response.send_message(
                "Not your turn!", ephemeral=True
            )
        if view.board[self.y][self.x] != 0 or view.game_over:
            return await interaction.response.defer()

        view.board[self.y][self.x] = view.current_symbol
        self.style = discord.ButtonStyle.primary
        self.label = "X" if view.current_symbol == 1 else "O"
        self.disabled = True

        winner = view.check_winner()
        if winner:
            view.game_over = True
            if winner == 3:
                content = "**Game Over!** It's a tie!"
            else:
                winner_user = view.player1 if winner == 1 else view.player2
                content = f"🎉 **{winner_user.display_name}** wins!"
            for child in view.children:
                child.disabled = True
        else:
            view.current_player = (
                view.player2 if view.current_player == view.player1 else view.player1
            )
            view.current_symbol = 2 if view.current_symbol == 1 else 1
            content = f"**{view.current_player.display_name}'s** turn ({'X' if view.current_symbol == 1 else 'O'})"

        await interaction.response.edit_message(content=content, view=view)


class TicTacToeView(ui.View):
    def __init__(self, player1: discord.Member, player2: discord.Member):
        super().__init__(timeout=60)
        self.player1 = player1
        self.player2 = player2
        self.current_player = player1
        self.current_symbol = 1
        self.board = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
        self.game_over = False

        for y in range(3):
            for x in range(3):
                self.add_item(TicTacToeButton(x, y))

    def check_winner(self):
        for row in self.board:
            if row[0] == row[1] == row[2] != 0:
                return row[0]
        for col in range(3):
            if self.board[0][col] == self.board[1][col] == self.board[2][col] != 0:
                return self.board[0][col]
        if self.board[0][0] == self.board[1][1] == self.board[2][2] != 0:
            return self.board[0][0]
        if self.board[0][2] == self.board[1][1] == self.board[2][0] != 0:
            return self.board[0][2]
        if all(cell != 0 for row in self.board for cell in row):
            return 3
        return 0


class Games(commands.Cog, description="Play games with our people."):
    def __init__(self, bot):
        self.bot = bot
        self.words = self.load_words()
        os.makedirs("data", exist_ok=True)

    def load_words(self):
        """Load words from a file or use default words if file doesn't exist."""
        word_file = os.path.join("data", "words.txt")
        default_words = [
            "python",
            "javascript",
            "programming",
            "computer",
            "keyboard",
            "monitor",
            "internet",
            "browser",
            "gaming",
            "developer",
            "discord",
            "hangman",
            "challenge",
            "difficult",
            "example",
        ]

        try:
            if os.path.exists(word_file):
                with open(word_file, "r") as f:
                    words = [
                        word.strip().lower() for word in f.readlines() if word.strip()
                    ]
                if words:
                    return words
            with open(word_file, "w") as f:
                f.write("\n".join(default_words))
            return default_words
        except Exception as e:
            print(f"Error loading words: {e}")
            return default_words

    def randomWord(self):
        """Get a random word from the words list."""
        if not self.words:
            self.words = self.load_words()
            if not self.words:
                return "hangman"

        return random.choice(self.words)

    @commands.command(name="hangman", aliases=["hm"])
    async def start_hangman(self, ctx):
        """Start a solo Hangman game"""
        if not self.words:
            return await ctx.send("No words available in words.txt!\n")
        word = self.randomWord()
        view = HangmanView(word)

        embed = discord.Embed(
            title="Hangman Game",
            description=(
                f"Guess the word!\n"
                f"{view.display_word()}\n\n"
                f"{view.get_hangman_art()}\n"
                f"**Lives:** ❤️ × {view.lives}"
            ),
            color=discord.Color.blue(),
        )

        await ctx.send(embed=embed, view=view)

    @commands.command(name="ttt", aliases=["tictactoe"])
    async def tictactoe(self, ctx, opponent: Optional[discord.Member] = None):
        """Challenge someone to Tic-Tac-Toe! Usage: `!ttt @user`"""
        if opponent and opponent.bot:
            return await ctx.send("You can't play against bots!")
        if opponent and opponent == ctx.author:
            return await ctx.send("You can't play against yourself!")

        if not opponent:
            candidates = [
                m
                for m in ctx.guild.members
                if not m.bot and m.status != discord.Status.offline and m != ctx.author
            ]
            if not candidates:
                return await ctx.send("No available players found!")
            opponent = random.choice(candidates)

        confirm_view = ConfirmView(ctx.author, opponent)
        confirm_msg = await ctx.send(
            f"{opponent.mention}, {ctx.author.mention} challenges you to Tic-Tac-Toe!",
            view=confirm_view,
        )
        confirm_view.message = confirm_msg
        await confirm_view.wait()

        if confirm_view.confirmed:
            await ctx.send(
                f"**Tic-Tac-Toe**\n"
                f"{ctx.author.mention} (X) vs {opponent.mention} (O)\n"
                f"{ctx.author.display_name} goes first!",
                view=TicTacToeView(ctx.author, opponent),
            )
