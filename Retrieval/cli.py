import argparse
import asyncio
import logging
import sys
from pathlib import Path


sys.path.append(str(Path(__file__).parent.parent))

try:
    from stage_1.config import load_config
    from stage_1.retriever import Stage1Retriever
except ImportError:
    from Retrieval.stage_1.config import load_config
    from Retrieval.stage_1.retriever import Stage1Retriever

def setup_cli_logging(level_name: str, log_file: Path):
    """Set up standard logging configuration for the CLI."""
    log_file.parent.mkdir(parents=True, exist_ok=True)
    level = getattr(logging, level_name.upper(), logging.INFO)
    
   
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout)
        ]
    )

async def run_search(args):
    
    config = load_config(args.config)
    
   
    log_path = config.get_absolute_path(config.logging.log_file)
    setup_cli_logging(config.logging.level, log_path)
    
    logger = logging.getLogger("retrieval.cli")
    logger.info(f"Initializing Stage-1 Retriever...")
    retriever = Stage1Retriever(config)
    
  
    use_rerank = args.rerank if args.rerank is not None else config.retrieval.rerank
    limit = args.limit if args.limit is not None else config.retrieval.limit
    mode = args.mode if args.mode is not None else config.retrieval.mode

    if use_rerank:
        logger.info(f"Initializing Stage-2 Reranker...")
        try:
            from stage_2.reranker import Stage2Reranker
        except ImportError:
            from Retrieval.stage_2.reranker import Stage2Reranker
        reranker = Stage2Reranker(config)
    else:
        reranker = None
        
    print("\n" + "=" * 80)
    print(f"SEARCHING FOR: '{args.query}'")
    if args.server:
        print(f"Target Server: {args.server}")
    else:
        print("Target Server: [None]")
    print(f"Mode: {mode.upper()} | Limit: {limit} | Stage-2 Rerank: {use_rerank}")
    print("=" * 80)
    
    # Run retrieval
    try:
       
        stage_1_limit = config.retrieval.rerank_prefetch_limit if use_rerank else limit
        hits = await retriever.retrieve(
            query=args.query,
            server_name_or_id=args.server,
            mode=mode,
            limit=stage_1_limit
        )
        
        #Stage-2 Cross-Encoder reranking
        if use_rerank and hits:
            hits = await reranker.rerank(
                query=args.query,
                stage_1_results=hits,
                limit=limit
            )
            
    except ValueError as e:
        print(f"\nError: {e}")
        print("=" * 80 + "\n")
        sys.exit(1)
    
    if not hits:
        print("\nNo matching document chunks found.")
        print("=" * 80)
        return
        
    for idx, hit in enumerate(hits):
        score_str = f"{hit['score']:.4f}" if hit['score'] is not None else "N/A (Lexical Match)"
        print(f"\n[{idx+1}] Score: {score_str} | Server: {hit['server']} ({hit['server_id']})")
        print(f"Channel: #{hit['channel']} | Time Range: {hit['start_timestamp']} -> {hit['end_timestamp']}")
        print(f"Source File: {hit['source_file']}")
        print(f"Snippet:\n{hit['text']}")
        print("-" * 80)
        
    print(f"Total Results Returned: {len(hits)}")
    print("=" * 80 + "\n")

def main():
    try:
       #utf-8 on windows
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

    parser = argparse.ArgumentParser(
        description="Discord Retrieval Pipeline CLI Utility",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--query", 
        type=str, 
        required=True, 
        help="Search query string"
    )
    parser.add_argument(
        "--server", 
        type=str, 
        help="Server name or Guild ID folder name. Must be provided."
    )
    parser.add_argument(
        "--mode", 
        type=str, 
        choices=["semantic", "lexical", "sparse", "hybrid"], 
        default=None, 
        help="Retrieval mode: 'semantic', 'lexical', 'sparse', or 'hybrid' (falls back to config)"
    )
    parser.add_argument(
        "--limit", 
        type=int, 
        default=None, 
        help="Number of results to return (falls back to config)"
    )
    parser.add_argument(
        "--rerank",
        action="store_true",
        default=None,
        help="Enable Stage-2 Cross-Encoder reranking."
    )
    parser.add_argument(
        "--no-rerank",
        action="store_false",
        dest="rerank",
        help="Disable Stage-2 Cross-Encoder reranking."
    )
    parser.add_argument(
        "--config", 
        type=str, 
        help="Path to custom config.yaml file"
    )

    args = parser.parse_args()
    
    asyncio.run(run_search(args))

if __name__ == "__main__":
    main()
