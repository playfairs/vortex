class Permissions:
    """
    Class to sort permissions into categories.
    Each category lists relevant Discord permissions.
    """

    # Core Administrative Permissions / Probably don't need to import this but I'm doing it just in case people don't know what it is.
    ADMINISTRATOR: list[str] = ["administrator", "manage_guild"]

    # Server Management
    SERVER: list[str] = sorted(
        [
            "manage_emojis_and_stickers",
            "manage_guild",
            "manage_webhooks",
            "view_audit_log",
        ]
    )

    # Channel Management
    CHANNEL: list[str] = sorted(
        [
            "create_instant_invite",
            "create_private_threads",
            "create_public_threads",
            "manage_channels",
            "manage_permissions",
            "manage_threads",
        ]
    )

    # Moderation
    MODERATION: list[str] = sorted(
        [
            "ban_members",
            "change_nickname",
            "kick_members",
            "manage_nicknames",
            "manage_roles",
            "mention_everyone",
            "moderate_members",
        ]
    )

    # Voice & Stage Management
    VOICE: list[str] = sorted(
        [
            "connect",
            "deafen_members",
            "manage_voice_states",
            "move_members",
            "mute_members",
            "priority_speaker",
            "request_to_speak",
            "speak",
            "stream",
            "use_external_emojis",
            "use_voice_activation",
        ]
    )

    # Message Management
    MESSAGE: list[str] = sorted(
        [
            "add_reactions",
            "attach_files",
            "embed_links",
            "read_message_history",
            "send_messages",
            "send_messages_in_threads",
            "send_tts_messages",
            "use_embedded_activities",
            "use_external_emojis",
        ]
    )

    # Application Commands / use_slash_commands is for bots, not users, it'll show as they don't have it if its a human.
    APPLICATION_COMMANDS: list[str] = sorted(
        ["use_application_commands", "use_external_apps", "use_slash_commands"]
    )
