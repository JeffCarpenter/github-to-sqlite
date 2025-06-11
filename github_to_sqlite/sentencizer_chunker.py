from typing import Iterable, List, Sequence, Union

import numpy as np

try:
    import torch
    TensorType = (np.ndarray, torch.Tensor)
except Exception:  # pragma: no cover - torch not installed
    TensorType = (np.ndarray,)


class BasicSentencizerChunker:
    """Chunk token vectors on a designated period token."""

    def __init__(self, period_token: str = "."):
        self.period_token = period_token

    def chunk(
        self, tokens: Sequence[str], vectors: Sequence[TensorType]
    ) -> List[List[TensorType]]:
        if len(tokens) != len(vectors):
            raise ValueError("tokens and vectors must be the same length")
        chunks: List[List[TensorType]] = []
        current: List[TensorType] = []
        for token, vec in zip(tokens, vectors):
            current.append(vec)
            if token == self.period_token:
                chunks.append(current)
                current = []
        # drop incomplete final chunk
        return chunks

    __call__ = chunk

