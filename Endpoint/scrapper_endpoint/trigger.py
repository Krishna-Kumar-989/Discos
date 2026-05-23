import sys
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCRAPPER_ROOT = PROJECT_ROOT / "Scrapper"

async def trigger_scrapper(
    server_id: str,
    discord_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Programmatically trigger the Discord scraper for a specific server (guild) name or ID.
    
    Args:
        server_id: The guild ID (as digit string) or name of the server to scrape.
        discord_token: Discord bot user token. If not provided, loads from project root .env.
        
    Returns:
        A dictionary containing the scraping execution status.
    """
 
    original_path = sys.path.copy()
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    if str(SCRAPPER_ROOT) not in sys.path:
        sys.path.insert(0, str(SCRAPPER_ROOT))
        
  
    saved_modules = {}
    modules_to_isolate = [
        "config", "utils", "utils.logger", "utils.file_utils", 
        "utils.date_utils", "exporters", "exporters.channel_exporter", 
        "exporters.thread_exporter", "exporters.message_serializer"
    ]
    for mod in modules_to_isolate:
        if mod in sys.modules:
            saved_modules[mod] = sys.modules.pop(mod)
            
    try:
     
        from dotenv import load_dotenv
        import os
        
     
        env_path = PROJECT_ROOT / ".env"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)
            
        token = discord_token or os.getenv("DISCORD_TOKEN")
        if not token:
            raise ValueError("Discord token not found. Please set DISCORD_TOKEN in env or pass it.")
            
        from runner import run_scraper
        
        scrape_status = await run_scraper(discord_token=token, servers=[server_id])
        scrape_status["server_id"] = server_id
        return scrape_status
        
    except Exception as e:
        return {
            "status": "error",
            "server_id": server_id,
            "error": str(e)
        }
    finally:

        sys.path = original_path
     
        for mod in modules_to_isolate:
            if mod in sys.modules:
                sys.modules.pop(mod)
            if mod in saved_modules:
                sys.modules[mod] = saved_modules[mod]
