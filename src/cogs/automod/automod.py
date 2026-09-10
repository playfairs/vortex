import discord
import asyncio
from datetime import timedelta, datetime

from discord import app_commands
from discord.ext.commands import (
    Cog,
    Context,
    command,
    group,
    has_permissions,
    hybrid_group,
    hybrid_command as hybrid,
)
from discord import (
    AutoModRuleEventType,
    AutoModRuleTriggerType,
    AutoModRuleActionType,
    AutoModTrigger,
    AutoModRuleAction,
)
from typing import Optional
from var.links import *


class Automod(Cog, description="View commands in Automod."):
    def __init__(self, bot):
        self.bot = bot

    def get_actions(self, option: str, time: Optional[str] = None):
        if option == "ban":
            return [AutoModRuleAction(type=AutoModRuleActionType.ban)]
        elif option == "timeout":
            try:
                if not time:
                    duration = 300
                else:
                    if time.endswith("s"):
                        duration = int(time[:-1])
                    elif time.endswith("m"):
                        duration = int(time[:-1]) * 60
                    elif time.endswith("h"):
                        duration = int(time[:-1]) * 3600
                    elif time.endswith("d"):
                        duration = int(time[:-1]) * 86400
                    elif time.endswith("w"):
                        duration = int(time[:-1]) * 604800
                    else:
                        duration = 300

                duration = max(1, min(duration, 2419200))

                return [
                    AutoModRuleAction(
                        type=AutoModRuleActionType.timeout,
                        duration=timedelta(seconds=duration),
                    )
                ]
            except (ValueError, TypeError):
                return [
                    AutoModRuleAction(
                        type=AutoModRuleActionType.timeout,
                        duration=timedelta(seconds=300),
                    )
                ]
        else:
            return [AutoModRuleAction(type=AutoModRuleActionType.block_message)]

    @hybrid_group(
        name="automod",
        aliases=["am"],
        description="Base command for Automod Management.",
        invoke_without_command=True,
    )
    @has_permissions(manage_guild=True)
    async def automod(self, ctx: Context):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @automod.command(name="filter", description="Filter words via Automod.")
    @app_commands.describe(
        keyword="The word to filter.",
        option="The action to perform. (Default: 'block')",
        time="The time to timeout a member (60s, 5m, 10m, 1h, 1d, 7d, or 1w)",
    )
    @app_commands.choices(
        option=[
            app_commands.Choice(name="Block Message", value="block"),
            app_commands.Choice(name="Ban User", value="ban"),
            app_commands.Choice(name="Timeout User", value="timeout"),
        ],
        time=[
            app_commands.Choice(name="60 seconds", value="60s"),
            app_commands.Choice(name="5 minutes", value="5m"),
            app_commands.Choice(name="10 minutes", value="10m"),
            app_commands.Choice(name="1 hour", value="1h"),
            app_commands.Choice(name="1 day", value="1d"),
            app_commands.Choice(name="7 days", value="7d"),
            app_commands.Choice(name="1 week", value="1w"),
        ],
    )
    @has_permissions(manage_guild=True)
    async def filter(
        self,
        ctx: Context,
        keyword: str,
        option: str = "block",
        time: Optional[str] = None,
    ):
        if option == "timeout":
            if not time or time.lower() not in [
                "60s",
                "5m",
                "10m",
                "1h",
                "1d",
                "7d",
                "1w",
            ]:
                embed = discord.Embed(
                    title="Invalid Time Format",
                    description=(
                        "Please specify a valid time duration for the timeout.\n"
                        "**Available options:**\n"
                        "- 60s (1 minute)\n"
                        "- 5m (5 minutes)\n"
                        "- 10m (10 minutes)\n"
                        "- 1h (1 hour)\n"
                        "- 1d (1 day)\n"
                        "- 7d (7 days)\n"
                        "- 1w (1 week)"
                    ),
                    color=discord.Color(0xFFFFFF),
                )
                await ctx.send(embed=embed)
                return

        actions = self.get_actions(option, time)
        if not actions:
            embed = discord.Embed(
                description="Failed to create actions. Please check your parameters.",
                color=discord.Color(0xFFFFFF),
            )
            await ctx.send(embed=embed)
            return

        existing_rules = await ctx.guild.fetch_automod_rules()
        vortex_rule = discord.utils.get(existing_rules, name="vortex")

        if vortex_rule:
            current_keywords = vortex_rule.trigger.keyword_filter or []
            if keyword in current_keywords:
                embed = discord.Embed(
                    description=f"The word '{keyword}' is already filtered.",
                    color=discord.Color(0xFFFFFF),
                )
                await ctx.send(embed=embed)
                return

            current_keywords.append(keyword)
            was_timeout = any(
                action.type == AutoModRuleActionType.timeout
                for action in vortex_rule.actions
            )
            previous_duration = None
            if was_timeout and option == "timeout":
                for action in vortex_rule.actions:
                    if action.type == AutoModRuleActionType.timeout and hasattr(
                        action, "duration"
                    ):
                        previous_duration = action.duration
                        break

            await vortex_rule.edit(
                trigger=AutoModTrigger(
                    type=AutoModRuleTriggerType.keyword, keyword_filter=current_keywords
                ),
                actions=actions,
            )

            if option == "timeout":
                if was_timeout and (
                    previous_duration is None
                    or previous_duration
                    != next(
                        (
                            a.duration
                            for a in actions
                            if a.type == AutoModRuleActionType.timeout
                        ),
                        None,
                    )
                ):
                    action_text = f"Updated to timeout users for {time}"
                else:
                    action_text = "Unchanged"
            elif option == "ban":
                action_text = "Set to ban users"
            else:
                action_text = "Blocked"

            embed = discord.Embed(
                description=f"Added '{keyword}' to filtered words. Action: {action_text}.",
                color=discord.Color(0xFFFFFF),
            )
            await ctx.send(embed=embed)
        else:
            await ctx.guild.create_automod_rule(
                name="vortex",
                event_type=AutoModRuleEventType.message_send,
                trigger=AutoModTrigger(
                    type=AutoModRuleTriggerType.keyword, keyword_filter=[keyword]
                ),
                actions=actions,
                enabled=True,
                exempt_roles=[],
                exempt_channels=[],
            )
            action_text = {
                "block": "Blocked",
                "ban": "Bans",
                "timeout": f"Timeouts for {time}",
            }.get(option, "Blocked")

            embed = discord.Embed(
                description=f"Created new Automod rule with {action_text}, and added '{keyword}' to filtered words.",
                color=discord.Color(0xFFFFFF),
            )
            await ctx.send(embed=embed)

    @automod.command(name="list", description="List all filtered words.")
    @has_permissions(manage_guild=True)
    async def list(self, ctx: Context):
        existing_rules = await ctx.guild.fetch_automod_rules()
        vortex_rule = discord.utils.get(existing_rules, name="vortex")

        if vortex_rule:
            current_keywords = vortex_rule.trigger.keyword_filter or []
            embed = discord.Embed(
                description=f"Filtered words: {', '.join(current_keywords) or 'None'}",
                color=discord.Color(0xFFFFFF),
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description="No Automod rule found.",
                color=discord.Color(0xFFFFFF),
            )
            await ctx.send(embed=embed)

    @automod.command(name="enable", description="Enable the Automod Filter.")
    @has_permissions(manage_guild=True)
    async def enable(self, ctx: Context):
        existing_rules = await ctx.guild.fetch_automod_rules()
        vortex_rule = discord.utils.get(existing_rules, name="vortex")
        if vortex_rule.enabled:
            embed = discord.Embed(
                description="The Automod Filter is already enabled.",
                color=discord.Color(0xFFFFFF),
            )
            await ctx.send(embed=embed)
            return
        if vortex_rule:
            await vortex_rule.edit(enabled=True)
            embed = discord.Embed(
                description="Enabled the Automod Filter.",
                color=discord.Color(0xFFFFFF),
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description="No Automod rule found.",
                color=discord.Color(0xFFFFFF),
            )
            await ctx.send(embed=embed)

    @automod.command(name="disable", description="Disable the Automod Filter.")
    @has_permissions(manage_guild=True)
    async def disable(self, ctx: Context):
        existing_rules = await ctx.guild.fetch_automod_rules()
        vortex_rule = discord.utils.get(existing_rules, name="vortex")
        if not vortex_rule.enabled:
            embed = discord.Embed(
                description="The Automod Filter is already disabled.",
                color=discord.Color(0xFFFFFF),
            )
            await ctx.send(embed=embed)
            return
        if vortex_rule:
            await vortex_rule.edit(enabled=False)
            embed = discord.Embed(
                description="Disabled the Automod Filter.",
                color=discord.Color(0xFFFFFF),
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description="No Automod rule found.",
                color=discord.Color(0xFFFFFF),
            )
            await ctx.send(embed=embed)

    @automod.command(
        name="exempt", description="Exempt a role from the Automod Filter."
    )
    @app_commands.describe(role="The role to exempt.")
    @has_permissions(manage_guild=True)
    async def exempt(self, ctx: Context, role: discord.Role):
        existing_rules = await ctx.guild.fetch_automod_rules()
        vortex_rule = discord.utils.get(existing_rules, name="vortex")

        if vortex_rule:
            await vortex_rule.edit(exempt_roles=[role])
            embed = discord.Embed(
                description=f"Exempted {role.mention} from the Automod Filter.",
                color=discord.Color(0xFFFFFF),
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                description="No Automod rule found.",
                color=discord.Color(0xFFFFFF),
            )
            await ctx.send(embed=embed)

    @automod.command(name="edit", description="Edit the action of the Automod Filter.")
    @app_commands.describe(
        option="The action to perform.",
        time="The time to timeout a member if the option is timeout (60s, 5m, 10m, 1h, 1d, 7d, or 1w)",
        rule_id="The ID of the Automod rule to edit.",
    )
    @app_commands.choices(
        option=[
            app_commands.Choice(name="Block Message", value="block"),
            app_commands.Choice(name="Ban User", value="ban"),
            app_commands.Choice(name="Timeout User", value="timeout"),
        ],
        time=[
            app_commands.Choice(name="60 seconds", value="60s"),
            app_commands.Choice(name="5 minutes", value="5m"),
            app_commands.Choice(name="10 minutes", value="10m"),
            app_commands.Choice(name="1 hour", value="1h"),
            app_commands.Choice(name="1 day", value="1d"),
            app_commands.Choice(name="7 days", value="7d"),
            app_commands.Choice(name="1 week", value="1w"),
        ],
    )
    @has_permissions(manage_guild=True)
    async def edit(
        self,
        ctx: Context,
        option: str,
        time: Optional[str] = None,
        rule_id: Optional[int] = None,
    ):
        if option == "timeout":
            if not time or time.lower() not in [
                "60s",
                "5m",
                "10m",
                "1h",
                "1d",
                "7d",
                "1w",
            ]:
                embed = discord.Embed(
                    title="Invalid Time Format",
                    description=(
                        "Please specify a valid time duration for the timeout.\n"
                        "**Available options:**\n"
                        "- 60s (1 minute)\n"
                        "- 5m (5 minutes)\n"
                        "- 10m (10 minutes)\n"
                        "- 1h (1 hour)\n"
                        "- 1d (1 day)\n"
                        "- 7d (7 days)\n"
                        "- 1w (1 week)"
                    ),
                    color=discord.Color(0xFFFFFF),
                )
                await ctx.send(embed=embed)
                return

        actions = self.get_actions(option, time)
        existing_rules = await ctx.guild.fetch_automod_rules()
        if rule_id:
            vortex_rule = discord.utils.get(existing_rules, id=rule_id)
        else:
            vortex_rule = discord.utils.get(existing_rules, name="vortex")

        if not vortex_rule:
            embed = discord.Embed(
                description="No Automod rule found.",
                color=discord.Color(0xFFFFFF),
            )
            await ctx.send(embed=embed)
            return

        was_timeout = any(
            action.type == AutoModRuleActionType.timeout
            for action in vortex_rule.actions
        )
        previous_duration = None
        if was_timeout and option == "timeout":
            for action in vortex_rule.actions:
                if action.type == AutoModRuleActionType.timeout and hasattr(
                    action, "duration"
                ):
                    previous_duration = action.duration
                    break

        await vortex_rule.edit(actions=actions)

        if option == "timeout":
            if was_timeout and (
                previous_duration is None
                or previous_duration
                != next(
                    (
                        a.duration
                        for a in actions
                        if a.type == AutoModRuleActionType.timeout
                    ),
                    None,
                )
            ):
                action_text = f"Updated to timeout users for {time}"
            else:
                action_text = f"Set to timeout users for {time}"
        elif option == "ban":
            action_text = "Set to ban users"
        else:
            action_text = "Set to block messages"

        embed = discord.Embed(
            description=f"{action_text}.",
            color=discord.Color(0xFFFFFF),
        )
        await ctx.send(embed=embed)

    @automod.command(
        name="remove", description="Remove a word from the Automod filter."
    )
    @has_permissions(manage_guild=True)
    async def remove(self, ctx: Context, keyword: str):
        existing_rules = await ctx.guild.fetch_automod_rules()
        vortex_rule = discord.utils.get(existing_rules, name="vortex")

        if not vortex_rule:
            embed = discord.Embed(
                description="No Automod rule named 'vortex' found.",
                color=discord.Color(0xFFFFFF),
            )
            await ctx.send(embed=embed)
            return

        current_keywords = vortex_rule.trigger.keyword_filter or []
        if keyword not in current_keywords:
            embed = discord.Embed(
                description=f"The word '{keyword}' is not filtered.",
                color=discord.Color(0xFFFFFF),
            )
            await ctx.send(embed=embed)
            return

        current_keywords.remove(keyword)

        new_trigger = discord.AutoModTrigger(
            type=discord.AutoModRuleTriggerType.keyword, keyword_filter=current_keywords
        )

        await vortex_rule.edit(trigger=new_trigger)

        embed = discord.Embed(
            description=f"Removed '{keyword}' from filtered words.",
            color=discord.Color(0xFFFFFF),
        )
        await ctx.send(embed=embed)

    @automod.command(
        name="alert", description="Configure alert settings for Automod rule."
    )
    @app_commands.describe(
        enabled="Whether to enable or disable alerts",
        channel="The channel to send alerts to (leave empty to keep current or if disabled)",
    )
    @has_permissions(manage_guild=True)
    async def alert(
        self,
        ctx: Context,
        enabled: bool = None,
        channel: Optional[discord.TextChannel] = None,
    ):
        existing_rules = await ctx.guild.fetch_automod_rules()
        vortex_rule = discord.utils.get(existing_rules, name="vortex")

        if not vortex_rule:
            embed = discord.Embed(
                description="No Automod rule named 'vortex' found.",
                color=discord.Color(0xFFFFFF),
            )
            await ctx.send(embed=embed)
            return

        current_actions = vortex_rule.actions.copy()

        if enabled is not None:
            current_actions = [
                a
                for a in current_actions
                if a.type != discord.AutoModRuleActionType.send_alert_message
            ]
            if enabled:
                alert_action = discord.AutoModRuleAction(
                    type=discord.AutoModRuleActionType.send_alert_message,
                    channel_id=channel.id if channel else None,
                )
                current_actions.append(alert_action)

        if enabled is not None:
            await vortex_rule.edit(actions=current_actions)

        if channel is not None and any(
            a.type == discord.AutoModRuleActionType.send_alert_message
            for a in current_actions
        ):
            alert_action = next(
                (
                    a
                    for a in current_actions
                    if a.type == discord.AutoModRuleActionType.send_alert_message
                ),
                None,
            )
            if alert_action:
                alert_action.channel_id = channel.id
                await vortex_rule.edit(actions=current_actions)

        current_settings = []
        has_alert = any(
            a.type == discord.AutoModRuleActionType.send_alert_message
            for a in current_actions
        )

        if enabled is not None:
            current_settings.append(f"Alerts: {'Enabled' if has_alert else 'Disabled'}")

        if channel is not None and has_alert:
            current_settings.append(f"Alert Channel: {channel.mention}")

        if not current_settings:
            current_settings = ["No settings were updated."]

        embed = discord.Embed(
            title="Automod Alert Settings Updated",
            description="\n".join(current_settings),
            color=discord.Color(0xFFFFFF),
        )
        await ctx.send(embed=embed)

    @automod.command(
        name="config", description="Shows the current Automod rule configuration."
    )
    @has_permissions(manage_guild=True)
    async def config(self, ctx: Context):
        existing_rules = await ctx.guild.fetch_automod_rules()
        vortex_rule = discord.utils.get(existing_rules, name="vortex")

        if not vortex_rule:
            embed = discord.Embed(
                description="No Automod rule named 'vortex' found.",
                color=discord.Color(0xFFFFFF),
            )
            await ctx.send(embed=embed)
            return

        action_descriptions = []
        for action in vortex_rule.actions:
            if action.type == AutoModRuleActionType.timeout and hasattr(
                action, "duration"
            ):
                seconds = int(action.duration.total_seconds())
                if seconds % 604800 == 0:
                    duration = f"{seconds // 604800}w"
                elif seconds % 86400 == 0:
                    duration = f"{seconds // 86400}d"
                elif seconds % 3600 == 0:
                    duration = f"{seconds // 3600}h"
                elif seconds % 60 == 0:
                    duration = f"{seconds // 60}m"
                else:
                    duration = f"{seconds}s"
                action_descriptions.append(f"{action.type.name.upper()} ({duration})")
            else:
                action_descriptions.append(action.type.name.upper())

        alert_channel = None
        for action in vortex_rule.actions:
            if action.type == AutoModRuleActionType.send_alert_message and hasattr(
                action, "channel_id"
            ):
                alert_channel = ctx.guild.get_channel(action.channel_id)
                break

        embed = discord.Embed(
            title="Automod Rule Configuration",
            description="\n".join(
                [
                    f"**Event Type:** {vortex_rule.event_type.name.upper() if vortex_rule.event_type else 'None'}",
                    f"**Trigger Type:** {vortex_rule.trigger.type.name.title() if hasattr(vortex_rule.trigger, 'type') else 'None'}",
                    f"**Actions:** {', '.join(action_descriptions) if action_descriptions else 'None'}",
                    f"**Enabled:** {'Yes' if vortex_rule.enabled else 'No'}",
                    f"**Exempt Roles:** {', '.join([r.mention for r in vortex_rule.exempt_roles]) if vortex_rule.exempt_roles else 'None'}",
                    f"**Exempt Channels:** {', '.join([c.mention for c in vortex_rule.exempt_channels]) if vortex_rule.exempt_channels else 'None'}",
                    f"**Filtered Words:** {len(vortex_rule.trigger.keyword_filter) if hasattr(vortex_rule.trigger, 'keyword_filter') and vortex_rule.trigger.keyword_filter else '0'}",
                    f"**Alert Channel:** {alert_channel.mention if alert_channel else 'None'}",
                ]
            ),
            color=discord.Color(0xFFFFFF),
        )
        await ctx.send(embed=embed)

    @hybrid_group(
        name="antilink",
        description="Base command for Antilink management.",
        invoke_without_command=True,
    )
    async def antilink(self, ctx: Context):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @antilink.command(name="enable", description="Enable Antilink.")
    @has_permissions(manage_guild=True)
    @app_commands.describe(
        url_type="The type of URL to filter.",
        action="The type of action to take when a link is detected.",
        channel="The channel to send alerts to (leave empty for none)",
        time="The time to timeout the user for (leave empty for none)",
    )
    @app_commands.choices(
        url_type=[
            app_commands.Choice(name="All", value="all"),
            app_commands.Choice(name="Discord", value="discord"),
            app_commands.Choice(name="Media", value="media"),
            app_commands.Choice(name="NSFW", value="nsfw"),
            app_commands.Choice(name="Social", value="social"),
        ],
        action=[
            app_commands.Choice(name="Block", value="block"),
            app_commands.Choice(name="Timeout", value="timeout"),
        ],
    )
    async def enable(
        self,
        ctx: Context,
        url_type: str,
        action: str,
        channel: Optional[discord.TextChannel] = None,
        time: Optional[str] = None,
    ):
        existing_rules = await ctx.guild.fetch_automod_rules()
        antilink_rule = discord.utils.get(existing_rules, name="antilink")

        new_keywords = []
        if url_type == "all":
            new_keywords = ["*https://*", "*http://*", "*www.*"]
        elif url_type == "discord":
            new_keywords = [
                "*discord.gg/*",
                "*discord.com/invite/*",
                "*discordapp.com/invite/*",
                "*dsc.gg/*",
                "*gg./*",
            ]
        elif url_type == "media":
            new_keywords = [
                "*.jpg*",
                "*.jpeg*",
                "*.png*",
                "*.gif*",
                "*.webp*",
                "*.mp4*",
                "*.webm*",
                "*.mov*",
                "*.avi*",
                "*.mkv*",
            ]
        elif url_type == "nsfw":
            new_keywords = [
                "*porn*",
                "*xxx*",
                "*nsfw*",
                "*hentai*",
                "*fuck*",
                "*pornhub*",
                "*xhamster*",
                "*xnxx*",
                "*redtube*",
                "*youporn*",
            ]
        elif url_type == "social":
            new_keywords = [
                "*twitter.com/*",
                "*x.com/*",
                "*instagram.com/*",
                "*facebook.com/*",
                "*tiktok.com/*",
                "*reddit.com/*",
            ]

        new_actions = self.get_actions(action, time)

        if not antilink_rule:
            if not new_keywords:
                new_keywords = ["*https://*"]

            antilink_rule = await ctx.guild.create_automod_rule(
                name="antilink",
                event_type=discord.AutoModRuleEventType.message_send,
                trigger=AutoModTrigger(
                    type=AutoModRuleTriggerType.keyword,
                    keyword_filter=new_keywords[:20],
                ),
                actions=new_actions,
                enabled=True,
                exempt_roles=[],
                exempt_channels=[],
                reason=f"Antilink rule created by {ctx.author}",
            )
            await ctx.send("Created new antilink rule and enabled it")
            return

        if action == "timeout":
            if not time or time.lower() not in [
                "60s",
                "5m",
                "10m",
                "1h",
                "1d",
                "7d",
                "1w",
            ]:
                container = discord.ui.Container()
                container.add_item(
                    discord.ui.TextDisplay(content="Invalid time format")
                )
                container.add_item(
                    discord.ui.TextDisplay(
                        content="Valid time formats:\n60s: 60 seconds\n5m: 5 minutes\n10m: 10 minutes\n1h: 1 hour\n1d: 1 day\n7d: 7 days\n1w: 1 week"
                    )
                )
                view = discord.ui.LayoutView()
                view.add_item(container)
                await ctx.send(view=view)
                return

        try:
            existing_trigger = antilink_rule.trigger
            existing_keywords = (
                set(existing_trigger.keyword_filter)
                if existing_trigger.keyword_filter
                else set()
            )
            existing_actions = list(antilink_rule.actions)

            combined_keywords = list(existing_keywords.union(new_keywords))

            action_types = {a.type: a for a in existing_actions}
            for action in new_actions:
                action_types[action.type] = action
            combined_actions = list(action_types.values())

            await antilink_rule.edit(
                trigger=AutoModTrigger(
                    type=AutoModRuleTriggerType.keyword,
                    keyword_filter=combined_keywords[:20],
                ),
                actions=combined_actions,
                enabled=True,
            )

            if channel:
                alert_action = next(
                    (
                        a
                        for a in combined_actions
                        if a.type == AutoModRuleActionType.send_alert_message
                    ),
                    None,
                )
                if alert_action:
                    alert_action.channel_id = channel.id
                else:
                    combined_actions.append(
                        AutoModRuleAction(
                            type=AutoModRuleActionType.send_alert_message,
                            channel_id=channel.id,
                        )
                    )

                await antilink_rule.edit(actions=combined_actions)

            await ctx.send(
                f"Updated antilink rule with **{url_type.title()}** filters."
            )

        except Exception as e:
            await ctx.send(f"Failed to update antilink rule: {str(e)}")
            return

    @antilink.command(name="disable", description="Disable Antilink.")
    @has_permissions(manage_guild=True)
    async def disable(self, ctx: Context):
        existing_rules = await ctx.guild.fetch_automod_rules()
        antilink_rule = discord.utils.get(existing_rules, name="antilink")

        if not antilink_rule:
            await ctx.send("Antilink rule not found")
            return

        try:
            await antilink_rule.delete()
            await ctx.send("Antilink rule disabled")
        except Exception as e:
            await ctx.send(f"Failed to disable antilink rule: {str(e)}")
            return

    @antilink.command(
        name="remove", description="Remove a specific URL type from the antilink rule."
    )
    @has_permissions(manage_guild=True)
    @app_commands.describe(
        url_type="The type of URL to remove from the antilink rule.",
    )
    @app_commands.choices(
        url_type=[
            app_commands.Choice(name="All URLs", value="all"),
            app_commands.Choice(name="Discord Invites", value="discord"),
            app_commands.Choice(name="Media Files", value="media"),
            app_commands.Choice(name="NSFW Content", value="nsfw"),
            app_commands.Choice(name="Social Media", value="social"),
        ]
    )
    async def remove(self, ctx: Context, url_type: str):
        """Remove specific URL types from the antilink rule."""
        existing_rules = await ctx.guild.fetch_automod_rules()
        antilink_rule = discord.utils.get(existing_rules, name="antilink")

        if not antilink_rule:
            await ctx.send("No antilink rule found to modify.")
            return

        if url_type == "all":
            await antilink_rule.edit(
                trigger=AutoModTrigger(
                    type=AutoModRuleTriggerType.keyword,
                    keyword_filter=[
                        "AntilinkPlaceholderSinceAutomodFiltersCan'tBeEmpty"
                    ],
                ),
                enabled=False,
            )
            await ctx.send(
                "All antilink filters have been cleared and the rule has been disabled."
            )
            return

        keywords_to_remove = []
        if url_type == "discord":
            keywords_to_remove = [
                "*discord.gg/*",
                "*discord.com/invite/*",
                "*discordapp.com/invite/*",
                "*dsc.gg/*",
                "*gg./*",
            ]
        elif url_type == "media":
            keywords_to_remove = [
                "*.jpg*",
                "*.jpeg*",
                "*.png*",
                "*.gif*",
                "*.webp*",
                "*.mp4*",
                "*.webm*",
                "*.mov*",
                "*.avi*",
                "*.mkv*",
            ]
        elif url_type == "nsfw":
            keywords_to_remove = [
                "*porn*",
                "*xxx*",
                "*nsfw*",
                "*hentai*",
                "*fuck*",
                "*pornhub*",
                "*xhamster*",
                "*xnxx*",
                "*redtube*",
                "*youporn*",
            ]
        elif url_type == "social":
            keywords_to_remove = [
                "*twitter.com/*",
                "*x.com/*",
                "*instagram.com/*",
                "*facebook.com/*",
                "*tiktok.com/*",
                "*reddit.com/*",
            ]

        try:
            existing_trigger = antilink_rule.trigger
            existing_keywords = (
                set(existing_trigger.keyword_filter)
                if existing_trigger.keyword_filter
                else set()
            )

            updated_keywords = list(existing_keywords - set(keywords_to_remove))

            if not updated_keywords:
                updated_keywords = ["*https://*"]

            await antilink_rule.edit(
                trigger=AutoModTrigger(
                    type=AutoModRuleTriggerType.keyword,
                    keyword_filter=updated_keywords[:20],
                ),
                enabled=bool(updated_keywords),
            )

            await ctx.send(f"Removed {url_type} filters from the antilink rule.")

        except Exception as e:
            await ctx.send(f"Failed to update antilink rule: {str(e)}")
            return

    @antilink.command(
        name="exempt", description="Exempt a role from the Antilink Filter."
    )
    @app_commands.describe(role="The role to exempt.")
    @has_permissions(manage_guild=True)
    async def exempt(self, ctx: Context, role: discord.Role):
        existing_rules = await ctx.guild.fetch_automod_rules()
        antilink_rule = discord.utils.get(existing_rules, name="antilink")

        if antilink_rule:
            await antilink_rule.edit(exempt_roles=[role])
            container = discord.ui.Container(
                discord.ui.TextDisplay(
                    content=f"Exempted {role.mention} from the Antilink Filter."
                )
            )
            view = discord.ui.LayoutView()
            view.add_item(container)
            await ctx.send(view=view)
        else:
            container = discord.ui.Container(
                discord.ui.TextDisplay(content="No Antilink rule found.")
            )
            view = discord.ui.LayoutView()
            view.add_item(container)
            await ctx.send(view=view)

    @antilink.command(
        name="alert", description="Configure alert settings for Antilink rule."
    )
    @app_commands.describe(
        enabled="Whether to enable or disable alerts",
        channel="The channel to send alerts to (leave empty to keep current or if disabled)",
    )
    @has_permissions(manage_guild=True)
    async def alert(
        self,
        ctx: Context,
        enabled: bool = None,
        channel: Optional[discord.TextChannel] = None,
    ):
        existing_rules = await ctx.guild.fetch_automod_rules()
        antilink_rule = discord.utils.get(existing_rules, name="antilink")

        if not antilink_rule:
            embed = discord.Embed(
                description="No Antilink rule found.",
                color=discord.Color(0xFFFFFF),
            )
            await ctx.send(embed=embed)
            return

        current_actions = antilink_rule.actions.copy()

        if enabled is not None:
            current_actions = [
                a
                for a in current_actions
                if a.type != discord.AutoModRuleActionType.send_alert_message
            ]
            if enabled:
                alert_action = discord.AutoModRuleAction(
                    type=discord.AutoModRuleActionType.send_alert_message,
                    channel_id=channel.id if channel else None,
                )
                current_actions.append(alert_action)

        if enabled is not None:
            await antilink_rule.edit(actions=current_actions)

        if channel is not None and any(
            a.type == discord.AutoModRuleActionType.send_alert_message
            for a in current_actions
        ):
            alert_action = next(
                (
                    a
                    for a in current_actions
                    if a.type == discord.AutoModRuleActionType.send_alert_message
                ),
                None,
            )
            if alert_action:
                alert_action.channel_id = channel.id
                await antilink_rule.edit(actions=current_actions)

        current_settings = []
        has_alert = any(
            a.type == discord.AutoModRuleActionType.send_alert_message
            for a in current_actions
        )

        if enabled is not None:
            current_settings.append(f"Alerts: {'Enabled' if has_alert else 'Disabled'}")

        if channel is not None and has_alert:
            current_settings.append(f"Alert Channel: {channel.mention}")

        if not current_settings:
            current_settings = ["No settings were updated."]

        container = discord.ui.Container(
            discord.ui.TextDisplay(
                content="Automod Alert Settings Updated\n\n"
                + "\n".join(current_settings)
            )
        )
        view = discord.ui.LayoutView()
        view.add_item(container)

        await ctx.send(view=view)
