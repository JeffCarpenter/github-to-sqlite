import json
import base64
import pathlib
from click.testing import CliRunner
import sqlite_utils
import types
import sys

from github_to_sqlite import cli, utils


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
    monkeypatch.setattr(utils, "_maybe_load_sqlite_vec", lambda db: False)

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
            ["starred-embeddings", str(db_path), "-a", str(auth_path), "--verbose"],
        )
        assert result.exit_code == 0
        assert "sqlite-vec extension not loaded" in result.output

    db = sqlite_utils.Database(db_path)
    assert db["repo_embeddings"].count == 1
    assert db["readme_chunk_embeddings"].count == 1
    assert db["repo_build_files"].count == 1
    assert db["repo_metadata"].count == 1

    row = db["repo_embeddings"].get(repo["id"])
    assert row["title_embedding"] == b"\x00\x00\x80?"
    assert row["description_embedding"] == b"\x00\x00\x80?"
    assert row["readme_embedding"] == b"\x00\x00\x80?"

    chunk = db["readme_chunk_embeddings"].get((repo["id"], 0))
    assert chunk["chunk_text"] == "Readme"
    assert chunk["embedding"] == b"\x00\x00\x80?"

    build = db["repo_build_files"].get((repo["id"], "pyproject.toml"))
    assert build["metadata"] == '{"name": "pkg"}'

    meta = db["repo_metadata"].get(repo["id"])
    assert meta["language"] == repo["language"]
    assert meta["directory_tree"] == '{".": {"dirs": [], "files": ["pyproject.toml"]}}'
