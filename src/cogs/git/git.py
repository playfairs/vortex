import os
import asyncio
import discord
from discord.ext import commands
from discord.ext.commands import Context, group
from typing import Optional

from .pagination import PaginatorView, paginate_text


class Git(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.repository = os.getenv("REPOSITORY")
        self.branch = os.getenv("BRANCH")

    async def cog_check(self, ctx: Context) -> bool:
        if ctx.author.id not in self.bot.owner_ids:
            await ctx.send("This is an owner only command.", ephemeral=True)
            return False
        return True

    async def _run_git_command(self, command: str, ctx: Context, title: str) -> None:
        """Helper method to run git commands with pagination."""
        try:
            process = await asyncio.create_subprocess_shell(
                command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if stderr:
                error_msg = stderr.decode("utf-8")
                if not any(
                    warning in error_msg.lower() for warning in ["warning", "hint"]
                ):
                    return await ctx.send(f"Error: {error_msg}")

                output = f"{error_msg}\n\n{stdout.decode('utf-8')}"
            else:
                output = stdout.decode("utf-8")

            pages = paginate_text(output)

            if len(pages) == 1:
                return await ctx.send(f"```\n{pages[0]}\n```")

            view = PaginatorView(pages=pages, title=title)
            message = await ctx.send(embed=view.get_embed(), view=view)
            view.message = message

        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}")

    @group(name="git", description="Git commands.")
    async def git(self, ctx: Context):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(self.git)

    @git.command(
        name="status",
        description="Shows the working tree status of the git repository.",
    )
    async def git_status(self, ctx: Context):
        """Show the working tree status."""
        await self._run_git_command("git status", ctx, "Git Status")

    @git.command(
        name="push", description="Pushes the git repository to the remote repository."
    )
    async def git_push(self, ctx: Context):
        """Push changes to the remote repository."""
        await self._run_git_command("git push", ctx, "Git Push")

    @git.command(
        name="pull", description="Pulls the git repository from the remote repository."
    )
    async def git_pull(self, ctx: Context):
        """Pull changes from the remote repository."""
        await self._run_git_command("git pull", ctx, "Git Pull")

    @git.command(name="log", description="Shows the commit logs.")
    async def git_log(self, ctx: Context, limit: int = 10):
        """Show commit logs.

        Parameters:
        limit: Number of commits to show (default: 10)
        """
        await self._run_git_command(
            f"git log -n {max(1, min(50, limit))} --oneline",
            ctx,
            f"Git Log (Last {limit} commits)",
        )
