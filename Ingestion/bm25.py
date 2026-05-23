import re
import math
import zlib
from typing import List, Dict, Tuple, Any

def tokenize(text: str) -> List[str]:
    """Tokenize text into lowercase alphanumeric words."""
    if not text:
        return []
    return re.findall(r'[a-zA-Z0-9]+', text.lower())

def get_token_id(token: str) -> int:
    """Stable hash for a token to use as a sparse vector index."""
    #crc32
    return zlib.crc32(token.encode('utf-8'))

class BM25Vectorizer:
    def __init__(self, N: int = 0, total_len: int = 0, df: Dict[str, int] = None, k1: float = 1.2, b: float = 0.75):
        self.N = N
        self.total_len = total_len
        self.df = df or {}
        self.k1 = k1
        self.b = b
        self.avgdl = (self.total_len / self.N) if self.N > 0 else 0

    def compute_idf(self, token_id: str) -> float:
        """Compute the BM25 IDF for a given token hash (as string)."""
        df_t = self.df.get(token_id, 0)
        # Standard BM25 IDF formula
        # idf = ln(1 + (N - df + 0.5) / (df + 0.5))
        return math.log(1 + (self.N - df_t + 0.5) / (df_t + 0.5))

    def vectorize(self, text: str) -> Tuple[List[int], List[float]]:
        """
        Generate sparse vector for a document.
        Returns (indices, values) representing the sparse vector.
        """
        tokens = tokenize(text)
        doc_len = len(tokens)
        if doc_len == 0:
            return [], []

        # Calculate term frequencies in the document
        tf: Dict[int, int] = {}
        for token in tokens:
            tid = get_token_id(token)
            tf[tid] = tf.get(tid, 0) + 1

        indices = []
        values = []

        # Safety check for empty corpus avgdl
        avgdl = self.avgdl if self.avgdl > 0 else doc_len

        for tid, freq in tf.items():
            idf = self.compute_idf(str(tid))
            # BM25 term weight formula
            # weight = idf * (freq * (k1 + 1)) / (freq + k1 * (1 - b + b * (doc_len / avgdl)))
            numerator = freq * (self.k1 + 1)
            denominator = freq + self.k1 * (1 - self.b + self.b * (doc_len / avgdl))
            weight = idf * (numerator / denominator)
            
            # Filter out negative or zero weights for sparsity efficiency
            if weight > 0:
                indices.append(tid)
                values.append(weight)

        return indices, values

    def extract_document_stats(self, text: str) -> Tuple[int, Dict[str, int]]:
        """
        Tokenize document and extract its length and unique token counts.
        Used during the incremental indexing pass to update global stats.
        Returns: (doc_len, dict_of_unique_token_ids_and_counts_as_strings)
        """
        tokens = tokenize(text)
        doc_len = len(tokens)
        
        unique_tids = {}
        for token in set(tokens):
            tid_str = str(get_token_id(token))
            unique_tids[tid_str] = 1 
            
        return doc_len, unique_tids
