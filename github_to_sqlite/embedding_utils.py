"""Utilities for embedding table management and sqlite-vec loading."""
from __future__ import annotations

import sqlite3
from typing import Optional, Tuple, cast

import sqlite_utils

from . import config

EMBEDDING_DIM = config.config.embedding_dim

# Map database connections to whether sqlite-vec was successfully loaded
_SQLITE_VEC_CACHE: dict[sqlite3.Connection, bool] = {}


def _create_table_if_missing(
    db: sqlite_utils.Database,
    tables: set[str],
    name: str,
    columns: dict[str, type],
    pk: str | Tuple[str, ...],
    foreign_keys: Optional[list[tuple[str, str, str]]] = None,
) -> None:
    """Create *name* if it doesn't exist in *tables*."""
    if name not in tables:
        table = cast(sqlite_utils.db.Table, db[name])
        table.create(columns, pk=pk, foreign_keys=foreign_keys or [])


def _create_virtual_table_if_missing(db: sqlite_utils.Database, name: str, sql: str) -> None:
    """Create a virtual table using provided SQL if it does not already exist."""
    existing = set(db.table_names())
    if name not in existing:
        db.execute(sql)


def _maybe_load_sqlite_vec(db: sqlite_utils.Database) -> bool:
    """Attempt to load sqlite-vec extension, returning True if available."""
    conn = db.conn
    if conn in _SQLITE_VEC_CACHE:
        return _SQLITE_VEC_CACHE[conn]
    try:
        import sqlite_vec
    except ImportError:
        _SQLITE_VEC_CACHE[conn] = False
        return False
    try:
        sqlite_vec.load(conn)
    except (OSError, sqlite3.DatabaseError, AttributeError):
        _SQLITE_VEC_CACHE[conn] = False
    else:
        _SQLITE_VEC_CACHE[conn] = True
    return _SQLITE_VEC_CACHE[conn]


def ensure_embedding_tables(db: sqlite_utils.Database) -> None:
    """Create tables used for embedding storage if they do not exist."""
    using_vec = _maybe_load_sqlite_vec(db)

    tables = set(db.table_names())

    schema = [
        {
            "name": "repo_embeddings",
            "virtual": (
                """
                create virtual table if not exists repo_embeddings using vec0(
                    repo_id int primary key,
                    title_embedding float[{dim}],
                    description_embedding float[{dim}],
                    readme_embedding float[{dim}]
                )
                """
            ),
            "columns": {
                "repo_id": int,
                "title_embedding": bytes,
                "description_embedding": bytes,
                "readme_embedding": bytes,
            },
            "pk": "repo_id",
        },
        {
            "name": "readme_chunk_embeddings",
            "virtual": (
                """
                create virtual table if not exists readme_chunk_embeddings using vec0(
                    repo_id int,
                    chunk_index int,
                    chunk_text text,
                    embedding float[{dim}]
                )
                """
            ),
            "columns": {
                "repo_id": int,
                "chunk_index": int,
                "chunk_text": str,
                "embedding": bytes,
            },
            "pk": ("repo_id", "chunk_index"),
            "indexes": [
                "create index if not exists readme_chunk_idx on readme_chunk_embeddings(repo_id, chunk_index)"
            ],
        },
        {
            "name": "repo_build_files",
            "columns": {"repo_id": int, "file_path": str, "metadata": str},
            "pk": ("repo_id", "file_path"),
        },
        {
            "name": "repo_metadata",
            "columns": {"repo_id": int, "language": str, "directory_tree": str},
            "pk": "repo_id",
        },
    ]

    for spec in schema:
        name = cast(str, spec["name"])
        if name in tables:
            continue
        indexes = spec.get("indexes", [])
        if using_vec and spec.get("virtual"):
            _create_virtual_table_if_missing(
                db, name, cast(str, spec["virtual"]).format(dim=EMBEDDING_DIM)
            )
        else:
            fk = []
            if "repo_id" in spec.get("columns", {}) and "repos" in tables:
                fk.append(("repo_id", "repos", "id"))
            _create_table_if_missing(
                db,
                tables,
                name,
                cast(dict[str, type], spec["columns"]),
                pk=cast(str | Tuple[str, ...], spec["pk"]),
                foreign_keys=fk,
            )
        for sql in indexes:
            db.execute(cast(str, sql))
