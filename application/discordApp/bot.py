import sys
import os
import logging
from pathlib import Path
import asyncio

#environment variables to suppress noisy logs and progress bars from ML libraries
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

logging.basicConfig(level=logging.ERROR)
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)

import discord
from discord.ext import commands
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


load_dotenv(PROJECT_ROOT / ".env")

BOT_TOKEN = os.getenv("DISCORD_TOKEN") or os.getenv("DISCORD_BOT_TOKEN")


intents = discord.Intents.default()
intents.message_content = True

class DiscosBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!", 
            intents=intents,
            help_command=commands.DefaultHelpCommand()
        )
        
    async def setup_hook(self):
        """
        Executed before the bot connects to Discord.
        Loads all cogs from the `cogs` directory.
        """
        cogs_dir = Path(__file__).resolve().parent / "cogs"
        if not cogs_dir.exists():
            cogs_dir.mkdir(parents=True, exist_ok=True)
            
        # Load cogs
        for filename in os.listdir(cogs_dir):
            if filename.endswith(".py") and not filename.startswith("__"):
                extension = f"cogs.{filename[:-3]}"
                try:
                    await self.load_extension(extension)
                    print(f"Loaded extension '{extension}'")
                except Exception as e:
                    print(f"Failed to load extension {extension}: {e}")

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        print("------")
        print("Bot is ready. Modular cogs have been loaded.")

    async def on_command_error(self, ctx, error):
        """Global error handler for commands."""
        if isinstance(error, commands.CommandNotFound):
            return
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Missing required argument: {error.param.name}")
        else:
            logging.error(f"Ignoring exception in command {ctx.command}:", exc_info=error)
            await ctx.send("An unexpected error occurred while processing your command.")

bot = DiscosBot()

if __name__ == "__main__":
    if not BOT_TOKEN:
        print("Error: DISCORD_TOKEN or DISCORD_BOT_TOKEN not found in .env file.")
        sys.exit(1)
    

    bot.run(BOT_TOKEN)
