import importlib
from github_to_sqlite import config as cfg
from github_to_sqlite import tokenization


def test_load_tokenizer(monkeypatch):
    calls = []

    def fake_from_pretrained(model):
        calls.append(model)
        return 'tok'

    monkeypatch.setattr('tokenizers.Tokenizer.from_pretrained', fake_from_pretrained)
    importlib.reload(tokenization)
    assert tokenization.load_tokenizer() == 'tok'
    assert calls == [cfg.config.default_model]
