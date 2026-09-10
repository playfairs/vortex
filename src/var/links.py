import re

discord_links = (
    [
        r"discord\.(?:gg|me|io|li|media|gift|gifts|plus|solutions|new|support|guilded|gift|gifts|plus|solutions|new|support|guilded)/[a-zA-Z0-9-]+",
        r"discord(?:app)?\.com/(?:invite|channels|guilds|guild|guild-discovery|guilded|gift|gifts|plus|solutions|new|support)/[a-zA-Z0-9-]+",
        r"(?:gg|dsc)\.(?:gg|io|me)/[a-zA-Z0-9-]+",
        r"(?:discord|dis)\.(?:com|gg|io|me|li|media|gift|gifts|plus|solutions|new|support|guilded)/(?:invite/)?[a-zA-Z0-9-]+",
    ],
)

media_links = (
    [
        r"\.(?:jpe?g|jpe|jfif|png|gif|webp|bmp|tiff?|svg|ico|heic|heif|raw|cr2|nef|orf|sr2|psd|xcf|dng|mp4|webm|mov|avi|mkv|flv|wmv|m4v|3gp|mpg|mpeg|m2v|m4v|svi|3gpp|3g2|f4v|m4p|m4v|ogv|qt|yuv|rm|rmvb|asf|amv|m4p|m4v|svi|mxf|roq|nsv|flv|f4v|f4p|f4a|f4b)(?:\?.*)?$",
    ],
)

media_hosts = (
    [
        r"(?:youtu\.be/|youtube\.com/\S*?(?:\?|&)(?:v=|/v/|/embed/|/v\.be/))[\w-]+",
        r"(?:vimeo\.com/|player\.vimeo\.com/video/)\d+",
        r"(?:imgur\.com/[a-zA-Z0-9]+(?:\.[a-z]+)?)",
        r"gyazo\.com/[a-f0-9]+",
        r"gfycat\.com/[a-zA-Z]+",
        r"streamable\.com/[a-z0-9]+",
        r"clips\.twitch\.tv/[a-zA-Z0-9-_]+",
    ],
)

social_links = (
    [
        r"(?:https?:\/\/)?(?:www\.)?(?:twitter|x)\.com\/(?:#!\/)?(?:\w+)\/status(?:es)?\/\d+",
        r"(?:https?:\/\/)?(?:www\.)?instagram\.com\/(?:p|reel|reels)\/([^\/\?]+)",
        r"(?:https?:\/\/)?(?:www\.)?facebook\.com\/[^\/]+\/(?:posts|photos|videos)\/[0-9]+",
        r"(?:https?:\/\/)?(?:www\.)?tiktok\.com\/@[^\/]+\/video\/\d+",
        r"(?:https?:\/\/)?(?:www\.)?reddit\.com\/r\/\w+\/comments\/\w+",
        r"(?:https?:\/\/)?(?:www\.)?linkedin\.com\/feed\/update\/urn:li:activity:\d+",
    ],
)

nsfw_links = [
    # Adult content platforms
    r"(?:https?:\/\/)?(?:www\.)?(?:pornhub\.com|phncdn\.com|p-cdn\.co|phprcdn\.com)\/[\w\-\/]+",
    r"(?:https?:\/\/)?(?:www\.)?(?:xvideos\.com|xvideos\-?cdn\.com)\/[\w\-\/]+",
    r"(?:https?:\/\/)?(?:www\.)?xnxx\.com\/[\w\-\/]+",
    r"(?:https?:\/\/)?(?:www\.)?xhamster\.com\/[\w\-\/]+",
    r"(?:https?:\/\/)?(?:www\.)?redtube\.com\/[\w\-\/]+",
    r"(?:https?:\/\/)?(?:www\.)?youporn\.com\/[\w\-\/]+",
    r"(?:https?:\/\/)?(?:www\.)?brazzers\.com\/[\w\-\/]+",
    r"(?:https?:\/\/)?(?:www\.)?fakku\.net\/[\w\-\/]+",
    # Hentai/Anime adult content
    r"(?:https?:\/\/)?(?:www\.)?nhentai\.net\/g\/\d+",
    r"(?:https?:\/\/)?(?:www\.)?e-?hentai\.org\/[\w\-\/]+",
    r"(?:https?:\/\/)?(?:www\.)?hanime\.tv\/[\w\-\/]+",
    r"(?:https?:\/\/)?(?:www\.)?hentaihaven\.com\/[\w\-\/]+",
    r"(?:https?:\/\/)?(?:www\.)?hentaicity\.com\/[\w\-\/]+",
    r"(?:https?:\/\/)?(?:www\.)?hentaimama\.com\/[\w\-\/]+",
    # Imageboards with NSFW content
    r"(?:https?:\/\/)?(?:www\.)?rule34\.xxx\/index\.php\?.*page=post",
    r"(?:https?:\/\/)?(?:www\.)?gelbooru\.com\/index\.php\?.*id=\d+",
    r"(?:https?:\/\/)?(?:www\.)?danbooru\.donmai\.us\/posts\/\d+",
    r"(?:https?:\/\/)?(?:www\.)?sankakucomplex\.com\/[\w\-\/]+",
    # Furry/Anthro content
    r"(?:https?:\/\/)?(?:www\.)?furaffinity\.net\/view\/\d+",
    r"(?:https?:\/\/)?(?:www\.)?e621\.net\/posts\/\d+",
    r"(?:https?:\/\/)?(?:www\.)?inkbunny\.net\/[\w\-\/]+",
    # NSFW subreddits (sample of common ones)
    r"(?:https?:\/\/)?(?:www\.)?reddit\.com\/r\/(?:gonewild|nsfw|RealGirls|nsfw2|porn|NSFW_GIF|nsfw_gifs|porn_gifs|pussy|ass|boobs|boobies|tits|thick|thighdeology|thighhighs|asshole\/\/[\w\-\/]+",
]
