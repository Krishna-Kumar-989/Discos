import sys
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional

# Resolve paths
SCRAPPER_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = SCRAPPER_ROOT.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SCRAPPER_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRAPPER_ROOT))

import discord
from exporters.channel_exporter import export_channel
from exporters.thread_exporter import export_threads
from utils.logger import log

async def run_scraper(
    discord_token: str,
    servers: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Programmatic entrypoint to run the Discord scraper for specific servers or all servers.
    
    Args:
        discord_token: Discord bot user token.
        servers: Optional list of server IDs (digit string) or server names.
                 If None or empty, scrapes all guilds the bot belongs to.
                 
    Returns:
        A dictionary containing the scraping execution status:
        {
            "status": "success" | "error",
            "channels_processed": int,
            "error": Optional[str]
        }
    """
    intents = discord.Intents.default()
    intents.guilds = True
    intents.messages = True
    intents.message_content = True
    
    client = discord.Client(intents=intents)
    
    scrape_status = {
        "status": "pending",
        "error": None,
        "channels_processed": 0
    }
    
    @client.event
    async def on_ready():
        try:
            log(f"Logged in to Discord as {client.user}")
            
            # Resolve guilds
            guilds_to_scrape = []
            if servers:
                for server_id in servers:
                    guild = None
                    if server_id.isdigit():
                        guild = client.get_guild(int(server_id))
                        if not guild:
                            try:
                                guild = await client.fetch_guild(int(server_id))
                            except Exception:
                                pass
                    
                    if not guild:
                        # Find by name
                        for g in client.guilds:
                            if g.name.lower() == server_id.lower() or str(g.id) == server_id:
                                guild = g
                                break
                                
                    if guild:
                        guilds_to_scrape.append(guild)
                    else:
                        log(f"Warning: Guild '{server_id}' not found or bot does not have access.")
                
                if not guilds_to_scrape:
                    raise ValueError(f"None of the specified servers {servers} could be found or accessed.")
            else:
                guilds_to_scrape = list(client.guilds)
                
            channels_count = 0
            for guild in guilds_to_scrape:
                log("=" * 50)
                log(f"SCRAPING SERVER: {guild.name} (ID: {guild.id})")
                log("=" * 50)
                
                for channel in guild.text_channels:
                    try:
                        await export_channel(channel, str(guild.id), guild.name)
                        channels_count += 1
                    except discord.Forbidden:
                        log(f"No access to channel #{channel.name}")
                    except Exception as ce:
                        log(f"Error scraping channel #{channel.name}: {ce}")
                        
                try:
                    await export_threads(guild)
                except Exception as te:
                    log(f"Thread export error for guild {guild.name}: {te}")
                    
            log(f"Scraper successfully finished. Processed {channels_count} channels.")
            scrape_status["status"] = "success"
            scrape_status["channels_processed"] = channels_count
            
        except Exception as e:
            scrape_status["status"] = "error"
            scrape_status["error"] = str(e)
            log(f"Error during scraper execution: {e}")
        finally:
            await client.close()
            
    try:
        await client.start(discord_token)
    except Exception as e:
        scrape_status["status"] = "error"
        scrape_status["error"] = str(e)
        
    return scrape_status
