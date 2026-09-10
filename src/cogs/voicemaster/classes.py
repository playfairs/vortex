import discord
from discord import (
    app_commands,
)
from discord.ext import commands
from discord.ext.commands import (
    Cog,
    Context,
    group,
    has_permissions,
    hybrid_command as hybrid,
    hybrid_group,
)
from vortex import vortex


class Join2Create(Cog):
    def __init__(self, bot: vortex):
        self.bot = bot
        self.db = bot.db
        self._setup_done = False

    async def cog_load(self):
        self._setup_done = True

    async def get_voice_master_info(self, guild_id: int):
        """Get the VoiceMaster category and join channel ID for a guild."""
        return await self.db.fetchrow(
            "SELECT category_id, channel_id FROM voice_master WHERE guild_id = $1",
            guild_id,
        )

    @Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        try:
            if not self._setup_done or member.bot or member == self.bot.user:
                return

            vm_info = await self.get_voice_master_info(member.guild.id)
            if not vm_info:
                return

            join_channel_id = vm_info["channel_id"]
            category_id = vm_info["category_id"]

            if after.channel and after.channel.id == join_channel_id:
                try:
                    existing_channel = await self.db.fetchrow(
                        "SELECT channel_id FROM vm_channels WHERE owner_id = $1",
                        member.id,
                    )

                    if existing_channel:
                        channel = member.guild.get_channel(
                            existing_channel["channel_id"]
                        )
                        if channel and isinstance(channel, discord.VoiceChannel):
                            await member.move_to(
                                channel, reason="Rejoined VoiceMaster channel"
                            )
                            return
                        else:
                            await self.db.execute(
                                "DELETE FROM vm_channels WHERE channel_id = $1",
                                existing_channel["channel_id"],
                            )

                    category = member.guild.get_channel(category_id)
                    if not category or not isinstance(
                        category, discord.CategoryChannel
                    ):
                        return
                    new_channel = await category.create_voice_channel(
                        name=f"{member.display_name}'s Channel",
                        reason=f"VoiceMaster: Created for {member}",
                    )

                    await member.move_to(
                        new_channel, reason="Joined VoiceMaster channel"
                    )

                    await self.db.execute(
                        """
                        INSERT INTO vm_channels (channel_id, owner_id)
                        VALUES ($1, $2)
                        ON CONFLICT (channel_id) DO NOTHING
                        """,
                        new_channel.id,
                        member.id,
                    )

                except discord.Forbidden as e:
                    try:
                        await member.guild.owner.send(
                            f"I don't have permission to manage voice channels in {member.guild}."
                        )
                    except:
                        pass

            if (
                before.channel
                and before.channel.id != join_channel_id
                and before.channel.id
                in (
                    channel["channel_id"]
                    for channel in await self.db.fetch(
                        "SELECT channel_id FROM vm_channels"
                    )
                )
                and len(before.channel.members) == 0
            ):

                try:
                    await before.channel.delete(reason="Voice channel is empty")
                    await self.db.execute(
                        "DELETE FROM vm_channels WHERE channel_id = $1",
                        before.channel.id,
                    )
                except discord.Forbidden:
                    pass

        except Exception as e:
            print(f"Error in voice state update: {e}")
            raise
