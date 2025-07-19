import json
import sys
import types
from pathlib import Path

import sqlite_utils
from click.testing import CliRunner

from github_to_sqlite import cli, utils


def test_starred_embeddings_command(monkeypatch, tmpdir):
    starred = json.load(open(Path(__file__).parent / "starred.json"))
    repo = starred[0]["repo"]

    repo_dir = Path(tmpdir) / repo["full_name"]
    repo_dir.mkdir(parents=True)
    (repo_dir / "pyproject.toml").write_text("name = 'pkg'")

    monkeypatch.setattr(utils, "fetch_all_starred", lambda token=None: starred)
    monkeypatch.setattr(utils, "fetch_readme", lambda token, full_name: "Readme")
    monkeypatch.setattr(utils, "chunk_readme", lambda text: ["chunk1", "chunk2"])
    monkeypatch.setattr(
        utils, "find_build_files", lambda path, patterns=None: ["pyproject.toml"]
    )
    monkeypatch.setattr(utils, "directory_tree", lambda path: {".": {"dirs": [], "files": ["pyproject.toml"]}})
    monkeypatch.setattr(utils, "parse_build_file", lambda path: {"name": "pkg"})

    class DummyModel:
        def encode(self, texts):
            return [[1.0, 0.0]] * len(texts)

    dummy_mod = types.SimpleNamespace(SentenceTransformer=lambda name: DummyModel())
    monkeypatch.setitem(sys.modules, "sentence_transformers", dummy_mod)
    monkeypatch.setattr(utils, "_maybe_load_sqlite_vec", lambda db: False)

    db_path = str(Path(tmpdir) / "test.db")
    runner = CliRunner()
    result = runner.invoke(cli.cli, ["starred-embeddings", db_path])
    assert result.exit_code == 0

    db = sqlite_utils.Database(db_path)
    assert db["repo_embeddings"].count == 1
    assert db["readme_chunk_embeddings"].count == 2
    assert db["repo_build_files"].count == 1
    assert db["repo_metadata"].count == 1


def test_starred_embeddings_command_sqlite_vec(monkeypatch, tmpdir):
    starred = json.load(open(Path(__file__).parent / "starred.json"))
    repo = starred[0]["repo"]

    repo_dir = Path(tmpdir) / repo["full_name"]
    repo_dir.mkdir(parents=True)
    (repo_dir / "pyproject.toml").write_text("name = 'pkg'")

    monkeypatch.setattr(utils, "fetch_all_starred", lambda token=None: starred)
    monkeypatch.setattr(utils, "fetch_readme", lambda token, full_name: "Readme")
    monkeypatch.setattr(utils, "chunk_readme", lambda text: ["chunk1", "chunk2"])
    monkeypatch.setattr(
        utils, "find_build_files", lambda path, patterns=None: ["pyproject.toml"]
    )
    monkeypatch.setattr(utils, "directory_tree", lambda path: {".": {"dirs": [], "files": ["pyproject.toml"]}})
    monkeypatch.setattr(utils, "parse_build_file", lambda path: {"name": "pkg"})

    class DummyModel:
        def encode(self, texts):
            return [[1.0, 0.0]] * len(texts)

    dummy_mod = types.SimpleNamespace(SentenceTransformer=lambda name: DummyModel())
    monkeypatch.setitem(sys.modules, "sentence_transformers", dummy_mod)

    def fake_ensure_embedding_tables(db):
        tables = set(db.table_names())
        if "repo_embeddings" not in tables:
            db["repo_embeddings"].create({"repo_id": int, "title_embedding": bytes, "description_embedding": bytes, "readme_embedding": bytes}, pk="repo_id")
        if "readme_chunk_embeddings" not in tables:
            db["readme_chunk_embeddings"].create({"repo_id": int, "chunk_index": int, "chunk_text": str, "embedding": bytes}, pk=("repo_id", "chunk_index"))
        if "repo_build_files" not in tables:
            db["repo_build_files"].create({"repo_id": int, "file_path": str, "metadata": str}, pk=("repo_id", "file_path"))
        if "repo_metadata" not in tables:
            db["repo_metadata"].create({"repo_id": int, "language": str, "directory_tree": str}, pk="repo_id")

    monkeypatch.setattr(utils, "_maybe_load_sqlite_vec", lambda db: True)
    monkeypatch.setattr(utils, "ensure_embedding_tables", fake_ensure_embedding_tables)
    dummy_sqlite_vec = types.SimpleNamespace(
        serialize_float32=lambda v: b"".join(float(x).hex().encode() for x in v),
        load=lambda conn: None,
    )
    monkeypatch.setitem(sys.modules, "sqlite_vec", dummy_sqlite_vec)

    db_path = str(Path(tmpdir) / "test.db")
    runner = CliRunner()
    result = runner.invoke(cli.cli, ["starred-embeddings", db_path, "--verbose"])
    assert result.exit_code == 0
    assert "Using sqlite-vec for embedding storage" in result.output

def test_starred_embeddings_env_model(monkeypatch, tmpdir):
    starred = json.load(open(Path(__file__).parent / "starred.json"))
    repo = starred[0]["repo"]

    repo_dir = Path(tmpdir) / repo["full_name"]
    repo_dir.mkdir(parents=True)
    (repo_dir / "pyproject.toml").write_text("name = 'pkg'")

    monkeypatch.setattr(utils, "fetch_all_starred", lambda token=None: starred)
    monkeypatch.setattr(utils, "fetch_readme", lambda token, full_name: "Readme")
    monkeypatch.setattr(utils, "chunk_readme", lambda text: ["chunk1"]) 
    monkeypatch.setattr(utils, "find_build_files", lambda path, patterns=None: [])
    monkeypatch.setattr(utils, "directory_tree", lambda path: {})
    monkeypatch.setattr(utils, "parse_build_file", lambda path: {})
    monkeypatch.setattr(utils, "_maybe_load_sqlite_vec", lambda db: False)

    called = []
    class DummyModel:
        def __init__(self, name):
            called.append(name)
        def encode(self, texts):
            return [[0.0]] * len(texts)
    dummy_mod = types.SimpleNamespace(SentenceTransformer=DummyModel)
    monkeypatch.setitem(sys.modules, "sentence_transformers", dummy_mod)
    monkeypatch.setenv("GITHUB_TO_SQLITE_MODEL", "env-model")

    db_path = str(Path(tmpdir) / "test.db")
    result = CliRunner().invoke(cli.cli, ["starred-embeddings", db_path])
    assert result.exit_code == 0
    assert called == ["env-model"]


def test_starred_embeddings_custom_patterns(monkeypatch, tmpdir):
    called = []

    def fake_generate(db, token, model_name=None, *, force=False, verbose=False, patterns=None):
        called.append(patterns)

    monkeypatch.setattr(utils, "generate_starred_embeddings", fake_generate)

    db_path = str(Path(tmpdir) / "test.db")
    result = CliRunner().invoke(
        cli.cli, ["starred-embeddings", db_path, "--pattern", "BUILD.yml", "--pattern", "*.cfg"]
    )
    assert result.exit_code == 0
    assert called == [["BUILD.yml", "*.cfg"]]
