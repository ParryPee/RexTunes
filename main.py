import discord
import os
from dotenv import load_dotenv
from discord import app_commands
from music_player import MusicPlayer
from command_handler import register_commands

def run_bot():
    # Load environment variables
    load_dotenv()
    TOKEN = os.getenv("token")
    GUILD_ID = os.getenv("server_id")
    
    # Set up Discord client
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)
    tree = app_commands.CommandTree(client)
    
    # Initialize music player
    music_player = MusicPlayer()
    
    # Register commands with the command tree
    register_commands(tree, client, music_player, GUILD_ID)

    @client.event
    async def on_ready():
        # Sync for a single guild
        await tree.sync(guild=discord.Object(id=GUILD_ID))
        # For all guilds: await tree.sync()
        print(f"{client.user} is now ready.")

    # Run the client
    client.run(TOKEN)

if __name__ == "__main__":
    run_bot()