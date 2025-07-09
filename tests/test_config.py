import importlib
import pytest
from github_to_sqlite import tokenization


def test_load_tokenizer(monkeypatch):
    calls = []

    def fake_from_pretrained(model):
        calls.append(model)
        return 'tok'

    monkeypatch.setattr('tokenizers.Tokenizer.from_pretrained', fake_from_pretrained)
    monkeypatch.setenv('GITHUB_TO_SQLITE_MODEL', 'env-model')
    importlib.reload(tokenization)
    assert tokenization.load_tokenizer() == 'tok'
    assert calls == ['env-model']


def test_load_tokenizer_failure(monkeypatch):
    def boom(model):
        raise OSError("missing")

    monkeypatch.setattr('tokenizers.Tokenizer.from_pretrained', boom)
    with pytest.raises(RuntimeError) as exc:
        tokenization.load_tokenizer("bad")
    assert "Failed to load tokenizer" in str(exc.value)
