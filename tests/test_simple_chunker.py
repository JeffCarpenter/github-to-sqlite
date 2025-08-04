from dataclasses import dataclass
from github_to_sqlite.simple_chunker import SimpleChunker, BaseSplitter


@dataclass
class LambdaSplitter(BaseSplitter):
    func: callable

    def __call__(self, doc: str):
        return self.func(doc)


def test_simple_chunker_drops_partial(tmp_path):
    text = "Sentence one. Sentence two. Sentence three. Sentence four. Sentence five. Sentence six. Extra."  # 7 sentences
    chunker = SimpleChunker(
        name="test", splitter=LambdaSplitter(func=lambda d: d), target_length=3
    )
    chunks = chunker([text])[0]
    # Expect two chunks of exactly 3 sentences each, dropping the last partial chunk
    assert len(chunks) == 2
    assert "Sentence three." in chunks[0].content
    assert "Sentence six." in chunks[1].content


def test_punkt_download(monkeypatch):
    calls = []

    def failing(text):
        monkeypatch.setattr('github_to_sqlite.simple_chunker.sent_tokenize', lambda t: ['ok'])
        raise LookupError

    monkeypatch.setattr('github_to_sqlite.simple_chunker.sent_tokenize', failing)
    monkeypatch.setattr('nltk.download', lambda name: calls.append(name))

    chunker = SimpleChunker(name='t', splitter=LambdaSplitter(func=lambda d: d), target_length=1)
    assert chunker._split('hi') == ['ok']
    assert 'punkt' in calls

