# Discos Generation Subsystem

The Generation module runs the LLM-powered answer generation workflows using **LangGraph** state machines. It retrieves context from the Retrieval module, builds structured prompts, and calls the configured LLM provider to produce responses.

## Supported Workflows

### 1. `QnA_workflow`
Answers factual questions about the Discord server's history. The graph:
1. Retrieves context documents from Qdrant via the Retrieval module.
2. Evaluates and caches retrieved documents.
3. Builds a structured prompt from a template.
4. Invokes the LLM and returns the formatted answer.

### 2. `Summary_workflow`
Synthesizes and summarizes historical discussions from a Discord channel or topic. It first runs a filter extraction step to identify relevant date/channel scopes before summarizing.

---

## Component Overview

| Component | Role |
|-----------|------|
| `pipeline/QnA_workflow/workflow.py` | LangGraph state machine for Q&A. |
| `pipeline/Summary_workflow/workflow.py` | LangGraph state machine for Summarization. |
| `pipeline/providers.py` | Unified `BaseLLMProvider` factory — supports OpenAI, Gemini, Groq, Ollama, and Mock. |
| `pipeline/config.py` | Pydantic config schema. |
| `prompts/` | System prompt template files (`.txt`). |
| `utils/logging.py` | Shared logger setup. |
| `cli.py` | CLI test interface. |

---

## Supported LLM Providers

| Provider | `provider` key | Requirement |
|----------|---------------|-------------|
| OpenAI | `openai` | `OPENAI_API_KEY` in `.env` |
| Google Gemini | `gemini` | `GEMINI_API_KEY` in `.env` |
| Groq | `groq` | `GROQ_API_KEY` in `.env` |
| Ollama (local) | `ollama` | `OLLAMA_BASE_URL` in `.env` |
| Mock (testing) | `mock` | No key needed |

---

## CLI Usage

Run from the project root:

```bash
python Generation/cli.py --query "your question" --server <server_name_or_id> [options]
```

### Options

| Flag | Description |
|------|-------------|
| `--query` | (Required) The question or summary request. |
| `--server` | (Required) Target server name or Guild ID. |
| `--workflow` | Workflow type: `QnA_workflow` or `Summary_workflow`. |
| `--provider` | Override the LLM provider (e.g., `groq`, `openai`, `mock`). |
| `--model` | Override the model name string. |
| `--temperature` | Adjust model output temperature. |
| `--prompt_template` | Override prompt template filename. |
| `--mode` | Retrieval mode: `semantic`, `lexical`, `sparse`, `hybrid`. |
| `--limit` | Number of context documents to retrieve. |
| `--rerank` | Enable Cross-Encoder reranking. |
| `--config` | Path to a custom config YAML file. |

---

## Programmatic Usage

```python
from Endpoint import query_generation_pipeline

result = await query_generation_pipeline(
    query="Who pinged everyone last week?",
    server_id="1234567890",
    provider="groq",
    model="llama-3.3-70b-versatile",
    workflow_type="QnA_workflow"
)
print(result["response"])
```
