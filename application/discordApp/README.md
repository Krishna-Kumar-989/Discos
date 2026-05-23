# Discos Discord App

This module is the Discord frontend for the Discos project. It uses the `discord.py` library to expose the Generation Endpoint pipeline to users via a familiar chat interface.

## Setup

1. Ensure your `.env` file at the root of the project (e.g., `<project_root>/.env`) contains your Discord Bot Token:
```env
DISCORD_TOKEN=your_bot_token_here
```
*(Also ensure that the relevant LLM API keys like `GROQ_API_KEY` are configured in `.env`)*

2. Make sure the bot is invited to your Discord Server and has the **Message Content Intent** enabled in the Discord Developer Portal.

3. Install dependencies from the project root if you haven't already:
```bash
pip install -r ../../requirements.txt
```

## Running the Bot

Run the bot script directly:
```bash
python bot.py
```

## Usage

Once the bot is online and inside a Discord server, users can type:
```
!ask Who set the color roles?
```
or
```
!summary Summarize the backend channel discussion about databases
```

The bot will automatically grab the Discord Server's ID, fetch the relevant context from the Vector Database, generate an answer or summary using the LLM, and reply in the channel!

## Modular Architecture

The Discord bot is built using `discord.py`'s `commands.Cog` extension framework. This allows it to be highly modular and scalable.

- **`bot.py`**: The main entry point. It initializes the bot and dynamically loads all extensions present in the `cogs/` directory.
- **`cogs/`**: Place any new feature modules here. Existing modules include:
  - `generation.py`: Handles the `!ask` and `!summary` commands.
  - `config.py`: Handles the interactive `!config` UI and backend pipeline triggers.

To create a new module, simply add a new Python file in `cogs/` containing a `commands.Cog` class and a `setup(bot)` function, and it will be loaded automatically on startup.
