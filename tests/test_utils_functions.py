import sys
import sqlite3

import sqlite_utils

from github_to_sqlite import utils


def test_vector_to_blob_round_trip():
    import numpy as np

    vec = np.array([1.0, 2.0, 3.5], dtype="float32")
    blob = utils.vector_to_blob(vec)
    assert isinstance(blob, bytes)
    # Byte length should match the float32 representation
    assert len(blob) == vec.astype("float32").nbytes
    arr = np.frombuffer(blob, dtype="float32")
    assert arr.dtype == np.float32
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
    b = tmp_path / "b"
    a = tmp_path / "a"
    b.mkdir()
    a.mkdir()
    (a / "2.txt").write_text("data")
    (a / "1.txt").write_text("data")

    tree = utils.directory_tree(str(tmp_path))
    # Root should list directories sorted alphabetically
    assert tree["."]["dirs"] == ["a", "b"]
    assert tree["."]["files"] == []
    # Files should also be sorted
    assert tree["a"]["files"] == ["1.txt", "2.txt"]


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
            raise sqlite3.DatabaseError("boom")
    monkeypatch.setitem(sys.modules, "sqlite_vec", Dummy())
    utils._SQLITE_VEC_LOADED = None
    assert utils._maybe_load_sqlite_vec(db) is False
    utils._SQLITE_VEC_LOADED = None
