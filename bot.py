#!/usr/bin/env python3
"""
VCBot - Simplified Petition-Only Bot
Only contains petition system functionality

Python 3.13+ Ready: Uses modern async/await syntax and typing features
"""

import os
import sys
import discord
from discord.ext import commands
from pathlib import Path
from datetime import datetime, timezone

# Add current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Import configuration and command systems
import config
import petition_commands
import faceclaim_commands
import archive_commands
import ping_commands
import party_role_enforcement
import bump_commands
import page_watcher

# =============================================================================
# DISCORD CLIENT SETUP
# =============================================================================

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.reactions = True

client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)

# =============================================================================
# COMMAND REGISTRATION
# =============================================================================

# Register petition command
if petition_commands:
    try:
        petition_commands.setup_petition_commands(tree)
        print("Petition commands registered")
    except Exception as e:
        print(f"Failed to register petition command: {e}")

# Register faceclaim commands
if faceclaim_commands:
    try:
        tree.add_command(faceclaim_commands.claim)
        tree.add_command(faceclaim_commands.see)
        tree.add_command(faceclaim_commands.kill)
        tree.add_command(faceclaim_commands.override)
        print("Face claim commands registered")
    except Exception as e:
        print(f"Failed to register faceclaim commands: {e}")

# Register archive command
if archive_commands:
    try:
        tree.add_command(archive_commands.archive)
        tree.add_command(archive_commands.archive_stop)
        print("Archive commands registered")
    except Exception as e:
        print(f"Failed to register archive commands: {e}")

# Register ping commands
if ping_commands:
    try:
        ping_commands.setup_ping_commands(tree)
        print("Ping commands registered")
    except Exception as e:
        print(f"Failed to register ping commands: {e}")

# Register bump commands
if bump_commands:
    try:
        bump_commands.setup_bump_commands(tree)
        print("Bump commands registered")
    except Exception as e:
        print(f"Failed to register bump commands: {e}")

# Register sync command (admin-only manual command syncing)
@tree.command(name="sync", description="Admin only: Manually sync all bot commands")
async def sync_commands(interaction: discord.Interaction):
    """Manually sync all bot commands"""
    # Check if user has admin role
    if config.ADMIN_ROLE_ID not in [role.id for role in interaction.user.roles]:
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Sync commands globally
        synced_global = await tree.sync()
        
        # Also sync for the current guild if we're in one
        guild_sync_msg = ""
        if interaction.guild:
            tree.copy_global_to(guild=interaction.guild)
            synced_guild = await tree.sync(guild=interaction.guild)
            guild_sync_msg = f"\nGuild sync: {len(synced_guild)} commands"
        
        embed = discord.Embed(
            title="Commands Synced Successfully",
            description=f"Global sync: {len(synced_global)} commands{guild_sync_msg}",
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc)
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        print(f"Manual sync completed - Global: {len(synced_global)}, Guild: {len(synced_guild) if interaction.guild else 0}")
        
    except Exception as e:
        await interaction.followup.send(f"Failed to sync commands: {str(e)}", ephemeral=True)
        print(f"Manual sync failed: {e}")

# Setup bot permissions

# =============================================================================
# EVENT HANDLERS
# =============================================================================

@client.event
async def on_ready():
    """Bot startup initialization."""
    print(f"Logged in as {client.user}")
    
    # Initialize guild-specific data structure
    from file_utils import ensure_directories
    ensure_directories()
    
    # Display channel information
    guild = client.get_guild(config.GUILD_ID)
    if guild:
        print(f"Connected to guild: {guild.name}")
        
        # Check for petition channels
        petition_channel = client.get_channel(petition_commands.PETITIONS_CHANNEL_ID)
        submission_channel = client.get_channel(petition_commands.PETITION_SUBMISSION_CHANNEL_ID)
        
        if petition_channel:
            print(f"Petition Channel: {petition_channel.name}")
        else:
            print("Petition Channel: Not Found")
            
        if submission_channel:
            print(f"Submission Channel: {submission_channel.name}")
        else:
            print("Submission Channel: Not Found")
    
    # Initialize petition system handlers
    if petition_commands:
        try:
            petition_commands.setup_petition_handlers(client)
            print("Petition system ready")
        except Exception as e:
            print(f"Failed to initialize petition handlers: {e}")
    
    # Initialize party role enforcement
    if party_role_enforcement:
        try:
            party_role_enforcement.setup_party_enforcement(client)
        except Exception as e:
            print(f"Failed to initialize party enforcement: {e}")
    
    # Initialize bump reminders
    if bump_commands:
        try:
            bump_commands.setup_bump_message_handler(client)
            await bump_commands.initialize_bump_reminders(client)
            print("Bump reminders initialized")
        except Exception as e:
            print(f"Failed to initialize bump reminders: {e}")
    
    # Initialize page watcher (silent)
    try:
        page_watcher.setup_page_watcher(client)
    except:
        pass
    
    # Smart command sync
    print("Checking command sync...")
    
    try:
        if config.GUILD_ID:
            guild_obj = discord.Object(id=config.GUILD_ID)
            
            # Get existing commands
            try:
                existing = await tree.fetch_commands(guild=guild_obj)
            except:
                existing = []
            
            # Get local commands
            local = tree.get_commands()
            
            existing_names = {cmd.name for cmd in existing}
            local_names = {cmd.name for cmd in local}
            
            added = local_names - existing_names
            removed = existing_names - local_names
            
            if added or removed or len(existing) == 0:
                if len(existing) == 0:
                    print("No commands found in Discord, forcing initial sync...")
                else:
                    print("Syncing commands...")
                
                tree.copy_global_to(guild=guild_obj)
                synced = await tree.sync(guild=guild_obj)
                print(f"Synced {len(synced)} commands")
                
                if removed:
                    print(f"   Removed: {', '.join(sorted(removed))}")
                if added:
                    print(f"   Added: {', '.join(sorted(added))}")
            else:
                print("Commands already in sync")
                
    except Exception as e:
        print(f"Command sync error: {e}")
    
    # Show registered commands for debugging
    print(f"Bot ready! Registered {len(tree.get_commands())} commands:")
    for cmd in tree.get_commands():
        print(f"  - /{cmd.name}: {cmd.description}")
    
    print("VCBot is ready!")

@client.event
async def on_command_error(ctx, error):
    """Handle command errors."""
    if isinstance(error, commands.CommandNotFound):
        return  # Ignore unknown commands
    
    print(f"Command error: {error}")

@client.event
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    """Handle application command errors."""
    if not interaction.response.is_done():
        await interaction.response.send_message(
            f"An error occurred: {str(error)}", 
            ephemeral=True
        )
    print(f"App command error: {error}")

# =============================================================================
# MAIN FUNCTION
# =============================================================================

def main():
    """Main entry point."""
    print("VCBot (Petition-Only) starting...")
    
    # Verify token exists
    if not config.DISCORD_TOKEN:
        print("DISCORD_TOKEN not found in environment variables!")
        return
    
    # Start the bot
    try:
        client.run(config.DISCORD_TOKEN)
    except Exception as e:
        print(f"Failed to start bot: {e}")

if __name__ == "__main__":
    main()