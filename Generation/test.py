import asyncio
import sys
from pathlib import Path
import logging

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

sys.path.append(str(Path(__file__).parent.parent))

from Generation.pipeline.config import load_config
from Generation.pipeline.QnA_workflow.workflow import QnAWorkflow
from Generation.storage.document_store import InMemoryDocumentStore
from Generation.utils.logging import setup_logger

logger = setup_logger("generation.test", "INFO")

def test_config_loading():
    logger.info("Running config loading test...")
    config = load_config()
    assert config.generation.QnA_workflow.provider is not None, "Provider missing"
    assert config.retrieval.mode in ["hybrid", "semantic", "lexical", "sparse"], "Invalid retrieval mode"
    logger.info("Config loading test: SUCCESS")
    return True

def test_document_store():
    logger.info("Running document store test...")
    store = InMemoryDocumentStore(ttl_seconds=5)
    
    store.store_documents("run123", [{"id": "doc1", "text": "hello"}])
    docs = store.get_documents("run123")
    assert docs is not None and len(docs) == 1, "Failed to retrieve stored documents"
    
    store.clear_expired()
    assert store.get_documents("run123") is not None, "Documents incorrectly expired"
    logger.info("Document store test: SUCCESS")
    return True

async def test_workflow_mock():
    logger.info("Running mock workflow end-to-end test...")
    config = load_config()
    # Force mock provider
    config.generation.QnA_workflow.provider = "mock"
    
    workflow = QnAWorkflow(config)
    
    try:
    
     
        server_ids = workflow.retriever.get_available_servers()
        if not server_ids:
            logger.warning("No servers ingested. Skipping retrieval test part.")
            return True
            
        test_server = server_ids[0]
        
        result = await workflow.run(
            query="test generation pipeline",
            server_name_or_id=test_server,
            mode="lexical", # fastest
            limit=2
        )
        
        assert "response" in result, "Response missing from workflow output"
        assert "[MOCK RESPONSE" in result["response"], "Mock response string missing"
        assert "retrieved_documents" in result, "Retrieved docs missing from workflow output"
        logger.info("Mock workflow end-to-end test: SUCCESS")
        return True
    except Exception as e:
        logger.error(f"Mock workflow test failed: {e}", exc_info=True)
        return False

def test_groq_provider_instantiation():
    logger.info("Running GroqProvider instantiation test...")
    from Generation.pipeline.providers import get_provider, GroqProvider
    provider = get_provider("groq", "llama-3.3-70b-versatile", 0.7, 100)
    assert isinstance(provider, GroqProvider), "Failed to instantiate GroqProvider"
    assert provider.model_name == "llama-3.3-70b-versatile"
    assert provider.temperature == 0.7
    assert provider.max_tokens == 100
    logger.info("GroqProvider instantiation test: SUCCESS")
    return True

async def test_groq_provider_missing_key():
    logger.info("Running GroqProvider missing key test...")
    from Generation.pipeline.providers import get_provider
    import os
    original_key = os.environ.get("GROQ_API_KEY")
    try:
        if "GROQ_API_KEY" in os.environ:
            del os.environ["GROQ_API_KEY"]
        provider = get_provider("groq", "llama-3.3-70b-versatile", 0.7, 100)
        try:
            await provider.generate("test prompt")
            assert False, "Should have raised ValueError for missing GROQ_API_KEY"
        except ValueError as e:
            assert "GROQ_API_KEY environment variable is not set." in str(e), f"Unexpected error: {e}"
    finally:
        if original_key is not None:
            os.environ["GROQ_API_KEY"] = original_key
    logger.info("GroqProvider missing key test: SUCCESS")
    return True

async def test_workflow_dynamic_overrides():
    logger.info("Running dynamic workflow overrides test...")
    config = load_config()
    # Override configs for tests
    workflow = QnAWorkflow(config)
    
    server_ids = workflow.retriever.get_available_servers()
    if not server_ids:
        logger.warning("No servers ingested. Skipping overrides test.")
        return True
        
    test_server = server_ids[0]
    result = await workflow.run(
        query="test overrides",
        server_name_or_id=test_server,
        mode="lexical",
        limit=2,
        provider="mock",
        model="custom-override-model"
    )
    
    assert "response" in result, "Response missing"
    assert "[MOCK RESPONSE from custom-override-model]" in result["response"], f"Override model name missing, got: {result['response']}"
    logger.info("Dynamic workflow overrides test: SUCCESS")
    return True

async def run_all():
    logger.info("Starting Generation Verification Tests...")
    c_ok = test_config_loading()
    s_ok = test_document_store()
    g_inst_ok = test_groq_provider_instantiation()
    g_key_ok = await test_groq_provider_missing_key()
    w_ok = await test_workflow_mock()
    o_ok = await test_workflow_dynamic_overrides()
    
    if all([c_ok, s_ok, g_inst_ok, g_key_ok, w_ok, o_ok]):
        logger.info("==============================================")
        logger.info("ALL GENERATION TESTS PASSED SUCCESSFULLY!")
        logger.info("==============================================")
        sys.exit(0)
    else:
        logger.error("SOME TESTS FAILED.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_all())
