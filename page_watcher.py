"""
Private page watcher - DMs a specific user when a webpage changes
"""

import discord
import aiohttp
import asyncio
from pathlib import Path

# Configuration
TARGET_USER_ID = 272788643662528514
PAGE_URL = "https://www.findbolig.nu/da-dk/udlejere/frederiksberg-boligfond/ekstern-venteliste"
CLOSED_TEXT = "Lukket for opskrivning"
CHECK_INTERVAL_SECONDS = 60  # Check every minute

# State file to persist across restarts
STATE_FILE = Path("data") / ".page_watcher_state"

async def check_page() -> tuple[bool, str | None]:
    """Check if the page still contains the closed text. Returns (is_open, error_message)."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(PAGE_URL, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    html = await response.text()
                    return (CLOSED_TEXT not in html, None)
                else:
                    return (False, f"HTTP {response.status}")
    except asyncio.TimeoutError:
        return (False, "Connection timed out")
    except aiohttp.ClientError as e:
        return (False, f"Connection error: {type(e).__name__}")
    except Exception as e:
        return (False, f"Error: {type(e).__name__}")
    return (False, None)

def was_notified() -> bool:
    """Check if we already sent a notification"""
    try:
        return STATE_FILE.exists()
    except:
        return False

def mark_notified():
    """Mark that we sent a notification"""
    try:
        STATE_FILE.parent.mkdir(exist_ok=True)
        STATE_FILE.touch()
    except:
        pass

def clear_notification():
    """Clear the notification state (page closed again)"""
    try:
        if STATE_FILE.exists():
            STATE_FILE.unlink()
    except:
        pass

# Track consecutive errors to avoid spamming
ERROR_STATE_FILE = Path("data") / ".page_watcher_error"

def was_error_notified() -> bool:
    try:
        return ERROR_STATE_FILE.exists()
    except:
        return False

def mark_error_notified():
    try:
        ERROR_STATE_FILE.parent.mkdir(exist_ok=True)
        ERROR_STATE_FILE.touch()
    except:
        pass

def clear_error_notification():
    try:
        if ERROR_STATE_FILE.exists():
            ERROR_STATE_FILE.unlink()
    except:
        pass

async def page_watcher_loop(client: discord.Client):
    """Background task that monitors the page"""
    await client.wait_until_ready()
    consecutive_errors = 0
    
    while not client.is_closed():
        try:
            is_open, error = await check_page()
            
            if error:
                consecutive_errors += 1
                # Only notify after 5 consecutive errors and haven't notified yet
                if consecutive_errors >= 5 and not was_error_notified():
                    user = await client.fetch_user(TARGET_USER_ID)
                    if user:
                        await user.send(
                            f"⚠️ **Page Watcher Error**\n\n"
                            f"Having trouble checking the Frederiksberg Boligfond page.\n"
                            f"Error: {error}\n\n"
                            f"Will keep trying..."
                        )
                        mark_error_notified()
            else:
                # Successful check, reset error counter
                if consecutive_errors > 0:
                    consecutive_errors = 0
                    clear_error_notification()
                
                if is_open and not was_notified():
                    # Page changed - sign-ups are open!
                    user = await client.fetch_user(TARGET_USER_ID)
                    if user:
                        await user.send(
                            f"🚨 **Frederiksberg Boligfond - Venteliste er ÅBEN!**\n\n"
                            f"Teksten \"Lukket for opskrivning\" er ikke længere på siden.\n\n"
                            f"🔗 {PAGE_URL}"
                        )
                        mark_notified()
                elif not is_open and was_notified():
                    # Page closed again, reset state for future notifications
                    clear_notification()
                
        except:
            pass
        
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)

def setup_page_watcher(client: discord.Client):
    """Start the page watcher background task"""
    asyncio.create_task(page_watcher_loop(client))
