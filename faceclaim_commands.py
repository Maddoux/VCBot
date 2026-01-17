#!/usr/bin/env python3
"""
Faceclaim System for VCBot
Handles roleplay character faceclaims with uniqueness validation

Python 3.13+ Ready: Uses modern typing, async/await, and pathlib
"""

import discord
from discord import app_commands
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import json
import re
from pathlib import Path
import config
import aiohttp

# Configuration
FACECLAIM_DATA_FILE = Path("data") / "faceclaims.json"

class FaceClaimManager:
    """Manages faceclaim data and operations"""
    
    def __init__(self):
        self.data = self.load_data()
    
    def load_data(self) -> Dict[str, Any]:
        """Load faceclaim data from JSON file"""
        try:
            if FACECLAIM_DATA_FILE.exists():
                with open(FACECLAIM_DATA_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading faceclaim data: {e}")
        
        return {
            "claims": {},  # user_id -> claim_data
            "taken_faces": {}  # normalized_name -> user_id
        }
    
    def save_data(self):
        """Save faceclaim data to JSON file"""
        try:
            FACECLAIM_DATA_FILE.parent.mkdir(exist_ok=True)
            with open(FACECLAIM_DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving faceclaim data: {e}")
            raise
    
    def normalize_name(self, name: str) -> str:
        """Normalize faceclaim name for comparison (case-insensitive)"""
        return name.lower().strip()
    
    def is_faceclaim_taken(self, faceclaim: str, exclude_user: int = None) -> Optional[int]:
        """
        Check if a faceclaim is already taken by another user
        Returns user_id of the current claimant, or None if available
        """
        normalized = self.normalize_name(faceclaim)
        current_user = self.data["taken_faces"].get(normalized)
        
        if current_user and current_user != exclude_user:
            return current_user
        return None
    
    def get_user_claim(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get a user's current faceclaim data"""
        return self.data["claims"].get(str(user_id))
    
    def set_user_claim(self, user_id: int, rpname: str, faceclaim: str, image_url: str, message_id: int):
        """Set or update a user's faceclaim"""
        user_id_str = str(user_id)
        
        # Remove old faceclaim from taken_faces if user had one
        old_claim = self.get_user_claim(user_id)
        if old_claim:
            old_normalized = self.normalize_name(old_claim["faceclaim"])
            if old_normalized in self.data["taken_faces"]:
                del self.data["taken_faces"][old_normalized]
        
        # Add new claim
        normalized = self.normalize_name(faceclaim)
        self.data["taken_faces"][normalized] = user_id
        self.data["claims"][user_id_str] = {
            "rpname": rpname,
            "faceclaim": faceclaim,
            "image_url": image_url,
            "message_id": message_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        self.save_data()
    
    def remove_user_claim(self, user_id: int):
        """Remove a user's faceclaim completely"""
        user_id_str = str(user_id)
        claim = self.get_user_claim(user_id)
        
        if claim:
            # Remove from taken_faces
            normalized = self.normalize_name(claim["faceclaim"])
            if normalized in self.data["taken_faces"]:
                del self.data["taken_faces"][normalized]
            
            # Remove from claims
            del self.data["claims"][user_id_str]
            
            self.save_data()
            return claim
        return None

# Global manager instance
faceclaim_manager = FaceClaimManager()

async def validate_image_url(url: str) -> bool:
    """Validate that a URL is a valid HTTP(S) link"""
    if not url:
        return True  # Optional parameter, so empty is valid
    
    try:
        # Just check if it's a valid HTTP(S) URL format
        # Be lenient - accept any valid URL instead of checking content-type
        if not re.match(r'^https?://.+\..+', url):
            return False
        
        return True
    except Exception:
        return False

def create_faceclaim_embed(user: discord.Member, rpname: str, faceclaim: str, image_url: str) -> discord.Embed:
    """Create an embed for faceclaim display"""
    embed = discord.Embed(
        title=f"{rpname}",
        color=discord.Color.blue(),
        timestamp=datetime.now(timezone.utc)
    )
    
    embed.add_field(
        name="Player", 
        value=user.mention, 
        inline=False
    )
    
    embed.add_field(
        name="Character Name", 
        value=rpname, 
        inline=False
    )
    
    embed.add_field(
        name="Face Claim", 
        value=faceclaim, 
        inline=False
    )
    
    if image_url:
        embed.set_image(url=image_url)
        embed.add_field(
            name="Reference Image", 
            value=f"[View Image]({image_url})", 
            inline=False
        )
    
    embed.set_footer(
        text=f"Claimed by {user.display_name}", 
        icon_url=user.display_avatar.url
    )
    
    return embed

@app_commands.command(name="claim", description="Claim a face for your roleplay character")
@app_commands.describe(
    rpname="Your character's roleplay name",
    faceclaim="The real person you want to use as your character's face",
    image="Optional: Direct image URL for reference"
)
async def claim_face(interaction: discord.Interaction, rpname: str, faceclaim: str, image: str = None):
    """Claim a faceclaim for roleplay character"""
    await interaction.response.defer()
    
    try:
        # Validate input lengths
        if len(rpname) > 100:
            await interaction.followup.send("Character name must be 100 characters or less.", ephemeral=True)
            return
        
        if len(faceclaim) > 150:
            await interaction.followup.send("Face claim name must be 150 characters or less.", ephemeral=True)
            return
        
        # Validate image URL if provided
        if image and not await validate_image_url(image):
            await interaction.followup.send("The provided URL is not valid. Please provide a valid http:// or https:// link.", ephemeral=True)
            return
        
        # Check if faceclaim is already taken by another user
        current_claimant = faceclaim_manager.is_faceclaim_taken(faceclaim, exclude_user=interaction.user.id)
        if current_claimant:
            try:
                claimant_user = await interaction.client.fetch_user(current_claimant)
                claimant_mention = claimant_user.mention
            except:
                claimant_mention = f"User ID: {current_claimant}"
            
            await interaction.followup.send(
                f"**Face claim already taken!**\n"
                f"'{faceclaim}' is already claimed by {claimant_mention}.\n\n"
                f"*Admins can use `/override` if this is an error.*",
                ephemeral=True
            )
            return
        
        # Get faceclaim channel
        channel = interaction.guild.get_channel(config.FACECLAIM_CHANNEL_ID)
        if not channel:
            await interaction.followup.send("Face claim channel not found. Please contact an admin.", ephemeral=True)
            return
        
        # Check if user already has a faceclaim (for updating)
        old_claim = faceclaim_manager.get_user_claim(interaction.user.id)
        old_message = None
        
        if old_claim and old_claim.get("message_id"):
            try:
                old_message = await channel.fetch_message(old_claim["message_id"])
            except:
                pass  # Message might be deleted
        
        # Create and send new faceclaim embed
        embed = create_faceclaim_embed(interaction.user, rpname, faceclaim, image or "")
        
        if old_message:
            # Update existing message
            try:
                await old_message.edit(embed=embed)
                message = old_message
            except:
                # If edit fails, send new message
                message = await channel.send(embed=embed)
        else:
            # Send new message
            message = await channel.send(embed=embed)
        
        # Save the claim
        faceclaim_manager.set_user_claim(
            interaction.user.id,
            rpname,
            faceclaim,
            image or "",
            message.id
        )
        
        # Send success response
        action = "updated" if old_claim else "created"
        await interaction.followup.send(
            f"**Face claim {action} successfully!**\n"
            f"**Character:** {rpname}\n"
            f"**Face Claim:** {faceclaim}\n"
            f"Posted in {channel.mention}",
            ephemeral=True
        )
        
    except Exception as e:
        await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)
        print(f"Error in claim_face: {e}")

@app_commands.command(name="see", description="View someone's face claim")
@app_commands.describe(user="The user whose face claim you want to see")
async def see_faceclaim(interaction: discord.Interaction, user: discord.Member):
    """View a user's current faceclaim"""
    claim = faceclaim_manager.get_user_claim(user.id)
    
    if not claim:
        await interaction.response.send_message(
            f"**This user does not have a face claim yet!**\n"
            f"{user.mention} hasn't set up a character face claim.",
            ephemeral=True
        )
        return
    
    # Create embed to display the faceclaim
    embed = create_faceclaim_embed(
        user, 
        claim["rpname"], 
        claim["faceclaim"], 
        claim["image_url"]
    )
    
    # Add timestamp of when it was claimed
    try:
        claimed_time = datetime.fromisoformat(claim["timestamp"])
        embed.add_field(
            name="Claimed On",
            value=f"<t:{int(claimed_time.timestamp())}:f>",
            inline=False
        )
    except:
        pass
    
    await interaction.response.send_message(embed=embed, ephemeral=False)

@app_commands.command(name="kill", description="Admin only: Remove a character's face claim")
@app_commands.describe(user="The user whose character to kill/remove")
async def kill_character(interaction: discord.Interaction, user: discord.Member):
    """Admin command to remove a user's faceclaim"""
    # Check if user has admin role
    if config.ADMIN_ROLE_ID not in [role.id for role in interaction.user.roles]:
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    await interaction.response.defer()
    
    try:
        # Get user's claim
        claim = faceclaim_manager.get_user_claim(user.id)
        if not claim:
            await interaction.followup.send(
                f"**This user does not have a face claim yet!**\n"
                f"{user.mention} doesn't have a character to kill.",
                ephemeral=True
            )
            return
        
        # Try to delete the message from faceclaim channel
        if claim.get("message_id"):
            try:
                faceclaim_channel = interaction.client.get_channel(config.FACECLAIM_CHANNEL_ID)
                if faceclaim_channel:
                    message = await faceclaim_channel.fetch_message(claim["message_id"])
                    await message.delete()
            except Exception as e:
                print(f"Couldn't delete faceclaim message: {e}")
        
        # Remove the claim from data
        faceclaim_manager.remove_user_claim(user.id)
        
        await interaction.followup.send(
            f"**Character killed successfully!**\n"
            f"Removed {user.mention}'s character **{claim['rpname']}** (face: {claim['faceclaim']}).",
            ephemeral=False
        )
        
    except Exception as e:
        await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)
        print(f"Error in kill_character: {e}")

@app_commands.command(name="override", description="Admin only: Override faceclaim uniqueness check")
@app_commands.describe(
    user="The user to set the faceclaim for",
    rpname="Character's roleplay name", 
    faceclaim="The face claim (will override existing)",
    image="Optional: Direct image URL for reference"
)
async def override_faceclaim(interaction: discord.Interaction, user: discord.Member, rpname: str, faceclaim: str, image: str = None):
    """Admin command to override faceclaim restrictions"""
    # Check if user has admin role
    if config.ADMIN_ROLE_ID not in [role.id for role in interaction.user.roles]:
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    await interaction.response.defer()
    
    try:
        # Validate input lengths
        if len(rpname) > 100:
            await interaction.followup.send("Character name must be 100 characters or less.", ephemeral=True)
            return
        
        if len(faceclaim) > 150:
            await interaction.followup.send("Face claim name must be 150 characters or less.", ephemeral=True)
            return
        
        # Validate image URL if provided
        if image and not await validate_image_url(image):
            await interaction.followup.send("The provided URL is not valid. Please provide a valid http:// or https:// link.", ephemeral=True)
            return
        
        # Check who currently has this faceclaim
        current_claimant = faceclaim_manager.is_faceclaim_taken(faceclaim, exclude_user=user.id)
        override_msg = ""
        
        if current_claimant:
            try:
                current_user = await interaction.client.fetch_user(current_claimant)
                override_msg = f"\n*Override: Removed from {current_user.mention}*"
                
                # Remove the old claim
                faceclaim_manager.remove_user_claim(current_claimant)
                
                # Try to delete their old message
                old_claim = faceclaim_manager.get_user_claim(current_claimant)
                if old_claim and old_claim.get("message_id"):
                    try:
                        faceclaim_channel = interaction.client.get_channel(config.FACECLAIM_CHANNEL_ID)
                        if faceclaim_channel:
                            old_message = await faceclaim_channel.fetch_message(old_claim["message_id"])
                            await old_message.delete()
                    except:
                        pass
            except Exception as e:
                print(f"Error handling override: {e}")
        
        # Get faceclaim channel
        faceclaim_channel = interaction.client.get_channel(config.FACECLAIM_CHANNEL_ID)
        if not faceclaim_channel:
            await interaction.followup.send("Face claim channel not found.", ephemeral=True)
            return
        
        # Remove user's old claim if they had one
        old_claim = faceclaim_manager.get_user_claim(user.id)
        if old_claim and old_claim.get("message_id"):
            try:
                old_message = await faceclaim_channel.fetch_message(old_claim["message_id"])
                await old_message.delete()
            except:
                pass
        
        # Create and send new faceclaim embed
        embed = create_faceclaim_embed(user, rpname, faceclaim, image or "")
        embed.color = 0xff6600  # Orange color to indicate admin override
        embed.set_footer(
            text=f"Admin Override by {interaction.user.display_name} | {embed.footer.text}",
            icon_url=interaction.user.display_avatar.url
        )
        
        message = await faceclaim_channel.send(embed=embed)
        
        # Save the claim
        faceclaim_manager.set_user_claim(
            user.id,
            rpname,
            faceclaim,
            image or "",
            message.id
        )
        
        await interaction.followup.send(
            f"**Admin override successful!**\n"
            f"**User:** {user.mention}\n"
            f"**Character:** {rpname}\n" 
            f"**Face Claim:** {faceclaim}{override_msg}",
            ephemeral=False
        )
        
    except Exception as e:
        await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)
        print(f"Error in override_faceclaim: {e}")

# Export commands for bot registration
claim = claim_face
see = see_faceclaim  
kill = kill_character
override = override_faceclaim