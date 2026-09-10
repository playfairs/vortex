import discord
from discord import app_commands
from discord.ext.commands import (
    Cog,
    Context,
    hybrid_command as hybrid,
    hybrid_group,
    has_permissions,
)

from vortex import vortex
from .permissions import Permissions
import json


class FakePermissions(Cog, description="View commands in FakePermissions."):
    def __init__(self, bot: vortex):
        self.bot = bot
        self.bot.loop.create_task(self.create_tables())

    async def create_tables(self):
        await self.bot.db.execute(
            """
            CREATE TABLE IF NOT EXISTS fake_permissions (
                role_id BIGINT PRIMARY KEY,
                guild_id BIGINT,
                permissions TEXT
            )
            """
        )

    @hybrid_group(name="fakepermissions", aliases=["fp"], invoke_without_command=True)
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guild_only()
    async def fakepermissions(self, ctx: Context):
        """View commands in FakePermissions."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @fakepermissions.command(name="add")
    @app_commands.describe(
        role="The role to add permissions for.",
        permissions="The permissions to add.",
    )
    @has_permissions(administrator=True)
    @app_commands.choices(
        permissions=[
            app_commands.Choice(name="Administrator", value="admin"),
            app_commands.Choice(name="Server Management", value="server"),
            app_commands.Choice(name="Channel Management", value="channel"),
            app_commands.Choice(name="Moderation", value="mod"),
            app_commands.Choice(name="Voice & Stage", value="voice"),
            app_commands.Choice(name="Message", value="message"),
            app_commands.Choice(name="Application Commands", value="app_cmd"),
        ]
    )
    async def add(self, ctx: Context, role: discord.Role, permissions: str):
        """Add fake permissions for a role."""
        try:
            permission_map = {
                "admin": Permissions.ADMINISTRATOR,
                "server": Permissions.SERVER,
                "channel": Permissions.CHANNEL,
                "mod": Permissions.MODERATION,
                "voice": Permissions.VOICE,
                "message": Permissions.MESSAGE,
                "app_cmd": Permissions.APPLICATION_COMMANDS,
            }

            perm_list = permission_map.get(permissions)
            if not perm_list:
                return await ctx.send(
                    "Invalid permission set selected.", ephemeral=True
                )

            await self.bot.db.execute(
                """
                INSERT INTO fake_permissions (role_id, guild_id, permissions)
                VALUES ($1, $2, $3)
                ON CONFLICT (role_id) 
                DO UPDATE SET permissions = $3
                WHERE fake_permissions.role_id = $1
                """,
                role.id,
                ctx.guild.id,
                json.dumps(perm_list),
            )

            await ctx.send(
                f"Added fake permissions to {role.mention}: {', '.join(perm_list)}",
                ephemeral=True,
            )
        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}", ephemeral=True)

    @fakepermissions.command(name="list")
    @has_permissions(administrator=True)
    @app_commands.guild_only()
    async def list_permissions(self, ctx: Context, role: discord.Role = None):
        """List fake permissions for a role."""
        if role is None:
            records = await self.bot.db.fetch(
                "SELECT role_id, permissions FROM fake_permissions WHERE guild_id = $1",
                ctx.guild.id,
            )

            if not records:
                return await ctx.send(
                    "No fake permissions have been set up in this server."
                )

            embed = discord.Embed(title="Fake Permissions", color=discord.Color.blue())
            for record in records:
                role = ctx.guild.get_role(record["role_id"])
                if role:
                    perms = ", ".join(json.loads(record["permissions"]))
                    embed.add_field(name=role.name, value=perms, inline=False)

            await ctx.send(embed=embed)
        else:
            record = await self.bot.db.fetchrow(
                "SELECT permissions FROM fake_permissions WHERE role_id = $1", role.id
            )

            if not record:
                return await ctx.send(f"{role.mention} has no fake permissions set up.")

            perms = ", ".join(json.loads(record["permissions"]))
            await ctx.send(
                f"{role.mention} has the following fake permissions: {perms}"
            )

    async def get_role_permissions(self, role_id: int) -> list[str]:
        """Get the list of permissions for a role."""
        record = await self.bot.db.fetchrow(
            "SELECT permissions FROM fake_permissions WHERE role_id = $1", role_id
        )
        return json.loads(record["permissions"]) if record else []

    @fakepermissions.command(name="remove")
    @has_permissions(administrator=True)
    @app_commands.guild_only()
    @app_commands.describe(
        role="The role to remove fake permissions from",
        permissions="The permissions to remove",
    )
    async def remove_permissions(
        self, ctx: Context, role: discord.Role, permissions: str = None
    ):
        """Remove fake permissions from a role."""
        try:
            if permissions is None:
                await self.bot.db.execute(
                    "DELETE FROM fake_permissions WHERE role_id = $1", role.id
                )
                return await ctx.send(
                    f"Removed all fake permissions from {role.mention}"
                )

            current_perms = await self.get_role_permissions(role.id)
            if not current_perms:
                return await ctx.send(
                    f"{role.mention} has no fake permissions to remove."
                )

            perms_to_remove = json.loads(permissions)

            new_perms = [p for p in current_perms if p not in perms_to_remove]

            if not new_perms:
                await self.bot.db.execute(
                    "DELETE FROM fake_permissions WHERE role_id = $1", role.id
                )
            else:
                await self.bot.db.execute(
                    """
                    UPDATE fake_permissions 
                    SET permissions = $1
                    WHERE role_id = $2
                    """,
                    json.dumps(new_perms),
                    role.id,
                )

            await ctx.send(
                f"Removed permissions from {role.mention}: {', '.join(perms_to_remove)}"
            )

        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}", ephemeral=True)

    @remove_permissions.autocomplete("permissions")
    async def remove_permissions_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for permissions to remove."""
        role = interaction.namespace.role
        if not role:
            return []

        try:
            current_perms = await self.get_role_permissions(role.id)
            if not current_perms:
                return []

            choices = []
            for perm in current_perms:
                choices.append(
                    app_commands.Choice(
                        name=f"{perm} (Permission)", value=json.dumps([perm])
                    )
                )

            choices.append(
                app_commands.Choice(name="Remove All Permissions", value="all")
            )

            return [
                choice for choice in choices if current.lower() in choice.name.lower()
            ][:25]

        except Exception:
            return []
