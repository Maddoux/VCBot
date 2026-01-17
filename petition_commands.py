#!/usr/bin/env python3
"""
Petition System for VCBot
Handles petition creation, tracking, and threshold notifications
"""

import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone, timedelta
from typing import Optional
import asyncio
import json
import re
from pathlib import Path

# Configuration
PETITIONS_CHANNEL_ID = 859209770439278613
PETITION_SUBMISSION_CHANNEL_ID = 1169091012178743306
ADMIN_ROLE_ID = 654477469004595221
BALLPOINT_EMOJI = "🖊️"  # :pen_ballpoint: emoji
SIGNATURE_THRESHOLD = 25  # Threshold for normal petitions
RECALL_SIGNATURE_THRESHOLD = 30  # Threshold for recall petitions
PETITION_EXPIRY_DAYS = 30
RECALL_KEYWORDS = ["fire", "sack", "recall"]  # Keywords that make a petition a recall

# File to store petition data
PETITION_DATA_FILE = Path("data") / "petitions.json"

class PetitionModal(discord.ui.Modal):
    """Modal form for creating petitions"""
    
    def __init__(self):
        super().__init__(title="Create Petition")
        
        # Title field
        self.title_input = discord.ui.TextInput(
            label="Petition Title",
            placeholder="Enter the title of your petition...",
            max_length=200,
            required=True
        )
        self.add_item(self.title_input)
        
        # Description field
        self.description_input = discord.ui.TextInput(
            label="Petition Description",
            placeholder="Describe what your petition is about...",
            style=discord.TextStyle.paragraph,
            max_length=2000,
            required=True
        )
        self.add_item(self.description_input)
        
        # Optional link field
        self.link_input = discord.ui.TextInput(
            label="Link (Optional)",
            placeholder="https://example.com (optional supporting link)",
            max_length=500,
            required=False
        )
        self.add_item(self.link_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle form submission"""
        await interaction.response.defer()
        
        try:
            # Get petition data
            title = self.title_input.value.strip()
            description = self.description_input.value.strip()
            link = self.link_input.value.strip() if self.link_input.value else None
            
            # Get petitions channel
            petitions_channel = interaction.client.get_channel(PETITIONS_CHANNEL_ID)
            if not petitions_channel:
                await interaction.followup.send(
                    "Error: Petitions channel not found. Please contact an administrator.",
                    ephemeral=True
                )
                return
            
            # Check if this is a recall petition
            is_recall = is_recall_petition(title, description)
            threshold = RECALL_SIGNATURE_THRESHOLD if is_recall else SIGNATURE_THRESHOLD
            
            # Create petition embed (same appearance for both types)
            embed = discord.Embed(
                title=title,
                description=description,
                color=0x0099ff,  # Blue for all petitions
                timestamp=datetime.now(timezone.utc)
            )
            
            embed.add_field(
                name="Author",
                value=interaction.user.mention,
                inline=False
            )
            
            embed.add_field(
                name="Signatures Needed",
                value=f"0/{threshold}",
                inline=False
            )
            
            if link:
                embed.add_field(
                    name="Link",
                    value=link,
                    inline=False
                )
            
            embed.set_footer(text="React with the pen emoji to sign this petition • Use /petition to create your own")
            
            # Send petition to channel
            petition_message = await petitions_channel.send(embed=embed)
            
            # Add ballpoint pen reaction
            await petition_message.add_reaction(BALLPOINT_EMOJI)
            
            # Create thread with petition title
            thread = await petition_message.create_thread(
                name=title[:100],  # Discord thread name limit
                auto_archive_duration=10080  # 7 days
            )
            
            # Send initial message in thread
            await thread.send(
                f"Discussion thread for petition: **{title}**\n\n"
                f"Created by {interaction.user.mention}\n"
                f"React to the main message with the pen emoji to sign this petition."
            )
            
            # Store petition data
            await store_petition_data(petition_message.id, {
                'title': title,
                'description': description,
                'link': link,
                'author_id': interaction.user.id,
                'author_name': interaction.user.display_name,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'thread_id': thread.id,
                'signatures': 0,
                'is_recall': is_recall,
                'threshold_reached': False,
                'expired': False
            })
            
            # Confirm to user
            await interaction.followup.send(
                f"Petition '{title}' has been created successfully!\n"
                f"It has been posted in the petitions channel with a discussion thread.\n"
                f"Users can sign by reacting with the pen emoji.",
                ephemeral=True
            )
            
        except Exception as e:
            await interaction.followup.send(
                f"Error creating petition: {str(e)}",
                ephemeral=True
            )

async def store_petition_data(message_id: int, data: dict):
    """Store petition data to file"""
    try:
        # Ensure data directory exists
        PETITION_DATA_FILE.parent.mkdir(exist_ok=True)
        
        # Load existing data
        if PETITION_DATA_FILE.exists():
            with open(PETITION_DATA_FILE, 'r') as f:
                petitions = json.load(f)
        else:
            petitions = {}
        
        # Add new petition
        petitions[str(message_id)] = data
        
        # Save data
        with open(PETITION_DATA_FILE, 'w') as f:
            json.dump(petitions, f, indent=2)
            
    except Exception as e:
        print(f"Error storing petition data: {e}")

def is_recall_petition(title: str, description: str) -> bool:
    """Check if petition is a recall based on keywords"""
    text = (title + " " + description).lower()
    return any(keyword in text for keyword in RECALL_KEYWORDS)

def get_petition_threshold(petition_data: dict) -> int:
    """Get the signature threshold for a petition (25 for regular, 30 for recalls)"""
    if petition_data.get('is_recall', False):
        return RECALL_SIGNATURE_THRESHOLD
    return SIGNATURE_THRESHOLD

async def load_petition_data():
    """Load petition data from file"""
    try:
        if PETITION_DATA_FILE.exists():
            with open(PETITION_DATA_FILE, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"Error loading petition data: {e}")
        return {}

async def mark_petition_invalid(message_id: int, reason: str = "Message not found"):
    """Mark a petition as invalid to prevent future checking"""
    try:
        petitions = await load_petition_data()
        message_id_str = str(message_id)
        
        if message_id_str in petitions:
            petitions[message_id_str]['invalid'] = True
            petitions[message_id_str]['invalid_reason'] = reason
            petitions[message_id_str]['marked_invalid_at'] = datetime.now(timezone.utc).isoformat()
            
            # Save updated data
            with open(PETITION_DATA_FILE, 'w') as f:
                json.dump(petitions, f, indent=2)
            
            petition_title = petitions[message_id_str].get('title', 'Unknown')
            print(f"🚫 Marked petition as invalid: {petition_title} (ID: {message_id_str}) - {reason}")
            return True
        return False
    except Exception as e:
        print(f"Error marking petition as invalid: {e}")
        return False

async def update_petition_signatures(message_id: int, signature_count: int):
    """Update signature count for a petition"""
    try:
        petitions = await load_petition_data()
        
        if str(message_id) in petitions:
            petitions[str(message_id)]['signatures'] = signature_count
            
            # Save updated data
            with open(PETITION_DATA_FILE, 'w') as f:
                json.dump(petitions, f, indent=2)
                
    except Exception as e:
        print(f"Error updating petition signatures: {e}")

async def repair_petitions_command(interaction: discord.Interaction):
    """Admin command to repair petition system"""
    # Check if user has admin role
    user_roles = [role.id for role in interaction.user.roles]
    if ADMIN_ROLE_ID not in user_roles:
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    await interaction.response.defer()
    
    try:
        # Run petition repair
        await repair_petition_system(interaction.client)
        
        embed = discord.Embed(
            title="🔧 Petition System Repair Complete",
            description="The petition system has been checked and repaired.",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        
        embed.add_field(
            name="✅ Repairs Applied",
            value=(
                "• Added missing ballpoint pen reactions\n"
                "• Fixed signature counts in embeds\n"
                "• Updated stored signature data\n"
                "• Created missing discussion threads\n"
                "• Fixed embed colors for completed petitions"
            ),
            inline=False
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error repairing petitions: {str(e)}", ephemeral=True)
        print(f"Error in repair_petitions_command: {e}")

async def manage_invalid_petitions_command(interaction: discord.Interaction):
    """Admin command to view and manage invalid petitions"""
    # Check if user has admin role
    user_roles = [role.id for role in interaction.user.roles]
    if ADMIN_ROLE_ID not in user_roles:
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    try:
        petitions = await load_petition_data()
        invalid_petitions = {k: v for k, v in petitions.items() if v.get('invalid', False)}
        
        if not invalid_petitions:
            embed = discord.Embed(
                title="✅ No Invalid Petitions",
                description="All petitions are currently valid.",
                color=0x00ff00,
                timestamp=datetime.now(timezone.utc)
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🚫 Invalid Petitions Report",
            description=f"Found {len(invalid_petitions)} invalid petition(s)",
            color=0xff6b6b,
            timestamp=datetime.now(timezone.utc)
        )
        
        count = 0
        for message_id_str, petition_data in invalid_petitions.items():
            if count >= 10:  # Limit to 10 entries to avoid embed limits
                embed.add_field(
                    name="...",
                    value=f"And {len(invalid_petitions) - count} more invalid petitions",
                    inline=False
                )
                break
            
            title = petition_data.get('title', 'Unknown')[:100]
            reason = petition_data.get('invalid_reason', 'Unknown reason')
            marked_at = petition_data.get('marked_invalid_at', 'Unknown time')
            
            if marked_at != 'Unknown time':
                try:
                    marked_dt = datetime.fromisoformat(marked_at.replace('Z', '+00:00'))
                    marked_at = f"<t:{int(marked_dt.timestamp())}:R>"
                except:
                    marked_at = "Unknown time"
            
            embed.add_field(
                name=f"📋 {title}",
                value=f"**ID:** `{message_id_str}`\n**Reason:** {reason}\n**Marked:** {marked_at}",
                inline=False
            )
            count += 1
        
        embed.set_footer(text="These petitions will be skipped in future checks")
        await interaction.followup.send(embed=embed, ephemeral=True)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error checking invalid petitions: {str(e)}", ephemeral=True)
        print(f"Error in manage_invalid_petitions_command: {e}")

async def mark_threshold_reached(message_id: int):
    """Mark petition as having reached threshold"""
    try:
        petitions = await load_petition_data()
        
        if str(message_id) in petitions:
            petitions[str(message_id)]['threshold_reached'] = True
            
            # Save updated data
            with open(PETITION_DATA_FILE, 'w') as f:
                json.dump(petitions, f, indent=2)
                
            return True
        
        return False
        
    except Exception as e:
        print(f"Error marking threshold reached: {e}")
        return False

async def repair_petition_system(client: discord.Client):
    """Comprehensive repair of petition system - adds missing reactions, fixes counts, creates missing threads"""
    try:
        petitions_channel = client.get_channel(PETITIONS_CHANNEL_ID)
        if not petitions_channel:
            print("❌ Petition channel not found")
            return
        
        petitions = await load_petition_data()
        repairs_made = 0
        total_petitions = len(petitions)
        processed = 0
        skipped_expired = 0
        
        print(f"🔧 Starting repair of {total_petitions} petitions with rate limiting...")
        
        for message_id_str, petition_data in petitions.items():
            # Skip invalid petitions
            if petition_data.get('invalid', False):
                continue
            
            # Skip expired petitions
            created_at_str = petition_data.get('created_at')
            if created_at_str:
                try:
                    created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                    petition_age = (datetime.now(timezone.utc) - created_at).days
                    if petition_age > PETITION_EXPIRY_DAYS:
                        skipped_expired += 1
                        continue
                except (ValueError, AttributeError):
                    pass  # If date parsing fails, continue checking petition
                
            try:
                processed += 1
                print(f"📋 Processing petition {processed}/{total_petitions - skipped_expired}")
                
                message_id = int(message_id_str)
                message = await petitions_channel.fetch_message(message_id)
                
                # Rate limiting: Add delay between API calls
                await asyncio.sleep(1.0)  # 1 second delay between petitions
                
                if not message or not message.embeds:
                    continue
                
                print(f"🔧 Checking petition: {petition_data.get('title', 'Unknown')}")
                
                # 1. Ensure ballpoint pen reaction exists
                has_ballpoint_reaction = False
                ballpoint_reaction = None
                
                for reaction in message.reactions:
                    if str(reaction.emoji) == BALLPOINT_EMOJI:
                        has_ballpoint_reaction = True
                        ballpoint_reaction = reaction
                        break
                
                if not has_ballpoint_reaction:
                    print(f"  ➕ Adding missing ballpoint pen reaction")
                    await message.add_reaction(BALLPOINT_EMOJI)
                    await asyncio.sleep(0.5)  # Rate limit after adding reaction
                    repairs_made += 1
                    # Refresh message to get updated reactions
                    message = await petitions_channel.fetch_message(message_id)
                    await asyncio.sleep(0.5)  # Rate limit after fetching message
                    for reaction in message.reactions:
                        if str(reaction.emoji) == BALLPOINT_EMOJI:
                            ballpoint_reaction = reaction
                            break
                
                # 2. Fix signature count in embed and data
                if ballpoint_reaction:
                    # Count only human signatures (exclude bots)
                    users = [user async for user in ballpoint_reaction.users() if not user.bot]
                    actual_signatures = len(users)
                else:
                    actual_signatures = 0
                
                # 3. Update embed if signature count is wrong
                embed = message.embeds[0]
                needs_embed_update = False
                
                # Get threshold for this petition
                threshold = get_petition_threshold(petition_data)
                
                for i, field in enumerate(embed.fields):
                    if field.name == "Signatures Needed":
                        expected_value = f"{actual_signatures}/{threshold}"
                        if field.value != expected_value:
                            print(f"  📊 Fixing signature count: {field.value} → {expected_value}")
                            embed.set_field_at(
                                i,
                                name="Signatures Needed",
                                value=expected_value,
                                inline=False
                            )
                            needs_embed_update = True
                            repairs_made += 1
                        break
                
                # Update embed color if needed
                if actual_signatures >= SIGNATURE_THRESHOLD and embed.color != 0x00ff00:
                    embed.color = 0x00ff00  # Green when threshold reached
                    needs_embed_update = True
                
                if needs_embed_update:
                    await message.edit(embed=embed)
                    await asyncio.sleep(0.5)  # Rate limit after editing embed
                
                # 4. Update stored signature count
                await update_petition_signatures(message_id, actual_signatures)
                
                # 5. Ensure thread exists
                if not hasattr(message, 'thread') or not message.thread:
                    print(f"  🧵 Creating missing thread")
                    try:
                        thread = await message.create_thread(
                            name=petition_data.get('title', 'Petition Discussion')[:100],
                            auto_archive_duration=10080  # 7 days
                        )
                        await thread.send(
                            f"Discussion thread for petition: **{petition_data.get('title', 'Unknown')}**\n\n"
                            f"Created by <@{petition_data.get('author_id', 'Unknown')}>\n"
                            f"React to the main message with the pen emoji (🖊️) to sign this petition."
                        )
                        await asyncio.sleep(0.5)  # Rate limit after thread creation
                        repairs_made += 1
                    except Exception as thread_error:
                        print(f"  ❌ Could not create thread: {thread_error}")
                        
            except discord.HTTPException as e:
                if e.status == 429:  # Rate limited
                    retry_after = getattr(e, 'retry_after', 5)
                    print(f"⚠️ Rate limited while repairing petition {message_id_str}, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                elif e.status == 404:  # Message not found
                    petition_title = petition_data.get('title', 'Unknown')
                    print(f"📋 Message not found for petition '{petition_title}' (ID: {message_id_str})")
                    await mark_petition_invalid(int(message_id_str), "Message not found (404)")
                else:
                    print(f"❌ HTTP error repairing petition {message_id_str}: {e}")
            except discord.NotFound:
                petition_title = petition_data.get('title', 'Unknown')
                print(f"📋 Message not found for petition '{petition_title}' (ID: {message_id_str})")
                await mark_petition_invalid(int(message_id_str), "Message not found")
            except Exception as e:
                print(f"❌ Error repairing petition {message_id_str}: {e}")
        
        if skipped_expired > 0:
            print(f"⏭️  Skipped {skipped_expired} expired petitions (older than {PETITION_EXPIRY_DAYS} days)")
        
        if repairs_made > 0:
            print(f"✅ Completed {repairs_made} petition system repairs")
        else:
            print("✅ All petitions are properly configured")
            
    except Exception as e:
        print(f"❌ Error repairing petition system: {e}")

async def check_petition_expired(petition_data: dict):
    """Check if a petition has expired (30 days old)"""
    try:
        created_at = datetime.fromisoformat(petition_data['created_at'].replace('Z', '+00:00'))
        expiry_date = created_at + timedelta(days=PETITION_EXPIRY_DAYS)
        return datetime.now(timezone.utc) > expiry_date
    except Exception as e:
        print(f"Error checking petition expiry: {e}")
        return False

async def mark_petition_expired(message_id: int):
    """Mark petition as expired"""
    try:
        petitions = await load_petition_data()
        
        if str(message_id) in petitions:
            petitions[str(message_id)]['expired'] = True
            
            # Save updated data
            with open(PETITION_DATA_FILE, 'w') as f:
                json.dump(petitions, f, indent=2)
                
            return True
        
        return False
        
    except Exception as e:
        print(f"Error marking petition expired: {e}")
        return False

async def handle_petition_reaction(payload: discord.RawReactionActionEvent, client: discord.Client):
    """Handle reactions on petition messages"""
    
    # Only handle reactions in petitions channel
    if payload.channel_id != PETITIONS_CHANNEL_ID:
        return
    
    # Only handle ballpoint pen emoji
    if str(payload.emoji) != BALLPOINT_EMOJI:
        return
    
    try:
        # Get the message
        channel = client.get_channel(payload.channel_id)
        if not channel:
            return
            
        message = await channel.fetch_message(payload.message_id)
        if not message:
            return
        
        # Load petition data
        petitions = await load_petition_data()
        petition_data = petitions.get(str(message.id))
        
        if not petition_data:
            print(f"No petition data found for message {message.id}")
            return
        
        # Get the threshold for this petition
        threshold = get_petition_threshold(petition_data)
        
        # Check if petition has expired
        is_expired = await check_petition_expired(petition_data)
        was_already_expired = petition_data.get('expired', False)
        
        # If petition just expired, mark it and update embed
        if is_expired and not was_already_expired:
            await mark_petition_expired(message.id)
            await update_expired_embed(message, petition_data)
            return
        
        # If petition is already expired, don't process new reactions
        if is_expired:
            return
        
        # Find the ballpoint reaction
        reaction = None
        for r in message.reactions:
            if str(r.emoji) == BALLPOINT_EMOJI:
                reaction = r
                break
        
        if not reaction:
            # No reactions at all, add bot signature
            await message.add_reaction(BALLPOINT_EMOJI)
            await update_petition_signatures(message.id, 0)
            return
        
        # Get all users who reacted, separating humans from bot
        try:
            all_users = [user async for user in reaction.users()]
        except Exception as e:
            print(f"Error fetching reaction users: {e}")
            return
            
        human_users = [user for user in all_users if not user.bot]
        bot_has_reacted = any(user.id == client.user.id for user in all_users)
        human_signature_count = len(human_users)
        
        # Manage bot signature based on human signatures
        try:
            if human_signature_count == 0 and not bot_has_reacted:
                # No signatures at all, bot should add its signature
                await message.add_reaction(BALLPOINT_EMOJI)
            elif human_signature_count > 0 and bot_has_reacted:
                # Humans have signed, bot should remove its signature
                await message.remove_reaction(BALLPOINT_EMOJI, client.user)
        except discord.errors.NotFound:
            # Message or reaction was deleted, ignore
            pass
        except Exception as e:
            print(f"Error managing bot signature: {e}")
        
        # Update signature count in data
        await update_petition_signatures(message.id, human_signature_count)
        
        # Update embed with new signature count
        if message.embeds:
            embed = message.embeds[0]
            
            # Update signatures field
            for i, field in enumerate(embed.fields):
                if field.name == "Signatures Needed":
                    embed.set_field_at(
                        i,
                        name="Signatures Needed",
                        value=f"{human_signature_count}/{threshold}",
                        inline=False
                    )
                    break
            
            # Check if threshold just reached
            has_reached_threshold = petition_data.get('threshold_reached', False)
            if human_signature_count >= threshold and not has_reached_threshold:
                embed.color = 0x00ff00  # Green when threshold reached
                # Update local petition data with current signature count for notification
                petition_data['signatures'] = human_signature_count
                await notify_threshold_reached(client, petition_data, message.id)
                await mark_threshold_reached(message.id)
            
            await message.edit(embed=embed)
            
    except Exception as e:
        print(f"Error handling petition reaction: {e}")

async def update_expired_embed(message: discord.Message, petition_data: dict):
    """Update embed to show petition has expired"""
    try:
        if not message.embeds:
            return
        
        embed = message.embeds[0]
        
        # Change color to red
        embed.color = 0xff0000
        
        # Update title to show expired
        embed.title = f"[EXPIRED] {petition_data['title']}"
        
        # Update signatures field to show expired
        for i, field in enumerate(embed.fields):
            if field.name == "Signatures Needed":
                embed.set_field_at(
                    i,
                    name="Signatures Needed",
                    value=f"{petition_data['signatures']}/{SIGNATURE_THRESHOLD} (EXPIRED)",
                    inline=False
                )
                break
        
        # Update footer
        embed.set_footer(text=f"This petition expired after {PETITION_EXPIRY_DAYS} days • Use /petition to create your own")
        
        await message.edit(embed=embed)
        print(f"Marked petition as expired: {petition_data['title']}")
        
    except Exception as e:
        print(f"Error updating expired embed: {e}")

async def check_all_petitions_for_expiry(client: discord.Client):
    """Check all active petitions for expiry and mark expired ones"""
    try:
        petitions = await load_petition_data()
        petitions_channel = client.get_channel(PETITIONS_CHANNEL_ID)
        
        if not petitions_channel:
            print("Petitions channel not found for expiry check")
            return
        
        expired_count = 0
        
        for message_id_str, petition_data in petitions.items():
            # Skip already expired, completed, or invalid petitions
            if (petition_data.get('expired', False) or 
                petition_data.get('threshold_reached', False) or
                petition_data.get('invalid', False)):
                continue
            
            # Check if petition has expired
            if await check_petition_expired(petition_data):
                try:
                    # Rate limiting: Add delay between API calls
                    await asyncio.sleep(0.5)  # 500ms delay between expiry checks
                    
                    message_id = int(message_id_str)
                    message = await petitions_channel.fetch_message(message_id)
                    
                    if message:
                        await mark_petition_expired(message_id)
                        await update_expired_embed(message, petition_data)
                        expired_count += 1
                        print(f"Expired petition: {petition_data['title']}")
                        
                except discord.HTTPException as e:
                    if e.status == 429:  # Rate limited
                        retry_after = getattr(e, 'retry_after', 5)
                        print(f"⚠️ Rate limited while checking expiry for petition {message_id_str}, waiting {retry_after}s")
                        await asyncio.sleep(retry_after)
                    elif e.status == 404:  # Message not found
                        petition_title = petition_data.get('title', 'Unknown')
                        print(f"📋 Message not found for petition '{petition_title}' (ID: {message_id_str})")
                        await mark_petition_invalid(int(message_id_str), "Message not found (404)")
                    else:
                        print(f"❌ HTTP error checking expiry for petition {message_id_str}: {e}")
                except discord.NotFound:
                    petition_title = petition_data.get('title', 'Unknown')
                    print(f"📋 Message not found for petition '{petition_title}' (ID: {message_id_str})")
                    await mark_petition_invalid(int(message_id_str), "Message not found")
                except Exception as e:
                    print(f"Error processing expired petition {message_id_str}: {e}")
        
        if expired_count > 0:
            print(f"Marked {expired_count} petitions as expired")
            
    except Exception as e:
        print(f"Error checking petitions for expiry: {e}")



async def verify_petition_signature_counts(client: discord.Client):
    """Verify that stored signature counts match actual Discord reactions"""
    try:
        petitions = await load_petition_data()
        petitions_channel = client.get_channel(PETITIONS_CHANNEL_ID)
        
        if not petitions_channel:
            print("Petitions channel not found for signature verification")
            return
        
        corrections_made = 0
        skipped_expired = 0
        
        for message_id_str, petition_data in petitions.items():
            # Skip expired, completed, or invalid petitions
            if (petition_data.get('expired', False) or 
                petition_data.get('threshold_reached', False) or
                petition_data.get('invalid', False)):
                continue
            
            # Skip petitions older than expiry threshold
            created_at_str = petition_data.get('created_at')
            if created_at_str:
                try:
                    created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                    petition_age = (datetime.now(timezone.utc) - created_at).days
                    if petition_age > PETITION_EXPIRY_DAYS:
                        skipped_expired += 1
                        continue
                except (ValueError, AttributeError):
                    pass
            
            try:
                # Rate limiting: Add delay between API calls
                await asyncio.sleep(0.5)  # 500ms delay between signature verifications
                
                message_id = int(message_id_str)
                message = await petitions_channel.fetch_message(message_id)
                
                if not message:
                    continue
                
                # Find the ballpoint pen reaction
                actual_signatures = 0
                for reaction in message.reactions:
                    if str(reaction.emoji) == BALLPOINT_EMOJI:
                        # Count only human signatures (exclude bots)
                        users = [user async for user in reaction.users() if not user.bot]
                        actual_signatures = len(users)
                        break
                
                stored_signatures = petition_data.get('signatures', 0)
                
                # If counts don't match, update stored data and embed
                if actual_signatures != stored_signatures:
                    print(f"Signature count mismatch for petition '{petition_data['title']}': "
                          f"stored={stored_signatures}, actual={actual_signatures}")
                    
                    # Update stored data
                    await update_petition_signatures(message_id, actual_signatures)
                    
                    # Update embed
                    if message.embeds:
                        embed = message.embeds[0]
                        
                        # Get threshold for this petition
                        threshold = get_petition_threshold(petition_data)
                        
                        # Update signatures field
                        for i, field in enumerate(embed.fields):
                            if field.name == "Signatures Needed":
                                embed.set_field_at(
                                    i,
                                    name="Signatures Needed",
                                    value=f"{actual_signatures}/{threshold}",
                                    inline=False
                                )
                                break
                        
                        # Check if threshold reached
                        if actual_signatures >= threshold and not petition_data.get('threshold_reached', False):
                            embed.color = 0x00ff00  # Green when threshold reached
                            # Update local petition data with current signature count for notification
                            petition_data['signatures'] = actual_signatures
                            await notify_threshold_reached(client, petition_data, message_id)
                            await mark_threshold_reached(message_id)
                        
                        await message.edit(embed=embed)
                    
                    corrections_made += 1
                    
            except discord.HTTPException as e:
                if e.status == 429:  # Rate limited
                    retry_after = getattr(e, 'retry_after', 5)
                    print(f"⚠️ Rate limited while verifying petition {message_id_str}, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                elif e.status == 404:  # Message not found
                    petition_title = petition_data.get('title', 'Unknown')
                    print(f"📋 Message not found for petition '{petition_title}' (ID: {message_id_str})")
                    await mark_petition_invalid(int(message_id_str), "Message not found (404)")
                else:
                    print(f"❌ HTTP error verifying petition {message_id_str}: {e}")
            except discord.NotFound:
                petition_title = petition_data.get('title', 'Unknown')
                print(f"📋 Message not found for petition '{petition_title}' (ID: {message_id_str})")
                await mark_petition_invalid(int(message_id_str), "Message not found")
            except Exception as e:
                print(f"Error verifying petition {message_id_str}: {e}")
        
        if skipped_expired > 0:
            print(f"⏭️  Skipped {skipped_expired} expired petitions (older than {PETITION_EXPIRY_DAYS} days)")
        
        if corrections_made > 0:
            print(f"Corrected {corrections_made} petition signature counts")
        else:
            print("All petition signature counts verified as accurate")
            
    except Exception as e:
        print(f"Error verifying petition signature counts: {e}")

async def start_petition_signature_checker(client: discord.Client):
    """Start periodic check for petition signature accuracy (runs every hour)"""
    while True:
        try:
            await asyncio.sleep(3600)  # 1 hour
            await verify_petition_signature_counts(client)
        except Exception as e:
            print(f"Error in petition signature checker: {e}")
            await asyncio.sleep(1800)  # Wait 30 minutes before retrying

async def start_petition_expiry_checker(client: discord.Client):
    """Start periodic check for expired petitions (runs every 6 hours)"""
    while True:
        try:
            await asyncio.sleep(21600)  # 6 hours
            await check_all_petitions_for_expiry(client)
        except Exception as e:
            print(f"Error in petition expiry checker: {e}")
            await asyncio.sleep(3600)  # Wait 1 hour before retrying

async def notify_threshold_reached(client: discord.Client, petition_data: dict, message_id: int):
    """Notify admins when petition reaches threshold"""
    try:
        # Get submission channel
        submission_channel = client.get_channel(PETITION_SUBMISSION_CHANNEL_ID)
        if not submission_channel:
            print("Petition submission channel not found")
            return
        
        # Create notification embed
        embed = discord.Embed(
            title="Petition Threshold Reached",
            description=f"A petition has reached {SIGNATURE_THRESHOLD} signatures and requires admin review.",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        
        embed.add_field(
            name="Petition Title",
            value=petition_data['title'],
            inline=False
        )
        
        embed.add_field(
            name="Author",
            value=f"<@{petition_data['author_id']}> ({petition_data['author_name']})",
            inline=False
        )
        
        embed.add_field(
            name="Signatures",
            value=f"{petition_data['signatures']}/{SIGNATURE_THRESHOLD}",
            inline=False
        )
        
        embed.add_field(
            name="Created",
            value=f"<t:{int(datetime.fromisoformat(petition_data['created_at'].replace('Z', '+00:00')).timestamp())}:R>",
            inline=False
        )
        
        if petition_data.get('link'):
            embed.add_field(
                name="Link",
                value=petition_data['link'],
                inline=False
            )
        
        embed.add_field(
            name="Original Message",
            value=f"https://discord.com/channels/{submission_channel.guild.id}/{PETITIONS_CHANNEL_ID}/{message_id}",
            inline=False
        )
        
        # Send notification with admin ping
        await submission_channel.send(
            f"<@&{ADMIN_ROLE_ID}> A petition has reached the signature threshold.",
            embed=embed
        )
        
        print(f"Notified admins about petition threshold reached: {petition_data['title']}")
        
    except Exception as e:
        print(f"Error notifying threshold reached: {e}")

# Command registration - using command group for cleaner /petition subcommands
petition_group = app_commands.Group(name="petition", description="Petition system commands")

@petition_group.command(name="create", description="Create a new petition")
async def petition_create_command(interaction: discord.Interaction):
    """Create a new petition with a form"""
    
    # Show the petition modal
    modal = PetitionModal()
    await interaction.response.send_modal(modal)

@petition_group.command(name="repair", description="[ADMIN] Repair petition system - fix missing reactions, counts, and threads")
async def petition_repair_command(interaction: discord.Interaction):
    """Admin command to repair petition system"""
    # Check if user has admin role
    user_roles = [role.id for role in interaction.user.roles]
    if ADMIN_ROLE_ID not in user_roles:
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    await interaction.response.defer()
    
    try:
        # Run petition repair
        await repair_petition_system(interaction.client)
        
        embed = discord.Embed(
            title="🔧 Petition System Repair Complete",
            description="The petition system has been checked and repaired.",
            color=0x00ff00,
            timestamp=datetime.now(timezone.utc)
        )
        
        embed.add_field(
            name="✅ Repairs Applied",
            value=(
                "• Added missing ballpoint pen reactions\n"
                "• Fixed signature counts in embeds\n"
                "• Updated stored signature data\n"
                "• Created missing discussion threads\n"
                "• Fixed embed colors for completed petitions"
            ),
            inline=False
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error repairing petitions: {str(e)}", ephemeral=True)
        print(f"Error in petition_repair_command: {e}")

@petition_group.command(name="invalid", description="[ADMIN] View and manage invalid petitions")
async def petition_invalid_command(interaction: discord.Interaction):
    """Admin command to view and manage invalid petitions"""
    # Check if user has admin role
    user_roles = [role.id for role in interaction.user.roles]
    if ADMIN_ROLE_ID not in user_roles:
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    try:
        petitions = await load_petition_data()
        invalid_petitions = {k: v for k, v in petitions.items() if v.get('invalid', False)}
        
        if not invalid_petitions:
            embed = discord.Embed(
                title="✅ No Invalid Petitions",
                description="All petitions are currently valid.",
                color=0x00ff00,
                timestamp=datetime.now(timezone.utc)
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🚫 Invalid Petitions Report",
            description=f"Found {len(invalid_petitions)} invalid petition(s)",
            color=0xff6b6b,
            timestamp=datetime.now(timezone.utc)
        )
        
        count = 0
        for message_id_str, petition_data in invalid_petitions.items():
            if count >= 10:  # Limit to 10 entries to avoid embed limits
                embed.add_field(
                    name="...",
                    value=f"And {len(invalid_petitions) - count} more invalid petitions",
                    inline=False
                )
                break
            
            title = petition_data.get('title', 'Unknown')[:100]
            reason = petition_data.get('invalid_reason', 'Unknown reason')
            marked_at = petition_data.get('marked_invalid_at', 'Unknown time')
            
            if marked_at != 'Unknown time':
                try:
                    marked_dt = datetime.fromisoformat(marked_at.replace('Z', '+00:00'))
                    marked_at = f"<t:{int(marked_dt.timestamp())}:R>"
                except:
                    marked_at = "Unknown time"
            
            embed.add_field(
                name=f"📋 {title}",
                value=f"**ID:** `{message_id_str}`\n**Reason:** {reason}\n**Marked:** {marked_at}",
                inline=False
            )
            count += 1
        
        embed.set_footer(text="These petitions will be skipped in future checks")
        await interaction.followup.send(embed=embed, ephemeral=True)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error checking invalid petitions: {str(e)}", ephemeral=True)
        print(f"Error in petition_invalid_command: {e}")

# Function to register reaction handlers
def setup_petition_handlers(client: discord.Client):
    """Set up petition reaction handlers and expiry checker"""
    
    # Store the original event handlers if they exist
    original_reaction_add = getattr(client, '_original_on_raw_reaction_add', None)
    original_reaction_remove = getattr(client, '_original_on_raw_reaction_remove', None)
    
    async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
        """Handle reaction additions"""
        # Call original handler if it exists
        if original_reaction_add:
            await original_reaction_add(payload)
        
        # Handle petition reactions
        await handle_petition_reaction(payload, client)
    
    async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
        """Handle reaction removals"""
        # Call original handler if it exists
        if original_reaction_remove:
            await original_reaction_remove(payload)
        
        # Handle petition reactions
        await handle_petition_reaction(payload, client)
    
    # Store original handlers if they exist
    if hasattr(client, 'on_raw_reaction_add'):
        client._original_on_raw_reaction_add = client.on_raw_reaction_add
    if hasattr(client, 'on_raw_reaction_remove'):
        client._original_on_raw_reaction_remove = client.on_raw_reaction_remove
    
    # Override the event handlers
    client.on_raw_reaction_add = on_raw_reaction_add
    client.on_raw_reaction_remove = on_raw_reaction_remove
    
    # Start petition system with staggered initialization to prevent rate limiting
    asyncio.create_task(staggered_petition_startup(client))

async def staggered_petition_startup(client: discord.Client):
    """Start petition system components with staggered timing to prevent rate limiting"""
    print("🚀 Starting petition system with staggered initialization...")
    
    # Phase 1: Start background checkers first (no immediate API calls)
    asyncio.create_task(start_petition_expiry_checker(client))
    print("✅ Petition expiry checker started (checks every 6 hours)")
    
    await asyncio.sleep(2)  # Wait 2 seconds
    
    asyncio.create_task(start_petition_signature_checker(client))
    print("✅ Petition signature verification checker started (checks every hour)")
    
    await asyncio.sleep(3)  # Wait 3 seconds
    
    # Phase 2: Run repair system (heavy API usage)
    print("🔧 Starting petition system repair...")
    await repair_petition_system(client)
    
    await asyncio.sleep(5)  # Wait 5 seconds after repair
    
    # Phase 4: Run initial verification checks
    print("🔍 Running initial petition checks...")
    await check_all_petitions_for_expiry(client)
    
    await asyncio.sleep(3)  # Wait 3 seconds
    
    await verify_petition_signature_counts(client)
    
    print("✅ Petition system fully initialized with rate limiting protection")

def setup_petition_commands(tree):
    """Register petition commands with the command tree"""
    tree.add_command(petition_group)
    print("✅ Petition commands registered successfully")

# Export the command group (for backward compatibility)
petition = petition_group
