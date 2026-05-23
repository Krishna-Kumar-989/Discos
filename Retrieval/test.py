import asyncio
import logging
import sys
from pathlib import Path
from typing import List, Dict, Any

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass


sys.path.append(str(Path(__file__).parent.parent))

try:
    from stage_1.config import load_config
    from stage_1.retriever import Stage1Retriever
    from stage_2.reranker import Stage2Reranker
except ImportError:
    from Retrieval.stage_1.config import load_config
    from Retrieval.stage_1.retriever import Stage1Retriever
    from Retrieval.stage_2.reranker import Stage2Reranker


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("retrieval.test")

def test_config_loading() -> bool:
    """Validate that the configuration loads properly and has the expected default attributes."""
    logger.info("Running config loading test...")
    try:
        config = load_config()
        assert config.qdrant.vectordb_dir is not None, "qdrant.vectordb_dir is missing"
        assert config.embedding.model_name is not None, "embedding.model_name is missing"
        assert config.bm25.k1 == 1.2, f"Expected k1=1.2, got {config.bm25.k1}"
        assert config.retrieval.mode in ["hybrid", "semantic", "lexical"], "Invalid retrieval mode"
        logger.info("Config loading test: SUCCESS")
        return True
    except Exception as e:
        logger.error(f"Config loading test failed: {e}", exc_info=True)
        return False

async def test_semantic_search(retriever: Stage1Retriever, server_id: str) -> bool:
    """Validate semantic dense search capability on a specific server."""
    logger.info(f"Running semantic search test on server {server_id}...")
    try:
        hits = await retriever.retrieve(
            query="colour list",
            server_name_or_id=server_id,
            mode="semantic",
            limit=3
        )
        logger.info(f"Semantic search returned {len(hits)} hits.")
        for idx, hit in enumerate(hits):
            logger.info(f"  [{idx+1}] Score: {hit['score']:.4f} | Text: {hit['text'][:60]}...")
            assert hit["score"] is not None, "Semantic hit score must not be None"
            assert "text" in hit, "Hit text is missing"
            assert hit["server_id"] == server_id, f"Expected server_id {server_id}, got {hit['server_id']}"
        logger.info("Semantic search test: SUCCESS")
        return True
    except Exception as e:
        logger.error(f"Semantic search test failed: {e}", exc_info=True)
        return False

async def test_lexical_search(retriever: Stage1Retriever, server_id: str) -> bool:
    """Validate lexical exact match keyword search on a specific server."""
    logger.info(f"Running lexical search test on server {server_id}...")
    try:
        # Query for a term that definitely exists (from color-role sample JSON)
        hits = await retriever.retrieve(
            query="colours",
            server_name_or_id=server_id,
            mode="lexical",
            limit=3
        )
        logger.info(f"Lexical search returned {len(hits)} hits.")
        for idx, hit in enumerate(hits):
            logger.info(f"  [{idx+1}] Text: {hit['text'][:60]}...")
            assert "colours" in hit["text"].lower() or "color" in hit["text"].lower(), "Lexical hit text should contain match word"
            assert hit["server_id"] == server_id, f"Expected server_id {server_id}, got {hit['server_id']}"
        logger.info("Lexical search test: SUCCESS")
        return True
    except Exception as e:
        logger.error(f"Lexical search test failed: {e}", exc_info=True)
        return False

async def test_sparse_search(retriever: Stage1Retriever, server_id: str) -> bool:
    """Validate sparse vector search on a specific server."""
    logger.info(f"Running sparse search test on server {server_id}...")
    try:
        hits = await retriever.retrieve(
            query="colours reaction",
            server_name_or_id=server_id,
            mode="sparse",
            limit=3
        )
        logger.info(f"Sparse search returned {len(hits)} hits.")
        for idx, hit in enumerate(hits):
            logger.info(f"  [{idx+1}] Score: {hit['score']:.4f} | Text: {hit['text'][:60]}...")
            assert hit["score"] is not None, "Sparse hit score must not be None"
            assert hit["server_id"] == server_id, f"Expected server_id {server_id}, got {hit['server_id']}"
        logger.info("Sparse search test: SUCCESS")
        return True
    except Exception as e:
        logger.error(f"Sparse search test failed: {e}", exc_info=True)
        return False

async def test_hybrid_search(retriever: Stage1Retriever, server_id: str) -> bool:
    """Validate hybrid dense + sparse search (RRF) on a specific server."""
    logger.info(f"Running hybrid search test on server {server_id}...")
    try:
        hits = await retriever.retrieve(
            query="welcome to colors",
            server_name_or_id=server_id,
            mode="hybrid",
            limit=3
        )
        logger.info(f"Hybrid search returned {len(hits)} hits.")
        for idx, hit in enumerate(hits):
            logger.info(f"  [{idx+1}] Score (RRF): {hit['score']:.4f} | Text: {hit['text'][:60]}...")
            assert hit["score"] is not None, "Hybrid hit score must not be None"
            assert hit["server_id"] == server_id, f"Expected server_id {server_id}, got {hit['server_id']}"
        logger.info("Hybrid search test: SUCCESS")
        return True
    except Exception as e:
        logger.error(f"Hybrid search test failed: {e}", exc_info=True)
        return False

async def test_missing_server_error(retriever: Stage1Retriever) -> bool:
    """Validate that omitting server_name_or_id raises a ValueError as expected."""
    logger.info("Running missing server error test...")
    try:
        await retriever.retrieve(
            query="hello",
            server_name_or_id=None,
            mode="hybrid",
            limit=5
        )
        logger.error("Expected ValueError when server_name_or_id is None, but no exception was raised.")
        return False
    except ValueError as e:
        logger.info(f"Successfully caught expected ValueError: {e}")
        logger.info("Missing server error test: SUCCESS")
        return True
    except Exception as e:
        logger.error(f"Expected ValueError, but got unexpected exception: {e}", exc_info=True)
        return False

async def test_stage_2_reranker() -> bool:
    """Validate Stage-2 Cross-Encoder reranking capability."""
    logger.info("Running Stage-2 reranker test...")
    try:
        config = load_config()
        reranker = Stage2Reranker(config)
        dummy_hits = [
            {"id": "1", "score": 0.9, "text": "This is a document about cats."},
            {"id": "2", "score": 0.8, "text": "This is a document about weather forecasting."},
            {"id": "3", "score": 0.7, "text": "This is a document about programming in Python."},
        ]
        reranked = await reranker.rerank("Python programming language", dummy_hits, limit=2)
        assert len(reranked) == 2, f"Expected 2 reranked hits, got {len(reranked)}"
        
    
        assert reranked[0]["id"] == "3", f"Expected document about Python to rank first, but got id {reranked[0]['id']}"
        
        # Verify they are sorted in descending order of scores
        assert reranked[0]["score"] >= reranked[1]["score"], "Results are not sorted descending by score"
        
        logger.info("Stage-2 reranker test: SUCCESS")
        return True
    except Exception as e:
        logger.error(f"Stage-2 reranker test failed: {e}", exc_info=True)
        return False

async def run_all_tests():
    """Run all retrieval unit and integration tests."""
    logger.info("Starting Retrieval Pipeline Verification Tests...")
    
    # 1. Config test
    if not test_config_loading():
        sys.exit(1)
        
    # Initialize retriever
    config = load_config()
    retriever = Stage1Retriever(config)
    
    # Get available server IDs
    server_ids = retriever.get_available_servers()
    if not server_ids:
        logger.error("No active vector databases found to run retrieval tests on. Please ingest some servers first.")
        sys.exit(1)
        
    test_server_id = server_ids[0]
    logger.info(f"Targeting server ID '{test_server_id}' for database-level tests.")

    # 2. Semantic search test
    semantic_ok = await test_semantic_search(retriever, test_server_id)
    
    # 3. Lexical search test
    lexical_ok = await test_lexical_search(retriever, test_server_id)
    
    # 4. Sparse search test
    sparse_ok = await test_sparse_search(retriever, test_server_id)
    
    # 5. Hybrid search test
    hybrid_ok = await test_hybrid_search(retriever, test_server_id)
    
    # 6. Missing server error test
    missing_server_ok = await test_missing_server_error(retriever)
    
    # 7. Stage 2 reranking test
    stage2_ok = await test_stage_2_reranker()
    
    all_success = all([
        semantic_ok,
        lexical_ok,
        sparse_ok,
        hybrid_ok,
        missing_server_ok,
        stage2_ok
    ])
    
    if all_success:
        logger.info("==============================================")
        logger.info("ALL RETRIEVAL VERIFICATION TESTS PASSED SUCCESSFULLY!")
        logger.info("==============================================")
        sys.exit(0)
    else:
        logger.error("==============================================")
        logger.error("SOME RETRIEVAL TESTS FAILED. PLEASE VERIFY SYSTEM LOGS.")
        logger.error("==============================================")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_all_tests())
