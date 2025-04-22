import discord
from discord import app_commands

def register_commands(tree, client, music_player, guild_id):
    """Register all slash commands with the command tree"""
    
    @tree.command(
        name="play",
        description="Play a song",
        guild=discord.Object(id=guild_id)
    )
    @app_commands.describe(song_title="Enter song title or YouTube URL")
    async def play(interaction: discord.Interaction, song_title: str):
        # Connect to voice channel first
        if not await music_player.connect_to_voice(interaction):
            await interaction.response.send_message("You need to join a voice channel first!")
            return
            
        # Play the song
        success, message = await music_player.play_song(interaction, song_title)
        
        try:
            await interaction.response.send_message(message)
        except discord.errors.InteractionResponded:
            await interaction.followup.send(message)

    @tree.command(
        name="stop",
        description="Stops the player and disconnects the bot",
        guild=discord.Object(id=guild_id)
    )
    async def stop(interaction: discord.Interaction):
        try:
            guild_id = interaction.guild_id
            if guild_id in music_player.voice_clients:
                music_player.voice_clients[guild_id].stop()
                await interaction.response.send_message("Leaving ;-;")
                await music_player.voice_clients[guild_id].disconnect()
                del music_player.voice_clients[guild_id]
                
                if guild_id in music_player.queues:
                    del music_player.queues[guild_id]
            else:
                await interaction.response.send_message("Nothing is playing!")
        except Exception as e:
            print(f"Error in stop command: {e}")
            await interaction.response.send_message("Failed to stop playback!")

    @tree.command(
        name="pause",
        description="Pauses the player",
        guild=discord.Object(id=guild_id)
    )
    async def pause(interaction: discord.Interaction):
        try:
            guild_id = interaction.guild_id
            if guild_id in music_player.voice_clients and music_player.voice_clients[guild_id].is_playing():
                music_player.voice_clients[guild_id].pause()
                await interaction.response.send_message("Paused")
            else:
                await interaction.response.send_message("Nothing is playing!")
        except Exception as e:
            print(f"Error in pause command: {e}")
            await interaction.response.send_message("Failed to pause playback!")

    @tree.command(
        name="resume",
        description="Resumes the player",
        guild=discord.Object(id=guild_id)
    )
    async def resume(interaction: discord.Interaction):
        try:
            guild_id = interaction.guild_id
            if guild_id in music_player.voice_clients and music_player.voice_clients[guild_id].is_paused():
                music_player.voice_clients[guild_id].resume()
                await interaction.response.send_message("Resuming player")
            else:
                await interaction.response.send_message("Nothing is paused!")
        except Exception as e:
            print(f"Error in resume command: {e}")
            await interaction.response.send_message("Failed to resume playback!")

    @tree.command(
        name="skip",
        description="Skips the current song",
        guild=discord.Object(id=guild_id)
    )
    async def skip(interaction: discord.Interaction):
        try:
            guild_id = interaction.guild_id
            
            # Check if we have a queue for this guild
            if guild_id not in music_player.queues or not music_player.queues[guild_id]:
                await interaction.response.send_message("No songs in queue to skip to!")
                return
                
            # Stop current playback if playing
            if guild_id in music_player.voice_clients and music_player.voice_clients[guild_id].is_playing():
                music_player.voice_clients[guild_id].stop()
            
            await interaction.response.send_message("Skipping to next song...")
            
            # Manually trigger play_next with the guild_id
            await music_player.play_next(guild_id, client.loop, client)
            
        except Exception as e:
            print(f"Error in skip function: {e}")
            try:
                await interaction.response.send_message("Failed to skip. Is anything playing?")
            except discord.errors.InteractionResponded:
                await interaction.followup.send("Failed to skip. Is anything playing?")

    @tree.command(
        name="queue",
        description="Shows the current song queue",
        guild=discord.Object(id=guild_id)
    )
    async def queue(interaction: discord.Interaction):
        guild_id = interaction.guild_id
        
        if guild_id not in music_player.queues or not music_player.queues[guild_id]:
            await interaction.response.send_message("The queue is empty!")
            return
            
        # Get song titles for songs in queue
        queue_list = []
        position = 1
        
        for song_url in music_player.queues[guild_id][:10]:  # Limit to first 10 songs
            try:
                song_url, title = await music_player.search_youtube(song_url)
                queue_list.append(f"{position}. {title}")
                position += 1
            except:
                queue_list.append(f"{position}. Unknown song")
                position += 1
                
        # Format the queue message
        queue_message = "**Current Queue:**\n" + "\n".join(queue_list)
        
        if len(music_player.queues[guild_id]) > 10:
            queue_message += f"\n\n...and {len(music_player.queues[guild_id]) - 10} more songs"
            
        await interaction.response.send_message(queue_message)