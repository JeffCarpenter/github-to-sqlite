import sys
from github_to_sqlite import utils


def test_chunk_readme_fallback():
    text = """Paragraph one.

Paragraph two.

Paragraph three."""
    chunks = utils.chunk_readme(text)
    assert chunks == ["Paragraph one.", "Paragraph two.", "Paragraph three."]


def test_chunk_readme_with_chunker(monkeypatch):
    class DummyChunker:
        def chunk(self, text):
            return ["chunk1", "chunk2"]

    def dummy_init():
        return DummyChunker()

    monkeypatch.setitem(
        sys.modules,
        'semantic_chunkers.chunkers',
        type('m', (), {'StatisticalChunker': dummy_init})
    )
    assert utils.chunk_readme('anything') == ['chunk1', 'chunk2']

