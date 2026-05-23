import sys
import asyncio
import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Endpoint.scrapper_endpoint.trigger import trigger_scrapper

async def get_bot_guilds(token: str):
    import httpx
    headers = {"Authorization": f"Bot {token}"}
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get("https://discord.com/api/v10/users/@me/guilds", headers=headers)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
    return []

async def main():
    print("=== Discos Scrapper CLI ===")
    
    from dotenv import load_dotenv
    env_path = PROJECT_ROOT / ".env"
    load_dotenv(dotenv_path=env_path)
    
    token = os.getenv("DISCORD_TOKEN") or os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("Error: Discord token not found in .env (DISCORD_TOKEN or DISCORD_BOT_TOKEN)")
        return
        
    print("Fetching active bot servers...")
    guilds = await get_bot_guilds(token)
    
    print("\nServers the bot is currently active in:")
    if not guilds:
        print("  (Bot is not in any servers or token is invalid)")
    for idx, g in enumerate(guilds):
        print(f"  [{idx + 1}] {g['name']} (ID: {g['id']})")
        
    print("\nType a server ID or name to scrape. Type 'help' to list active servers again, or 'exit' to quit.")
    
    while True:
        try:
            choice = input("\nSelect a server to scrape: ").strip()
            if not choice:
                continue
            if choice.lower() in ["exit", "quit"]:
                break
            if choice.lower() == "help":
                print("\nServers the bot is currently active in:")
                for idx, g in enumerate(guilds):
                    print(f"  [{idx + 1}] {g['name']} (ID: {g['id']})")
                continue
                
            server_id = choice
            if choice.isdigit() and 1 <= int(choice) <= len(guilds):
                server_id = str(guilds[int(choice) - 1]["id"])
                
            print(f"Triggering scrapper for server: {server_id}...")
            result = await trigger_scrapper(server_id=server_id, discord_token=token)
            
            if result.get("status") == "success":
                print(f"Successfully scraped {result.get('channels_processed')} channels!")
            else:
                print(f"Scraping failed: {result.get('error')}")
                
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break

if __name__ == "__main__":
    asyncio.run(main())
