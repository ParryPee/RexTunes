import discord
import os, json
import asyncio
import yt_dlp
from youtube_search import YoutubeSearch
from dotenv import load_dotenv
from discord import app_commands

def run_bot():
    load_dotenv()
    TOKEN = os.getenv("token")
    GUILD_ID = os.getenv("server_id")
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)
    tree = app_commands.CommandTree(client)

    queues = {}
    voice_clients = {}
    yt_dlp_options = {"format": "bestaudio[abr<=96]/bestaudio","noplaylist": True, "youtube_include_dash_manifest": False, "youtube_include hls_manifest": False,}
    ytdl = yt_dlp.YoutubeDL(yt_dlp_options)

    
    ffmpeg_options = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5','options': '-vn -filter:a "volume=0.25"'}

    @client.event
    async def on_ready():
        #Sync for a single guild
        await tree.sync(guild=discord.Object(id=GUILD_ID))
        #Sync for all guilds
        # await tree.sync()


        print(f"{client.user} is now ready.")

    @tree.command(name="play",description="Play song",guild=discord.Object(id=GUILD_ID))
    @app_commands.describe(song_title="Enter song title")
    async def play(interaction:discord.Interaction, song_title: str):
        try:
            voice_client_id = interaction.user.voice.channel.id
            voice_channel = client.get_channel(voice_client_id)
            if interaction.guild_id not in voice_clients:
                voice_client = await voice_channel.connect()
                voice_clients[interaction.guild_id] = voice_client
                

        except Exception as e:
            print(e)
            await interaction.response.send_message("You need to join a voice channel first!")
            return

        # Initialize queue if it doesn't exist
        if interaction.guild_id not in queues:
            queues[interaction.guild_id] = []

        # Check if we're using a URL directly (from skip function)
        if song_title.startswith("https://www.youtube.com/watch?v="):
            song_url = song_title
            # Get song info for display
            try:
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(None, lambda: ytdl.extract_info(song_url, download=False))
                title = data.get('title', song_url)
            except:
                title = song_url
        else:
            # User input a song title instead of link
            search = song_title
            yt = YoutubeSearch(search, max_results=1).to_json()
            try:
                song_id = str(json.loads(yt)['videos'][0]['id']) # takes in the first available search result returned in YTDL
                song_url = "https://www.youtube.com/watch?v="+song_id
                title = json.loads(yt)['videos'][0]['title']
            except Exception as e:
                print(e)
                await interaction.response.send_message("Couldn't find that song!")
                return

        try:
            if voice_clients[interaction.guild_id].is_playing(): # If the bot is already playing something, add it to the queue instead of playing it now
                # Add to queue instead of playing immediately
                queues[interaction.guild_id].append(song_url)
                try:
                    await interaction.response.send_message(f"Added to queue: {title}")
                except discord.errors.InteractionResponded:
                    await interaction.followup.send(f"Added to queue: {title}")
            else:
                # Play immediately happens when there is nothing playing on the bot
                try:
                    await interaction.response.send_message(f"Playing: {title}")
                except discord.errors.InteractionResponded:
                    await interaction.followup.send(f"Playing: {title}")

                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(None, lambda: ytdl.extract_info(song_url, download=False))

                song = data['url']
                player = discord.FFmpegPCMAudio(song, **ffmpeg_options)
                voice_clients[interaction.guild_id].play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(interaction.guild_id, client.loop), client.loop))
            
        except Exception as e:
            print(f"Error in play function: {e}")

    @tree.command(name="stop",description="Stops the player",guild=discord.Object(id=GUILD_ID))
    async def stop(interaction: discord.Interaction):
        try:
            voice_clients[interaction.guild_id].stop()
            await interaction.response.send_message(f"Leaving ;-;")
            await voice_clients[interaction.guild_id].disconnect()
            del voice_clients[interaction.guild_id]
            if interaction.guild_id in queues:
                del queues[interaction.guild_id]
        except Exception as e:
            print(e)
            await interaction.response.send_message("Nothing is playing!")

    @tree.command(name="pause",description="Pauses the player",guild=discord.Object(id=GUILD_ID))
    async def pause(interaction: discord.Interaction):
        try:
            await interaction.response.send_message(f"Paused")
            voice_clients[interaction.guild_id].pause()
        except Exception as e:
            print(e)
            await interaction.response.send_message("Nothing is playing!")

    @tree.command(name="resume",description="Resumes the player",guild=discord.Object(id=GUILD_ID))
    async def resume(interaction: discord.Interaction):
        try:
            await interaction.response.send_message(f"Resuming player")
            voice_clients[interaction.guild_id].resume()
        except Exception as e:
            print(e)
            await interaction.response.send_message("Nothing is paused!")

    @tree.command(name="skip",description="Skips the current song",guild=discord.Object(id=GUILD_ID))
    async def skip(interaction: discord.Interaction):
        try:
            # Check if we have a queue for this guild
            if interaction.guild_id not in queues or not queues[interaction.guild_id]:
                await interaction.response.send_message("No songs in queue to skip to!")
                return
                
            # Stop current playback if playing
            if interaction.guild_id in voice_clients and voice_clients[interaction.guild_id].is_playing():
                voice_clients[interaction.guild_id].stop()
            
            await interaction.response.send_message("Skipping to next song...")
            
            # Manually trigger play_next with the guild_id
            await play_next(interaction.guild_id, client.loop)
            
        except Exception as e:
            print(f"Error in skip function: {e}")
            try:
                await interaction.response.send_message("Failed to skip. Is anything playing?")
            except discord.errors.InteractionResponded:
                await interaction.followup.send("Failed to skip. Is anything playing?")

    async def play_next(guild_id, bot_loop):
        # Check if queue exists and has songs
        if guild_id in queues and queues[guild_id]:
            next_song = queues[guild_id].pop(0)
            
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
                data = await loop.run_in_executor(None, lambda: ytdl.extract_info(next_song, download=False))
                
                song = data['url']
                title = data.get('title', next_song)
                
                # Play the song
                player = discord.FFmpegPCMAudio(song, **ffmpeg_options)
                voice_clients[guild_id].play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(guild_id, bot_loop), bot_loop))
                
                # Notify about the new song
                if text_channel:
                    await text_channel.send(f"Now playing: {title}")
            
            except Exception as e:
                print(f"Error in play_next function: {e}")
                if text_channel:
                    await text_channel.send("Failed to play next song")

    client.run(TOKEN)