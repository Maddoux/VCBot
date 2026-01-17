#!/usr/bin/env python3
"""
Simplified configuration for VCBot - Petition Only
Contains only essential settings for petition functionality

Python 3.13+ Ready: Uses pathlib and modern environment handling
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# =============================================================================
# ESSENTIAL CONFIGURATION
# =============================================================================

# Bot credentials
BOT_ID = int(os.getenv("BOT_ID", 0))
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD", 654458344781774879))  # Default to main guild

# Channel IDs
FACECLAIM_CHANNEL_ID = int(os.getenv("FACECLAIM_CHANNEL_ID", 940417384827740210))

# Role IDs  
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID", 654477469004595221))

# Validate required settings
if not DISCORD_TOKEN:
    raise ValueError("DISCORD_TOKEN environment variable must be set")

if not BOT_ID:
    raise ValueError("BOT_ID environment variable must be set")

# =============================================================================
# DIRECTORIES
# =============================================================================

# File paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

print(f"Config loaded - Guild: {GUILD_ID}, Data: {DATA_DIR}")