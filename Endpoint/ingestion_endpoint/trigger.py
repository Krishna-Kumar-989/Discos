import sys
from pathlib import Path
from typing import Dict, Any, Optional


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
INGESTION_ROOT = PROJECT_ROOT / "Ingestion"

def trigger_ingestion(
    server_id: str,
    rebuild: bool = False,
    config_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Programmatically trigger the ingestion pipeline for a specific server_id/guild_id.
    
    Args:
        server_id: The server name or guild ID to ingest.
        rebuild: Force rebuilding the collection from scratch.
        config_path: Custom path to a configuration file.
        
    Returns:
        A dictionary containing the status of ingestion.
    """
   
    original_path = sys.path.copy()
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    if str(INGESTION_ROOT) not in sys.path:
        sys.path.insert(0, str(INGESTION_ROOT))
        
   
    saved_modules = {}
    for mod in ["config", "loaders", "chunkers", "embeddings", "bm25", "pipeline"]:
        if mod in sys.modules:
            saved_modules[mod] = sys.modules.pop(mod)
            
    try:
        from Ingestion.pipeline import ingest_server
        from Ingestion.config import load_config
        
        cfg = load_config(config_path) if config_path else None
        
        # Trigger ingestion
        results = ingest_server(
            server_name_or_id=server_id,
            rebuild=rebuild,
            config=cfg
        )
        return {
            "status": "success",
            "server_id": server_id,
            "results": results
        }
    except Exception as e:
        return {
            "status": "error",
            "server_id": server_id,
            "error": str(e)
        }
    finally:
       
        sys.path = original_path
       
        for mod in ["config", "loaders", "chunkers", "embeddings", "bm25", "pipeline"]:
            if mod in sys.modules:
                sys.modules.pop(mod)
            if mod in saved_modules:
                sys.modules[mod] = saved_modules[mod]
