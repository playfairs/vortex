import discord
from discord.ext import commands, tasks
from discord.ext.commands import (
    Cog,
    Context,
    group,
    has_permissions,
    guild_only,
    hybrid_command as hybrid,
    hybrid_group,
    BucketType,
    cooldown,
)
from discord import app_commands
from typing import Optional
from .classes import Join2Create

from vortex import vortex
from config import DISCORD, BUTTONS
import time


class VoiceMaster(Cog, description="View commands in VoiceMaster."):
    def __init__(self, bot: vortex):
        self.bot = bot
        self.db = bot.db
        self.join2create = Join2Create(bot)

    async def setup_tables(self):
        """Create necessary database tables if they don't exist."""
        await self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS voice_master (
                guild_id BIGINT PRIMARY KEY,
                category_id BIGINT,
                channel_id BIGINT,
                commands_channel_id BIGINT,
                static_role_id BIGINT
            )
            """
        )
        await self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS vm_channels (
                channel_id BIGINT PRIMARY KEY,
                owner_id BIGINT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
            """
        )
        print("VoiceMaster tables created/verified")

    @guild_only()
    @hybrid_group(name="voicemaster", aliases=["vm", "vc"])
    async def voicemaster(self, ctx: Context):
        """View commands in VoiceMaster."""
        await ctx.send_help(ctx.command)

    @voicemaster.command(name="setup")
    @app_commands.describe(
        category="The name of your category. (VoiceMaster by default)"
    )
    @has_permissions(manage_guild=True)
    async def setup(self, ctx: Context, category: Optional[str] = None):
        """Setup VoiceMaster with a category and join channel."""
        await self.setup_tables()

        if category is None:
            category = "VoiceMaster"

        try:
            new_category = await ctx.guild.create_category_channel(name=category)
            join_channel = await new_category.create_voice_channel(name="Join 2 Create")
            commands_channel = await new_category.create_text_channel(name="commands")

            await self.db.execute(
                """
                INSERT INTO voice_master (guild_id, category_id, channel_id, commands_channel_id)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (guild_id) 
                DO UPDATE SET category_id = $2, channel_id = $3, commands_channel_id = $4
                """,
                ctx.guild.id,
                new_category.id,
                join_channel.id,
                commands_channel.id,
            )

            await ctx.send(
                "VoiceMaster has been set up, you can rename the channel or category if you want."
            )

        except discord.Forbidden:
            await ctx.send("I don't have permission to create channels or categories.")
        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}")
            raise

    @voicemaster.command(name="staticrole")
    @has_permissions(manage_guild=True)
    async def staticrole(self, ctx: Context, role: discord.Role):
        """Set a staticrole for VoiceMaster (The role that all members get when they join the server)."""
        await self.db.execute(
            "UPDATE voice_master SET static_role_id = $1 WHERE guild_id = $2",
            role.id,
            ctx.guild.id,
        )
        await ctx.send(f"Static role set to {role.mention}.")

    @voicemaster.command(name="reset")
    @has_permissions(manage_guild=True)
    async def reset(self, ctx: Context):
        """Reset VoiceMaster."""

        record = await self.db.fetchrow(
            "SELECT category_id, channel_id, static_role_id, commands_channel_id FROM voice_master WHERE guild_id = $1",
            ctx.guild.id,
        )

        if not record:
            return await ctx.send("VoiceMaster is not set up.")

        category_id, _, static_role_id, commands_channel_id = record

        if category_id:
            try:
                category = ctx.guild.get_channel(category_id)
                if category and isinstance(category, discord.CategoryChannel):
                    for channel in category.channels:
                        try:
                            await channel.delete(
                                reason="VoiceMaster reset - Deleting all channels in category"
                            )
                        except Exception as e:
                            await ctx.send(
                                f"Could not delete channel {channel.name}: {str(e)}"
                            )
                    await category.delete(
                        reason="VoiceMaster reset - Deleting category"
                    )
            except discord.Forbidden:
                await ctx.send(
                    "I don't have permission to delete channels or categories."
                )
                return
            except Exception as e:
                await ctx.send(f"An error occurred while deleting category: {str(e)}")
                raise

        if record[1]:
            try:
                channel = ctx.guild.get_channel(record[1])
                if channel:
                    await channel.delete(
                        reason="VoiceMaster reset - Deleting join-to-create channel"
                    )
            except Exception as e:
                await ctx.send(f"Could not delete join-to-create channel: {str(e)}")

        if static_role_id:
            await self.db.execute(
                "UPDATE voice_master SET static_role_id = NULL WHERE guild_id = $1",
                ctx.guild.id,
            )

        if commands_channel_id:
            try:
                commands_channel = ctx.guild.get_channel(commands_channel_id)
                if commands_channel:
                    await commands_channel.delete(
                        reason="VoiceMaster reset - Deleting commands channel"
                    )
            except Exception as e:
                await ctx.send(f"Could not delete commands channel: {str(e)}")

        try:
            await self.db.execute(
                "DELETE FROM voice_master WHERE guild_id = $1", ctx.guild.id
            )
            await self.db.execute(
                "DELETE FROM vm_channels WHERE channel_id IN (SELECT channel_id FROM voice_master WHERE guild_id = $1)",
                ctx.guild.id,
            )
            await ctx.send(
                "VoiceMaster has been completely reset. All associated channels have been deleted."
            )
        except Exception as e:
            await ctx.send(
                f"VoiceMaster channels have been deleted, but there was an error cleaning up the database: {str(e)}"
            )

    @voicemaster.command(name="lock")
    async def vm_lock(self, ctx: Context):
        """Lock your VoiceMaster channel to prevent others from joining."""
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send(
                "You need to be in a voice channel to use this command."
            )

        voice_channel = ctx.author.voice.channel

        record = await self.db.fetchrow(
            """
            SELECT vmc.owner_id, vm.static_role_id
            FROM vm_channels vmc
            LEFT JOIN voice_master vm ON vm.guild_id = $1
            WHERE vmc.channel_id = $2
            """,
            ctx.guild.id,
            voice_channel.id,
        )

        if not record:
            return await ctx.send(
                "This is not a VoiceMaster channel or it's not set up correctly."
            )

        owner_id, static_role_id = record

        if ctx.author.id != owner_id:
            return await ctx.send("Only the channel owner can lock this channel.")

        roles_to_lock = [ctx.guild.default_role]
        if static_role_id:
            static_role = ctx.guild.get_role(static_role_id)
            if static_role:
                roles_to_lock.append(static_role)

        try:
            for role in roles_to_lock:
                current_overwrites = voice_channel.overwrites_for(role)
                current_overwrites.update(connect=False)
                await voice_channel.set_permissions(role, overwrite=current_overwrites)
            await ctx.send("👍")
        except discord.Forbidden:
            await ctx.send("I don't have permission to modify channel permissions.")
        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}")

    @voicemaster.command(name="unlock")
    async def vm_unlock(self, ctx: Context):
        """Unlock your VoiceMaster channel to allow others to join."""
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send(
                "You need to be in a voice channel to use this command."
            )

        voice_channel = ctx.author.voice.channel

        record = await self.db.fetchrow(
            """
            SELECT vmc.owner_id, vm.static_role_id
            FROM vm_channels vmc
            LEFT JOIN voice_master vm ON vm.guild_id = $1
            WHERE vmc.channel_id = $2
            """,
            ctx.guild.id,
            voice_channel.id,
        )

        if not record:
            return await ctx.send(
                "This is not a VoiceMaster channel or it's not set up correctly."
            )

        owner_id, static_role_id = record

        if ctx.author.id != owner_id:
            return await ctx.send("Only the channel owner can unlock this channel.")

        roles_to_unlock = [ctx.guild.default_role]
        if static_role_id:
            static_role = ctx.guild.get_role(static_role_id)
            if static_role:
                roles_to_unlock.append(static_role)

        try:
            for role in roles_to_unlock:
                current_overwrites = voice_channel.overwrites_for(role)
                current_overwrites.update(connect=None)
                await voice_channel.set_permissions(role, overwrite=current_overwrites)
            await ctx.send("👍")
        except discord.Forbidden:
            await ctx.send("I don't have permission to modify channel permissions.")
        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}")

    @voicemaster.command(name="hide")
    async def vm_hide(self, ctx: Context):
        """Hide your VoiceMaster channel from the channel list."""
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send(
                "You need to be in a voice channel to use this command."
            )

        voice_channel = ctx.author.voice.channel

        record = await self.db.fetchrow(
            """
            SELECT vmc.owner_id, vm.static_role_id
            FROM vm_channels vmc
            LEFT JOIN voice_master vm ON vm.guild_id = $1
            WHERE vmc.channel_id = $2
            """,
            ctx.guild.id,
            voice_channel.id,
        )

        if not record:
            return await ctx.send(
                "This is not a VoiceMaster channel or it's not set up correctly."
            )

        owner_id, static_role_id = record

        if ctx.author.id != owner_id:
            return await ctx.send("Only the channel owner can hide this channel.")

        roles_to_hide = [ctx.guild.default_role]
        if static_role_id:
            static_role = ctx.guild.get_role(static_role_id)
            if static_role:
                roles_to_hide.append(static_role)

        try:
            for role in roles_to_hide:
                current_overwrites = voice_channel.overwrites_for(role)
                current_overwrites.update(view_channel=False)
                await voice_channel.set_permissions(role, overwrite=current_overwrites)
            await ctx.send("👍")
        except discord.Forbidden:
            await ctx.send("I don't have permission to modify channel permissions.")
        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}")

    @voicemaster.command(name="unhide")
    async def vm_unhide(self, ctx: Context):
        """Unhide your VoiceMaster channel from the channel list."""
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send(
                "You need to be in a voice channel to use this command."
            )

        voice_channel = ctx.author.voice.channel

        record = await self.db.fetchrow(
            """
            SELECT vmc.owner_id, vm.static_role_id
            FROM vm_channels vmc
            LEFT JOIN voice_master vm ON vm.guild_id = $1
            WHERE vmc.channel_id = $2
            """,
            ctx.guild.id,
            voice_channel.id,
        )

        if not record:
            return await ctx.send(
                "This is not a VoiceMaster channel or it's not set up correctly."
            )

        owner_id, static_role_id = record

        if ctx.author.id != owner_id:
            return await ctx.send("Only the channel owner can unhide this channel.")

        roles_to_unhide = [ctx.guild.default_role]
        if static_role_id:
            static_role = ctx.guild.get_role(static_role_id)
            if static_role:
                roles_to_unhide.append(static_role)

        try:
            for role in roles_to_unhide:
                current_overwrites = voice_channel.overwrites_for(role)
                current_overwrites.update(view_channel=None)
                await voice_channel.set_permissions(role, overwrite=current_overwrites)
            await ctx.send("👍")
        except discord.Forbidden:
            await ctx.send("I don't have permission to modify channel permissions.")
        except Exception as e:
            await ctx.send(f"An error occurred: {str(e)}")

    @voicemaster.command(name="cleanup")
    @has_permissions(manage_channels=True)
    async def vm_cleanup(self, ctx: Context):
        """Cleanup empty VoiceMaster channels."""
        try:
            vm_data = await self.db.fetchrow(
                "SELECT category_id, channel_id FROM voice_master WHERE guild_id = $1",
                ctx.guild.id,
            )

            if not vm_data:
                return await ctx.send("VoiceMaster is not set up in this server.")

            category_id, join_channel_id = vm_data
            category = ctx.guild.get_channel(category_id)

            if not category or not isinstance(category, discord.CategoryChannel):
                return await ctx.send("Could not find the VoiceMaster category.")

            deleted_count = 0

            for channel in category.voice_channels:
                if channel.id == join_channel_id or channel.members:
                    continue

                try:
                    await self.db.execute(
                        "DELETE FROM vm_channels WHERE channel_id = $1", channel.id
                    )
                    await channel.delete(reason="VoiceMaster cleanup - Empty channel")
                    deleted_count += 1
                except Exception as e:
                    await ctx.send(f"Failed to delete channel {channel.name}: {str(e)}")

            if deleted_count > 0:
                await ctx.send(
                    f"Cleaned up {deleted_count} empty voice channel{'s' if deleted_count != 1 else ''}."
                )
            else:
                await ctx.send("No empty voice channels to clean up.")

        except Exception as e:
            await ctx.send(f"An error occurred during cleanup: {str(e)}")

    @voicemaster.command(name="claim")
    async def vm_claim(self, ctx: Context):
        """Claim a VoiceMaster channel if the owner is not present."""
        try:
            if not ctx.author.voice or not ctx.author.voice.channel:
                return await ctx.send(
                    "You need to be in a voice channel to use this command."
                )

            vm_data = await self.db.fetchrow(
                """
                SELECT vmc.owner_id, vmc.channel_id
                FROM vm_channels vmc
                INNER JOIN voice_master vm ON vm.guild_id = $1
                WHERE vmc.channel_id = $2
                """,
                ctx.guild.id,
                ctx.author.voice.channel.id,
            )

            if not vm_data:
                return await ctx.send("This is not a VoiceMaster channel.")

            owner_id, channel_id = vm_data

            owner = ctx.guild.get_member(owner_id)
            if (
                owner
                and owner.voice
                and owner.voice.channel
                and owner.voice.channel.id == channel_id
            ):
                return await ctx.send(
                    "You cannot claim this VoiceMaster channel while the owner is present."
                )

            await self.db.execute(
                """
                UPDATE vm_channels 
                SET owner_id = $1 
                WHERE channel_id = $2
                """,
                ctx.author.id,
                channel_id,
            )

            await ctx.send(f"You are now the owner of this VoiceMaster channel.")

        except Exception as e:
            await ctx.send(f"An error occurred while claiming the channel: {str(e)}")

    @voicemaster.command(name="transfer")
    async def vm_transfer(self, ctx: Context, user: discord.User):
        """Transfer ownership of a VoiceMaster channel to another user."""
        try:
            if not ctx.author.voice or not ctx.author.voice.channel:
                return await ctx.send(
                    "You need to be in a voice channel to use this command."
                )

            vm_data = await self.db.fetchrow(
                """
                SELECT vmc.owner_id, vmc.channel_id
                FROM vm_channels vmc
                INNER JOIN voice_master vm ON vm.guild_id = $1
                WHERE vmc.channel_id = $2
                """,
                ctx.guild.id,
                ctx.author.voice.channel.id,
            )

            if not vm_data:
                return await ctx.send("This is not a VoiceMaster channel.")

            owner_id, channel_id = vm_data

            if ctx.author.id != owner_id:
                return await ctx.send(
                    "Only the current owner can transfer this channel."
                )

            if user.id == owner_id:
                return await ctx.send("This user is already the owner of this channel.")

            if not any(
                member.id == user.id for member in ctx.author.voice.channel.members
            ):
                return await ctx.send(
                    "The new owner must be in the same voice channel."
                )

            await self.db.execute(
                """
                UPDATE vm_channels 
                SET owner_id = $1 
                WHERE channel_id = $2
                """,
                user.id,
                channel_id,
            )

            await ctx.send(
                f"{user.mention} is now the owner of this VoiceMaster channel."
            )

        except Exception as e:
            await ctx.send(
                f"An error occurred while transferring the channel: {str(e)}"
            )

    @voicemaster.command(name="restrict")
    @app_commands.describe(
        user="The user to restrict.",
        action="The action to restrict (join, speak, view).",
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="Join", value="join"),
            app_commands.Choice(name="Speak", value="speak"),
            app_commands.Choice(name="View", value="view"),
        ]
    )
    async def vm_restrict(
        self, ctx: Context, user: discord.Member, action: app_commands.Choice[str]
    ):
        """Restrict a user's permissions in this VoiceMaster channel."""
        try:
            action_value = action.value

            if not ctx.author.voice or not ctx.author.voice.channel:
                return await ctx.send(
                    "You need to be in a voice channel to use this command."
                )

            vm_data = await self.db.fetchrow(
                """
                SELECT vmc.owner_id, vmc.channel_id
                FROM vm_channels vmc
                INNER JOIN voice_master vm ON vm.guild_id = $1
                WHERE vmc.channel_id = $2
                """,
                ctx.guild.id,
                ctx.author.voice.channel.id,
            )

            if not vm_data:
                return await ctx.send("This is not a VoiceMaster channel.")

            owner_id, channel_id = vm_data

            if ctx.author.id != owner_id:
                return await ctx.send(
                    "Only the owner of this VoiceMaster channel can restrict users."
                )

            channel = ctx.guild.get_channel(channel_id)
            if not channel:
                return await ctx.send("Could not find the voice channel.")

            overwrites = channel.overwrites_for(user)

            permission_updated = False
            action_name = action_value

            if action_value == "join":
                overwrites.update(connect=False)
                action_name = "join"
                permission_updated = True
            elif action_value == "speak":
                overwrites.update(speak=False)
                action_name = "speak"
                permission_updated = True
            elif action_value == "view":
                overwrites.update(view_channel=False)
                action_name = "view"
                permission_updated = True

            if not permission_updated:
                return await ctx.send("Invalid action selected.")

            reason = f"VoiceMaster: {ctx.author} restricted {action_name} for {user}"
            await channel.set_permissions(user, overwrite=overwrites, reason=reason)

            action_verb = action_name + (
                "ing" if not action_name.endswith("e") else "ing"
            )
            await ctx.send(
                f"{user.mention} has been restricted from {action_verb} in this channel."
            )

        except Exception as e:
            await ctx.send(f"An error occurred while updating restrictions: {str(e)}")

    @voicemaster.command(name="permit")
    @app_commands.describe(
        user="The user to permit.", action="The action to permit (join, speak, view)."
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="Join", value="join"),
            app_commands.Choice(name="Speak", value="speak"),
            app_commands.Choice(name="View", value="view"),
        ]
    )
    async def vm_permit(
        self, ctx: Context, user: discord.Member, action: app_commands.Choice[str]
    ):
        """Permit a user's permissions in this VoiceMaster channel."""
        try:
            action_value = action.value

            if not ctx.author.voice or not ctx.author.voice.channel:
                return await ctx.send(
                    "You need to be in a voice channel to use this command."
                )

            vm_data = await self.db.fetchrow(
                """
                SELECT vmc.owner_id, vmc.channel_id
                FROM vm_channels vmc
                INNER JOIN voice_master vm ON vm.guild_id = $1
                WHERE vmc.channel_id = $2
                """,
                ctx.guild.id,
                ctx.author.voice.channel.id,
            )

            if not vm_data:
                return await ctx.send("This is not a VoiceMaster channel.")

            owner_id, channel_id = vm_data

            if ctx.author.id != owner_id:
                return await ctx.send(
                    "Only the owner of this VoiceMaster channel can permit users."
                )

            channel = ctx.guild.get_channel(channel_id)
            if not channel:
                return await ctx.send("Could not find the voice channel.")

            overwrites = channel.overwrites_for(user)

            permission_updated = False
            action_name = action_value

            if action_value == "join":
                overwrites.update(connect=None)
                action_name = "join"
                permission_updated = True
            elif action_value == "speak":
                overwrites.update(speak=None)
                action_name = "speak"
                permission_updated = True
            elif action_value == "view":
                overwrites.update(view_channel=None)
                action_name = "view"
                permission_updated = True

            if not permission_updated:
                return await ctx.send("Invalid action selected.")

            reason = f"VoiceMaster: {ctx.author} permitted {action_name} for {user}"
            await channel.set_permissions(user, overwrite=overwrites, reason=reason)

            action_verb = action_name + (
                "ing" if not action_name.endswith("e") else "ing"
            )
            await ctx.send(
                f"{user.mention} has been permitted to {action_verb} in this channel."
            )

        except Exception as e:
            await ctx.send(f"An error occurred while updating permissions: {str(e)}")

    @voicemaster.command(name="rename")
    @app_commands.describe(name="The new name for the channel.")
    @cooldown(1, 10 * 60, BucketType.channel)
    async def vm_rename(self, ctx: Context, name: str):
        """Rename this VoiceMaster channel."""
        if len(name) > 100:
            return await ctx.send("Channel name too long.")

        try:
            if not ctx.author.voice or not ctx.author.voice.channel:
                return await ctx.send(
                    "You need to be in a voice channel to use this command."
                )

            vm_data = await self.db.fetchrow(
                """
                SELECT vmc.owner_id, vmc.channel_id
                FROM vm_channels vmc
                INNER JOIN voice_master vm ON vm.guild_id = $1
                WHERE vmc.channel_id = $2
                """,
                ctx.guild.id,
                ctx.author.voice.channel.id,
            )

            if not vm_data:
                return await ctx.send("This is not a VoiceMaster channel.")

            owner_id, channel_id = vm_data

            if ctx.author.id != owner_id:
                return await ctx.send(
                    "Only the owner of this VoiceMaster channel can rename it."
                )

            channel = ctx.guild.get_channel(channel_id)
            if not channel:
                return await ctx.send("Could not find the voice channel.")

            await channel.edit(name=name)
            await ctx.send(f"Successfully renamed the channel to {name}.")
        except Exception as e:
            await ctx.send(f"An error occurred while renaming the channel: {str(e)}")
