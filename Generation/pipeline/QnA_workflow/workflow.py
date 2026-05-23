import sys
from pathlib import Path
import logging
from typing import TypedDict, List, Dict, Any, Optional
import uuid


sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from langgraph.graph import StateGraph, END

from Generation.pipeline.config import AppConfig, load_config
from Generation.pipeline.providers import get_provider
from Generation.storage.document_store import KeyValueDocumentStore, InMemoryDocumentStore
from CacheDb.factory import get_cache_client
from Retrieval.stage_1.retriever import Stage1Retriever
from Retrieval.stage_1.config import load_config as load_retrieval_config

logger = logging.getLogger("generation.workflow")

# Shared document store (temporary cache)
doc_store = None

class AgentState(TypedDict):
    run_id: str
    query: str
    original_query: Optional[str]
    server_name_or_id: Optional[str]
    mode: Optional[str]
    limit: Optional[int]
    rerank: Optional[bool]
    provider: Optional[str]
    model: Optional[str]
    temperature: Optional[float]
    max_tokens: Optional[int]
    prompt_template: Optional[str]
    
    # Internal state
    retrieved_documents: List[Dict[str, Any]]
    prompt: Optional[str]
    response: Optional[str]

class QnAWorkflow:
    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or load_config()
        self.retrieval_config = load_retrieval_config()
        
        # Initialize dependencies
        self.retriever = Stage1Retriever(self.retrieval_config)
        
        global doc_store
        if doc_store is None:
            cache_client = get_cache_client()
      
            ttl = self.config.cache.document_store_ttl_seconds if hasattr(self.config, 'cache') else self.config.storage.cache_ttl_seconds
            
            # Fallback to in-memory if Redis is unavailable
            if getattr(cache_client, 'client', None) is not None:
                doc_store = KeyValueDocumentStore(cache_client, ttl_seconds=ttl)
            else:
                logger.warning("CacheDb is disconnected. Falling back to InMemoryDocumentStore.")
                doc_store = InMemoryDocumentStore(ttl_seconds=ttl)
            
        self.doc_store = doc_store
        
        # Setup provider
        self.llm = get_provider(
            provider_name=self.config.generation.QnA_workflow.provider,
            model_name=self.config.generation.QnA_workflow.model,
            temperature=self.config.generation.QnA_workflow.temperature,
            max_tokens=self.config.generation.QnA_workflow.max_tokens
        )
        
        # Build graph
        self.app = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("rewrite_query", self.node_rewrite_query)
        workflow.add_node("retrieve", self.node_retrieve)
        workflow.add_node("cache", self.node_cache)
        workflow.add_node("build_prompt", self.node_build_prompt)
        workflow.add_node("generate", self.node_generate)
        
        # Set edges
        workflow.set_entry_point("rewrite_query")
        workflow.add_edge("rewrite_query", "retrieve")
        workflow.add_edge("retrieve", "cache")
        workflow.add_edge("cache", "build_prompt")
        workflow.add_edge("build_prompt", "generate")
        workflow.add_edge("generate", END)
        
        return workflow.compile()

    async def node_rewrite_query(self, state: AgentState) -> Dict[str, Any]:
        """Optionally rewrite the query for better retrieval."""
        if not self.config.generation.QnA_workflow.enable_query_rewrite:
            return {"original_query": state["query"]}
            
        logger.info(f"[{state['run_id']}] Rewriting query for optimal retrieval...")
        rewrite_prompt = (
            "You are an AI assistant tasked with reformulating user queries to improve retrieval in a vector database. "
            "Rewrite the following user query to be more descriptive and optimal for semantic search. "
            "Do not answer the query. Only return the rewritten query text, nothing else.\n\n"
            f"Query: {state['query']}"
        )
        
        provider_name = state.get("provider") or self.config.generation.QnA_workflow.provider
        model_name = state.get("model") or self.config.generation.QnA_workflow.model
        temp = state.get("temperature") if state.get("temperature") is not None else self.config.generation.QnA_workflow.temperature
        max_t = state.get("max_tokens") if state.get("max_tokens") is not None else self.config.generation.QnA_workflow.max_tokens
        
        if (state.get("provider") or state.get("model") or state.get("temperature") is not None or state.get("max_tokens") is not None):
            llm = get_provider(provider_name=provider_name, model_name=model_name, temperature=temp, max_tokens=max_t)
        else:
            llm = self.llm
            
        try:
            rewritten_query = await llm.generate(rewrite_prompt)
            rewritten_query = rewritten_query.strip()
            logger.info(f"[{state['run_id']}] Rewritten query: {rewritten_query}")
            return {"original_query": state["query"], "query": rewritten_query}
        except Exception as e:
            logger.error(f"[{state['run_id']}] Query rewrite failed: {e}. Falling back to original query.")
            return {"original_query": state["query"]}

    async def node_retrieve(self, state: AgentState) -> Dict[str, Any]:
        """Stage-1 (+ Stage-2) Retrieval execution."""
        logger.info(f"[{state['run_id']}] Executing retrieval...")
        query = state["query"]
        server = state.get("server_name_or_id")
        
        mode = state.get("mode") or self.config.retrieval.mode
        limit = state.get("limit") or self.config.retrieval.limit
        rerank = state.get("rerank") if state.get("rerank") is not None else self.config.retrieval.rerank
        
        # Determine retrieval limit based on whether reranking is enabled
        stage_1_limit = self.config.retrieval.rerank_prefetch_limit if rerank else limit
        
        hits = await self.retriever.retrieve(
            query=query,
            server_name_or_id=server,
            mode=mode,
            limit=stage_1_limit
        )
        
        # Optionally perform reranking
        if rerank and hits:
            logger.info(f"[{state['run_id']}] Reranking candidates...")
            try:
                from Retrieval.stage_2.reranker import Stage2Reranker
                reranker = Stage2Reranker(self.retrieval_config)
                hits = await reranker.rerank(query=query, stage_1_results=hits, limit=limit)
            except ImportError:
                logger.warning("Retrieval/stage_2/reranker.py not found. Bypassing reranking.")
                hits = hits[:limit]
        else:
            hits = hits[:limit]
            
        return {"retrieved_documents": hits}

    async def node_cache(self, state: AgentState) -> Dict[str, Any]:
        """Cache retrieved chunks to memory store."""
        docs = state.get("retrieved_documents", [])
        logger.info(f"[{state['run_id']}] Caching {len(docs)} documents.")
        self.doc_store.store_documents(state["run_id"], docs)
        return {}

    async def node_build_prompt(self, state: AgentState) -> Dict[str, Any]:
        """Load template and format prompt with context."""
        template_name = state.get("prompt_template") or self.config.generation.QnA_workflow.prompt_template
        template_path = self.config.get_absolute_path(f"prompts/{template_name}")
        
        if not template_path.exists():
            raise FileNotFoundError(f"Prompt template {template_path} not found.")
            
        with open(template_path, "r", encoding="utf-8") as f:
            template = f.read()
            
        docs = state.get("retrieved_documents", [])
        
        # Format context
        context_parts = []
        for i, doc in enumerate(docs):
            channel = doc.get("channel", "Unknown Channel")
            server = doc.get("server", "Unknown Server")
            timestamp = doc.get("start_timestamp", "Unknown Time")
            text = doc.get("text", "")
            context_parts.append(f"[Doc {i+1} | Server: {server} | Channel: #{channel} | Time: {timestamp}]\n{text}")
            
        context_str = "\n\n".join(context_parts)
        if not context_str:
            context_str = "No relevant context found."
            
        original_q = state.get("original_query") or state["query"]
        prompt = template.replace("{context}", context_str).replace("{query}", original_q)
        
        return {"prompt": prompt}

    async def node_generate(self, state: AgentState) -> Dict[str, Any]:
        """Invoke the LLM to generate the final response."""
        prompt = state.get("prompt", "")
        
        provider_name = state.get("provider") or self.config.generation.QnA_workflow.provider
        model_name = state.get("model") or self.config.generation.QnA_workflow.model
        temp = state.get("temperature") if state.get("temperature") is not None else self.config.generation.QnA_workflow.temperature
        max_t = state.get("max_tokens") if state.get("max_tokens") is not None else self.config.generation.QnA_workflow.max_tokens
        
        logger.info(f"[{state['run_id']}] Invoking LLM ({model_name}) from provider ({provider_name})...")
        
        # Instantiate LLM provider dynamically if overridden
        if (state.get("provider") or state.get("model") or state.get("temperature") is not None or state.get("max_tokens") is not None):
            llm = get_provider(
                provider_name=provider_name,
                model_name=model_name,
                temperature=temp,
                max_tokens=max_t
            )
        else:
            llm = self.llm
            
        try:
            response = await llm.generate(prompt)
            
            # Append citations
            docs = state.get("retrieved_documents", [])
            if docs:
                citations_str = "\n\n**Sources:**\n"
                added_links = set()
                for i, doc in enumerate(docs):
                    server_id = doc.get("server_id")
                    channel_id = doc.get("channel_id")
                    msg_ids = doc.get("metadata", {}).get("message_ids", [])
                    
                    if server_id and channel_id and msg_ids:
                        # Use the first message ID in the chunk for the link
                        msg_id = msg_ids[0]
                        link = f"https://discord.com/channels/{server_id}/{channel_id}/{msg_id}"
                        if link not in added_links:
                            citations_str += f"- [Doc {i+1}] {link}\n"
                            added_links.add(link)
                
                if added_links:
                    response += citations_str
                    
            return {"response": response}
        except Exception as e:
            logger.error(f"[{state['run_id']}] LLM Generation failed: {e}")
            return {"response": f"An error occurred during generation: {e}"}

    async def run(
        self, 
        query: str, 
        server_name_or_id: str, 
        mode: Optional[str] = None, 
        limit: Optional[int] = None,
        rerank: Optional[bool] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        prompt_template: Optional[str] = None
    ) -> Dict[str, Any]:
        """Main execution entrypoint for the pipeline."""
        run_id = str(uuid.uuid4())
        
        initial_state = {
            "run_id": run_id,
            "query": query,
            "original_query": None,
            "server_name_or_id": server_name_or_id,
            "mode": mode,
            "limit": limit,
            "rerank": rerank,
            "provider": provider,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "prompt_template": prompt_template,
            "retrieved_documents": [],
            "prompt": None,
            "response": None
        }
        
        logger.info(f"[{run_id}] Starting QnA Workflow. Query: '{query}'")
        final_state = await self.app.ainvoke(initial_state)
        
        return {
            "run_id": run_id,
            "response": final_state.get("response", ""),
            "retrieved_documents": final_state.get("retrieved_documents", []),
            "prompt": final_state.get("prompt", "")
        }
