import logging
import sys
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

from config import load_config, AppConfig
from loaders import DiscordDataLoader
from chunkers import SlidingWindowChunker
from embeddings import EmbeddingGenerator
from qdrant.client import QdrantManager
from bm25 import BM25Vectorizer

logger = logging.getLogger("ingestion.pipeline")

def setup_pipeline_logging(level_name: str, log_file_path: Path):
    """Set up standard logging configuration for the ingestion pipeline."""
    try:
      
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

    log_file_path.parent.mkdir(parents=True, exist_ok=True)
    level = getattr(logging, level_name.upper(), logging.INFO)
    
    #logger config
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout)
        ]
    )

def ingest_server(
    server_name_or_id: Optional[str] = None,
    rebuild: bool = False,
    config: Optional[AppConfig] = None,
    progress_callback: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Ingest Discord JSON data into Qdrant for a specific server or all available servers.
    
    Args:
        server_name_or_id: Optional server name or Guild ID. If None, indexes all discovered servers.
        rebuild: If True, forces recreating the Qdrant collections.
        config: Optional AppConfig instance. If None, loads from default config.yaml.
        progress_callback: Optional wrapper for iterators (e.g. tqdm).
        
    Returns:
        A dictionary summarizing the status of the operation per server.
    """
    if config is None:
        config = load_config()
        
    log_file = config.get_absolute_path(config.logging.log_file)
    setup_pipeline_logging(config.logging.level, log_file)
    
    loader = DiscordDataLoader(config)
    available_ids = loader.get_available_servers()
    
    if not available_ids:
        raise ValueError("No server datasets found in the data directory.")
        
    servers_to_process = []
    if server_name_or_id:
        resolved_id = loader.resolve_server_id(server_name_or_id)
        if not resolved_id:
            raise ValueError(f"Server '{server_name_or_id}' not found in available datasets.")
        servers_to_process = [resolved_id]
    else:
        servers_to_process = available_ids

    #intialize embedding modle
    generator = EmbeddingGenerator(config)
    vector_size = generator.get_embedding_dimension()
    chunker = SlidingWindowChunker(config)
    
    results = {}

    for server_id in servers_to_process:
        server_name = loader.get_server_name(server_id)
        files = loader.get_server_files(server_id)
        
        if not files:
            results[server_id] = {
                "server_name": server_name,
                "status": "skipped",
                "reason": "No files found in the data directory",
                "processed": 0,
                "skipped": 0
            }
            continue
            
        db = QdrantManager(server_id, config, vector_size)
        db.ensure_collection_exists(force_recreate=rebuild)
        
        processed = 0
        skipped = 0
        
        #progress-bar
        iterator = progress_callback(files, desc=f"Indexing {server_name}") if progress_callback else files
        
        for obj_name in iterator:
            filename = obj_name.split('/')[-1]
            stat_info = loader.store.stat_object(obj_name)
            
            if not rebuild and db.is_file_unchanged(filename, stat_info):
                skipped += 1
                continue
                
            try:
                data = loader.load_file_content(obj_name)
                chunks = chunker.chunk_messages(data, filename)
                
                if chunks:
                    if not rebuild:
                        db.remove_file_vectors(filename)
                        
                    texts = [c["text"] for c in chunks]
                    embeddings = generator.generate_embeddings(texts)
                    
                    bm25 = BM25Vectorizer(**db.state.get("bm25_stats", {}))
                    for text in texts:
                        doc_len, tids = bm25.extract_document_stats(text)
                        bm25.N += 1
                        bm25.total_len += doc_len
                        for tid_str, _ in tids.items():
                            bm25.df[tid_str] = bm25.df.get(tid_str, 0) + 1
                            
                    bm25.avgdl = (bm25.total_len / bm25.N) if bm25.N > 0 else 0
                    sparse_vectors = [bm25.vectorize(text) for text in texts]
                    
                    db.state["bm25_stats"] = {
                        "N": bm25.N,
                        "total_len": bm25.total_len,
                        "df": bm25.df
                    }
                    
                    db.upsert_chunks(chunks, embeddings, sparse_vectors)
                    
                db.mark_file_indexed(filename, stat_info)
                processed += 1
            except Exception as e:
                logger.error(f"Error processing object {filename}: {e}", exc_info=True)
                
        db.save_state()
        results[server_id] = {
            "server_name": server_name,
            "status": "completed",
            "processed": processed,
            "skipped": skipped
        }
        
    return results

def get_servers_status(config: Optional[AppConfig] = None) -> List[Dict[str, Any]]:
    """
    Get the status of all available server vector databases.
    
    Returns:
        A list of dictionaries with status information per server.
    """
    if config is None:
        config = load_config()
        
    loader = DiscordDataLoader(config)
    servers = loader.get_available_servers()
    status_list = []
    
    for server_id in servers:
        server_name = loader.get_server_name(server_id)
        db_path = config.get_absolute_path(config.vectordb_dir) / server_id
        state_file = db_path / "ingestion_state.json"
        
        server_info = {
            "server_id": server_id,
            "server_name": server_name,
            "db_path": db_path,
            "state_file_exists": state_file.exists(),
            "indexed_files_count": 0,
            "collection_name": None,
            "points_count": 0,
            "collection_status": "Not Found",
            "error": None
        }
        
        if state_file.exists():
            try:
                with open(state_file, "r") as f:
                    state = json.load(f)
                server_info["indexed_files_count"] = len(state.get("files", {}))
            except Exception as e:
                server_info["error"] = f"Failed to read state file: {e}"
                
        try:
            
            db = QdrantManager(server_id, config, 384)
            info = db.get_collection_info()
            if "error" not in info:
                server_info["collection_name"] = info.get("collection_name")
                server_info["points_count"] = info.get("points_count", 0)
                server_info["collection_status"] = info.get("status", "Green")
        except Exception as e:
            server_info["collection_status"] = f"Error: {e}"
            
        status_list.append(server_info)
        
    return status_list

def query_server(
    server_name_or_id: str,
    text: str,
    mode: str = "semantic",
    limit: int = 5,
    config: Optional[AppConfig] = None
) -> List[Dict[str, Any]]:
    """
    Query the database index of a Discord server using semantic, lexical, or hybrid mode.
    
    Returns:
        A list of search hits as standardized dictionaries.
    """
    if config is None:
        config = load_config()
        
    loader = DiscordDataLoader(config)
    resolved_id = loader.resolve_server_id(server_name_or_id)
    if not resolved_id:
        raise ValueError(f"Server '{server_name_or_id}' not found in available datasets.")
        
    db = QdrantManager(resolved_id, config, 384)
    collection_name = db.collection_name
    
    if not db.client.collection_exists(collection_name):
        raise ValueError(f"Collection '{collection_name}' does not exist. Index the server first.")
        
    raw_results = []
    
    if mode == "lexical":
        from qdrant_client import models
        response, _ = db.client.scroll(
            collection_name=collection_name,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="text",
                        match=models.MatchText(text=text)
                    )
                ]
            ),
            limit=limit,
            with_payload=True,
            with_vectors=False
        )
        raw_results = response
    elif mode == "hybrid":
        from qdrant_client import models
        generator = EmbeddingGenerator(config)
        vector_size = generator.get_embedding_dimension()
        
        if vector_size != 384:
            db = QdrantManager(resolved_id, config, vector_size)
            
        query_dense = generator.generate_embeddings([text])[0]
        
        bm25 = BM25Vectorizer(**db.state.get("bm25_stats", {}))
        sparse_indices, sparse_values = bm25.vectorize(text)
        
        prefetch_queries = [
            models.Prefetch(
                query=query_dense,
                using="",
                limit=limit
            )
        ]
        if sparse_indices:
            prefetch_queries.append(
                models.Prefetch(
                    query=models.SparseVector(
                        indices=sparse_indices,
                        values=sparse_values
                    ),
                    using="text-sparse",
                    limit=limit
                )
            )
            
        response = db.client.query_points(
            collection_name=collection_name,
            prefetch=prefetch_queries,
            query=models.FusionQuery(
                fusion=models.Fusion.RRF
            ),
            limit=limit
        )
        raw_results = response.points
    else:  # semantic
        generator = EmbeddingGenerator(config)
        vector_size = generator.get_embedding_dimension()
        
        if vector_size != 384:
            db = QdrantManager(resolved_id, config, vector_size)
            
        query_vector = generator.generate_embeddings([text])[0]
        
        response = db.client.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=limit
        )
        raw_results = response.points
        
    # Standardize result fields
    hits = []
    for hit in raw_results:
        payload = hit.payload or {}
        score = getattr(hit, "score", None)
        hits.append({
            "id": hit.id,
            "score": score,
            "channel": payload.get("channel"),
            "start_timestamp": payload.get("start_timestamp"),
            "end_timestamp": payload.get("end_timestamp"),
            "source_file": payload.get("source_file"),
            "text": payload.get("text"),
            "metadata": {k: v for k, v in payload.items() if k not in ["channel", "start_timestamp", "end_timestamp", "source_file", "text"]}
        })
        
    return hits
