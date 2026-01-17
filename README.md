# VCBot

A Discord bot for Virtual Congress server management, providing petition tracking, faceclaim management, channel archiving, ping permissions, party role enforcement, and automated bump reminders.

## Features

- **Petition System**: Create, vote on, and track petitions with automatic result tallying
- **Faceclaim Management**: Register and manage character faceclaims with duplicate prevention
- **Archive Commands**: Archive Discord channels to HTML for permanent records
- **Ping Permissions**: Control who can use @everyone and @here mentions
- **Party Role Enforcement**: Automatically enforce party affiliation rules
- **Bump Reminders**: Automated reminders for server bumping

## Requirements

- Python 3.13+
- discord.py >= 2.6.0
- python-dotenv >= 1.0.1
- aiohttp >= 3.12.0

## Installation

1. Clone the repository:
```bash
git clone https://github.com/Maddoux/VCBot.git
cd VCBot
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the root directory with the following variables:
```env
DISCORD_TOKEN=your_bot_token_here
BOT_ID=your_bot_id_here
GUILD=your_guild_id_here
FACECLAIM_CHANNEL_ID=your_faceclaim_channel_id
ADMIN_ROLE_ID=your_admin_role_id
```

4. Run the bot:
```bash
python bot.py
```

## Configuration

The bot uses environment variables for configuration. All settings can be found in `config.py`:

- **BOT_ID**: Your Discord bot's user ID
- **DISCORD_TOKEN**: Your Discord bot token
- **GUILD_ID**: The Discord server ID where the bot operates
- **FACECLAIM_CHANNEL_ID**: Channel for faceclaim submissions
- **ADMIN_ROLE_ID**: Role ID for administrative permissions

## Data Storage

The bot stores data in JSON files located in the `data/` directory:

- `petitions.json`: Active and historical petition data
- `faceclaims.json`: Registered faceclaims
- `ping_permissions.json`: Ping permission settings
- `bill_refs.json`: Bill reference tracking
- `channel_restrictions.json`: Channel-specific restrictions

## Commands

### Petition Commands
- Create petitions with voting
- Track petition status
- Automatic result calculation

### Faceclaim Commands
- Register character faceclaims
- Check existing faceclaims
- Prevent duplicate registrations

### Archive Commands
- Archive channels to HTML format
- Preserve message history
- Store in `data/archives/` directory

### Ping Commands
- Manage @everyone and @here permissions
- Role-based ping controls

## Project Structure

```
VCBot/
├── bot.py                      # Main bot entry point
├── config.py                   # Configuration management
├── requirements.txt            # Python dependencies
├── petition_commands.py        # Petition system
├── faceclaim_commands.py       # Faceclaim management
├── archive_commands.py         # Channel archiving
├── ping_commands.py            # Ping permission controls
├── party_role_enforcement.py   # Party affiliation rules
├── bump_commands.py            # Bump reminder system
├── file_utils.py              # File utility functions
└── data/                       # Data storage directory
    ├── petitions.json
    ├── faceclaims.json
    ├── ping_permissions.json
    └── archives/               # Archived channel HTML files
```

## License

This project is provided as-is for use with the Virtual Congress Discord server.

## Support

For issues or questions, please open an issue on the GitHub repository.
