from .configuration import Config
from discord import app_commands
from discord.ext import commands
from discord.ext.commands import (
    Cog,
    Context,
    has_permissions,
    hybrid_group,
    hybrid_command as hybrid,
)
from vortex import vortex
import discord
from base.embeds import Builder


class Gate(Cog):
    def __init__(self, bot: vortex):
        self.bot = bot
        self.db = bot.db

    def _format_message(self, message: str, member: discord.Member) -> str:
        """Helper method to format messages with member and guild placeholders"""
        if not message:
            return ""

        try:
            safe_message = message

            replacements = {
                "{user.mention}": getattr(member, "mention", ""),
                "{member.mention}": getattr(member, "mention", ""),
                "{user.name}": getattr(member, "name", ""),
                "{member.name}": getattr(member, "name", ""),
                "{user.id}": str(getattr(member, "id", "")),
                "{member.id}": str(getattr(member, "id", "")),
                "{user.avatar}": str(getattr(member.display_avatar, "url", "")),
                "{member.avatar}": str(getattr(member.display_avatar, "url", "")),
                "{guild.name}": str(getattr(member.guild, "name", "")),
                "{guild.id}": str(getattr(member.guild, "id", "")),
                "{guild.count}": str(getattr(member.guild, "member_count", "")),
            }

            for placeholder, value in replacements.items():
                if placeholder in safe_message:
                    safe_message = safe_message.replace(
                        placeholder, str(value) if value is not None else ""
                    )

            return safe_message

        except Exception as e:
            print(f"Error in _format_message: {e}")
            return str(message) if message is not None else ""

    @Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Handle member join events and send welcome messages if configured."""
        try:
            gate_config = await self.db.fetchrow(
                """
                SELECT channel_id, welcome_message, dm_message
                FROM gate
                WHERE guild_id = $1
                """,
                member.guild.id,
            )

            if not gate_config:
                return

            channel_id, welcome_message, dm_message = gate_config

            if channel_id and welcome_message:
                channel = self.bot.get_channel(channel_id)
                if channel and channel.permissions_for(member.guild.me).send_messages:
                    try:
                        formatted_message = self._format_message(
                            welcome_message, member
                        )
                        await channel.send(formatted_message)
                    except discord.HTTPException as e:
                        print(f"Failed to send welcome message in {member.guild}: {e}")

            if dm_message and not member.bot:
                try:
                    formatted_dm = self._format_message(dm_message, member)
                    await member.send(formatted_dm)
                except discord.Forbidden:
                    pass
                except Exception as e:
                    print(f"Failed to send DM to {member}: {e}")

        except Exception as e:
            print(f"Error in on_member_join for {member.guild}: {e}")

        try:
            autorole_data = await self.db.fetchrow(
                """
                SELECT role_id, bot_role_id
                FROM autorole
                WHERE guild_id = $1
                """,
                member.guild.id,
            )

            if not autorole_data:
                return

            if not member.bot and autorole_data["role_id"]:
                role = member.guild.get_role(int(autorole_data["role_id"]))
                if role:
                    try:
                        await member.add_roles(role, reason="Autorole given")
                    except discord.Forbidden:
                        print(f"Failed to add human role to {member}: Forbidden")
                    except Exception as e:
                        print(f"Failed to add human role to {member}: {e}")

            if member.bot and autorole_data["bot_role_id"]:
                role = member.guild.get_role(int(autorole_data["bot_role_id"]))
                if role:
                    try:
                        await member.add_roles(role, reason="Bot autorole given")
                    except discord.Forbidden:
                        print(f"Failed to add bot role to {member}: Forbidden")
                    except Exception as e:
                        print(f"Failed to add bot role to {member}: {e}")

        except Exception as e:
            print(f"Error in on_member_join for {member.guild}: {e}")

    @Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        try:
            gate_config = await self.db.fetchrow(
                """
                SELECT channel_id, goodbye_message
                FROM gate
                WHERE guild_id = $1
                """,
                member.guild.id,
            )

            if not gate_config:
                return

            channel_id, goodbye_message = gate_config

            if channel_id and goodbye_message:
                channel = self.bot.get_channel(channel_id)
                if channel and channel.permissions_for(member.guild.me).send_messages:
                    try:
                        formatted_message = self._format_message(
                            goodbye_message, member
                        )
                        await channel.send(formatted_message)
                    except discord.HTTPException as e:
                        print(f"Failed to send goodbye message: {e}")
        except Exception as e:
            print(f"Error in on_member_remove for {member.guild}: {e}")
