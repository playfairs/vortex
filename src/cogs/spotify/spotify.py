# import os
# import aiohttp
# import spotipy
# import urllib

# from discord.ext import commands
# from discord.ext.commands import Cog, Context, hybrid_command as hybrid
# from discord import app_commands

# from vortex import vortex
# from config import DISCORD
# from managers.classes import Media, Emojis, Colors


# class Spotify(Cog, command_attrs=dict(hidden=True)):
#     def __init__(self, bot: vortex):
#         self.bot = bot
#         self.session = aiohttp.ClientSession()
#         self.spotify_api_key = os.getenv("SPOTIFY_API_KEY")
#         self.spotify_api_secret = os.getenv("SPOTIFY_API_SECRET")
#         self.spotify_api_token = None
#         self.spotify = spotipy.Spotify(auth_manager=spotipy.SpotifyOAuth(
#             client_id=self.spotify_api_key,
#             client_secret=self.spotify_api_secret,
#             redirect_uri="http://localhost:8000/callback",
#             scope="user-read-currently-playing user-read-playback-state",
#         ))

#     async def cog_load(self):
#         self.spotify_api_token = await self.spotify.auth_manager.get_access_token()

#     async def cog_unload(self):
#         await self.session.close()
#         await self.spotify.close()

#     @hybrid(name="spotifyctl", aliases=["spotifycontrol"], description="Controls the Host's Spotify Session.")
#     @app_commands.allowed_installs(guilds=True, users=True)
#     @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
#     async def spotifyctl(
#         self, ctx: Context, action: str = None, *, query: str = None
#     ):
#         """Controls the Host's Spotify Session."""
#         try:
#             if action == "play":
#                 if (
#                     query
#                     and not query.startswith("https://")
#                     and not query.startswith("http://")
#                 ):
#                     query = urllib.parse.quote_plus(query)
#                     os.system(
#                         f'osascript -e \'tell application "Spotify" to play "https://open.spotify.com/search/{query}"\''
#                     )
#                 elif query:
#                     os.system(
#                         f'osascript -e \'tell application "Spotify" to play url "{query}"\''
#                     )
#                 else:
#                     os.system("osascript -e 'tell application \"Spotify\" to playpause'")

#                 await ctx.send("👍")
#                 await asyncio.sleep(1)
#                 await ctx.message.delete()
#             elif action == "stop":
#                 os.system("osascript -e 'tell application \"Spotify\" to playpause'")
#                 await ctx.send("👍")
#             elif action == "skip":
#                 os.system("osascript -e 'tell application \"Spotify\" to next track'")
#                 await ctx.send("👍")
#             elif action == "previous":
#                 os.system("osascript -e 'tell application \"Spotify\" to previous track'")
#                 await ctx.send("👍")
#             else:
#                 await ctx.send("This command is not yet implemented.")
#         except Exception as e:
#             await ctx.send(f"An unexpected error occurred: {str(e)}")
