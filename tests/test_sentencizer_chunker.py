import numpy as np
import pytest
from github_to_sqlite.sentencizer_chunker import BasicSentencizerChunker


def test_sentencizer_chunks_vectors():
    tokens = ["hello", ".", "world", "."]
    vecs = [np.array([1]), np.array([2]), np.array([3]), np.array([4])]
    chunker = BasicSentencizerChunker()
    chunks = chunker(tokens, vecs)
    assert len(chunks) == 2
    assert len(chunks[0]) == 2
    assert len(chunks[1]) == 2


def test_sentencizer_drops_incomplete():
    tokens = ["hello", ".", "world"]
    vecs = [np.array([1]), np.array([2]), np.array([3])]
    chunker = BasicSentencizerChunker()
    chunks = chunker(tokens, vecs)
    assert len(chunks) == 1


def test_sentencizer_length_mismatch():
    tokens = ["a", "."]
    vecs = [np.array([1])]
    chunker = BasicSentencizerChunker()
    with pytest.raises(ValueError):
        chunker(tokens, vecs)
