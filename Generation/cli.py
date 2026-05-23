import argparse
import asyncio
import logging
import sys
from pathlib import Path
from pprint import pprint


sys.path.append(str(Path(__file__).parent.parent))

from Generation.pipeline.QnA_workflow.workflow import QnAWorkflow
from Generation.pipeline.Summary_workflow.workflow import SummarizationWorkflow
from Generation.pipeline.config import load_config
from Generation.utils.logging import setup_logger

async def run_generation(args):
    # Load base config
    config = load_config(args.config)
    
    # Determine the active workflow config to override
    workflow_type = config.generation.workflow_type
    if workflow_type == "QnA_workflow":
        wf_config = config.generation.QnA_workflow
    elif workflow_type == "Summary_workflow":
        wf_config = config.generation.Summary_workflow
    else:
        wf_config = None

    # Override settings from CLI
    if wf_config:
        if args.provider:
            wf_config.provider = args.provider
        if args.model:
            wf_config.model = args.model
        if args.temperature is not None:
            wf_config.temperature = args.temperature
        if args.prompt_template:
            if hasattr(wf_config, "prompt_template"):
                wf_config.prompt_template = args.prompt_template
            elif hasattr(wf_config, "summarization_template"):
                wf_config.summarization_template = args.prompt_template

    log_path = config.get_absolute_path(config.logging.log_file)
    setup_logger("generation", config.logging.level, log_path)
    
    # Initialize pipeline
    if workflow_type == "QnA_workflow":
        workflow = QnAWorkflow(config)
    elif workflow_type == "Summary_workflow":
        workflow = SummarizationWorkflow(config)
    else:
        raise ValueError(f"Unknown workflow_type '{workflow_type}'")
    
    print("\n" + "=" * 80)
    print(f"GENERATING ANSWER FOR: '{args.query}'")
    print(f"Target Server: {args.server}")
    active_provider = wf_config.provider if wf_config else "Unknown"
    active_model = wf_config.model if wf_config else "Unknown"
    print(f"Provider: {active_provider} | Model: {active_model}")
    print("=" * 80)
    
    try:
        result = await workflow.run(
            query=args.query,
            server_name_or_id=args.server,
            mode=args.mode,
            limit=args.limit,
            rerank=args.rerank
        )
        
        docs = result["retrieved_documents"]
        print(f"\n[Retrieved {len(docs)} context documents]")
        for i, doc in enumerate(docs):
            print(f"  {i+1}. Score: {doc.get('score', 'N/A')} | Snippet: {doc.get('text', '')[:60]}...")
            
        print("\n" + "-" * 80)
        print("FINAL RESPONSE:\n")
        print(result["response"])
        print("-" * 80 + "\n")
        
    except Exception as e:
        print(f"\nError during pipeline execution: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def main():
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="LangGraph RAG Generation CLI")
    
    parser.add_argument("--query", type=str, required=True, help="Search query string")
    parser.add_argument("--server", type=str, required=True, help="Server name or Guild ID folder name")
    
    # Retrieval Overrides
    parser.add_argument("--mode", type=str, choices=["semantic", "lexical", "sparse", "hybrid"], default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--rerank", action="store_true", default=None)
    parser.add_argument("--no-rerank", action="store_false", dest="rerank")
    
    # Generation Overrides
    parser.add_argument("--provider", type=str, default=None)
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--prompt-template", type=str, default=None)
    
    parser.add_argument("--config", type=str, help="Path to custom config.yaml file")

    args = parser.parse_args()
    asyncio.run(run_generation(args))

if __name__ == "__main__":
    main()
