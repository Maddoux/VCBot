#!/usr/bin/env python3
"""
Simple Channel Archive System for VCBot
"""

import discord
from discord import app_commands
from datetime import datetime, timezone
from typing import Optional, List
import re
from pathlib import Path
import config
import asyncio
import html as html_lib

# Configuration
ARCHIVE_DATA_DIR = Path("data") / "archives"
ARCHIVE_DATA_DIR.mkdir(exist_ok=True)
RECORDS_TEAM_ROLE_ID = 1269061253964238919

# Track active archives by channel ID
active_archives = {}  # {channel_id: {"user_id": int, "stop_flag": bool}}

def escape_html(text: str) -> str:
    """Safely escape HTML in text"""
    return html_lib.escape(text)


def get_html_header(channel_name: str, guild_name: str, message_count: int = 0, archived_by: str = None, archive_date: str = None) -> str:
    """Generate HTML header with Discord-like styling"""
    escaped_channel = escape_html(channel_name)
    escaped_guild = escape_html(guild_name)
    
    archive_info = ""
    if archived_by and archive_date:
        archive_info = f"""
        <div class="archive-info">
            📁 Archive created by {escape_html(archived_by)} on {escape_html(archive_date)} • {message_count:,} messages
        </div>
        """
    
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>#{escaped_channel} - {escaped_guild}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ background-color: #36393f; color: #dcddde; font-family: Arial, sans-serif; font-size: 16px; }}
        .header {{ background-color: #2f3136; padding: 16px; border-bottom: 1px solid #202225; }}
        .channel-name {{ font-size: 24px; font-weight: bold; color: #ffffff; }}
        .guild-name {{ font-size: 14px; color: #b9bbbe; margin-top: 4px; }}
        .archive-info {{ font-size: 12px; color: #72767d; margin-top: 8px; padding: 8px; background-color: #202225; border-radius: 4px; }}
        .messages {{ padding: 16px; max-width: 1200px; margin: 0 auto; }}
        .message {{ padding: 8px 16px 8px 72px; margin-top: 8px; position: relative; min-height: 40px; }}
        .message:hover {{ background-color: rgba(4, 4, 5, 0.07); }}
        .avatar {{ position: absolute; left: 16px; top: 8px; width: 40px; height: 40px; border-radius: 50%; object-fit: cover; }}
        .username {{ font-weight: 500; color: #ffffff; font-size: 16px; margin-right: 8px; }}
        .bot-badge {{ background-color: #5865f2; color: #ffffff; font-size: 10px; padding: 2px 4px; border-radius: 3px; margin-left: 4px; font-weight: 600; }}
        .timestamp {{ color: #72767d; font-size: 12px; cursor: help; }}
        .edited {{ color: #72767d; font-size: 10px; margin-left: 4px; }}
        .content {{ color: #dcddde; margin-top: 4px; word-wrap: break-word; }}
        .reply {{ background-color: #2e3338; border-left: 4px solid #4e5058; padding: 4px 8px; margin-bottom: 4px; border-radius: 3px; font-size: 14px; }}
        .reply .reply-author {{ color: #00b0f4; font-weight: 500; }}
        .reply .reply-content {{ color: #b9bbbe; margin-top: 2px; }}
        .attachment {{ margin-top: 8px; max-width: 400px; }}
        .attachment img {{ max-width: 100%; border-radius: 4px; }}
        .reactions {{ margin-top: 8px; display: flex; flex-wrap: wrap; gap: 4px; }}
        .reaction {{ background-color: #2f3136; border: 1px solid #202225; border-radius: 4px; padding: 4px 8px; font-size: 14px; display: inline-flex; align-items: center; gap: 4px; }}
        .reaction:hover {{ background-color: #36393f; border-color: #72767d; }}
        .reaction-count {{ color: #b9bbbe; font-size: 12px; }}
        .embed {{ background-color: #2f3136; border-left: 4px solid #202225; border-radius: 4px; padding: 8px 12px; margin-top: 8px; max-width: 520px; }}
        .embed-author {{ display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }}
        .embed-author-icon {{ width: 24px; height: 24px; border-radius: 50%; }}
        .embed-author-name {{ color: #ffffff; font-weight: 500; font-size: 14px; }}
        .embed-title {{ color: #00b0f4; font-weight: 600; font-size: 16px; margin-bottom: 4px; }}
        .embed-description {{ color: #dcddde; font-size: 14px; margin-bottom: 8px; }}
        .embed-field {{ margin-bottom: 8px; }}
        .embed-field-name {{ color: #ffffff; font-weight: 600; font-size: 14px; margin-bottom: 2px; }}
        .embed-field-value {{ color: #b9bbbe; font-size: 14px; }}
        .embed-footer {{ color: #72767d; font-size: 12px; margin-top: 8px; }}
        .embed-image {{ max-width: 100%; border-radius: 4px; margin-top: 8px; }}
        .embed-thumbnail {{ max-width: 80px; max-height: 80px; border-radius: 4px; float: right; margin-left: 16px; }}
        .sticker {{ margin-top: 8px; }}
        .sticker img {{ max-width: 160px; max-height: 160px; }}
        .message-id {{ color: #72767d; font-size: 10px; margin-top: 4px; font-family: monospace; }}
        a {{ color: #00b0f4; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        code {{ background-color: #2f3136; padding: 2px 4px; border-radius: 3px; font-family: monospace; }}
    </style>
</head>
<body>
    <div class="header">
        <div class="channel-name">#{escaped_channel}</div>
        <div class="guild-name">{escaped_guild}</div>
        {archive_info}
    </div>
    <div class="messages">
"""

def get_html_footer() -> str:
    """Generate HTML footer"""
    return """
    </div>
</body>
</html>
"""

def format_content(content: str, msg) -> str:
    """Format message content with mention conversion"""
    if not content:
        return ""
    
    import re
    
    # Store mentions with placeholders BEFORE HTML escaping
    mention_map = {}
    placeholder_counter = [0]  # Use list to make it mutable in nested function
    
    def create_placeholder(replacement_text):
        placeholder = f"___MENTION_{placeholder_counter[0]}___"
        mention_map[placeholder] = replacement_text
        placeholder_counter[0] += 1
        return placeholder
    
    # User mentions: <@!ID> or <@ID>
    def replace_user_mention(match):
        user_id = int(match.group(1))
        # Check message mentions first (these are guaranteed to be available)
        if msg and msg.mentions:
            for mentioned_user in msg.mentions:
                if mentioned_user.id == user_id:
                    return create_placeholder(f'<span style="color: #00b0f4;">@{escape_html(mentioned_user.display_name)}</span>')
        # Fallback to guild lookup
        if msg and msg.guild:
            member = msg.guild.get_member(user_id)
            if member:
                return create_placeholder(f'<span style="color: #00b0f4;">@{escape_html(member.display_name)}</span>')
        return match.group(0)  # Keep original if not found
    
    # Role mentions: <@&ID>
    def replace_role_mention(match):
        role_id = int(match.group(1))
        # Check message role mentions
        if msg and msg.role_mentions:
            for mentioned_role in msg.role_mentions:
                if mentioned_role.id == role_id:
                    return create_placeholder(f'<span style="color: #00b0f4;">@{escape_html(mentioned_role.name)}</span>')
        # Fallback to guild lookup
        if msg and msg.guild:
            role = msg.guild.get_role(role_id)
            if role:
                return create_placeholder(f'<span style="color: #00b0f4;">@{escape_html(role.name)}</span>')
        return match.group(0)
    
    # Channel mentions: <#ID>
    def replace_channel_mention(match):
        channel_id = int(match.group(1))
        # Check message channel mentions
        if msg and msg.channel_mentions:
            for mentioned_channel in msg.channel_mentions:
                if mentioned_channel.id == channel_id:
                    return create_placeholder(f'<span style="color: #00b0f4;">#{escape_html(mentioned_channel.name)}</span>')
        # Fallback to guild lookup
        if msg and msg.guild:
            channel = msg.guild.get_channel(channel_id)
            if channel:
                return create_placeholder(f'<span style="color: #00b0f4;">#{escape_html(channel.name)}</span>')
        return match.group(0)
    
    # Replace mentions with placeholders first
    content = re.sub(r'<@!?(\d+)>', replace_user_mention, content)
    content = re.sub(r'<@&(\d+)>', replace_role_mention, content)
    content = re.sub(r'<#(\d+)>', replace_channel_mention, content)
    
    # Now escape HTML (this will escape any remaining < > & etc)
    content = escape_html(content)
    content = content.replace('\n', '<br>')
    
    # Convert URLs to links
    content = re.sub(r'(https?://[^\s&lt;&gt;]+)', r'<a href="\1" target="_blank">\1</a>', content)
    
    # Bold
    content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)
    
    # Code
    content = re.sub(r'`(.+?)`', r'<code>\1</code>', content)
    
    # Replace placeholders with actual mention HTML
    for placeholder, replacement in mention_map.items():
        content = content.replace(placeholder, replacement)
    
    return content
    
    return content

def generate_message_html(msg, guild) -> str:
    """Generate HTML for a single message"""
    # Full date and time with tooltip
    timestamp_short = msg.created_at.strftime("%I:%M %p")
    timestamp_full = msg.created_at.strftime("%B %d, %Y at %I:%M:%S %p")
    
    # Use actual avatar URL or fallback to colored circle
    avatar_url = msg.author.display_avatar.url if msg.author.display_avatar else None
    if avatar_url:
        avatar_html = f'<img class="avatar" src="{escape_html(avatar_url)}" alt="{escape_html(msg.author.display_name)}">'
    else:
        avatar_color = f"hsl({hash(msg.author.name) % 360}, 70%, 50%)"
        avatar_html = f'<div class="avatar" style="background-color: {avatar_color};"></div>'
    
    html = f'<div class="message">\n'
    html += f'  {avatar_html}\n'
    
    # Username with bot badge if applicable
    html += f'  <div class="username">{escape_html(msg.author.display_name)}'
    if msg.author.bot:
        html += '<span class="bot-badge">BOT</span>'
    html += '</div>\n'
    
    # Timestamp with full date on hover
    html += f'  <span class="timestamp" title="{escape_html(timestamp_full)}">{timestamp_short}</span>\n'
    
    # Show edit timestamp if edited
    if msg.edited_at:
        edited_time = msg.edited_at.strftime("%B %d, %Y at %I:%M:%S %p")
        html += f'  <span class="edited" title="Edited: {escape_html(edited_time)}">(edited)</span>\n'
    
    # Show replied message if this is a reply
    if msg.reference and msg.reference.resolved:
        replied_msg = msg.reference.resolved
        replied_author = replied_msg.author.display_name if hasattr(replied_msg, 'author') else "Unknown"
        replied_content = replied_msg.content[:100] if hasattr(replied_msg, 'content') and replied_msg.content else "[No content]"
        html += f'  <div class="reply">\n'
        html += f'    <span class="reply-author">@{escape_html(replied_author)}</span>\n'
        html += f'    <div class="reply-content">{escape_html(replied_content)}</div>\n'
        html += f'  </div>\n'
    
    # Message content
    if msg.content:
        html += f'  <div class="content">{format_content(msg.content, msg)}</div>\n'
    
    # Stickers
    if msg.stickers:
        for sticker in msg.stickers:
            html += f'  <div class="sticker">\n'
            if sticker.url:
                html += f'    <img src="{escape_html(sticker.url)}" alt="{escape_html(sticker.name)}" title="{escape_html(sticker.name)}">\n'
            else:
                html += f'    <span>[Sticker: {escape_html(sticker.name)}]</span>\n'
            html += f'  </div>\n'
    
    # Attachments
    if msg.attachments:
        for att in msg.attachments:
            if att.content_type and att.content_type.startswith('image/'):
                html += f'  <div class="attachment"><img src="{escape_html(att.url)}" alt="{escape_html(att.filename)}"></div>\n'
            else:
                html += f'  <div class="attachment"><a href="{escape_html(att.url)}">{escape_html(att.filename)}</a></div>\n'
    
    # Embeds
    if msg.embeds:
        for embed in msg.embeds:
            border_color = f"#{embed.color.value:06x}" if embed.color else "#202225"
            html += f'  <div class="embed" style="border-left-color: {border_color};">\n'
            
            # Embed author
            if embed.author:
                html += f'    <div class="embed-author">\n'
                if embed.author.icon_url:
                    html += f'      <img class="embed-author-icon" src="{escape_html(embed.author.icon_url)}">\n'
                if embed.author.name:
                    html += f'      <span class="embed-author-name">{escape_html(embed.author.name)}</span>\n'
                html += f'    </div>\n'
            
            # Embed title
            if embed.title:
                if embed.url:
                    html += f'    <a href="{escape_html(embed.url)}" class="embed-title">{escape_html(embed.title)}</a>\n'
                else:
                    html += f'    <div class="embed-title">{escape_html(embed.title)}</div>\n'
            
            # Embed thumbnail
            if embed.thumbnail:
                html += f'    <img class="embed-thumbnail" src="{escape_html(embed.thumbnail.url)}">\n'
            
            # Embed description
            if embed.description:
                html += f'    <div class="embed-description">{escape_html(embed.description[:500])}</div>\n'
            
            # Embed fields
            if embed.fields:
                for field in embed.fields:
                    html += f'    <div class="embed-field">\n'
                    html += f'      <div class="embed-field-name">{escape_html(field.name)}</div>\n'
                    html += f'      <div class="embed-field-value">{escape_html(field.value)}</div>\n'
                    html += f'    </div>\n'
            
            # Embed image
            if embed.image:
                html += f'    <img class="embed-image" src="{escape_html(embed.image.url)}">\n'
            
            # Embed footer
            if embed.footer:
                footer_text = embed.footer.text
                if embed.timestamp:
                    footer_text += f" • {embed.timestamp.strftime('%B %d, %Y at %I:%M %p')}"
                html += f'    <div class="embed-footer">{escape_html(footer_text)}</div>\n'
            
            html += f'  </div>\n'
    
    # Reactions
    if msg.reactions:
        html += f'  <div class="reactions">\n'
        for reaction in msg.reactions:
            emoji_display = str(reaction.emoji)
            html += f'    <div class="reaction" title="{reaction.count} reaction(s)">\n'
            html += f'      <span>{escape_html(emoji_display)}</span>\n'
            html += f'      <span class="reaction-count">{reaction.count}</span>\n'
            html += f'    </div>\n'
        html += f'  </div>\n'
    
    # Message ID for reference
    html += f'  <div class="message-id">ID: {msg.id}</div>\n'
    
    html += '</div>\n'
    return html

async def fetch_all_messages(channel, limit, progress_callback):
    """Fetch all messages from channel"""
    global active_archives
    
    messages = []
    batch_size = 100
    before_msg = None
    
    print(f"📥 Fetching messages from #{channel.name}")
    
    while True:
        # Check channel-specific stop flag
        if channel.id in active_archives and active_archives[channel.id].get("stop_flag"):
            print(f"🛑 Stopped at {len(messages)} messages")
            break
        
        try:
            batch = []
            async for msg in channel.history(limit=batch_size, before=before_msg, oldest_first=False):
                batch.append(msg)
            
            if not batch:
                print(f"✅ End reached: {len(messages)} total messages")
                break
            
            messages.extend(batch)
            before_msg = batch[-1]
            
            if progress_callback:
                await progress_callback(len(messages), limit)
            
            if limit and len(messages) >= limit:
                messages = messages[:limit]
                print(f"✅ Limit reached: {limit} messages")
                break
            
            await asyncio.sleep(0.1)
            
        except Exception as e:
            print(f"⚠️ Fetch error: {e}")
            await asyncio.sleep(2)
            continue
    
    messages.reverse()
    return messages

async def create_archive(channel, messages, archived_by: str = None):
    """Create HTML archive file"""
    archive_date_display = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    
    # Build clean filename
    server_name = channel.guild.name
    channel_name = channel.name
    
    # Check if this is a thread
    thread_name = None
    if isinstance(channel, discord.Thread):
        thread_name = channel.name
        # Get parent channel name
        if channel.parent:
            channel_name = channel.parent.name
    
    # Build filename parts
    if thread_name:
        base_filename = f"{server_name} - {channel_name} - {thread_name}"
    else:
        base_filename = f"{server_name} - {channel_name}"
    
    # Sanitize filename (remove invalid characters)
    base_filename = re.sub(r'[<>:"/\\|?*]', '', base_filename)
    
    # Check if file exists and add number suffix if needed
    filename = f"{base_filename}.html"
    filepath = ARCHIVE_DATA_DIR / filename
    counter = 1
    while filepath.exists():
        filename = f"{base_filename} ({counter}).html"
        filepath = ARCHIVE_DATA_DIR / filename
        counter += 1
    
    print(f"📝 Creating HTML with {len(messages)} messages")
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(get_html_header(
            channel.name, 
            channel.guild.name, 
            len(messages),
            archived_by,
            archive_date_display
        ))
        
        for msg in messages:
            f.write(generate_message_html(msg, channel.guild))
        
        f.write(get_html_footer())
    
    print(f"✅ Archive saved: {filepath}")
    return str(filepath)

@app_commands.command(name="archive", description="Archive channel to HTML")
@app_commands.describe(
    channel="Channel to archive (default: current)",
    limit="Max messages (default: all)"
)
async def archive_channel(interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None, limit: Optional[int] = None):
    """Archive a channel"""
    global active_archives
    
    # Check permissions
    user_roles = [role.id for role in interaction.user.roles]
    if config.ADMIN_ROLE_ID not in user_roles and RECORDS_TEAM_ROLE_ID not in user_roles:
        await interaction.response.send_message("❌ No permission", ephemeral=True)
        return
    
    if channel is None:
        channel = interaction.channel
    
    # Check if this specific channel is already being archived
    if channel.id in active_archives:
        archiver_id = active_archives[channel.id]["user_id"]
        await interaction.response.send_message(f"❌ #{channel.name} is already being archived by <@{archiver_id}>", ephemeral=True)
        return
    
    if limit is not None and limit <= 0:
        await interaction.response.send_message("❌ Limit must be positive", ephemeral=True)
        return
    
    await interaction.response.defer()
    
    # Register this archive
    active_archives[channel.id] = {"user_id": interaction.user.id, "stop_flag": False}
    
    try:
        progress_msg = None
        last_update = datetime.now()
        
        async def update_progress(current, total):
            nonlocal progress_msg, last_update
            
            now = datetime.now()
            if (now - last_update).total_seconds() < 3:
                return
            last_update = now
            
            embed = discord.Embed(
                title=f"📥 Archiving #{channel.name}",
                color=discord.Color.blue()
            )
            
            if total:
                percent = (current / total) * 100
                bar_len = 20
                filled = int(bar_len * current // total)
                bar = "█" * filled + "░" * (bar_len - filled)
                embed.add_field(
                    name="Progress",
                    value=f"`{bar}` {percent:.1f}%\n{current:,} / {total:,} messages",
                    inline=False
                )
            else:
                embed.add_field(name="Fetched", value=f"{current:,} messages", inline=False)
            
            try:
                if progress_msg:
                    await progress_msg.edit(embed=embed)
                else:
                    progress_msg = await interaction.followup.send(embed=embed, wait=True)
            except:
                pass
        
        print(f"🚀 Archive by {interaction.user.name} for #{channel.name}")
        messages = await fetch_all_messages(channel, limit, update_progress)
        
        if not messages:
            await interaction.followup.send("❌ No messages found", ephemeral=True)
            return
        
        # Check if stopped
        if channel.id in active_archives and active_archives[channel.id].get("stop_flag"):
            await interaction.followup.send("🛑 Stopped", ephemeral=True)
            return
        
        filepath = await create_archive(channel, messages, interaction.user.display_name)
        
        embed = discord.Embed(
            title="✅ Archive Complete",
            description=f"Archived **#{channel.name}**",
            color=discord.Color.green()
        )
        
        embed.add_field(name="Messages", value=f"{len(messages):,}", inline=True)
        embed.add_field(name="Size", value=f"{Path(filepath).stat().st_size / 1024:.1f} KB", inline=True)
        
        file = discord.File(filepath)
        
        try:
            if progress_msg:
                await progress_msg.edit(embed=embed, attachments=[file])
            else:
                await interaction.followup.send(embed=embed, file=file)
        except:
            await interaction.followup.send(embed=embed, file=file)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
        print(f"❌ Archive error: {e}")
    finally:
        # Clean up this channel's archive tracking
        if channel.id in active_archives:
            del active_archives[channel.id]

@app_commands.command(name="archivestop", description="Stop archive in this channel")
async def archive_stop(interaction: discord.Interaction):
    """Stop archive for current channel"""
    global active_archives
    
    user_roles = [role.id for role in interaction.user.roles]
    if config.ADMIN_ROLE_ID not in user_roles and RECORDS_TEAM_ROLE_ID not in user_roles:
        await interaction.response.send_message("❌ No permission", ephemeral=True)
        return
    
    channel = interaction.channel
    
    # Check if this channel has an active archive
    if channel.id not in active_archives:
        await interaction.response.send_message("❌ No archive running in this channel", ephemeral=True)
        return
    
    # Set stop flag for this channel
    active_archives[channel.id]["stop_flag"] = True
    archiver_id = active_archives[channel.id]["user_id"]
    
    embed = discord.Embed(
        title="🛑 Stop Requested",
        description=f"Archive for **#{channel.name}** will stop after current batch",
        color=discord.Color.orange()
    )
    
    embed.add_field(name="Started By", value=f"<@{archiver_id}>", inline=True)
    embed.add_field(name="Stopped By", value=interaction.user.mention, inline=True)
    
    await interaction.response.send_message(embed=embed)

# Export
archive = archive_channel
