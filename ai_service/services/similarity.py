"""
Similarity utilities
--------------------
Cosine similarity between two L2-normalised embeddings.
"""

from __future__ import annotations

import numpy as np


def cosine_similarity(emb1: np.ndarray, emb2: np.ndarray) -> float:
    """
    Compute cosine similarity between two embeddings.
    Both vectors are expected to be L2-normalised (unit vectors),
    in which case dot product == cosine similarity.
    """
    sim = float(np.dot(emb1, emb2))
    # Clamp to [-1, 1] to handle floating-point drift
    return max(-1.0, min(1.0, sim))