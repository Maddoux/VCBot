#!/usr/bin/env python3
"""
Party Role Enforcement System for VCBot
Prevents party-switching during election season (1st-11th of each month)
Allows party switching on the 11th at 20:00 UTC
"""

import discord
from discord.ext import commands
from datetime import datetime, timezone
from typing import Optional

# Configuration
ALERT_CHANNEL_ID = 654467992272371712
ADMIN_ROLE_ID = 654477469004595221
MODERATOR_ROLE_ID = 707781265985896469
BOT_ROLE_ID = 654722769862393867  # Bots with this role can change party roles

# Party switching allowed hour (9 PM CET = 20:00 UTC in winter, 19:00 UTC in summer)
# Using 20:00 UTC as CET (Central European Time, UTC+1)
PARTY_SWITCH_ALLOWED_HOUR_UTC = 20  # 9 PM CET = 20:00 UTC

# Party role IDs
PARTY_ROLE_IDS = {
    707784620678316093: "Democrat",
    707784409780191353: "Republican",
    654499723658526741: "Independent",
}

def is_party_switch_allowed_time() -> bool:
    """Check if current time is the allowed party switching time (11th of month at 20:00 UTC)"""
    now = datetime.now(timezone.utc)
    return now.day == 11 and now.hour == PARTY_SWITCH_ALLOWED_HOUR_UTC

def is_election_season() -> bool:
    """Check if current date is within election season (1st-11th of month)"""
    now = datetime.now(timezone.utc)
    # Allow switching on the 11th at 20:00 UTC regardless of election season
    if is_party_switch_allowed_time():
        return False
    return 1 <= now.day <= 11

def get_party_roles(roles: list) -> list:
    """Get list of party roles from a member's roles"""
    return [role for role in roles if role.id in PARTY_ROLE_IDS]

async def on_member_update_party_check(before: discord.Member, after: discord.Member):
    """
    Event handler for member updates - checks for unauthorized party switching
    
    Args:
        before: Member state before update
        after: Member state after update
    """
    # Only check during election season
    if not is_election_season():
        return
    
    # Get party roles before and after
    before_parties = get_party_roles(before.roles)
    after_parties = get_party_roles(after.roles)
    
    # If no change in party roles, ignore
    if set(r.id for r in before_parties) == set(r.id for r in after_parties):
        return
    
    # Case 1: User had no party and now has one (new member picking party) - ALLOW
    if len(before_parties) == 0 and len(after_parties) > 0:
        print(f"✅ New member {after.display_name} selected party: {after_parties[0].name}")
        return
    
    # Case 2: User had party and changed it - CHECK WHO MADE THE CHANGE
    if len(before_parties) > 0 and after_parties != before_parties:
        # Get audit log to see who made the change
        try:
            guild = after.guild
            
            # Look for recent role updates in audit log
            async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.member_role_update):
                # Check if this entry is for our member and is very recent (within last 2 seconds)
                if entry.target.id == after.id:
                    time_diff = (datetime.now(timezone.utc) - entry.created_at).total_seconds()
                    
                    if time_diff < 2:  # Within 2 seconds
                        moderator = entry.user
                        
                        # If changed by admin, moderator, or bot, allow it
                        if moderator.id != after.id:  # Someone else changed it
                            moderator_roles = [role.id for role in moderator.roles]
                            if (ADMIN_ROLE_ID in moderator_roles or 
                                MODERATOR_ROLE_ID in moderator_roles or 
                                BOT_ROLE_ID in moderator_roles):
                                print(f"✅ Admin/Mod/Bot {moderator.display_name} changed {after.display_name}'s party")
                                return
                        
                        # If changed by themselves during election season - BLOCK IT
                        if moderator.id == after.id:
                            await handle_unauthorized_party_switch(after, before_parties, after_parties)
                            return
                        
                        break
            
            # If we can't determine who changed it, but party changed during election season, flag it
            # This is a safety catch for when audit log is unavailable
            print(f"⚠️ Party change detected for {after.display_name} but couldn't verify in audit log")
                    
        except discord.Forbidden:
            print(f"❌ Missing permissions to check audit log for party change")
        except Exception as e:
            print(f"❌ Error checking party change for {after.display_name}: {e}")

async def handle_unauthorized_party_switch(member: discord.Member, old_parties: list, new_parties: list):
    """
    Handle unauthorized party switching - revert and notify
    
    Args:
        member: Member who tried to switch
        old_parties: List of old party roles
        new_parties: List of new party roles
    """
    try:
        guild = member.guild
        
        # Determine what changed
        old_party_names = [PARTY_ROLE_IDS.get(r.id, r.name) for r in old_parties]
        new_party_names = [PARTY_ROLE_IDS.get(r.id, r.name) for r in new_parties]
        
        # Revert the role change
        # Remove new party roles
        for role in new_parties:
            if role not in old_parties:
                await member.remove_roles(role, reason="Unauthorized party switch during election season")
        
        # Re-add old party roles
        for role in old_parties:
            if role not in new_parties:
                await member.add_roles(role, reason="Reverting unauthorized party switch")
        old_party_str = ", ".join(old_party_names) if old_party_names else "None"
        new_party_str = ", ".join(new_party_names) if new_party_names else "None"
        
        print(f"🚫 Blocked party switch: {member.display_name} tried to change from {old_party_names} to {new_party_names}")
        
        # Try to DM the user first
        dm_failed = False
        try:
            await member.send(
                f"❌ **Party Switch Blocked**\n\n"
                f"You attempted to change your party affiliation during election season (1st-11th of the month). "
                f"Party changes are not allowed during this time to ensure election integrity.\n\n"
                f"Your party has been reverted to: **{old_party_str}**\n\n"
                f"You can change your party on the 11th at 20:00 UTC."
            )
        except discord.Forbidden:
            # User has DMs disabled
            dm_failed = True
        except Exception:
            dm_failed = True
        
        # Send notification to alert channel
        alert_channel = guild.get_channel(ALERT_CHANNEL_ID)
        if alert_channel:
            # If DM succeeded, send simple message without embed
            if not dm_failed:
                await alert_channel.send(f"**{member.display_name}** tried to change their party, but it's election season!")
            else:
                # If DM failed, send full embed with all details
                embed = discord.Embed(
                    title="🚫 Party Switch Blocked",
                    description=f"**{member.display_name}** attempted to change their party affiliation during election season.",
                    color=discord.Color.red(),
                    timestamp=datetime.now(timezone.utc)
                )
                
                embed.add_field(name="Previous Party", value=old_party_str, inline=True)
                embed.add_field(name="Attempted Party", value=new_party_str, inline=True)
                embed.add_field(name="Election Season", value="1st-11th of month", inline=False)
                embed.add_field(
                    name="Note", 
                    value="Party changes are not allowed during election season (1st-11th). You can change your party on the 11th at 20:00 UTC.",
                    inline=False
                )
                
                embed.set_footer(text=f"User ID: {member.id}")
                
                message_content = f"{member.mention} I couldn't send you a DM - your party change has been blocked. Party changes are not allowed during election season (1st-11th)."
                await alert_channel.send(content=message_content, embed=embed)
        
    except Exception as e:
        print(f"❌ Error handling unauthorized party switch for {member.display_name}: {e}")

def setup_party_enforcement(client: discord.Client):
    """
    Register the party enforcement event handler
    
    Args:
        client: Discord client instance
    """
    @client.event
    async def on_member_update(before: discord.Member, after: discord.Member):
        """Event fired when member is updated (roles, nickname, etc.)"""
        # Run party check
        await on_member_update_party_check(before, after)
    
    print("✅ Party role enforcement system activated")
    
    # Print current status
    if is_election_season():
        now = datetime.now(timezone.utc)
        print(f"🗳️  ELECTION SEASON ACTIVE (Day {now.day} of month) - Party switching is restricted")
    else:
        print(f"✅ Party switching is currently allowed (not election season)")
