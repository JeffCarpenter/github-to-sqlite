import importlib
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
