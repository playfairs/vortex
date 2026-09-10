from discord import Color

# class Emojis:
#     """CTX"""

#     automod = "<:supports_automod:1379468073681289286>"
#     balance = "<:hypesquad_balance:1297930998864019509>"
#     bravery = "<:hypesquad_bravery:1297931035421708358>"
#     brilliance = "<:hypesquad_brilliance:1297931072503418890>"
#     booster = "<:boost:1297931223972450488>"
#     bot = "<a:bot2:1323899876924198976>"
#     bug_hunter = "<:bug_hunter:1297931813121036321>"
#     bug_hunter_level_2 = "<:bug_hunter_level_2:1297931831521312850>"
#     cancel = "<:cancel:1307448502913204294>"
#     check = "<:check:1301903971535028314>"
#     developer = "<:active_developer:1297930880987431035>"
#     early_supporter = "<:early_supporter:1297931252158042283>"
#     error = "<:error:1354931772810334367>"
#     hypesquad = "<:hypesquad:1297930974633398293>"
#     info = "<:info:1378658024289468437>"
#     left = "<:left:1307448382326968330>"
#     moderator = "<:certified_moderator:1297932110514098290>"
#     owner = "<:server_owner:1297930836368167015>"
#     partner = "<:partner:1297931370357723198>"
#     staff = "<:staff:1297931763229917246>"
#     right = "<:right:1307448399624405134>"
#     verified_developer = "<:verified_bot_developer:1297931270139150338>"

#     heresy = "<:heresyicon:1338845590033006744>"
#     python = "<:python:1344022861530009650>"
#     vortex = "<:vortex:1351304264563032136>"


class Emojis:
    """CTX for Emojis in Vortex."""

    balance = "<:hypesquad_balance:1381816391719583795>"
    blacktea = "<:blacktea:1410072573684744222>"
    bravery = "<:hypesquad_bravery:1381816395498651708>"
    brilliance = "<:hypesquad_brilliance:1381816398157713579>"
    booster = "<:boost:1381816403161645130>"
    bot = "<a:bot2:1381816408748331128>"
    bug_hunter = "<:bug_hunter:1381816369401692191>"
    bug_hunter_level_2 = "<:bug_hunter_level_2:1381816371855233145>"
    cancel = "<:cancel:1381816342004498453>"
    check = "<:check:1381816339425132606>"
    delete = "<:delete:1414433504409813123>"
    developer = "<:active_developer:1381816388351688774>"
    developer2 = "<:developer:1398338548628983938>"
    developer3 = "<:developer3:1398339500429807636>"
    disabled = "<:disabled:1406379252072452116>"
    enabled = "<:enabled:1406379264659427370>"
    error = "<:error:1381816350552625186>"
    early_supporter = "<:early_supporter:1381816374392914012>"
    endofpage = "<:endofpage:1403620994500923432>"
    frontofpage = "<:frontofpage:1403621369396199534>"
    hypesquad = "<:hypesquad:1381816367057080470>"
    home = ":house:"
    info = "<:info:1381816410673516798>"
    left = "<:left:1398347378716704902>"
    moderator = "<:certified_moderator:1381816379400912898>"
    moderator_programs_alumni = "<:moderator_2:1386490124778602598>"
    partner = "<:partner:1381816364532105346>"
    premium = "<:premium:1398436442879037562>"
    private = "<:private:1406380480521306203>"
    public = "<:public:1406380496300015788>"
    python = "<:python:1381816359037702144>"
    right = "<:right:1398347382407827498>"
    search = "<:search:1411397802914742414>"
    originally_known_as = "<:originallyknownas:1386490903639625738>"
    owner = "<:server_owner:1381816400691073054>"
    quest = "<:quest:1386490905065689149>"
    staff = "<:staff:1381816361944350721>"
    supports_automod = "<:supports_automod:1381816413282631750>"
    verified_developer = "<:verified_bot_developer:1381816377136119890>"
    xletter = "<:xletter:1368837324791877653>"
    vortex = "<:vortexicon:1394564493333368892>"


class VoiceMasterButtons:
    """Buttons for VoiceMaster Interface"""


class Colors:
    """Embed Colors"""

    main = Color(0xFFFFFF)
    secondary = Color(0x000000)
    error_color = Color(0xFFFFED)


class Media:
    """Media Imported from playfairs.cc"""

    # vortex = "https://upload.cc/i1/2025/04/11/PpV5Uf.png"
    heresy = "https://playfairs.cc/heresy.png"
    hydra = "https://playfairs.cc/hydra.png"
    mouse = "https://upload.cc/i1/2025/04/11/rNFyhq.gif"
    fox = "https://upload.cc/i1/2025/04/11/rOwpEn.gif"
    # vortex = "https://snarkydev.me/assets/images/vortex-logo.png"
    loredb = "https://media.playfairs.cc/assets/LoreDB.png"
    vortex = "https://vortex.playfairs.cc/kaxu.png"
    blacktea = "https://bio.playfairs.cc/assets/blacktea.png"


class Assets:
    """Assets Imported from assets folder"""

    vortex = "assets/vortex.png"
    heresy = "assets/heresy.png"
    mouse = "assets/mouse.gif"
    fox = "assets/fox.gif"


class Servers:
    """Servers"""

    unix = "https://discord.gg/unix"
    vortex = "https://discord.gg/vortexbot"


class FallBackURLs:
    """Fallback URLs"""

    default_avatar0 = "https://cdn.discordapp.com/embed/avatars/0.png"
    default_avatar1 = "https://cdn.discordapp.com/embed/avatars/1.png"
    default_avatar2 = "https://cdn.discordapp.com/embed/avatars/2.png"
    default_avatar3 = "https://cdn.discordapp.com/embed/avatars/3.png"
    default_avatar4 = "https://cdn.discordapp.com/embed/avatars/4.png"
    default_avatar5 = "https://cdn.discordapp.com/embed/avatars/5.png"

    def default_avatar(self, user_id: int) -> str:
        return f"https://cdn.discordapp.com/embed/avatars/{(user_id >> 22) % 5}.png"


class Links:
    """Links"""

    invite = "https://discordapp.com/oauth2/authorize?client_id=1347441071323480074&scope=bot+applications.commands&permissions=8"
