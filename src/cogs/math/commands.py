import discord, math, operator, re, aiohttp, numpy as np, sympy
from sympy import sympify, solve, Symbol, Eq, sqrt
from sympy.parsing.sympy_parser import parse_expr
from discord.ext import commands
from discord.ext.commands import (
    Cog,
    Context,
    command,
    BucketType,
    cooldown,
    has_permissions,
    hybrid_command as hybrid,
    hybrid_group,
)
from discord import app_commands, Guild, User
from typing import Union, Optional, Dict, List, Tuple
from vortex import vortex


class Math(Cog, description="View commands in Math."):
    def __init__(self, bot: vortex):
        self.bot = bot

    @hybrid_group(name="math", description="View commands in Math.")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def math(self, ctx: Context):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(self.math)

    @math.command(name="calc", description="Calculate a mathematical expression")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(expression="The mathematical expression to evaluate.")
    async def calc(self, ctx: Context, *, expression: str):
        """Calculate a mathematical expression with basic operations (+, -, *, /, ^, **)"""
        try:
            expr = expression.strip().replace("^", "**")

            result = sympify(expr, evaluate=True)

            if result.is_number:
                result_str = (
                    f"{float(result):,}" if "." in str(result) else f"{int(result):,}"
                )
            else:
                result_str = str(result)

            display_expr = expression.replace("**", "^")

            container = discord.ui.Container()
            container.add_item(discord.ui.TextDisplay(content="### Calculator"))
            container.add_item(
                discord.ui.Separator(
                    visible=True, spacing=discord.SeparatorSpacing.small
                ),
            )
            container.add_item(
                discord.ui.TextDisplay(content=f"**Expression:** `{display_expr}`")
            )
            container.add_item(
                discord.ui.TextDisplay(content=f"**Result:** `{result_str}`")
            )
            container.accent_colour = discord.Colour(0xFFFFFF)
            view = discord.ui.LayoutView()
            view.add_item(container)
            await ctx.send(view=view)

        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

    @math.command(name="algebra", description="Solve equations or evaluate expressions")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.describe(
        input="Equation to solve.", variable="Variable to solve for."
    )
    async def algebra(self, ctx: Context, input: str, variable: str = "x"):
        """Solve equations or evaluate mathematical expressions"""
        try:
            expr_str = input.replace("sqrt", "sqrt_").replace("^", "**").strip()

            expr_str = re.sub(r"(\d+)([a-zA-Z])", r"\1*\2", expr_str)  # 2x -> 2*x
            expr_str = re.sub(r"([a-zA-Z])(\d+)", r"\1*\2", expr_str)  # x2 -> x*2
            expr_str = re.sub(r"([a-zA-Z])(\()", r"\1*\2", expr_str)  # x( -> x*(
            expr_str = re.sub(r"(\))([a-zA-Z])", r"\1*\2", expr_str)  # )x -> )*x
            expr_str = re.sub(r"(\d)(\()", r"\1*\2", expr_str)  # 2( -> 2*(

            expr_str = expr_str.replace("sqrt_", "sqrt")

            if "=" in expr_str:
                left, right = expr_str.split("=", 1)
                expr = sympify(f"({left.strip()}) - ({right.strip()})")
                solutions = solve(expr, variable)

                if not solutions:
                    result = "No solution found"
                else:
                    solutions = [
                        soln.evalf(5)
                        for soln in (
                            solutions if isinstance(solutions, list) else [solutions]
                        )
                    ]
                    result = "\n".join(f"{variable} = {soln}" for soln in solutions)

                title = "Equation Solver"
                content = f"**Equation:** `{input}`\n**Solutions:**\n```\n{result}\n```"
            else:
                expr = sympify(expr_str)
                result = expr.evalf(10)
                title = "Expression Evaluator"
                content = f"**Expression:** `{input}`\n**Result:** `{result}`"

            container = discord.ui.Container()
            container.add_item(discord.ui.TextDisplay(content=f"### {title}"))
            container.add_item(
                discord.ui.Separator(
                    visible=True, spacing=discord.SeparatorSpacing.small
                )
            )
            container.add_item(discord.ui.TextDisplay(content=content))

            view = discord.ui.LayoutView()
            view.add_item(container)
            await ctx.send(view=view)

        except Exception as e:
            error_msg = f"Error: {str(e)}"
            await ctx.send(error_msg, ephemeral=True)
