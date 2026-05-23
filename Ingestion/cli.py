import argparse
import sys
from pathlib import Path

# Add project root to sys.path to allow importing from the 'qdrant' module
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from tqdm import tqdm

from config import load_config
from pipeline import ingest_server, get_servers_status, query_server

def cmd_ingest(args):
    try:
        results = ingest_server(
            server_name_or_id=args.server,
            rebuild=args.rebuild,
            progress_callback=tqdm
        )
        for s_id, summary in results.items():
            if summary["status"] == "skipped":
                print(f"Skipping {summary['server_name']} (ID: {s_id}): {summary['reason']}")
            else:
                print(f"Finished server {summary['server_name']} (ID: {s_id}). Index status: {summary['processed']} file(s) indexed, {summary['skipped']} file(s) unchanged/skipped.")
    except Exception as e:
        print(f"Error during ingestion: {e}")
        sys.exit(1)

def cmd_status(args):
    try:
        statuses = get_servers_status()
        print("\n================== LocalState Servers Status ==================")
        for s in statuses:
            print(f"\nServer: {s['server_name']} (ID: {s['server_id']})")
            print(f"  Storage location: {s['db_path']}")
            if s['state_file_exists']:
                print(f"  Indexed files count in state: {s['indexed_files_count']}")
            else:
                print("  Indexed files count: No state file found (not yet ingested)")
            
            if s['collection_name']:
                print(f"  Qdrant collection: {s['collection_name']}")
                print(f"  Total vector points: {s['points_count']}")
                print(f"  Status: {s['collection_status']}")
            else:
                print("  Qdrant collection: Collection not found")
        print("=============================================================")
    except Exception as e:
        print(f"Error getting status: {e}")
        sys.exit(1)

def cmd_query(args):
    try:
        hits = query_server(
            server_name_or_id=args.server,
            text=args.text,
            mode=args.mode,
            limit=args.limit
        )
        
        print("\n" + "=" * 70)
        print(f"SEARCH RESULTS ({args.mode.upper()} MODE) FOR QUERY: '{args.text}'")
        print("=" * 70)
        
        if not hits:
            print("No matches found.")
            return
            
        for idx, hit in enumerate(hits):
            score_str = f"{hit['score']:.4f}" if hit['score'] is not None else "N/A (Lexical Match)"
            print(f"\n[{idx+1}] Match Score: {score_str}")
            print(f"Channel: #{hit['channel']} | Time range: {hit['start_timestamp']} -> {hit['end_timestamp']}")
            print(f"Source file: {hit['source_file']}")
            print(f"Content snippet:\n{hit['text']}")
            print("-" * 70)
    except Exception as e:
        print(f"Error during query: {e}")
        sys.exit(1)

def main():
    try:
        #utf8
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

    parser = argparse.ArgumentParser(
        description="Discord Server Vector Ingestion Pipeline CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command", required=True, help="Subcommands")
    
    # Ingest command
    parser_ingest = subparsers.add_parser("ingest", help="Ingest Discord JSON data into Qdrant")
    parser_ingest.add_argument(
        "--server", 
        type=str, 
        help="Specify server name. If not set, all detected servers will be processed."
    )
    parser_ingest.add_argument(
        "--rebuild", 
        action="store_true", 
        help="Force rebuild index (deletes existing Qdrant collection and re-indexes from scratch)"
    )
    
    # Status command
    subparsers.add_parser("status", help="Show ingestion and vector database status of all servers")
    
    # Query command
    parser_query = subparsers.add_parser("query", help="Query vector database index for a server")
    parser_query.add_argument(
        "--server", 
        type=str, 
        required=True, 
        help="Server index to search"
    )
    parser_query.add_argument(
        "--text", 
        type=str, 
        required=True, 
        help="Text to search for"
    )
    parser_query.add_argument(
        "--limit", 
        type=int, 
        default=5, 
        help="Limit number of search results (default: 5)"
    )
    parser_query.add_argument(
        "--mode", 
        type=str, 
        choices=["semantic", "lexical", "hybrid"], 
        default="semantic", 
        help="Search mode: 'semantic' (dense vector search), 'lexical' (exact keyword match), or 'hybrid' (dense + BM25 sparse + RRF) (default: semantic)"
    )

    args = parser.parse_args()
    
    if args.command == "ingest":
        cmd_ingest(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "query":
        cmd_query(args)

if __name__ == "__main__":
    main()
