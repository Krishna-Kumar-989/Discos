import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("retrieval.fusion")

def reciprocal_rank_fusion(
    ranked_lists: List[List[Dict[str, Any]]],
    k: int = 60,
    weights: Optional[List[float]] = None
) -> List[Dict[str, Any]]:
    """
    Perform Reciprocal Rank Fusion (RRF) on multiple ranked lists of hits.
    
    Args:
        ranked_lists: A list of ranked lists, where each list contains dicts with at least an 'id'.
        k: The constant parameter for RRF (default: 60).
        weights: Optional weights to apply to each ranked list.
        
    Returns:
        A single fused list sorted by the RRF score in descending order.
    """
    if not ranked_lists:
        return []
        
    # Remove empty lists
    ranked_lists = [rl for rl in ranked_lists if rl]
    if not ranked_lists:
        return []
        
    if weights is None:
        weights = [1.0] * len(ranked_lists)
    elif len(weights) != len(ranked_lists):
        logger.warning("Weights length does not match ranked lists. Defaulting to equal weights.")
        weights = [1.0] * len(ranked_lists)
        
    rrf_scores: Dict[str, float] = {}
    docs: Dict[str, Dict[str, Any]] = {}
    
    # Calculate RRF score for each unique document ID
    for list_idx, ranked_list in enumerate(ranked_lists):
        weight = weights[list_idx]
        for rank, hit in enumerate(ranked_list):
            doc_id = hit.get("id")
            if not doc_id:
                continue
                
           
            if doc_id not in docs:
                docs[doc_id] = hit
            
            # Rank is 0-indexed
            r = rank + 1
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + weight * (1.0 / (k + r))
            
    # Sort document IDs by RRF score descending
    sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
    
    merged_results = []
    for doc_id in sorted_ids:
        # Create a copy and update score with final fused RRF score
        hit_copy = dict(docs[doc_id])
        hit_copy["score"] = rrf_scores[doc_id]
        merged_results.append(hit_copy)
        
    return merged_results
