try:
    from stage_2.reranker import Stage2Reranker
except ImportError:
    from Retrieval.stage_2.reranker import Stage2Reranker

__all__ = ["Stage2Reranker"]
