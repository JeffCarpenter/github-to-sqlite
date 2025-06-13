import sys

import sqlite_utils

from github_to_sqlite import utils


def test_vector_to_blob_round_trip():
    import numpy as np

    vec = np.array([1.0, 2.0, 3.5], dtype="float32")
    blob = utils.vector_to_blob(vec)
    assert isinstance(blob, bytes)
    arr = np.frombuffer(blob, dtype="float32")
    assert arr.tolist() == [1.0, 2.0, 3.5]


def test_parse_build_file_json_and_toml(tmp_path):
    json_file = tmp_path / "package.json"
    json_file.write_text('{"name": "pkg", "author": "me"}')
    toml_file = tmp_path / "pyproject.toml"
    toml_file.write_text('name = "pkg"\nauthor = "you"')

    assert utils.parse_build_file(str(json_file)) == {"name": "pkg", "author": "me"}
    result = utils.parse_build_file(str(toml_file))
    assert result["name"] == "pkg"
    assert result["author"] == "you"


def test_directory_tree(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "file.txt").write_text("data")

    tree = utils.directory_tree(str(tmp_path))
    assert tree["."] == {"dirs": ["sub"], "files": []}
    assert tree["sub"] == {"dirs": [], "files": ["file.txt"]}


def test_maybe_load_sqlite_vec(monkeypatch):
    db = sqlite_utils.Database(memory=True)

    # No sqlite_vec module -> False
    sys.modules.pop("sqlite_vec", None)
    utils._SQLITE_VEC_LOADED = None
    assert utils._maybe_load_sqlite_vec(db) is False

    # Module with load that succeeds -> True
    dummy = type("M", (), {"load": lambda conn: None})
    monkeypatch.setitem(sys.modules, "sqlite_vec", dummy)
    utils._SQLITE_VEC_LOADED = None
    assert utils._maybe_load_sqlite_vec(db) is True
    utils._SQLITE_VEC_LOADED = None

def test_parse_build_file_invalid(tmp_path):
    bad = tmp_path / "bad.toml"
    bad.write_text("not : valid")
    assert utils.parse_build_file(str(bad)) == {}


def test_maybe_load_sqlite_vec_failure(monkeypatch):
    db = sqlite_utils.Database(memory=True)
    class Dummy:
        def load(self, conn):
            raise ValueError("boom")
    monkeypatch.setitem(sys.modules, "sqlite_vec", Dummy())
    utils._SQLITE_VEC_LOADED = None
    assert utils._maybe_load_sqlite_vec(db) is False
    utils._SQLITE_VEC_LOADED = None
