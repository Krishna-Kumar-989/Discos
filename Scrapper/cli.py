import sys
import argparse
import asyncio
from pathlib import Path
from typing import List, Optional

# Resolve paths to allow correct imports
SCRAPPER_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = SCRAPPER_ROOT.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SCRAPPER_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRAPPER_ROOT))

from runner import run_scraper
from config import TOKEN

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Discos Modular Discord Scraper CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "-s", "--server",
        action="append",
        help="Discord Server ID or case-insensitive Name to scrape. Can specify multiple times."
    )
    parser.add_argument(
        "-t", "--token",
        help="Discord Bot Token to use (overrides env/config token)."
    )
    return parser.parse_args()

async def main():
    args = parse_args()
    
    # Resolve bot token
    token = args.token or TOKEN
    if not token:
        print("Error: Discord token not found. Please set DISCORD_TOKEN in your .env or pass it via --token / -t.")
        sys.exit(1)
        
    servers = args.server
    if servers:
        print(f"Starting scraper for server(s): {', '.join(servers)}")
    else:
        print("No specific servers specified. Starting scraper for all servers.")
        
    result = await run_scraper(discord_token=token, servers=servers)
    
    if result.get("status") == "success":
        print(f"\nScraping completed successfully! Processed {result.get('channels_processed')} channels.")
        sys.exit(0)
    else:
        print(f"\nScraping failed with error: {result.get('error')}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
