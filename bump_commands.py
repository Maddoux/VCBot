"""
Bump Reminder Commands System for VCBot
Allows admins to set up recurring bump reminders in specified channels
"""

import discord
from discord import app_commands
from discord.ext import commands
import json
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Configuration
from config import ADMIN_ROLE_ID

# DISBOARD bot ID
DISBOARD_BOT_ID = 302050872383242240

# File path for storing bump settings
BUMP_DATA_FILE = Path("data") / "bump_settings.json"

# Store active bump tasks and last bump times
active_bump_tasks: dict[int, asyncio.Task] = {}  # guild_id -> task
last_bump_time: dict[int, datetime] = {}  # guild_id -> last bump datetime
_bump_initialized: set[int] = set()  # Track which guilds have been initialized

async def load_bump_data() -> dict:
    """Load bump settings from JSON file"""
    try:
        BUMP_DATA_FILE.parent.mkdir(exist_ok=True)
        
        if BUMP_DATA_FILE.exists():
            with open(BUMP_DATA_FILE, 'r') as f:
                return json.load(f)
        else:
            return {}
    except Exception as e:
        print(f"Error loading bump data: {e}")
        return {}

async def save_bump_data(data: dict) -> bool:
    """Save bump settings to JSON file"""
    try:
        BUMP_DATA_FILE.parent.mkdir(exist_ok=True)
        
        with open(BUMP_DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving bump data: {e}")
        return False

async def send_bump_reminder(client: discord.Client, guild_id: int, channel_id: int, message: str):
    """Send a bump reminder to the specified channel"""
    try:
        channel = client.get_channel(channel_id)
        if not channel:
            print(f"Bump reminder channel {channel_id} not found for guild {guild_id}")
            return False
        
        # Send the message - Discord will automatically handle any role/user mentions in the message
        await channel.send(message)
        print(f"Sent bump reminder to #{channel.name} in guild {guild_id}")
        return True
        
    except Exception as e:
        print(f"Error sending bump reminder: {e}")
        return False

async def bump_reminder_loop(client: discord.Client, guild_id: int):
    """Background task that sends ONE reminder after interval, then waits for bump"""
    awaiting_bump = False  # True = we sent a reminder and are waiting for someone to bump
    
    while True:
        try:
            # Load current settings
            bump_data = await load_bump_data()
            guild_settings = bump_data.get(str(guild_id))
            
            if not guild_settings or not guild_settings.get('enabled', False):
                break
            
            channel_id = guild_settings.get('channel_id')
            message = guild_settings.get('message', '🔔 Time to bump the server!')
            interval_hours = guild_settings.get('interval_hours', 2)
            interval_seconds = interval_hours * 3600
            
            # Get current state
            now = datetime.now(timezone.utc)
            last_bump = last_bump_time.get(guild_id)
            
            if awaiting_bump:
                # We already sent a reminder, just wait for a bump
                # Check if a bump happened
                current_last_bump = last_bump_time.get(guild_id)
                if current_last_bump and (not last_bump or current_last_bump > last_bump):
                    # Bump detected! Reset state and wait for next interval
                    awaiting_bump = False
                    last_bump = current_last_bump
                else:
                    # Still waiting, check again in 30 seconds
                    await asyncio.sleep(30)
                continue
            
            # Calculate wait time
            if last_bump:
                elapsed = (now - last_bump).total_seconds()
                wait_time = interval_seconds - elapsed
            else:
                wait_time = interval_seconds
            
            if wait_time > 0:
                await asyncio.sleep(wait_time)
                continue  # Re-check everything after sleeping
            
            # Time's up - send ONE reminder
            await send_bump_reminder(client, guild_id, channel_id, message)
            awaiting_bump = True
            
        except asyncio.CancelledError:
            break
        except Exception:
            await asyncio.sleep(60)

def start_bump_task(client: discord.Client, guild_id: int):
    """Start the bump reminder task for a guild"""
    # Cancel existing task if any
    if guild_id in active_bump_tasks:
        task = active_bump_tasks[guild_id]
        if not task.done():
            task.cancel()
            # Wait a moment for cancellation
            try:
                asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.1))
            except:
                pass
        del active_bump_tasks[guild_id]
    
    # Create new task
    task = asyncio.create_task(bump_reminder_loop(client, guild_id))
    active_bump_tasks[guild_id] = task

def stop_bump_task(guild_id: int):
    """Stop the bump reminder task for a guild"""
    if guild_id in active_bump_tasks:
        active_bump_tasks[guild_id].cancel()
        del active_bump_tasks[guild_id]
        print(f"Stopped bump reminder task for guild {guild_id}")

# Command group
bump_group = app_commands.Group(name="bump", description="Bump reminder commands")

@bump_group.command(name="reminder", description="Set up a recurring bump reminder")
@app_commands.describe(
    channel="The channel to send bump reminders to",
    message="The reminder message (can include role/user mentions)",
    time="Interval between reminders in hours (default: 2)"
)
async def bump_reminder_command(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    message: str,
    time: Optional[float] = 2.0
):
    """Set up a recurring bump reminder"""
    # Check if user has admin role
    user_roles = [role.id for role in interaction.user.roles]
    if ADMIN_ROLE_ID not in user_roles:
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    # Validate time
    if time <= 0:
        await interaction.response.send_message("Time interval must be greater than 0 hours.", ephemeral=True)
        return
    
    if time < 0.1:  # Minimum 6 minutes to prevent spam
        await interaction.response.send_message("Time interval must be at least 0.1 hours (6 minutes).", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    try:
        guild_id = interaction.guild_id
        
        # Load existing data
        bump_data = await load_bump_data()
        
        # Save new settings
        bump_data[str(guild_id)] = {
            'enabled': True,
            'channel_id': channel.id,
            'message': message,
            'interval_hours': time,
            'set_by': interaction.user.id,
            'set_at': datetime.now(timezone.utc).isoformat()
        }
        
        await save_bump_data(bump_data)
        
        # Start the bump task
        start_bump_task(interaction.client, guild_id)
        
        # Format time display
        if time == int(time):
            time_display = f"{int(time)} hour{'s' if time != 1 else ''}"
        else:
            time_display = f"{time} hours"
        
        embed = discord.Embed(
            title="✅ Bump Reminder Set",
            description="Your bump reminder has been configured successfully!",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        
        embed.add_field(name="Channel", value=channel.mention, inline=True)
        embed.add_field(name="Interval", value=time_display, inline=True)
        embed.add_field(name="Message", value=message[:1024], inline=False)
        embed.set_footer(text=f"Set by {interaction.user.display_name}")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
        # Send an initial test message
        await channel.send(f"📢 **Bump reminder activated!** You'll receive reminders every {time_display}.\n\nFirst reminder message preview:\n{message}")
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error setting bump reminder: {str(e)}", ephemeral=True)
        print(f"Error in bump_reminder_command: {e}")

@bump_group.command(name="stop", description="Stop the bump reminder")
async def bump_stop_command(interaction: discord.Interaction):
    """Stop the bump reminder for this server"""
    # Check if user has admin role
    user_roles = [role.id for role in interaction.user.roles]
    if ADMIN_ROLE_ID not in user_roles:
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    try:
        guild_id = interaction.guild_id
        
        # Load existing data
        bump_data = await load_bump_data()
        
        if str(guild_id) not in bump_data or not bump_data[str(guild_id)].get('enabled', False):
            await interaction.followup.send("❌ No active bump reminder found for this server.", ephemeral=True)
            return
        
        # Disable the reminder
        bump_data[str(guild_id)]['enabled'] = False
        bump_data[str(guild_id)]['stopped_by'] = interaction.user.id
        bump_data[str(guild_id)]['stopped_at'] = datetime.now(timezone.utc).isoformat()
        
        await save_bump_data(bump_data)
        
        # Stop the task
        stop_bump_task(guild_id)
        
        embed = discord.Embed(
            title="🛑 Bump Reminder Stopped",
            description="The bump reminder has been disabled.",
            color=0xff6b6b,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text=f"Stopped by {interaction.user.display_name}")
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error stopping bump reminder: {str(e)}", ephemeral=True)
        print(f"Error in bump_stop_command: {e}")

@bump_group.command(name="status", description="Check the current bump reminder status")
async def bump_status_command(interaction: discord.Interaction):
    """Check the current bump reminder status"""
    await interaction.response.defer(ephemeral=True)
    
    try:
        guild_id = interaction.guild_id
        
        # Load existing data
        bump_data = await load_bump_data()
        guild_settings = bump_data.get(str(guild_id))
        
        if not guild_settings:
            embed = discord.Embed(
                title="📊 Bump Reminder Status",
                description="No bump reminder has been configured for this server.",
                color=0x808080,
                timestamp=datetime.now(timezone.utc)
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        is_enabled = guild_settings.get('enabled', False)
        channel_id = guild_settings.get('channel_id')
        message = guild_settings.get('message', 'Not set')
        interval = guild_settings.get('interval_hours', 2)
        set_by = guild_settings.get('set_by')
        set_at = guild_settings.get('set_at')
        
        channel = interaction.client.get_channel(channel_id)
        channel_display = channel.mention if channel else f"Unknown ({channel_id})"
        
        # Format time display
        if interval == int(interval):
            time_display = f"{int(interval)} hour{'s' if interval != 1 else ''}"
        else:
            time_display = f"{interval} hours"
        
        embed = discord.Embed(
            title="📊 Bump Reminder Status",
            color=0x00ff00 if is_enabled else 0xff6b6b,
            timestamp=datetime.now(timezone.utc)
        )
        
        embed.add_field(name="Status", value="✅ Active" if is_enabled else "❌ Disabled", inline=True)
        embed.add_field(name="Channel", value=channel_display, inline=True)
        embed.add_field(name="Interval", value=time_display, inline=True)
        embed.add_field(name="Message", value=message[:1024], inline=False)
        
        if set_by:
            embed.add_field(name="Set By", value=f"<@{set_by}>", inline=True)
        
        if set_at:
            try:
                set_dt = datetime.fromisoformat(set_at.replace('Z', '+00:00'))
                embed.add_field(name="Set At", value=f"<t:{int(set_dt.timestamp())}:R>", inline=True)
            except:
                pass
        
        # Check if task is actually running
        task_running = guild_id in active_bump_tasks and not active_bump_tasks[guild_id].done()
        if is_enabled and not task_running:
            embed.add_field(
                name="⚠️ Warning",
                value="The reminder is enabled but the task is not running. Use `/bump reminder` to restart it.",
                inline=False
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error checking bump status: {str(e)}", ephemeral=True)
        print(f"Error in bump_status_command: {e}")

async def initialize_bump_reminders(client: discord.Client):
    """Initialize bump reminders from saved data on bot startup"""
    global _bump_initialized
    
    try:
        bump_data = await load_bump_data()
        
        started_count = 0
        for guild_id_str, settings in bump_data.items():
            if settings.get('enabled', False):
                guild_id = int(guild_id_str)
                
                # Skip if already initialized
                if guild_id in _bump_initialized:
                    continue
                
                # Verify the guild and channel still exist
                channel = client.get_channel(settings.get('channel_id'))
                if channel:
                    # Load last bump time if saved
                    last_bump_str = settings.get('last_bump_time')
                    if last_bump_str:
                        try:
                            last_bump_time[guild_id] = datetime.fromisoformat(last_bump_str.replace('Z', '+00:00'))
                        except:
                            pass
                    
                    start_bump_task(client, guild_id)
                    _bump_initialized.add(guild_id)
                    started_count += 1
        
        if started_count > 0:
            print(f"✅ Initialized {started_count} bump reminder(s)")
            
    except Exception as e:
        print(f"Error initializing bump reminders: {e}")

async def handle_disboard_message(message: discord.Message):
    """Handle messages from DISBOARD bot to detect successful bumps"""
    # Only check messages from DISBOARD bot
    if message.author.id != DISBOARD_BOT_ID:
        return
    
    # Make sure we're in a guild
    if not message.guild:
        return
    
    # Check if message has embeds with "Bump done!" text
    for embed in message.embeds:
        # Check embed description for "Bump done!"
        if embed.description and "Bump done!" in embed.description:
            guild_id = message.guild.id
            now = datetime.now(timezone.utc)
            
            # Update last bump time
            last_bump_time[guild_id] = now
            print(f"🔔 DISBOARD bump detected for guild {guild_id} at {now.isoformat()}")
            
            # Save to persistent storage
            bump_data = await load_bump_data()
            if str(guild_id) in bump_data:
                bump_data[str(guild_id)]['last_bump_time'] = now.isoformat()
                await save_bump_data(bump_data)
            
            # Note: We don't restart the task here anymore
            # The loop will check last_bump_time and recalculate wait time
            # This prevents duplicate tasks and race conditions
            
            return

def setup_bump_message_handler(client: discord.Client):
    """Set up message handler for DISBOARD bump detection"""
    original_on_message = getattr(client, '_original_bump_on_message', None)
    
    async def on_message(message: discord.Message):
        # Call original handler if it exists
        if original_on_message:
            await original_on_message(message)
        
        # Handle DISBOARD messages
        await handle_disboard_message(message)
    
    # Store original handler
    if hasattr(client, 'on_message') and not hasattr(client, '_original_bump_on_message'):
        client._original_bump_on_message = client.on_message
    
    # Set up our handler
    client.on_message = on_message
    print("✅ DISBOARD bump detection handler set up")

def setup_bump_commands(tree):
    """Register bump commands with the command tree"""
    tree.add_command(bump_group)
    print("✅ Bump commands registered successfully")
