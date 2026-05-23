import sys
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from CacheDb.factory import get_cache_client


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from Retrieval.stage_1.config import load_config as load_retrieval_config
from Generation.pipeline.QnA_workflow.workflow import QnAWorkflow
from Generation.pipeline.Summary_workflow.workflow import SummarizationWorkflow
from Generation.pipeline.config import load_config
from Generation.utils.logging import setup_logger
from DataDb import db, ConversationHistory

_db_initialized = False

async def ensure_db_initialized():
    global _db_initialized
    if not _db_initialized:
        await db.initialize_db()
        _db_initialized = True


async def query_generation_pipeline(
    query: str,
    server_id: str,
    mode: Optional[str] = None,
    limit: Optional[int] = None,
    rerank: Optional[bool] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    prompt_template: Optional[str] = None,
    config_path: Optional[str] = None,
    workflow_type: Optional[str] = None,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Programmatic entrypoint to run the answer generation pipeline for a user query.
    
    Args:
        query: User search query.
        server_id: Discord server name or Guild ID to fetch context from.
        mode: Retrieval mode ('semantic', 'lexical', 'sparse', 'hybrid').
        limit: Max retrieved documents to context-inject.
        rerank: Enable/disable CrossEncoder reranking.
        provider: Override model provider (e.g. 'openai', 'gemini', 'groq', 'mock').
        model: Override model name.
        temperature: Override model generation temperature.
        max_tokens: Override max tokens to generate.
        prompt_template: Name of prompt file in Generation/prompts/.
        config_path: Path to a custom config.yaml file if desired.
        workflow_type: Optional workflow type override ('QnA_workflow', 'Summary_workflow').
        
    Returns:
        A dictionary containing:
            - 'run_id': Unique run execution identifier.
            - 'response': Generated answer from LLM.
            - 'retrieved_documents': List of matched documents used as context.
            - 'prompt': The final formatted prompt sent to the model.
    """

    if config_path is None:
        local_config = Path(__file__).resolve().parent / "config.yaml"
        if local_config.exists():
            config_path = str(local_config)
            
    config = load_config(config_path)
    
   
    log_path = config.get_absolute_path(config.logging.log_file)
    setup_logger("generation", config.logging.level, log_path)
    

    resolved_workflow = workflow_type or config.generation.workflow_type
    
    #Semantic Response Caching 
    cache_client = get_cache_client()
    cache_key = None
    if hasattr(config, 'cache') and config.cache.enable_semantic_cache:
        query_hash = hashlib.md5(query.strip().lower().encode('utf-8')).hexdigest()
        cache_key = f"semantic_cache:{server_id}:{query_hash}"
        cached_result = cache_client.get(cache_key)
        if cached_result:
            import logging
            logging.getLogger("generation").info(f"Semantic Cache hit for query: '{query}'")
            return cached_result

    
    if resolved_workflow == "QnA_workflow":
        workflow = QnAWorkflow(config)
    elif resolved_workflow == "Summary_workflow":
        workflow = SummarizationWorkflow(config)
    else:
        raise ValueError(f"Unknown workflow_type '{resolved_workflow}' specified in Generation config.")
    
    # Run the compiled LangGraph execution
    result = await workflow.run(
        query=query,
        server_name_or_id=server_id,
        mode=mode,
        limit=limit,
        rerank=rerank,
        provider=provider,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        prompt_template=prompt_template
    )
    
    #Save Conversation History
    now_dt = datetime.utcnow()
    run_id = result.get("run_id", "unknown_run")
    
    #Save to objectStore conversation history
    try:
        from objectStore import get_object_store
        import io
        
        timestamp = now_dt.isoformat()
        
        history_data = {
            "run_id": run_id,
            "timestamp": timestamp,
            "server_id": server_id,
            "user_id": user_id,
            "workflow_type": resolved_workflow,
            "query": query,
            "response": result.get("response"),
            "retrieved_documents": result.get("retrieved_documents", []),
            "metadata": {
                "mode": mode,
                "limit": limit,
                "rerank": rerank,
                "provider": provider,
                "model": model
            }
        }
        
        object_name = f"conversation_history/{server_id}/{run_id}.json"
        json_bytes = json.dumps(history_data, indent=4, ensure_ascii=False).encode('utf-8')
        data_stream = io.BytesIO(json_bytes)
        
        store = get_object_store()
        store.upload_object(object_name, data_stream, content_type="application/json")
        
    except Exception as e:
        import logging
        logging.error(f"Failed to save conversation history to object store for run {run_id}: {e}", exc_info=True)

    #save to DataDb API
    try:
        await ensure_db_initialized()
        await db.insert(
            ConversationHistory,
            {
                "id": run_id,
                "timestamp": now_dt,
                "server_id": server_id,
                "user_id": user_id,
                "workflow_type": resolved_workflow,
                "query": query,
                "response": result.get("response"),
                "retrieved_documents": result.get("retrieved_documents", []),
                "metadata_info": {
                    "mode": mode,
                    "limit": limit,
                    "rerank": rerank,
                    "provider": provider,
                    "model": model
                }
            }
        )
    except Exception as e:
        import logging
        logging.error(f"Failed to save conversation history to DataDb for run {run_id}: {e}", exc_info=True)

 
    
    #Semantic Response Caching save
    if cache_key and hasattr(config, 'cache') and config.cache.enable_semantic_cache:
        cache_client.set(cache_key, result, ttl=config.cache.semantic_cache_ttl_seconds)

    
    return result
