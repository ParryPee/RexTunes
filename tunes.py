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
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)
    tree = app_commands.CommandTree(client)

    queues = {}
    voice_clients = {}
    yt_dlp_options = {"format": "bestaudio/best"}
    ytdl = yt_dlp.YoutubeDL(yt_dlp_options)

    
    ffmpeg_options = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5','options': '-vn -filter:a "volume=0.25"'}

    @client.event
    async def on_ready():
        #Sync for a single guild
        await tree.sync(guild=discord.Object(id=""))
        #Sync for all guilds
        # await tree.sync()


        print(f"{client.user} is now ready.")

    @tree.command(name="play",description="Play song",guild=discord.Object(id=""))
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
            # await interaction.response.send_message("You need to join a voice channel first!")

        search = song_title
        yt = YoutubeSearch(search,max_results=1).to_json()
        try:
            song_id = str(json.loads(yt)['videos'][0]['id'])
            song_url = "https://www.youtube.com/watch?v="+song_id
            if voice_clients[interaction.guild_id].is_playing():
                await queue(interaction,song_url)
            else:
            
                await interaction.response.send_message(f"Playing: {song_url}")

                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(None, lambda: ytdl.extract_info(song_url, download=False))


                song=data['url']
                player = discord.FFmpegPCMAudio(song, **ffmpeg_options)
                voice_clients[interaction.guild_id].play(player, after=lambda e: asyncio.run_coroutine_threadsafe(playnext(interaction), client.loop))


            
        except Exception as e:
            print(e)
    @tree.command(name="stop",description="Stops the player",guild=discord.Object(id=""))
    async def stop(interaction: discord.Interaction):
        try:
            voice_clients[interaction.guild_id].stop()
            await interaction.response.send_message(f"Leaving ;-;")
            await voice_clients[interaction.guild_id].disconnect()
            del voice_clients[interaction.guild_id]
            del queues[interaction.guild_id]
            await voice_clients[interaction.guild_id].cleanup()
        except Exception as e:
            print(e)
    @tree.command(name="pause",description="Pauses the player",guild=discord.Object(id=""))
    async def pause(interaction: discord.Interaction):
        try:
            await interaction.response.send_message(f"Paused")
            voice_clients[interaction.guild_id].pause()
        except Exception as e:
            print(e)
    @tree.command(name="resume",description="Resumes the player",guild=discord.Object(id=""))
    async def resume(interaction: discord.Interaction):
        try:
            await interaction.response.send_message(f"Resuming player")
            voice_clients[interaction.guild_id].resume()
        except Exception as e:
            print(e)
    @tree.command(name="skip",description="skips the player",guild=discord.Object(id=""))
    async def skip(interaction: discord.Interaction):
        try:
            await interaction.response.send_message(f"Skipping....")
            await playnext(interaction)
        except Exception as e:
            print(e)
            
    
    async def queue(interaction:discord.Interaction, song_url: str):
        if interaction.guild_id not in queues:
            queues[interaction.guild_id] = []
        queues[interaction.guild_id].append(song_url)
        try:
            await interaction.response.send_message(f"Added {song_url}")
        except Exception as e:
            print(e)

    async def playnext(interaction: discord.Interaction):
        if queues[interaction.guild_id] != []:
            link = queues[interaction.guild_id].pop(0)
            await play(interaction, link)
            
    
                
    client.run(TOKEN)
        

    