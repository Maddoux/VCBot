"""
Ping Commands System for VCBot - Enhanced Version
Allows admins to create role ping permissions with multiple users and roles
"""

import discord
from discord import app_commands
from discord.ext import commands
import json
import asyncio
from datetime import datetime, timezone
import os

# Configuration
from config import ADMIN_ROLE_ID

# File path for storing ping permissions
PING_DATA_FILE = "data/ping_permissions.json"

async def load_ping_data() -> dict:
    """Load ping permissions from JSON file"""
    try:
        os.makedirs(os.path.dirname(PING_DATA_FILE), exist_ok=True)
        
        if os.path.exists(PING_DATA_FILE):
            with open(PING_DATA_FILE, 'r') as f:
                return json.load(f)
        else:
            return {}
    except Exception as e:
        print(f"Error loading ping data: {e}")
        return {}

async def save_ping_data(data: dict) -> bool:
    """Save ping permissions to JSON file"""
    try:
        os.makedirs(os.path.dirname(PING_DATA_FILE), exist_ok=True)
        
        with open(PING_DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving ping data: {e}")
        return False

def generate_ping_id(name: str) -> str:
    """Generate a unique ID for a ping permission"""
    import hashlib
    import time
    
    # Create a unique ID based on name and timestamp
    content = f"{name}_{int(time.time())}"
    return hashlib.md5(content.encode()).hexdigest()[:8]

def user_can_use_ping(user_roles: list, ping_info: dict, user_id: int) -> bool:
    """Check if a user can use a specific ping permission"""
    # Check if user is specifically allowed
    if user_id in ping_info.get('allowed_users', []):
        return True
    
    # Check if user has any of the allowed roles
    allowed_role_ids = ping_info.get('allowed_roles', [])
    user_role_ids = [role.id for role in user_roles]
    
    return bool(set(allowed_role_ids) & set(user_role_ids))

async def pingcreate_command(
    interaction: discord.Interaction,
    ping: discord.Role,
    user: discord.Member = None,
    role: discord.Role = None
):
    """Create a new ping permission (Admin only)"""
    # Check if user has admin role
    user_roles = [user_role.id for user_role in interaction.user.roles]
    if ADMIN_ROLE_ID not in user_roles:
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return
    
    # Auto-generate name based on role name
    name = f"Ping {ping.name}"
    
    # Load existing ping data
    ping_data = await load_ping_data()
    
    # Check for duplicate target roles
    for existing_ping in ping_data.values():
        if existing_ping['target_role'] == ping.id:
            await interaction.response.send_message(
                f"❌ A ping permission for {ping.mention} already exists.",
                ephemeral=True
            )
            return
    
    # Generate unique ID
    ping_id = generate_ping_id(name)
    
    # Create ping permission data
    ping_info = {
        'name': name,
        'target_role': ping.id,
        'allowed_users': [user.id] if user else [],
        'allowed_roles': [role.id] if role else [],
        'created_by': interaction.user.id,
        'created_at': datetime.now(timezone.utc).isoformat()
    }
    
    # Save to data
    ping_data[ping_id] = ping_info
    success = await save_ping_data(ping_data)
    
    if not success:
        await interaction.response.send_message("❌ Failed to save ping permission.", ephemeral=True)
        return
    
    # Create success embed
    embed = discord.Embed(
        title="✅ Ping Permission Created",
        description=f"Successfully created ping permission: **{name}**",
        color=0x4ecdc4,
        timestamp=datetime.now(timezone.utc)
    )
    
    embed.add_field(
        name="Target Role",
        value=f"{ping.mention} (`{ping.name}`)",
        inline=False
    )
    
    access_list = []
    if user:
        access_list.append(f"👤 {user.mention}")
    if role:
        access_list.append(f"👥 {role.mention}")
    
    if access_list:
        embed.add_field(
            name="Initial Access",
            value="\n".join(access_list),
            inline=False
        )
    
    embed.add_field(
        name="Usage",
        value=f"`/ping role:{ping.mention}`",
        inline=False
    )
    
    embed.set_footer(text=f"Ping ID: {ping_id}")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

async def ping_command(interaction: discord.Interaction, role: discord.Role):
    """Use a ping permission to mention a role"""
    # Load ping permissions
    ping_data = await load_ping_data()
    
    if not ping_data:
        await interaction.response.send_message(
            "❌ No ping permissions have been created yet.",
            ephemeral=True
        )
        return
    
    # Find ping permissions for this role
    available_pings = []
    for ping_id, ping_info in ping_data.items():
        if ping_info['target_role'] == role.id:
            if user_can_use_ping(interaction.user.roles, ping_info, interaction.user.id):
                available_pings.append((ping_id, ping_info))
    
    if not available_pings:
        await interaction.response.send_message(
            f"❌ You don't have permission to ping {role.mention}.",
            ephemeral=True
        )
        return
    
    # Send the role ping
    await interaction.response.send_message(
        content=f"<@&{role.id}>",
        allowed_mentions=discord.AllowedMentions(roles=True),
        ephemeral=False
    )

async def pingadduser_command(interaction: discord.Interaction, ping: discord.Role, user: discord.Member):
    """Add a user to an existing ping permission"""
    # Check if user has admin role
    user_roles = [user_role.id for user_role in interaction.user.roles]
    if ADMIN_ROLE_ID not in user_roles:
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return
    
    ping_data = await load_ping_data()
    
    # Find the ping permission for this role
    target_ping = None
    for ping_id, ping_info in ping_data.items():
        if ping_info['target_role'] == ping.id:
            target_ping = (ping_id, ping_info)
            break
    
    if not target_ping:
        await interaction.response.send_message(f"❌ No ping permission found for {ping.mention}.", ephemeral=True)
        return
    
    ping_id, ping_info = target_ping
    
    # Check if user is already in the list
    if user.id in ping_info.get('allowed_users', []):
        await interaction.response.send_message(f"❌ {user.mention} already has permission to ping {ping.mention}.", ephemeral=True)
        return
    
    # Add the user
    ping_info['allowed_users'].append(user.id)
    success = await save_ping_data(ping_data)
    
    if success:
        await interaction.response.send_message(f"✅ Added {user.mention} to ping permission for {ping.mention}.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Failed to update ping permission.", ephemeral=True)

async def pingaddrole_command(interaction: discord.Interaction, ping: discord.Role, role: discord.Role):
    """Add a role to an existing ping permission"""
    # Check if user has admin role
    user_roles = [user_role.id for user_role in interaction.user.roles]
    if ADMIN_ROLE_ID not in user_roles:
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return
    
    ping_data = await load_ping_data()
    
    # Find the ping permission for this role
    target_ping = None
    for ping_id, ping_info in ping_data.items():
        if ping_info['target_role'] == ping.id:
            target_ping = (ping_id, ping_info)
            break
    
    if not target_ping:
        await interaction.response.send_message(f"❌ No ping permission found for {ping.mention}.", ephemeral=True)
        return
    
    ping_id, ping_info = target_ping
    
    # Check if role is already in the list
    if role.id in ping_info.get('allowed_roles', []):
        await interaction.response.send_message(f"❌ {role.mention} already has permission to ping {ping.mention}.", ephemeral=True)
        return
    
    # Add the role
    ping_info['allowed_roles'].append(role.id)
    success = await save_ping_data(ping_data)
    
    if success:
        await interaction.response.send_message(f"✅ Added {role.mention} to ping permission for {ping.mention}.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Failed to update ping permission.", ephemeral=True)

async def pingremoveuser_command(interaction: discord.Interaction, ping: discord.Role, user: discord.Member):
    """Remove a user from an existing ping permission"""
    # Check if user has admin role
    user_roles = [user_role.id for user_role in interaction.user.roles]
    if ADMIN_ROLE_ID not in user_roles:
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return
    
    ping_data = await load_ping_data()
    
    # Find the ping permission for this role
    target_ping = None
    for ping_id, ping_info in ping_data.items():
        if ping_info['target_role'] == ping.id:
            target_ping = (ping_id, ping_info)
            break
    
    if not target_ping:
        await interaction.response.send_message(f"❌ No ping permission found for {ping.mention}.", ephemeral=True)
        return
    
    ping_id, ping_info = target_ping
    
    # Check if user is in the list
    if user.id not in ping_info.get('allowed_users', []):
        await interaction.response.send_message(f"❌ {user.mention} doesn't have permission to ping {ping.mention}.", ephemeral=True)
        return
    
    # Remove the user
    ping_info['allowed_users'].remove(user.id)
    success = await save_ping_data(ping_data)
    
    if success:
        await interaction.response.send_message(f"✅ Removed {user.mention} from ping permission for {ping.mention}.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Failed to update ping permission.", ephemeral=True)

async def pingremoverole_command(interaction: discord.Interaction, ping: discord.Role, role: discord.Role):
    """Remove a role from an existing ping permission"""
    # Check if user has admin role
    user_roles = [user_role.id for user_role in interaction.user.roles]
    if ADMIN_ROLE_ID not in user_roles:
        await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
        return
    
    ping_data = await load_ping_data()
    
    # Find the ping permission for this role
    target_ping = None
    for ping_id, ping_info in ping_data.items():
        if ping_info['target_role'] == ping.id:
            target_ping = (ping_id, ping_info)
            break
    
    if not target_ping:
        await interaction.response.send_message(f"❌ No ping permission found for {ping.mention}.", ephemeral=True)
        return
    
    ping_id, ping_info = target_ping
    
    # Check if role is in the list
    if role.id not in ping_info.get('allowed_roles', []):
        await interaction.response.send_message(f"❌ {role.mention} doesn't have permission to ping {ping.mention}.", ephemeral=True)
        return
    
    # Remove the role
    ping_info['allowed_roles'].remove(role.id)
    success = await save_ping_data(ping_data)
    
    if success:
        await interaction.response.send_message(f"✅ Removed {role.mention} from ping permission for {ping.mention}.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Failed to update ping permission.", ephemeral=True)

async def pinglist_command(interaction: discord.Interaction, ping: discord.Role):
    """List all users and roles who can use a ping permission"""
    ping_data = await load_ping_data()
    
    # Find the ping permission for this role
    target_ping = None
    for ping_id, ping_info in ping_data.items():
        if ping_info['target_role'] == ping.id:
            target_ping = (ping_id, ping_info)
            break
    
    if not target_ping:
        await interaction.response.send_message(f"❌ No ping permission found for {ping.mention}.", ephemeral=True)
        return
    
    ping_id, ping_info = target_ping
    
    embed = discord.Embed(
        title=f"📋 Ping Permission for {ping.name}",
        description=f"Who can ping {ping.mention}",
        color=0x5865f2,
        timestamp=datetime.now(timezone.utc)
    )
    
    # List allowed users
    allowed_users = ping_info.get('allowed_users', [])
    if allowed_users:
        user_mentions = []
        for user_id in allowed_users:
            try:
                user = interaction.guild.get_member(user_id)
                if user:
                    user_mentions.append(user.mention)
                else:
                    user_mentions.append(f"<@{user_id}> (not found)")
            except:
                user_mentions.append(f"<@{user_id}> (error)")
        
        embed.add_field(
            name="👤 Allowed Users",
            value="\n".join(user_mentions) if user_mentions else "None",
            inline=False
        )
    
    # List allowed roles
    allowed_roles = ping_info.get('allowed_roles', [])
    if allowed_roles:
        role_mentions = []
        for role_id in allowed_roles:
            try:
                role = interaction.guild.get_role(role_id)
                if role:
                    role_mentions.append(role.mention)
                else:
                    role_mentions.append(f"<@&{role_id}> (not found)")
            except:
                role_mentions.append(f"<@&{role_id}> (error)")
        
        embed.add_field(
            name="👥 Allowed Roles",
            value="\n".join(role_mentions) if role_mentions else "None",
            inline=False
        )
    
    if not allowed_users and not allowed_roles:
        embed.add_field(
            name="⚠️ No Access",
            value="No users or roles can currently use this ping permission.",
            inline=False
        )
    
    embed.set_footer(text=f"Ping ID: {ping_id}")
    await interaction.response.send_message(embed=embed, ephemeral=True)

def setup_ping_commands(tree):
    """Register ping commands with the command tree"""
    
    @tree.command(name="pingcreate", description="Create ping permission")
    @app_commands.describe(
        ping="Role to ping",
        user="Initial user who can use this ping (optional)",
        role="Initial role whose members can use this ping (optional)"
    )
    async def pingcreate(
        interaction: discord.Interaction,
        ping: discord.Role,
        user: discord.Member = None,
        role: discord.Role = None
    ):
        await pingcreate_command(interaction, ping, user, role)
    
    @tree.command(name="ping", description="Ping a role")
    @app_commands.describe(role="Role to ping")
    async def ping(interaction: discord.Interaction, role: discord.Role):
        await ping_command(interaction, role)
    
    @tree.command(name="pingadduser", description="Add user to ping permission")
    @app_commands.describe(
        ping="Role that can be pinged",
        user="User to add to this ping permission"
    )
    async def pingadduser(
        interaction: discord.Interaction,
        ping: discord.Role,
        user: discord.Member
    ):
        await pingadduser_command(interaction, ping, user)
    
    @tree.command(name="pingaddrole", description="Add role to ping permission")
    @app_commands.describe(
        ping="Role that can be pinged",
        role="Role to add to this ping permission"
    )
    async def pingaddrole(
        interaction: discord.Interaction,
        ping: discord.Role,
        role: discord.Role
    ):
        await pingaddrole_command(interaction, ping, role)
    
    @tree.command(name="pingremoveuser", description="Remove user from ping permission")
    @app_commands.describe(
        ping="Role that can be pinged",
        user="User to remove from this ping permission"
    )
    async def pingremoveuser(
        interaction: discord.Interaction,
        ping: discord.Role,
        user: discord.Member
    ):
        await pingremoveuser_command(interaction, ping, user)
    
    @tree.command(name="pingremoverole", description="Remove role from ping permission")
    @app_commands.describe(
        ping="Role that can be pinged",
        role="Role to remove from this ping permission"
    )
    async def pingremoverole(
        interaction: discord.Interaction,
        ping: discord.Role,
        role: discord.Role
    ):
        await pingremoverole_command(interaction, ping, role)
    
    @tree.command(name="pinglist", description="List who can use a ping permission")
    @app_commands.describe(ping="Role to check ping permissions for")
    async def pinglist(
        interaction: discord.Interaction,
        ping: discord.Role
    ):
        await pinglist_command(interaction, ping)
    
    print("✅ Ping commands registered successfully")
