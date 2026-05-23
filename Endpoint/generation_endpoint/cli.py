import sys
import asyncio
import os
import logging
from pathlib import Path


os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"


logging.basicConfig(level=logging.ERROR)
logging.getLogger().setLevel(logging.ERROR)
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Endpoint.generation_endpoint.query import query_generation_pipeline
from Retrieval.stage_1.retriever import Stage1Retriever
from Retrieval.stage_1.config import load_config as load_retrieval_config


try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

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
    print("=== Discos Simple Chatbox CLI ===")
    
    from dotenv import load_dotenv
    env_path = PROJECT_ROOT / ".env"
    load_dotenv(dotenv_path=env_path)
    token = os.getenv("DISCORD_TOKEN") or os.getenv("DISCORD_BOT_TOKEN")
    
    if token:
        guilds = await get_bot_guilds(token)
        if guilds:
            print("\nServers the bot is currently active in (for reference):")
            for g in guilds:
                print(f"  - {g['name']} (ID: {g['id']})")
    
    print("\n" + "-"*40)
    #Resolve available servers
    try:
        retrieval_cfg = load_retrieval_config()
        retriever = Stage1Retriever(retrieval_cfg)
        server_ids = retriever.get_available_servers()
    except Exception as e:
        print(f"Error loading indexed servers: {e}")
        return

    if not server_ids:
        print("No indexed servers found in LocalState. Please index a server first.")
        return

    print("Available Servers:")
    for idx, s_id in enumerate(server_ids):
        print(f"  [{idx + 1}] ID: {s_id}")

    server_id = None
    while not server_id:
        try:
            choice = input("\nSelect a server (number or server ID): ").strip()
            if not choice:
                continue
            if choice.isdigit() and 1 <= int(choice) <= len(server_ids):
                server_id = server_ids[int(choice) - 1]
            elif choice in server_ids:
                server_id = choice
            else:
                resolved = retriever.resolve_server_id(choice)
                if resolved:
                    server_id = resolved
                else:
                    print("Invalid server selection. Please try again.")
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            return

    print(f"\nChat session started for server: {server_id}")
    print("Type your question and press Enter. Type 'exit' or 'quit' to exit.\n")

    while True:
        try:
            query = input("Ask a question: ").strip()
            if not query:
                continue
            if query.lower() in ["exit", "quit"]:
                print("Goodbye!")
                break

            print("Generating answer...")
            result = await query_generation_pipeline(query=query, server_id=server_id)
            print("\nAnswer:")
            print(result.get("response", "No answer generated."))
            print("-" * 50 + "\n")
            
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

if __name__ == "__main__":
    asyncio.run(main())
