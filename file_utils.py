#!/usr/bin/env python3
"""
Simplified File Utils for VCBot - Petition Only
Contains only essential directory management functions

Python 3.13+ Ready: Uses pathlib for modern file operations
"""

from pathlib import Path
import os

# Get working directory
BASE_DIR = Path.cwd()

# =============================================================================
# DIRECTORY MANAGEMENT
# =============================================================================

def ensure_directories():
    """Ensure essential directories exist."""
    try:
        # Create data directory for petition storage
        data_dir = BASE_DIR / "data"
        data_dir.mkdir(exist_ok=True)
        
        print(f"Data directory ready: {data_dir}")
        
    except Exception as e:
        print(f"Error creating directories: {e}")
        raise

# Initialize directories on import
if __name__ != "__main__":
    ensure_directories()