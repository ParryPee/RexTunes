import asyncio
import json
import discord
import os
import yt_dlp
from youtube_search import YoutubeSearch
from spotify import Spotify

class MusicPlayer:
    def __init__(self):
        self.queues = {}
        self.voice_clients = {}
        self.current_songs = {}  # Track currently playing songs
        self.text_channels = {} # Track text channels 
        
        spot_id = os.getenv("spot_id")
        spot_secret = os.getenv("spot_secret")
        self.sp = Spotify(spot_secret, spot_id)
        
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
            # Check if user is in a voice channel
            if not interaction.user.voice:
                return False
                
            voice_client_id = interaction.user.voice.channel.id
            voice_channel = interaction.client.get_channel(voice_client_id)
            
            guild_id = interaction.guild_id
            
            # If already connected to a different channel, move to the new one
            if guild_id in self.voice_clients:
                # If already in the right channel, we're good
                if self.voice_clients[guild_id].channel.id == voice_client_id:
                    return True
                # Otherwise, disconnect to reconnect to the new channel    
                await self.voice_clients[guild_id].disconnect()
                
            # Connect to the voice channel
            voice_client = await voice_channel.connect()
            self.voice_clients[guild_id] = voice_client
            return True
            
        except Exception as e:
            print(f"Voice connection error: {e}")
            return False
    
    async def search_youtube(self, search_term):
        """Search YouTube for a song"""
        if not search_term:
            return None, None
            
        try:
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
        except Exception as e:
            print(f"Search YouTube error: {e}")
            return None, None
            
    async def play_playlist(self, interaction, playlist_url):
        """Play or add songs from a playlist"""
        guild_id = interaction.guild_id
        
        # Initialize queue if it doesn't exist
        if guild_id not in self.queues:
            self.queues[guild_id] = []
        if guild_id not in self.text_channels:
            self.text_channels[guild_id] = interaction.channel_id
            
        try:
            # Get playlist info in List([track_name, artist_name])
            playlist_info = self.sp.get_playlist_info(playlist_url)
            
            if not playlist_info:
                return False, "Couldn't find or access that playlist!"
                
            # Add songs to the queue
            added_songs = []
            
            for song in playlist_info:
                # Form search query - song name + artist name
                search_query = f"{song[0]} {song[1]['name']}"
                song_url, title = await self.search_youtube(search_query)
                
                if not song_url:
                    continue
                    
                added_songs.append((song_url, title))
            
            if not added_songs:
                return False, "Couldn't find any songs from that playlist!"
                
            # Check if already playing music
            if guild_id in self.voice_clients and self.voice_clients[guild_id].is_playing():
                # Add all songs to queue
                for song_url, title in added_songs:
                    self.queues[guild_id].append(song_url)
                    
                return True, f"Added {len(added_songs)} songs from the playlist to queue."
            else:
                # Play first song immediately
                first_song_url, first_title = added_songs[0]
                
                # Add remaining songs to queue
                for song_url, title in added_songs[1:]:
                    self.queues[guild_id].append(song_url)
                
                # Play first song
                await self.play_immediate(guild_id, first_song_url, interaction.client)
                
                return True, f"Playing: {first_title}\nAdded {len(added_songs) - 1} more songs to the queue."
                
        except Exception as e:
            print(f"Error in play_playlist function: {e}")
            return False, f"Error playing the playlist: {str(e)}"
        
    async def play_immediate(self, guild_id, song_url, client):
        """Immediately play a song without interaction"""
        try:
            # Get song info
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, lambda: self.ytdl.extract_info(song_url, download=False))
            
            if not data or 'url' not in data:
                print(f"No valid URL found for {song_url}")
                return False
                
            # Store current song for reference
            self.current_songs[guild_id] = song_url
            
            # Create audio player
            source_url = data['url']
            player = discord.FFmpegPCMAudio(source_url, **self.ffmpeg_options)
            
            # Play the song
            self.voice_clients[guild_id].play(
                player, 
                after=lambda e: asyncio.run_coroutine_threadsafe(
                    self.play_next(guild_id, client.loop, client), 
                    client.loop
                )
            )
            return True
        except Exception as e:
            print(f"Error in play_immediate: {e}")
            return False
        
    async def play_song(self, interaction, song_url):
        """Play a song in a voice channel"""
        guild_id = interaction.guild_id
        
        # Initialize queue if it doesn't exist
        if guild_id not in self.queues:
            self.queues[guild_id] = []
        if guild_id not in self.text_channels:
            self.text_channels[guild_id] = interaction.channel_id
        
        try:
            # Get song info
            song_url, title = await self.search_youtube(song_url)
            if not song_url:
                return False, "Couldn't find that song!"
            
            # Check if already playing
            if guild_id in self.voice_clients and self.voice_clients[guild_id].is_playing():
                # Add to queue if already playing
                self.queues[guild_id].append(song_url)
                return True, f"Added to queue: {title}"
            else:
                # Play immediately and track current song
                self.current_songs[guild_id] = song_url
                
                # Get song audio URL
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(None, lambda: self.ytdl.extract_info(song_url, download=False))
                
                if not data or 'url' not in data:
                    return False, "Error processing that song!"
                    
                source_url = data['url']
                player = discord.FFmpegPCMAudio(source_url, **self.ffmpeg_options)
                
                # Play the song
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
            return False, f"Error playing the song: {str(e)}"
    
    async def play_next(self, guild_id, bot_loop, client):
        """Play the next song in the queue"""
        # Clear current song reference
        if guild_id in self.current_songs:
            del self.current_songs[guild_id]
            
        # Check if queue exists and has songs
        if guild_id in self.queues and self.queues[guild_id] and guild_id in self.voice_clients:
            try:
                # Get the next song from queue
                next_song = self.queues[guild_id].pop(0)
                self.current_songs[guild_id] = next_song
                
                # Get guild from client
                guild = client.get_guild(guild_id)
                if not guild:
                    print(f"Could not find guild with ID {guild_id}")
                    return
                    
                # Find a text channel to notify about the next song
                text_channel = None
                if guild_id in self.text_channels:
                    channel_id = self.text_channels[guild_id]
                    text_channel = client.get_channel(channel_id)
                                    # If channel no longer exists or bot doesn't have permissions, log it
                    if text_channel is None or not text_channel.permissions_for(guild.me).send_messages:
                        print(f"Cannot send to original channel {channel_id}, looking for alternative")
                        text_channel = None
                if text_channel == None:
                    for channel in guild.text_channels:
                        if channel.permissions_for(guild.me).send_messages:
                            text_channel = channel
                            break
                
                # Get song info
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(None, lambda: self.ytdl.extract_info(next_song, download=False))
                
                if not data or 'url' not in data:
                    print(f"Failed to get URL for {next_song}")
                    if text_channel:
                        await text_channel.send("Failed to play next song - couldn't process audio")
                    # Try playing the next one in queue
                    await self.play_next(guild_id, bot_loop, client)
                    return
                
                source_url = data['url']
                title = data.get('title', next_song)
                
                # Create and play the audio source
                player = discord.FFmpegPCMAudio(source_url, **self.ffmpeg_options)
                
                if guild_id in self.voice_clients and self.voice_clients[guild_id].is_connected():
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
                else:
                    print(f"Voice client disconnected for guild {guild_id}")
            
            except Exception as e:
                print(f"Error in play_next function: {e}")
                # Try to get a channel to notify
                try:
                    guild = client.get_guild(guild_id)
                    if guild:
                        text_channel = None
                        for channel in guild.text_channels:
                            if channel.permissions_for(guild.me).send_messages:
                                text_channel = channel
                                break
                        
                        if text_channel:
                            await text_channel.send(f"Failed to play next song: {str(e)}")
                except:
                    pass
    async def check_empty_voice_channels(self, client):
        """
        Check if the bot is alone in any voice channels and disconnect if so.
        This should be called periodically.
        """
        # Create a list of guild IDs to avoid modifying dictionary during iteration
        guild_ids = list(self.voice_clients.keys())
        
        for guild_id in guild_ids:
            try:
                # Get the voice client for this guild
                voice_client = self.voice_clients.get(guild_id)
                if not voice_client or not voice_client.is_connected():
                    continue
                
                # Get the voice channel
                channel = voice_client.channel
                
                # Count members in the voice channel (excluding bots)
                human_members = sum(1 for member in channel.members if not member.bot)
                
                # If no human members are in the channel, disconnect
                if human_members == 0:
                    print(f"No users in voice channel {channel.name} ({channel.id}), disconnecting...")
                    
                    # Try to send a message before disconnecting
                    if guild_id in self.text_channels:
                        try:
                            text_channel = client.get_channel(self.text_channels[guild_id])
                            if text_channel:
                                await text_channel.send("Leaving voice channel because everyone left!")
                        except Exception as e:
                            print(f"Failed to send leave message: {e}")
                    
                    # Stop playback if playing
                    if voice_client.is_playing():
                        voice_client.stop()
                    
                    # Disconnect from voice channel
                    await voice_client.disconnect()
                    
                    # Clean up resources
                    del self.voice_clients[guild_id]
                    
                    # Clear the queue
                    if guild_id in self.queues:
                        self.queues[guild_id] = []
                        
                    # Clear current song reference
                    if guild_id in self.current_songs:
                        del self.current_songs[guild_id]
                        
            except Exception as e:
                print(f"Error checking empty voice channel for guild {guild_id}: {e}")