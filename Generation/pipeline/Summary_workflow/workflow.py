import sys
import json
import logging
import uuid
from pathlib import Path
from typing import TypedDict, List, Dict, Any, Optional


sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from langgraph.graph import StateGraph, END

from Generation.pipeline.config import AppConfig, load_config
from Generation.pipeline.providers import get_provider
from Generation.storage.document_store import KeyValueDocumentStore, InMemoryDocumentStore
from CacheDb.factory import get_cache_client
from Retrieval.metadata_search.retriever import MetadataRetriever
from Retrieval.stage_1.config import load_config as load_retrieval_config

logger = logging.getLogger("generation.summary_workflow")

# Shared document store
doc_store = None

class SummaryState(TypedDict):
    run_id: str
    query: str
    server_name_or_id: Optional[str]
    provider: Optional[str]
    model: Optional[str]
    temperature: Optional[float]
    max_tokens: Optional[int]
    
    # Internal state
    extracted_filters: Dict[str, Any]
    retrieved_documents: List[Dict[str, Any]]
    prompt: Optional[str]
    response: Optional[str]

class SummarizationWorkflow:
    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or load_config()
        self.retrieval_config = load_retrieval_config()
        
        # Initialize dependencies
        self.retriever = MetadataRetriever(self.retrieval_config)
        
        global doc_store
        if doc_store is None:
            cache_client = get_cache_client()
            # Support both new and old config structures
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
            provider_name=self.config.generation.Summary_workflow.provider,
            model_name=self.config.generation.Summary_workflow.model,
            temperature=self.config.generation.Summary_workflow.temperature,
            max_tokens=self.config.generation.Summary_workflow.max_tokens
        )
        
        self.app = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(SummaryState)
        
        workflow.add_node("extract_filters", self.node_extract_filters)
        workflow.add_node("retrieve_metadata", self.node_retrieve_metadata)
        workflow.add_node("cache", self.node_cache)
        workflow.add_node("build_prompt", self.node_build_prompt)
        workflow.add_node("generate", self.node_generate)
        
        workflow.set_entry_point("extract_filters")
        workflow.add_edge("extract_filters", "retrieve_metadata")
        workflow.add_edge("retrieve_metadata", "cache")
        workflow.add_edge("cache", "build_prompt")
        workflow.add_edge("build_prompt", "generate")
        workflow.add_edge("generate", END)
        
        return workflow.compile()

    def _get_llm(self, state: SummaryState):
        provider_name = state.get("provider") or self.config.generation.Summary_workflow.provider
        model_name = state.get("model") or self.config.generation.Summary_workflow.model
        temp = state.get("temperature") if state.get("temperature") is not None else self.config.generation.Summary_workflow.temperature
        max_t = state.get("max_tokens") if state.get("max_tokens") is not None else self.config.generation.Summary_workflow.max_tokens
        
        if (state.get("provider") or state.get("model") or state.get("temperature") is not None or state.get("max_tokens") is not None):
            return get_provider(provider_name=provider_name, model_name=model_name, temperature=temp, max_tokens=max_t)
        return self.llm

    async def node_extract_filters(self, state: SummaryState) -> Dict[str, Any]:
        """Extract metadata filters from the query using the LLM."""
        logger.info(f"[{state['run_id']}] Extracting filters from query...")
        
        template_name = self.config.generation.Summary_workflow.filter_extraction_template
        template_path = self.config.get_absolute_path(f"prompts/{template_name}")
        with open(template_path, "r", encoding="utf-8") as f:
            template = f.read()
            
        prompt = template.replace("{query}", state["query"])
        llm = self._get_llm(state)
        
        try:
            response = await llm.generate(prompt)
            # Clean up potential markdown wrapper
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.endswith("```"):
                response = response[:-3]
            
            filters = json.loads(response.strip())
            logger.info(f"[{state['run_id']}] Extracted filters: {filters}")
            return {"extracted_filters": filters}
        except Exception as e:
            logger.error(f"[{state['run_id']}] Filter extraction failed: {e}. Proceeding with empty filters.")
            return {"extracted_filters": {}}

    async def node_retrieve_metadata(self, state: SummaryState) -> Dict[str, Any]:
        """Retrieve documents using metadata-only search."""
        logger.info(f"[{state['run_id']}] Executing metadata retrieval...")
        
        server = state.get("server_name_or_id")
        filters = state.get("extracted_filters", {})
        
        # High limit for summarization context
        hits = await self.retriever.retrieve_metadata(
            server_name_or_id=server,
            filters=filters,
            limit=100
        )
        
        logger.info(f"[{state['run_id']}] Retrieved {len(hits)} records for summarization.")
        return {"retrieved_documents": hits}

    async def node_cache(self, state: SummaryState) -> Dict[str, Any]:
        """Cache retrieved chunks to memory store."""
        docs = state.get("retrieved_documents", [])
        self.doc_store.store_documents(state["run_id"], docs)
        return {}

    async def node_build_prompt(self, state: SummaryState) -> Dict[str, Any]:
        """Load template and format summarization prompt with context."""
        template_name = self.config.generation.Summary_workflow.summarization_template
        template_path = self.config.get_absolute_path(f"prompts/{template_name}")
        
        with open(template_path, "r", encoding="utf-8") as f:
            template = f.read()
            
        docs = state.get("retrieved_documents", [])
        
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
            
        prompt = template.replace("{context}", context_str).replace("{query}", state["query"])
        
        return {"prompt": prompt}

    async def node_generate(self, state: SummaryState) -> Dict[str, Any]:
        """Invoke the LLM to generate the final summary."""
        prompt = state.get("prompt", "")
        llm = self._get_llm(state)
        
        logger.info(f"[{state['run_id']}] Generating summary...")
        
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
                        msg_id = msg_ids[0]
                        link = f"https://discord.com/channels/{server_id}/{channel_id}/{msg_id}"
                        if link not in added_links:
                            citations_str += f"- [Doc {i+1}] {link}\n"
                            added_links.add(link)
                
                if added_links:
                    response += citations_str
                    
            return {"response": response}
        except Exception as e:
            logger.error(f"[{state['run_id']}] Summary generation failed: {e}")
            return {"response": f"An error occurred during summarization: {e}"}

    async def run(
        self, 
        query: str, 
        server_name_or_id: str, 
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs # Accept extra args gracefully
    ) -> Dict[str, Any]:
        """Main execution entrypoint for the summarization pipeline."""
        run_id = str(uuid.uuid4())
        
        initial_state = {
            "run_id": run_id,
            "query": query,
            "server_name_or_id": server_name_or_id,
            "provider": provider,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "extracted_filters": {},
            "retrieved_documents": [],
            "prompt": None,
            "response": None
        }
        
        logger.info(f"[{run_id}] Starting Summarization Workflow. Query: '{query}'")
        final_state = await self.app.ainvoke(initial_state)
        
        return {
            "run_id": run_id,
            "response": final_state.get("response", ""),
            "retrieved_documents": final_state.get("retrieved_documents", []),
            "prompt": final_state.get("prompt", "")
        }
