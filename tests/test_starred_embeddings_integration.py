import json
import base64
import pathlib
from click.testing import CliRunner
import sqlite_utils
import types
import sys

from github_to_sqlite import cli


def test_starred_embeddings_integration(requests_mock, tmp_path, monkeypatch):
    starred = json.load(open(pathlib.Path(__file__).parent / "starred.json"))
    repo = starred[0]["repo"]

    # Mock GitHub API
    requests_mock.get(
        "https://api.github.com/user/starred?per_page=100",
        json=starred,
    )
    encoded = base64.b64encode(b"Readme").decode("utf-8")
    requests_mock.get(
        f"https://api.github.com/repos/{repo['full_name']}/readme",
        json={"content": encoded},
    )

    # Stub sentence_transformers
    class DummyModel:
        def encode(self, texts):
            return [[1.0]] * len(texts)

    dummy_mod = types.SimpleNamespace(SentenceTransformer=lambda name: DummyModel())
    monkeypatch.setitem(sys.modules, "sentence_transformers", dummy_mod)

    # Prepare filesystem
    auth_path = tmp_path / "auth.json"
    auth_path.write_text(json.dumps({"github_personal_token": "x"}))

    db_path = tmp_path / "test.db"

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        repo_dir = pathlib.Path(repo["full_name"])
        repo_dir.mkdir(parents=True)
        (repo_dir / "pyproject.toml").write_text("name='pkg'")

        result = runner.invoke(
            cli.cli,
            ["starred-embeddings", str(db_path), "-a", str(auth_path)],
        )
        assert result.exit_code == 0

    db = sqlite_utils.Database(db_path)
    assert db["repo_embeddings"].count == 1
    assert db["readme_chunk_embeddings"].count == 1
    assert db["repo_build_files"].count == 1
    assert db["repo_metadata"].count == 1
