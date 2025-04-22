import asyncio
import json
import discord
import yt_dlp
from youtube_search import YoutubeSearch

class MusicPlayer:
    def __init__(self):
        self.queues = {}
        self.voice_clients = {}
        
        # YT-DLP configuration
        self.yt_dlp_options = {
            "format": "bestaudio[abr<=96]/bestaudio",
            "noplaylist": True,
            "youtube_include_dash_manifest": False,
            "youtube_include_hls_manifest": False,
        }
        self.ytdl = yt_dlp.YoutubeDL(self.yt_dlp_options)
        
        # FFmpeg options
        self.ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn -filter:a "volume=0.25"'
        }
    
    async def connect_to_voice(self, interaction):
        """Connect to the user's voice channel"""
        try:
            voice_client_id = interaction.user.voice.channel.id
            voice_channel = interaction.client.get_channel(voice_client_id)
            
            if interaction.guild_id not in self.voice_clients:
                voice_client = await voice_channel.connect()
                self.voice_clients[interaction.guild_id] = voice_client
                return True
            return True
        except Exception as e:
            print(f"Voice connection error: {e}")
            return False
    
    async def search_youtube(self, search_term):
        """Search YouTube for a song"""
        if search_term.startswith("https://www.youtube.com/watch?v="):
            # Direct URL provided
            song_url = search_term
            try:
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(None, lambda: self.ytdl.extract_info(song_url, download=False))
                title = data.get('title', song_url)
                return song_url, title
            except Exception as e:
                print(f"Error extracting info from URL: {e}")
                return None, None
        else:
            # Search by title
            try:
                yt = YoutubeSearch(search_term, max_results=1).to_json()
                search_results = json.loads(yt)['videos']
                
                if not search_results:
                    return None, None
                    
                song_id = str(search_results[0]['id'])
                song_url = f"https://www.youtube.com/watch?v={song_id}"
                title = search_results[0]['title']
                return song_url, title
            except Exception as e:
                print(f"YouTube search error: {e}")
                return None, None
    
    async def play_song(self, interaction, song_url):
        """Play a song in a voice channel"""
        guild_id = interaction.guild_id
        
        # Initialize queue if it doesn't exist
        if guild_id not in self.queues:
            self.queues[guild_id] = []
        
        # Get song info
        song_url, title = await self.search_youtube(song_url)
        if not song_url:
            return False, "Couldn't find that song!"
        
        try:
            if self.voice_clients[guild_id].is_playing():
                # Add to queue if already playing
                self.queues[guild_id].append(song_url)
                return True, f"Added to queue: {title}"
            else:
                # Play immediately
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(None, lambda: self.ytdl.extract_info(song_url, download=False))
                
                song = data['url']
                player = discord.FFmpegPCMAudio(song, **self.ffmpeg_options)
                self.voice_clients[guild_id].play(
                    player, 
                    after=lambda e: asyncio.run_coroutine_threadsafe(
                        self.play_next(guild_id, interaction.client.loop, interaction.client), 
                        interaction.client.loop
                    )
                )
                return True, f"Playing: {title}"
        except Exception as e:
            print(f"Error in play function: {e}")
            return False, "Error playing the song."
    
    async def play_next(self, guild_id, bot_loop, client):
        """Play the next song in the queue"""
        # Check if queue exists and has songs
        if guild_id in self.queues and self.queues[guild_id]:
            next_song = self.queues[guild_id].pop(0)
            
            # Get guild from client
            guild = client.get_guild(guild_id)
            if not guild:
                print(f"Could not find guild with ID {guild_id}")
                return
                
            # Find a text channel to notify about the next song
            text_channel = None
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).send_messages:
                    text_channel = channel
                    break
            
            try:
                # Get song info
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(None, lambda: self.ytdl.extract_info(next_song, download=False))
                
                song = data['url']
                title = data.get('title', next_song)
                
                # Play the song
                player = discord.FFmpegPCMAudio(song, **self.ffmpeg_options)
                self.voice_clients[guild_id].play(
                    player, 
                    after=lambda e: asyncio.run_coroutine_threadsafe(
                        self.play_next(guild_id, bot_loop, client), 
                        bot_loop
                    )
                )
                
                # Notify about the new song
                if text_channel:
                    await text_channel.send(f"Now playing: {title}")
            
            except Exception as e:
                print(f"Error in play_next function: {e}")
                if text_channel:
                    await text_channel.send("Failed to play next song")