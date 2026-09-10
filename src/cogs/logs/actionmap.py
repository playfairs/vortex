import discord

from discord.ext import commands, tasks
from discord.ui import View, Button

from vortex import vortex


class ActionMap:
    def __init__(self):
        self.action_map = {
            "ban": "banned",
            "kick": "kicked",
            "jail": "jailed",
            "unjail": "unjailed",
            "mute": "muted",
            "unmute": "unmuted",
            "warn": "warned",
            "timeout": "timed a member out",
            "untimeout": "removed a member's timeout",
            "unban": "unbanned",
            "unbanall": "cleared bans",
            "nickname": "altered a member's nickname",
            "forcenick": "forced a member's nickname",
            "lock": "started a channel lockdown",
            "softban": "soft banned",
            "nuke": "nuked",
            "unlockall": "ended the lockdown",
            "unlock": "ended a channel lockdown",
        }

    def get_action(self, action):
        return self.action_map.get(action, action)
